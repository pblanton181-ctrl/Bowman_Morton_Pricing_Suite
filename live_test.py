import time
from ui.excel_components import FormulaHudBar, apply_excel_table_style
# ==========================================
# SECTION 1: SYSTEM SYSTEM WORKSPACE ARCHITECTURE
# ==========================================
import os
import sys
import json
import time
import shutil
import datetime
import webbrowser
import urllib.parse
import custom_quoting_module as cqm

from PySide6.QtCore import Qt, QTimer, QSize, QPoint, QRect, QTimer, QFileSystemWatcher
from PySide6.QtGui import QFont, QColor, QAction
from PySide6.QtWidgets import (
    QHeaderView,
    QTreeWidget, QTreeWidgetItem, QAbstractItemView,
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
    QGridLayout, QLabel, QComboBox, QLineEdit, QCheckBox, QPushButton, 
    QTextEdit, QFrame, QScrollArea, QInputDialog, QMessageBox, QFileDialog, 
    QDialog, QTabWidget
)
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def get_workspace_path(filename=""):
    """Forces the app to read and write database assets directly inside the folder 
    it is launched from, ensuring instant network synchronization for everyone."""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    if filename:
        return os.path.join(base_dir, filename)
    return base_dir

class PasscodeInputDialog(QInputDialog):
    def __init__(self, parent, title, label):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setLabelText(label)
        self.setTextEchoMode(QLineEdit.Password)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
    def get_inputcode(self):
        return self.textValue()
# ==========================================
# SECTION 2: STORAGE LOOKUP SCHEMAS BLOCK A
# ==========================================
CARDS_SCHEMA_MATRIX = {
    "CARD_1": {
        "dropdown_sheet": "Column Caps & Bases", "mode": "standard", "min_ht_col": 2,
        "model_col": 0, "extra_col": 1, "lbs_col": 4, "cost_col": 5, "start_row": 1, "end_row": 500,
        "surcharges_labels": ["Rush (B8)", "Flush To Top (C8)", "RT STRP OTHR THN 90 (D8)", "W3>W1 (B10)", "Rough BM Sz (C10)", "BCCOBQ (D10)", "SKD CCQ Cap (B12)", "Greater Height (C12)", "HDG (D12)"],
        "default_title": "COLUMN CAP'S & BASE'S-BGLB-BHGLB-BGLS"
    },
    "CARD_2": {
        "dropdown_sheet": "BLGU, BMGU, BHGU, BHGUM, BHGUS", "mode": "height_input", "min_ht_col": 2,
        "model_col": 0, "extra_col": 2, "lbs_col": 3, "cost_col": 4, "start_row": 1, "end_row": 500, "manual_label": "Actual Height (F6):",
        "surcharges_labels": ["Rush (F8)", "SKW (G8)", "SLP (H8)", "HDG (H12)"],
        "default_title": "BLGU, BMGU, BHGU, BHGUM, BHGUS"
    },
    "CARD_3": {
        "dropdown_sheet": "BWP-BWMU-BWD-BHW-BHWD-BHWP-BHWP", "mode": "height_input", "min_ht_col": 2,
        "model_col": 0, "extra_col": 2, "lbs_col": 3, "cost_col": 4, "start_row": 0, "end_row": 500, "manual_label": "Actual Height (J6):",
        "surcharges_labels": ["Rush (J8)", "SKW (K8)", "SLP (L8)", "TFOR/TFOL (J10)", "Ridge Hanger (K10)", "SLOPE TF (L10)", "HDG (L12)"],
        "default_title": "BWP-BWMU-BWD-BHW-BHWD-BHWP-BHWPH"
    },
    "CARD_4": {
        "dropdown_sheet": "BA-BHB-BMIU-BHU(C)(Q)-BHSUL(R)-", "mode": "height_input", "min_ht_col": 2,
        "model_col": 0, "extra_col": 2, "lbs_col": 3, "cost_col": 4, "start_row": 1, "end_row": 800, "manual_label": "Actual Height (N6):",
        "surcharges_labels": ["Rush (N8)", "SKW (O8)", "SLP (P8)", "RGH LMB (N10)", "RGH LMB W&H (O10)", "HDG (P12)"],
        "default_title": "BA-BHB-BMIU-BHU(C)(Q)-BHSUL(R)-BHUS-BHHUS"
    },
    "CARD_5": {
        "dropdown_sheet": "BHGLT, BHGLTV, BEG, BEGQ", "mode": "height_input", "min_ht_col": 2,
        "model_col": 0, "extra_col": 2, "lbs_col": 3, "cost_col": 4, "start_row": 0, "end_row": 500, "manual_label": "Actual Height (B20):",
        "surcharges_labels": ["Rush (B22)", "SKW (C22)", "SLP (D22)", "OFFSET (B24)", "SKW&SLP (C24)", "HDG (D26)"],
        "default_title": "BHGLT, BHGLTV, BFG, BEGO-BHGLS"
    },
# ==========================================
# SECTION 3: SCHEMAS BLOCK B & INTERFACE CSS
# ==========================================
    "CARD_6": {
        "dropdown_sheet": "Hinge Connectors-Truss Girder H", "mode": "standard", "min_ht_col": -1,
        "model_col": 0, "extra_col": 1, "lbs_col": 2, "cost_col": 3, "start_row": 1, "end_row": 500, "manual_label": "Actual Height (F20):",
        "surcharges_labels": ["Rush (F22)", "G22", "SLP (H22)", "OFFSET (F24)", "SKW&SLP (G24)", "HDG (H26)"],
        "default_title": "HINGE CONNECTORS-TRUSS IRRIGATION HANGER-ANGL-MASONRY HANGERS-BABU"
    },
    "CARD_7": {
        "dropdown_sheet": "Misc Fixed Prices", "mode": "qty_input", "min_ht_col": -1,
        "model_col": 0, "extra_col": 0, "lbs_col": 5, "cost_col": 6, 
        "start_row": 5, 
        "end_row": 103, 
        "manual_label": "Order QTY (J20):",
        "surcharges_labels": ["Rush (J22)", "Mod CHRG $15 (K22)", "BOCCOB Price Increase (J26)", "OCC Rough Cut (K26)"],
        "default_title": "MISC FIXED PRICE UNITS - PLATE WASHERS"
    },
    "CARD_8": {
        "dropdown_sheet": "Misc Fixed Prices", "mode": "fixed_standard_cost", "min_ht_col": -1,
        "model_col": 0, "extra_col": 0, "lbs_col": 2, "cost_col": 5, 
        "start_row": 104, 
        "end_row": 650, # Expanded limits layout matrix mapping bounds safely
        "manual_label": "Order QTY:",
        "surcharges_labels": ["Rush (J22)", "Mod CHRG $15 (K22)"],
        "default_title": "MISC FIXED PRICE UNITS - STANDARD ITEMS"
    },
    "CARD_9": {
        "dropdown_sheet": "BMSC", "mode": "double_height", "min_ht_col": 2,
        "model_col": 0, "extra_col": 1, "lbs_col": 3, "cost_col": 6, "start_row": 1, "end_row": 5,
        "surcharges_labels": ["Rush (N25)", "No SLP (O25)", "HDG (P25)"],
        "default_title": "BMSC"
    }
}

MODERN_STYLESHEET = """
QMainWindow, QDialog, QWidget#CentralWorkspace {
    background-color: #f3f2f1;
    color: #201f1e;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #d2d0ce;
    background-color: #ffffff;
    border-radius: 6px;
}
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #d2d0ce;
    border-top: 3px solid #0078d4;
    border-radius: 6px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: 700;
    color: #201f1e;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: #0078d4;
    background-color: #ffffff;
    font-size: 13px;
    font-weight: 800;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    color: #201f1e;
    border: 1px solid #8a8886;
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {
    border: 1.5px solid #0078d4;
}
QTableWidget, QTreeWidget, QListWidget {
    background-color: #ffffff;
    alternate-background-color: #faf9f8;
    color: #201f1e;
    gridline-color: #edebe9;
    border: 1px solid #d2d0ce;
    border-radius: 4px;
    selection-background-color: #eff6fc;
    selection-color: #0078d4;
}
QHeaderView::section {
    background-color: #f3f2f1;
    color: #323130;
    font-weight: 700;
    font-size: 12px;
    border: none;
    border-right: 1px solid #d2d0ce;
    border-bottom: 1.5px solid #0078d4;
    padding: 6px 8px;
}
QPushButton {
    background-color: #ffffff;
    color: #201f1e;
    border: 1px solid #8a8886;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #edebe9;
    border-color: #323130;
}
QPushButton:pressed {
    background-color: #e1dfdd;
}
QScrollBar:vertical {
    background: #f3f2f1;
    width: 11px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #c8c6c4;
    min-height: 28px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #8a8886;
}
"""
# ==========================================
# SECTION 4: DATA PROCESSOR AND MATRICES
# ==========================================
class DataProcessingCore:
    def __init__(self):
        self.database_file = get_workspace_path("matrix.json")
        self.clean_database = {}
        self.raw_full_json_blob = {}
        self.rfq_ledger_items = []
        self.runtime_visual_titles = {}
        
    def load_and_sanitize_matrix(self):
        if not os.path.exists(self.database_file): return False
        
        for _ in range(5):
            try:
                with open(self.database_file, "r", encoding="utf-8") as f:
                    self.raw_full_json_blob = json.load(f)
                break 
            except IOError:
                time.sleep(0.1) 
            except Exception as e:
                print(f"Sanitization error: {e}")
                return False
                
        try:
            config_block = self.raw_full_json_blob.get("ADMIN_METADATA_CONFIG_BLOCK", {})
            self.clean_database = {}
            for c_id, config in CARDS_SCHEMA_MATRIX.items():
                active_title = config_block.get(c_id, config["default_title"])
                self.runtime_visual_titles[c_id] = active_title
                self.clean_database[active_title] = {}
                
                tab_rows = self.raw_full_json_blob.get(config["dropdown_sheet"], [])
                start, end = config["start_row"], config["end_row"]
                m_col = config["model_col"]
                
                for row_idx, row in enumerate(tab_rows[start:end], start=start):
                    if row and len(row) > max(config["lbs_col"], config["cost_col"]):
                        model_name = " ".join(str(row[m_col]).split()).strip()
                        
                        filter_keywords = ["STEEL", "MATERIAL", "MODEL", "PRICE", "QTY", "CATEGORY", "ADD 15%", "MISC FIXED", "PLATE WASHERS", "ITEM", "EST.", "LBS"]
                        if len(model_name) > 1 and not any(k in model_name.upper() for k in filter_keywords):
                            
                            row_min_ht = 0.0
                            if config["min_ht_col"] != -1 and len(row) > config["min_ht_col"]:
                                try: row_min_ht = float(str(row[config["min_ht_col"]]).replace("$","").strip())
                                except ValueError: row_min_ht = 0.0

                            if config["mode"] == "qty_input":
                                all_costs = []
                                for c_idx in range(6, 15):
                                    if c_idx < len(row): all_costs.append(str(row[c_idx]).strip())
                                cost_str = "|".join(all_costs)
                            else:
                                cost_str = str(row[config["cost_col"]]).strip()

                            self.clean_database[active_title][model_name] = {
                                "lbs": str(row[config["lbs_col"]]).strip(),
                                "cost": cost_str,
                                "extra": str(row[config["extra_col"]]).strip(),
                                "min_ht": row_min_ht,
                                "raw_row_index": row_idx,
                                "schema_id": c_id
                            }
            return True
        except Exception as e:
            print(f"Sanitization error: {e}")
            return False
    def import_bulk_excel_sheet(self, file_path, target_category_title, schema_id, mode_type, operation_mode):
        """
        Parses an external Excel workbook row-by-row and translates the cell matrix
        directly into the schema matrix format of the active inventory target block,
        applying natural sorting rules to preserve clean structural groupings.
        """
        import openpyxl
        import re
        
        def natural_sort_key(row_item):
            """Splits text and strings into integer structures so 1/4x3x3 sorts cleanly after 3/16x2x2."""
            text = str(row_item[0]) # Target the part name field
            return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb.active 
            
            sheet_target_key = CARDS_SCHEMA_MATRIX[schema_id]["dropdown_sheet"]
            if sheet_target_key not in self.raw_full_json_blob:
                self.raw_full_json_blob[sheet_target_key] = []
            
            # Keep historical static headers intact
            start_boundary = CARDS_SCHEMA_MATRIX[schema_id]["start_row"]
            header_rows = self.raw_full_json_blob[sheet_target_key][:start_boundary]
            
            # Separate active items for sorting calculations
            existing_items = []
            if operation_mode == "APPEND":
                existing_items = self.raw_full_json_blob[sheet_target_key][start_boundary:]
            
            new_incoming_items = []
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or row[0] is None: 
                    continue
                
                model_lbl = str(row[0]).strip()
                weight_val = str(row[1]).strip() if len(row) > 1 and row[1] is not None else "0"
                cost_val = str(row[2]).strip() if len(row) > 2 and row[2] is not None else "0"
                h_val = str(row[3]).strip() if len(row) > 3 and row[3] is not None else "0.0"
                
                if schema_id == "CARD_1":
                    new_row = [model_lbl, "0", h_val, "0", weight_val, cost_val]
                elif schema_id in ["CARD_2", "CARD_3", "CARD_4", "CARD_5"]:
                    new_row = [model_lbl, "0", h_val, weight_val, cost_val]
                elif schema_id == "CARD_6":
                    new_row = [model_lbl, "0", weight_val, cost_val]
                elif mode_type == "qty_input":
                    new_row = [model_lbl, "0", "0", "0", "0", weight_val] + cost_val.split("|")
                elif mode_type == "fixed_standard_cost":
                    new_row = [model_lbl, "0", weight_val, "0", "0", cost_val]
                else:
                    new_row = [model_lbl, "0", "0", weight_val, h_val, h_val, cost_val]
                
                new_incoming_items.append(new_row)
            
            # Combine historical cache items and new elements, then apply sort logic
            combined_inventory = existing_items + new_incoming_items
            combined_inventory.sort(key=natural_sort_key)
            
            # Save the reconstructed table format
            self.raw_full_json_blob[sheet_target_key] = header_rows + combined_inventory
            
            with open(self.database_file, "w", encoding="utf-8") as f:
                json.dump(self.raw_full_json_blob, f, indent=4)
                
            self.load_and_sanitize_matrix()
            return True, len(new_incoming_items)
        except Exception as e:
            return False, str(e)

# ==========================================
# SECTION 5: ESTIMATION PRICING FORMULAS
# ==========================================
class PricingCalculatorCore:
    @staticmethod
    def get_profile_multiplier(raw_profile_str, cfg=None):
        cfg = cfg or {}
        text_check = str(raw_profile_str).upper()
        if "CONSTRUCTION SUPPLY" in text_check: return float(cfg.get("mult_const_supply", 0.50))
        if "LUMBER YARD" in text_check: return float(cfg.get("mult_lumber_yard", 0.60))
        return 1.00

    @staticmethod
    def calc_card1(base_cost, lbs_weight, profile_mult, checks, cfg=None):
        cfg = cfg or {}
        subtotal = base_cost * profile_mult
        if checks.get("Flush To Top (C8)"): subtotal += (float(cfg.get("c1_flush_top_fee", 30.00)) * profile_mult)
        if checks.get("RT STRP OTHR THN 90 (D8)"): subtotal += (float(cfg.get("c1_rt_strp_fee", 25.00)) * profile_mult)
        if checks.get("BCCOBQ (D10)"): subtotal += (float(cfg.get("c1_bccobq_fee", 11.00)) * profile_mult)
        if checks.get("SKD CCQ Cap (B12)"):
            skd_h = float(cfg.get("card1_skd_heavy_rate", 0.80))
            hdg_l = float(cfg.get("hdg_light_rate_per_lb", 1.88))
            subtotal += ((lbs_weight * skd_h) if lbs_weight >= 20.00 else (lbs_weight * hdg_l)) * profile_mult
        if checks.get("Greater Height (C12)"): subtotal *= float(cfg.get("c1_greater_ht_mult", 1.05))
        if checks.get("W3>W1 (B10)"): subtotal *= float(cfg.get("c1_w3_w1_mult", 1.10))
        if checks.get("Rough BM Sz (C10)"): subtotal *= float(cfg.get("c1_rough_bm_mult", 1.25))
        if checks.get("HDG (D12)"): subtotal *= float(cfg.get("card1_hdg_mult", 1.15))
        if checks.get("Rush (B8)"): subtotal *= float(cfg.get("rush_multiplier", 1.25))
        return subtotal

    @staticmethod
    def calc_standard_height(base_cost, lbs_weight, profile_mult, checks, actual_ht, dynamic_row_min_ht, labels_list, extra_height_rate=0.50, cfg=None):
        cfg = cfg or {}
        ext_rate = float(cfg.get("std_extra_ht_rate", extra_height_rate))
        subtotal = base_cost * profile_mult
        calculated_wgt = lbs_weight
        if actual_ht > dynamic_row_min_ht:
            height_delta = actual_ht - dynamic_row_min_ht
            subtotal += (height_delta * 2.0 * ext_rate * profile_mult)
            calculated_wgt += (height_delta * 1.0)
        for label in labels_list:
            if checks.get(label):
                if "SKW" in label or "SLP" in label: subtotal += (float(cfg.get("std_skw_slp_fee", 25.00)) * profile_mult)
                if "RGH LMB" in label.upper(): subtotal += (float(cfg.get("std_rgh_lmb_fee", 11.00)) * profile_mult)
                if "HDG" in label:
                    hdg_rate = float(cfg.get("hdg_heavy_rate_per_lb", 0.62)) if calculated_wgt >= 20.00 else float(cfg.get("hdg_light_rate_per_lb", 1.88))
                    subtotal += (calculated_wgt * hdg_rate) * profile_mult
        if any(checks.get(l) and "RUSH" in l.upper() for l in labels_list): subtotal *= float(cfg.get("rush_multiplier", 1.25))
        return subtotal, calculated_wgt

    @staticmethod
    def calc_card5_6(base_cost, lbs_weight, profile_mult, checks, actual_ht, dynamic_row_min_ht, labels_list, cfg=None):
        cfg = cfg or {}
        subtotal = base_cost * profile_mult
        calculated_wgt = lbs_weight
        if actual_ht > dynamic_row_min_ht:
            height_delta = actual_ht - dynamic_row_min_ht
            subtotal += (height_delta * 2.0 * float(cfg.get("c56_extra_ht_rate", 1.40)) * profile_mult)
            calculated_wgt += (height_delta * 1.0)
        for label in labels_list:
            if checks.get(label):
                if "SKW" in label and "SLP" not in label: subtotal += (float(cfg.get("c56_skw_fee", 44.00)) * profile_mult)
                if "SLP" in label and "SKW" not in label: subtotal += (float(cfg.get("c56_slp_fee", 42.50)) * profile_mult)
                if "OFFSET" in label: subtotal += (float(cfg.get("c56_offset_fee", 15.00)) * profile_mult)
                if "SKW&SLP" in label: subtotal += (float(cfg.get("c56_skw_slp_fee", 50.00)) * profile_mult)
                if "HDG" in label:
                    hdg_rate = float(cfg.get("hdg_heavy_rate_per_lb", 0.62)) if calculated_wgt >= 20.00 else float(cfg.get("hdg_light_rate_per_lb", 1.88))
                    subtotal += (calculated_wgt * hdg_rate) * profile_mult
        if any(checks.get(l) and "RUSH" in l.upper() for l in labels_list): subtotal *= float(cfg.get("rush_multiplier", 1.25))
        return subtotal, calculated_wgt

    @staticmethod
    def calc_card7_tiered(base_row_dict, profile_mult, checks, order_qty):
        raw_cost_string = str(base_row_dict.get("cost", "0.0")).strip()
        tier_prices = []
        if "|" in raw_cost_string:
            for x in raw_cost_string.split("|"):
                try:
                    cl = "".join(c for c in x if c.isdigit() or c == ".")
                    tier_prices.append(float(cl) if cl else 0.0)
                except ValueError: tier_prices.append(0.0)
        else:
            cl = "".join(c for c in raw_cost_string if c.isdigit() or c == ".")
            tier_prices = [float(cl) if cl else 0.0] * 9

        if len(tier_prices) >= 9:
            if order_qty == 1: idx = 0
            elif order_qty == 2: idx = 1
            elif order_qty == 3: idx = 2
            elif order_qty == 4: idx = 3
            elif order_qty == 5: idx = 4
            elif 6 <= order_qty <= 10: idx = 5
            elif 11 <= order_qty <= 15: idx = 6
            elif 16 <= order_qty < 250: idx = 7
            else: idx = 8
            base_unit_rate = tier_prices[idx]
            if idx == 8 and base_unit_rate > 0: base_unit_rate = base_unit_rate / 250.0
        else: base_unit_rate = tier_prices if tier_prices else 0.0

        unit_subtotal = base_unit_rate + (15.00 if checks.get("Mod CHRG $15 (K22)") else 0.0)
        if checks.get("BOCCOB Price Increase (J26)"): unit_subtotal *= 1.10
        if checks.get("OCC Rough Cut (K26)"): unit_subtotal *= 1.15
        
        if checks.get("Rush (J22)"): unit_subtotal *= 1.25
        return unit_subtotal, unit_subtotal * order_qty

    @staticmethod
    def calc_card8(base_cost, lbs_weight, profile_mult, model_name, checks, valley_val, ridge_val, cfg=None):
        cfg = cfg or {}
        min_height_p18 = 9.5 if "MSC 5" in model_name else (7.5 if "MSC 4" in model_name else 5.5)
        def clean_ht(v, def_h):
            cl = "".join(c for c in str(v) if c in (".", "-") or c.isdigit())
            return float(cl) if cl else def_h
        v_ht = clean_ht(valley_val, min_height_p18)
        r_ht = clean_ht(ridge_val, min_height_p18)
        if "MSC 4" in model_name or "MSC 5" in model_name:
            v_mult, r_mult = float(cfg.get("c8_msc45_valley_rate", 6.00)), float(cfg.get("c8_msc45_ridge_rate", 3.00))
        else:
            v_mult, r_mult = float(cfg.get("c8_std_valley_rate", 3.20)), float(cfg.get("c8_std_ridge_rate", 1.60))
        v_delta = max(0.0, v_ht - min_height_p18)
        r_delta = max(0.0, r_ht - min_height_p18)
        subtotal = (base_cost + (v_delta * 2.0 * v_mult) + (r_delta * 2.0 * r_mult)) * profile_mult
        v_wgt_rate, r_wgt_rate = (1.20, 0.60) if ("MSC 4" in model_name or "MSC 5" in model_name) else (0.80, 0.40)
        calculated_wgt = lbs_weight + (v_delta * 2.0 * v_wgt_rate) + (r_delta * 2.0 * r_wgt_rate)
        if checks.get("No SLP (O25)"): subtotal -= (float(cfg.get("c8_no_slp_credit", 35.00)) * profile_mult)
        if checks.get("HDG (P25)"):
            hdg_rate = float(cfg.get("hdg_heavy_rate_per_lb", 0.62)) if calculated_wgt >= 20.00 else float(cfg.get("hdg_light_rate_per_lb", 1.88))
            subtotal += (calculated_wgt * hdg_rate) * profile_mult
        if checks.get("Rush (N25)"): subtotal *= float(cfg.get("rush_multiplier", 1.25))
        return subtotal, calculated_wgt

# ==========================================
# SECTION 6: ADMINISTRATIVE SCREEN INIT
# ==========================================
class AdminDashboardWindow(QDialog):
    def __init__(self, parent=None, data_core=None):
        super().__init__(parent)
        self.data_core = data_core
        self.setWindowTitle("Privileged Administrative Workspace Control Center")
        self.setMinimumSize(700, 500)
        
        self.master_layout = QVBoxLayout(self)
        self.master_layout.setContentsMargins(15, 15, 15, 15)
        self.master_layout.setSpacing(10)
        
        self.admin_tabs_deck = QTabWidget()
        self.create_tab_1_title_remapper()
        self.create_tab_2_variant_appender()
        self.create_tab_3_bulk_modifiers()
        self.create_tab_4_inline_grid()
        
        self.master_layout.addWidget(self.admin_tabs_deck)
        self.sync_admin_purgable_model_dropdown()

    def create_tab_1_title_remapper(self):
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        from PySide6.QtGui import QColor
        tab1_page = QWidget()
        tab1_page.setStyleSheet("background: transparent !important;")
        lay = QVBoxLayout(tab1_page)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        hdr_lbl = QLabel("Double-click any Display Screen Title cell below to rename how that card appears across the app:")
        hdr_lbl.setStyleSheet("color: #0369a1; font-weight: 700; font-size: 12px;")
        lay.addWidget(hdr_lbl)

        self.title_table = QTableWidget(len(CARDS_SCHEMA_MATRIX), 3)
        apply_excel_table_style(self.title_table)
        self.title_table.setAlternatingRowColors(True)
        self.title_table.setHorizontalHeaderLabels(["CARD ID", "SOURCE EXCEL SHEET", "ACTIVE SCREEN DISPLAY TITLE (DOUBLE-CLICK TO EDIT)"])
        thdr = self.title_table.horizontalHeader()
        thdr.setStretchLastSection(True)
        thdr.setVisible(True)
        thdr.setFixedHeight(32)
        thdr.setStyleSheet("QHeaderView::section { background-color: #dcebfa; color: #0369a1; font-weight: 600; font-size: 12px; padding: 6px; border-bottom: 2px solid #475569; }")
        hdr_qss = "QHeaderView::section { background-color: #dcebfa; color: #0369a1; font-family: 'Segoe UI', sans-serif; font-size: 12px; font-weight: 700; padding: 6px 8px; border: none; border-bottom: 2px solid #475569; }"
        thdr.setStyleSheet(hdr_qss)
        for c_i, w_i in [(0, 120), (1, 310), (2, 480)]:
            thdr.setSectionResizeMode(c_i, QHeaderView.Interactive)
            self.title_table.setColumnWidth(c_i, w_i)
        thdr.sectionDoubleClicked.connect(lambda c: self.title_table.resizeColumnToContents(c))
        self.title_table.verticalHeader().setVisible(False)
        self.title_table.setStyleSheet("""
            QTableWidget { background-color: rgba(207, 228, 250, 0.46) !important; alternate-background-color: rgba(239, 246, 255, 0.72) !important; color: #0f172a !important; border: 1px solid #cbd5e1; border-radius: 8px; gridline-color: rgba(96, 165, 250, 0.55); font-family: 'Segoe UI', sans-serif; font-size: 12px; font-weight: 600; }
            QTableWidget::viewport { background: transparent !important; }
            QTableWidget QLineEdit { background-color: #dcebfa !important; color: #0f172a !important; border: 1px solid #38bdf8 !important; padding: 2px 6px !important; }
            QTableWidget::item:selected, QTableWidget::item:selected:!active { background-color: #93c5fd; color: #0f172a; }
        """)

        self.title_inputs_map = {}
        for r_i, (c_id, config) in enumerate(CARDS_SCHEMA_MATRIX.items()):
            self.title_table.setRowHeight(r_i, 32)
            cur_title = self.data_core.runtime_visual_titles.get(c_id, config["default_title"])

            c0 = QTableWidgetItem(c_id)
            c0.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            c0.setTextAlignment(Qt.AlignCenter)
            c0.setForeground(QColor("#0369a1"))

            c1 = QTableWidgetItem(config["dropdown_sheet"])
            c1.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            c1.setForeground(QColor("#1e3a8a"))

            c2 = QTableWidgetItem(cur_title)
            c2.setForeground(QColor("#047857"))
            c2.setData(Qt.UserRole, cur_title)

            self.title_table.setItem(r_i, 0, c0)
            self.title_table.setItem(r_i, 1, c1)
            self.title_table.setItem(r_i, 2, c2)
            self.title_inputs_map[c_id] = c2

        def _on_title_cell_changed(item):
            if item.column() == 2:
                if item.text().strip() != item.data(Qt.UserRole):
                    item.setBackground(QColor(245, 158, 11, 75))
                    item.setForeground(QColor("#b45309"))
                else:
                    item.setBackground(QColor(0, 0, 0, 0))
                    item.setForeground(QColor("#047857"))

        self.title_table.itemChanged.connect(_on_title_cell_changed)
        self.title_table.horizontalHeader().setVisible(False)
        t1_hdr = QFrame()
        t1_hdr.setStyleSheet("background-color: rgba(207, 228, 250, 0.85); border: 1px solid #475569; border-radius: 6px;")
        t1_hl = QHBoxLayout(t1_hdr); t1_hl.setContentsMargins(10, 6, 10, 6)
        for txt, w in [("CARD ID", 115), ("SOURCE EXCEL SHEET", 305), ("ACTIVE SCREEN DISPLAY TITLE (DOUBLE-CLICK TO EDIT)", 0)]:
            lbl = QLabel(txt); lbl.setStyleSheet("color: #0369a1; font-weight: 700; font-size: 12px;")
            if w: lbl.setFixedWidth(w)
            t1_hl.addWidget(lbl, 0 if w else 1)
        lay.addWidget(t1_hdr)
        lay.addWidget(self.title_table, 1)

        self.btn_save_titles = QPushButton("COMMIT AND ENCRYPT NEW TITLES TO DATABASE")
        self.btn_save_titles.setObjectName("EmeraldAction")
        self.btn_save_titles.setStyleSheet("QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12.5px; font-weight: 700; border-radius: 6px; padding: 4px 12px; } QPushButton:hover { background-color: rgba(110, 231, 183, 0.82); color: #000000; }")
        self.btn_save_titles.setMinimumHeight(40)
        self.btn_save_titles.clicked.connect(self.admin_save_encrypted_titles)
        lay.addWidget(self.btn_save_titles)
        self.admin_tabs_deck.addTab(tab1_page, "Category Title Matrix")

    def create_tab_2_variant_appender(self):
        tab2_page = QWidget()
        tab2_page.setStyleSheet("background: transparent !important;")
        center_box = QVBoxLayout(tab2_page)
        center_box.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        center_box.setContentsMargins(24, 18, 24, 18)
        host_w = QWidget()
        host_w.setMaximumWidth(1140)
        wrap = QVBoxLayout(host_w)
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.setSpacing(14)
        banner = QLabel("CATALOG DATABASE EXPANSION - Add individual part variants or merge full Excel pricing sheets into the live matrix.")
        banner.setStyleSheet("background-color: #eff6ff; border: 1px solid #cbd5e1; border-left: 4px solid #0284c7; border-radius: 6px; padding: 10px 14px; color: #0f172a; font-size: 12px; font-weight: 600;")
        wrap.addWidget(banner)
        outer = QHBoxLayout()
        outer.setSpacing(18)
        wrap.addLayout(outer, 1)
        center_box.addWidget(host_w)

        # Left Card: Single Part Variant Quick-Add
        left_card = QFrame(); left_card.setObjectName("AppendCard")
        left_card.setStyleSheet("QFrame#AppendCard { background-color: rgba(207, 228, 250, 0.78) !important; border: 1px solid #cbd5e1 !important; border-radius: 8px; }")
        left_l = QVBoxLayout(left_card)
        left_l.setContentsMargins(16, 14, 16, 14)
        left_l.setSpacing(10)

        lbl_l_hdr = QLabel("APPEND SINGLE PART VARIANT TO DATABASE")
        lbl_l_hdr.setStyleSheet("color: #0369a1; font-size: 12px; font-weight: 700;")
        left_l.addWidget(lbl_l_hdr)

        form_grid = QGridLayout()
        form_grid.setHorizontalSpacing(12)
        form_grid.setVerticalSpacing(14)
        form_grid.setColumnStretch(0, 0)
        form_grid.setColumnStretch(1, 1)

        form_grid.addWidget(QLabel("Target Category:"), 0, 0)
        self.cat_select = QComboBox()
        self.cat_select.addItems(list(self.data_core.clean_database.keys()))
        form_grid.addWidget(self.cat_select, 0, 1)

        form_grid.addWidget(QLabel("Part Model Label:"), 1, 0)
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("e.g., BABU8-10 or BGLB-12")
        form_grid.addWidget(self.model_input, 1, 1)

        form_grid.addWidget(QLabel("Weight (lbs):"), 2, 0)
        self.weight_input = QLineEdit()
        self.weight_input.setPlaceholderText("e.g., 14.5")
        form_grid.addWidget(self.weight_input, 2, 1)

        form_grid.addWidget(QLabel("Base Cost ($):"), 3, 0)
        self.cost_input = QLineEdit()
        self.cost_input.setPlaceholderText("e.g., 168.00")
        form_grid.addWidget(self.cost_input, 3, 1)

        left_l.addLayout(form_grid)
        left_l.addStretch()

        self.btn_save_item = QPushButton("COMMIT SINGLE VARIANT TO DISK")
        self.btn_save_item.setStyleSheet("QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 4px 12px; } QPushButton:hover { background-color: rgba(167, 243, 208, 0.68); color: #0f172a; }")
        self.btn_save_item.setMinimumHeight(42)
        self.btn_save_item.clicked.connect(self.save_database_entry)
        left_l.addWidget(self.btn_save_item)
        outer.addWidget(left_card, 1)

        # Right Card: Bulk Import Excel Workbook Matrix
        right_card = QFrame(); right_card.setObjectName("AppendCard")
        right_card.setStyleSheet("QFrame#AppendCard { background-color: rgba(207, 228, 250, 0.78) !important; border: 1px solid #cbd5e1 !important; border-radius: 8px; }")
        right_l = QVBoxLayout(right_card)
        right_l.setContentsMargins(16, 14, 16, 14)
        right_l.setSpacing(10)

        lbl_r_hdr = QLabel("BULK IMPORT CATEGORY SHEET FROM EXCEL")
        lbl_r_hdr.setStyleSheet("color: #0369a1; font-size: 12px; font-weight: 700;")
        right_l.addWidget(lbl_r_hdr)

        class _ExcelDropPad(QFrame):
            def __init__(self, on_drop_cb, parent=None):
                super().__init__(parent)
                self._cb = on_drop_cb
                self.setAcceptDrops(True)
                self.setMinimumHeight(150)
                self._base_qss = (
                    "QFrame { background-color: rgba(239, 246, 255, 0.65); "
                    "border: 2.5px dashed #0284c7; border-radius: 10px; padding: 14px; }"
                )
                self._hover_qss = (
                    "QFrame { background-color: rgba(147, 197, 253, 0.72); "
                    "border: 2.5px solid #0369a1; border-radius: 10px; padding: 14px; }"
                )
                self.setStyleSheet(self._base_qss)
                dl = QVBoxLayout(self)
                dl.setAlignment(Qt.AlignCenter)
                dl.setSpacing(6)
                t1 = QLabel("DROP EXCEL PRICING SHEET HERE (.XLSX / .XLSM)")
                t1.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                t1.setAlignment(Qt.AlignCenter)
                t1.setWordWrap(True)
                t1.setStyleSheet("color: #0369a1; font-size: 12.5px; font-weight: 700; background: transparent; border: none;")
                t2 = QLabel("Drag & drop your filled Excel template onto this pad?or use the buttons below to download a template or browse for a file.")
                t2.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                t2.setAlignment(Qt.AlignCenter)
                t2.setWordWrap(True)
                t2.setStyleSheet("color: #0f172a; font-size: 12px; font-weight: 700; background: transparent; border: none;")
                dl.addWidget(t1)
                dl.addWidget(t2)
            def dragEnterEvent(self, ev):
                if ev.mimeData().hasUrls():
                    urls = [u.toLocalFile() for u in ev.mimeData().urls()]
                    if any(u.lower().endswith((".xlsx", ".xlsm")) for u in urls):
                        self.setStyleSheet(self._hover_qss)
                        ev.acceptProposedAction()
                        return
                ev.ignore()
            def dragMoveEvent(self, ev):
                if ev.mimeData().hasUrls():
                    ev.acceptProposedAction()
            def dragLeaveEvent(self, ev):
                self.setStyleSheet(self._base_qss)
            def mousePressEvent(self, ev):
                if ev.button() == Qt.LeftButton:
                    self._cb(None)
            def dropEvent(self, ev):
                ev.acceptProposedAction()
                self.setStyleSheet(self._base_qss)
                for u in ev.mimeData().urls():
                    fp = u.toLocalFile()
                    if fp.lower().endswith((".xlsx", ".xlsm")):
                        self._cb(fp)
                        break

        self.setAcceptDrops(True)
        tab2_page.setAcceptDrops(True)
        right_card.setAcceptDrops(True)
        self.excel_drop_pad = _ExcelDropPad(lambda fp: self.admin_bulk_import_excel_sheet(fp), self)
        right_l.addWidget(self.excel_drop_pad, 1)

        t_card_row = QHBoxLayout()
        t_card_row.addWidget(QLabel("Target Card:"))
        self.bulk_card_combo = QComboBox()
        for c_id, cfg in CARDS_SCHEMA_MATRIX.items():
            title_txt = self.data_core.runtime_visual_titles.get(c_id, cfg["default_title"])
            self.bulk_card_combo.addItem(f"{c_id} - {title_txt}", c_id)
        t_card_row.addWidget(self.bulk_card_combo, 1)
        right_l.addLayout(t_card_row)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Merge Mode:"))
        self.bulk_mode_combo = QComboBox()
        self.bulk_mode_combo.addItems(["Append & Sort into Existing Card", "Replace Entire Card Matrix"])
        mode_row.addWidget(self.bulk_mode_combo, 1)
        right_l.addLayout(mode_row)

        self.btn_dl_template = QPushButton("Download Selected Card Excel Template (.xlsx)")
        self.btn_dl_template.setToolTip("<b>Download Card-Specific Excel Template</b><br>Generates a ready-to-fill .xlsx template formatted with the exact<br>columns and example rows required for the selected card.")
        self.btn_dl_template.setStyleSheet("QPushButton { background-color: rgba(239, 246, 255, 0.72); border: 2px solid #0284c7; color: #000000; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 8px; } QPushButton:hover { background-color: rgba(2, 132, 199, 0.28); color: #0f172a; }")
        self.btn_dl_template.setMinimumHeight(38)
        self.btn_dl_template.clicked.connect(self.admin_download_card_excel_template)
        right_l.addWidget(self.btn_dl_template)

        self.btn_bulk_import = QPushButton("LOAD EXCEL SHEET (.XLSX)...")
        self.btn_bulk_import.setStyleSheet("QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 4px 12px; } QPushButton:hover { background-color: rgba(96, 165, 250, 0.82); color: #0f172a; }")
        self.btn_bulk_import.setMinimumHeight(42)
        self.btn_bulk_import.clicked.connect(lambda: self.admin_bulk_import_excel_sheet())
        right_l.addWidget(self.btn_bulk_import)
        outer.addWidget(right_card, 1)

        self.admin_tabs_deck.addTab(tab2_page, "Append Material Records")

    def create_tab_3_bulk_modifiers(self):
        from PySide6.QtWidgets import QListWidget, QAbstractItemView, QSplitter
        tab3_page = QWidget()
        tab3_page.setStyleSheet("background: transparent !important;")
        t3_outer = QHBoxLayout(tab3_page)
        t3_outer.setAlignment(Qt.AlignHCenter)
        t3_outer.setContentsMargins(24, 14, 24, 14)

        v_split = QSplitter(Qt.Vertical)
        v_split.setMaximumWidth(1140)
        v_split.setHandleWidth(7)
        v_split.setStyleSheet("QSplitter { background: transparent; } QSplitter::handle { background-color: rgba(2, 132, 199, 0.35); border-radius: 3px; margin: 2px 40px; } QSplitter::handle:hover { background-color: #0284c7; }")

        top_card = QFrame()
        top_card.setStyleSheet("QFrame { background-color: rgba(248, 250, 252, 0.78) !important; border: 1px solid #cbd5e1 !important; border-radius: 8px; }")
        lay = QVBoxLayout(top_card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(10)

        lay.addWidget(QLabel("Select Category & Highlight Models to Delete (Hold Shift or Ctrl for Multiple):"))
        top_sel = QHBoxLayout()
        self.bulk_cat_select = QComboBox()
        self.bulk_cat_select.addItems(list(self.data_core.clean_database.keys()))
        self.bulk_cat_select.currentIndexChanged.connect(self.sync_admin_purgable_model_dropdown)
        top_sel.addWidget(self.bulk_cat_select, 1)

        self.bulk_model_filter = QLineEdit()
        self.bulk_model_filter.setPlaceholderText("Filter models (e.g., BABU, BGLB)...")
        self.bulk_model_filter.textChanged.connect(self.sync_admin_purgable_model_dropdown)
        top_sel.addWidget(self.bulk_model_filter, 1)
        lay.addLayout(top_sel)

        from PySide6.QtWidgets import QTableWidget, QHeaderView
        t3_hdr = QFrame()
        t3_hdr.setStyleSheet("background-color: rgba(207, 228, 250, 0.85); border: 1px solid #60a5fa; border-radius: 6px;")
        t3_hl = QHBoxLayout(t3_hdr); t3_hl.setContentsMargins(10, 6, 10, 6)
        for txt, w in [("MODEL / PART NUMBER", 460), ("WEIGHT (LBS)", 180), ("BASE LIST COST ($)", 0)]:
            lbl = QLabel(txt); lbl.setStyleSheet("color: #0369a1; font-weight: 700; font-size: 13px;")
            if w: lbl.setFixedWidth(w); lbl.setAlignment(Qt.AlignCenter if "WEIGHT" in txt else Qt.AlignLeft)
            else: lbl.setAlignment(Qt.AlignCenter)
            t3_hl.addWidget(lbl, 0 if w else 1)
        lay.addWidget(t3_hdr)

        self.delete_model_list = QTableWidget(0, 3)
        apply_excel_table_style(self.delete_model_list)
        self.delete_model_list.setAlternatingRowColors(True)
        self.delete_model_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.delete_model_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.delete_model_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.delete_model_list.verticalHeader().setVisible(False)
        self.delete_model_list.horizontalHeader().setVisible(False)
        self.delete_model_list.horizontalHeader().setStretchLastSection(True)
        for c_i, w_i in [(0, 465), (1, 185), (2, 220)]:
            self.delete_model_list.setColumnWidth(c_i, w_i)
        self.delete_model_list.setMinimumHeight(185)
        self.delete_model_list.setStyleSheet(self.title_table.styleSheet() + " QTableWidget::item:selected, QTableWidget::item:selected:!active { background-color: #fecaca; color: #7f1d1d; }")
        lay.addWidget(self.delete_model_list)

        del_btns = QHBoxLayout()
        btn_sel_all = QPushButton("Select All Filtered")
        btn_sel_all.setStyleSheet("QPushButton { background-color: rgba(239, 246, 255, 0.72); border: 2px solid #0284c7; color: #000000; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 8px; } QPushButton:hover { background-color: rgba(2, 132, 199, 0.28); color: #0f172a; }")
        btn_sel_all.clicked.connect(self.delete_model_list.selectAll)
        del_btns.addWidget(btn_sel_all, 1)

        self.btn_delete_item = QPushButton("ERASE SELECTED MODELS FROM DATABASE")
        self.btn_delete_item.setStyleSheet("QPushButton { background-color: #ffffff; border: 1px solid #fca5a5; color: #b91c1c; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 4px 12px; } QPushButton:hover { background-color: rgba(252, 165, 165, 0.84); color: #7f1d1d; }")
        self.btn_delete_item.setObjectName("DangerAction")
        self.btn_delete_item.setMinimumHeight(38)
        self.btn_delete_item.clicked.connect(self.admin_purge_single_item_record)
        del_btns.addWidget(self.btn_delete_item, 2)
        lay.addLayout(del_btns)

        v_split.addWidget(top_card)

        bot_card = QFrame()
        bot_card.setStyleSheet("QFrame { background-color: rgba(248, 250, 252, 0.78) !important; border: 1px solid #cbd5e1 !important; border-radius: 8px; }")
        bot_l = QVBoxLayout(bot_card)
        bot_l.setContentsMargins(18, 14, 18, 14)
        bot_l.setSpacing(10)
        bot_l.addWidget(QLabel("Enter Global Spreadsheet Price Adjustment Shift Percentage Factor (%):"))
        self.pct_input = QLineEdit()
        self.pct_input.setPlaceholderText("e.g., 5.0 for +5% increase or -3.5 for 3.5% decrease")
        bot_l.addWidget(self.pct_input)

        self.btn_bulk_scale = QPushButton("MULTIPLY ENTIRE CARD PRICING MATRIX BY SCALE FACTOR %")
        self.btn_bulk_scale.setStyleSheet("QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 4px 12px; } QPushButton:hover { background-color: rgba(96, 165, 250, 0.82); color: #0f172a; }")
        self.btn_bulk_scale.setObjectName("PrimaryAction")
        self.btn_bulk_scale.setMinimumHeight(42)
        self.btn_bulk_scale.clicked.connect(self.admin_execute_bulk_percentage_scale)
        bot_l.addWidget(self.btn_bulk_scale)
        bot_l.addStretch()
        v_split.addWidget(bot_card)
        v_split.setSizes([420, 180])
        t3_outer.addWidget(v_split, 1)
        self.admin_tabs_deck.addTab(tab3_page, "Bulk Pricing Modifiers")

    def admin_purge_single_item_record(self):
        cat = self.bulk_cat_select.currentText()
        selected_models = {self.delete_model_list.item(idx.row(), 0).text() for idx in self.delete_model_list.selectionModel().selectedRows()}
        if not selected_models or not cat:
            QMessageBox.warning(self, "No Models Selected", "Highlight one or more models first (hold Shift or Ctrl to select multiple).")
            return
        reply = QMessageBox.question(self, "Confirm Batch Delete", f"Permanently delete {len(selected_models)} selected model(s) from {cat}?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            if hasattr(self, 'push_catalog_snapshot'): self.push_catalog_snapshot(f'Before Deleting {len(selected_models)} in {cat}')
            models_list = list(self.data_core.clean_database[cat].keys())
            first_model = models_list[0] if models_list else None
            schema_id = self.data_core.clean_database[cat][first_model]["schema_id"] if first_model else "CARD_1"
            sheet_target = CARDS_SCHEMA_MATRIX[schema_id]["dropdown_sheet"]
            m_col = CARDS_SCHEMA_MATRIX[schema_id]["model_col"]

            rows = self.data_core.raw_full_json_blob.get(sheet_target, [])
            new_rows = [r for r in rows if not (len(r) > m_col and str(r[m_col]).strip() in selected_models)]
            self.data_core.raw_full_json_blob[sheet_target] = new_rows

            with open(self.data_core.database_file, "w", encoding="utf-8") as f:
                json.dump(self.data_core.raw_full_json_blob, f, indent=4)

            self.data_core.load_and_sanitize_matrix()
            if self.parent() and hasattr(self.parent(), 'handle_card_switch'):
                self.parent().handle_card_switch()

            QMessageBox.information(self, "Batch Purge Complete", f"Successfully deleted {len(selected_models)} model(s) from {cat}.")
            self.sync_admin_purgable_model_dropdown()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Purge Failure: {e}")

    def admin_execute_bulk_percentage_scale(self):
        cat = self.bulk_cat_select.currentText()
        pct_text = self.pct_input.text().strip()
        if not pct_text or not cat: return
        try:
            if hasattr(self, 'push_catalog_snapshot'): self.push_catalog_snapshot(f'Before {pct_text}% Scale on {cat}')
            factor = 1.0 + (float(pct_text) / 100.0)
            models_list = list(self.data_core.clean_database[cat].keys())
            first_model = models_list[0] if models_list else None
            schema_id = self.data_core.clean_database[cat][first_model]["schema_id"] if first_model else "CARD_1"
            sheet_target = CARDS_SCHEMA_MATRIX[schema_id]["dropdown_sheet"]
            start = CARDS_SCHEMA_MATRIX[schema_id]["start_row"]
            end = CARDS_SCHEMA_MATRIX[schema_id]["end_row"]
            cost_col = CARDS_SCHEMA_MATRIX[schema_id]["cost_col"]
            rows = self.data_core.raw_full_json_blob.get(sheet_target, [])
            
            for i in range(start, min(end, len(rows))):
                row = rows[i]
                if CARDS_SCHEMA_MATRIX[schema_id]["mode"] == "qty_input":
                    for c_idx in range(6, 15):
                        if c_idx < len(row):
                            try:
                                cleaned = "".join(c for c in str(row[c_idx]) if c.isdigit() or c == ".")
                                if cleaned: rows[i][c_idx] = f"{float(cleaned) * factor:.2f}"
                            except ValueError: continue
                else:
                    if row and len(row) > cost_col:
                        try:
                            cleaned = "".join(c for c in str(row[cost_col]) if c.isdigit() or c == ".")
                            if cleaned: rows[i][cost_col] = f"{float(cleaned) * factor:.2f}"
                        except ValueError: continue
            
            with open(self.data_core.database_file, "w", encoding="utf-8") as f:
                json.dump(self.data_core.raw_full_json_blob, f, indent=4)
                
            self.data_core.load_and_sanitize_matrix()
            if self.parent() and hasattr(self.parent(), 'handle_card_switch'):
                self.parent().handle_card_switch()
            QMessageBox.information(self, "Success", "Matrices updated completely.")
        except Exception as e: 
            QMessageBox.critical(self, "Error", f"Bulk Error: {e}")
    def admin_save_encrypted_titles(self):
        try:
            for c_id, cell_item in self.title_inputs_map.items():
                new_t = cell_item.text().strip()
                if new_t:
                    self.data_core.runtime_visual_titles[c_id] = new_t
                    cell_item.setData(Qt.UserRole, new_t)
                    cell_item.setBackground(QColor(0, 0, 0, 0))
                    cell_item.setForeground(QColor("#047857"))
            if hasattr(self.data_core, "save_visual_titles"):
                self.data_core.save_visual_titles()
            if self.parent() and hasattr(self.parent(), "handle_card_switch"):
                self.parent().handle_card_switch()
            if hasattr(self.parent(), "custom_admin_tab"):
                self.parent().custom_admin_tab.log_admin_activity("Updated Category Screen Titles")
            QMessageBox.information(self, "Titles Saved", "All category display titles updated across the suite.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save titles: {e}")

    def admin_download_card_excel_template(self):
        from PySide6.QtWidgets import QFileDialog
        c_id = self.bulk_card_combo.currentData() or "CARD_1"
        cfg = CARDS_SCHEMA_MATRIX[c_id]
        mode = cfg["mode"]
        title_clean = self.data_core.runtime_visual_titles.get(c_id, cfg["default_title"])
        safe_slug = "".join(ch if ch.isalnum() else "_" for ch in f"{c_id}_{title_clean[:24]}").strip("_")
        default_path = get_workspace_path(f"{safe_slug}_Import_Template.xlsx")
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Card Excel Import Template", default_path, "Excel Workbook (*.xlsx)")
        if not save_path:
            return
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = c_id
            if mode == "qty_input":
                headers = ["MODEL / PART NUMBER", "WEIGHT (LBS)", "QTY 1 ($)", "QTY 2 ($)", "QTY 3 ($)", "QTY 4 ($)", "QTY 5 ($)", "QTY 6-10 ($)", "QTY 11-15 ($)", "QTY 16-249 ($)", "QTY 250+ ($)"]
                samples = [
                    ["PW-1/2X4X4-EXAMPLE", 2.25, 8.50, 8.00, 7.50, 7.00, 6.75, 6.25, 5.80, 5.25, 1150.00],
                    ["PW-3/4X6X6-EXAMPLE", 7.65, 14.00, 13.25, 12.50, 11.75, 11.25, 10.50, 9.75, 8.90, 1950.00],
                ]
            elif mode in ("height_input", "double_height") or c_id == "CARD_1":
                headers = ["MODEL / PART NUMBER", "WEIGHT (LBS)", "BASE LIST COST ($)", "MIN HEIGHT (IN)"]
                samples = [
                    ["EXAMPLE-MODEL-A", 14.5, 165.00, 8.0],
                    ["EXAMPLE-MODEL-B", 22.0, 215.00, 10.0],
                ]
            else:
                headers = ["MODEL / PART NUMBER", "WEIGHT (LBS)", "BASE LIST COST ($)"]
                samples = [
                    ["EXAMPLE-ITEM-1", 12.0, 145.00],
                    ["EXAMPLE-ITEM-2", 18.5, 195.00],
                ]
            ws.append(headers)
            hdr_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
            hdr_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            for col_i in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col_i)
                cell.fill = hdr_fill
                cell.font = hdr_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions.height = 24
            ws.freeze_panes = "A2"
            for s_row in samples:
                ws.append(s_row)
            ws.append([])
            ws.append([f"INSTRUCTIONS: Replace the 2 example rows above with your {c_id} ({title_clean}) items, delete this instruction row, save, and click LOAD EXCEL SHEET (.XLSX)."])
            ws.cell(row=5, column=1).font = Font(italic=True, color="0369A1")
            for col in ws.columns:
                max_len = max(len(str(c.value or "")) for c in col[:4])
                ws.column_dimensions[col[0].column_letter].width = max(18, min(38, max_len + 5))
            wb.save(save_path)
            if os.name == "nt":
                os.startfile(save_path)
            QMessageBox.information(self, "Template Created", f"Excel import template for {c_id} saved and opened:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Template Error", f"Could not generate Excel template: {e}")

    def admin_bulk_import_excel_sheet(self, dropped_path=None):
        from PySide6.QtWidgets import QFileDialog
        import openpyxl
        c_id = self.bulk_card_combo.currentData() or "CARD_1"
        cfg = CARDS_SCHEMA_MATRIX[c_id]
        mode = cfg["mode"]
        title_clean = self.data_core.runtime_visual_titles.get(c_id, cfg["default_title"])
        op_mode = "REPLACE" if "Replace" in self.bulk_mode_combo.currentText() else "APPEND"
        xlsx_path = dropped_path if isinstance(dropped_path, str) and dropped_path else QFileDialog.getOpenFileName(self, f"Select Excel Sheet for {c_id}", "", "Excel Files (*.xlsx *.xlsm)")
        if not xlsx_path:
            return
        try:
            if hasattr(self, "push_catalog_snapshot"):
                self.push_catalog_snapshot(f"Before {c_id} Excel Import")
            wb = openpyxl.load_workbook(xlsx_path, data_only=True)
            ws = wb.active
            if mode == "qty_input":
                temp_wb = openpyxl.Workbook()
                tws = temp_wb.active
                tws.append(["MODEL", "WEIGHT", "COST", "HEIGHT"])
                for r in ws.iter_rows(min_row=2, values_only=True):
                    if not r or not r[0] or str(r[0]).upper().startswith("INSTRUCTIONS"):
                        continue
                    tiers = "|".join(str(x if x is not None else 0) for x in r[2:11])
                    tws.append([r[0], r[1] or 0, tiers, 0])
                norm_path = get_workspace_path("_tmp_norm_import.xlsx")
                temp_wb.save(norm_path)
                ok, res = self.data_core.import_bulk_excel_sheet(norm_path, title_clean, c_id, mode, op_mode)
                if os.path.exists(norm_path):
                    os.remove(norm_path)
            else:
                ok, res = self.data_core.import_bulk_excel_sheet(xlsx_path, title_clean, c_id, mode, op_mode)
            if not ok:
                QMessageBox.critical(self, "Import Error", f"Import failed: {res}")
                return
            if self.parent() and hasattr(self.parent(), "handle_card_switch"):
                self.parent().handle_card_switch()
            if hasattr(self, "populate_inline_catalog_grid"):
                self.populate_inline_catalog_grid()
            self.sync_admin_purgable_model_dropdown()
            if hasattr(self.parent(), "custom_admin_tab"):
                self.parent().custom_admin_tab.log_admin_activity(f"Imported {res} rows into {c_id}")
            QMessageBox.information(self, "Import Complete", f"Successfully imported and sorted {res} item(s) into {c_id} ({title_clean}).")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Excel import failed: {e}")

    def save_database_entry(self):
        cat = self.cat_select.currentText()
        model = self.model_input.text().strip()
        w_txt = self.weight_input.text().strip()
        c_txt = self.cost_input.text().strip()
        if not cat or not model or not w_txt or not c_txt:
            QMessageBox.warning(self, "Missing Fields", "Enter Category, Model Label, Weight, and Base Cost first.")
            return
        try:
            w_val = float(w_txt)
            c_val = float(c_txt)
            models_list = list(self.data_core.clean_database.get(cat, {}).keys())
            schema_id = self.data_core.clean_database[cat][models_list[0]]["schema_id"] if models_list else "CARD_1"
            sheet_target = CARDS_SCHEMA_MATRIX[schema_id]["dropdown_sheet"]
            m_col = CARDS_SCHEMA_MATRIX[schema_id]["model_col"]
            w_col = CARDS_SCHEMA_MATRIX[schema_id]["weight_col"]
            c_col = CARDS_SCHEMA_MATRIX[schema_id]["cost_col"]

            if hasattr(self, "push_catalog_snapshot"):
                self.push_catalog_snapshot(f"Before Adding {model}")

            rows = self.data_core.raw_full_json_blob.setdefault(sheet_target, [])
            max_col = max(m_col, w_col, c_col) + 1
            new_row = [""] * max_col
            new_row[m_col] = model
            new_row[w_col] = w_val
            new_row[c_col] = c_val
            rows.append(new_row)

            with open(self.data_core.database_file, "w", encoding="utf-8") as f:
                json.dump(self.data_core.raw_full_json_blob, f, indent=4)

            self.data_core.load_and_sanitize_matrix()
            if self.parent() and hasattr(self.parent(), "handle_card_switch"):
                self.parent().handle_card_switch()
            if hasattr(self, "populate_inline_catalog_grid"):
                self.populate_inline_catalog_grid()
            self.sync_admin_purgable_model_dropdown()
            self.model_input.clear()
            self.weight_input.clear()
            self.cost_input.clear()
            if hasattr(self.parent(), "custom_admin_tab"):
                self.parent().custom_admin_tab.log_admin_activity(f"Added {model} to {cat}")
            QMessageBox.information(self, "Variant Added", f"Successfully added {model} (${c_val:,.2f}) to {cat}.")
        except ValueError:
            QMessageBox.warning(self, "Invalid Numbers", "Weight and Base Cost must be valid numeric values.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to add variant: {e}")

    def sync_admin_purgable_model_dropdown(self):
        from PySide6.QtWidgets import QTableWidgetItem
        cat = self.bulk_cat_select.currentText()
        if not cat or cat not in self.data_core.clean_database:
            return
        q = self.bulk_model_filter.text().strip().lower() if hasattr(self, "bulk_model_filter") else ""
        items = [(m, info) for m, info in self.data_core.clean_database[cat].items() if not q or q in m.lower()]
        self.delete_model_list.setRowCount(len(items))
        for r_i, (m_name, info) in enumerate(items):
            self.delete_model_list.setRowHeight(r_i, 30)
            c0 = QTableWidgetItem(m_name); c0.setForeground(QColor("#0f172a"))
            c1 = QTableWidgetItem(str(info.get("lbs", "0"))); c1.setTextAlignment(Qt.AlignCenter); c1.setForeground(QColor("#1e3a8a"))
            c2 = QTableWidgetItem(str(info.get("cost", "0.00"))); c2.setTextAlignment(Qt.AlignCenter); c2.setForeground(QColor("#047857"))
            self.delete_model_list.setItem(r_i, 0, c0); self.delete_model_list.setItem(r_i, 1, c1); self.delete_model_list.setItem(r_i, 2, c2)

    def create_tab_4_inline_grid(self):
        from PySide6.QtWidgets import QTableWidget, QHeaderView
        tab4_page = QWidget()
        tab4_page.setStyleSheet("background: transparent !important;")
        lay = QVBoxLayout(tab4_page)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        t4_top_frame = QFrame()
        t4_top_frame.setStyleSheet("QFrame { background-color: rgba(248, 250, 252, 0.78); border: 1px solid #cbd5e1; border-radius: 8px; }")
        top_bar = QHBoxLayout(t4_top_frame)
        top_bar.setContentsMargins(10, 6, 10, 6)
        top_bar.addWidget(QLabel("Category:"))
        self.grid_cat_select = QComboBox()
        self.grid_cat_select.addItems(list(self.data_core.clean_database.keys()))
        self.grid_cat_select.currentIndexChanged.connect(self.populate_inline_catalog_grid)
        top_bar.addWidget(self.grid_cat_select, 1)

        self.grid_filter_input = QLineEdit()
        self.grid_filter_input.setPlaceholderText("Filter models in grid...")
        self.grid_filter_input.textChanged.connect(self.filter_inline_catalog_grid)
        top_bar.addWidget(self.grid_filter_input, 1)

        self.cat_snap_combo = QComboBox()
        self.cat_snap_combo.setMinimumWidth(180)
        self.cat_snap_combo.addItem("Catalog Snapshots (0)")
        top_bar.addWidget(self.cat_snap_combo)

        btn_cat_undo = QPushButton("Restore Snapshot")
        btn_cat_undo.setStyleSheet("background-color: #ffffff; border: 1px solid #94a3b8; color: #0f172a; font-weight: 700; padding: 6px 12px; border-radius: 6px;")
        btn_cat_undo.clicked.connect(self.restore_catalog_snapshot)
        top_bar.addWidget(btn_cat_undo)
        lay.addWidget(t4_top_frame)

        self.inline_cat_table = QTableWidget(0, 3)
        apply_excel_table_style(self.inline_cat_table)
        self.inline_cat_table.setAlternatingRowColors(True)
        self.inline_cat_table.setHorizontalHeaderLabels(["MODEL / PART NUMBER", "WEIGHT (LBS)", "BASE LIST COST ($)"])
        ihdr = self.inline_cat_table.horizontalHeader()
        ihdr.setStretchLastSection(True)
        ihdr.setVisible(True)
        ihdr.setFixedHeight(32)
        ihdr.setStyleSheet("QHeaderView::section { background-color: #dcebfa; color: #0369a1; font-weight: 600; font-size: 12px; padding: 6px; border-bottom: 2px solid #475569; }")
        ihdr_qss = "QHeaderView::section { background-color: #dcebfa; color: #0369a1; font-family: 'Segoe UI', sans-serif; font-size: 12px; font-weight: 700; padding: 6px 8px; border: none; border-bottom: 2px solid #475569; }"
        ihdr.setStyleSheet(ihdr_qss)
        for c_i, w_i in [(0, 420), (1, 140), (2, 160)]:
            ihdr.setSectionResizeMode(c_i, QHeaderView.Interactive)
            self.inline_cat_table.setColumnWidth(c_i, w_i)
        ihdr.sectionDoubleClicked.connect(lambda c: self.inline_cat_table.resizeColumnToContents(c))
        self.inline_cat_table.verticalHeader().setVisible(False)
        self.inline_cat_table.setStyleSheet("""
            QTableWidget { background-color: rgba(207, 228, 250, 0.46) !important; alternate-background-color: rgba(239, 246, 255, 0.72) !important; color: #0f172a !important; border: 1px solid #cbd5e1; border-radius: 8px; gridline-color: rgba(96, 165, 250, 0.55); font-family: 'Segoe UI', sans-serif; font-size: 12px; font-weight: 600; }
            QTableWidget::viewport { background: transparent !important; }
            QTableWidget QLineEdit { background-color: #dcebfa !important; color: #0f172a !important; border: 1px solid #38bdf8 !important; padding: 2px 6px !important; }
            QTableWidget::item:selected, QTableWidget::item:selected:!active { background-color: #93c5fd; color: #0f172a; }
        """)
        self.inline_cat_table.itemChanged.connect(self.on_inline_cat_cell_changed)
        self.inline_cat_table.horizontalHeader().setVisible(False)
        t4_hdr = QFrame()
        t4_hdr.setStyleSheet("background-color: rgba(207, 228, 250, 0.85); border: 1px solid #475569; border-radius: 6px;")
        t4_hl = QHBoxLayout(t4_hdr); t4_hl.setContentsMargins(10, 6, 10, 6)
        for txt, w in [("MODEL / PART NUMBER", 415), ("WEIGHT (LBS)", 140), ("BASE LIST COST ($)", 0)]:
            lbl = QLabel(txt); lbl.setStyleSheet("color: #0369a1; font-weight: 700; font-size: 12px;")
            if w: lbl.setFixedWidth(w); lbl.setAlignment(Qt.AlignCenter if "WEIGHT" in txt else Qt.AlignLeft)
            else: lbl.setAlignment(Qt.AlignCenter)
            t4_hl.addWidget(lbl, 0 if w else 1)
        lay.addWidget(t4_hdr)
        lay.addWidget(self.inline_cat_table, 1)

        btn_commit_grid = QPushButton("COMMIT INLINE GRID PRICE && WEIGHT EDITS TO DATABASE")
        btn_commit_grid.setObjectName("EmeraldAction")
        btn_commit_grid.setMinimumHeight(38)
        btn_commit_grid.clicked.connect(self.commit_inline_catalog_edits)
        lay.addWidget(btn_commit_grid)

        self._cat_snapshots = []
        self.populate_inline_catalog_grid()
        for _b in tab4_page.findChildren(QPushButton):
            if _b is not btn_cat_undo:
                _b.setStyleSheet("QPushButton { background-color: #ffffff !important; border: 1.5px solid #0284c7 !important; color: #0284c7 !important; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12.5px; font-weight: 700; border-radius: 6px; padding: 4px 12px; } QPushButton:hover { background-color: rgba(110, 231, 183, 0.86) !important; }")
        self.admin_tabs_deck.addTab(tab4_page, "Inline Catalog Grid Editor")

    def push_catalog_snapshot(self, label):
        import copy, datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._cat_snapshots.insert(0, (f"{ts} - {label}", copy.deepcopy(self.data_core.raw_full_json_blob)))
        self._cat_snapshots = self._cat_snapshots[:5]
        if hasattr(self, "cat_snap_combo"):
            self.cat_snap_combo.clear()
            for lbl, _ in self._cat_snapshots:
                self.cat_snap_combo.addItem(lbl)

    def restore_catalog_snapshot(self):
        idx = self.cat_snap_combo.currentIndex()
        if not getattr(self, "_cat_snapshots", None) or idx < 0 or idx >= len(self._cat_snapshots):
            QMessageBox.information(self, "No Snapshot", "No catalog snapshot recorded yet in this session.")
            return
        lbl, blob = self._cat_snapshots[idx]
        self.data_core.raw_full_json_blob = blob
        with open(self.data_core.database_file, "w", encoding="utf-8") as f:
            json.dump(self.data_core.raw_full_json_blob, f, indent=4)
        self.data_core.load_and_sanitize_matrix()
        if self.parent() and hasattr(self.parent(), "handle_card_switch"):
            self.parent().handle_card_switch()
        self.populate_inline_catalog_grid()
        self.sync_admin_purgable_model_dropdown()
        QMessageBox.information(self, "Catalog Restored", f"Restored catalog database to: {lbl}")

    def populate_inline_catalog_grid(self):
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtGui import QColor
        cat = self.grid_cat_select.currentText()
        if not cat or cat not in self.data_core.clean_database:
            return
        self.inline_cat_table.blockSignals(True)
        models = list(self.data_core.clean_database[cat].items())
        self.inline_cat_table.setRowCount(len(models))
        for r_i, (m_name, info) in enumerate(models):
            self.inline_cat_table.setRowHeight(r_i, 28)
            c0 = QTableWidgetItem(m_name); c0.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            w_raw = "".join(ch for ch in str(info.get('lbs', 0.0)) if ch in ('.', '-') or ch.isdigit())
            w_num = float(w_raw) if w_raw else 0.0
            c1 = QTableWidgetItem(f"{w_num:g}"); c1.setTextAlignment(Qt.AlignCenter); c1.setData(Qt.UserRole, f"{w_num:g}")
            c2 = QTableWidgetItem(f"{float(info.get('cost', 0.0)):.2f}"); c2.setTextAlignment(Qt.AlignCenter); c2.setForeground(QColor("#047857")); c2.setData(Qt.UserRole, f"{float(info.get('cost', 0.0)):.2f}")
            self.inline_cat_table.setItem(r_i, 0, c0); self.inline_cat_table.setItem(r_i, 1, c1); self.inline_cat_table.setItem(r_i, 2, c2)
        self.inline_cat_table.blockSignals(False)
        self.filter_inline_catalog_grid()

    def filter_inline_catalog_grid(self):
        q = self.grid_filter_input.text().strip().lower()
        for r_i in range(self.inline_cat_table.rowCount()):
            self.inline_cat_table.setRowHidden(r_i, bool(q and q not in self.inline_cat_table.item(r_i, 0).text().lower()))

    def on_inline_cat_cell_changed(self, item):
        from PySide6.QtGui import QColor
        if item.column() in (1, 2):
            if item.text().strip() != item.data(Qt.UserRole):
                item.setBackground(QColor(245, 158, 11, 75)); item.setForeground(QColor("#b45309"))
            else:
                item.setBackground(QColor(0, 0, 0, 0)); item.setForeground(QColor("#047857") if item.column() == 2 else QColor("#f8fafc"))

    def commit_inline_catalog_edits(self):
        cat = self.grid_cat_select.currentText()
        models_list = list(self.data_core.clean_database.get(cat, {}).keys())
        if not models_list: return
        schema_id = self.data_core.clean_database[cat][models_list[0]]["schema_id"]
        sheet_target = CARDS_SCHEMA_MATRIX[schema_id]["dropdown_sheet"]
        m_col, w_col, c_col = CARDS_SCHEMA_MATRIX[schema_id]["model_col"], CARDS_SCHEMA_MATRIX[schema_id]["weight_col"], CARDS_SCHEMA_MATRIX[schema_id]["cost_col"]
        updates = {}
        try:
            for r_i in range(self.inline_cat_table.rowCount()):
                w_it, c_it = self.inline_cat_table.item(r_i, 1), self.inline_cat_table.item(r_i, 2)
                if w_it.text().strip() != w_it.data(Qt.UserRole) or c_it.text().strip() != c_it.data(Qt.UserRole):
                    updates[self.inline_cat_table.item(r_i, 0).text().strip()] = (float(w_it.text().strip()), float(c_it.text().strip()))
        except ValueError:
            QMessageBox.warning(self, "Invalid Number", "Ensure all edited Weight and Cost cells contain valid numbers."); return
        if not updates:
            QMessageBox.information(self, "No Changes", "No cells were modified in the grid."); return
        self.push_catalog_snapshot(f"Grid Edit ({len(updates)} in {cat})")
        for r in self.data_core.raw_full_json_blob.get(sheet_target, []):
            if len(r) > m_col and str(r[m_col]).strip() in updates:
                nw, nc = updates[str(r[m_col]).strip()]
                if len(r) > w_col: r[w_col] = nw
                if len(r) > c_col: r[c_col] = nc
        with open(self.data_core.database_file, "w", encoding="utf-8") as f:
            json.dump(self.data_core.raw_full_json_blob, f, indent=4)
        self.data_core.load_and_sanitize_matrix()
        if self.parent() and hasattr(self.parent(), "handle_card_switch"): self.parent().handle_card_switch()
        self.populate_inline_catalog_grid()
        if hasattr(self.parent(), "custom_admin_tab"): self.parent().custom_admin_tab.log_admin_activity(f"Edited {len(updates)} model(s) in {cat}")
        QMessageBox.information(self, "Grid Saved", f"Updated {len(updates)} model(s) in {cat}.")

# ==========================================
# SECTION 10: USER WORKSTATION FRAME INITIALIZATION
# ==========================================
class StandaloneManufacturingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bowman-Morton Standalone Pricing Tool & RFQ Ledger")
        self.setMinimumSize(1300, 850)
        self.setStyleSheet(MODERN_STYLESHEET)
        
        self.data_core = DataProcessingCore()
        self.data_core.load_and_sanitize_matrix()
        
        from PySide6.QtGui import QPainter, QPixmap
        class _FullScreenBackdropWidget(QWidget):
            def __init__(self, img_path, parent=None):
                super().__init__(parent)
                self._bg_pix = QPixmap(img_path)
                self._cached_sz = None
                self._cached_layer = None
            def _rebuild_cache(self):
                from PySide6.QtGui import QPen
                pm = QPixmap(self.size())
                pm.fill(QColor("#e8eef5"))
                p = QPainter(pm)
                p.setPen(QPen(QColor(148, 163, 184, 85), 1))
                for gx in range(0, self.width(), 32): p.drawLine(gx, 0, gx, self.height())
                for gy in range(0, self.height(), 32): p.drawLine(0, gy, self.width(), gy)
                if not self._bg_pix.isNull():
                    p.setOpacity(0.06)
                    scaled = self._bg_pix.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.FastTransformation)
                    p.drawPixmap((self.width() - scaled.width()) // 2, (self.height() - scaled.height()) // 2, scaled)
                p.end()
                self._cached_sz = self.size()
                self._cached_layer = pm
            def paintEvent(self, ev):
                if self._cached_layer is None or self._cached_sz != self.size():
                    self._rebuild_cache()
                p = QPainter(self)
                p.drawPixmap(0, 0, self._cached_layer)
                p.end()

        self.central_widget = QWidget(self)
        self.central_widget.setStyleSheet("QWidget { background-color: #e2e8f0; }")
        self.setCentralWidget(self.central_widget)
        
        outer_deck_layout = QVBoxLayout(self.central_widget)
        outer_deck_layout.setContentsMargins(12, 12, 12, 12)

        self.custom_safeguards_file = get_workspace_path("shop_safeguards.json")
        self.custom_ledger_file = get_workspace_path("project_ledger.json")
        self.custom_safeguards = self._load_custom_safeguards()
        self.custom_ledger_pool, self.custom_quote_seq = self._load_custom_ledger()

        self.master_tabs = QTabWidget()
        self.master_tabs.setObjectName("MasterTransparentTabs")
        self.master_tabs.tabBar().setVisible(False)
        self.master_tabs.setDocumentMode(True)
        self.master_tabs.setStyleSheet('QTabWidget#MasterTransparentTabs::pane { border: none; margin: 0px; padding: 0px; background-color: #f1f5f9; }')
        import ribbon_bar_widget as rbw
        from PySide6.QtWidgets import QSplitter
        self.master_ribbon = rbw.BowmanMortonRibbonBar(self, self.central_widget)
        self.master_tabs.currentChanged.connect(self.master_ribbon.set_active_tab)
        outer_deck_layout.setContentsMargins(0, 0, 0, 0)
        outer_deck_layout.setSpacing(0)
        outer_deck_layout.addWidget(self.master_ribbon, 0)
        self.fx_bar = QFrame()
        self.fx_bar.setFixedHeight(28)
        self.fx_bar.setStyleSheet("QFrame { background-color: #f8fafc; border-bottom: 1px solid #cbd5e1; } QLabel { color: #334155; font-family: 'Consolas', monospace; font-size: 12px; font-weight: 600; background: transparent; border: none; }")
        fxl = QHBoxLayout(self.fx_bar); fxl.setContentsMargins(12, 0, 12, 0); fxl.setSpacing(8)
        fx_tag = QLabel("fx")
        fx_tag.setStyleSheet("color: #0284c7; font-family: 'Georgia', serif; font-style: italic; font-size: 14px; font-weight: 700;")
        self.lbl_fx_formula = QLabel("Active Formula: Select a steel member or catalog hanger to inspect live pricing breakdown")
        fxl.addWidget(fx_tag); fxl.addWidget(self.lbl_fx_formula, 1)
        outer_deck_layout.addWidget(self.fx_bar, 0)
        self.fx_bar.setVisible(False)
        self.master_tabs.currentChanged.connect(lambda idx: self.fx_bar.setVisible(idx in (1, 2)))
        self.master_tabs.setCurrentIndex(0)
        outer_deck_layout.addWidget(self.master_tabs, 1)

        tab1_standard = QWidget()
        tab1_standard.setStyleSheet('background: transparent;')
        self.main_layout = QHBoxLayout(tab1_standard)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(20)

        self.menuBar().setVisible(False)
        self.t1_splitter = QSplitter(Qt.Horizontal)
        self.t1_splitter.setHandleWidth(8)
        self.t1_splitter.setChildrenCollapsible(False)
        self.t1_splitter.setStyleSheet("QSplitter::handle { background-color: rgba(56, 189, 248, 0.30); border-radius: 3px; margin: 4px 1px; } QSplitter::handle:hover { background-color: #0369a1; }")
        _orig_main_layout = self.main_layout
        class _SP:
            def __init__(self, sp): self.sp = sp
            def addWidget(self, w, *a): w.setMinimumWidth(340); self.sp.addWidget(w)
        self.main_layout = _SP(self.t1_splitter)
        self.setup_left_quoting_panel()
        self.setup_right_ledger_panel()
        self.main_layout = _orig_main_layout
        self.t1_splitter.setSizes([600, 600])
        self.main_layout.addWidget(self.t1_splitter)
        self.handle_card_switch()
        self.update_rfq_ledger_view()

        self.master_tabs.addTab(tab1_standard, "Standard Hangers & Catalog")

        self.custom_quoting_tab = cqm.StructuralQuotingSandbox(
            self._commit_custom_project, self.custom_safeguards, self
        )
        self.custom_ledger_tab = cqm.HistoricalArchiveLedgerPage(
            self.custom_ledger_pool, self.custom_safeguards, self._save_custom_ledger, self.reopen_quote_into_workspace, self
        )
        self.custom_admin_tab = cqm.AdminControlDashboardPage(
            self.custom_safeguards, self._on_custom_safeguards_saved, self
        )

        steel_db = getattr(self.custom_quoting_tab, "steel_matrix", {})
        self.planset_takeoff_tab = cqm.PdfBomImporterDialog(None, [], steel_db, parent=self, embed_in_main=True)
        self.planset_takeoff_tab.setWindowFlags(Qt.Widget)
        if hasattr(self.planset_takeoff_tab, "btn_accept"):
            self.planset_takeoff_tab.btn_accept.clicked.connect(
                lambda: (
                    self.custom_quoting_tab.ingest_pdf_bom_items(getattr(self.planset_takeoff_tab, "accepted_rows", []))
                    if hasattr(self.custom_quoting_tab, "ingest_pdf_bom_items") else None,
                    self.master_tabs.setCurrentIndex(2)
                )
            )
        self.master_tabs.insertTab(0, self.planset_takeoff_tab, "Planset Takeoff")
        self.master_tabs.addTab(self.custom_quoting_tab, "Custom Structural Quoting")
        self.master_tabs.addTab(self.custom_ledger_tab, "Running Project Ledger")
        self.catalog_admin_embedded = AdminDashboardWindow(self, self.data_core)
        self.catalog_admin_embedded.setWindowFlags(Qt.Widget)
        self.catalog_admin_embedded.setAttribute(Qt.WA_StyledBackground, True)
        self.catalog_admin_embedded.setStyleSheet('''
            AdminDashboardWindow, QStackedWidget, QTabWidget::pane { background: transparent !important; border: none !important; }
            QWidget { font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; color: #0f172a; }
            QTabBar::tab { background-color: #eff6ff; color: #1e3a8a; border: 1px solid #60a5fa; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 4px; }
            QTabBar::tab:selected { background-color: #ffffff; color: #0f172a; border-top: 3px solid #fbbf24; border-bottom-color: #0284c7; }
            QFrame#GlassCard, QGroupBox { background-color: rgba(248, 250, 252, 0.78) !important; border: 1px solid #cbd5e1 !important; border-radius: 8px; padding: 12px; }
            QLabel { font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; background: transparent !important; border: none !important; color: #0f172a; }
            QLineEdit, QComboBox { background-color: #ffffff !important; color: #0f172a !important; border: 1px solid #475569 !important; border-radius: 4px; padding: 6px; }
            QComboBoxPrivateContainer { background-color: #eff6ff !important; border: 1.5px solid #0284c7 !important; padding: 0px !important; margin: 0px !important; }
            ''')
        self.custom_admin_tab.attach_catalog_admin_widget(self.catalog_admin_embedded)
        UNIFIED_ADMIN_CSS = """
            AdminControlDashboardPage, AdminDashboardWindow, QStackedWidget, QTabWidget::pane,
            QTableWidget::viewport, QListWidget::viewport, QAbstractScrollArea::viewport {
                background: transparent !important;
                border: none !important;
            }
            QWidget { font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; color: #0f172a; }
            QTabBar::tab { background-color: #eff6ff; color: #1e3a8a; border: 1px solid #60a5fa; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 4px; }
            QTabBar::tab:selected { background-color: #ffffff; color: #0f172a; border-top: 3px solid #fbbf24; border-bottom-color: #0284c7; }
            QFrame#GlassCard, QGroupBox { background-color: rgba(248, 250, 252, 0.78) !important; border: 1px solid #cbd5e1 !important; border-radius: 8px; padding: 12px; }
            QFrame#LockGlass { background-color: rgba(248, 250, 252, 0.78) !important; border: 1px solid #cbd5e1 !important; border-radius: 8px; padding: 24px; }
            QLabel { font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; background: transparent !important; border: none !important; color: #0f172a; }
            QLineEdit, QComboBox { background-color: #ffffff !important; color: #0f172a !important; border: 1px solid #475569 !important; border-radius: 4px; padding: 6px; }
            QComboBoxPrivateContainer { background-color: #eff6ff !important; border: 1.5px solid #0284c7 !important; padding: 0px !important; margin: 0px !important; }
            QPushButton#EmeraldAction { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-size: 12.5px; font-weight: 700; border-radius: 6px; padding: 4px 12px; }
            QPushButton#EmeraldAction:hover { background-color: #047857; }
        """
        self.custom_admin_tab.setStyleSheet(UNIFIED_ADMIN_CSS)
        self.master_tabs.addTab(self.custom_admin_tab, "Unified Admin Center")
        self.custom_ledger_tab.populate_ledger_grid()
        
        self.file_monitor = QFileSystemWatcher(self)
        for watch_p in [self.data_core.database_file, self.custom_safeguards_file, self.custom_ledger_file]:
            if os.path.exists(watch_p):
                self.file_monitor.addPath(watch_p)
        self.file_monitor.fileChanged.connect(self.execute_silent_network_sync)

        self.data_core.rfq_ledger_items.clear()
        self.std_cust_input.clear()
        self.std_proj_input.clear()
        for _qattr in ("qty_input", "input_qty", "std_qty_input"):
            if hasattr(self, _qattr): getattr(self, _qattr).setText("1")
        self.update_rfq_ledger_view()


    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            if any(u.toLocalFile().lower().endswith((".xlsx", ".xlsm")) for u in ev.mimeData().urls()):
                ev.acceptProposedAction()
                if hasattr(self, "catalog_admin_embedded") and hasattr(self.catalog_admin_embedded, "excel_drop_pad"):
                    pad = self.catalog_admin_embedded.excel_drop_pad
                    pad.setStyleSheet(pad._hover_qss)
                return
        ev.ignore()

    def dragMoveEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dragLeaveEvent(self, ev):
        if hasattr(self, "catalog_admin_embedded") and hasattr(self.catalog_admin_embedded, "excel_drop_pad"):
            pad = self.catalog_admin_embedded.excel_drop_pad
            pad.setStyleSheet(pad._base_qss)

    def dropEvent(self, ev):
        if hasattr(self, "catalog_admin_embedded") and hasattr(self.catalog_admin_embedded, "excel_drop_pad"):
            pad = self.catalog_admin_embedded.excel_drop_pad
            pad.setStyleSheet(pad._base_qss)
        if ev.mimeData().hasUrls():
            for u in ev.mimeData().urls():
                fp = u.toLocalFile()
                if fp.lower().endswith((".xlsx", ".xlsm")):
                    ev.acceptProposedAction()
                    if hasattr(self, "catalog_admin_embedded"):
                        from PySide6.QtCore import QTimer
                        QTimer.singleShot(50, lambda p=fp: self.catalog_admin_embedded.admin_bulk_import_excel_sheet(p))
                    return

    def open_ledger_analytics_dashboard(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QFrame, QFileDialog
        from collections import defaultdict
        import csv

        quotes = list(getattr(self, "custom_ledger_pool", []) or [])
        if not quotes:
            ledger_path = get_workspace_path("custom_ledger.json")
            if os.path.exists(ledger_path):
                try:
                    with open(ledger_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list): quotes = data
                except Exception:
                    quotes = []

        dlg = QDialog(self)
        dlg.setWindowTitle("Running Project Ledger - Quote Analytics & Trends")
        dlg.resize(1140, 660)
        dlg.setStyleSheet("QDialog { background-color: #dcebfa; } QLabel { color: #0f172a; font-weight: 700; }")
        vl = QVBoxLayout(dlg); vl.setContentsMargins(16, 14, 16, 14); vl.setSpacing(12)

        total_rev = sum(float(q.get("cost", q.get("total_cost", q.get("grand_total", 0))) or 0) for q in quotes)
        total_lbs = sum(float(q.get("weight", q.get("total_lbs", q.get("total_weight", 0))) or 0) for q in quotes)
        avg_val = (total_rev / len(quotes)) if quotes else 0.0
        std_cnt = sum(1 for q in quotes if any(k in (str(q.get("project", "")) + " " + str(q.get("quote_type", ""))).upper() for k in ("STANDARD", "CATALOG")) or str(q.get("id", q.get("quote_id", ""))).startswith("BM-STD"))
        cust_cnt = len(quotes) - std_cnt

        kpi_row = QHBoxLayout(); kpi_row.setSpacing(10)
        for title, val, accent in [
            ("TOTAL QUOTED PIPELINE", f"${total_rev:,.2f}", "#059669"),
            ("TOTAL QUOTED WEIGHT", f"{total_lbs:,.0f} lbs ({total_lbs/2000.0:,.2f} Tons)", "#0284c7"),
            ("TOTAL QUOTES LOGGED", f"{len(quotes)}  ({std_cnt} Catalog / {cust_cnt} Structural)", "#1e3a8a"),
            ("AVERAGE QUOTE VALUE", f"${avg_val:,.2f}", "#d97706"),
        ]:
            card = QFrame()
            card.setStyleSheet("QFrame { background-color: rgba(239, 246, 255, 0.88); border: 1px solid #cbd5e1; border-radius: 8px; padding: 4px 12px; }")
            cl = QVBoxLayout(card); cl.setContentsMargins(8, 6, 8, 6); cl.setSpacing(4)
            t_l = QLabel(title); t_l.setStyleSheet("color: #475569; font-size: 12px; font-weight: 700; border: none; background: transparent;")
            v_l = QLabel(val); v_l.setStyleSheet(f"color: {accent}; font-size: 18px; font-weight: 700; border: none; background: transparent;")
            cl.addWidget(t_l); cl.addWidget(v_l); kpi_row.addWidget(card, 1)
        vl.addLayout(kpi_row)

        cust_totals = defaultdict(lambda: [0, 0.0, 0.0])
        month_totals = defaultdict(lambda: [0, 0.0, 0.0])
        for q in quotes:
            c_name = str(q.get("customer", "Walk-In / Unassigned")).strip() or "Walk-In / Unassigned"
            dt_str = str(q.get("timestamp", q.get("date", "")))[:7] or "Unknown"
            gt = float(q.get("cost", q.get("total_cost", q.get("grand_total", 0))) or 0)
            wt = float(q.get("weight", q.get("total_lbs", q.get("total_weight", 0))) or 0)
            cust_totals[c_name][0] += 1; cust_totals[c_name][1] += wt; cust_totals[c_name][2] += gt
            month_totals[dt_str][0] += 1; month_totals[dt_str][1] += wt; month_totals[dt_str][2] += gt

        mid_row = QHBoxLayout(); mid_row.setSpacing(12)
        def _make_summary_tbl(headers, rows_data):
            t = QTableWidget(len(rows_data), len(headers))
            t.setHorizontalHeaderLabels(headers); t.setAlternatingRowColors(True); t.verticalHeader().setVisible(False)
            t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            for ci in range(1, len(headers)):
                t.horizontalHeader().setSectionResizeMode(ci, QHeaderView.ResizeToContents)
            t.setStyleSheet("QTableWidget { background-color: rgba(239, 246, 255, 0.86); alternate-background-color: #dcebfa; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 14px; font-weight: 600; } QHeaderView::section { background-color: #bfdbfe; color: #0f172a; font-weight: 700; padding: 6px; border: none; border-bottom: 1.5px solid #60a5fa; }")
            for r_i, row_vals in enumerate(rows_data):
                for c_i, val in enumerate(row_vals):
                    it = QTableWidgetItem(str(val))
                    if c_i > 0: it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    t.setItem(r_i, c_i, it)
            return t

        top_cust_rows = [[k, v[0], f"{v[1]:,.0f} lbs", f"${v[2]:,.2f}"] for k, v in sorted(cust_totals.items(), key=lambda x: x[1][2], reverse=True)]
        month_rows = [[k, v[0], f"{v[1]:,.0f} lbs", f"${v[2]:,.2f}"] for k, v in sorted(month_totals.items(), reverse=True)]
        c_box = QVBoxLayout(); c_box.addWidget(QLabel("TOP CUSTOMERS BY QUOTED VOLUME")); c_box.addWidget(_make_summary_tbl(["Customer", "Quotes", "Weight", "Quoted ($)"], top_cust_rows))
        m_box = QVBoxLayout(); m_box.addWidget(QLabel("MONTHLY QUOTE & TONNAGE TRENDS")); m_box.addWidget(_make_summary_tbl(["Month", "Quotes", "Weight", "Quoted ($)"], month_rows))
        mid_row.addLayout(c_box, 1); mid_row.addLayout(m_box, 1); vl.addLayout(mid_row, 1)

        bot = QHBoxLayout()
        btn_csv = QPushButton("Export Analytics Summary (.CSV / Excel)")
        btn_csv.setStyleSheet("background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; padding: 8px 14px; border-radius: 6px;")
        def _export_csv():
            sp, _ = QFileDialog.getSaveFileName(dlg, "Save Quote Analytics CSV", get_workspace_path("Bowman_Morton_Quote_Trends.csv"), "CSV Files (*.csv)")
            if not sp: return
            with open(sp, "w", newline="", encoding="utf-8") as cf:
                w = csv.writer(cf)
                w.writerow(["SECTION", "NAME / MONTH", "QUOTE COUNT", "TOTAL WEIGHT (LBS)", "TOTAL QUOTED ($)"])
                for r in top_cust_rows: w.writerow(["Customer"] + r)
                for r in month_rows: w.writerow(["Month"] + r)
            QMessageBox.information(dlg, "Exported", f"Quote trends exported to:\n{sp}")
        btn_csv.clicked.connect(_export_csv); bot.addWidget(btn_csv); bot.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setStyleSheet("background-color: rgba(147, 197, 253, 0.78); border: 1.5px solid #0284c7; color: #000000; font-weight: 700; padding: 8px 18px; border-radius: 6px;")
        btn_close.clicked.connect(dlg.accept); bot.addWidget(btn_close); vl.addLayout(bot); dlg.exec()

    def open_developer_code_studio(self):
        from PySide6.QtWidgets import QInputDialog, QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QPlainTextEdit, QPushButton, QLabel, QMessageBox
        from PySide6.QtGui import QFont
        import py_compile, sys, os

        pwd, ok = QInputDialog.getText(self, "Developer Authentication", "Enter Master Developer Password:", QLineEdit.Password)
        if not ok or not pwd:
            return
        if pwd != "100901$":
            QMessageBox.critical(self, "Access Denied", "Invalid Developer Password.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Bowman Morton Live Developer & Hot-Reload Studio")
        dlg.resize(1120, 740)
        dlg.setStyleSheet("QDialog { background-color: #dcebfa; } QLabel { color: #0f172a; font-weight: 700; }")
        vl = QVBoxLayout(dlg)
        vl.setContentsMargins(14, 12, 14, 12)
        vl.setSpacing(8)

        top = QHBoxLayout()
        top.addWidget(QLabel("Active Module:"))
        file_cb = QComboBox()
        modules = [f for f in ("live_test.py", "custom_quoting_module.py", "ribbon_bar_widget.py", "blueprint_takeoff_ui.py", "bom_summary_panel.py", "matrix.json", "admin_rates.json", "steel_shapes.json") if os.path.exists(get_workspace_path(f))]
        file_cb.addItems(modules)
        top.addWidget(file_cb, 1)

        search_ed = QLineEdit()
        search_ed.setPlaceholderText("Find text in module...")
        top.addWidget(search_ed, 1)

        btn_find = QPushButton("Find Next")
        btn_find.setStyleSheet("background-color: rgba(147, 197, 253, 0.75); border: 1.5px solid #0284c7; color: #000000; font-weight: 700; padding: 6px 12px; border-radius: 5px;")
        top.addWidget(btn_find)
        vl.addLayout(top)

        editor = QPlainTextEdit()
        editor.setFont(QFont("Consolas", 12))
        editor.setStyleSheet("QPlainTextEdit { background-color: #f8fafc; color: #0f172a; border: 1.5px solid #0284c7; border-radius: 6px; padding: 8px; }")
        vl.addWidget(editor, 1)

        status_lbl = QLabel("Ready ? edit source code directly and click Save & Hot-Reload App.")
        status_lbl.setStyleSheet("color: #0369a1; font-size: 14px;")
        vl.addWidget(status_lbl)

        def _load_file():
            fp = get_workspace_path(file_cb.currentText())
            with open(fp, "r", encoding="utf-8") as f:
                editor.setPlainText(f.read())
            status_lbl.setText(f"Loaded {file_cb.currentText()} ({len(editor.toPlainText().splitlines())} lines)")

        def _find_next():
            q = search_ed.text()
            if q and not editor.find(q):
                cur = editor.textCursor()
                cur.movePosition(cur.MoveOperation.Start)
                editor.setTextCursor(cur)
                editor.find(q)

        def _save_and_reload(restart_now=False):
            fname = file_cb.currentText()
            fp = get_workspace_path(fname)
            bak = fp + ".bak"
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    old_txt = f.read()
                with open(bak, "w", encoding="utf-8") as f:
                    f.write(old_txt)
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(editor.toPlainText())
                if fname.endswith(".py"):
                    py_compile.compile(fp, doraise=True)
                elif fname.endswith(".json"):
                    json.loads(editor.toPlainText())
                status_lbl.setText(f"Saved & verified {fname} cleanly! Backup stored at {fname}.bak.")
                if restart_now:
                    dlg.accept()
                    os.execl(sys.executable, sys.executable, *sys.argv)
            except Exception as ex:
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(old_txt)
                QMessageBox.critical(dlg, "Syntax / Validation Error (Rolled Back)", f"Change reverted automatically:\n{ex}")

        file_cb.currentIndexChanged.connect(_load_file)
        btn_find.clicked.connect(_find_next)
        search_ed.returnPressed.connect(_find_next)
        _load_file()

        bot = QHBoxLayout()
        btn_save = QPushButton("Save & Verify Syntax")
        btn_save.setStyleSheet("background-color: rgba(147, 197, 253, 0.75); border: 2px solid #0284c7; color: #000000; font-weight: 700; padding: 8px 16px; border-radius: 6px;")
        btn_save.clicked.connect(lambda: _save_and_reload(False))
        bot.addWidget(btn_save, 1)

        btn_reload = QPushButton("Save & Hot-Reload App Now")
        btn_reload.setStyleSheet("background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; padding: 8px 16px; border-radius: 6px;")
        btn_reload.clicked.connect(lambda: _save_and_reload(True))
        bot.addWidget(btn_reload, 1)
        vl.addLayout(bot)

        dlg.exec()

# ==========================================
# SECTION 11: REPORTLAB DOCUMENT EXPORT ENGINE
# ==========================================
    def generate_pdf_quote_document(self, explicit_path=None):
        if not self.data_core.rfq_ledger_items: 
            QMessageBox.warning(self, "Ledger Empty", "Add items to your RFQ Ledger before exporting.")
            return None
        try:
            if explicit_path: pdf_path = explicit_path
            else:
                desktop_folder = os.path.join(os.path.expanduser("~"), "Desktop")
                pdf_path = os.path.join(desktop_folder, "Bowman_Morton_Quote.pdf")
                
            if not pdf_path.endswith(".pdf"): pdf_path += ".pdf"
            
            doc = SimpleDocTemplate(pdf_path, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
            styles = getSampleStyleSheet()
            story = []
            
            title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=22, textColor=colors.HexColor('#0f172a'), spaceAfter=4)
            current_date_str = datetime.datetime.now().strftime("%m/%d/%Y")
            subtitle_style = ParagraphStyle('DocSub', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#0284c7'), spaceAfter=20)
            cell_header_style = ParagraphStyle('CellHead', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.white)
            cell_style = ParagraphStyle('CellBody', parent=styles['Normal'], fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#334155'), leading=13)
            cell_addons_style = ParagraphStyle('CellAddons', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=8.5, textColor=colors.HexColor('#64748b'), leading=11, leftIndent=12)
            cell_bold = ParagraphStyle('CellBodyBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#0f172a'))
            summary_label_style = ParagraphStyle('SummaryLabel', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#475569'), alignment=2)
            summary_val_style = ParagraphStyle('SummaryVal', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#0f172a'))
            total_style = ParagraphStyle('TotalStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor('#0284c7'))

            story.append(Paragraph("BOWMAN-MORTON MFG & MACHINE", title_style))
            story.append(Paragraph(f"OFFICIAL PRICE QUOTE STATEMENT â€” {current_date_str}", subtitle_style))
            
            table_data = [[Paragraph("PART MODEL SPECIFICATION VARIANT", cell_header_style), Paragraph("EST. UNIT WEIGHT", cell_header_style), Paragraph("STANDALONE COST", cell_header_style)]]
            tot_cost, tot_weight = 0.0, 0.0
            
            for idx, item in enumerate(self.data_core.rfq_ledger_items):
                model_name = str(item['model'])
                addons_str = item.get("addons", "None")
                
                description_cell = [Paragraph(model_name, cell_style)]
                if addons_str != "None": description_cell.append(Paragraph(f"Requested Add-ons: {addons_str}", cell_addons_style))

                table_data.append([description_cell, Paragraph(str(item['weight']), cell_style), Paragraph(str(item['cost']), cell_bold)])
                try: tot_cost += float(item['cost'].replace("$", "").replace(",", ""))
                except ValueError: pass
                try: tot_weight += float(item['weight'].lower().replace("lbs", "").strip())
                except ValueError: pass

            # --- REPLACE the summary lines with this exact structure ---
            
            table_data.append([
                Paragraph("AGGREGATE ORDER SHIPPING WEIGHT:", summary_label_style),
                Paragraph("", cell_style),  # Leave Column 1 blank for the merge span
                Paragraph(f"{tot_weight:.1f} lbs", summary_val_style)  # Moved to Column 2!
            ])
            
            table_data.append([
                Paragraph("TOTAL MASTER CALCULATED ORDER VALUE (USD):", summary_label_style),
                Paragraph("", cell_style),  # Leave Column 1 blank for the merge span
                Paragraph(f"${tot_cost:,.2f}", total_style)  # Moved to Column 2!
            ])
            
            # ACCURATE CELL AUTOWRAP WIDTH ALLOCATION
            ledger_table = Table(table_data, colWidths=[330, 105, 105])
            # --- REPLACE THE SPAN VALUES IN THE TABLE STYLES ARRAY ---
            ledger_styles = [
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('TOPPADDING', (0,0), (-1,0), 8),
                ('BOTTOMPADDING', (0,0), (-1,0), 8),
                
                # Merge the left descriptions cleanly across columns 0 and 1
                ('SPAN', (0, -2), (1, -2)), 
                ('SPAN', (0, -1), (1, -1)),
                
                # Keep column 2 visible and aligned nicely with your line costs
                ('ALIGN', (2, -2), (2, -1), 'LEFT'), 
                
                ('LINEABOVE', (0, -2), (-1, -2), 1.5, colors.HexColor('#0f172a')), 
                ('TOPPADDING', (0, -2), (-1, -1), 10),
                ('BOTTOMPADDING', (0, -2), (-1, -1), 10),
            ]
            
            for r_idx in range(1, len(table_data) - 2):
                bg = colors.HexColor('#f8fafc') if r_idx % 2 == 1 else colors.white
                ledger_styles.append(('BACKGROUND', (0, r_idx), (-1, r_idx), bg))
                ledger_styles.append(('LINEBELOW', (0, r_idx), (-1, r_idx), 0.5, colors.HexColor('#e2e8f0')))
                ledger_styles.append(('TOPPADDING', (0, r_idx), (-1, r_idx), 8))
                ledger_styles.append(('BOTTOMPADDING', (0, r_idx), (-1, r_idx), 8))
                
            ledger_table.setStyle(TableStyle(ledger_styles))
            story.append(ledger_table)
            story.append(Spacer(1, 25))
            
            foot_style = ParagraphStyle('LegalFoot', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=8, textColor=colors.HexColor('#64748b'), leading=11)
            story.append(Paragraph("<b>Terms & Operations Loop:</b> All listed structural pricing line metrics reflect current internal standard plant operational cycles. Valid for 10 days.", foot_style))
            
            doc.build(story)
            if sys.platform == "win32": os.startfile(pdf_path)
            return pdf_path
        except Exception as e:
            QMessageBox.critical(self, "PDF Error", f"Failed to generate quote document: {e}")
            return None

    def trigger_save_as_file_dialog(self):
        if not self.data_core.rfq_ledger_items: return
        target_f, _ = QFileDialog.getSaveFileName(self, "Export Custom Price Quote Package", get_workspace_path("Bowman_Morton_Quote.pdf"), "Portable Document Format (*.pdf)")
        if target_f: self.generate_pdf_quote_document(explicit_path=target_f)

    def trigger_email_client_package(self):
        if not self.data_core.rfq_ledger_items: return
        try:
            body_str = "Bowman-Morton Quote Breakdown:\n\n"
            tot = 0.0
            for item in self.data_core.rfq_ledger_items:
                body_str += f"- {item['model']}: {item['cost']}\n"
                try: tot += float(item['cost'].replace("$", "").replace(",", ""))
                except ValueError: pass
            body_str += f"\nTotal Order Value: ${tot:.2f}"
            webbrowser.open("mailto:?subject=Bowman-Morton%20Manufacturing%20Quote%20Package&body=" + urllib.parse.quote(body_str))
        except Exception as e: QMessageBox.critical(self, "Mail Error", f"Could not launch default mail software: {e}")
# ==========================================
# SECTION 12: PARAMETERS VIEW CONTEXT
# ==========================================
    def setup_left_quoting_panel(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("background: transparent; border: none;")
        
        container = QWidget()
        container.setObjectName("LeftScrollContainer")
        container.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(container)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll_layout.setSpacing(15)
        
        std_cust_card = QWidget()
        std_cust_card.setAttribute(Qt.WA_StyledBackground, True)
        std_cust_card.setStyleSheet('''
            QWidget {
                background-color: rgba(248, 250, 252, 0.78);
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
            QLabel { color: #0f172a; font-weight: 600; background: transparent; border: none; }
            QLineEdit {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #475569;
                padding: 6px;
                border-radius: 4px;
            }
        ''')
        std_cust_card.setMinimumHeight(88)
        std_cust_grid = QGridLayout(std_cust_card)
        std_cust_grid.setContentsMargins(12, 12, 12, 12)
        std_cust_grid.addWidget(QLabel("Customer Name:"), 0, 0)
        self.std_cust_input = QLineEdit()
        self.std_cust_input.setPlaceholderText("Customer Name / Company...")
        std_cust_grid.addWidget(self.std_cust_input, 0, 1)
        std_cust_grid.addWidget(QLabel("Project Name:"), 1, 0)
        self.std_proj_input = QLineEdit()
        self.std_proj_input.setPlaceholderText("Project Reference / Bid ID...")
        self.std_cust_input.textChanged.connect(self.update_rfq_ledger_view)
        self.std_proj_input.textChanged.connect(self.update_rfq_ledger_view)
        std_cust_grid.addWidget(self.std_proj_input, 1, 1)
        scroll_layout.addWidget(std_cust_card)

        c1 = QWidget()
        c1.setAttribute(Qt.WA_StyledBackground, True)
        c1.setStyleSheet("""
            QWidget { 
                background-color: rgba(248, 250, 252, 0.78); 
                border: 1px solid #cbd5e1; 
                border-radius: 8px; 
            }
            QLabel { color: #0f172a; font-weight: 600; background: transparent; border: none; }
            QComboBox QAbstractItemView { background-color: #dcebfa; color: #0f172a; font-family: 'Segoe UI', Arial, sans-serif; font-weight: 600; font-size: 12px; selection-background-color: #0284c7; }
QComboBox, QLineEdit { 
                background-color: #ffffff; 
                color: #0f172a; 
                border: 1px solid #475569; 
                padding: 6px; 
                border-radius: 4px; 
            }
        """)
        c1_layout = QVBoxLayout(c1)
        c1_layout.setContentsMargins(12, 12, 12, 12)
        
        c1_layout.addWidget(QLabel("Select Client tier profile standard markup matrix:"))
        self.team_box = QComboBox()
        self.team_box.addItems(["Construction Supply (50%)", "Lumber Yard (40%)", "Standard Retail"])
        c1_layout.addWidget(self.team_box)
        
        c1_layout.addWidget(QLabel("Select active inventory category group table:"))
        self.category_box = QComboBox()
        self.category_box.addItems(list(self.data_core.clean_database.keys()))
        self.category_box.currentIndexChanged.connect(self.handle_card_switch)
        c1_layout.addWidget(self.category_box)
        
        self.smart_lookup_input = QLineEdit()
        self.smart_lookup_input.setPlaceholderText("Type to filter model results instantly...")
        self.smart_lookup_input.textChanged.connect(self.handle_smart_lookup_filter)
        
        self.model_box = QComboBox()
        self.model_box.currentIndexChanged.connect(self.handle_model_switch_visual_update)
        
        c1_layout.addWidget(QLabel("Smart Lookup Model Selection Terminal:"))
        c1_layout.addWidget(self.smart_lookup_input)
        c1_layout.addWidget(self.model_box)
        scroll_layout.addWidget(c1)

        c2 = QWidget()
        c2.setAttribute(Qt.WA_StyledBackground, True)
        c2.setStyleSheet("""
            QWidget { 
                background-color: rgba(248, 250, 252, 0.78); 
                border: 1px solid #cbd5e1; 
                border-radius: 8px; 
            }
            QLabel { color: #0f172a; font-weight: 600; background: transparent; border: none; }
            QLineEdit { 
                background-color: #ffffff; 
                color: #0f172a; 
                border: 1px solid #475569; 
                padding: 6px; 
                border-radius: 4px; 
            }
        """)
        self.c2_layout = QVBoxLayout(c2)
        self.c2_layout.setContentsMargins(12, 12, 12, 12)
        
        self.lbl_manual_1 = QLabel("Input Variable 1:")
        self.entry_manual_1 = QLineEdit()
        self.var1_widget = QWidget()
        self.var1_widget.setStyleSheet("background: transparent; border: none;")
        v1_lay = QHBoxLayout(self.var1_widget)
        v1_lay.setContentsMargins(0, 0, 0, 0)
        v1_lay.addWidget(self.lbl_manual_1, 2)
        v1_lay.addWidget(self.entry_manual_1, 3)
        self.c2_layout.addWidget(self.var1_widget)
        
        self.lbl_manual_2 = QLabel("Input Variable 2:")
        self.entry_manual_2 = QLineEdit()
        self.var2_widget = QWidget()
        self.var2_widget.setStyleSheet("background: transparent; border: none;")
        v2_lay = QHBoxLayout(self.var2_widget)
        v2_lay.setContentsMargins(0, 0, 0, 0)
        v2_lay.addWidget(self.lbl_manual_2, 2)
        v2_lay.addWidget(self.entry_manual_2, 3)
        self.c2_layout.addWidget(self.var2_widget)
        scroll_layout.addWidget(c2)

        c3 = QWidget()
        c3.setAttribute(Qt.WA_StyledBackground, True)
        c3.setStyleSheet("""
            QWidget { 
                background-color: rgba(248, 250, 252, 0.78); 
                border: 1px solid #cbd5e1; 
                border-radius: 8px; 
            }
            QLabel { color: #0f172a; font-weight: 600; background: transparent; border: none; }
            QCheckBox { color: #0f172a; font-weight: 600; background: transparent; border: none; }
        """)
        c3_layout = QVBoxLayout(c3)
        c3_layout.setContentsMargins(12, 12, 12, 12)
        
        c3_layout.addWidget(QLabel("Available Manufacturing Surcharges & Modifiers:"))
        self.surcharge_grid = QGridLayout()
        self.surcharge_grid.setSpacing(10)
        self.check_boxes = []
        for i in range(9):
            cb = QCheckBox("")
            cb.setVisible(False)
            self.surcharge_grid.addWidget(cb, i // 3, i % 3)
            self.check_boxes.append(cb)
        c3_layout.addLayout(self.surcharge_grid)
        scroll_layout.addWidget(c3)

        c4 = QWidget()
        c4.setAttribute(Qt.WA_StyledBackground, True)
        c4.setStyleSheet("""
            QWidget { 
                background-color: rgba(248, 250, 252, 0.78); 
                border: 1px solid #cbd5e1; 
                border-radius: 8px; 
            }
        """)
        c4_layout = QVBoxLayout(c4)
        c4_layout.setContentsMargins(12, 12, 12, 12)
        self.spec_label = QLabel("Configure parameters to compute calculation layout loop.")
        self.spec_label.setWordWrap(True)
        self.spec_label.setStyleSheet("color: #0f172a !important; font-family: 'Segoe UI', Arial, sans-serif; font-weight: 600; font-size: 12px; background: transparent; border: none;")
        c4_layout.addWidget(self.spec_label)
        scroll_layout.addWidget(c4)

        self.btn_compute = QPushButton("Compute & Add to Quote")
        self.btn_compute.setObjectName("PrimaryAction")
        self.btn_compute.setStyleSheet("QPushButton { background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 4px 12px; } QPushButton:hover { background-color: rgba(96, 165, 250, 0.82); color: #0f172a; }")
        self.btn_compute.setFixedHeight(32)
        self.btn_compute.clicked.connect(self.calculate_standalone_pricing)
        scroll_layout.addWidget(self.btn_compute)
        
        scroll_area.setWidget(container)
        self.main_layout.addWidget(scroll_area, 6)

    def refresh_live_category_titles(self):
        self.category_box.blockSignals(True)
        current_selection = self.category_box.currentText()
        self.data_core.load_and_sanitize_matrix()
        self.category_box.clear()
        self.category_box.addItems(list(self.data_core.clean_database.keys()))
        index = self.category_box.findText(current_selection)
        if index >= 0: self.category_box.setCurrentIndex(index)
        else: self.category_box.setCurrentIndex(0)
        self.category_box.blockSignals(False)
        self.handle_card_switch()

    def execute_silent_network_sync(self):
        try:
            self.data_core.load_and_sanitize_matrix()
            self.refresh_live_category_titles()
            self.custom_safeguards.update(self._load_custom_safeguards())
            self.custom_quoting_tab.safeguards = self.custom_safeguards
            self.custom_quoting_tab.sync_local_workbench_view()
            if len(self.custom_quoting_tab.current_project_items) == 1 and self.custom_quoting_tab.ledger_tree.topLevelItemCount() > 0:
                self.custom_quoting_tab.ledger_tree.setCurrentItem(self.custom_quoting_tab.ledger_tree.topLevelItem(0))
                self.custom_quoting_tab.edit_selected_project_item()
            self.handle_card_switch()
            if hasattr(self.custom_quoting_tab, "active_card") and hasattr(self.custom_quoting_tab.active_card, "populate_surcharges_by_shape"):
                self.custom_quoting_tab.active_card.populate_surcharges_by_shape(self.custom_quoting_tab.active_card.current_shape)
            self.custom_admin_tab.refresh_summary_text()
            quotes, seq = self._load_custom_ledger()
            self.custom_ledger_pool[:] = quotes
            self.custom_quote_seq = seq
            self.custom_ledger_tab.populate_ledger_grid()
            for watch_p in [self.data_core.database_file, self.custom_safeguards_file, self.custom_ledger_file]:
                if os.path.exists(watch_p) and watch_p not in self.file_monitor.files():
                    self.file_monitor.addPath(watch_p)
        except Exception:
            pass
# ==========================================
# SECTION 13 (PART A): RIGHT MONOSPACE readout PANEL
# ==========================================
    def setup_right_ledger_panel(self):
        right_container = QWidget()
        right_container.setAttribute(Qt.WA_StyledBackground, True)
        right_container.setStyleSheet("background: transparent !important;")
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        hdr_card = QWidget()
        hdr_card.setStyleSheet("background-color: rgba(248, 250, 252, 0.78); border: 1px solid #cbd5e1; border-radius: 8px;")
        hdr_layout = QHBoxLayout(hdr_card)
        hdr_layout.setContentsMargins(10, 6, 10, 6)
        self.lbl_std_header = QLabel("CATALOG: RETAIL CUSTOMER | STANDARD ORDER")
        self.lbl_std_header.setStyleSheet("font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; color: #0369a1; background: transparent; border: none;")
        hdr_layout.addWidget(self.lbl_std_header)
        hdr_layout.addStretch()

        self._std_expanded = True
        self.btn_std_toggle_expand = QPushButton("Collapse All")
        self.btn_std_toggle_expand.setStyleSheet("background-color: rgba(239, 246, 255, 0.72); border: 2px solid #0284c7; color: #000000; font-weight: 700; font-size: 13px; font-weight: 600; padding: 4px 10px; border-radius: 5px;")
        self.btn_std_toggle_expand.clicked.connect(self.toggle_all_std_tree_items)
        hdr_layout.addWidget(self.btn_std_toggle_expand)
        right_layout.addWidget(hdr_card)

        self.cat_fx_bar = FormulaHudBar(self)
        right_layout.addWidget(self.cat_fx_bar)
        self.std_ledger_tree = QTreeWidget()
        apply_excel_table_style(self.std_ledger_tree)
        self.std_ledger_tree.currentItemChanged.connect(
            lambda cur, prev: self.cat_fx_bar.set_formula(
                f"ROW {self.std_ledger_tree.indexOfTopLevelItem(cur) + 1}" if cur else "ACTIVE",
                f"{cur.text(0)}  |  Weight: {cur.text(1)}  |  Total: {cur.text(2)}" if cur else ""
            )
        )
        self.std_ledger_tree.setColumnCount(4)
        self.std_ledger_tree.setHeaderLabels(["PART / DESCRIPTION", "SHIP WEIGHT", "QUOTE COST", ""])
        self.std_ledger_tree.setRootIsDecorated(True)
        self.std_ledger_tree.setTextElideMode(Qt.ElideNone)
        self.std_ledger_tree.setSelectionMode(QAbstractItemView.NoSelection)
        self.std_ledger_tree.header().setStretchLastSection(False)
        self.std_ledger_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.std_ledger_tree.setColumnWidth(1, 115)
        self.std_ledger_tree.setColumnWidth(2, 105)
        self.std_ledger_tree.header().setSectionResizeMode(1, QHeaderView.Interactive)
        self.std_ledger_tree.header().setSectionResizeMode(2, QHeaderView.Interactive)
        self.std_ledger_tree.header().setSectionResizeMode(3, QHeaderView.Fixed)
        self.std_ledger_tree.setColumnWidth(3, 36)
        self.std_ledger_tree.setStyleSheet("""
            QTreeWidget { background-color: rgba(248, 250, 252, 0.78) !important; color: #0f172a !important; border: 1px solid #cbd5e1; border-radius: 8px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; padding: 4px; }
            QTreeWidget::viewport, QTreeWidget QWidget { background: transparent !important; }
            QTreeWidget::item { padding: 5px 3px; border-bottom: 1px solid #93c5fd; }
            QTreeWidget::item:selected, QTreeWidget::item:selected:!active { background-color: #93c5fd; color: #0f172a; }
            QHeaderView::section { background-color: rgba(207, 228, 250, 0.85); color: #0369a1; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; padding: 6px; border: none; border-bottom: 1px solid #334155; }
        """)
        right_layout.addWidget(self.std_ledger_tree, 1)

        t1_item_ops = QHBoxLayout()
        t1_item_ops.setSpacing(8)
        btn_t1_dup = QPushButton("Duplicate Selected Item")
        btn_t1_dup.setStyleSheet("background-color: rgba(2, 132, 199, 0.20); border: 1px solid #38bdf8; color: #0f172a; font-weight: 600; border-radius: 6px; padding: 6px;")
        btn_t1_dup.clicked.connect(self.duplicate_selected_standard_item)
        btn_t1_edit = QPushButton("Edit Selected Item")
        btn_t1_edit.setStyleSheet("background-color: rgba(245, 158, 11, 0.20); border: 1px solid #fbbf24; color: #0f172a; font-weight: 600; border-radius: 6px; padding: 6px;")
        btn_t1_edit.clicked.connect(self.edit_selected_standard_item)
        t1_item_ops.addWidget(btn_t1_dup, 1)
        t1_item_ops.addWidget(btn_t1_edit, 1)
        right_layout.addLayout(t1_item_ops)

        totals_card = QWidget()
        totals_card.setStyleSheet("background-color: #ffffff; border: 1.5px solid #94a3b8; border-radius: 6px;")
        t_grid = QGridLayout(totals_card)
        t_grid.setContentsMargins(12, 8, 12, 8)
        t_grid.setVerticalSpacing(3)

        m_lbl = "font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; color: #1e3a8a; background: transparent; border: none;"
        m_val = "font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; color: #0f172a; background: transparent; border: none;"
        g_lbl = "font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; color: #0369a1; background: transparent; border: none;"

        self.lbl_std_wgt = QLabel("0.0 lbs")
        self.lbl_std_base = QLabel("$0.00")
        self.lbl_std_addons = QLabel("$0.00")
        self.lbl_std_sub = QLabel("$0.00")
        self.lbl_std_tier = QLabel("CLIENT TIER (50%):")
        self.lbl_std_tier_val = QLabel("+$0.00")
        self.lbl_std_grand = QLabel("$0.00")

        for r_i, (t_txt, v_w, lc, vc) in enumerate([
            ("ACTUAL SHIP WEIGHT:", self.lbl_std_wgt, m_lbl, m_val),
            ("BASE CATALOG ITEMS:", self.lbl_std_base, m_lbl, m_val),
            ("ADD-ONS & COATINGS:", self.lbl_std_addons, m_lbl, m_val),
            ("COMBINED SUBTOTAL:", self.lbl_std_sub, m_lbl, m_val),
            (None, self.lbl_std_tier_val, m_lbl, m_val),
            ("TOTAL CUSTOMER QUOTE:", self.lbl_std_grand, g_lbl, g_lbl),
        ]):
            lw = self.lbl_std_tier if t_txt is None else QLabel(t_txt)
            lw.setStyleSheet(lc)
            v_w.setStyleSheet(vc)
            v_w.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            t_grid.addWidget(lw, r_i, 0)
            t_grid.addWidget(v_w, r_i, 1)
        s_nh = QHBoxLayout()
        s_lbl = QLabel("ESTIMATOR NOTES & CUSTOMER SCOPE (Saved to Ledger & Customer PDF):")
        s_lbl.setStyleSheet("color: #0369a1; font-size: 12px; font-weight: 700; background: transparent; border: none;")
        s_nh.addWidget(s_lbl); s_nh.addStretch()
        btn_s_clause = QPushButton("+ Insert Standard Scope Clause")
        btn_s_clause.setStyleSheet("background-color: rgba(239, 246, 255, 0.85); border: 1px solid #60a5fa; color: #0f172a; font-size: 12px; font-weight: 700; border-radius: 4px; padding: 2px 8px;")
        btn_s_clause.clicked.connect(lambda: self.std_estimator_notes.setPlainText((self.std_estimator_notes.toPlainText().strip() + "\nFurnished FOB Frederickson, WA. Standard catalog hardware lead time 3-5 business days.").strip()))
        s_nh.addWidget(btn_s_clause)
        right_layout.addLayout(s_nh)

        self.std_estimator_notes = QTextEdit()
        self.std_estimator_notes.setPlaceholderText("Click here to add customer scope notes, finish specs, or delivery notes before finalizing...")
        self.std_estimator_notes.setMaximumHeight(58)
        self.std_estimator_notes.setStyleSheet("QTextEdit { background-color: rgba(239, 246, 255, 0.82); color: #0f172a; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px 8px; font-size: 14px; font-weight: 600; }")
        right_layout.addWidget(self.std_estimator_notes)
        right_layout.addWidget(totals_card)

        blue_g = 'background-color: #ffffff; border: 1.5px solid #0284c7; color: #0284c7; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 4px 12px;'
        red_g = 'background-color: #ffffff; border: 1px solid #fca5a5; color: #b91c1c; font-weight: 700; font-weight: 600; border-radius: 6px; padding: 8px;'

        self.btn_finalize_std = QPushButton("FINALIZE & SAVE TO RUNNING PROJECT LEDGER")
        self.btn_finalize_std.setObjectName("PrimaryAction")
        self.btn_finalize_std.setStyleSheet(blue_g)
        self.btn_finalize_std.setMinimumHeight(42)
        self.btn_finalize_std.clicked.connect(self.finalize_standard_catalog_to_ledger)
        right_layout.addWidget(self.btn_finalize_std)

        self.btn_reset = QPushButton("Clear Active Session")
        self.btn_reset.setObjectName("DangerAction")
        self.btn_reset.setStyleSheet(red_g)
        self.btn_reset.clicked.connect(self.clear_rfq_ledger_session)
        right_layout.addWidget(self.btn_reset)
        self.main_layout.addWidget(right_container, 5)

    def handle_card_switch(self):
        card = self.category_box.currentText()
        if not card or card not in self.data_core.clean_database: return
        self.current_card_models = list(self.data_core.clean_database[card].keys())
        
        # FIXED: Added [0] to extract the first single string element out of the list
        first_m = self.current_card_models[0] if self.current_card_models else None
        s_id = self.data_core.clean_database[card][first_m]["schema_id"] if first_m else "CARD_1"
        config = CARDS_SCHEMA_MATRIX[s_id]
        
        self.smart_lookup_input.blockSignals(True)
        self.smart_lookup_input.clear()
        self.smart_lookup_input.blockSignals(False)
        self.populate_model_box(self.current_card_models)
        self.var1_widget.setVisible(config["mode"] in ["height_input", "qty_input", "double_height", "fixed_standard_cost"])
        self.var2_widget.setVisible(config["mode"] == "double_height")
        if config["mode"] == "height_input":
            self.lbl_manual_1.setText(config["manual_label"])
            self.entry_manual_1.setText("8.0")
        elif config["mode"] in ["qty_input", "fixed_standard_cost"]:
            self.lbl_manual_1.setText(config["manual_label"])
            self.entry_manual_1.setText("1")
        elif config["mode"] == "double_height":
            self.lbl_manual_1.setText("Valley Height:")
            self.entry_manual_1.setText("5.50")
            self.lbl_manual_2.setText("Ridge Height:")
            self.entry_manual_2.setText("5.50")
        for i, cb in enumerate(self.check_boxes):
            if i < len(config.get("surcharges_labels", [])):
                cb.setText(config["surcharges_labels"][i])
                cb.setChecked(False)
                cb.setVisible(True)
            else: cb.setVisible(False)

        custom_t1_fees = [e for e in self.custom_safeguards.get("custom_extra_fees", []) if e.get("category") == "Tab 1 Catalog Flat Fees"]
        for cb in self.check_boxes:
            if getattr(cb, "_is_custom_admin_cb", False):
                cb.setVisible(False)
                cb.setChecked(False)
                cb._is_custom_admin_cb = False
        for cf, cb in zip(custom_t1_fees, [c for c in self.check_boxes if not c.isVisible()]):
            cb.setText(f"{cf['label']} (${float(cf['value']):,.2f})")
            cb._is_custom_admin_cb = True
            cb._custom_fee_val = float(cf["value"])
            cb.setChecked(False)
            cb.setVisible(True)
        self.calculate_standalone_pricing()

    def handle_model_switch_visual_update(self):
        card = self.category_box.currentText()
        model = self.model_box.currentText()
        if not card or not model or model == "No matched variants found" or card not in self.data_core.clean_database: return
        c_data = self.data_core.clean_database.get(card, {}).get(model, None)
        if not c_data: return
        
        row_min_ht = c_data.get("min_ht", 0.0)
        models_list = list(self.data_core.clean_database[card].keys())
        first_m = models_list[0] if models_list else None
        s_id = self.data_core.clean_database[card][first_m]["schema_id"] if first_m else "CARD_1"
        mode = CARDS_SCHEMA_MATRIX[s_id]["mode"]

        if mode == "height_input": 
            self.entry_manual_1.setText(f"{row_min_ht:.2f}")
        elif mode == "double_height":
            # Automatically detect baseline variables based on catalog series rules
            default_ht = 9.5 if "MSC 5" in model else (7.5 if "MSC 4" in model else 5.5)
            self.entry_manual_1.setText(f"{default_ht:.2f}") 
            self.entry_manual_2.setText(f"{default_ht:.2f}")

    def handle_smart_lookup_filter(self, filter_text):
        if not hasattr(self, 'current_card_models'): return
        query = filter_text.strip().upper()
        filtered = [m for m in self.current_card_models if query in m.upper()] if query else self.current_card_models
        self.populate_model_box(filtered)

    def populate_model_box(self, items_list):
        self.model_box.blockSignals(True)
        self.model_box.clear()
        if items_list:
            self.model_box.addItem("Select a model...")
            self.model_box.addItems(items_list)
            self.model_box.setCurrentIndex(0)
        else:
            self.model_box.addItem("No matched variants found")
        self.model_box.blockSignals(False)

# ==========================================
# SECTION 13 (PART B): PIPELINE CALCULATION & EXECUTION LOOP
# ==========================================
    def calculate_standalone_pricing(self):
        card = self.category_box.currentText()
        model = self.model_box.currentText()
        if model in ("Select a model...", "No matched variants found") or not model or card not in self.data_core.clean_database:
            if hasattr(self, "spec_label"):
                self.spec_label.setText(
                    "Quoting Terminal Breakout:\n"
                    "-> Part Model Base: N/A\n"
                    "-> Configured Height: N/A\n"
                    "-> Shipping Weight: 0.0 lbs\n"
                    "-> Baseline Item Cost: $0.00\n"
                    "-> Active Surcharges: None\n"
                    "-> Add-ons Premium Total: $0.00\n\n"
                    "FINAL CALCULATED RATE: $0.00"
                )
            return
        
        c_data = self.data_core.clean_database.get(card, {}).get(model, None)
        if not c_data: return
        s_id = c_data["schema_id"]
        config = CARDS_SCHEMA_MATRIX[s_id]
        raw_p = self.team_box.currentText()
        mult = PricingCalculatorCore.get_profile_multiplier(raw_p, self.custom_safeguards)
        
        try:
            def scrub(v):
                cl = "".join(c for c in str(v) if c in (".", "-") or c.isdigit())
                return float(cl) if cl else 0.0
            wgt = scrub(c_data["lbs"])
            checks = {cb.text(): cb.isChecked() for cb in self.check_boxes if cb.isVisible()}
            v1 = scrub(self.entry_manual_1.text())
            row_min_ht = c_data.get("min_ht", 0.0)
            
            # --- CALCULATE INTERMEDIATE RAW BASELINE PRICING ---
            no_checks = {k: False for k in checks}
            if s_id in ["CARD_5", "CARD_6"]:
                base_raw, _ = PricingCalculatorCore.calc_card5_6(scrub(c_data["cost"]), wgt, mult, no_checks, v1, row_min_ht, config["surcharges_labels"], self.custom_safeguards)
                base_raw *= 1.05
            elif config["mode"] == "standard":
                base_raw = PricingCalculatorCore.calc_card1(scrub(c_data["cost"]), wgt, mult, no_checks, self.custom_safeguards) * float(self.custom_safeguards.get("cat_base_margin", 1.05))
            elif config["mode"] == "height_input":
                r_p, _ = PricingCalculatorCore.calc_standard_height(scrub(c_data["cost"]), wgt, mult, no_checks, v1, row_min_ht, config["surcharges_labels"], cfg=self.custom_safeguards)
                base_raw = r_p * float(self.custom_safeguards.get("cat_base_margin", 1.05))
            elif config["mode"] == "qty_input":
                _, base_raw = PricingCalculatorCore.calc_card7_tiered(c_data, mult, no_checks, int(max(1.0, v1)))
            elif config["mode"] == "fixed_standard_cost":
                base_raw = (scrub(c_data["cost"]) * mult) * int(max(1.0, v1)) * float(self.custom_safeguards.get("cat_base_margin", 1.05))
            else:
                v2 = scrub(self.entry_manual_2.text())
                r_p, _ = PricingCalculatorCore.calc_card8(scrub(c_data["cost"]), wgt, mult, model, no_checks, v1, v2, self.custom_safeguards)
                base_raw = r_p * float(self.custom_safeguards.get("cat_base_margin", 1.05))

            # --- CALCULATE TRUE PREMIUM PRICING MATRIX ---
            if s_id in ["CARD_5", "CARD_6"]:
                f_price, calculated_wgt = PricingCalculatorCore.calc_card5_6(scrub(c_data["cost"]), wgt, mult, checks, v1, row_min_ht, config["surcharges_labels"], self.custom_safeguards)
                f_price *= 1.05
                wgt = calculated_wgt
            elif config["mode"] == "standard":
                f_price = PricingCalculatorCore.calc_card1(scrub(c_data["cost"]), wgt, mult, checks, self.custom_safeguards) * float(self.custom_safeguards.get("cat_base_margin", 1.05))
            elif config["mode"] == "height_input":
                raw_f_price, calculated_wgt = PricingCalculatorCore.calc_standard_height(scrub(c_data["cost"]), wgt, mult, checks, v1, row_min_ht, config["surcharges_labels"], cfg=self.custom_safeguards)
                f_price = raw_f_price * float(self.custom_safeguards.get("cat_base_margin", 1.05))
                wgt = calculated_wgt 
            # ... (inside calculate_standalone_pricing where f_price is determined) ...
            elif config["mode"] == "qty_input":
                rate, total = PricingCalculatorCore.calc_card7_tiered(c_data, mult, checks, int(max(1.0, v1)))
                f_price = total
                wgt = wgt * int(max(1.0, v1))
            elif config["mode"] == "fixed_standard_cost":
                base_rate = scrub(c_data["cost"])
                if checks.get("Mod CHRG $15 (K22)"): base_rate += float(self.custom_safeguards.get("c7_mod_chrg_fee", 15.00))
                base_rate *= mult
                if checks.get("Rush (J22)"): base_rate *= float(self.custom_safeguards.get("rush_multiplier", 1.25))
                f_price = base_rate * int(max(1.0, v1)) * float(self.custom_safeguards.get("cat_base_margin", 1.05))
                wgt = wgt * int(max(1.0, v1))
            else:
                v2 = scrub(self.entry_manual_2.text())
                # FIXED: Intercept both the final price AND the double-saddle calculated weight output
                raw_f_price, calculated_wgt = PricingCalculatorCore.calc_card8(scrub(c_data["cost"]), wgt, mult, model, checks, v1, v2, self.custom_safeguards)
                f_price = raw_f_price * float(self.custom_safeguards.get("cat_base_margin", 1.05))
                wgt = calculated_wgt # Updates the display token variables perfectly

            # === START OF CODE REPLACEMENT AT THE BOTTOM OF THE FUNCTION ===
                cat_margin = float(self.custom_safeguards.get("cat_base_margin", 1.05))
            for cb in self.check_boxes:
                if getattr(cb, "_is_custom_admin_cb", False) and cb.isVisible() and cb.isChecked():
                    f_price += (float(getattr(cb, "_custom_fee_val", 0.0)) * mult * cat_margin)
            surcharge_delta = max(0.0, f_price - base_raw)
            
            # FIXED: Correctly strips the first string segment [0] out of the split list layout
            active_addons = [name.split("(")[0].strip() for name, checked in checks.items() if checked]
            addon_list_str = ", ".join(active_addons) if active_addons else "None"

            # 1. Format the height variable tracking string cleanly for the breakout view
            if config["mode"] == "height_input":
                breakout_height_str = f" H {v1:.2f}\""
            elif config["mode"] == "double_height":
                v2 = scrub(self.entry_manual_2.text())
                breakout_height_str = f" {v1:.2f}\"V / {v2:.2f}\"R"
            else:
                breakout_height_str = " N/A"

            # 2. Update the live breakout terminal window text
            unit_price_line = ""
            if config["mode"] in ["qty_input", "fixed_standard_cost"]:
                order_qty_int = int(max(1.0, v1))
                per_unit_cost = f_price / order_qty_int
                unit_price_line = f"  -> Cost Per Plate Washer / Unit ({order_qty_int} qty): ${per_unit_cost:.2f} ea\n"

            unit_html = unit_price_line.replace("\n", "<br>") if unit_price_line else ""
            if active_addons:
                bullets_html = "<br>" + "<br>".join(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span style='color:#0369a1;'>- {a[0] if isinstance(a, tuple) else str(a)}</span>" for a in active_addons)
            else:
                bullets_html = " None"
            res = (
                f"Quoting Terminal Breakout:<br>"
                f"  -> Part Model Base: {model}<br>"
                f"  -> Configured Height:{breakout_height_str}<br>"
                f"  -> Shipping Weight: {wgt:.1f} lbs<br>"
                f"  -> Baseline Item Cost: ${base_raw:.2f}<br>"
                f"  -> Active Surcharges:{bullets_html}<br>"
                f"  -> Add-ons Premium Total: ${surcharge_delta:.2f}<br>"
                f"{unit_html}"
                f"------------------------------------<br>"
                f"FINAL CALCULATED RATE: ${f_price:.2f}"
            )
            self.spec_label.setText(res)
            if hasattr(self, 'lbl_fx_formula'):
                self.lbl_fx_formula.setText(f"CATALOG FORMULA: Base (${base_raw:,.2f}) + Add-ons (${surcharge_delta:,.2f})  =  Final Rate ${f_price:,.2f}  [{wgt:.1f} lbs]")
            
            # 3. Format the model description text layout for the ledger side
            if config["mode"] == "height_input":
                extended_model_label = f"{model} H {v1:.2f}\""
            elif config["mode"] == "double_height":
                extended_model_label = f"{model} {v1:.2f}\"V / {v2:.2f}\"R"
            elif config["mode"] in ["qty_input", "fixed_standard_cost"]:
                extended_model_label = f"{model} (x{int(v1)})"
            else:
                extended_model_label = model

            # 4. Write data to history log dictionary list array
            addon_breakdown_list = [f"Base Catalog Item: ${base_raw:,.2f}"]
            if active_addons:
                for add_tup in active_addons:
                    lbl_a = str(add_tup)
                    d_amt = float(add_tup) if len(add_tup) > 2 and isinstance(add_tup, (int, float)) else (surcharge_delta / len(active_addons))
                    addon_breakdown_list.append(f"{lbl_a}: +${d_amt:,.2f}")
            else:
                addon_breakdown_list.append("Standard Stock (No Add-ons)")

            self.data_core.rfq_ledger_items.append({
                "model": f"{model} (x{int(v1) if config['mode']=='qty_input' else 1})",
                "weight": f"{wgt:.1f} lbs",
                "cost": f"${f_price:.2f}",
                "addons": addon_list_str,
                "base_cost": float(base_raw),
                "list_cost": float(round(f_price / (float("".join(c for c in self.team_box.currentText().partition("(")[-1] if c.isdigit()) or 100) / 100.0), 2)),
                "addon_cost": float(surcharge_delta),
                "addon_lines": addon_breakdown_list
            })
            self.update_rfq_ledger_view()

            # --- PASTE THE CHECKBOX CLEANUP LOOP HERE ---
            for cb in self.check_boxes:
                if cb.isVisible():
                    cb.blockSignals(True)
                    cb.setChecked(False)
                    cb.blockSignals(False)

        except Exception as e: self.spec_label.setText(f"âŒ Calculation Error: {e}")
        # === END OF FUNCTION ===

    def toggle_all_std_tree_items(self):
        self._std_expanded = not self._std_expanded
        for i in range(self.std_ledger_tree.topLevelItemCount()):
            self.std_ledger_tree.topLevelItem(i).setExpanded(self._std_expanded)
        self.btn_std_toggle_expand.setText("Collapse All" if self._std_expanded else "Expand All")

    def remove_std_ledger_item(self, idx):
        if 0 <= idx < len(self.data_core.rfq_ledger_items):
            self.data_core.rfq_ledger_items.pop(idx)
            self.update_rfq_ledger_view()

    def duplicate_selected_standard_item(self):
        cur = self.std_ledger_tree.currentItem()
        if not cur:
            QMessageBox.warning(self, "No Item Selected", "Click an item row in the active session first.")
            return
        top = cur.parent() if cur.parent() else cur
        idx = self.std_ledger_tree.indexOfTopLevelItem(top)
        if 0 <= idx < len(self.data_core.rfq_ledger_items):
            import copy
            self.data_core.rfq_ledger_items.append(copy.deepcopy(self.data_core.rfq_ledger_items[idx]))
            self.update_rfq_ledger_view()

    def edit_selected_standard_item(self):
        cur = self.std_ledger_tree.currentItem()
        if not cur:
            QMessageBox.warning(self, "No Item Selected", "Click an item row in the active session first.")
            return
        top = cur.parent() if cur.parent() else cur
        idx = self.std_ledger_tree.indexOfTopLevelItem(top)
        if 0 <= idx < len(self.data_core.rfq_ledger_items):
            it = self.data_core.rfq_ledger_items.pop(idx)
            raw_lbl = str(it.get("model", "")).strip()
            base_model = raw_lbl.split(" (x")[0].strip()
            qty_str = "1"
            if " (x" in raw_lbl:
                qty_str = raw_lbl.split(" (x", 1)[1].rstrip(")").strip() or "1"

            # Find matching category card & model on the left builder panel
            found_cat = None
            for cat_name, cat_obj in self.data_core.clean_database.items():
                if base_model in cat_obj.get("models", {}):
                    found_cat = cat_name
                    break
            if found_cat and hasattr(self, "category_box"):
                c_idx = self.category_box.findText(found_cat)
                if c_idx >= 0:
                    self.category_box.setCurrentIndex(c_idx)
                    self.handle_card_switch()
            if hasattr(self, "model_box"):
                m_idx = self.model_box.findText(base_model)
                if m_idx >= 0:
                    self.model_box.setCurrentIndex(m_idx)
            if hasattr(self, "entry_manual_1"):
                self.entry_manual_1.setText(qty_str)
                self.entry_manual_1.setFocus()
                self.entry_manual_1.selectAll()

            # Restore any checked modifiers from addon_lines
            addon_blob = " | ".join(str(x) for x in it.get("addon_lines", []))
            for cb in getattr(self, "check_boxes", []):
                if cb.isVisible() and cb.text():
                    cb.setChecked(cb.text().lower() in addon_blob.lower())

            self.update_rfq_ledger_view()

    def _delete_highlighted_t1_item(self):
        cur = self.std_ledger_tree.currentItem()
        if not cur:
            return
        top = cur.parent() if cur.parent() else cur
        idx = self.std_ledger_tree.indexOfTopLevelItem(top)
        if 0 <= idx < len(self.data_core.rfq_ledger_items):
            self.data_core.rfq_ledger_items.pop(idx)
            self.update_rfq_ledger_view()

    def update_rfq_ledger_view(self):
        c_name = self.std_cust_input.text().strip() if hasattr(self, "std_cust_input") and self.std_cust_input.text().strip() else "Retail Customer"
        p_name = self.std_proj_input.text().strip() if hasattr(self, "std_proj_input") and self.std_proj_input.text().strip() else "Standard Order"
        tier_full = self.team_box.currentText() if hasattr(self, "team_box") else "Standard"

        self.lbl_std_header.setText(f"CATALOG: {c_name.upper()} | {p_name.upper()}")
        self.lbl_std_tier.setText(f"TIER: {tier_full.upper()}")

        self.std_ledger_tree.clear()
        tot_cost, tot_wgt = 0.0, 0.0
        if not self.data_core.rfq_ledger_items:
            ph = QTreeWidgetItem(self.std_ledger_tree)
            ph.setText(0, "No items queued - select a model to begin")
            ph.setText(1, "?")
            ph.setText(2, "$0.00")
            ph.setForeground(0, QColor("#334155"))
            ph.setForeground(1, QColor("#334155"))
            ph.setForeground(2, QColor("#334155"))
        for idx, item in enumerate(self.data_core.rfq_ledger_items):
            w_val = float(str(item['weight']).lower().replace("lbs", "").strip() or 0.0)
            c_val = float(str(item['cost']).replace("$", "").replace(",", "").strip() or 0.0)

            parent = QTreeWidgetItem(self.std_ledger_tree)
            parent.setText(0, item["model"])
            parent.setText(1, f"{w_val:.1f} lbs")
            parent.setText(2, f"${c_val:,.2f}")
            parent.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
            parent.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)

            fb = parent.font(0)
            fb.setBold(True)
            for c in range(3):
                parent.setFont(c, fb)

            btn_del = QPushButton("X")
            btn_del.setFixedSize(24, 22)
            btn_del.setStyleSheet("background-color: rgba(220, 38, 38, 0.25); border: 1px solid #f87171; color: #fca5a5; font-weight: 600; border-radius: 4px; padding: 0px;")
            btn_del.clicked.connect(lambda checked=False, i=idx: self.remove_std_ledger_item(i))
            self.std_ledger_tree.setItemWidget(parent, 3, btn_del)

            a_lines = item.get("addon_lines", [])
            if a_lines:
                for line_txt in a_lines:
                    ca = QTreeWidgetItem(parent)
                    ca.setFirstColumnSpanned(True)
                    ca.setText(0, f"- {line_txt}")
                    ca.setForeground(0, QColor("#0369a1") if "+$" in line_txt else QColor("#1e3a8a"))
            else:
                addons_s = item.get("addons", "None")
                if addons_s and addons_s != "None":
                    for tok in addons_s.split(","):
                        if tok.strip():
                            ca = QTreeWidgetItem(parent)
                            ca.setFirstColumnSpanned(True)
                            ca.setText(0, f"- {tok.strip()}")
                            ca.setForeground(0, QColor("#0369a1"))
                else:
                    cs = QTreeWidgetItem(parent)
                    cs.setFirstColumnSpanned(True)
                    cs.setText(0, "- Standard Catalog Spec")
                    cs.setForeground(0, QColor("#1e3a8a"))

            parent.setExpanded(self._std_expanded)
            tot_wgt += w_val
            tot_cost += c_val

        tier_pct_str = "(" + tier_full.partition("(")[-1] if "(" in tier_full else "(50%)"
        tot_base = sum(float(i.get('base_cost', str(i['cost']).replace('$','').replace(',',''))) for i in self.data_core.rfq_ledger_items)
        tot_add = sum(float(i.get('addon_cost', 0.0)) for i in self.data_core.rfq_ledger_items)
        tot_list = sum(float(i.get('list_cost', str(i['cost']).replace('$','').replace(',',''))) for i in self.data_core.rfq_ledger_items)
        raw_sub = round(tot_base + tot_add, 2)
        tier_delta = round(tot_cost - tot_list, 2)
        if tier_delta < -0.005:
            self.lbl_std_tier.setText(f"CLIENT TIER SAVINGS {tier_pct_str}:")
            self.lbl_std_tier_val.setText(f"-${abs(tier_delta):,.2f}")
        else:
            self.lbl_std_tier.setText(f"CLIENT TIER {tier_pct_str}:")
            self.lbl_std_tier_val.setText(f"+${abs(tier_delta):,.2f}")
        self.lbl_std_wgt.setText(f"{tot_wgt:.1f} lbs")
        self.lbl_std_base.setText(f"${tot_base:,.2f}")
        self.lbl_std_addons.setText(f"${tot_add:,.2f}")
        self.lbl_std_sub.setText(f"${raw_sub:,.2f}")
        self.lbl_std_grand.setText(f"${tot_cost:,.2f}")

    def finalize_standard_catalog_to_ledger(self):
        if not self.data_core.rfq_ledger_items:
            QMessageBox.warning(self, "Empty Session", "Add at least one standard catalog item before finalizing.")
            return

        cust_name = self.std_cust_input.text().strip() if self.std_cust_input.text().strip() else "Retail Customer"
        proj_name = self.std_proj_input.text().strip() if self.std_proj_input.text().strip() else "Standard Catalog Order"
        tier_label = self.team_box.currentText()
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        tot_wgt = sum(float(str(i["weight"]).lower().replace("lbs", "").strip() or 0.0) for i in self.data_core.rfq_ledger_items)
        tot_cost = sum(float(str(i["cost"]).replace("$", "").replace(",", "").strip() or 0.0) for i in self.data_core.rfq_ledger_items)
        tot_base = sum(float(i.get("base_cost", str(i["cost"]).replace("$", "").replace(",", ""))) for i in self.data_core.rfq_ledger_items)
        tot_add = sum(float(i.get("addon_cost", 0.0)) for i in self.data_core.rfq_ledger_items)
        tot_list = sum(float(i.get("list_cost", str(i["cost"]).replace("$", "").replace(",", ""))) for i in self.data_core.rfq_ledger_items)

        quote_num = f"BM-2026-{self.custom_quote_seq}"
        self.custom_quote_seq += 1

        lines = [
            f"ITEMIZED MANIFEST ({quote_num})",
            f"? Customer: {cust_name}",
            f"? Project: {proj_name}",
            f"? Date: {ts}",
            f"Client Tier Matrix: {tier_label}",
            "-" * 50
        ]
        cust_lines = []
        catalog_items_saved = []
        for idx, it in enumerate(self.data_core.rfq_ledger_items, 1):
            w_v = float(str(it["weight"]).lower().replace("lbs", "").strip() or 0.0)
            c_v = float(str(it["cost"]).replace("$", "").replace(",", "").strip() or 0.0)
            b_v = float(it.get("base_cost", c_v))
            a_lines = it.get("addon_lines", [f"Base Catalog Item: ${b_v:,.2f}"])
            lines.append(f"Item #{idx}: {it['model']} (Ship Wgt: {w_v:.1f} lbs | Price: ${c_v:,.2f}) [Addons: {it.get('addons', 'None')}]")
            cust_lines.append({"desc": it["model"], "specs": it.get("addons", "Standard Stock"), "weight": w_v, "price": c_v})
            catalog_items_saved.append({"model": it["model"], "weight": w_v, "cost": c_v, "addon_lines": a_lines})

        lines.append("-" * 50)
        lines.append(f"Base Catalog Items: ${tot_base:,.2f}  |  Add-ons & Coatings: ${tot_add:,.2f}")
        lines.append(f"TOTAL PROJECT WEIGHT: {tot_wgt:.1f} lbs  |  GRAND PROJECT VALUE: ${tot_cost:,.2f}")

        edit_q1 = getattr(self, "_editing_quote_num", None)
        if edit_q1:
            self.custom_ledger_pool[:] = [r for r in self.custom_ledger_pool if r.get("quote_num") != edit_q1]
            quote_num = edit_q1
            self._editing_quote_num = None
        self.custom_ledger_pool.append({
            "quote_type": "catalog",
            "quote_num": quote_num,
            "timestamp": ts,
            "customer": cust_name,
            "project": proj_name,
            "tier_label": tier_label,
            "weight": round(tot_wgt, 1),
            "base_total": round(tot_base, 2),
            "addon_total": round(tot_add, 2),
            "list_total": round(tot_list, 2),
            "cost": round(tot_cost, 2),
            "summary": "\n".join(lines),
            "customer_lines": cust_lines,
            "catalog_items": catalog_items_saved
        })
        self._save_custom_ledger()
        self.custom_ledger_tab.populate_ledger_grid()

        if self.data_core.rfq_ledger_items and QMessageBox.question(self, 'Confirm Clear Session', f'Clear all {len(self.data_core.rfq_ledger_items)} item(s) from the active catalog session?', QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self.data_core.rfq_ledger_items.clear()
        self.update_rfq_ledger_view()
        QMessageBox.information(self, "Saved to Running Project Ledger", f"Standard Catalog Quote {quote_num} saved to Running Project Ledger!")

    def clear_rfq_ledger_session(self):
        self._editing_quote_num = None
        self.data_core.rfq_ledger_items = []
        self.std_cust_input.clear()
        self.std_proj_input.clear()
        for _qattr in ("qty_input", "input_qty", "std_qty_input"):
            if hasattr(self, _qattr): getattr(self, _qattr).setText("1")
        self.update_rfq_ledger_view()


    def _load_custom_safeguards(self):
        defaults = {
            "admin_passcode": "Barron", "base_labor_rate": 86.0, "eng_labor_rate": 175.0,
            "std_stud_rate": 5.00, "labor_markup": 1.40, "handling_mins_per_pc": 15.0, "primer_rate_per_lb": 0.12, "max_saw_beam_size": "W16",
            "max_drill_diameter": 1.125, "max_manual_punch_weight": 45.0,
            "turret_max_length": 48.0, "turret_max_width": 48.0,
            "carbon_shear_max_thickness": 0.50, "ss_shear_max_thickness": 0.375,
            "max_shear_length": 120.0, "max_press_brake_length": 120.0,
            "fillet_ipm": 6.0, "pjp_ipm": 2.0, "cjp_ipm": 0.1,
            "passes_3_16": 1, "passes_1_4": 1, "passes_5_16": 2, "passes_3_8": 2, "passes_1_2": 3,
            "saw_ipm": 0.8, "drill_spm": 2.0, "light_ppm": 4.0, "heavy_ppm": 0.5,
            "heavy_weight_cutoff": 40.0
        }
        if os.path.exists(self.custom_safeguards_file):
            try:
                with open(self.custom_safeguards_file, "r", encoding="utf-8") as f:
                    defaults.update(json.load(f))
            except Exception as e:
                print(f"Custom safeguards load warning: {e}")
        return defaults

    def _on_custom_safeguards_saved(self):
        self.custom_quoting_tab.safeguards = self.custom_safeguards
        self.custom_quoting_tab.sync_local_workbench_view()
        try:
            with open(self.custom_safeguards_file, "w", encoding="utf-8") as f:
                json.dump(self.custom_safeguards, f, indent=4)
            if os.path.exists(self.custom_safeguards_file) and self.custom_safeguards_file not in self.file_monitor.files():
                self.file_monitor.addPath(self.custom_safeguards_file)
        except Exception as e:
            print(f"Custom safeguards save warning: {e}")

    def _load_custom_ledger(self):
        if os.path.exists(self.custom_ledger_file):
            try:
                with open(self.custom_ledger_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("quotes", []), data.get("next_seq", 1001)
            except Exception as e:
                print(f"Custom ledger load warning: {e}")
        return [], 1001

    def _save_custom_ledger(self):
        try:
            payload = {"next_seq": self.custom_quote_seq, "quotes": self.custom_ledger_pool}
            with open(self.custom_ledger_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4)
            if os.path.exists(self.custom_ledger_file) and self.custom_ledger_file not in self.file_monitor.files():
                self.file_monitor.addPath(self.custom_ledger_file)
        except Exception as e:
            print(f"Custom ledger save warning: {e}")

    def reopen_quote_into_workspace(self, record):
        import re
        q_num = record.get("quote_num", "Quote")
        box = QMessageBox(self)
        box.setWindowTitle("Re-Open or Clone Quote")
        box.setIcon(QMessageBox.Question)
        box.setText(f"How would you like to load {q_num}?")
        box.setInformativeText("Re-Open Existing updates this exact quote number when finalized.\nClone as New creates a separate revision with a new quote number.")
        box.setStyleSheet("QMessageBox { min-width: 560px; } QPushButton { padding: 8px 18px; min-width: 145px; }")
        btn_edit = box.addButton(f"Re-Open Existing ({q_num})", QMessageBox.AcceptRole)
        btn_clone = box.addButton("Clone as New (Rev)", QMessageBox.ActionRole)
        btn_cancel = box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() == btn_cancel:
            return
        is_edit_existing = (box.clickedButton() == btn_edit)
        self._editing_quote_num = q_num if is_edit_existing else None
        if record.get("quote_type") == "catalog":
            self.std_cust_input.setText(record.get("customer", ""))
            base_p0 = re.sub(r"(\s*\(Rev\))+\s*$", "", str(record.get("project", "")), flags=re.IGNORECASE).strip()
            self.std_proj_input.setText(base_p0 if is_edit_existing else f"{base_p0} (Rev)")
            self.data_core.rfq_ledger_items.clear()
            for it in record.get("catalog_items", []):
                self.data_core.rfq_ledger_items.append({
                    "model": it.get("model", "Item"),
                    "weight": f"{float(it.get('weight', 0.0)):.1f} lbs",
                    "cost": f"${float(it.get('cost', 0.0)):,.2f}",
                    "base_cost": float(it.get("cost", 0.0)),
                    "addon_cost": 0.0,
                    "list_cost": float(it.get("cost", 0.0)),
                    "addons": ", ".join(it.get("addon_lines", [])),
                    "addon_lines": list(it.get("addon_lines", []))
                })
            self.update_rfq_ledger_view()
            self.master_tabs.setCurrentIndex(1)
            QMessageBox.information(self, "Quote Cloned", f"Loaded {q_num} into Standard Hangers Catalog for editing.")
        else:
            self.custom_quoting_tab.input_cust_name.setText(record.get("customer", ""))
            base_p = re.sub(r"(\s*\(Rev\))+\s*$", "", str(record.get("project", "")), flags=re.IGNORECASE).strip()
            self.custom_quoting_tab.input_proj_name.setText(base_p if is_edit_existing else f"{base_p} (Rev)")
            self.custom_quoting_tab.current_project_items.clear()
            markup_mult = float(self.custom_safeguards.get("labor_markup", 1.40)) or 1.40
            p_restored, d_restored = "0", "0"
            for cl in record.get("customer_lines", []):
                c_desc = str(cl.get("desc", ""))
                c_specs = str(cl.get("specs", ""))
                if "Programming & Shop Detailing" in c_desc or "CNC Programming" in c_desc:
                    mp = re.search(r"Programming\s*\(([0-9.]+)\s*hrs?\)", c_desc + " " + c_specs, re.IGNORECASE)
                    md = re.search(r"Detailing\s*\(([0-9.]+)\s*hrs?\)", c_desc + " " + c_specs, re.IGNORECASE)
                    if mp: p_restored = mp.group(1)
                    if md: d_restored = md.group(1)
                    continue
            if p_restored == "0" and d_restored == "0":
                sum_txt = str(record.get("summary", ""))
                mp2 = re.search(r"Programming\s*\(([0-9.]+)\s*hrs?\)", sum_txt, re.IGNORECASE)
                md2 = re.search(r"Detailing\s*\(([0-9.]+)\s*hrs?\)", sum_txt, re.IGNORECASE)
                if mp2: p_restored = mp2.group(1)
                if md2: d_restored = md2.group(1)
            if hasattr(self.custom_quoting_tab, "input_prog_hrs"):
                self.custom_quoting_tab.input_prog_hrs.setText(p_restored)
            if hasattr(self.custom_quoting_tab, "input_detail_hrs"):
                self.custom_quoting_tab.input_detail_hrs.setText(d_restored)
            for cl in record.get("customer_lines", []):
                if "Programming & Shop Detailing" in cl.get("desc", "") or "CNC Programming" in cl.get("desc", ""):
                    continue
                raw_c = round(float(cl.get("price", 0.0)) / markup_mult, 2)
                self.custom_quoting_tab.current_project_items.append({
                    "model": re.sub(r"\s*\[\$[0-9,]+\.\d{2}\s*ea\]", "", str(cl.get("desc", "Custom Member"))).strip(),
                    "weight": float(cl.get("weight", 0.0)),
                    "billable_weight": float(cl.get("weight", 0.0)),
                    "mat_cost": raw_c,
                    "labor_cost": 0.0,
                    "cost": raw_c,
                    "addons": cl.get("specs", "Standard Stock"),
                    "form_state": cl.get("form_state"),
                })
            self.custom_quoting_tab.sync_local_workbench_view()
            self.master_tabs.setCurrentIndex(2)
            QMessageBox.information(self, "Quote Cloned", f"Loaded {q_num} into Custom Structural Quoting for editing.")

    def _commit_custom_project(self, customer, project, total_weight, total_cost, summary_desc, customer_lines=None):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        edit_q = getattr(self, "_editing_quote_num", None)
        updated_existing = False
        if edit_q:
            for rec in self.custom_ledger_pool:
                if rec.get("quote_num") == edit_q:
                    rec.update({
                        "timestamp": timestamp, "customer": customer,
                        "project": project, "weight": total_weight, "cost": total_cost,
                        "summary": summary_desc, "customer_lines": customer_lines or []
                    })
                    updated_existing = True
                    break
            self._editing_quote_num = None
        if not updated_existing:
            quote_str = f"BM-2026-{self.custom_quote_seq}"
            self.custom_quote_seq += 1
            self.custom_ledger_pool.append({
                "quote_num": quote_str, "timestamp": timestamp, "customer": customer,
                "project": project, "weight": total_weight, "cost": total_cost,
                "summary": summary_desc, "customer_lines": customer_lines or []
            })
        self._save_custom_ledger()
        self.custom_ledger_tab.populate_ledger_grid()

    def nativeEvent(self, eventType, message):
        if os.name == "nt" and eventType in (b"windows_generic_MSG", "windows_generic_MSG"):
            try:
                import ctypes
                from ctypes import wintypes
                msg = wintypes.MSG.from_address(int(message))

                if msg.message == 0x0084:  # WM_NCHITTEST
                    x = ctypes.c_short(msg.lParam & 0xFFFF).value
                    y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                    gpos = self.mapFromGlobal(QPoint(x, y))

                    rb = getattr(self, "master_ribbon", None)
                    btn_m = getattr(rb, "btn_max", None) if rb else None
                    if btn_m and btn_m.isVisible():
                        tl = btn_m.mapTo(self, QPoint(0, 0))
                        on_max = QRect(tl, btn_m.size()).contains(gpos)
                        if getattr(self, "_max_hovered", False) != on_max:
                            self._max_hovered = on_max
                            bg_m = "#c8c6c4" if on_max else "transparent"
                            btn_m.setStyleSheet(f"QPushButton {{ background-color: {bg_m} !important; border: none !important; border-radius: 0px; padding: 0px; }}")
                        if on_max:
                            return True, 9  # HTMAXBUTTON -> triggers Windows 11 Snap Layouts!
                elif msg.message in (0x00A1, 0x00A2) and msg.wParam == 9:  # WM_NCLBUTTONDOWN / UP on HTMAXBUTTON
                    rb = getattr(self, "master_ribbon", None)
                    if rb and hasattr(rb, "_toggle_max"):
                        rb._toggle_max()
                        return True, 0
            except Exception:
                pass
        return super().nativeEvent(eventType, message)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        w_px = self.width()
        rb = getattr(self, 'master_ribbon', None)
        if rb:
            is_max = self.isMaximized()
            if getattr(self, "_last_max_state", None) != is_max and hasattr(rb, 'btn_max'):
                self._last_max_state = is_max
                import ribbon_bar_widget as _rbw
                rb.btn_max.setIcon(_rbw._win_caption_icon('restore' if is_max else 'max', '#1f2937'))
            is_compact = (w_px < 1820)
            if getattr(self, "_last_compact_state", None) != is_compact and hasattr(rb, 'adapt_to_width'):
                self._last_compact_state = is_compact
                rb.adapt_to_width(w_px)
        for sp in (getattr(self, 't1_splitter', None), getattr(getattr(self, 'custom_quoting_tab', None), 't2_splitter', None)):
            if sp is not None and w_px > 400:
                try:
                    sp.setSizes([int(w_px * 0.50), int(w_px * 0.50)])
                except RuntimeError:
                    pass

if __name__ == "__main__":
    # Hardware D3D11 enabled for smooth frameless window drag
    import qdarktheme
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.RoundPreferFloor)
    app = QApplication(sys.argv)
    app.setEffectEnabled(Qt.UI_FadeTooltip, False)
    app.setEffectEnabled(Qt.UI_AnimateTooltip, False)
    from PySide6.QtGui import QPalette
    _pal = app.palette()
    _pal.setColor(QPalette.ToolTipBase, QColor("#eff6ff"))
    _pal.setColor(QPalette.ToolTipText, QColor("#0f172a"))
    app.setPalette(_pal)
    qdarktheme.setup_theme(theme="light", corner_shape="rounded", custom_colors={"primary": "#0284c7"})
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(app.styleSheet() + """
        QWidget {
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        #LeftScrollContainer QLabel, StructuralQuotingSandbox QLabel, HistoricalArchiveLedgerPage QLabel, AdminControlDashboardPage QLabel {
            font-size: 12px;
            font-weight: 600;
        }
        #LeftScrollContainer QLineEdit, #LeftScrollContainer QComboBox,
        StructuralQuotingSandbox QLineEdit, StructuralQuotingSandbox QComboBox, StructuralQuotingSandbox QTextEdit,
        HistoricalArchiveLedgerPage QLineEdit, AdminControlDashboardPage QLineEdit, AdminControlDashboardPage QComboBox {
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #cbd5e1;
            border-radius: 5px;
            padding: 5px 8px;
            font-size: 12px;
            font-weight: 600;
        }
        QPushButton {
            background-color: #ffffff;
            border: 1px solid #94a3b8;
            color: #0f172a;
            font-size: 13px;
            font-weight: 600;
            border-radius: 5px;
            padding: 6px 12px;
        }
        QPushButton:hover {
            background-color: #e2e8f0;
            border-color: #475569;
        }
        QPushButton#EmeraldAction, QPushButton#PrimaryAction {
            background-color: #ffffff !important; border: 1.5px solid #0284c7 !important; color: #0284c7 !important;
            font-weight: 600 !important;
        }
        QPushButton#EmeraldAction:hover, QPushButton#PrimaryAction:hover {
            background-color: #1d4ed8 !important;
        }
        QPushButton#DangerAction {
            background-color: #ffffff !important;
            border: 1px solid #fca5a5 !important;
            color: #b91c1c !important;
        }
        QPushButton#DangerAction:hover {
            background-color: #fef2f2 !important;
            border-color: #dc2626 !important;
        }
        QComboBoxPrivateContainer, QComboBox QFrame, QComboBox QAbstractItemView, QComboBox QListView, QAbstractItemView {
            background-color: #eff6ff !important;
            color: #0f172a !important;
            selection-background-color: #0284c7 !important;
            selection-color: #ffffff !important;
            border: 1.5px solid #0284c7 !important;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 12px !important;
            font-weight: 600;
            outline: none;
        }
        QAbstractItemView::item {
            background-color: #eff6ff;
            color: #0f172a;
            padding: 5px 8px;
        }
        QAbstractItemView::item:selected, QAbstractItemView::item:hover {
            background-color: #ffffff; color: #0f172a;
        }
        QMessageBox, QDialog, QInputDialog {
            background-color: #dcebfa !important;
            color: #0f172a !important;
        }
        QMessageBox QLabel, QDialog QLabel, QInputDialog QLabel {
            color: #0f172a !important;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 12px;
            font-weight: 600;
            background: transparent !important;
        }
        QMessageBox QPushButton, QInputDialog QPushButton {
            background-color: #ffffff; color: #0f172a !important;
            border: 1.5px solid #0369a1 !important;
            border-radius: 5px;
            padding: 6px 16px;
            min-width: 85px;
            font-weight: 600;
        }
        QMessageBox QPushButton:hover {
            background-color: #0369a1 !important;
        }
        QToolTip, QTipLabel { background-color: #ffffff; color: #0f172a; border: 1px solid #94a3b8; padding: 7px 9px; font-family: "Segoe UI", Arial, sans-serif; font-size: 11.5px; }
    """)

    def _styled_msgbox(icon, parent, title, text, buttons=QMessageBox.Ok, default_btn=QMessageBox.NoButton):
        mb = QMessageBox(icon, title, str(text), buttons, parent)
        if default_btn != QMessageBox.NoButton:
            mb.setDefaultButton(default_btn)
        mb.setAttribute(Qt.WA_StyledBackground, True)
        mb.setStyleSheet(
            "QMessageBox { background-color: #dcebfa; color: #0f172a; border: 2px solid #0284c7; } "
            "QLabel { color: #0f172a; background: transparent; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; } "
            "QPushButton { background-color: #ffffff; color: #0f172a; border: 1.5px solid #0369a1; border-radius: 5px; padding: 6px 18px; min-width: 85px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 600; } "
            "QPushButton:hover { background-color: rgba(96, 165, 250, 0.82); color: #0f172a; }"
        )
        return mb.exec()

    QMessageBox.information = staticmethod(lambda parent, title, text, buttons=QMessageBox.Ok, defaultButton=QMessageBox.NoButton: _styled_msgbox(QMessageBox.Information, parent, title, text, buttons, defaultButton))
    QMessageBox.warning = staticmethod(lambda parent, title, text, buttons=QMessageBox.Ok, defaultButton=QMessageBox.NoButton: _styled_msgbox(QMessageBox.Warning, parent, title, text, buttons, defaultButton))
    QMessageBox.critical = staticmethod(lambda parent, title, text, buttons=QMessageBox.Ok, defaultButton=QMessageBox.NoButton: _styled_msgbox(QMessageBox.Critical, parent, title, text, buttons, defaultButton))
    QMessageBox.question = staticmethod(lambda parent, title, text, buttons=QMessageBox.Yes | QMessageBox.No, defaultButton=QMessageBox.NoButton: _styled_msgbox(QMessageBox.Question, parent, title, text, buttons, defaultButton))

    from PySide6.QtCore import QObject, QEvent
    class _PopupThemeFixer(QObject):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._edge = ""
            self._start_gpos = None
            self._start_geo = None
        def _hit_edge(self, w, pos):
            if w.isMaximized(): return ""
            b = 7
            l, r, t, bt = pos.x() <= b, pos.x() >= w.width() - b, pos.y() <= b, pos.y() >= w.height() - b
            return ("T" if t else ("B" if bt else "")) + ("L" if l else ("R" if r else ""))
        def _show_clean_card_tip(self, gpos, text):
            if not hasattr(self, "_card_tip"):
                self._card_tip = QLabel(None, Qt.ToolTip | Qt.FramelessWindowHint)
                self._card_tip.setAttribute(Qt.WA_ShowWithoutActivating, True)
                self._card_tip.setStyleSheet("QLabel { background-color: #ffffff; color: #0f172a; border: 1px solid #94a3b8; padding: 7px 10px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 11.5px; }")
            lines = str(text).split("\n", 1)
            if len(lines) == 2:
                self._card_tip.setTextFormat(Qt.RichText)
                body_html = lines[1].replace("\n", "<br>")
                self._card_tip.setText(f"<b style='color:#0f172a;font-size:12px;'>{lines[0]}</b><br><span style='color:#334155;'>{body_html}</span>")
            else:
                self._card_tip.setTextFormat(Qt.PlainText)
                self._card_tip.setText(str(text))
            self._card_tip.adjustSize()
            self._card_tip.move(gpos.x() + 12, gpos.y() + 18)
            self._card_tip.show()
            self._card_tip.raise_()

        def eventFilter(self, obj, ev):
            et = ev.type()
            if et == QEvent.ShortcutOverride and getattr(ev, "key", lambda: None)() == Qt.Key_Tab:
                fw = QApplication.focusWidget()
                if fw is not None and fw.__class__.__name__ == "CadBlueprintCanvas":
                    ev.accept()
                    return True
            if et == QEvent.ToolTip and isinstance(obj, QWidget):
                tip_txt = obj.toolTip()
                if tip_txt and not tip_txt.lstrip().startswith("<b"):
                    self._show_clean_card_tip(ev.globalPos(), tip_txt)
                    ev.accept()
                    return True
            elif et in (QEvent.Leave, QEvent.MouseButtonPress, QEvent.WindowDeactivate):
                if hasattr(self, "_card_tip") and self._card_tip.isVisible():
                    self._card_tip.hide()
            et = ev.type()
            if et == QEvent.Show and obj.inherits("QComboBoxPrivateContainer"):
                obj.setAttribute(Qt.WA_StyledBackground, True)
                obj.setStyleSheet("QFrame { background-color: #eff6ff; border: 1.5px solid #0284c7; padding: 0px; }")
            elif window is not None and isinstance(obj, QWidget) and obj.window() is window:
                if et == QEvent.MouseMove and not self._edge:
                    ed = self._hit_edge(window, window.mapFromGlobal(ev.globalPosition().toPoint()))
                    cmap = {"L": Qt.SizeHorCursor, "R": Qt.SizeHorCursor, "T": Qt.SizeVerCursor, "B": Qt.SizeVerCursor,
                            "TL": Qt.SizeFDiagCursor, "BR": Qt.SizeFDiagCursor, "TR": Qt.SizeBDiagCursor, "BL": Qt.SizeBDiagCursor}
                    if ed: window.setCursor(cmap[ed])
                    elif window.cursor().shape() in cmap.values(): window.unsetCursor()
                elif et == QEvent.MouseButtonPress and ev.button() == Qt.LeftButton:
                    ed = self._hit_edge(window, window.mapFromGlobal(ev.globalPosition().toPoint()))
                    if ed:
                        self._edge = ed
                        self._start_gpos = ev.globalPosition().toPoint()
                        self._start_geo = window.geometry()
                        return True
                elif et == QEvent.MouseMove and self._edge:
                    gp = ev.globalPosition().toPoint()
                    dx, dy = gp.x() - self._start_gpos.x(), gp.y() - self._start_gpos.y()
                    g = QRect(self._start_geo)
                    mw, mh = window.minimumWidth(), window.minimumHeight()
                    if "L" in self._edge: g.setLeft(min(g.right() - mw, g.left() + dx))
                    if "R" in self._edge: g.setRight(max(g.left() + mw, g.right() + dx))
                    if "T" in self._edge: g.setTop(min(g.bottom() - mh, g.top() + dy))
                    if "B" in self._edge: g.setBottom(max(g.top() + mh, g.bottom() + dy))
                    window.setGeometry(g)
                    return True
                elif et == QEvent.MouseButtonRelease and self._edge:
                    self._edge = ""
                    window.unsetCursor()
                    return True
            return False
    window = None
    _popup_fixer = _PopupThemeFixer(app)
    app.installEventFilter(_popup_fixer)

    window = StandaloneManufacturingApp()
    window.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
    if os.name == "nt":
        try:
            import ctypes
            hwnd = int(window.winId())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
            ctypes.windll.user32.SetWindowLongW(hwnd, -16, (style & ~0x00C00000) | 0x00040000 | 0x00020000 | 0x00010000)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 3, ctypes.byref(ctypes.c_int(1)), 4)
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
        except Exception:
            pass
    window.setAcceptDrops(True)
    if hasattr(window, "central_widget"):
        window.central_widget.setAcceptDrops(True)
    if hasattr(window, "master_tabs"):
        window.master_tabs.setAcceptDrops(True)
    if os.name == "nt":
        try:
            import ctypes
            for msg in (0x0233, 0x004A, 0x0049):
                ctypes.windll.user32.ChangeWindowMessageFilter(msg, 1)
                ctypes.windll.user32.ChangeWindowMessageFilterEx(int(window.winId()), msg, 1, None)
        except Exception:
            pass

    class _GlobalExcelDropFilter(QObject):
        def _show_clean_card_tip(self, gpos, text):
            if not hasattr(self, "_card_tip"):
                self._card_tip = QLabel(None, Qt.ToolTip | Qt.FramelessWindowHint)
                self._card_tip.setAttribute(Qt.WA_ShowWithoutActivating, True)
                self._card_tip.setStyleSheet("QLabel { background-color: #ffffff; color: #0f172a; border: 1px solid #94a3b8; padding: 7px 10px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 11.5px; }")
            lines = str(text).split("\n", 1)
            if len(lines) == 2:
                self._card_tip.setTextFormat(Qt.RichText)
                body_html = lines[1].replace("\n", "<br>")
                self._card_tip.setText(f"<b style='color:#0f172a;font-size:12px;'>{lines[0]}</b><br><span style='color:#334155;'>{body_html}</span>")
            else:
                self._card_tip.setTextFormat(Qt.PlainText)
                self._card_tip.setText(str(text))
            self._card_tip.adjustSize()
            self._card_tip.move(gpos.x() + 12, gpos.y() + 18)
            self._card_tip.show()
            self._card_tip.raise_()

        def eventFilter(self, obj, ev):
            et = ev.type()
            if et == QEvent.ShortcutOverride and getattr(ev, "key", lambda: None)() == Qt.Key_Tab:
                fw = QApplication.focusWidget()
                if fw is not None and fw.__class__.__name__ == "CadBlueprintCanvas":
                    ev.accept()
                    return True
            if et == QEvent.ToolTip and isinstance(obj, QWidget):
                tip_txt = obj.toolTip()
                if tip_txt and not tip_txt.lstrip().startswith("<b"):
                    self._show_clean_card_tip(ev.globalPos(), tip_txt)
                    ev.accept()
                    return True
            elif et in (QEvent.Leave, QEvent.MouseButtonPress, QEvent.WindowDeactivate):
                if hasattr(self, "_card_tip") and self._card_tip.isVisible():
                    self._card_tip.hide()
            et = ev.type()
            if et in (QEvent.DragEnter, QEvent.DragMove):
                if hasattr(ev, "mimeData") and ev.mimeData().hasUrls():
                    if any(u.toLocalFile().lower().endswith((".xlsx", ".xlsm")) for u in ev.mimeData().urls()):
                        ev.acceptProposedAction()
                        if hasattr(window, "catalog_admin_embedded") and hasattr(window.catalog_admin_embedded, "excel_drop_pad"):
                            pad = window.catalog_admin_embedded.excel_drop_pad
                            pad.setStyleSheet(pad._hover_qss)
                        return True
            elif et == QEvent.Drop:
                if hasattr(ev, "mimeData") and ev.mimeData().hasUrls():
                    for u in ev.mimeData().urls():
                        fp = u.toLocalFile()
                        if fp.lower().endswith((".xlsx", ".xlsm")):
                            ev.acceptProposedAction()
                            if hasattr(window, "catalog_admin_embedded"):
                                pad = getattr(window.catalog_admin_embedded, "excel_drop_pad", None)
                                if pad: pad.setStyleSheet(pad._base_qss)
                                QTimer.singleShot(50, lambda p=fp: window.catalog_admin_embedded.admin_bulk_import_excel_sheet(p))
                            return True
            return False

    _excel_drop_filter = _GlobalExcelDropFilter(app)
    app.installEventFilter(_excel_drop_filter)
    if window.central_widget.layout() is not None:
        window.central_widget.layout().setContentsMargins(0, 0, 0, 0)
        window.central_widget.layout().setSpacing(0)
    if hasattr(window, "planset_takeoff_tab"):
        window.planset_takeoff_tab.show()
        window.master_tabs.setCurrentWidget(window.planset_takeoff_tab)
    if hasattr(window, "master_ribbon"):
        window.master_ribbon.set_active_tab(0)
    window.showMaximized()
    sys.exit(app.exec())
