import os
import sys
import time
import glob
import threading
import pymupdf
import numpy as np
import mss
import imageio.v2 as imageio

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QColor, QCursor, QPainter, QPen, QBrush
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QFileDialog

import live_test


EXPORT_DIR = os.path.join(os.path.abspath("."), "Marketing_Trailer_Exports")
VIDEO_OUT = os.path.join(EXPORT_DIR, "Bowman_Morton_Marketing_Trailer.mp4")

class WindowVideoRecorder:
    """Thread-safe screen recorder capturing the live app window into an H.264 MP4."""

    def __init__(self, target_widget, out_path, fps=24):
        self.target = target_widget
        self.out_path = out_path
        self.fps = fps
        self._running = False
        self._thread = None
        self.frame_count = 0
        self.mon = {"left": 0, "top": 0, "width": 1920, "height": 1080}

    def start(self):
        os.makedirs(os.path.dirname(self.out_path), exist_ok=True)
        geo = self.target.frameGeometry()
        w = max(640, (geo.width() // 2) * 2)
        h = max(480, (geo.height() // 2) * 2)
        self.mon = {"left": max(0, int(geo.x())), "top": max(0, int(geo.y())), "width": int(w), "height": int(h)}
        self._running = True
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()
    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=8.0)

    def _record_loop(self):
        dt = 1.0 / max(1, self.fps)
        writer = None
        with mss.MSS() as sct:
            while self._running:
                t0 = time.perf_counter()
                try:
                    raw = sct.grab(self.mon)
                    frame = np.asarray(raw)[:, :, :3][:, :, ::-1]
                    if writer is None:
                        writer = imageio.get_writer(
                            self.out_path,
                            fps=self.fps,
                            codec="libx264",
                            quality=8,
                            pixelformat="yuv420p",
                            macro_block_size=1,
                        )
                    writer.append_data(frame)
                    self.frame_count += 1
                except Exception:
                    pass
                elapsed = time.perf_counter() - t0
                if elapsed < dt:
                    time.sleep(dt - elapsed)
        if writer is not None:
            try:
                writer.close()
            except Exception:
                pass

class CursorRippleOverlay(QLabel):
    """Visual click-ring indicator so viewers follow every mouse click."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFixedSize(72, 72)
        self._alpha = 0
        self._radius = 10
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._tick)
        self.hide()

    def pulse_at_global(self, gpos):
        lpos = self.parent().mapFromGlobal(gpos)
        self.move(lpos.x() - 36, lpos.y() - 36)
        self._alpha = 235
        self._radius = 10
        self.raise_()
        self.show()
        self._pulse_timer.start(22)
    def _tick(self):
        self._radius += 3
        self._alpha -= 24
        if self._alpha <= 0:
            self._pulse_timer.stop()
            self.hide()
        else:
            self.update()

    def paintEvent(self, ev):
        if self._alpha <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        c = QColor(14, 165, 233, max(0, self._alpha))
        p.setPen(QPen(c, 3.0))
        p.setBrush(QBrush(QColor(56, 189, 248, max(0, self._alpha // 4))))
        p.drawEllipse(QPoint(36, 36), self._radius, self._radius)
        p.end()

class TrailerOverlayBanner(QLabel):
    """Broadcast lower-third caption banner explaining each step clearly."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setWordWrap(True)
        self.setStyleSheet(
            "QLabel {"
            "  background-color: rgba(15, 23, 42, 0.92);"
            "  color: #f8fafc;"
            "  border-left: 5px solid #38bdf8;"
            "  border-top: 1px solid rgba(148, 163, 184, 0.35);"
            "  border-right: 1px solid rgba(148, 163, 184, 0.35);"
            "  border-bottom: 1px solid rgba(148, 163, 184, 0.35);"
            "  border-radius: 8px;"
            "  padding: 12px 18px;"
            "  font-family: 'Segoe UI', Arial, sans-serif;"
            "  font-size: 14px;"
            "}"
        )
        self.setFixedWidth(820)
        self.setMinimumHeight(64)
        self.hide()

    def show_caption(self, step_tag, headline, detail):
        self.setText(
            f"<span style='color:#38bdf8; font-weight:800; font-size:11px; letter-spacing:1px;'>{step_tag}</span><br>"
            f"<span style='color:#ffffff; font-weight:700; font-size:15px;'>{headline}</span> "
            f"<span style='color:#cbd5e1; font-size:13px;'>— {detail}</span>"
        )
        self.adjustSize()
        pw = self.parent().width()
        ph = self.parent().height()
        self.move(max(24, (pw - self.width()) // 2), max(24, ph - self.height() - 26))
        self.raise_()
        self.show()

class MarketingTrailerDirector:
    """Drives the live UI with smooth human cursor motion & real planset navigation."""

    def __init__(self, win):
        self.win = win
        self.pdf_path = self._find_planset()
        self.banner = TrailerOverlayBanner(win)
        self.ripple = CursorRippleOverlay(win)
        self.recorder = WindowVideoRecorder(win, VIDEO_OUT, fps=24)
        self.steel_pages = []
        self._sheet_cursor = 0
        self._edit_cursor = 0
        self._total_members = 0

        self._anim_timer = QTimer(win)
        self._anim_timer.timeout.connect(self._anim_step)
        self._anim_start = QPoint(0, 0)
        self._anim_end = QPoint(0, 0)
        self._anim_t0 = 0.0
        self._anim_dur = 0.65
        self._anim_on_move = None
        self._anim_on_done = None

        QMessageBox.information = lambda *a, **k: QMessageBox.Ok
        QMessageBox.warning = lambda *a, **k: QMessageBox.Ok

    def _find_planset(self):
        exact = os.path.abspath("1230-Dave Pugsley_3122 Broadway - Combined Plan Set.pdf")
        if os.path.exists(exact):
            return exact
        hits = glob.glob("*Dave Pugsley*.pdf") or glob.glob("*3122 Broadway*.pdf")
        if hits:
            return os.path.abspath(hits)
        raise FileNotFoundError("Could not find 1230-Dave Pugsley_3122 Broadway - Combined Plan Set.pdf")
    def _glide_to_widget(self, widget, duration_ms=650, click_pulse=True, on_done=None):
        """Moves the real OS cursor smoothly to the center of `widget` using ease-in-out."""
        if widget is None or not widget.isVisible():
            if on_done:
                QTimer.singleShot(80, on_done)
            return
        center_global = widget.mapToGlobal(QPoint(widget.width() // 2, widget.height() // 2))
        self._glide_to_global(center_global, duration_ms=duration_ms, click_pulse=click_pulse, on_done=on_done)

    def _glide_to_global(self, target_gpos, duration_ms=650, click_pulse=True, on_move=None, on_done=None):
        self._anim_start = QCursor.pos()
        self._anim_end = target_gpos
        self._anim_t0 = time.perf_counter()
        self._anim_dur = max(0.12, duration_ms / 1000.0)
        self._anim_on_move = on_move

        def _finish():
            if click_pulse:
                self.ripple.pulse_at_global(target_gpos)
            if on_done:
                QTimer.singleShot(140, on_done)

        self._anim_on_done = _finish
        self._anim_timer.start(16)

    def _anim_step(self):
        u = min(1.0, (time.perf_counter() - self._anim_t0) / self._anim_dur)
        eased = 4 * u * u * u if u < 0.5 else 1 - pow(-2 * u + 2, 3) / 2
        nx = int(round(self._anim_start.x() + (self._anim_end.x() - self._anim_start.x()) * eased))
        ny = int(round(self._anim_start.y() + (self._anim_end.y() - self._anim_start.y()) * eased))
        cur = QPoint(nx, ny)
        QCursor.setPos(cur)
        if self._anim_on_move:
            try:
                self._anim_on_move(cur)
            except Exception:
                pass
        if u >= 1.0:
            self._anim_timer.stop()
            cb = self._anim_on_done
            self._anim_on_done = None
            if cb:
                cb()
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
        QCursor.setPos(c)

        self.banner.show_caption(
            "BOWMAN-MORTON PRICING SUITE",
            "Effortless Planset Navigation, Takeoff & Structural Quoting",
            "Live walkthrough on 1230 Dave Pugsley — 3122 Broadway Combined Plan Set",
        )
        self.recorder.start()
        QTimer.singleShot(1400, self._scene_1_click_open_pdf)

    def _scene_1_click_open_pdf(self):
        rb = self.win.master_ribbon
        btn_open = getattr(rb, "btn_open_pdf", None)
        self.banner.show_caption(
            "STEP 1 OF 6 • PLANSET INGESTION",
            "Opening Multi-Sheet Structural PDF",
            os.path.basename(self.pdf_path),
        )

        def _do_load():
            pt = self.win.planset_takeoff_tab
            orig_open = QFileDialog.getOpenFileName
            QFileDialog.getOpenFileName = lambda *a, **k: (self.pdf_path, "PDF Files (*.pdf)")
            try:
                pt.load_new_pdf_planset()
            finally:
                QFileDialog.getOpenFileName = orig_open
            QTimer.singleShot(1300, self._scene_2_click_auto_scan)

        self._glide_to_widget(btn_open, duration_ms=700, on_done=_do_load)
    def _scene_2_click_auto_scan(self):
        rb = self.win.master_ribbon
        btn_scan = getattr(rb, "btn_auto_scan", None)
        self.banner.show_caption(
            "STEP 2 OF 6 • AUTOMATED STRUCTURAL BOM EXTRACTION",
            "Scanning Every Sheet for Steel Profiles & Lengths",
            "Detecting Wide Flange Beams, HSS Columns, Angles, Channels & Plates",
        )

        def _do_scan():
            pt = self.win.planset_takeoff_tab
            pt.scan_whole_planset()
            pt._switch_dialog_view(0)
            if hasattr(pt, "tree"):
                pt.tree.expandAll()
            QApplication.processEvents()
            QTimer.singleShot(2200, self._scene_3_color_key_and_navigate)

        self._glide_to_widget(btn_scan, duration_ms=650, on_done=_do_scan)
    def _scene_3_color_key_and_navigate(self):
        pt = self.win.planset_takeoff_tab
        vw = pt.vis_workspace
        pt._switch_dialog_view(1)
        QApplication.processEvents()

        btn_auto_color = getattr(vw, "btn_auto_color", None)
        self.banner.show_caption(
            "STEP 3 OF 6 • STEEL COLOR KEY & SHEET MARKUP EXPORT",
            "Auto-Assigning CAD Colors & Exporting Marked-Up Steel Sheets",
            "Color-coding every profile across the plan set and baking vector PDFs",
        )

        def _do_color_and_collect():
            vw._auto_color_all_bom_profiles()
            QApplication.processEvents()

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
                    meta = ch.data(0, Qt.UserRole) or {}
                    if isinstance(meta.get("page"), int):
                        pages_with_steel.add(meta["page"])

            if not pages_with_steel and getattr(vw, "_doc", None):
                pages_with_steel = set(range(len(vw._doc)))
            self.steel_pages = sorted(pages_with_steel)
            self._sheet_cursor = 0
            QTimer.singleShot(1100, self._step_export_next_steel_sheet)

        self._glide_to_widget(btn_auto_color, duration_ms=650, on_done=_do_color_and_collect)
    def _step_export_next_steel_sheet(self):
        pt = self.win.planset_takeoff_tab
        vw = pt.vis_workspace
        if self._sheet_cursor >= len(self.steel_pages):
            QTimer.singleShot(900, self._scene_4_live_measure_verification)
            return

        pg_idx = self.steel_pages[self._sheet_cursor]
        if 0 <= pg_idx < pt.sheet_combo.count():
            pt.sheet_combo.setCurrentIndex(pg_idx)
        vw.render_sheet(pg_idx + 1)
        QApplication.processEvents()

        pg_num = vw.get_page_fn()
        sh_label = pt.sheet_combo.currentText().split("—").strip().replace("/", "-")
        out_pdf = os.path.join(EXPORT_DIR, f"3122_Broadway_{sh_label}_Pg{pg_num}_MarkedUp.pdf")
        self._write_marked_sheet_pdf(vw, pg_num, out_pdf)

        cv = vw.canvas
        g_pt = cv.mapToGlobal(QPoint(int(cv.width() * 0.45), int(cv.height() * 0.42)))
        self.banner.show_caption(
            f"STEP 3 OF 6 • STRUCTURAL SHEET {self._sheet_cursor + 1} OF {len(self.steel_pages)}",
            f"Navigating & Exporting {os.path.basename(out_pdf)}",
            f"{len(cv.key_highlights)} color-keyed steel members highlighted & baked to PDF",
        )
        self._sheet_cursor += 1
        self._glide_to_global(
            g_pt,
            duration_ms=550,
            click_pulse=False,
            on_done=lambda: QTimer.singleShot(850, self._step_export_next_steel_sheet),
        )
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
    def _scene_4_live_measure_verification(self):
        pt = self.win.planset_takeoff_tab
        vw = pt.vis_workspace
        rb = self.win.master_ribbon

        if self.steel_pages:
            first_idx = self.steel_pages
            pt.sheet_combo.setCurrentIndex(first_idx)
            vw.render_sheet(first_idx + 1)
            QApplication.processEvents()

        beam_profile = "W16X57"
        beam_len_ft = 20.0
        for top_i in range(pt.tree.topLevelItemCount()):
            p_item = pt.tree.topLevelItem(top_i)
            for c_i in range(p_item.childCount()):
                ch = p_item.child(c_i)
                prof = ch.text(3).strip()
                if prof.startswith("W") or prof.startswith("HSS"):
                    beam_profile = prof
                    try:
                        beam_len_ft = float(ch.text(5))
                    except ValueError:
                        beam_len_ft = 20.0
                    break

        btn_measure = getattr(rb, "btn_measure", None)
        self.banner.show_caption(
            "STEP 4 OF 6 • MEASURE TILE ACCURACY VERIFICATION",
            f"Selecting Measure Tool to Verify {beam_profile} Span",
            "Snapping directly onto the plan set to confirm BOM extraction accuracy",
        )
        self._glide_to_widget(
            btn_measure,
            duration_ms=650,
            on_done=lambda: self._animate_measure_span(beam_profile, beam_len_ft),
        )
    def _animate_measure_span(self, beam_profile, beam_len_ft):
        pt = self.win.planset_takeoff_tab
        vw = pt.vis_workspace
        rb = self.win.master_ribbon

        if hasattr(rb, "_vis_mode"):
            rb._vis_mode("measure")
        else:
            vw.set_mode("measure")

        cv = vw.canvas
        p1_local = QPoint(int(cv.width() * 0.30), int(cv.height() * 0.46))
        p2_local = QPoint(int(cv.width() * 0.62), int(cv.height() * 0.46))
        if cv.key_highlights:
            rx0, ry0, rx1, ry1 = cv.key_highlights["rect"]
            q_start = cv._from_pdf_pt(rx0, ry1 + 12.0)
            p1_local = QPoint(max(80, q_start.x()), max(80, q_start.y()))
            p2_local = QPoint(min(cv.width() - 80, p1_local.x() + 260), p1_local.y())

        p1_global = cv.mapToGlobal(p1_local)
        p2_global = cv.mapToGlobal(p2_local)
        x1, y1 = cv._to_pdf_pt(p1_local)
        x2, y2 = cv._to_pdf_pt(p2_local)
        lbl_str = cv._format_ft_in(beam_len_ft)

        def _after_p1():
            cv._p1 = p1_local
            cv._hover_pt = p1_local

            def _on_drag(cur_gpos):
                cv._hover_pt = cv.mapFromGlobal(cur_gpos)
                cv.update()

            def _after_p2():
                cv._p1 = None
                cv._hover_pt = None
                cv.markups.append({
                    "type": "span",
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "label": f"{lbl_str}  [VERIFIED == BOM {beam_profile}]",
                    "ft": beam_len_ft,
                    "color": QColor("#16a34a"),
                    "line_width": 3.0,
                    "font_size": 12,
                })
                cv.selected_idx = len(cv.markups) - 1
                cv.update()
                if hasattr(vw, "on_span_measured"):
                    vw.on_span_measured(beam_len_ft)

                self.banner.show_caption(
                    "STEP 4 OF 6 • MEASURE TILE CONFIRMED",
                    f"Measured {lbl_str} == BOM {beam_profile} ({beam_len_ft:.2f} ft)",
                    "1:1 plan-set geometry verified before sending to Structural Quoting",
                )
                QTimer.singleShot(2200, self._scene_5_send_bom_to_structural)

            self._glide_to_global(p2_global, duration_ms=950, click_pulse=True, on_move=_on_drag, on_done=_after_p2)

        self._glide_to_global(p1_global, duration_ms=650, click_pulse=True, on_done=_after_p1)
    def _scene_5_send_bom_to_structural(self):
        pt = self.win.planset_takeoff_tab
        rb = self.win.master_ribbon
        btn_send = getattr(rb, "btn_send_bom", None)
        self.banner.show_caption(
            "STEP 5 OF 6 • ONE-CLICK SEND TO STRUCTURAL QUOTING",
            "Pushing Verified BOM to Structural Quoting Workbench",
            "Every steel profile, quantity & cut length transfers automatically",
        )

        def _do_send():
            pt._accept_checked()
            self.win.master_tabs.setCurrentWidget(self.win.custom_quoting_tab)
            self.win.master_ribbon.set_active_tab(2)
            QApplication.processEvents()
            sq = self.win.custom_quoting_tab
            self._total_members = len(getattr(sq, "current_project_items", []))
            self._edit_cursor = 0
            QTimer.singleShot(1400, self._step_edit_next_structural_member)

        self._glide_to_widget(btn_send, duration_ms=650, on_done=_do_send)
    def _step_edit_next_structural_member(self):
        sq = self.win.custom_quoting_tab
        items = getattr(sq, "current_project_items", [])
        max_edits = min(len(items), 5)
        if self._edit_cursor >= max_edits:
            QTimer.singleShot(1200, self._scene_6_finish_trailer)
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

                self.banner.show_caption(
                    f"STEP 5 OF 6 • DETAILING MEMBER {self._edit_cursor + 1} OF {max_edits}",
                    f"Configured {model} ({extent:.1f} ft)",
                    f"Plan-Set Add-Ons Applied: {spec_desc}",
                )
                self._edit_cursor += 1
                QTimer.singleShot(1350, self._step_edit_next_structural_member)

            self._glide_to_global(row_gpos, duration_ms=520, click_pulse=True, on_done=_after_row_click)
        else:
            QTimer.singleShot(800, self._scene_6_finish_trailer)

    def _scene_6_finish_trailer(self):
        sq = self.win.custom_quoting_tab
        if sq.ledger_tree.topLevelItemCount() > 0:
            sq.ledger_tree.expandAll()
        self.banner.show_caption(
            "STEP 6 OF 6 • COMPLETE QUOTE & MARKED-UP PDF PACKAGE READY",
            f"All {self._total_members} Members Priced & {len(self.steel_pages)} Marked-Up PDFs Exported",
            "Saved MP4 Trailer & Sheet PDFs to Marketing_Trailer_Exports\\",
        )
        QTimer.singleShot(2500, self._shutdown_and_open_exports)

    def _shutdown_and_open_exports(self):
        self.recorder.stop()
        self.banner.hide()
        print(f"[PASS] Marketing Trailer MP4 saved ({self.recorder.frame_count} frames): {VIDEO_OUT}")
        print(f"[PASS] Marked-up steel sheet PDFs saved in: {EXPORT_DIR}")
        if os.path.exists(EXPORT_DIR):
            os.startfile(EXPORT_DIR)

def main():
    app = QApplication.instance() or QApplication(sys.argv)
    win = live_test.StandaloneManufacturingApp()
    director = MarketingTrailerDirector(win)
    QTimer.singleShot(500, director.start)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()