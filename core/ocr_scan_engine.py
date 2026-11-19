# -*- coding: utf-8 -*-
"""
Dedicated Engine 2: High-DPI Raster & SHX Optical Character Recognition (OCR) Engine.
Covers all 4 cardinal orientations (0°, 90°/-270°, 180°, 270°/-90°), normalizes
AutoCAD SHX stroke-font character swaps, stitches both horizontal and vertical
multi-token callouts, and deduplicates overlapping multi-angle hits.
"""
import math
import re
import pymupdf
from core.plan_world import scan_world_ocr, normalize_cad_text


def _normalize_ocr_cad_noise(raw_txt):
    t = normalize_cad_text(raw_txt)
    if not t:
        return ""
    t = re.sub(r"\b(W|WT|S|HP|HSS|L|C|MC|PL|FB|PIPE)\s+(\d)", r"\1\2", t)
    t = re.sub(r"(?<=\d)\s*[X×*]\s*(?=\d)", "X", t)
    t = re.sub(r"\b(HSS|W|L|C|PL)(\d+)O\b", r"\g<1>\g<2>0", t)
    t = re.sub(r"\b(S\d+)\.L\b", r"\1.1", re.sub(r"\b(S\d+)\.O\b", r"\1.0", t))
    return t.strip()


def stitch_ocr_boxes(raw_boxes):
    """Deduplicate multi-angle OCR hits and stitch horizontal & vertical multi-token steel callouts."""
    if not raw_boxes:
        return [], []

    dedup_boxes = []
    for wx0, wy0, wx1, wy1, txt in raw_boxes:
        nt = _normalize_ocr_cad_noise(txt)
        if not nt:
            continue
        cx, cy = (wx0 + wx1) * 0.5, (wy0 + wy1) * 0.5
        if any(d_txt == nt and math.hypot(cx - d_cx, cy - d_cy) < 10.0 for _, _, _, _, d_cx, d_cy, _, _, d_txt in dedup_boxes):
            continue
        w, h = max(1.0, wx1 - wx0), max(1.0, wy1 - wy0)
        dedup_boxes.append((wx0, wy0, wx1, wy1, cx, cy, w, h, nt))

    items = [(cx, cy, nt) for _, _, _, _, cx, cy, _, _, nt in dedup_boxes]
    vert_words = [(cx, cy, nt) for _, _, _, _, cx, cy, w, h, nt in dedup_boxes if h > w * 1.35]

    # 1. Horizontal token stitching (same Y band, adjacent X within 32pt)
    horiz_boxes = [b for b in dedup_boxes if b[6] >= b[7] * 0.75]
    horiz_boxes.sort(key=lambda b: (round(b[5] / 7.0), b[0]))
    h_cluster = []
    last_y = None
    for box in horiz_boxes:
        if last_y is None or abs(box[5] - last_y) <= max(7.5, box[7] * 0.65):
            h_cluster.append(box)
            last_y = box[5] if last_y is None else (last_y * 0.7 + box[5] * 0.3)
        else:
            if len(h_cluster) > 1:
                h_cluster.sort(key=lambda b: b[0])
                grp = [h_cluster[0]]
                for nxt in h_cluster[1:]:
                    if (nxt[0] - grp[-1][2]) <= 14.0:
                        grp.append(nxt)
                    else:
                        if len(grp) > 1:
                            merged = _normalize_ocr_cad_noise("".join(g[8] for g in grp))
                            if not any(g[8] == merged for g in grp):
                                items.append(((grp[0][0] + grp[-1][2]) * 0.5, (grp[0][1] + grp[-1][3]) * 0.5, merged))
                        grp = [nxt]
                if len(grp) > 1:
                    merged = _normalize_ocr_cad_noise("".join(g[8] for g in grp))
                    if not any(g[8] == merged for g in grp):
                                items.append(((grp[0][0] + grp[-1][2]) * 0.5, (grp[0][1] + grp[-1][3]) * 0.5, merged))
            h_cluster = [box]
            last_y = box[5]
    if len(h_cluster) > 1:
        h_cluster.sort(key=lambda b: b[0])
        merged = _normalize_ocr_cad_noise("".join(g[8] for g in h_cluster))
        items.append(((h_cluster[0][0] + h_cluster[-1][2]) * 0.5, (h_cluster[0][1] + h_cluster[-1][3]) * 0.5, merged))

    # 2. Vertical token stitching (same X column, adjacent Y within 32pt)
    vert_boxes = [b for b in dedup_boxes if b[7] > b[6] * 1.25]
    vert_boxes.sort(key=lambda b: (round(b[4] / 7.0), b[1]))
    v_cluster = []
    last_x = None
    for box in vert_boxes:
        if last_x is None or abs(box[4] - last_x) <= max(7.5, box[6] * 0.65):
            v_cluster.append(box)
            last_x = box[4] if last_x is None else (last_x * 0.7 + box[4] * 0.3)
        else:
            if len(v_cluster) > 1:
                v_cluster.sort(key=lambda b: b[1])
                merged_tb = _normalize_ocr_cad_noise("".join(g[8] for g in v_cluster))
                merged_bt = _normalize_ocr_cad_noise("".join(g[8] for g in reversed(v_cluster)))
                vcx = (v_cluster[0][0] + v_cluster[-1][2]) * 0.5
                vcy = (v_cluster[0][1] + v_cluster[-1][3]) * 0.5
                items.append((vcx, vcy, merged_tb))
                if merged_bt != merged_tb:
                    items.append((vcx, vcy, merged_bt))
            v_cluster = [box]
            last_x = box[4]
    if len(v_cluster) > 1:
        v_cluster.sort(key=lambda b: b[1])
        merged_tb = _normalize_ocr_cad_noise("".join(g[8] for g in v_cluster))
        merged_bt = _normalize_ocr_cad_noise("".join(g[8] for g in reversed(v_cluster)))
        vcx = (v_cluster[0][0] + v_cluster[-1][2]) * 0.5
        vcy = (v_cluster[0][1] + v_cluster[-1][3]) * 0.5
        items.append((vcx, vcy, merged_tb))
        if merged_bt != merged_tb:
            items.append((vcx, vcy, merged_bt))

    return items, vert_words


def extract_ocr_page_tokens(page, clip_rect=None, dpi=240, multi_angle=True):
    """Run dedicated 4-angle High-DPI OCR on a page or clipped region."""
    pw, ph = float(page.rect.width), float(page.rect.height)
    raw_boxes = scan_world_ocr(page, world_rect=clip_rect, dpi=dpi, multi_angle=multi_angle)
    items, vert_words = stitch_ocr_boxes(raw_boxes)

    sheet_tag = ""
    if clip_rect is None:
        tb_hits = scan_world_ocr(
            page, world_rect=pymupdf.Rect(pw * 0.85, ph * 0.85, pw, ph), dpi=300, multi_angle=False
        )
        tb_joined = _normalize_ocr_cad_noise(" ".join(t for _, _, _, _, t in tb_hits))
        m_sh = re.search(r"\b(SD?-\d+(?:\.\d+)?|S\d+\.\d+|S-\d+)\b", tb_joined)
        if m_sh:
            sheet_tag = m_sh.group(1)

    return items, vert_words, raw_boxes, sheet_tag
