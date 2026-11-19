import os
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def export_quote_to_excel(quote_dict: dict, output_path: str) -> str:
    """Exports a quote dictionary to a styled multi-tab Excel workbook with live =SUM() formulas."""
    wb = openpyxl.Workbook()

    # Sheet 1: Customer Quote
    ws = wb.active
    ws.title = "Customer Quote"

    hdr_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    sub_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
    tot_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
    hdr_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    sec_font = Font(name="Segoe UI", size=10, bold=True, color="0F172A")
    body_font = Font(name="Segoe UI", size=10, color="1E293B")
    tot_font = Font(name="Segoe UI", size=11, bold=True, color="107C41")
    thin = Side(style="thin", color="CBD5E1")
    cell_border = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws.merge_cells("A1:D1")
    ws["A1"] = f"BOWMAN-MORTON MANUFACTURING — QUOTE {quote_dict.get('quote_num', 'DRAFT')}"
    ws["A1"].font = hdr_font
    ws["A1"].fill = hdr_fill
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws["A2"] = f"Customer: {quote_dict.get('customer', '')}"
    ws["B2"] = f"Project: {quote_dict.get('project', '')}"
    ws["C2"] = f"Date: {quote_dict.get('timestamp', '')}"
    ws["D2"] = f"Tier: {quote_dict.get('tier_label', 'Engineered Bid')}"
    for col_let in ("A", "B", "C", "D"):
        ws[f"{col_let}2"].font = sec_font
        ws[f"{col_let}2"].fill = sub_fill

    headers = ["Item / Member Description", "Specifications & Fabrication", "Ship Weight (lbs)", "Line Total ($)"]
    ws.append([])
    ws.append(headers)
    hdr_row = 4
    for col_idx in range(1, 5):
        c = ws.cell(row=hdr_row, column=col_idx)
        c.font = sec_font
        c.fill = sub_fill
        c.border = cell_border
        c.alignment = Alignment(horizontal="right" if col_idx >= 3 else "left", vertical="center")

    lines = quote_dict.get("customer_lines", [])
    start_row = 5
    for idx, ln in enumerate(lines):
        r = start_row + idx
        c1 = ws.cell(row=r, column=1, value=str(ln.get("desc", "")))
        c2 = ws.cell(row=r, column=2, value=str(ln.get("specs", "")))
        c3 = ws.cell(row=r, column=3, value=round(float(ln.get("weight", 0.0) or 0.0), 2))
        c4 = ws.cell(row=r, column=4, value=round(float(ln.get("price", 0.0) or 0.0), 2))
        c3.number_format = "#,##0.0"
        c4.number_format = "$#,##0.00"
        for c in (c1, c2, c3, c4):
            c.font = body_font
            c.border = cell_border

    end_row = max(start_row, start_row + len(lines) - 1)
    tot_row = end_row + 1
    ws.cell(row=tot_row, column=1, value="GRAND TOTAL").font = tot_font
    ws.cell(row=tot_row, column=2, value=f"{len(lines)} Line Items").font = tot_font
    c_wt = ws.cell(row=tot_row, column=3, value=f"=SUM(C{start_row}:C{end_row})" if lines else 0.0)
    c_pr = ws.cell(row=tot_row, column=4, value=f"=SUM(D{start_row}:D{end_row})" if lines else float(quote_dict.get("cost", 0.0)))
    c_wt.number_format = "#,##0.0"
    c_pr.number_format = "$#,##0.00"
    for col_idx in range(1, 5):
        cell = ws.cell(row=tot_row, column=col_idx)
        cell.font = tot_font
        cell.fill = tot_fill
        cell.border = cell_border

    # Sheet 2: Shop Cut List
    ws2 = wb.create_sheet(title="Shop Cut List")
    ws2.append(["Item #", "Member / Part", "Qty", "Length (ft)", "Alloy", "Total Weight (lbs)"])
    for col_idx in range(1, 7):
        c = ws2.cell(row=1, column=col_idx)
        c.font = sec_font
        c.fill = sub_fill
        c.border = cell_border

    for idx, ln in enumerate(lines, start=1):
        fs = ln.get("form_state") or {}
        ws2.append([
            idx,
            fs.get("model") or ln.get("desc", ""),
            fs.get("qty", 1),
            fs.get("length", ""),
            fs.get("alloy", "Standard"),
            round(float(ln.get("weight", 0.0) or 0.0), 2),
        ])

    for sheet in (ws, ws2):
        for ci, col in enumerate(sheet.columns, start=1):
            max_len = max((len(str(cell.value or "")) for cell in col), default=12)
            sheet.column_dimensions[get_column_letter(ci)].width = min(56, max(14, max_len + 4))

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb.save(output_path)
    return output_path
