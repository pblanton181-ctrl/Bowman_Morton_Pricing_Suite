import os, tempfile
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap
from blueprint_takeoff_ui import CadBlueprintCanvas
from core.excel_workbook_engine import export_quote_to_excel
from core.cad_dxf_engine import export_bom_to_dxf
import live_test


def test_every_cad_takeoff_tool_pressure(qtbot):
    canvas = CadBlueprintCanvas(lambda *a: None, lambda *a: None)
    canvas.resize(1000, 800)
    pm = QPixmap(1000, 800)
    pm.fill(Qt.white)
    canvas._base_pix = pm
    canvas.setPixmap(pm)
    qtbot.addWidget(canvas)
    canvas.show()

    # 1. Hanger Skew: Skew Right & Skew Left
    canvas.mode = "hanger_skew"
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(200, 300))
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(400, 300))
    qtbot.mouseMove(canvas, pos=QPoint(460, 420))
    canvas.repaint()
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(460, 420))
    assert canvas.markups[-1]["type"] == "hanger_skew"
    assert "SKEW" in canvas.markups[-1]["label"]

    # 2. Line, Dashed, Centerline, Arrow + Enter break
    for m_name, y_off in [("line", 100), ("dashed", 130), ("centerline", 160), ("arrow", 190)]:
        canvas.mode = m_name
        qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(100, y_off))
        qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(260, y_off))
        qtbot.keyClick(canvas, Qt.Key_Return)
        assert canvas._p1 is None

    # 3. Polyline + C close loop
    canvas.mode = "polyline"
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(500, 100))
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(620, 100))
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(620, 200))
    qtbot.keyClick(canvas, Qt.Key_C)
    assert canvas.markups[-1]["type"] == "polyline"

    # 4. Span Measure & Count Badges
    canvas.mode = "measure"
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(500, 300))
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(700, 300))
    assert canvas.markups[-1]["type"] == "span"

    canvas.mode = "count"
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(550, 400))
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(580, 400))
    assert sum(1 for m in canvas.markups if m.get("type") == "count") == 2

    # 5. Window & Crossing Marquee Selection, Group Move & Undo
    canvas.mode = "select"
    qtbot.mousePress(canvas, Qt.LeftButton, pos=QPoint(530, 380))
    qtbot.mouseMove(canvas, pos=QPoint(610, 430))
    qtbot.mouseRelease(canvas, Qt.LeftButton, pos=QPoint(610, 430))
    assert len(canvas.selected_indices) >= 2

    before_undo = len(canvas.markups)
    canvas.undo_last_markup()
    assert len(canvas.markups) == before_undo - 1


def test_every_workspace_and_export_pressure(qtbot, monkeypatch):
    monkeypatch.setattr(live_test.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(live_test.QMessageBox, "information", lambda *a, **k: None)
    win = live_test.StandaloneManufacturingApp()
    qtbot.addWidget(win)
    win.show()

    # 1. Switch through all 5 workspaces & trigger ribbon mode buttons
    for ws_idx in range(5):
        win.master_ribbon._switch_workspace(ws_idx)
    win.master_ribbon._switch_workspace(0)
    for mode_cmd in ("select", "pan", "measure", "polyline", "line", "dashed", "centerline", "hanger_skew", "count"):
        win.master_ribbon._vis_mode(mode_cmd)
        assert win.planset_takeoff_tab.vis_workspace.canvas.mode == mode_cmd

    # 2. Catalog Quoting: Compute -> Duplicate -> Edit back to left panel -> Re-compute
    win.master_ribbon._switch_workspace(1)
    win.data_core.rfq_ledger_items.clear()
    for ci in range(win.category_box.count()):
        win.category_box.setCurrentIndex(ci)
        win.handle_card_switch()
        if win.model_box.count() > 1:
            win.model_box.setCurrentIndex(1)
            break
    win.std_cust_input.setText("Pressure Client")
    win.std_proj_input.setText("Full Suite Job")
    win.entry_manual_1.setText("3")
    win.entry_manual_2.setText("12")
    win.calculate_standalone_pricing()
    assert len(win.data_core.rfq_ledger_items) == 1
    win.std_ledger_tree.setCurrentItem(win.std_ledger_tree.topLevelItem(0))
    win.edit_selected_standard_item()
    assert len(win.data_core.rfq_ledger_items) == 0
    win.calculate_standalone_pricing()
    assert len(win.data_core.rfq_ledger_items) == 1

    # 3. Structural Quoting + Excel (.xlsx) & Advance Steel (.dxf) Export Engines
    win.master_ribbon._switch_workspace(2)
    card = win.custom_quoting_tab.active_member_card
    card.addon_rows.clear()
    card.chk_conn_hardware.setChecked(True)
    card.apply_connection_preset()
    assert len(card.addon_rows) >= 1

    with tempfile.TemporaryDirectory() as tmp:
        xlsx_p = export_quote_to_excel(
            {
                "quote_num": "BM-PRESS-01",
                "customer": "Pressure Client",
                "project": "Full Suite Job",
                "timestamp": "2026-11-17",
                "customer_lines": [{"desc": "W16X57 (x2)", "specs": "3-Bolt Shear Tab", "weight": 2280.0, "price": 4500.0}],
            },
            os.path.join(tmp, "pressure_bid.xlsx"),
        )
        assert os.path.exists(xlsx_p) and os.path.getsize(xlsx_p) > 2000

        dxf_p = export_bom_to_dxf(
            [{"model": "W16X57", "qty": 2, "length_ft": 20.0}],
            os.path.join(tmp, "pressure_takeoff.dxf"),
        )
        assert os.path.exists(dxf_p) and os.path.getsize(dxf_p) > 1000

    win.close()
