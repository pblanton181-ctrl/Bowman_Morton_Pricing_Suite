import os
import re
import math
import tempfile
import subprocess
import pymupdf


def normalize_cad_text(s):
    s = str(s or "").upper().strip()
    s = s.replace("\u00d7", "X").replace("\u2013", "-").replace("\u2014", "-")
    s = re.sub(r"\s+", "", s)
    # Normalize AutoCAD SHX stroke-font OCR character confusions in steel profiles (O->0, J->3, I/L->1)
    s = re.sub(r"\b(W|HSS|MC|C|L|WT|HP)(\d*)O", lambda m: m.group(1) + m.group(2) + "0", s)
    s = re.sub(r"(X\d+)O\b", lambda m: m.group(1) + "0", s)
    s = re.sub(r"\b(W\d+X\d+)J\b", lambda m: m.group(1) + "3", s)
    s = re.sub(r"\b(W\d+X)I(\d+)\b", lambda m: m.group(1) + "1" + m.group(2), s)
    s = re.sub(r"\bWBX(\d+)", lambda m: "W8X" + m.group(1), s)
    return s


def round_structural_ft(raw_ft):
    """Single shared 1/4-ft (3-inch) rounding rule across BOM, Measure, and OCR."""
    return round(float(raw_ft) * 4.0) / 4.0


def parse_arch_scale(txt):
    """Parses architectural scale fractions (e.g. 1/4\"=1'-0\" -> 18.0 pts/ft),
    ignoring standard 24X36 SHEET border boilerplate."""
    cleaned = re.sub(
        r"\d+\s*[X×]\s*\d+\s*SHEET\s*:?\s*1\s*/\s*8\s*\"\s*=\s*1\s*'\s*-?\s*0\s*\"?",
        " ",
        str(txt),
        flags=re.IGNORECASE,
    )
    m = re.search(r"(\d+)\s*/\s*(\d+)\s*\"\s*=\s*1\s*'\s*-?\s*0", cleaned)
    if m and float(m.group(2)) > 0:
        return (float(m.group(1)) / float(m.group(2))) * 72.0
    m2 = re.search(r"\b([1-3])\s*\"\s*=\s*1\s*'\s*-?\s*0", cleaned)
    return float(m2.group(1)) * 72.0 if m2 else 18.0


class SheetWorldState:
    """Single unified PDF world-space model (72 DPI points) for one sheet."""

    def __init__(self, page, page_num, pts_per_ft=None):
        self.page_num = int(page_num)
        self.width_pt = float(page.rect.width)
        self.height_pt = float(page.rect.height)
        self.pts_per_ft = float(pts_per_ft) if pts_per_ft else self._detect_scale(page)
        self.snap_endpoints = []
        self.snap_midpoints = []
        self.bay_segments = []
        self._build_vector_world(page)

    def _detect_scale(self, page):
        mx, my = self.width_pt * 0.72, self.height_pt * 0.94
        full_tb = normalize_cad_text(page.get_text("text"))
        vp_words = [
            normalize_cad_text(wstr)
            for wx0, wy0, wx1, wy1, wstr, *_ in page.get_text("words")
            if wx0 < mx and wy0 < my
        ]
        return float(parse_arch_scale(full_tb + " " + " ".join(vp_words)))

    def world_to_px(self, wx, wy, view_w, view_h):
        if self.width_pt <= 0 or self.height_pt <= 0:
            return 0.0, 0.0
        return float(wx) * (float(view_w) / self.width_pt), float(wy) * (float(view_h) / self.height_pt)

    def px_to_world(self, px, py, view_w, view_h):
        if view_w <= 0 or view_h <= 0:
            return 0.0, 0.0
        return float(px) * (self.width_pt / float(view_w)), float(py) * (self.height_pt / float(view_h))

    def pts_to_ft(self, pdf_pts):
        return round_structural_ft(float(pdf_pts) / max(1.0, self.pts_per_ft))

    def _build_vector_world(self, page):
        mx_vp = self.width_pt * 0.88
        eps, mps = set(), set()
        raw_h, raw_v = [], []
        min_seg_pts = max(24.0, self.pts_per_ft * 3.0)

        for drw in page.get_drawings():
            for itm in drw.get("items", []):
                op = itm.__getitem__(0)
                if op == "l" and len(itm) >= 3:
                    p_a, p_b = itm.__getitem__(1), itm.__getitem__(2)
                    if p_a.x > mx_vp and p_b.x > mx_vp:
                        continue
                    ax, ay = round(float(p_a.x), 2), round(float(p_a.y), 2)
                    bx, by = round(float(p_b.x), 2), round(float(p_b.y), 2)
                    dx, dy = abs(bx - ax), abs(by - ay)
                    if math.hypot(dx, dy) >= 12.0:
                        eps.add((ax, ay))
                        eps.add((bx, by))
                        mps.add((round((ax + bx) * 0.5, 2), round((ay + by) * 0.5, 2)))
                    if dy <= 1.0 and dx >= 3.0:
                        raw_h.append((min(ax, bx), max(ax, bx), round((ay + by) * 0.5, 2)))
                    elif dx <= 1.0 and dy >= 3.0:
                        raw_v.append((min(ay, by), max(ay, by), round((ax + bx) * 0.5, 2)))
                elif op == "re" and len(itm) >= 2:
                    rc = itm.__getitem__(1)
                    if rc.x0 > mx_vp:
                        continue
                    x0, y0 = round(float(rc.x0), 2), round(float(rc.y0), 2)
                    x1, y1 = round(float(rc.x1), 2), round(float(rc.y1), 2)
                    eps.update([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
                    mps.update([
                        (round((x0 + x1) * 0.5, 2), y0),
                        (round((x0 + x1) * 0.5, 2), y1),
                        (x0, round((y0 + y1) * 0.5, 2)),
                        (x1, round((y0 + y1) * 0.5, 2)),
                    ])
                elif op == "c" and len(itm) >= 5:
                    p_a, p_b = itm.__getitem__(1), itm.__getitem__(4)
                    eps.add((round(float(p_a.x), 2), round(float(p_a.y), 2)))
                    eps.add((round(float(p_b.x), 2), round(float(p_b.y), 2)))

        merged_h, merged_v = [], []
        for x0, x1, y in sorted(raw_h, key=lambda s: (round(s.__getitem__(2), 1), s.__getitem__(0))):
            if merged_h and abs(merged_h[-1].__getitem__(2) - y) <= 1.2 and x0 <= merged_h[-1].__getitem__(1) + 10.5:
                px0, px1, py = merged_h[-1]
                merged_h[-1] = (px0, max(px1, x1), py)
            else:
                merged_h.append((x0, x1, y))
        for y0, y1, x in sorted(raw_v, key=lambda s: (round(s.__getitem__(2), 1), s.__getitem__(0))):
            if merged_v and abs(merged_v[-1].__getitem__(2) - x) <= 1.2 and y0 <= merged_v[-1].__getitem__(1) + 10.5:
                py0, py1, px = merged_v[-1]
                merged_v[-1] = (py0, max(py1, y1), px)
            else:
                merged_v.append((y0, y1, x))

        merged_h = [s for s in merged_h if (s.__getitem__(1) - s.__getitem__(0)) >= min_seg_pts]
        merged_v = [s for s in merged_v if (s.__getitem__(1) - s.__getitem__(0)) >= min_seg_pts]

        for x0, x1, y in merged_h:
            eps.add((x0, y))
            eps.add((x1, y))
            mps.add((round((x0 + x1) * 0.5, 2), y))
        for y0, y1, x in merged_v:
            eps.add((x, y0))
            eps.add((x, y1))
            mps.add((x, round((y0 + y1) * 0.5, 2)))

        for hx0, hx1, hy in merged_h:
            for vy0, vy1, vx in merged_v:
                if (hx0 - 2.5) <= vx <= (hx1 + 2.5) and (vy0 - 2.5) <= hy <= (vy1 + 2.5):
                    eps.add((vx, hy))

        self.snap_endpoints = list(eps)
        self.snap_midpoints = list(mps)
        segs = [(x0, y, x1, y, (x1 - x0) / self.pts_per_ft, "h") for x0, x1, y in merged_h]
        segs += [(x, y0, x, y1, (y1 - y0) / self.pts_per_ft, "v") for y0, y1, x in merged_v]
        self.bay_segments = segs
    def attach_beam_to_callout(self, cx, cy, is_horiz, max_perp_pts=9.5, max_span_ft=34.0, min_span_ft=6.0):
        """Finds the structural bay-bounded vector beam touching a callout in PDF world space,
        splitting overly long continuous gridlines only at major perpendicular structural beams (never leader arrows)."""
        max_pts = float(max_span_ft) * self.pts_per_ft
        min_pts = float(min_span_ft) * self.pts_per_ft
        # Collect only major perpendicular structural beam lines (>= 6 ft) as valid bay boundaries
        perp_h = [round((sy1 + sy2) * 0.5, 2) for sx1, sy1, sx2, sy2, sft, ornt in self.bay_segments if ornt == "h" and sft >= min_span_ft]
        perp_v = [round((sx1 + sx2) * 0.5, 2) for sx1, sy1, sx2, sy2, sft, ornt in self.bay_segments if ornt == "v" and sft >= min_span_ft]

        best_seg = None
        best_d = float(max_perp_pts)
        for sx1, sy1, sx2, sy2, _, orient in self.bay_segments:
            if (orient == "h") != bool(is_horiz):
                continue
            abx, aby = sx2 - sx1, sy2 - sy1
            ab2 = abx * abx + aby * aby
            t = ((cx - sx1) * abx + (cy - sy1) * aby) / max(1.0, ab2)
            if -0.02 <= t <= 1.02:
                tc = max(0.0, min(1.0, t))
                perp_d = math.hypot(cx - (sx1 + tc * abx), cy - (sy1 + tc * aby))
                if perp_d < best_d:
                    csx1, csy1, csx2, csy2 = sx1, sy1, sx2, sy2
                    if is_horiz:
                        lx0, lx1 = min(sx1, sx2), max(sx1, sx2)
                        if (lx1 - lx0) > max_pts:
                            cuts = sorted({vx for vx in perp_v if (lx0 + min_pts) < vx < (lx1 - min_pts)})
                            lb = max([lx0] + [c for c in cuts if c <= cx])
                            rb = min([lx1] + [c for c in cuts if c >= cx])
                            if (rb - lb) > max_pts:
                                lb = max(lx0, cx - max_pts * 0.5)
                                rb = min(lx1, cx + max_pts * 0.5)
                            csx1, csx2 = lb, rb
                    else:
                        ly0, ly1 = min(sy1, sy2), max(sy1, sy2)
                        if (ly1 - ly0) > max_pts:
                            cuts = sorted({hy for hy in perp_h if (ly0 + min_pts) < hy < (ly1 - min_pts)})
                            tb = max([ly0] + [c for c in cuts if c <= cy])
                            bb = min([ly1] + [c for c in cuts if c >= cy])
                            if (bb - tb) > max_pts:
                                tb = max(ly0, cy - max_pts * 0.5)
                                bb = min(ly1, cy + max_pts * 0.5)
                            csy1, csy2 = tb, bb
                    span_pts = math.hypot(csx2 - csx1, csy2 - csy1)
                    if min_pts <= span_pts <= max_pts:
                        best_d = perp_d
                        best_seg = (csx1, csy1, csx2, csy2, round_structural_ft(span_pts / self.pts_per_ft))
        return best_seg


def _ocr_tile_worker(args):
    """Unified tile OCR worker: isolates pure black AutoCAD SHX text pen strokes
    (stripping walls, joists, and dimension lines) when vector drawings are present,
    or renders full raster for scanned PDFs, and scans across 0, 90, 270, +-32, +-45 deg."""
    from PIL import Image, ImageDraw

    pdf_path, page_num, rect_tuple, dpi, angles, tile_id = args
    rx0, ry0, rx1, ry1 = rect_tuple
    rect = pymupdf.Rect(rx0, ry0, rx1, ry1)
    doc = pymupdf.open(pdf_path)
    tmp_png = os.path.join(tempfile.gettempdir(), f"bm_tile_{os.getpid()}_{tile_id}.png")
    try:
        page = doc.load_page(int(page_num) - 1)
        max_side_pt = max(1.0, float(rect.width), float(rect.height))
        safe_dpi = max(240, min(int(dpi), int((1850.0 * 72.0) / max_side_pt)))
        sc = safe_dpi / 72.0

        # Check if tile contains AutoCAD SHX black text strokes (0.24..0.85 pen width, <= 12 pt)
        shx_strokes = []
        for drw in page.get_drawings():
            r = drw.get("rect")
            if not r or not rect.intersects(r):
                continue
            w_pen = round(float(drw.get("width") or 0.0), 2)
            col = drw.get("color") or ()
            is_blk = (len(col) >= 3 and col.__getitem__(0) < 0.1 and col.__getitem__(1) < 0.1 and col.__getitem__(2) < 0.1)
            if is_blk and 0.24 <= w_pen <= 0.85 and r.width <= 12.0 and r.height <= 12.0:
                shx_strokes.append((w_pen, drw.get("items", ())))

        if len(shx_strokes) >= 12:
            w_px = max(32, int(round(rect.width * sc)))
            h_px = max(32, int(round(rect.height * sc)))
            clean_im = Image.new("L", (w_px, h_px), 255)
            draw = ImageDraw.Draw(clean_im)
            for w_pen, items in shx_strokes:
                lw = max(2, int(round(w_pen * sc * 1.45)))
                for itm in items:
                    op = itm.__getitem__(0)
                    if op == "l" and len(itm) >= 3:
                        p1, p2 = itm.__getitem__(1), itm.__getitem__(2)
                        draw.line([((p1.x - rect.x0) * sc, (p1.y - rect.y0) * sc), ((p2.x - rect.x0) * sc, (p2.y - rect.y0) * sc)], fill=0, width=lw)
                    elif op == "c" and len(itm) >= 5:
                        p1, p2 = itm.__getitem__(1), itm.__getitem__(4)
                        draw.line([((p1.x - rect.x0) * sc, (p1.y - rect.y0) * sc), ((p2.x - rect.x0) * sc, (p2.y - rect.y0) * sc)], fill=0, width=lw)
            clean_im.save(tmp_png)
            eff_scale = 72.0 / float(safe_dpi)
        else:
            pix = page.get_pixmap(dpi=safe_dpi, clip=rect, alpha=False)
            pix.save(tmp_png)
            eff_scale = 72.0 / float(safe_dpi)
    finally:
        doc.close()

    ps_script = (
        "Add-Type -AssemblyName System.Runtime.WindowsRuntime;"
        "Add-Type -AssemblyName System.Drawing;"
        "$null = [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime];"
        "$null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime];"
        "$null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime];"
        "function Await($op, $t){$m=[System.WindowsRuntimeSystemExtensions].GetMethods()|?{$_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1}|select -First 1;$g=$m.MakeGenericMethod($t);$tk=$g.Invoke($null,@($op));$tk.Wait(-1)|Out-Null;$tk.Result};"
        "$eng = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages();"
        f"$baseBmp = New-Object System.Drawing.Bitmap('{tmp_png}');"
        "$bw = $baseBmp.Width; $bh = $baseBmp.Height;"
        f"foreach($ang in @({angles})) {{"
        "  $rotPng = [System.IO.Path]::ChangeExtension([System.IO.Path]::GetTempFileName(), '.png');"
        "  $bmpDraw = $null;"
        "  if($ang -eq 0){ $baseBmp.Save($rotPng, [System.Drawing.Imaging.ImageFormat]::Png); }"
        "  elseif($ang -eq 90){ $bmpDraw = $baseBmp.Clone(); $bmpDraw.RotateFlip([System.Drawing.RotateFlipType]::Rotate90FlipNone); $bmpDraw.Save($rotPng, [System.Drawing.Imaging.ImageFormat]::Png); }"
        "  elseif($ang -eq 270){ $bmpDraw = $baseBmp.Clone(); $bmpDraw.RotateFlip([System.Drawing.RotateFlipType]::Rotate270FlipNone); $bmpDraw.Save($rotPng, [System.Drawing.Imaging.ImageFormat]::Png); }"
        "  else {"
        "    $diag = [int][math]::Ceiling([math]::Sqrt($bw*$bw + $bh*$bh));"
        "    $bmpDraw = New-Object System.Drawing.Bitmap($diag, $diag);"
        "    $g = [System.Drawing.Graphics]::FromImage($bmpDraw);"
        "    $g.Clear([System.Drawing.Color]::White);"
        "    $g.TranslateTransform($diag/2.0, $diag/2.0);"
        "    $g.RotateTransform($ang);"
        "    $g.TranslateTransform(-$bw/2.0, -$bh/2.0);"
        "    $g.DrawImage($baseBmp, 0, 0, $bw, $bh);"
        "    $g.Dispose();"
        "    $bmpDraw.Save($rotPng, [System.Drawing.Imaging.ImageFormat]::Png);"
        "  }"
        "  $f = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($rotPng)) ([Windows.Storage.StorageFile]);"
        "  $st = Await ($f.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream]);"
        "  $dec = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($st)) ([Windows.Graphics.Imaging.BitmapDecoder]);"
        "  $sbmp = Await ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap]);"
        "  $res = Await ($eng.RecognizeAsync($sbmp)) ([Windows.Media.Ocr.OcrResult]);"
        "  $st.Dispose();"
        "  foreach($l in $res.Lines){"
        "    $w=$l.Words; if($w.Count -gt 0){$r0=$w.BoundingRect; Write-Output ('{0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}' -f $ang,$bw,$bh,[math]::Round($r0.X,1),[math]::Round($r0.Y,1),[math]::Round($r0.Width,1),[math]::Round($r0.Height,1),$l.Text)};"
        "    foreach($wi in $w){$r=$wi.BoundingRect; Write-Output ('{0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}' -f $ang,$bw,$bh,[math]::Round($r.X,1),[math]::Round($r.Y,1),[math]::Round($r.Width,1),[math]::Round($r.Height,1),$wi.Text)}"
        "  }"
        "  if($bmpDraw -ne $null){ $bmpDraw.Dispose(); }"
        "  Remove-Item $rotPng -Force -ErrorAction SilentlyContinue;"
        "}"
        "$baseBmp.Dispose();"
    )
    hits = []
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps_script],
            stderr=subprocess.DEVNULL,
            encoding="utf-8",
            errors="replace",
            timeout=35,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        for ln in out.splitlines():
            parts = ln.split("|", 7)
            if len(parts) == 8:
                ang = int(parts.__getitem__(0))
                bw, bh = float(parts.__getitem__(1)), float(parts.__getitem__(2))
                rx, ry = float(parts.__getitem__(3)), float(parts.__getitem__(4))
                rw, rh = float(parts.__getitem__(5)), float(parts.__getitem__(6))
                cx_r, cy_r = rx + rw * 0.5, ry + rh * 0.5
                if ang == 0:
                    ox, oy = cx_r, cy_r
                elif ang == 90:
                    ox, oy = cy_r, bh - cx_r
                elif ang == 270:
                    ox, oy = bw - cy_r, cx_r
                else:
                    diag = math.ceil(math.hypot(bw, bh))
                    rad = math.radians(-ang)
                    dx, dy = cx_r - diag * 0.5, cy_r - diag * 0.5
                    ox = dx * math.cos(rad) - dy * math.sin(rad) + bw * 0.5
                    oy = dx * math.sin(rad) + dy * math.cos(rad) + bh * 0.5
                wcx = rect.x0 + max(0.0, min(bw, ox)) * eff_scale
                wcy = rect.y0 + max(0.0, min(bh, oy)) * eff_scale
                hw, hh = (rw * eff_scale) * 0.5, (rh * eff_scale) * 0.5
                ntxt = normalize_cad_text(parts.__getitem__(7))
                if ntxt:
                    hits.append((wcx - hw, wcy - hh, wcx + hw, wcy + hh, ntxt))
    except Exception:
        pass
    finally:
        if os.path.exists(tmp_png):
            try:
                os.remove(tmp_png)
            except OSError:
                pass
    return hits


def scan_world_ocr(page, world_rect=None, dpi=320, multi_angle=True):
    """Unified Dynamic Neighbor-Aware Grid OCR: pads drag-box selections by +18 PDF pts
    and subdivides ANY region (drag-box OR full sheet) into overlapping <=360pt tiles
    at 320 DPI across 0, 90, 270, +-30, +-45 deg, stitching split HSS/W tokens."""
    from concurrent.futures import ThreadPoolExecutor

    pdf_path = getattr(getattr(page, "parent", None), "name", None)
    page_num = int(getattr(page, "number", 0)) + 1
    pw, ph = float(page.rect.width), float(page.rect.height)

    if world_rect is not None:
        r = pymupdf.Rect(world_rect)
        rx0 = max(0.0, r.x0 - 18.0)
        ry0 = max(0.0, r.y0 - 18.0)
        rx1 = min(pw, r.x1 + 18.0)
        ry1 = min(ph, r.y1 + 18.0)
    else:
        rx0, ry0, rx1, ry1 = 0.0, 0.0, pw * 0.90, ph * 0.95

    span_w, span_h = max(1.0, rx1 - rx0), max(1.0, ry1 - ry0)
    target_tile_pts = 360.0
    cols = max(1, int(math.ceil(span_w / target_tile_pts)))
    rows = max(1, int(math.ceil(span_h / target_tile_pts)))
    tile_w, tile_h = span_w / cols, span_h / rows
    ov_x, ov_y = (tile_w * 0.16 if cols > 1 else 0.0), (tile_h * 0.16 if rows > 1 else 0.0)

    tasks = []
    for r_i in range(rows):
        for c_i in range(cols):
            tx0 = max(rx0, rx0 + c_i * tile_w - (ov_x if c_i > 0 else 0.0))
            ty0 = max(ry0, ry0 + r_i * tile_h - (ov_y if r_i > 0 else 0.0))
            tx1 = min(rx1, rx0 + (c_i + 1) * tile_w + (ov_x if c_i < cols - 1 else 0.0))
            ty1 = min(ry1, ry0 + (r_i + 1) * tile_h + (ov_y if r_i < rows - 1 else 0.0))
            tasks.append((pdf_path, page_num, (tx0, ty0, tx1, ty1), 320, "0,90,270,32,45,315,328", f"r{r_i}c{c_i}"))

    merged_hits = []
    with ThreadPoolExecutor(max_workers=min(6, len(tasks))) as pool:
        for t_hits in pool.map(_ocr_tile_worker, tasks):
            for hx0, hy0, hx1, hy1, htxt in t_hits:
                hcx, hcy = (hx0 + hx1) * 0.5, (hy0 + hy1) * 0.5
                if any(
                    t0 == htxt and math.hypot(hcx - ((a0 + a1) * 0.5), hcy - ((b0 + b1) * 0.5)) < 10.0
                    for a0, b0, a1, b1, t0 in merged_hits
                ):
                    continue
                merged_hits.append((hx0, hy0, hx1, hy1, htxt))

    # Stitch adjacent split OCR tokens (e.g. 'HSS' + '4X2X1/4' -> 'HSS4X2X1/4', 'W12' + 'X53' -> 'W12X53')
    stitched = list(merged_hits)
    for i, (ax0, ay0, ax1, ay1, atxt) in enumerate(merged_hits):
        if atxt in ("HSS", "W", "PL", "MC", "C", "L") or re.match(r"^(W\d+|HSS\d+X\d+)$", atxt):
            acx, acy = (ax0 + ax1) * 0.5, (ay0 + ay1) * 0.5
            for j, (bx0, by0, bx1, by1, btxt) in enumerate(merged_hits):
                if i == j:
                    continue
                bcx, bcy = (bx0 + bx1) * 0.5, (by0 + by1) * 0.5
                if math.hypot(bcx - acx, bcy - acy) <= 45.0:
                    comb = normalize_cad_text(atxt + btxt)
                    if re.match(r"^(W\d+X\d+|HSS\d+(?:\.\d+)?X\d+(?:\.\d+)?X\d+/\d+|PL\d+/\d+X\d+)$", comb):
                        stitched.append((min(ax0, bx0), min(ay0, by0), max(ax1, bx1), max(ay1, by1), comb))
    return stitched


class PlanWorldModel:
    """Central world-space coordinator for a planset PDF across BOM, OCR, OSNAP, Measure, and Color Key."""

    def __init__(self, pdf_path=None):
        self.pdf_path = pdf_path
        self.sheet_scales = {}
        self._states = {}
        self._load_calibrations()

    def _calib_file(self):
        if not self.pdf_path or not os.path.exists(str(self.pdf_path)):
            return None
        import hashlib
        st = os.stat(self.pdf_path)
        sig = hashlib.sha256(f"{os.path.basename(self.pdf_path)}:{st.st_size}:{int(st.st_mtime)}".encode("utf-8")).hexdigest()[:20]
        base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
        cdir = os.path.join(base, "BowmanMortonPricingSuite", "calibrations")
        os.makedirs(cdir, exist_ok=True)
        return os.path.join(cdir, f"{sig}.json")

    def _load_calibrations(self):
        cf = self._calib_file()
        if cf and os.path.exists(cf):
            try:
                import json
                with open(cf, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                self.sheet_scales = {int(k): float(v) for k, v in raw.items() if float(v) > 0}
            except Exception:
                pass

    def _save_calibrations(self):
        cf = self._calib_file()
        if cf:
            try:
                import json
                with open(cf, "w", encoding="utf-8") as f:
                    json.dump({str(k): float(v) for k, v in self.sheet_scales.items()}, f, indent=2)
            except Exception:
                pass

    def set_sheet_scale(self, page_num, pts_per_ft):
        pno = int(page_num)
        self.sheet_scales[pno] = float(pts_per_ft)
        self._states.pop(pno, None)
        self._save_calibrations()

    def get_sheet(self, doc, page_num):
        pno = int(page_num)
        if pno not in self._states:
            pg = doc.load_page(pno - 1)
            override = self.sheet_scales.get(pno)
            self._states[pno] = SheetWorldState(pg, pno, pts_per_ft=override)
        return self._states[pno]