# -*- coding: utf-8 -*-
"""
Dedicated Engine 3: Vector + OCR Hybrid Spatial Fusion Engine.
Combines native CAD vector text extraction with High-DPI Multi-Angle OCR
and spatially deduplicates overlapping tokens so mixed vector/raster/SHX
blueprints achieve complete coverage without double-counting.
"""
import math
from core.vector_scan_engine import extract_vector_page_tokens
from core.ocr_scan_engine import extract_ocr_page_tokens


def extract_hybrid_page_tokens(page, clip_rect=None, ocr_dpi=220):
    """Fuse vector text and High-DPI OCR tokens with spatial deduplication."""
    vec_items, vec_vert, full_tb = extract_vector_page_tokens(page, clip_rect=clip_rect)
    ocr_items, ocr_vert, raw_boxes, ocr_sheet = extract_ocr_page_tokens(
        page, clip_rect=clip_rect, dpi=ocr_dpi, multi_angle=True
    )

    merged_items = list(vec_items)
    for ox, oy, otxt in ocr_items:
        # Skip OCR token if an identical vector token is already within 16pt
        if any(vtxt == otxt and math.hypot(ox - vx, oy - vy) < 16.0 for vx, vy, vtxt in vec_items):
            continue
        merged_items.append((ox, oy, otxt))

    merged_vert = list(vec_vert)
    for ox, oy, otxt in ocr_vert:
        if any(vtxt == otxt and math.hypot(ox - vx, oy - vy) < 16.0 for vx, vy, vtxt in vec_vert):
            continue
        merged_vert.append((ox, oy, otxt))

    return merged_items, merged_vert, raw_boxes, full_tb, ocr_sheet
