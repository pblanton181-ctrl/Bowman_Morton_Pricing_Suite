# -*- coding: utf-8 -*-
"""
Dedicated Engine 2: High-DPI Raster & SHX Optical Character Recognition (OCR) Engine.
Covers orthogonal CAD orientations (0 deg, -90 deg), normalizes AutoCAD SHX stroke-font
character swaps, stitches strictly adjacent horizontal/vertical fragments (<=14pt gap),
and deduplicates overlapping multi-angle hits without creating phantom mid-room duplicates.
"""
import math
import re
import pymupdf
from core.plan_world import scan_world_ocr, normalize_cad_text


def _normalize_ocr_cad_noise(raw_txt):
    t = normalize_cad_text(raw_txt)
    if not t:
        return ""
    t = re.sub(r"BENT\s*(HSS|PL|L|C|MC)", r"BENT \1", t)
    t = re.sub(r"\b(W|WT|S|HP|HSS|L|C|MC|PL|FB|PIPE)\s+(\d)", r"\1\2", t)
    t = re.sub(r"(?<=\d)\s*[X\u00d7*]\s*(?=\d)", "X", t)
    t = re.sub(r"\b(HSS|W|L|C|PL)(\d+)O\b", r"\g<1>\g<2>0", t)
    t = re.sub(r"\bW[IL](\d+X[\dJ]+(?:\.\d+)?)", r"W1\1", t)
    t = re.sub(r"\b(W\d+X\d+)J\b", r"\g<1>3", t)
    t = re.sub(r"(?<![A-Z])SS[AB](?=X\d+(?:\.\d+)?X\d+)", "HSS8", t)
    t = re.sub(r"(?<![A-Z])SS(?=\d+(?:\.\d+)?X\d+(?:\.\d+)?X\d+)", "HSS", t)
    t = re.sub(r"(?<![A-Z0-9])(4X2\.5X1/4|4X4X1/4|5X5X1/4|6X6X1/4|6X6X5/16|8X4X5/16|8X4X3/8)\b", r"HSS\1", t)
    t = re.sub(r"\b(HSS\d+(?:\.\d+)?X\d+(?:\.\d+)?)56\b", r"\1X5/16", t)
    t = re.sub(r"\b(HSS\d+(?:\.\d+)?X\d+(?:\.\d+)?)14\b", r"\1X1/4", t)
    t = re.sub(r"\b(HSS\d+(?:\.\d+)?X\d+(?:\.\d+)?)38\b", r"\1X3/8", t)
    t = re.sub(r"\b(HSS\d+(?:\.\d+)?X\d+(?:\.\d+)?)12\b", r"\1X1/2", t)
    t = re.sub(r"\b(CUSTOMPL|PL|BASEPL|PLATEWASHERPL|FB)(?:34|94)(?=[\"X])", r"\g<1>3/4", t)
    t = re.sub(r"\b(S\d+)\.L\b", r"\1.1", re.sub(r"\b(S\d+)\.O\b", r"\1.0", t))
    return t.strip()


def _emit_adjacent_h_groups(cluster, items):
    if len(cluster) <= 1:
        return
    cluster.sort(key=lambda b: b.__getitem__(0))
    grp = [cluster.__getitem__(0)]
    for nxt in cluster[1:]:
        if (nxt.__getitem__(0) - grp[-1].__getitem__(2)) <= 14.0:
            grp.append(nxt)
        else:
            if len(grp) > 1:
                merged = _normalize_ocr_cad_noise("".join(g.__getitem__(8) for g in grp))
                if merged and not any(g.__getitem__(8) == merged for g in grp):
                    items.append(((grp.__getitem__(0).__getitem__(0) + grp[-1].__getitem__(2)) * 0.5, (grp.__getitem__(0).__getitem__(1) + grp[-1].__getitem__(3)) * 0.5, merged))
            grp = [nxt]
    if len(grp) > 1:
        merged = _normalize_ocr_cad_noise("".join(g.__getitem__(8) for g in grp))
        if merged and not any(g.__getitem__(8) == merged for g in grp):
            items.append(((grp.__getitem__(0).__getitem__(0) + grp[-1].__getitem__(2)) * 0.5, (grp.__getitem__(0).__getitem__(1) + grp[-1].__getitem__(3)) * 0.5, merged))


def _emit_adjacent_v_groups(cluster, items, vert_words):
    if len(cluster) <= 1:
        return
    cluster.sort(key=lambda b: b.__getitem__(1))
    grp = [cluster.__getitem__(0)]
    for nxt in cluster[1:]:
        if (nxt.__getitem__(1) - grp[-1].__getitem__(3)) <= 22.0:
            grp.append(nxt)
        else:
            if len(grp) > 1:
                merged_tb = _normalize_ocr_cad_noise("".join(g.__getitem__(8) for g in grp))
                merged_bt = _normalize_ocr_cad_noise("".join(g.__getitem__(8) for g in reversed(grp)))
                vcx = (grp.__getitem__(0).__getitem__(0) + grp[-1].__getitem__(2)) * 0.5
                vcy = (grp.__getitem__(0).__getitem__(1) + grp[-1].__getitem__(3)) * 0.5
                if merged_tb and not any(g.__getitem__(8) == merged_tb for g in grp):
                    items.append((vcx, vcy, merged_tb))
                    vert_words.append((vcx, vcy, merged_tb))
                if merged_bt and merged_bt != merged_tb and not any(g.__getitem__(8) == merged_bt for g in grp):
                    items.append((vcx, vcy, merged_bt))
                    vert_words.append((vcx, vcy, merged_bt))
            grp = [nxt]
    if len(grp) > 1:
        merged_tb = _normalize_ocr_cad_noise("".join(g.__getitem__(8) for g in grp))
        merged_bt = _normalize_ocr_cad_noise("".join(g.__getitem__(8) for g in reversed(grp)))
        vcx = (grp.__getitem__(0).__getitem__(0) + grp[-1].__getitem__(2)) * 0.5
        vcy = (grp.__getitem__(0).__getitem__(1) + grp[-1].__getitem__(3)) * 0.5
        if merged_tb and not any(g.__getitem__(8) == merged_tb for g in grp):
            items.append((vcx, vcy, merged_tb))
            vert_words.append((vcx, vcy, merged_tb))
        if merged_bt and merged_bt != merged_tb and not any(g.__getitem__(8) == merged_bt for g in grp):
            items.append((vcx, vcy, merged_bt))
            vert_words.append((vcx, vcy, merged_bt))


def stitch_ocr_boxes(raw_boxes):
    """Deduplicate multi-angle OCR hits and stitch strictly adjacent horizontal & vertical steel callouts."""
    if not raw_boxes:
        return [], []

    dedup_boxes = []
    for _row5 in raw_boxes:
        wx0, wy0, wx1, wy1, txt = _row5.__getitem__(0), _row5.__getitem__(1), _row5.__getitem__(2), _row5.__getitem__(3), _row5.__getitem__(4)
        nt = _normalize_ocr_cad_noise(txt)
        if not nt:
            continue
        cx, cy = (wx0 + wx1) * 0.5, (wy0 + wy1) * 0.5
        if any(d_txt == nt and math.hypot(cx - d_cx, cy - d_cy) < 16.0 for _, _, _, _, d_cx, d_cy, _, _, d_txt in dedup_boxes):
            continue
        w, h = max(1.0, wx1 - wx0), max(1.0, wy1 - wy0)
        dedup_boxes.append((wx0, wy0, wx1, wy1, cx, cy, w, h, nt))

    items = [(cx, cy, nt) for _, _, _, _, cx, cy, _, _, nt in dedup_boxes]
    vert_words = [(cx, cy, nt) for _, _, _, _, cx, cy, w, h, nt in dedup_boxes if h > w * 1.35]

    # 1. Horizontal token stitching (same Y band, strictly <= 14pt horizontal gap)
    horiz_boxes = [b for b in dedup_boxes if b.__getitem__(6) >= b.__getitem__(7) * 0.75]
    horiz_boxes.sort(key=lambda b: (round(b.__getitem__(5) / 7.0), b.__getitem__(0)))
    h_cluster = []
    last_y = None
    for box in horiz_boxes:
        if last_y is None or abs(box.__getitem__(5) - last_y) <= max(7.5, box.__getitem__(7) * 0.65):
            h_cluster.append(box)
            last_y = box.__getitem__(5) if last_y is None else (last_y * 0.7 + box.__getitem__(5) * 0.3)
        else:
            _emit_adjacent_h_groups(h_cluster, items)
            h_cluster = [box]
            last_y = box.__getitem__(5)
    _emit_adjacent_h_groups(h_cluster, items)

    # 2. Vertical token stitching (same X column, strictly <= 14pt vertical gap)
    vert_boxes = [b for b in dedup_boxes if b.__getitem__(7) > b.__getitem__(6) * 1.25]
    vert_boxes.sort(key=lambda b: (round(b.__getitem__(4) / 7.0), b.__getitem__(1)))
    v_cluster = []
    last_x = None
    for box in vert_boxes:
        if last_x is None or abs(box.__getitem__(4) - last_x) <= max(7.5, box.__getitem__(6) * 0.65):
            v_cluster.append(box)
            last_x = box.__getitem__(4) if last_x is None else (last_x * 0.7 + box.__getitem__(4) * 0.3)
        else:
            _emit_adjacent_v_groups(v_cluster, items, vert_words)
            v_cluster = [box]
            last_x = box.__getitem__(4)
    _emit_adjacent_v_groups(v_cluster, items, vert_words)

    return items, vert_words


def extract_ocr_page_tokens(page, clip_rect=None, dpi=180, multi_angle=True):
    """Run dedicated High-DPI OCR on a page or clipped region with disk box caching & single-pass title-block recovery."""
    import os, json, hashlib, tempfile
    pw, ph = float(page.rect.width), float(page.rect.height)
    raw_boxes = None
    cache_fp = None
    if clip_rect is None:
        try:
            doc_name = getattr(getattr(page, "parent", None), "name", "") or ""
            p_idx = int(getattr(page, "number", 0)) + 1
            if doc_name and os.path.exists(doc_name):
                st = os.stat(doc_name)
                sig = hashlib.sha256(f"{os.path.basename(doc_name)}:{st.st_size}:{int(st.st_mtime)}".encode("utf-8")).hexdigest()[:20]
                cdir = os.path.join(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir(), "BowmanMortonPricingSuite", "ocr_box_cache_v1")
                os.makedirs(cdir, exist_ok=True)
                cache_fp = os.path.join(cdir, f"{sig}_p{p_idx}_d{int(dpi)}_m{int(bool(multi_angle))}.json")
                if os.path.exists(cache_fp):
                    with open(cache_fp, "r", encoding="utf-8") as cf:
                        raw_boxes = [tuple(x) for x in json.load(cf)]
        except Exception:
            raw_boxes = None

    if raw_boxes is None:
        raw_boxes = scan_world_ocr(page, world_rect=clip_rect, dpi=dpi, multi_angle=multi_angle)
        if cache_fp:
            try:
                with open(cache_fp, "w", encoding="utf-8") as cf:
                    json.dump([list(x) for x in raw_boxes], cf)
            except Exception:
                pass

    items, vert_words = stitch_ocr_boxes(raw_boxes)

    sheet_tag = ""
    if clip_rect is None:
        tb_from_raw = " ".join(str(it.__getitem__(4)) for it in raw_boxes if float(it.__getitem__(0)) >= pw * 0.82 and float(it.__getitem__(1)) >= ph * 0.75)
        if not tb_from_raw.strip():
            tb_hits = scan_world_ocr(
                page, world_rect=pymupdf.Rect(pw * 0.85, ph * 0.85, pw, ph), dpi=240, multi_angle=False
            )
            tb_from_raw = " ".join(str(it.__getitem__(4)) for it in tb_hits)
        tb_joined = _normalize_ocr_cad_noise(tb_from_raw)
        m_sh = re.search(r"\b(SD?-\d+(?:\.\d+)?|S\d+\.\d+|S-\d+)\b", tb_joined)
        if m_sh:
            sheet_tag = m_sh.group(1)

    return items, vert_words, raw_boxes, sheet_tag
