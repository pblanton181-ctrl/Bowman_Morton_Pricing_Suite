import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap
from blueprint_takeoff_ui import CadBlueprintCanvas
import live_test


def test_cad_canvas_tools_pressure(qtbot):
    canvas = CadBlueprintCanvas(lambda *a: None, lambda *a: None)
    canvas.resize(900, 700)
    pm = QPixmap(900, 700)
    pm.fill(Qt.white)
    canvas._base_pix = pm
    canvas.setPixmap(pm)
    qtbot.addWidget(canvas)
    canvas.show()

    # 1. 3-click Hanger Skew T-Square tool & live pivot swing
    canvas.mode = "hanger_skew"
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(200, 300))
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(400, 300))
    assert len(canvas._skew_pts) == 2
    qtbot.mouseMove(canvas, pos=QPoint(460, 420))
    canvas.repaint()
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(460, 420))
    assert len(canvas.markups) == 1
    assert canvas.markups[-1]["type"] == "hanger_skew"
    assert "SKEW" in canvas.markups[-1]["label"]

    # 2. Click-click Line drawing + Enter chain break
    canvas.mode = "line"
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(100, 100))
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(250, 100))
    assert len(canvas.markups) == 2
    qtbot.keyClick(canvas, Qt.Key_Return)
    assert canvas._p1 is None and canvas.mode == "line"

    # 3. Marquee selection box + Undo
    canvas.mode = "select"
    qtbot.mousePress(canvas, Qt.LeftButton, pos=QPoint(80, 80))
    qtbot.mouseMove(canvas, pos=QPoint(270, 130))
    qtbot.mouseRelease(canvas, Qt.LeftButton, pos=QPoint(270, 130))
    assert 1 in canvas.selected_indices

    canvas.undo_last_markup()
    assert len(canvas.markups) == 1


def test_full_manufacturing_app_pressure(qtbot, monkeypatch):
    monkeypatch.setattr(live_test.QMessageBox, "warning", lambda *a, **k: None)
    win = live_test.StandaloneManufacturingApp()
    qtbot.addWidget(win)
    win.show()

    # 1. Cycle all 5 main workspaces via ribbon
    for ws_idx in range(5):
        if hasattr(win, "master_ribbon"):
            win.master_ribbon._switch_workspace(ws_idx)

    # 2. Switch back to Catalog workspace (1) & pressure test compute + Edit Selected Item
    if hasattr(win, "master_ribbon"):
        win.master_ribbon._switch_workspace(1)
    win.data_core.rfq_ledger_items.clear()
    if hasattr(win, "category_box"):
        for ci in range(win.category_box.count()):
            win.category_box.setCurrentIndex(ci)
            win.handle_card_switch()
            if hasattr(win, "model_box") and win.model_box.count() > 1:
                win.model_box.setCurrentIndex(1)
                break
    if hasattr(win, "std_cust_input"): win.std_cust_input.setText("Test Client")
    if hasattr(win, "std_proj_input"): win.std_proj_input.setText("Test Job")
    win.entry_manual_1.setText("2")
    if hasattr(win, "entry_manual_2"):
        win.entry_manual_2.setText("10")
    win.calculate_standalone_pricing()
    assert len(win.data_core.rfq_ledger_items) == 1
    win.std_ledger_tree.setCurrentItem(win.std_ledger_tree.topLevelItem(0))
    win.edit_selected_standard_item()
    assert len(win.data_core.rfq_ledger_items) == 0

    # 3. Pressure test Structural Advance Steel Connection Presets + Hardware Toggle
    card = win.custom_quoting_tab.active_member_card
    card.addon_rows.clear()
    card.chk_conn_hardware.setChecked(True)
    card.apply_connection_preset()
    with_hw_count = len(card.addon_rows)
    card.addon_rows.clear()
    card.chk_conn_hardware.setChecked(False)
    card.apply_connection_preset()
    no_hw_count = len(card.addon_rows)
    assert with_hw_count >= no_hw_count
    win.close()


def test_full_window_canvas_select_floating_toolbar(qtbot):
    win = live_test.StandaloneManufacturingApp()
    qtbot.addWidget(win)
    win.show()
    cv = win.planset_takeoff_tab.vis_workspace.canvas
    pm = QPixmap(800, 600)
    pm.fill(Qt.white)
    cv._base_pix = pm
    cv.setPixmap(pm)
    cv.mode = "line"
    qtbot.mouseClick(cv, Qt.LeftButton, pos=QPoint(120, 120))
    qtbot.mouseClick(cv, Qt.LeftButton, pos=QPoint(280, 120))
    cv.mode = "select"
    qtbot.mouseClick(cv, Qt.LeftButton, pos=QPoint(200, 120))
    assert cv.selected_idx == 0
    win.close()
