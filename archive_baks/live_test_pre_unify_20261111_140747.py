# ==========================================
# SECTION 1: SYSTEM SYSTEM WORKSPACE ARCHITECTURE
# ==========================================
import os
import sys
import json
import shutil
import datetime
import webbrowser
import urllib.parse
import custom_quoting_module as cqm

from PySide6.QtCore import Qt, QSize, QFileSystemWatcher
from PySide6.QtGui import QFont, QColor, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
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
QScrollArea, QScrollArea > QWidget, QScrollArea::viewport, #LeftScrollContainer { 
    background: transparent !important; 
    border: none; 
}
QLabel, QLabel#MutedLabel { 
    font-family: 'Segoe UI', Arial; 
    font-weight: bold; 
    font-size: 13px; 
}
QTabWidget::pane { 
    border: 1px solid #1e294b; 
    background-color: #131b2e; 
    border-radius: 8px; 
    margin-top: 0px; 
}
QTabBar::tab { 
    background-color: #090d16; 
    color: #94a3b8; 
    border: 1px solid #1e294b; 
    padding: 10px 20px; 
    border-top-left-radius: 6px; 
    border-top-right-radius: 6px; 
    font-weight: bold; 
}
QTabBar::tab:selected { 
    background-color: #131b2e; 
    color: #38bdf8; 
    border-bottom-color: #131b2e; 
}
QTabBar::tab:hover { 
    color: #ffffff; 
    background-color: #1e294b; 
}
QPushButton#PrimaryAction { background-color: #0284c7; color: #ffffff; font-weight: bold; border-radius: 6px; padding: 12px; }
QPushButton#PrimaryAction:hover { background-color: #0369a1; }
QPushButton#SecondaryAction { background-color: #475569; color: #ffffff; border: 1px solid #64748b; border-radius: 6px; padding: 10px; font-weight: bold; }
QPushButton#SecondaryAction:hover { background-color: #64748b; }
QPushButton#EmeraldAction { background-color: #059669; color: #ffffff; font-weight: bold; border-radius: 6px; padding: 10px; }
QPushButton#EmeraldAction:hover { background-color: #047857; }
QPushButton#DangerAction { background-color: #dc2626; color: #ffffff; font-weight: bold; border-radius: 6px; padding: 10px; }
QPushButton#DangerAction:hover { background-color: #b91c1c; }
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
    def get_profile_multiplier(raw_profile_str):
        text_check = str(raw_profile_str).upper()
        if "CONSTRUCTION SUPPLY" in text_check: 
            return 0.50  
        if "LUMBER YARD" in text_check: 
            return 0.60  
        return 1.00      

    @staticmethod
    def calc_card1(base_cost, lbs_weight, profile_mult, checks):
        subtotal = base_cost * profile_mult  
        if checks.get("Flush To Top (C8)"): subtotal += (30.00 * profile_mult)
        if checks.get("RT STRP OTHR THN 90 (D8)"): subtotal += (25.00 * profile_mult)
        if checks.get("BCCOBQ (D10)"): subtotal += (11.00 * profile_mult)
        if checks.get("SKD CCQ Cap (B12)"): subtotal += ((lbs_weight * 0.80) if lbs_weight >= 20.00 else (lbs_weight * 1.88)) * profile_mult
        if checks.get("Greater Height (C12)"): subtotal *= 1.05
        if checks.get("W3>W1 (B10)"): subtotal *= 1.10
        if checks.get("Rough BM Sz (C10)"): subtotal *= 1.25
        if checks.get("HDG (D12)"): subtotal *= 1.15
        
        # Exact implementation matching requirement: Rush evaluated last
        if checks.get("Rush (B8)"): subtotal *= 1.25
        return subtotal

    @staticmethod
    def calc_standard_height(base_cost, lbs_weight, profile_mult, checks, actual_ht, dynamic_row_min_ht, labels_list, extra_height_rate=0.50):
        subtotal = base_cost * profile_mult  
        calculated_wgt = lbs_weight
        
        if actual_ht > dynamic_row_min_ht: 
            height_delta = actual_ht - dynamic_row_min_ht
            subtotal += (height_delta * 2.0 * extra_height_rate * profile_mult)
            calculated_wgt += (height_delta * 1.0)
            
        for label in labels_list:
            if checks.get(label):
                if "SKW" in label or "SLP" in label: 
                    subtotal += (25.00 * profile_mult)
                if "RGH LMB" in label.upper():
                    subtotal += (11.00 * profile_mult)
                if "HDG" in label: 
                    hdg_rate = 0.62 if calculated_wgt >= 20.00 else 1.88
                    subtotal += (calculated_wgt * hdg_rate) * profile_mult
                    
        if any(checks.get(l) and "RUSH" in l.upper() for l in labels_list): subtotal *= 1.25
        
        return subtotal, calculated_wgt

    @staticmethod
    def calc_card5_6(base_cost, lbs_weight, profile_mult, checks, actual_ht, dynamic_row_min_ht, labels_list):
        subtotal = base_cost * profile_mult  
        calculated_wgt = lbs_weight
        
        if actual_ht > dynamic_row_min_ht: 
            height_delta = actual_ht - dynamic_row_min_ht
            subtotal += (height_delta * 2.0 * 1.40 * profile_mult)
            calculated_wgt += (height_delta * 1.0)
            
        for label in labels_list:
            if checks.get(label):
                if "SKW" in label and "SLP" not in label: subtotal += (44.00 * profile_mult)
                if "SLP" in label and "SKW" not in label: subtotal += (42.50 * profile_mult)
                if "OFFSET" in label: subtotal += (15.00 * profile_mult)
                if "SKW&SLP" in label: subtotal += (50.00 * profile_mult)
                if "HDG" in label: 
                    hdg_rate = 0.62 if calculated_wgt >= 20.00 else 1.88
                    subtotal += (calculated_wgt * hdg_rate) * profile_mult
                    
        if any(checks.get(l) and "RUSH" in l.upper() for l in labels_list): subtotal *= 1.25
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
    @staticmethod
    def calc_card8(base_cost, lbs_weight, profile_mult, model_name, checks, valley_val, ridge_val):
        min_height_p18 = 9.5 if "MSC 5" in model_name else (7.5 if "MSC 4" in model_name else 5.5)
        
        def clean_ht(v, def_h):
            cl = "".join(c for c in str(v) if c in (".", "-") or c.isdigit())
            return float(cl) if cl else def_h
            
        v_ht = clean_ht(valley_val, min_height_p18)
        r_ht = clean_ht(ridge_val, min_height_p18)
        
        # Pull multiplier values per half-inch increments
        v_mult, r_mult = (6.00, 3.00) if ("MSC 4" in model_name or "MSC 5" in model_name) else (3.20, 1.60)
        
        v_delta = max(0.0, v_ht - min_height_p18)
        r_delta = max(0.0, r_ht - min_height_p18)
        
        subtotal = (base_cost + (v_delta * 2.0 * v_mult) + (r_delta * 2.0 * r_mult)) * profile_mult
        
        # CORRECT MATRIX WEIGHT: Multiplies by 2.0 because of the two matching physical saddles
        v_wgt_rate, r_wgt_rate = (1.20, 0.60) if ("MSC 4" in model_name or "MSC 5" in model_name) else (0.80, 0.40)
        calculated_wgt = lbs_weight + (v_delta * 2.0 * v_wgt_rate) + (r_delta * 2.0 * r_wgt_rate)
        
        if checks.get("No SLP (O25)"): 
            subtotal -= (35.00 * profile_mult)
            
        # CORRECTED HDG WEIGHT ACCUMULATION: Evaluates using the true double-saddle expanded weight
        if checks.get("HDG (P25)"): 
            hdg_rate = 0.62 if calculated_wgt >= 20.00 else 1.88
            subtotal += (calculated_wgt * hdg_rate) * profile_mult
            
        if checks.get("Rush (N25)"): 
            subtotal *= 1.25
            
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
        
        self.master_layout.addWidget(self.admin_tabs_deck)
        self.toggle_admin_context_fields()
        self.sync_admin_purgable_model_dropdown()

    def create_tab_1_title_remapper(self):
        tab1_page = QWidget()
        lay = QVBoxLayout(tab1_page)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.addWidget(QLabel("Administrative Screen Title Re-Mapping Registry Framework:"))
        
        self.title_inputs_map = {}
        t_grid = QGridLayout()
        row_counter = 0
        for c_id, config in CARDS_SCHEMA_MATRIX.items():
            t_grid.addWidget(QLabel(f"{config['dropdown_sheet']} ({c_id}):"), row_counter, 0)
            t_in = QLineEdit()
            t_in.setText(self.data_core.runtime_visual_titles.get(c_id, config["default_title"]))
            t_grid.addWidget(t_in, row_counter, 1)
            self.title_inputs_map[c_id] = t_in
            row_counter += 1
        lay.addLayout(t_grid)
        
        self.btn_save_titles = QPushButton("🔒 COMMIT AND ENCRYPT NEW TITLES TO DATABASE")
        self.btn_save_titles.setObjectName("EmeraldAction")
        self.btn_save_titles.setMinimumHeight(42)
        self.btn_save_titles.clicked.connect(self.admin_save_encrypted_titles)
        lay.addWidget(self.btn_save_titles)
        lay.addStretch()
        self.admin_tabs_deck.addTab(tab1_page, "📋 Category Title Matrix")
# ==========================================
# SECTION 7: ADMINISTRATIVE VARIANT RECORDING
# ==========================================
    def create_tab_2_variant_appender(self):
        tab2_page = QWidget()
        lay = QVBoxLayout(tab2_page)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(15)
        lay.addWidget(QLabel("➕ Append Single New Part Variant Record to Active Database Ledger Sheet:"))
        
        self.grid = QGridLayout()
        self.grid.setSpacing(12)
        self.grid.addWidget(QLabel("Target Category:"), 0, 0)
        self.cat_select = QComboBox()
        self.cat_select.addItems(list(self.data_core.clean_database.keys()))
        self.cat_select.currentIndexChanged.connect(self.toggle_admin_context_fields)
        self.grid.addWidget(self.cat_select, 0, 1)
        
        self.grid.addWidget(QLabel("Part Model Variant Label:"), 1, 0)
        self.model_input = QLineEdit()
        self.grid.addWidget(self.model_input, 1, 1)
        
        self.grid.addWidget(QLabel("Weight Metric Value (lbs):"), 2, 0)
        self.weight_input = QLineEdit()
        self.grid.addWidget(self.weight_input, 2, 1)
        
        self.cost_lbl = QLabel("Standard Base Cost ($):")
        self.cost_input = QLineEdit()
        self.grid.addWidget(self.cost_lbl, 3, 0)
        self.grid.addWidget(self.cost_input, 3, 1)
        
        self.base_height_label = QLabel("Min Base Reference Height:")
        self.base_height_input = QLineEdit()
        self.grid.addWidget(self.base_height_label, 4, 0)
        self.grid.addWidget(self.base_height_input, 4, 1)
        lay.addLayout(self.grid)
        
        self.btn_save = QPushButton("COMMIT SINGLE VARIANT TO DISK")
        self.btn_save.setObjectName("EmeraldAction")
        self.btn_save.setMinimumHeight(38)
        self.btn_save.clicked.connect(self.save_database_entry)
        lay.addWidget(self.btn_save)
        
        separator_line = QFrame()
        separator_line.setFrameShape(QFrame.HLine)
        lay.addWidget(separator_line)
        
        # --- ORIGINAL EXCEL BULK CONTROLS INTERFACE ATTACHMENT ---
        lay.addWidget(QLabel("📂 Bulk Import Complete Category Sheet via Excel Workbook Matrix:"))
        
        bulk_h_layout = QHBoxLayout()
        self.bulk_op_mode_toggle = QComboBox()
        self.bulk_op_mode_toggle.addItems(["➕ Import & Automatically Sort/Group into Matrix", "❌ Wipe and Replace Current Section rows"])
        self.bulk_op_mode_toggle.setMinimumHeight(38)
        
        self.btn_trigger_bulk_import = QPushButton("⚡ LOAD EXCEL SHEET (.XLSX)...")
        self.btn_trigger_bulk_import.setObjectName("PrimaryAction")
        self.btn_trigger_bulk_import.setMinimumHeight(38)
        self.btn_trigger_bulk_import.clicked.connect(self.execute_admin_bulk_import_transaction)
        
        bulk_h_layout.addWidget(self.bulk_op_mode_toggle, 3)
        bulk_h_layout.addWidget(self.btn_trigger_bulk_import, 2)
        lay.addLayout(bulk_h_layout)
        
        lay.addStretch()
        self.admin_tabs_deck.addTab(tab2_page, "➕ Append Material Records")

    def execute_admin_bulk_import_transaction(self):
        cat_title = self.cat_select.currentText()
        if not cat_title or cat_title not in self.data_core.clean_database: return
        
        models_list = list(self.data_core.clean_database[cat_title].keys())
        
        # FIXED: Extract the first single string element out of the list
        first_model = models_list[0] if models_list else None
        schema_id = self.data_core.clean_database[cat_title][first_model]["schema_id"] if first_model else "CARD_1"
        mode_type = CARDS_SCHEMA_MATRIX[schema_id]["mode"]
        
        op_mode = "REPLACE" if "Wipe and Replace" in self.bulk_op_mode_toggle.currentText() else "APPEND"
        
        file_path, _ = QFileDialog.getOpenFileName(self, "Select External Inventory Workbook Matrix Source", "", "Excel Spreadsheets (*.xlsx)")
        if not file_path: return
        
        success, info_payload = self.data_core.import_bulk_excel_sheet(file_path, cat_title, schema_id, mode_type, op_mode)
        
        if success:
            QMessageBox.information(self, "Workbook Synced", f"Transaction processed successfully.\nSuccessfully parsed and written {info_payload} records inside tracking ledger sheets.")
            if self.parent() and hasattr(self.parent(), 'handle_card_switch'):
                self.parent().handle_card_switch()
            self.sync_admin_purgable_model_dropdown()
        else:
            QMessageBox.critical(self, "Import Aborted", f"Structural parser failure sequence hit:\n{info_payload}")
# ==========================================
# SECTION 8: ADMINISTRATIVE DISPLAY LAYOUTS
# ==========================================
    def toggle_admin_context_fields(self):
        cat = self.cat_select.currentText()
        if not cat or cat not in self.data_core.clean_database: return
        models_list = list(self.data_core.clean_database[cat].keys())
        
        # FIXED: Added [0] index key slice to extract the model name string out of the list
        first_model = models_list[0] if models_list else None
        schema_id = self.data_core.clean_database[cat][first_model]["schema_id"] if first_model else "CARD_1"
        mode = CARDS_SCHEMA_MATRIX[schema_id]["mode"]
        
        self.base_height_label.setVisible(mode in ["height_input", "double_height"])
        self.base_height_input.setVisible(mode in ["height_input", "double_height"])
        
        if mode == "qty_input":
            self.cost_lbl.setText("Tier Prices (G-O split by | ):")
            self.cost_input.setPlaceholderText("e.g. 5.10|4.80|4.50|4.20|4.00|3.80|3.60|3.40|800.00")
        else:
            self.cost_lbl.setText("Standard Base Cost ($):")
            self.cost_input.setPlaceholderText("")

    def admin_save_encrypted_titles(self):
        try:
            if "ADMIN_METADATA_CONFIG_BLOCK" not in self.data_core.raw_full_json_blob:
                self.data_core.raw_full_json_blob["ADMIN_METADATA_CONFIG_BLOCK"] = {}
            for c_id, t_in in self.title_inputs_map.items():
                self.data_core.raw_full_json_blob["ADMIN_METADATA_CONFIG_BLOCK"][c_id] = t_in.text().strip()
            with open(self.data_core.database_file, "w", encoding="utf-8") as f:
                json.dump(self.data_core.raw_full_json_blob, f, indent=4)
                
            if self.parent() and hasattr(self.parent(), 'refresh_live_category_titles'):
                self.parent().refresh_live_category_titles()
            QMessageBox.information(self, "Titles Secured", "Administrative titles saved successfully.")
        except Exception as e: 
            QMessageBox.critical(self, "Exception", f"Error saving titles: {e}")

    def sync_admin_purgable_model_dropdown(self):
        cat = self.bulk_cat_select.currentText()
        if not cat or cat not in self.data_core.clean_database: return
        models = list(self.data_core.clean_database[cat].keys())
        self.delete_model_select.clear()
        if models: self.delete_model_select.addItems(models)
# ==========================================
# SECTION 9: ADMINISTRATIVE SHEET SCALE MANIPULATION
# ==========================================
    def save_database_entry(self):
        cat = self.cat_select.currentText()
        model = self.model_input.text().strip()
        weight = self.weight_input.text().strip()
        cost = self.cost_input.text().strip()
        if not model or not weight or not cost or not cat: return
        try:
            models_list = list(self.data_core.clean_database[cat].keys())
            
            # FIXED: Ensure [0] index is present here too to avoid unhashable type list crash
            first_model = models_list[0] if models_list else None
            schema_id = self.data_core.clean_database[cat][first_model]["schema_id"] if first_model else "CARD_1"
            sheet_target = CARDS_SCHEMA_MATRIX[schema_id]["dropdown_sheet"]
            h_val = float(self.base_height_input.text().strip()) if self.base_height_input.isVisible() else 0.0
            
            if sheet_target in self.data_core.raw_full_json_blob:
                if CARDS_SCHEMA_MATRIX[schema_id]["mode"] == "qty_input":
                    new_row = [model, "0", "0", "0", "0", weight] + cost.split("|")
                elif CARDS_SCHEMA_MATRIX[schema_id]["mode"] == "fixed_standard_cost":
                    new_row = [model, "0", weight, "0", "0", cost]
                elif schema_id in ["CARD_2", "CARD_3", "CARD_4", "CARD_5"]:
                    new_row = [model, "0", str(h_val), weight, cost]
                elif schema_id == "CARD_6":
                    new_row = [model, "0", weight, cost]
                else:
                    new_row = [model, "0", str(h_val), "0", weight, cost]
                    
                self.data_core.raw_full_json_blob[sheet_target].append(new_row)
                with open(self.data_core.database_file, "w", encoding="utf-8") as f:
                    json.dump(self.data_core.raw_full_json_blob, f, indent=4)
            
            self.data_core.load_and_sanitize_matrix()
            if self.parent() and hasattr(self.parent(), 'handle_card_switch'):
                self.parent().handle_card_switch()
            QMessageBox.information(self, "Success", "Variant appended successfully.")
            self.model_input.clear()
            self.weight_input.clear()
            self.cost_input.clear()
            self.sync_admin_purgable_model_dropdown()
        except Exception as e: 
            QMessageBox.critical(self, "Error", f"Failed write hook: {e}")

    def create_tab_3_bulk_modifiers(self):
        tab3_page = QWidget()
        lay = QVBoxLayout(tab3_page)
        lay.setContentsMargins(20, 20, 20, 20)
        
        self.bulk_cat_select = QComboBox()
        self.bulk_cat_select.addItems(list(self.data_core.clean_database.keys()))
        self.bulk_cat_select.currentIndexChanged.connect(self.sync_admin_purgable_model_dropdown)
        lay.addWidget(self.bulk_cat_select)
        
        self.delete_model_select = QComboBox()
        lay.addWidget(self.delete_model_select)
        
        self.btn_delete_item = QPushButton("❌ ERASE SELECTED MODEL OUT OF LOCAL CACHE")
        self.btn_delete_item.setObjectName("DangerAction")
        self.btn_delete_item.setMinimumHeight(38)
        self.btn_delete_item.clicked.connect(self.admin_purge_single_item_record)
        lay.addWidget(self.btn_delete_item)
        
        lay.addWidget(QLabel("Enter Global Spreadsheet Price Adjustment Shift Percentage Factor (%):"))
        self.pct_input = QLineEdit()
        lay.addWidget(self.pct_input)
        
        self.btn_bulk_scale = QPushButton("🔥 MULTIPLY ENTIRE CARD PRICING MATRIX BY SCALE FACTOR %")
        self.btn_bulk_scale.setObjectName("PrimaryAction")
        self.btn_bulk_scale.setMinimumHeight(42)
        self.btn_bulk_scale.clicked.connect(self.admin_execute_bulk_percentage_scale)
        lay.addWidget(self.btn_bulk_scale)
        lay.addStretch()
        self.admin_tabs_deck.addTab(tab3_page, "⚡ Bulk Pricing Modifiers")

    def admin_purge_single_item_record(self):
        cat = self.bulk_cat_select.currentText()
        model = self.delete_model_select.currentText()
        if not model or not cat: return
        try:
            models_list = list(self.data_core.clean_database[cat].keys())
            
            # FIXED: Added single-element list index selection [0] to eliminate the unhashable type crash
            first_model = models_list[0] if models_list else None
            schema_id = self.data_core.clean_database[cat][first_model]["schema_id"] if first_model else "CARD_1"
            sheet_target = CARDS_SCHEMA_MATRIX[schema_id]["dropdown_sheet"]
            m_col = CARDS_SCHEMA_MATRIX[schema_id]["model_col"]
            
            rows = self.data_core.raw_full_json_blob.get(sheet_target, [])
            new_rows = [r for r in rows if not (len(r) > m_col and str(r[m_col]).strip() == model)]
            self.data_core.raw_full_json_blob[sheet_target] = new_rows
            
            with open(self.data_core.database_file, "w", encoding="utf-8") as f:
                json.dump(self.data_core.raw_full_json_blob, f, indent=4)
                
            self.data_core.load_and_sanitize_matrix()
            if self.parent() and hasattr(self.parent(), 'handle_card_switch'):
                self.parent().handle_card_switch()
                
            QMessageBox.information(self, "Success", f"Variant item {model} purged successfully.")
            self.sync_admin_purgable_model_dropdown()
        except Exception as e: 
            QMessageBox.critical(self, "Error", f"Purge Failure: {e}")

    def admin_execute_bulk_percentage_scale(self):
        cat = self.bulk_cat_select.currentText()
        pct_text = self.pct_input.text().strip()
        if not pct_text or not cat: return
        try:
            factor = 1.0 + (float(pct_text) / 100.0)
            models_list = list(self.data_core.clean_database[cat].keys())
            first_model = models_list if models_list else None
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
        
        self.central_widget = QWidget()
        self.central_widget.setObjectName("CentralMasterWidget")
        self.setCentralWidget(self.central_widget)
        self.central_widget.setAttribute(Qt.WA_StyledBackground, True)
        self.central_widget.setStyleSheet("""
            QWidget#CentralMasterWidget {
                background-image: url('BMAPP.jpg');
                background-repeat: no-repeat;
                background-position: center;
                background-color: transparent !important;
            }
        """)
        
        outer_deck_layout = QVBoxLayout(self.central_widget)
        outer_deck_layout.setContentsMargins(12, 12, 12, 12)

        self.custom_safeguards_file = get_workspace_path("shop_safeguards.json")
        self.custom_ledger_file = get_workspace_path("project_ledger.json")
        self.custom_safeguards = self._load_custom_safeguards()
        self.custom_ledger_pool, self.custom_quote_seq = self._load_custom_ledger()

        self.master_tabs = QTabWidget()
        outer_deck_layout.addWidget(self.master_tabs)

        tab1_standard = QWidget()
        self.main_layout = QHBoxLayout(tab1_standard)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(20)

        self.setup_menu_bar_tabs()
        self.setup_left_quoting_panel()
        self.setup_right_ledger_panel()
        self.handle_card_switch()
        self.master_tabs.addTab(tab1_standard, "?? Standard Hangers & Catalog")

        self.custom_quoting_tab = cqm.StructuralQuotingSandbox(
            self._commit_custom_project, self.custom_safeguards, self
        )
        self.custom_ledger_tab = cqm.HistoricalArchiveLedgerPage(
            self.custom_ledger_pool, self.custom_safeguards, self._save_custom_ledger, self
        )
        self.custom_admin_tab = cqm.AdminControlDashboardPage(
            self.custom_safeguards, self._on_custom_safeguards_saved, self
        )

        self.master_tabs.addTab(self.custom_quoting_tab, "?? Custom Structural Quoting")
        self.master_tabs.addTab(self.custom_ledger_tab, "??? Running Project Ledger")
        self.master_tabs.addTab(self.custom_admin_tab, "??? Shop Safeguards & Rates")
        self.custom_ledger_tab.populate_ledger_grid()
        
        self.file_monitor = QFileSystemWatcher(self)
        for watch_p in [self.data_core.database_file, self.custom_safeguards_file, self.custom_ledger_file]:
            if os.path.exists(watch_p):
                self.file_monitor.addPath(watch_p)
        self.file_monitor.fileChanged.connect(self.execute_silent_network_sync)

    def setup_menu_bar_tabs(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        
        pdf_action = QAction("Save Quote PDF Sheet...", self)
        pdf_action.triggered.connect(self.trigger_save_as_file_dialog)
        file_menu.addAction(pdf_action)
        
        email_action = QAction("Email Quote Package directly...", self)
        email_action.triggered.connect(self.trigger_email_client_package)
        file_menu.addAction(email_action)
        
        file_menu.addSeparator()
        exit_action = QAction("Exit Suite", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        view_menu = menubar.addMenu("Workspace Views")
        admin_action = QAction("Switch to Administrative Controls...", self)
        admin_action.triggered.connect(self.show_admin_gateway)
        view_menu.addAction(admin_action)
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
            story.append(Paragraph(f"OFFICIAL PRICE QUOTE STATEMENT — {current_date_str}", subtitle_style))
            
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
        
        c1 = QWidget()
        c1.setAttribute(Qt.WA_StyledBackground, True)
        c1.setStyleSheet("""
            QWidget { 
                background-color: rgba(30, 41, 59, 0.45); 
                border: 2px solid #334155; 
                border-radius: 8px; 
            }
            QLabel { color: #f8fafc; font-weight: bold; background: transparent; border: none; }
            QComboBox, QLineEdit { 
                background-color: rgba(15, 23, 42, 0.55); 
                color: #ffffff; 
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
                background-color: rgba(30, 41, 59, 0.45); 
                border: 2px solid #334155; 
                border-radius: 8px; 
            }
            QLabel { color: #f8fafc; font-weight: bold; background: transparent; border: none; }
            QLineEdit { 
                background-color: rgba(15, 23, 42, 0.55); 
                color: #ffffff; 
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
                background-color: rgba(30, 41, 59, 0.45); 
                border: 2px solid #334155; 
                border-radius: 8px; 
            }
            QLabel { color: #f8fafc; font-weight: bold; background: transparent; border: none; }
            QCheckBox { color: #f8fafc; font-weight: bold; background: transparent; border: none; }
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
                background-color: rgba(30, 41, 59, 0.45); 
                border: 2px solid #334155; 
                border-radius: 8px; 
            }
        """)
        c4_layout = QVBoxLayout(c4)
        c4_layout.setContentsMargins(12, 12, 12, 12)
        self.spec_label = QLabel("Configure parameters to compute calculation layout loop.")
        self.spec_label.setStyleSheet("color: #FFFFFF !important; font-family: 'Segoe UI', Arial; font-weight: bold; font-size: 13px; background: transparent; border: none;")
        c4_layout.addWidget(self.spec_label)
        scroll_layout.addWidget(c4)

        self.btn_compute = QPushButton("COMPUTE DISK RATE AND WRITE TO CONSOLIDATED RFQ LEDGER")
        self.btn_compute.setObjectName("PrimaryAction")
        self.btn_compute.setMinimumHeight(52)
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
        right_layout = QVBoxLayout(right_container)
        right_container.setAttribute(Qt.WA_StyledBackground, True)
        right_container.setStyleSheet("background-color: transparent !important; background: transparent !important;")
        
        ledger_frame = QFrame()
        ledger_frame.setObjectName("SurfaceCard")
        ledger_frame.setAttribute(Qt.WA_StyledBackground, True)
        ledger_frame.setStyleSheet("background-color: transparent !important; background: transparent !important; border: none;")
        
        lf_layout = QVBoxLayout(ledger_frame)
        lf_layout.setContentsMargins(0, 0, 0, 0)
        
        self.ledger_textbox = QTextEdit()
        self.ledger_textbox.setAttribute(Qt.WA_StyledBackground, True)
        self.ledger_textbox.setStyleSheet("""
            QTextEdit {
                background-color: rgba(30, 41, 59, 0.45) !important; 
                color: #f8fafc !important;            
                border: 2px solid #334155;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                font-weight: bold;
                border-radius: 8px;
            }
        """)
        self.ledger_textbox.setReadOnly(True)
        lf_layout.addWidget(self.ledger_textbox)
        right_layout.addWidget(ledger_frame)
        
        self.btn_reset = QPushButton("🔄 RESET ACTIVE LEDGER SESSION")
        self.btn_reset.setObjectName("SecondaryAction")
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
        if items_list: self.model_box.addItems(items_list)
        else: self.model_box.addItem("No matched variants found")
        self.model_box.blockSignals(False)
# ==========================================
# SECTION 13 (PART B): PIPELINE CALCULATION & EXECUTION LOOP
# ==========================================
    def calculate_standalone_pricing(self):
        card = self.category_box.currentText()
        model = self.model_box.currentText()
        if model == "No matched variants found" or not model or card not in self.data_core.clean_database: return
        
        c_data = self.data_core.clean_database.get(card, {}).get(model, None)
        if not c_data: return
        s_id = c_data["schema_id"]
        config = CARDS_SCHEMA_MATRIX[s_id]
        raw_p = self.team_box.currentText()
        mult = PricingCalculatorCore.get_profile_multiplier(raw_p)
        
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
                base_raw, _ = PricingCalculatorCore.calc_card5_6(scrub(c_data["cost"]), wgt, mult, no_checks, v1, row_min_ht, config["surcharges_labels"])
                base_raw *= 1.05
            elif config["mode"] == "standard":
                base_raw = PricingCalculatorCore.calc_card1(scrub(c_data["cost"]), wgt, mult, no_checks) * 1.05
            elif config["mode"] == "height_input":
                r_p, _ = PricingCalculatorCore.calc_standard_height(scrub(c_data["cost"]), wgt, mult, no_checks, v1, row_min_ht, config["surcharges_labels"])
                base_raw = r_p * 1.05
            elif config["mode"] == "qty_input":
                _, base_raw = PricingCalculatorCore.calc_card7_tiered(c_data, mult, no_checks, int(max(1.0, v1)))
            elif config["mode"] == "fixed_standard_cost":
                base_raw = (scrub(c_data["cost"]) * mult) * int(max(1.0, v1)) * 1.05
            else:
                v2 = scrub(self.entry_manual_2.text())
                r_p, _ = PricingCalculatorCore.calc_card8(scrub(c_data["cost"]), wgt, mult, model, no_checks, v1, v2)
                base_raw = r_p * 1.05

            # --- CALCULATE TRUE PREMIUM PRICING MATRIX ---
            if s_id in ["CARD_5", "CARD_6"]:
                f_price, calculated_wgt = PricingCalculatorCore.calc_card5_6(scrub(c_data["cost"]), wgt, mult, checks, v1, row_min_ht, config["surcharges_labels"])
                f_price *= 1.05
                wgt = calculated_wgt
            elif config["mode"] == "standard":
                f_price = PricingCalculatorCore.calc_card1(scrub(c_data["cost"]), wgt, mult, checks) * 1.05
            elif config["mode"] == "height_input":
                raw_f_price, calculated_wgt = PricingCalculatorCore.calc_standard_height(scrub(c_data["cost"]), wgt, mult, checks, v1, row_min_ht, config["surcharges_labels"])
                f_price = raw_f_price * 1.05
                wgt = calculated_wgt 
            # ... (inside calculate_standalone_pricing where f_price is determined) ...
            elif config["mode"] == "qty_input":
                rate, total = PricingCalculatorCore.calc_card7_tiered(c_data, mult, checks, int(max(1.0, v1)))
                f_price = total
                wgt = wgt * int(max(1.0, v1))
            elif config["mode"] == "fixed_standard_cost":
                base_rate = scrub(c_data["cost"])
                if checks.get("Mod CHRG $15 (K22)"): base_rate += 15.00
                base_rate *= mult
                if checks.get("Rush (J22)"): base_rate *= 1.25
                f_price = base_rate * int(max(1.0, v1)) * 1.05
                wgt = wgt * int(max(1.0, v1))
            else:
                v2 = scrub(self.entry_manual_2.text())
                # FIXED: Intercept both the final price AND the double-saddle calculated weight output
                raw_f_price, calculated_wgt = PricingCalculatorCore.calc_card8(scrub(c_data["cost"]), wgt, mult, model, checks, v1, v2)
                f_price = raw_f_price * 1.05
                wgt = calculated_wgt # Updates the display token variables perfectly

            # === START OF CODE REPLACEMENT AT THE BOTTOM OF THE FUNCTION ===
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
            res = (
                f"🎯 Quoting Terminal Breakout:\n"
                f"  -> Part Model Base: {model}\n"
                f"  -> Configured Height:{breakout_height_str}\n"
                f"  -> Shipping Weight: {wgt:.1f} lbs\n"
                f"  -> Baseline Item Cost: ${base_raw:.2f}\n"
                f"  -> Active Surcharges: {addon_list_str}\n"
                f"  -> Add-ons Premium Total: ${surcharge_delta:.2f}\n"
                f"  -----------------------------------------\n"
                f"  🔥 FINAL CALCULATED RATE: ${f_price:.2f}"
            )
            self.spec_label.setText(res)
            
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
            self.data_core.rfq_ledger_items.append({
                "model": extended_model_label, 
                "weight": f"{wgt:.1f} lbs", 
                "cost": f"${f_price:.2f}", 
                "addons": addon_list_str
            })
            self.update_rfq_ledger_view()

            # --- PASTE THE CHECKBOX CLEANUP LOOP HERE ---
            for cb in self.check_boxes:
                if cb.isVisible():
                    cb.blockSignals(True)
                    cb.setChecked(False)
                    cb.blockSignals(False)

        except Exception as e: self.spec_label.setText(f"❌ Calculation Error: {e}")
        # === END OF FUNCTION ===

    def update_rfq_ledger_view(self):
        self.ledger_textbox.clear()
        header = f"{'PART MODEL VARIANT':<30} | {'WEIGHT':<14} | {'STANDALONE COST':<16}\n"
        divider = "-" * 68 + "\n"
        self.ledger_textbox.insertPlainText(header + divider)
        tot_final, tot_weight = 0.00, 0.00
        for item in self.data_core.rfq_ledger_items:
            m_str, w_str, c_str = str(item['model'])[:28], str(item['weight'])[:12], str(item['cost'])[:14]
            self.ledger_textbox.insertPlainText(f"{m_str:<30} | {w_str:<14} | {c_str:>16}\n")
            addons_str = item.get("addons", "None")
            if addons_str != "None": self.ledger_textbox.insertPlainText(f"   [Add-ons: {addons_str}]\n")
            try: tot_final += float(item['cost'].replace("$", "").replace(",", "").strip())
            except ValueError: pass
            try: tot_weight += float(item['weight'].lower().replace("lbs", "").strip())
            except ValueError: pass
        self.ledger_textbox.insertPlainText("\n" + divider)
        self.ledger_textbox.insertPlainText(f"{'TOTAL COMBINED ORDER VALUE:':<30}   {'':<14}   ${tot_final:.2f}\n")

    def clear_rfq_ledger_session(self):
        self.data_core.rfq_ledger_items = []
        self.update_rfq_ledger_view()

    def show_admin_gateway(self):
        dialog = PasscodeInputDialog(self, "Security Authorization Required", "Enter Administrative Passcode:")
        if dialog.exec() and dialog.get_inputcode() == "Barron":
            AdminDashboardWindow(self, self.data_core).exec()

    def _load_custom_safeguards(self):
        defaults = {
            "admin_passcode": "Barron", "base_labor_rate": 86.0, "eng_labor_rate": 175.0,
            "std_stud_rate": 5.00, "labor_markup": 1.40, "max_saw_beam_size": "W16",
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

    def _commit_custom_project(self, customer, project, total_weight, total_cost, summary_desc, customer_lines=None):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        quote_str = f"BM-2026-{self.custom_quote_seq}"
        self.custom_quote_seq += 1
        self.custom_ledger_pool.append({
            "quote_num": quote_str, "timestamp": timestamp, "customer": customer,
            "project": project, "weight": total_weight, "cost": total_cost,
            "summary": summary_desc, "customer_lines": customer_lines or []
        })
        self._save_custom_ledger()
        self.custom_ledger_tab.populate_ledger_grid()

if __name__ == "__main__":
    import qdarktheme
    app = QApplication(sys.argv)
    qdarktheme.setup_theme(theme="dark", corner_shape="rounded", custom_colors={"primary": "#0284c7"})
    window = StandaloneManufacturingApp()
    window.show()
    sys.exit(app.exec())
