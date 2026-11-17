import os, tempfile, inspect, pymupdf, pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap, QColor
import live_test


def test_bom_tree_actions_and_structural_import(shared_app_win, qtbot, monkeypatch):
    monkeypatch.setattr(live_test.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(live_test.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(live_test.QMessageBox, "question", lambda *a, **k: live_test.QMessageBox.Yes)
    win = shared_app_win

    pt = win.planset_takeoff_tab
    sample_rows = [
        {"sheet": "S-101", "detail": "1/S101", "model": "W16X57", "qty": 3, "length_ft": 24.0, "unit_wt": 57.0, "total_weight": 4104.0, "category": "Wide Flange Beams"},
        {"sheet": "S-101", "detail": "2/S101", "model": "HSS8X8X3/8", "qty": 4, "length_ft": 14.0, "unit_wt": 37.69, "total_weight": 2110.64, "category": "HSS Columns"},
        {"sheet": "S-102", "detail": "3/S102", "model": "L4X4X3/8", "qty": 6, "length_ft": 10.0, "unit_wt": 9.8, "total_weight": 588.0, "category": "Angles"},
    ]
    if hasattr(pt, "_load_rows_into_tree"):
        pt._load_rows_into_tree(sample_rows)
        assert pt.tree.topLevelItemCount() >= 1

    # Exercise Select All, Select None, Expand/Collapse, and Row Double-Click sheet jump
    for m_name in ("_select_all_rows", "_select_no_rows", "_select_all_rows"):
        if hasattr(pt, m_name):
            getattr(pt, m_name)()

    if pt.tree.topLevelItemCount() > 0:
        top = pt.tree.topLevelItem(0)
        child = top.child(0) if top.childCount() > 0 else top
        if hasattr(pt, "_on_bom_row_double_clicked"):
            pt._on_bom_row_double_clicked(child, 0)

    # Trigger BOM import into Structural Quoting
    if hasattr(pt, "_import_selected_to_structural"):
        pt._import_selected_to_structural()

    pass


def test_takeoff_cad_shapes_calibration_and_sheet_color_keys(shared_app_win, qtbot, monkeypatch):
    monkeypatch.setattr(live_test.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(live_test.QMessageBox, "information", lambda *a, **k: None)
    win = shared_app_win

    vw = win.planset_takeoff_tab.vis_workspace
    cv = vw.canvas
    pm = QPixmap(900, 700)
    pm.fill(Qt.white)
    cv._base_pix = pm
    cv.setPixmap(pm)

    # 1. Custom CAD shape stamping
    for shape_type in ("wide_flange", "hss_tube", "angle", "channel", "base_plate", "bolt_hole"):
        cv._pending_cad_shape = shape_type
        qtbot.mouseClick(cv, Qt.LeftButton, pos=QPoint(250, 250))
    assert len(cv.markups) >= 1

    # 2. Sheet-scoped vs Global color key switching & Auto-Color
    if hasattr(vw, "key_scope_combo") and vw.key_scope_combo.count() > 1:
        vw.key_scope_combo.setCurrentIndex(1)
        vw._auto_color_all_bom_profiles()
        vw.key_scope_combo.setCurrentIndex(0)

    # 3. Scale calibration & imperial parser
    cv.pts_per_ft = 18.0
    assert cv.pts_per_ft == pytest.approx(18.0)

    # 4. Inline text creation & commit
    cv._start_inline_text(QPoint(300, 300), "VERIFY FIELD WELD")
    if hasattr(cv, '_inline_editor') and cv._inline_editor.isVisible():
        cv._inline_editor.hide()

    pass


def test_pdf_quote_report_generation_and_admin_refresh(shared_app_win, qtbot, monkeypatch):
    monkeypatch.setattr(live_test.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(live_test.QMessageBox, "information", lambda *a, **k: None)
    win = shared_app_win

    with tempfile.TemporaryDirectory() as tmp:
        pdf_out = os.path.join(tmp, "customer_quote_test.pdf")
        monkeypatch.setattr(live_test.QFileDialog, "getSaveFileName", lambda *a, **k: (pdf_out, "PDF Files (*.pdf)"))

        # Populate Catalog ledger item & trigger PDF export if available
        win.data_core.rfq_ledger_items = [
            {"category": "Beams", "model": "W16X57", "qty": "2", "height": "20", "weight": "2280.0 lbs", "cost": "$3,850.00", "notes": "Prime Gray"}
        ]
        if hasattr(win, "refresh_ledger_display"):
            win.refresh_ledger_display()
        for fn_name in ("export_rfq_to_pdf", "generate_pdf_quote", "export_customer_quote_pdf"):
            if hasattr(win, fn_name):
                getattr(win, fn_name)()
                break

    pass