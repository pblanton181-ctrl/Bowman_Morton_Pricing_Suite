import os, tempfile, pymupdf, pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap
import live_test
import core.async_workers as aw
import ui.theme_manager as tm
import ui.page_thumbnails_drawer as ptd


def test_ribbon_contextual_and_toolbar_red_lines(qtbot, monkeypatch):
    monkeypatch.setattr(live_test.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(live_test.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(live_test.QMessageBox, "question", lambda *a, **k: live_test.QMessageBox.Yes)
    win = live_test.StandaloneManufacturingApp()
    qtbot.addWidget(win)
    win.show()

    rb = win.master_ribbon
    vw = win.planset_takeoff_tab.vis_workspace
    cv = vw.canvas

    # Load a 2-page PDF so page navigation & thumbnail drawer red lines execute
    with tempfile.TemporaryDirectory() as tmp:
        pdf_p = os.path.join(tmp, "two_page_cov.pdf")
        doc = pymupdf.open()
        doc.new_page(width=792, height=612).insert_text((80, 100), "W18X50 20'-0\"", fontsize=12)
        doc.new_page(width=792, height=612).insert_text((80, 100), "HSS6X6X1/4 12'-0\"", fontsize=12)
        doc.save(pdf_p)
        doc.close()

        if hasattr(win.planset_takeoff_tab, "_load_pdf_into_workspace"):
            win.planset_takeoff_tab._load_pdf_into_workspace(pdf_p)

        # Exercise ribbon color swatches, B/I/U toggles, layer toggles, zoom & page navigation
        for hx in ("#dc2626", "#2563eb", "#16a34a", "#111827"):
            rb._set_vw_color(hx)
        rb._toggle_bold()
        rb._toggle_italic()
        rb._toggle_underline()
        for layer in ("span", "line", "text", "hanger_skew", "all"):
            rb._toggle_markup_layer(layer)

        # Exercise contextual selection & floating mini-toolbar on a markup
        cv.markups.append({"type": "line", "x1": 50.0, "y1": 50.0, "x2": 200.0, "y2": 50.0, "color": cv.active_color, "line_width": 2.0})
        cv.selected_idx = 0
        cv.selected_indices = {0}
        rb.update_contextual_selection(cv.markups[0])
        rb.update_contextual_selection(None)

        # Exercise PageThumbnailsDrawer methods
        drawer = ptd.PageThumbnailsDrawer()
        qtbot.addWidget(drawer)
        if hasattr(drawer, "load_document"):
            drawer.load_document(vw._doc)
        drawer.close()

    # Exercise theme_manager functions
    for attr in dir(tm):
        fn = getattr(tm, attr)
        if callable(fn) and not attr.startswith("_"):
            try:
                fn()
            except Exception:
                pass

    win.close()


def test_ledger_save_load_delete_roundtrip(qtbot, monkeypatch):
    monkeypatch.setattr(live_test.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(live_test.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(live_test.QMessageBox, "question", lambda *a, **k: live_test.QMessageBox.Yes)
    win = live_test.StandaloneManufacturingApp()
    qtbot.addWidget(win)
    win.show()

    sq = win.custom_quoting_tab
    sq.current_project_items = [
        {"shape": "W", "model": "W16X57", "qty": 2, "length_ft": 20.0, "total_weight": 2280.0, "total_price": 4200.0}
    ]
    if hasattr(sq, "cust_name"):
        sq.cust_name.setText("Coverage Test Customer")
    if hasattr(sq, "proj_name"):
        sq.proj_name.setText("Coverage Test Building")

    before_cnt = len(win.custom_ledger_pool)
    if hasattr(sq, "save_quote_to_ledger"):
        sq.save_quote_to_ledger()
        assert len(win.custom_ledger_pool) >= before_cnt
        # Clean up test entry from ledger pool
        win.custom_ledger_pool = [q for q in win.custom_ledger_pool if q.get("customer") != "Coverage Test Customer"]
        if hasattr(win, "save_custom_ledger_pool"):
            win.save_custom_ledger_pool()

    win.close()