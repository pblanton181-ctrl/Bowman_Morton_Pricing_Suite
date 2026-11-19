import os, re, math
import numpy as np

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

def decompose_page_objects(page, page_num=1, pdf_path=""):
    """Decomposes a PDF page into live, selectable, movable, and editable text/SHX objects."""
    objects = []
    for blk in page.get_text("dict").get("blocks", []):
        if blk.get("type") != 0:
            continue
        for ln in blk.get("lines", []):
            l_rect = pymupdf.Rect(ln.get("bbox", (0, 0, 0, 0)))
            if l_rect.width < 2 or l_rect.height < 2:
                continue
            spans = ln.get("spans", [])
            txt = "".join(s.get("text", "") for s in spans).strip()
            if not txt:
                continue
            fsz = max(7.0, float(spans[0].get("size", 11.0))) if spans else 11.0
            c_int = int(spans[0].get("color", 0)) if spans else 0
            r_c = ((c_int >> 16) & 255) / 255.0
            g_c = ((c_int >> 8) & 255) / 255.0
            b_c = (c_int & 255) / 255.0
            objects.append({
                "kind": "truetype",
                "rect": [float(l_rect.x0), float(l_rect.y0), float(l_rect.x1), float(l_rect.y1)],
                "text": txt,
                "font_size": fsz,
                "color": (r_c, g_c, b_c),
            })
    if objects:
        return objects

    pw, ph = float(page.rect.width), float(page.rect.height)
    glyph_rects = []
    for drw in page.get_drawings():
        r = drw.get("rect")
        if not r or r.is_empty:
            continue
        if max(r.width, r.height) <= 45.0 and (r.width * r.height) <= 900.0:
            glyph_rects.append(pymupdf.Rect(r))

    merged = []
    for gr in sorted(glyph_rects, key=lambda x: (round(x.y0 / 5.0), x.x0)):
        placed = False
        for m in merged:
            if abs(gr.y0 - m.y0) <= 6.0 and abs(gr.y1 - m.y1) <= 6.0 and (gr.x0 - m.x1) <= 11.0 and (m.x0 - gr.x1) <= 11.0:
                m.include_rect(gr)
                placed = True
                break
        if not placed:
            merged.append(pymupdf.Rect(gr))

    final_boxes = []
    for box in sorted(merged, key=lambda x: (round(x.y0 / 5.0), x.x0)):
        if box.width < 3.0 and box.height < 3.0:
            continue
        if final_boxes:
            prev = final_boxes[-1]
            if abs(box.y0 - prev.y0) <= 5.0 and abs(box.y1 - prev.y1) <= 5.0 and -2.0 <= (box.x0 - prev.x1) <= 12.0:
                prev.include_rect(box)
                continue
        final_boxes.append(box)

    ocr_hits = []
    if pdf_path and os.path.exists(pdf_path):
        try:
            import json as _js, bom_pdf_engine as _be
            _cf = os.path.join(_be._cache_dir(), f"{_be._file_fingerprint(pdf_path)}_pg{page_num}_boxes.json")
            if os.path.exists(_cf):
                with open(_cf, encoding="utf-8") as _f:
                    ocr_hits = _js.load(_f)
        except Exception:
            pass

    for b in final_boxes:
        if b.x0 > pw * 0.96 or b.y0 > ph * 0.96:
            continue
        matched_txt = ""
        best_ov = 0.0
        for ox0, oy0, ox1, oy1, ot in ocr_hits:
            inter = b & pymupdf.Rect(ox0, oy0, ox1, oy1)
            if not inter.is_empty:
                ov = inter.get_area()
                if ov > best_ov:
                    best_ov = ov
                    matched_txt = str(ot).strip()
        objects.append({
            "kind": "shx_vector",
            "rect": [float(b.x0), float(b.y0), float(b.x1), float(b.y1)],
            "text": matched_txt,
            "font_size": max(7.5, min(28.0, float(b.height) * 0.85)),
            "color": (0.05, 0.08, 0.14),
        })
    return objects

def strip_vectors_and_text_in_rect(page, rect_tuple):
    target = pymupdf.Rect(*rect_tuple).inflate(1.2, 1.2)
    page.add_redact_annot(target, fill=None)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
    page.draw_rect(target, color=(1, 1, 1), fill=(1, 1, 1), width=0)
