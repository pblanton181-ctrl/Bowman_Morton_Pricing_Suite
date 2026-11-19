import os, re, math
try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

class PdfLiveEditorEngine:
    """Dedicated Adobe Acrobat-style PDF object decomposition & live vector/text stream editor."""

    @staticmethod
    def extract_live_objects(page, page_num=1, pdf_path="", run_ocr_if_shx=True):
        objects = []

        # 1. Native TrueType / OpenType text lines with exact font family, size, weight & RGB color
        for blk in page.get_text("dict").get("blocks", []):
            if blk.get("type") != 0:
                continue
            for ln in blk.get("lines", []):
                l_rect = pymupdf.Rect(ln.get("bbox", (0, 0, 0, 0)))
                if l_rect.width < 2.0 or l_rect.height < 2.0:
                    continue
                all_spans = ln.get("spans", [])
                txt = "".join(s.get("text", "") for s in all_spans).strip()
                if not txt:
                    continue
                non_empty = [s for s in all_spans if str(s.get("text", "")).strip()]
                s0 = non_empty[0] if non_empty else (all_spans[0] if all_spans else {})
                fsz = max(6.0, float(s0.get("size", 10.0)))
                raw_font = str(s0.get("font", "Arial"))
                flags = int(s0.get("flags", 0))
                is_bold = bool(flags & 16) or ("bold" in raw_font.lower())
                is_italic = bool(flags & 2) or ("italic" in raw_font.lower()) or ("oblique" in raw_font.lower())
                clean_fam = raw_font.split("+")[-1].split("-")[0].split(",")[0].strip() or "Arial"
                c_int = int(s0.get("color", 0))
                rgb = (((c_int >> 16) & 255) / 255.0, ((c_int >> 8) & 255) / 255.0, (c_int & 255) / 255.0)
                orig_pt = s0.get("origin")
                base_y = float(orig_pt[1]) if (isinstance(orig_pt, (list, tuple)) and len(orig_pt) >= 2) else float(l_rect.y1 - fsz * 0.2)
                objects.append({
                    "kind": "truetype",
                    "rect": [float(l_rect.x0), float(l_rect.y0), float(l_rect.x1), float(l_rect.y1)],
                    "baseline_y": base_y,
                    "text": txt,
                    "font_family": clean_fam,
                    "font_size": fsz,
                    "bold": is_bold,
                    "italic": is_italic,
                    "color": rgb,
                })
        if objects:
            return objects

        # 2. AutoCAD .SHX Vector Planset: Cluster character strokes into live selectable text/callout boxes
        pw, ph = float(page.rect.width), float(page.rect.height)
        glyph_rects = []
        for drw in page.get_drawings():
            r = drw.get("rect")
            if not r or r.is_empty:
                continue
            if max(r.width, r.height) <= 48.0 and (r.width * r.height) <= 1050.0:
                glyph_rects.append(pymupdf.Rect(r))

        merged = []
        for gr in sorted(glyph_rects, key=lambda x: (round(x.y0 / 5.0), x.x0)):
            placed = False
            for m in merged:
                if abs(gr.y0 - m.y0) <= 6.5 and abs(gr.y1 - m.y1) <= 6.5 and (gr.x0 - m.x1) <= 12.0 and (m.x0 - gr.x1) <= 12.0:
                    m.include_rect(gr)
                    placed = True
                    break
            if not placed:
                merged.append(pymupdf.Rect(gr))

        final_boxes = []
        for box in sorted(merged, key=lambda x: (round(x.y0 / 5.0), x.x0)):
            if box.width < 3.5 and box.height < 3.5:
                continue
            if final_boxes:
                prev = final_boxes[-1]
                if abs(box.y0 - prev.y0) <= 5.5 and abs(box.y1 - prev.y1) <= 5.5 and -2.0 <= (box.x0 - prev.x1) <= 13.0:
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
        if not ocr_hits and run_ocr_if_shx:
            try:
                from core.plan_world import scan_world_ocr
                ocr_hits = scan_world_ocr(page, world_rect=None, dpi=180)
            except Exception:
                ocr_hits = []

        for b in final_boxes:
            if b.x0 > pw * 0.97 or b.y0 > ph * 0.97:
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
                "font_family": "Arial",
                "font_size": max(7.0, min(28.0, float(b.height) * 0.85)),
                "bold": False,
                "italic": False,
                "color": (0.05, 0.08, 0.14),
            })
        return objects

    @staticmethod
    def erase_region(page, rect_tuple, is_shx=False):
        r = pymupdf.Rect(*rect_tuple)
        # Inset slightly for TrueType text so adjacent lines/columns are never touched by PyMuPDF redaction!
        target = (r + (-0.5, -0.5, 0.5, 0.5)) if is_shx else (r + (0.35, 0.75, -0.35, -0.75))
        if target.width <= 0.5 or target.height <= 0.5:
            target = r
        page.add_redact_annot(target, fill=None)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
        if is_shx:
            page.draw_rect(target, color=(1, 1, 1), fill=(1, 1, 1), width=0)

    @staticmethod
    def _resolve_win_font(fam_hint, bold=False, italic=False):
        f_low = str(fam_hint or "").lower()
        win_fonts = r"C:\Windows\Fonts"
        candidates = []
        if "calibri" in f_low:
            candidates = ["calibrib.ttf" if bold else "calibri.ttf"]
        elif "narrow" in f_low or "condensed" in f_low or "swiss" in f_low or "simplex" in f_low or "romans" in f_low:
            candidates = ["ARIALNB.TTF" if bold else "ARIALN.TTF", "calibri.ttf"]
        elif "segoe" in f_low:
            candidates = ["segoeuib.ttf" if bold else "segoeui.ttf"]
        elif "consola" in f_low or "courier" in f_low or "mono" in f_low:
            candidates = ["consolab.ttf" if bold else "consola.ttf"]
        else:
            candidates = ["calibri.ttf", "arialbd.ttf" if bold else "arial.ttf"]
        for fn in candidates:
            fp = os.path.join(win_fonts, fn)
            if os.path.exists(fp):
                return "custom_win", fp
        fb = "hebo" if (bold and not italic) else ("heit" if (italic and not bold) else ("hebi" if (bold and italic) else "helv"))
        return fb, None

    @staticmethod
    def replace_or_insert_text(page, old_rect_tuple, new_rect_tuple, new_text, font_size=11.0, color_rgb=(0.05, 0.08, 0.14), bold=False, italic=False, font_family="Calibri", baseline_y=None, is_shx=False):
        PdfLiveEditorEngine.erase_region(page, old_rect_tuple, is_shx=is_shx)
        txt_clean = str(new_text or "").strip()
        if not txt_clean:
            return
        rx0, ry0, _, ry1 = new_rect_tuple
        fsz = max(6.0, float(font_size))
        fname, ffile = PdfLiveEditorEngine._resolve_win_font(font_family, bold=bold, italic=italic)
        first_y = float(baseline_y) if baseline_y is not None else float(ry1 - fsz * 0.18)
        line_h = max(8.0, fsz * 1.18)
        for li, line_s in enumerate(txt_clean.splitlines()):
            kw = {"fontname": fname, "fontsize": fsz, "color": color_rgb}
            if ffile:
                kw["fontfile"] = ffile
            page.insert_text(pymupdf.Point(rx0, first_y + li * line_h), line_s, **kw)

    @staticmethod
    def move_object(page, blk, dx_pdf, dy_pdf):
        old_r = blk["rect"]
        new_r = (old_r[0] + dx_pdf, old_r[1] + dy_pdf, old_r[2] + dx_pdf, old_r[3] + dy_pdf)
        txt = str(blk.get("text", "")).strip()
        if txt:
            PdfLiveEditorEngine.replace_or_insert_text(
                page, old_r, new_r, txt,
                font_size=float(blk.get("font_size", 11.0)),
                color_rgb=blk.get("color", (0.05, 0.08, 0.14)),
                bold=bool(blk.get("bold", False)),
                italic=bool(blk.get("italic", False)),
            )
        else:
            src_rect = pymupdf.Rect(*old_r)
            pix = page.get_pixmap(dpi=220, clip=src_rect, alpha=False)
            PdfLiveEditorEngine.erase_region(page, old_r)
            page.insert_image(pymupdf.Rect(*new_r), pixmap=pix)
