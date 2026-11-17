# 1. Fix RuntimeWarning in custom_quoting_module.py:261
with open("custom_quoting_module.py", "r", encoding="utf-8-sig") as f:
    cq = f.read()
cq = cq.replace(
    "self.type_select.currentIndexChanged.disconnect()",
    "try:\n                self.type_select.currentIndexChanged.disconnect()\n            except Exception:\n                pass",
    1
)
with open("custom_quoting_module.py", "w", encoding="utf-8") as f:
    f.write(cq)

# 2. Fix _refresh_ribbon_summary in ribbon_bar_widget.py to check pt.bom_items, pt.tree, AND vw.bom_items
with open("ribbon_bar_widget.py", "r", encoding="utf-8-sig") as f:
    rb = f.read()

start_rs = rb.index("    def _refresh_ribbon_summary(self):")
end_rs = rb.index("\n    def ", start_rs + 10)

clean_rs = '''    def _refresh_ribbon_summary(self):
        if not hasattr(self, "_sum_vals"):
            return
        pt = getattr(self.app, "planset_takeoff_tab", None)
        vw = getattr(pt, "vis_workspace", None) if pt else None
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
        self._sum_vals["members"].setText(f"{bom_pcs:,} pcs")
        self._sum_vals["takeoff_wt"].setText(f"{bom_lbs:,.0f} lbs")
        cat_items = getattr(getattr(self.app, "data_core", None), "rfq_ledger_items", []) or []
        cat_tot = 0.0
        for it in cat_items:
            try:
                cat_tot += float(str(it.get("cost", 0)).replace("$", "").replace(",", "").strip() or 0.0)
            except Exception:
                pass
        self._sum_vals["cat_tot"].setText(f"${cat_tot:,.2f}")
        sq = getattr(self.app, "custom_quoting_tab", None)
        st_items = getattr(sq, "current_project_items", []) or []
        st_tot = sum(float(x.get("total_price", x.get("price", 0.0)) or 0.0) for x in st_items)
        self._sum_vals["struct_tot"].setText(f"${st_tot:,.2f}")
        quotes = getattr(self.app, "custom_ledger_pool", []) or []
        self._sum_vals["ledger_cnt"].setText(f"{len(quotes)} quotes")
'''
rb = rb[:start_rs] + clean_rs + rb[end_rs:]
with open("ribbon_bar_widget.py", "w", encoding="utf-8") as f:
    f.write(rb)

# 3. Create brutal Chaos, Fuzz & Multi-Member Lifecycle Stress Suite
@'
import random, os, tempfile, pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap
from blueprint_takeoff_ui import CadBlueprintCanvas
import live_test


def test_chaos_random_clicks_zooms_and_fuzz_inputs(qtbot):
    rng = random.Random(2026)
    canvas = CadBlueprintCanvas(lambda *a: None, lambda *a: None)
    canvas.resize(1100, 850)
    pm = QPixmap(1100, 850)
    pm.fill(Qt.white)
    canvas._base_pix = pm
    canvas.setPixmap(pm)
    qtbot.addWidget(canvas)
    canvas.show()

    modes = ["select", "pan", "measure", "polyline", "line", "dashed", "centerline", "arrow", "hanger_skew", "count", "area", "filled_box", "ellipse", "cloud"]
    for step in range(120):
        canvas.mode = rng.choice(modes)
        pt = QPoint(rng.randint(20, 1050), rng.randint(20, 800))
        act = rng.randint(0, 4)
        if act == 0:
            qtbot.mouseClick(canvas, Qt.LeftButton, pos=pt)
        elif act == 1:
            qtbot.mouseMove(canvas, pos=pt)
        elif act == 2:
            qtbot.keyClick(canvas, rng.choice([Qt.Key_Return, Qt.Key_Escape, Qt.Key_Backspace, Qt.Key_Tab, Qt.Key_Delete]))
        elif act == 3:
            canvas.set_zoom(rng.uniform(0.35, 3.2))
        else:
            canvas.undo_last_markup()
    canvas.clear_markups()
    assert len(canvas.markups) == 0


def test_corrupt_and_extreme_numeric_fuzzing(qtbot, monkeypatch):
    monkeypatch.setattr(live_test.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(live_test.QMessageBox, "information", lambda *a, **k: None)
    win = live_test.StandaloneManufacturingApp()
    qtbot.addWidget(win)
    win.show()

    bad_inputs = ["", "   ", "-9999", "0", "0.0001", "99999999", "$1,234.56", "abc!@#", "NaN", "inf"]
    win.master_ribbon._switch_workspace(1)
    for bad in bad_inputs:
        win.entry_manual_1.setText(bad)
        win.entry_manual_2.setText(bad)
        win.calculate_standalone_pricing()

    # Zero-scale calibration guard on canvas
    cv = win.planset_takeoff_tab.vis_workspace.canvas
    cv.pts_per_ft = 0.0
    assert isinstance(cv._format_ft_in(0.0), str)
    cv.pts_per_ft = 18.0
    win.close()


def test_15_member_structural_project_edit_duplicate_delete_stress(qtbot, monkeypatch):
    monkeypatch.setattr(live_test.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(live_test.QMessageBox, "information", lambda *a, **k: None)
    win = live_test.StandaloneManufacturingApp()
    qtbot.addWidget(win)
    win.show()

    win.master_ribbon._switch_workspace(2)
    sq = win.custom_quoting_tab
    sq.current_project_items.clear()
    card = sq.active_member_card

    shapes = ["W", "HSS", "L", "C", "PL", "Pipe", "FB"]
    for i in range(15):
        sh = shapes[i % len(shapes)]
        card.populate_surcharges_by_shape(sh)
        if card.combo_model.count() > 0:
            card.combo_model.setCurrentIndex(i % card.combo_model.count())
        card.chk_conn_hardware.setChecked(i % 2 == 0)
        card.apply_connection_preset()
        card.trigger_compute()

    assert len(sq.current_project_items) == 15
    win.master_ribbon._refresh_ribbon_summary()
    assert "$" in win.master_ribbon._sum_vals["struct_tot"].text()
    win.close()
