import os
import sys
import json
import math
import datetime
import textwrap
from PySide6.QtCore import Qt, QMarginsF
from PySide6.QtGui import QTextDocument, QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QComboBox, QLineEdit, QPushButton, QFrame, QScrollArea, 
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, 
    QMessageBox, QMainWindow, QCheckBox, QSplitter, QInputDialog, QStackedWidget,
    QFileDialog
)

def get_workspace_path(filename=""):
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, filename) if filename else base_dir

SANDBOX_MEMBER_STYLESHEET = """
QScrollArea, QScrollArea > QWidget, QScrollArea::viewport, #LeftScrollContainer { 
    background: transparent !important; 
    border: none; 
}
QLabel { 
    font-family: 'Segoe UI', Arial, sans-serif; 
    font-weight: bold; 
    font-size: 12px; 
    color: #f8fafc;
}
QComboBox, QLineEdit { 
    background-color: rgba(15, 23, 42, 0.85); 
    color: #ffffff !important; 
    border: 1px solid #334155; 
    padding: 5px; 
    border-radius: 4px; 
}
QComboBox:hover, QLineEdit:hover { border: 1px solid #475569; }
QComboBox:focus, QLineEdit:focus { border: 1px solid #38bdf8; }
QCheckBox { color: #f8fafc; font-weight: bold; font-size: 11px; }
QPushButton#PrimaryAction { background-color: #0284c7; color: #ffffff; font-weight: bold; border-radius: 6px; padding: 12px; }
QPushButton#PrimaryAction:hover { background-color: #0369a1; }
QPushButton#EmeraldAction { background-color: #059669; color: #ffffff; font-weight: bold; border-radius: 4px; padding: 6px; }
QPushButton#EmeraldAction:hover { background-color: #047857; }
QTableWidget {
    background-color: rgba(30, 41, 59, 0.45);
    border: 2px solid #334155;
    border-radius: 8px;
    gridline-color: #334155;
    color: #f8fafc;
}
QHeaderView::section {
    background-color: #0f172a;
    color: #38bdf8;
    padding: 6px;
    font-weight: bold;
    border: 1px solid #334155;
}
"""
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
        total_needed_ft = cut_length * qty
        if shape_key == "plate":
            return total_needed_ft
        if shape_key == "beam":
            if total_needed_ft <= 20.0:
                return 20.0
            return math.ceil(total_needed_ft / 5.0) * 5.0
        if shape_key in ["angle", "channel", "flat_bar", "round_bar", "square_bar"]:
            return 20.0 if total_needed_ft <= 20.0 else 40.0
        if shape_key in ["hss_tube", "pipe"]:
            if total_needed_ft <= 20.0:
                return 20.0
            if total_needed_ft <= 24.0:
                return 24.0
            return 40.0
        return total_needed_ft

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
                "CJP": float(safeguards.get("cjp_ipm", 0.1))
            }
            pass_map = {
                "3/16\"": float(safeguards.get("passes_3_16", 1)),
                "1/4\"": float(safeguards.get("passes_1_4", 1)),
                "5/16\"": float(safeguards.get("passes_5_16", 2)),
                "3/8\"": float(safeguards.get("passes_3_8", 2)),
                "1/2\"": float(safeguards.get("passes_1_2", 3))
            }
            ipm = ipm_map.get(weld_type, 6.0)
            passes = pass_map.get(weld_size, 1)
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

        self.btn_delete = QPushButton("❌")
        self.btn_delete.setFixedWidth(28)
        self.btn_delete.setStyleSheet("background-color: rgba(220, 38, 38, 0.2); color: #ef4444; border: 1px solid #dc2626;")
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
        self.combo_weld_size.addItems(["3/16\"", "1/4\"", "5/16\"", "3/8\"", "1/2\""])
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
            self.type_select.currentIndexChanged.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.type_select.clear()

        options_map = {
            "beam": [
                "Stiffeners", "Standard Studs", "HD Studs", "Drill Holes",
                "NSC-Angled cuts", "WH-Welded Hanger", "Torch cut", "Cope",
                "Standard End Plate", "Top Flange End Plate", "Band Saw Cut"
            ],
            "channel": [
                "Standard Studs", "HD Studs", "Drill Holes",
                "NSC-Angled cuts", "Torch cut", "Cope", "Band Saw Cut"
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

        self.type_select.addItems(options_map.get(shape_key, ["Drill Holes"]))
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
        self.setStyleSheet("QFrame#DynamicMemberCard { background-color: rgba(30, 41, 59, 0.45); border: 2px solid #334155; border-radius: 8px; }")
        self.init_ui()

    def init_ui(self):
        self.card_layout = QVBoxLayout(self)
        self.card_layout.setContentsMargins(12, 12, 12, 12)
        self.card_layout.setSpacing(10)

        self.header_lbl = QLabel("STRUCTURAL BEAM MEMBER")
        self.header_lbl.setStyleSheet("color: #38bdf8; font-size: 13px; font-weight: bold;")
        self.card_layout.addWidget(self.header_lbl)

        self.grid = QGridLayout()
        self.grid.setSpacing(8)

        self.grid.addWidget(QLabel("Select Profile Variant:"), 0, 0)
        self.combo_model = QComboBox()
        self.combo_model.currentIndexChanged.connect(self.trigger_geometry_updates)
        self.grid.addWidget(self.combo_model, 0, 1)

        self.lbl_extent = QLabel("Length Input (ft):")
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
        self.chk_powder = QCheckBox("Apply Powder Coating (PC)")
        self.chk_galv = QCheckBox("Apply Hot-Dip Galvanized (HDG)")
        treat_layout.addWidget(self.chk_powder)
        treat_layout.addWidget(self.chk_galv)
        self.card_layout.addWidget(treatment_host)

        self.card_layout.addWidget(QLabel("Line-Item Fabrication Add-ons:"))
        self.addon_host = QWidget()
        self.addon_layout = QVBoxLayout(self.addon_host)
        self.addon_layout.setContentsMargins(0, 0, 0, 0)
        self.addon_layout.setSpacing(6)
        self.card_layout.addWidget(self.addon_host)

        self.btn_add_op = QPushButton("➕ Append Fabrication Add-on")
        self.btn_add_op.setObjectName("EmeraldAction")
        self.btn_add_op.clicked.connect(self.add_addon_row)
        self.card_layout.addWidget(self.btn_add_op)

        self.btn_calc = QPushButton("Add Component to Active Project Workbook")
        self.btn_calc.setObjectName("PrimaryAction")
        self.btn_calc.clicked.connect(self.submit_card_calculation)
        self.card_layout.addWidget(self.btn_calc)

    def toggle_custom_mill_input(self, checked):
        self.input_custom_mill.setVisible(checked)
        if checked:
            self.input_custom_mill.setText(self.input_extent.text().strip())

    def add_addon_row(self):
        row = AddonRowWidget(remove_callback=self.remove_addon_row, parent_card=self)
        self.addon_layout.addWidget(row)
        row.populate_surcharges_by_shape(self.active_shape_key)
        self.addon_rows.append(row)

    def remove_addon_row(self, row_widget):
        if row_widget in self.addon_rows:
            self.addon_rows.remove(row_widget)
        row_widget.deleteLater()

    def clear_all_addon_rows(self):
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
        self.lbl_extent.setText("Plate Length (in):" if is_plate else "Length Input (ft):")
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
class StructuralQuotingSandbox(QWidget):
    def __init__(self, finalize_project_callback, admin_safeguards_reference, parent=None):
        super().__init__(parent)
        self.steel_matrix_data = {}
        self.current_project_items = []
        self.finalize_project_callback = finalize_project_callback
        self.safeguards = admin_safeguards_reference

        self.build_workspace_ui()
        self.load_steel_json_matrix()

    def build_workspace_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(15)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("LeftScrollContainer")
        self.deck_layout = QVBoxLayout(container)
        self.deck_layout.setSpacing(12)

        cust_card = QWidget()
        cust_card.setStyleSheet("background-color: rgba(30, 41, 59, 0.45); border: 2px solid #334155; border-radius: 8px;")
        cust_grid = QGridLayout(cust_card)
        cust_grid.addWidget(QLabel("Customer Name:"), 0, 0)
        self.input_cust_name = QLineEdit()
        self.input_cust_name.setPlaceholderText("Customer Name / Company...")
        cust_grid.addWidget(self.input_cust_name, 0, 1)

        cust_grid.addWidget(QLabel("Project Name:"), 1, 0)
        self.input_proj_name = QLineEdit()
        self.input_proj_name.setPlaceholderText("Project Reference / Bid ID...")
        cust_grid.addWidget(self.input_proj_name, 1, 1)
        self.deck_layout.addWidget(cust_card)

        global_card = QWidget()
        global_card.setStyleSheet("background-color: rgba(30, 41, 59, 0.45); border: 2px solid #334155; border-radius: 8px;")
        g_grid = QGridLayout(global_card)
        g_grid.addWidget(QLabel("Inventory Category:"), 0, 0)
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
        self.main_layout.addWidget(scroll, 6)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        self.ledger_textbox = QTextEdit()
        self.ledger_textbox.setReadOnly(True)
        self.ledger_textbox.setLineWrapMode(QTextEdit.WidgetWidth)
        self.ledger_textbox.setStyleSheet("""
            QTextEdit {
                background-color: rgba(30, 41, 59, 0.45) !important; color: #f8fafc !important;
                border: 2px solid #334155; font-family: 'Consolas', 'Courier New', monospace; font-size: 13px; border-radius: 8px; padding: 12px;
            }
        """)
        right_layout.addWidget(self.ledger_textbox)

        eng_card = QWidget()
        eng_card.setStyleSheet("background-color: rgba(30, 41, 59, 0.45); border: 2px solid #334155; border-radius: 8px;")
        eng_layout = QHBoxLayout(eng_card)
        eng_layout.setContentsMargins(10, 8, 10, 8)
        eng_layout.addWidget(QLabel("💻 Programming Hrs:"))
        self.input_prog_hrs = QLineEdit("0")
        self.input_prog_hrs.setFixedWidth(55)
        self.input_prog_hrs.textChanged.connect(self.sync_local_workbench_view)
        eng_layout.addWidget(self.input_prog_hrs)

        eng_layout.addWidget(QLabel("📐 Detailing Hrs:"))
        self.input_detail_hrs = QLineEdit("0")
        self.input_detail_hrs.setFixedWidth(55)
        self.input_detail_hrs.textChanged.connect(self.sync_local_workbench_view)
        eng_layout.addWidget(self.input_detail_hrs)
        eng_layout.addStretch()
        right_layout.addWidget(eng_card)

        self.btn_finalize_quote = QPushButton("🔒 FINALIZE COMPLETE GROUPED PROJECT BID")
        self.btn_finalize_quote.setObjectName("PrimaryAction")
        self.btn_finalize_quote.setMinimumHeight(45)
        self.btn_finalize_quote.clicked.connect(self.pack_and_finalize_project_quote)
        right_layout.addWidget(self.btn_finalize_quote)

        self.btn_clear_canvas = QPushButton("❌ Clear Workspace Canvas")
        self.btn_clear_canvas.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; border-radius: 4px; padding: 6px;")
        self.btn_clear_canvas.clicked.connect(self.clear_canvas_session)
        right_layout.addWidget(self.btn_clear_canvas)

        self.main_layout.addWidget(right_container, 5)
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

    def clear_canvas_session(self):
        self.current_project_items.clear()
        self.input_prog_hrs.setText("0")
        self.input_detail_hrs.setText("0")
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
            base_material_cost = billable_wgt * rate_per_lb

        active_nsc_angle = 0.0
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
                            line_cost = 25.00 * a_qty
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
                        line_cost = 25.00 * a_qty
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
                line_cost = (p2 * 1.00) * a_qty
                stud_mass = BidFormMathEngine.calculate_hd_stud_weight(p1, p2, alloy) * a_qty * qty
                actual_wgt += stud_mass
                billable_wgt += stud_mass
                base_material_cost += (stud_mass * rate_per_lb)
                weld_inches = (math.pi * p1) * a_qty

            elif mode == "WH-Welded Hanger":
                line_cost = 75.00 * a_qty
                weld_inches = 12.0 * a_qty

            elif mode == "Saddle Cut":
                line_cost = 0.50 * base_labor_rate * a_qty

            elif mode == "Torch cut":
                c_map = {"Level 1": 10.0, "Level 2": 20.0, "Level 3": 35.0, "Level 4": 50.0}
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
            else:
                op_label = f"{mode}(x{a_qty}) {weld_tag}".strip()
            addon_summary_tokens.append(op_label)

        pc_fee, hdg_fee = BidFormMathEngine.calculate_finishing_treatments(actual_wgt, pc, hdg)
        raw_labor_and_finish = addon_labor_surcharges + pc_fee + hdg_fee
        raw_item_cost = base_material_cost + raw_labor_and_finish

        tags = []
        if alloy == "304 Stainless": tags.append("304 SS")
        elif alloy == "316 Stainless": tags.append("316 SS")
        if pc: tags.append("PC")
        if hdg: tags.append("HDG")
        tag_summary = f" [{'+'.join(tags)}]" if tags else ""

        if override_logs:
            addon_summary_tokens.append(f"⚠️ OVERRIDES: {', '.join(override_logs)}")

        self.current_project_items.append({
            "model": f"{label_desc} (x{qty}){tag_summary}",
            "weight": actual_wgt,
            "billable_weight": billable_wgt,
            "mat_cost": base_material_cost,
            "labor_cost": raw_labor_and_finish,
            "cost": raw_item_cost,
            "addons": ", ".join(addon_summary_tokens) if addon_summary_tokens else "None"
        })
        self.sync_local_workbench_view()
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

    def sync_local_workbench_view(self):
        self.ledger_textbox.clear()
        c_name = self.input_cust_name.text().strip() if self.input_cust_name.text().strip() else "Retail Customer"
        p_name = self.input_proj_name.text().strip() if self.input_proj_name.text().strip() else "Standard Build"
        markup_mult = float(self.safeguards.get("labor_markup", 1.40))
        markup_pct = round((markup_mult - 1.0) * 100)

        self.ledger_textbox.insertPlainText(f"==========================================================================\n ACTIVE WORKBENCH: {c_name.upper()} | {p_name.upper()}\n==========================================================================\n")
        self.ledger_textbox.insertPlainText(f"{'PART DESCRIPTION MODEL':<40} | {'WEIGHT':<14} | {'RAW COST':<14}\n")
        divider = "-" * 74 + "\n"
        self.ledger_textbox.insertPlainText(divider)

        t_wgt = 0.0
        for item in self.current_project_items:
            m_str = f"{item['model'][:38]:<40}"
            w_str = f"{item['weight']:>10.1f} lbs "
            c_str = f"${item['cost']:>12.2f}"
            self.ledger_textbox.insertPlainText(f"{m_str} | {w_str} | {c_str}\n")
            mat_c = item.get('mat_cost', item['cost'])
            lab_c = item.get('labor_cost', 0.0)
            self.ledger_textbox.insertPlainText(f"   • Breakdown: Raw Steel = ${mat_c:,.2f}  |  Shop Labor & Finish = ${lab_c:,.2f}\n")
            if item['addons'] != "None":
                addon_lines = textwrap.wrap(
                    f"   ↳ Addons: {item['addons']}",
                    width=74,
                    subsequent_indent="             "
                )
                self.ledger_textbox.insertPlainText("\n".join(addon_lines) + "\n")
            t_wgt += item['weight']

        p_hrs, d_hrs, eng_rate, eng_cost = self.get_engineering_hours_and_cost()
        if eng_cost > 0:
            eng_label = f"Prog ({p_hrs:g}h) + Detail ({d_hrs:g}h) @ ${eng_rate:.0f}/hr"
            self.ledger_textbox.insertPlainText(f"{eng_label:<40} | {'--':>14} | {f'${eng_cost:.2f}':>14}\n")

        raw_mat_total = sum(i.get('mat_cost', i['cost']) for i in self.current_project_items)
        raw_labor_total = sum(i.get('labor_cost', 0.0) for i in self.current_project_items) + eng_cost
        raw_subtotal = round(raw_mat_total + raw_labor_total, 2)

        markup_dollars = round(raw_subtotal * (markup_mult - 1.0), 2)
        grand_total = round(raw_subtotal + markup_dollars, 2)

        self.ledger_textbox.insertPlainText("\n" + divider)
        self.ledger_textbox.insertPlainText(f"{'SESSION ACTUAL SHIP WEIGHT:':<40} | {t_wgt:>10.1f} lbs | \n")
        self.ledger_textbox.insertPlainText(f"{'RAW STEEL MATERIALS TOTAL:':<40} | {'':<14} | {f'${raw_mat_total:,.2f}':>14}\n")
        self.ledger_textbox.insertPlainText(f"{'RAW SHOP & ENG. LABOR TOTAL:':<40} | {'':<14} | {f'${raw_labor_total:,.2f}':>14}\n")
        self.ledger_textbox.insertPlainText(f"{'COMBINED RAW SHOP SUBTOTAL:':<40} | {'':<14} | {f'${raw_subtotal:,.2f}':>14}\n")
        self.ledger_textbox.insertPlainText(f"{f'BID MARKUP ({markup_pct}%):':<40} | {'':<14} | {f'+${markup_dollars:,.2f}':>14}\n")
        self.ledger_textbox.insertPlainText(f"{'TOTAL CUSTOMER QUOTE VALUE:':<40} | {'':<14} | {f'${grand_total:,.2f}':>14}\n")
        self.ledger_textbox.insertPlainText(divider)

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
            manifest_entries.append(
                f" Item #{idx+1}: {item['model']} (Ship Wgt: {item['weight']:.1f} lbs | Mill Wgt: {item.get('billable_weight', item['weight']):.1f} lbs | Mat: ${mat_c:,.2f} | Labor: ${lab_c:,.2f} | Raw: ${item['cost']:,.2f}) [Addons: {item['addons']}]"
            )
            clean_addons = ", ".join([t.strip() for t in item['addons'].split(",") if "OVERRIDES:" not in t]) if item['addons'] != "None" else "Standard Stock"
            customer_lines.append({
                "desc": item['model'],
                "specs": clean_addons if clean_addons else "Standard Stock",
                "weight": item['weight'],
                "price": item['cost'] * markup_mult
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
        self.input_prog_hrs.setText("0")
        self.input_detail_hrs.setText("0")
        self.sync_local_workbench_view()
        QMessageBox.information(self, "Bid Finalized", "Grouped Project Quote saved to Running Project Ledger.")
class HistoricalArchiveLedgerPage(QWidget):
    def __init__(self, rfq_ledger_items_reference, admin_safeguards_reference, save_ledger_callback, parent=None):
        super().__init__(parent)
        self.rfq_ledger_items = rfq_ledger_items_reference
        self.safeguards = admin_safeguards_reference
        self.save_ledger_callback = save_ledger_callback
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        splitter = QSplitter(Qt.Vertical)

        search_widget = QWidget()
        search_layout = QHBoxLayout(search_widget)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.addWidget(QLabel("🔍 Search Archived Projects:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by customer, project name, or quote #...")
        self.search_input.textChanged.connect(self.apply_live_filter_matching)
        search_layout.addWidget(self.search_input)

        self.btn_export_pdf = QPushButton("📄 Export Customer PDF Quote")
        self.btn_export_pdf.setObjectName("PrimaryAction")
        self.btn_export_pdf.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; border-radius: 4px; padding: 6px 12px;")
        self.btn_export_pdf.clicked.connect(self.export_selected_quote_pdf)
        search_layout.addWidget(self.btn_export_pdf)

        self.btn_delete_quote = QPushButton("🗑️ Delete Selected Quote")
        self.btn_delete_quote.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; border-radius: 4px; padding: 6px 12px;")
        self.btn_delete_quote.clicked.connect(self.delete_selected_quote)
        search_layout.addWidget(self.btn_delete_quote)

        layout.addWidget(search_widget)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setHorizontalHeaderLabels(["QUOTE #", "TIMESTAMP", "CUSTOMER", "PROJECT JOB NAME", "TOTAL WEIGHT", "AGGREGATE VALUE"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemClicked.connect(self.display_detailed_project_manifest_popup)
        splitter.addWidget(self.table)

        self.manifest_viewer = QTextEdit()
        self.manifest_viewer.setReadOnly(True)
        self.manifest_viewer.setLineWrapMode(QTextEdit.WidgetWidth)
        self.manifest_viewer.setStyleSheet("background-color: #0f172a; border: 2px solid #334155; font-family: 'Consolas'; color: #38bdf8; border-radius: 8px; padding: 10px;")
        self.manifest_viewer.setPlaceholderText("Click any archived project row above to view the full itemized manifest.")
        splitter.addWidget(self.manifest_viewer)

        layout.addWidget(splitter)

    def populate_ledger_grid(self):
        self.table.setRowCount(0)
        for row_idx, item in enumerate(self.rfq_ledger_items):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(item.get("quote_num", "")))
            self.table.setItem(row_idx, 1, QTableWidgetItem(item.get("timestamp", "")))
            self.table.setItem(row_idx, 2, QTableWidgetItem(item.get("customer", "")))
            self.table.setItem(row_idx, 3, QTableWidgetItem(item.get("project", "")))
            self.table.setItem(row_idx, 4, QTableWidgetItem(f"{item.get('weight', 0.0):.1f} lbs"))
            self.table.setItem(row_idx, 5, QTableWidgetItem(f"${item.get('cost', 0.0):,.2f}"))

    def delete_selected_quote(self):
        row = self.table.currentRow()
        if row < 0 or not self.table.item(row, 0):
            QMessageBox.warning(self, "No Quote Selected", "Click a quote row in the table first before deleting.")
            return

        quote_num = self.table.item(row, 0).text()
        pwd, ok = QInputDialog.getText(self, "Admin Authorization Required", f"Enter Administrative Passcode to delete {quote_num}:", QLineEdit.Password)
        if not ok:
            return
        if pwd != self.safeguards.get("admin_passcode", "Barron"):
            QMessageBox.warning(self, "Access Denied", "Incorrect administrative passcode. Quote was not deleted.")
            return

        confirm = QMessageBox.question(
            self, "Confirm Permanent Deletion",
            f"Permanently delete {quote_num} from the Running Project Ledger?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.rfq_ledger_items[:] = [r for r in self.rfq_ledger_items if r.get("quote_num") != quote_num]
            self.save_ledger_callback()
            self.populate_ledger_grid()
            self.manifest_viewer.clear()
            QMessageBox.information(self, "Deleted", f"{quote_num} has been permanently removed.")

    def display_detailed_project_manifest_popup(self, item):
        row = item.row()
        quote_num = self.table.item(row, 0).text()
        for record in self.rfq_ledger_items:
            if record.get("quote_num") == quote_num:
                wrapped_lines = []
                for raw_line in record.get("summary", "").splitlines():
                    if len(raw_line) <= 72:
                        wrapped_lines.append(raw_line)
                    else:
                        wrapped_lines.extend(
                            textwrap.wrap(
                                raw_line,
                                width=72,
                                subsequent_indent="          "
                            )
                        )
                clean_summary = "\n".join(wrapped_lines)

                breakdown = (
                    f"========================================================================\n"
                    f" ITEMIZED MANIFEST BREAKDOWN FOR BID ID: {quote_num}\n"
                    f"========================================================================\n"
                    f" • Customer: {record.get('customer')}\n"
                    f" • Project:  {record.get('project')}\n"
                    f" • Date:     {record.get('timestamp')}\n"
                    f" ──────────────────────────────────────────────────────────────────────\n"
                    f"{clean_summary}\n"
                    f" ──────────────────────────────────────────────────────────────────────\n"
                    f" TOTAL PROJECT WEIGHT: {record.get('weight'):.1f} lbs\n"
                    f" GRAND PROJECT VALUE:  ${record.get('cost'):,.2f}\n"
                    f"========================================================================\n"
                )
                self.manifest_viewer.setPlainText(breakdown)
                break

    def apply_live_filter_matching(self, query_text):
        query = query_text.strip().lower()
        for row in range(self.table.rowCount()):
            match = any(
                self.table.item(row, col) and query in self.table.item(row, col).text().lower()
                for col in range(self.table.columnCount())
            )
            self.table.setRowHidden(row, not match)
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
                    f"<tr><td valign='top' style='padding:8pt; border-bottom:1pt solid #cbd5e1; font-size:10pt;'>{idx}</td>"
                    f"<td valign='top' style='padding:8pt; border-bottom:1pt solid #cbd5e1; font-size:10pt;'><b>{line['desc']}</b></td>"
                    f"<td valign='top' style='padding:8pt; border-bottom:1pt solid #cbd5e1; font-size:10pt;'>{specs_html}</td>"
                    f"<td valign='top' style='padding:8pt; border-bottom:1pt solid #cbd5e1; font-size:10pt; text-align:right;'>{wgt_str}</td>"
                    f"<td valign='top' style='padding:8pt; border-bottom:1pt solid #cbd5e1; font-size:10pt; text-align:right;'>${line['price']:,.2f}</td></tr>"
                )
        else:
            rows_html = (
                f"<tr><td valign='top' style='padding:8pt; border-bottom:1pt solid #cbd5e1; font-size:10pt;'>1</td>"
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
            f"<html><body style='font-family:Arial, Helvetica, sans-serif; color:#334155; font-size:9pt;'>"
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

        painter = QPainter(printer)
        body_doc.drawContents(painter, QRectF(0, 0, page_rect.width(), page_rect.height() - footer_h - 10))
        painter.save()
        painter.translate(0, page_rect.height() - footer_h)
        footer_doc.drawContents(painter)
        painter.restore()
        painter.end()

        QMessageBox.information(self, "PDF Exported", f"Customer quote saved cleanly to:\n{file_path}")


class AdminControlDashboardPage(QWidget):
    def __init__(self, admin_safeguards_reference, save_callback, parent=None):
        super().__init__(parent)
        self.safeguards = admin_safeguards_reference
        self.save_callback = save_callback
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(15, 15, 15, 15)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack)

        lock_page = QWidget()
        lock_layout = QVBoxLayout(lock_page)
        lock_layout.setAlignment(Qt.AlignCenter)
        lock_layout.setSpacing(12)

        lock_lbl = QLabel("🔒 RESTRICTED ADMIN AREA — ENTER PASSCODE TO UNLOCK SHOP RATES & SAFEGUARDS")
        lock_lbl.setStyleSheet("color: #38bdf8; font-size: 14px; font-weight: bold;")
        lock_layout.addWidget(lock_lbl, alignment=Qt.AlignCenter)

        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.setPlaceholderText("Enter Admin Passcode...")
        self.pass_input.setFixedWidth(260)
        self.pass_input.returnPressed.connect(self.unlock_admin_panel)
        lock_layout.addWidget(self.pass_input, alignment=Qt.AlignCenter)

        btn_unlock = QPushButton("🔓 UNLOCK ADMIN SETTINGS")
        btn_unlock.setObjectName("PrimaryAction")
        btn_unlock.setFixedWidth(260)
        btn_unlock.clicked.connect(self.unlock_admin_panel)
        lock_layout.addWidget(btn_unlock, alignment=Qt.AlignCenter)

        self.stack.addWidget(lock_page)

        admin_page = QWidget()
        layout = QVBoxLayout(admin_page)
        layout.setSpacing(8)

        top_bar = QHBoxLayout()
        header = QLabel("🛡️ BOWMAN-MORTON SHOP RATES, ARC-ON SPEEDS & SAFEGUARDS ADMIN DESK")
        header.setStyleSheet("color: #38bdf8; font-size: 14px; font-weight: bold;")
        top_bar.addWidget(header)
        top_bar.addStretch()

        btn_lock = QPushButton("🔒 Lock Admin Panel")
        btn_lock.setStyleSheet("background-color: #475569; color: white; padding: 6px 12px; border-radius: 4px;")
        btn_lock.clicked.connect(self.lock_admin_panel)
        top_bar.addWidget(btn_lock)
        layout.addLayout(top_bar)

        grid = QGridLayout()
        grid.setSpacing(6)

        grid.addWidget(QLabel("Rates: Shop, Prog/Det, Stud ($), & Markup:"), 0, 0)
        rate_row = QHBoxLayout()
        self.edit_labor = QLineEdit(str(self.safeguards.get("base_labor_rate", 86.0)))
        self.edit_eng_labor = QLineEdit(str(self.safeguards.get("eng_labor_rate", 175.0)))
        self.edit_stud_rate = QLineEdit(str(self.safeguards.get("std_stud_rate", 5.00)))
        self.edit_markup = QLineEdit(str(self.safeguards.get("labor_markup", 1.40)))
        rate_row.addWidget(QLabel("Shop:"))
        rate_row.addWidget(self.edit_labor)
        rate_row.addWidget(QLabel("Prog/Det:"))
        rate_row.addWidget(self.edit_eng_labor)
        rate_row.addWidget(QLabel("Stud:"))
        rate_row.addWidget(self.edit_stud_rate)
        rate_row.addWidget(QLabel("Markup:"))
        rate_row.addWidget(self.edit_markup)
        grid.addLayout(rate_row, 0, 1)

        grid.addWidget(QLabel("Max Saw Beam Size & Max Drill Dia (in):"), 1, 0)
        saw_drill_row = QHBoxLayout()
        self.edit_saw_beam = QLineEdit(str(self.safeguards.get("max_saw_beam_size", "W16")))
        self.edit_drill = QLineEdit(str(self.safeguards.get("max_drill_diameter", 1.125)))
        saw_drill_row.addWidget(QLabel("Saw Max:"))
        saw_drill_row.addWidget(self.edit_saw_beam)
        saw_drill_row.addWidget(QLabel("Drill Max:"))
        saw_drill_row.addWidget(self.edit_drill)
        grid.addLayout(saw_drill_row, 1, 1)

        grid.addWidget(QLabel("Manual Punch Max Wgt (lbs) & Turret Bed (in):"), 2, 0)
        punch_row = QHBoxLayout()
        self.edit_punch_wgt = QLineEdit(str(self.safeguards.get("max_manual_punch_weight", 45.0)))
        self.edit_turret_l = QLineEdit(str(self.safeguards.get("turret_max_length", 48.0)))
        self.edit_turret_w = QLineEdit(str(self.safeguards.get("turret_max_width", 48.0)))
        punch_row.addWidget(QLabel("Max Wgt:"))
        punch_row.addWidget(self.edit_punch_wgt)
        punch_row.addWidget(QLabel("Bed L:"))
        punch_row.addWidget(self.edit_turret_l)
        punch_row.addWidget(QLabel("Bed W:"))
        punch_row.addWidget(self.edit_turret_w)
        grid.addLayout(punch_row, 2, 1)

        grid.addWidget(QLabel("Shear Max Thk (Carbon / SS in) & Bed Len (in):"), 3, 0)
        shear_row = QHBoxLayout()
        self.edit_carb_shear = QLineEdit(str(self.safeguards.get("carbon_shear_max_thickness", 0.50)))
        self.edit_ss_shear = QLineEdit(str(self.safeguards.get("ss_shear_max_thickness", 0.375)))
        self.edit_brake_len = QLineEdit(str(self.safeguards.get("max_press_brake_length", 120.0)))
        shear_row.addWidget(QLabel("Carbon:"))
        shear_row.addWidget(self.edit_carb_shear)
        shear_row.addWidget(QLabel("SS:"))
        shear_row.addWidget(self.edit_ss_shear)
        shear_row.addWidget(QLabel("Max Len:"))
        shear_row.addWidget(self.edit_brake_len)
        grid.addLayout(shear_row, 3, 1)

        grid.addWidget(QLabel("Arc-On Weld Speeds (Fillet / PJP / CJP IPM):"), 4, 0)
        arc_row = QHBoxLayout()
        self.edit_fillet_ipm = QLineEdit(str(self.safeguards.get("fillet_ipm", 6.0)))
        self.edit_pjp_ipm = QLineEdit(str(self.safeguards.get("pjp_ipm", 2.0)))
        self.edit_cjp_ipm = QLineEdit(str(self.safeguards.get("cjp_ipm", 0.1)))
        arc_row.addWidget(QLabel("Fillet:"))
        arc_row.addWidget(self.edit_fillet_ipm)
        arc_row.addWidget(QLabel("PJP:"))
        arc_row.addWidget(self.edit_pjp_ipm)
        arc_row.addWidget(QLabel("CJP:"))
        arc_row.addWidget(self.edit_cjp_ipm)
        grid.addLayout(arc_row, 4, 1)

        grid.addWidget(QLabel("Weld Pass Counts by Size (3/16 to 1/2):"), 5, 0)
        pass_row = QHBoxLayout()
        self.edit_p_3_16 = QLineEdit(str(self.safeguards.get("passes_3_16", 1)))
        self.edit_p_1_4 = QLineEdit(str(self.safeguards.get("passes_1_4", 1)))
        self.edit_p_5_16 = QLineEdit(str(self.safeguards.get("passes_5_16", 2)))
        self.edit_p_3_8 = QLineEdit(str(self.safeguards.get("passes_3_8", 2)))
        self.edit_p_1_2 = QLineEdit(str(self.safeguards.get("passes_1_2", 3)))
        for lbl_txt, box in [("3/16:", self.edit_p_3_16), ("1/4:", self.edit_p_1_4), ("5/16:", self.edit_p_5_16), ("3/8:", self.edit_p_3_8), ("1/2:", self.edit_p_1_2)]:
            pass_row.addWidget(QLabel(lbl_txt))
            pass_row.addWidget(box)
        grid.addLayout(pass_row, 5, 1)

        grid.addWidget(QLabel("Machine Speeds & Heavy Handling Cutoff:"), 6, 0)
        mach_row = QHBoxLayout()
        self.edit_saw_ipm = QLineEdit(str(self.safeguards.get("saw_ipm", 0.8)))
        self.edit_drill_spm = QLineEdit(str(self.safeguards.get("drill_spm", 2.0)))
        self.edit_light_ppm = QLineEdit(str(self.safeguards.get("light_ppm", 4.0)))
        self.edit_heavy_ppm = QLineEdit(str(self.safeguards.get("heavy_ppm", 0.5)))
        self.edit_heavy_wgt = QLineEdit(str(self.safeguards.get("heavy_weight_cutoff", 40.0)))
        for lbl_txt, box in [("Saw IPM:", self.edit_saw_ipm), ("Drill SPM:", self.edit_drill_spm), ("Light PPM:", self.edit_light_ppm), ("Heavy PPM:", self.edit_heavy_ppm), ("Heavy lbs:", self.edit_heavy_wgt)]:
            mach_row.addWidget(QLabel(lbl_txt))
            mach_row.addWidget(box)
        grid.addLayout(mach_row, 6, 1)

        layout.addLayout(grid)

        btn_save = QPushButton("💾 SAVE & APPLY ALL RATES, ARC SPEEDS & SAFEGUARDS")
        btn_save.setObjectName("PrimaryAction")
        btn_save.setMinimumHeight(36)
        btn_save.clicked.connect(self.submit_safeguards_changes)
        layout.addWidget(btn_save)

        self.summary_box = QTextEdit()
        self.summary_box.setReadOnly(True)
        self.summary_box.setStyleSheet("background-color: #0f172a; border: 2px solid #334155; font-family: 'Consolas', 'Segoe UI'; font-size: 11px; color: #cbd5e1; border-radius: 8px; padding: 8px;")
        layout.addWidget(self.summary_box)
        self.refresh_summary_text()

        self.stack.addWidget(admin_page)
    def refresh_summary_text(self):
        s = self.safeguards
        l_rate = s.get('base_labor_rate', 86.0)
        e_rate = s.get('eng_labor_rate', 175.0)
        st_rate = s.get('std_stud_rate', 5.00)
        l_mark = s.get('labor_markup', 1.40)
        saw_max = s.get('max_saw_beam_size', 'W16')
        drill_max = s.get('max_drill_diameter', 1.125)
        punch_wgt = s.get('max_manual_punch_weight', 45.0)
        tur_l = s.get('turret_max_length', 48.0)
        tur_w = s.get('turret_max_width', 48.0)
        carb_s = s.get('carbon_shear_max_thickness', 0.50)
        ss_s = s.get('ss_shear_max_thickness', 0.375)
        max_len = s.get('max_press_brake_length', 120.0)

        f_ipm = s.get('fillet_ipm', 6.0)
        p_ipm = s.get('pjp_ipm', 2.0)
        c_ipm = s.get('cjp_ipm', 0.1)

        p316 = s.get('passes_3_16', 1)
        p14 = s.get('passes_1_4', 1)
        p516 = s.get('passes_5_16', 2)
        p38 = s.get('passes_3_8', 2)
        p12 = s.get('passes_1_2', 3)

        saw_ipm = s.get('saw_ipm', 0.8)
        drill_spm = s.get('drill_spm', 2.0)
        light_ppm = s.get('light_ppm', 4.0)
        heavy_ppm = s.get('heavy_ppm', 0.5)
        heavy_wgt = s.get('heavy_weight_cutoff', 40.0)

        lines = [
            "LIVE SHOP SAFEGUARDS, RATES & ARC-ON TIME ENGINE REFERENCE:",
            "===============================================================================",
            f"ACTIVE RATES: Shop = ${l_rate:.2f}/hr | Prog/Detail = ${e_rate:.2f}/hr | Std Stud = ${st_rate:.2f}/ea | End Markup = {l_mark}x",
            f"GATES: Saw Max = {saw_max} | Drill Max = {drill_max} in | Punch Max = {punch_wgt} lbs | Turret = {tur_l}x{tur_w} in | Shear = {carb_s} C / {ss_s} SS x {max_len} in",
            f"ARC SPEEDS: Fillet = {f_ipm} IPM | PJP = {p_ipm} IPM | CJP = {c_ipm} IPM",
            f"WELD PASSES: 3/16 = {p316} | 1/4 = {p14} | 5/16 = {p516} | 3/8 = {p38} | 1/2 = {p12}",
            f"MACHINE SPEEDS: Saw = {saw_ipm} IPM | Drill = {drill_spm} SPM | Light = {light_ppm} PPM | Heavy (>={heavy_wgt} lbs) = {heavy_ppm} PPM",
            "-------------------------------------------------------------------------------",
            "WHAT EACH SAFEGUARD GATE & RATE CONTROLS:",
            f"- Base Shop Labor Rate (${l_rate:.2f}/hr): Applied to all welding, sawing, drilling, coping, and bending.",
            f"- Prog & Detailing Rate (${e_rate:.2f}/hr): Applied to project-level Programming & Detailing hours before final markup.",
            f"- Standard Studs (${st_rate:.2f}/ea): Flat per-stud charge for drawn-arc stud gun installation (no fillet weld added).",
            f"- Max Beam Saw Cut Size ({saw_max}): Largest W-beam depth your band saw cuts before prompting for override or routing to Torch.",
            f"- Max Mechanical Drill Dia ({drill_max} in): Largest hole your drill runs before prompting for override or auto-routing to Torch.",
            f"- Max Manual Punch Press Weight ({punch_wgt} lbs): Heaviest part an operator hand-feeds before auto-routing to Drilling ({drill_spm} SPM).",
            f"- CNC Turret Table Max Bed ({tur_l} x {tur_w} in): Maximum sheet footprint for turret table punching.",
            f"- Shear & Brake Limits ({carb_s} in C / {ss_s} in SS x {max_len} in): Max thickness and bed length (plus tonnage curve limits).",
            "",
            "ARC-ON WELDING & BID MARKUP FORMULAS:",
            "- Coverage Multiplier: Single Side = 1x contact | Full Wrap / Both Sides = 2x contact | Field Weld = $0.00 shop weld",
            f"- Arc-On Formula: ((Linear Inches x Coverage) / IPM / 60 mins) x Passes x ${l_rate:.2f}/hr",
            f"- Cold-Fab Formula: Saw = (Inches / {saw_ipm} IPM) / 60 | Drill = (Holes / {drill_spm} SPM) / 60 | Punch/Brake = (Parts / PPM) / 60",
            f"- Finishing & Bid Markup: Raw Subtotal = Steel Mat + Shop Labor + Prog/Detail + PC ($1.80/lb) + HDG ($0.62 or $1.88/lb) | Final Bid = Raw Subtotal x {l_mark}x"
        ]
        self.summary_box.setPlainText("\n".join(lines))

    def unlock_admin_panel(self):
        if self.pass_input.text() == self.safeguards.get("admin_passcode", "Barron"):
            self.pass_input.clear()
            self.stack.setCurrentIndex(1)
        else:
            QMessageBox.warning(self, "Access Denied", "Incorrect administrative passcode.")
            self.pass_input.clear()

    def lock_admin_panel(self):
        self.stack.setCurrentIndex(0)

    def submit_safeguards_changes(self):
        try:
            f_ipm = float(self.edit_fillet_ipm.text().strip())
            p_ipm = float(self.edit_pjp_ipm.text().strip())
            c_ipm = float(self.edit_cjp_ipm.text().strip())
            if f_ipm <= 0 or p_ipm <= 0 or c_ipm <= 0:
                QMessageBox.warning(self, "Invalid Speed", "Arc-On IPM speeds must be greater than zero.")
                return

            self.safeguards["base_labor_rate"] = float(self.edit_labor.text().strip())
            self.safeguards["eng_labor_rate"] = float(self.edit_eng_labor.text().strip())
            self.safeguards["std_stud_rate"] = float(self.edit_stud_rate.text().strip())
            self.safeguards["labor_markup"] = float(self.edit_markup.text().strip())
            self.safeguards["max_saw_beam_size"] = self.edit_saw_beam.text().strip().upper()
            self.safeguards["max_drill_diameter"] = float(self.edit_drill.text().strip())
            self.safeguards["max_manual_punch_weight"] = float(self.edit_punch_wgt.text().strip())
            self.safeguards["turret_max_length"] = float(self.edit_turret_l.text().strip())
            self.safeguards["turret_max_width"] = float(self.edit_turret_w.text().strip())
            self.safeguards["carbon_shear_max_thickness"] = float(self.edit_carb_shear.text().strip())
            self.safeguards["ss_shear_max_thickness"] = float(self.edit_ss_shear.text().strip())
            self.safeguards["max_press_brake_length"] = float(self.edit_brake_len.text().strip())
            self.safeguards["max_shear_length"] = float(self.edit_brake_len.text().strip())

            self.safeguards["fillet_ipm"] = f_ipm
            self.safeguards["pjp_ipm"] = p_ipm
            self.safeguards["cjp_ipm"] = c_ipm

            self.safeguards["passes_3_16"] = float(self.edit_p_3_16.text().strip())
            self.safeguards["passes_1_4"] = float(self.edit_p_1_4.text().strip())
            self.safeguards["passes_5_16"] = float(self.edit_p_5_16.text().strip())
            self.safeguards["passes_3_8"] = float(self.edit_p_3_8.text().strip())
            self.safeguards["passes_1_2"] = float(self.edit_p_1_2.text().strip())

            self.safeguards["saw_ipm"] = float(self.edit_saw_ipm.text().strip())
            self.safeguards["drill_spm"] = float(self.edit_drill_spm.text().strip())
            self.safeguards["light_ppm"] = float(self.edit_light_ppm.text().strip())
            self.safeguards["heavy_ppm"] = float(self.edit_heavy_ppm.text().strip())
            self.safeguards["heavy_weight_cutoff"] = float(self.edit_heavy_wgt.text().strip())

            self.save_callback()
            self.refresh_summary_text()
            QMessageBox.information(self, "Saved", "All shop rates, stud rates, pass counts, machine speeds, and safeguards saved.")
        except ValueError:
            QMessageBox.warning(self, "Error", "Ensure all numeric rate, pass count, speed, and limit fields are valid numbers.")
class CombinedSandboxAppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bowman-Morton Structural Estimates & Archive Suite")
        self.setMinimumSize(1380, 860)

        self.safeguards_file = get_workspace_path("shop_safeguards.json")
        self.ledger_file = get_workspace_path("project_ledger.json")

        self.global_safeguards_config = self.load_safeguards_from_disk()
        self.master_historical_rfq_pool, self.quote_sequence_counter = self.load_ledger_from_disk()

        self.tabs = QTabWidget()
        self.setStyleSheet(SANDBOX_MEMBER_STYLESHEET)

        self.quoting_canvas_tab = StructuralQuotingSandbox(self.commit_project_to_permanent_ledger, self.global_safeguards_config, self)
        self.historical_ledger_tab = HistoricalArchiveLedgerPage(
            self.master_historical_rfq_pool, self.global_safeguards_config, self.save_ledger_to_disk, self
        )
        self.admin_control_tab = AdminControlDashboardPage(self.global_safeguards_config, self.on_admin_safeguards_saved, self)

        self.tabs.addTab(self.quoting_canvas_tab, "🎯 Custom Quoting Canvas")
        self.tabs.addTab(self.historical_ledger_tab, "🗄️ Running Project Ledger")
        self.tabs.addTab(self.admin_control_tab, "🛡️ Shop Safeguards & Rates")
        self.setCentralWidget(self.tabs)

        self.historical_ledger_tab.populate_ledger_grid()

    def load_safeguards_from_disk(self):
        defaults = {
            "admin_passcode": "Barron",
            "base_labor_rate": 86.0,
            "eng_labor_rate": 175.0,
            "std_stud_rate": 5.00,
            "labor_markup": 1.40,
            "max_saw_beam_size": "W16",
            "max_drill_diameter": 1.125,
            "max_manual_punch_weight": 45.0,
            "turret_max_length": 48.0,
            "turret_max_width": 48.0,
            "carbon_shear_max_thickness": 0.50,
            "ss_shear_max_thickness": 0.375,
            "max_shear_length": 120.0,
            "max_press_brake_length": 120.0,
            "fillet_ipm": 6.0,
            "pjp_ipm": 2.0,
            "cjp_ipm": 0.1,
            "passes_3_16": 1,
            "passes_1_4": 1,
            "passes_5_16": 2,
            "passes_3_8": 2,
            "passes_1_2": 3,
            "saw_ipm": 0.8,
            "drill_spm": 2.0,
            "light_ppm": 4.0,
            "heavy_ppm": 0.5,
            "heavy_weight_cutoff": 40.0
        }
        if os.path.exists(self.safeguards_file):
            try:
                with open(self.safeguards_file, "r", encoding="utf-8") as f:
                    defaults.update(json.load(f))
            except Exception as e:
                print(f"Safeguards load warning: {e}")
        return defaults

    def save_safeguards_to_disk(self):
        try:
            with open(self.safeguards_file, "w", encoding="utf-8") as f:
                json.dump(self.global_safeguards_config, f, indent=4)
        except Exception as e:
            print(f"Safeguards save warning: {e}")

    def load_ledger_from_disk(self):
        if os.path.exists(self.ledger_file):
            try:
                with open(self.ledger_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("quotes", []), data.get("next_seq", 1001)
            except Exception as e:
                print(f"Ledger load warning: {e}")
        return [], 1001

    def save_ledger_to_disk(self):
        try:
            payload = {
                "next_seq": self.quote_sequence_counter,
                "quotes": self.master_historical_rfq_pool
            }
            with open(self.ledger_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4)
        except Exception as e:
            print(f"Ledger save warning: {e}")

    def commit_project_to_permanent_ledger(self, customer, project, total_weight, total_cost, summary_desc, customer_lines=None):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        quote_str = f"BM-2026-{self.quote_sequence_counter}"
        self.quote_sequence_counter += 1

        self.master_historical_rfq_pool.append({
            "quote_num": quote_str, "timestamp": timestamp, "customer": customer,
            "project": project, "weight": total_weight, "cost": total_cost,
            "summary": summary_desc, "customer_lines": customer_lines or []
        })
        self.save_ledger_to_disk()
        self.historical_ledger_tab.populate_ledger_grid()

    def on_admin_safeguards_saved(self):
        self.quoting_canvas_tab.safeguards = self.global_safeguards_config
        self.quoting_canvas_tab.sync_local_workbench_view()
        self.save_safeguards_to_disk()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    import qdarktheme
    qdarktheme.setup_theme(theme="dark", corner_shape="rounded", custom_colors={"primary": "#0284c7"})
    window = CombinedSandboxAppWindow()
    window.show()
    sys.exit(app.exec())
