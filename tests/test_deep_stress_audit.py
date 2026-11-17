import json, os, tempfile, pymupdf, pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap
from blueprint_takeoff_ui import CadBlueprintCanvas
import live_test


def test_every_remaining_canvas_tool_and_edge_cases(qtbot):
    canvas = CadBlueprintCanvas(lambda *a: None, lambda *a: None)
    canvas.resize(1000, 800)
    pm = QPixmap(1000, 800)
    pm.fill(Qt.white)
    canvas._base_pix = pm
    canvas.setPixmap(pm)
    qtbot.addWidget(canvas)
    canvas.show()

    # 1. Edge cases on empty canvas (must never crash)
    for k in (Qt.Key_Delete, Qt.Key_Backspace, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Tab):
        qtbot.keyClick(canvas, k)
    canvas.undo_last_markup()
    canvas.delete_selected_markup()
    canvas.rotate_selected_markup()
    canvas.duplicate_selected_markup()

    # 2. Drag tools: box, filled_box, highlight, ellipse, cloud, angle
    for idx, dmode in enumerate(("box", "filled_box", "highlight", "ellipse", "cloud", "angle")):
        canvas.mode = dmode
        y0 = 60 + idx * 70
        qtbot.mousePress(canvas, Qt.LeftButton, pos=QPoint(80, y0))
        qtbot.mouseMove(canvas, pos=QPoint(220, y0 + 45))
        qtbot.mouseRelease(canvas, Qt.LeftButton, pos=QPoint(220, y0 + 45))
    assert len(canvas.markups) == 6

    # 3. Freehand Adobe Highlighter stroke
    canvas.mode = "free_highlight"
    qtbot.mousePress(canvas, Qt.LeftButton, pos=QPoint(300, 100))
    qtbot.mouseMove(canvas, pos=QPoint(380, 105))
    qtbot.mouseMove(canvas, pos=QPoint(460, 100))
    qtbot.mouseRelease(canvas, Qt.LeftButton, pos=QPoint(460, 100))
    assert canvas.markups[-1]["type"] == "free_highlight"

    # 4. Area polygon (3 points + Enter finish)
    canvas.mode = "area"
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(300, 220))
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(450, 220))
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(450, 340))
    qtbot.keyClick(canvas, Qt.Key_Return)
    assert canvas.markups[-1]["type"] == "area"

    # 5. Rotate, Duplicate, Group Move, and Clear All
    canvas.selected_idx = 0
    canvas.selected_indices = {0, 1}
    canvas.rotate_selected_markup()
    before_dup = len(canvas.markups)
    canvas.duplicate_selected_markup()
    assert len(canvas.markups) == before_dup + 1
    canvas.clear_markups()
    assert len(canvas.markups) == 0


def test_every_catalog_card_and_structural_shape_math(qtbot, monkeypatch):
    monkeypatch.setattr(live_test.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(live_test.QMessageBox, "information", lambda *a, **k: None)
    win = live_test.StandaloneManufacturingApp()
    qtbot.addWidget(win)
    win.show()

    # 1. Sweep EVERY category in Catalog and compute pricing on its first real model
    win.master_ribbon._switch_workspace(1)
    win.std_cust_input.setText("Sweep Client")
    win.std_proj_input.setText("Sweep Job")
    tested_cats = 0
    for ci in range(win.category_box.count()):
        win.category_box.setCurrentIndex(ci)
        win.handle_card_switch()
        if win.model_box.count() > 1:
            win.model_box.setCurrentIndex(1)
            win.entry_manual_1.setText("2")
            win.entry_manual_2.setText("10")
            win.calculate_standalone_pricing()
            tested_cats += 1
    assert tested_cats > 0
    assert len(win.data_core.rfq_ledger_items) == tested_cats

    # 2. Sweep EVERY structural shape type in Structural Quoting
    win.master_ribbon._switch_workspace(2)
    card = win.custom_quoting_tab.active_member_card
    for si in range(card.type_select.count()):
        card.type_select.setCurrentIndex(si)
        if card.size_select.count() > 0:
            card.size_select.setCurrentIndex(0)
        card.qty_input.setValue(2)
        card.len_ft_input.setValue(12.0)
        win.custom_quoting_tab.execute_fabrication_math_routine()

    # 3. Sweep all non-modal ribbon actions from config/ribbon_config.json
    with open("config/ribbon_config.json", "r", encoding="utf-8-sig") as f:
        rcfg = json.load(f)

    actions = []
    def collect_actions(node):
        if isinstance(node, list):
            for x in node: collect_actions(x)
        elif isinstance(node, dict):
            if "action" in node: actions.append(node["action"])
            for v in node.values(): collect_actions(v)
    collect_actions(rcfg)

    skip_prefixes = ("trig:", "app:trigger_save", "app:trigger_email", "app:open_dev", "admin:", "pdf:load", "pdf:open_acrobat", "ledger:open_excel")
    for act in actions:
        if any(act.startswith(p) for p in skip_prefixes):
            continue
        if hasattr(win.master_ribbon, "dispatch_ribbon_action"):
            win.master_ribbon.dispatch_ribbon_action(act)

    win.close()
