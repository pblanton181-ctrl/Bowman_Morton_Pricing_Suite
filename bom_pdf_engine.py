import os
import re
import json
import math
import time
import hashlib
import shutil
import tempfile
import subprocess

try:
    import pymupdf
from core.plan_world import PlanWorldModel, scan_world_ocr, round_structural_ft, parse_arch_scale
except ImportError:
    import fitz as pymupdf

STEEL_RX = re.compile(
    r"(?<![A-Z0-9])("
    r"W\d+X\d+|WT\d+X[\d.]+|S\d+X[\d.]+|HP\d+X\d+|"
    r"HSS\d+X\d+X[\d/.]+|HSS\d+X[\d/.]+|"
    r"L\d+X\d+X[\d/.]+|C\d+X[\d.]+|MC\d+X[\d.]+|PIPE\s*[\d/.]+|"
    r"(?:BASE\s*PL|PLATE\s*WASHER\s*PL|CUSTOM\s*PL|PL|FB)\s*[\d/.-]+\s*[\"\u201d]?\s*X\s*[\d/.-]+(?:\s*[\"\u201d]?\s*X\s*[\d/.-]+)?"
    r")(?![0-9/])"
)

DETAIL_RX = re.compile(r"\b(\d{1,2}\s*/\s*(?:SD-\d+|S-?\d+(?:\.\d+)?))\b")

def normalize_cad_text(raw):
    t = str(raw).upper().replace("BENTIHSS", "BENT HSS")
    t = re.sub(r"\b(W|HSS|L|C|MC|WT|S|HP|PIPE)\s+(?=\d)", r"\1", t)
    t = re.sub(r"\s*([X/])\s*", r"\1", t)
    t = re.sub(r"(?<=\d)O(?=\d)", "0", t)
    t = re.sub(r"(?<=[WHSLC])O(?=\d)", "0", t)
    return t

def _cache_dir():
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    d = os.path.join(base, "BowmanMortonPricingSuite", "bom_cache_v2")
    os.makedirs(d, exist_ok=True)
    return d

def _file_fingerprint(path):
    st = os.stat(path)
    h = hashlib.sha256()
    h.update(f"{st.st_size}:{int(st.st_mtime)}".encode("utf-8"))
    with open(path, "rb") as f:
        h.update(f.read(65536))
    return h.hexdigest()[:24]

def load_catalog_lookup(matrix_path="steel_matrix.json"):
    lookup = {}
    if not os.path.exists(matrix_path):
        return lookup
    with open(matrix_path, encoding="utf-8") as f:
        data = json.load(f)
    for sk, items in data.items():
        for entry in items:
            des = normalize_cad_text(entry.get("designation", "")).strip()
            wt = float(entry.get("weight_steel_lb_ft", entry.get("weight_per_ft", entry.get("weight", 0.0))))
            if des and wt > 0:
                lookup[des] = (sk, wt)
    return lookup

def parse_plate_spec(raw_pl):
    def _frac(tok):
        tok = tok.strip().replace('"', "").replace("\u201d", "")
        if not tok:
            return 0.0
        m1 = re.match(r"^(\d+)-(\d+)/(\d+)$", tok)
        if m1 and float(m1.group(3)) > 0:
            return float(m1.group(1)) + float(m1.group(2)) / float(m1.group(3))
        m2 = re.match(r"^(\d)(\d)/(\d+)$", tok)
        if m2 and int(m2.group(2)) < int(m2.group(3)):
            return float(m2.group(1)) + float(m2.group(2)) / float(m2.group(3))
        try:
            if "/" in tok:
                a, b = tok.split("/", 1)
                return float(a) / float(b) if float(b) > 0 else 0.0
            return float(tok)
        except ValueError:
            return 0.0

    cleaned = re.sub(r"^(?:BASE\s*PL|PLATE\s*WASHER\s*PL|CUSTOM\s*PL|PL|FB)\s*", "", raw_pl).strip()
    nums = [_frac(pt) for pt in cleaned.split("X") if pt.strip()]
    t_raw, w_raw, l_raw = (nums + [0.0, 0.0, 0.0])[:3]
    thk = t_raw if t_raw > 0 else 0.5
    wid = w_raw if w_raw > 0 else 6.0
    ln = l_raw if l_raw > 0 else 12.0
    uw = round((thk * (wid / 12.0)) * 40.8, 2)
    return max(0.5, uw), max(0.25, round(ln / 12.0, 2)), thk, wid

def extract_story_heights(doc):
    elevs = {}
    for pno in range(len(doc)):
        txt = doc.load_page(pno).get_text("text").upper()
        if not re.search(r"(?:T\.O\.\s*ROOF|FLOOR\s*\d|LEVEL\s*\d|PARKING)", txt):
            continue
        for ln in txt.splitlines():
            m = re.search(
                r"\b(T\.O\.\s*ROOF|ROOF|FLOOR\s*[1-9](?:\.0)?|LEVEL\s*[1-9]|PARKING|FIRST\s*FLOOR|SECOND\s*FLOOR|THIRD\s*FLOOR|FOURTH\s*FLOOR)\b"
                r".*?(\d{1,3})\s*'\s*-\s*(\d{1,2})(?:\s+(\d+)/(\d+))?\s*\"",
                ln,
            )
            if m:
                lbl = re.sub(r"\s+", " ", m.group(1)).strip()
                ft, inch = float(m.group(2)), float(m.group(3))
                frac = (float(m.group(4)) / float(m.group(5))) if (m.group(4) and m.group(5) and float(m.group(5)) > 0) else 0.0
                val = ft + (inch + frac) / 12.0
                if 0.0 <= val <= 900.0:
                    elevs[lbl] = val
    if len(elevs) < 2:
        return []
    ordered = sorted(elevs.items(), key=lambda kv: kv.__getitem__(1))
    vals = [v for _, v in ordered]
    return [round(b - a, 2) for a, b in zip(vals, vals.__getitem__(slice(1, None))) if 6.0 <= (b - a) <= 35.0]

def get_sheet_tag(page):
    pw, ph = float(page.rect.width), float(page.rect.height)
    tb_all = [str(bstr) for bx0, by0, bx1, by1, bstr, *_ in page.get_text("blocks") if bx0 > pw * 0.72]
    tb_str = " ".join(tb_all).upper()
    if any(k in tb_str for k in ("CIVIL", "TOPOGRAPHIC", "UTILITY", "DRAINAGE", "PUBLIC WORKS", "SWPPP")):
        return "CIVIL"
    corner = [str(bstr) for bx0, by0, bx1, by1, bstr, *_ in page.get_text("blocks") if bx0 > pw * 0.84 and by0 > ph * 0.78]
    m_c = re.findall(r"\b(SD-\d+|S-\d+|S\d+\.\d+|A-?\d+(?:\.\d+)?|C-?\d+)\b", " ".join(corner).upper())
    if m_c:
        return m_c[-1]
    m = re.findall(r"\b(SD-\d+|S-\d+|S\d+\.\d+|A-?\d+(?:\.\d+)?|C-?\d+)\b", tb_str)
    return m[-1] if m else ""

def parse_arch_scale(txt):
    cleaned = re.sub(r"\d+\s*[X×]\s*\d+\s*SHEET\s*:?\s*1\s*/\s*8\s*\"\s*=\s*1\s*'\s*-?\s*0\s*\"?", " ", str(txt), flags=re.IGNORECASE)
    m = re.search(r"(\d+)\s*/\s*(\d+)\s*\"\s*=\s*1\s*'\s*-?\s*0", cleaned)
    if m and float(m.group(2)) > 0:
        return (float(m.group(1)) / float(m.group(2))) * 72.0
    m2 = re.search(r"\b([1-3])\s*\"\s*=\s*1\s*'\s*-?\s*0", cleaned)
    return float(m2.group(1)) * 72.0 if m2 else 18.0

def round_structural_ft(raw_ft):
    """Single shared 1/4-ft (3-inch) rounding rule for both BOM extraction and Measure tool."""
    return round(float(raw_ft) * 4.0) / 4.0

def get_sheet_calibration(page, sheet_scales=None):
    pno = int(getattr(page, "number", 0)) + 1
    if isinstance(sheet_scales, dict) and pno in sheet_scales and float(sheet_scales[pno]) > 0:
        return float(sheet_scales[pno])
    from core.plan_world import SheetWorldState
    return SheetWorldState(page, pno).pts_per_ft

def extract_vector_snap_nodes(page, pts_per_ft=18.0):
    from core.plan_world import SheetWorldState
    st = SheetWorldState(page, int(getattr(page, "number", 0)) + 1, pts_per_ft=pts_per_ft)
    return st.snap_endpoints, st.snap_midpoints, st.bay_segments

def scan_region_windows_native_ocr(page, clip_rect=None, dpi=200):
    return [(wx0, wy0, txt) for wx0, wy0, wx1, wy1, txt in scan_world_ocr(page, world_rect=clip_rect, dpi=dpi)]

def inspect_pdf_sheets(pdf_path):
    doc = pymupdf.open(pdf_path)
    sheets = []
    for pno in range(len(doc)):
        pg = doc.load_page(pno)
        sh = get_sheet_tag(pg)
        pw, ph = float(pg.rect.width), float(pg.rect.height)
        vp_len = sum(len(str(bstr).strip()) for bx0, by0, bx1, by1, bstr, *_ in pg.get_text("blocks") if bx0 < pw * 0.88 and by0 < ph * 0.94)
        mode = "Vector Text" if vp_len >= 30 else ("SHX Vector" if len(pg.get_drawings()) >= 40 else "Blank/Raster")
        is_struct = sh.startswith(("S-", "SD-", "S")) and not sh.startswith(("SUR", "SITE"))
        sheets.append({"page": pno + 1, "sheet": sh or f"P.{pno+1}", "mode": mode, "recommended": is_struct})
    return sheets

def extract_full_bom(pdf_path, matrix_path="steel_matrix.json", selected_pages=None, region_clip=None, use_native_ocr=True, sheet_scales=None):
    t0 = time.perf_counter()
    fp = _file_fingerprint(pdf_path)
    sel_key = "all" if not selected_pages else "_".join(str(p) for p in sorted(selected_pages))
    cache_file = os.path.join(_cache_dir(), f"{fp}_{sel_key}.json")
    if region_clip is None and os.path.exists(cache_file):
        with open(cache_file, encoding="utf-8") as f:
            return json.load(f)["rows"], time.perf_counter() - t0, True

    local_pdf = os.path.join(tempfile.gettempdir(), f"bm_work_{fp}.pdf")
    if not os.path.exists(local_pdf):
        shutil.copy2(pdf_path, local_pdf)

    catalog = load_catalog_lookup(matrix_path)
    doc = pymupdf.open(local_pdf)
    story_deltas = extract_story_heights(doc)

    extracted = {}
    col_groups = {}

    for pno in range(len(doc)):
        if selected_pages and (pno + 1) not in selected_pages:
            continue
        pg = doc.load_page(pno)
        sh = get_sheet_tag(pg)
        if not selected_pages and (sh == "CIVIL" or sh.startswith(("C", "A"))):
            continue

        pw, ph = float(pg.rect.width), float(pg.rect.height)
        mx, my = pw * 0.72, ph * 0.94
        full_tb = pg.get_text("text").upper()
        items = []
        lines_grp = {}
        vert_words = []
        for wx0, wy0, wx1, wy1, wstr, bno, lno, wno in pg.get_text("words"):
            if wx0 < mx and wy0 < my:
                nw = normalize_cad_text(wstr)
                cx_w, cy_w = (wx0 + wx1) * 0.5, (wy0 + wy1) * 0.5
                items.append((cx_w, cy_w, nw))
                if (wy1 - wy0) > (wx1 - wx0) * 1.35:
                    vert_words.append((cx_w, cy_w, nw))
                lines_grp.setdefault((bno, lno), []).append((wx0, wy0, wx1, wy1, nw))
        for (bno, lno), wlist in lines_grp.items():
            if len(wlist) > 1:
                lx0 = min(w.__getitem__(0) for w in wlist)
                ly0 = min(w.__getitem__(1) for w in wlist)
                lx1 = max(w.__getitem__(2) for w in wlist)
                ly1 = max(w.__getitem__(3) for w in wlist)
                ltxt = " ".join(w.__getitem__(4) for w in wlist)
                if not STEEL_RX.search(ltxt) or any(k in ltxt for k in ("TREAD", "0'-6", "BASE", "PL", "WASHER", "CUSTOM", "FB")):
                    items.append(((lx0 + lx1) * 0.5, (ly0 + ly1) * 0.5, ltxt))

        if sum(len(t) for _, _, t in items) < 30 and use_native_ocr and (selected_pages or sh.startswith("S")) and len(pg.get_drawings()) >= 40:
            items = scan_region_windows_native_ocr(pg, clip_rect=region_clip)

        if not items:
            continue

        sheet_lbl = sh or f"P.{pno+1}"
        all_txt = full_tb + " " + " ".join(t for _, _, t in items)
        if sheet_lbl in ("S-0", "S-1") or "SHEET S-1" not in all_txt and "GENERAL STRUCTURAL NOTES" in all_txt:
            continue
        is_detail = sheet_lbl.startswith("SD")
        pts_per_ft = get_sheet_calibration(pg, sheet_scales=sheet_scales)

        segs = []
        if not is_detail:
            _, _, segs = extract_vector_snap_nodes(pg, pts_per_ft)

        det_pts = []
        for cx, cy, t in items:
            for dm in DETAIL_RX.finditer(t):
                det_pts.append((cx, cy, dm.group(1).replace(" ", "")))

        seen_callouts = []
        for cx, cy, t in items:
            if any(w in t for w in ("EXAMPLE", "EXISTING", "EXIST.")):
                continue
            if is_detail and not t.startswith(("L", "PL", "BASE", "PLATE", "CUSTOM", "FB", "C", "MC")):
                continue
            for m in STEEL_RX.finditer(t):
                prof = m.group(1).strip()
                if any(p0 == prof and math.hypot(cx - x0, cy - y0) < 5.0 for p0, x0, y0 in seen_callouts):
                    continue
                seen_callouts.append((prof, cx, cy))

                near_txt = " ".join(t2 for x2, y2, t2 in items if abs(x2 - cx) <= 85.0 and abs(y2 - cy) <= 35.0)
                is_bent = "BENT" in near_txt
                is_plate = prof.startswith(("PL", "BASE", "PLATE", "CUSTOM", "FB"))
                pl_dims = None

                if is_plate:
                    uw, meas_len, thk_p, wid_p = parse_plate_spec(prof)
                    sk = "plate"
                    pl_dims = (thk_p, wid_p)
                elif prof in catalog:
                    sk, uw = catalog[prof]
                    meas_len = 20.0
                else:
                    if prof.startswith(("HSS", "PIPE")):
                        sk, uw = "hss_tube", 20.0
                    elif prof.startswith("L"):
                        sk, uw = "angle", 20.0
                    elif prof.startswith(("C", "MC")):
                        sk, uw = "channel", 15.3
                    else:
                        sk, uw = "beam", 28.0
                    meas_len = 20.0

                near_det = ""
                best_dd = 110.0
                for dx, dy, dlbl in det_pts:
                    dd = math.hypot(cx - dx, cy - dy)
                    if dd < best_dd:
                        best_dd, near_det = dd, dlbl

                col_tag_txt = " ".join(t2 for x2, y2, t2 in items if abs(x2 - cx) <= 38.0 and abs(y2 - cy) <= 20.0)
                is_col = (not is_detail and not is_bent and (sk == "hss_tube" or "SMF" in col_tag_txt or "WF COL" in col_tag_txt))
                if is_col:
                    st_i = 0
                    if "ROOF FRAMING" in all_txt:
                        st_i = 3
                    elif "THIRD FLOOR" in all_txt or "FLOOR 03" in all_txt:
                        st_i = 2
                    elif "PARKING FLOOR" in all_txt or "SECOND FLOOR" in all_txt or "FLOOR 02" in all_txt:
                        st_i = 1
                    col_h = story_deltas.__getitem__(min(st_i, len(story_deltas) - 1)) if story_deltas else (9.0 if st_i == 0 else (14.33 if st_i == 1 else (10.0 if st_i == 2 else 11.83)))
                    ck = (sheet_lbl, prof, col_h)
                    col_groups.setdefault(ck, {"sheet": sheet_lbl, "dets": set(), "sk": sk, "prof": prof, "len": col_h, "uw": uw, "qty": 0})
                    col_groups[ck]["qty"] += 1
                    if near_det:
                        col_groups[ck]["dets"].add(near_det)
                    continue

                if not is_plate and segs:
                    is_vert_lbl = any(w_txt == prof and math.hypot(cx - vx, cy - vy) < 6.0 for vx, vy, w_txt in vert_words)
                    from core.plan_world import SheetWorldState
                    _st = getattr(pg, "_world_state_cache", None)
                    if _st is None:
                        _st = SheetWorldState(pg, pno + 1, pts_per_ft=pts_per_ft)
                        pg._world_state_cache = _st
                    attached = _st.attach_beam_to_callout(cx, cy, is_horiz=(not is_vert_lbl), max_perp_pts=9.5, max_span_ft=34.0)
                    if attached is not None:
                        meas_len = attached.__getitem__(4)
                elif sk == "angle" and is_detail:
                    if "TREAD" in near_txt and len(t) <= 12:
                        continue
                    meas_len = 0.5 if ("0'-6" in near_txt or "TREAD" in near_txt) else 4.0

                m_mult = re.search(r"(?:\(\s*(\d{1,2})\s*\)|\b(\d{1,2})\s*[X-]\s*)$", t[:m.start()])
                qty_add = 72 if (sk == "angle" and "EA SIDE OF TREAD" in near_txt) else (int(m_mult.group(1) or m_mult.group(2)) if m_mult else 1)

                cat = (
                    "Plates & Base Plates" if sk == "plate" else
                    "Angles" if sk == "angle" else
                    "Channels" if sk == "channel" else
                    "HSS & Pipe" if sk == "hss_tube" else
                    "Beams"
                )
                key = (sheet_lbl, sk, prof, meas_len)
                if key not in extracted:
                    extracted[key] = {
                        "category": cat, "sheet": sheet_lbl, "detail_ref": near_det or "Typ. / Plan",
                        "shape_key": sk, "profile": prof, "qty": 0, "length": meas_len, "unit_wt": uw,
                        "plate_w": str(pl_dims.__getitem__(1)) if pl_dims else "12",
                        "plate_thk": str(pl_dims.__getitem__(0)) if pl_dims else "",
                    }
                extracted[key]["qty"] += max(1, qty_add)

    rows = list(extracted.values())
    for ck, cg in col_groups.items():
        rows.append({
            "category": "Columns", "sheet": cg["sheet"],
            "detail_ref": ", ".join(sorted(cg["dets"])) if cg["dets"] else "Typ. / Plan",
            "shape_key": cg["sk"], "profile": cg["prof"], "qty": cg["qty"],
            "length": cg["len"], "unit_wt": cg["uw"], "plate_w": "12", "plate_thk": "",
        })

    if region_clip is None:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"rows": rows}, f, indent=2)
    return rows, time.perf_counter() - t0, False
