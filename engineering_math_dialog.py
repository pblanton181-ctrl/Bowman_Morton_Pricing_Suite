# -*- coding: utf-8 -*-
import math
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPolygonF
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QFormLayout,
    QDoubleSpinBox, QComboBox, QLabel, QPushButton, QMessageBox,
    QFrame, QGridLayout
)


class _ShopCadViewport(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 270)
        self.mode = "stair"
        self.data = {}

    def set_scene(self, mode, data):
        self.mode = mode
        self.data = dict(data)
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#0f172a"))
        p.setPen(QPen(QColor("#334155"), 1.5))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 7, 7)

        p.setPen(QPen(QColor(30, 41, 59, 180), 1))
        for gx in range(18, w, 22):
            p.drawLine(gx, 4, gx, h - 4)
        for gy in range(18, h, 22):
            p.drawLine(4, gy, w - 4, gy)

        p.setFont(QFont("Consolas", 9, QFont.Bold))
        if self.mode == "stair":
            run = max(1.0, float(self.data.get("run_in", 120.0)))
            rise = max(1.0, float(self.data.get("rise_in", 96.0)))
            n_r = max(2, int(self.data.get("risers", 14)))
            sc = min((w - 84) / run, (h - 74) / rise)
            bw, bh = run * sc, rise * sc
            x0, y0 = (w - bw) * 0.5, (h + bh) * 0.5 + 8
            p.setPen(QPen(QColor("#64748b"), 1.5, Qt.DashLine))
            p.drawLine(int(x0 - 16), int(y0), int(x0 + bw + 16), int(y0))
            p.drawLine(int(x0 + bw - 10), int(y0 - bh), int(x0 + bw + 26), int(y0 - bh))
            p.setPen(QPen(QColor("#38bdf8"), 3.0))
            p.drawLine(QPointF(x0, y0), QPointF(x0 + bw, y0 - bh))
            p.setPen(QPen(QColor("#34d399"), 1.5))
            dx_s, dy_s = bw / max(1, n_r - 1), bh / n_r
            cx, cy = x0, y0
            for i in range(n_r):
                p.drawLine(QPointF(cx, cy), QPointF(cx, cy - dy_s))
                cy -= dy_s
                if i < n_r - 1:
                    p.drawLine(QPointF(cx, cy), QPointF(cx + dx_s, cy))
                    cx += dx_s
            p.setPen(QColor("#f8fafc"))
            p.drawText(int(x0 + bw * 0.25), int(y0 + 18), f"Run: {self.data.get('run_s', '')}")
            p.drawText(int(x0 + bw + 8), int(y0 - bh * 0.5), f"Rise: {self.data.get('rise_s', '')}")
            p.setPen(QColor("#fbbf24"))
            p.drawText(int(x0 + 8), int(y0 - bh * 0.62), f"Cut: {self.data.get('cut_s', '')} @ {self.data.get('ang', 0):.1f}°")

        elif self.mode == "brace":
            bw_ft = max(1.0, float(self.data.get("bay_ft", 14.0)))
            bh_ft = max(1.0, float(self.data.get("ht_ft", 12.0)))
            sc = min((w - 86) / bw_ft, (h - 76) / bh_ft)
            gw, gh = bw_ft * sc, bh_ft * sc
            x0, y0 = (w - gw) * 0.5, (h + gh) * 0.5 + 8
            p.setPen(QPen(QColor("#94a3b8"), 3.0))
            p.drawLine(int(x0), int(y0 + 10), int(x0), int(y0 - gh - 12))
            p.drawLine(int(x0 - 12), int(y0 - gh), int(x0 + gw + 14), int(y0 - gh))
            p.setBrush(QColor(251, 191, 36, 70))
            p.setPen(QPen(QColor("#fbbf24"), 1.6))
            p.drawPolygon(QPolygonF([QPointF(x0, y0 - gh), QPointF(x0 + 36, y0 - gh), QPointF(x0, y0 - gh + 36)]))
            p.setPen(QPen(QColor("#38bdf8"), 3.2))
            p.drawLine(QPointF(x0 + 18, y0 - gh + 18), QPointF(x0 + gw - 14, y0 - 14))
            p.setPen(QColor("#38bdf8"))
            p.drawText(int(x0 + gw * 0.22), int(y0 - gh * 0.35), f"Net Cut: {self.data.get('net_s', '')}")
            p.setPen(QColor("#fbbf24"))
            p.drawText(int(x0 + 42), int(y0 - gh + 16), f"Gusset: {self.data.get('gus_s', '')}")

        elif self.mode == "roll":
            od = max(4.0, float(self.data.get("od_in", 24.0)))
            ht = max(2.0, float(self.data.get("ht_in", 18.0)))
            r_px = min(w * 0.16, h * 0.26, 46.0)
            cx, cy = w * 0.25, h * 0.5
            p.setBrush(QColor(56, 189, 248, 35))
            p.setPen(QPen(QColor("#38bdf8"), 2.2))
            p.drawEllipse(QPointF(cx, cy), r_px, r_px)
            p.setBrush(QColor("#0f172a"))
            p.drawEllipse(QPointF(cx, cy), max(4.0, r_px * 0.78), max(4.0, r_px * 0.78))
            p.setPen(QColor("#f8fafc"))
            p.drawText(int(cx - 32), int(cy + r_px + 18), f'OD {od:g}"')
            rx, ry = w * 0.48, h * 0.26
            rw, rh = w * 0.44, h * 0.46
            p.setBrush(QColor(52, 211, 153, 35))
            p.setPen(QPen(QColor("#34d399"), 2.0))
            p.drawRect(QRectF(rx, ry, rw, rh))
            p.setPen(QColor("#34d399"))
            p.drawText(int(rx + 6), int(ry - 6), f"Flat Blank: {self.data.get('blank_s', '')}")
            p.setPen(QColor("#cbd5e1"))
            p.drawText(int(rx + 6), int(ry + rh + 16), f'Seam Weld: {ht:g}"')

        elif self.mode == "baseplate":
            pw_in = max(4.0, float(self.data.get("pw", 14.0)))
            pl_in = max(4.0, float(self.data.get("pl", 14.0)))
            cw_in = max(1.0, float(self.data.get("cw", 6.0)))
            sc = min((w - 90) / pw_in, (h - 75) / pl_in)
            bw, bh = pw_in * sc, pl_in * sc
            x0, y0 = (w - bw) * 0.5, (h - bh) * 0.5
            p.setBrush(QColor(56, 189, 248, 28))
            p.setPen(QPen(QColor("#38bdf8"), 2.0))
            p.drawRect(QRectF(x0, y0, bw, bh))
            cw_px = cw_in * sc
            p.setBrush(QColor(148, 163, 184, 55))
            p.setPen(QPen(QColor("#e2e8f0"), 2.0))
            p.drawRect(QRectF(x0 + (bw - cw_px) * 0.5, y0 + (bh - cw_px) * 0.5, cw_px, cw_px))
            p.setBrush(QColor("#fbbf24"))
            p.setPen(QPen(QColor("#0f172a"), 1.0))
            for hx, hy in self.data.get("holes", []):
                qx, qy = x0 + hx * sc, y0 + hy * sc
                p.drawEllipse(QPointF(qx, qy), 4.5, 4.5)
            p.setPen(QColor("#f8fafc"))
            p.drawText(int(x0), int(y0 - 6), f'Plate: {pw_in:g}" x {pl_in:g}"')


class EngineeringTrigGeometryDialog(QDialog):
    def __init__(self, on_stamp_note=None, parent=None):
        super().__init__(parent)
        self.on_stamp_note = on_stamp_note
        self._last_summary = ""
        self._tab_summaries = {}
        self._tab_shapes = {}
        self._tab_quote_items = {}
        self.setWindowTitle("Structural Steel Fab & Layout Studio")
        self.resize(940, 560)
        self.setStyleSheet('''
            QDialog { background-color: #f1f5f9; color: #0f172a; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12.5px; }
            QTabWidget::pane { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px; }
            QTabBar::tab { background-color: #e2e8f0; color: #334155; padding: 8px 16px; border: 1px solid #cbd5e1; border-bottom: none; border-top-left-radius: 5px; border-top-right-radius: 5px; margin-right: 3px; font-weight: 600; }
            QTabBar::tab:selected { background-color: #ffffff; color: #0369a1; font-weight: 700; border-top: 3px solid #0284c7; }
            QDoubleSpinBox, QComboBox { background-color: #f8fafc; color: #0f172a; border: 1px solid #94a3b8; border-radius: 4px; padding: 4px 8px; font-weight: 600; min-width: 135px; }
            QPushButton { background-color: #ffffff; border: 1px solid #94a3b8; color: #0f172a; font-weight: 600; border-radius: 5px; padding: 7px 14px; }
            QPushButton#QuoteSendBtn { background-color: #059669; border: 1px solid #047857; color: #ffffff; font-weight: 700; }
            QPushButton#StampBtn { background-color: #0284c7; border: 1px solid #0369a1; color: #ffffff; font-weight: 700; }
        ''')
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_stair_tab(), "1. Stair Stringer & IBC Layout")
        self.tabs.addTab(self._build_brace_tab(), "2. Brace & Gusset Setbacks")
        self.tabs.addTab(self._build_roll_tab(), "3. Rolled Plate Stretch-Out")
        self.tabs.addTab(self._build_baseplate_tab(), "4. Base Plate & Bolt Pattern")
        lay.addWidget(self.tabs, 1)

        bot = QHBoxLayout()
        self.btn_send_quote = QPushButton("Send Calculated Steel & Plates to Tab 2 Quote"); self.btn_send_quote.setObjectName("QuoteSendBtn")
        self.btn_send_quote.clicked.connect(self._send_to_tab2_quote); bot.addWidget(self.btn_send_quote)
        self.btn_stamp = QPushButton("Stamp Shop Detail onto Blueprint"); self.btn_stamp.setObjectName("StampBtn")
        self.btn_stamp.clicked.connect(self._stamp_to_sheet); bot.addWidget(self.btn_stamp); bot.addStretch()
        btn_close = QPushButton("Close"); btn_close.clicked.connect(self.accept); bot.addWidget(btn_close); lay.addLayout(bot)

    def _make_kv_card(self, keys):
        card = QFrame(); card.setStyleSheet("QFrame { background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px; } QLabel { border: none; background: transparent; }")
        gl = QGridLayout(card); val_lbls = {}
        for r, k_txt in enumerate(keys):
            kl = QLabel(k_txt); kl.setStyleSheet("color: #475569; font-size: 12px; font-weight: 600;")
            vl = QLabel("-"); vl.setStyleSheet("color: #0f172a; font-size: 13px; font-weight: 700;"); vl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            gl.addWidget(kl, r, 0); gl.addWidget(vl, r, 1); val_lbls[k_txt] = vl
        return card, val_lbls

    def _fmt_ft_in(self, ft_val):
        tot16 = int(round(abs(ft_val) * 192.0))
        whole_in, rem16 = divmod(tot16, 16)
        feet, inches = divmod(whole_in, 12)
        frac = "" if rem16 == 0 else f" {rem16 // math.gcd(rem16, 16)}/{16 // math.gcd(rem16, 16)}"
        return f'{feet}\'-{inches}{frac}"'


    def _build_stair_tab(self):
        w = QWidget(); hl = QHBoxLayout(w); fl = QFormLayout(); left_col = QVBoxLayout()
        self.st_rise = QDoubleSpinBox(); self.st_rise.setRange(1.0, 60.0); self.st_rise.setDecimals(3); self.st_rise.setValue(10.0); self.st_rise.setSuffix(" ft")
        self.st_run = QDoubleSpinBox(); self.st_run.setRange(1.0, 80.0); self.st_run.setDecimals(3); self.st_run.setValue(14.667); self.st_run.setSuffix(" ft")
        self.st_width = QDoubleSpinBox(); self.st_width.setRange(24.0, 120.0); self.st_width.setDecimals(1); self.st_width.setValue(44.0); self.st_width.setSuffix(" in")
        self.st_prof = QComboBox(); self.st_prof.addItems(["MC12X10.6", "C12X20.7", "C10X15.3", 'PL 1/2" x 12"', 'PL 3/8" x 12"'])
        fl.addRow("Floor-to-Floor Rise:", self.st_rise); fl.addRow("Total Horizontal Run:", self.st_run); fl.addRow("Stair Clear Width:", self.st_width); fl.addRow("Stringer Section:", self.st_prof); left_col.addLayout(fl)
        card, kv = self._make_kv_card(["Risers & Treads Count", "Actual Riser / Tread Step", "IBC / OSHA Code Check", "Stringer Cut Length & Miter", "Est. Steel Weight (2 Stringers + Angles)"])
        left_col.addWidget(card, 1); hl.addLayout(left_col, 3); diag = _ShopCadViewport(); hl.addWidget(diag, 2)

        def _calc_stair():
            rise_in, run_in, wid_in, prof = self.st_rise.value() * 12.0, self.st_run.value() * 12.0, self.st_width.value(), self.st_prof.currentText()
            n_risers = max(2, int(round(rise_in / 7.0))); n_treads = n_risers - 1
            act_r, act_t = rise_in / n_risers, run_in / max(1, n_treads)
            slope_ft = round((math.hypot(rise_in, run_in) + 14.0) / 12.0, 2); deg = math.degrees(math.atan2(rise_in, run_in))
            code_ok = (act_r <= 7.05 and act_t >= 10.95)
            uw = {"MC12X10.6": 10.6, "C12X20.7": 20.7, "C10X15.3": 15.3, 'PL 1/2" x 12"': 20.42, 'PL 3/8" x 12"': 15.32}.get(prof, 15.0)
            angle_ft = round(wid_in / 12.0, 2); tot_wgt = (2 * slope_ft * uw) + (2 * n_treads * angle_ft * 3.19)
            kv["Risers & Treads Count"].setText(f"{n_risers} Risers  /  {n_treads} Treads")
            kv["Actual Riser / Tread Step"].setText(f'{act_r:.3f}" R  x  {act_t:.3f}" T')
            kv["IBC / OSHA Code Check"].setText('PASS (IBC <=7" R / >=11" T)' if code_ok else f'CHECK: {act_r:.2f}" R x {act_t:.2f}" T')
            kv["Stringer Cut Length & Miter"].setText(f"{self._fmt_ft_in(slope_ft)} ({slope_ft:.2f}') @ {deg:.1f}°")
            kv["Est. Steel Weight (2 Stringers + Angles)"].setText(f"{tot_wgt:,.1f} lbs")
            self._tab_summaries[0] = f'STAIR {n_risers}R/{n_treads}T ({act_r:.2f}"x{act_t:.2f}") | (2) {prof} @ {self._fmt_ft_in(slope_ft)} ({deg:.1f} deg)'
            self._tab_shapes[0] = {"kind": "right", "run": self.st_run.value(), "rise": self.st_rise.value(), "hyp": slope_ft, "deg": deg, "pitch": (rise_in / run_in) * 12.0, "run_s": self._fmt_ft_in(self.st_run.value()), "rise_s": self._fmt_ft_in(self.st_rise.value()), "hyp_s": self._fmt_ft_in(slope_ft)}
            is_pl = prof.startswith("PL")
            self._tab_quote_items[0] = [{"category": "Plates & Base Plates" if is_pl else "Channels", "sheet": "Layout Studio", "detail_ref": f"Stair {deg:.1f}°", "shape_key": "plate" if is_pl else "channel", "profile": "PL 1/2X12" if "1/2" in prof else ("PL 3/8X12" if "3/8" in prof else prof), "qty": 2, "length": slope_ft, "unit_wt": uw, "plate_w": "12", "plate_thk": "0.5" if "1/2" in prof else ("0.375" if "3/8" in prof else "")}, {"category": "Angles", "sheet": "Layout Studio", "detail_ref": "Tread Carriers", "shape_key": "angle", "profile": "L2X2X1/4", "qty": 2 * n_treads, "length": angle_ft, "unit_wt": 3.19, "plate_w": "12", "plate_thk": ""}]
            diag.set_scene("stair", {"run_in": run_in, "rise_in": rise_in, "risers": n_risers, "run_s": self._fmt_ft_in(self.st_run.value()), "rise_s": self._fmt_ft_in(self.st_rise.value()), "cut_s": self._fmt_ft_in(slope_ft), "ang": deg})

        for w_in in (self.st_rise, self.st_run, self.st_width): w_in.valueChanged.connect(_calc_stair)
        self.st_prof.currentIndexChanged.connect(_calc_stair); _calc_stair(); return w


    def _build_brace_tab(self):
        w = QWidget(); hl = QHBoxLayout(w); fl = QFormLayout(); left_col = QVBoxLayout()
        self.br_bay = QDoubleSpinBox(); self.br_bay.setRange(1.0, 60.0); self.br_bay.setDecimals(3); self.br_bay.setValue(14.0); self.br_bay.setSuffix(" ft")
        self.br_ht = QDoubleSpinBox(); self.br_ht.setRange(1.0, 60.0); self.br_ht.setDecimals(3); self.br_ht.setValue(12.0); self.br_ht.setSuffix(" ft")
        self.br_prof = QComboBox(); self.br_prof.addItems(["HSS4X4X1/4", "HSS5X5X1/4", "HSS6X6X3/8", "HSS4X2.5X1/4", "L4X4X3/8"])
        self.br_setback = QDoubleSpinBox(); self.br_setback.setRange(0.0, 36.0); self.br_setback.setDecimals(2); self.br_setback.setValue(8.5); self.br_setback.setSuffix(" in (each end)")
        self.br_gus_thk = QComboBox(); self.br_gus_thk.addItems(['3/8"', '1/2"', '5/8"', '3/4"'])
        fl.addRow("Bay Width (Work-Point):", self.br_bay); fl.addRow("Story Height (Work-Point):", self.br_ht); fl.addRow("Diagonal Brace Size:", self.br_prof); fl.addRow("Gusset Setback:", self.br_setback); fl.addRow("Gusset Plate Thickness:", self.br_gus_thk); left_col.addLayout(fl)
        card, kv = self._make_kv_card(["Work-Point Diagonal (C-to-C)", "Net Brace Cut Length", "Brace Slope & Bevel Angle", "Gusset Plate Blank (2x)", "Total Brace + Gussets Weight"])
        left_col.addWidget(card, 1); hl.addLayout(left_col, 3); diag = _ShopCadViewport(); hl.addWidget(diag, 2)

        def _calc_brace():
            bay_ft, ht_ft = self.br_bay.value(), self.br_ht.value()
            wp_ft = math.hypot(bay_ft, ht_ft); net_ft = max(0.5, wp_ft - (2.0 * self.br_setback.value() / 12.0)); deg = math.degrees(math.atan2(ht_ft, bay_ft))
            prof = self.br_prof.currentText(); uw = {"HSS4X4X1/4": 12.75, "HSS5X5X1/4": 16.15, "HSS6X6X3/8": 28.69, "HSS4X2.5X1/4": 10.20, "L4X4X3/8": 9.72}.get(prof, 14.0)
            g_thk = {'3/8"': 0.375, '1/2"': 0.50, '5/8"': 0.625, '3/4"': 0.75}.get(self.br_gus_thk.currentText(), 0.375)
            g_w, g_l = 14.0, 16.0; gus_uw = round((g_thk * (g_w / 12.0)) * 40.8, 2); tot_wgt = (net_ft * uw) + (2 * (g_l / 12.0) * gus_uw)
            kv["Work-Point Diagonal (C-to-C)"].setText(f"{self._fmt_ft_in(wp_ft)} ({wp_ft:.3f}')")
            kv["Net Brace Cut Length"].setText(f"{self._fmt_ft_in(net_ft)} ({net_ft:.2f}')")
            kv["Brace Slope & Bevel Angle"].setText(f"{deg:.2f}°  (Bevel {90.0 - deg:.2f}°)")
            kv["Gusset Plate Blank (2x)"].setText(f'PL {self.br_gus_thk.currentText()} x {g_w:g}" x {g_l:g}"')
            kv["Total Brace + Gussets Weight"].setText(f"{tot_wgt:,.1f} lbs")
            self._tab_summaries[1] = f'BRACE {prof} NET CUT {self._fmt_ft_in(net_ft)} @ {deg:.1f}° + (2) GUSSET PL {self.br_gus_thk.currentText()}x{g_w:g}"x{g_l:g}"'
            self._tab_shapes[1] = {"kind": "right", "run": bay_ft, "rise": ht_ft, "hyp": net_ft, "deg": deg, "pitch": (ht_ft / bay_ft) * 12.0, "run_s": self._fmt_ft_in(bay_ft), "rise_s": self._fmt_ft_in(ht_ft), "hyp_s": self._fmt_ft_in(net_ft)}
            self._tab_quote_items[1] = [{"category": "Angles" if prof.startswith("L") else "HSS & Pipe", "sheet": "Layout Studio", "detail_ref": f"Brace {deg:.1f}°", "shape_key": "angle" if prof.startswith("L") else "hss_tube", "profile": prof, "qty": 1, "length": round(net_ft, 2), "unit_wt": uw, "plate_w": "12", "plate_thk": ""}, {"category": "Plates & Base Plates", "sheet": "Layout Studio", "detail_ref": "Gusset Plates", "shape_key": "plate", "profile": f"PL {self.br_gus_thk.currentText()}X{g_w:g}X{g_l:g}", "qty": 2, "length": round(g_l / 12.0, 2), "unit_wt": gus_uw, "plate_w": str(g_w), "plate_thk": str(g_thk)}]
            diag.set_scene("brace", {"bay_ft": bay_ft, "ht_ft": ht_ft, "net_s": self._fmt_ft_in(net_ft), "gus_s": f"{self.br_gus_thk.currentText()}x{g_w:g}x{g_l:g}"})

        for w_in in (self.br_bay, self.br_ht, self.br_setback): w_in.valueChanged.connect(_calc_brace)
        for cb_in in (self.br_prof, self.br_gus_thk): cb_in.currentIndexChanged.connect(_calc_brace)
        _calc_brace(); return w


    def _build_roll_tab(self):
        w = QWidget(); hl = QHBoxLayout(w); fl = QFormLayout(); left_col = QVBoxLayout()
        self.rl_id = QDoubleSpinBox(); self.rl_id.setRange(2.0, 240.0); self.rl_id.setDecimals(3); self.rl_id.setValue(24.0); self.rl_id.setSuffix(" in (ID)")
        self.rl_ht = QDoubleSpinBox(); self.rl_ht.setRange(1.0, 240.0); self.rl_ht.setDecimals(3); self.rl_ht.setValue(18.0); self.rl_ht.setSuffix(" in (Height)")
        self.rl_thk = QComboBox(); self.rl_thk.addItems(['3/16"', '1/4"', '5/16"', '3/8"', '1/2"', '3/4"']); self.rl_thk.setCurrentText('1/4"')
        fl.addRow("Cylinder Inside Dia (ID):", self.rl_id); fl.addRow("Cylinder Height / Width:", self.rl_ht); fl.addRow("Shell Plate Thickness:", self.rl_thk); left_col.addLayout(fl)
        card, kv = self._make_kv_card(["Mean Neutral-Axis Diameter", "Finished Outside Diameter", "Flat Plate Stretch-Out Blank", "Longitudinal Seam Weld", "Rolled Shell Weight"])
        left_col.addWidget(card, 1); hl.addLayout(left_col, 3); diag = _ShopCadViewport(); hl.addWidget(diag, 2)

        def _calc_roll():
            id_in, ht_in = self.rl_id.value(), self.rl_ht.value()
            thk = {'3/16"': 0.1875, '1/4"': 0.25, '5/16"': 0.3125, '3/8"': 0.375, '1/2"': 0.50, '3/4"': 0.75}.get(self.rl_thk.currentText(), 0.25)
            mean_d, od_in = id_in + thk, id_in + (2.0 * thk)
            stretch_in = round(math.pi * mean_d, 3); uw = round((thk * (ht_in / 12.0)) * 40.8, 2); tot_wgt = round(uw * (stretch_in / 12.0), 1)
            kv["Mean Neutral-Axis Diameter"].setText(f"{mean_d:.3f} in")
            kv["Finished Outside Diameter"].setText(f"{od_in:.3f} in")
            kv["Flat Plate Stretch-Out Blank"].setText(f'{self.rl_thk.currentText()} x {ht_in:g}" x {stretch_in:.2f}"')
            kv["Longitudinal Seam Weld"].setText(f'{ht_in:g} in (100% CJP/Fillet)')
            kv["Rolled Shell Weight"].setText(f"{tot_wgt:,.1f} lbs")
            self._tab_summaries[2] = f'ROLLED SHELL ID {id_in:g}" x {ht_in:g}" -> FLAT BLANK PL {self.rl_thk.currentText()} x {ht_in:g}" x {stretch_in:.2f}"'
            self._tab_shapes[2] = {"kind": "circle", "dia_in": od_in, "n": 4, "bolt_deg": 90.0, "bolt_chord": od_in * 0.7071}
            self._tab_quote_items[2] = [{"category": "Plates & Base Plates", "sheet": "Layout Studio", "detail_ref": f'Rolled ID {id_in:g}"', "shape_key": "plate", "profile": f"PL {self.rl_thk.currentText()}X{ht_in:g}X{stretch_in:.1f}", "qty": 1, "length": round(stretch_in / 12.0, 2), "unit_wt": uw, "plate_w": str(ht_in), "plate_thk": str(thk)}]
            diag.set_scene("roll", {"od_in": od_in, "ht_in": ht_in, "blank_s": f'{self.rl_thk.currentText()} x {ht_in:g}" x {stretch_in:.1f}"'})

        self.rl_id.valueChanged.connect(_calc_roll); self.rl_ht.valueChanged.connect(_calc_roll); self.rl_thk.currentIndexChanged.connect(_calc_roll); _calc_roll(); return w


    def _build_baseplate_tab(self):
        w = QWidget(); hl = QHBoxLayout(w); fl = QFormLayout(); left_col = QVBoxLayout()
        self.bp_col = QDoubleSpinBox(); self.bp_col.setRange(2.0, 24.0); self.bp_col.setDecimals(2); self.bp_col.setValue(6.0); self.bp_col.setSuffix(" in (Col)")
        self.bp_w = QDoubleSpinBox(); self.bp_w.setRange(4.0, 48.0); self.bp_w.setDecimals(2); self.bp_w.setValue(14.0); self.bp_w.setSuffix(" in (W)")
        self.bp_l = QDoubleSpinBox(); self.bp_l.setRange(4.0, 48.0); self.bp_l.setDecimals(2); self.bp_l.setValue(14.0); self.bp_l.setSuffix(" in (L)")
        self.bp_thk = QComboBox(); self.bp_thk.addItems(['3/8"', '1/2"', '5/8"', '3/4"', '1"', '1-1/4"']); self.bp_thk.setCurrentText('1/2"')
        self.bp_edge = QDoubleSpinBox(); self.bp_edge.setRange(0.75, 6.0); self.bp_edge.setDecimals(2); self.bp_edge.setValue(1.75); self.bp_edge.setSuffix(" in (Edge)")
        self.bp_bolts = QComboBox(); self.bp_bolts.addItems(["4-Bolt (Corners)", "6-Bolt (3 per side)", "8-Bolt (Perimeter)"])
        fl.addRow("Column Width / Depth:", self.bp_col); fl.addRow("Base Plate Width:", self.bp_w); fl.addRow("Base Plate Length:", self.bp_l); fl.addRow("Base Plate Thickness:", self.bp_thk); fl.addRow("Bolt Edge Distance:", self.bp_edge); fl.addRow("Anchor Bolt Pattern:", self.bp_bolts); left_col.addLayout(fl)
        card, kv = self._make_kv_card(["Bolt Gage Spacing (C-to-C)", "Socket / Wrench Clearance", "Hole Coordinates (0,0 Corner)", "Base Plate Weight (Each)"])
        left_col.addWidget(card, 1); hl.addLayout(left_col, 3); diag = _ShopCadViewport(); hl.addWidget(diag, 2)

        def _calc_bp():
            cw, pw, pl, ed = self.bp_col.value(), self.bp_w.value(), self.bp_l.value(), self.bp_edge.value()
            thk = {'3/8"': 0.375, '1/2"': 0.50, '5/8"': 0.625, '3/4"': 0.75, '1"': 1.0, '1-1/4"': 1.25}.get(self.bp_thk.currentText(), 0.50)
            gx, gy = max(1.0, pw - 2.0 * ed), max(1.0, pl - 2.0 * ed)
            clear_in = ((pw - cw) * 0.5) - ed; pat = self.bp_bolts.currentText()
            holes = [(ed, ed), (pw - ed, ed), (ed, pl - ed), (pw - ed, pl - ed)]
            if "6-Bolt" in pat: holes.extend([(ed, pl * 0.5), (pw - ed, pl * 0.5)])
            elif "8-Bolt" in pat: holes.extend([(ed, pl * 0.5), (pw - ed, pl * 0.5), (pw * 0.5, ed), (pw * 0.5, pl - ed)])
            uw = round((thk * (pw / 12.0)) * 40.8, 2); pc_wgt = round(uw * (pl / 12.0), 1); clr_ok = clear_in >= 1.25
            kv["Bolt Gage Spacing (C-to-C)"].setText(f'{gx:g}" X  x  {gy:g}" Y  ({len(holes)} Holes)')
            kv["Socket / Wrench Clearance"].setText(f'{clear_in:.2f}" ({"PASS" if clr_ok else "TIGHT TO COLUMN"})')
            kv["Hole Coordinates (0,0 Corner)"].setText(f'({ed:g}", {ed:g}") -> ({pw - ed:g}", {pl - ed:g}")')
            kv["Base Plate Weight (Each)"].setText(f"{pc_wgt:,.1f} lbs")
            self._tab_summaries[3] = f'BASE PL {self.bp_thk.currentText()}x{pw:g}"x{pl:g}" | {len(holes)} HOLES @ {gx:g}"x{gy:g}" GAGE'
            self._tab_shapes[3] = {"kind": "baseplate", "pw": pw, "pl": pl, "cw": cw, "holes": holes, "n": len(holes), "gx": gx, "gy": gy}
            self._tab_quote_items[3] = [{"category": "Plates & Base Plates", "sheet": "Layout Studio", "detail_ref": f"{len(holes)}-Bolt Base", "shape_key": "plate", "profile": f"BASE PL {self.bp_thk.currentText()}X{pw:g}X{pl:g}", "qty": 1, "length": round(pl / 12.0, 2), "unit_wt": uw, "plate_w": str(pw), "plate_thk": str(thk)}]
            diag.set_scene("baseplate", {"pw": pw, "pl": pl, "cw": cw, "holes": holes})

        for w_in in (self.bp_col, self.bp_w, self.bp_l, self.bp_edge): w_in.valueChanged.connect(_calc_bp)
        for cb_in in (self.bp_thk, self.bp_bolts): cb_in.currentIndexChanged.connect(_calc_bp)
        _calc_bp(); return w

    def _send_to_tab2_quote(self):
        idx = self.tabs.currentIndex()
        items = self._tab_quote_items.get(idx, [])
        p_win = self.parent()
        t2 = getattr(p_win, "custom_quoting_tab", None)
        if t2 and hasattr(t2, "ingest_pdf_bom_items") and items:
            t2.ingest_pdf_bom_items(items)
            if hasattr(p_win, "master_tabs"): p_win.master_tabs.setCurrentWidget(t2)
            if hasattr(p_win, "master_ribbon"): p_win.master_ribbon.set_active_tab(2)
            self.accept()
        else:
            QMessageBox.information(self, "Ready", "Calculated steel items staged.")

    def _stamp_to_sheet(self):
        idx = self.tabs.currentIndex()
        msg = self._tab_summaries.get(idx, self._last_summary)
        shape_data = self._tab_shapes.get(idx)
        if callable(self.on_stamp_note) and msg:
            try: self.on_stamp_note(msg, shape_data)
            except TypeError: self.on_stamp_note(msg)
            self.accept()
        else:
            QMessageBox.information(self, "Result", msg)
