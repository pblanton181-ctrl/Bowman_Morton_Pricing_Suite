import os
import sys
import json
import textwrap
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QToolButton, QMenu, QComboBox, QFontComboBox, QSpinBox, QDoubleSpinBox
)
from ui.icon_loader import get_icon

def load_ribbon_schema():
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg_path = os.path.join(base, "config", "ribbon_config.json")
    with open(cfg_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

class RibbonFactory:
    def __init__(self, ribbon_bar):
        self.rb = ribbon_bar

    def format_tip(self, title: str, body: str = "") -> str:
        clean_title = title.replace("\n", " ")
        if not body:
            return clean_title
        return f"{clean_title}\n{textwrap.fill(body, width=38)}"

    def dispatch(self, action_str: str):
        if not action_str:
            return
        if ":" in action_str:
            prefix, target = action_str.split(":", 1)
            if prefix == "mode":
                self.rb._vis_mode(target)
            elif prefix == "tool":
                self.rb._vis_mode("box" if target == "ocr_box" else target)
            elif prefix == "canvas":
                self.rb._canvas_call(target)
            elif prefix == "vis":
                self.rb._vis_call(target)
            elif prefix == "vis_btn":
                self.rb._vis_click(target)
            elif prefix == "tk":
                self.rb._tk_click(target)
            elif prefix == "layer":
                self.rb._toggle_markup_layer(target)
            elif prefix == "trig":
                self.rb._open_trig_studio(int(target))
            elif prefix == "app":
                self.rb._app_call(target)
            elif prefix == "tier":
                if hasattr(self.rb.app, "team_box"):
                    self.rb.app.team_box.setCurrentIndex(int(target))
            elif prefix == "t2":
                self.rb._t2(lambda t: getattr(t, target)())
            elif prefix == "t2_card":
                self.rb._t2(lambda t: getattr(t.active_member_card, target)())
            elif prefix == "shape":
                self.rb._jump_shape_and_profile(target, "")
            elif prefix == "finish":
                attr_map = {"primer": "chk_primer", "pc": "chk_powder", "hdg": "chk_galv"}
                chk_attr = attr_map.get(target)
                if chk_attr:
                    self.rb._t2(lambda t: getattr(t.active_member_card, chk_attr).toggle())
            elif prefix == "t3":
                self.rb._t3(lambda t: getattr(t, target)())
            elif prefix == "admin_view":
                self.rb._t4(lambda t: t.switch_admin_subview(int(target)))
            return

        if action_str == "_act_scan_planset_fast":
            self.rb._act_scan_planset_fast()
        elif action_str == "_act_scan_planset_ocr":
            self.rb._act_scan_planset_ocr()
        elif action_str == "_act_scan_planset_hybrid":
            self.rb._act_scan_planset_hybrid()
        elif action_str == "pen_yellow_hl":
            self.rb._arm_pen("#eab308", "free_highlight")
        elif action_str == "t3_focus_search":
            self.rb._t3(lambda t: t.search_input.setFocus())
        elif hasattr(self.rb, action_str):
            getattr(self.rb, action_str)()

    def make_group(self, title: str):
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent; border: none;")
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)

        box = QFrame()
        box.setObjectName("OfficeGroup")
        box.setStyleSheet("QFrame#OfficeGroup { background: transparent; border: none; }")
        vl = QVBoxLayout(box)
        vl.setContentsMargins(6, 2, 6, 2)
        vl.setSpacing(2)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        vl.addLayout(row, 1)

        lbl = QLabel(title)
        lbl.setObjectName("OfficeGroupCap")
        lbl.setTextFormat(Qt.PlainText); lbl.setAlignment(Qt.AlignCenter); lbl.setFixedHeight(14)
        vl.addWidget(lbl)
        wl.addWidget(box)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background-color: #c8c6c4; border: none; margin-top: 5px; margin-bottom: 5px;")
        wl.addWidget(sep)
        return wrap, row

    def build_tile(self, spec: dict) -> QToolButton:
        b = QToolButton()
        b.setText(spec.get("text", ""))
        b.setIcon(get_icon(spec.get("icon", ""), size=24))
        b.setIconSize(QSize(18, 18))
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedSize(56, 54)
        b.setStyleSheet(
            "QToolButton { background: transparent; border: 1px solid transparent; border-radius: 4px; "
            "color: #111827; font-size: 10px; font-weight: 500; padding: 3px 2px 2px 2px; } "
            "QToolButton:hover { background-color: #e2e8f0; border: 1px solid #cbd5e1; }"
        )
        b.setToolTip(self.format_tip(spec.get("text", ""), spec.get("tip", "")))

        t_type = spec.get("type", "tile")
        if t_type == "mode_tile":
            mode_key = spec.get("mode", "pan")
            b.clicked.connect(lambda _=False, mk=mode_key: self.rb._vis_mode(mk))
            self.rb._mode_widgets.setdefault(mode_key, []).append(b)
        elif t_type == "menu_tile":
            b.setPopupMode(QToolButton.InstantPopup)
            b.setStyleSheet(b.styleSheet() + " QToolButton::menu-indicator { image: none; }")
            menu = QMenu(b)
            menu.setStyleSheet(
                "QMenu { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; padding: 4px; font-size: 11.5px; } "
                "QMenu::item { padding: 5px 14px 5px 8px; border-radius: 3px; } "
                "QMenu::item:selected { background-color: #e0f2fe; color: #0369a1; }"
            )
            for entry in spec.get("menu", []):
                act = menu.addAction(get_icon(entry.get("icon", ""), size=18), entry.get("text", ""))
                act.triggered.connect(lambda _=False, a=entry.get("action", ""): self.dispatch(a))
            b.setMenu(menu)
        else:
            act_str = spec.get("action", "")
            b.clicked.connect(lambda _=False, a=act_str: self.dispatch(a))
        return b

    def build_stack(self, items: list) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setContentsMargins(2, 1, 2, 1)
        col.setSpacing(1)
        for item in items:
            b = QPushButton(" " + item.get("text", ""))
            b.setIcon(get_icon(item.get("icon", ""), color_hex="#1e293b", size=18))
            b.setIconSize(QSize(18, 18))
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(18)
            b.setStyleSheet(
                "QPushButton { background: transparent !important; border: 1px solid transparent !important; "
                "color: #111827 !important; font-size: 11px !important; font-weight: 500 !important; "
                "border-radius: 3px; padding: 1px 8px; text-align: left; } "
                "QPushButton:hover { background-color: #e2e8f0 !important; border: 1px solid #cbd5e1 !important; }"
            )
            if item.get("tip"):
                b.setToolTip(self.format_tip(item.get("text", ""), item["tip"]))
            act_str = item.get("action", "")
            b.clicked.connect(lambda _=False, a=act_str: self.dispatch(a))
            col.addWidget(b)
        return col

    def build_subtab_page(self, subtab_spec: dict) -> QWidget:
        w = QWidget()
        hl = QHBoxLayout(w)
        hl.setContentsMargins(2, 1, 2, 1)
        hl.setSpacing(4)
        w._adaptive_groups = []
        for grp in subtab_spec.get("groups", []):
            title = grp.get("title", "")
            g_wrap, g_row = self.make_group(title)
            custom_key = grp.get("custom_widget")
            first_icon = "layers"
            if custom_key == "font_appearance_bar":
                self._inject_font_bar(g_row)
                first_icon = "type"
            elif custom_key == "scale_snap_bar":
                self._inject_scale_bar(g_row)
                first_icon = "ruler"
            elif custom_key == "sheet_nav_bar":
                self._inject_sheet_bar(g_row)
                first_icon = "file-image"
            else:
                for it in grp.get("items", []):
                    if it.get("type") == "stack":
                        s_items = it.get("items", [])
                        if s_items:
                            first_icon = s_items[0].get("icon", first_icon)
                        g_row.addLayout(self.build_stack(s_items))
                    else:
                        first_icon = it.get("icon", first_icon)
                        g_row.addWidget(self.build_tile(it))

            # Build collapsed Office-style dropdown button for narrow window widths
            c_btn = QToolButton()
            c_btn.setText(title.replace("&", "&&"))
            c_btn.setIcon(get_icon(first_icon, size=18))
            c_btn.setIconSize(QSize(18, 18))
            c_btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            c_btn.setPopupMode(QToolButton.InstantPopup)
            c_btn.setFixedSize(68, 62)
            c_btn.setStyleSheet(
                "QToolButton { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; "
                "color: #111827; font-size: 10px; font-weight: 600; padding: 3px 2px; } "
                "QToolButton:hover { background-color: #e0f2fe; border-color: #0284c7; } "
                "QToolButton::menu-indicator { width: 10px; subcontrol-position: bottom center; }"
            )
            c_menu = QMenu(c_btn)
            c_menu.setStyleSheet(
                "QMenu { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; padding: 4px; font-size: 11.5px; } "
                "QMenu::item { padding: 5px 14px 5px 8px; border-radius: 3px; color: #0f172a; } "
                "QMenu::item:selected { background-color: #e0f2fe; color: #0369a1; }"
            )
            if custom_key == "scale_snap_bar":
                act_o = c_menu.addAction(get_icon("ruler", size=16), "Toggle Ortho 90 Lock")
                act_o.triggered.connect(lambda: self.host.btn_ortho_lock.click() if hasattr(self.host, "btn_ortho_lock") else None)
                act_s = c_menu.addAction(get_icon("circle-dot", size=16), "Toggle Endpoint Snap")
                act_s.triggered.connect(lambda: self.host.btn_ep_snap.click() if hasattr(self.host, "btn_ep_snap") else None)
                c_menu.addSeparator()
                for sc_idx, sc_lbl in [(0, 'Scale: 1/8" = 1\'-0"'), (1, 'Scale: 1/4" = 1\'-0"'), (2, 'Scale: 3/8" = 1\'-0"'), (3, 'Scale: 1/2" = 1\'-0"')]:
                    a_sc = c_menu.addAction(sc_lbl)
                    a_sc.triggered.connect(lambda _=False, idx=sc_idx: self.host.ribbon_scale_cb.setCurrentIndex(idx) if hasattr(self.host, "ribbon_scale_cb") else None)
            elif custom_key == "font_appearance_bar":
                for col_lbl, col_hx in [("Red Pen (#dc2626)", "#dc2626"), ("Blue Pen (#0284c7)", "#0284c7"), ("Green Pen (#107c41)", "#107c41"), ("Black Pen (#111827)", "#111827")]:
                    a_c = c_menu.addAction(get_icon("paintbrush", size=16), col_lbl)
                    a_c.triggered.connect(lambda _=False, hx=col_hx: self.host._set_vw_color(hx))
            elif custom_key == "sheet_nav_bar":
                a_prev = c_menu.addAction("Previous Sheet")
                a_prev.triggered.connect(lambda: self.host._step_sheet(-1))
                a_next = c_menu.addAction("Next Sheet")
                a_next.triggered.connect(lambda: self.host._step_sheet(1))
            else:
                for it in grp.get("items", []):
                    if it.get("type") == "stack":
                        for sub in it.get("items", []):
                            act = c_menu.addAction(get_icon(sub.get("icon", ""), size=16), sub.get("text", "").replace("&", "&&"))
                            act.triggered.connect(lambda _=False, a=sub.get("action", ""): self.dispatch(a))
                    else:
                        act = c_menu.addAction(get_icon(it.get("icon", ""), size=16), it.get("text", "").replace("\n", " ").replace("&", "&&"))
                        act.triggered.connect(lambda _=False, a=it.get("action", ""): self.dispatch(a))
            c_btn.setMenu(c_menu)
            c_btn.setVisible(False)

            hl.addWidget(g_wrap)
            hl.addWidget(c_btn)
            w._adaptive_groups.append((g_wrap, c_btn, g_wrap.sizeHint().width()))
        return w

    def _inject_font_bar(self, row):
        fc = QVBoxLayout()
        fc.setContentsMargins(2, 2, 2, 2)
        fc.setSpacing(4)
        ft = QHBoxLayout()
        ft.setContentsMargins(0, 0, 0, 0)
        ft.setSpacing(4)

        self.rb.rib_font_cb = QFontComboBox()
        self.rb.rib_font_cb.setFontFilters(QFontComboBox.ScalableFonts)
        self.rb.rib_font_cb.setCurrentFont(QFont("Arial"))
        self.rb.rib_font_cb.setFixedSize(135, 25)
        self.rb.rib_font_cb.setStyleSheet("QFontComboBox { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 1px 6px; font-size: 11.5px; }")
        self.rb.rib_font_cb.currentFontChanged.connect(self.rb._set_vw_font)
        ft.addWidget(self.rb.rib_font_cb)

        self.rb.rib_font_sz = QSpinBox()
        self.rb.rib_font_sz.setRange(8, 72)
        self.rb.rib_font_sz.setValue(18)
        self.rb.rib_font_sz.setSuffix(" pt")
        self.rb.rib_font_sz.setFixedSize(74, 24)
        self.rb.rib_font_sz.setStyleSheet("QSpinBox { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 1px 4px; font-size: 11.5px; }")
        self.rb.rib_font_sz.valueChanged.connect(lambda v: self.rb._set_vw_prop("font_size_spin", v))
        ft.addWidget(self.rb.rib_font_sz)

        self.rb.rib_line_w = QDoubleSpinBox()
        self.rb.rib_line_w.setRange(0.5, 12.0)
        self.rb.rib_line_w.setSingleStep(0.5)
        self.rb.rib_line_w.setValue(2.0)
        self.rb.rib_line_w.setSuffix(" px")
        self.rb.rib_line_w.setFixedSize(74, 24)
        self.rb.rib_line_w.setStyleSheet("QDoubleSpinBox { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 1px 4px; font-size: 11.5px; }")
        self.rb.rib_line_w.valueChanged.connect(lambda v: self.rb._set_vw_prop("line_width_spin", v))
        ft.addWidget(self.rb.rib_line_w)
        fc.addLayout(ft)

        fb = QHBoxLayout()
        fb.setContentsMargins(0, 0, 0, 0)
        fb.setSpacing(4)
        self.rb._biu_btns = {}
        for lbl_bi, slot_bi, extra_css in [("B", self.rb._toggle_bold, "font-weight: 700;"), ("I", self.rb._toggle_italic, "font-style: italic;"), ("U", self.rb._toggle_underline, "text-decoration: underline;")]:
            b_bi = QPushButton(lbl_bi)
            b_bi.setFixedSize(22, 22)
            b_bi.setCursor(Qt.PointingHandCursor)
            b_bi.setProperty("extra_css", extra_css)
            b_bi.clicked.connect(slot_bi)
            fb.addWidget(b_bi)
            self.rb._biu_btns[lbl_bi] = b_bi
        self.rb._refresh_biu_styles()

        self.rb._swatch_btns.clear()
        for hx, s_tip in [("#111827", "Black"), ("#dc2626", "Red"), ("#0284c7", "Blue"), ("#059669", "Green"), ("#ea580c", "Orange"), ("#7c3aed", "Purple"), ("#eab308", "Yellow"), ("#ffffff", "White")]:
            sw = QPushButton("")
            sw.setFixedSize(17, 17)
            sw.setCursor(Qt.PointingHandCursor)
            sw.setToolTip(s_tip)
            sw.clicked.connect(lambda _=False, c=hx: self.rb._set_vw_color(c))
            fb.addWidget(sw)
            self.rb._swatch_btns[hx] = sw
        self.rb._refresh_swatch_styles("#111827")

        b_wheel = QPushButton("+")
        b_wheel.setFixedSize(20, 20)
        b_wheel.setCursor(Qt.PointingHandCursor)
        b_wheel.setToolTip("Custom Color")
        b_wheel.setStyleSheet("QPushButton { background-color: #ffffff !important; border: 1px solid #94a3b8 !important; color: #0f172a !important; font-size: 11px !important; font-weight: 700 !important; border-radius: 3px; padding: 0px !important; }")
        b_wheel.clicked.connect(self.rb._pick_ribbon_color_before_use)
        fb.addWidget(b_wheel)
        fc.addLayout(fb)
        row.addLayout(fc)

    def _inject_scale_bar(self, row):
        sc_col = QVBoxLayout()
        sc_col.setContentsMargins(2, 2, 2, 2)
        sc_col.setSpacing(5)
        self.rb.ribbon_scale_cb = QComboBox()
        self.rb.ribbon_scale_cb.setFixedSize(145, 24)
        self.rb.ribbon_scale_cb.setStyleSheet("QComboBox { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 1px 6px; font-size: 11.5px; }")
        for lbl_s, pts_s in [('1/8" = 1\'-0"', 9.0), ('3/16" = 1\'-0"', 13.5), ('1/4" = 1\'-0"', 18.0), ('3/8" = 1\'-0"', 27.0), ('1/2" = 1\'-0"', 36.0), ('3/4" = 1\'-0"', 54.0), ('1" = 1\'-0"', 72.0), ('1-1/2" = 1\'-0"', 108.0), ('3" = 1\'-0"', 216.0)]:
            self.rb.ribbon_scale_cb.addItem(lbl_s, pts_s)
        self.rb.ribbon_scale_cb.setCurrentIndex(2)
        self.rb.ribbon_scale_cb.currentIndexChanged.connect(self.rb._on_scale_changed)
        sc_col.addWidget(self.rb.ribbon_scale_cb)

        snap_row = QHBoxLayout()
        snap_row.setContentsMargins(0, 0, 0, 0)
        snap_row.setSpacing(5)
        self.rb.btn_ortho_lock = QPushButton("Ortho 90")
        self.rb.btn_ortho_lock.setCheckable(True)
        self.rb.btn_ortho_lock.setFixedSize(74, 24)
        self.rb.btn_ortho_lock.setStyleSheet("QPushButton { background-color: #ffffff !important; border: 1px solid #cbd5e1 !important; color: #0f172a !important; font-size: 11px !important; font-weight: 500 !important; border-radius: 3px; padding: 0px 4px !important; }")
        self.rb.btn_ortho_lock.toggled.connect(self.rb._toggle_ortho_lock)

        self.rb.btn_ep_snap = QPushButton("Snap")
        self.rb.btn_ep_snap.setCheckable(True)
        self.rb.btn_ep_snap.setChecked(True)
        self.rb.btn_ep_snap.setFixedSize(66, 24)
        self.rb.btn_ep_snap.setStyleSheet("QPushButton { background-color: #dbeafe !important; border: 1px solid #0284c7 !important; color: #0f172a !important; font-size: 11px !important; font-weight: 700 !important; border-radius: 3px; padding: 0px 4px !important; }")
        self.rb.btn_ep_snap.toggled.connect(self.rb._toggle_endpoint_snap)

        snap_row.addWidget(self.rb.btn_ortho_lock)
        snap_row.addWidget(self.rb.btn_ep_snap)
        sc_col.addLayout(snap_row)
        row.addLayout(sc_col)

    def _inject_sheet_bar(self, row):
        sh_col = QVBoxLayout()
        sh_col.setContentsMargins(2, 2, 2, 2)
        sh_col.setSpacing(4)
        self.rb.ribbon_sheet_cb = QComboBox()
        self.rb.ribbon_sheet_cb.setFixedSize(165, 24)
        self.rb.ribbon_sheet_cb.setStyleSheet("QComboBox { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 1px 6px; font-size: 11.5px; }")
        self.rb.ribbon_sheet_cb.addItem("Pg 1 (Blank Sheet)", 0)
        self.rb.ribbon_sheet_cb.currentIndexChanged.connect(self.rb._on_ribbon_sheet_changed)
        sh_col.addWidget(self.rb.ribbon_sheet_cb)

        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)
        nav_row.setSpacing(4)
        for nav_txt, d_sh in [("Prev Sheet", -1), ("Next Sheet", 1)]:
            nb = QPushButton(nav_txt)
            nb.setFixedHeight(18)
            nb.setCursor(Qt.PointingHandCursor)
            nb.setStyleSheet("QPushButton { background-color: #ffffff; border: 1px solid #cbd5e1; color: #0f172a; font-size: 11px; font-weight: 600; border-radius: 4px; padding: 0px 8px; } QPushButton:hover { background-color: #e0f2fe; }")
            nb.clicked.connect(lambda _=False, d=d_sh: self.rb._step_sheet(d))
            nav_row.addWidget(nb)
        sh_col.addLayout(nav_row)
        row.addLayout(sh_col)
