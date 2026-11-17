import openpyxl
from openpyxl.utils import get_column_letter

# 1. Initialize a clean data workbook framework container
wb = openpyxl.Workbook()

# --- SHEET 1: PATTERN A (STANDARD VARIABLE HEIGHT FIELDS) ---
ws1 = wb.active
ws1.title = "Pattern A - Height Input"
ws1.append(["Part Model Variant Label", "Physical Weight (lbs)", "Baseline Retail List Cost", "Min Reference Height"])
ws1.append(["BLGU325SDS", 5.50, 112.00, 8.00])
ws1.append(["BLGU3.63/11.875", 5.60, 116.00, 8.00])
ws1.append(["BHWPH562", 7.04, 21.00, 6.00])

# --- SHEET 2: PATTERN B (VOLUME QUANTITY TIERS PIPED CHART) ---
ws2 = wb.create_sheet(title="Pattern B - Tiered Quantity")
ws2.append(["Part Model Variant Label", "Physical Weight (lbs)", "All 9 Tier Costs (Piped Matrix)"])
ws2.append(["3/16x2x2", 0.213, "10.26|10.26|6.93|5.26|4.26|3.12|1.80|1.51|322.20"])
ws2.append(["3/16x3x3", 0.479, "10.59|10.59|7.26|5.59|4.59|3.45|2.13|1.84|392.92"])

# --- SHEET 3: PATTERN C (FIXED FLAT PRICE COMPONENT STOCK) ---
ws3 = wb.create_sheet(title="Pattern C - Fixed Standard Cost")
ws3.append(["Part Model Variant Label", "Physical Weight (lbs)", "Flat Baseline Retail Unit Rate", "Ignored Padding Column"])
ws3.append(["FM-2", 3.51, 12.75, 0])
ws3.append(["FM-3", 0.31, 5.50, 0])
ws3.append(["BABU44", 1.867, 30.00, 0])

# --- SHEET 4: PATTERN D (SPECIALIZED BMSC DOUBLE HEIGHT) ---
ws4 = wb.create_sheet(title="Pattern D - BMSC Hangers")
ws4.append(["Part Model Variant Label", "Physical Weight (lbs)", "Baseline Retail List Cost", "Dynamic Reference Height Min"])
ws4.append(["MSC 4", 29.00, 550.00, 7.50])
ws4.append(["MSC 5", 32.00, 624.00, 9.50])

# 2. Loop across pages to scale visual frame layout padding automatically
for ws in wb.worksheets:
    # Set thin grid lines visible to formatting teams
    ws.views.sheetView[0].showGridLines = True
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 14)

# 3. Save compiled template to physical asset sheet on system disk
file_name = "Bowman_Morton_Import_Templates.xlsx"
wb.save(file_name)
print(f"🎯 Success! Generated master validation spreadsheet: '{file_name}'")
