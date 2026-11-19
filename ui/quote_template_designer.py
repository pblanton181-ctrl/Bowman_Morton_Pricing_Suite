# -*- coding: utf-8 -*-
import os, re, copy, json, base64, datetime
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QPixmap, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QWidget, QLabel, QLineEdit,
    QPlainTextEdit, QTextBrowser, QPushButton, QComboBox, QCheckBox, QFrame,
    QGridLayout, QMessageBox, QColorDialog, QFileDialog, QSpinBox, QFontComboBox, QToolButton
)

SMART_FIELDS = [
    ("Quote #", "{{QUOTE_NUM}}"),
    ("Quote Date", "{{DATE}}"),
    ("Valid Until (+15d)", "{{VALID_UNTIL}}"),
    ("Customer Name", "{{CUSTOMER}}"),
    ("Project Name", "{{PROJECT}}"),
    ("Line Count", "{{ITEM_COUNT}}"),
    ("Total Weight", "{{TOTAL_WEIGHT}}"),
    ("Total Tons", "{{TOTAL_TONS}}"),
    ("Grand Total ($)", "{{GRAND_TOTAL}}"),
]

def default_blocks():
    nl = chr(10)
    return [
        {"id": "logo", "kind": "logo", "title": "Company Logo", "x": 36, "y": 24, "w": 120, "h": 68, "text": "", "font_family": "Arial", "font_size": 10, "bold": False, "italic": False, "underline": False, "text_color": "#0f172a", "align": "left", "visible": False},
        {"id": "header", "kind": "header", "title": "Company Header", "x": 36, "y": 24, "w": 540, "h": 68,
         "text": nl.join(["Bowman-Morton Mfg & Machine", "Bowman Connect LLC  |  Structural Steel & Custom Metal Fabrication", "7447 2nd Ave S., Seattle, WA 98108  |  (206) 524-8890  |  info@bowman-morton.com"]),
         "font_family": "Arial", "font_size": 15, "bold": True, "italic": False, "underline": False, "text_color": "#0f172a", "align": "center", "visible": True},
        {"id": "cust_box", "kind": "box", "title": "Customer & Project Box", "x": 36, "y": 106, "w": 290, "h": 64,
         "text": nl.join(["CUSTOMER: {{CUSTOMER}}", "PROJECT: {{PROJECT}}"]), "font_family": "Arial", "font_size": 10, "bold": False, "italic": False, "underline": False, "text_color": "#0f172a", "align": "left", "visible": True},
        {"id": "quote_box", "kind": "box", "title": "Quote # & Date Box", "x": 336, "y": 106, "w": 240, "h": 64,
         "text": nl.join(["QUOTATION #: {{QUOTE_NUM}}", "DATE: {{DATE}}", "VALID UNTIL: {{VALID_UNTIL}}"]), "font_family": "Arial", "font_size": 10, "bold": False, "italic": False, "underline": False, "text_color": "#0f172a", "align": "right", "visible": True},
        {"id": "table", "kind": "table", "title": "Line Items & Totals Table", "x": 36, "y": 186, "w": 540, "h": 390,
         "text": "", "font_family": "Arial", "font_size": 10, "bold": False, "italic": False, "underline": False, "text_color": "#0f172a", "align": "left", "visible": True},
        {"id": "terms", "kind": "terms", "title": "Terms & Conditions", "x": 36, "y": 670, "w": 540, "h": 86,
         "text": nl.join(["• Pricing valid for 15 days due to mill steel market fluctuations.", "• Applicable taxes, freight, and field erection excluded unless noted.", "• Thank you for the opportunity to quote your project!"]),
         "font_family": "Arial", "font_size": 9, "bold": False, "italic": False, "underline": False, "text_color": "#475569", "align": "left", "visible": True},
    ]

def load_quote_template_config(base_dir):
    cfg_path = os.path.join(base_dir, "config", "quote_template.json")
    defaults = {
        "logo_path": "",
        "accent_color": "#0284c7",
        "table_header_color": "#0f172a",
        "table_header_text_color": "#ffffff",
        "table_stripe_color": "#f8fafc",
        "table_border_color": "#cbd5e1",
        "row_pad_pt": 7,
        "specs_mode": "Customer-Friendly Summary",
        "custom_specs_tpl": "{{FABRICATION}} | {{FINISH}}",
        "show_line_num_col": True,
        "show_unit_price": True,
        "show_weight_col": True,
        "show_signature_block": False,
        "blocks": default_blocks(),
    }
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8-sig") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    defaults.update(loaded)
        except Exception:
            pass
    if not isinstance(defaults.get("blocks"), list) or not defaults["blocks"]:
        defaults["blocks"] = default_blocks()
    return defaults, cfg_path

def _sanitize_customer_specs(raw_specs):
    txt = str(raw_specs or "").strip()
    if not txt or txt == "Standard Stock":
        return ["Standard Mill Finish"], "Standard Mill Finish", "Cut to Length"
    finishes, fab_ops = [], []
    for tok in [t.strip() for t in txt.split(",") if t.strip()]:
        low = tok.lower()
        if "shop handling" in low or "overrides" in low or "sheet " in low:
            continue
        if "shop primer" in low: finishes.append("Shop Primed")
        elif "powder coat" in low: finishes.append("Powder Coated")
        elif "galv" in low or "hdg" in low: finishes.append("Hot-Dip Galvanized")
        elif "auto band saw" in low or "band saw" in low: fab_ops.append("Cut to Length")
        else:
            fab_ops.append(re.sub(r"\s*\(\$[0-9.,/a-zA-Z]+\)", "", tok).strip())
    if not finishes: finishes.append("Bare Steel")
    if not fab_ops: fab_ops.append("Cut to Length")
    return list(dict.fromkeys(fab_ops + finishes)), ", ".join(dict.fromkeys(finishes)), ", ".join(dict.fromkeys(fab_ops))


def _expand_tokens(text, tok_map):
    out = str(text or "")
    for k, v in tok_map.items():
        out = out.replace(k, v)
    lines = []
    for raw_ln in out.splitlines():
        ln = raw_ln.strip()
        if not ln:
            continue
        if ":" in ln and not ln.startswith("•"):
            k_part, _, v_part = ln.partition(":")
            lines.append(f"<b>{k_part.strip()}:</b> {v_part.strip()}")
        else:
            lines.append(ln)
    return "<br>".join(lines)

def render_quote_documents(record, cfg):
    quote_num = str(record.get("quote_num", "BM-2026-1050"))
    ts = str(record.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
    try:
        valid_str = (datetime.datetime.strptime(ts[:10], "%Y-%m-%d") + datetime.timedelta(days=15)).strftime("%Y-%m-%d")
    except Exception:
        valid_str = "15 Days from Issue"

    accent = cfg.get("accent_color", "#0284c7")
    tbl_hdr = cfg.get("table_header_color", "#0f172a")
    tbl_hdr_txt = cfg.get("table_header_text_color", "#ffffff")
    tbl_stripe = cfg.get("table_stripe_color", "#f8fafc")
    tbl_brd = cfg.get("table_border_color", "#cbd5e1")
    r_pad = max(3, int(cfg.get("row_pad_pt", 7)))
    specs_mode = cfg.get("specs_mode", "Customer-Friendly Summary")
    show_specs = (specs_mode != "Hide Specs Column")
    show_line = bool(cfg.get("show_line_num_col", True))
    show_unit = bool(cfg.get("show_unit_price", True))
    show_wgt = bool(cfg.get("show_weight_col", True))
    c_lines = record.get("customer_lines", [])
    tot_wgt_num = float(record.get("weight", 0.0) or 0.0)
    tot_cost_num = float(record.get("cost", 0.0) or 0.0)

    tok_map = {
        "{{QUOTE_NUM}}": f"<span style='color:{accent}; font-weight:bold;'>{quote_num}</span>",
        "{{DATE}}": ts, "{{VALID_UNTIL}}": valid_str,
        "{{CUSTOMER}}": str(record.get("customer", "")), "{{PROJECT}}": str(record.get("project", "")),
        "{{ITEM_COUNT}}": str(max(1, len(c_lines))), "{{TOTAL_WEIGHT}}": f"{tot_wgt_num:,.1f} lbs",
        "{{TOTAL_TONS}}": f"{tot_wgt_num / 2000.0:,.2f} Tons", "{{GRAND_TOTAL}}": f"${tot_cost_num:,.2f}",
    }

    blocks = sorted([b for b in cfg.get("blocks", default_blocks()) if b.get("visible", True)], key=lambda b: (float(b.get("y", 0)), float(b.get("x", 0))))
    tbl_blk = next((b for b in blocks if b.get("kind") == "table"), {})
    tbl_ff = tbl_blk.get("font_family", "Arial")
    tbl_fsz = int(tbl_blk.get("font_size", 10))
    tbl_tc = tbl_blk.get("text_color", "#0f172a")

    rows_html = ""
    for idx, line in enumerate(c_lines or [{"desc": "Custom Structural Steel Package", "specs": "Standard Stock", "weight": tot_wgt_num, "price": tot_cost_num}], 1):
        raw_desc = str(line.get("desc", ""))
        me = re.search(r"\s*\[\$([0-9,]+\.\d{2})\s*ea\]", raw_desc)
        base_desc = re.sub(r"\s*\[\$[0-9,]+\.\d{2}\s*ea\]", "", raw_desc).strip()
        if show_unit and me:
            desc_cell_html = f"<b>{base_desc}</b><br><span style='font-size:8.5pt; color:#475569; font-weight:normal;'>Unit Price: ${me.group(1)} ea</span>"
        else:
            desc_cell_html = f"<b>{base_desc}</b>"

        mq = re.search(r"\(x(\d+)\)", base_desc)
        q_str = mq.group(1) if mq else "1"
        ea_str = f"${me.group(1)}" if me else f"${float(line.get('price', 0.0)):,.2f}"
        wgt_val = float(line.get("weight", 0.0) or 0.0)
        wgt_str = f"{wgt_val:,.1f} lbs" if wgt_val > 0 else "—"
        clean_bullets, clean_fin, clean_fab = _sanitize_customer_specs(line.get("specs", ""))
        if specs_mode == "Custom Row Smart Fields":
            sp_tpl = str(cfg.get("custom_specs_tpl", "{{FABRICATION}} | {{FINISH}}"))
            specs_html = sp_tpl.replace("{{FINISH}}", clean_fin).replace("{{FABRICATION}}", clean_fab).replace("{{QTY}}", q_str).replace("{{UNIT_PRICE}}", ea_str).replace("\n", "<br>")
        else:
            specs_html = ", ".join(clean_bullets)

        row_bg = tbl_stripe if idx % 2 == 0 else "#ffffff"
        cell_css = f"padding:{r_pad+1}pt 8pt; border-bottom:1pt solid {tbl_brd}; font-family:'{tbl_ff}', Arial, sans-serif; font-size:{tbl_fsz}pt; color:{tbl_tc};"
        ln_td = f"<td valign='top' style='{cell_css} text-align:center;'>{idx}</td>" if show_line else ""
        sp_td = f"<td valign='top' style='{cell_css}'>{specs_html}</td>" if show_specs else ""
        wgt_td = f"<td valign='top' style='{cell_css} text-align:right; white-space:nowrap;'>{wgt_str}</td>" if show_wgt else ""
        rows_html += f"<tr bgcolor='{row_bg}' style='page-break-inside: avoid;'>{ln_td}<td valign='top' style='{cell_css}'>{desc_cell_html}</td>{sp_td}{wgt_td}<td valign='top' style='{cell_css} text-align:right; white-space:nowrap; font-weight:bold;'>${float(line.get('price', 0.0)):,.2f}</td></tr>"

    hdr_css = f"padding:{r_pad+2}pt 8pt; font-family:'{tbl_ff}', Arial, sans-serif; font-size:{max(9, tbl_fsz-1)}pt; font-weight:bold; color:{tbl_hdr_txt};"
    ln_th = f"<th width='7%' style='{hdr_css} text-align:center;'>LINE</th>" if show_line else ""
    desc_w = "35%" if show_specs else "58%"
    sp_th = f"<th width='28%' style='{hdr_css} text-align:left;'>FABRICATION &amp; FINISH</th>" if show_specs else ""
    wgt_th = f"<th width='14%' style='{hdr_css} text-align:right;'>WEIGHT</th>" if show_wgt else ""
    wgt_tot_td = f"<td style='padding:{r_pad+3}pt 8pt; text-align:right; font-family:{tbl_ff}, Arial, sans-serif; font-size:{tbl_fsz}pt; font-weight:bold; color:{tbl_tc}; border-top:2pt solid {tbl_hdr}; white-space:nowrap;'>{tot_wgt_num:,.1f} lbs</td>" if show_wgt else ""
    span_n = 1 + (1 if show_line else 0) + (1 if show_specs else 0)
    table_html = (
        f"<table width='100%' cellspacing='0' cellpadding='0' style='border-collapse:collapse; border:1pt solid {tbl_brd}; margin-bottom:14pt;'>"
        f"<tbody>"
        f"<tr bgcolor='{tbl_hdr}'>{ln_th}<th width='{desc_w}' style='{hdr_css} text-align:left;'>ITEM / DESCRIPTION</th>{sp_th}{wgt_th}<th width='16%' style='{hdr_css} text-align:right;'>LINE TOTAL</th></tr>"
        f"{rows_html}"
        f"<tr bgcolor='{tbl_stripe}'><td colspan='{span_n}' style='padding:{r_pad+3}pt 8pt; text-align:right; font-family:{tbl_ff}, Arial, sans-serif; font-size:{tbl_fsz}pt; font-weight:bold; color:{tbl_tc}; border-top:2pt solid {tbl_hdr};'>PROJECT TOTALS:</td>{wgt_tot_td}<td style='padding:{r_pad+3}pt 8pt; text-align:right; font-family:{tbl_ff}, Arial, sans-serif; font-size:{tbl_fsz+1}pt; font-weight:bold; color:{accent}; border-top:2pt solid {tbl_hdr}; white-space:nowrap;'>${tot_cost_num:,.2f}</td></tr>"
        f"</tbody></table>"
    )

    logo_path = str(cfg.get("logo_path", "")).strip()
    logo_b64 = ""
    if logo_path and os.path.exists(logo_path):
        try:
            ext = os.path.splitext(logo_path).__getitem__(1).lower().lstrip(".")
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
            with open(logo_path, "rb") as f:
                logo_b64 = f"data:{mime};base64,{base64.b64encode(f.read()).decode('ascii')}"
        except Exception:
            logo_b64 = ""

    top_bands = []
    footer_terms_html = ""
    prev_bottom = 24.0
    i = 0
    while i < len(blocks):
        b = blocks.__getitem__(i)
        kind = b.get("kind", "box")
        ff = b.get("font_family", "Arial")
        fsz = int(b.get("font_size", 10))
        tc = b.get("text_color", "#0f172a")
        fw = "bold" if b.get("bold") else "normal"
        fs = "italic" if b.get("italic") else "normal"
        td = "underline" if b.get("underline") else "none"
        txt_style = f"font-family:'{ff}', Arial, sans-serif; font-size:{fsz}pt; color:{tc}; font-weight:{fw}; font-style:{fs}; text-decoration:{td};"

        if kind == "terms":
            footer_terms_html = f"<span style='{txt_style}'>{_expand_tokens(b.get('text', ''), tok_map)}</span>"
            i += 1
            continue

        cur_y = float(b.get("y", prev_bottom))
        gap_pt = max(6, min(90, int(round(cur_y - prev_bottom))))
        prev_bottom = cur_y + float(b.get("h", 50))

        if kind == "table":
            top_bands.append(f"<div style='margin-top:{gap_pt}pt;'>{table_html}</div>")
            i += 1
            continue

        row_grp = [b]
        while i + 1 < len(blocks) and blocks.__getitem__(i + 1).get("kind") in ("logo", "header", "box", "text") and abs(float(blocks.__getitem__(i + 1).get("y", 0)) - cur_y) <= 24.0:
            i += 1
            row_grp.append(blocks.__getitem__(i))
            prev_bottom = max(prev_bottom, float(blocks.__getitem__(i).get("y", 0)) + float(blocks.__getitem__(i).get("h", 50)))
        row_grp.sort(key=lambda it: float(it.get("x", 0)))
        tds = []
        for it in row_grp:
            w_pct = max(12, min(100, int(round((float(it.get("w", 260)) / 540.0) * 100.0))))
            aln = it.get("align", "left")
            iff = it.get("font_family", "Arial")
            ifsz = int(it.get("font_size", 10))
            itc = it.get("text_color", "#0f172a")
            ifw = "bold" if it.get("bold") else "normal"
            ifs = "italic" if it.get("italic") else "normal"
            itd = "underline" if it.get("underline") else "none"
            istyle = f"font-family:'{iff}', Arial, sans-serif; font-size:{ifsz}pt; color:{itc}; font-weight:{ifw}; font-style:{ifs}; text-decoration:{itd};"
            if it.get("kind") == "logo" and logo_b64:
                lh = max(24, int(it.get("h", 64)))
                tds.append(f"<td width='{w_pct}%' valign='middle' style='text-align:{aln};'><img src='{logo_b64}' height='{lh}' /></td>")
            elif it.get("kind") == "header":
                lns = [x.strip() for x in str(it.get("text", "")).splitlines() if x.strip()]
                h0 = f"<span style='{istyle}'>{lns[0]}</span>" if lns else ""
                sub_sz = max(9, min(14, int(round(ifsz * 0.68))))
                rest = "<br>".join(lns[1:])
                tds.append(f"<td width='{w_pct}%' valign='middle' style='text-align:{aln}; border-bottom:2pt solid {accent}; padding-bottom:8pt;'>{h0}{'<br><span style="font-family:' + iff + ', Arial, sans-serif; font-size:' + str(sub_sz) + 'pt; color:#334155; font-weight:normal;">' + rest + '</span>' if rest else ''}</td>")
            else:
                bg = f"background-color:{tbl_stripe}; border:1pt solid {tbl_brd}; padding:8pt;" if it.get("kind") == "box" else "padding:4pt;"
                tds.append(f"<td width='{w_pct}%' valign='top' style='text-align:{aln}; line-height:1.45; {istyle} {bg}'>{_expand_tokens(it.get('text', ''), tok_map)}</td>")
        top_bands.append(f"<table width='100%' cellspacing='6' cellpadding='0' style='margin-top:{gap_pt}pt; margin-bottom:6pt;'><tr>{''.join(tds)}</tr></table>")
        i += 1

    notes_raw = str(record.get("notes", "")).strip()
    if notes_raw:
        top_bands.append(f"<div style='margin-top:12pt; padding:8pt; background-color:{tbl_stripe}; border-left:3pt solid {accent}; font-size:9.5pt;'><b>SCOPE &amp; ESTIMATOR NOTES:</b><br>{notes_raw.replace(chr(10), '<br>')}</div>")
    if cfg.get("show_signature_block"):
        top_bands.append("<table width='100%' cellspacing='0' cellpadding='6' style='margin-top:22pt; font-size:9.5pt;'><tr><td width='55%' style='border-bottom:1pt solid #475569;'><b>Accepted By (Customer Signature):</b></td><td width='10%'></td><td width='35%' style='border-bottom:1pt solid #475569;'><b>Date / PO #:</b></td></tr></table>")

    body_html = f"<html><body style='font-family:Arial, Helvetica, sans-serif; color:#0f172a; font-size:10pt;'>{''.join(top_bands)}</body></html>"
    footer_html = f"<html><body style='font-family:Arial, Helvetica, sans-serif; color:#475569; font-size:9pt;'><div style='padding-top:8pt; border-top:1pt solid {tbl_brd}; line-height:1.45;'><b>TERMS &amp; NOTES:</b><br>{footer_terms_html}</div></body></html>"
    return body_html, footer_html


class _QuotePageCanvas(QWidget):
    PAGE_W = 612.0
    PAGE_H = 792.0

    def __init__(self, get_cfg_fn, on_select_cb, on_commit_cb, parent=None):
        super().__init__(parent)
        self.get_cfg_fn = get_cfg_fn
        self.on_select_cb = on_select_cb
        self.on_commit_cb = on_commit_cb
        self.selected_id = "header"
        self._drag_mode = ""
        self._drag_start = QPointF()
        self._orig_rect = QRectF()
        self._logo_pm = None
        self._logo_cached_path = ""
        self.setMinimumSize(650, 830)
        self.setMouseTracking(True)

    def _page_origin(self):
        return QPointF(max(16.0, (self.width() - self.PAGE_W) * 0.5), 16.0)

    def _get_logo_pixmap(self, lp):
        if lp != self._logo_cached_path:
            self._logo_cached_path = lp
            self._logo_pm = QPixmap(lp) if (lp and os.path.exists(lp)) else None
        return self._logo_pm

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#cbd5e1"))
        org = self._page_origin()
        page_rc = QRectF(org.x(), org.y(), self.PAGE_W, self.PAGE_H)
        p.fillRect(page_rc, QColor("#ffffff"))
        p.setPen(QPen(QColor("#64748b"), 1.5))
        p.drawRect(page_rc)

        p.setPen(QPen(QColor("#f1f5f9"), 1.0))
        for gx in range(12, int(self.PAGE_W), 12):
            p.drawLine(QPointF(org.x() + gx, org.y()), QPointF(org.x() + gx, org.y() + self.PAGE_H))
        for gy in range(12, int(self.PAGE_H), 12):
            p.drawLine(QPointF(org.x(), org.y() + gy), QPointF(org.x() + self.PAGE_W, org.y() + gy))

        cfg = self.get_cfg_fn()
        accent = QColor(cfg.get("accent_color", "#0284c7"))
        tbl_hdr = QColor(cfg.get("table_header_color", "#0f172a"))
        tbl_hdr_txt = QColor(cfg.get("table_header_text_color", "#ffffff"))
        tbl_stripe = QColor(cfg.get("table_stripe_color", "#f8fafc"))
        tbl_brd = QColor(cfg.get("table_border_color", "#cbd5e1"))
        pm = self._get_logo_pixmap(cfg.get("logo_path", ""))

        for b in cfg.get("blocks", []):
            if not b.get("visible", True):
                continue
            bx = org.x() + float(b.get("x", 36))
            by = org.y() + float(b.get("y", 24))
            bw = float(b.get("w", 240))
            bh = float(b.get("h", 60))
            rc = QRectF(bx, by, bw, bh)
            is_sel = (b.get("id") == self.selected_id)

            p.fillRect(rc, tbl_stripe if b.get("kind") in ("box", "terms") else QColor(255, 255, 255, 230))
            p.setPen(QPen(accent if is_sel else tbl_brd, 2.0 if is_sel else 1.0, Qt.SolidLine if is_sel else Qt.DashLine))
            p.drawRect(rc)

            p.setFont(QFont("Segoe UI", 7.5, QFont.Bold))
            p.setPen(accent if is_sel else QColor("#64748b"))
            p.drawText(QRectF(bx + 4, by - 13, bw, 13), Qt.AlignLeft | Qt.AlignVCenter, b.get("title", "Block"))

            kind = b.get("kind", "box")
            fnt = QFont(b.get("font_family", "Arial"), int(b.get("font_size", 10)), QFont.Bold if b.get("bold") else QFont.Normal)
            fnt.setItalic(bool(b.get("italic", False)))
            fnt.setUnderline(bool(b.get("underline", False)))
            p.setFont(fnt)
            p.setPen(QColor(b.get("text_color", "#0f172a")))

            if kind == "logo":
                if pm and not pm.isNull():
                    scaled = pm.scaled(int(bw - 8), int(bh - 8), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    p.drawPixmap(int(bx + (bw - scaled.width()) * 0.5), int(by + (bh - scaled.height()) * 0.5), scaled)
                else:
                    p.setPen(QColor("#64748b"))
                    p.drawText(rc, Qt.AlignCenter, "Company Logo\n(Click Add Logo)")
            elif kind == "table":
                hdr_rc = QRectF(bx + 2, by + 2, bw - 4, 24)
                p.fillRect(hdr_rc, tbl_hdr)
                p.setPen(tbl_hdr_txt)
                p.setFont(QFont(b.get("font_family", "Arial"), 8.5, QFont.Bold))
                p.drawText(hdr_rc.adjusted(6, 0, -6, 0), Qt.AlignLeft | Qt.AlignVCenter, "LINE #   |   ITEM / DESCRIPTION   |   FABRICATION & FINISH   |   WEIGHT   |   TOTAL")
                p.fillRect(QRectF(bx + 2, by + 48, bw - 4, 22), tbl_stripe)
                p.setPen(QColor(b.get("text_color", "#0f172a")))
                p.setFont(QFont(b.get("font_family", "Arial"), 8.5))
                p.drawText(rc.adjusted(8, 30, -8, -8), Qt.AlignLeft | Qt.AlignTop, "1   16' HSS4X4X1/4 (x4)   |   Cut to Length, Shop Primed   |   816.0 lbs   |   $2,336.95\n2   16' HSS5X4X1/4 (x4)   |   Cut to Length, Shop Primed   |   924.8 lbs   |   $2,621.79\n\n                                                                         PROJECT TOTALS:  2,301.1 lbs   $6,761.60")
            elif kind == "header":
                aln_map = {"center": Qt.AlignHCenter, "right": Qt.AlignRight}
                h_aln = aln_map.get(b.get("align", "center"), Qt.AlignHCenter)
                lns = [x.strip() for x in str(b.get("text", "")).splitlines() if x.strip()]
                if lns:
                    p.setFont(fnt)
                    p.drawText(QRectF(bx + 6, by + 4, bw - 12, 24), h_aln | Qt.AlignVCenter, lns[0])
                if len(lns) > 1:
                    sub_f = QFont(b.get("font_family", "Arial"), max(8, int(round(int(b.get("font_size", 15)) * 0.62))))
                    p.setFont(sub_f)
                    p.setPen(QColor("#475569"))
                    p.drawText(QRectF(bx + 6, by + 28, bw - 12, bh - 34), h_aln | Qt.AlignTop | Qt.TextWordWrap, "\n".join(lns[1:]))
                p.setPen(QPen(accent, 2.0))
                p.drawLine(QPointF(bx + 2, by + bh - 2), QPointF(bx + bw - 2, by + bh - 2))
            else:
                aln_map = {"center": Qt.AlignHCenter, "right": Qt.AlignRight}
                fl = aln_map.get(b.get("align", "left"), Qt.AlignLeft) | Qt.AlignTop | Qt.TextWordWrap
                p.drawText(rc.adjusted(6, 5, -6, -5), fl, str(b.get("text", "")))

            if is_sel:
                p.fillRect(QRectF(rc.right() - 8, rc.bottom() - 8, 8, 8), accent)

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        org = self._page_origin()
        pt = ev.position() - org
        cfg = self.get_cfg_fn()
        for b in reversed(cfg.get("blocks", [])):
            if not b.get("visible", True):
                continue
            rc = QRectF(float(b.get("x", 0)), float(b.get("y", 0)), float(b.get("w", 100)), float(b.get("h", 40)))
            if rc.adjusted(-4, -14, 6, 6).contains(pt):
                self.selected_id = b.get("id")
                self.on_select_cb(self.selected_id)
                self._drag_start = pt
                self._orig_rect = QRectF(rc)
                self._drag_mode = "resize" if QRectF(rc.right() - 12, rc.bottom() - 12, 16, 16).contains(pt) else "move"
                self.update()
                return

    def mouseMoveEvent(self, ev):
        org = self._page_origin()
        pt = ev.position() - org
        cfg = self.get_cfg_fn()
        blk = next((b for b in cfg.get("blocks", []) if b.get("id") == self.selected_id), None)
        if not self._drag_mode or not blk:
            return
        dx, dy = pt.x() - self._drag_start.x(), pt.y() - self._drag_start.y()
        snap = lambda v: round(v / 6.0) * 6.0
        if self._drag_mode == "move":
            blk["x"] = max(12.0, min(self.PAGE_W - self._orig_rect.width() - 12.0, snap(self._orig_rect.x() + dx)))
            blk["y"] = max(12.0, min(self.PAGE_H - self._orig_rect.height() - 12.0, snap(self._orig_rect.y() + dy)))
        else:
            blk["w"] = max(72.0, min(self.PAGE_W - self._orig_rect.x() - 12.0, snap(self._orig_rect.width() + dx)))
            blk["h"] = max(28.0, min(self.PAGE_H - self._orig_rect.y() - 12.0, snap(self._orig_rect.height() + dy)))
        self.update()

    def mouseReleaseEvent(self, ev):
        if self._drag_mode:
            self._drag_mode = ""
            self.on_commit_cb()


class QuoteTemplateDesignerDialog(QDialog):
    def __init__(self, base_dir, sample_record=None, parent=None):
        super().__init__(parent)
        self.base_dir = base_dir
        self.cfg, self.cfg_path = load_quote_template_config(base_dir)
        self._undo_stack, self._redo_stack, self._syncing = [], [], False
        self.sample_record = sample_record or {
            "quote_num": "BM-2026-1050", "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "customer": "ALKI Marine (Jerry)", "project": "Wilson Project", "weight": 2301.1, "cost": 6761.60,
            "notes": "Furnished FOB Seattle, WA. Standard shop primer included.",
            "customer_lines": [
                {"desc": "16' HSS4X4X1/4 (x4) [$584.24 ea]", "specs": "Auto Band Saw Cut (x4), Shop Handling (15m/pc), Shop Primer ($0.12/lb)", "weight": 816.0, "price": 2336.95},
                {"desc": "16' HSS5X4X1/4 (x4) [$655.45 ea]", "specs": "Auto Band Saw Cut (x4), Shop Handling (15m/pc), Shop Primer ($0.12/lb)", "weight": 924.8, "price": 2621.79},
            ],
        }
        self.setWindowTitle("Bowman-Morton Customer Quote Page Designer")
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.resize(1380, 860); self.setWindowState(self.windowState() | Qt.WindowMaximized)
        self.setStyleSheet("""
            QDialog { background-color: #e5e7eb; color: #0f172a; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; }
            QFrame#OfficeRibbonStrip { background-color: #e5e7eb; border-bottom: 1px solid #c8c6c4; }
            QFrame#OfficeCommandBand { background-color: #f3f2f1; border: 1px solid #c8c6c4; border-radius: 6px; margin: 4px 8px 4px 8px; }
            QFrame#SideCard { background-color: #f3f2f1; border: 1px solid #c8c6c4; border-radius: 6px; }
            QLabel { color: #0f172a; font-weight: 600; background: transparent; border: none; }
            QLabel#GroupCap { color: #334155; font-size: 10.5px; font-weight: 700; }
            QLineEdit, QComboBox, QPlainTextEdit, QSpinBox, QFontComboBox { background-color: #ffffff; color: #0f172a; border: 1px solid #94a3b8; border-radius: 4px; padding: 3px 6px; font-size: 11.5px; }
            QPushButton { background-color: #ffffff; border: 1px solid #94a3b8; color: #0f172a; font-weight: 600; border-radius: 4px; padding: 4px 9px; font-size: 11.5px; }
            QPushButton:hover { background-color: #e0f2fe; border-color: #0284c7; color: #0369a1; }
            QPushButton#PrimaryBtn { background-color: #0078d4; border-color: #005a9e; color: #ffffff; font-weight: 700; }
            QPushButton#PrimaryBtn:hover { background-color: #106ebe; }
            QPushButton#TokenPill { background-color: #ffffff; border: 1px solid #94a3b8; color: #0f172a; font-size: 11px; padding: 4px 8px; }
            QPushButton#TokenPill:hover { background-color: #e0f2fe; border-color: #0284c7; }
        """)
        self._saved_snapshot = copy.deepcopy(self.cfg)
        self._push_undo(); self._build_ui(); self._select_block("header")

    def _push_undo(self):
        snap = copy.deepcopy(self.cfg)
        if not self._undo_stack or self._undo_stack[-1] != snap:
            self._undo_stack.append(snap); self._undo_stack = self._undo_stack[-30:]; self._redo_stack.clear()

    def _undo(self):
        if len(self._undo_stack) > 1:
            self._redo_stack.append(self._undo_stack.pop()); self.cfg = copy.deepcopy(self._undo_stack[-1]); self._select_block(self.canvas.selected_id); self.canvas.update()

    def _redo(self):
        if self._redo_stack:
            nxt = self._redo_stack.pop(); self._undo_stack.append(copy.deepcopy(nxt)); self.cfg = copy.deepcopy(nxt); self._select_block(self.canvas.selected_id); self.canvas.update()

    def _make_ribbon_group(self, title_txt):
        wrap = QWidget(); wl = QVBoxLayout(wrap); wl.setContentsMargins(6, 4, 6, 2); wl.setSpacing(3)
        body = QWidget(); bl = QHBoxLayout(body); bl.setContentsMargins(0, 0, 0, 0); bl.setSpacing(4); wl.addWidget(body, 1)
        cap = QLabel(title_txt); cap.setObjectName("GroupCap"); cap.setAlignment(Qt.AlignCenter); wl.addWidget(cap, 0)
        sep = QFrame(); sep.setFrameShape(QFrame.VLine); sep.setStyleSheet("color: #cbd5e1;")
        return wrap, bl, sep

    def _build_ui(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 8); root.setSpacing(6)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._undo); QShortcut(QKeySequence("Ctrl+Y"), self, activated=self._redo)

        rib_host = QFrame(); rib_host.setObjectName("OfficeRibbonStrip"); rhl = QVBoxLayout(rib_host); rhl.setContentsMargins(0, 0, 0, 0)
        cmd_band = QFrame(); cmd_band.setObjectName("OfficeCommandBand"); cbl = QHBoxLayout(cmd_band); cbl.setContentsMargins(6, 3, 6, 3); cbl.setSpacing(4)

        g1, l1, s1 = self._make_ribbon_group("History & Insert")
        for lbl, fn in [("Undo", self._undo), ("Redo", self._redo), ("Add Logo", self._pick_logo), ("+ Text Box", self._add_text_box)]:
            b = QPushButton(lbl); b.clicked.connect(fn); l1.addWidget(b)
        cbl.addWidget(g1); cbl.addWidget(s1)

        g2, l2, s2 = self._make_ribbon_group("Font & Text Style")
        f_col = QVBoxLayout(); f_col.setSpacing(3); r_top = QHBoxLayout(); r_top.setSpacing(3)
        self.cb_font = QFontComboBox(); self.cb_font.setMaximumWidth(155); self.cb_font.currentFontChanged.connect(self._on_prop_changed); r_top.addWidget(self.cb_font)
        self.sp_fsz = QSpinBox(); self.sp_fsz.setRange(8, 28); self.sp_fsz.setValue(10); self.sp_fsz.valueChanged.connect(self._on_prop_changed); r_top.addWidget(self.sp_fsz)
        f_col.addLayout(r_top); r_bot = QHBoxLayout(); r_bot.setSpacing(3)
        self.btn_b = QPushButton("B"); self.btn_b.setCheckable(True); self.btn_b.setFixedWidth(28); self.btn_b.setStyleSheet("font-weight: 800;"); self.btn_b.toggled.connect(self._on_prop_changed); r_bot.addWidget(self.btn_b)
        self.btn_i = QPushButton("I"); self.btn_i.setCheckable(True); self.btn_i.setFixedWidth(28); self.btn_i.setStyleSheet("font-style: italic;"); self.btn_i.toggled.connect(self._on_prop_changed); r_bot.addWidget(self.btn_i)
        self.btn_u = QPushButton("U"); self.btn_u.setCheckable(True); self.btn_u.setFixedWidth(28); self.btn_u.setStyleSheet("text-decoration: underline;"); self.btn_u.toggled.connect(self._on_prop_changed); r_bot.addWidget(self.btn_u)
        b_tc = QPushButton("Text Color"); b_tc.clicked.connect(self._pick_text_color); r_bot.addWidget(b_tc)
        f_col.addLayout(r_bot); l2.addLayout(f_col); cbl.addWidget(g2); cbl.addWidget(s2)

        g3, l3, s3 = self._make_ribbon_group("Alignment")
        self.cb_align = QComboBox(); self.cb_align.addItems(["left", "center", "right"]); self.cb_align.currentTextChanged.connect(self._on_prop_changed); l3.addWidget(self.cb_align)
        cbl.addWidget(g3); cbl.addWidget(s3)

        g4, l4, s4 = self._make_ribbon_group("Quote & Table Colors")
        cg = QGridLayout(); cg.setSpacing(3)
        for r_i, c_i, lbl, k, tit in [(0,0,"Table Banner","table_header_color","Table Banner Color"),(0,1,"Alt-Row Tint","table_stripe_color","Table Row Stripe Color"),(1,0,"Grid Borders","table_border_color","Table Grid Border Color"),(1,1,"Accent Color","accent_color","Quote Accent Color")]:
            b = QPushButton(lbl); b.clicked.connect(lambda _=False, key=k, t=tit: self._pick_cfg_color(key, t)); cg.addWidget(b, r_i, c_i)
        l4.addLayout(cg); cbl.addWidget(g4); cbl.addWidget(s4)

        g5, l5, _ = self._make_ribbon_group("Preview")
        b_prev = QPushButton("Preview Customer PDF"); b_prev.setObjectName("PrimaryBtn"); b_prev.clicked.connect(self._open_live_preview); l5.addWidget(b_prev)
        cbl.addWidget(g5); cbl.addStretch(1); rhl.addWidget(cmd_band); root.addWidget(rib_host)

        split = QSplitter(Qt.Horizontal)
        left = QFrame(); left.setObjectName("SideCard"); ll = QVBoxLayout(left); ll.setContentsMargins(10, 10, 10, 10); ll.setSpacing(8)
        ll.addWidget(QLabel("CLICK SMART FIELD TO INSERT INTO SELECTED BOX:"))
        tg = QGridLayout(); tg.setSpacing(4)
        for i, (lbl, tok) in enumerate(SMART_FIELDS):
            tb = QPushButton(f"+ {lbl}"); tb.setObjectName("TokenPill")
            tb.clicked.connect(lambda _=False, t=tok: (self.ed_blk_text.insertPlainText(t), self.ed_blk_text.setFocus())); tg.addWidget(tb, i // 2, i % 2)
        ll.addLayout(tg)

        self.lbl_sel_blk = QLabel("SELECTED BLOCK: Company Header"); self.lbl_sel_blk.setStyleSheet("color: #0369a1; font-weight: 800;"); ll.addWidget(self.lbl_sel_blk)
        self.ed_blk_text = QPlainTextEdit(); self.ed_blk_text.setMaximumHeight(110); self.ed_blk_text.textChanged.connect(self._on_text_edited); ll.addWidget(self.ed_blk_text)

        ll.addWidget(QLabel("CUSTOMER-SAFE TABLE & SPECS SETTINGS:"))
        self.cb_specs = QComboBox(); self.cb_specs.addItems(["Customer-Friendly Summary", "Hide Specs Column", "Custom Row Smart Fields"])
        self.cb_specs.setCurrentText(self.cfg.get("specs_mode", "Customer-Friendly Summary")); self.cb_specs.currentTextChanged.connect(self._on_global_changed); ll.addWidget(self.cb_specs)

        self.chk_line = QCheckBox("Show Line # Column"); self.chk_line.setChecked(bool(self.cfg.get("show_line_num_col", True))); self.chk_line.toggled.connect(self._on_global_changed); ll.addWidget(self.chk_line)
        self.chk_unit = QCheckBox("Show Unit Price ($ ea)"); self.chk_unit.setChecked(bool(self.cfg.get("show_unit_price", True))); self.chk_unit.toggled.connect(self._on_global_changed); ll.addWidget(self.chk_unit)
        self.chk_wgt = QCheckBox("Show Weight Column"); self.chk_wgt.setChecked(bool(self.cfg.get("show_weight_col", True))); self.chk_wgt.toggled.connect(self._on_global_changed); ll.addWidget(self.chk_wgt)
        self.chk_sig = QCheckBox("Include Customer Signature Line"); self.chk_sig.setChecked(bool(self.cfg.get("show_signature_block", False))); self.chk_sig.toggled.connect(self._on_global_changed); ll.addWidget(self.chk_sig)
        ll.addStretch(); split.addWidget(left)

        self.canvas = _QuotePageCanvas(lambda: self.cfg, self._select_block, self._push_undo, self)
        split.addWidget(self.canvas); split.setSizes(list((360, 960))); root.addWidget(split, 1)

        bot = QHBoxLayout(); bot.setContentsMargins(10, 0, 10, 0)
        b_rst = QPushButton("Reset Default Layout"); b_rst.clicked.connect(self._reset_default); bot.addWidget(b_rst); bot.addStretch()
        b_can = QPushButton("Cancel"); b_can.clicked.connect(self.reject); bot.addWidget(b_can)
        b_sav = QPushButton("Save && Apply Quote Layout"); b_sav.setObjectName("PrimaryBtn"); b_sav.clicked.connect(self._save_template); bot.addWidget(b_sav)
        root.addLayout(bot)

    def _cur_block(self):
        return next((b for b in self.cfg.get("blocks", []) if b.get("id") == self.canvas.selected_id), None)

    def _select_block(self, blk_id):
        self._syncing = True
        blk = next((b for b in self.cfg.get("blocks", []) if b.get("id") == blk_id), None)
        if blk:
            self.lbl_sel_blk.setText(f"SELECTED BLOCK: {blk.get('title', 'Block')} (Drag or resize on page)")
            self.ed_blk_text.setPlainText(str(blk.get("text", "")))
            self.cb_font.setCurrentFont(QFont(blk.get("font_family", "Arial")))
            self.cb_align.setCurrentText(str(blk.get("align", "left")))
            self.sp_fsz.setValue(int(blk.get("font_size", 10)))
            self.btn_b.setChecked(bool(blk.get("bold", False))); self.btn_i.setChecked(bool(blk.get("italic", False))); self.btn_u.setChecked(bool(blk.get("underline", False)))
        self._syncing = False

    def _on_text_edited(self):
        if self._syncing: return
        blk = self._cur_block()
        if blk is not None: blk["text"] = self.ed_blk_text.toPlainText(); self.canvas.update(); self._push_undo()

    def _on_prop_changed(self, *_):
        if self._syncing: return
        blk = self._cur_block()
        if blk is not None:
            blk["font_family"] = self.cb_font.currentFont().family(); blk["align"] = self.cb_align.currentText()
            blk["font_size"] = self.sp_fsz.value(); blk["bold"] = self.btn_b.isChecked(); blk["italic"] = self.btn_i.isChecked(); blk["underline"] = self.btn_u.isChecked()
            self.canvas.update(); self._push_undo()

    def _on_global_changed(self, *_):
        if self._syncing: return
        self.cfg["specs_mode"] = self.cb_specs.currentText(); self.cfg["show_line_num_col"] = self.chk_line.isChecked()
        self.cfg["show_unit_price"] = self.chk_unit.isChecked(); self.cfg["show_weight_col"] = self.chk_wgt.isChecked(); self.cfg["show_signature_block"] = self.chk_sig.isChecked()
        self.canvas.update(); self._push_undo()

    def _pick_text_color(self):
        blk = self._cur_block()
        if not blk: return
        c = QColorDialog.getColor(QColor(blk.get("text_color", "#0f172a")), self, "Select Text Color")
        if c.isValid(): blk["text_color"] = c.name(); self.canvas.update(); self._push_undo()

    def _pick_cfg_color(self, key, title):
        c = QColorDialog.getColor(QColor(self.cfg.get(key, "#0f172a")), self, title)
        if c.isValid(): self.cfg[key] = c.name(); self.canvas.update(); self._push_undo()

    def _pick_logo(self):
        fp, _ = QFileDialog.getOpenFileName(self, "Select Company Logo Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if fp:
            self.cfg["logo_path"] = fp
            logo_blk = next((b for b in self.cfg.get("blocks", []) if b.get("id") == "logo"), None)
            hdr_blk = next((b for b in self.cfg.get("blocks", []) if b.get("id") == "header"), None)
            if logo_blk:
                logo_blk["visible"] = True
                if hdr_blk and float(hdr_blk.get("x", 36)) < 150: hdr_blk["x"] = 168; hdr_blk["w"] = 408
            self.canvas.selected_id = "logo"; self._select_block("logo"); self.canvas.update(); self._push_undo()

    def _add_text_box(self):
        nid = f"note_{len(self.cfg.get('blocks', [])) + 1}"
        self.cfg["blocks"].append({"id": nid, "kind": "text", "title": "Custom Text Note", "x": 36, "y": 172, "w": 540, "h": 34, "text": "Thank you for the opportunity to quote {{PROJECT}}.", "font_family": "Arial", "font_size": 10, "bold": False, "italic": False, "underline": False, "text_color": "#0f172a", "align": "left", "visible": True})
        self.canvas.selected_id = nid; self._select_block(nid); self.canvas.update(); self._push_undo()

    def _open_live_preview(self):
        import tempfile, pymupdf
        from PySide6.QtCore import QSizeF, QMarginsF
        from PySide6.QtGui import QTextDocument, QPageLayout, QPageSize, QPainter
        from PySide6.QtPrintSupport import QPrinter
        from PySide6.QtWidgets import QScrollArea

        b_html, f_html = render_quote_documents(self.sample_record, self.cfg)
        fd, tmp_pdf = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            printer = QPrinter(QPrinter.ScreenResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(tmp_pdf)
            printer.setPageLayout(QPageLayout(QPageSize(QPageSize.Letter), QPageLayout.Portrait, QMarginsF(0.5, 0.5, 0.5, 0.5), QPageLayout.Inch))
            page_rect = printer.pageRect(QPrinter.DevicePixel)

            body_doc = QTextDocument(); body_doc.documentLayout().setPaintDevice(printer); body_doc.setHtml(b_html)
            footer_doc = QTextDocument(); footer_doc.documentLayout().setPaintDevice(printer); footer_doc.setHtml(f_html); footer_doc.setTextWidth(page_rect.width())
            footer_h = footer_doc.size().height()
            usable_h = max(100.0, page_rect.height() - footer_h - 16.0)
            body_doc.setPageSize(QSizeF(page_rect.width(), usable_h))
            total_pages = max(1, body_doc.pageCount())

            painter = QPainter(printer)
            for pg in range(total_pages):
                if pg > 0:
                    printer.newPage()
                painter.save()
                y_off = pg * usable_h
                painter.translate(0, -y_off)
                body_doc.drawContents(painter, QRectF(0, y_off, page_rect.width(), usable_h))
                painter.restore()
                painter.save()
                painter.translate(0, page_rect.height() - footer_h)
                footer_doc.drawContents(painter)
                painter.setPen(QColor("#64748b"))
                painter.drawText(QRectF(0, footer_h - 18, page_rect.width(), 18), Qt.AlignRight | Qt.AlignVCenter, f"Page {pg + 1} of {total_pages}")
                painter.restore()
            painter.end()

            doc = pymupdf.open(tmp_pdf)
            pg0 = doc.load_page(0)
            pix = pg0.get_pixmap(dpi=135, alpha=False)
            from PySide6.QtGui import QImage
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
            doc.close()
        finally:
            try:
                os.remove(tmp_pdf)
            except Exception:
                pass

        dlg = QDialog(self)
        dlg.setWindowTitle("Customer Quote PDF Preview (8.5 x 11 Letter)")
        dlg.resize(740, 930)
        dlg.setStyleSheet("QDialog { background-color: #cbd5e1; }")
        vl = QVBoxLayout(dlg); vl.setContentsMargins(14, 14, 14, 14)
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setFrameShape(QFrame.NoFrame)
        sc.setStyleSheet("background: transparent;")
        holder = QWidget(); hl = QVBoxLayout(holder); hl.setAlignment(Qt.AlignCenter)
        lbl_page = QLabel()
        pm_fit = QPixmap.fromImage(qimg).scaled(650, 842, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        lbl_page.setPixmap(pm_fit)
        lbl_page.setStyleSheet("background-color: #ffffff; border: 1.5px solid #64748b;")
        hl.addWidget(lbl_page)
        sc.setWidget(holder)
        vl.addWidget(sc)
        dlg.exec()

    def _reset_default(self):
        self.cfg["logo_path"] = ""; self.cfg["accent_color"] = "#0284c7"; self.cfg["table_header_color"] = "#0f172a"; self.cfg["table_stripe_color"] = "#f8fafc"; self.cfg["table_border_color"] = "#cbd5e1"; self.cfg["blocks"] = default_blocks()
        self.canvas.selected_id = "header"; self._select_block("header"); self.canvas.update(); self._push_undo()

    def closeEvent(self, ev):
        if self.cfg != self._saved_snapshot:
            box = QMessageBox(self)
            box.setWindowTitle("Unsaved Quote Layout Changes")
            box.setStyleSheet("QMessageBox { background-color: #dcebfa; color: #0f172a; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; } QLabel { color: #0f172a; font-weight: 600; background: transparent; border: none; } QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; border-radius: 6px; padding: 6px 14px; min-width: 110px; } QPushButton:hover { background-color: #e0f2fe; color: #0369a1; }")
            box.setText("You have unsaved changes to your Customer Quote Style & Layout.\nIf you close now, your edits will be lost.")
            b_save = box.addButton("Save && Close", QMessageBox.AcceptRole)
            b_disc = box.addButton("Discard Changes", QMessageBox.DestructiveRole)
            b_stay = box.addButton("Keep Editing", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() == b_save:
                self._save_template()
                ev.accept()
                return
            if box.clickedButton() != b_disc:
                ev.ignore()
                return
        ev.accept()

    def _save_template(self):
        os.makedirs(os.path.dirname(self.cfg_path), exist_ok=True)
        with open(self.cfg_path, "w", encoding="utf-8") as f: json.dump(self.cfg, f, indent=4)
        self._saved_snapshot = copy.deepcopy(self.cfg)
        QMessageBox.information(self, "Quote Layout Saved", "Your custom block positions, fonts, colors, logo, and customer-safe fields have been saved.")
        self.accept()
