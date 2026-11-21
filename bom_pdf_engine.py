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
except ImportError:
    import fitz as pymupdf

STEEL_RX = re.compile(
    r"(?<![A-Z0-9])("
    r"W\d+\s*X\s*\d+(?:\.\d+)?|WT\d+\s*X\s*[\d.]+|S\d+\s*X\s*[\d.]+|HP\d+\s*X\s*\d+|"
    r"(?:HSS|TS)\s*\d+(?:-\d+/\d{1,2}|\.\d+)?\s*X\s*\d+(?:-\d+/\d{1,2}|\.\d+)?\s*X\s*\d+(?:/\d{1,2}|\.\d+)?(?![0-9/])|(?:HSS|TS)\s*\d+(?:-\d+/\d{1,2}|\.\d+)?\s*X\s*\d+(?:/\d{1,2}|\.\d+)?(?![0-9/])|"
    r"L\d+(?:\.\d+)?\s*X\s*\d+(?:\.\d+)?\s*X\s*[\d/.]+|C\d+\s*X\s*\d+\.\d+|MC\d+\s*X\s*\d+\.\d+|"
    r"(?:PIPE|STD\s*PIPE|XS\s*PIPE)\s*[\d/.]+(?:\s*[\"\u201d])?|"
    r"(?:BASE\s*PL|PLATE\s*WASHER\s*PL|CUSTOM\s*PL|PL|FB)\s*[\d/.-]+\s*[\"\u201d]?\s*X\s*[\d/.-]+(?:\s*[\"\u201d]?\s*X\s*[\d/.-]+)?"
    r")(?:#|\b|(?![0-9/]))"
)

DETAIL_RX = re.compile(r"\b(\d{1,2}\s*/\s*(?:SD-\d+|S-?\d+(?:\.\d+)?))\b")

def _cache_dir():
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    d = os.path.join(base, "BowmanMortonPricingSuite", "bom_cache_v5")
    os.makedirs(d, exist_ok=True)
    return d

from core.plan_world import PlanWorldModel, scan_world_ocr, round_structural_ft, parse_arch_scale, normalize_cad_text

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
        m2 = re.match(r"^(\d{1,2})(\d)/(\d+)$", tok)
        if m2 and int(m2.group(2)) < int(m2.group(3)) and int(m2.group(3)) in (2, 4, 8, 16, 32):
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
    ff_elevs = dict()
    any_elevs = dict()
    for pno in range(len(doc)):
        txt = doc.load_page(pno).get_text("text").upper()
        if not re.search(r"(?:T\.O\.\s*ROOF|TOP\s*OF\s*ROOF|FLOOR\s*\d|LEVEL\s*\d|PARKING)", txt):
            continue
        for ln in txt.splitlines():
            if "T.O.P" in ln or "T.O. WIN" in ln or "WINDOW" in ln:
                continue
            m = re.search(
                r"\b(TOP\s*OF\s*ROOF|T\.O\.\s*ROOF|ROOF|FLOOR\s*[1-9](?:\.0)?|LEVEL\s*[1-9](?:\s*FF)?|PARKING|FIRST\s*FLOOR|SECOND\s*FLOOR|THIRD\s*FLOOR|FOURTH\s*FLOOR)\b"
                r".*?(\d{1,3})\s*'\s*-\s*(\d{1,2})(?:\s+(\d+)/(\d+))?\s*\"",
                ln,
            )
            if m:
                lbl = re.sub(r"\s+", " ", m.group(1)).strip()
                ft, inch = float(m.group(2)), float(m.group(3))
                frac = (float(m.group(4)) / float(m.group(5))) if (m.group(4) and m.group(5) and float(m.group(5)) > 0) else 0.0
                val = ft + (inch + frac) / 12.0
                if 0.0 <= val <= 900.0:
                    base_k = re.sub(r"\s*FF$", "", lbl)
                    if "FF" in lbl or "ROOF" in lbl or "PARKING" in lbl or "FLOOR" in lbl:
                        ff_elevs[base_k] = val
                    any_elevs[base_k] = val
    use_map = ff_elevs if len(ff_elevs) >= 2 else any_elevs
    if len(use_map) < 2:
        return list()
    ordered = sorted(use_map.items(), key=lambda kv: kv.__getitem__(1))
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
    return [(it.__getitem__(0), it.__getitem__(1), it.__getitem__(4)) for it in scan_world_ocr(page, world_rect=clip_rect, dpi=dpi)]

def inspect_pdf_sheets(pdf_path):
    doc = pymupdf.open(pdf_path)
    sheets = []
    for pno in range(len(doc)):
        pg = doc.load_page(pno)
        sh = get_sheet_tag(pg)
        pw, ph = float(pg.rect.width), float(pg.rect.height)
        vp_len = sum(len(str(bstr).strip()) for bx0, by0, bx1, by1, bstr, *_ in pg.get_text("blocks") if bx0 < pw * 0.88 and by0 < ph * 0.94)
        mode = "Vector Text" if vp_len >= 30 else ("SHX Vector" if len(pg.get_drawings()) >= 40 else "Blank/Raster")
        if not sh and mode in ("SHX Vector", "Blank/Raster"):
            try:
                tb_hits = scan_world_ocr(pg, world_rect=pymupdf.Rect(pw * 0.84, ph * 0.82, pw, ph), dpi=180, multi_angle=False)
                tb_txt = normalize_cad_text(" ".join(str(it.__getitem__(4)) for it in tb_hits))
                m_tb = re.findall(r"\b(SD?-\d+(?:\.\d+)?|S\d+\.\d+|S-\d+|[ACMEPLG]-?\d+(?:\.\d+)?)\b", tb_txt)
                if m_tb:
                    sh = m_tb[-1]
            except Exception:
                pass
        is_struct = bool(sh and sh.startswith(("S-", "SD-", "S")) and not sh.startswith(("SUR", "SITE", "SPEC")))
        sheets.append({"page": pno + 1, "sheet": sh or f"P.{pno+1}", "mode": mode, "recommended": is_struct})
    return sheets

def _stitch_adjacent_ocr_tokens(raw_boxes):
    """Joins split SHX OCR fragments across horizontal, vertical, and 45-degree angled callouts."""
    out = list()
    short_toks = list()
    for it_rb in raw_boxes:
        bx0, by0, bx1, by1, t = it_rb.__getitem__(0), it_rb.__getitem__(1), it_rb.__getitem__(2), it_rb.__getitem__(3), it_rb.__getitem__(4)
        t_s = str(t or "").strip()
        if not t_s:
            continue
        out.append(((bx0 + bx1) * 0.5, (by0 + by1) * 0.5, t_s))
        if len(t_s) <= 14:
            short_toks.append((float(bx0), float(by0), float(bx1), float(by1), t_s))
    for i in range(len(short_toks)):
        ax0, ay0, ax1, ay1, at = short_toks.__getitem__(i)
        acx, acy = (ax0 + ax1) * 0.5, (ay0 + ay1) * 0.5
        for j in range(i + 1, len(short_toks)):
            bx0, by0, bx1, by1, bt = short_toks.__getitem__(j)
            bcx, bcy = (bx0 + bx1) * 0.5, (by0 + by1) * 0.5
            if math.hypot(bcx - acx, bcy - acy) <= 44.0:
                mx, my = (acx + bcx) * 0.5, (acy + bcy) * 0.5
                out.append((mx, my, f"{at}{bt}"))
                out.append((mx, my, f"{bt}{at}"))
    return out

def _try_ai_vision_sheet_extract(pg, sheet_lbl, catalog):
    """Optional cloud multimodal vision extraction when an API key is configured in shop_safeguards.json."""
    try:
        sg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shop_safeguards.json")
        if not os.path.exists(sg_path):
            return None
        with open(sg_path, "r", encoding="utf-8-sig") as f:
            api_key = str(json.load(f).get("ai_vision_api_key", "")).strip()
        if not api_key:
            return None
        import base64, urllib.request
        pix = pg.get_pixmap(dpi=160, alpha=False)
        b64_img = base64.b64encode(pix.tobytes("png")).decode("ascii")
        prompt = (
            "Extract all structural steel members (Beams, Columns, HSS & Pipe, Angles, Channels, Plates & Base Plates) "
            "from this engineering sheet as a JSON array of objects with keys: "
            "category, detail_ref, profile, qty, length_ft. Return ONLY valid JSON array."
        )
        if api_key.startswith("AIza"):
            url = f"https://googleapis.com{api_key}"
            body = json.dumps({"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/png", "data": b64_img}}]}]}).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=35) as resp:
                raw_out = json.loads(resp.read().decode("utf-8"))["candidates"][0]["content"]["parts"][0]["text"]
        else:
            url = "https://openai.com"
            body = json.dumps({
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}]}],
                "temperature": 0.0,
            }).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"})
            with urllib.request.urlopen(req, timeout=35) as resp:
                raw_out = json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]
        m_json = re.search(r"\[.*\]", raw_out, re.DOTALL)
        if not m_json:
            return None
        parsed = json.loads(m_json.group(0))
        out_rows = []
        for it in parsed:
            prof = normalize_cad_text(it.get("profile", "")).strip()
            if not prof:
                continue
            sk, uw = catalog.get(prof, ("beam", 26.0))
            out_rows.append({
                "category": str(it.get("category", "Beams")),
                "sheet": sheet_lbl,
                "detail_ref": str(it.get("detail_ref", "AI Vision")),
                "shape_key": sk,
                "profile": prof,
                "qty": max(1, int(float(it.get("qty", 1) or 1))),
                "length": max(0.5, float(it.get("length_ft", 20.0) or 20.0)),
                "unit_wt": uw,
                "plate_w": "12",
                "plate_thk": "",
            })
        return out_rows
    except Exception:
        return None

def extract_full_bom(pdf_path, matrix_path="steel_matrix.json", selected_pages=None, region_clip=None, use_native_ocr=True, sheet_scales=None, scan_mode=None, progress_cb=None, cancel_check=None):
    from core.vector_scan_engine import extract_vector_page_tokens, pair_vector_beam_length
    from core.ocr_scan_engine import extract_ocr_page_tokens
    from core.hybrid_scan_engine import extract_hybrid_page_tokens

    if scan_mode is None:
        scan_mode = "hybrid" if use_native_ocr else "vector"
    scan_mode = str(scan_mode).strip().lower()
    if scan_mode not in ("vector", "ocr", "hybrid"):
        scan_mode = "hybrid"

    t0 = time.perf_counter()
    fp = _file_fingerprint(pdf_path)
    wm_cal = PlanWorldModel(pdf_path)
    merged_scales = dict(wm_cal.sheet_scales)
    if isinstance(sheet_scales, dict):
        merged_scales.update({int(k): float(v) for k, v in sheet_scales.items() if float(v) > 0})
    sheet_scales = merged_scales
    sc_sig = hashlib.sha256(json.dumps(sorted(sheet_scales.items())).encode("utf-8")).hexdigest()[:10] if sheet_scales else "auto"
    sel_key = "all" if not selected_pages else "_".join(str(p) for p in sorted(selected_pages))
    cache_file = os.path.join(_cache_dir(), f"{fp}_{sel_key}_{sc_sig}_{scan_mode}.json")
    if region_clip is None and os.path.exists(cache_file):
        with open(cache_file, encoding="utf-8") as f:
            return json.load(f)["rows"], time.perf_counter() - t0, True

    tmp_dir = tempfile.gettempdir()
    try:
        cutoff_ts = time.time() - 86400.0
        for fn_t in os.listdir(tmp_dir):
            if fn_t.startswith("bm_work_") and fn_t.endswith(".pdf"):
                fp_t = os.path.join(tmp_dir, fn_t)
                if os.path.getmtime(fp_t) < cutoff_ts:
                    os.remove(fp_t)
    except Exception:
        pass
    local_pdf = os.path.join(tmp_dir, f"bm_work_{fp}.pdf")
    if not os.path.exists(local_pdf):
        shutil.copy2(pdf_path, local_pdf)

    catalog = load_catalog_lookup(matrix_path)
    doc = pymupdf.open(local_pdf)
    _st_cache = os.path.join(_cache_dir(), f"{fp}_stories.json")
    if os.path.exists(_st_cache):
        try:
            with open(_st_cache, "r", encoding="utf-8") as _sf:
                story_deltas = json.load(_sf)
        except Exception:
            story_deltas = extract_story_heights(doc)
    else:
        story_deltas = extract_story_heights(doc)
        try:
            with open(_st_cache, "w", encoding="utf-8") as _sf:
                json.dump(story_deltas, _sf)
        except Exception:
            pass

    extracted = {}
    col_groups = {}

    target_pages = [p for p in range(len(doc)) if not selected_pages or (p + 1) in selected_pages]
    tot_target = max(1, len(target_pages))
    for step_idx, pno in enumerate(target_pages, 1):
        if callable(cancel_check) and cancel_check():
            break
        pg = doc.load_page(pno)
        sh = get_sheet_tag(pg)
        if callable(progress_cb):
            try:
                progress_cb(step_idx, tot_target, sh or f"Pg {pno + 1}", len(extracted) + len(col_groups))
            except Exception:
                pass
        if not selected_pages and (sh == "CIVIL" or sh.startswith(("C", "A"))):
            continue

        items = []
        vert_words = []
        full_tb = (pg.get_text("text") or "").upper()
        raw_ocr_boxes = []

        if scan_mode == "vector":
            items, vert_words, full_tb = extract_vector_page_tokens(pg, clip_rect=region_clip)
        elif scan_mode == "ocr":
            ocr_dpi = 300 if region_clip is not None else 180
            items, vert_words, raw_ocr_boxes, ocr_sh = extract_ocr_page_tokens(pg, clip_rect=region_clip, dpi=ocr_dpi, multi_angle=True)
            if not sh and ocr_sh:
                sh = ocr_sh
        else:
            hyb_dpi = 300 if region_clip is not None else 180
            items, vert_words, raw_ocr_boxes, full_tb, ocr_sh = extract_hybrid_page_tokens(pg, clip_rect=region_clip, ocr_dpi=hyb_dpi)
            if not sh and ocr_sh:
                sh = ocr_sh

        if raw_ocr_boxes and region_clip is None:
            try:
                _ocr_box_cache = os.path.join(_cache_dir(), f"{fp}_pg{pno+1}_boxes.json")
                with open(_ocr_box_cache, "w", encoding="utf-8") as _bf:
                    json.dump([list(it_b) for it_b in raw_ocr_boxes], _bf)
            except Exception:
                pass

        if not items:
            continue

        sheet_lbl = sh or f"P.{pno+1}"
        all_txt = full_tb + " " + " ".join(t for _, _, t in items)
        if sheet_lbl == "S-0":
            continue
        if region_clip is None and scan_mode in ("ocr", "hybrid"):
            _ai_rows = _try_ai_vision_sheet_extract(pg, sheet_lbl, catalog)
            if _ai_rows:
                for _ar in _ai_rows:
                    _k = (_ar["sheet"], _ar["shape_key"], _ar["profile"], _ar["length"])
                    if _k not in extracted:
                        extracted[_k] = dict(_ar)
                    else:
                        extracted[_k]["qty"] += _ar["qty"]
                continue
        is_detail = sheet_lbl.startswith(("SD-", "SD", "S3."))
        pts_per_ft = get_sheet_calibration(pg, sheet_scales=sheet_scales)

        segs = []
        if not is_detail:
            _, _, segs = extract_vector_snap_nodes(pg, pts_per_ft)
            if not segs and scan_mode in ("ocr", "hybrid"):
                from core.plan_world import extract_raster_beam_segments, SheetWorldState
                segs = extract_raster_beam_segments(pg, pts_per_ft)
                if segs:
                    _st_r = SheetWorldState(pg, pno + 1, pts_per_ft=pts_per_ft)
                    _st_r.bay_segments = segs
                    pg._world_state_cache = _st_r

        det_pts = []
        example_pts = []
        for cx, cy, t in items:
            tu = str(t or "").upper()
            if any(k in tu for k in ("EXAMPLE", "FRAMING LEGEND", "FRAMINGLEGEND", "STEEL BEAM", "STEELBEAM")):
                example_pts.append((cx, cy))
            for dm in DETAIL_RX.finditer(t):
                det_pts.append((cx, cy, dm.group(1).replace(" ", "")))

        seen_callouts = []
        _pw_lim = float(pg.rect.width) * (0.72 if len(pg.get_text("words")) >= 30 else 0.88)
        for cx, cy, t in items:
            if not is_detail and region_clip is None and cx > _pw_lim:
                continue
            t = re.sub(r"\bW[IL](\d+X[\dJ]+(?:\.\d+)?)", r"W1\1", t)
            t = re.sub(r"\b(W\d+X\d+)J\b", r"\g<1>3", t)
            t = re.sub(r"\b(W\d+X)S(\d)\b", r"\g<1>5\2", t)
            t = re.sub(r"\b(W\d+X\d)B\b", r"\g<1>8", t)
            t = re.sub(r"(?<![A-Z])SS[AB](?=X\d+(?:\.\d+)?X\d+)", "HSS8", t)
            t = re.sub(r"(?<![A-Z])SS(?=\d+(?:\.\d+)?X\d+(?:\.\d+)?X\d+)", "HSS", t)
            t = re.sub(r"(?<![A-Z0-9])(4X2\.5X1/4|4X4X1/4|5X5X1/4|6X6X1/4|6X6X5/16|8X4X5/16|8X4X3/8)\b", r"HSS\1", t)
            t = re.sub(r"BENT\s*(HSS|PL|L|C|MC)", r"BENT \1", t)
            t = re.sub(r"\b(W|WT|S|HP|HSS|L|C|MC)\s+(\d)", r"\1\2", t)
            t = re.sub(r"(?<=\d)\s*[X×]\s*(?=\d)", "X", t)
            if any(w in t for w in ("EXAMPLE", "EXISTING", "EXIST.", "FRAMINGLEGEND", "STEELBEAM(")):
                continue
            if any(abs(cx - ex) <= 145.0 and abs(cy - ey) <= 45.0 for ex, ey in example_pts):
                continue
            for m in STEEL_RX.finditer(t):
                prof = re.sub(r"^TS(?=[0-9])", "HSS", re.sub(r"\s+", "", m.group(1)).rstrip("#.").strip())
                prof = re.sub(r"(\d+)-1/2(?=X)", r"\1.5", prof)
                prof = re.sub(r"(\d+)-1/4(?=X)", r"\1.25", prof)
                prof = re.sub(r"(\d+)-3/4(?=X)", r"\1.75", prof)
                if prof == "HSS4X2/2":
                    prof = "HSS4X2.5X1/4"
                prof = re.sub(r"^(HSS\d+(?:\.\d+)?X\d+(?:\.\d+)?)56$", r"\1X5/16", prof)
                prof = re.sub(r"^(HSS\d+(?:\.\d+)?X\d+(?:\.\d+)?)14$", r"\1X1/4", prof)
                prof = re.sub(r"^(HSS\d+(?:\.\d+)?X\d+(?:\.\d+)?)38$", r"\1X3/8", prof)
                prof = re.sub(r"^(HSS\d+(?:\.\d+)?X\d+(?:\.\d+)?)12$", r"\1X1/2", prof)
                if re.match(r"^W\d+X\d{3}$", prof) and prof not in catalog and prof.__getitem__(slice(0, -1)) in catalog:
                    prof = prof.__getitem__(slice(0, -1))
                if prof.startswith(("PL", "BASE", "PLATE", "CUSTOM", "FB")):
                    prof = re.sub(r"^(CUSTOMPL|PL|BASEPL|PLATEWASHERPL|FB)(?:34|94)(?=[\"X])", r"\g<1>3/4", prof)
                    prof = re.sub(r"^(CUSTOMPL|PL|BASEPL|PLATEWASHERPL|FB)1{1,2}4(?=[\"X])", r"\g<1>1/4", prof)
                    prof = re.sub(r"^(CUSTOMPL|PL|BASEPL|PLATEWASHERPL|FB)1{1,2}2(?=[\"X])", r"\g<1>1/2", prof)
                    prof = re.sub(r"X3/2X", "X3-1/2X", prof)
                    prof = re.sub(r"(\d)1/(2|4|8)(?=X|$)", r"\1-1/\2", prof)
                    prof = re.sub(r"(X10)1$", r"\1", prof)
                if any((p0 == prof or p0.startswith(prof) or prof.startswith(p0)) and math.hypot(cx - x0, cy - y0) < 68.0 for p0, x0, y0 in seen_callouts):
                    continue
                if is_detail and not prof.startswith(("PL", "CUSTOMPL", "BASEPL", "PLATEWASHERPL", "FB")):
                    continue
                seen_callouts.append((prof, cx, cy))

                near_txt = " ".join(t2 for x2, y2, t2 in items if abs(x2 - cx) <= 95.0 and abs(y2 - cy) <= 45.0)
                if any(k in near_txt for k in ("EXAMPLE", "FRAMINGLEGEND", "STEELBEAM(")):
                    continue
                is_bent = "BENT" in near_txt
                is_plate = prof.startswith(("PL", "BASE", "PLATE", "CUSTOM", "FB"))
                pl_dims = None

                in_cat = bool(is_plate or (prof in catalog))
                if is_plate:
                    uw, meas_len, thk_p, wid_p = parse_plate_spec(prof)
                    sk = "plate"
                    pl_dims = (thk_p, wid_p)
                elif prof in catalog:
                    sk, uw = catalog[prof]
                    meas_len = 20.0
                else:
                    if prof.startswith(("W", "WT", "S", "HP")):
                        mw_nom = re.match(r"^(?:WT|HP|W|S)\d+(?:\.\d+)?X(\d+(?:\.\d+)?)$", prof)
                        if not mw_nom:
                            continue
                        sk, uw = "beam", float(mw_nom.group(1))
                    elif prof.startswith(("HSS", "PIPE")):
                        sk, uw = "hss_tube", 20.0
                        mh = re.match(r"HSS(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)X(\d+)/(\d+)", prof)
                        if mh and float(mh.group(4)) > 0:
                            b_in, h_in = float(mh.group(1)), float(mh.group(2))
                            t_in = float(mh.group(3)) / float(mh.group(4))
                            uw = round(max(1.5, 2.0 * (b_in + h_in - 2.0 * t_in) * t_in * 3.4), 2)

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
                is_col = (not is_detail and not is_bent and (sk == "hss_tube" or "SMFCOL" in col_tag_txt.replace(" ", "") or "WFCOL" in col_tag_txt.replace(" ", "") or "COLUMN" in col_tag_txt))
                if is_col:
                    st_i = 0
                    if "LEVEL 1 WALL" in all_txt or "FIRST FLOOR WALL" in all_txt or "1ST FLOOR WALL" in all_txt:
                        st_i = 0
                    elif "LEVEL 2 WALL" in all_txt or "SECOND FLOOR WALL" in all_txt or "2ND FLOOR WALL" in all_txt:
                        st_i = 1
                    elif "LEVEL 3 WALL" in all_txt or "THIRD FLOOR WALL" in all_txt or "3RD FLOOR WALL" in all_txt:
                        st_i = 2
                    elif "ROOF FRAMING" in all_txt:
                        st_i = max(0, len(story_deltas) - 1) if story_deltas else 2
                    elif "THIRD FLOOR" in all_txt or "LEVEL 3" in all_txt or "FLOOR 03" in all_txt:
                        st_i = 2
                    elif "PARKING FLOOR" in all_txt or "SECOND FLOOR" in all_txt or "LEVEL 2" in all_txt or "FLOOR 02" in all_txt:
                        st_i = 1
                    col_h = story_deltas.__getitem__(min(st_i, len(story_deltas) - 1)) if story_deltas else (9.0 if st_i == 0 else (14.33 if st_i == 1 else (10.0 if st_i == 2 else 11.83)))
                    ck = (sheet_lbl, prof, col_h)
                    col_groups.setdefault(ck, {"sheet": sheet_lbl, "dets": set(), "sk": sk, "prof": prof, "len": col_h, "uw": uw, "qty": 0, "in_cat": in_cat})
                    col_groups[ck]["qty"] += 1
                    if near_det:
                        col_groups[ck]["dets"].add(near_det)
                    continue

                span_verified = False
                if not is_plate and segs:
                    is_vert_lbl = any(
                        (prof in re.sub(r"^TS(?=[0-9])", "HSS", normalize_cad_text(w_txt))
                         or re.sub(r"^TS(?=[0-9])", "HSS", normalize_cad_text(w_txt)) in prof)
                        and math.hypot(cx - vx, cy - vy) < 18.0
                        for vx, vy, w_txt in vert_words
                    )
                    from core.plan_world import SheetWorldState
                    _st = getattr(pg, "_world_state_cache", None)
                    if _st is None or abs(float(getattr(_st, "pts_per_ft", 0.0)) - float(pts_per_ft)) > 0.1:
                        _st = SheetWorldState(pg, pno + 1, pts_per_ft=pts_per_ft)
                        pg._world_state_cache = _st
                    peer_pts = [(ix, iy) for ix, iy, itxt in items if STEEL_RX.search(itxt)]
                    attached = _st.attach_beam_to_callout(cx, cy, is_horiz=(not is_vert_lbl), max_perp_pts=30.0, max_span_ft=36.0, peer_callouts=peer_pts)
                    if attached is None:
                        attached = _st.attach_beam_to_callout(cx, cy, is_horiz=(not is_vert_lbl), max_perp_pts=45.0, max_span_ft=36.0, peer_callouts=peer_pts)
                    if attached is None:
                        attached = _st.attach_beam_to_callout(cx, cy, is_horiz=bool(is_vert_lbl), max_perp_pts=16.0, max_span_ft=36.0, peer_callouts=peer_pts)
                    if attached is not None:
                        meas_len = float(attached.__getitem__(4)) if isinstance(attached, (tuple, list)) else float(attached)
                        span_verified = True
                if not is_plate and not span_verified:
                    best_dim_d = 130.0
                    for dx2, dy2, dt2 in items:
                        mdim = re.search(r"\b(\d{1,2})\s*'\s*-?\s*(\d{1,2})\s*\"", dt2)
                        if mdim:
                            cand_ft = round_structural_ft(float(mdim.group(1)) + float(mdim.group(2)) / 12.0)
                            dd2 = math.hypot(cx - dx2, cy - dy2)
                            if 4.0 <= cand_ft <= 48.0 and dd2 < best_dim_d:
                                best_dim_d = dd2
                                meas_len = cand_ft
                                span_verified = True
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
                        "category": cat, "sheet": sheet_lbl, "detail_ref": near_det or ("Plan Span" if (is_plate or span_verified) else "Verify Span (Est. 20')"),
                        "shape_key": sk, "profile": prof, "qty": 0, "length": meas_len, "unit_wt": uw,
                        "plate_w": str(pl_dims.__getitem__(1)) if pl_dims else "12",
                        "plate_thk": str(pl_dims.__getitem__(0)) if pl_dims else "",
                        "in_catalog": in_cat,
                    }
                extracted[key]["qty"] += max(1, qty_add)

    rows = list(extracted.values())
    for ck, cg in col_groups.items():
        rows.append({
            "category": "Columns", "sheet": cg["sheet"],
            "detail_ref": ", ".join(sorted(cg["dets"])) if cg["dets"] else "Typ. / Plan",
            "shape_key": cg["sk"], "profile": cg["prof"], "qty": cg["qty"],
            "length": cg["len"], "unit_wt": cg["uw"], "plate_w": "12", "plate_thk": "", "in_catalog": cg.get("in_cat", True),
        })

    if region_clip is None:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"rows": rows}, f, indent=2)
    return rows, time.perf_counter() - t0, False
