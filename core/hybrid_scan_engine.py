# -*- coding: utf-8 -*-
"""
Dedicated Engine 3: Vector + OCR Hybrid Fusion Engine.
Uses instant CAD vector/SHX extraction first (~0.05s) and invokes High-DPI OCR
only when a sheet or clipped region has no vector steel callouts (e.g. scanned PDFs).
"""
import re
from core.vector_scan_engine import extract_vector_page_tokens
from core.ocr_scan_engine import extract_ocr_page_tokens

_HYB_STEEL_RX = re.compile(
    r"(?<![A-Z0-9])("
    r"W\d+\s*X\s*\d+(?:\.\d+)?|WT\d+\s*X\s*[\d.]+|S\d+\s*X\s*[\d.]+|HP\d+\s*X\s*\d+|"
    r"(?:HSS|TS)\s*\d+(?:\.\d+)?\s*X\s*\d+(?:\.\d+)?\s*X\s*[\d/.]+|(?:HSS|TS)\s*\d+(?:\.\d+)?\s*X\s*[\d/.]+|"
    r"L\d+(?:\.\d+)?\s*X\s*\d+(?:\.\d+)?\s*X\s*[\d/.]+|C\d+\s*X\s*[\d.]+|MC\d+\s*X\s*[\d.]+|"
    r"(?:PIPE|STD\s*PIPE|XS\s*PIPE)\s*[\d/.]+|"
    r"(?:BASE\s*PL|PLATE\s*WASHER\s*PL|CUSTOM\s*PL|PL|FB)\s*[\d/.-]+\s*[\"\u201d]?\s*X\s*[\d/.-]+"
    r")"
)


def extract_hybrid_page_tokens(page, clip_rect=None, ocr_dpi=180):
    """Run vector extraction first; use fast title-block check on raster sheets and skip redundant OCR on native text sheets."""
    import pymupdf
    from core.plan_world import scan_world_ocr, normalize_cad_text
    vec_items, vec_vert, full_tb = extract_vector_page_tokens(page, clip_rect=clip_rect)
    if any(_HYB_STEEL_RX.search(t) for _, _, t in vec_items):
        return vec_items, vec_vert, list(), full_tb, ""
    if clip_rect is None and len(vec_items) >= 40:
        return vec_items, vec_vert, list(), full_tb, ""
    ocr_sh = ""
    if clip_rect is None:
        pw, ph = float(page.rect.width), float(page.rect.height)
        tb_hits = scan_world_ocr(page, world_rect=pymupdf.Rect(pw * 0.84, ph * 0.82, pw, ph), dpi=200, multi_angle=False)
        tb_txt = normalize_cad_text(" ".join(str(it.__getitem__(4)) for it in tb_hits))
        m_non_s = re.search(r"\b([ACMEPLG]\d+(?:\.\d+)?|[ACMEPLG]-\d+)\b", tb_txt)
        m_struct = re.search(r"\b(SD?-\d+(?:\.\d+)?|S\d+\.\d+|S-\d+)\b", tb_txt)
        if m_struct:
            ocr_sh = m_struct.group(1)
        elif m_non_s:
            return vec_items, vec_vert, list(), full_tb, m_non_s.group(1)
    ocr_items, ocr_vert, raw_ocr_boxes, det_sh = extract_ocr_page_tokens(
        page, clip_rect=clip_rect, dpi=ocr_dpi, multi_angle=True
    )
    if det_sh and not ocr_sh:
        ocr_sh = det_sh
    merged_items = list(vec_items) + list(ocr_items)
    merged_vert = list(vec_vert) + list(ocr_vert)
    return merged_items, merged_vert, raw_ocr_boxes, full_tb, ocr_sh
