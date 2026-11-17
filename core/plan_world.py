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


def scan_world_ocr(page, world_rect=None, dpi=200, multi_angle=True):
    """Runs Windows Native OCR on a PDF world rectangle across 0°, 90°, 270° (and ±45° for clipped boxes)
    so vertical and angled SHX steel callouts are read and mapped back to exact PDF world coordinates."""
    pw, ph = float(page.rect.width), float(page.rect.height)
    rect = world_rect or pymupdf.Rect(0, 0, pw * 0.88, ph * 0.94)
    pix = page.get_pixmap(dpi=int(dpi), clip=rect, alpha=False)
    tmp_png = os.path.join(tempfile.gettempdir(), f"bm_world_ocr_{os.getpid()}.png")
    pix.save(tmp_png)
    scale = 72.0 / float(dpi)
    angles = "0,90,270,45,315" if world_rect is not None else ("0,90,270" if multi_angle else "0")

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
        "    $w=$l.Words; if($w.Count -gt 0){$r0=$w[0].BoundingRect; Write-Output ('{0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}' -f $ang,$bw,$bh,[math]::Round($r0.X,1),[math]::Round($r0.Y,1),[math]::Round($r0.Width,1),[math]::Round($r0.Height,1),$l.Text)};"
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
            text=True,
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
                wcx = rect.x0 + max(0.0, min(bw, ox)) * scale
                wcy = rect.y0 + max(0.0, min(bh, oy)) * scale
                hw, hh = (rw * scale) * 0.5, (rh * scale) * 0.5
                hits.append((wcx - hw, wcy - hh, wcx + hw, wcy + hh, normalize_cad_text(parts.__getitem__(7))))
    except Exception:
        pass
    finally:
        if os.path.exists(tmp_png):
            try:
                os.remove(tmp_png)
            except OSError:
                pass
    return hits


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