from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QHeaderView, QAbstractItemView
)


class FormulaHudBar(QFrame):
    """Microsoft Excel 365-style live fx formula & breakdown bar."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setStyleSheet(
            "FormulaHudBar { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; }"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 2, 8, 2)
        lay.setSpacing(8)

        self.lbl_cell = QLabel("ACTIVE")
        self.lbl_cell.setFixedWidth(56)
        self.lbl_cell.setAlignment(Qt.AlignCenter)
        self.lbl_cell.setStyleSheet(
            "background-color: #f1f5f9; color: #334155; font-size: 10px; font-weight: 700; "
            "border: 1px solid #cbd5e1; border-radius: 3px; padding: 1px 4px;"
        )

        self.lbl_fx = QLabel("fx")
        self.lbl_fx.setStyleSheet(
            "color: #107c41; font-family: 'Georgia', serif; font-style: italic; font-size: 13px; font-weight: 800; border: none;"
        )

        self.txt_formula = QLineEdit()
        self.txt_formula.setReadOnly(True)
        self.txt_formula.setPlaceholderText("Select any line item or member to inspect live pricing formula breakdown...")
        self.txt_formula.setStyleSheet(
            "QLineEdit { background: transparent; border: none; color: #0f172a; font-family: 'Consolas', 'Segoe UI', monospace; font-size: 11px; }"
        )

        lay.addWidget(self.lbl_cell)
        lay.addWidget(self.lbl_fx)
        lay.addWidget(self.txt_formula, 1)

    def set_formula(self, cell_tag: str, formula_text: str):
        self.lbl_cell.setText(cell_tag or "ACTIVE")
        self.txt_formula.setText(formula_text or "")


class ExcelPinnedTotalBar(QFrame):
    """Compact Excel-style pinned bottom Total Row replacing bulky summary boxes."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setStyleSheet(
            "ExcelPinnedTotalBar { background-color: #f8fafc; border: 1px solid #cbd5e1; "
            "border-top: 2px solid #107c41; border-radius: 4px; }"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 2, 12, 2)
        lay.setSpacing(18)

        lbl_title = QLabel("TOTAL")
        lbl_title.setStyleSheet("color: #107c41; font-size: 11px; font-weight: 800; letter-spacing: 0.5px; border: none;")
        lay.addWidget(lbl_title)

        self._fields = {}
        for key, label, default_val, color in [
            ("count", "Items:", "0", "#334155"),
            ("weight", "Total Weight:", "0.0 lbs", "#0f172a"),
            ("sub", "Subtotal:", "$0.00", "#334155"),
            ("total", "Grand Total:", "$0.00", "#107c41"),
        ]:
            cap = QLabel(label)
            cap.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 600; border: none;")
            val = QLabel(default_val)
            val.setStyleSheet(f"color: {color}; font-size: 11.5px; font-weight: 800; border: none;")
            lay.addWidget(cap)
            lay.addWidget(val)
            self._fields[key] = val

        lay.addStretch(1)

    def update_totals(self, count: int = 0, weight_lbs: float = 0.0, subtotal: float = 0.0, grand_total: float = 0.0):
        self._fields["count"].setText(str(count))
        self._fields["weight"].setText(f"{weight_lbs:,.1f} lbs")
        self._fields["sub"].setText(f"${subtotal:,.2f}")
        self._fields["total"].setText(f"${grand_total:,.2f}")


def apply_excel_table_style(view):
    """Applies Excel 365 banded row styling, crisp headers, and double-click column auto-fit."""
    view.setAlternatingRowColors(True)
    if hasattr(view, "setSelectionBehavior"):
        view.setSelectionBehavior(QAbstractItemView.SelectRows)
    view.setStyleSheet(
        "QTreeWidget, QTableWidget, QTableView { "
        "background-color: #ffffff; alternate-background-color: #f8fafc; "
        "color: #0f172a; gridline-color: #e2e8f0; border: 1px solid #cbd5e1; border-radius: 4px; "
        "font-size: 11.5px; selection-background-color: #e0f2fe; selection-color: #0369a1; } "
        "QHeaderView::section { "
        "background-color: #f1f5f9; color: #334155; font-size: 11px; font-weight: 700; "
        "border: none; border-right: 1px solid #cbd5e1; border-bottom: 1.5px solid #94a3b8; padding: 5px 8px; }"
    )
    hdr = view.header() if hasattr(view, "header") else (view.horizontalHeader() if hasattr(view, "horizontalHeader") else None)
    if hdr:
        hdr.setStretchLastSection(True)
        hdr.sectionDoubleClicked.connect(lambda col: view.resizeColumnToContents(col))
