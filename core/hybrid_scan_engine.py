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
    """Run vector extraction first; fall back to OCR only if vector text yields zero steel callouts."""
    vec_items, vec_vert, full_tb = extract_vector_page_tokens(page, clip_rect=clip_rect)
    if any(_HYB_STEEL_RX.search(t) for _, _, t in vec_items):
        return vec_items, vec_vert, [], full_tb, ""

    ocr_items, ocr_vert, raw_ocr_boxes, ocr_sh = extract_ocr_page_tokens(
        page, clip_rect=clip_rect, dpi=ocr_dpi, multi_angle=True
    )
    merged_items = list(vec_items) + list(ocr_items)
    merged_vert = list(vec_vert) + list(ocr_vert)
    return merged_items, merged_vert, raw_ocr_boxes, full_tb, ocr_sh
