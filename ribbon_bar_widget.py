# -*- coding: utf-8 -*-
import os, csv, datetime, tempfile, subprocess
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QPixmap, QIcon, QFont, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QStackedWidget, QDialog, QLineEdit, QGridLayout, QSizePolicy,
    QToolButton, QMessageBox, QInputDialog, QColorDialog, QApplication, QCompleter
)
from ui.icon_loader import get_icon
from ui.ribbon_factory import RibbonFactory, load_ribbon_schema

def _win_caption_icon(kind, color_hex="#1f2937"):
    pm = QPixmap(32, 32); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing, True); p.setRenderHint(QPainter.TextAntialiasing, True)
    p.setPen(QColor(color_hex))
    glyphs = {"min": "\uE921", "max": "\uE922", "restore": "\uE923", "close": "\uE8BB"}
    f = QFont("Segoe Fluent Icons", 10)
    if not f.exactMatch():
        f = QFont("Segoe MDL2 Assets", 10)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, glyphs.get(kind, "\uE922"))
    p.end()
    pm.setDevicePixelRatio(2.0)
    return QIcon(pm)

class _QuickEstimatorCalcDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Shop & Structural Calculator"); self.setFixedSize(310, 350)
        self.setStyleSheet("QDialog { background-color: #f8fafc; border: 1px solid #cbd5e1; } QLineEdit { background-color: #ffffff; color: #0f172a; border: 1px solid #94a3b8; border-radius: 5px; padding: 6px 8px; font-size: 18px; font-weight: 700; } QPushButton { background-color: #ffffff; border: 1px solid #cbd5e1; color: #0f172a; font-size: 14px; font-weight: 600; border-radius: 5px; padding: 6px; } QPushButton:hover { background-color: #e0f2fe; border-color: #0284c7; }")
        lay = QVBoxLayout(self); lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(8)
        self.disp = QLineEdit(); self.disp.setAlignment(Qt.AlignRight); self.disp.setPlaceholderText("0"); self.disp.returnPressed.connect(self._eval); lay.addWidget(self.disp)
        grid = QGridLayout(); grid.setSpacing(5)
        for txt, r, c in [("7",0,0),("8",0,1),("9",0,2),("/",0,3),("4",1,0),("5",1,1),("6",1,2),("*",1,3),("1",2,0),("2",2,1),("3",2,2),("-",2,3),("0",3,0),(".",3,1),("C",3,2),("+",3,3)]:
            b = QPushButton(txt)
            if txt == "C": b.clicked.connect(self.disp.clear)
            else: b.clicked.connect(lambda _=False, t=txt: self.disp.setText(self.disp.text() + t))
            grid.addWidget(b, r, c)
        lay.addLayout(grid, 1)
        eq_btn = QPushButton("= Compute"); eq_btn.clicked.connect(self._eval); lay.addWidget(eq_btn)

    def _eval(self):
        expr = self.disp.text().strip().replace("x", "*").replace("X", "*")
        if expr and all(ch in "0123456789.+-*/() " for ch in expr):
            try:
                res = eval(expr, {"__builtins__": None}, {})
                self.disp.setText(f"{res:,.4f}".rstrip("0").rstrip(".") if isinstance(res, float) else str(res))
            except Exception: self.disp.setText("Error")

class BowmanMortonRibbonBar(QFrame):
    def __init__(self, app_win, parent=None):
        super().__init__(parent)
        self.app = app_win; self._collapsed = False; self._active_color_hex = "#111827"
        self._swatch_btns = {}; self._mode_widgets = {}; self._tab_btns = []; self._ws_btns = []
        self._active_ws = 0; self._active_subtab = 0
        self.schema = load_ribbon_schema()
        self.factory = RibbonFactory(self)

        self.setObjectName("OfficeGreyRibbon"); self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(164); self.setMaximumHeight(164)
        self.setStyleSheet("""
            QFrame#OfficeGreyRibbon { background-color: #e5e7eb; border: none; border-bottom: 1px solid #c8c6c4; }
            QFrame#OfficeCommandBand { background-color: #f3f2f1; border: 1px solid #c8c6c4; border-radius: 6px; margin: 0px 8px 6px 8px; }
            QFrame#ContextualSelectionGroup { background-color: #eff6fc; border: 1px solid #0078d4; border-radius: 5px; margin-top: 3px; margin-bottom: 3px; }
            QLabel#OfficeGroupCap { color: #1e293b; background: transparent; font-size: 11px; font-weight: 700; border: none; padding: 1px 4px 0px 4px; }
            QLabel#CtxGroupCap { color: #0078d4; background: transparent; font-size: 10px; font-weight: 700; border: none; padding: 1px 4px 0px 4px; }
        """)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        title_bar = QFrame(); title_bar.setFixedHeight(32); title_bar.setStyleSheet("QFrame { background-color: #f3f2f1; border-bottom: 1px solid #e1dfdd; }")
        tr = QHBoxLayout(title_bar); tr.setContentsMargins(10, 0, 0, 0); tr.setSpacing(4)
        for qa in self.schema.get("quick_access", []):
            qb = QToolButton(); qb.setIcon(get_icon(qa.get("icon", ""), size=18)); qb.setIconSize(QSize(18, 18))
            qb.setToolTip(qa.get("tip", "")); qb.setCursor(Qt.PointingHandCursor); qb.setFixedSize(24, 24)
            qb.setStyleSheet("QToolButton { background: transparent; border: none; border-radius: 4px; } QToolButton:hover { background-color: #cbd5e1; }")
            qb.clicked.connect(lambda _=False, a=qa.get("action", ""): self.factory.dispatch(a)); tr.addWidget(qb)
        tr.addSpacing(8)
        brand = QLabel("BOWMAN MORTON")
        brand.setStyleSheet("color: #0f172a; font-size: 12px; font-weight: 800; background: transparent;")
        tr.addWidget(brand); tr.addSpacing(10)

        ws_pill = QFrame(); ws_pill.setStyleSheet("QFrame { background-color: #e2e8f0; border-radius: 5px; padding: 1px; }")
        wsl = QHBoxLayout(ws_pill); wsl.setContentsMargins(2, 2, 2, 2); wsl.setSpacing(2)
        for ws in self.schema.get("workspaces", []):
            idx = int(ws.get("tab_index", 0))
            wb_s = QPushButton(ws.get("label", "")); wb_s.setCursor(Qt.PointingHandCursor); wb_s.setFixedHeight(23)
            wb_s.clicked.connect(lambda _=False, i=idx: self._switch_workspace(i))
            wsl.addWidget(wb_s); self._ws_btns.append(wb_s)
        tr.addWidget(ws_pill); tr.addStretch(1)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Command (Ctrl+K): DIM, WELD, W12X26, BABU, or 14.5*26*1.30...")
        self.search_box.setFixedHeight(22); self.search_box.setMinimumWidth(180); self.search_box.setMaximumWidth(340)
        self.search_box.setStyleSheet("QLineEdit { background-color: #ffffff; color: #0f172a; border: 1px solid #94a3b8; border-radius: 4px; padding: 1px 10px; font-size: 11.5px; } QLineEdit:focus { border: 1.5px solid #0284c7; }")
        self.search_box.returnPressed.connect(self._on_quick_search)
        QShortcut(QKeySequence("Ctrl+K"), self.app, activated=self.search_box.setFocus)
        tr.addWidget(self.search_box); tr.addStretch(1)

        for kind, tip, slot, is_close in [("min", "Minimize", lambda: self.app.showMinimized(), False), ("max", "Maximize / Restore", self._toggle_max, False), ("close", "Close", lambda: self.app.close(), True)]:
            wb = QPushButton(""); wb.setIcon(_win_caption_icon(kind, "#1f2937")); wb.setIconSize(QSize(16, 16)); wb.setToolTip(tip); wb.setFixedSize(46, 30)
            h_bg = "#e81123" if is_close else "#cbd5e1"
            wb.setStyleSheet(f"QPushButton {{ background: transparent !important; border: none !important; border-radius: 0px; padding: 0px; }} QPushButton:hover {{ background-color: {h_bg} !important; }}")
            wb.clicked.connect(slot); tr.addWidget(wb)
            if kind == "max": self.btn_max = wb; wb.setIcon(_win_caption_icon("restore" if self.app.isMaximized() else "max", "#1f2937"))
            elif is_close:
                wb.enterEvent = lambda _e, b=wb: b.setIcon(_win_caption_icon("close", "#ffffff"))
                wb.leaveEvent = lambda _e, b=wb: b.setIcon(_win_caption_icon("close", "#1f2937"))
        outer.addWidget(title_bar)

        tab_strip = QFrame(); tab_strip.setFixedHeight(36); tab_strip.setStyleSheet("QFrame { background-color: #e5e7eb; border: none; }")
        self.tab_row = QHBoxLayout(tab_strip); self.tab_row.setContentsMargins(10, 2, 10, 0); self.tab_row.setSpacing(2)
        for idx in range(6):
            tb = QPushButton(""); tb.setObjectName("RibbonSubTabBtn"); tb.setCursor(Qt.PointingHandCursor); tb.setMinimumHeight(28); tb.setMaximumHeight(30); tb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            tb.clicked.connect(lambda _=False, i=idx: self._switch_subtab(i))
            self.tab_row.addWidget(tb); self._tab_btns.append(tb)

        self.tab_row.addSpacing(10)
        self.lbl_live_telemetry = QLabel("Armed: Hand Pan  |  Scale: 1/4\" = 1'-0\"")
        self.lbl_live_telemetry.setStyleSheet("color: #0369a1; background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 9px; padding: 1px 10px; font-size: 10.5px; font-weight: 600;")
        self.tab_row.addWidget(self.lbl_live_telemetry); self.tab_row.addStretch()

        self.btn_pin = QPushButton("Collapse"); self.btn_pin.setCursor(Qt.PointingHandCursor); self.btn_pin.setFixedHeight(22)
        self.btn_pin.setStyleSheet("QPushButton { background: transparent !important; border: none !important; color: #334155 !important; font-size: 11px; font-weight: 600; padding: 0px 8px !important; } QPushButton:hover { background-color: #cbd5e1 !important; border-radius: 4px; }")
        self.btn_pin.clicked.connect(self._toggle_collapse); self.tab_row.addWidget(self.btn_pin)
        outer.addWidget(tab_strip)

        self.cmd_band = QFrame(); self.cmd_band.setObjectName("OfficeCommandBand"); self.cmd_band.setAttribute(Qt.WA_StyledBackground, True)
        self.band_layout = QHBoxLayout(self.cmd_band); self.band_layout.setContentsMargins(4, 2, 4, 2); self.band_layout.setSpacing(0)

        self.ctx_stack = QStackedWidget(); self.ctx_stack.setStyleSheet("background: transparent; border: none;")
        self.ctx_stack.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        self._ws_subtab_labels = {}
        self._page_map = {}
        shared_tools = self.schema.get("shared_tools_subtab")
        for ws in self.schema.get("workspaces", []):
            ws_i = int(ws.get("tab_index", 0))
            subtabs = list(ws.get("subtabs", []))
            if shared_tools:
                subtabs.append(shared_tools)
            self._ws_subtab_labels[ws_i] = [st.get("label", "") for st in subtabs]
            for st_i, st_spec in enumerate(subtabs):
                self._page_map[(ws_i, st_i)] = self.ctx_stack.addWidget(self.factory.build_subtab_page(st_spec))
        self.band_layout.addWidget(self.ctx_stack, 0, Qt.AlignLeft)

        self.grp_selected_ctx, r_sel = self.factory.make_group("Selected Markup")
        self.grp_selected_ctx.setObjectName("ContextualSelectionGroup")
        self.lbl_sel_type = QLabel("None")
        self.lbl_sel_type.setStyleSheet("color: #0284c7; font-size: 10.5px; font-weight: 700; padding: 0px 4px;")
        sel_col = QVBoxLayout(); sel_col.setContentsMargins(2, 1, 2, 1); sel_col.setSpacing(2); sel_col.addWidget(self.lbl_sel_type)
        sel_btns = QHBoxLayout(); sel_btns.setSpacing(3)
        for s_lbl, s_fn in [("Clone", lambda: self._canvas_call("duplicate_selected_markup")), ("Rotate", lambda: self._canvas_call("rotate_selected_markup")), ("Delete", lambda: self._canvas_call("delete_selected_markup"))]:
            sb = QPushButton(s_lbl); sb.setFixedHeight(25); sb.setCursor(Qt.PointingHandCursor)
            sb.setStyleSheet("QPushButton { background-color: #ffffff; border: 1px solid #7dd3fc; color: #0f172a; font-size: 10.5px; font-weight: 600; border-radius: 3px; padding: 0px 6px; } QPushButton:hover { background-color: #bae6fd; }")
            sb.clicked.connect(s_fn); sel_btns.addWidget(sb)
        sel_col.addLayout(sel_btns); r_sel.addLayout(sel_col)
        self.grp_selected_ctx.setVisible(False)
        self.band_layout.addWidget(self.grp_selected_ctx, 0, Qt.AlignLeft)
        self.band_layout.addStretch(1)

        # Sleek Compact Summary Boxes (Bluebeam/Excel HUD style)
        sum_card = QFrame(); self._sum_card = sum_card
        sum_card.setStyleSheet("QFrame { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 5px; margin: 2px 4px; }")
        sg = QGridLayout(sum_card); sg.setContentsMargins(10, 4, 10, 4); sg.setHorizontalSpacing(14); sg.setVerticalSpacing(4)
        self._sum_vals = {}
        for idx_s, (s_key, s_lbl, s_init, s_col) in enumerate([
            ("sheets", "Sheets:", "1", "#0284c7"),
            ("members", "BOM:", "0 pcs", "#107c41"),
            ("weight", "Weight:", "0 lbs", "#0f172a"),
            ("marks", "Marks:", "0", "#b45309"),
        ]):
            r_i, c_i = divmod(idx_s, 2)
            row_w = QWidget(); rl = QHBoxLayout(row_w); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(4)
            l_cap = QLabel(s_lbl); l_cap.setStyleSheet("color: #64748b; font-size: 10.5px; font-weight: 600; border: none;")
            l_val = QLabel(s_init); l_val.setStyleSheet(f"color: {s_col}; font-size: 11px; font-weight: 800; border: none;")
            rl.addWidget(l_cap); rl.addWidget(l_val)
            sg.addWidget(row_w, r_i, c_i)
            self._sum_vals[s_key] = l_val
        self.band_layout.addWidget(sum_card, 0, Qt.AlignRight | Qt.AlignVCenter)
        outer.addWidget(self.cmd_band, 1)

        self._sum_timer = QTimer(self)
        self._sum_timer.timeout.connect(self._refresh_ribbon_summary)
        self._sum_timer.start(900)

        QTimer.singleShot(250, self._init_smart_completer)
        self.set_active_tab(0)

    def _switch_workspace(self, ws_idx):
        if hasattr(self.app, "master_tabs"):
            self.app.master_tabs.setCurrentIndex(ws_idx)
        self.set_active_tab(ws_idx)

    def set_active_tab(self, ws_idx):
        if ws_idx not in self._ws_subtab_labels:
            return
        self._active_ws = ws_idx
        for i, wb in enumerate(self._ws_btns):
            if i == ws_idx:
                wb.setStyleSheet("QPushButton { background-color: #ffffff !important; border: none !important; color: #0369a1 !important; font-size: 11px !important; font-weight: 700 !important; border-radius: 4px; padding: 0px 10px !important; }")
            else:
                wb.setStyleSheet("QPushButton { background: transparent !important; border: none !important; color: #334155 !important; font-size: 11px !important; font-weight: 600 !important; border-radius: 4px; padding: 0px 10px !important; } QPushButton:hover { background-color: #e2e8f0 !important; color: #0f172a !important; }")
        labels = self._ws_subtab_labels[ws_idx]
        for i, tb in enumerate(self._tab_btns):
            if i < len(labels):
                tb.setText(labels[i].replace("&", "&&")); tb.setVisible(True)
            else:
                tb.setVisible(False)
        self._switch_subtab(0); self.adapt_to_width(self.width())

    def _switch_subtab(self, st_idx):
        page_idx = self._page_map.get((self._active_ws, st_idx))
        if page_idx is not None:
            self._active_subtab = st_idx
            self.ctx_stack.setCurrentIndex(page_idx); self.adapt_to_width(self.width())
            for i, tb in enumerate(self._tab_btns):
                if not tb.isVisible():
                    continue
                if i == st_idx:
                    tb.setStyleSheet(
                        "QPushButton#RibbonSubTabBtn { background-color: #f3f2f1 !important; border: 1px solid #c8c6c4 !important; "
                        "border-bottom: 3px solid #0284c7 !important; color: #000000 !important; font-size: 12px !important; "
                        "font-weight: 800 !important; border-top-left-radius: 5px; border-top-right-radius: 5px; padding: 3px 14px 4px 14px !important; }"
                    )
                else:
                    tb.setStyleSheet(
                        "QPushButton#RibbonSubTabBtn { background-color: #f3f4f6 !important; border: 1px solid #cbd5e1 !important; "
                        "color: #1f2937 !important; font-size: 11.5px !important; font-weight: 600 !important; "
                        "border-top-left-radius: 5px; border-top-right-radius: 5px; padding: 3px 14px 4px 14px !important; } "
                        "QPushButton#RibbonSubTabBtn:hover { background-color: #cbd5e1 !important; color: #ffffff !important; }"
                    )

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.adapt_to_width(ev.size().width())

    def adapt_to_width(self, w_px):
        if self._collapsed or not hasattr(self, "ctx_stack"):
            return
        cur_page = self.ctx_stack.currentWidget()
        groups = getattr(cur_page, "_adaptive_groups", None)
        if not groups:
            return
        if hasattr(self, "_sum_card"):
            self._sum_card.setVisible(w_px >= 1080)
        sum_w = self._sum_card.sizeHint().width() if (hasattr(self, "_sum_card") and self._sum_card.isVisible()) else 0
        avail = max(260, w_px - sum_w - 32)
        if hasattr(self, "grp_selected_ctx") and self.grp_selected_ctx.isVisible():
            avail -= (self.grp_selected_ctx.sizeHint().width() + 10)

        for g_wrap, c_btn, _ in groups:
            g_wrap.setVisible(True)
            c_btn.setVisible(False)
        cur_page.adjustSize()

        total_w = sum(g_wrap.sizeHint().width() + 4 for g_wrap, _, _ in groups)
        for idx in range(len(groups) - 1, -1, -1):
            if total_w <= avail:
                break
            g_wrap, c_btn, _ = groups[idx]
            full_w = g_wrap.sizeHint().width()
            if full_w > 78:
                g_wrap.setVisible(False)
                c_btn.setVisible(True)
                total_w -= (full_w - 72)

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self.cmd_band.setVisible(not self._collapsed)
        self.setMinimumHeight(62 if self._collapsed else 164)
        self.setMaximumHeight(62 if self._collapsed else 164)
        self.btn_pin.setText("Expand" if self._collapsed else "Collapse")

    def _init_smart_completer(self):
        suggestions = ["DIM - Linear Dimension", "WELD - AWS Weld Symbol", "CNT - Count Marker", "TEXT - Text Note", "CALL - Callout Box", "CLD - Revision Cloud", "GRID - Column Grid Bubble", "PAN - Hand Pan", "Takeoff", "Catalog", "Structural", "Ledger", "Admin", "Trends"]
        t2 = getattr(self.app, "custom_quoting_tab", None)
        if t2 and isinstance(getattr(t2, "steel_matrix_data", None), dict):
            for items in t2.steel_matrix_data.values():
                for it in items:
                    des = str(it.get("designation", "")).strip()
                    if des: suggestions.append(des)
        dc = getattr(self.app, "data_core", None)
        if dc and isinstance(getattr(dc, "clean_database", None), dict):
            for models in dc.clean_database.values():
                for m_name in list(models.keys())[:250]: suggestions.append(m_name)
        comp = QCompleter(sorted(set(suggestions)), self.search_box)
        comp.setCaseSensitivity(Qt.CaseInsensitive); comp.setFilterMode(Qt.MatchContains)
        self.search_box.setCompleter(comp)

    def update_contextual_selection(self, markup_dict):
        if not hasattr(self, "grp_selected_ctx"):
            return
        if not markup_dict:
            self.grp_selected_ctx.setVisible(False)
            if hasattr(self, "_mini_bar") and self._mini_bar:
                self._mini_bar.hide()
            return
        mtype = str(markup_dict.get("type", "Markup")).replace("_", " ").title()
        detail = markup_dict.get("label") or markup_dict.get("text") or ""
        self.lbl_sel_type.setText(f"{mtype}: {detail[:16]}" if detail else mtype)
        self.grp_selected_ctx.setVisible(True)
        self._show_floating_mini_toolbar()

    def _show_floating_mini_toolbar(self):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        cv = getattr(getattr(pt, "vis_workspace", None), "canvas", None) if pt else None
        if not cv or not (0 <= cv.selected_idx < len(cv.markups)):
            return
        if not getattr(self, "_mini_bar", None):
            bar = QFrame(cv)
            bar.setStyleSheet(
                "QFrame { background-color: #ffffff; border: 1px solid #94a3b8; border-radius: 6px; } "
                "QPushButton { background: transparent; border: none; color: #0f172a; font-size: 11px; font-weight: 600; padding: 4px 7px; border-radius: 4px; } "
                "QPushButton:hover { background-color: #e0f2fe; color: #0369a1; }"
            )
            hl = QHBoxLayout(bar); hl.setContentsMargins(4, 3, 4, 3); hl.setSpacing(2)
            for lbl, fn in [
                ("Clone", lambda: self._canvas_call("duplicate_selected_markup")),
                ("Rotate", lambda: self._canvas_call("rotate_selected_markup")),
                ("Red", lambda: self._recolor_selected("#dc2626")),
                ("Blue", lambda: self._recolor_selected("#0284c7")),
                ("Green", lambda: self._recolor_selected("#107c41")),
                ("Delete", lambda: self._canvas_call("delete_selected_markup")),
            ]:
                b = QPushButton(lbl); b.setCursor(Qt.PointingHandCursor); b.clicked.connect(fn); hl.addWidget(b)
            bar.adjustSize()
            self._mini_bar = bar
        bb = cv._markup_bbox_px(cv.markups[cv.selected_idx])
        if not bb.isNull():
            x = max(8, min(cv.width() - self._mini_bar.width() - 8, bb.left()))
            y = max(8, bb.top() - self._mini_bar.height() - 8)
            self._mini_bar.move(x, y)
            self._mini_bar.show()
            self._mini_bar.raise_()

    def _recolor_selected(self, hex_col):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        cv = getattr(getattr(pt, "vis_workspace", None), "canvas", None) if pt else None
        if cv and 0 <= cv.selected_idx < len(cv.markups):
            cv.markups[cv.selected_idx]["color"] = QColor(hex_col)
            cv.update()
        self._show_floating_mini_toolbar()

    def _show_floating_mini_toolbar(self):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        cv = getattr(getattr(pt, "vis_workspace", None), "canvas", None) if pt else None
        if not cv or not (0 <= cv.selected_idx < len(cv.markups)):
            return
        if not getattr(self, "_mini_bar", None):
            bar = QFrame(cv)
            bar.setStyleSheet(
                "QFrame { background-color: #ffffff; border: 1px solid #94a3b8; border-radius: 6px; } "
                "QPushButton { background: transparent; border: none; color: #0f172a; font-size: 11px; font-weight: 600; padding: 4px 7px; border-radius: 4px; } "
                "QPushButton:hover { background-color: #e0f2fe; color: #0369a1; }"
            )
            hl = QHBoxLayout(bar); hl.setContentsMargins(4, 3, 4, 3); hl.setSpacing(2)
            for lbl, fn in [
                ("Clone", lambda: self._canvas_call("duplicate_selected_markup")),
                ("Rotate", lambda: self._canvas_call("rotate_selected_markup")),
                ("Red", lambda: self._recolor_selected("#dc2626")),
                ("Blue", lambda: self._recolor_selected("#0284c7")),
                ("Green", lambda: self._recolor_selected("#107c41")),
                ("Delete", lambda: self._canvas_call("delete_selected_markup")),
            ]:
                b = QPushButton(lbl); b.setCursor(Qt.PointingHandCursor); b.clicked.connect(fn); hl.addWidget(b)
            bar.adjustSize()
            self._mini_bar = bar
        bb = cv._markup_bbox_px(cv.markups[cv.selected_idx])
        if not bb.isNull():
            x = max(8, min(cv.width() - self._mini_bar.width() - 8, bb.left()))
            y = max(8, bb.top() - self._mini_bar.height() - 8)
            self._mini_bar.move(x, y)
            self._mini_bar.show()
            self._mini_bar.raise_()

    def _recolor_selected(self, hex_col):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        cv = getattr(getattr(pt, "vis_workspace", None), "canvas", None) if pt else None
        if cv and 0 <= cv.selected_idx < len(cv.markups):
            cv.markups[cv.selected_idx]["color"] = QColor(hex_col)
            cv.update()

    def mousePressEvent(self, ev):
        pw = QApplication.activePopupWidget()
        if pw is not None: pw.hide()
        if ev.button() == Qt.LeftButton and ev.position().y() <= 34:
            wh = self.window().windowHandle() if self.window() else None
            if wh is not None and wh.startSystemMove():
                ev.accept(); return
        super().mousePressEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        if ev.position().y() <= 30: self._toggle_max()
        super().mouseDoubleClickEvent(ev)

    def _toggle_max(self):
        if self.app.isMaximized():
            self.app.showNormal()
            if hasattr(self, "btn_max"): self.btn_max.setIcon(_win_caption_icon("max", "#1f2937"))
        else:
            self.app.showMaximized()
            if hasattr(self, "btn_max"): self.btn_max.setIcon(_win_caption_icon("restore", "#1f2937"))

    def _on_scale_changed(self, idx):
        self._set_vw_idx("scale_combo", idx); self._update_telemetry()

    def _update_telemetry(self, mode_label=None):
        if not hasattr(self, "lbl_live_telemetry"): return
        if mode_label: self._cur_mode_label = mode_label
        m_txt = getattr(self, "_cur_mode_label", "Hand Pan")
        sc_txt = self.ribbon_scale_cb.currentText() if hasattr(self, "ribbon_scale_cb") else "1/4\" = 1'-0\""
        self.lbl_live_telemetry.setText(f"Armed: {m_txt}  |  Scale: {sc_txt}")

    def _on_ribbon_sheet_changed(self, idx):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        cb = getattr(pt, "sheet_combo", None) if pt else None
        if cb and 0 <= idx < cb.count() and cb.currentIndex() != idx: cb.setCurrentIndex(idx)

    def sync_sheet_list(self, items_with_data, cur_idx=0):
        if not hasattr(self, "ribbon_sheet_cb"): return
        self.ribbon_sheet_cb.blockSignals(True); self.ribbon_sheet_cb.clear()
        for txt, dat in items_with_data: self.ribbon_sheet_cb.addItem(txt, dat)
        if 0 <= cur_idx < self.ribbon_sheet_cb.count(): self.ribbon_sheet_cb.setCurrentIndex(cur_idx)
        self.ribbon_sheet_cb.blockSignals(False)

    def _step_sheet(self, delta):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        cb = getattr(pt, "sheet_combo", None) if pt else None
        if cb and cb.count() > 0:
            nxt = max(0, min(cb.count() - 1, cb.currentIndex() + delta))
            cb.setCurrentIndex(nxt)
            if hasattr(self, "ribbon_sheet_cb"):
                self.ribbon_sheet_cb.blockSignals(True); self.ribbon_sheet_cb.setCurrentIndex(nxt); self.ribbon_sheet_cb.blockSignals(False)

    def _toggle_ortho_lock(self, checked):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        cv = getattr(getattr(pt, "vis_workspace", None), "canvas", None) if pt else None
        if cv: cv.ortho_lock = bool(checked)
        bg = "#dbeafe" if checked else "#ffffff"; brd = "#0284c7" if checked else "#cbd5e1"
        self.btn_ortho_lock.setStyleSheet(f"QPushButton {{ background-color: {bg} !important; border: 1px solid {brd} !important; color: #0f172a !important; font-size: 10.5px !important; font-weight: {'700' if checked else '500'} !important; border-radius: 3px; padding: 0px 5px; }}")

    def _toggle_endpoint_snap(self, checked):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        cv = getattr(getattr(pt, "vis_workspace", None), "canvas", None) if pt else None
        if cv: cv.endpoint_snap = bool(checked)
        bg = "#dbeafe" if checked else "#ffffff"; brd = "#0284c7" if checked else "#cbd5e1"
        self.btn_ep_snap.setStyleSheet(f"QPushButton {{ background-color: {bg} !important; border: 1px solid {brd} !important; color: #0f172a !important; font-size: 10.5px !important; font-weight: {'700' if checked else '500'} !important; border-radius: 3px; padding: 0px 5px; }}")

    def _jump_shape_and_profile(self, shape_key, designation=""):
        self._switch_workspace(2)
        t2 = getattr(self.app, "custom_quoting_tab", None)
        if not t2: return
        if hasattr(t2, "combo_picker"):
            idx = t2.combo_picker.findText(shape_key, Qt.MatchFixedString)
            if idx >= 0: t2.combo_picker.setCurrentIndex(idx)
        if designation and hasattr(t2, "active_member_card"):
            cb = t2.active_member_card.combo_model
            m_idx = cb.findText(designation, Qt.MatchContains)
            if m_idx >= 0: cb.setCurrentIndex(m_idx)

    def _on_quick_search(self):
        raw_q = self.search_box.text().strip()
        if not raw_q: return
        q = raw_q.split(" - ")[0].strip(); ql = q.lower()
        cad_aliases = {"dim": "measure", "measure": "measure", "m": "measure", "weld": "weld", "w": "weld", "cnt": "count", "count": "count", "c": "count", "txt": "text", "text": "text", "t": "text", "call": "callout", "callout": "callout", "q": "callout", "cld": "cloud", "cloud": "cloud", "r": "cloud", "grid": "grid_bubble", "g": "grid_bubble", "pan": "pan", "esc": "pan"}
        if ql in cad_aliases:
            self._switch_workspace(0); self._vis_mode(cad_aliases[ql]); self.search_box.clear(); return
        if any(op in q for op in ("+", "-", "*", "/")) and all(ch in "0123456789.+-*/() " for ch in q):
            try:
                res = eval(q, {"__builtins__": None}, {})
                QMessageBox.information(self.app, "Quick Calculation", f"{q}  =  {res:,.4f}".rstrip("0").rstrip(".")); return
            except Exception: pass
        nav = {"takeoff": 0, "planset": 0, "pdf": 0, "catalog": 1, "hangers": 1, "structural": 2, "custom": 2, "beams": 2, "ledger": 3, "quotes": 3, "admin": 4, "rates": 4}
        if ql in nav: self._switch_workspace(nav[ql]); return
        if ql in ("trends", "analytics"): self._act_analytics(); return
        t2 = getattr(self.app, "custom_quoting_tab", None)
        if t2 and isinstance(getattr(t2, "steel_matrix_data", None), dict):
            qu = q.upper().replace(" ", "")
            for sk, items in t2.steel_matrix_data.items():
                for it in items:
                    des = str(it.get("designation", "")).upper().replace(" ", "")
                    if qu == des or qu in des:
                        self._jump_shape_and_profile(sk, it.get("designation", "")); self.search_box.clear(); return
        if hasattr(self.app, "smart_lookup_input"):
            self._switch_workspace(1); self.app.smart_lookup_input.setText(q)
            if hasattr(self.app, "model_box") and self.app.model_box.count() > 1: self.app.model_box.setCurrentIndex(1)

    def _app_call(self, fn_name):
        fn = getattr(self.app, fn_name, None)
        if callable(fn): fn()

    def _is_admin_unlocked(self):
        t = getattr(self.app, "custom_admin_tab", None)
        if t is None or t.stack.currentIndex() == 0:
            QMessageBox.warning(self.app, "Admin Locked", "Please unlock the Unified Admin Center first before accessing admin tools."); return False
        return True

    def _vis_mode(self, mode_name):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        vw = getattr(pt, "vis_workspace", None) if pt is not None else None
        cur_m = getattr(getattr(vw, "canvas", None), "mode", "") if vw else ""
        if mode_name == "edit_pdf" and cur_m == "edit_pdf": mode_name = "select"
        if pt is not None:
            if hasattr(pt, "btn_tab_vis"): pt.btn_tab_vis.click()
            if vw and hasattr(vw, "set_mode"): vw.set_mode(mode_name)
        self._highlight_active_mode(mode_name); self._update_telemetry(mode_name.replace("_", " ").title())

    def _highlight_active_mode(self, mode_name):
        for m_key, widgets in self._mode_widgets.items():
            is_act = (m_key == mode_name)
            for w in widgets:
                if hasattr(w, "setToolButtonStyle"):
                    bg = "#e0f2fe" if is_act else "transparent"; brd = "#0284c7" if is_act else "transparent"
                    w.setStyleSheet(f"QToolButton {{ background-color: {bg}; border: 1px solid {brd}; border-radius: 4px; color: #0f172a; font-size: 11px; font-weight: {'700' if is_act else '500'}; padding: 2px 4px; }} QToolButton:hover {{ background-color: #e2e8f0; border: 1px solid #94a3b8; }}")

    def _vis_call(self, fn_name):
        pt = getattr(self.app, "planset_takeoff_tab", None); vw = getattr(pt, "vis_workspace", None) if pt else None
        if vw and hasattr(vw, fn_name): getattr(vw, fn_name)()

    def _canvas_call(self, fn_name):
        pt = getattr(self.app, "planset_takeoff_tab", None); vw = getattr(pt, "vis_workspace", None) if pt else None
        cv = getattr(vw, "canvas", None) if vw else None
        if cv and hasattr(cv, fn_name): getattr(cv, fn_name)()

    def _set_vw_idx(self, attr, idx):
        pt = getattr(self.app, "planset_takeoff_tab", None); vw = getattr(pt, "vis_workspace", None) if pt else None
        if vw and hasattr(vw, attr): getattr(vw, attr).setCurrentIndex(idx)

    def _set_vw_font(self, qfont):
        pt = getattr(self.app, "planset_takeoff_tab", None); vw = getattr(pt, "vis_workspace", None) if pt else None
        if vw and hasattr(vw, "font_combo"): vw.font_combo.setCurrentFont(qfont)

    def _stamp_review_note(self):
        pt = getattr(self.app, "planset_takeoff_tab", None); vw = getattr(pt, "vis_workspace", None) if pt else None; cv = getattr(vw, "canvas", None) if vw else None
        if not cv: return
        today = datetime.date.today().strftime("%m/%d/%Y")
        txt, ok = QInputDialog.getItem(self.app, "Stamp Blueprint Note", "Stamp text:", [f"VERIFIED FOR TAKEOFF - {today}", f"HOLD FOR RFI - {today}", f"FIELD VERIFY - {today}", f"APPROVED FOR FAB - {today}"], 0, True)
        if ok and txt.strip():
            cv.markups.append({"type": "text", "x": 60.0, "y": 60.0, "text": txt.strip(), "color": QColor(cv.active_color), "font_family": cv.font_family, "font_size": cv.font_size, "bold": True, "italic": False})
            cv.selected_idx = len(cv.markups) - 1; self._vis_mode("select"); self.update_contextual_selection(cv.markups[cv.selected_idx]); cv.update()

    def _refresh_biu_styles(self):
        pt = getattr(self.app, "planset_takeoff_tab", None); vw = getattr(pt, "vis_workspace", None) if pt else None; cv = getattr(vw, "canvas", None) if vw else None
        states = {"B": bool(getattr(cv, "font_bold", True)), "I": bool(getattr(cv, "font_italic", False)), "U": bool(getattr(cv, "font_underline", False))}
        for k, btn in getattr(self, "_biu_btns", {}).items():
            on = states.get(k, False); ex = btn.property("extra_css") or ""; bg = "#dbeafe" if on else "transparent"; brd = "#0284c7" if on else "transparent"
            btn.setStyleSheet(f"QPushButton {{ background-color: {bg} !important; border: 1px solid {brd} !important; color: #0f172a !important; font-size: 11px !important; {ex} border-radius: 3px; padding: 0px !important; }}")

    def _toggle_bold(self):
        pt = getattr(self.app, "planset_takeoff_tab", None); cv = getattr(getattr(pt, "vis_workspace", None), "canvas", None) if pt else None
        if cv:
            cv.font_bold = not getattr(cv, "font_bold", True)
            if 0 <= cv.selected_idx < len(cv.markups) and cv.markups[cv.selected_idx].get("type") == "text": cv.markups[cv.selected_idx]["bold"] = cv.font_bold
            if cv._inline_editor.isVisible(): cv._apply_inline_style()
            cv.update()
        self._refresh_biu_styles()

    def _toggle_italic(self):
        pt = getattr(self.app, "planset_takeoff_tab", None); cv = getattr(getattr(pt, "vis_workspace", None), "canvas", None) if pt else None
        if cv:
            cv.font_italic = not getattr(cv, "font_italic", False)
            if 0 <= cv.selected_idx < len(cv.markups) and cv.markups[cv.selected_idx].get("type") == "text": cv.markups[cv.selected_idx]["italic"] = cv.font_italic
            if cv._inline_editor.isVisible(): cv._apply_inline_style()
            cv.update()
        self._refresh_biu_styles()

    def _toggle_underline(self):
        pt = getattr(self.app, "planset_takeoff_tab", None); cv = getattr(getattr(pt, "vis_workspace", None), "canvas", None) if pt else None
        if cv:
            cv.font_underline = not getattr(cv, "font_underline", False)
            if cv._inline_editor.isVisible(): cv._apply_inline_style()
            cv.update()
        self._refresh_biu_styles()

    def _set_vw_prop(self, widget_attr, val):
        pt = getattr(self.app, "planset_takeoff_tab", None); vw = getattr(pt, "vis_workspace", None) if pt else None
        if vw and hasattr(vw, widget_attr): getattr(vw, widget_attr).setValue(val)

    def _arm_pen(self, hex_c, mode_name="line"):
        self._set_vw_color(hex_c); self._vis_mode(mode_name)

    def _refresh_swatch_styles(self, active_hex):
        self._active_color_hex = str(active_hex).lower()
        for hx, btn in self._swatch_btns.items():
            is_sel = (hx.lower() == self._active_color_hex)
            brd_col = "#0284c7" if is_sel else ("#64748b" if hx == "#ffffff" else "#94a3b8")
            btn.setStyleSheet(f"QPushButton {{ background-color: {hx} !important; border: {'2.5px' if is_sel else '1.5px'} solid {brd_col} !important; border-radius: 3px; padding: 0px !important; }}")

    def _set_vw_color(self, hex_c):
        qc = QColor(hex_c); self._refresh_swatch_styles(qc.name())
        pt = getattr(self.app, "planset_takeoff_tab", None); vw = getattr(pt, "vis_workspace", None) if pt else None
        if vw:
            if hasattr(vw, "_set_canvas_pen"): vw._set_canvas_pen(qc)
            if hasattr(vw, "canvas"): vw.canvas.fill_color = QColor(qc)

    def _pick_ribbon_color_before_use(self):
        pt = getattr(self.app, "planset_takeoff_tab", None); vw = getattr(pt, "vis_workspace", None) if pt else None
        cur = vw.canvas.active_color if (vw and hasattr(vw, "canvas")) else QColor("#111827")
        chosen = QColorDialog.getColor(cur, self.app, "Pick Color Before Using Tool")
        if chosen.isValid(): self._set_vw_color(chosen.name())

    def _toggle_markup_layer(self, layer_key):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        cv = getattr(getattr(pt, "vis_workspace", None), "canvas", None) if pt else None
        if not cv: return
        if layer_key == "all": cv.hidden_layers.clear()
        elif layer_key in cv.hidden_layers: cv.hidden_layers.remove(layer_key)
        else: cv.hidden_layers.add(layer_key)
        cv.update()

    def _vis_click(self, attr):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        if pt is not None:
            if hasattr(pt, "btn_tab_vis"): pt.btn_tab_vis.click()
            vw = getattr(pt, "vis_workspace", None)
            if vw is not None and hasattr(vw, attr): getattr(vw, attr).click()

    def _tk_click(self, a):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        if pt is not None and hasattr(pt, a): getattr(pt, a).click()

    def _t2(self, fn):
        t = getattr(self.app, "custom_quoting_tab", None)
        if t is not None: fn(t)

    def _t3(self, fn):
        t = getattr(self.app, "custom_ledger_tab", None)
        if t is not None: fn(t)

    def _t4(self, fn):
        if not self._is_admin_unlocked(): return
        t = getattr(self.app, "custom_admin_tab", None)
        if t is not None: fn(t)

    def _act_reset_sheet(self):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        if pt and hasattr(pt, "reset_to_blank_sheet"): pt.reset_to_blank_sheet()

    def _act_load_pdf(self):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        if pt and hasattr(pt, "load_new_pdf_planset"): pt.load_new_pdf_planset()

    def _act_scan_pdf(self):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        if pt and hasattr(pt, "btn_scan_pg"): pt.btn_scan_pg.click()

    def _act_scan_planset(self, use_ocr=False):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        if pt and hasattr(pt, "scan_whole_planset"): pt.scan_whole_planset(use_ocr=use_ocr, prompt_if_empty=False)

    def _act_send_bom(self):
        pt = getattr(self.app, "planset_takeoff_tab", None)
        if pt and hasattr(pt, "_accept_checked"): pt._accept_checked()

    def _open_in_adobe_acrobat(self):
        pt = getattr(self.app, "planset_takeoff_tab", None); pdf_p = getattr(pt, "pdf_path", "") if pt else ""
        if not pdf_p or not os.path.exists(pdf_p):
            QMessageBox.information(self.app, "No PDF Loaded", "Load a PDF planset first to open it in Adobe Acrobat."); return
        acro = r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe"
        subprocess.Popen([acro, pdf_p]) if os.path.exists(acro) else os.startfile(pdf_p)

    def _open_ledger_in_excel(self):
        quotes = getattr(self.app, "custom_ledger_pool", [])
        if not quotes:
            QMessageBox.information(self.app, "Empty Ledger", "No quotes logged in the Project Ledger yet."); return
        tmp_csv = os.path.join(tempfile.gettempdir(), "Bowman_Morton_Project_Ledger.csv")
        with open(tmp_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["Quote ID", "Date", "Customer", "Project", "Weight (lbs)", "Total Quoted ($)"])
            for q in quotes: w.writerow([q.get("quote_num", q.get("id", "")), q.get("timestamp", ""), q.get("customer", ""), q.get("project", ""), q.get("weight", 0), q.get("cost", 0)])
        xl = r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE"
        subprocess.Popen([xl, tmp_csv]) if os.path.exists(xl) else os.startfile(tmp_csv)

    def _act_analytics(self):
        if hasattr(self.app, "open_ledger_analytics_dashboard"): self.app.open_ledger_analytics_dashboard()

    def _open_trig_studio(self, tab_idx=0):
        import engineering_math_dialog as emd
        def _stamp_cb(summary_txt, shape_data=None):
            pt = getattr(self.app, "planset_takeoff_tab", None)
            cv = getattr(getattr(pt, "vis_workspace", None), "canvas", None) if pt else None
            if cv:
                ppf = max(1.0, float(getattr(cv, "pts_per_ft", 18.0)))
                if isinstance(shape_data, dict):
                    kind = shape_data.get("kind", "right")
                    if kind == "right":
                        w_pts = max(4.0, float(shape_data.get("run", 12.0)) * ppf)
                        h_pts = max(4.0, float(shape_data.get("rise", 5.0)) * ppf)
                    elif kind == "oblique":
                        span_ft = max(float(shape_data.get("a", 10.0)), float(shape_data.get("b", 14.0)))
                        w_pts = max(4.0, span_ft * ppf); h_pts = w_pts * 0.72
                    else:
                        dia_ft = float(shape_data.get("dia_in", 24.0)) / 12.0
                        w_pts = max(4.0, dia_ft * ppf); h_pts = w_pts
                    cv._pending_cad_shape = {"type": "cad_shape", "x": 0.0, "y": 0.0, "w_pts": w_pts, "h_pts": h_pts, "shape": dict(shape_data), "label": summary_txt, "color": QColor(cv.active_color), "line_width": float(cv.active_line_width)}
                else:
                    cv._pending_cad_shape = {"type": "text", "x": 0.0, "y": 0.0, "text": summary_txt, "color": QColor(cv.active_color), "font_family": cv.font_family, "font_size": cv.font_size, "bold": True, "italic": False}
                cv.setFocus()
                cv.update()
        dlg = emd.EngineeringTrigGeometryDialog(on_stamp_note=_stamp_cb, parent=self.app)
        dlg.tabs.setCurrentIndex(tab_idx); dlg.exec()

    def _act_calc(self): _QuickEstimatorCalcDialog(self.app).exec()
    def _act_dev(self):
        if hasattr(self.app, "open_developer_code_studio"): self.app.open_developer_code_studio()
    def _act_dl_tpl(self):
        if self._is_admin_unlocked():
            cad = getattr(self.app, "catalog_admin_embedded", None)
            if cad: cad.admin_download_card_excel_template()
    def _act_imp_xl(self):
        if self._is_admin_unlocked():
            cad = getattr(self.app, "catalog_admin_embedded", None)
            if cad: cad.admin_bulk_import_excel_sheet()

    def _refresh_ribbon_summary(self):
        if not hasattr(self, "_sum_vals"):
            return
        pt = getattr(self.app, "planset_takeoff_tab", None)
        vw = getattr(pt, "vis_workspace", None) if pt else None
        cv = getattr(vw, "canvas", None) if vw else None
        doc = getattr(pt, "doc", None) or getattr(vw, "doc", None)
        n_sheets = len(doc) if doc is not None else 1
        bom = (getattr(pt, "bom_items", None) or getattr(pt, "staged_bom_items", None) or getattr(vw, "bom_items", None) or []) if pt else []
        bom_pcs = sum(int(x.get("qty", 1) or 1) for x in bom) if bom else 0
        bom_lbs = sum(float(x.get("total_weight", x.get("weight", 0.0)) or 0.0) for x in bom) if bom else 0.0
        if bom_pcs == 0 and pt and hasattr(pt, "tree"):
            for i in range(pt.tree.topLevelItemCount()):
                p_it = pt.tree.topLevelItem(i)
                for j in range(p_it.childCount()):
                    ch = p_it.child(j)
                    try:
                        bom_pcs += int(float(ch.text(2) or 1))
                        bom_lbs += float(str(ch.text(5)).replace(",", "") or 0.0)
                    except Exception:
                        pass
        n_marks = len(getattr(cv, "markups", []) or []) if cv else 0
        if "sheets" in self._sum_vals:
            self._sum_vals["sheets"].setText(str(max(1, n_sheets)))
        if "members" in self._sum_vals:
            self._sum_vals["members"].setText(f"{bom_pcs:,} pcs")
        if "weight" in self._sum_vals:
            self._sum_vals["weight"].setText(f"{bom_lbs:,.0f} lbs")
        if "marks" in self._sum_vals:
            self._sum_vals["marks"].setText(str(n_marks))
