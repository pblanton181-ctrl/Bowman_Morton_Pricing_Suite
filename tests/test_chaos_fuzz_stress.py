import random, pytest
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
    for _ in range(120):
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

    cv = win.planset_takeoff_tab.vis_workspace.canvas
    cv.pts_per_ft = 0.0
    assert isinstance(cv._format_ft_in(0.0), str)
    cv.pts_per_ft = 18.0
    win.close()


def test_15_member_structural_project_stress(qtbot, monkeypatch):
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
