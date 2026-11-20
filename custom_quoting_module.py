from PySide6.QtCore import SIGNAL
from ui.excel_components import FormulaHudBar, apply_excel_table_style
import pymupdf
import os
import sys
import json
import math
import datetime
from PySide6.QtGui import QColor
import textwrap
from PySide6.QtCore import Qt, QMarginsF
from PySide6.QtGui import QTextDocument, QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QComboBox, QLineEdit, QPushButton, QFrame, QScrollArea, 
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, 
    QMessageBox, QMainWindow, QCheckBox, QSplitter, QInputDialog, QStackedWidget,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QAbstractItemView
)

def get_workspace_path(filename=""):
    if getattr(sys, 'frozen', False):
        exe_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        mei_dir = getattr(sys, '_MEIPASS', exe_dir)
        base_dir = exe_dir
        if filename and not os.path.exists(os.path.join(exe_dir, filename)) and os.path.exists(os.path.join(mei_dir, filename)):
            return os.path.join(mei_dir, filename)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    if filename in ("project_ledger.json", "matrix.json", "steel_matrix.json", "shop_safeguards.json"):
        srv_dir = r"\\BOWMANSERVER\shared\Bowman-Morton Pricing & Bidding 2025\AppData"
        try:
            if os.path.exists(r"\\BOWMANSERVER\shared\Bowman-Morton Pricing & Bidding 2025"):
                os.makedirs(srv_dir, exist_ok=True)
                srv_fp = os.path.join(srv_dir, filename)
                loc_fp = os.path.join(base_dir, filename)
                if not os.path.exists(srv_fp) and os.path.exists(loc_fp):
                    import shutil
                    shutil.copy2(loc_fp, srv_fp)
                return srv_fp
        except Exception:
            pass
    return os.path.join(base_dir, filename) if filename else base_dir


SANDBOX_MEMBER_STYLESHEET = """
QScrollArea, QScrollArea > QWidget, QScrollArea::viewport, #LeftScrollContainer { 
    background-color: transparent; border: none; 
    border: none; 
}
QLabel { 
    font-family: 'Segoe UI', Arial, sans-serif; font-weight: 600; 
    font-weight: 600; 
    font-size: 12px; 
    color: #0f172a;
}
QComboBox, QLineEdit { 
    background-color: #eff6ff; 
    color: #0f172a !important; 
    border: 1px solid #475569; 
    padding: 5px; 
    border-radius: 4px; 
}
QComboBox:hover, QLineEdit:hover { border: 1px solid #475569; }
QComboBox:focus, QLineEdit:focus { border: 1px solid #38bdf8; }
QCheckBox { color: #0f172a; font-weight: 600; font-size: 12px; }
QPushButton#PrimaryAction { background-color: rgba(147, 197, 253, 0.68) !important; border: 2px solid #0284c7 !important; color: #000000 !important; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 10px; }
QPushButton#PrimaryAction:hover { background-color: rgba(2, 132, 199, 0.45); border: 2px solid #7dd3fc; }
QPushButton#EmeraldAction { background-color: rgba(167, 243, 208, 0.68) !important; border: 2px solid #059669 !important; color: #000000 !important; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 8px; }
QPushButton#EmeraldAction:hover { background-color: rgba(167, 243, 208, 0.68); border: 2px solid #6ee7b7; }
QPushButton#DangerAction { background-color: #ffffff; border: 1px solid #fca5a5; color: #b91c1c; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 8px; }
QPushButton#DangerAction:hover { background-color: rgba(220, 38, 38, 0.45); border: 2px solid #fca5a5; }
QTableWidget {
    background-color: rgba(248, 250, 252, 0.80);
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    gridline-color: #60a5fa;
    color: #0f172a;
}
QHeaderView::section {
    background-color: #e8eef5;
    color: #0369a1;
    padding: 6px;
    font-weight: 600;
    border: 1px solid #60a5fa;
}
"""
def _ensure_pdf_writable(parent_widget, target_path):
    if not target_path or not os.path.exists(target_path):
        return True
    try:
        with open(target_path, "ab"):
            return True
    except (PermissionError, OSError):
        QMessageBox.warning(
            parent_widget,
            "PDF Currently Open",
            f"Cannot overwrite this PDF because it is currently open in another program:\n\n"
            f"  • {os.path.basename(target_path)}\n\n"
            f"Please close the PDF in your PDF viewer first (or save under a new file name) and try again.",
        )
        return False

class BidFormMathEngine:
    ALLOY_DENSITIES = {
        "Carbon Steel": 0.2836,
        "304 Stainless": 0.2890,
        "316 Stainless": 0.2900
    }

    WELD_SPEED_IPM = {
        "Fillet": 6.0,
        "PJP": 2.0,
        "CJP": 0.1
    }

    WELD_PASS_MULTIPLIER = {
        "3/16\"": 1,
        "1/4\"": 1,
        "5/16\"": 2,
        "3/8\"": 2,
        "1/2\"": 3
    }

    @staticmethod
    def get_density(alloy_name="Carbon Steel"):
        return BidFormMathEngine.ALLOY_DENSITIES.get(alloy_name, 0.2836)

    @staticmethod
    def calculate_billable_length(shape_key, cut_length, qty):
        cut_ft = max(0.01, float(cut_length))
        n_pcs = max(1, int(qty))
        total_needed_ft = cut_ft * n_pcs
        if shape_key == "plate":
            return total_needed_ft

        if shape_key == "beam":
            stock_opts = [float(x) for x in range(20, 65, 5)]
        elif shape_key in ["hss_tube", "pipe"]:
            stock_opts = [20.0, 24.0, 40.0]
        elif shape_key in ["angle", "channel", "flat_bar", "round_bar", "square_bar"]:
            stock_opts = [20.0, 40.0]
        else:
            return total_needed_ft

        # Pieces yielded per single stock stick of length S (never splice a piece across 2 sticks)
        usable = [(s, int(math.floor((s + 1e-6) / cut_ft))) for s in stock_opts if s + 1e-6 >= cut_ft]
        if not usable:
            # Cut length exceeds longest single mill bar; round up in 5-ft increments
            return math.ceil(cut_ft / 5.0) * 5.0 * n_pcs

        # Dynamic programming over piece count 0..n_pcs to minimize (total_purchased_ft, stick_count)
        INF = (1e18, 10**9)
        dp = [INF] * (n_pcs + 1)
        dp[0] = (0.0, 0)
        for rem in range(1, n_pcs + 1):
            best = INF
            for s_len, yield_cnt in usable:
                prev = max(0, rem - yield_cnt)
                cand = (dp[prev].__getitem__(0) + s_len, dp[prev].__getitem__(1) + 1)
                if cand < best:
                    best = cand
            dp[rem] = best
        return round(dp[n_pcs].__getitem__(0), 2)

    @staticmethod
    def calculate_plate(qty, length_in, width_in, thickness_in, rate_per_lb, alloy="Carbon Steel"):
        density = BidFormMathEngine.get_density(alloy)
        weight_per_unit = length_in * width_in * thickness_in * density
        total_weight = weight_per_unit * qty
        raw_cost = total_weight * rate_per_lb
        return round(weight_per_unit, 3), round(total_weight, 2), round(raw_cost, 2)

    @staticmethod
    def calculate_stiffener_geometry(beam_item):
        if not beam_item:
            return 5.5, 1.875
        d = beam_item.get("depth_in", 6.0)
        bf = beam_item.get("flange_width_in", 4.0)
        tf = beam_item.get("flange_thickness_in", 0.25)
        tw = beam_item.get("web_thickness_in", 0.20)
        height = max(0.0, d - (2.0 * tf) - 0.0625)
        width = max(0.0, ((bf - tw) / 2.0) - 0.0625)
        return round(height, 3), round(width, 3)

    @staticmethod
    def calculate_hd_stud_weight(dia, length, alloy="Carbon Steel"):
        density = BidFormMathEngine.get_density(alloy)
        return (math.pi * ((dia / 2.0) ** 2) * length) * density

    @staticmethod
    def calculate_finishing_treatments(weight, apply_pc, apply_hdg):
        pc_cost = (weight * 1.80) if apply_pc else 0.0
        hdg_cost = 0.0
        if apply_hdg:
            hdg_cost = (weight * 0.62) if weight >= 20.0 else (weight * 1.88)
        return round(pc_cost, 2), round(hdg_cost, 2)

    @staticmethod
    def calculate_weld_cost(linear_inches, weld_type, weld_size, full_wrap, base_labor_rate, safeguards=None):
        if linear_inches <= 0:
            return 0.0
        effective_inches = linear_inches * (2.0 if full_wrap else 1.0)
        if safeguards:
            ipm_map = {
                "Fillet": float(safeguards.get("fillet_ipm", 6.0)),
                "PJP": float(safeguards.get("pjp_ipm", 2.0)),
                "CJP": float(safeguards.get("cjp_ipm", 2.5))
            }
            pass_map = {
                "3/16\"": float(safeguards.get("passes_3_16", 1)),
                "1/4\"": float(safeguards.get("passes_1_4", 1)),
                "5/16\"": float(safeguards.get("passes_5_16", 2)),
                "3/8\"": float(safeguards.get("passes_3_8", 2)),
                "1/2\"": float(safeguards.get("passes_1_2", 3)), "5/8\"": float(safeguards.get("passes_5_8", 4)), "3/4\"": float(safeguards.get("passes_3_4", 5)), "1\"": float(safeguards.get("passes_1", 7))
            }
            ipm = ipm_map.get(weld_type, 6.0)
            passes = 1 if weld_type in ('CJP', 'PJP') else pass_map.get(weld_size, 1)
        else:
            ipm = BidFormMathEngine.WELD_SPEED_IPM.get(weld_type, 6.0)
            passes = BidFormMathEngine.WELD_PASS_MULTIPLIER.get(weld_size, 1)

        arc_hours = ((effective_inches / ipm) / 60.0) * passes
        return arc_hours * base_labor_rate
class AddonRowWidget(QWidget):
    WELDABLE_OPS = {
        "Stiffeners", "HD Studs", "WH-Welded Hanger",
        "Standard End Plate", "Top Flange End Plate", "Flush End Cap",
        "Oversized Base Plate", "Shear Tabs"
    }

    def __init__(self, remove_callback, parent_card, parent=None):
        super().__init__(parent)
        self.remove_callback = remove_callback
        self.card = parent_card
        self.init_ui()

    def init_ui(self):
        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(4, 4, 4, 4)
        self.outer_layout.setSpacing(4)

        top_line = QHBoxLayout()
        top_line.setSpacing(5)

        self.type_select = QComboBox()
        self.type_select.setFixedWidth(155)
        top_line.addWidget(self.type_select)

        self.in_param1 = QLineEdit()
        self.in_param2 = QLineEdit()
        self.in_param3 = QLineEdit()
        self.in_param4 = QLineEdit()
        for w in [self.in_param1, self.in_param2, self.in_param3, self.in_param4]:
            w.setFixedWidth(62)
            top_line.addWidget(w)

        self.combo_sub = QComboBox()
        self.combo_sub.setFixedWidth(95)
        top_line.addWidget(self.combo_sub)

        self.chk_nsc_end = QCheckBox("NSC End")
        top_line.addWidget(self.chk_nsc_end)

        self.in_qty = QLineEdit("1")
        self.in_qty.setFixedWidth(36)
        top_line.addWidget(self.in_qty)

        self.btn_delete = QPushButton("✕")
        self.btn_delete.setFixedSize(26, 24)
        self.btn_delete.setStyleSheet("QPushButton { background-color: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; border-radius: 4px; padding: 0px; font-weight: 800; font-size: 12px; } QPushButton:hover { background-color: #fecaca; color: #7f1d1d; }")
        self.btn_delete.clicked.connect(lambda: self.remove_callback(self))
        top_line.addWidget(self.btn_delete)
        top_line.addStretch()

        self.outer_layout.addLayout(top_line)

        self.weld_bar = QWidget()
        weld_layout = QHBoxLayout(self.weld_bar)
        weld_layout.setContentsMargins(12, 0, 0, 0)
        weld_layout.setSpacing(8)

        self.chk_field_weld = QCheckBox("Field Weld (Ship Loose)")
        self.chk_field_weld.toggled.connect(self.toggle_weld_controls)
        weld_layout.addWidget(self.chk_field_weld)

        self.combo_weld_wrap = QComboBox()
        self.combo_weld_wrap.addItems(["Full Wrap / Both Sides", "Single Side"])
        self.combo_weld_wrap.setFixedWidth(145)
        weld_layout.addWidget(self.combo_weld_wrap)

        self.combo_weld_type = QComboBox()
        self.combo_weld_type.addItems(["Fillet", "PJP", "CJP"])
        self.combo_weld_type.setFixedWidth(70)
        weld_layout.addWidget(self.combo_weld_type)

        self.combo_weld_size = QComboBox()
        self.combo_weld_size.addItems(["3/16\"", "1/4\"", "5/16\"", "3/8\"", "1/2\"", "5/8\"", "3/4\"", "1\""])
        self.combo_weld_size.setCurrentText("1/4\"")
        self.combo_weld_size.setFixedWidth(65)
        weld_layout.addWidget(self.combo_weld_size)

        weld_layout.addStretch()
        self.outer_layout.addWidget(self.weld_bar)

    def toggle_weld_controls(self, is_field_weld):
        shop_welded = not is_field_weld
        self.combo_weld_wrap.setVisible(shop_welded)
        self.combo_weld_type.setVisible(shop_welded)
        self.combo_weld_size.setVisible(shop_welded)
    def populate_surcharges_by_shape(self, shape_key):
        try:
            try:
                try:
                    import warnings as _w
                    with _w.catch_warnings():
                        _w.simplefilter('ignore', RuntimeWarning)
                        self.type_select.currentIndexChanged.disconnect()
                except Exception:
                    pass
            except Exception:
                pass
        except (RuntimeError, TypeError):
            pass
        self.type_select.clear()

        options_map = {
            "beam": [
                "Stiffeners", "Standard Studs", "HD Studs", "Drill Holes",
                "NSC-Angled cuts", "WH-Welded Hanger", "Torch cut", "Cope",
                "Standard End Plate", "Top Flange End Plate", "Shear Tabs", "Band Saw Cut"
            ],
            "channel": [
                "Standard Studs", "HD Studs", "Drill Holes",
                "NSC-Angled cuts", "Torch cut", "Cope", "Shear Tabs", "Band Saw Cut"
            ],
            "hss_tube": [
                "Flush End Cap", "Oversized Base Plate", "Shear Tabs",
                "Standard Studs", "HD Studs", "Drill Holes",
                "NSC-Angled cuts", "Torch cut", "Band Saw Cut"
            ],
            "angle": [
                "Standard Studs", "HD Studs", "Drill Holes",
                "NSC-Angled cuts", "Torch cut", "Band Saw Cut"
            ],
            "pipe": [
                "Flush End Cap", "Oversized Base Plate", "Standard Studs",
                "HD Studs", "Drill Holes", "Saddle Cut", "Torch cut", "Band Saw Cut"
            ],
            "flat_bar": [
                "Punch Holes", "Shear Cuts", "Standard Studs",
                "HD Studs", "Drill Holes", "Band Saw Cut", "Torch cut"
            ],
            "round_bar": [
                "Standard Studs", "HD Studs", "Drill Holes",
                "Band Saw Cut", "Torch cut"
            ],
            "square_bar": [
                "Punch Holes", "Shear Cuts", "Standard Studs",
                "HD Studs", "Drill Holes", "Band Saw Cut", "Torch cut"
            ],
            "plate": [
                "Drill Holes", "Punch Holes", "Shear Cuts",
                "Press Brake Bend", "Band Saw Cut", "Torch cut"
            ]
        }

        items_for_shape = list(options_map.get(shape_key, ["Drill Holes"]))
        sg = getattr(self.window(), "custom_safeguards", None) if hasattr(self, "window") else None
        if isinstance(sg, dict):
            for cf in sg.get("custom_extra_fees", []):
                if cf.get("category") == "Tab 2 Custom Flat Fees":
                    items_for_shape.append(f"Custom Fee: {cf['label']}")
        self.type_select.addItems(items_for_shape)
        self.type_select.currentIndexChanged.connect(self.adapt_field_visibility_slots)
        self.adapt_field_visibility_slots()

    def adapt_field_visibility_slots(self):
        mode = self.type_select.currentText()
        for w in [self.in_param1, self.in_param2, self.in_param3, self.in_param4]:
            w.setVisible(False)
            w.setEnabled(True)
            w.clear()
        self.combo_sub.setVisible(False)
        self.combo_sub.clear()
        self.chk_nsc_end.setVisible(False)
        self.chk_nsc_end.setChecked(False)

        is_weldable = mode in self.WELDABLE_OPS
        self.weld_bar.setVisible(is_weldable)
        if is_weldable:
            self.toggle_weld_controls(self.chk_field_weld.isChecked())

        if mode == "Stiffeners":
            self.in_param1.setVisible(True); self.in_param1.setPlaceholderText("Thk (in)")
            self.in_param2.setVisible(True); self.in_param2.setPlaceholderText("W Auto")
            self.in_param3.setVisible(True); self.in_param3.setPlaceholderText("H Auto")
            self.in_param2.setEnabled(False); self.in_param3.setEnabled(False)
            dims = self.card.get_active_profile_dimensions()
            h, w = BidFormMathEngine.calculate_stiffener_geometry(dims)
            self.in_param2.setText(str(w))
            self.in_param3.setText(str(h))
        elif mode in ["Standard Studs", "WH-Welded Hanger", "Saddle Cut", "Band Saw Cut"]:
            pass
        elif mode == "HD Studs":
            self.in_param1.setVisible(True); self.in_param1.setPlaceholderText("Dia (in)")
            self.in_param2.setVisible(True); self.in_param2.setPlaceholderText("Len (in)")
        elif mode in ["Drill Holes", "Punch Holes"]:
            self.in_param1.setVisible(True); self.in_param1.setPlaceholderText("Dia (in)")
            self.in_param2.setVisible(True); self.in_param2.setPlaceholderText("Hole Qty")
        elif mode == "NSC-Angled cuts":
            self.in_param1.setVisible(True); self.in_param1.setPlaceholderText("Degree")
        elif mode == "Torch cut":
            self.combo_sub.setVisible(True)
            self.combo_sub.addItems(["Level 1", "Level 2", "Level 3", "Level 4"])
        elif mode == "Cope":
            self.combo_sub.setVisible(True)
            beams = [b.get("designation", "") for b in self.card.steel_matrix_data.get("beam", []) if "designation" in b]
            self.combo_sub.addItems(beams)
        elif mode == "Standard End Plate":
            self.in_param1.setVisible(True); self.in_param1.setPlaceholderText("Thk (in)")
            self.chk_nsc_end.setVisible(True)
        elif mode == "Flush End Cap":
            self.in_param1.setVisible(True); self.in_param1.setPlaceholderText("Thk (in)")
        elif mode in ["Top Flange End Plate", "Oversized Base Plate", "Shear Tabs"]:
            self.in_param1.setVisible(True); self.in_param1.setPlaceholderText("Thk (in)")
            self.in_param2.setVisible(True); self.in_param2.setPlaceholderText("Width")
            self.in_param3.setVisible(True); self.in_param3.setPlaceholderText("Length")
            self.in_param4.setVisible(True); self.in_param4.setPlaceholderText("Hole Qty")
        elif mode in ["Shear Cuts", "Press Brake Bend"]:
            self.in_param1.setVisible(True); self.in_param1.setPlaceholderText("Bend/Cut L")

    def parse_fractional_input(self, text_str):
        text = text_str.strip()
        if not text:
            return 0.0
        if "/" in text:
            try:
                if "-" in text:
                    whole, frac = text.split("-", 1)
                    num, den = frac.split("/", 1)
                    return float(whole) + (float(num) / float(den))
                if " " in text:
                    whole, frac = text.split(" ", 1)
                    num, den = frac.split("/", 1)
                    return float(whole) + (float(num) / float(den))
                num, den = text.split("/", 1)
                return float(num) / float(den)
            except (ValueError, ZeroDivisionError):
                return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0

    def load_state(self, st):
        if not isinstance(st, dict):
            return
        mode_val = str(st.get("mode", "")).strip()
        if mode_val:
            idx = self.type_select.findText(mode_val, Qt.MatchFixedString)
            if idx < 0:
                idx = self.type_select.findText(mode_val, Qt.MatchContains)
            if idx >= 0:
                self.type_select.setCurrentIndex(idx)
                self.adapt_field_visibility_slots()
        for slot_w, key_p in ((self.in_param1, "p1"), (self.in_param2, "p2"), (self.in_param3, "p3"), (self.in_param4, "p4")):
            v = st.get(key_p, 0)
            if slot_w.isVisible() and slot_w.isEnabled() and v not in (None, "", 0, 0.0):
                slot_w.setText(f"{float(v):g}" if isinstance(v, (int, float)) else str(v))
        sub_v = str(st.get("sub", "")).strip()
        if self.combo_sub.isVisible() and sub_v:
            s_idx = self.combo_sub.findText(sub_v, Qt.MatchFixedString)
            if s_idx >= 0:
                self.combo_sub.setCurrentIndex(s_idx)
        if self.chk_nsc_end.isVisible():
            self.chk_nsc_end.setChecked(bool(st.get("nsc_end", False)))
        self.in_qty.setText(str(max(1, int(float(st.get("qty", 1) or 1)))))
        if self.weld_bar.isVisible():
            fw = bool(st.get("field_weld", False))
            self.chk_field_weld.setChecked(fw)
            self.toggle_weld_controls(fw)
            self.combo_weld_wrap.setCurrentIndex(0 if st.get("full_wrap", True) else 1)
            wt = str(st.get("weld_type", "Fillet")).strip()
            if wt:
                self.combo_weld_type.setCurrentText(wt)
            ws = str(st.get("weld_size", "1/4\"")).strip()
            if ws:
                self.combo_weld_size.setCurrentText(ws)

    def get_payload(self):
        try:
            qty = int(self.in_qty.text().strip()) if self.in_qty.text().strip() else 1
        except ValueError:
            qty = 0
        return {
            "mode": self.type_select.currentText(),
            "p1": self.parse_fractional_input(self.in_param1.text()) if self.in_param1.isVisible() else 0.0,
            "p2": self.parse_fractional_input(self.in_param2.text()) if self.in_param2.isVisible() else 0.0,
            "p3": self.parse_fractional_input(self.in_param3.text()) if self.in_param3.isVisible() else 0.0,
            "p4": self.parse_fractional_input(self.in_param4.text()) if self.in_param4.isVisible() else 0.0,
            "sub": self.combo_sub.currentText() if self.combo_sub.isVisible() else "",
            "nsc_end": self.chk_nsc_end.isChecked() if self.chk_nsc_end.isVisible() else False,
            "qty": qty,
            "field_weld": self.chk_field_weld.isChecked() if self.weld_bar.isVisible() else False,
            "full_wrap": (self.combo_weld_wrap.currentText() == "Full Wrap / Both Sides"),
            "weld_type": self.combo_weld_type.currentText(),
            "weld_size": self.combo_weld_size.currentText()
        }
class DynamicMemberCard(QFrame):
    def __init__(self, calc_callback, parent=None):
        super().__init__(parent)
        self.calc_callback = calc_callback
        self.addon_rows = []
        self.active_shape_key = "beam"
        self.steel_matrix_data = {}

        self.setObjectName("DynamicMemberCard")
        self.setStyleSheet("QFrame#DynamicMemberCard { background-color: rgba(248, 250, 252, 0.80); border: 1px solid #cbd5e1; border-radius: 8px; }")
        self.init_ui()

    def init_ui(self):
        self.card_layout = QVBoxLayout(self)
        self.card_layout.setContentsMargins(12, 12, 12, 12)
        self.card_layout.setSpacing(10)

        self.header_lbl = QLabel("STRUCTURAL BEAM MEMBER")
        self.header_lbl.setStyleSheet("color: #0369a1; font-size: 12px; font-weight: 600;")
        self.card_layout.addWidget(self.header_lbl)

        self.grid = QGridLayout()
        self.grid.setSpacing(8)

        self.grid.addWidget(QLabel("Select Steel Size:"), 0, 0)
        self.combo_model = QComboBox()
        self.combo_model.currentIndexChanged.connect(self.trigger_geometry_updates)
        self.grid.addWidget(self.combo_model, 0, 1)

        self.lbl_extent = QLabel("Cut Length (ft):")
        self.grid.addWidget(self.lbl_extent, 1, 0)
        self.input_extent = QLineEdit("10.0")
        self.grid.addWidget(self.input_extent, 1, 1)

        self.chk_custom_mill = QCheckBox("Override Mill Stock Length")
        self.chk_custom_mill.toggled.connect(self.toggle_custom_mill_input)
        self.input_custom_mill = QLineEdit("10.0")
        self.input_custom_mill.setPlaceholderText("Billable ft")
        self.input_custom_mill.setVisible(False)
        self.grid.addWidget(self.chk_custom_mill, 2, 0)
        self.grid.addWidget(self.input_custom_mill, 2, 1)

        self.lbl_plate_w = QLabel("Plate Width (in):")
        self.input_plate_w = QLineEdit("12.0")
        self.lbl_plate_thk = QLabel("Plate Thickness (in):")
        self.input_plate_thk = QLineEdit("0.25")
        self.grid.addWidget(self.lbl_plate_w, 3, 0)
        self.grid.addWidget(self.input_plate_w, 3, 1)
        self.grid.addWidget(self.lbl_plate_thk, 4, 0)
        self.grid.addWidget(self.input_plate_thk, 4, 1)

        self.card_layout.addLayout(self.grid)

        treatment_host = QWidget()
        treat_layout = QHBoxLayout(treatment_host)
        treat_layout.setContentsMargins(0, 0, 0, 0)
        self.chk_primer = QCheckBox("Apply Standard Shop Primer")
        self.chk_primer.setChecked(True)
        self.chk_powder = QCheckBox("Apply Powder Coating (PC)")
        self.chk_galv = QCheckBox("Apply Hot-Dip Galvanized (HDG)")
        treat_layout.addWidget(self.chk_primer)
        treat_layout.addWidget(self.chk_powder)
        self.chk_powder.toggled.connect(lambda c: self.chk_primer.setChecked(False) if c else None)
        self.chk_galv.toggled.connect(lambda c: self.chk_primer.setChecked(False) if c else None)
        treat_layout.addWidget(self.chk_galv)
        self.card_layout.addWidget(treatment_host)

        self.card_layout.addWidget(QLabel("Shop Fabrication & Connections:"))
        self.addon_host = QWidget()
        self.addon_layout = QVBoxLayout(self.addon_host)
        self.addon_layout.setContentsMargins(0, 0, 0, 0)
        self.addon_layout.setSpacing(6)
        self.card_layout.addWidget(self.addon_host)

        self.btn_add_op = QPushButton("+ Add Fabrication Add-on")
        self.btn_add_op.setStyleSheet("QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 8px; } QPushButton:hover { background-color: rgba(167, 243, 208, 0.68); color: #0f172a; }")
        self.btn_add_op.clicked.connect(self.add_addon_row)

        # Connection Library Bar (with Include Hardware / Fasteners toggle)
        self.conn_host = QWidget()
        self.conn_host.setStyleSheet("background: transparent; border: none;")
        conn_bar = QHBoxLayout(self.conn_host)
        conn_bar.setContentsMargins(0, 2, 0, 2)
        conn_bar.setSpacing(6)
        self.cb_conn_preset = QComboBox()
        self.cb_conn_preset.setMinimumHeight(32)
        self.cb_conn_preset.setToolTip("Select a reusable shop connection preset")
        self._conn_presets_data = []
        try:
            _cp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "connection_presets.json")
            if os.path.exists(_cp_path):
                with open(_cp_path, "r", encoding="utf-8-sig") as _cpf:
                    self._conn_presets_data = json.load(_cpf).get("presets", [])
        except Exception:
            self._conn_presets_data = []
        self.cb_conn_preset.addItem("Select Connection Preset...", None)
        for _pr in self._conn_presets_data:
            self.cb_conn_preset.addItem(_pr.get("name", "Preset"), _pr)
        self.chk_conn_hardware = QCheckBox("Include Hardware / Fasteners")
        self.chk_conn_hardware.setChecked(True)
        self.chk_conn_hardware.setToolTip("Uncheck when Bowman-Morton is fabricating steel/plates only without supplying bolts or anchors.")
        self.btn_apply_conn = QPushButton("Apply Connection")
        self.btn_apply_conn.setMinimumHeight(32)
        self.btn_apply_conn.setCursor(Qt.PointingHandCursor)
        self.btn_apply_conn.clicked.connect(self.apply_connection_preset)
        conn_bar.addWidget(self.cb_conn_preset, 1)
        conn_bar.addWidget(self.chk_conn_hardware, 0)
        conn_bar.addWidget(self.btn_apply_conn, 0)
        self.conn_host.setVisible(False)
        self.card_layout.addWidget(self.conn_host)
        self.card_layout.addWidget(self.btn_add_op)

        self.btn_calc = QPushButton("Add Member to Quote")
        self.btn_calc.setStyleSheet("QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 10px; } QPushButton:hover { background-color: rgba(96, 165, 250, 0.82); color: #0f172a; }")
        self.btn_calc.clicked.connect(self.submit_card_calculation)
        self.card_layout.addWidget(self.btn_calc)

    def toggle_custom_mill_input(self, checked):
        self.input_custom_mill.setVisible(checked)
        if checked:
            self.input_custom_mill.setText(self.input_extent.text().strip())


    def apply_connection_preset(self):
        preset = self.cb_conn_preset.currentData()
        if not preset:
            return
        items = list(preset.get("steel_and_weld", []))
        if self.chk_conn_hardware.isChecked():
            items.extend(preset.get("hardware_items", []))
        for st in items:
            self.add_addon_row()
            if self.addon_rows:
                row = self.addon_rows[-1]
                if hasattr(row, "load_state"):
                    row.load_state(st)
        if hasattr(self, "recalculate_card"):
            self.recalculate_card()

    def add_addon_row(self):
        if hasattr(self, "conn_host") and self.active_shape_key in ("beam", "channel", "hss_tube", "pipe"):
            self.conn_host.setVisible(True)
        row = AddonRowWidget(remove_callback=self.remove_addon_row, parent_card=self)
        self.addon_layout.addWidget(row)
        row.populate_surcharges_by_shape(self.active_shape_key)
        self.addon_rows.append(row)

    def remove_addon_row(self, row_widget):
        if row_widget in self.addon_rows:
            self.addon_rows.remove(row_widget)
        row_widget.deleteLater()

    def clear_all_addon_rows(self):
        if hasattr(self, "conn_host"):
            self.conn_host.setVisible(False)
            self.cb_conn_preset.setCurrentIndex(0)
        while self.addon_rows:
            row_widget = self.addon_rows.pop()
            row_widget.deleteLater()

    def get_active_profile_dimensions(self):
        model_name = self.combo_model.currentText()
        for item in self.steel_matrix_data.get(self.active_shape_key, []):
            if item.get("designation") == model_name:
                return item
        return None

    def trigger_geometry_updates(self):
        for r in self.addon_rows:
            if r.type_select.currentText() == "Stiffeners":
                r.adapt_field_visibility_slots()

    def update_card_context(self, shape_key, matrix_data):
        self.active_shape_key = shape_key
        self.steel_matrix_data = matrix_data
        self.combo_model.clear()
        self.clear_all_addon_rows()

        title_maps = {
            "beam": "STRUCTURAL BEAM MEMBER", "angle": "ANGLE IRON SECTION",
            "channel": "CHANNEL PROFILE MEMBER", "pipe": "STRUCTURAL PIPE SELECTION",
            "hss_tube": "HOLLOW STRUCTURAL SECTION (HSS)", "plate": "CUSTOM PLATE ASSET",
            "flat_bar": "COMMERCIAL FLAT BAR MEMBER", "round_bar": "ROUND BAR STOCK",
            "square_bar": "SQUARE BAR STOCK"
        }
        self.header_lbl.setText(title_maps.get(shape_key, "MEMBER PROFILE"))

        items_list = [item.get("designation", "") for item in self.steel_matrix_data.get(shape_key, []) if "designation" in item]
        self.combo_model.addItems(items_list)

        is_plate = (shape_key == "plate")
        if hasattr(self, "conn_host"):
            self.conn_host.setVisible(False)
            self.cb_conn_preset.setCurrentIndex(0)
        self.lbl_extent.setText("Plate Length (in):" if is_plate else "Cut Length (ft):")
        self.chk_custom_mill.setVisible(not is_plate)
        self.chk_custom_mill.setChecked(False)
        self.input_custom_mill.setVisible(False)
        for w in [self.lbl_plate_w, self.input_plate_w, self.lbl_plate_thk, self.input_plate_thk]:
            w.setVisible(is_plate)

    def submit_card_calculation(self):
        try:
            extent = float(self.input_extent.text().strip())
            plate_w = float(self.input_plate_w.text().strip()) if self.input_plate_w.isVisible() else 0.0
            plate_thk = float(self.input_plate_thk.text().strip()) if self.input_plate_thk.isVisible() else 0.0
            custom_mill = float(self.input_custom_mill.text().strip()) if (self.chk_custom_mill.isVisible() and self.chk_custom_mill.isChecked()) else None
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Verify dimensional numbers are valid.")
            return

        model = self.combo_model.currentText()
        payloads = [r.get_payload() for r in self.addon_rows]
        pc = self.chk_powder.isChecked()
        hdg = self.chk_galv.isChecked()

        self.calc_callback(self.active_shape_key, model, extent, plate_w, plate_thk, pc, hdg, payloads, custom_mill)

        self.clear_all_addon_rows()
        self.chk_powder.setChecked(False)
        self.chk_galv.setChecked(False)
        self.chk_custom_mill.setChecked(False)


from PySide6.QtWidgets import QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog


from blueprint_takeoff_ui import VisualTakeoffWorkspace


from PySide6.QtCore import QThread, Signal

class _BomBackgroundScanWorker(QThread):
    progress_scan = Signal(int, int, str, int)
    finished_scan = Signal(list, float, str)
    failed_scan = Signal(str)

    def __init__(self, pdf_path, matrix_path, selected_pages=None, region_clip=None, use_native_ocr=True, sheet_scales=None, mode_tag="sheet", scan_mode="hybrid", parent=None):
        super().__init__(parent)
        self.pdf_path = pdf_path
        self.matrix_path = matrix_path
        self.selected_pages = selected_pages
        self.region_clip = region_clip
        self.use_native_ocr = use_native_ocr
        self.sheet_scales = sheet_scales
        self.mode_tag = mode_tag
        self.scan_mode = scan_mode or ("hybrid" if use_native_ocr else "vector")
        self._stop_flag = False

    def request_stop(self):
        self._stop_flag = True

    def run(self):
        try:
            if self.mode_tag == "box" and self.region_clip is not None and self.selected_pages:
                from core.region_sheet_scan_engine import scan_drag_region_bom
                rows, dt, _ = scan_drag_region_bom(
                    self.pdf_path,
                    self.selected_pages[0],
                    self.region_clip,
                    scan_mode=self.scan_mode,
                    matrix_path=self.matrix_path,
                    sheet_scales=self.sheet_scales,
                )
            elif self.mode_tag == "sheet" and self.selected_pages:
                from core.region_sheet_scan_engine import scan_current_sheet_bom
                rows, dt, _ = scan_current_sheet_bom(
                    self.pdf_path,
                    self.selected_pages[0],
                    scan_mode=self.scan_mode,
                    matrix_path=self.matrix_path,
                    sheet_scales=self.sheet_scales,
                )
            else:
                import bom_pdf_engine as eng
                rows, dt, _ = eng.extract_full_bom(
                    self.pdf_path,
                    matrix_path=self.matrix_path,
                    selected_pages=self.selected_pages,
                    region_clip=self.region_clip,
                    use_native_ocr=(self.scan_mode != "vector"),
                    sheet_scales=self.sheet_scales,
                    scan_mode=self.scan_mode,
                    progress_cb=lambda cur, tot, sh, cnt: self.progress_scan.emit(cur, tot, sh, cnt),
                    cancel_check=lambda: bool(self._stop_flag),
                )
            self.finished_scan.emit(rows, float(dt), self.mode_tag)
        except Exception as ex:
            self.failed_scan.emit(str(ex))

class PdfBomImporterDialog(QDialog):
    def __init__(self, pdf_path, extracted_rows, steel_matrix_data, parent=None, embed_in_main=False):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )
        self._embed_in_main = bool(embed_in_main)
        self.pdf_path = pdf_path or ""
        self.setWindowTitle(f"Structural PDF BOM & Visual Takeoff - {os.path.basename(self.pdf_path) if self.pdf_path else 'No Planset Loaded'}")
        self.resize(1180, 740)
        self.steel_matrix_data = steel_matrix_data
        self.accepted_rows = []
        self._updating_tree = False
        if self.pdf_path and os.path.exists(self.pdf_path):
            self._doc = pymupdf.open(self.pdf_path)
        else:
            self._doc = pymupdf.open()
            self._doc.new_page(width=1224, height=792)

        self.setStyleSheet(
            "QDialog, QStackedWidget, QWidget#BomPage, QWidget#VisPage { background-color: transparent; color: #0f172a; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; } "
            "QLabel, QCheckBox { color: #0f172a; font-size: 12px; font-weight: 600; } "
            "QComboBox, QLineEdit { background-color: #eff6ff; color: #0f172a; border: 1px solid #60a5fa; border-radius: 4px; padding: 3px 7px; font-size: 12px; font-weight: 600; } "
            "QComboBox QAbstractItemView { background-color: #eff6ff; color: #0f172a; selection-background-color: #0284c7; selection-color: #ffffff; border: 1px solid #0284c7; font-size: 12px; font-weight: 600; outline: none; } "
            "QTreeWidget, QListWidget { background-color: #f0f7ff; color: #0f172a; border: 1px solid #60a5fa; alternate-background-color: #dbeafe; font-size: 12px; } "
            "QTreeWidget::item { padding: 3px 5px; border-bottom: 1px solid #bfdbfe; } "
            "QTreeWidget::item:selected { background-color: #93c5fd; color: #0f172a; } "
            "QHeaderView::section { background-color: #1e3a8a; color: #ffffff; font-size: 12px; font-weight: 600; padding: 4px 6px; border: 1px solid #60a5fa; } "
            "QPushButton { background-color: rgba(239, 246, 255, 0.85) !important; border: 1.5px solid #0284c7 !important; color: #0f172a !important; font-family: 'Segoe UI', Arial, sans-serif !important; font-size: 12px !important; font-weight: 600 !important; padding: 4px 10px !important; border-radius: 5px; } "
            "QPushButton:hover { background-color: rgba(147, 197, 253, 0.55) !important; }"
        )

        layout = QVBoxLayout(self)
        if embed_in_main:
            layout.setContentsMargins(6, 0, 6, 4)
            layout.setSpacing(2)

        self.inner_nav_frame = QFrame()
        self.inner_nav_frame.setVisible(not embed_in_main)
        if embed_in_main:
            self.inner_nav_frame.setFixedHeight(0)
        nav_bar = QHBoxLayout(self.inner_nav_frame)
        nav_bar.setContentsMargins(0, 0, 0, 0)
        self.btn_tab_bom = QPushButton("1. BOM Staging Tree")
        self.btn_tab_vis = QPushButton("2. Visual Sheet Preview & Takeoff")
        nav_bar.addWidget(self.btn_tab_bom)
        nav_bar.addWidget(self.btn_tab_vis)
        nav_bar.addSpacing(12)
        nav_bar.addWidget(QLabel("Sheet:"))
        self.sheet_combo = QComboBox()
        import bom_pdf_engine as eng
        if self.pdf_path and os.path.exists(self.pdf_path):
            for s_info in eng.inspect_pdf_sheets(self.pdf_path):
                self.sheet_combo.addItem(f"Pg {s_info['page']} ({s_info['sheet']} - {s_info['mode']})", s_info["page"])
        else:
            self.sheet_combo.addItem("Pg 1 (Blank Sheet)", 0)
        self.sheet_combo.currentIndexChanged.connect(self._render_current_sheet)
        nav_bar.addWidget(self.sheet_combo)
        self.btn_scan_pg = QPushButton("Auto-Scan Sheet")
        self.btn_scan_pg.clicked.connect(self._scan_selected_sheet)
        nav_bar.addWidget(self.btn_scan_pg)
        nav_bar.addStretch()
        layout.addWidget(self.inner_nav_frame)

        self.view_stack = QStackedWidget()
        layout.addWidget(self.view_stack, 1)

        bom_page = QWidget()
        bom_page.setObjectName("BomPage")
        bom_l = QVBoxLayout(bom_page)
        bom_l.setContentsMargins(0, 2, 0, 0)
        top_lbl = QLabel(
            f"Extracted {len(extracted_rows)} structural steel group(s). "
            "Double-click Qty or Length (ft) to adjust, or switch to Visual Sheet Preview to box-read or measure SHX plans."
        )
        top_lbl.setWordWrap(True)
        bom_l.addWidget(top_lbl)

        bar = QHBoxLayout()
        btn_exp = QPushButton("Expand All")
        btn_col = QPushButton("Collapse All")
        btn_all = QPushButton("Check All")
        btn_none = QPushButton("Uncheck All")
        btn_split = QPushButton("Duplicate / Split Selected")
        btn_del = QPushButton("Delete Selected")
        btn_del.setStyleSheet("QPushButton { background-color: #ffffff; border: 1px solid #fca5a5; color: #b91c1c; font-weight: 700; font-weight: 600; } QPushButton:hover { background-color: rgba(252, 165, 165, 0.84); color: #7f1d1d; }")

        self.tree = QTreeWidget()
        apply_excel_table_style(self.tree)
        self.tree.setColumnCount(8)
        self.tree.setHeaderLabels([
            "Category / Keep", "Sheet", "Detail Callout", "Profile / Plate Size", "Qty", "Length (ft)", "Unit Wt (lb/ft)", "Est. Ship Wt (lbs)"
        ])
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(QHeaderView.Interactive)
        self.tree.header().setStretchLastSection(True)
        for c_i, w_px in enumerate([235, 68, 120, 225, 65, 95, 110, 125]):
            self.tree.setColumnWidth(c_i, w_px)

        btn_exp.clicked.connect(self.tree.expandAll)
        btn_col.clicked.connect(self.tree.collapseAll)
        btn_all.clicked.connect(lambda: self._toggle_all(Qt.Checked))
        btn_none.clicked.connect(lambda: self._toggle_all(Qt.Unchecked))
        btn_split.clicked.connect(self._duplicate_selected_row)
        btn_del.clicked.connect(self._remove_selected_row)

        for b in (btn_exp, btn_col, btn_all, btn_none, btn_split, btn_del):
            bar.addWidget(b)
        from bom_summary_panel import SmartBomSummaryPanel
        bar.addStretch()
        bom_l.addLayout(bar)

        bom_split = QSplitter(Qt.Horizontal)
        bom_split.setChildrenCollapsible(False)
        bom_split.addWidget(self.tree)
        self.smart_summary_panel = SmartBomSummaryPanel(on_jump_to_sheet=self._jump_to_sheet_from_bom, on_jump_to_profile=self._jump_to_profile_from_bom, parent=bom_page)
        bom_split.addWidget(self.smart_summary_panel)
        self.smart_summary_panel.setMinimumWidth(310)
        self.smart_summary_panel.setMaximumWidth(360)
        self.smart_summary_panel.setVisible(True)
        bom_split.setStretchFactor(0, 3)
        bom_split.setStretchFactor(1, 1)
        bom_split.setSizes([960, 290])
        bom_l.addWidget(bom_split, 1)
        self.tree.itemDoubleClicked.connect(self._on_bom_row_double_clicked)
        self.view_stack.addWidget(bom_page)

        vis_page = QWidget()
        vis_page.setObjectName("VisPage")
        vis_l = QVBoxLayout(vis_page)
        vis_l.setContentsMargins(0, 0, 0, 0)

        self.vis_workspace = VisualTakeoffWorkspace(
            pdf_path=pdf_path,
            steel_matrix_data=steel_matrix_data,
            get_page_fn=lambda: int(self.sheet_combo.currentData() or 1),
            on_box_ocr=self._handle_box_ocr,
            on_span_measured=self._handle_span_measured,
            on_count_changed=self._handle_count_changed,
            on_calibrated=self._handle_calibrated,
            parent=vis_page,
        )
        self.viewport = self.vis_workspace.canvas
        vis_l.addWidget(self.vis_workspace, 1)

        self.qa_shape = QComboBox(); self.qa_shape.addItems(["beam", "hss_tube", "angle", "channel", "pipe", "plate"]); self.qa_shape.setVisible(False)
        self.qa_profile = QComboBox(); self.qa_profile.setVisible(False)
        self.qa_qty = QLineEdit("1"); self.qa_qty.setVisible(False)
        self.qa_len = QLineEdit("20.0"); self.qa_len.setVisible(False)
        btn_qa_add = QPushButton("+ Add"); btn_qa_add.setVisible(False)

        cad_status = QFrame()
        cad_status.setFixedHeight(26)
        cad_status.setStyleSheet("QFrame { background-color: #e2e8f0; border: 1px solid #cbd5e1; border-radius: 5px; } QLabel { color: #334155; font-family: 'Consolas', 'Segoe UI', monospace; font-size: 11.5px; font-weight: 600; background: transparent; border: none; }")
        st_l = QHBoxLayout(cad_status)
        st_l.setContentsMargins(10, 0, 10, 0)
        st_l.setSpacing(14)
        self.lbl_cad_coords = QLabel("XY: 0'-0\", 0'-0\"")
        self.lbl_cad_hint = QLabel("READY  |  Middle/Right-Drag: Pan  |  Ctrl+Wheel: Zoom  |  Esc: Reset Tool")
        self.lbl_cad_coords.setFixedWidth(168)
        st_l.addWidget(self.lbl_cad_coords)
        st_l.addWidget(QLabel("|"))
        st_l.addWidget(self.lbl_cad_hint, 1)
        self.btn_stop_scan = QPushButton("Stop Scan")
        self.btn_stop_scan.setVisible(False)
        self.btn_stop_scan.setFixedHeight(20)
        self.btn_stop_scan.setStyleSheet("QPushButton { background-color: #fee2e2; border: 1px solid #dc2626; color: #991b1b; font-size: 11px; font-weight: 700; border-radius: 4px; padding: 0px 8px; } QPushButton:hover { background-color: #fecaca; }")
        self.btn_stop_scan.clicked.connect(self.stop_active_scan)
        st_l.addWidget(self.btn_stop_scan)
        vis_l.addWidget(cad_status)
        self.view_stack.addWidget(vis_page)

        self.btn_tab_bom.clicked.connect(lambda: self._switch_dialog_view(0))
        self.btn_tab_vis.clicked.connect(lambda: self._switch_dialog_view(1))
        if embed_in_main:
            self.vis_workspace.inner_ribbon_box.setVisible(False)
            self._switch_dialog_view(1)

        self.lbl_summary = QLabel("")
        self._cat_nodes = {}
        self.tree.itemChanged.connect(self._on_tree_item_changed)
        self._load_rows_into_tree(extracted_rows)
        self._populate_qa_profiles(self.qa_shape.currentText())

        bottom = QHBoxLayout()
        self._refresh_all_totals()
        bottom.addWidget(self.lbl_summary)
        bottom.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("QPushButton { background-color: #f1f5f9; border: 1.5px solid #64748b; color: #60a5fa; }")
        btn_cancel.clicked.connect(self.reject)
        self.btn_send = QPushButton("Send Checked BOM to Tab 2 Workbench")
        btn_send = self.btn_send
        btn_send.setStyleSheet("QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; } QPushButton:hover { background-color: rgba(167, 243, 208, 0.68); color: #0f172a; }")
        btn_send.clicked.connect(self._accept_checked)
        btn_cancel.setVisible(not embed_in_main)
        bottom.addWidget(btn_cancel)
        bottom.addWidget(btn_send)
        bom_l.addLayout(bottom)

        for _pb in self.findChildren(QPushButton):
            _pb.setAutoDefault(False)
            _pb.setDefault(False)
        self.btn_tab_bom.setToolTip("<b>BOM Staging Tree</b><br>Review, edit quantities/lengths, and check<br>extracted structural members before importing.")
        self.btn_tab_vis.setToolTip("<b>Visual Sheet Preview & Takeoff</b><br>View blueprint sheets, measure spans, count marks,<br>type notes, and color-code steel profiles.")
        self.sheet_combo.setToolTip("<b>Sheet Selector</b><br>Switch between planset pages (Vector Text vs. SHX).")
        self.btn_scan_pg.setToolTip("<b>Auto-Scan Sheet</b><br>Scan the active sheet for structural steel callouts<br>and add them to the BOM Staging Tree.")
        btn_exp.setToolTip("<b>Expand All</b><br>Expand every steel category group in the BOM table.")
        btn_col.setToolTip("<b>Collapse All</b><br>Collapse all steel category groups to summary rows.")
        btn_all.setToolTip("<b>Check All</b><br>Select every item in the BOM table for import.")
        btn_none.setToolTip("<b>Uncheck All</b><br>Clear all checkboxes in the BOM table.")
        btn_split.setToolTip("<b>Duplicate / Split Selected</b><br>Clone the selected row to split lengths or quantities.")
        btn_del.setToolTip("<b>Delete Selected</b><br>Remove the highlighted row from the BOM staging list.")
        self.qa_shape.setToolTip("<b>Member Category</b><br>Choose beam, HSS tube, angle, channel, pipe, or plate.")
        self.qa_profile.setToolTip("<b>Steel Profile</b><br>Pick the AISC designation to add to the BOM.")
        self.qa_qty.setToolTip("<b>Quantity</b><br>Number of pieces (auto-filled by Count Marks).")
        self.qa_len.setToolTip("<b>Length (ft)</b><br>Member length in feet (auto-filled by Measure Span).")
        btn_qa_add.setToolTip("<b>Add to BOM Tree</b><br>Add this member directly into your BOM Staging Tree.")
        btn_cancel.setToolTip("<b>Cancel</b><br>Close this window without importing items.")
        btn_send.setToolTip("<b>Send Checked BOM to Tab 2</b><br>Import all checked rows into your Tab 2 quoting sandbox.")
        self._switch_dialog_view(0 if extracted_rows else 1)
        self.setWindowState(self.windowState() | Qt.WindowMaximized)
        self._set_takeoff_mode("box")
        self._render_current_sheet()

    def reject(self):
        if getattr(self, "_embed_in_main", False):
            if hasattr(self, "vis_workspace"):
                vw = self.vis_workspace
                if hasattr(vw, "canvas"):
                    vw.canvas._inline_editor.hide()
                    vw.canvas._drag_start = None
                    vw.canvas._drag_cur = None
                    vw.canvas._p1 = None
                    vw.canvas._p2 = None
                    vw.canvas.selected_idx = -1
                    vw.canvas.update()
                if hasattr(vw, "set_mode"):
                    vw.set_mode("pan")
            return
        super().reject()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape and getattr(self, "_embed_in_main", False):
            self.reject()
            ev.accept()
            return
        super().keyPressEvent(ev)

    def _switch_dialog_view(self, idx):
        self.view_stack.setCurrentIndex(idx)
        on_s = "QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-weight: 600; padding: 6px 12px; border-radius: 6px; }"
        off_s = "QPushButton { background-color: #eff6ff; border: 1px solid #93c5fd; color: #1e3a8a; font-weight: 600; padding: 6px 12px; border-radius: 6px; }"
        self.btn_tab_bom.setStyleSheet(on_s if idx == 0 else off_s)
        self.btn_tab_vis.setStyleSheet(on_s if idx == 1 else off_s)

    def _set_takeoff_mode(self, mode):
        if hasattr(self, "vis_workspace"):
            self.vis_workspace.set_mode(mode)

    def _handle_count_changed(self, cnt):
        if cnt > 0:
            self.qa_qty.setText(str(cnt))
            self.lbl_summary.setText(f"Count Markers Active: {cnt} item(s) tagged on sheet (Qty auto-updated).")

    def _handle_calibrated(self, pdf_pts):
        known_ft, ok = QInputDialog.getDouble(
            self, "Calibrate Sheet Scale",
            "Enter the true real-world length (in feet) between the two points you clicked:",
            20.0, 0.25, 500.0, 2
        )
        if ok and known_ft > 0:
            new_ppf = pdf_pts / known_ft
            self.viewport.pts_per_ft = new_ppf
            vw = getattr(self, "vis_workspace", None)
            if vw is not None and hasattr(vw, "world_model"):
                pg_n = int(vw.get_page_fn())
                vw.world_model.set_sheet_scale(pg_n, new_ppf)
                if getattr(vw, "_doc", None):
                    ws_new = vw.world_model.get_sheet(vw._doc, pg_n)
                    self.viewport.world_state = ws_new
                    self.viewport.pdf_snap_endpoints = ws_new.snap_endpoints
                    self.viewport.pdf_snap_midpoints = ws_new.snap_midpoints
                    self.viewport.canonical_beam_segs = ws_new.bay_segments
            self.lbl_summary.setText(f"Calibrated Sheet Scale: {new_ppf:.2f} pts/ft ({known_ft:.2f} ft) — synced to BOM & Measure.")
        self._set_takeoff_mode("measure")

    def _update_viewport_scale(self):
        self.viewport.pts_per_ft = float(self.scale_combo.currentData() or 18.0)

    def _render_current_sheet(self):
        if hasattr(self, 'vis_workspace'):
            self.vis_workspace.render_sheet(int(self.sheet_combo.currentData() or 1))

    def _populate_qa_profiles(self, shape_key):
        self.qa_profile.clear()
        items = [x.get("designation", "") for x in self.steel_matrix_data.get(shape_key, []) if x.get("designation")]
        self.qa_profile.addItems(items if items else ["CUSTOM PL 1/2X12X12"])

    def _handle_span_measured(self, span_ft):
        self.qa_len.setText(f"{span_ft:.2f}")
        self.lbl_summary.setText(f"Measured Span: {span_ft:.2f} ft  |  Adjust profile/qty in Quick Add bar and click '+ Add to BOM Tree'.")

    def _start_bg_bom_scan(self, selected_pages, region_clip=None, use_native_ocr=True, mode_tag="sheet", scan_mode=None):
        if getattr(self, "_bg_scan_worker", None) and self._bg_scan_worker.isRunning():
            if hasattr(self, "lbl_cad_hint"):
                self.lbl_cad_hint.setText("BACKGROUND SCAN ALREADY IN PROGRESS — KEEP WORKING FREELY...")
            return
        sm = scan_mode or ("hybrid" if use_native_ocr else "vector")
        engine_names = {
            "vector": "CAD Vector Engine",
            "ocr": "High-DPI OCR Engine",
            "hybrid": "Vector + OCR Hybrid Fusion Engine",
        }
        eng_lbl = "300-DPI Region Engine" if mode_tag == "box" else ("Current-Sheet Engine" if mode_tag == "sheet" else engine_names.get(sm, "Hybrid Engine"))
        scales = getattr(getattr(self, "vis_workspace", None), "sheet_scales", None)
        if hasattr(self, "btn_stop_scan"):
            self.btn_stop_scan.setVisible(True)
        if hasattr(self, "lbl_cad_hint"):
            self.lbl_cad_hint.setText(f"RUNNING {eng_lbl.upper()} — UI STAYS UNLOCKED...")
        if hasattr(self, "lbl_summary"):
            self.lbl_summary.setText(f"{eng_lbl} scanning... (UI stays unlocked)")

        w = _BomBackgroundScanWorker(
            self.pdf_path, get_workspace_path("steel_matrix.json"),
            selected_pages=selected_pages, region_clip=region_clip,
            use_native_ocr=(sm != "vector"), sheet_scales=scales, mode_tag=mode_tag, scan_mode=sm, parent=self
        )
        self._bg_scan_worker = w

        def _on_done(rows, dt, tag):
            if hasattr(self, "btn_stop_scan"):
                self.btn_stop_scan.setVisible(False)
            if getattr(w, "_stop_flag", False):
                if hasattr(self, "lbl_cad_hint"):
                    self.lbl_cad_hint.setText(f"SCAN STOPPED BY USER ({len(rows)} partial group(s) kept)")
                return
            if hasattr(self, "lbl_cad_hint"):
                self.lbl_cad_hint.setText(f"READY ({eng_lbl})  |  Last Scan: {len(rows)} group(s) in {dt:.1f}s")
            if not rows:
                if hasattr(self, "lbl_summary"):
                    self.lbl_summary.setText(f"{eng_lbl} finished in {dt:.1f}s — 0 structural steel callouts detected.")
                return
            if tag == "planset":
                self._load_rows_into_tree(rows)
            elif tag == "sheet":
                target_sheets = {str(r.get("sheet", "")).strip() for r in rows if r.get("sheet")}
                if target_sheets:
                    self._updating_tree = True
                    try:
                        for ti in range(self.tree.topLevelItemCount() - 1, -1, -1):
                            pit = self.tree.topLevelItem(ti)
                            for ci in range(pit.childCount() - 1, -1, -1):
                                if pit.child(ci).text(1).strip() in target_sheets:
                                    pit.removeChild(pit.child(ci))
                            if pit.childCount() == 0:
                                cat_k = pit.data(0, Qt.UserRole)
                                self._cat_nodes.pop(cat_k, None)
                                self.tree.takeTopLevelItem(ti)
                    finally:
                        self._updating_tree = False
                self._append_rows_to_tree(rows)
            else:
                self._append_rows_to_tree(rows)
            if hasattr(self, "lbl_summary"):
                self.lbl_summary.setText(f"{eng_lbl} Complete ({dt:.1f}s): Staged {len(rows)} steel group(s) to BOM Tree.")

        def _on_err(err_msg):
            if hasattr(self, "btn_stop_scan"):
                self.btn_stop_scan.setVisible(False)
            if hasattr(self, "lbl_cad_hint"):
                self.lbl_cad_hint.setText(f"SCAN ERROR ({eng_lbl}): {err_msg}")

        def _on_prog(cur_p, tot_p, sh_lbl, found_cnt):
            pct = int(round((cur_p / max(1, tot_p)) * 100))
            msg = f"{eng_lbl}: Scanning Sheet {cur_p} of {tot_p} ({sh_lbl}) [{pct}%] — {found_cnt} steel group(s) found so far..."
            if hasattr(self, "lbl_cad_hint"):
                self.lbl_cad_hint.setText(msg.upper())
            if hasattr(self, "lbl_summary"):
                self.lbl_summary.setText(msg)

        w.progress_scan.connect(_on_prog)
        w.finished_scan.connect(_on_done)
        w.failed_scan.connect(_on_err)
        w.start()

    def stop_active_scan(self):
        w = getattr(self, "_bg_scan_worker", None)
        if w and w.isRunning():
            w.request_stop()
            if hasattr(self, "lbl_cad_hint"):
                self.lbl_cad_hint.setText("STOPPING SCAN AFTER CURRENT SHEET...")
            if hasattr(self, "btn_stop_scan"):
                self.btn_stop_scan.setVisible(False)

    def _handle_box_ocr(self, clip_rect):
        pdf_p = self.pdf_path or getattr(getattr(self, "vis_workspace", None), "pdf_path", "")
        if not pdf_p or not os.path.exists(pdf_p):
            QMessageBox.information(self, "No PDF Loaded", "Please load a PDF planset first before running Drag & Scan.")
            return
        self.pdf_path = pdf_p
        pg_num = int(self.sheet_combo.currentData() or 1)
        box_mode = "hybrid"
        try:
            if hasattr(self, "_doc") and 1 <= pg_num <= len(self._doc):
                vec_clip_txt = (self._doc.load_page(pg_num - 1).get_text("text", clip=pymupdf.Rect(clip_rect)) or "").strip()
                if len(vec_clip_txt) >= 3:
                    box_mode = "vector"
        except Exception:
            pass
        self._start_bg_bom_scan(selected_pages=[pg_num], region_clip=clip_rect, use_native_ocr=(box_mode != "vector"), mode_tag="box", scan_mode=box_mode)

    def scan_whole_planset(self, use_ocr=True, prompt_if_empty=False, scan_mode=None):
        if not self.pdf_path or not os.path.exists(self.pdf_path):
            self.load_new_pdf_planset()
            return
        import bom_pdf_engine as eng
        sheets = eng.inspect_pdf_sheets(self.pdf_path)
        rec_pages = [s["page"] for s in sheets if s.get("recommended")] or [s["page"] for s in sheets]
        sm = scan_mode or ("hybrid" if use_ocr else "vector")
        self._start_bg_bom_scan(selected_pages=rec_pages, region_clip=None, use_native_ocr=(sm != "vector"), mode_tag="planset", scan_mode=sm)

    def _scan_selected_sheet(self, scan_mode="hybrid"):
        if not self.pdf_path or not os.path.exists(self.pdf_path):
            if hasattr(self, "load_new_pdf_planset"):
                self.load_new_pdf_planset()
            return
        pg_num = int(self.sheet_combo.currentData() or 1)
        self._start_bg_bom_scan(selected_pages=[pg_num], region_clip=None, use_native_ocr=(scan_mode != "vector"), mode_tag="sheet", scan_mode=scan_mode)

    def _add_quick_member_to_tree(self):
        sk = self.qa_shape.currentText()
        prof = self.qa_profile.currentText().strip()
        try:
            qty = max(1, int(float(self.qa_qty.text().strip() or 1)))
            ln = max(0.1, float(self.qa_len.text().strip() or 20.0))
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Enter valid numeric Qty and Length (ft).")
            return
        uw = 28.0
        for it in self.steel_matrix_data.get(sk, []):
            if str(it.get("designation", "")).upper() == prof.upper():
                uw = float(it.get("weight_steel_lb_ft", it.get("weight_per_ft", 28.0)))
                break
        cat_map = {"beam": "Beams", "hss_tube": "HSS & Pipe", "pipe": "HSS & Pipe", "angle": "Angles", "channel": "Channels", "plate": "Plates & Base Plates"}
        raw_sh = self.sheet_combo.currentText()
        pg_lbl = raw_sh.split("(").__getitem__(1).split("-").__getitem__(0).strip() if "(" in raw_sh else "Plan"
        self._append_rows_to_tree([{
            "category": cat_map.get(sk, "Beams"), "sheet": pg_lbl, "detail_ref": "Visual Takeoff",
            "shape_key": sk, "profile": prof, "qty": qty, "length": ln, "unit_wt": uw,
            "plate_w": "12", "plate_thk": "0.5"
        }])
        self._switch_dialog_view(0)

    def reset_to_blank_sheet(self):
        self.pdf_path = ""
        self._doc = pymupdf.open()
        self._doc.new_page(width=1224, height=792)
        if hasattr(self, "vis_workspace"):
            self.vis_workspace.pdf_path = ""
            self.vis_workspace._doc = self._doc
            self.vis_workspace.page_markups = {}
            self.vis_workspace.global_color_key.clear()
            self.vis_workspace.sheet_color_keys.clear()
            self.vis_workspace.canvas.clear_markups()
        if hasattr(self, "sheet_combo"):
            self.sheet_combo.blockSignals(True)
            self.sheet_combo.clear()
            self.sheet_combo.addItem("Pg 1 (Blank Sheet)", 0)
            self.sheet_combo.blockSignals(False)
        if hasattr(self, "tree"):
            self.tree.clear()
            self._cat_nodes = {}
            self._refresh_all_totals()
        self._render_current_sheet()

    def _centered_open_pdf_dialog(self):
        from PySide6.QtWidgets import QFileDialog
        from PySide6.QtCore import QTimer
        win = self.window()
        dlg = QFileDialog(win, "Select Structural PDF Planset", "", "PDF Drawings (*.pdf)")
        dlg.setFileMode(QFileDialog.ExistingFile)
        dlg.resize(900, 560)
        def _center():
            if win is not None:
                c = win.frameGeometry().center()
                dlg.move(c.x() - dlg.width() // 2, c.y() - dlg.height() // 2)
        QTimer.singleShot(0, _center)
        if dlg.exec() == QFileDialog.Accepted and dlg.selectedFiles():
            return dlg.selectedFiles().__getitem__(0), "PDF Drawings (*.pdf)"
        return "", ""

    def load_new_pdf_planset(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import bom_pdf_engine as eng
        fp, _ = self._centered_open_pdf_dialog()
        if not fp:
            return
        try:
            self.pdf_path = fp
            self._doc = pymupdf.open(fp)
            if hasattr(self, "vis_workspace"):
                from core.plan_world import PlanWorldModel
                self.vis_workspace.pdf_path = fp
                self.vis_workspace._doc = self._doc
                self.vis_workspace.world_model = PlanWorldModel(fp)
                self.vis_workspace.sheet_scales = self.vis_workspace.world_model.sheet_scales
                self.vis_workspace.page_markups = {}
            if hasattr(self, "sheet_combo"):
                self.sheet_combo.blockSignals(True)
                self.sheet_combo.clear()
                for s_info in eng.inspect_pdf_sheets(fp):
                    self.sheet_combo.addItem(f"Pg {s_info['page']} ({s_info['sheet']} - {s_info['mode']})", s_info["page"])
                self.sheet_combo.blockSignals(False)
            p_win = self.window()
            if hasattr(p_win, 'master_ribbon') and hasattr(p_win.master_ribbon, 'sync_sheet_list'):
                p_win.master_ribbon.sync_sheet_list([(self.sheet_combo.itemText(i), self.sheet_combo.itemData(i)) for i in range(self.sheet_combo.count())], 0)
            self._render_current_sheet()
            if hasattr(self, "btn_tab_vis"):
                self.btn_tab_vis.click()
        except Exception as ex:
            QMessageBox.critical(self, "PDF Load Error", f"Could not load PDF planset:\n{ex}")

    def _load_rows_into_tree(self, rows):
        self.tree.clear()
        self._cat_nodes = {}
        self._append_rows_to_tree(rows)

    def _append_rows_to_tree(self, rows):
        self._updating_tree = True
        try:
            existing_keys = set()
            for ti in range(self.tree.topLevelItemCount()):
                pit = self.tree.topLevelItem(ti)
                for ci in range(pit.childCount()):
                    ch = pit.child(ci)
                    existing_keys.add((ch.text(1).strip(), ch.text(3).strip(), round(float(ch.text(5) or 0.0), 2)))
            for r in rows:
                r_key = (str(r.get("sheet", "")).strip(), str(r.get("profile", "")).strip(), round(float(r.get("length", 0.0)), 2))
                if r_key in existing_keys:
                    continue
                existing_keys.add(r_key)
                cat = r.get("category", "Beams")
                if cat not in self._cat_nodes:
                    parent_item = QTreeWidgetItem(self.tree)
                    parent_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    parent_item.setCheckState(0, Qt.Checked)
                    fnt = parent_item.font(0)
                    fnt.setBold(True)
                    for c_idx in range(8):
                        parent_item.setFont(c_idx, fnt)
                        parent_item.setBackground(c_idx, QColor("#283548"))
                        parent_item.setForeground(c_idx, QColor("#fbbf24" if c_idx == 0 else "#38bdf8"))
                    parent_item.setText(0, cat)
                    parent_item.setData(0, Qt.UserRole, cat)
                    parent_item.setExpanded(True)
                    self._cat_nodes[cat] = parent_item
                self._append_child_row(self._cat_nodes[cat], r)
            self._refresh_all_totals()
        finally:
            self._updating_tree = False

    def _append_child_row(self, parent_item, r, insert_idx=None):
        child = QTreeWidgetItem()
        child.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
        child.setCheckState(0, Qt.Checked)
        child.setText(0, r.get("shape_key", "beam"))
        child.setText(1, str(r.get("sheet", "")))
        child.setText(2, str(r.get("detail_ref", "")))
        child.setText(3, str(r.get("profile", "")))
        child.setText(4, str(r.get("qty", 1)))
        child.setText(5, str(r.get("length", 0.0)))
        child.setText(6, f"{float(r.get('unit_wt', 0.0)):.2f}")
        child.setData(0, Qt.UserRole, dict(r))
        if insert_idx is not None:
            parent_item.insertChild(insert_idx, child)
        else:
            parent_item.addChild(child)
        return child

    def _on_tree_item_changed(self, item, col):
        if self._updating_tree:
            return
        self._updating_tree = True
        try:
            if item.parent() is None and col == 0:
                state = item.checkState(0)
                for i in range(item.childCount()):
                    item.child(i).setCheckState(0, state)
            self._refresh_all_totals()
        finally:
            self._updating_tree = False

    def _toggle_all(self, state):
        self._updating_tree = True
        try:
            for top_i in range(self.tree.topLevelItemCount()):
                p_item = self.tree.topLevelItem(top_i)
                p_item.setCheckState(0, state)
                for c_i in range(p_item.childCount()):
                    p_item.child(c_i).setCheckState(0, state)
            self._refresh_all_totals()
        finally:
            self._updating_tree = False

    def _duplicate_selected_row(self):
        cur = self.tree.currentItem()
        if not cur or cur.parent() is None:
            return
        parent = cur.parent()
        idx = parent.indexOfChild(cur)
        meta = dict(cur.data(0, Qt.UserRole) or {})
        try:
            q_val = max(1, int(float(cur.text(4))))
        except ValueError:
            q_val = 1
        meta["qty"] = max(1, q_val // 2) if q_val > 1 else 1
        meta["length"] = float(cur.text(5) or 0.0)
        meta["unit_wt"] = float(cur.text(6) or 0.0)
        meta["profile"] = cur.text(3)
        meta["detail_ref"] = cur.text(2)
        self._updating_tree = True
        try:
            if q_val > 1:
                cur.setText(4, str(q_val - meta["qty"]))
            self._append_child_row(parent, meta, insert_idx=idx + 1)
            self._refresh_all_totals()
        finally:
            self._updating_tree = False

    def _remove_selected_row(self):
        cur = self.tree.currentItem()
        if not cur:
            return
        self._updating_tree = True
        try:
            if cur.parent() is None:
                idx = self.tree.indexOfTopLevelItem(cur)
                self.tree.takeTopLevelItem(idx)
            else:
                parent = cur.parent()
                parent.removeChild(cur)
                if parent.childCount() == 0:
                    self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(parent))
            self._refresh_all_totals()
        finally:
            self._updating_tree = False

    def _refresh_all_totals(self):
        total_pcs, total_wt = 0, 0.0
        for top_i in range(self.tree.topLevelItemCount()):
            p_item = self.tree.topLevelItem(top_i)
            cat_base = p_item.data(0, Qt.UserRole) or p_item.text(0).split(" (")[0][0]
            cat_pcs, cat_wt = 0, 0.0
            for c_i in range(p_item.childCount()):
                ch = p_item.child(c_i)
                try:
                    q = max(0, int(float(ch.text(4))))
                    ln = max(0.0, float(ch.text(5)))
                    uw = max(0.0, float(ch.text(6)))
                except ValueError:
                    q, ln, uw = 0, 0.0, 0.0
                row_wt = q * ln * uw
                ch.setText(7, f"{row_wt:,.1f}")
                if ch.checkState(0) == Qt.Checked:
                    cat_pcs += q
                    cat_wt += row_wt
            p_item.setText(0, f"{cat_base} ({p_item.childCount()} rows | {cat_pcs} pcs)")
            p_item.setText(7, f"{cat_wt:,.1f} lbs")
            total_pcs += cat_pcs
            total_wt += cat_wt
        self.lbl_summary.setText(f"Checked BOM Totals: {total_pcs} pcs  |  {total_wt:,.1f} lbs")
        if hasattr(self, "smart_summary_panel"):
            self.smart_summary_panel.refresh_from_tree(self.tree)

    def _jump_to_sheet_from_bom(self, sheet_label, highlight_profile=None):
        target = str(sheet_label).strip().upper()
        for idx in range(self.sheet_combo.count()):
            txt = self.sheet_combo.itemText(idx).upper()
            if f"({target} " in txt or f"({target}-" in txt or target in txt:
                self.sheet_combo.setCurrentIndex(idx)
                break
        self._switch_dialog_view(1)
        if hasattr(self, "vis_workspace"):
            self.vis_workspace.highlight_profile_and_fit(highlight_profile or "")

    def _jump_to_profile_from_bom(self, profile_name, sheet_label):
        self._jump_to_sheet_from_bom(sheet_label, highlight_profile=profile_name)

    def _on_bom_row_double_clicked(self, item, col):
        if item.parent() is not None and col in (0, 1, 2, 3):
            self._jump_to_sheet_from_bom(item.text(1), highlight_profile=item.text(3))

    def _accept_checked(self):
        self.accepted_rows = []
        for top_i in range(self.tree.topLevelItemCount()):
            p_item = self.tree.topLevelItem(top_i)
            for c_i in range(p_item.childCount()):
                ch = p_item.child(c_i)
                if ch.checkState(0) != Qt.Checked:
                    continue
                meta = dict(ch.data(0, Qt.UserRole) or {})
                try:
                    qty = max(1, int(float(ch.text(4))))
                    length = max(0.1, float(ch.text(5)))
                    unit_wt = max(0.01, float(ch.text(6)))
                except ValueError:
                    continue
                meta["shape_key"] = ch.text(0).strip() or meta.get("shape_key", "beam")
                meta["sheet"] = ch.text(1).strip()
                meta["detail_ref"] = ch.text(2).strip()
                meta["profile"] = ch.text(3).strip()
                meta["qty"] = qty
                meta["length"] = length
                meta["unit_wt"] = unit_wt
                self.accepted_rows.append(meta)
        if not self.accepted_rows:
            QMessageBox.warning(self, "No Rows Selected", "Please check at least one BOM row to send to Tab 2.")
            return
        p_win = self.window()
        if hasattr(p_win, "custom_quoting_tab") and hasattr(p_win, "master_tabs"):
            if hasattr(p_win.custom_quoting_tab, "ingest_pdf_bom_items"):
                p_win.custom_quoting_tab.ingest_pdf_bom_items(self.accepted_rows)
            p_win.master_tabs.setCurrentWidget(p_win.custom_quoting_tab)
            if hasattr(p_win, "master_ribbon"):
                p_win.master_ribbon.set_active_tab(2)
            return
        self.accept()

class StructuralQuotingSandbox(QWidget):
    def __init__(self, finalize_project_callback, admin_safeguards_reference, parent=None):
        super().__init__(parent)
        self.steel_matrix_data = {}
        self.current_project_items = []
        self.finalize_project_callback = finalize_project_callback
        self.safeguards = admin_safeguards_reference

        self.setObjectName("StructuralQuotingSandbox")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(SANDBOX_MEMBER_STYLESHEET + "\nQWidget#StructuralQuotingSandbox { background: transparent !important; }")
        self.build_workspace_ui()
        self.load_steel_json_matrix()

    def _append_default_scope_note(self):
        clause = str(self.safeguards.get("std_scope_clause_t2", "Furnished FOB Seattle, WA. Includes shop fabrication per AISC standards; excludes field erection, field welding, and anchor bolts unless itemized above.")).strip()
        cur = self.estimator_notes_edit.toPlainText().strip()
        self.estimator_notes_edit.setPlainText((cur + "\n" + clause).strip() if cur else clause)

    def build_workspace_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(15)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        scroll.setStyleSheet("background-color: transparent; border: none;")
        container = QWidget()
        container.setObjectName("LeftScrollContainer")
        container.setStyleSheet("background-color: transparent;")
        self.deck_layout = QVBoxLayout(container)
        self.deck_layout.setSpacing(12)

        cust_card = QWidget()
        cust_card.setStyleSheet("background-color: rgba(248, 250, 252, 0.80); border: 1px solid #cbd5e1; border-radius: 8px;")
        cust_grid = QGridLayout(cust_card)
        cust_grid.addWidget(QLabel("Customer Name:"), 0, 0)
        self.input_cust_name = QLineEdit()
        self.input_cust_name.setPlaceholderText("Customer Name / Company...")
        cust_grid.addWidget(self.input_cust_name, 0, 1)

        cust_grid.addWidget(QLabel("Project Name:"), 1, 0)
        self.input_proj_name = QLineEdit()
        self.input_proj_name.setPlaceholderText("Project Reference / Bid ID...")
        cust_grid.addWidget(self.input_proj_name, 1, 1)
        self.btn_import_pdf_bom = QPushButton("Import Structural PDF Planset (BOM)")
        self.btn_import_pdf_bom.setStyleSheet(
            "QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; "
            "font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; padding: 8px 14px; border-radius: 6px; } "
            "QPushButton:hover { background-color: rgba(96, 165, 250, 0.82); color: #0f172a; }"
        )
        self.btn_import_pdf_bom.clicked.connect(self.open_pdf_bom_importer)
        cust_grid.addWidget(self.btn_import_pdf_bom, 2, 0, 1, 2)
        self.deck_layout.addWidget(cust_card)

        global_card = QWidget()
        global_card.setStyleSheet("background-color: rgba(248, 250, 252, 0.80); border: 1px solid #cbd5e1; border-radius: 8px;")
        g_grid = QGridLayout(global_card)
        g_grid.addWidget(QLabel("Steel Shape:"), 0, 0)
        self.combo_picker = QComboBox()
        self.combo_picker.addItems(["beam", "channel", "hss_tube", "angle", "pipe", "flat_bar", "round_bar", "square_bar", "plate"])
        self.combo_picker.currentIndexChanged.connect(self.handle_card_context_swap)
        g_grid.addWidget(self.combo_picker, 0, 1)

        g_grid.addWidget(QLabel("Alloy Grade:"), 0, 2)
        self.combo_alloy = QComboBox()
        self.combo_alloy.addItems(["Carbon Steel", "304 Stainless", "316 Stainless"])
        g_grid.addWidget(self.combo_alloy, 0, 3)

        g_grid.addWidget(QLabel("Run Qty:"), 1, 0)
        self.input_run_qty = QLineEdit("1")
        g_grid.addWidget(self.input_run_qty, 1, 1)
        g_grid.addWidget(QLabel("Steel Rate $/lb:"), 1, 2)
        self.input_lb_rate = QLineEdit("1.30")
        g_grid.addWidget(self.input_lb_rate, 1, 3)
        self.deck_layout.addWidget(global_card)

        self.active_member_card = DynamicMemberCard(calc_callback=self.execute_fabrication_math_routine, parent=self)
        self.deck_layout.addWidget(self.active_member_card)
        self.deck_layout.addStretch()
        scroll.setWidget(container)
        self.t2_splitter = QSplitter(Qt.Horizontal)
        self.t2_splitter.setHandleWidth(8)
        self.t2_splitter.setChildrenCollapsible(False)
        self.t2_splitter.setStyleSheet("QSplitter { background: transparent; } QSplitter::handle { background-color: rgba(56, 189, 248, 0.30); border-radius: 3px; margin: 4px 1px; } QSplitter::handle:hover { background-color: #0369a1; }")
        scroll.setMinimumWidth(340)
        self.t2_splitter.addWidget(scroll)

        right_container = QWidget()
        right_container.setAttribute(Qt.WA_StyledBackground, True)
        right_container.setStyleSheet("background: transparent !important;")
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        hdr_card = QWidget()
        hdr_card.setStyleSheet("background-color: rgba(248, 250, 252, 0.80); border: 1px solid #cbd5e1; border-radius: 8px;")
        hdr_layout = QHBoxLayout(hdr_card)
        hdr_layout.setContentsMargins(10, 6, 10, 6)
        self.lbl_wb_header = QLabel("WORKBENCH: RETAIL CUSTOMER | STANDARD BUILD")
        self.lbl_wb_header.setStyleSheet("font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; color: #0369a1; background: transparent; border: none;")
        hdr_layout.addWidget(self.lbl_wb_header)
        hdr_layout.addStretch()

        self._wb_expanded = True
        self.btn_toggle_expand = QPushButton("Collapse All")
        self.btn_toggle_expand.setStyleSheet("background-color: rgba(239, 246, 255, 0.72); border: 2px solid #0284c7; color: #000000; font-weight: 700; font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 5px;")
        self.btn_toggle_expand.clicked.connect(self.toggle_all_tree_items)
        hdr_layout.addWidget(self.btn_toggle_expand)
        right_layout.addWidget(hdr_card)

        self.struct_fx_bar = FormulaHudBar(self)
        right_layout.addWidget(self.struct_fx_bar)
        self.ledger_tree = QTreeWidget()
        apply_excel_table_style(self.ledger_tree)
        self.ledger_tree.currentItemChanged.connect(self._on_t2_fx_selection_changed)
        self.ledger_tree.itemClicked.connect(lambda it, col: self._on_t2_fx_selection_changed(it, None))
        self.ledger_tree.setColumnCount(4)
        self.ledger_tree.setHeaderLabels(["PART / DESCRIPTION", "SHIP WEIGHT", "RAW COST", ""])
        self.ledger_tree.setRootIsDecorated(True)
        self.ledger_tree.setTextElideMode(Qt.ElideNone)
        self.ledger_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ledger_tree.itemDoubleClicked.connect(lambda *_: self.edit_selected_project_item())
        self.ledger_tree.header().setStretchLastSection(False)
        self.ledger_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.ledger_tree.setColumnWidth(1, 112)
        self.ledger_tree.setColumnWidth(2, 115)
        self.ledger_tree.header().setSectionResizeMode(1, QHeaderView.Interactive)
        self.ledger_tree.header().setSectionResizeMode(2, QHeaderView.Interactive)
        self.ledger_tree.header().setSectionResizeMode(3, QHeaderView.Fixed)
        self.ledger_tree.setColumnWidth(3, 36)
        self.ledger_tree.setStyleSheet("""
            QTreeWidget { background-color: rgba(248, 250, 252, 0.80) !important; color: #0f172a !important; border: 1px solid #cbd5e1; border-radius: 8px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; padding: 4px; }
            QTreeWidget::viewport, QTreeWidget QWidget { background: transparent !important; }
            QTreeWidget::item { padding: 4px 2px; border-bottom: 1px solid rgba(51, 65, 85, 0.45); }
            QHeaderView::section { background-color: rgba(207, 228, 250, 0.85); color: #0369a1; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; padding: 6px; border: none; border-bottom: 1px solid #60a5fa; }
        """)
        self.ledger_tree.expanded.connect(lambda *_: self.ledger_tree.viewport().update())
        self.ledger_tree.collapsed.connect(lambda *_: self.ledger_tree.viewport().update())
        self.ledger_tree.verticalScrollBar().valueChanged.connect(lambda *_: self.ledger_tree.viewport().update())
        right_layout.addWidget(self.ledger_tree, 1)

        t2_item_ops = QHBoxLayout()
        t2_item_ops.setSpacing(8)
        btn_t2_dup = QPushButton("Duplicate Selected Item")
        btn_t2_dup.setStyleSheet("background-color: rgba(239, 246, 255, 0.72); border: 2px solid #0284c7; color: #000000; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 6px;")
        btn_t2_dup.clicked.connect(self.duplicate_selected_project_item)
        btn_t2_edit = QPushButton("Edit Selected Item")
        btn_t2_edit.setStyleSheet("background-color: #ffffff; border: 1px solid #94a3b8; color: #0f172a; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 6px;")
        btn_t2_edit.clicked.connect(self.edit_selected_project_item)
        t2_item_ops.addWidget(btn_t2_dup, 1)
        self.btn_waive_sub = QPushButton("Waive / Restore Sub-Line Cost")
        self.btn_waive_sub.setStyleSheet("QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; border-radius: 6px; padding: 6px 10px; } QPushButton:hover { background-color: #e0f2fe; color: #0369a1; }")
        self.btn_waive_sub.clicked.connect(self.toggle_selected_subline_waive)
        t2_item_ops.addWidget(self.btn_waive_sub)
        t2_item_ops.addWidget(btn_t2_edit, 1)
        right_layout.addLayout(t2_item_ops)

        totals_card = QWidget()
        totals_card.setStyleSheet("background-color: #ffffff; border: 1.5px solid #94a3b8; border-radius: 6px;")
        t_grid = QGridLayout(totals_card)
        t_grid.setContentsMargins(12, 8, 12, 8)
        t_grid.setVerticalSpacing(3)

        m_lbl = "font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; color: #1e3a8a; background: transparent; border: none;"
        m_val = "font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; color: #0f172a; background: transparent; border: none;"
        g_lbl = "font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; color: #0369a1; background: transparent; border: none;"

        self.lbl_tot_wgt = QLabel("0.0 lbs")
        self.lbl_tot_mat = QLabel("$0.00")
        self.lbl_tot_mach = QLabel("$0.00")
        self.lbl_tot_lab = QLabel("$0.00")
        self.lbl_tot_fin = QLabel("$0.00")
        self.lbl_tot_sub = QLabel("$0.00")
        self.lbl_tot_mkp = QLabel("$0.00")
        self.lbl_tot_grand = QLabel("$0.00")
        self.lbl_markup_title = QLabel("BID MARKUP (40%):")
        for r_i, (t_txt, v_w, lc, vc) in enumerate([
            ("ACTUAL SHIP WEIGHT:", self.lbl_tot_wgt, m_lbl, m_val),
            ("RAW STEEL MATERIALS:", self.lbl_tot_mat, m_lbl, m_val),
            ("RAW SHOP MACHINING:", self.lbl_tot_mach, m_lbl, m_val),
            ("RAW SHOP & ENG. LABOR:", self.lbl_tot_lab, m_lbl, m_val),
            ("RAW COATING & FINISH:", self.lbl_tot_fin, m_lbl, m_val),
            ("COMBINED RAW SUBTOTAL:", self.lbl_tot_sub, m_lbl, m_val),
            (None, self.lbl_tot_mkp, m_lbl, m_val),
            ("TOTAL CUSTOMER QUOTE:", self.lbl_tot_grand, g_lbl, g_lbl),
        ]):
            lw = self.lbl_markup_title if t_txt is None else QLabel(t_txt)
            lw.setStyleSheet(lc)
            v_w.setStyleSheet(vc)
            v_w.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            t_grid.addWidget(lw, r_i, 0)
            t_grid.addWidget(v_w, r_i, 1)
        notes_hdr = QHBoxLayout()
        nh_lbl = QLabel("ESTIMATOR NOTES & CUSTOMER SCOPE (Saved to Ledger & Customer PDF):")
        nh_lbl.setStyleSheet("color: #0369a1; font-size: 12px; font-weight: 700; background: transparent; border: none;")
        notes_hdr.addWidget(nh_lbl); notes_hdr.addStretch()
        self.btn_add_std_note = QPushButton("+ Insert Standard Scope Clause")
        self.btn_add_std_note.setStyleSheet("background-color: rgba(239, 246, 255, 0.85); border: 1px solid #60a5fa; color: #0f172a; font-size: 12px; font-weight: 700; border-radius: 4px; padding: 2px 8px;")
        self.btn_add_std_note.clicked.connect(self._append_default_scope_note)
        notes_hdr.addWidget(self.btn_add_std_note)
        right_layout.addLayout(notes_hdr)

        self.estimator_notes_edit = QTextEdit()
        self.estimator_notes_edit.setPlaceholderText("Click here to type estimator scope notes, lead times, delivery terms, or exclusions to include on the Running Ledger & Customer PDF...")
        self.estimator_notes_edit.setMaximumHeight(58)
        self.estimator_notes_edit.setStyleSheet("QTextEdit { background-color: rgba(239, 246, 255, 0.82); color: #0f172a; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px 8px; font-size: 14px; font-weight: 600; }")
        right_layout.addWidget(self.estimator_notes_edit)
        right_layout.addWidget(totals_card)

        eng_card = QWidget()
        eng_card.setAttribute(Qt.WA_StyledBackground, True)
        eng_card.setStyleSheet("""
            QWidget { background-color: rgba(248, 250, 252, 0.80) !important; border: 1px solid #cbd5e1; border-radius: 8px; }
            QLabel { background: transparent !important; border: none !important; color: #0f172a; font-weight: 600; }
            QLineEdit { background-color: #eff6ff !important; border: 1px solid #cbd5e1; border-radius: 5px; color: #0f172a; padding: 4px 6px; font-weight: 600; }
        """)
        eng_layout = QHBoxLayout(eng_card)
        eng_layout.setContentsMargins(10, 8, 10, 8)
        eng_layout.addWidget(QLabel("Programming Hrs:"))
        self.input_prog_hrs = QLineEdit("0")
        self.input_prog_hrs.setFixedWidth(55)
        self.input_prog_hrs.textChanged.connect(self.sync_local_workbench_view)
        eng_layout.addWidget(self.input_prog_hrs)

        eng_layout.addWidget(QLabel("Detailing Hrs:"))
        self.input_detail_hrs = QLineEdit("0")
        self.input_detail_hrs.setFixedWidth(55)
        self.input_detail_hrs.textChanged.connect(self.sync_local_workbench_view)
        eng_layout.addWidget(self.input_detail_hrs)
        eng_layout.addStretch()
        right_layout.addWidget(eng_card)

        self.btn_finalize_quote = QPushButton("FINALIZE && SAVE QUOTE")
        self.btn_finalize_quote.setObjectName("PrimaryAction")
        self.btn_finalize_quote.setMinimumHeight(45)
        self.btn_finalize_quote.setStyleSheet("QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 10px; } QPushButton:hover { background-color: rgba(96, 165, 250, 0.82); color: #0f172a; }")
        self.btn_finalize_quote.clicked.connect(self.pack_and_finalize_project_quote)
        right_layout.addWidget(self.btn_finalize_quote)

        draft_bar = QHBoxLayout()
        draft_bar.setSpacing(6)
        self.btn_save_draft = QPushButton("Save Quote Draft")
        self.btn_save_draft.setStyleSheet("QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; border-radius: 6px; padding: 8px; } QPushButton:hover { background-color: #e0f2fe; }")
        self.btn_save_draft.clicked.connect(self.save_structural_draft)
        draft_bar.addWidget(self.btn_save_draft, 1)

        self.btn_load_draft = QPushButton("Resume Draft")
        self.btn_load_draft.setStyleSheet("QPushButton { background-color: #ffffff; border: 1.5px solid #0369a1; color: #0369a1; font-weight: 700; border-radius: 6px; padding: 8px; } QPushButton:hover { background-color: #e0f2fe; }")
        self.btn_load_draft.clicked.connect(self.load_structural_draft)
        draft_bar.addWidget(self.btn_load_draft, 1)
        right_layout.addLayout(draft_bar)

        self.btn_clear_canvas = QPushButton("Clear Current Quote")
        self.btn_clear_canvas.setObjectName("DangerAction")
        self.btn_clear_canvas.setStyleSheet("QPushButton { background-color: #ffffff; border: 1px solid #fca5a5; color: #b91c1c; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 8px; } QPushButton:hover { background-color: rgba(252, 165, 165, 0.84); color: #7f1d1d; }")
        self.btn_clear_canvas.clicked.connect(self.clear_canvas_session)
        right_layout.addWidget(self.btn_clear_canvas)

        right_container.setMinimumWidth(340)
        self.t2_splitter.addWidget(right_container)
        self.t2_splitter.setSizes([620, 580])
        self.main_layout.addWidget(self.t2_splitter)
        self.sync_local_workbench_view()

    def load_steel_json_matrix(self):
        matrix_path = get_workspace_path("steel_matrix.json")
        if not os.path.exists(matrix_path):
            QMessageBox.warning(self, "Missing Matrix File", f"Could not find steel_matrix.json at:\n{matrix_path}")
            return
        try:
            with open(matrix_path, "r", encoding="utf-8") as f:
                self.steel_matrix_data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "JSON Syntax Error", f"Error reading steel_matrix.json:\n{e}")
        self.handle_card_context_swap()

    def handle_card_context_swap(self):
        self.active_member_card.update_card_context(self.combo_picker.currentText(), self.steel_matrix_data)

    def _prewarm_ocr_engine(self):
        if hasattr(self, "_rapid_ocr_engine"):
            return
        try:
            from rapidocr_onnxruntime import RapidOCR
            try:
                self._rapid_ocr_engine = RapidOCR(intra_op_num_threads=max(2, os.cpu_count() or 4))
            except TypeError:
                try:
                    self._rapid_ocr_engine = RapidOCR(det_use_dml=True, cls_use_dml=True, rec_use_dml=True)
                except Exception:
                    try:
                        self._rapid_ocr_engine = RapidOCR(use_dml=True)
                    except Exception:
                        self._rapid_ocr_engine = RapidOCR()
        except Exception:
            pass

    def ingest_pdf_bom_items(self, bom_rows):
        if not bom_rows:
            return
        try:
            rate_per_lb = float(self.input_lb_rate.text().strip() or 1.30)
        except ValueError:
            rate_per_lb = 1.30
        base_rate = float(self.safeguards.get("base_labor_rate", 86.0))
        handling_mins = float(self.safeguards.get("handling_mins_per_pc", 15.0))
        primer_rate = float(self.safeguards.get("primer_rate_per_lb", 0.12))

        for r in bom_rows:
            sk = r.get("shape_key", "beam")
            prof = r.get("profile", "")
            qty = max(1, int(r.get("qty", 1)))
            ln_ft = float(r.get("length", 20.0))
            uw = float(r.get("unit_wt", 28.0))
            sh_ref = f"{r.get('sheet', '')} ({r.get('detail_ref', 'Typ.')})"

            if sk == "plate":
                pw = float(r.get("plate_w", 12.0) or 12.0)
                pt = float(r.get("plate_thk", 0.5) or 0.5)
                pl_in = round(ln_ft * 12.0, 2)
                _, act_wgt, mat_c = BidFormMathEngine.calculate_plate(qty, pl_in, pw, pt, rate_per_lb, "Carbon Steel")
                bill_wgt = act_wgt
                lbl = f"{prof} ({pl_in:g}\"x{pw:g}\"x{pt:g}\") (x{qty})"
            else:
                bill_ft = BidFormMathEngine.calculate_billable_length(sk, ln_ft, qty)
                act_wgt = uw * ln_ft * qty
                bill_wgt = uw * bill_ft
                mat_c = bill_wgt * rate_per_lb
                lbl = f"{ln_ft:g}' {prof} (x{qty})"

            heavy_cut = float(self.safeguards.get("heavy_weight_cutoff", 40.0))
            light_hm = float(self.safeguards.get("light_handling_mins_per_pc", 0.75))
            u_pc_w = act_wgt / max(1, qty)
            tot_hm = (handling_mins + max(0, qty - 1) * (handling_mins * 0.5)) if u_pc_w >= heavy_cut else (min(3.0, handling_mins * 0.25) + light_hm * qty)
            hand_c = round((tot_hm / 60.0) * base_rate, 2)
            prim_c = round(act_wgt * primer_rate, 2)
            lab_c = round(hand_c + prim_c, 2)
            sub_rows = [
                {
                    "label": f"Shop Handling ({handling_mins:g}m/pc)",
                    "cost": hand_c,
                    "ea_cost": round(hand_c / max(1, qty), 2),
                    "category": "labor",
                    "formula": f"Handling: ({handling_mins:g} mins / 60) x ${base_rate:.2f}/hr x {qty} pcs = ${hand_c:,.2f}",
                },
                {
                    "label": f"Shop Primer (${primer_rate:.2f}/lb)",
                    "cost": prim_c,
                    "ea_cost": round(prim_c / max(1, qty), 2),
                    "category": "finish",
                    "formula": f"Shop Primer: {act_wgt:,.1f} lbs x ${primer_rate:.2f}/lb = ${prim_c:,.2f}",
                },
            ]
            self.current_project_items.append({
                "model": lbl,
                "weight": round(act_wgt, 1),
                "billable_weight": round(bill_wgt, 1),
                "main_mat_cost": round(mat_c, 2),
                "addon_mat_cost": 0.0,
                "mat_cost": round(mat_c, 2),
                "waived_keys": [],
                "machining_cost": 0.0,
                "fab_labor_cost": hand_c,
                "finish_cost": prim_c,
                "labor_cost": lab_c,
                "cost": round(mat_c + lab_c, 2),
                "addons": f"Shop Primer (${primer_rate:.2f}/lb), Sheet {sh_ref}",
                "subline_details": sub_rows,
                "form_state": {
                    "shape_key": sk, "model": prof, "qty": qty, "length": str(ln_ft),
                    "plate_w": str(r.get("plate_w", "12")), "plate_thk": str(r.get("plate_thk", "")),
                    "alloy": "Carbon Steel", "steel_rate": f"{rate_per_lb:.2f}",
                    "primer": True, "pc": False, "hdg": False, "custom_mill": "", "addons_list": []
                }
            })
        self.sync_local_workbench_view()

    def open_pdf_bom_importer(self):
        p_win = self.window()
        if hasattr(p_win, "planset_takeoff_tab") and hasattr(p_win, "master_tabs"):
            p_win.master_tabs.setCurrentWidget(p_win.planset_takeoff_tab)
            if hasattr(p_win, "master_ribbon"):
                p_win.master_ribbon.set_active_tab(0)
            p_win.planset_takeoff_tab.load_new_pdf_planset()
            return
        import bom_pdf_engine as eng

        pdf_path, _ = QFileDialog.getOpenFileName(
            self, "Select Structural PDF Planset", "", "PDF Files (*.pdf)"
        )
        if not pdf_path:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            sheet_list = eng.inspect_pdf_sheets(pdf_path)
            rec_pages = [x["page"] for x in sheet_list if x["recommended"]] or [x["page"] for x in sheet_list]
            rows, dt, from_cache = eng.extract_full_bom(
                pdf_path, matrix_path=get_workspace_path("steel_matrix.json"), selected_pages=rec_pages
            )
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "PDF BOM Import Error", f"Could not read PDF planset:\n{exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        # Opens directly on Visual Sheet Preview when 0 vector rows found

        dlg = PdfBomImporterDialog(pdf_path, rows, self.steel_matrix_data, self)
        if dlg.exec() != QDialog.Accepted or not dlg.accepted_rows:
            return

        try:
            rate_per_lb = float(self.input_lb_rate.text().strip() or 1.30)
        except ValueError:
            rate_per_lb = 1.30
        base_rate = float(self.safeguards.get("base_labor_rate", 86.0))
        handling_mins = float(self.safeguards.get("handling_mins_per_pc", 15.0))
        primer_rate = float(self.safeguards.get("primer_rate_per_lb", 0.12))

        for r in dlg.accepted_rows:
            sk = r.get("shape_key", "beam")
            prof = r.get("profile", "")
            qty = max(1, int(r.get("qty", 1)))
            ln_ft = float(r.get("length", 20.0))
            uw = float(r.get("unit_wt", 28.0))
            sh_ref = f"{r.get('sheet', '')} ({r.get('detail_ref', 'Typ.')})"

            if sk == "plate":
                pw = float(r.get("plate_w", 12.0) or 12.0)
                pt = float(r.get("plate_thk", 0.5) or 0.5)
                pl_in = round(ln_ft * 12.0, 2)
                _, act_wgt, mat_c = BidFormMathEngine.calculate_plate(qty, pl_in, pw, pt, rate_per_lb, "Carbon Steel")
                bill_wgt = act_wgt
                lbl = f"{prof} ({pl_in:g}\"x{pw:g}\"x{pt:g}\") (x{qty})"
            else:
                bill_ft = BidFormMathEngine.calculate_billable_length(sk, ln_ft, qty)
                act_wgt = uw * ln_ft * qty
                bill_wgt = uw * bill_ft
                mat_c = bill_wgt * rate_per_lb
                lbl = f"{ln_ft:g}' {prof} (x{qty})"

            lab_c = ((handling_mins / 60.0) * base_rate * qty) + (act_wgt * primer_rate)
            self.current_project_items.append({
                "model": lbl,
                "weight": round(act_wgt, 1),
                "billable_weight": round(bill_wgt, 1),
                "mat_cost": round(mat_c, 2),
                "labor_cost": round(lab_c, 2),
                "cost": round(mat_c + lab_c, 2),
                "addons": f"Shop Primer (${primer_rate:.2f}/lb), Sheet {sh_ref}",
                "form_state": {
                    "shape_key": sk, "model": prof, "qty": qty, "length": str(ln_ft),
                    "plate_w": str(r.get("plate_w", "12")), "plate_thk": str(r.get("plate_thk", "")),
                    "alloy": "Carbon Steel", "steel_rate": f"{rate_per_lb:.2f}",
                    "primer": True, "pc": False, "hdg": False, "custom_mill": "", "addons_list": []
                }
            })

        self.sync_local_workbench_view()

    def _structural_draft_path(self):
        d = os.path.join(get_workspace_path(), "config")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "draft_structural.json")

    def _on_t2_fx_selection_changed(self, cur, prev):
        if getattr(self, "_suppress_t2_fx_sel", False):
            return
        if cur is None:
            self.struct_fx_bar.set_formula("ACTIVE", "Click any main line or sub-line to inspect its live cost & formula...")
            return
        parent = cur.parent()
        fx_detail = cur.data(0, Qt.UserRole + 1)
        if parent is None:
            r_idx = self.ledger_tree.indexOfTopLevelItem(cur)
            if 0 <= r_idx < len(self.current_project_items):
                import re as _re_fx
                raw_m = str(self.current_project_items[r_idx].get("model", ""))
                clean_m = _re_fx.sub(r"\s*\[\$[0-9,]+\.\d{2}\s*ea\]", "", raw_m).strip()
                def _save_t2_main(new_v, i=r_idx):
                    if 0 <= i < len(self.current_project_items):
                        self.current_project_items[i]["model"] = new_v
                        self._suppress_t2_fx_sel = True
                        self.sync_local_workbench_view()
                        if i < self.ledger_tree.topLevelItemCount():
                            self.ledger_tree.setCurrentItem(self.ledger_tree.topLevelItem(i))
                        self._suppress_t2_fx_sel = False
                self.struct_fx_bar.set_formula(f"ROW {r_idx + 1}", str(fx_detail or clean_m))
        else:
            p_idx = self.ledger_tree.indexOfTopLevelItem(parent)
            c_idx = parent.indexOfChild(cur)
            disp_fx = str(fx_detail or cur.text(0).lstrip("- ").strip())
            self.struct_fx_bar.set_formula(f"ROW {p_idx + 1}.{c_idx + 1}", disp_fx)

    def save_structural_draft(self, silent=False):
        payload = {
            "customer": self.input_cust_name.text().strip(),
            "project": self.input_proj_name.text().strip(),
            "notes": self.estimator_notes_edit.toPlainText() if hasattr(self, "estimator_notes_edit") else "",
            "lb_rate": self.input_lb_rate.text().strip(),
            "prog_hrs": self.input_prog_hrs.text().strip(),
            "detail_hrs": self.input_detail_hrs.text().strip(),
            "items": self.current_project_items,
        }
        with open(self._structural_draft_path(), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        if not silent:
            QMessageBox.information(self, "Draft Saved", f"Saved quote draft ({len(self.current_project_items)} member(s)) safely to disk. You can resume it anytime.")

    def load_structural_draft(self):
        dp = self._structural_draft_path()
        if not os.path.exists(dp):
            QMessageBox.information(self, "No Saved Draft", "No saved structural quote draft was found on disk.")
            return
        if self.current_project_items:
            ans = QMessageBox.question(self, "Replace Unsaved Quote?", "You currently have unsaved items in your active quote. Loading the saved draft will overwrite them. Continue?", QMessageBox.Yes | QMessageBox.No)
            if ans != QMessageBox.Yes:
                return
        with open(dp, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        self.input_cust_name.setText(data.get("customer", ""))
        self.input_proj_name.setText(data.get("project", ""))
        if hasattr(self, "estimator_notes_edit"):
            self.estimator_notes_edit.setPlainText(data.get("notes", ""))
        self.input_lb_rate.setText(data.get("lb_rate", "1.30"))
        self.input_prog_hrs.setText(data.get("prog_hrs", "0"))
        self.input_detail_hrs.setText(data.get("detail_hrs", "0"))
        self.current_project_items = list(data.get("items", []))
        self.sync_local_workbench_view()
        QMessageBox.information(self, "Draft Restored", f"Restored {len(self.current_project_items)} member(s) from your saved draft.")

    def clear_canvas_session(self):
        if hasattr(self.parent(), '_editing_quote_num'): self.parent()._editing_quote_num = None
        if self.current_project_items:
            ans = QMessageBox.question(self, "Confirm Clear Workspace", f"Clear all {len(self.current_project_items)} item(s) from the active workspace?", QMessageBox.Yes | QMessageBox.No)
            if ans != QMessageBox.Yes:
                return
        try:
            if os.path.exists(self._structural_draft_path()): os.remove(self._structural_draft_path())
        except Exception:
            pass
        self.current_project_items.clear()
        self.input_cust_name.clear()
        self.input_proj_name.clear()
        if hasattr(self, "estimator_notes_edit"):
            self.estimator_notes_edit.clear()
        self.input_prog_hrs.setText("0")
        self.input_detail_hrs.setText("0")
        self._reset_member_builder_panel(reset_steel_rate=True)
        self.sync_local_workbench_view()

    def verify_safeguard_override(self, warning_message):
        reply = QMessageBox.question(
            self, "Shop Safeguard Gate Triggered",
            f"{warning_message}\n\nDo you have Foreman/Admin override authorization?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            pwd, ok = QInputDialog.getText(self, "Admin Override", "Enter Administrative Passcode:", QLineEdit.Password)
            if ok and pwd == self.safeguards.get("admin_passcode", "Barron"):
                return True
            QMessageBox.warning(self, "Access Denied", "Invalid passcode. Standard safety routing enforced.")
        return False
    def _reset_member_builder_panel(self, reset_steel_rate=False):
        if reset_steel_rate and hasattr(self, "input_lb_rate"):
            self.input_lb_rate.setText("1.30")
        if hasattr(self, "input_run_qty"):
            self.input_run_qty.setText("1")
        if hasattr(self, "combo_alloy"):
            self.combo_alloy.setCurrentIndex(0)
        if hasattr(self, "combo_picker"):
            self.combo_picker.blockSignals(True)
            self.combo_picker.setCurrentIndex(0)
            self.combo_picker.blockSignals(False)
            self.handle_card_context_swap()
        ac = getattr(self, "active_member_card", None)
        if ac is not None:
            if ac.combo_model.count() > 0:
                ac.combo_model.setCurrentIndex(0)
            ac.input_extent.setText("10.0")
            ac.input_plate_w.setText("12.0")
            ac.input_plate_thk.setText("0.25")
            ac.chk_custom_mill.setChecked(False)
            ac.input_custom_mill.setText("10.0")
            ac.chk_primer.setChecked(True)
            ac.chk_powder.setChecked(False)
            ac.chk_galv.setChecked(False)
            ac.clear_all_addon_rows()

    def execute_fabrication_math_routine(self, shape_key, model, extent, plate_w, plate_thk, pc, hdg, addons_list, custom_mill=None):
        try:
            qty = int(self.input_run_qty.text().strip())
            rate_per_lb = float(self.input_lb_rate.text().strip())
            base_labor_rate = float(self.safeguards.get("base_labor_rate", 86.0))
        except ValueError:
            QMessageBox.warning(self, "Error", "Verify quantities and rates are valid numbers.")
            return

        alloy = self.combo_alloy.currentText()
        density = BidFormMathEngine.get_density(alloy)
        is_stainless = ("stainless" in alloy.lower())

        addon_summary_tokens = []
        override_logs = []
        addon_labor_surcharges = 0.0

        if custom_mill is not None and shape_key != "plate":
            billable_footage = custom_mill
            override_logs.append(f"CUSTOM STOCK ({custom_mill}ft)")
        else:
            billable_footage = BidFormMathEngine.calculate_billable_length(shape_key, extent, qty)

        actual_wgt, billable_wgt, base_material_cost = 0.0, 0.0, 0.0
        label_desc = f"{model}"

        active_item = None
        for item in self.steel_matrix_data.get(shape_key, []):
            if item.get("designation") == model:
                active_item = item
                break

        weight_key = "weight_steel_lb_ft"
        if alloy == "304 Stainless":
            weight_key = "weight_ss304_lb_ft"
        elif alloy == "316 Stainless":
            weight_key = "weight_ss316_lb_ft"

        if shape_key == "plate":
            _, actual_wgt, base_material_cost = BidFormMathEngine.calculate_plate(qty, extent, plate_w, plate_thk, rate_per_lb, alloy)
            billable_wgt = actual_wgt
            label_desc = f"{model} ({extent}\"x{plate_w}\"x{plate_thk}\")"
        else:
            weight_ft = active_item.get(weight_key, active_item.get("weight_steel_lb_ft", 13.0)) if active_item else 13.0
            actual_wgt = weight_ft * (extent * qty)
            billable_wgt = weight_ft * billable_footage
            main_member_mat_cost = round(billable_wgt * rate_per_lb, 2)
            base_material_cost = main_member_mat_cost
            label_desc = f"{extent:g}' {model}"

        active_nsc_angle = 0.0
        machining_accum = 0.0
        fab_labor_accum = 0.0
        subline_details = []
        for op in addons_list:
            if op["mode"] == "NSC-Angled cuts" and op["qty"] > 0:
                active_nsc_angle = op["p1"]

        for op in addons_list:
            a_qty = op["qty"]
            if a_qty <= 0:
                continue
            mode = op["mode"]
            p1, p2, p3, p4 = op["p1"], op["p2"], op["p3"], op["p4"]
            line_cost = 0.0
            weld_inches = 0.0

            if mode == "Band Saw Cut":
                if shape_key == "beam":
                    max_beam_num = int(self.safeguards.get("max_saw_beam_size", "W16").upper().replace("W", ""))
                    try:
                        prefix, _, _ = model.upper().partition("X")
                        curr_beam_num = int(prefix.replace("W", "").replace("S", ""))
                    except ValueError:
                        curr_beam_num = 0
                    if curr_beam_num > max_beam_num:
                        if self.verify_safeguard_override(f"{model} exceeds max saw size {self.safeguards.get('max_saw_beam_size', 'W16')}."):
                            override_logs.append("SAW SIZE OVERRIDE")
                            line_cost = (2.0 / 60.0) * base_labor_rate * a_qty
                        else:
                            line_cost = float(self.safeguards.get("gate_override_fee", 25.00)) * a_qty
                    else:
                        line_cost = (2.0 / 60.0) * base_labor_rate * a_qty
                else:
                    line_cost = (1.5 / 60.0) * base_labor_rate * a_qty

            elif mode == "Cope":
                rec_beam = op["sub"]
                rec_depth, rec_bf = 8.0, 4.0
                for b in self.steel_matrix_data.get("beam", []):
                    if b.get("designation") == rec_beam:
                        rec_depth = b.get("depth_in", 8.0)
                        rec_bf = b.get("flange_width_in", 4.0)
                        break
                cope_lin_in = rec_depth + rec_bf
                torch_hrs = ((cope_lin_in / 12.0) / 60.0) + 0.15
                line_cost = torch_hrs * base_labor_rate * a_qty

            elif mode == "NSC-Angled cuts":
                b_depth = active_item.get("depth_in", 6.0) if active_item else 6.0
                rad = math.radians(p1) if 0 < p1 < 90 else math.radians(45)
                lin_in = b_depth / math.cos(rad)
                saw_ipm = float(self.safeguards.get("saw_ipm", 0.8))
                saw_hrs = (lin_in / saw_ipm) / 60.0
                line_cost = saw_hrs * base_labor_rate * a_qty
            elif mode == "Drill Holes":
                drill_spm = float(self.safeguards.get("drill_spm", 2.0))
                if p1 > self.safeguards.get("max_drill_diameter", 1.125):
                    if self.verify_safeguard_override(f"Hole Dia {p1}\" exceeds max drill capacity ({self.safeguards.get('max_drill_diameter', 1.125)}\")."):
                        override_logs.append("DRILL DIA OVERRIDE")
                        drill_hrs = (p2 / drill_spm) / 60.0
                        line_cost = drill_hrs * base_labor_rate * a_qty
                    else:
                        torch_hrs = ((math.pi * p1 * p2) / 10.0) / 60.0
                        line_cost = torch_hrs * base_labor_rate * a_qty
                else:
                    drill_hrs = (p2 / drill_spm) / 60.0
                    line_cost = drill_hrs * base_labor_rate * a_qty

            elif mode == "Punch Holes":
                drill_spm = float(self.safeguards.get("drill_spm", 2.0))
                light_ppm = float(self.safeguards.get("light_ppm", 4.0))
                overweight = (shape_key != "plate") and (actual_wgt > self.safeguards.get("max_manual_punch_weight", 45.0))
                oversized_sheet = (shape_key == "plate") and (extent > self.safeguards.get("turret_max_length", 48.0) or plate_w > self.safeguards.get("turret_max_width", 48.0))
                if overweight or oversized_sheet:
                    msg = f"Part weight ({actual_wgt:.1f} lbs) exceeds 45 lb manual punch press limit." if overweight else "Plate exceeds 4'x4' CNC turret bed."
                    if self.verify_safeguard_override(msg):
                        override_logs.append("PUNCH GATE OVERRIDE")
                        punch_hrs = (p2 / light_ppm) / 60.0
                        line_cost = punch_hrs * base_labor_rate * a_qty
                    else:
                        drill_hrs = (p2 / drill_spm) / 60.0
                        line_cost = drill_hrs * base_labor_rate * a_qty
                else:
                    punch_hrs = (p2 / light_ppm) / 60.0
                    line_cost = punch_hrs * base_labor_rate * a_qty

            elif mode == "Shear Cuts":
                max_thk = self.safeguards.get("ss_shear_max_thickness", 0.375) if is_stainless else self.safeguards.get("carbon_shear_max_thickness", 0.50)
                max_len = self.safeguards.get("max_shear_length", 120.0)
                heavy_wgt = float(self.safeguards.get("heavy_weight_cutoff", 40.0))
                ppm = float(self.safeguards.get("heavy_ppm", 0.5)) if actual_wgt >= heavy_wgt else float(self.safeguards.get("light_ppm", 4.0))
                if plate_thk > max_thk or p1 > max_len:
                    if self.verify_safeguard_override(f"Shear limits exceeded (Max {max_thk}\" x {max_len}\")."):
                        override_logs.append("SHEAR GATE OVERRIDE")
                        line_cost = ((1.0 / ppm) / 60.0) * base_labor_rate * a_qty
                    else:
                        line_cost = float(self.safeguards.get("gate_override_fee", 25.00)) * a_qty
                else:
                    line_cost = ((1.0 / ppm) / 60.0) * base_labor_rate * a_qty

            elif mode == "Press Brake Bend":
                max_brake_len = self.safeguards.get("max_press_brake_length", 120.0)
                tonnage_violation = (
                    p1 > max_brake_len or
                    (plate_thk > 0.1192 and p1 > 120.0) or
                    (plate_thk > 0.187 and p1 > 72.0) or
                    (plate_thk > 0.25 and p1 > 48.0) or
                    (plate_thk > 0.375 and p1 > 40.0) or
                    (plate_thk > 0.50 and p1 > 18.0)
                )
                if tonnage_violation:
                    if self.verify_safeguard_override(f"Press brake limit exceeded ({plate_thk}\" thk x {p1}\" len, max 10' bed)."):
                        override_logs.append("BRAKE PRESS OVERRIDE")
                heavy_wgt = float(self.safeguards.get("heavy_weight_cutoff", 40.0))
                ppm = float(self.safeguards.get("heavy_ppm", 0.5)) if actual_wgt >= heavy_wgt else float(self.safeguards.get("light_ppm", 4.0))
                line_cost = ((1.0 / ppm) / 60.0) * base_labor_rate * a_qty
            elif mode == "Standard Studs":
                stud_rate = float(self.safeguards.get("std_stud_rate", 5.00))
                line_cost = stud_rate * a_qty
                weld_inches = 0.0

            elif mode == "HD Studs":
                line_cost = (p2 * float(self.safeguards.get("hd_stud_rate", 1.00))) * a_qty
                stud_mass = BidFormMathEngine.calculate_hd_stud_weight(p1, p2, alloy) * a_qty * qty
                actual_wgt += stud_mass
                billable_wgt += stud_mass
                base_material_cost += (stud_mass * rate_per_lb)
                weld_inches = (math.pi * p1) * a_qty

            elif mode == "WH-Welded Hanger":
                line_cost = float(self.safeguards.get("wh_flat_rate", 75.00)) * a_qty
                weld_inches = 12.0 * a_qty
            elif mode.startswith("Custom Fee: "):
                cf_lbl = mode.replace("Custom Fee: ", "", 1).strip()
                cf_match = next((e for e in self.safeguards.get("custom_extra_fees", []) if e.get("label") == cf_lbl), None)
                cf_rate = float(cf_match.get("value", 0.0)) if cf_match else 0.0
                line_cost = cf_rate * a_qty

            elif mode == "Saddle Cut":
                line_cost = 0.50 * base_labor_rate * a_qty

            elif mode == "Torch cut":
                c_map = {"Level 1": float(self.safeguards.get("torch_lvl1_fee", 10.0)), "Level 2": float(self.safeguards.get("torch_lvl2_fee", 20.0)), "Level 3": float(self.safeguards.get("torch_lvl3_fee", 35.0)), "Level 4": float(self.safeguards.get("torch_lvl4_fee", 50.0))}
                line_cost = c_map.get(op["sub"], 15.0) * a_qty

            elif mode == "Stiffeners":
                h, w = BidFormMathEngine.calculate_stiffener_geometry(active_item)
                stiff_wgt = h * w * p1 * density * a_qty * qty
                actual_wgt += stiff_wgt
                billable_wgt += stiff_wgt
                base_material_cost += (stiff_wgt * rate_per_lb)
                line_cost = (2.0 / 60.0) * base_labor_rate * a_qty
                weld_inches = (h * 2.0 + w) * a_qty

            elif mode == "Standard End Plate":
                p_width = active_item.get("flange_width_in", 4.0) if active_item else 4.0
                p_height = active_item.get("depth_in", 6.0) if active_item else 6.0
                if op["nsc_end"] and 0 < active_nsc_angle < 90:
                    p_height = p_height / math.cos(math.radians(active_nsc_angle))
                plt_wgt = p_width * p_height * p1 * density * a_qty * qty
                actual_wgt += plt_wgt
                billable_wgt += plt_wgt
                base_material_cost += (plt_wgt * rate_per_lb)
                line_cost = (2.0 / 60.0) * base_labor_rate * a_qty
                weld_inches = ((p_width * 2.0) + (p_height * 2.0)) * a_qty

            elif mode == "Flush End Cap":
                p_width = active_item.get("width_in", active_item.get("od_in", 4.0)) if active_item else 4.0
                p_height = active_item.get("height_in", active_item.get("od_in", 4.0)) if active_item else 4.0
                plt_wgt = p_width * p_height * p1 * density * a_qty * qty
                actual_wgt += plt_wgt
                billable_wgt += plt_wgt
                base_material_cost += (plt_wgt * rate_per_lb)
                line_cost = (1.5 / 60.0) * base_labor_rate * a_qty
                weld_inches = ((p_width * 2.0) + (p_height * 2.0)) * a_qty

            elif mode in ["Top Flange End Plate", "Oversized Base Plate", "Shear Tabs"]:
                plt_wgt = p2 * p3 * p1 * density * a_qty * qty
                actual_wgt += plt_wgt
                billable_wgt += plt_wgt
                base_material_cost += (plt_wgt * rate_per_lb)
                hole_hrs = (p4 / 2.0) / 60.0 if p4 > 0 else 0.0
                line_cost = (((2.0 / 60.0) + hole_hrs) * base_labor_rate) * a_qty

                if mode == "Shear Tabs":
                    weld_inches = p3 * a_qty
                elif mode == "Oversized Base Plate":
                    m_w = active_item.get("width_in", active_item.get("od_in", 4.0)) if active_item else 4.0
                    m_h = active_item.get("height_in", active_item.get("od_in", 4.0)) if active_item else 4.0
                    weld_inches = ((m_w * 2.0) + (m_h * 2.0)) * a_qty
                else:
                    weld_inches = ((p2 * 2.0) + (p3 * 2.0)) * a_qty

            weld_tag = ""
            if weld_inches > 0:
                if op["field_weld"]:
                    weld_tag = "[FIELD WELD]"
                else:
                    w_cost = BidFormMathEngine.calculate_weld_cost(
                        weld_inches, op["weld_type"], op["weld_size"], op["full_wrap"], base_labor_rate, self.safeguards
                    )
                    line_cost += w_cost
                    wrap_lbl = "Wrap" if op["full_wrap"] else "1-Side"
                    weld_tag = f"[{op['weld_size']} {op['weld_type']} {wrap_lbl}]"

            addon_labor_surcharges += line_cost
            if mode in ["Drill Holes", "Punch Holes"]:
                total_holes = int(p2 * a_qty)
                op_label = f"{mode} ({total_holes} @ {p1:g}\")"
                op_cat = "machining"
            elif mode in ["Cope", "Torch Cut", "Torch cut", "Shear Cuts", "Press Brake Bend", "Saddle Cut", "Laser Cut", "Angle Cut", "NSC-Angled Cut"]:
                if mode in ["Top Flange End Plate", "Oversized Base Plate", "Shear Tabs"] and p2 > 0 and p3 > 0:
                    op_label = f"{mode} ({p1:g}\" x {p2:g}\" x {p3:g}\") (x{a_qty}) {weld_tag}".strip()
                else:
                    op_label = f"{mode}(x{a_qty}) {weld_tag}".strip()
                op_cat = "machining"
            else:
                op_label = f"{mode}(x{a_qty}) {weld_tag}".strip()
                op_cat = "labor"
            op_total_run = round(line_cost * qty, 2)
            addon_summary_tokens.append(op_label)
            if op_cat == "machining":
                machining_accum += op_total_run
            else:
                fab_labor_accum += op_total_run
            subline_details.append({
                "label": op_label,
                "cost": op_total_run,
                "ea_cost": round(line_cost, 2),
                "category": op_cat,
                "formula": f"{op_label}: ${line_cost:,.2f}/pc x {qty} pcs = ${op_total_run:,.2f} raw",
            })

        base_rate = float(self.safeguards.get('base_labor_rate', 86.0))
        baseline_labor_accum = 0.0
        saw_cost = 0.0
        has_manual_cut = any(
            op.get("qty", 0) > 0 and op.get("mode") in ("Band Saw Cut", "NSC-Angled cuts", "Shear Cuts", "Torch cut")
            for op in (addons_list or [])
        )
        if shape_key != "plate" and not has_manual_cut and extent < billable_footage / max(1, qty):
            dim_a = float(active_item.get("depth_in", 4.0)) if active_item else 4.0
            dim_b = float(active_item.get("flange_width_in", 4.0)) if active_item else 4.0
            saw_ipm = max(0.1, float(self.safeguards.get('saw_ipm', 0.8)))
            saw_cost = (((dim_a + dim_b) / saw_ipm) / 60.0) * base_rate * qty
            baseline_labor_accum += saw_cost
            machining_accum += saw_cost
            saw_lbl = f"Auto Band Saw Cut (x{qty})"
            addon_summary_tokens.insert(0, saw_lbl)
            subline_details.insert(0, {
                "label": saw_lbl, "cost": round(saw_cost, 2), "ea_cost": round(saw_cost / max(1, qty), 2),
                "category": "machining",
                "formula": f"Saw Cut: (({dim_a:g}\" + {dim_b:g}\") / {saw_ipm:g} ipm / 60) x ${base_rate:.2f}/hr x {qty} pcs = ${saw_cost:,.2f}",
            })
        heavy_cutoff = float(self.safeguards.get("heavy_weight_cutoff", 40.0))
        handling_mins = float(self.safeguards.get("handling_mins_per_pc", 15.0))
        light_hand_mins = float(self.safeguards.get("light_handling_mins_per_pc", 0.75))
        unit_pc_wgt = actual_wgt / max(1, qty)
        hand_cost = 0.0
        if handling_mins > 0:
            if unit_pc_wgt >= heavy_cutoff:
                tot_hand_mins = handling_mins + max(0, qty - 1) * (handling_mins * 0.5)
                hand_lbl = f"Shop Handling ({tot_hand_mins:g}m batch)"
                hand_fx = f"Heavy Batch Handling: {handling_mins:g}m setup + {max(0, qty - 1)} x {handling_mins * 0.5:g}m = {tot_hand_mins:g}m @ ${base_rate:.2f}/hr"
            else:
                setup_m = min(3.0, handling_mins * 0.25)
                tot_hand_mins = setup_m + (light_hand_mins * qty)
                hand_lbl = f"Bench Handling ({tot_hand_mins:g}m batch)"
                hand_fx = f"Light Bench Handling: {setup_m:g}m setup + ({qty} x {light_hand_mins:g}m) = {tot_hand_mins:g}m @ ${base_rate:.2f}/hr"
            hand_cost = (tot_hand_mins / 60.0) * base_rate
            baseline_labor_accum += hand_cost
            fab_labor_accum += hand_cost
            ins_idx = 1 if saw_cost > 0 else 0
            addon_summary_tokens.insert(ins_idx, hand_lbl)
            subline_details.insert(ins_idx, {
                "label": hand_lbl, "cost": round(hand_cost, 2), "ea_cost": round(hand_cost / max(1, qty), 2),
                "category": "labor",
                "formula": f"{hand_fx} = ${hand_cost:,.2f}",
            })

        ac_chk = getattr(self, "active_member_card", None)
        raw_primer_chk = bool(ac_chk.chk_primer.isChecked()) if (ac_chk and hasattr(ac_chk, "chk_primer")) else False
        primer = raw_primer_chk and not (pc or hdg)
        primer_rate = float(self.safeguards.get("primer_rate_per_lb", 0.12))
        primer_cost = (actual_wgt * primer_rate) if primer else 0.0
        if primer:
            p_lbl = f"Shop Primer (${primer_rate:.2f}/lb)"
            addon_summary_tokens.append(p_lbl)
            subline_details.append({
                "label": p_lbl, "cost": round(primer_cost, 2), "ea_cost": round(primer_cost / max(1, qty), 2),
                "category": "finish",
                "formula": f"Shop Primer: {actual_wgt:,.1f} lbs x ${primer_rate:.2f}/lb = ${primer_cost:,.2f}",
            })
        pc_rate_lb = float(self.safeguards.get("pc_rate_per_lb", 1.80))
        hdg_h_lb = float(self.safeguards.get("hdg_heavy_rate_per_lb", 0.62))
        hdg_l_lb = float(self.safeguards.get("hdg_light_rate_per_lb", 1.88))
        pc_fee = (actual_wgt * pc_rate_lb) if pc else 0.0
        if pc:
            pc_lbl = f"Powder Coating (${pc_rate_lb:.2f}/lb)"
            addon_summary_tokens.append(pc_lbl)
            subline_details.append({
                "label": pc_lbl, "cost": round(pc_fee, 2), "ea_cost": round(pc_fee / max(1, qty), 2),
                "category": "finish",
                "formula": f"Powder Coating: {actual_wgt:,.1f} lbs x ${pc_rate_lb:.2f}/lb = ${pc_fee:,.2f}",
            })
        hdg_eff_rate = (hdg_h_lb if actual_wgt >= 20.0 else hdg_l_lb)
        hdg_fee = (actual_wgt * hdg_eff_rate) if hdg else 0.0
        if hdg:
            hdg_lbl = f"Hot-Dip Galvanized (${hdg_eff_rate:.2f}/lb)"
            addon_summary_tokens.append(hdg_lbl)
            subline_details.append({
                "label": hdg_lbl, "cost": round(hdg_fee, 2), "ea_cost": round(hdg_fee / max(1, qty), 2),
                "category": "finish",
                "formula": f"Hot-Dip Galvanized: {actual_wgt:,.1f} lbs x ${hdg_eff_rate:.2f}/lb = ${hdg_fee:,.2f}",
            })
        finish_accum = primer_cost + pc_fee + hdg_fee
        raw_labor_and_finish = baseline_labor_accum + primer_cost + (addon_labor_surcharges * qty) + pc_fee + hdg_fee
        raw_item_cost = base_material_cost + raw_labor_and_finish

        tags = []
        if alloy == "304 Stainless": tags.append("304 SS")
        elif alloy == "316 Stainless": tags.append("316 SS")
        if pc: tags.append("PC")
        if hdg: tags.append("HDG")
        tag_summary = f" [{'+'.join(tags)}]" if tags else ""

        if override_logs:
            addon_summary_tokens.append(f"OVERRIDES: {', '.join(override_logs)}")

        ac = getattr(self, "active_member_card", None)
        form_state = {
            "shape_key": shape_key,
            "model": model,
            "qty": self.input_run_qty.text().strip() if hasattr(self, "input_run_qty") else "1",
            "length": ac.input_extent.text().strip() if ac else str(extent),
            "plate_w": ac.input_plate_w.text().strip() if ac else str(plate_w),
            "plate_thk": ac.input_plate_thk.text().strip() if ac else str(plate_thk),
            "alloy": self.combo_alloy.currentText() if hasattr(self, "combo_alloy") else "Carbon Steel",
            "steel_rate": self.input_lb_rate.text().strip() if hasattr(self, "input_lb_rate") else "1.30",
            "primer": bool(ac.chk_primer.isChecked()) if (ac and hasattr(ac, "chk_primer")) else True,
            "pc": bool(pc),
            "hdg": bool(hdg),
            "custom_mill": ac.input_custom_mill.text().strip() if (ac and ac.chk_custom_mill.isChecked()) else "",
            "addons_list": [dict(a) for a in (addons_list or [])],
        }
        new_model_lbl = f"{label_desc} (x{qty}){tag_summary}"
        new_addons_lbl = ", ".join(addon_summary_tokens) if addon_summary_tokens else "None"
        if any(
            str(existing.get("model", "")).strip() == new_model_lbl
            and str(existing.get("addons", "")).strip() == new_addons_lbl
            for existing in self.current_project_items
        ):
            ans_dup = QMessageBox.question(
                self,
                "Duplicate Line Item Detected",
                f"An identical line item is already in your Active Project Workbook:\n\n"
                f"  • {new_model_lbl}\n\n"
                f"Do you want to add another duplicate line?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if ans_dup != QMessageBox.Yes:
                return

        self.current_project_items.append({
            "model": new_model_lbl,
            "weight": actual_wgt,
            "billable_weight": billable_wgt,
            "main_mat_cost": round(float(locals().get("main_member_mat_cost", base_material_cost)), 2),
            "addon_mat_cost": round(max(0.0, base_material_cost - float(locals().get("main_member_mat_cost", base_material_cost))), 2),
            "mat_cost": round(base_material_cost, 2),
            "waived_keys": [],
            "machining_cost": round(machining_accum, 2),
            "fab_labor_cost": round(fab_labor_accum, 2),
            "finish_cost": round(finish_accum, 2),
            "labor_cost": round(raw_labor_and_finish, 2),
            "cost": round(raw_item_cost, 2),
            "addons": new_addons_lbl,
            "subline_details": subline_details,
            "form_state": form_state,
        })
        self.sync_local_workbench_view()
        self._reset_member_builder_panel(reset_steel_rate=False)

    def get_engineering_hours_and_cost(self):
        try:
            p_hrs = float(self.input_prog_hrs.text().strip()) if hasattr(self, "input_prog_hrs") and self.input_prog_hrs.text().strip() else 0.0
        except ValueError:
            p_hrs = 0.0
        try:
            d_hrs = float(self.input_detail_hrs.text().strip()) if hasattr(self, "input_detail_hrs") and self.input_detail_hrs.text().strip() else 0.0
        except ValueError:
            d_hrs = 0.0
        eng_rate = float(self.safeguards.get("eng_labor_rate", 175.0))
        total_hrs = max(0.0, p_hrs) + max(0.0, d_hrs)
        return max(0.0, p_hrs), max(0.0, d_hrs), eng_rate, (total_hrs * eng_rate)

    def toggle_all_tree_items(self):
        cnt = self.ledger_tree.topLevelItemCount()
        if cnt == 0:
            return
        any_open = any(self.ledger_tree.topLevelItem(i).isExpanded() for i in range(cnt))
        target_state = not any_open
        self._wb_expanded = target_state
        for i in range(cnt):
            self.ledger_tree.topLevelItem(i).setExpanded(target_state)
        self.btn_toggle_expand.setText("Collapse All" if target_state else "Expand All")
        self.ledger_tree.viewport().update()

    def toggle_selected_subline_waive(self):
        cur = self.ledger_tree.currentItem()
        if not cur or cur.parent() is None:
            QMessageBox.information(self, "Select a Sub-Line", "Click any cost sub-line (such as Main Member Steel, Auto Band Saw Cut, or an add-on) to waive or restore its cost while keeping weight for HDG & shipping.")
            return
        tag = cur.data(0, Qt.UserRole + 2)
        if not tag or not isinstance(tag, (tuple, list)) or len(tag) != 2:
            return
        item_idx, w_key = int(tag[0]), str(tag[1])
        if not (0 <= item_idx < len(self.current_project_items)):
            return
        it = self.current_project_items[item_idx]
        w_list = list(it.get("waived_keys") or [])
        if w_key in w_list:
            w_list.remove(w_key)
        else:
            w_list.append(w_key)
        it["waived_keys"] = w_list
        self.sync_local_workbench_view()
        if item_idx < self.ledger_tree.topLevelItemCount():
            self.ledger_tree.setCurrentItem(self.ledger_tree.topLevelItem(item_idx))

    def remove_workbench_item(self, idx):
        if 0 <= idx < len(self.current_project_items):
            self.current_project_items.pop(idx)
            self.sync_local_workbench_view()

    def sync_local_workbench_view(self):
        c_name = self.input_cust_name.text().strip() if self.input_cust_name.text().strip() else "Retail Customer"
        p_name = self.input_proj_name.text().strip() if self.input_proj_name.text().strip() else "Standard Build"
        self.lbl_wb_header.setText(f"WORKBENCH: {c_name.upper()} | {p_name.upper()}")
        markup_mult = float(self.safeguards.get("labor_markup", 1.40))
        markup_pct = round((markup_mult - 1.0) * 100)
        self.lbl_markup_title.setText(f"BID MARKUP ({markup_pct}%):")
        self.ledger_tree.clear()
        t_wgt = 0.0
        for idx, item in enumerate(self.current_project_items):
            import re as _re
            _mq = _re.search(r"\(x(\d+)\)", str(item.get("model", "")))
            _qty = int(_mq.group(1)) if _mq else int((item.get("form_state") or {}).get("qty", 1) or 1)
            _ea_cost = (float(item["cost"]) / _qty) if _qty > 1 else float(item["cost"])
            _ea_wgt = (float(item["weight"]) / _qty) if _qty > 1 else float(item["weight"])

            parent = QTreeWidgetItem(self.ledger_tree)
            parent.setData(0, Qt.UserRole, idx)
            import re as _re_ea
            _clean_m = _re_ea.sub(r"\s*\[\$[0-9,]+\.\d{2}\s*ea\]", "", str(item["model"])).strip()
            _disp_model = f"{_clean_m} [${_ea_cost:,.2f} ea]" if _qty > 1 else _clean_m
            parent.setText(0, _disp_model)
            parent.setText(1, f"{item['weight']:.1f} lbs")
            parent.setText(2, f"${item['cost']:,.2f}")
            if _qty > 1:
                ea_child = QTreeWidgetItem(parent)
                ea_child.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                ea_child.setText(0, f"  • Each (x{_qty}): ${_ea_cost:,.2f} | {_ea_wgt:.1f} lbs")
                ea_child.setForeground(0, QColor("#0369a1"))
            parent.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
            parent.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
            btn_del = QPushButton("X")
            btn_del.setFixedSize(24, 22)
            btn_del.setStyleSheet("background-color: rgba(220, 38, 38, 0.25); border: 1px solid #f87171; color: #fca5a5; font-weight: 600; border-radius: 4px; padding: 0px;")
            btn_del.clicked.connect(lambda checked=False, i=idx: self.remove_workbench_item(i))
            self.ledger_tree.setItemWidget(parent, 3, btn_del)
            waived = set(item.get("waived_keys") or [])
            _raw_main_mat = float(item.get("main_mat_cost", item.get("mat_cost", item["cost"])))
            _raw_addon_mat = float(item.get("addon_mat_cost", max(0.0, float(item.get("mat_cost", item["cost"])) - _raw_main_mat)))
            _eff_main_mat = 0.0 if "main_mat" in waived else _raw_main_mat
            _eff_addon_mat = 0.0 if "addon_mat" in waived else _raw_addon_mat
            _m_tot = round(_eff_main_mat + _eff_addon_mat, 2)

            sub_list = item.get("subline_details") or []
            if sub_list:
                _mach_tot = round(sum(float(sd.get("cost", 0.0)) for si, sd in enumerate(sub_list) if sd.get("category") == "machining" and f"sub_{si}" not in waived), 2)
                _fab_tot = round(sum(float(sd.get("cost", 0.0)) for si, sd in enumerate(sub_list) if sd.get("category") == "labor" and f"sub_{si}" not in waived), 2)
                _fin_tot = round(sum(float(sd.get("cost", 0.0)) for si, sd in enumerate(sub_list) if sd.get("category") == "finish" and f"sub_{si}" not in waived), 2)
            else:
                _mach_tot = float(item.get("machining_cost", 0.0))
                _fab_tot = float(item.get("fab_labor_cost", float(item.get("labor_cost", 0.0)) - _mach_tot - float(item.get("finish_cost", 0.0))))
                _fin_tot = float(item.get("finish_cost", 0.0))

            _eff_item_cost = round(_m_tot + _mach_tot + _fab_tot + _fin_tot, 2)
            item["mat_cost"] = _m_tot
            item["machining_cost"] = _mach_tot
            item["fab_labor_cost"] = _fab_tot
            item["finish_cost"] = _fin_tot
            item["labor_cost"] = round(_mach_tot + _fab_tot + _fin_tot, 2)
            item["cost"] = _eff_item_cost
            _ea_cost = (_eff_item_cost / _qty) if _qty > 1 else _eff_item_cost
            _disp_model = f"{_clean_m} [${_ea_cost:,.2f} ea]" if _qty > 1 else _clean_m
            parent.setText(0, _disp_model)
            parent.setText(2, f"${_eff_item_cost:,.2f}")
            if _qty > 1 and parent.childCount() > 0:
                parent.child(0).setText(0, f"  • Each (x{_qty}): ${_ea_cost:,.2f} | {_ea_wgt:.1f} lbs")

            parent.setData(0, Qt.UserRole + 1, f"{_clean_m}  =  Materials ${_m_tot:,.2f} + Machining ${_mach_tot:,.2f} + Labor ${_fab_tot:,.2f} + Finish ${_fin_tot:,.2f}  ->  ${_eff_item_cost:,.2f} Raw (${_ea_cost:,.2f}/ea)")

            c1 = QTreeWidgetItem(parent)
            c1.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            c1.setFirstColumnSpanned(True)
            c1.setData(0, Qt.UserRole + 2, (idx, "main_mat"))
            if "main_mat" in waived:
                c1.setText(0, f"Main Member Steel: $0.00 [CUSTOMER SUPPLIED — ${_raw_main_mat:,.2f} Waived | {item.get('billable_weight', item['weight']):.1f} lbs Kept for HDG/Ship]")
                c1.setData(0, Qt.UserRole + 1, f"Customer Supplied Main Member: ${_raw_main_mat:,.2f} steel waived, {item['weight']:.1f} lbs weight kept for HDG & shipping")
                c1.setForeground(0, QColor("#b45309"))
            else:
                _mm_ea = f" (${_raw_main_mat/_qty:,.2f}/ea)" if _qty > 1 else ""
                c1.setText(0, f"Main Member Steel: ${_raw_main_mat:,.2f}{_mm_ea}  |  Mill Stock: {item.get('billable_weight', item['weight']):.1f} lbs")
                c1.setData(0, Qt.UserRole + 1, f"Main Member Steel: ${_raw_main_mat:,.2f} raw (${_raw_main_mat/max(1,_qty):,.2f}/ea) — Click 'Waive / Restore Sub-Line Cost' if Customer Supplied")
                c1.setForeground(0, QColor("#0369a1"))

            if _raw_addon_mat > 0:
                c_amat = QTreeWidgetItem(parent)
                c_amat.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                c_amat.setFirstColumnSpanned(True)
                c_amat.setData(0, Qt.UserRole + 2, (idx, "addon_mat"))
                if "addon_mat" in waived:
                    c_amat.setText(0, f"Plate / Attachment Steel: $0.00 [WAIVED — ${_raw_addon_mat:,.2f}]")
                    c_amat.setForeground(0, QColor("#b45309"))
                else:
                    _am_ea = f" (${_raw_addon_mat/_qty:,.2f}/ea)" if _qty > 1 else ""
                    c_amat.setText(0, f"Plate / Attachment Steel: ${_raw_addon_mat:,.2f}{_am_ea}")
                    c_amat.setData(0, Qt.UserRole + 1, f"Plate / Attachment Steel: ${_raw_addon_mat:,.2f} raw (${_raw_addon_mat/max(1,_qty):,.2f}/ea)")
                    c_amat.setForeground(0, QColor("#0369a1"))

            c_mach = QTreeWidgetItem(parent)
            c_mach.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            c_mach.setFirstColumnSpanned(True)
            _ea_mach = f" (${_mach_tot/_qty:,.2f}/ea)" if _qty > 1 else ""
            c_mach.setText(0, f"Machining (Saw / Drill / Punch / Torch): ${_mach_tot:,.2f}{_ea_mach}")
            c_mach.setData(0, Qt.UserRole + 1, f"Shop Machining Total: ${_mach_tot:,.2f} raw (${_mach_tot/max(1,_qty):,.2f}/ea)")
            c_mach.setForeground(0, QColor("#0f172a"))

            c2 = QTreeWidgetItem(parent)
            c2.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            c2.setFirstColumnSpanned(True)
            _ea_fab = f" (${_fab_tot/_qty:,.2f}/ea)" if _qty > 1 else ""
            c2.setText(0, f"Shop Fab & Weld Labor: ${_fab_tot:,.2f}{_ea_fab}")
            c2.setData(0, Qt.UserRole + 1, f"Shop Fabrication & Weld Labor: ${_fab_tot:,.2f} raw (${_fab_tot/max(1,_qty):,.2f}/ea)")
            c2.setForeground(0, QColor("#0f172a"))

            if _fin_tot > 0:
                c_fin = QTreeWidgetItem(parent)
                c_fin.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                c_fin.setFirstColumnSpanned(True)
                _ea_fin = f" (${_fin_tot/_qty:,.2f}/ea)" if _qty > 1 else ""
                c_fin.setText(0, f"Coating / Finish: ${_fin_tot:,.2f}{_ea_fin}")
                c_fin.setData(0, Qt.UserRole + 1, f"Coating / Finish Total: ${_fin_tot:,.2f} raw (${_fin_tot/max(1,_qty):,.2f}/ea)")
                c_fin.setForeground(0, QColor("#0369a1"))

            if sub_list:
                for si, sd in enumerate(sub_list):
                    ca = QTreeWidgetItem(parent)
                    ca.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    ca.setFirstColumnSpanned(True)
                    s_key = f"sub_{si}"
                    ca.setData(0, Qt.UserRole + 2, (idx, s_key))
                    sc_tot = float(sd.get("cost", 0.0))
                    sc_ea = float(sd.get("ea_cost", sc_tot / max(1, _qty)))
                    ea_tag = f" (${sc_ea:,.2f}/ea)" if _qty > 1 else ""
                    if s_key in waived:
                        ca.setText(0, f"- {sd.get('label', '')}: $0.00 [WAIVED — ${sc_tot:,.2f}]")
                        ca.setData(0, Qt.UserRole + 1, f"WAIVED: {sd.get('formula', '')}")
                        ca.setForeground(0, QColor("#b45309"))
                    else:
                        ca.setText(0, f"- {sd.get('label', '')}: ${sc_tot:,.2f}{ea_tag}")
                        ca.setData(0, Qt.UserRole + 1, str(sd.get("formula") or f"{sd.get('label', '')}: ${sc_tot:,.2f}"))
                        ca.setForeground(0, QColor("#1e3a8a"))
            elif item.get("addons") and item["addons"] != "None":
                for tok in item["addons"].split(","):
                    if tok.strip():
                        ca = QTreeWidgetItem(parent)
                        ca.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                        ca.setFirstColumnSpanned(True)
                        ca.setText(0, f"- {tok.strip()}")
                        ca.setForeground(0, QColor("#1e3a8a"))
            sub_ov2 = item.get("custom_sublines") or {}
            for _ci, _ct in sub_ov2.items():
                if 0 <= int(_ci) < parent.childCount():
                    parent.child(int(_ci)).setText(0, f"- {_ct}")
            parent.setExpanded(self._wb_expanded)
            t_wgt += item["weight"]

        p_hrs, d_hrs, eng_rate, eng_cost = self.get_engineering_hours_and_cost()
        if eng_cost > 0:
            er = QTreeWidgetItem(self.ledger_tree)
            er.setText(0, f"Prog ({p_hrs:g}h) + Det ({d_hrs:g}h) @ ${eng_rate:.0f}/hr")
            er.setText(1, "--")
            er.setText(2, f"${eng_cost:,.2f}")
            er.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
            er.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
            er.setForeground(0, QColor("#b45309"))

        raw_mat = sum(float(i.get("mat_cost", i["cost"])) for i in self.current_project_items)
        raw_mach = sum(float(i.get("machining_cost", 0.0)) for i in self.current_project_items)
        raw_fin = sum(float(i.get("finish_cost", 0.0)) for i in self.current_project_items)
        raw_fab = sum(float(i.get("fab_labor_cost", float(i.get("labor_cost", 0.0)) - float(i.get("machining_cost", 0.0)) - float(i.get("finish_cost", 0.0)))) for i in self.current_project_items) + eng_cost
        raw_sub = round(raw_mat + raw_mach + raw_fab + raw_fin, 2)
        mkp_dol = round(raw_sub * (markup_mult - 1.0), 2)
        grand = round(raw_sub + mkp_dol, 2)
        self.lbl_tot_wgt.setText(f"{t_wgt:.1f} lbs")
        self.lbl_tot_mat.setText(f"${raw_mat:,.2f}")
        self.lbl_tot_mach.setText(f"${raw_mach:,.2f}")
        self.lbl_tot_lab.setText(f"${raw_fab:,.2f}")
        self.lbl_tot_fin.setText(f"${raw_fin:,.2f}")
        self.lbl_tot_sub.setText(f"${raw_sub:,.2f}")
        self.lbl_tot_mkp.setText(f"+${mkp_dol:,.2f}")
        self.lbl_tot_grand.setText(f"${grand:,.2f}")

    def duplicate_selected_project_item(self):
        cur = self.ledger_tree.currentItem()
        if not cur:
            QMessageBox.warning(self, "No Item Selected", "Click a component row in the active workbook first.")
            return
        top = cur.parent() if cur.parent() else cur
        idx = self.ledger_tree.indexOfTopLevelItem(top)
        if 0 <= idx < len(self.current_project_items):
            import copy
            self.current_project_items.append(copy.deepcopy(self.current_project_items[idx]))
            self.sync_local_workbench_view()

    def _infer_form_state_from_label(self, label_str, specs_str=""):
        import re
        txt = str(label_str)
        m_qty = re.search(r"\(x(\d+)\)", txt)
        qty = int(m_qty.group(1)) if m_qty else 1
        m_len = re.match(r"^\s*([0-9.]+)['\"]?\s+(.+?)\s*(?:\(x\d+\)|\[|$)", txt)
        if m_len:
            length_str = m_len.group(1)
            des = m_len.group(2).strip()
        else:
            length_str = "20"
            des = txt.split("(")[0].split("[")[0].strip()
        shape_guess = "beam"
        for sk, items in self.steel_matrix_data.items():
            if any(str(x.get("designation", "")).upper() == des.upper() for x in items):
                shape_guess = sk
                break
        alloy = "304 Stainless" if "[304 SS" in txt else ("316 Stainless" if "[316 SS" in txt else "Carbon Steel")
        inferred_addons = []
        for tok in re.split(r"[\r\n,]+", str(specs_str or "")):
            tok = re.sub(r"^[\u2022\u00b7\-\*\s]+", "", tok).strip()
            if not tok or tok in ("None", "Standard Stock") or "Shop Primer" in tok or "Auto Band Saw" in tok or "Powder Coat" in tok or "HDG" in tok:
                continue
            m_a = re.match(r"^([^(]+?)(?:\s*\(x(\d+)\))?(?:\[(.*?)\])?$", tok)
            if m_a:
                mode_name = m_a.group(1).strip()
                a_qty = int(m_a.group(2)) if m_a.group(2) else 1
                w_info = m_a.group(3) or ""
                w_type = "CJP" if "CJP" in w_info else ("PJP" if "PJP" in w_info else "Fillet")
                m_ws = re.search(r"(\d+/\d+\"|1\")", w_info)
                w_size = m_ws.group(1) if m_ws else "1/4\""
                inferred_addons.append({
                    "mode": mode_name, "qty": a_qty, "field_weld": "FIELD WELD" in w_info.upper(),
                    "full_wrap": "1-Side" not in w_info, "weld_type": w_type, "weld_size": w_size
                })
        return {
            "shape_key": shape_guess, "model": des, "qty": qty, "length": length_str,
            "plate_w": "12", "plate_thk": "", "alloy": alloy, "steel_rate": "1.30",
            "primer": "Shop Primer" in str(specs_str), "pc": "PC" in txt or "Powder Coat" in str(specs_str),
            "hdg": "HDG" in txt or "HDG" in str(specs_str),
            "custom_mill": "", "addons_list": inferred_addons
        }

    def edit_selected_project_item(self):
        cur = self.ledger_tree.currentItem()
        if not cur:
            QMessageBox.warning(self, "No Item Selected", "Click a component row in the active workbook first.")
            return
        top = cur.parent() if cur.parent() else cur
        idx = self.ledger_tree.indexOfTopLevelItem(top)
        if not (0 <= idx < len(self.current_project_items)):
            return
        child_lines = "\n".join(top.child(c).text(0) for c in range(top.childCount()))
        it = self.current_project_items.pop(idx)
        combined_specs = (it.get("addons", "") + "\n" + child_lines).strip()
        fs = it.get("form_state") or self._infer_form_state_from_label(it.get("model", ""), combined_specs)
        ac = self.active_member_card
        sk = fs.get("shape_key", "beam")
        s_idx = self.combo_picker.findText(sk)
        if s_idx >= 0:
            self.combo_picker.setCurrentIndex(s_idx)
        self.combo_alloy.setCurrentText(fs.get("alloy", "Carbon Steel"))
        self.input_run_qty.setText(str(fs.get("qty", 1)))
        self.input_lb_rate.setText(str(fs.get("steel_rate", "1.30")))
        m_idx = ac.combo_model.findText(fs.get("model", ""), Qt.MatchFixedString)
        if m_idx >= 0:
            ac.combo_model.setCurrentIndex(m_idx)
        ac.input_extent.setText(str(fs.get("length", "20")))
        if fs.get("plate_w"): ac.input_plate_w.setText(str(fs.get("plate_w")))
        if fs.get("plate_thk"): ac.input_plate_thk.setText(str(fs.get("plate_thk")))
        cm = str(fs.get("custom_mill", "")).strip()
        ac.chk_custom_mill.setChecked(bool(cm))
        ac.input_custom_mill.setText(cm)
        ac.chk_primer.setChecked(bool(fs.get("primer", True)))
        ac.chk_powder.setChecked(bool(fs.get("pc", False)))
        ac.chk_galv.setChecked(bool(fs.get("hdg", False)))
        for old_rw in list(ac.addon_rows):
            old_rw.setParent(None)
            old_rw.deleteLater()
        ac.addon_rows.clear()
        for op in fs.get("addons_list", []):
            ac.btn_add_op.click()
            rw = ac.addon_rows[-1]
            t_idx = rw.type_select.findText(op.get("mode", ""), Qt.MatchFixedString)
            if t_idx >= 0: rw.type_select.setCurrentIndex(t_idx)
            if op.get("p1"): rw.in_param1.setText(str(op.get("p1")))
            if op.get("p2"): rw.in_param2.setText(str(op.get("p2")))
            if op.get("p3"): rw.in_param3.setText(str(op.get("p3")))
            if op.get("p4"): rw.in_param4.setText(str(op.get("p4")))
            if op.get("sub"): rw.combo_sub.setCurrentText(str(op.get("sub")))
            rw.chk_nsc_end.setChecked(bool(op.get("nsc_end", False)))
            rw.in_qty.setText(str(op.get("qty", 1)))
            rw.chk_field_weld.setChecked(bool(op.get("field_weld", False)))
            rw.combo_weld_wrap.setCurrentIndex(0 if op.get("full_wrap", True) else 1)
            rw.combo_weld_type.setCurrentText(op.get("weld_type", "Fillet"))
            rw.combo_weld_size.setCurrentText(op.get("weld_size", "1/4\""))
        self.sync_local_workbench_view()

    def _delete_highlighted_t2_item(self):
        cur = self.ledger_tree.currentItem()
        if not cur:
            return
        top = cur.parent() if cur.parent() else cur
        idx = self.ledger_tree.indexOfTopLevelItem(top)
        if 0 <= idx < len(self.current_project_items):
            self.current_project_items.pop(idx)
            self.sync_local_workbench_view()

    def pack_and_finalize_project_quote(self):
        p_hrs, d_hrs, eng_rate, eng_cost = self.get_engineering_hours_and_cost()
        if not self.current_project_items and eng_cost <= 0:
            QMessageBox.warning(self, "Workbook Empty", "Add at least one component or engineering hour before finalizing.")
            return
        cust = self.input_cust_name.text().strip() if self.input_cust_name.text().strip() else "Retail Customer"
        proj = self.input_proj_name.text().strip() if self.input_proj_name.text().strip() else "Standard Build"
        markup_mult = float(self.safeguards.get("labor_markup", 1.40))
        markup_pct = round((markup_mult - 1.0) * 100)

        raw_mat_total = sum(i.get('mat_cost', i['cost']) for i in self.current_project_items)
        raw_labor_total = sum(i.get('labor_cost', 0.0) for i in self.current_project_items) + eng_cost
        raw_subtotal = round(raw_mat_total + raw_labor_total, 2)
        t_wgt = sum(i['weight'] for i in self.current_project_items)
        markup_dollars = round(raw_subtotal * (markup_mult - 1.0), 2)
        grand_total = round(raw_subtotal + markup_dollars, 2)

        manifest_entries = []
        customer_lines = []
        for idx, item in enumerate(self.current_project_items):
            mat_c = item.get('mat_cost', item['cost'])
            lab_c = item.get('labor_cost', 0.0)
            waived_set = set(item.get("waived_keys") or [])
            is_cust_supplied = ("main_mat" in waived_set)
            manifest_entries.append(
                f" Item #{idx+1}: {item['model']} (Ship Wgt: {item['weight']:.1f} lbs | Mill Wgt: {item.get('billable_weight', item['weight']):.1f} lbs | Mat: ${mat_c:,.2f} | Labor: ${lab_c:,.2f} | Raw: ${item['cost']:,.2f}) [Addons: {item['addons']}]"
            )
            sub_ov2 = item.get("custom_sublines") or {}
            if sub_ov2:
                clean_addons = " || ".join(str(v).strip() for _, v in sorted(sub_ov2.items(), key=lambda kv: int(kv)) if str(v).strip())
            else:
                active_toks = [t.strip() for t in item['addons'].split(",") if t.strip() and "OVERRIDES:" not in t]
                clean_addons = " || ".join(active_toks) if active_toks else "Standard Stock"
            import re as _re2
            _mq2 = _re2.search(r"\(x(\d+)\)", str(item.get("model", "")))
            _qty2 = int(_mq2.group(1)) if _mq2 else int((item.get("form_state") or {}).get("qty", 1) or 1)
            import re as _re_cl
            _base_model_cl = _re_cl.sub(r"\s*\[\$[0-9,]+\.\d{2}\s*ea\]", "", str(item['model'])).strip()
            _clean_desc_no_qty = _re_cl.sub(r"\s*\(x\d+\)", "", _base_model_cl).strip()
            _shape_k = str((item.get("form_state") or {}).get("shape_key", "")).lower()
            _cs_label = "Customer Supplied Pipe" if ("pipe" in _shape_k or "pipe" in _clean_desc_no_qty.lower()) else "Customer Supplied Material"
            _line_marked = round(float(item['cost']) * markup_mult, 2)
            _unit_marked = round(_line_marked / max(1, _qty2), 2)
            customer_lines.append({
                "qty": _qty2,
                "desc": _clean_desc_no_qty,
                "unit_price": _unit_marked,
                "customer_supplied": is_cust_supplied,
                "customer_supplied_label": _cs_label if is_cust_supplied else "",
                "specs": clean_addons if clean_addons else "Standard Stock",
                "weight": round(float(item['weight']), 1),
                "price": _line_marked,
                "form_state": item.get("form_state"),
            })

        if eng_cost > 0:
            manifest_entries.append(f" Engineering: Programming ({p_hrs:g} hrs) + Detailing ({d_hrs:g} hrs) @ ${eng_rate:.2f}/hr = ${eng_cost:,.2f}")
            customer_lines.append({
                "desc": "CNC Programming & Shop Detailing",
                "specs": f"Programming ({p_hrs:g} hrs) + Detailing ({d_hrs:g} hrs)",
                "weight": 0.0,
                "price": eng_cost * markup_mult
            })

        manifest_entries.append(" ──────────────────────────────────────────────────────────────────────")
        manifest_entries.append(f" Raw Steel Materials: ${raw_mat_total:,.2f}  |  Raw Shop & Eng. Labor: ${raw_labor_total:,.2f}")
        manifest_entries.append(f" Combined Raw Subtotal: ${raw_subtotal:,.2f}  |  Bid Markup ({markup_pct}%): +${grand_total - raw_subtotal:,.2f}")
        full_detailed_manifest = "\n".join(manifest_entries)

        self.finalize_project_callback(cust, proj, t_wgt, grand_total, full_detailed_manifest, customer_lines)
        self.current_project_items.clear()
        self.input_cust_name.clear()
        self.input_proj_name.clear()
        self.input_run_qty.setText("1")
        self.input_prog_hrs.setText("0")
        self.input_detail_hrs.setText("0")
        self.sync_local_workbench_view()
        QMessageBox.information(self, "Bid Finalized", "Grouped Project Quote saved to Running Project Ledger.")
class HistoricalArchiveLedgerPage(QWidget):
    def __init__(self, rfq_ledger_items, safeguards, on_ledger_changed_callback=None, on_reopen_quote_callback=None, parent=None):
        super().__init__(parent)
        self.rfq_ledger_items = rfq_ledger_items
        self.safeguards = safeguards
        self.on_ledger_changed = on_ledger_changed_callback
        self.on_reopen_quote = on_reopen_quote_callback
        self._detail_expanded = True
        self.init_ui()

    def init_ui(self):
        outer_v = QVBoxLayout(self)
        outer_v.setContentsMargins(12, 12, 12, 12)
        main_split = QSplitter(Qt.Vertical)
        main_split.setStyleSheet("QSplitter { background: transparent !important; } QSplitter::handle { background-color: #475569; height: 5px; border-radius: 2px; margin: 2px 0px; } QSplitter::handle:hover { background-color: #0369a1; }")
        outer_v.addWidget(main_split)
        
        left_panel = QWidget()
        left_panel.setAttribute(Qt.WA_StyledBackground, True)
        left_panel.setStyleSheet("background: transparent !important;")
        left_l = QVBoxLayout(left_panel)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(8)

        top_card = QWidget()
        top_card.setStyleSheet("background-color: rgba(248, 250, 252, 0.80); border: 1px solid #cbd5e1; border-radius: 8px;")
        top_bar = QHBoxLayout(top_card)
        top_bar.setContentsMargins(10, 8, 10, 8)
        lbl_s = QLabel("Search:")
        lbl_s.setStyleSheet("font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; color: #0f172a; background: transparent; border: none;")
        top_bar.addWidget(lbl_s)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Quote #, Customer, or Project...")
        self.search_input.setStyleSheet("background-color: rgba(239, 246, 255, 0.80); color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 6px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600;")
        self.search_input.textChanged.connect(self.populate_ledger_grid)
        top_bar.addWidget(self.search_input, 1)
        left_l.addWidget(top_card)

        self.table = QTableWidget(0, 6)
        apply_excel_table_style(self.table)
        self.table.setHorizontalHeaderLabels(["QUOTE #", "DATE", "CUSTOMER", "PROJECT", "WEIGHT", "TOTAL"])
        hdr_t = self.table.horizontalHeader()
        hdr_t.setStretchLastSection(False)
        for _c in range(6):
            hdr_t.setSectionResizeMode(_c, QHeaderView.Interactive)
        hdr_t.sectionDoubleClicked.connect(lambda c: self.table.resizeColumnToContents(c))
        for _c, _w in enumerate([160, 175, 220, 260, 115, 130]): self.table.setColumnWidth(_c, _w)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        from PySide6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence(Qt.Key_Delete), self.table, activated=self.delete_selected_quote)
        QShortcut(QKeySequence('Ctrl+F'), self, activated=self.search_input.setFocus)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setStyleSheet("""
            QTableWidget { background-color: rgba(248, 250, 252, 0.80) !important; color: #0f172a !important; border: 1px solid #cbd5e1; border-radius: 8px; gridline-color: #60a5fa; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; }
            QTableWidget::viewport, QTableWidget QWidget, QTableCornerButton::section { background: transparent !important; border: none !important; }
            QTableWidget::item:selected, QTableWidget::item:selected:!active { background-color: #93c5fd; color: #0f172a; }
            QHeaderView::section { background-color: rgba(248, 250, 252, 0.80); color: #0369a1; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; padding: 6px; border: none; border-bottom: 1px solid #60a5fa; }
        """)
        self.table.itemSelectionChanged.connect(lambda: (self.display_selected_quote_summary(), self.smart_fit_columns()))
        left_l.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_export_pdf = QPushButton("Export Customer PDF Quote")
        self.btn_export_pdf.setStyleSheet("background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; border-radius: 6px; padding: 10px;")
        self.btn_export_pdf.clicked.connect(self.export_selected_quote_pdf)
        btn_row.addWidget(self.btn_export_pdf, 1)

        self.btn_quote_style = QPushButton("Customize Quote Style & Tokens")
        self.btn_quote_style.setStyleSheet("background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; border-radius: 6px; padding: 10px;")
        self.btn_quote_style.clicked.connect(self.open_quote_template_designer)
        btn_row.addWidget(self.btn_quote_style, 1)

        self.btn_reopen_quote = QPushButton("Re-Open / Clone Quote")
        self.btn_reopen_quote.setStyleSheet("background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; border-radius: 6px; padding: 10px;")
        self.btn_reopen_quote.clicked.connect(self.reopen_selected_quote)
        btn_row.addWidget(self.btn_reopen_quote, 1)

        self.btn_delete_quote = QPushButton("Delete Selected Quote")
        self.btn_delete_quote.setStyleSheet("background-color: #ffffff; border: 1px solid #fca5a5; color: #b91c1c; font-weight: 700; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; border-radius: 6px; padding: 10px;")
        self.btn_delete_quote.clicked.connect(self.delete_selected_quote)
        btn_row.addWidget(self.btn_delete_quote, 1)
        main_split.addWidget(left_panel)

        right_panel = QWidget()
        right_panel.setAttribute(Qt.WA_StyledBackground, True)
        right_panel.setStyleSheet("background: transparent !important;")
        right_l = QVBoxLayout(right_panel)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(8)

        det_hdr = QWidget()
        det_hdr.setStyleSheet("background-color: rgba(248, 250, 252, 0.80); border: 1px solid #cbd5e1; border-radius: 8px;")
        det_hdr_l = QHBoxLayout(det_hdr)
        det_hdr_l.setContentsMargins(10, 6, 10, 6)
        self.lbl_detail_title = QLabel("QUOTE INSPECTOR: SELECT A QUOTE ABOVE")
        self.lbl_detail_title.setStyleSheet("font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; color: #0369a1; background: transparent; border: none;")
        det_hdr_l.addWidget(self.lbl_detail_title)
        det_hdr_l.addStretch()

        self.btn_toggle_detail = QPushButton("Collapse All")
        self.btn_toggle_detail.setStyleSheet("background-color: rgba(239, 246, 255, 0.72); border: 2px solid #0284c7; color: #000000; font-weight: 700; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 5px;")
        self.btn_toggle_detail.clicked.connect(self.toggle_detail_tree)
        det_hdr_l.addWidget(self.btn_toggle_detail)
        right_l.addWidget(det_hdr)

        self.detail_tree = QTreeWidget()
        apply_excel_table_style(self.detail_tree)
        self.detail_tree.setColumnCount(3)
        self.detail_tree.setHeaderLabels(["PART / DESCRIPTION", "SHIP WEIGHT", "RAW COST"])
        self.detail_tree.setRootIsDecorated(True)
        self.detail_tree.setTextElideMode(Qt.ElideNone)
        self.detail_tree.setSelectionMode(QAbstractItemView.NoSelection)
        self.detail_tree.header().setStretchLastSection(False)
        self.detail_tree.header().setSectionResizeMode(0, QHeaderView.Interactive)
        self.detail_tree.setColumnWidth(0, 680)
        self.detail_tree.setColumnWidth(1, 130)
        self.detail_tree.setColumnWidth(2, 130)
        self.detail_tree.header().setSectionResizeMode(1, QHeaderView.Interactive)
        self.detail_tree.header().setSectionResizeMode(2, QHeaderView.Interactive)
        self.detail_tree.setStyleSheet("""
            QTreeWidget { background-color: rgba(248, 250, 252, 0.80) !important; color: #0f172a !important; border: 1px solid #cbd5e1; border-radius: 8px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; padding: 4px; }
            QTreeWidget::viewport, QTreeWidget QWidget { background: transparent !important; }
            QTreeWidget::item { padding: 4px 2px; border-bottom: 1px solid rgba(51, 65, 85, 0.45); }
            QHeaderView::section { background-color: rgba(248, 250, 252, 0.80); color: #0369a1; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; padding: 6px; border: none; border-bottom: 1px solid #60a5fa; }
        """)
        right_l.addWidget(self.detail_tree, 1)

        self.tot_table = QTableWidget(6, 3)
        self.tot_table.horizontalHeader().setVisible(False)
        self.tot_table.verticalHeader().setVisible(False)
        self.tot_table.setShowGrid(False)
        self.tot_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.tot_table.setFocusPolicy(Qt.NoFocus)
        self.tot_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tot_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tot_table.setFixedHeight(168)
        self.tot_table.setStyleSheet("""
            QTableWidget { background-color: rgba(248, 250, 252, 0.80) !important; color: #0f172a !important; border: 1px solid #cbd5e1; border-radius: 8px; padding: 4px 6px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; }
            QTableWidget::viewport, QTableWidget QWidget, QTableCornerButton::section { background: transparent !important; border: none !important; }
            QTableWidget::item { padding: 1px 6px; border: none; border-bottom: 1px solid rgba(51, 65, 85, 0.45); }
        """)

        m_lbl = "font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; color: #1e3a8a; background: transparent; border: none;"
        m_val = "font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; color: #0f172a; background: transparent; border: none;"
        g_lbl = "font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; color: #0369a1; background: transparent; border: none;"

        self.lbl_t3_wgt = QLabel("0.0 lbs")
        self.lbl_t3_mat = QLabel("$0.00")
        self.lbl_t3_lab = QLabel("$0.00")
        self.lbl_t3_sub = QLabel("$0.00")
        self.lbl_t3_mkp = QLabel("+$0.00")
        self.lbl_t3_grand = QLabel("$0.00")
        self.lbl_t3_r1_title = QLabel("RAW STEEL MATERIALS:")
        self.lbl_t3_r2_title = QLabel("RAW SHOP & ENG. LABOR:")
        self.lbl_t3_r3_title = QLabel("COMBINED RAW SUBTOTAL:")
        self.lbl_t3_r4_title = QLabel("BID MARKUP:")

        rows_spec = [
            (QLabel("ACTUAL SHIP WEIGHT:"), self.lbl_t3_wgt, QLabel(""), m_lbl, m_val, m_val),
            (self.lbl_t3_r1_title, QLabel(""), self.lbl_t3_mat, m_lbl, m_val, m_val),
            (self.lbl_t3_r2_title, QLabel(""), self.lbl_t3_lab, m_lbl, m_val, m_val),
            (self.lbl_t3_r3_title, QLabel(""), self.lbl_t3_sub, m_lbl, m_val, m_val),
            (self.lbl_t3_r4_title, QLabel(""), self.lbl_t3_mkp, m_lbl, m_val, m_val),
            (QLabel("TOTAL CUSTOMER QUOTE:"), QLabel(""), self.lbl_t3_grand, g_lbl, g_lbl, g_lbl),
        ]
        for r_i, (lw, mw, rw, lc, mc, rc) in enumerate(rows_spec):
            self.tot_table.setRowHeight(r_i, 25)
            lw.setStyleSheet(lc); lw.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            mw.setStyleSheet(mc); mw.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            rw.setStyleSheet(rc); rw.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            for _c_idx in range(3):
                self.tot_table.setItem(r_i, _c_idx, QTableWidgetItem(""))
            self.tot_table.setCellWidget(r_i, 0, lw)
            self.tot_table.setCellWidget(r_i, 1, mw)
            self.tot_table.setCellWidget(r_i, 2, rw)

        def _sync_bottom_cols(*_args):
            sb_w = self.detail_tree.verticalScrollBar().width() if self.detail_tree.verticalScrollBar().isVisible() else 0
            self.tot_table.setColumnWidth(0, self.detail_tree.columnWidth(0))
            self.tot_table.setColumnWidth(1, self.detail_tree.columnWidth(1))
            self.tot_table.setColumnWidth(2, self.detail_tree.columnWidth(2) + sb_w)

        self.detail_tree.header().sectionResized.connect(_sync_bottom_cols)
        self.detail_tree.header().sectionDoubleClicked.connect(lambda c: (self.detail_tree.resizeColumnToContents(c), _sync_bottom_cols()))
        self._sync_bottom_cols = _sync_bottom_cols

        det_vsplit = QSplitter(Qt.Vertical)
        det_vsplit.setStyleSheet("QSplitter { background: transparent !important; } QSplitter::handle { background-color: #475569; height: 4px; border-radius: 2px; } QSplitter::handle:hover { background-color: #0369a1; }")
        right_l.removeWidget(self.detail_tree)
        det_vsplit.addWidget(self.detail_tree)
        det_vsplit.addWidget(self.tot_table)
        det_vsplit.setSizes([280, 168])
        right_l.addWidget(det_vsplit, 1)
        outer_v.setSpacing(8)
        outer_v.addLayout(btn_row)
        main_split.addWidget(right_panel)
        main_split.setSizes([320, 440])

    def toggle_detail_tree(self):
        self._detail_expanded = not self._detail_expanded
        for i in range(self.detail_tree.topLevelItemCount()):
            self.detail_tree.topLevelItem(i).setExpanded(self._detail_expanded)
        self.btn_toggle_detail.setText("Collapse All" if self._detail_expanded else "Expand All")


    def smart_fit_columns(self):
        # Top 6-column quote table: fit compact data columns to content, give remaining width to Customer & Project
        tw = max(700, self.table.viewport().width())
        fixed_cols = {0: 145, 1: 165, 4: 115, 5: 125}
        for col_i, min_w in fixed_cols.items():
            self.table.resizeColumnToContents(col_i)
            self.table.setColumnWidth(col_i, max(min_w, self.table.columnWidth(col_i) + 18))
        used = sum(self.table.columnWidth(c) for c in fixed_cols)
        rem = max(260, tw - used)
        self.table.setColumnWidth(2, int(rem * 0.45))
        self.table.setColumnWidth(3, rem - int(rem * 0.45))

        # Bottom detail tree: fit Ship Weight & Quote Cost cleanly, give all remaining width to Part / Description
        dw = max(600, self.detail_tree.viewport().width())
        self.detail_tree.resizeColumnToContents(1)
        self.detail_tree.resizeColumnToContents(2)
        w1 = max(135, self.detail_tree.columnWidth(1) + 34)
        w2 = max(150, self.detail_tree.columnWidth(2) + 34)
        w0 = max(260, dw - w1 - w2)
        self.detail_tree.header().blockSignals(True)
        self.detail_tree.setColumnWidth(0, w0)
        self.detail_tree.setColumnWidth(1, w1)
        self.detail_tree.setColumnWidth(2, w2)
        self.detail_tree.header().blockSignals(False)
        if hasattr(self, "_sync_bottom_cols"):
            self._sync_bottom_cols()

    def showEvent(self, event):
        super().showEvent(event)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.smart_fit_columns)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.smart_fit_columns()

    def populate_ledger_grid(self):
        query = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""
        self.table.setRowCount(0)
        for record in reversed(self.rfq_ledger_items):
            q_num = record.get("quote_num", "")
            cust = record.get("customer", "")
            proj = record.get("project", "")
            if query and query not in q_num.lower() and query not in cust.lower() and query not in proj.lower():
                continue
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(q_num))
            self.table.setItem(r, 1, QTableWidgetItem(record.get("timestamp", "")))
            self.table.setItem(r, 2, QTableWidgetItem(cust))
            self.table.setItem(r, 3, QTableWidgetItem(proj))
            self.table.setItem(r, 4, QTableWidgetItem(f"{record.get('weight', 0.0):.1f} lbs"))
            self.table.setItem(r, 5, QTableWidgetItem(f"${record.get('cost', 0.0):,.2f}"))
        self.detail_tree.clear()
        self.lbl_detail_title.setText("QUOTE INSPECTOR: SELECT A QUOTE ABOVE")
        for lbl, z in [(self.lbl_t3_wgt, "0.0 lbs"), (self.lbl_t3_mat, "$0.00"), (self.lbl_t3_lab, "$0.00"), (self.lbl_t3_sub, "$0.00"), (self.lbl_t3_mkp, "+$0.00"), (self.lbl_t3_grand, "$0.00")]:
            lbl.setText(z)

    def display_selected_quote_summary(self):
        row = self.table.currentRow()
        if row < 0 or not self.table.item(row, 0):
            return
        quote_num = self.table.item(row, 0).text()
        record = next((r for r in self.rfq_ledger_items if r.get("quote_num") == quote_num), None)
        if not record:
            return
        self.lbl_detail_title.setText(f"{quote_num} | {record.get('customer', '')} - {record.get('project', '')}")
        self.detail_tree.clear()

        is_catalog = (record.get("quote_type") == "catalog") or ("Client Tier Matrix:" in record.get("summary", ""))
        if is_catalog:
            self.detail_tree.setHeaderLabels(["PART / DESCRIPTION", "SHIP WEIGHT", "QUOTE COST"])
            self.lbl_t3_r1_title.setText("BASE CATALOG ITEMS:")
            self.lbl_t3_r2_title.setText("ADD-ONS & COATINGS:")
            self.lbl_t3_r3_title.setText("COMBINED SUBTOTAL:")
            tier_lbl = record.get("tier_label", "")
            if not tier_lbl:
                for line in record.get("summary", "").splitlines():
                    if "Client Tier Matrix:" in line:
                        tier_lbl = line.partition("Client Tier Matrix:").__getitem__(2).strip()
            tier_pct = "(" + tier_lbl.partition("(").__getitem__(2) if "(" in tier_lbl else "(50%)"
            self.lbl_t3_r4_title.setText(f"CLIENT TIER {tier_pct}:")

            for idx, ci in enumerate(record.get("catalog_items", []), 1):
                parent = QTreeWidgetItem(self.detail_tree)
                parent.setText(0, f"Item #{idx}: {ci['model']}")
                parent.setText(1, f"{ci['weight']:.1f} lbs")
                parent.setText(2, f"${ci['cost']:,.2f}")
                parent.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
                parent.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
                for al in ci.get("addon_lines", []):
                    c_sub = QTreeWidgetItem(parent)
                    c_sub.setFirstColumnSpanned(True)
                    c_sub.setText(0, f"- {al}")
                    c_sub.setForeground(0, QColor("#0369a1") if "+$" in al else QColor("#1e3a8a"))
                parent.setExpanded(self._detail_expanded)

            derived_base, derived_addon = 0.0, 0.0
            if not record.get("catalog_items"):
                item_prices = []
                for line in record.get("summary", "").splitlines():
                    clean_l = line.strip()
                    if clean_l.startswith("Item #"):
                        tag = "[Add-ons:" if "[Add-ons:" in clean_l else "[Addons:"
                        main_part, _, addon_raw = clean_l.partition(tag)
                        addon_part = addon_raw.rstrip("]").strip()
                        title_p = main_part.partition("(").__getitem__(0).strip()
                        det_p = main_part.partition("(").__getitem__(2).rstrip(")")
                        w_c, c_c = "", ""
                        for tok in det_p.split("|"):
                            t = tok.strip()
                            if t.startswith("Ship Wgt:"): w_c = t.partition(":").__getitem__(2).strip()
                            elif t.startswith("Price:"): c_c = t.partition(":").__getitem__(2).strip().rstrip(")")
                        p_val = float(c_c.replace("$", "").replace(",", "") or 0.0)
                        item_prices.append((p_val, addon_part))
                        parent = QTreeWidgetItem(self.detail_tree)
                        parent.setText(0, title_p)
                        parent.setText(1, w_c)
                        parent.setText(2, c_c)
                        parent.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
                        parent.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
                        if addon_part and addon_part != "None":
                            for at in addon_part.split(","):
                                if at.strip():
                                    ca = QTreeWidgetItem(parent)
                                    ca.setFirstColumnSpanned(True)
                                    ca.setText(0, f"- {at.strip()}")
                                    ca.setForeground(0, QColor("#0369a1"))
                        else:
                            cs = QTreeWidgetItem(parent)
                            cs.setFirstColumnSpanned(True)
                            cs.setText(0, "- Standard Catalog Spec")
                            cs.setForeground(0, QColor("#1e3a8a"))
                        parent.setExpanded(self._detail_expanded)
                # Estimate base vs addon split for legacy catalog quotes
                plain_prices = [pv for pv, ap in item_prices if not ap or ap == "None"]
                ref_base = plain_prices.__getitem__(0) if plain_prices else None
                for pv, ap in item_prices:
                    if ref_base and ap and ap != "None" and pv > ref_base:
                        derived_base += ref_base
                        derived_addon += (pv - ref_base)
                    else:
                        derived_base += pv

            tot_w = float(record.get("weight", 0.0))
            tot_c = float(record.get("cost", 0.0))
            b_tot = float(record.get("base_total", derived_base if derived_base > 0 else tot_c))
            a_tot = float(record.get("addon_total", derived_addon))
            sub_c = round(b_tot + a_tot, 2)
            pct_digits = "".join(ch for ch in tier_pct if ch.isdigit())
            t_mult = (float(pct_digits) / 100.0) if pct_digits else 1.0
            l_tot = float(record.get("list_total", round(tot_c / t_mult, 2) if t_mult > 0 else tot_c))
            t_delta = round(tot_c - l_tot, 2)
            if t_delta < -0.005:
                self.lbl_t3_r4_title.setText(f"CLIENT TIER SAVINGS {tier_pct}:")
                self.lbl_t3_mkp.setText(f"-${abs(t_delta):,.2f}")
            else:
                self.lbl_t3_r4_title.setText(f"CLIENT TIER {tier_pct}:")
                self.lbl_t3_mkp.setText(f"+${abs(t_delta):,.2f}")
            self.lbl_t3_wgt.setText(f"{tot_w:.1f} lbs")
            self.lbl_t3_mat.setText(f"${b_tot:,.2f}")
            self.lbl_t3_lab.setText(f"${a_tot:,.2f}")
            self.lbl_t3_sub.setText(f"${sub_c:,.2f}")
            self.lbl_t3_grand.setText(f"${tot_c:,.2f}")
            return
        self._render_custom_quote_details(record)

    def _render_custom_quote_details(self, record):
        self.detail_tree.setHeaderLabels(["PART / DESCRIPTION", "SHIP WEIGHT", "RAW COST"])
        self.lbl_t3_r1_title.setText("RAW STEEL MATERIALS:")
        self.lbl_t3_r2_title.setText("RAW SHOP & ENG. LABOR:")
        self.lbl_t3_r3_title.setText("COMBINED RAW SUBTOTAL:")
        self.lbl_t3_r4_title.setText("BID MARKUP:")

        raw_lines = [l.strip() for l in record.get("summary", "").splitlines() if l.strip()]
        merged = []
        for l in raw_lines:
            if set(l) <= {"=", "-", "?"} or l.startswith(("ITEMIZED MANIFEST", "? Customer:", "? Project:", "? Date:")):
                continue
            if l.startswith(("Item #", "Engineering:", "Raw Steel Materials:", "Combined Raw Subtotal:", "TOTAL PROJECT WEIGHT:", "GRAND PROJECT VALUE:")):
                merged.append(l)
            elif merged:
                merged[-1] += " " + l

        footer_summary = []
        for l in merged:
            if l.startswith(("Raw Steel Materials:", "Combined Raw Subtotal:", "TOTAL PROJECT WEIGHT:", "GRAND PROJECT VALUE:")):
                footer_summary.append(l)
                continue
            if l.startswith("Item #"):
                tag = "[Addons:" if "[Addons:" in l else "[Add-ons:"
                main_part, _, addon_raw = l.partition(tag)
                addon_part = addon_raw.rstrip("]").strip()
                split_key = "(Ship Wgt:" if "(Ship Wgt:" in main_part else ("(Weight:" if "(Weight:" in main_part else "(")
                title_part = main_part.partition(split_key).__getitem__(0).strip()
                details_part = (split_key.lstrip("(") + main_part.partition(split_key).__getitem__(2)).rstrip(")")
                wgt_col, cost_col = "", ""
                sub_tokens = [t.strip() for t in details_part.split("|") if t.strip()]
                for tok in sub_tokens:
                    if tok.startswith(("Ship Wgt:", "Weight:", "Mass:")):
                        wgt_col = tok.partition(":").__getitem__(2).strip()
                    elif tok.startswith(("Raw:", "Price:")):
                        cost_col = tok.partition(":").__getitem__(2).strip().rstrip(")")
                parent = QTreeWidgetItem(self.detail_tree)
                parent.setText(0, title_part)
                parent.setText(1, wgt_col)
                parent.setText(2, cost_col)
                parent.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
                parent.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
                for tok in sub_tokens:
                    if not tok.startswith(("Ship Wgt:", "Weight:", "Mass:", "Raw:", "Price:")):
                        c_sub = QTreeWidgetItem(parent)
                        c_sub.setFirstColumnSpanned(True)
                        c_sub.setText(0, f"- {tok}")
                        c_sub.setForeground(0, QColor("#1e3a8a"))
                if addon_part and addon_part != "None":
                    for a_tok in addon_part.split(","):
                        if a_tok.strip():
                            c_add = QTreeWidgetItem(parent)
                            c_add.setFirstColumnSpanned(True)
                            c_add.setText(0, f"- {a_tok.strip()}")
                            c_add.setForeground(0, QColor("#1e3a8a"))
                parent.setExpanded(self._detail_expanded)
            else:
                ri = QTreeWidgetItem(self.detail_tree)
                ri.setText(0, l)
                ri.setForeground(0, QColor("#b45309") if l.startswith("Engineering:") else QColor("#0369a1"))

        self.lbl_t3_wgt.setText(f"{record.get('weight', 0.0):.1f} lbs")
        self.lbl_t3_grand.setText(f"${record.get('cost', 0.0):,.2f}")
        mat_s, lab_s, sub_s, mkp_s = "--", "--", "--", "--"
        for fl in footer_summary:
            if "Raw Steel Materials:" in fl: mat_s = fl.partition("Raw Steel Materials:").__getitem__(2).partition("|").__getitem__(0).strip()
            if "Raw Shop & Eng. Labor:" in fl: lab_s = fl.partition("Raw Shop & Eng. Labor:").__getitem__(2).partition("|").__getitem__(0).strip()
            if "Combined Raw Subtotal:" in fl: sub_s = fl.partition("Combined Raw Subtotal:").__getitem__(2).partition("|").__getitem__(0).strip()
            if "Bid Markup" in fl: mkp_s = fl.partition("Bid Markup").__getitem__(2).partition(":").__getitem__(2).partition("|").__getitem__(0).strip()
        self.lbl_t3_mat.setText(mat_s)
        self.lbl_t3_lab.setText(lab_s)
        self.lbl_t3_sub.setText(sub_s)
        self.lbl_t3_mkp.setText(mkp_s)

    def reopen_selected_quote(self):
        row = self.table.currentRow()
        if row < 0 or not self.table.item(row, 0):
            QMessageBox.warning(self, "No Quote Selected", "Select a quote row in the table first before cloning.")
            return
        quote_num = self.table.item(row, 0).text()
        record = next((r for r in self.rfq_ledger_items if r.get("quote_num") == quote_num), None)
        if not record:
            return
        if self.on_reopen_quote:
            self.on_reopen_quote(record)

    def delete_selected_quote(self):
        selected_rows = sorted({idx.row() for idx in self.table.selectionModel().selectedRows()})
        if not selected_rows and self.table.currentRow() >= 0:
            selected_rows = [self.table.currentRow()]
        quote_nums = {self.table.item(r, 0).text() for r in selected_rows if self.table.item(r, 0)}
        if not quote_nums:
            QMessageBox.warning(self, "No Quote Selected", "Select one or more quote rows in the table first (hold Shift or Ctrl to select multiple).")
            return
        target_label = next(iter(quote_nums)) if len(quote_nums) == 1 else f"{len(quote_nums)} selected quotes"
        expected_pass = str(self.safeguards.get("admin_passcode", "Barron"))
        entered, ok = QInputDialog.getText(self, "Passcode Required", f"Enter Admin Passcode to permanently delete {target_label}:", QLineEdit.Password)
        if not ok or entered != expected_pass:
            if ok: QMessageBox.critical(self, "Access Denied", "Incorrect Admin Passcode.")
            return
        deleted_recs = [r for r in self.rfq_ledger_items if r.get("quote_num") in quote_nums]
        if deleted_recs:
            self._deleted_undo_stack = getattr(self, "_deleted_undo_stack", [])
            self._deleted_undo_stack.append(deleted_recs)
        self.rfq_ledger_items[:] = [r for r in self.rfq_ledger_items if r.get("quote_num") not in quote_nums]
        if self.on_ledger_changed: self.on_ledger_changed()
        self.populate_ledger_grid()

    def open_quote_template_designer(self):
        from ui.quote_template_designer import QuoteTemplateDesignerDialog
        row = self.table.currentRow()
        sample_rec = None
        if row >= 0 and self.table.item(row, 0):
            q_num = self.table.item(row, 0).text()
            sample_rec = next((r for r in self.rfq_ledger_items if r.get("quote_num") == q_num), None)
        QuoteTemplateDesignerDialog(get_workspace_path(), sample_record=sample_rec, parent=self).exec()

    def export_selected_quote_pdf(self):
        from PySide6.QtGui import QPainter
        from PySide6.QtCore import QRectF
        row = self.table.currentRow()
        if row < 0 or not self.table.item(row, 0):
            QMessageBox.warning(self, "No Quote Selected", "Click a quote row in the table first before exporting to PDF.")
            return

        quote_num = self.table.item(row, 0).text()
        record = next((r for r in self.rfq_ledger_items if r.get("quote_num") == quote_num), None)
        if not record:
            return

        default_path = get_workspace_path(f"{quote_num}_Customer_Quote.pdf")
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Customer PDF Quote", default_path, "PDF Files (*.pdf)")
        if not file_path:
            return
        if str(file_path).lower().endswith(".pdf") and not _ensure_pdf_writable(self, file_path):
            return

        from ui.quote_template_designer import load_quote_template_config, render_quote_documents
        tpl_cfg, _ = load_quote_template_config(get_workspace_path())
        body_html, footer_html = render_quote_documents(record, tpl_cfg)
        if body_html and footer_html:
            printer = QPrinter(QPrinter.ScreenResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(file_path)
            printer.setPageLayout(QPageLayout(QPageSize(QPageSize.Letter), QPageLayout.Portrait, QMarginsF(0.5, 0.5, 0.5, 0.5), QPageLayout.Inch))
            page_rect = printer.pageRect(QPrinter.DevicePixel)
            body_doc = QTextDocument(); body_doc.documentLayout().setPaintDevice(printer); body_doc.setHtml(body_html)
            footer_doc = QTextDocument(); footer_doc.documentLayout().setPaintDevice(printer); footer_doc.setHtml(footer_html); footer_doc.setTextWidth(page_rect.width())
            footer_h = footer_doc.size().height()
            from PySide6.QtCore import QSizeF
            usable_h = max(100.0, page_rect.height() - footer_h - 16.0)
            body_doc.setPageSize(QSizeF(page_rect.width(), usable_h))
            total_pages = max(1, body_doc.pageCount())
            painter = QPainter(printer)
            for pg in range(total_pages):
                if pg > 0: printer.newPage()
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
            QMessageBox.information(self, "PDF Exported", f"Customer quote saved cleanly to:\n{file_path}")
            return
        c_lines = record.get("customer_lines", [])
        rows_html = ""
        if c_lines:
            for idx, line in enumerate(c_lines, 1):
                wgt_str = f"{line['weight']:.1f} lbs" if line['weight'] > 0 else "?"
                specs_raw = line.get('specs', '')
                if specs_raw and specs_raw != "Standard Stock":
                    items = [x.strip() for x in specs_raw.split(",") if x.strip()]
                    specs_html = "<ul style='margin:0; padding-left:14pt;'>" + "".join(f"<li style='margin-bottom:2pt;'>{x}</li>" for x in items) + "</ul>"
                else:
                    specs_html = "Standard Stock"
                rows_html += (
                    f"<tr style='page-break-inside: avoid;'><td valign='top' style='padding:8pt; border-bottom:1pt solid #cbd5e1; font-size:10pt;'>{idx}</td>"
                    f"<td valign='top' style='padding:8pt; border-bottom:1pt solid #cbd5e1; font-size:10pt;'><b>{line['desc']}</b></td>"
                    f"<td valign='top' style='padding:8pt; border-bottom:1pt solid #cbd5e1; font-size:10pt;'>{specs_html}</td>"
                    f"<td valign='top' style='padding:8pt; border-bottom:1pt solid #cbd5e1; font-size:10pt; text-align:right;'>{wgt_str}</td>"
                    f"<td valign='top' style='padding:8pt; border-bottom:1pt solid #cbd5e1; font-size:10pt; text-align:right;'>${line['price']:,.2f}</td></tr>"
                )
        else:
            rows_html = (
                f"<tr style='page-break-inside: avoid;'><td valign='top' style='padding:8pt; border-bottom:1pt solid #cbd5e1; font-size:10pt;'>1</td>"
                f"<td valign='top' style='padding:8pt; border-bottom:1pt solid #cbd5e1; font-size:10pt;'><b>Custom Structural Steel Fabrication Package</b></td>"
                f"<td valign='top' style='padding:8pt; border-bottom:1pt solid #cbd5e1; font-size:10pt;'>Per Approved Project Specifications</td>"
                f"<td valign='top' style='padding:8pt; border-bottom:1pt solid #cbd5e1; font-size:10pt; text-align:right;'>{record.get('weight', 0.0):.1f} lbs</td>"
                f"<td valign='top' style='padding:8pt; border-bottom:1pt solid #cbd5e1; font-size:10pt; text-align:right;'>${record.get('cost', 0.0):,.2f}</td></tr>"
            )

        body_html = (
            f"<html><body style='font-family:Arial, Helvetica, sans-serif; color:#0f172a; font-size:10pt;'>"
            f"<div style='text-align:center; border-bottom:2pt solid #0284c7; padding-bottom:8pt; margin-bottom:16pt;'>"
            f"<span style='font-size:18pt; font-weight:bold; color:#0f172a;'>BOWMAN-MORTON MANUFACTURING</span><br>"
            f"<span style='font-size:10pt; color:#475569;'>Structural Steel &amp; Custom Metal Fabrication</span></div>"
            f"<table width='100%' cellspacing='0' cellpadding='8' style='background-color:#f8fafc; border:1pt solid #cbd5e1; margin-bottom:22pt;'>"
            f"<tr><td style='font-size:10pt; text-align:left; line-height:1.4;'>"
            f"<b>QUOTATION #:</b> <span style='color:#0284c7; font-weight:bold;'>{quote_num}</span><br>"
            f"<b>DATE:</b> {record.get('timestamp', '')}<br>"
            f"<b>CUSTOMER:</b> {record.get('customer', '')}<br>"
            f"<b>PROJECT:</b> {record.get('project', '')}</td></tr></table>"
            f"<table width='100%' cellspacing='0' cellpadding='0' style='border-collapse:collapse;'><thead>"
            f"<tr style='background-color:#0f172a; color:#ffffff;'>"
            f"<th width='9%' style='padding:8pt; text-align:left; font-size:10pt;'>Line #</th>"
            f"<th width='25%' style='padding:8pt; text-align:left; font-size:10pt;'>ITEM / DESCRIPTION</th>"
            f"<th width='35%' style='padding:8pt; text-align:left; font-size:10pt;'>FABRICATION &amp; FINISH SPECS</th>"
            f"<th width='14%' style='padding:8pt; text-align:right; font-size:10pt;'>WEIGHT</th>"
            f"<th width='17%' style='padding:8pt; text-align:right; font-size:10pt;'>GRAND TOTAL</th></tr></thead><tbody>{rows_html}"
            f"<tr><td colspan='5' style='height:75pt;'>&nbsp;</td></tr>"
            f"<tr style='background-color:#f1f5f9;'>"
            f"<td colspan='3' style='padding:10pt 8pt; text-align:right; font-size:10pt; font-weight:bold; border-top:2pt solid #0f172a;'>PROJECT TOTALS:</td>"
            f"<td style='padding:10pt 8pt; text-align:right; font-size:10pt; font-weight:bold; border-top:2pt solid #0f172a;'>{record.get('weight', 0.0):.1f} lbs</td>"
            f"<td style='padding:10pt 8pt; text-align:right; font-size:11pt; font-weight:bold; color:#0284c7; border-top:2pt solid #0f172a;'>${record.get('cost', 0.0):,.2f}</td></tr></tbody></table>"
            f"</body></html>"
        )

        footer_html = (
            f"<html><body style='font-family:Arial, Helvetica, sans-serif; color:#60a5fa; font-size:9pt;'>"
            f"<div style='padding-top:8pt; border-top:1pt solid #94a3b8; line-height:1.45;'>"
            f"<b>TERMS &amp; NOTES:</b><br>"
            f"&bull; Pricing valid for 15 days due to mill steel market fluctuations.<br>"
            f"&bull; Applicable taxes, freight, and field erection excluded unless noted.<br>"
            f"&bull; Thank you for the opportunity to quote your project!</div>"
            f"</body></html>"
        )

        printer = QPrinter(QPrinter.ScreenResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(file_path)
        printer.setPageLayout(QPageLayout(QPageSize(QPageSize.Letter), QPageLayout.Portrait, QMarginsF(0.5, 0.5, 0.5, 0.5), QPageLayout.Inch))

        page_rect = printer.pageRect(QPrinter.DevicePixel)
        body_doc = QTextDocument()
        body_doc.documentLayout().setPaintDevice(printer)
        body_doc.setHtml(body_html)
        body_doc.setPageSize(page_rect.size())

        footer_doc = QTextDocument()
        footer_doc.documentLayout().setPaintDevice(printer)
        footer_doc.setHtml(footer_html)
        footer_doc.setTextWidth(page_rect.width())
        footer_h = footer_doc.size().height()

        import math
        from PySide6.QtCore import QSizeF
        usable_h = max(100.0, page_rect.height() - footer_h - 16.0)
        body_doc.setPageSize(QSizeF(page_rect.width(), usable_h))
        total_pages = max(1, body_doc.pageCount())

        painter = QPainter(printer)
        for pg in range(total_pages):
            if pg > 0:
                printer.newPage()
            painter.save()
            y_offset = pg * usable_h
            painter.translate(0, -y_offset)
            body_doc.drawContents(painter, QRectF(0, y_offset, page_rect.width(), usable_h))
            painter.restore()

            painter.save()
            painter.translate(0, page_rect.height() - footer_h)
            footer_doc.drawContents(painter)
            painter.setPen(QColor("#64748b"))
            painter.drawText(
                QRectF(0, footer_h - 18, page_rect.width(), 18),
                Qt.AlignRight | Qt.AlignVCenter,
                f"Page {pg + 1} of {total_pages}"
            )
            painter.restore()
        painter.end()

        QMessageBox.information(self, "PDF Exported", f"Customer quote saved cleanly to:\n{file_path}")


class AdminControlDashboardPage(QWidget):
    def __init__(self, admin_safeguards_reference, save_callback, parent=None):
        super().__init__(parent)
        self.safeguards = admin_safeguards_reference
        self.save_callback = save_callback
        self._rollback_stack = []
        self._recent_changes = []
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            AdminControlDashboardPage, QStackedWidget { background: transparent !important; }
            QFrame#GlassCard { background-color: rgba(248, 250, 252, 0.80) !important; border: 1px solid #cbd5e1 !important; border-radius: 10px; }
            QFrame#LockGlass { background-color: rgba(248, 250, 252, 0.80) !important; border: 2px solid #0284c7 !important; border-radius: 12px; }
            QLabel { font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 12px; font-weight: 600; color: #0f172a; background: transparent !important; border: none !important; }
            QLineEdit, QComboBox { background-color: rgba(239, 246, 255, 0.80) !important; color: #0f172a !important; border: 1px solid #cbd5e1 !important; border-radius: 6px; padding: 5px 9px; font-family: 'Segoe UI', sans-serif; font-size: 12px; font-weight: 600; }
            QLineEdit:focus, QComboBox:focus { border: 1px solid #38bdf8 !important; }
        """)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent !important;")
        outer.addWidget(self.stack)

        # --- LOCK SCREEN ---
        lock_page = QFrame()
        lock_page.setAttribute(Qt.WA_StyledBackground, True)
        lock_page.setObjectName("LockGlass")
        lock_layout = QVBoxLayout(lock_page)
        lock_layout.setAlignment(Qt.AlignCenter)
        lock_layout.setSpacing(12)

        lock_lbl = QLabel("RESTRICTED ADMIN AREA - ENTER PASSCODE TO UNLOCK SHOP RATES & SAFEGUARDS")
        lock_lbl.setStyleSheet("color: #0369a1; font-size: 12px; font-weight: 700;")
        lock_layout.addWidget(lock_lbl, alignment=Qt.AlignCenter)

        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.setPlaceholderText("Enter Admin Passcode...")
        self.pass_input.setFixedWidth(270)
        self.pass_input.returnPressed.connect(self.unlock_admin_panel)
        lock_layout.addWidget(self.pass_input, alignment=Qt.AlignCenter)

        btn_unlock = QPushButton("UNLOCK ADMIN SETTINGS")
        btn_unlock.setStyleSheet("QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 10px; } QPushButton:hover { background-color: rgba(96, 165, 250, 0.82); color: #0f172a; }")
        btn_unlock.setFixedWidth(270)
        btn_unlock.clicked.connect(self.unlock_admin_panel)
        lock_layout.addWidget(btn_unlock, alignment=Qt.AlignCenter)
        self.stack.addWidget(lock_page)

        # --- UNLOCKED DYNAMIC ADMIN WORKSPACE ---
        admin_page = QWidget()
        admin_page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(admin_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 1. Live Quote Impact Simulator Strip
        sim_card = QFrame()
        sim_card.setStyleSheet("QFrame { background-color: rgba(248, 250, 252, 0.80); border: 2px solid #0284c7; border-radius: 8px; } QLabel { color: #0f172a; font-weight: 600; background: transparent; border: none; } QComboBox { background-color: #eff6ff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 5px; padding: 4px 8px; font-weight: 600; }")
        sim_l = QHBoxLayout(sim_card)
        sim_l.setContentsMargins(12, 8, 12, 8)
        sim_l.setSpacing(8)
        sim_title = QLabel("LIVE QUOTE SIMULATOR:")
        sim_title.setStyleSheet("color: #0369a1; font-weight: 800; font-size: 12px;")
        sim_l.addWidget(sim_title)

        self.sim_member_combo = QComboBox()
        self.sim_member_combo.addItem("W12x26 (20')", ("beam", 26.0, 20.0))
        self.sim_member_combo.addItem("W16x57 (24')", ("beam", 57.0, 24.0))
        self.sim_member_combo.addItem("W18x71 (14.3')", ("beam", 71.0, 14.33))
        self.sim_member_combo.addItem("HSS8x8x3/8 (14.3')", ("hss_tube", 38.89, 14.33))
        sim_l.addWidget(self.sim_member_combo)

        self.sim_weld_combo = QComboBox()
        self.sim_weld_combo.addItems(["24\" Fillet", "24\" PJP", "24\" CJP", "No Weld"])
        sim_l.addWidget(self.sim_weld_combo)

        self.sim_finish_combo = QComboBox()
        self.sim_finish_combo.addItems(["Shop Primer", "Hot-Dip Galv (HDG)", "Powder Coat (PC)"])
        sim_l.addWidget(self.sim_finish_combo)

        self.lbl_sim_preview = QLabel("Calculating...")
        self.lbl_sim_preview.setStyleSheet("color: #065f46; font-weight: 800; font-size: 12px;")
        sim_l.addWidget(self.lbl_sim_preview, 1)

        self.sim_member_combo.currentIndexChanged.connect(self.update_live_simulator)
        self.sim_weld_combo.currentIndexChanged.connect(self.update_live_simulator)
        self.sim_finish_combo.currentIndexChanged.connect(self.update_live_simulator)

        btn_lock = QPushButton("Lock Admin")
        btn_lock.setStyleSheet("background-color: #ffffff; border: 1px solid #fca5a5; color: #b91c1c; font-weight: 700; font-weight: 600; padding: 5px 12px; border-radius: 6px;")
        btn_lock.clicked.connect(self.lock_admin_panel)
        sim_l.addWidget(btn_lock)
        layout.addWidget(sim_card)

        # 2. Filter Bar + Rollback Controls
        ctrl_card = QFrame()
        ctrl_card.setObjectName("GlassCard")
        ctrl_l = QHBoxLayout(ctrl_card)
        ctrl_card.setStyleSheet("QFrame { background-color: rgba(207, 228, 250, 0.82); border: 1px solid #cbd5e1; border-radius: 8px; }")
        ctrl_l.setContentsMargins(12, 7, 12, 7)
        ctrl_l.setSpacing(10)

        ctrl_l.addWidget(QLabel("Filter:"))
        self.rate_search = QLineEdit()
        self.rate_search.setPlaceholderText("Search rates, weld speeds, gates, discounts...")
        self.rate_search.textChanged.connect(self.filter_rate_rows)
        ctrl_l.addWidget(self.rate_search, 2)

        self.cat_filter = QComboBox()
        self.cat_filter.addItems(["All Categories", "Customer Tiers & Multipliers", "Finishes (HDG, PC & Primer)", "Tab 1 Catalog Flat Fees", "Tab 2 Custom Flat Fees", "Labor & Markup", "Machine Safeguard Gates", "Arc-On & Weld Passes"])
        self.cat_filter.currentTextChanged.connect(self.filter_rate_rows)
        ctrl_l.addWidget(self.cat_filter, 1)

        self.rollback_combo = QComboBox()
        self.rollback_combo.setMinimumWidth(195)
        self.rollback_combo.addItem("Rollback Snapshots (0)")
        ctrl_l.addWidget(self.rollback_combo)

        btn_restore_snap = QPushButton("Restore Snapshot")
        btn_restore_snap.setStyleSheet("background-color: #ffffff; border: 1px solid #94a3b8; color: #0f172a; font-weight: 700; font-weight: 600; padding: 6px 10px; border-radius: 6px;")
        btn_restore_snap.clicked.connect(self.restore_selected_snapshot)
        ctrl_l.addWidget(btn_restore_snap)
        layout.addWidget(ctrl_card)

        # 3. Dynamic Draggable 4-Column Parameter Table
        self.rate_table = QTableWidget(0, 4)
        apply_excel_table_style(self.rate_table)
        self.rate_table.setAlternatingRowColors(True)
        self.rate_table.setHorizontalHeaderLabels(["CATEGORY", "PARAMETER / RATE SETTING", "ACTIVE VALUE", "WHAT IT CONTROLS"])
        hdr = self.rate_table.horizontalHeader()
        hdr.setStretchLastSection(True)
        for c_i, w_i in [(0, 195), (1, 290), (2, 120), (3, 380)]:
            hdr.setSectionResizeMode(c_i, QHeaderView.Interactive)
            self.rate_table.setColumnWidth(c_i, w_i)
        hdr.sectionDoubleClicked.connect(lambda c: self.rate_table.resizeColumnToContents(c))
        self.rate_table.verticalHeader().setVisible(False)
        self.rate_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rate_table.setStyleSheet("""
            QTableWidget { background-color: rgba(248, 250, 252, 0.80) !important; color: #0f172a !important; border: 1px solid #cbd5e1; border-radius: 10px; gridline-color: rgba(71, 85, 105, 0.55); font-family: 'Segoe UI', sans-serif; font-size: 12px; font-weight: 600; }
            QTableWidget::viewport, QTableWidget QWidget, QTableCornerButton::section { background: transparent !important; border: none !important; }
            QTableWidget QLineEdit { background-color: #dcebfa !important; color: #0f172a !important; border: 1px solid #38bdf8 !important; padding: 2px 6px !important; }
            QTableWidget::item { padding: 4px 8px; }
            QTableWidget::item:selected, QTableWidget::item:selected:!active { background-color: #93c5fd; color: #0f172a; }
            QHeaderView::section { background-color: rgba(207, 228, 250, 0.92); color: #0369a1; font-family: 'Segoe UI', sans-serif; font-size: 12px; font-weight: 700; padding: 7px; border: none; border-bottom: 1px solid #475569; }
        """)
        self.rate_table.itemChanged.connect(self.on_rate_cell_edited)
        layout.addWidget(self.rate_table, 1)

        # 4. Action Bar + Recent Activity Strip
        act_row = QHBoxLayout()
        act_row.setSpacing(10)
        btn_edit_fee = QPushButton("Edit Selected")
        btn_edit_fee.setStyleSheet("background-color: #ffffff; border: 1px solid #94a3b8; color: #0f172a; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 8px;")
        btn_edit_fee.setMinimumHeight(38)
        btn_edit_fee.clicked.connect(self.edit_selected_rate_row)
        act_row.addWidget(btn_edit_fee, 1)

        btn_add_fee = QPushButton("+ Add New Fee")
        btn_add_fee.setStyleSheet("QPushButton { background-color: #ffffff !important; border: 1.5px solid #0284c7 !important; color: #0284c7 !important; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12.5px; font-weight: 700; border-radius: 6px; padding: 10px; } QPushButton:hover { background-color: rgba(110, 231, 183, 0.86) !important; }")
        btn_add_fee.setMinimumHeight(38)
        btn_add_fee.clicked.connect(self.add_custom_fee_dialog)
        act_row.addWidget(btn_add_fee, 1)

        btn_del_fee = QPushButton("Delete / Hide Fee")
        btn_del_fee.setStyleSheet("background-color: #ffffff; border: 1px solid #fca5a5; color: #b91c1c; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 8px;")
        btn_del_fee.setMinimumHeight(38)
        btn_del_fee.clicked.connect(self.delete_or_hide_selected_fee)
        act_row.addWidget(btn_del_fee, 1)

        btn_save = QPushButton("SAVE & APPLY ALL RATES & FEES")
        btn_save.setStyleSheet("QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 8px; } QPushButton:hover { background-color: rgba(96, 165, 250, 0.82); color: #0f172a; }")
        btn_save.setMinimumHeight(38)
        btn_save.clicked.connect(self.submit_safeguards_changes)
        act_row.addWidget(btn_save, 2)

        self.lbl_activity_strip = QLabel("Recent Admin Activity: Ready - double-click any Active Value cell to edit live.")
        self.lbl_activity_strip.setWordWrap(True)
        self.lbl_activity_strip.setStyleSheet("background-color: rgba(248, 250, 252, 0.80); border: 1px solid #64748b; border-radius: 6px; padding: 8px 12px; color: #1e3a8a; font-size: 12px;")
        act_row.addWidget(self.lbl_activity_strip, 3)
        layout.addLayout(act_row)

        self.populate_rate_table()
        self.update_live_simulator()
        self.stack.addWidget(admin_page)

    def get_parameter_schema(self):
        return [
            ("Customer Tiers & Multipliers", "mult_const_supply", "Construction Supply Multiplier (0.50 = 50% off)", 0.50, "Catalog price multiplier for Construction Supply accounts"),
            ("Customer Tiers & Multipliers", "mult_lumber_yard", "Lumber Yard Multiplier (0.60 = 40% off)", 0.60, "Catalog price multiplier for Lumber Yard accounts"),
            ("Customer Tiers & Multipliers", "cat_base_margin", "Catalog Base Margin Multiplier (1.05 = +5%)", 1.05, "Baseline margin multiplier applied across Tab 1 catalog quotes"),
            ("Customer Tiers & Multipliers", "rush_multiplier", "Rush Order Multiplier (1.25 = +25%)", 1.25, "Multiplier applied when Rush checkbox is selected on Tab 1"),
            ("Finishes (HDG, PC & Primer)", "pc_rate_per_lb", "Powder Coat (PC) Rate ($/lb)", 1.80, "Per-pound finishing rate for Powder Coat on Tab 2"),
            ("Finishes (HDG, PC & Primer)", "hdg_heavy_rate_per_lb", "HDG Heavy Rate (>= 20 lbs) ($/lb)", 0.62, "Hot-Dip Galvanizing rate per lb for items weighing 20 lbs or more"),
            ("Finishes (HDG, PC & Primer)", "hdg_light_rate_per_lb", "HDG Light Rate (< 20 lbs) ($/lb)", 1.88, "Hot-Dip Galvanizing rate per lb for items under 20 lbs"),
            ("Finishes (HDG, PC & Primer)", "card1_hdg_mult", "Card 1 HDG Multiplier (1.15 = +15%)", 1.15, "Multiplier applied when HDG (D12) is checked on Card 1"),
            ("Finishes (HDG, PC & Primer)", "card1_skd_heavy_rate", "Card 1 SKD CCQ Cap Heavy Rate (>= 20 lbs) ($/lb)", 0.80, "Per-pound rate for SKD CCQ Cap (B12) when weight >= 20 lbs"),
            ("Finishes (HDG, PC & Primer)", "primer_rate_per_lb", "Standard Shop Primer Rate ($/lb)", 0.12, "Default shop primer rate on Tab 2 (auto-clears if PC or HDG checked)"),
            ("Tab 1 Catalog Flat Fees", "c1_flush_top_fee", "Card 1 - Flush To Top (C8) Fee ($)", 30.00, "Flat surcharge added when Flush To Top is checked on Card 1"),
            ("Tab 1 Catalog Flat Fees", "c1_rt_strp_fee", "Card 1 - RT STRP OTHR THN 90 (D8) Fee ($)", 25.00, "Flat surcharge for non-90 degree strap on Card 1"),
            ("Tab 1 Catalog Flat Fees", "c1_bccobq_fee", "Card 1 - BCCOBQ (D10) Fee ($)", 11.00, "Flat surcharge for BCCOBQ option on Card 1"),
            ("Tab 1 Catalog Flat Fees", "c1_greater_ht_mult", "Card 1 - Greater Height (C12) Multiplier", 1.05, "Multiplier when Greater Height is checked on Card 1"),
            ("Tab 1 Catalog Flat Fees", "c1_w3_w1_mult", "Card 1 - W3>W1 (B10) Multiplier", 1.10, "Multiplier when W3>W1 is checked on Card 1"),
            ("Tab 1 Catalog Flat Fees", "c1_rough_bm_mult", "Card 1 - Rough BM Sz (C10) Multiplier", 1.25, "Multiplier when Rough Beam Size is checked on Card 1"),
            ("Tab 1 Catalog Flat Fees", "std_skw_slp_fee", "Cards 2-4 - Skew / Slope (SKW / SLP) Fee ($)", 25.00, "Flat surcharge for Skew or Slope on standard height cards"),
            ("Tab 1 Catalog Flat Fees", "std_rgh_lmb_fee", "Cards 2-4 - Rough Lumber (RGH LMB) Fee ($)", 11.00, "Flat surcharge for Rough Lumber on standard height cards"),
            ("Tab 1 Catalog Flat Fees", "std_extra_ht_rate", "Cards 2-4 - Extra Height Rate ($/half-in)", 0.50, "Per half-inch height adder above minimum height on Cards 2-4"),
            ("Tab 1 Catalog Flat Fees", "c56_extra_ht_rate", "Cards 5-6 - Extra Height Rate ($/half-in)", 1.40, "Per half-inch height adder above minimum height on Cards 5-6"),
            ("Tab 1 Catalog Flat Fees", "c56_skw_fee", "Cards 5-6 - Skew Only (SKW) Fee ($)", 44.00, "Flat surcharge for Skew Only on Cards 5-6"),
            ("Tab 1 Catalog Flat Fees", "c56_slp_fee", "Cards 5-6 - Slope Only (SLP) Fee ($)", 42.50, "Flat surcharge for Slope Only on Cards 5-6"),
            ("Tab 1 Catalog Flat Fees", "c56_skw_slp_fee", "Cards 5-6 - Combined Skew & Slope (SKW&SLP) Fee ($)", 50.00, "Flat surcharge when both Skew & Slope are selected on Cards 5-6"),
            ("Tab 1 Catalog Flat Fees", "c56_offset_fee", "Cards 5-6 - Offset Fee ($)", 15.00, "Flat surcharge for Offset on Cards 5-6"),
            ("Tab 1 Catalog Flat Fees", "c7_mod_chrg_fee", "Card 7 - Mod CHRG (K22) Fee ($)", 15.00, "Flat modification surcharge on Card 7 fixed-cost items"),
            ("Tab 1 Catalog Flat Fees", "c8_no_slp_credit", "Card 8 - No Slope (No SLP O25) Reduction ($)", 35.00, "Flat price deduction when No Slope is checked on Card 8"),
            ("Tab 1 Catalog Flat Fees", "c8_msc45_valley_rate", "Card 8 - MSC 4/5 Valley Rate ($/half-in)", 6.00, "Valley height increment rate per half-inch for MSC 4 & MSC 5"),
            ("Tab 1 Catalog Flat Fees", "c8_msc45_ridge_rate", "Card 8 - MSC 4/5 Ridge Rate ($/half-in)", 3.00, "Ridge height increment rate per half-inch for MSC 4 & MSC 5"),
            ("Tab 1 Catalog Flat Fees", "c8_std_valley_rate", "Card 8 - Standard Valley Rate ($/half-in)", 3.20, "Valley height increment rate per half-inch for standard Card 8"),
            ("Tab 1 Catalog Flat Fees", "c8_std_ridge_rate", "Card 8 - Standard Ridge Rate ($/half-in)", 1.60, "Ridge height increment rate per half-inch for standard Card 8"),
            ("Tab 2 Custom Flat Fees", "std_stud_rate", "Standard Drawn-Arc Stud Rate ($/ea)", 5.00, "Flat per-stud charge for standard 3.25 in studs on Tab 2"),
            ("Tab 2 Custom Flat Fees", "hd_stud_rate", "Heavy-Duty (HD) Stud Base Rate ($/ea)", 1.00, "Base labor charge per HD stud (plus steel weight & weld)"),
            ("Tab 2 Custom Flat Fees", "wh_flat_rate", "Welded Hanger (WH) Flat Rate ($)", 75.00, "Flat fabrication fee per Welded Hanger add-on on Tab 2"),
            ("Tab 2 Custom Flat Fees", "torch_lvl1_fee", "Torch Cut - Level 1 Flat Fee ($)", 10.00, "Flat shop rate for Level 1 torch cut operation"),
            ("Tab 2 Custom Flat Fees", "torch_lvl2_fee", "Torch Cut - Level 2 Flat Fee ($)", 20.00, "Flat shop rate for Level 2 torch cut operation"),
            ("Tab 2 Custom Flat Fees", "torch_lvl3_fee", "Torch Cut - Level 3 Flat Fee ($)", 35.00, "Flat shop rate for Level 3 torch cut operation"),
            ("Tab 2 Custom Flat Fees", "torch_lvl4_fee", "Torch Cut - Level 4 Flat Fee ($)", 50.00, "Flat shop rate for Level 4 torch cut operation"),
            ("Tab 2 Custom Flat Fees", "gate_override_fee", "Safeguard Gate Reroute Flat Fee ($)", 25.00, "Flat fee applied when an oversized saw/shear cut reroutes"),
            ("Labor & Markup", "base_labor_rate", "Base Shop Labor Rate ($/hr)", 86.0, "Hourly shop fabrication rate for welding, sawing, drilling & coping"),
            ("Labor & Markup", "eng_labor_rate", "Programming & Detailing Rate ($/hr)", 175.0, "Hourly rate for CNC programming & shop detailing"),
            ("Labor & Markup", "labor_markup", "End-of-Bid Markup Multiplier (1.40 = 40%)", 1.40, "Applied to combined raw material + shop & engineering labor subtotal"),
            ("Labor & Markup", "handling_mins_per_pc", "Heavy Structural Handling (>=40 lbs) (mins)", 15.0, "Base crane/forklift handling for 1st heavy piece (+50% per repeat pc)"),
            ("Labor & Markup", "light_handling_mins_per_pc", "Light Part Handling (<40 lbs) (mins/pc)", 0.75, "Per-piece bench handling for light plates/angles under 40 lbs (+3m batch setup)"),
            ("Labor & Markup", "admin_passcode", "Admin Console Passcode", "Barron", "Passcode required to unlock Admin Center & override gates"),
            ("Labor & Markup", "ai_vision_api_key", "AI Vision Planset API Key (Optional)", "", "Optional Gemini or OpenAI API key for cloud multimodal blueprint vision scanning"),
            ("Labor & Markup", "std_scope_clause_t1", "Catalog Standard Scope Clause (Tab 1)", "Furnished FOB Seattle, WA. Standard catalog hardware lead time 3-5 business days.", "Default clause inserted when clicking + Insert Standard Scope Clause on Tab 1"),
            ("Labor & Markup", "std_scope_clause_t2", "Structural Standard Scope Clause (Tab 2)", "Furnished FOB Seattle, WA. Includes shop fabrication per AISC standards; excludes field erection, field welding, and anchor bolts unless itemized above.", "Default clause inserted when clicking + Insert Standard Scope Clause on Tab 2"),
            ("Machine Safeguard Gates", "max_saw_beam_size", "Max Band Saw Beam Depth", "W16", "Largest W-beam size cut by saw before prompting override / torch"),
            ("Machine Safeguard Gates", "max_drill_diameter", "Max Mechanical Drill Diameter (in)", 1.125, "Largest hole diameter drilled before routing to torch cut"),
            ("Machine Safeguard Gates", "max_manual_punch_weight", "Max Manual Punch Part Weight (lbs)", 45.0, "Heaviest piece hand-fed at punch press before routing to drill"),
            ("Machine Safeguard Gates", "turret_max_length", "CNC Turret / Laser Max Length (in)", 48.0, "Maximum sheet length capacity (48 in = 4 ft)"),
            ("Machine Safeguard Gates", "turret_max_width", "CNC Turret / Laser Max Width (in)", 48.0, "Maximum sheet width capacity (48 in = 4 ft)"),
            ("Machine Safeguard Gates", "carbon_shear_max_thickness", "Carbon Steel Shear Max Thickness (in)", 0.50, "Maximum carbon steel plate thickness for shear"),
            ("Machine Safeguard Gates", "ss_shear_max_thickness", "Stainless Steel Shear Max Thickness (in)", 0.375, "Maximum stainless steel plate thickness for shear"),
            ("Machine Safeguard Gates", "max_press_brake_length", "Press Brake Max Bed Length (in)", 120.0, "Maximum forming bed length (120 in = 10 ft)"),
            ("Arc-On & Weld Passes", "fillet_ipm", "Fillet Weld Arc-On Speed (IPM)", 6.0, "Inches per minute for standard fillet welds"),
            ("Arc-On & Weld Passes", "pjp_ipm", "PJP Groove Weld Speed (IPM)", 2.0, "Inches per minute for Partial Joint Penetration welds"),
            ("Arc-On & Weld Passes", "cjp_ipm", "CJP Groove Weld Speed (IPM)", 2.5, "Inches per minute for Complete Joint Penetration welds"),
            ("Arc-On & Weld Passes", "passes_3_16", "Weld Passes - 3/16 in", 1, "Pass multiplier for 3/16 in weld size"),
            ("Arc-On & Weld Passes", "passes_1_4", "Weld Passes - 1/4 in", 1, "Pass multiplier for 1/4 in weld size"),
            ("Arc-On & Weld Passes", "passes_5_16", "Weld Passes - 5/16 in", 2, "Pass multiplier for 5/16 in weld size"),
            ("Arc-On & Weld Passes", "passes_3_8", "Weld Passes - 3/8 in", 2, "Pass multiplier for 3/8 in weld size"),
            ("Arc-On & Weld Passes", "passes_1_2", "Weld Passes - 1/2 in", 3, "Pass multiplier for 1/2 in weld size"),
            ("Arc-On & Weld Passes", "passes_5_8", "Weld Passes - 5/8 in", 4, "Pass multiplier for 5/8 in weld size"),
            ("Arc-On & Weld Passes", "passes_3_4", "Weld Passes - 3/4 in", 5, "Pass multiplier for 3/4 in weld size"),
            ("Arc-On & Weld Passes", "passes_1", "Weld Passes - 1 in", 7, "Pass multiplier for 1 in weld size"),
            ("Arc-On & Weld Passes", "saw_ipm", "Band Saw Cut Speed (IPM)", 0.8, "Linear inches per minute for cold saw cutting"),
            ("Arc-On & Weld Passes", "drill_spm", "Mechanical Drill Speed (Holes/Min)", 2.0, "Strokes per minute for mechanical drilling"),
            ("Arc-On & Weld Passes", "light_ppm", "Light Plate Punch/Brake Speed (Parts/Min)", 4.0, "Parts per minute under heavy weight cutoff"),
            ("Arc-On & Weld Passes", "heavy_ppm", "Heavy Plate Handling Speed (Parts/Min)", 0.5, "Parts per minute at or above heavy weight cutoff"),
            ("Arc-On & Weld Passes", "heavy_weight_cutoff", "Heavy Part Weight Cutoff (lbs)", 40.0, "Weight threshold switching from Light PPM to Heavy PPM"),
        ]

    def populate_rate_table(self):
        self.rate_table.blockSignals(True)
        hidden = set(self.safeguards.get("hidden_fee_keys", []))
        custom_labels = self.safeguards.get("custom_fee_labels", {})
        rows = []
        for cat, key, label, default_val, desc in self.get_parameter_schema():
            if key in hidden: continue
            rows.append((cat, key, custom_labels.get(key, label), self.safeguards.get(key, default_val), desc, False))
        for cf in self.safeguards.get("custom_extra_fees", []):
            rows.append((cf.get("category", "Tab 2 Custom Flat Fees"), cf["key"], cf["label"], cf["value"], cf.get("desc", "Custom user-defined fee"), True))
        self.rate_table.setRowCount(len(rows))
        for r_i, (cat, key, label, val, desc, is_custom) in enumerate(rows):
            self.rate_table.setRowHeight(r_i, 30)
            c0 = QTableWidgetItem(cat); c0.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled); c0.setForeground(QColor("#0369a1"))
            c1 = QTableWidgetItem(label); c1.setData(Qt.UserRole, key); c1.setData(Qt.UserRole + 1, label)
            c2 = QTableWidgetItem(str(val)); c2.setTextAlignment(Qt.AlignCenter); c2.setForeground(QColor("#047857")); c2.setData(Qt.UserRole, str(val))
            c3 = QTableWidgetItem(desc); c3.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled); c3.setForeground(QColor("#0f172a"))
            self.rate_table.setItem(r_i, 0, c0); self.rate_table.setItem(r_i, 1, c1); self.rate_table.setItem(r_i, 2, c2); self.rate_table.setItem(r_i, 3, c3)
        self.rate_table.blockSignals(False)

    def edit_selected_rate_row(self):
        from PySide6.QtWidgets import QDialog
        row = self.rate_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Row Selected", "Click any rate or fee row in the table first, then click Edit Selected.")
            return
        lbl_item = self.rate_table.item(row, 1)
        val_item = self.rate_table.item(row, 2)
        desc_item = self.rate_table.item(row, 3)

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Parameter / Fee")
        dlg.setMinimumWidth(480)
        dlg.setStyleSheet("QDialog { background-color: #e8eef5; border: 2px solid #38bdf8; } QLabel { color: #0f172a; font-family: 'Segoe UI', sans-serif; font-size: 12px; font-weight: 600; } QLineEdit { background-color: #eff6ff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px; font-size: 12px; font-weight: 600; } QLineEdit:focus { border: 1px solid #38bdf8; }")
        v = QVBoxLayout(dlg)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(10)

        sub = QLabel(desc_item.text())
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #1e3a8a; font-size: 12px;")
        v.addWidget(sub)

        v.addWidget(QLabel("Display Name:"))
        in_name = QLineEdit(lbl_item.text())
        in_name.setMinimumWidth(430)
        v.addWidget(in_name)

        val_row = QHBoxLayout()
        val_row.addWidget(QLabel("Active Value:"))
        in_val = QLineEdit(val_item.text())
        in_val.setFixedWidth(150)
        in_val.setAlignment(Qt.AlignCenter)
        val_row.addWidget(in_val)
        val_row.addStretch()
        v.addLayout(val_row)

        btns = QHBoxLayout()
        btns.addStretch()
        b_cancel = QPushButton("Cancel")
        b_cancel.clicked.connect(dlg.reject)
        b_ok = QPushButton("Apply Changes")
        b_ok.setObjectName("PrimaryAction")
        b_ok.clicked.connect(dlg.accept)
        btns.addWidget(b_cancel)
        btns.addWidget(b_ok)
        v.addLayout(btns)

        if dlg.exec() == QDialog.Accepted:
            if in_name.text().strip():
                lbl_item.setText(in_name.text().strip())
            if in_val.text().strip():
                val_item.setText(in_val.text().strip())

    def add_custom_fee_dialog(self):
        target, ok0 = QInputDialog.getItem(self, "New Custom Fee Target", "Where should this new fee be used?", ["Tab 2 Custom Flat Fees", "Tab 1 Catalog Flat Fees"], 0, False)
        if not ok0: return
        name, ok1 = QInputDialog.getText(self, "New Fee Name", "Enter Fee Display Name (e.g., Field Template Fee):")
        if not ok1 or not name.strip(): return
        amt, ok2 = QInputDialog.getDouble(self, "Fee Amount ($)", "Enter Flat Dollar Rate ($):", 25.00, -99999.0, 999999.0, 2)
        if not ok2: return
        desc, ok3 = QInputDialog.getText(self, "Description", "Short description of what this fee covers:", text=f"Custom flat fee ({target})")
        if not ok3: return
        import re
        slug = "custom_" + re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
        self.push_rollback_snapshot(f"Before Adding {name.strip()}")
        extras = self.safeguards.setdefault("custom_extra_fees", [])
        extras = [e for e in extras if e.get("key") != slug]
        extras.append({"key": slug, "category": target, "label": name.strip(), "value": round(amt, 2), "desc": desc.strip()})
        self.safeguards["custom_extra_fees"] = extras
        self.safeguards[slug] = round(amt, 2)
        self.save_callback(); self.populate_rate_table(); self.update_live_simulator()
        self.log_admin_activity(f"Added fee: {name.strip()} (${amt:,.2f})")

    def delete_or_hide_selected_fee(self):
        row = self.rate_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Row Selected", "Click a fee row in the table first.")
            return
        key = self.rate_table.item(row, 1).data(Qt.UserRole)
        lbl = self.rate_table.item(row, 1).text()
        if key in {"base_labor_rate", "eng_labor_rate", "labor_markup", "admin_passcode"}:
            QMessageBox.warning(self, "Core Rate Protected", "Core labor rates and the Admin Passcode cannot be deleted.")
            return
        if QMessageBox.question(self, "Confirm Remove Fee", f"Remove '{lbl}' from the active fee list?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self.push_rollback_snapshot(f"Before Removing {lbl}")
        extras = self.safeguards.get("custom_extra_fees", [])
        if any(e.get("key") == key for e in extras):
            self.safeguards["custom_extra_fees"] = [e for e in extras if e.get("key") != key]
            self.safeguards.pop(key, None)
        else:
            hidden = self.safeguards.setdefault("hidden_fee_keys", [])
            if key not in hidden: hidden.append(key)
        self.save_callback(); self.populate_rate_table(); self.update_live_simulator()
        self.log_admin_activity(f"Removed fee: {lbl}")

    def filter_rate_rows(self):
        q = self.rate_search.text().strip().lower()
        cat_sel = self.cat_filter.currentText()
        for r_i in range(self.rate_table.rowCount()):
            cat_txt = self.rate_table.item(r_i, 0).text()
            lbl_txt = self.rate_table.item(r_i, 1).text().lower()
            desc_txt = self.rate_table.item(r_i, 3).text().lower()
            cat_ok = (cat_sel == "All Categories") or (cat_txt == cat_sel)
            txt_ok = (not q) or (q in lbl_txt) or (q in desc_txt) or (q in cat_txt.lower())
            self.rate_table.setRowHidden(r_i, not (cat_ok and txt_ok))

    def on_rate_cell_edited(self, item):
        if item.column() == 1:
            if item.text().strip() != item.data(Qt.UserRole + 1):
                item.setBackground(QColor(245, 158, 11, 75)); item.setForeground(QColor("#b45309"))
            else:
                item.setBackground(QColor(0, 0, 0, 0)); item.setForeground(QColor("#f8fafc"))
        elif item.column() == 2:
            if item.text().strip() != item.data(Qt.UserRole):
                item.setBackground(QColor(245, 158, 11, 75))
                item.setForeground(QColor("#b45309"))
            else:
                item.setBackground(QColor(0, 0, 0, 0))
                item.setForeground(QColor("#047857"))
            self.update_live_simulator()

    def _read_draft_safeguards(self):
        draft = dict(self.safeguards)
        for r_i in range(self.rate_table.rowCount()):
            key = self.rate_table.item(r_i, 1).data(Qt.UserRole)
            raw_v = self.rate_table.item(r_i, 2).text().strip()
            draft[key] = (raw_v.upper() if key == "max_saw_beam_size" else raw_v) if key in {"max_saw_beam_size", "admin_passcode", "std_scope_clause_t1", "std_scope_clause_t2", "ai_vision_api_key"} else float(raw_v)
        return draft

    def update_live_simulator(self):
        try:
            d = self._read_draft_safeguards()
            l_rate = float(d.get("base_labor_rate", 86.0))
            markup = float(d.get("labor_markup", 1.40))
            drill_spm = max(0.01, float(d.get("drill_spm", 2.0)))
            h_mins = float(d.get("handling_mins_per_pc", 15.0))

            _, uw, ln_ft = self.sim_member_combo.currentData() if hasattr(self, "sim_member_combo") else ("beam", 26.0, 20.0)
            wgt = uw * ln_ft
            mat_cost = wgt * 1.30

            w_txt = self.sim_weld_combo.currentText() if hasattr(self, "sim_weld_combo") else "24\" Fillet"
            if "Fillet" in w_txt:
                weld_hrs = 24.0 / max(0.01, float(d.get("fillet_ipm", 6.0))) / 60.0
            elif "PJP" in w_txt:
                weld_hrs = 24.0 / max(0.01, float(d.get("pjp_ipm", 2.0))) / 60.0
            elif "CJP" in w_txt:
                weld_hrs = 24.0 / max(0.01, float(d.get("cjp_ipm", 2.5))) / 60.0
            else:
                weld_hrs = 0.0

            f_txt = self.sim_finish_combo.currentText() if hasattr(self, "sim_finish_combo") else "Shop Primer"
            if "HDG" in f_txt:
                fin_rate = float(d.get("hdg_heavy_rate_per_lb", 0.62)) if wgt >= 20.0 else float(d.get("hdg_light_rate_per_lb", 1.88))
            elif "Powder" in f_txt:
                fin_rate = float(d.get("pc_rate_per_lb", 1.80))
            else:
                fin_rate = float(d.get("primer_rate_per_lb", 0.12))

            lab_hrs = (h_mins / 60.0) + (6.0 / drill_spm / 60.0) + weld_hrs
            raw_sub = mat_cost + (wgt * fin_rate) + (lab_hrs * l_rate)
            quoted = raw_sub * markup
            self.lbl_sim_preview.setText(f"{wgt:,.0f} lbs  |  Raw Cost: ${raw_sub:,.2f}  |  Customer Quote ({markup:.2f}x): ${quoted:,.2f}")
        except Exception:
            self.lbl_sim_preview.setText("Live Simulator: Enter valid numeric values to preview quote impact.")

    def push_rollback_snapshot(self, label):
        import copy
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._rollback_stack.insert(0, (f"{ts} - {label}", copy.deepcopy(self.safeguards)))
        self._rollback_stack = self._rollback_stack[:6]
        self.rollback_combo.clear()
        for snap_lbl, _ in self._rollback_stack:
            self.rollback_combo.addItem(snap_lbl)

    def restore_selected_snapshot(self):
        idx = self.rollback_combo.currentIndex()
        if not self._rollback_stack or idx < 0 or idx >= len(self._rollback_stack):
            QMessageBox.information(self, "No Snapshot", "No rollback snapshot recorded in this session yet.")
            return
        snap_lbl, snap_data = self._rollback_stack[idx]
        self.safeguards.clear(); self.safeguards.update(snap_data)
        self.save_callback(); self.populate_rate_table(); self.update_live_simulator()
        self.log_admin_activity(f"Restored ({snap_lbl})")
        QMessageBox.information(self, "Restored", f"Reverted rates & safeguards to: {snap_lbl}")

    def log_admin_activity(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M")
        self._recent_changes = ([f"[{ts}] {msg}"] + self._recent_changes)[:5]
        if hasattr(self, "lbl_activity_strip"):
            self.lbl_activity_strip.setText("Recent Activity: " + "  -  ".join(self._recent_changes))

    def submit_safeguards_changes(self):
        try:
            draft = self._read_draft_safeguards()
            if float(draft.get("fillet_ipm", 6.0)) <= 0 or float(draft.get("pjp_ipm", 2.0)) <= 0 or float(draft.get("cjp_ipm", 0.1)) <= 0:
                QMessageBox.warning(self, "Invalid Speed", "Arc-On IPM speeds must be greater than zero.")
                return
            self.push_rollback_snapshot("Before Rate Save")
            changed = [f"{self.rate_table.item(r, 1).text()} -> {self.rate_table.item(r, 2).text().strip()}" for r in range(self.rate_table.rowCount()) if self.rate_table.item(r, 2).text().strip() != self.rate_table.item(r, 2).data(Qt.UserRole)]
            draft["max_shear_length"] = draft.get("max_press_brake_length", 120.0)
            lbl_map = dict(draft.get("custom_fee_labels", {}))
            extras_by_key = {e["key"]: e for e in draft.get("custom_extra_fees", [])}
            for r_i in range(self.rate_table.rowCount()):
                k_i = self.rate_table.item(r_i, 1).data(Qt.UserRole)
                new_lbl = self.rate_table.item(r_i, 1).text().strip()
                if new_lbl:
                    lbl_map[k_i] = new_lbl
                    if k_i in extras_by_key:
                        extras_by_key[k_i]["label"] = new_lbl
                        extras_by_key[k_i]["value"] = draft.get(k_i, extras_by_key[k_i]["value"])
            draft["custom_fee_labels"] = lbl_map
            self.safeguards.clear(); self.safeguards.update(draft)
            self.save_callback(); self.populate_rate_table(); self.update_live_simulator()
            self.log_admin_activity(", ".join(changed[:2]) if changed else "Saved settings")
            QMessageBox.information(self, "Saved", "All shop rates, customer tiers, flat fees, and safeguards updated.")
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Ensure all numeric fields contain valid numbers before saving.")

    def unlock_admin_panel(self):
        if self.pass_input.text() == self.safeguards.get("admin_passcode", "Barron"):
            self.pass_input.clear(); self.stack.setCurrentIndex(1)
            if hasattr(self, "admin_mode_bar"): self.admin_mode_bar.setVisible(True)
        else:
            QMessageBox.warning(self, "Access Denied", "Incorrect administrative passcode."); self.pass_input.clear()

    def lock_admin_panel(self):
        self.stack.setCurrentIndex(0)
        if hasattr(self, "admin_mode_bar"): self.admin_mode_bar.setVisible(False)

    def attach_catalog_admin_widget(self, widget):
        if not hasattr(self, "catalog_page_layout"):
            self.catalog_page = QWidget(); self.catalog_page_layout = QVBoxLayout(self.catalog_page); self.catalog_page_layout.setContentsMargins(0, 0, 0, 0)
            self.stack.addWidget(self.catalog_page)
            self.admin_mode_bar = QFrame(); self.admin_mode_bar.setVisible(False); self.admin_mode_bar.setStyleSheet("QFrame { background-color: rgba(248, 250, 252, 0.80); border: 1px solid #cbd5e1; border-radius: 8px; }")
            m_l = QHBoxLayout(self.admin_mode_bar); m_l.setContentsMargins(10, 6, 10, 6)
            self.btn_mode_rates = QPushButton("Shop Rates & Safeguards")
            self.btn_mode_catalog = QPushButton("Hangers & Catalog Matrix Admin")
            self.btn_mode_steel = QPushButton("Structural Steel Members")
            self.btn_mode_rates.setStyleSheet("background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-weight: 600; padding: 8px 16px; border-radius: 6px;")
            self.btn_mode_catalog.setStyleSheet("background-color: rgba(239, 246, 255, 0.65); border: 1px solid #cbd5e1; color: #000000; font-weight: 600; padding: 8px 16px; border-radius: 6px;")
            self.btn_mode_steel.setStyleSheet("background-color: rgba(239, 246, 255, 0.65); border: 1px solid #cbd5e1; color: #000000; font-weight: 600; padding: 8px 16px; border-radius: 6px;")
            self.btn_mode_rates.clicked.connect(lambda: self.switch_admin_subview(0))
            self.btn_mode_catalog.clicked.connect(lambda: self.switch_admin_subview(1))
            self.btn_mode_steel.clicked.connect(lambda: self.switch_admin_subview(2))
            m_l.addWidget(self.btn_mode_rates); m_l.addWidget(self.btn_mode_catalog); m_l.addWidget(self.btn_mode_steel); m_l.addStretch()
            self._build_steel_members_subview()
            self.layout().insertWidget(0, self.admin_mode_bar)
        self.catalog_page_layout.addWidget(widget)

    def switch_admin_subview(self, idx):
        self.stack.setCurrentIndex(idx + 1)
        on_s = "background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-weight: 600; padding: 8px 16px; border-radius: 6px;"
        off_s = "background-color: rgba(239, 246, 255, 0.65); border: 1px solid #cbd5e1; color: #000000; font-weight: 600; padding: 8px 16px; border-radius: 6px;"
        self.btn_mode_rates.setStyleSheet(on_s if idx == 0 else off_s)
        self.btn_mode_catalog.setStyleSheet(on_s if idx == 1 else off_s)
        if hasattr(self, "btn_mode_steel"):
            self.btn_mode_steel.setStyleSheet(on_s if idx == 2 else off_s)

    def _build_steel_members_subview(self):
        self.steel_page = QWidget()
        sl = QVBoxLayout(self.steel_page)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(8)

        top_bar = QFrame(); top_bar.setStyleSheet("QFrame { background-color: rgba(248, 250, 252, 0.80) !important; border: 1px solid #cbd5e1 !important; border-radius: 8px; }")
        tl = QHBoxLayout(top_bar); tl.setContentsMargins(12, 8, 12, 8); tl.setSpacing(10)
        tl.addWidget(QLabel("Shape:"))
        self.steel_shape_combo = QComboBox()
        self.steel_shape_combo.addItems(["beam", "channel", "hss_tube", "angle", "pipe", "plate", "flat_bar", "round_bar", "square_bar"])
        self.steel_shape_combo.currentTextChanged.connect(self.populate_steel_members_table)
        tl.addWidget(self.steel_shape_combo, 1)

        self.steel_search_input = QLineEdit()
        self.steel_search_input.setPlaceholderText("Filter steel designations (e.g., W12, HSS6, L4X4)...")
        self.steel_search_input.textChanged.connect(self.filter_steel_members_table)
        tl.addWidget(self.steel_search_input, 2)
        sl.addWidget(top_bar)

        self.steel_table = QTableWidget(0, 4)
        apply_excel_table_style(self.steel_table)
        self.steel_table.setAlternatingRowColors(True)
        self.steel_table.setHorizontalHeaderLabels(["DESIGNATION", "CARBON WT (LB/FT or SQFT)", "PRIMARY DIM (IN)", "SECONDARY / THK (IN)"])
        shdr = self.steel_table.horizontalHeader()
        shdr.setStretchLastSection(True)
        for c_i, w_i in [(0, 260), (1, 190), (2, 170), (3, 190)]:
            shdr.setSectionResizeMode(c_i, QHeaderView.Interactive)
            self.steel_table.setColumnWidth(c_i, w_i)
        self.steel_table.verticalHeader().setVisible(False)
        self.steel_table.setStyleSheet(self.rate_table.styleSheet())
        sl.addWidget(self.steel_table, 1)

        bot_bar = QHBoxLayout(); bot_bar.setSpacing(10)
        b_add_st = QPushButton("+ Add Steel Member")
        b_add_st.setStyleSheet("QPushButton { background-color: #ffffff !important; border: 1.5px solid #0284c7 !important; color: #0284c7 !important; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12.5px; font-weight: 700; border-radius: 6px; padding: 8px; } QPushButton:hover { background-color: rgba(110, 231, 183, 0.86) !important; }"); b_add_st.setMinimumHeight(38)
        b_add_st.clicked.connect(self.add_steel_member_dialog)
        bot_bar.addWidget(b_add_st, 1)

        b_del_st = QPushButton("Delete Selected Member")
        b_del_st.setStyleSheet("background-color: #ffffff; border: 1px solid #fca5a5; color: #b91c1c; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 8px;")
        b_del_st.setMinimumHeight(38)
        b_del_st.clicked.connect(self.delete_selected_steel_member)
        bot_bar.addWidget(b_del_st, 1)

        b_save_st = QPushButton("SAVE & RELOAD STEEL MATRIX TO TAB 2")
        b_save_st.setStyleSheet("QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 8px; } QPushButton:hover { background-color: rgba(96, 165, 250, 0.82); color: #0f172a; }"); b_save_st.setMinimumHeight(38)
        b_save_st.clicked.connect(self.save_steel_members_edits)
        bot_bar.addWidget(b_save_st, 2)
        sl.addLayout(bot_bar)

        self.stack.addWidget(self.steel_page)
        self.populate_steel_members_table()

    @staticmethod
    def _natural_steel_sort_key(item):
        import re
        des = str(item.get("designation", "")).upper()
        prefix_rank = 1 if des.startswith("MC") else (1 if des.startswith("S") and not des.startswith("SQ") else 0)
        parts = [float(tok) if re.match(r"^\d+(?:\.\d+)?$", tok) else tok for tok in re.split(r"(\d+(?:\.\d+)?)", des)]
        return (prefix_rank, parts)

    def _steel_dim_keys(self, shape):
        return {
            "beam": ("weight_steel_lb_ft", "depth_in", "flange_width_in"),
            "channel": ("weight_steel_lb_ft", "depth_in", "flange_width_in"),
            "hss_tube": ("weight_steel_lb_ft", "width_in", "height_in"),
            "angle": ("weight_steel_lb_ft", "leg1_in", "leg2_in"),
            "pipe": ("weight_steel_lb_ft", "od_in", "wall_thickness_in"),
            "plate": ("weight_steel_lb_sqft", "thickness_in", "thickness_in"),
            "flat_bar": ("weight_steel_lb_ft", "width_in", "thickness_in"),
            "round_bar": ("weight_steel_lb_ft", "diameter_in", "diameter_in"),
            "square_bar": ("weight_steel_lb_ft", "size_in", "size_in"),
        }.get(shape, ("weight_steel_lb_ft", "depth_in", "flange_width_in"))

    def populate_steel_members_table(self):
        shape = self.steel_shape_combo.currentText()
        mp = get_workspace_path("steel_matrix.json")
        self._steel_blob = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
        items = self._steel_blob.get(shape, [])
        wk, d1k, d2k = self._steel_dim_keys(shape)
        self.steel_table.blockSignals(True)
        self.steel_table.setRowCount(len(items))
        for r_i, it in enumerate(items):
            self.steel_table.setRowHeight(r_i, 28)
            c0 = QTableWidgetItem(str(it.get("designation", "")))
            c1 = QTableWidgetItem(str(it.get(wk, 0.0))); c1.setTextAlignment(Qt.AlignCenter); c1.setForeground(QColor("#047857"))
            c2 = QTableWidgetItem(str(it.get(d1k, 0.0))); c2.setTextAlignment(Qt.AlignCenter)
            c3 = QTableWidgetItem(str(it.get(d2k, it.get("thickness_in", 0.0)))); c3.setTextAlignment(Qt.AlignCenter)
            self.steel_table.setItem(r_i, 0, c0); self.steel_table.setItem(r_i, 1, c1); self.steel_table.setItem(r_i, 2, c2); self.steel_table.setItem(r_i, 3, c3)
        self.steel_table.blockSignals(False)
        self.filter_steel_members_table()

    def filter_steel_members_table(self):
        q = self.steel_search_input.text().strip().lower()
        for r_i in range(self.steel_table.rowCount()):
            self.steel_table.setRowHidden(r_i, bool(q and q not in self.steel_table.item(r_i, 0).text().lower()))

    def add_steel_member_dialog(self):
        shape = self.steel_shape_combo.currentText()
        des, ok0 = QInputDialog.getText(self, f"New {shape} Member", "Designation (e.g., W14X90, HSS6X4X1/4, L4X3X3/8):")
        if not ok0 or not des.strip(): return
        w_val, ok1 = QInputDialog.getDouble(self, "Carbon Steel Weight", "Weight (lb/ft, or lb/sqft for plate):", 20.0, 0.001, 99999.0, 3)
        if not ok1: return
        d1_val, ok2 = QInputDialog.getDouble(self, "Primary Dimension", "Depth / Width / OD / Diameter (in):", 6.0, 0.001, 999.0, 3)
        if not ok2: return
        d2_val, ok3 = QInputDialog.getDouble(self, "Secondary / Wall Thickness", "Flange Width / Height / Thickness (in):", 4.0, 0.001, 999.0, 3)
        if not ok3: return
        wk, d1k, d2k = self._steel_dim_keys(shape)
        entry = {"designation": des.strip().upper(), wk: round(w_val, 3), d1k: round(d1_val, 3), d2k: round(d2_val, 3)}
        if wk == "weight_steel_lb_ft":
            entry["weight_ss304_lb_ft"] = round(w_val * 1.019, 3)
            entry["weight_ss316_lb_ft"] = round(w_val * 1.023, 3)
        else:
            entry["weight_ss304_lb_sqft"] = round(w_val * 1.019, 3)
            entry["weight_ss316_lb_sqft"] = round(w_val * 1.023, 3)
        self._steel_blob.setdefault(shape, []).append(entry)
        self._steel_blob[shape].sort(key=self._natural_steel_sort_key)
        json.dump(self._steel_blob, open(get_workspace_path("steel_matrix.json"), "w", encoding="utf-8"), indent=4)
        self.populate_steel_members_table()
        if hasattr(self.window(), "custom_quoting_tab"): self.window().custom_quoting_tab.load_steel_json_matrix()
        self.log_admin_activity(f"Added {des.strip().upper()} to {shape}")

    def delete_selected_steel_member(self):
        row = self.steel_table.currentRow()
        if row < 0: return
        shape = self.steel_shape_combo.currentText()
        des = self.steel_table.item(row, 0).text()
        if QMessageBox.question(self, "Confirm Delete", f"Remove {des} from {shape}?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes: return
        self._steel_blob[shape] = [x for x in self._steel_blob.get(shape, []) if x.get("designation") != des]
        json.dump(self._steel_blob, open(get_workspace_path("steel_matrix.json"), "w", encoding="utf-8"), indent=4)
        self.populate_steel_members_table()
        if hasattr(self.window(), "custom_quoting_tab"): self.window().custom_quoting_tab.load_steel_json_matrix()
        self.log_admin_activity(f"Removed {des} from {shape}")

    def save_steel_members_edits(self):
        shape = self.steel_shape_combo.currentText()
        wk, d1k, d2k = self._steel_dim_keys(shape)
        items = self._steel_blob.get(shape, [])
        try:
            for r_i in range(min(len(items), self.steel_table.rowCount())):
                des = self.steel_table.item(r_i, 0).text().strip()
                wv = float(self.steel_table.item(r_i, 1).text().strip())
                d1v = float(self.steel_table.item(r_i, 2).text().strip())
                d2v = float(self.steel_table.item(r_i, 3).text().strip())
                items[r_i]["designation"] = des
                items[r_i][wk] = wv; items[r_i][d1k] = d1v; items[r_i][d2k] = d2v
                if wk == "weight_steel_lb_ft":
                    items[r_i]["weight_ss304_lb_ft"] = round(wv * 1.019, 3); items[r_i]["weight_ss316_lb_ft"] = round(wv * 1.023, 3)
            self._steel_blob[shape].sort(key=self._natural_steel_sort_key)
            json.dump(self._steel_blob, open(get_workspace_path("steel_matrix.json"), "w", encoding="utf-8"), indent=4)
            self.populate_steel_members_table()
            if hasattr(self.window(), "custom_quoting_tab"): self.window().custom_quoting_tab.load_steel_json_matrix()
            self.log_admin_activity(f"Saved {shape} steel matrix")
            QMessageBox.information(self, "Steel Matrix Saved", f"Updated {shape} members and reloaded Tab 2.")
        except ValueError:
            QMessageBox.warning(self, "Invalid Number", "Ensure all Weight and Dimension cells contain valid numbers.")

