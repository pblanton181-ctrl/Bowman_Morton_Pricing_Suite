# -*- coding: utf-8 -*-
"""
Dedicated Engine 1: CAD Vector PDF Structural Extraction Engine.
Extracts native PDF vector text spans, rotated/vertical callouts, multi-word line
groups, title-block sheet identifiers, and vector beam stroke lengths.
"""
import math
import re
import pymupdf
from core.plan_world import normalize_cad_text, SheetWorldState


def extract_vector_page_tokens(page, clip_rect=None):
    """Return (items, vert_words, sheet_tag, full_text) strictly from native PDF vector text."""
    pw, ph = float(page.rect.width), float(page.rect.height)
    mx, my = pw * 0.885, ph * 0.945
    full_tb = (page.get_text("text") or "").upper()

    items = []
    lines_grp = {}
    vert_words = []

    for wx0, wy0, wx1, wy1, wstr, bno, lno, wno in page.get_text("words"):
        cx_w, cy_w = (wx0 + wx1) * 0.5, (wy0 + wy1) * 0.5
        if clip_rect is not None:
            if not clip_rect.contains(pymupdf.Point(cx_w, cy_w)):
                continue
        elif not (wx0 < mx and wy0 < my):
            continue

        nw = normalize_cad_text(wstr)
        if not nw:
            continue
        items.append((cx_w, cy_w, nw))
        if (wy1 - wy0) > (wx1 - wx0) * 1.35:
            vert_words.append((cx_w, cy_w, nw))
        lines_grp.setdefault((bno, lno), []).append((wx0, wy0, wx1, wy1, nw))

    # Stitch adjacent vector words on the same text line (handles split "W 12 X 26" or "PL 1/2 X 12")
    for (bno, lno), wlist in lines_grp.items():
        if len(wlist) > 1:
            w_sorted = sorted(wlist, key=lambda w: w[0])
            lx0 = min(w[0] for w in w_sorted)
            ly0 = min(w[1] for w in w_sorted)
            lx1 = max(w[2] for w in w_sorted)
            ly1 = max(w[3] for w in w_sorted)
            joined = " ".join(w[4] for w in w_sorted)
            compact = re.sub(r"\b(W|WT|S|HP|HSS|L|C|MC|PL|FB|PIPE)\s+(\d)", r"\1\2", joined)
            compact = re.sub(r"(?<=\d)\s*[X×]\s*(?=\d)", "X", compact)
            items.append(((lx0 + lx1) * 0.5, (ly0 + ly1) * 0.5, compact))
            if compact != joined:
                items.append(((lx0 + lx1) * 0.5, (ly0 + ly1) * 0.5, joined))


    # Stitch 90-deg / 270-deg rotated vertical fragments sharing the same X column
    if len(vert_words) > 1:
        v_sorted = sorted(vert_words, key=lambda item: (round(item.__getitem__(0) / 8.0), item.__getitem__(1)))
        v_cluster = [v_sorted.__getitem__(0)]
        for vw in v_sorted[1:]:
            if abs(vw.__getitem__(0) - v_cluster[-1].__getitem__(0)) <= 8.0 and abs(vw.__getitem__(1) - v_cluster[-1].__getitem__(1)) <= 36.0:
                v_cluster.append(vw)
            else:
                if len(v_cluster) > 1:
                    vcx = sum(x for x, _, _ in v_cluster) / len(v_cluster)
                    vcy = sum(y for _, y, _ in v_cluster) / len(v_cluster)
                    for merged_v in ("".join(t for _, _, t in v_cluster), "".join(t for _, _, t in reversed(v_cluster))):
                        mv_norm = normalize_cad_text(merged_v)
                        items.append((vcx, vcy, mv_norm))
                        vert_words.append((vcx, vcy, mv_norm))
                v_cluster = [vw]
        if len(v_cluster) > 1:
            vcx = sum(x for x, _, _ in v_cluster) / len(v_cluster)
            vcy = sum(y for _, y, _ in v_cluster) / len(v_cluster)
            for merged_v in ("".join(t for _, _, t in v_cluster), "".join(t for _, _, t in reversed(v_cluster))):
                mv_norm = normalize_cad_text(merged_v)
                items.append((vcx, vcy, mv_norm))
                vert_words.append((vcx, vcy, mv_norm))

    return items, vert_words, full_tb


def pair_vector_beam_length(page, pno, cx, cy, prof, vert_words, pts_per_ft, max_span_ft=38.0):
    """Pair a structural beam/joist callout with its underlying CAD vector line stroke."""
    is_vert_lbl = any(w_txt == prof and math.hypot(cx - vx, cy - vy) < 8.0 for vx, vy, w_txt in vert_words)
    st = getattr(page, "_world_state_cache", None)
    if st is None:
        st = SheetWorldState(page, pno + 1, pts_per_ft=pts_per_ft)
        page._world_state_cache = st
    attached = st.attach_beam_to_callout(
        cx, cy, is_horiz=(not is_vert_lbl), max_perp_pts=10.5, max_span_ft=max_span_ft
    )
    return attached[4] if attached is not None else None
