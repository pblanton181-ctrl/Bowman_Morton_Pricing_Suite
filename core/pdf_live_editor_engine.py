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
        if len(objects) >= 20:
            return objects
        tt_rects = [pymupdf.Rect(o.get("rect", (0, 0, 0, 0))) for o in objects]

        # 2. AutoCAD .SHX Vector Planset: Lab-verified uniform horizontal text line extraction across rot=0 & rot=270
        pw, ph = float(page.rect.width), float(page.rect.height)
        rot_m = getattr(page, "rotation_matrix", pymupdf.Matrix(1, 1))
        is_rot = (int(getattr(page, "rotation", 0)) % 360) != 0
        y_buckets = {}
        for drw in page.get_drawings():
            r0 = drw.get("rect")
            if not r0 or r0.is_empty:
                continue
            r = (r0 * rot_m) if is_rot else r0
            if 0.8 <= max(r.width, r.height) <= 32.0 and (r.width * r.height) <= 650.0:
                bk = int(r.y0 // 10.0)
                y_buckets.setdefault(bk, []).append(pymupdf.Rect(r))

        all_glyphs = []
        for bk, row_rects in y_buckets.items():
            if len(row_rects) <= 750:
                all_glyphs.extend(row_rects)

        # Sort by vertical center then X so Y-bucket boundaries never split a single text line
        all_glyphs.sort(key=lambda r: (round((r.y0 + r.y1) * 0.5 / 4.0), r.x0))
        merged = []
        for gr in all_glyphs:
            placed = False
            g_cy = (gr.y0 + gr.y1) * 0.5
            for m in reversed(merged[-40:]):
                m_cy = (m.y0 + m.y1) * 0.5
                if abs(g_cy - m_cy) <= 5.5 and -4.0 <= (gr.x0 - m.x1) <= 24.0 and max(gr.height, m.height) <= min(gr.height, m.height) * 2.5:
                    m.include_rect(gr)
                    placed = True
                    break
            if not placed:
                merged.append(pymupdf.Rect(gr))

        # Second pass: coalesce adjacent word fragments on the same baseline into clean line boxes
        final_boxes = []
        for box in sorted(merged, key=lambda x: ((x.y0 + x.y1) * 0.5, x.x0)):
            if box.width < 10.0 or box.height < 4.5 or box.height > 28.0 or box.width > pw * 0.70:
                continue
            if box.height > box.width * 1.35:
                continue
            merged_into_prev = False
            b_cy = (box.y0 + box.y1) * 0.5
            for prev in reversed(final_boxes[-25:]):
                p_cy = (prev.y0 + prev.y1) * 0.5
                if abs(b_cy - p_cy) <= 5.5 and -6.0 <= (box.x0 - prev.x1) <= 26.0 and (prev.x1 - prev.x0 + box.width) <= pw * 0.70:
                    prev.include_rect(box)
                    merged_into_prev = True
                    break
            if not merged_into_prev:
                final_boxes.append(box)

        shx_objs = []
        for b in final_boxes:
            if b.x0 > pw * 0.97 or b.y0 > ph * 0.97:
                continue
            if any((tr & b).get_area() > (b.get_area() * 0.45) for tr in tt_rects):
                continue
            fsz_est = max(6.5, min(28.0, float(b.height) * 0.85))
            shx_objs.append({
                "kind": "shx_vector",
                "rect": [float(b.x0), float(b.y0), float(b.x1), float(b.y1)],
                "baseline_y": float(b.y1 - fsz_est * 0.15),
                "text": "",
                "font_family": "Arial",
                "font_size": fsz_est,
                "bold": False,
                "italic": False,
                "color": (0.05, 0.08, 0.14),
            })

        if shx_objs:
            tmp_png = ""
            try:
                import json, re, subprocess, tempfile
                pix = page.get_pixmap(dpi=100, alpha=False)
                scale = 72.0 / 100.0
                fd, tmp_png = tempfile.mkstemp(suffix=".png")
                os.close(fd)
                pix.save(tmp_png)
                ps_cmd = (
                    "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
                    "$null = [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]; "
                    "$null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]; "
                    "$null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]; "
                    "$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters().ParameterType.Name -eq 'IAsyncOperation`1' }); "
                    "function Await($op, $t) { $asTask.MakeGenericMethod($t).Invoke($null, @($op)).GetAwaiter().GetResult() }; "
                    f"$f = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync('{tmp_png}')) ([Windows.Storage.StorageFile]); "
                    "$s = Await ($f.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream]); "
                    "$d = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($s)) ([Windows.Graphics.Imaging.BitmapDecoder]); "
                    "$b = Await ($d.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap]); "
                    "$e = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages(); "
                    "$res = Await ($e.RecognizeAsync($b)) ([Windows.Media.Ocr.OcrResult]); "
                    "$out = foreach ($ln in $res.Lines) { $ws = foreach ($w in $ln.Words) { $r = $w.BoundingRect; [pscustomobject]@{t=$w.Text; x=$r.X; y=$r.Y; w=$r.Width; h=$r.Height} }; [pscustomobject]@{text=$ln.Text; words=$ws} }; "
                    "$out | ConvertTo-Json -Depth 4 -Compress"
                )
                raw_json = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_cmd], timeout=8, encoding="utf-8", errors="ignore", stderr=subprocess.DEVNULL).strip()
                raw_json = re.sub(r"[\x00-\x1f]", " ", raw_json)
                ocr_lines = json.loads(raw_json, strict=False) if raw_json else []
                if isinstance(ocr_lines, dict):
                    ocr_lines = [ocr_lines]
                ocr_words = []
                for ln in ocr_lines:
                    ws = ln.get("words") or []
                    if isinstance(ws, dict):
                        ws = [ws]
                    for w in ws:
                        wx0 = float(w["x"]) * scale
                        wy0 = float(w["y"]) * scale
                        wx1 = wx0 + float(w["w"]) * scale
                        wy1 = wy0 + float(w["h"]) * scale
                        ocr_words.append((wx0, wy0, wx1, wy1, str(w["t"]).strip()))
                if ocr_words:
                    filtered_shx = []
                    for box in shx_objs:
                        bx0, by0, bx1, by1 = box["rect"]
                        matched = [
                            (w.__getitem__(0), w.__getitem__(4))
                            for w in ocr_words
                            if (bx0 - 6.0) <= ((w.__getitem__(0) + w.__getitem__(2)) * 0.5) <= (bx1 + 6.0)
                            and (by0 - 5.0) <= ((w.__getitem__(1) + w.__getitem__(3)) * 0.5) <= (by1 + 5.0)
                        ]
                        if matched:
                            matched.sort(key=lambda item: item.__getitem__(0))
                            box["text"] = " ".join(m.__getitem__(1) for m in matched)
                            filtered_shx.append(box)
                    shx_objs = filtered_shx
            except Exception:
                pass
            finally:
                if tmp_png and os.path.exists(tmp_png):
                    try:
                        os.remove(tmp_png)
                    except Exception:
                        pass

        objects.extend(shx_objs)

        # Instant 2ms loader from already-cached OCR boxes on scanned/raster sheets (no subprocess, zero scan overhead)
        if not objects and pdf_path and os.path.exists(pdf_path):
            try:
                import json as _js, hashlib as _hl, tempfile as _tf, bom_pdf_engine as _be
                raw_cached = list()
                _cf = os.path.join(_be._cache_dir(), f"{_be._file_fingerprint(pdf_path)}_pg{page_num}_boxes.json")
                if os.path.exists(_cf):
                    with open(_cf, encoding="utf-8") as _f:
                        raw_cached = _js.load(_f)
                else:
                    st = os.stat(pdf_path)
                    sig = _hl.sha256(f"{os.path.basename(pdf_path)}:{st.st_size}:{int(st.st_mtime)}".encode("utf-8")).hexdigest()[:20]
                    cdir = os.path.join(os.environ.get("LOCALAPPDATA") or _tf.gettempdir(), "BowmanMortonPricingSuite", "ocr_box_cache_v1")
                    for dpi_try in (180, 240, 150):
                        alt_cf = os.path.join(cdir, f"{sig}_p{page_num}_d{dpi_try}_m1.json")
                        if os.path.exists(alt_cf):
                            with open(alt_cf, encoding="utf-8") as _af:
                                raw_cached = _js.load(_af)
                            break
                for item in raw_cached:
                    if len(item) >= 5:
                        bx0, by0, bx1, by1, bt = float(item.__getitem__(0)), float(item.__getitem__(1)), float(item.__getitem__(2)), float(item.__getitem__(3)), str(item.__getitem__(4)).strip()
                        if bt and (bx1 - bx0) >= 5.0 and (by1 - by0) >= 4.0:
                            fsz_est = max(6.5, min(28.0, float(by1 - by0) * 0.85))
                            objects.append({
                                "kind": "shx_vector",
                                "rect": [bx0, by0, bx1, by1],
                                "baseline_y": float(by1 - fsz_est * 0.15),
                                "text": bt,
                                "font_family": "Arial",
                                "font_size": fsz_est,
                                "bold": False,
                                "italic": False,
                                "color": (0.05, 0.08, 0.14),
                            })
            except Exception:
                pass

        return PdfLiveEditorEngine._group_lines_into_paragraphs(objects)

    @staticmethod
    def _group_lines_into_paragraphs(line_objs):
        if not line_objs:
            return []
        # Sort top-to-bottom, left-to-right
        ordered = sorted(line_objs, key=lambda o: (round(float(o["rect"][1]) / 4.0), float(o["rect"][0])))
        paras = []
        for obj in ordered:
            r = obj.get("rect", [0, 0, 0, 0])
            x0, y0, x1, y1 = float(r[0]), float(r[1]), float(r[2]), float(r[3])
            h = max(4.0, y1 - y0)
            txt = str(obj.get("text", "") or "").strip()
            fsz = float(obj.get("font_size", 10.0))
            kind = obj.get("kind", "truetype")
            merged = False
            for p in reversed(paras[-20:]):
                pr = p["rect"]
                px0, py0, px1, py1 = float(pr[0]), float(pr[1]), float(pr[2]), float(pr[3])
                if p.get("kind") != kind:
                    continue
                if abs(float(p.get("font_size", 10.0)) - fsz) > 1.8:
                    continue
                # Same left column margin (within 14pt) and stacked directly below previous line (gap <= 1.15x line height)
                v_gap = y0 - py1
                left_aligned = abs(x0 - px0) <= 14.0
                horiz_overlap = min(x1, px1) - max(x0, px0) > 12.0
                if left_aligned and horiz_overlap and -2.0 <= v_gap <= max(10.0, h * 1.15):
                    # Don't merge across separate numbered notes unless part of same wrapped note
                    is_new_note = bool(txt and len(txt) >= 2 and txt[0].isdigit() and txt[1] in (".", ")"))
                    if is_new_note and v_gap > h * 0.45:
                        continue
                    pr[0] = min(px0, x0)
                    pr[1] = min(py0, y0)
                    pr[2] = max(px1, x1)
                    pr[3] = max(py1, y1)
                    if txt:
                        p["text"] = (p["text"] + "\n" + txt).strip() if p["text"] else txt
                    p["line_count"] = int(p.get("line_count", 1)) + 1
                    merged = True
                    break
            if not merged:
                nb = dict(obj)
                nb["rect"] = [x0, y0, x1, y1]
                nb["line_count"] = 1
                paras.append(nb)
        return paras

    @staticmethod
    def ocr_single_box(page, rect_tuple):
        tmp_png = ""
        try:
            import subprocess, tempfile
            r = (pymupdf.Rect(*rect_tuple) + (-6.0, -4.0, 6.0, 4.0)) & page.rect
            if r.is_empty or r.width < 4.0 or r.height < 3.0:
                return ""
            pix = page.get_pixmap(dpi=280, clip=r, alpha=False)
            fd, tmp_png = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            pix.save(tmp_png)
            ps_cmd = (
                "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
                "$null = [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]; "
                "$null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]; "
                "$null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]; "
                "$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters().ParameterType.Name -eq 'IAsyncOperation`1' }); "
                "function Await($op, $t) { $asTask.MakeGenericMethod($t).Invoke($null, @($op)).GetAwaiter().GetResult() }; "
                f"$f = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync('{tmp_png}')) ([Windows.Storage.StorageFile]); "
                "$s = Await ($f.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream]); "
                "$d = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($s)) ([Windows.Graphics.Imaging.BitmapDecoder]); "
                "$b = Await ($d.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap]); "
                "$e = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages(); "
                "$res = Await ($e.RecognizeAsync($b)) ([Windows.Media.Ocr.OcrResult]); "
                "Write-Output $res.Text"
            )
            out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_cmd], timeout=4, encoding="utf-8", errors="ignore", stderr=subprocess.DEVNULL)
            cleaned = "".join(ch for ch in out if ch >= " " or ch in "\t\n")
            return " ".join(cleaned.split()).strip()
        except Exception:
            return ""
        finally:
            if tmp_png and os.path.exists(tmp_png):
                try:
                    os.remove(tmp_png)
                except Exception:
                    pass
    @staticmethod
    def erase_region(page, rect_tuple, is_shx=False):
        r = pymupdf.Rect(*rect_tuple)
        target = (r + (-0.5, -0.5, 0.5, 0.5)) if is_shx else (r + (0.35, 0.75, -0.35, -0.75))
        if target.width <= 0.5 or target.height <= 0.5:
            target = r
        has_native_txt = False
        if not is_shx:
            try:
                has_native_txt = bool(page.get_text("words", clip=target))
            except Exception:
                has_native_txt = False
        rot = int(getattr(page, "rotation", 0)) % 360
        raw_target = (target * page.derotation_matrix) if rot != 0 else target
        if has_native_txt:
            page.add_redact_annot(raw_target, fill=(1, 1, 1))
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
        page.draw_rect(raw_target, color=(1, 1, 1), fill=(1, 1, 1), width=0, overlay=True)

    @staticmethod
    def erase_regions_batch(page, rect_items):
        if not rect_items:
            return
        rot = int(getattr(page, "rotation", 0)) % 360
        derot = getattr(page, "derotation_matrix", pymupdf.Matrix(1, 1))
        raw_boxes = []
        need_redact = False
        for rect_tuple, is_shx in rect_items:
            if not rect_tuple or len(rect_tuple) < 4:
                continue
            r = pymupdf.Rect(*rect_tuple)
            target = (r + (-0.5, -0.5, 0.5, 0.5)) if is_shx else (r + (0.35, 0.75, -0.35, -0.75))
            if target.width <= 0.5 or target.height <= 0.5:
                target = r
            raw_t = (target * derot) if rot != 0 else target
            raw_boxes.append(raw_t)
            if not is_shx:
                try:
                    if page.get_text("words", clip=target):
                        page.add_redact_annot(raw_t, fill=(1, 1, 1))
                        need_redact = True
                except Exception:
                    pass
        if need_redact:
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
        for raw_t in raw_boxes:
            page.draw_rect(raw_t, color=(1, 1, 1), fill=(1, 1, 1), width=0, overlay=True)

    @staticmethod
    def _resolve_win_font(fam_hint, bold=False, italic=False):
        f_low = str(fam_hint or "").lower()
        win_fonts = r"C:\Windows\Fonts"
        candidates = []
        if "calibri" in f_low:
            if bold and italic: candidates = ["calibriz.ttf", "calibrib.ttf", "calibri.ttf"]
            elif bold: candidates = ["calibrib.ttf", "calibri.ttf"]
            elif italic: candidates = ["calibrii.ttf", "calibri.ttf"]
            else: candidates = ["calibri.ttf"]
        elif "narrow" in f_low or "condensed" in f_low:
            candidates = ["ARIALNBI.TTF" if (bold and italic) else ("ARIALNB.TTF" if bold else ("ARIALNI.TTF" if italic else "ARIALN.TTF")), "arial.ttf"]
        elif "times" in f_low or "roman" in f_low or "serif" in f_low:
            candidates = ["timesbi.ttf" if (bold and italic) else ("timesbd.ttf" if bold else ("timesi.ttf" if italic else "times.ttf")), "arial.ttf"]
        elif "segoe" in f_low:
            candidates = ["segoeuiz.ttf" if (bold and italic) else ("segoeuib.ttf" if bold else ("segoeuii.ttf" if italic else "segoeui.ttf")), "arial.ttf"]
        elif "consola" in f_low or "courier" in f_low or "mono" in f_low:
            candidates = ["consolaz.ttf" if (bold and italic) else ("consolab.ttf" if bold else ("consolai.ttf" if italic else "consola.ttf")), "arial.ttf"]
        else:
            if bold and italic: candidates = ["arialbi.ttf", "arialbd.ttf", "arial.ttf"]
            elif bold: candidates = ["arialbd.ttf", "arial.ttf"]
            elif italic: candidates = ["ariali.ttf", "arial.ttf"]
            else: candidates = ["arial.ttf", "calibri.ttf"]
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
        rot = int(getattr(page, "rotation", 0)) % 360
        derot = getattr(page, "derotation_matrix", pymupdf.Matrix(1, 1))
        nx0, ny0, nx1, ny1 = new_rect_tuple
        box_w = max(40.0, float(nx1 - nx0))
        lines_in = txt_clean.splitlines()
        if len(lines_in) > 1 or box_w >= 90.0:
            # Word-wrap text to fit the paragraph column width cleanly, then render line-by-line upright
            wrapped_lines = []
            approx_char_w = max(3.2, fsz * 0.52)
            max_chars = max(12, int(box_w / approx_char_w))
            for raw_ln in lines_in:
                words_ln = raw_ln.split(" ")
                cur_ln = ""
                for w_tok in words_ln:
                    cand = (cur_ln + " " + w_tok).strip() if cur_ln else w_tok
                    if len(cand) <= max_chars or not cur_ln:
                        cur_ln = cand
                    else:
                        wrapped_lines.append(cur_ln)
                        cur_ln = w_tok
                if cur_ln:
                    wrapped_lines.append(cur_ln)
            first_y_box = float(ny0 + fsz * 0.92)
            for li, line_s in enumerate(wrapped_lines):
                pt_disp = pymupdf.Point(nx0, first_y_box + li * line_h)
                pt_raw = (pt_disp * derot) if rot != 0 else pt_disp
                kw = {"fontname": fname, "fontsize": fsz, "color": color_rgb, "rotate": rot, "overlay": True}
                if ffile:
                    kw["fontfile"] = ffile
                page.insert_text(pt_raw, line_s, **kw)
        else:
            for li, line_s in enumerate(lines_in):
                pt_disp = pymupdf.Point(nx0, first_y + li * line_h)
                pt_raw = (pt_disp * derot) if rot != 0 else pt_disp
                kw = {"fontname": fname, "fontsize": fsz, "color": color_rgb, "rotate": rot, "overlay": True}
                if ffile:
                    kw["fontfile"] = ffile
                page.insert_text(pt_raw, line_s, **kw)

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
