from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton, QProgressBar, QListWidget, QListWidgetItem
)

class SmartBomSummaryPanel(QFrame):
    def __init__(self, on_jump_to_sheet, on_jump_to_profile=None, parent=None):
        super().__init__(parent)
        self.on_jump_to_sheet = on_jump_to_sheet
        self.on_jump_to_profile = on_jump_to_profile
        self.setStyleSheet(
            "QFrame#SmartBomSummaryPanel { background-color: #cfe4fa; border: 1.5px solid #60a5fa; border-top: 3px solid #0284c7; border-radius: 6px; } "
            "QLabel { color: #0f172a; background: transparent; border: none; }"
        )
        self.setObjectName("SmartBomSummaryPanel")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        hdr = QLabel("SMART ESTIMATING BREAKDOWN")
        hdr.setStyleSheet("color: #0369a1; font-size: 12px; font-weight: 700;")
        root.addWidget(hdr)

        # Top KPI Strip
        kpi_box = QFrame()
        kpi_box.setStyleSheet("QFrame { background-color: #eff6ff; border: 1px solid #93c5fd; border-radius: 6px; }")
        kl = QHBoxLayout(kpi_box)
        kl.setContentsMargins(8, 6, 8, 6)
        self.lbl_kpi_pcs = QLabel("0 pcs")
        self.lbl_kpi_lft = QLabel("0.0 lf")
        self.lbl_kpi_tons = QLabel("0.00 Tons")
        for lbl, col in ((self.lbl_kpi_pcs, "#0369a1"), (self.lbl_kpi_lft, "#0f172a"), (self.lbl_kpi_tons, "#047857")):
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: {col}; font-size: 12px; font-weight: 700; border: none;")
            kl.addWidget(lbl)
        root.addWidget(kpi_box)

        # Section 1: Category Weight Breakdown Bars
        lbl_cat = QLabel("CATEGORY TONNAGE SHARE")
        lbl_cat.setStyleSheet("color: #1e3a8a; font-size: 12px; font-weight: 700;")
        root.addWidget(lbl_cat)

        self.cat_container = QWidget()
        self.cat_container.setStyleSheet("background: transparent;")
        self.cat_layout = QVBoxLayout(self.cat_container)
        self.cat_layout.setContentsMargins(0, 0, 0, 0)
        self.cat_layout.setSpacing(5)
        root.addWidget(self.cat_container)

        # Section 2: One-Click Sheet Jump Cards
        lbl_sh = QLabel("JUMP TO PLANSET SHEET (CLICK TO VIEW)")
        lbl_sh.setStyleSheet("color: #1e3a8a; font-size: 12px; font-weight: 700;")
        root.addWidget(lbl_sh)

        self.sheet_list = QListWidget()
        self.sheet_list.setToolTip("<b>One-Click Sheet Jump</b><br>Click any sheet below to open that exact page<br>in Visual Sheet Preview & Takeoff.")
        self.sheet_list.setStyleSheet(
            "QListWidget { background-color: #f0f7ff; color: #0f172a; border: 1px solid #60a5fa; border-radius: 5px; font-size: 11.5px; font-weight: 600; } "
            "QListWidget::item { padding: 6px 8px; border-bottom: 1px solid #bfdbfe; } "
            "QListWidget::item:hover { background-color: #bfdbfe; } "
            "QListWidget::item:selected, QListWidget::item:selected:!active { background-color: #93c5fd; color: #0f172a; border-left: 4px solid #0284c7; }"
        )
        self.sheet_list.itemClicked.connect(self._handle_sheet_click)
        root.addWidget(self.sheet_list, 1)

        # Section 3: Top Steel Profiles Summary
        lbl_pr = QLabel("TOP STEEL PROFILES (CHECKED)")
        lbl_pr.setStyleSheet("color: #1e3a8a; font-size: 12px; font-weight: 700;")
        root.addWidget(lbl_pr)

        self.prof_list = QListWidget()
        self.prof_list.setStyleSheet(
            "QListWidget { background-color: #f0f7ff; color: #0f172a; border: 1px solid #60a5fa; border-radius: 5px; font-size: 11.5px; font-weight: 600; } "
            "QListWidget::item { padding: 4px 6px; border-bottom: 1px solid #dbeafe; }"
        )
        self.prof_list.itemClicked.connect(self._handle_prof_click)
        root.addWidget(self.prof_list, 1)

    def _handle_prof_click(self, item):
        data = item.data(Qt.UserRole)
        if data and self.on_jump_to_profile:
            prof_name, target_sheet = data
            self.on_jump_to_profile(prof_name, target_sheet)

    def _handle_sheet_click(self, item):
        sh_name = item.data(Qt.UserRole)
        if sh_name and self.on_jump_to_sheet:
            self.on_jump_to_sheet(sh_name)

    def refresh_from_tree(self, tree_widget):
        total_pcs = 0
        total_lft = 0.0
        total_lbs = 0.0
        cat_lbs = {}
        sheet_stats = {}  # sheet -> [pcs, lbs]
        prof_stats = {}   # profile -> [pcs, lft, lbs]

        for i in range(tree_widget.topLevelItemCount()):
            p_item = tree_widget.topLevelItem(i)
            cat_name = p_item.data(0, Qt.UserRole) or p_item.text(0).split("(").__getitem__(0).strip()
            for j in range(p_item.childCount()):
                ch = p_item.child(j)
                if ch.checkState(0) != Qt.Checked:
                    continue
                sh = ch.text(1).strip() or "Plan"
                prof = ch.text(3).strip() or "Member"
                try:
                    qty = max(0, int(float(ch.text(4) or 0)))
                    ln = float(ch.text(5) or 0.0)
                    wt = float(ch.text(7).replace(",", "") or 0.0)
                except ValueError:
                    qty, ln, wt = 0, 0.0, 0.0

                total_pcs += qty
                total_lft += qty * ln
                total_lbs += wt
                cat_lbs[cat_name] = cat_lbs.get(cat_name, 0.0) + wt

                st = sheet_stats.setdefault(sh, [0, 0.0])
                st[0] += qty
                st[1] += wt

                pr = prof_stats.setdefault(prof, [0, 0.0, 0.0, {}])
                pr[0] += qty
                pr[1] += qty * ln
                pr[2] += wt
                pr[3][sh] = pr[3].get(sh, 0) + qty

        self.lbl_kpi_pcs.setText(f"{total_pcs:,} pcs")
        self.lbl_kpi_lft.setText(f"{total_lft:,.1f} lf")
        self.lbl_kpi_tons.setText(f"{total_lbs / 2000.0:,.2f} Tons")

        while self.cat_layout.count():
            it = self.cat_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        denom = max(1.0, total_lbs)
        for cat_name, w_val in sorted(cat_lbs.items(), key=lambda kv: kv[1], reverse=True):
            pct = int(round((w_val / denom) * 100.0))
            row_w = QWidget()
            rl = QVBoxLayout(row_w)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(2)
            lbl = QLabel(f"{cat_name}: {w_val:,.0f} lbs ({pct}%)")
            lbl.setStyleSheet("color: #0f172a; font-size: 11.5px; font-weight: 600;")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(pct)
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setStyleSheet(
                "QProgressBar { background-color: #eff6ff; border: 1px solid #93c5fd; border-radius: 4px; } "
                "QProgressBar::chunk { background-color: #0284c7; border-radius: 3px; }"
            )
            rl.addWidget(lbl)
            rl.addWidget(bar)
            self.cat_layout.addWidget(row_w)

        self.sheet_list.clear()
        for sh_name, (s_pcs, s_lbs) in sorted(sheet_stats.items(), key=lambda kv: kv[0]):
            li = QListWidgetItem(f"Sheet {sh_name}  ->  {s_pcs} pcs  |  {s_lbs:,.0f} lbs")
            li.setData(Qt.UserRole, sh_name)
            self.sheet_list.addItem(li)

        self.prof_list.clear()
        for pr_name, (p_pcs, p_lf, p_lbs, sh_map) in sorted(prof_stats.items(), key=lambda kv: kv[1][2], reverse=True)[:20]:
            sorted_sh = sorted(sh_map.items(), key=lambda kv: kv[1], reverse=True)
            primary_sh = sorted_sh[0][0] if sorted_sh else ""
            sh_tag = ", ".join(s for s, _ in sorted_sh[:2])
            li = QListWidgetItem(f"{pr_name} [{sh_tag}]:  {p_pcs} pcs | {p_lf:,.1f} lf | {p_lbs:,.0f} lbs")
            li.setData(Qt.UserRole, (pr_name, primary_sh))
            self.prof_list.addItem(li)
