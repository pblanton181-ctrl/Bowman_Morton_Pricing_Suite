# -*- coding: utf-8 -*-
"""
Dedicated Engine 4: Current-Sheet & Drag-and-Scan Region Engine.
Provides dedicated single-sheet scanning and high-precision 300-DPI
padded-clip marquee region scanning without polluting whole-planset cache.
"""
import pymupdf


def scan_current_sheet_bom(pdf_path, page_num_1based, scan_mode="hybrid", matrix_path="steel_matrix.json", sheet_scales=None):
    """Scan a single active blueprint sheet using the chosen dedicated engine ('vector', 'ocr', or 'hybrid')."""
    from bom_pdf_engine import extract_full_bom
    return extract_full_bom(
        pdf_path,
        matrix_path=matrix_path,
        selected_pages=[int(page_num_1based)],
        region_clip=None,
        scan_mode=scan_mode,
        sheet_scales=sheet_scales,
    )


def scan_drag_region_bom(pdf_path, page_num_1based, rect_pdf, scan_mode="hybrid", matrix_path="steel_matrix.json", sheet_scales=None):
    """Scan a user-dragged marquee region at 300 DPI with an 8pt safety margin so border text is never clipped."""
    from bom_pdf_engine import extract_full_bom
    r = pymupdf.Rect(rect_pdf).normalize()
    padded = pymupdf.Rect(max(0.0, r.x0 - 8.0), max(0.0, r.y0 - 8.0), r.x1 + 8.0, r.y1 + 8.0)
    return extract_full_bom(
        pdf_path,
        matrix_path=matrix_path,
        selected_pages=[int(page_num_1based)],
        region_clip=padded,
        scan_mode=scan_mode,
        sheet_scales=sheet_scales,
    )
