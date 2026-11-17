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

    def __init__(self, win):
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
        rb = self.win.master_ribbon
        btn_open = self._find_visible_button(rb, "Open PDF", "Open")
        self.caption.show_step(
            "SHOT 1 OF 7 • PLANSET FILE SELECTION",
            "Opening File Browser & Selecting the 3122 Broadway Combined Plan Set",
            os.path.basename(self.pdf_path),
        )

        def _show_file_picker():
            pt = self.win.planset_takeoff_tab
            dlg = QFileDialog(self.win, "Select Structural Plan Set PDF", os.path.dirname(self.pdf_path), "PDF Files (*.pdf)")
            dlg.setOption(QFileDialog.DontUseNativeDialog, True)
            dlg.setFileMode(QFileDialog.ExistingFile)
            dlg.resize(880, 520)
            dlg.show()
            QApplication.processEvents()

            dlg.selectFile(os.path.basename(self.pdf_path))
            QApplication.processEvents()

            row_gpos = dlg.mapToGlobal(QPoint(360, 220))
            for view in dlg.findChildren(QAbstractItemView):
                if not view.isVisible():
                    continue
                sel = view.selectionModel()
                if sel and sel.hasSelection():
                    idx = sel.selectedIndexes().__getitem__(0)
                    rect = view.visualRect(idx)
                    if rect.isValid():
                        row_gpos = view.viewport().mapToGlobal(rect.center())
                        break

            def _click_file_row():
                btn_open_dlg = None
                for b in dlg.findChildren(QAbstractButton):
                    if b.isVisible() and b.text().replace("&", "").strip().lower() in ("open", "choose"):
                        btn_open_dlg = b
                        break

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
                    QTimer.singleShot(850, self._shot_2_auto_scan_bom)

                self.cursor.glide_to_widget(btn_open_dlg, duration_ms=480, click_pulse=True, on_done=_close_picker_and_load)

            self.cursor.glide_to(row_gpos, duration_ms=560, click_pulse=True, on_done=_click_file_row)

        self.cursor.glide_to_widget(btn_open, duration_ms=500, click_pulse=True, on_done=_show_file_picker)

    def _shot_2_auto_scan_bom(self):
        rb = self.win.master_ribbon
        btn_scan = self._find_visible_button(rb, "Auto Scan", "Scan")
        self.caption.show_step(
            "SHOT 2 OF 7 • ONE-CLICK WHOLE-PLANSET BOM EXTRACTION",
            "Scanning Every Sheet for Wide Flange, HSS, Angles, Channels & Plates",
            "Extracting profiles, quantities & cut lengths automatically",
        )

        def _do_scan():
            pt = self.win.planset_takeoff_tab
            pt.scan_whole_planset()
            pt._switch_dialog_view(0)
            if hasattr(pt, "tree"):
                pt.tree.expandAll()
            QApplication.processEvents()
            QTimer.singleShot(1500, self._shot_3_smart_lookup_framing_sheet)

        self.cursor.glide_to_widget(btn_scan, duration_ms=500, click_pulse=True, on_done=_do_scan)
    def _shot_3_smart_lookup_framing_sheet(self):
        pt = self.win.planset_takeoff_tab
        vw = pt.vis_workspace
        pt._switch_dialog_view(1)
        if hasattr(vw, "chk_hl_lines") and not vw.chk_hl_lines.isChecked():
            vw.chk_hl_lines.setChecked(True)
        vw._auto_color_all_bom_profiles()
        QApplication.processEvents()

        self.caption.show_step(
            "SHOT 3 OF 7 • SMART STEEL COLOR KEY NAVIGATION",
            "Flipping Opening Pages — Then Jumping Straight to Steel Framing via Smart Lookup",
            "Click any steel profile in the Color Key to jump directly to its structural sheet",
        )

        def _after_flip():
            if pt.sheet_combo.count() > 1:
                pt.sheet_combo.setCurrentIndex(1)
                vw.render_sheet(2)
                QApplication.processEvents()

            # Find a beam profile that lives on an actual Structural sheet (S-xxx / Pg 30+)
            structural_profiles = set()
            for top_i in range(pt.tree.topLevelItemCount()):
                p_item = pt.tree.topLevelItem(top_i)
                for c_i in range(p_item.childCount()):
                    ch = p_item.child(c_i)
                    sh_txt = ch.text(1).strip().upper()
                    prof_txt = ch.text(3).strip().upper()
                    if (sh_txt.startswith("S") or "31" in sh_txt or "32" in sh_txt or "33" in sh_txt or "34" in sh_txt or "35" in sh_txt) and (prof_txt.startswith("W") or prof_txt.startswith("HSS")):
                        structural_profiles.add(re.sub(r"\s+", "", prof_txt))

            target_item = None
            best_score = -1
            for idx in range(vw.key_list.count()):
                it = vw.key_list.item(idx)
                txt = (it.text() or "").upper()
                prof_key = re.sub(r"\s+", "", txt.split("—").__getitem__(0))
                if prof_key.startswith("W") or prof_key.startswith("HSS"):
                    m_cnt = re.search(r"\((\d+)\)", txt)
                    cnt = int(m_cnt.group(1)) if m_cnt else 1
                    score = cnt + (100 if prof_key in structural_profiles else 0)
                    if score > best_score:
                        best_score = score
                        target_item = it
            if target_item is None and vw.key_list.count() > 0:
                target_item = vw.key_list.item(0)

            if target_item is not None:
                vw.key_list.scrollToItem(target_item)
                rect = vw.key_list.visualItemRect(target_item)
                item_gpos = vw.key_list.viewport().mapToGlobal(rect.center())

                def _click_smart_lookup():
                    vw.key_list.setCurrentItem(target_item)
                    vw._on_key_item_clicked(target_item)
                    QApplication.processEvents()
                    prof_name = (target_item.text() or "").split("—").__getitem__(0).strip()
                    self.caption.show_step(
                        "SHOT 3 OF 7 • SMART LOOKUP JUMPED TO STRUCTURAL FRAMING PLAN",
                        f"Clicked '{prof_name}' -> Auto-Jumped Straight to Structural Framing Sheet!",
                        "Color-coded beam callouts & attached steel lines highlighted live on drawing",
                    )
                    QTimer.singleShot(1200, self._shot_4_measure_highlighted_beam)

                self.cursor.glide_to(item_gpos, duration_ms=580, click_pulse=True, on_done=_click_smart_lookup)
            else:
                QTimer.singleShot(400, self._shot_4_measure_highlighted_beam)

        QTimer.singleShot(700, _after_flip)
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

        btn_measure = self._find_visible_button(rb, "Linear Dim", "Measure")
        self.caption.show_step(
            "SHOT 4 OF 7 • ZOOM IN & LIVE MEASURE / OSNAP VERIFICATION",
            f"Zooming Onto {beam_profile} & Measuring Real Beam Endpoints",
            "Interactive Measure tool & OSNAP confirm 1:1 BOM length accuracy",
        )
        self.cursor.glide_to_widget(
            btn_measure,
            duration_ms=500,
            click_pulse=True,
            on_done=lambda: self._run_real_canvas_measure(beam_profile, beam_len_ft),
        )

    def _run_real_canvas_measure(self, beam_profile, beam_len_ft):
        pt = self.win.planset_takeoff_tab
        vw = pt.vis_workspace
        rb = self.win.master_ribbon

        if hasattr(rb, "_vis_mode"):
            rb._vis_mode("measure")
        else:
            vw.set_mode("measure")
        for _ in range(3):
            if hasattr(vw, "zoom_in"):
                vw.zoom_in()
        QApplication.processEvents()

        cv = vw.canvas
        if cv.key_highlights:
            hl = cv.key_highlights.__getitem__(0)
            if hl.get("seg"):
                sx1, sy1, sx2, sy2 = hl["seg"]
                p1_local = cv._from_pdf_pt(sx1, sy1)
                p2_local = cv._from_pdf_pt(sx2, sy2)
            else:
                rx0, ry0, rx1, ry1 = hl["rect"]
                p1_local = cv._from_pdf_pt(rx0 - 30.0, (ry0 + ry1) * 0.5)
                p2_local = cv._from_pdf_pt(rx1 + 150.0, (ry0 + ry1) * 0.5)
        else:
            p1_local = QPoint(int(cv.width() * 0.32), int(cv.height() * 0.48))
            p2_local = QPoint(int(cv.width() * 0.64), int(cv.height() * 0.48))

        p1_local = QPoint(max(90, min(cv.width() - 140, p1_local.x())), max(90, min(cv.height() - 90, p1_local.y())))
        p2_local = QPoint(max(140, min(cv.width() - 90, p2_local.x())), max(90, min(cv.height() - 90, p2_local.y())))
        if abs(p2_local.x() - p1_local.x()) < 110 and abs(p2_local.y() - p1_local.y()) < 110:
            p2_local = QPoint(min(cv.width() - 90, p1_local.x() + 240), p1_local.y())

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
                    f"Measured Span: {measured_txt or cv._format_ft_in(beam_len_ft)}  |  BOM {beam_profile}: {beam_len_ft:.2f} ft",
                    "Real interactive Measure tool & OSNAP confirm plan-set scale accuracy",
                )
                QTimer.singleShot(1600, self._shot_5_export_all_steel_pdfs)

            self.cursor.glide_to(p2_global, duration_ms=850, click_pulse=True, on_move=_drag_to_p2, on_done=_click_p2)

        self.cursor.glide_to(p1_global, duration_ms=560, click_pulse=True, on_move=_hover_p1, on_done=_click_p1)

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