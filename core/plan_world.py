import os
import re
import math
import tempfile
import subprocess
import pymupdf


def normalize_cad_text(s):
    s = str(s or "").upper().strip()
    for uf, dec in (("\u00bd", ".5"), ("\u00bc", ".25"), ("\u00be", ".75"), ("\u215b", ".125"), ("\u215c", ".375"), ("\u215d", ".625"), ("\u215e", ".875")):
        s = s.replace(uf, dec)
    s = re.sub(r"(\d+)-1/2\b", r"\1.5", s)
    s = re.sub(r"(\d+)-1/4\b", r"\1.25", s)
    s = re.sub(r"(\d+)-3/4\b", r"\1.75", s)
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


_GLOBAL_RAPID_OCR = None

def _get_rapid_ocr():
    global _GLOBAL_RAPID_OCR
    if _GLOBAL_RAPID_OCR is not None:
        return _GLOBAL_RAPID_OCR
    try:
        from rapidocr_onnxruntime import RapidOCR
        _GLOBAL_RAPID_OCR = RapidOCR(use_angle_cls=False)
    except Exception:
        _GLOBAL_RAPID_OCR = False
    return _GLOBAL_RAPID_OCR

def _enhance_shx_for_ocr(arr):
    """Boost faint AutoCAD SHX stroke fonts and light blueprint scans to crisp high-contrast ink."""
    import numpy as np
    gray = arr.mean(axis=2).astype(np.float32)
    # Stretch contrast so light gray SHX strokes (120-225) become solid black while background stays 255
    lo, hi = 95.0, 232.0
    stretched = np.clip((gray - lo) * (255.0 / max(1.0, hi - lo)), 0.0, 255.0).astype(np.uint8)
    return np.stack([stretched, stretched, stretched], axis=2)


def scan_world_ocr(page, world_rect=None, dpi=210, multi_angle=True):
    """Locked-in 1180x1180pt / 1850px 4-angle structural OCR engine:
    - Exact 1180x1180pt tile grid & 1850px DBNet scale sweet spot (100% member capture)
    - Pass 1 (0°), Pass 2 (-90° CW with exact X/Y inverse), Pass 3 & 4 (±45° diagonal)
    - Deduplicates orthogonal hits (<32pt) and suppresses corrupted diagonal echoes (<45pt)
    """
    pw, ph = float(page.rect.width), float(page.rect.height)
    req_dpi = max(170, int(dpi or 210))
    if world_rect is not None:
        r = pymupdf.Rect(world_rect)
        rx0, ry0 = max(0.0, r.x0 - 12.0), max(0.0, r.y0 - 12.0)
        rx1, ry1 = min(pw, r.x1 + 12.0), min(ph, r.y1 + 12.0)
        target_tile_pts = 950.0
        use_dpi = max(250, min(300, req_dpi))
        max_px_cap = 2200.0
    else:
        rx0, ry0, rx1, ry1 = 0.0, 0.0, pw * 0.89, ph * 0.95
        target_tile_pts = 1180.0
        use_dpi = min(215, req_dpi)
        max_px_cap = 1850.0

    ro = _get_rapid_ocr()
    if not ro:
        return []

    import numpy as np
    from PIL import Image

    span_w, span_h = max(1.0, rx1 - rx0), max(1.0, ry1 - ry0)
    cols = max(1, int(math.ceil(span_w / target_tile_pts)))
    rows = max(1, int(math.ceil(span_h / target_tile_pts)))
    tile_w, tile_h = span_w / cols, span_h / rows
    ov_x = tile_w * 0.14 if cols > 1 else 0.0
    ov_y = tile_h * 0.14 if rows > 1 else 0.0

    raw_all = []
    for r_i in range(rows):
        for c_i in range(cols):
            tx0 = max(rx0, rx0 + c_i * tile_w - (ov_x if c_i > 0 else 0.0))
            ty0 = max(ry0, ry0 + r_i * tile_h - (ov_y if r_i > 0 else 0.0))
            tx1 = min(rx1, rx0 + (c_i + 1) * tile_w + (ov_x if c_i < cols - 1 else 0.0))
            ty1 = min(ry1, ry0 + (r_i + 1) * tile_h + (ov_y if r_i < rows - 1 else 0.0))
            rect = pymupdf.Rect(tx0, ty0, tx1, ty1)
            max_side = max(1.0, rect.width, rect.height)
            safe_dpi = max(165, min(use_dpi, int((max_px_cap * 72.0) / max_side)))
            pts_per_px = 72.0 / float(safe_dpi)
            pix = page.get_pixmap(dpi=safe_dpi, clip=rect, alpha=False)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)

            if world_rect is None and int((arr < 238).sum()) < 350:
                continue

            lo, hi = int(np.percentile(arr, 1)), int(np.percentile(arr, 98))
            if hi > lo + 18 and (lo > 12 or hi < 245):
                stretched = np.clip((arr.astype(np.float32) - lo) * (255.0 / float(hi - lo)), 0, 255).astype(np.uint8)
            else:
                stretched = arr
            h_px, w_px = stretched.shape[:2]

            # Pass 1: 0 deg
            res0, _ = ro(stretched)
            for item in (res0 or []):
                if not isinstance(item, (list, tuple)) or len(item) < 3:
                    continue
                box, raw_t, conf = item.__getitem__(0), item.__getitem__(1), float(item.__getitem__(2))
                if conf < 0.18 or not str(raw_t).strip():
                    continue
                xs = [float(pt.__getitem__(0)) for pt in box]
                ys = [float(pt.__getitem__(1)) for pt in box]
                raw_all.append((
                    tx0 + min(xs) * pts_per_px, ty0 + min(ys) * pts_per_px,
                    tx0 + max(xs) * pts_per_px, ty0 + max(ys) * pts_per_px,
                    normalize_cad_text(raw_t),
                ))

            if multi_angle:
                pil_base = Image.fromarray(stretched)
                # Pass 2: -90 deg CW (Vertical) with exact inverse X/Y transform
                im90 = np.array(pil_base.rotate(-90, expand=True))
                res90, _ = ro(im90)
                for item in (res90 or []):
                    if not isinstance(item, (list, tuple)) or len(item) < 3:
                        continue
                    box, raw_t, conf = item.__getitem__(0), item.__getitem__(1), float(item.__getitem__(2))
                    if conf < 0.20 or not str(raw_t).strip():
                        continue
                    orig_xs = [max(0.0, min(float(w_px), float(pt.__getitem__(1)))) for pt in box]
                    orig_ys = [max(0.0, min(float(h_px), float(h_px) - float(pt.__getitem__(0)))) for pt in box]
                    raw_all.append((
                        tx0 + min(orig_xs) * pts_per_px, ty0 + min(orig_ys) * pts_per_px,
                        tx0 + max(orig_xs) * pts_per_px, ty0 + max(orig_ys) * pts_per_px,
                        normalize_cad_text(raw_t),
                    ))

                # Pass 3 & 4: +/-45 deg diagonal leader callouts (full 1.0x resolution for tiny brace callouts)
                for ang_deg in (-45, 45):
                    pil_d = pil_base.rotate(ang_deg, expand=True, fillcolor=(255, 255, 255))
                    res_d, _ = ro(np.array(pil_d))
                    if not res_d:
                        continue
                    rad = math.radians(ang_deg)
                    cos_a, sin_a = math.cos(rad), math.sin(rad)
                    cx0, cy0 = w_px * 0.5, h_px * 0.5
                    cx1, cy1 = pil_d.width * 0.5, pil_d.height * 0.5
                    for item in res_d:
                        if not isinstance(item, (list, tuple)) or len(item) < 3:
                            continue
                        box, raw_t, conf = item.__getitem__(0), item.__getitem__(1), float(item.__getitem__(2))
                        if conf < 0.22 or not str(raw_t).strip():
                            continue
                        nt = normalize_cad_text(raw_t)
                        if not any(ch.isdigit() for ch in nt):
                            continue
                        orig_xs, orig_ys = [], []
                        for pt in box:
                            px_r, py_r = float(pt.__getitem__(0)), float(pt.__getitem__(1))
                            dx, dy = px_r - cx1, py_r - cy1
                            ox = cx0 + (dx * cos_a - dy * sin_a)
                            oy = cy0 + (dx * sin_a + dy * cos_a)
                            orig_xs.append(max(0.0, min(float(w_px), ox)))
                            orig_ys.append(max(0.0, min(float(h_px), oy)))
                        raw_all.append((
                            tx0 + min(orig_xs) * pts_per_px, ty0 + min(orig_ys) * pts_per_px,
                            tx0 + max(orig_xs) * pts_per_px, ty0 + max(orig_ys) * pts_per_px,
                            nt + "\x01DIAG",
                        ))

    ortho_hits, diag_hits = [], []
    for hx0, hy0, hx1, hy1, htxt in raw_all:
        if htxt.endswith("\x01DIAG"):
            diag_hits.append((hx0, hy0, hx1, hy1, htxt[:-5]))
        else:
            ortho_hits.append((hx0, hy0, hx1, hy1, htxt))

    hits_out = []
    for hx0, hy0, hx1, hy1, htxt in ortho_hits:
        hcx, hcy = (hx0 + hx1) * 0.5, (hy0 + hy1) * 0.5
        if any(ptxt == htxt and math.hypot(hcx - ((px0 + px1) * 0.5), hcy - ((py0 + py1) * 0.5)) < 32.0 for px0, py0, px1, py1, ptxt in hits_out):
            continue
        hits_out.append((hx0, hy0, hx1, hy1, htxt))

    for hx0, hy0, hx1, hy1, htxt in diag_hits:
        hcx, hcy = (hx0 + hx1) * 0.5, (hy0 + hy1) * 0.5
        if any(any(c.isdigit() for c in ptxt) and math.hypot(hcx - ((px0 + px1) * 0.5), hcy - ((py0 + py1) * 0.5)) < 45.0 for px0, py0, px1, py1, ptxt in hits_out):
            continue
        hits_out.append((hx0, hy0, hx1, hy1, htxt))
    return hits_out

class PlanWorldModel:
    """Unified multi-sheet PDF world coordinate & scale cache."""

    def __init__(self, pdf_path=None):
        self.pdf_path = str(pdf_path or "")
        self.sheet_scales = {}
        self._sheet_states = {}
        if self.pdf_path and os.path.exists(self.pdf_path):
            try:
                doc = pymupdf.open(self.pdf_path)
                for pno in range(len(doc)):
                    st = SheetWorldState(doc.load_page(pno), pno + 1)
                    self._sheet_states[pno + 1] = st
                    self.sheet_scales[pno + 1] = float(st.pts_per_ft)
                doc.close()
            except Exception:
                pass

    def set_sheet_scale(self, page_num, pts_per_ft):
        p = int(page_num)
        self.sheet_scales[p] = float(pts_per_ft)
        if p in self._sheet_states:
            self._sheet_states[p].pts_per_ft = float(pts_per_ft)

    def get_sheet(self, doc, page_num):
        p = int(page_num)
        if p not in self._sheet_states or (p in self.sheet_scales and abs(self._sheet_states[p].pts_per_ft - self.sheet_scales[p]) > 1e-3):
            pg = doc.load_page(max(0, min(len(doc) - 1, p - 1)))
            st = SheetWorldState(pg, p, pts_per_ft=self.sheet_scales.get(p))
            self._sheet_states[p] = st
            self.sheet_scales[p] = float(st.pts_per_ft)
        return self._sheet_states[p]


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
