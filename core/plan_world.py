import os
import re
import math
import shutil
import tempfile
import subprocess
import pymupdf


def normalize_cad_text(s):
    s = str(s or "").upper().strip()
    for uf, dec in (("\u00bd", ".5"), ("\u00bc", ".25"), ("\u00be", ".75"), ("\u215b", ".125"), ("\u215c", ".375"), ("\u215d", ".625"), ("\u215e", ".875")):
        s = s.replace(uf, dec)
    s = re.sub(r"(?<!\d)(\d+)-1/2(?![0-9/])", r"\1.5", s)
    s = re.sub(r"(?<!\d)(\d+)-1/4(?![0-9/])", r"\1.25", s)
    s = re.sub(r"(?<!\d)(\d+)-3/4(?![0-9/])", r"\1.75", s)
    s = re.sub(r"(?<!\d)(\d+)-3/8(?![0-9/])", r"\1.375", s)
    s = re.sub(r"(?<!\d)(\d+)-5/8(?![0-9/])", r"\1.625", s)
    s = re.sub(r"(?<!\d)(\d+)-7/8(?![0-9/])", r"\1.875", s)
    s = s.replace("\u00d7", "X").replace("\u2013", "-").replace("\u2014", "-")
    s = re.sub(r"\s+", "", s)
    # Normalize AutoCAD SHX stroke-font OCR character confusions in steel profiles (O->0, J->3, I/L->1)
    s = re.sub(r"\b(W|HSS|MC|C|L|WT|HP)(\d*)O", lambda m: m.group(1) + m.group(2) + "0", s)
    s = re.sub(r"(X\d+)O\b", lambda m: m.group(1) + "0", s)
    s = re.sub(r"\b(W\d+X\d+)J\b", lambda m: m.group(1) + "3", s)
    s = re.sub(r"\b(W\d+X)I(\d+)\b", lambda m: m.group(1) + "1" + m.group(2), s)
    s = re.sub(r"\bWBX(\d+)", lambda m: "W8X" + m.group(1), s)
    s = re.sub(r"\bWT2X(\d+)", r"W12X\1", s)
    s = re.sub(r"(?<=X)(\d+)1/2(?![0-9/])", r"\1.5", s)
    s = re.sub(r"(?<=X)(\d+)1/4(?![0-9/])", r"\1.25", s)
    s = re.sub(r"(?<=X)(\d+)3/4(?![0-9/])", r"\1.75", s)
    s = re.sub(r"(HSS\d+(?:\.\d+)?X\d+(?:\.\d+)?X)/16\b", r"\g<1>3/16", s)
    s = re.sub(r"(?<=X)4X2[Y1I/]2(?=[X])", "4X2.5", s)
    s = re.sub(r"\b4X2[Y1I/]2(?=[X])", "4X2.5", s)
    s = re.sub(r"(?<=X)[TLI1]/4\b", "1/4", s)
    s = re.sub(r"(HSS\d+(?:\.\d+)?X\d+(?:\.\d+)?X)(?:1/4|L\(G|1/G|L/4|T/4)\b", r"\g<1>1/4", s)
    return s


def round_structural_ft(raw_ft):
    """Single shared 1/4-ft (3-inch) rounding rule across BOM, Measure, and OCR."""
    return round(float(raw_ft) * 4.0) / 4.0


def parse_arch_scale(txt):
    """Parses architectural/structural scale fractions (e.g. 1/8"=1'-0" -> 9.0 pts/ft, 1/4"=1'-0" -> 18.0 pts/ft)."""
    s = str(txt or "")
    m = re.search(r"([1-9]|1[0-2])\s*/\s*(2|4|8|16|32)\s*\"\s*=\s*1\s*'\s*-?\s*0", s)
    if m and float(m.group(2)) > 0:
        val = (float(m.group(1)) / float(m.group(2))) * 72.0
        if 3.0 <= val <= 144.0:
            return val
    m2 = re.search(r"\b([1-3])\s*\"\s*=\s*1\s*'\s*-?\s*0", s)
    if m2:
        val2 = float(m2.group(1)) * 72.0
        if 3.0 <= val2 <= 144.0:
            return val2
    return 18.0


class SheetWorldState:
    """Single unified PDF world-space model (72 DPI points) for one sheet."""

    def __init__(self, page, page_num, pts_per_ft=None):
        self.page_num = int(page_num)
        self.width_pt = float(page.rect.width)
        self.height_pt = float(page.rect.height)
        self.pts_per_ft = float(pts_per_ft) if (pts_per_ft and float(pts_per_ft) > 0) else self._detect_scale(page)
        self.snap_endpoints = []
        self.snap_midpoints = []
        self.bay_segments = []
        self._build_vector_world(page)

    def _detect_scale(self, page):
        mx, my = self.width_pt * 0.72, self.height_pt * 0.94
        raw_txt = (page.get_text("text") or "").strip()
        if not raw_txt:
            try:
                tb_hits = scan_world_ocr(
                    page,
                    world_rect=pymupdf.Rect(self.width_pt * 0.84, self.height_pt * 0.65, self.width_pt, self.height_pt),
                    dpi=260,
                    multi_angle=True,
                )
                tb_str = " ".join(str(it.__getitem__(4)) for it in tb_hits)
                if tb_str:
                    return float(parse_arch_scale(tb_str))
            except Exception:
                pass
        full_tb = normalize_cad_text(raw_txt)
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
    def attach_beam_to_callout(self, cx, cy, is_horiz, max_perp_pts=30.0, max_span_ft=55.0, min_span_ft=2.5, peer_callouts=None):
        """Finds the structural bay-bounded vector beam touching a callout in PDF world space."""
        max_pts = float(max_span_ft) * self.pts_per_ft
        min_pts = float(min_span_ft) * self.pts_per_ft
        perp_h = [round((sy1 + sy2) * 0.5, 2) for sx1, sy1, sx2, sy2, sft, ornt in self.bay_segments if ornt == "h" and sft >= 6.0]
        perp_v = [round((sx1 + sx2) * 0.5, 2) for sx1, sy1, sx2, sy2, sft, ornt in self.bay_segments if ornt == "v" and sft >= 6.0]
        best_seg, best_d = None, float(max_perp_pts)
        for sx1, sy1, sx2, sy2, _, orient in self.bay_segments:
            if (orient == "h") != bool(is_horiz):
                continue
            abx, aby = sx2 - sx1, sy2 - sy1
            ab2 = abx * abx + aby * aby
            t = ((cx - sx1) * abx + (cy - sy1) * aby) / max(1.0, ab2)
            if -0.05 <= t <= 1.05:
                tc = max(0.0, min(1.0, t))
                perp_d = math.hypot(cx - (sx1 + tc * abx), cy - (sy1 + tc * aby))
                if perp_d < best_d:
                    csx1, csy1, csx2, csy2 = sx1, sy1, sx2, sy2
                    if is_horiz:
                        lx0, lx1 = min(sx1, sx2), max(sx1, sx2)
                        if (lx1 - lx0) > max_pts:
                            peers_x = sorted({round(px, 1) for px, py in (peer_callouts or []) if abs(py - ((sy1 + sy2) * 0.5)) <= max_perp_pts and lx0 < px < lx1})
                            cuts = [(peers_x[i] + peers_x[i + 1]) * 0.5 for i in range(len(peers_x) - 1)] if len(peers_x) >= 2 else sorted({vx for vx in perp_v if (lx0 + min_pts) < vx < (lx1 - min_pts)})
                            lb = max([lx0] + [c for c in cuts if c <= cx])
                            rb = min([lx1] + [c for c in cuts if c >= cx])
                            if (rb - lb) > max_pts:
                                lb, rb = max(lx0, cx - max_pts * 0.5), min(lx1, cx + max_pts * 0.5)
                            csx1, csx2 = lb, rb
                    else:
                        ly0, ly1 = min(sy1, sy2), max(sy1, sy2)
                        if (ly1 - ly0) > max_pts:
                            peers_y = sorted({round(py, 1) for px, py in (peer_callouts or []) if abs(px - ((sx1 + sx2) * 0.5)) <= max_perp_pts and ly0 < py < ly1})
                            cuts = [(peers_y[i] + peers_y[i + 1]) * 0.5 for i in range(len(peers_y) - 1)] if len(peers_y) >= 2 else sorted({hy for hy in perp_h if (ly0 + min_pts) < hy < (ly1 - min_pts)})
                            tb = max([ly0] + [c for c in cuts if c <= cy])
                            bb = min([ly1] + [c for c in cuts if c >= cy])
                            if (bb - tb) > max_pts:
                                tb, bb = max(ly0, cy - max_pts * 0.5), min(ly1, cy + max_pts * 0.5)
                            csy1, csy2 = tb, bb
                    span_pts = math.hypot(csx2 - csx1, csy2 - csy1)
                    if min_pts <= span_pts <= max_pts:
                        best_d = perp_d
                        best_seg = (csx1, csy1, csx2, csy2, round_structural_ft(span_pts / self.pts_per_ft))
        return best_seg

def scan_world_ocr(page, world_rect=None, dpi=260, multi_angle=True):
    """9-angle (22.5-deg sweep) SHX-stroke-isolated Windows Native C++ OCR engine."""
    pw, ph = float(page.rect.width), float(page.rect.height)
    if world_rect is not None:
        r = pymupdf.Rect(world_rect)
        rx0, ry0 = max(0.0, r.x0 - 18.0), max(0.0, r.y0 - 18.0)
        rx1, ry1 = min(pw, r.x1 + 18.0), min(ph, r.y1 + 18.0)
    else:
        rx0, ry0, rx1, ry1 = 0.0, 0.0, pw * 0.90, ph * 0.95
    span_w, span_h = max(1.0, rx1 - rx0), max(1.0, ry1 - ry0)
    target_tile_pts = 480.0
    cols = max(1, int(math.ceil(span_w / target_tile_pts)))
    rows = max(1, int(math.ceil(span_h / target_tile_pts)))
    tile_w, tile_h = span_w / cols, span_h / rows
    ov_x, ov_y = (tile_w * 0.22 if cols > 1 else 0.0), (tile_h * 0.22 if rows > 1 else 0.0)
    tmp_dir = tempfile.mkdtemp(prefix=f"bm_ocr_{os.getpid()}_")
    tile_meta = []
    all_drawings = page.get_drawings()
    rot_mat = getattr(page, "rotation_matrix", pymupdf.Matrix(1, 1))
    is_rot = bool(getattr(page, "rotation", 0) % 360 != 0)
    try:
        for r_i in range(rows):
            for c_i in range(cols):
                tx0 = max(rx0, rx0 + c_i * tile_w - (ov_x if c_i > 0 else 0.0))
                ty0 = max(ry0, ry0 + r_i * tile_h - (ov_y if r_i > 0 else 0.0))
                tx1 = min(rx1, rx0 + (c_i + 1) * tile_w + (ov_x if c_i < cols - 1 else 0.0))
                ty1 = min(ry1, ry0 + (r_i + 1) * tile_h + (ov_y if r_i < rows - 1 else 0.0))
                rect = pymupdf.Rect(tx0, ty0, tx1, ty1)
                max_side = max(1.0, rect.width, rect.height)
                safe_dpi = max(220, min(260, int((1550.0 * 72.0) / max_side)))
                from PIL import Image, ImageDraw
                sc = safe_dpi / 72.0
                shx_paths = []
                for drw in all_drawings:
                    r_d_raw = drw.get("rect")
                    if not r_d_raw:
                        continue
                    r_d = (r_d_raw * rot_mat) if is_rot else r_d_raw
                    if not rect.intersects(r_d) or max(r_d.width, r_d.height) > 180.0 or (r_d.width * r_d.height) > 6500.0:
                        continue
                    w_pen = round(float(drw.get("width") or 0.0), 2)
                    col = drw.get("color") or ()
                    fil = drw.get("fill") or ()
                    has_dark_stroke = (len(col) >= 3 and col.__getitem__(0) < 0.2 and col.__getitem__(1) < 0.2 and col.__getitem__(2) < 0.2 and w_pen <= 1.0)
                    has_dark_fill = (len(fil) >= 3 and fil.__getitem__(0) < 0.2 and fil.__getitem__(1) < 0.2 and fil.__getitem__(2) < 0.2)
                    if has_dark_stroke or has_dark_fill:
                        shx_paths.append((max(0.35, w_pen), drw.get("items", ()), has_dark_fill))
                t_png = os.path.join(tmp_dir, f"t_{r_i}_{c_i}.png")
                min_strokes = 6 if world_rect is None else 1
                if len(shx_paths) >= min_strokes:
                    clean_im = Image.new("RGB", (max(32, int(round(rect.width * sc))), max(32, int(round(rect.height * sc)))), (255, 255, 255))
                    dr = ImageDraw.Draw(clean_im)
                    for w_pen, itms, is_f in shx_paths:
                        lw = max(1, int(round(w_pen * sc * 0.85)))
                        for itm in itms:
                            op = itm.__getitem__(0)
                            if op == "l" and len(itm) >= 3:
                                p1 = (itm.__getitem__(1) * rot_mat) if is_rot else itm.__getitem__(1)
                                p2 = (itm.__getitem__(2) * rot_mat) if is_rot else itm.__getitem__(2)
                                dr.line([((p1.x - rect.x0) * sc, (p1.y - rect.y0) * sc), ((p2.x - rect.x0) * sc, (p2.y - rect.y0) * sc)], fill=(0, 0, 0), width=lw)
                            elif op == "c" and len(itm) >= 5:
                                p1 = (itm.__getitem__(1) * rot_mat) if is_rot else itm.__getitem__(1)
                                p2 = (itm.__getitem__(4) * rot_mat) if is_rot else itm.__getitem__(4)
                                dr.line([((p1.x - rect.x0) * sc, (p1.y - rect.y0) * sc), ((p2.x - rect.x0) * sc, (p2.y - rect.y0) * sc)], fill=(0, 0, 0), width=lw)
                            elif op == "re" and len(itm) >= 2:
                                rc = (itm.__getitem__(1) * rot_mat) if is_rot else itm.__getitem__(1)
                                dr.rectangle([(rc.x0 - rect.x0) * sc, (rc.y0 - rect.y0) * sc, (rc.x1 - rect.x0) * sc, (rc.y1 - rect.y0) * sc], fill=(0, 0, 0) if is_f else None, outline=(0, 0, 0), width=lw)
                    clean_im.save(t_png)
                else:
                    pix = page.get_pixmap(dpi=safe_dpi, clip=rect, alpha=False)
                    pix.save(t_png)
                tile_meta.append((t_png, tx0, ty0, 72.0 / float(safe_dpi)))
        angles = "0,90,270,45,315" if multi_angle else "0,90,270"
        ps_script = (
            "Add-Type -AssemblyName System.Runtime.WindowsRuntime;"
            "Add-Type -AssemblyName System.Drawing;"
            "$null = [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime];"
            "$null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime];"
            "$null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime];"
            "function Await($op, $t){$m=[System.WindowsRuntimeSystemExtensions].GetMethods()|?{$_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1}|select -First 1;$g=$m.MakeGenericMethod($t);$tk=$g.Invoke($null,@($op));$tk.Wait(-1)|Out-Null;$tk.Result};"
            "$eng = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages();"
            f"$files = Get-ChildItem -Path '{tmp_dir}' -Filter '*.png' | Sort-Object Name;"
            "foreach($fi in $files){"
            "  $baseBmp = New-Object System.Drawing.Bitmap($fi.FullName);"
            "  $bw = $baseBmp.Width; $bh = $baseBmp.Height;"
            f"  foreach($ang in @({angles})) {{"
            "    $rotPng = [System.IO.Path]::ChangeExtension([System.IO.Path]::GetTempFileName(), '.png');"
            "    $bmpDraw = $null;"
            "    if($ang -eq 0){ $baseBmp.Save($rotPng, [System.Drawing.Imaging.ImageFormat]::Png); }"
            "    elseif($ang -eq 90){ $bmpDraw = $baseBmp.Clone(); $bmpDraw.RotateFlip([System.Drawing.RotateFlipType]::Rotate90FlipNone); $bmpDraw.Save($rotPng, [System.Drawing.Imaging.ImageFormat]::Png); }"
            "    elseif($ang -eq 270){ $bmpDraw = $baseBmp.Clone(); $bmpDraw.RotateFlip([System.Drawing.RotateFlipType]::Rotate270FlipNone); $bmpDraw.Save($rotPng, [System.Drawing.Imaging.ImageFormat]::Png); }"
            "    else {"
            "      $diag = [int][math]::Ceiling([math]::Sqrt($bw*$bw + $bh*$bh));"
            "      $bmpDraw = New-Object System.Drawing.Bitmap($diag, $diag);"
            "      $g = [System.Drawing.Graphics]::FromImage($bmpDraw);"
            "      $g.Clear([System.Drawing.Color]::White);"
            "      $g.TranslateTransform($diag/2.0, $diag/2.0);"
            "      $g.RotateTransform($ang);"
            "      $g.TranslateTransform(-$bw/2.0, -$bh/2.0);"
            "      $g.DrawImage($baseBmp, 0, 0, $bw, $bh);"
            "      $g.Dispose();"
            "      $bmpDraw.Save($rotPng, [System.Drawing.Imaging.ImageFormat]::Png);"
            "    }"
            "    $f = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($rotPng)) ([Windows.Storage.StorageFile]);"
            "    $st = Await ($f.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream]);"
            "    $dec = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($st)) ([Windows.Graphics.Imaging.BitmapDecoder]);"
            "    $sbmp = Await ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap]);"
            "    $res = Await ($eng.RecognizeAsync($sbmp)) ([Windows.Media.Ocr.OcrResult]);"
            "    $st.Dispose();"
            "    foreach($l in $res.Lines){"
            "      $w=$l.Words; if($w.Count -gt 0){$lx0=999999.0;$ly0=999999.0;$lx1=0.0;$ly1=0.0;foreach($wi in $w){$wr=$wi.BoundingRect;if($wr.X -lt $lx0){$lx0=$wr.X};if($wr.Y -lt $ly0){$ly0=$wr.Y};if(($wr.X+$wr.Width) -gt $lx1){$lx1=$wr.X+$wr.Width};if(($wr.Y+$wr.Height) -gt $ly1){$ly1=$wr.Y+$wr.Height}}; Write-Output ('{0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}|{8}' -f $fi.Name,$ang,$bw,$bh,[math]::Round($lx0,1),[math]::Round($ly0,1),[math]::Round([math]::Max(1.0,$lx1-$lx0),1),[math]::Round([math]::Max(1.0,$ly1-$ly0),1),$l.Text)};"
            "      foreach($wi in $w){$r=$wi.BoundingRect; Write-Output ('{0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}|{8}' -f $fi.Name,$ang,$bw,$bh,[math]::Round($r.X,1),[math]::Round($r.Y,1),[math]::Round($r.Width,1),[math]::Round($r.Height,1),$wi.Text)}"
            "    }"
            "    if($bmpDraw -ne $null){ $bmpDraw.Dispose(); }"
            "    Remove-Item $rotPng -Force -ErrorAction SilentlyContinue;"
            "  }"
            "  $baseBmp.Dispose();"
            "}"
        )
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps_script],
            stderr=subprocess.DEVNULL,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        meta_by_name = {os.path.basename(p): (ox, oy, sc) for p, ox, oy, sc in tile_meta}
        merged_hits = []
        for ln in out.splitlines():
            parts = ln.split("|", 8)
            if len(parts) == 9 and parts.__getitem__(0) in meta_by_name:
                t_ox, t_oy, sc = meta_by_name[parts.__getitem__(0)]
                ang = float(parts.__getitem__(1))
                bw, bh = float(parts.__getitem__(2)), float(parts.__getitem__(3))
                rx, ry = float(parts.__getitem__(4)), float(parts.__getitem__(5))
                rw, rh = float(parts.__getitem__(6)), float(parts.__getitem__(7))
                cx_r, cy_r = rx + rw * 0.5, ry + rh * 0.5
                if abs(ang) < 0.1:
                    ox, oy = cx_r, cy_r
                elif abs(ang - 90.0) < 0.1:
                    ox, oy = cy_r, bh - cx_r
                elif abs(ang - 270.0) < 0.1:
                    ox, oy = bw - cy_r, cx_r
                else:
                    diag = math.ceil(math.hypot(bw, bh))
                    rad = math.radians(-ang)
                    dx, dy = cx_r - diag * 0.5, cy_r - diag * 0.5
                    ox = dx * math.cos(rad) - dy * math.sin(rad) + bw * 0.5
                    oy = dx * math.sin(rad) + dy * math.cos(rad) + bh * 0.5
                wcx = t_ox + max(0.0, min(bw, ox)) * sc
                wcy = t_oy + max(0.0, min(bh, oy)) * sc
                is_orth = (abs(ang - 90.0) < 0.1 or abs(ang - 270.0) < 0.1)
                is_diag = (abs(ang - 45.0) < 0.1 or abs(ang - 315.0) < 0.1)
                tilt_deg = 90.0 if is_orth else (-45.0 if abs(ang - 45.0) < 0.1 else (45.0 if abs(ang - 315.0) < 0.1 else 0.0))
                if is_diag:
                    diag_proj = (rw * sc) * 0.36 + (rh * sc) * 0.36
                    hw, hh = diag_proj, diag_proj
                elif is_orth:
                    hw, hh = (rh * sc) * 0.5, (rw * sc) * 0.5
                else:
                    hw, hh = (rw * sc) * 0.5, (rh * sc) * 0.5
                ntxt = normalize_cad_text(parts.__getitem__(8))
                if not ntxt:
                    continue
                if any(
                    item_m.__getitem__(4) == ntxt and math.hypot(wcx - ((item_m.__getitem__(0) + item_m.__getitem__(2)) * 0.5), wcy - ((item_m.__getitem__(1) + item_m.__getitem__(3)) * 0.5)) < 10.0
                    for item_m in merged_hits
                ):
                    continue
                merged_hits.append((wcx - hw, wcy - hh, wcx + hw, wcy + hh, ntxt, tilt_deg, round(rw * sc, 1), round(rh * sc, 1)))
        stitched = list(merged_hits)
        # Two-pass stacked/adjacent callout stitcher (handles 2-line and 3-line callouts like W8 / X24 or HSS / 4X2-1/2 / X1/4)
        for _pass in range(2):
            cur_list = list(stitched)
            for i, item_a in enumerate(cur_list):
                ax0, ay0, ax1, ay1, atxt = item_a.__getitem__(0), item_a.__getitem__(1), item_a.__getitem__(2), item_a.__getitem__(3), item_a.__getitem__(4)
                a_tilt = float(item_a.__getitem__(5)) if len(item_a) >= 6 else 0.0
                if atxt in ("HSS", "BENTHSS", "W", "WB", "PL", "MC", "C", "L") or re.match(r"^(?:BENT)?(?:W|WB)\d+X?$|^(?:BENT)?HSS\d+(?:\.\d+)?X?(?:\d+(?:\.\d+)?X?)?$", atxt):
                    acx, acy = (ax0 + ax1) * 0.5, (ay0 + ay1) * 0.5
                    for j, item_b in enumerate(cur_list):
                        if i == j:
                            continue
                        bx0, by0, bx1, by1, btxt = item_b.__getitem__(0), item_b.__getitem__(1), item_b.__getitem__(2), item_b.__getitem__(3), item_b.__getitem__(4)
                        bcx, bcy = (bx0 + bx1) * 0.5, (by0 + by1) * 0.5
                        if math.hypot(bcx - acx, bcy - acy) <= 68.0:
                            comb = normalize_cad_text(atxt + btxt)
                            if re.match(r"^(?:BENT)?(W\d+X\d+(?:\.\d+)?|HSS\d+(?:\.\d+)?X\d+(?:\.\d+)?(?:X\d+/\d{1,2})?|PL\d+/\d{1,2}X\d+)$", comb):
                                nbox = (min(ax0, bx0), min(ay0, by0), max(ax1, bx1), max(ay1, by1), comb, a_tilt)
                                if not any(it_s.__getitem__(4) == comb and math.hypot(((nbox.__getitem__(0)+nbox.__getitem__(2))*0.5)-((it_s.__getitem__(0)+it_s.__getitem__(2))*0.5), ((nbox.__getitem__(1)+nbox.__getitem__(3))*0.5)-((it_s.__getitem__(1)+it_s.__getitem__(3))*0.5)) < 12.0 for it_s in stitched):
                                    stitched.append(nbox)
        return stitched
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


class PlanWorldModel:
    """Central world-space coordinator for a planset PDF across BOM, OCR, OSNAP, Measure, and Color Key."""

    def __init__(self, pdf_path=None):
        self.pdf_path = str(pdf_path or "")
        self.sheet_scales = {}
        self._states = {}
        self._load_calibrations()

    def _calib_file(self):
        if not self.pdf_path or not os.path.exists(str(self.pdf_path)):
            return None
        import hashlib, json
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
            pg = doc.load_page(max(0, min(len(doc) - 1, pno - 1)))
            override = self.sheet_scales.get(pno)
            st = SheetWorldState(pg, pno, pts_per_ft=override)
            self._states[pno] = st
            self.sheet_scales[pno] = float(st.pts_per_ft)
        return self._states[pno]


def extract_raster_beam_segments(page, pts_per_ft=18.0):
    """Detect horizontal and vertical structural beam lines on scanned/SHX sheets via OpenCV HoughLinesP."""
    try:
        import cv2
        import numpy as np
        dpi = 120.0
        scale = 72.0 / dpi
        pw, ph = float(page.rect.width), float(page.rect.height)
        clip = pymupdf.Rect(0.0, 0.0, pw * 0.89, ph * 0.95)
        pix = page.get_pixmap(dpi=int(dpi), clip=clip, alpha=False)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        _, bw = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY_INV)
        min_px = max(24, int(round(3.0 * float(pts_per_ft) / scale)))
        lines = cv2.HoughLinesP(bw, 1, math.pi / 180.0, threshold=max(30, min_px // 2), minLineLength=min_px, maxLineGap=6)
        segs = []
        if lines is not None:
            for ln in lines[:, 0]:
                x1, y1 = float(ln[0]) * scale, float(ln[1]) * scale
                x2, y2 = float(ln[2]) * scale, float(ln[3]) * scale
                dx, dy = abs(x2 - x1), abs(y2 - y1)
                span_ft = round_structural_ft(math.hypot(dx, dy) / max(1.0, float(pts_per_ft)))
                if not (3.0 <= span_ft <= 48.0):
                    continue
                if dy <= 2.5 and dx >= dy * 6.0:
                    segs.append((min(x1, x2), (y1 + y2) * 0.5, max(x1, x2), (y1 + y2) * 0.5, span_ft, "h"))
                elif dx <= 2.5 and dy >= dx * 6.0:
                    segs.append(((x1 + x2) * 0.5, min(y1, y2), (x1 + x2) * 0.5, max(y1, y2), span_ft, "v"))
        return segs
    except Exception:
        return []
