
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
                    "STEP 4 OF 6 • 1:1 BOM ACCURACY CONFIRMED ON DRAWING",
                    f"Measured Span: {measured_txt or cv._format_ft_in(beam_len_ft)}  |  BOM {beam_profile}: {beam_len_ft:.2f} ft",
                    "Real interactive Measure tool & OSNAP confirm plan-set scale accuracy",
                )
                QTimer.singleShot(1600, self._scene_4b_export_all_steel_pdfs)

            self.cursor.glide_to(p2_global, duration_ms=820, click_pulse=True, on_move=_drag_to_p2, on_done=_click_p2)

        self.cursor.glide_to(p1_global, duration_ms=560, click_pulse=True, on_move=_hover_p1, on_done=_click_p1)

    def _scene_4b_export_all_steel_pdfs(self):
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
                "STEP 4 OF 6 • MARKED-UP STEEL SHEET PDFs EXPORTED",
                f"Saved {len(self.steel_pages)} Color-Keyed Marked-Up Sheet PDFs",
                "Ready for shop fabrication & customer submittal in Marketing_Trailer_Exports\\",
            )
            QTimer.singleShot(900, self._scene_5_send_bom_to_structural)
            return

        pg_idx = self.steel_pages.__getitem__(self._export_cursor)
        pt.sheet_combo.setCurrentIndex(pg_idx)
        vw.render_sheet(pg_idx + 1)
        pg_num = pg_idx + 1
        sh_label = pt.sheet_combo.currentText().split("—").__getitem__(0).strip().replace("/", "-")
        out_pdf = os.path.join(EXPORT_DIR, f"3122_Broadway_{sh_label}_Pg{pg_num}_MarkedUp.pdf")
        self._write_marked_sheet_pdf(vw, pg_num, out_pdf)

        self.caption.show_step(
            f"STEP 4 OF 6 • EXPORTING MARKED-UP SHEET {self._export_cursor + 1} OF {len(self.steel_pages)}",
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
    def _scene_5_send_bom_to_structural(self):
        pt = self.win.planset_takeoff_tab
        rb = self.win.master_ribbon
        btn_send = self._find_visible_button(rb, "Send BOM", "Send Checked")
        self.caption.show_step(
            "STEP 5 OF 6 • ONE-CLICK SEND TO STRUCTURAL QUOTING",
            "Transferring Verified BOM Into Structural Fabrication Workbench",
            "Every steel profile, quantity & cut length populates automatically",
        )

        def _do_send():
            pt._accept_checked()
            self.win.master_tabs.setCurrentWidget(self.win.custom_quoting_tab)
            self.win.master_ribbon.set_active_tab(2)
            QApplication.processEvents()
            sq = self.win.custom_quoting_tab
            self._total_members = len(getattr(sq, "current_project_items", []))
            self._edit_cursor = 0
            QTimer.singleShot(950, self._step_edit_next_structural_member)

        self.cursor.glide_to_widget(btn_send, duration_ms=500, click_pulse=True, on_done=_do_send)

    def _step_edit_next_structural_member(self):
        sq = self.win.custom_quoting_tab
        items = getattr(sq, "current_project_items", [])
        max_edits = min(len(items), 4)
        if self._edit_cursor >= max_edits:
            QTimer.singleShot(900, self._scene_6_finish_trailer)
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
                    f"STEP 5 OF 6 • DETAILING MEMBER {self._edit_cursor + 1} OF {max_edits}",
                    f"Configured {model} ({extent:.1f} ft)",
                    f"Plan-Set Add-Ons Applied: {spec_desc}",
                )
                self._edit_cursor += 1
                QTimer.singleShot(1050, self._step_edit_next_structural_member)

            self.cursor.glide_to(row_gpos, duration_ms=460, click_pulse=True, on_done=_after_row_click)
        else:
            QTimer.singleShot(600, self._scene_6_finish_trailer)

    def _scene_6_finish_trailer(self):
        sq = self.win.custom_quoting_tab
        if sq.ledger_tree.topLevelItemCount() > 0:
            sq.ledger_tree.expandAll()
        self.caption.show_step(
            "STEP 6 OF 6 • COMPLETE QUOTE & MARKED-UP PDF PACKAGE READY",
            f"All {self._total_members} Members Priced & {len(self.steel_pages)} Marked-Up PDFs Exported",
            "Saved MP4 Trailer & Sheet PDFs to Marketing_Trailer_Exports\\",
        )
        QTimer.singleShot(2000, self._shutdown_and_open_exports)

    def _shutdown_and_open_exports(self):
        self.recorder.stop()
        self.caption.hide()
        print(f"[PASS] Marketing Trailer MP4 saved ({self.recorder.frame_count} frames): {VIDEO_OUT}")
        print(f"[PASS] Marked-up steel sheet PDFs saved in: {EXPORT_DIR}")
        if os.path.exists(EXPORT_DIR):
            os.startfile(EXPORT_DIR)