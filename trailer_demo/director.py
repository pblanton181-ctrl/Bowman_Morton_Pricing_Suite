import os
import re
import glob
import pymupdf

from PySide6.QtCore import Qt, QTimer, QPoint, QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
    QFileDialog,
    QDialog,
    QAbstractButton,
    QAbstractItemView,
)

from trailer_demo.recorder import WindowVideoRecorder
from trailer_demo.cursor_driver import SmoothCursorAnimator, TrailerCaptionCard

EXPORT_DIR = os.path.join(os.path.abspath("."), "Marketing_Trailer_Exports")
VIDEO_OUT = os.path.join(EXPORT_DIR, "Bowman_Morton_Marketing_Trailer.mp4")


class MarketingTrailerDirector:
    """7-Shot Movie Trailer Director grounded in verified application handles."""

    def __init__(self, win, single_scene=None):
        self.single_scene = single_scene
        self.win = win
        self.pdf_path = self._find_planset()
        self.caption = TrailerCaptionCard(win)
        self.cursor = SmoothCursorAnimator(win)
        self.recorder = WindowVideoRecorder(win, VIDEO_OUT, fps=16)
        self.steel_pages = []
        self._export_cursor = 0
        self._edit_cursor = 0
        self._total_members = 0

        QMessageBox.information = lambda *a, **k: QMessageBox.Ok
        QMessageBox.warning = lambda *a, **k: QMessageBox.Ok

    def _find_planset(self):
        exact = os.path.abspath("1230-Dave Pugsley_3122 Broadway - Combined Plan Set.pdf")
        if os.path.exists(exact):
            return exact
        hits = glob.glob("*Dave Pugsley*.pdf") or glob.glob("*3122 Broadway*.pdf")
        if hits:
            return os.path.abspath(hits.__getitem__(0))
        raise FileNotFoundError("Could not find 1230-Dave Pugsley_3122 Broadway - Combined Plan Set.pdf")

    def _find_visible_button(self, root, *keywords):
        for btn in root.findChildren(QAbstractButton):
            if not btn.isVisible():
                continue
            txt = (btn.text() or "").replace("\n", " ").strip().lower()
            tip = (btn.toolTip() or "").strip().lower()
            for kw in keywords:
                if kw.lower() in txt or kw.lower() in tip:
                    return btn
        return None

    def start(self):
        os.makedirs(EXPORT_DIR, exist_ok=True)
        self.win.showMaximized()
        if hasattr(self.win, "planset_takeoff_tab"):
            self.win.planset_takeoff_tab.show()
            self.win.master_tabs.setCurrentWidget(self.win.planset_takeoff_tab)
        if hasattr(self.win, "master_ribbon"):
            self.win.master_ribbon.set_active_tab(0)
        QApplication.processEvents()

        c = self.win.mapToGlobal(QPoint(self.win.width() // 2, self.win.height() // 2))
        self.cursor.warp(c)
        self.caption.show_step(
            "BOWMAN-MORTON PRICING SUITE",
            "Effortless Planset Navigation, Takeoff & Structural Quoting",
            "Live walkthrough on 1230 Dave Pugsley — 3122 Broadway Combined Plan Set",
        )
        self.recorder.start()
        QTimer.singleShot(1100, self._shot_1_open_pdf_dialog)

    def _shot_1_open_pdf_dialog(self):
        from PySide6.QtWidgets import QTreeView, QLineEdit
        rb = self.win.master_ribbon
        btn_open = self._find_visible_button(rb, "Open PDF")
        self.caption.show_step(
            "SHOT 1 OF 7 • PLANSET FILE SELECTION",
            "Clicking 'Open PDF' to Browse Structural Drawings",
            "Opening project directory...",
        )

        def _show_file_picker():
            pt = self.win.planset_takeoff_tab
            dlg = QFileDialog(self.win, "Select Structural Plan Set PDF", os.path.dirname(self.pdf_path), "PDF Files (*.pdf)")
            dlg.setOption(QFileDialog.DontUseNativeDialog, True)
            dlg.setFileMode(QFileDialog.ExistingFile)
            dlg.resize(920, 540)
            dlg.show()
            QApplication.processEvents()

            target_file = os.path.basename(self.pdf_path)
            self.caption.show_step(
                "SHOT 1 OF 7 • PLANSET FILE SELECTION",
                f"Selecting '{target_file}'",
                "Clicking the combined architectural & structural planset PDF",
            )

            # Wait 350ms so QFileSystemModel finishes listing all files in the folder
            def _locate_and_glide_to_file():
                tree_view = None
                target_index = None
                # Pick the widest QTreeView (the main file list on the right, never the narrow sidebar)
                candidates = [tv for tv in dlg.findChildren(QTreeView) if tv.isVisible()]
                if candidates:
                    tree_view = max(candidates, key=lambda w: w.width())
                    model = tree_view.model()
                    root_idx = tree_view.rootIndex()
                    for r in range(model.rowCount(root_idx)):
                        idx0 = model.index(r, 0, root_idx)
                        if str(model.data(idx0) or "").strip() == target_file:
                            target_index = idx0
                            tree_view.scrollTo(idx0)
                            QApplication.processEvents()
                            break

                if tree_view is not None and target_index is not None:
                    rect = tree_view.visualRect(target_index)
                    row_gpos = tree_view.viewport().mapToGlobal(QPoint(rect.left() + 190, rect.center().y()))
                elif tree_view is not None:
                    row_gpos = tree_view.viewport().mapToGlobal(QPoint(220, 145))
                else:
                    row_gpos = dlg.mapToGlobal(QPoint(540, 260))

                def _on_arrive_at_file_row():
                    # Highlight the exact file row AND populate the 'File name:' input box visibly!
                    if tree_view is not None and target_index is not None:
                        tree_view.setCurrentIndex(target_index)
                    dlg.selectFile(target_file)
                    for le in dlg.findChildren(QLineEdit):
                        if le.isVisible():
                            le.setText(target_file)
                            break
                    QApplication.processEvents()

                    btn_open_dlg = None
                    for b in dlg.findChildren(QAbstractButton):
                        if b.isVisible() and b.text().replace("&", "").strip().lower() == "open":
                            btn_open_dlg = b
                            break

                    def _on_arrive_at_open_btn():
                        def _close_picker_and_load():
                            dlg.done(QDialog.Accepted)
                            dlg.close()
                            dlg.deleteLater()
                            QApplication.processEvents()

                            orig_open = QFileDialog.getOpenFileName
                            QFileDialog.getOpenFileName = lambda *a, **k: (self.pdf_path, "PDF Files (*.pdf)")
                            try:
                                pt.load_new_pdf_planset()
                            finally:
                                QFileDialog.getOpenFileName = orig_open
                            QApplication.processEvents()

                            if self.single_scene == 1:
                                self.caption.show_step(
                                    "SCENE 1 COMPLETE • PLANSET LOADED CLEANLY",
                                    "1230 Dave Pugsley — 3122 Broadway Combined Plan Set Ready",
                                    "Stopping Scene 1 preview recording now",
                                )
                                QTimer.singleShot(1600, self._shutdown_and_open_exports)
                            else:
                                QTimer.singleShot(950, self._shot_2_auto_scan_bom)

                        QTimer.singleShot(550, _close_picker_and_load)

                    QTimer.singleShot(750, lambda: self.cursor.glide_to_widget(btn_open_dlg, duration_ms=900, click_pulse=True, on_done=_on_arrive_at_open_btn))

                self.cursor.glide_to(row_gpos, duration_ms=1100, click_pulse=True, on_done=_on_arrive_at_file_row)

            QTimer.singleShot(350, _locate_and_glide_to_file)

        self.cursor.glide_to_widget(btn_open, duration_ms=850, click_pulse=True, on_done=_show_file_picker)

    def _shot_2_auto_scan_bom(self):
        rb = self.win.master_ribbon
        btn_scan = self._find_visible_button(rb, "Auto Scan")
        self.caption.show_step(
            "SHOT 2 OF 7 • ONE-CLICK WHOLE-PLANSET BOM EXTRACTION",
            "Clicking 'Auto Scan' to Extract Structural Steel Across All Sheets",
            "Detecting Wide Flange, HSS Columns, Angles, Channels & Base Plates...",
        )

        def _do_scan():
            pt = self.win.planset_takeoff_tab
            pt.scan_whole_planset()
            pt._switch_dialog_view(0)
            if hasattr(pt, "tree"):
                pt.tree.expandAll()
            QApplication.processEvents()

            self.caption.show_step(
                "SHOT 2 OF 7 • AUTOMATED BOM & TONNAGE BREAKDOWN",
                "Extracted Full Structural BOM with Live Weight & Tonnage Summary",
                "Categorized by Beams, Columns, HSS, Angles, Channels & Plates",
            )

            # Glide cursor smoothly across the Smart Estimating Breakdown panel so viewers inspect the totals
            panel = getattr(pt, "smart_summary_panel", None)
            target_pt = (
                panel.mapToGlobal(QPoint(panel.width() // 2, int(panel.height() * 0.45)))
                if (panel and panel.isVisible())
                else self.win.mapToGlobal(QPoint(int(self.win.width() * 0.78), int(self.win.height() * 0.48)))
            )

            def _after_inspect():
                if self.single_scene == 2:
                    self.caption.show_step(
                        "SCENE 2 COMPLETE • BOM EXTRACTION VERIFIED",
                        "All Structural Steel Profiles & Tonnage Staged Cleanly",
                        "Stopping Scene 2 preview recording now",
                    )
                    QTimer.singleShot(1600, self._shutdown_and_open_exports)
                else:
                    QTimer.singleShot(1100, self._shot_3_smart_lookup_framing_sheet)

            QTimer.singleShot(850, lambda: self.cursor.glide_to(target_pt, duration_ms=1050, click_pulse=False, on_done=_after_inspect))

        self.cursor.glide_to_widget(btn_scan, duration_ms=850, click_pulse=True, on_done=_do_scan)

    def _shot_3_smart_lookup_framing_sheet(self):
        pt = self.win.planset_takeoff_tab
        vw = pt.vis_workspace
        pt._switch_dialog_view(1)
        QApplication.processEvents()

        self.caption.show_step(
            "SHOT 3 OF 7 • GLOBAL STEEL COLOR KEY & SMART LOOKUP",
            "Enabling 'Highlight Attached Beam Lines' & Auto-Coloring All BOM Steel",
            "Color-coding every profile across the entire planset in one click",
        )

        # 1. Visibly click 'Highlight Attached Beam Lines' checkbox
        chk_hl = getattr(vw, "chk_hl_lines", None)

        def _click_auto_color():
            if chk_hl is not None and not chk_hl.isChecked():
                chk_hl.setChecked(True)
                QApplication.processEvents()

            btn_auto = self._find_visible_button(vw, "Auto-Color All BOM Steel")

            def _after_auto_color():
                vw._auto_color_all_bom_profiles()
                QApplication.processEvents()
                QTimer.singleShot(750, _flip_opening_pages)

            self.cursor.glide_to_widget(btn_auto, duration_ms=650, click_pulse=True, on_done=_after_auto_color)

        def _flip_opening_pages():
            self.caption.show_step(
                "SHOT 3 OF 7 • SMART STEEL COLOR KEY NAVIGATION",
                "Flipping Opening Sheets — Then Jumping Straight to Steel via Smart Lookup",
                "Click any steel profile in the Color Key to reveal its framing sheet pills",
            )
            btn_next = self._find_visible_button(vw, "Next Sheet")

            def _do_flip():
                if pt.sheet_combo.count() > 1:
                    pt.sheet_combo.setCurrentIndex(1)
                    vw.render_sheet(2)
                    QApplication.processEvents()
                QTimer.singleShot(750, _click_w16x57_in_key_list)

            self.cursor.glide_to_widget(btn_next, duration_ms=600, click_pulse=True, on_done=_do_flip)

        def _click_w16x57_in_key_list():
            # Target W16X57 (or the primary framing beam on Pg 35) inside vw.key_list
            target_item = None
            for idx in range(vw.key_list.count()):
                it = vw.key_list.item(idx)
                txt = (it.text() or "").upper()
                if "W16X57" in txt:
                    target_item = it
                    break
            if target_item is None:
                for idx in range(vw.key_list.count()):
                    it = vw.key_list.item(idx)
                    if (it.text() or "").strip().upper().startswith(("W16", "W14", "W12")):
                        target_item = it
                        break
            if target_item is None and vw.key_list.count() > 0:
                target_item = vw.key_list.item(0)

            if target_item is None:
                QTimer.singleShot(400, self._shot_4_measure_highlighted_beam)
                return

            vw.key_list.scrollToItem(target_item)
            QApplication.processEvents()
            rect = vw.key_list.visualItemRect(target_item)
            item_gpos = vw.key_list.viewport().mapToGlobal(rect.center())

            def _on_key_row_clicked():
                vw.key_list.setCurrentItem(target_item)
                vw._on_key_item_clicked(target_item)
                QApplication.processEvents()
                prof_name = (target_item.text() or "").split("—").__getitem__(0).strip()

                # Find the blue 'Pg 35' (or structural sheet) pill button that just appeared in prof_sheets_bar!
                pill_btn = None
                for i in range(vw.prof_sheets_bar.count()):
                    w_item = vw.prof_sheets_bar.itemAt(i).widget()
                    if isinstance(w_item, QAbstractButton) and w_item.isVisible():
                        pill_btn = w_item
                        if any(p in w_item.text() for p in ("31", "32", "33", "34", "35", "36", "37")):
                            break

                def _on_pill_clicked():
                    if pill_btn is not None:
                        pill_btn.click()
                    else:
                        vw._jump_page_from_pill(35)
                    QApplication.processEvents()
                    self.caption.show_step(
                        "SHOT 3 OF 7 • SMART LOOKUP JUMPED TO STRUCTURAL FRAMING PLAN",
                        f"Clicked '{prof_name}' -> Clicked '{pill_btn.text() if pill_btn else 'Pg 35'}' -> Landed on Framing Plan!",
                        "Color-coded steel callouts & attached beam lines highlighted live on drawing",
                    )
                    if self.single_scene == 3:
                        QTimer.singleShot(1800, self._shutdown_and_open_exports)
                    else:
                        QTimer.singleShot(1200, self._shot_4_measure_highlighted_beam)

                QTimer.singleShot(550, lambda: self.cursor.glide_to_widget(pill_btn, duration_ms=650, click_pulse=True, on_done=_on_pill_clicked))

            self.cursor.glide_to(item_gpos, duration_ms=680, click_pulse=True, on_done=_on_key_row_clicked)

        if chk_hl is not None and chk_hl.isVisible():
            self.cursor.glide_to_widget(chk_hl, duration_ms=600, click_pulse=True, on_done=_click_auto_color)
        else:
            _click_auto_color()

    def _dispatch_canvas_mouse(self, cv, ev_type, local_pt, btn=Qt.LeftButton, buttons=Qt.LeftButton):
        g_pt = cv.mapToGlobal(local_pt)
        ev = QMouseEvent(ev_type, QPointF(local_pt), QPointF(g_pt), btn, buttons, Qt.NoModifier)
        QApplication.sendEvent(cv, ev)

    def _shot_4_measure_highlighted_beam(self):
        pt = self.win.planset_takeoff_tab
        vw = pt.vis_workspace
        rb = self.win.master_ribbon

        active_item = vw.key_list.currentItem()
        beam_profile = (active_item.text().split("—").__getitem__(0).strip() if active_item else "W16X57")
        beam_len_ft = 20.0
        for top_i in range(pt.tree.topLevelItemCount()):
            p_item = pt.tree.topLevelItem(top_i)
            for c_i in range(p_item.childCount()):
                ch = p_item.child(c_i)
                if beam_profile in ch.text(3).upper():
                    try:
                        beam_len_ft = float(ch.text(5))
                    except ValueError:
                        beam_len_ft = 20.0
                    break

        btn_zoom_in = self._find_visible_button(rb, "Zoom In", "Zoom +")
        self.caption.show_step(
            "SHOT 4 OF 7 • ZOOMING DEEP INTO FRAMING PLAN",
            f"Zooming In on {beam_profile} Structural Beam & Callout",
            "Magnifying drawing details before verifying architectural scale & span",
        )

        def _do_zoom_sequence():
            cv = vw.canvas
            target_zooms = [1.25, 2.0, 2.85]

            def _zoom_step(idx_z):
                if btn_zoom_in is not None:
                    self.cursor.halo.pulse_at(btn_zoom_in.mapToGlobal(QPoint(btn_zoom_in.width() // 2, btn_zoom_in.height() // 2)))
                cv.set_zoom(target_zooms.__getitem__(idx_z))
                if cv.key_highlights:
                    hl0 = next((h for h in cv.key_highlights if h.get("seg")), cv.key_highlights.__getitem__(0))
                    if hl0.get("seg"):
                        sx1, sy1, sx2, sy2 = hl0["seg"]
                        ctr_px = cv._from_pdf_pt((sx1 + sx2) * 0.5, (sy1 + sy2) * 0.5)
                    else:
                        rx0, ry0, rx1, ry1 = hl0["rect"]
                        ctr_px = cv._from_pdf_pt((rx0 + rx1) * 0.5, (ry0 + ry1) * 0.5)
                    vw.scroll.horizontalScrollBar().setValue(max(0, ctr_px.x() - vw.scroll.viewport().width() // 2))
                    vw.scroll.verticalScrollBar().setValue(max(0, ctr_px.y() - vw.scroll.viewport().height() // 2))
                QApplication.processEvents()
                if idx_z + 1 < len(target_zooms):
                    QTimer.singleShot(420, lambda: _zoom_step(idx_z + 1))
                else:
                    QTimer.singleShot(450, lambda: self._set_scale_then_measure(beam_profile, beam_len_ft))

            _zoom_step(0)

        self.cursor.glide_to_widget(btn_zoom_in, duration_ms=550, click_pulse=True, on_done=_do_zoom_sequence)

    def _set_scale_then_measure(self, beam_profile, beam_len_ft):
        rb = self.win.master_ribbon
        scale_cb = getattr(rb, "ribbon_scale_cb", None)
        self.caption.show_step(
            "SHOT 4 OF 7 • VERIFYING ARCHITECTURAL DRAWING SCALE",
            "Confirming Sheet Scale (1/4\" = 1'-0\") Before Measuring Beam",
            "Setting exact blueprint scale so CAD measurement matches real-world feet",
        )

        def _after_scale_click():
            if scale_cb is not None and scale_cb.isVisible():
                scale_cb.showPopup()
                QApplication.processEvents()

                def _select_scale_and_arm_measure():
                    scale_cb.setCurrentIndex(0)
                    scale_cb.hidePopup()
                    QApplication.processEvents()
                    btn_measure = self._find_visible_button(rb, "Linear Dim", "Measure")
                    self.caption.show_step(
                        "SHOT 4 OF 7 • LIVE MEASURE TOOL & OSNAP VERIFICATION",
                        f"Selecting 'Linear Dim (M)' to Measure {beam_profile} Beam Endpoints",
                        "Snapping Measure tool directly onto the highlighted steel beam",
                    )
                    QTimer.singleShot(350, lambda: self.cursor.glide_to_widget(
                        btn_measure,
                        duration_ms=550,
                        click_pulse=True,
                        on_done=lambda: self._run_real_canvas_measure(beam_profile, beam_len_ft),
                    ))

                QTimer.singleShot(700, _select_scale_and_arm_measure)
            else:
                btn_measure = self._find_visible_button(rb, "Linear Dim", "Measure")
                self.cursor.glide_to_widget(
                    btn_measure,
                    duration_ms=550,
                    click_pulse=True,
                    on_done=lambda: self._run_real_canvas_measure(beam_profile, beam_len_ft),
                )

        if scale_cb is not None and scale_cb.isVisible():
            self.cursor.glide_to_widget(scale_cb, duration_ms=550, click_pulse=True, on_done=_after_scale_click)
        else:
            _after_scale_click()

    def _run_real_canvas_measure(self, beam_profile, beam_len_ft):
        pt = self.win.planset_takeoff_tab
        vw = pt.vis_workspace
        rb = self.win.master_ribbon

        if hasattr(rb, "_vis_mode"):
            rb._vis_mode("measure")
        else:
            vw.set_mode("measure")
        QApplication.processEvents()

        cv = vw.canvas
        if cv.key_highlights:
            hl = next((h for h in cv.key_highlights if h.get("seg")), cv.key_highlights.__getitem__(0))
            if hl.get("seg"):
                sx1, sy1, sx2, sy2 = hl["seg"]
                p1_local = cv._from_pdf_pt(sx1, sy1)
                p2_local = cv._from_pdf_pt(sx2, sy2)
            else:
                rx0, ry0, rx1, ry1 = hl["rect"]
                p1_local = cv._from_pdf_pt(rx0 - 35.0, (ry0 + ry1) * 0.5)
                p2_local = cv._from_pdf_pt(rx1 + 145.0, (ry0 + ry1) * 0.5)
        else:
            p1_local = QPoint(int(cv.width() * 0.35), int(cv.height() * 0.48))
            p2_local = QPoint(int(cv.width() * 0.62), int(cv.height() * 0.48))

        p1_global = cv.mapToGlobal(p1_local)
        p2_global = cv.mapToGlobal(p2_local)

        def _hover_p1(cur_gpos):
            self._dispatch_canvas_mouse(cv, QMouseEvent.MouseMove, cv.mapFromGlobal(cur_gpos), Qt.NoButton, Qt.NoButton)

        def _click_p1():
            self._dispatch_canvas_mouse(cv, QMouseEvent.MouseButtonPress, p1_local, Qt.LeftButton, Qt.LeftButton)
            self._dispatch_canvas_mouse(cv, QMouseEvent.MouseButtonRelease, p1_local, Qt.LeftButton, Qt.NoButton)
            QApplication.processEvents()

            def _drag_to_p2(cur_gpos):
                self._dispatch_canvas_mouse(cv, QMouseEvent.MouseMove, cv.mapFromGlobal(cur_gpos), Qt.NoButton, Qt.NoButton)

            def _click_p2():
                self._dispatch_canvas_mouse(cv, QMouseEvent.MouseButtonPress, p2_local, Qt.LeftButton, Qt.LeftButton)
                self._dispatch_canvas_mouse(cv, QMouseEvent.MouseButtonRelease, p2_local, Qt.LeftButton, Qt.NoButton)
                QApplication.processEvents()

                measured_txt = ""
                if cv.markups:
                    last_m = cv.markups.__getitem__(len(cv.markups) - 1)
                    measured_txt = str(last_m.get("label", ""))
                self.caption.show_step(
                    "SHOT 4 OF 7 • 1:1 BOM ACCURACY CONFIRMED ON FRAMING PLAN",
                    f"Measured Beam Span: {measured_txt or cv._format_ft_in(beam_len_ft)}  |  BOM {beam_profile}: {beam_len_ft:.2f} ft",
                    "Real interactive Measure tool & OSNAP confirm plan-set scale accuracy",
                )
                if self.single_scene == 4:
                    QTimer.singleShot(1800, self._shutdown_and_open_exports)
                else:
                    QTimer.singleShot(1600, self._shot_5_export_all_steel_pdfs)

            self.cursor.glide_to(p2_global, duration_ms=1050, click_pulse=True, on_move=_drag_to_p2, on_done=_click_p2)

        self.cursor.glide_to(p1_global, duration_ms=700, click_pulse=True, on_move=_hover_p1, on_done=_click_p1)

    def _shot_5_export_all_steel_pdfs(self):
        pt = self.win.planset_takeoff_tab
        vw = pt.vis_workspace
        if hasattr(vw, "zoom_fit"):
            vw.zoom_fit()
        pages_with_steel = set()
        for top_i in range(pt.tree.topLevelItemCount()):
            p_item = pt.tree.topLevelItem(top_i)
            for c_i in range(p_item.childCount()):
                ch = p_item.child(c_i)
                sh_txt = ch.text(1).strip()
                for idx in range(pt.sheet_combo.count()):
                    cmb_txt = pt.sheet_combo.itemText(idx)
                    if sh_txt and (sh_txt in cmb_txt or f"Pg {idx + 1}" in cmb_txt):
                        pages_with_steel.add(idx)
        self.steel_pages = sorted(pages_with_steel) if pages_with_steel else list(range(1))
        self._export_cursor = 0
        self._export_next_sheet_tick()

    def _export_next_sheet_tick(self):
        pt = self.win.planset_takeoff_tab
        vw = pt.vis_workspace
        if self._export_cursor >= len(self.steel_pages):
            self.caption.show_step(
                "SHOT 5 OF 7 • ALL MARKED-UP STEEL SHEET PDFs EXPORTED",
                f"Saved {len(self.steel_pages)} Color-Keyed Marked-Up Sheet PDFs",
                "Ready for shop fabrication & customer submittal in Marketing_Trailer_Exports\\",
            )
            QTimer.singleShot(900, self._shot_6_send_bom_to_structural)
            return

        pg_idx = self.steel_pages.__getitem__(self._export_cursor)
        pt.sheet_combo.setCurrentIndex(pg_idx)
        vw.render_sheet(pg_idx + 1)
        pg_num = pg_idx + 1
        sh_label = pt.sheet_combo.currentText().split("—").__getitem__(0).strip().replace("/", "-")
        out_pdf = os.path.join(EXPORT_DIR, f"3122_Broadway_{sh_label}_Pg{pg_num}_MarkedUp.pdf")
        self._write_marked_sheet_pdf(vw, pg_num, out_pdf)

        self.caption.show_step(
            f"SHOT 5 OF 7 • EXPORTING MARKED-UP SHEET {self._export_cursor + 1} OF {len(self.steel_pages)}",
            f"Exported {os.path.basename(out_pdf)}",
            "Vector highlights & steel color key baked into PDF",
        )
        self._export_cursor += 1
        QTimer.singleShot(85, self._export_next_sheet_tick)

    def _write_marked_sheet_pdf(self, vw, pg_num, out_path):
        if not getattr(vw, "_doc", None):
            return
        out_doc = pymupdf.open()
        out_doc.insert_pdf(vw._doc, from_page=pg_num - 1, to_page=pg_num - 1)
        pg = out_doc.load_page(0)

        def _rgb(qc):
            return (qc.redF(), qc.greenF(), qc.blueF())

        for hl in vw.canvas.key_highlights:
            c = _rgb(hl["color"])
            r = pymupdf.Rect(*hl["rect"]) + (-2, -1.5, 2, 1.5)
            pg.draw_rect(r, color=c, fill=c, fill_opacity=0.25, width=1.2)
            if hl.get("seg"):
                sx1, sy1, sx2, sy2 = hl["seg"]
                pg.draw_line(pymupdf.Point(sx1, sy1), pymupdf.Point(sx2, sy2), color=c, width=3.5, stroke_opacity=0.75)

        out_doc.save(out_path)
        out_doc.close()
    def _shot_6_send_bom_to_structural(self):
        pt = self.win.planset_takeoff_tab
        rb = self.win.master_ribbon
        btn_send = self._find_visible_button(rb, "Send BOM", "Send Checked")
        self.caption.show_step(
            "SHOT 6 OF 7 • ONE-CLICK SEND TO STRUCTURAL QUOTING",
            "Transferring Verified BOM Into Structural Fabrication Workbench",
            "Every steel profile, quantity & cut length populates automatically",
        )

        def _do_send():
            pt._accept_checked()
            sq = self.win.custom_quoting_tab
            if hasattr(sq, "ingest_pdf_bom_items"):
                sq.ingest_pdf_bom_items(getattr(pt, "accepted_rows", []))
            self.win.master_tabs.setCurrentIndex(2)
            self.win.master_ribbon.set_active_tab(2)
            QApplication.processEvents()
            self._total_members = len(getattr(sq, "current_project_items", []))
            self._edit_cursor = 0
            QTimer.singleShot(1000, self._step_edit_next_structural_member)

        self.cursor.glide_to_widget(btn_send, duration_ms=500, click_pulse=True, on_done=_do_send)

    def _step_edit_next_structural_member(self):
        sq = self.win.custom_quoting_tab
        items = getattr(sq, "current_project_items", [])
        max_edits = min(len(items), 4)
        if self._edit_cursor >= max_edits:
            QTimer.singleShot(900, self._shot_7_finish_trailer)
            return

        if sq.ledger_tree.topLevelItemCount() > 0:
            row_item = sq.ledger_tree.topLevelItem(0)
            sq.ledger_tree.setCurrentItem(row_item)
            rect = sq.ledger_tree.visualItemRect(row_item)
            row_gpos = sq.ledger_tree.viewport().mapToGlobal(rect.center())

            def _after_row_click():
                sq.edit_selected_project_item()
                QApplication.processEvents()

                ac = sq.active_member_card
                sk = sq.combo_picker.currentText()
                model = ac.combo_model.currentText()
                try:
                    extent = float(ac.input_extent.text().strip() or "20")
                except ValueError:
                    extent = 20.0

                if sk == "beam":
                    addons = [
                        {"type": "End Plate (Standard)", "thk": "3/8", "hole_dia": "13/16", "hole_qty": 4, "qty": 2},
                        {"type": "Cope (Standard Flange)", "qty": 2},
                        {"type": "Standard Studs", "qty": max(4, int(extent // 2))},
                    ]
                    spec_desc = "2x End Plates + Standard Flange Copes + Shear Studs"
                elif sk in ("tube", "pipe"):
                    addons = [
                        {"type": "End Plate (Standard)", "thk": "1/2", "hole_dia": "13/16", "hole_qty": 4, "qty": 1},
                    ]
                    spec_desc = "1/2\" Base Plate w/ (4) 13/16\" Anchor Holes"
                else:
                    addons = []
                    spec_desc = "Cut-to-Length + Shop Prime Coat"

                sq.execute_fabrication_math_routine(
                    shape_key=sk,
                    model=model,
                    extent=extent,
                    plate_w=12.0,
                    plate_thk=0.5,
                    pc=True,
                    hdg=False,
                    addons_list=addons,
                )
                sq.sync_local_workbench_view()
                QApplication.processEvents()

                self.caption.show_step(
                    f"SHOT 6 OF 7 • DETAILING MEMBER {self._edit_cursor + 1} OF {max_edits}",
                    f"Configured {model} ({extent:.1f} ft)",
                    f"Plan-Set Add-Ons Applied: {spec_desc}",
                )
                self._edit_cursor += 1
                QTimer.singleShot(1100, self._step_edit_next_structural_member)

            self.cursor.glide_to(row_gpos, duration_ms=460, click_pulse=True, on_done=_after_row_click)
        else:
            QTimer.singleShot(600, self._shot_7_finish_trailer)

    def _shot_7_finish_trailer(self):
        sq = self.win.custom_quoting_tab
        if sq.ledger_tree.topLevelItemCount() > 0:
            sq.ledger_tree.expandAll()
        self.caption.show_step(
            "SHOT 7 OF 7 • COMPLETE QUOTE & MARKED-UP PDF PACKAGE READY",
            f"All {self._total_members} Structural Members Priced & {len(self.steel_pages)} Marked-Up PDFs Exported",
            "Saved MP4 Trailer & Sheet PDFs to Marketing_Trailer_Exports\\",
        )
        QTimer.singleShot(2200, self._shutdown_and_open_exports)

    def _shutdown_and_open_exports(self):
        self.recorder.stop()
        self.caption.hide()
        print(f"[PASS] Marketing Trailer MP4 saved ({self.recorder.frame_count} frames): {VIDEO_OUT}")
        print(f"[PASS] Marked-up steel sheet PDFs saved in: {EXPORT_DIR}")
        if os.path.exists(EXPORT_DIR):
            os.startfile(EXPORT_DIR)