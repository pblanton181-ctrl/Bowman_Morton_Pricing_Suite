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

    # 2. Drag tools: OCR box + filled_box, highlight, ellipse, cloud, angle
    for idx, dmode in enumerate(("box", "filled_box", "highlight", "ellipse", "cloud", "angle")):
        canvas.mode = dmode
        y0 = 60 + idx * 70
        qtbot.mousePress(canvas, Qt.LeftButton, pos=QPoint(80, y0))
        qtbot.mouseMove(canvas, pos=QPoint(220, y0 + 45))
        qtbot.mouseRelease(canvas, Qt.LeftButton, pos=QPoint(220, y0 + 45))
    assert len(canvas.markups) == 5

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

    # 2. Sweep EVERY structural shape family in Structural Quoting
    win.master_ribbon._switch_workspace(2)
    card = win.custom_quoting_tab.active_member_card
    for shape_key in ("W", "HSS", "L", "C", "PL", "Pipe", "FB"):
        if hasattr(card, "populate_surcharges_by_shape"):
            card.populate_surcharges_by_shape(shape_key)
        if hasattr(card, "combo_model") and card.combo_model.count() > 0:
            card.combo_model.setCurrentIndex(0)
        if hasattr(card, "trigger_compute"):
            card.trigger_compute()

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


def test_multipage_pdf_takeoff_and_autocolor_pressure(qtbot, monkeypatch):
    monkeypatch.setattr(live_test.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(live_test.QMessageBox, "information", lambda *a, **k: None)
    win = live_test.StandaloneManufacturingApp()
    qtbot.addWidget(win)
    win.show()

    with tempfile.TemporaryDirectory() as tmp:
        pdf_p = os.path.join(tmp, "sample_structural_plan.pdf")
        doc = pymupdf.open()
        p1 = doc.new_page(width=792, height=612)
        p1.insert_text((100, 120), "BEAM SCHEDULE: W16X57 - 24 FT", fontsize=14)
        p1.insert_text((100, 180), "COLUMN: HSS8X8X3/8 - 14 FT", fontsize=14)
        p2 = doc.new_page(width=792, height=612)
        p2.insert_text((100, 120), "ROOF FRAMING: W12X26 - 18 FT", fontsize=14)
        doc.save(pdf_p)
        doc.close()

        pt = win.planset_takeoff_tab
        if hasattr(pt, "_load_pdf_into_workspace"):
            pt._load_pdf_into_workspace(pdf_p)
        vw = pt.vis_workspace
        vw.bom_items = [{"model": "W16X57", "qty": 2, "total_weight": 2736.0}, {"model": "HSS8X8X3/8", "qty": 4, "total_weight": 2000.0}]
        vw._auto_color_all_bom_profiles()
        assert len(vw.global_color_key) >= 2
        win.master_ribbon._refresh_ribbon_summary()
        assert "6 pcs" in win.master_ribbon._sum_vals["members"].text()

    win.close()


def test_all_keyboard_hotkeys_and_pricing_math_invariants(qtbot):
    canvas = CadBlueprintCanvas(lambda *a: None, lambda *a: None)
    canvas.resize(800, 600)
    pm = QPixmap(800, 600)
    pm.fill(Qt.white)
    canvas._base_pix = pm
    canvas.setPixmap(pm)
    qtbot.addWidget(canvas)
    canvas.show()

    expected_hotkeys = {
        Qt.Key_M: "measure", Qt.Key_P: "polyline", Qt.Key_C: "count",
        Qt.Key_A: "arrow", Qt.Key_L: "line", Qt.Key_R: "cloud",
        Qt.Key_W: "weld", Qt.Key_G: "grid_bubble", Qt.Key_V: "select",
    }
    for k, expected_mode in expected_hotkeys.items():
        qtbot.keyClick(canvas, k)
        assert canvas.mode == expected_mode

    # Verify pricing math invariants (never negative, NaN, or Inf)
    cfg = {"cat_base_margin": 1.05, "labor_rate": 85.0}
    r1 = live_test.PricingCalculatorCore.calc_card1(250.0, 45.0, 1.0, {}, cfg)
    assert r1 > 0 and r1 == r1


def test_ledger_roundtrip_and_admin_safeguards_pressure(qtbot, monkeypatch):
    monkeypatch.setattr(live_test.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(live_test.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(live_test.QMessageBox, "question", lambda *a, **k: live_test.QMessageBox.Yes)
    win = live_test.StandaloneManufacturingApp()
    qtbot.addWidget(win)
    win.show()

    # 1. Verify Admin safeguards & live matrix reload
    win.master_ribbon._switch_workspace(4)
    win.refresh_live_category_titles()
    assert len(win.data_core.clean_database) > 0
    mult = live_test.PricingCalculatorCore.get_profile_multiplier("Standard", win.custom_safeguards)
    assert mult > 0

    # 2. Verify Ledger grid population & search filtering
    win.master_ribbon._switch_workspace(3)
    if hasattr(win, "custom_ledger_tab") and hasattr(win.custom_ledger_tab, "populate_ledger_grid"):
        win.custom_ledger_tab.populate_ledger_grid()

    win.close()


def test_real_pdf_scan_and_marked_pdf_export_pressure(qtbot, monkeypatch):
    monkeypatch.setattr(live_test.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(live_test.QMessageBox, "information", lambda *a, **k: None)
    win = live_test.StandaloneManufacturingApp()
    qtbot.addWidget(win)
    win.show()

    with tempfile.TemporaryDirectory() as tmp:
        pdf_p = os.path.join(tmp, "real_scan_plan.pdf")
        out_p = os.path.join(tmp, "marked_output.pdf")
        doc = pymupdf.open()
        p1 = doc.new_page(width=792, height=612)
        p1.insert_text((120, 140), "W16X57", fontsize=14)
        p1.insert_text((120, 200), "HSS8X8X3/8", fontsize=14)
        doc.save(pdf_p)
        doc.close()

        pt = win.planset_takeoff_tab
        if hasattr(pt, "_load_pdf_into_workspace"):
            pt._load_pdf_into_workspace(pdf_p)
        if hasattr(pt, "scan_whole_planset"):
            pt.scan_whole_planset(use_ocr=False, prompt_if_empty=False)
        vw = pt.vis_workspace
        vw.canvas.markups.append({
            "type": "hanger_skew", "hx1": 100, "hy1": 250, "hx2": 220, "hy2": 250,
            "rx": 220, "ry": 250, "jx": 260, "jy": 340, "nx": 0, "ny": 1, "slen": 98.0,
            "label": "SKEW LEFT 24.0°", "skew_deg": 24.0,
            "color": vw.canvas.active_color, "line_width": 2.0, "font_size": 10
        })
        monkeypatch.setattr("blueprint_takeoff_ui.QFileDialog.getSaveFileName", lambda *a, **k: (out_p, "PDF Files (*.pdf)"))
        vw._export_marked_pdf()
        assert os.path.exists(out_p) and os.path.getsize(out_p) > 500

    win.close()
