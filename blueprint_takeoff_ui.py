from PySide6.QtCore import QRectF
from ui.page_thumbnails_drawer import PageThumbnailsDrawer
from PySide6.QtWidgets import QDoubleSpinBox
from PySide6.QtWidgets import QFileDialog
import os
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWidgets import QPlainTextEdit
import math
import re
import pymupdf
from PySide6.QtCore import Qt, QRect, QPoint, QPointF, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QImage, QPixmap, QIcon
from PySide6.QtWidgets import (
    QToolButton,
    QWidget, QLabel, QPushButton, QComboBox, QLineEdit, QScrollArea,
    QVBoxLayout, QHBoxLayout, QInputDialog, QFrame,
    QListWidget, QListWidgetItem, QColorDialog, QFontComboBox, QSpinBox
)

def make_swatch_icon(hex_or_qcolor, size=14):
    qc = QColor(hex_or_qcolor)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    pt = QPainter(pm)
    pt.setRenderHint(QPainter.Antialiasing, True)
    pt.setBrush(qc)
    pt.setPen(QPen(QColor("#ffffff"), 1.2))
    pt.drawRoundedRect(1, 1, size - 2, size - 2, 3, 3)
    pt.end()
    return QIcon(pm)

class CadBlueprintCanvas(QLabel):
    def __init__(self, on_box_selected, on_span_measured, on_count_changed=None, on_calibrated=None, on_status_msg=None, scroll_area=None, parent=None):
        super().__init__(parent)
        self.on_box_selected = on_box_selected
        self.on_span_measured = on_span_measured
        self.on_count_changed = on_count_changed
        self.on_calibrated = on_calibrated
        self.on_status_msg = on_status_msg
        self.scroll_area = scroll_area

        self.mode = "pan"
        self.pts_per_ft = 18.0
        self.render_dpi = 150.0
        self.zoom = 1.0
        self.active_color = QColor("#111827")
        self.fill_color = QColor("#ffffff")
        self.font_family = "Arial"
        self.font_size = 18
        self.active_line_width = 2.0
        self.font_bold = True
        self.font_italic = False
        self.font_underline = False
        self.ortho_lock = False
        self.endpoint_snap = True
        self.hidden_layers = set()

        self._base_pix = None
        self._drag_start = None
        self._drag_cur = None
        self._p1 = None
        self._p2 = None
        self._poly_pts = []
        self._free_pts = []
        self._hover_pt = None
        self._snap_badge_pt = None
        self._dyn_input_buf = ""
        self._dyn_ang_buf = ""
        self._dyn_field = "len"
        self._pline_pts = []
        self._panning = False
        self._pan_origin = None

        self.markups = []
        self.selected_idx = -1
        self.show_grid = False
        self.grid_spacing_px = 28
        self.selected_indices = set()
        self._dragging_selected = False
        self._drag_last_pdf = None
        self._marquee_start = None
        self._marquee_cur = None
        self._pending_cad_shape = None
        self._skew_pts = []

        self.legend_pdf_pos = [18.0, 18.0]
        self._legend_rect_px = QRect()
        self._dragging_legend = False
        self._legend_drag_offset = QPoint()

        class _CanvasNoteEditor(QPlainTextEdit):
            def __init__(self, canvas_ref):
                super().__init__(canvas_ref)
                self._c = canvas_ref
                self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                self.setFrameShape(QFrame.NoFrame)
            def keyPressEvent(self, ev):
                if ev.key() in (Qt.Key_Return, Qt.Key_Enter) and (ev.modifiers() & Qt.ControlModifier):
                    self._c._commit_inline_text()
                    ev.accept()
                    return
                if ev.key() == Qt.Key_Escape:
                    self.hide()
                    ev.accept()
                    return
                super().keyPressEvent(ev)

        self._inline_editor = _CanvasNoteEditor(self)
        self._inline_editor.hide()
        self._inline_editor.textChanged.connect(self._resize_inline_editor)
        self._inline_pdf_pt = (0.0, 0.0)
        self._inline_callout_pts = None

        self.key_highlights = []
        self.pdf_snap_endpoints = []
        self.pdf_snap_midpoints = []
        self.legend_entries = []

        self.setFocusPolicy(Qt.StrongFocus)
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)
        self.setStyleSheet("background-color: #f1f5f9; border: 1px solid #cbd5e1;")

        class _CadHudLineEdit(QLineEdit):
            def __init__(self, canvas_ref, is_angle=False):
                super().__init__(canvas_ref)
                self._c = canvas_ref
                self._is_angle = is_angle
                self.setAlignment(Qt.AlignCenter)
                self.setFixedHeight(22)
                self.setStyleSheet(
                    "QLineEdit { background-color: #ffffff; color: #0f172a; border: 1.5px solid #0284c7; "
                    "border-radius: 3px; font-family: 'Consolas', monospace; font-size: 11px; font-weight: 700; padding: 0px 4px; } "
                    "QLineEdit:focus { background-color: #eff6ff; border: 2px solid #0369a1; }"
                )
                self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                self.hide()
                self.textEdited.connect(self._on_edited)

            def _on_edited(self, txt):
                if self._is_angle:
                    self._c._dyn_ang_buf = txt.strip()
                else:
                    self._c._dyn_input_buf = txt.strip()
                self._c.update()

            def keyPressEvent(self, ev):
                if ev.key() == Qt.Key_Tab:
                    nxt = self._c._hud_len_edit if self._is_angle else self._c._hud_ang_edit
                    nxt.setFocus()
                    nxt.selectAll()
                    ev.accept()
                    return
                if ev.key() in (Qt.Key_Return, Qt.Key_Enter):
                    self._c._commit_hud_segment()
                    ev.accept()
                    return
                if ev.key() == Qt.Key_Escape:
                    self._c._pline_pts.clear()
                    self._c._p1 = None
                    self._c._p2 = None
                    self._c._drag_start = None
                    self._c._drag_cur = None
                    self._c._hide_hud_boxes()
                    self._c.setFocus()
                    self._c.update()
                    ev.accept()
                    return
                if ev.key() == Qt.Key_C and not self._is_angle and self._c.mode == "polyline" and len(self._c._pline_pts) >= 3:
                    self._c._hide_hud_boxes()
                    self._c._finish_polyline(close_loop=True)
                    ev.accept()
                    return
                super().keyPressEvent(ev)

        self._hud_len_edit = _CadHudLineEdit(self, is_angle=False)
        self._hud_ang_edit = _CadHudLineEdit(self, is_angle=True)

    def _current_qfont(self, scale_with_zoom=True):
        pt_sz = max(7, int(round(self.font_size * (self.zoom if scale_with_zoom else 1.0))))
        f = QFont(self.font_family, pt_sz)
        f.setBold(self.font_bold)
        f.setItalic(self.font_italic)
        f.setUnderline(self.font_underline)
        return f

    def _apply_inline_style(self):
        c_hex = self.active_color.name()
        wt = "bold" if self.font_bold else "normal"
        st = "italic" if self.font_italic else "normal"
        pt_sz = max(8, int(round(self.font_size * self.zoom)))
        self._inline_editor.setFont(self._current_qfont(True))
        self._inline_editor.setStyleSheet(
            f"QPlainTextEdit {{ background-color: transparent !important; border: none !important; "
            f"color: {c_hex} !important; font-family: '{self.font_family}'; "
            f"font-size: {pt_sz}pt; font-weight: {wt}; font-style: {st}; padding: 0px; }}"
        )

    def _resize_inline_editor(self):
        fm = self._inline_editor.fontMetrics()
        lines = self._inline_editor.toPlainText().split("\n") or [""]
        max_w = max(fm.horizontalAdvance(ln + "  ") for ln in lines)
        w = max(180, max_w + 28)
        h = max(30, len(lines) * (fm.lineSpacing() + 2) + 12)
        self._inline_editor.resize(w, h)

    def _start_inline_text(self, qpos, initial_text=""):
        if self._inline_editor.isVisible():
            self._commit_inline_text()
        self._inline_pdf_pt = self._to_pdf_pt(qpos)
        self._inline_editor.setPlainText(initial_text)
        self._apply_inline_style()
        self._resize_inline_editor()
        self._inline_editor.move(max(4, qpos.x()), max(4, qpos.y() - 14))
        self._inline_editor.show()
        self._inline_editor.setFocus()

    def _commit_inline_text(self):
        if not self._inline_editor.isVisible():
            return
        txt = self._inline_editor.toPlainText().strip()
        self._inline_editor.hide()
        c_pts = self._inline_callout_pts
        self._inline_callout_pts = None
        if txt:
            if c_pts is not None:
                x0, y0, x1, y1 = c_pts
                self.markups.append({
                    "type": "callout", "x1": x0, "y1": y0, "x2": x1, "y2": y1, "text": txt,
                    "color": QColor(self.active_color), "line_width": float(self.active_line_width),
                    "font_family": self.font_family, "font_size": self.font_size,
                    "bold": self.font_bold, "italic": self.font_italic,
                })
            else:
                px, py = self._inline_pdf_pt
                self.markups.append({
                    "type": "text", "x": px, "y": py, "text": txt,
                    "color": QColor(self.active_color),
                    "font_family": self.font_family, "font_size": self.font_size,
                    "bold": self.font_bold, "italic": self.font_italic,
                })
            self.selected_idx = len(self.markups) - 1
            self.update()

    def set_interaction_mode(self, mode):
        if self._inline_editor.isVisible():
            self._commit_inline_text()
        self.mode = mode
        self._drag_start = None
        self._drag_cur = None
        self._p1 = None
        self._p2 = None
        self._pline_pts.clear()
        self._poly_pts.clear()
        self._free_pts.clear()
        self._hide_hud_boxes()
        self._panning = False
        self.setCursor(Qt.OpenHandCursor if mode == "pan" else (Qt.ArrowCursor if mode == "select" else (Qt.IBeamCursor if mode == "text" else Qt.CrossCursor)))
        self.update()

    def rotate_selected_markup(self):
        if 0 <= self.selected_idx < len(self.markups):
            m = self.markups[self.selected_idx]
            if m.get("type") in ("span", "arrow", "line", "dashed", "angle"):
                mx, my = (m["x1"] + m["x2"]) * 0.5, (m["y1"] + m["y2"]) * 0.5
                dx1, dy1 = m["x1"] - mx, m["y1"] - my
                dx2, dy2 = m["x2"] - mx, m["y2"] - my
                m["x1"], m["y1"] = mx - dy1, my + dx1
                m["x2"], m["y2"] = mx - dy2, my + dx2
            elif m.get("type") in ("highlight", "filled_box", "ellipse", "cloud"):
                mx, my = (m["x1"] + m["x2"]) * 0.5, (m["y1"] + m["y2"]) * 0.5
                hw, hh = abs(m["x2"] - m["x1"]) * 0.5, abs(m["y2"] - m["y1"]) * 0.5
                m["x1"], m["y1"], m["x2"], m["y2"] = mx - hh, my - hw, mx + hh, my + hw
            self.update()

    def duplicate_selected_markup(self):
        if 0 <= self.selected_idx < len(self.markups):
            import copy
            clone = copy.deepcopy(self.markups[self.selected_idx])
            if clone.get("type") in ("span", "arrow", "highlight", "line", "ellipse", "angle", "cloud", "filled_box", "dashed", "callout", "weld", "centerline"):
                clone["x1"] += 18.0; clone["y1"] += 18.0
                clone["x2"] += 18.0; clone["y2"] += 18.0
            else:
                clone["x"] += 18.0; clone["y"] += 18.0
            self.markups.append(clone)
            self.selected_idx = len(self.markups) - 1
            self.update()

    def contextMenuEvent(self, ev):
        if not getattr(self, "_rclick_moved", False):
            self._show_canvas_context_menu(ev.globalPos(), ev.pos())
            ev.accept()
            return
        super().contextMenuEvent(ev)

    def _show_canvas_context_menu(self, global_pos, local_pos):
        from PySide6.QtWidgets import QMenu, QColorDialog, QInputDialog
        hit = self._hit_test_markup(local_pos)
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px; font-family: 'Segoe UI'; font-size: 12px; } "
            "QMenu::item { padding: 6px 18px 6px 10px; border-radius: 4px; } "
            "QMenu::item:selected { background-color: #e0f2fe; color: #0369a1; } "
            "QMenu::separator { height: 1px; background: #e2e8f0; margin: 4px 6px; }"
        )
        if hit >= 0:
            self.selected_idx = hit
            p_win = self.window()
            if hasattr(p_win, "master_ribbon") and hasattr(p_win.master_ribbon, "update_contextual_selection"):
                p_win.master_ribbon.update_contextual_selection(self.markups[hit])
            self.update()
            m = self.markups[hit]
            mtype = m.get("type", "")

            if mtype in ("text", "callout", "count", "weld", "grid_bubble"):
                act_edit = menu.addAction("Edit Text / Label...")
                def _do_edit():
                    cur_v = m.get("text") or m.get("label") or ""
                    nv, ok = QInputDialog.getText(self, "Edit Markup", "Text / Label:", text=str(cur_v))
                    if ok and nv.strip():
                        if "text" in m: m["text"] = nv.strip()
                        else: m["label"] = nv.strip()
                        self.update()
                act_edit.triggered.connect(_do_edit)

            if mtype == "text":
                act_hl_bg = menu.addAction("Highlight Text (Yellow Marker)")
                def _toggle_txt_hl():
                    m["bg_highlight"] = None if m.get("bg_highlight") else "#fef08a"
                    self.update()
                act_hl_bg.triggered.connect(_toggle_txt_hl)

            c_menu = menu.addMenu("Highlight / Set Color")
            for c_name, c_hex in [("Yellow Highlight", "#eab308"), ("Red Markup", "#dc2626"), ("Steel Blue", "#0284c7"), ("Emerald Green", "#059669"), ("Black Ink", "#111827")]:
                c_menu.addAction(c_name).triggered.connect(lambda _=False, hx=c_hex: (m.update({"color": QColor(hx)}), self.update()))
            c_menu.addSeparator()
            def _custom_col():
                qc = QColorDialog.getColor(m.get("color", QColor("#0284c7")), self, "Choose Markup Color")
                if qc.isValid():
                    m["color"] = qc
                    self.update()
            c_menu.addAction("Custom Color Wheel...").triggered.connect(_custom_col)

            menu.addSeparator()
            menu.addAction("Bring to Front").triggered.connect(lambda: (self.markups.append(self.markups.pop(hit)), setattr(self, "selected_idx", len(self.markups) - 1), self.update()))
            menu.addAction("Send to Back").triggered.connect(lambda: (self.markups.insert(0, self.markups.pop(hit)), setattr(self, "selected_idx", 0), self.update()))
            menu.addAction("Duplicate Item").triggered.connect(self.duplicate_selected_markup)
            menu.addAction("Rotate +90 deg").triggered.connect(self.rotate_selected_markup)
            menu.addSeparator()
            act_del = menu.addAction("Delete Item (Del)")
            act_del.triggered.connect(self.delete_selected_markup)
        else:
            menu.addAction("Select / Move Tool (V)").triggered.connect(lambda: self.set_mode("select"))
            menu.addAction("Adobe Highlighter Pen").triggered.connect(lambda: self.set_mode("free_highlight"))
            menu.addAction("Add Text Note Here").triggered.connect(lambda: (self.set_mode("text"), self._open_inline_text_editor(local_pos)))
            menu.addSeparator()
            menu.addAction("Fit Page to Screen").triggered.connect(self.fit_to_viewport)
            menu.addAction("Clear All Markups").triggered.connect(self.clear_markups)

        menu.exec(global_pos)

    def _markup_bbox_px(self, m):
        return self._markup_screen_rect(m)

    def _markup_screen_rect(self, m):
        mt = m.get("type")
        if mt in ("count", "text", "grid_bubble"):
            c = self._from_pdf_pt(m["x"], m["y"])
            return QRect(c.x() - 18, c.y() - 18, 36, 36)
        if mt == "cad_shape":
            ox, oy = m["x"], m["y"]
            wp, hp = m.get("w_pts", 180.0), m.get("h_pts", 140.0)
            return QRect(self._from_pdf_pt(ox, oy), self._from_pdf_pt(ox + wp, oy + hp)).normalized()
        if mt in ("area", "free_highlight", "polyline"):
            pts = [self._from_pdf_pt(px, py) for px, py in m.get("pts", [])]
            if not pts:
                return QRect()
            xs, ys = [p.x() for p in pts], [p.y() for p in pts]
            return QRect(min(xs), min(ys), max(1, max(xs) - min(xs)), max(1, max(ys) - min(ys)))
        if mt == "hanger_skew":
            pts = [self._from_pdf_pt(m["hx1"], m["hy1"]), self._from_pdf_pt(m["hx2"], m["hy2"]), self._from_pdf_pt(m["jx"], m["jy"])]
            xs, ys = [p.x() for p in pts], [p.y() for p in pts]
            return QRect(min(xs), min(ys), max(1, max(xs) - min(xs)), max(1, max(ys) - min(ys)))
        if "x1" in m and "y1" in m and "x2" in m and "y2" in m:
            return QRect(self._from_pdf_pt(m["x1"], m["y1"]), self._from_pdf_pt(m["x2"], m["y2"])).normalized()
        return QRect()

    def delete_selected_markup(self):
        targets = set(getattr(self, "selected_indices", set()))
        if 0 <= self.selected_idx < len(self.markups):
            targets.add(self.selected_idx)
        if not targets:
            return
        had_count = False
        for idx in sorted(targets, reverse=True):
            if 0 <= idx < len(self.markups):
                rem = self.markups.pop(idx)
                if rem.get("type") == "count":
                    had_count = True
        self.selected_idx = -1
        self.selected_indices.clear()
        if had_count and self.on_count_changed:
            self.on_count_changed(sum(1 for m in self.markups if m.get("type") == "count"))
        self.update()

    def undo_last_markup(self):
        if self._inline_editor.isVisible():
            self._inline_editor.hide()
            return
        if getattr(self, "_skew_pts", []):
            self._skew_pts.pop()
            self.update()
            return
        if getattr(self, "_pline_pts", []):
            self._pline_pts.pop()
            self.update()
            return
        if self._p1 is not None:
            self._p1 = None
            self._p2 = None
            self._hide_hud_boxes()
            self.update()
            return
        if self.markups:
            removed = self.markups.pop()
            self.selected_idx = -1
            if hasattr(self, "selected_indices"):
                self.selected_indices.clear()
            if removed.get("type") == "count" and self.on_count_changed:
                self.on_count_changed(sum(1 for m in self.markups if m.get("type") == "count"))
            self.update()

    def clear_markups(self):
        self._inline_editor.hide()
        self.markups.clear()
        self.selected_idx = -1
        self.selected_indices.clear()
        self._p1 = None
        self._p2 = None
        if self.on_count_changed:
            self.on_count_changed(0)
        self.update()

    def _hit_test_markup(self, qpt):
        for i in range(len(self.markups) - 1, -1, -1):
            m = self.markups[i]
            mt = m.get("type")
            if mt == "count":
                c = self._from_pdf_pt(m["x"], m["y"])
                if math.hypot(qpt.x() - c.x(), qpt.y() - c.y()) <= 15.0:
                    return i
            elif mt == "cad_shape":
                r_sh = self._markup_screen_rect(m).adjusted(-8, -8, 8, 8)
                if r_sh.contains(qpt):
                    return i
            elif mt == "text":
                t0 = self._from_pdf_pt(m["x"], m["y"])
                w_est = max(60, len(m.get("text", "")) * int(m.get("font_size", 13) * self.zoom * 0.85))
                h_est = max(22, int(m.get("font_size", 13) * self.zoom * 1.8))
                if QRect(t0.x() - 6, t0.y() - h_est, w_est + 12, h_est + 10).contains(qpt):
                    return i
            elif mt == "hanger_skew":
                if self._markup_screen_rect(m).adjusted(-10, -10, 10, 10).contains(qpt):
                    return i
            elif mt in ("span", "arrow", "line", "angle", "dashed", "callout", "weld", "centerline"):
                a, b = self._from_pdf_pt(m["x1"], m["y1"]), self._from_pdf_pt(m["x2"], m["y2"])
                abx, aby = float(b.x() - a.x()), float(b.y() - a.y())
                ab2 = abx * abx + aby * aby
                if ab2 > 1.0:
                    t = max(0.0, min(1.0, ((qpt.x() - a.x()) * abx + (qpt.y() - a.y()) * aby) / ab2))
                    if math.hypot(qpt.x() - (a.x() + t * abx), qpt.y() - (a.y() + t * aby)) <= 12.0:
                        return i
            elif mt in ("highlight", "ellipse", "cloud", "filled_box"):
                r_box = QRect(self._from_pdf_pt(m["x1"], m["y1"]), self._from_pdf_pt(m["x2"], m["y2"])).normalized().adjusted(-8, -8, 8, 8)
                if r_box.contains(qpt):
                    return i
            elif mt in ("area", "free_highlight", "polyline"):
                from PySide6.QtGui import QPolygon
                qpts = [self._from_pdf_pt(px, py) for px, py in m.get("pts", [])]
                if len(qpts) >= 3 and QPolygon(qpts).boundingRect().adjusted(-8, -8, 8, 8).contains(qpt):
                    return i
        return -1

    def set_color_key_overlays(self, highlights, legend_entries):
        self.key_highlights = highlights or []
        self.legend_entries = legend_entries or []
        self.update()

    def load_pixmap(self, qpix, render_dpi=150.0, page_markups=None):
        self._inline_editor.hide()
        self._base_pix = qpix
        self.render_dpi = float(render_dpi)
        self.selected_idx = -1
        if page_markups is not None:
            self.markups = page_markups
        self._apply_zoom()

    def fit_to_viewport(self):
        if not self._base_pix or self._base_pix.isNull() or not self.scroll_area:
            return
        vw = max(200, self.scroll_area.viewport().width() - 24)
        vh = max(200, self.scroll_area.viewport().height() - 24)
        self.zoom = max(0.25, min(2.5, min(vw / float(self._base_pix.width()), vh / float(self._base_pix.height()))))
        self._apply_zoom()

    def set_zoom(self, z, anchor_vp=None):
        old_z = self.zoom
        new_z = max(0.25, min(3.5, float(z)))
        if abs(new_z - old_z) < 1e-4:
            return
        self.zoom = new_z
        self._apply_zoom()
        if self.scroll_area and anchor_vp is not None:
            hbar, vbar = self.scroll_area.horizontalScrollBar(), self.scroll_area.verticalScrollBar()
            ratio = new_z / old_z
            hbar.setValue(int((hbar.value() + anchor_vp.x()) * ratio - anchor_vp.x()))
            vbar.setValue(int((vbar.value() + anchor_vp.y()) * ratio - anchor_vp.y()))

    def _apply_zoom(self, fast=False):
        if not self._base_pix or self._base_pix.isNull():
            return
        w, h = max(1, int(self._base_pix.width() * self.zoom)), max(1, int(self._base_pix.height() * self.zoom))
        mode = Qt.FastTransformation if fast else Qt.SmoothTransformation
        self.setPixmap(self._base_pix.scaled(w, h, Qt.KeepAspectRatio, mode))
        self.resize(w, h)
        self.update()

    def _to_pdf_pt(self, qpt):
        pw = getattr(self, "_pdf_page_w", 0.0)
        ph = getattr(self, "_pdf_page_h", 0.0)
        if pw > 0 and ph > 0 and self.width() > 0 and self.height() > 0:
            return float(qpt.x()) * (pw / float(self.width())), float(qpt.y()) * (ph / float(self.height()))
        sc = 72.0 / (self.render_dpi * self.zoom)
        return float(qpt.x()) * sc, float(qpt.y()) * sc

    def _from_pdf_pt(self, px, py):
        pw = getattr(self, "_pdf_page_w", 0.0)
        ph = getattr(self, "_pdf_page_h", 0.0)
        if pw > 0 and ph > 0 and self.width() > 0 and self.height() > 0:
            return QPoint(int(round(float(px) * (float(self.width()) / pw))), int(round(float(py) * (float(self.height()) / ph))))
        inv = (self.render_dpi * self.zoom) / 72.0
        return QPoint(int(round(px * inv)), int(round(py * inv)))

    @staticmethod
    def _format_ft_in(ft_val):
        wf = int(ft_val)
        inc = round((ft_val - wf) * 12.0)
        if inc == 12:
            wf += 1
            inc = 0
        return f"{wf}'-{inc}\""

    def _snap_to_endpoint(self, qpt):
        self._snap_badge_pt = None
        self._snap_kind = None
        self._track_guides = []
        if not getattr(self, "endpoint_snap", True):
            return qpt

        # Prioritize exact endpoints of highlighted steel beam segments so Measure matches BOM 1:1
        beam_eps = []
        for hl in getattr(self, "key_highlights", []):
            seg = hl.get("seg")
            if seg and len(seg) == 4:
                sx1, sy1, sx2, sy2 = seg
                beam_eps.extend([self._from_pdf_pt(sx1, sy1), self._from_pdf_pt(sx2, sy2)])
        for bep in beam_eps:
            if math.hypot(qpt.x() - bep.x(), qpt.y() - bep.y()) <= 24.0:
                self._snap_badge_pt = bep
                self._snap_kind = "endpoint"
                return bep

        endpoints = [self._from_pdf_pt(px, py) for px, py in getattr(self, "pdf_snap_endpoints", [])]
        midpoints = [self._from_pdf_pt(px, py) for px, py in getattr(self, "pdf_snap_midpoints", [])]
        for m in self.markups:
            if "x1" in m and "y1" in m and "x2" in m and "y2" in m:
                a, b = self._from_pdf_pt(m["x1"], m["y1"]), self._from_pdf_pt(m["x2"], m["y2"])
                endpoints.extend([a, b])
                midpoints.append(QPoint((a.x() + b.x()) // 2, (a.y() + b.y()) // 2))
            m_pts = [p_xy for p_xy in m.get("pts", []) if isinstance(p_xy, (list, tuple)) and len(p_xy) == 2]
            for idx_p, (px, py) in enumerate(m_pts):
                ep = self._from_pdf_pt(px, py)
                endpoints.append(ep)
                if idx_p + 1 < len(m_pts):
                    ep2 = self._from_pdf_pt(*m_pts[idx_p + 1])
                    midpoints.append(QPoint((ep.x() + ep2.x()) // 2, (ep.y() + ep2.y()) // 2))
            if m.get("type") == "cad_shape":
                x0, y0 = m["x"], m["y"]
                w_p, h_p = m.get("w_pts", 0), m.get("h_pts", 0)
                endpoints.extend([self._from_pdf_pt(x0, y0), self._from_pdf_pt(x0 + w_p, y0 + h_p), self._from_pdf_pt(x0, y0 + h_p)])

        act_pts = [p_xy for p_xy in getattr(self, "_pline_pts", []) if isinstance(p_xy, (list, tuple)) and len(p_xy) == 2]
        for idx_p, (px, py) in enumerate(act_pts):
            ep = self._from_pdf_pt(px, py)
            endpoints.append(ep)
            if idx_p + 1 < len(act_pts):
                ep2 = self._from_pdf_pt(*act_pts[idx_p + 1])
                midpoints.append(QPoint((ep.x() + ep2.x()) // 2, (ep.y() + ep2.y()) // 2))

        best_pt, best_d, best_kind = qpt, 18.0, None
        for ep in endpoints:
            d = math.hypot(qpt.x() - ep.x(), qpt.y() - ep.y())
            if d < best_d:
                best_d, best_pt, best_kind = d, ep, "endpoint"
        for mp in midpoints:
            d = math.hypot(qpt.x() - mp.x(), qpt.y() - mp.y())
            if d < best_d - 2.0:
                best_d, best_pt, best_kind = d, mp, "midpoint"

        if best_kind is not None:
            self._snap_badge_pt = best_pt
            self._snap_kind = best_kind
            return best_pt

        # AutoCAD Object Snap Tracking (OTRACK): project full-length green dashed XY alignment lines from corners & midpoints
        tx, ty = qpt.x(), qpt.y()
        best_dx, best_dy = 10.0, 10.0
        track_x_pt, track_y_pt = None, None
        for ep in (endpoints + midpoints):
            if abs(qpt.x() - ep.x()) < best_dx and abs(qpt.y() - ep.y()) > 8:
                best_dx, tx, track_x_pt = abs(qpt.x() - ep.x()), ep.x(), ep
            if abs(qpt.y() - ep.y()) < best_dy and abs(qpt.x() - ep.x()) > 8:
                best_dy, ty, track_y_pt = abs(qpt.y() - ep.y()), ep.y(), ep
        if track_x_pt is not None or track_y_pt is not None:
            snapped_t = QPoint(tx, ty)
            self._track_intersection = snapped_t if (track_x_pt is not None and track_y_pt is not None) else None
            if track_x_pt is not None:
                self._track_guides.append((QPoint(tx, 0), QPoint(tx, self.height()), track_x_pt))
            if track_y_pt is not None:
                self._track_guides.append((QPoint(0, ty), QPoint(self.width(), ty), track_y_pt))
            return snapped_t
        self._track_intersection = None
        return qpt

    def _snap_ortho(self, p1, p2, shift_held):
        if p1 is None or p2 is None:
            return p2
        dx, dy = p2.x() - p1.x(), p2.y() - p1.y()
        dist = math.hypot(dx, dy)
        if dist < 1.0:
            return p2
        deg = math.degrees(math.atan2(dy, dx))
        nearest_45 = round(deg / 45.0) * 45.0
        # Hard lock when Shift/Ortho is held, or magnetic AutoCAD Polar Snap within ±4.0° on any line
        if shift_held or abs(deg - nearest_45) <= 4.0:
            rad = math.radians(nearest_45)
            return QPoint(int(round(p1.x() + dist * math.cos(rad))), int(round(p1.y() + dist * math.sin(rad))))
        return p2

    def wheelEvent(self, ev):
        if not self.scroll_area:
            super().wheelEvent(ev)
            return
        delta, mods = ev.angleDelta().y(), ev.modifiers()
        if mods & Qt.ControlModifier:
            step = 1.15 if delta > 0 else (1.0 / 1.15)
            pos = self._snap_to_endpoint(ev.position().toPoint() if hasattr(ev, "position") else ev.pos())
            self.set_zoom(self.zoom * step, anchor_vp=self.mapTo(self.scroll_area.viewport(), pos))
            ev.accept()
        elif mods & Qt.ShiftModifier:
            self.scroll_area.horizontalScrollBar().setValue(self.scroll_area.horizontalScrollBar().value() - delta)
            ev.accept()
        else:
            self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value() - delta)
            ev.accept()

    def _hide_hud_boxes(self):
        self._dyn_input_buf = ""
        self._dyn_ang_buf = ""
        self._dyn_field = "len"
        if hasattr(self, "_hud_len_edit"):
            self._hud_len_edit.blockSignals(True); self._hud_len_edit.clear(); self._hud_len_edit.blockSignals(False); self._hud_len_edit.hide()
        if hasattr(self, "_hud_ang_edit"):
            self._hud_ang_edit.blockSignals(True); self._hud_ang_edit.clear(); self._hud_ang_edit.blockSignals(False); self._hud_ang_edit.hide()

    def _update_hud_boxes(self, hud_p0, hud_p1):
        if not hasattr(self, "_hud_len_edit"):
            return
        x1, y1 = self._to_pdf_pt(hud_p0)
        x2, y2 = self._to_pdf_pt(hud_p1)
        dist_ft = math.hypot(x2 - x1, y2 - y1) / max(1.0, self.pts_per_ft)
        deg = (-math.degrees(math.atan2(y2 - y1, x2 - x1))) % 360.0
        if deg > 180.0:
            deg -= 360.0

        # Position the two sleek dark CAD boxes cleanly near the midpoint & cursor
        mx, my = int((hud_p0.x() + hud_p1.x()) * 0.5), int((hud_p0.y() + hud_p1.y()) * 0.5)
        self._hud_len_edit.setFixedSize(88, 22)
        self._hud_len_edit.move(max(4, mx - 44), max(4, my - 30))
        if not self._dyn_input_buf:
            self._hud_len_edit.blockSignals(True)
            self._hud_len_edit.setText(self._format_ft_in(dist_ft))
            self._hud_len_edit.selectAll()
            self._hud_len_edit.blockSignals(False)
        if not self._hud_len_edit.isVisible():
            self._hud_len_edit.show()
            self._hud_len_edit.setFocus()
            self._hud_len_edit.selectAll()

        self._hud_ang_edit.setFixedSize(72, 22)
        self._hud_ang_edit.move(min(self.width() - 78, int(hud_p1.x()) + 14), min(self.height() - 28, int(hud_p1.y()) + 10))
        if not self._dyn_ang_buf:
            self._hud_ang_edit.blockSignals(True)
            self._hud_ang_edit.setText(f"{deg:.1f}°")
            self._hud_ang_edit.selectAll()
            self._hud_ang_edit.blockSignals(False)
        if not self._hud_ang_edit.isVisible():
            self._hud_ang_edit.show()

    def _commit_hud_segment(self):
        active_p0 = (self._from_pdf_pt(*self._pline_pts[-1]) if (self.mode == "polyline" and self._pline_pts) else (self._p1 or self._drag_start))
        active_p1 = self._hover_pt or self._drag_cur
        if not active_p0 or not active_p1:
            return
        if self.mode in ("polyline", "line", "dashed", "centerline") and not self._dyn_input_buf and not self._dyn_ang_buf:
            self._hide_hud_boxes()
            if self.mode == "polyline":
                self._finish_polyline(close_loop=False)
            else:
                self._p1 = None; self._p2 = None; self.update()
            return
        try:
            x1, y1 = self._to_pdf_pt(active_p0)
            x2_raw, y2_raw = self._to_pdf_pt(active_p1)
            ppf = max(1.0, self.pts_per_ft)
            raw_len = re.sub(r"[^0-9.\-]", "", self._dyn_input_buf or "")
            raw_ang = re.sub(r"[^0-9.\-]", "", self._dyn_ang_buf or "")
            val_ft = float(raw_len) if raw_len else (math.hypot(x2_raw - x1, y2_raw - y1) / ppf)
            ang = -math.radians(float(raw_ang)) if raw_ang else math.atan2(y2_raw - y1, x2_raw - x1)
            self._hide_hud_boxes()
            dist_pts = val_ft * ppf
            x2, y2 = x1 + dist_pts * math.cos(ang), y1 + dist_pts * math.sin(ang)
            if self.mode == "polyline":
                self._pline_pts.append((x2, y2))
                self._hover_pt = self._from_pdf_pt(x2, y2)
                self._update_hud_boxes(self._hover_pt, self._hover_pt)
                self.update()
                return
            if self.mode == "measure":
                self.markups.append({"type": "span", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "label": self._format_ft_in(val_ft), "ft": val_ft, "color": QColor(self.active_color), "line_width": float(self.active_line_width), "font_size": int(self.font_size)})
                self.on_span_measured(val_ft); self._p1 = None; self._p2 = None
            else:
                self.markups.append({"type": self.mode, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "color": QColor(self.active_color), "line_width": float(self.active_line_width)})
                self.selected_idx = len(self.markups) - 1
                if self.mode == "arrow":
                    self._p1 = None
                else:
                    nxt = self._from_pdf_pt(x2, y2)
                    self._p1 = nxt
                    self._hover_pt = nxt
                    self._update_hud_boxes(nxt, nxt)
                self._drag_start = None; self._drag_cur = None
            self.update()
        except ValueError:
            self._hide_hud_boxes()

    def _finish_polyline(self, close_loop=False):
        if len(self._pline_pts) >= 2:
            pts = list(self._pline_pts)
            if close_loop and len(pts) >= 3:
                first_x, first_y = next(iter(pts))
                pts.append((first_x, first_y))
            self._pline_pts.clear()
            self._dyn_input_buf = ""
            self._dyn_ang_buf = ""
            self._dyn_field = "len"
            self.markups.append({
                "type": "polyline", "pts": pts, "closed": bool(close_loop),
                "color": QColor(self.active_color), "line_width": float(self.active_line_width)
            })
            self.selected_idx = len(self.markups) - 1
            self.update()
        else:
            self._pline_pts.clear()
            self.update()

    def _finish_area_polygon(self):
        if len(self._poly_pts) >= 3:
            pts = list(self._poly_pts)
            self._poly_pts.clear()
            area_pts2 = 0.0
            perim_pts = 0.0
            for i in range(len(pts)):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % len(pts)]
                area_pts2 += (x1 * y2 - x2 * y1)
                perim_pts += math.hypot(x2 - x1, y2 - y1)
            ppf = max(1.0, self.pts_per_ft)
            sqft = abs(area_pts2) * 0.5 / (ppf * ppf)
            perim_ft = perim_pts / ppf
            self.markups.append({"type": "area", "pts": pts, "label": f"{sqft:,.1f} sq ft  |  {perim_ft:,.1f} lf", "color": QColor(self.active_color), "line_width": float(self.active_line_width), "font_size": int(self.font_size)})
            self.selected_idx = len(self.markups) - 1
            self.update()

    def mouseDoubleClickEvent(self, ev):
        if self.mode == "area" and len(self._poly_pts) >= 3:
            pts = list(self._poly_pts)
            self._poly_pts.clear()
            area_pts2 = 0.0
            perim_pts = 0.0
            for i in range(len(pts)):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % len(pts)]
                area_pts2 += (x1 * y2 - x2 * y1)
                perim_pts += math.hypot(x2 - x1, y2 - y1)
            ppf = max(1.0, self.pts_per_ft)
            sqft = abs(area_pts2) * 0.5 / (ppf * ppf)
            perim_ft = perim_pts / ppf
            self.markups.append({"type": "area", "pts": pts, "label": f"{sqft:,.1f} sq ft  |  {perim_ft:,.1f} lf", "color": QColor(self.active_color), "line_width": float(self.active_line_width), "font_size": int(self.font_size)})
            self.selected_idx = len(self.markups) - 1
            self.update()
            ev.accept()
            return
        pos = self._snap_to_endpoint(ev.position().toPoint() if hasattr(ev, "position") else ev.pos())
        hit = self._hit_test_markup(pos)
        if hit >= 0 and (ev.modifiers() & Qt.ControlModifier) and hasattr(self, 'duplicate_selected_markup'):
            self.selected_idx = hit
            self.duplicate_selected_markup()
            hit = self.selected_idx
        if 0 <= hit < len(self.markups) and self.markups[hit].get("type") == "text":
            m = self.markups.pop(hit)
            self.selected_idx = -1
            self.active_color = QColor(m.get("color", self.active_color))
            self.font_family = m.get("font_family", self.font_family)
            self.font_size = int(m.get("font_size", self.font_size))
            self.font_bold = bool(m.get("bold", True))
            self._start_inline_text(self._from_pdf_pt(m["x"], m["y"]), initial_text=m.get("text", ""))
            ev.accept()
            return
        super().mouseDoubleClickEvent(ev)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.RightButton and self.mode == "polyline" and len(self._pline_pts) >= 2:
            self._finish_polyline(False); ev.accept(); return
        if ev.button() == Qt.RightButton and self.mode == "hanger_skew" and self._skew_pts:
            self._skew_pts.clear(); self.update(); ev.accept(); return
        if ev.button() == Qt.RightButton and self.mode in ("line", "dashed", "centerline", "arrow") and self._p1 is not None:
            self._p1 = None; self._p2 = None; self._dyn_input_buf = ""; self._dyn_ang_buf = ""; self.update(); ev.accept(); return
        if ev.button() == Qt.RightButton and self.mode == "area" and len(self._poly_pts) >= 3:
            self._finish_area_polygon()
            ev.accept()
            return
        if not self._base_pix:
            return
        self.setFocus(Qt.MouseFocusReason)
        btn = ev.button()
        raw_pos = ev.position().toPoint() if hasattr(ev, "position") else ev.pos()
        pos = self._snap_to_endpoint(raw_pos) if self.mode in ("measure", "polyline", "calibrate", "line", "arrow", "dashed", "centerline", "weld", "callout", "hanger_skew") else raw_pos
        gpos = ev.globalPosition().toPoint() if hasattr(ev, "globalPosition") else ev.globalPos()
        shift_held = bool(ev.modifiers() & Qt.ShiftModifier) or getattr(self, 'ortho_lock', False)

        if btn == Qt.LeftButton and self.legend_entries and self._legend_rect_px.contains(pos):
            self._dragging_legend = True
            self._legend_drag_offset = pos - self._legend_rect_px.topLeft()
            self.setCursor(Qt.ClosedHandCursor)
            ev.accept()
            return

        if self._inline_editor.isVisible():
            self._commit_inline_text()

        if btn == Qt.LeftButton and self.mode == "pan" and self._hit_test_markup(pos) >= 0:
            pass
        elif btn in (Qt.MiddleButton, Qt.RightButton) or (btn == Qt.LeftButton and self.mode == "pan"):
            self._panning = True
            self._pan_origin = gpos
            self.setCursor(Qt.ClosedHandCursor)
            ev.accept()
            return
        if btn != Qt.LeftButton:
            return

        if getattr(self, "_pending_cad_shape", None) is not None and btn == Qt.LeftButton:
            px, py = self._to_pdf_pt(self._hover_pt or pos)
            sh = dict(self._pending_cad_shape)
            sh["x"] = px
            sh["y"] = py
            self.markups.append(sh)
            self.selected_idx = len(self.markups) - 1
            self.selected_indices = {self.selected_idx}
            self._pending_cad_shape = None
            self.mode = "select"
            self.update()
            ev.accept()
            return
        if self.mode in ("select", "pan"):
            hit = self._hit_test_markup(pos)
            if hit >= 0:
                if shift_held:
                    if hit in self.selected_indices:
                        self.selected_indices.remove(hit)
                        self.selected_idx = next(iter(self.selected_indices), -1)
                    else:
                        self.selected_indices.add(hit)
                        self.selected_idx = hit
                else:
                    if hit not in self.selected_indices:
                        self.selected_indices = {hit}
                    self.selected_idx = hit
                self._dragging_selected = True
                self._drag_last_pdf = self._to_pdf_pt(pos)
                self.setCursor(Qt.ClosedHandCursor if self.mode == "pan" else Qt.SizeAllCursor)
            else:
                if not shift_held:
                    self.selected_idx = -1
                    self.selected_indices.clear()
                if self.mode == "select":
                    self._marquee_start = pos
                    self._marquee_cur = pos
            self.setFocus()
            p_win = self.window()
            if hasattr(p_win, "master_ribbon") and hasattr(p_win.master_ribbon, "update_contextual_selection"):
                sel_m = self.markups[self.selected_idx] if 0 <= self.selected_idx < len(self.markups) else None
                p_win.master_ribbon.update_contextual_selection(sel_m)
        elif self.mode == "text":
            self._start_inline_text(pos)
            return
        elif self.mode == "polyline":
            if self._pline_pts and getattr(self, "_snap_badge_pt", None) is None:
                prev_q = self._from_pdf_pt(*self._pline_pts[-1])
                pos = self._snap_ortho(prev_q, pos, shift_held)
            self._pline_pts.append(self._to_pdf_pt(pos))
            self._dyn_input_buf = ""
            self._dyn_ang_buf = ""
            self._dyn_field = "len"
            self.update()
            return
        elif self.mode == "area":
            px, py = self._to_pdf_pt(pos)
            self._poly_pts.append((px, py))
            self.update()
            return
        elif self.mode == "free_highlight":
            self._free_pts = [self._to_pdf_pt(pos)]
            self.update()
            return
        elif self.mode in ("line", "dashed", "centerline", "arrow"):
            if self._p1 is None:
                self._p1 = pos
                self._p2 = None
                self._dyn_input_buf = ""
                self._dyn_ang_buf = ""
                self._dyn_field = "len"
                self._hover_pt = pos
            else:
                end_pt = self._snap_ortho(self._p1, pos, shift_held)
                x1, y1 = self._to_pdf_pt(self._p1)
                x2, y2 = self._to_pdf_pt(end_pt)
                if math.hypot(x2 - x1, y2 - y1) > 2.0:
                    self.markups.append({
                        "type": self.mode, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                        "color": QColor(self.active_color), "line_width": float(self.active_line_width)
                    })
                    self.selected_idx = len(self.markups) - 1
                if self.mode == "arrow":
                    self._p1 = None
                else:
                    self._p1 = end_pt
                self._p2 = None
                self._dyn_input_buf = ""
                self._dyn_ang_buf = ""
                self._dyn_field = "len"
        elif self.mode in ("box", "highlight", "ellipse", "angle", "cloud", "filled_box", "callout", "weld"):
            self._drag_start = pos
            self._drag_cur = pos
        elif self.mode == "count":
            px, py = self._to_pdf_pt(pos)
            cnt_num = sum(1 for m in self.markups if m.get("type") == "count") + 1
            self.markups.append({"type": "count", "x": px, "y": py, "num": cnt_num, "color": QColor(self.active_color)})
            if self.on_count_changed:
                self.on_count_changed(cnt_num)
        elif self.mode == "grid_bubble":
            from PySide6.QtWidgets import QInputDialog
            px, py = self._to_pdf_pt(pos)
            lbl, ok = QInputDialog.getText(self, "Column Grid Bubble", "Grid Line Label (e.g. A, B.1, 1, 12):", text="A")
            if ok and lbl.strip():
                self.markups.append({"type": "grid_bubble", "x": px, "y": py, "label": lbl.strip().upper(), "color": QColor(self.active_color), "line_width": float(self.active_line_width)})
                self.selected_idx = len(self.markups) - 1
                self.update()
        elif self.mode == "hanger_skew":
            px, py = self._to_pdf_pt(pos)
            self._skew_pts.append((px, py))
            if len(self._skew_pts) == 3:
                (hx1, hy1), (hx2, hy2), (jx, jy) = self._skew_pts
                self._skew_pts.clear()
                vx, vy = hx2 - hx1, hy2 - hy1
                vlen = math.hypot(vx, vy)
                if vlen > 2.0:
                    ux, uy = vx / vlen, vy / vlen
                    # Use Click 2 (hx2, hy2) as the fixed T-pivot root matching the live T-square preview
                    rx, ry = hx2, hy2
                    # Two unit normals to header; pick the one on the same side as (jx, jy)
                    nx, ny = -uy, ux
                    sx, sy = jx - rx, jy - ry
                    if (sx * nx + sy * ny) < 0:
                        nx, ny = -nx, -ny
                    slen = max(1.0, math.hypot(sx, sy))
                    # Signed angle from 90° perpendicular normal (+ = Right, - = Left looking from header out)
                    dot_n = max(-1.0, min(1.0, (sx * nx + sy * ny) / slen))
                    cross_n = (nx * sy - ny * sx) / slen
                    skew_deg = math.degrees(math.acos(dot_n))
                    if skew_deg < 1.0:
                        skew_deg = 0.0
                        lbl = "0.0° STD (90°)"
                    else:
                        side = "RIGHT" if cross_n < 0 else "LEFT"
                        lbl = f"SKEW {side} {skew_deg:.1f}°"
                    self.markups.append({
                        "type": "hanger_skew",
                        "hx1": hx1, "hy1": hy1, "hx2": hx2, "hy2": hy2,
                        "rx": rx, "ry": ry, "jx": jx, "jy": jy,
                        "nx": nx, "ny": ny, "slen": slen,
                        "label": lbl, "skew_deg": skew_deg,
                        "color": QColor(self.active_color),
                        "line_width": float(self.active_line_width),
                        "font_size": int(self.font_size)
                    })
                    self.selected_idx = -1
                    self.selected_indices.clear()
            self.update()
            return
        elif self.mode in ("measure", "calibrate"):
            if self._p1 is None or self._p2 is not None:
                self._p1 = pos
                self._p2 = None
            else:
                self._p2 = self._snap_ortho(self._p1, pos, shift_held)
                x1, y1 = self._to_pdf_pt(self._p1)
                x2, y2 = self._to_pdf_pt(self._p2)
                pdf_pts = math.hypot(x2 - x1, y2 - y1)
                if self.mode == "calibrate":
                    if self.on_calibrated and pdf_pts > 5.0:
                        self.on_calibrated(pdf_pts)
                else:
                    import bom_pdf_engine as _eng; dist_ft = _eng.round_structural_ft(pdf_pts / max(1.0, self.pts_per_ft))
                    self.markups.append({"type": "span", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "label": self._format_ft_in(dist_ft), "ft": dist_ft, "color": QColor(self.active_color), "line_width": float(self.active_line_width), "font_size": int(self.font_size)})
                    self.on_span_measured(dist_ft)
                self._p1 = None
                self._p2 = None
        self.update()

    def mouseMoveEvent(self, ev):
        raw_pos = ev.position().toPoint() if hasattr(ev, "position") else ev.pos()
        pos = self._snap_to_endpoint(raw_pos) if self.mode in ("measure", "polyline", "calibrate", "line", "arrow", "dashed", "centerline", "weld", "callout", "hanger_skew") else raw_pos
        gpos = ev.globalPosition().toPoint() if hasattr(ev, "globalPosition") else ev.globalPos()
        shift_held = bool(ev.modifiers() & Qt.ShiftModifier) or getattr(self, 'ortho_lock', False)
        if self.mode == "polyline" and self._pline_pts:
            self._hover_pt = pos if getattr(self, "_snap_badge_pt", None) is not None else self._snap_ortho(self._from_pdf_pt(*self._pline_pts[-1]), pos, shift_held)
        elif self.mode in ("measure", "calibrate", "line", "dashed", "centerline", "arrow") and self._p1:
            self._hover_pt = self._snap_ortho(self._p1, pos, shift_held)
        else:
            self._hover_pt = pos
        p_win = self.window()
        pt_tab = getattr(p_win, "planset_takeoff_tab", None)
        if pt_tab and hasattr(pt_tab, "lbl_cad_coords"):
            px, py = self._to_pdf_pt(pos)
            ppf = max(1.0, self.pts_per_ft)
            pt_tab.lbl_cad_coords.setText(f"XY: {self._format_ft_in(px / ppf)}, {self._format_ft_in(py / ppf)}")

        if self._dragging_legend:
            new_tl = pos - self._legend_drag_offset
            px, py = self._to_pdf_pt(QPoint(max(4, new_tl.x()), max(4, new_tl.y())))
            self.legend_pdf_pos = [px, py]
            self.update()
            return

        if self._marquee_start is not None:
            self._marquee_cur = pos
            self.update()
            return

        if self._dragging_selected and self._drag_last_pdf:
            cx, cy = self._to_pdf_pt(pos)
            lx, ly = self._drag_last_pdf
            dx, dy = cx - lx, cy - ly
            self._drag_last_pdf = (cx, cy)
            move_set = set(self.selected_indices)
            if 0 <= self.selected_idx < len(self.markups):
                move_set.add(self.selected_idx)
            for idx in move_set:
                if 0 <= idx < len(self.markups):
                    m = self.markups[idx]
                    if m.get("type") in ("span", "arrow", "line", "highlight", "ellipse", "angle", "cloud", "filled_box", "dashed", "callout", "weld", "centerline"):
                        m["x1"] += dx; m["y1"] += dy; m["x2"] += dx; m["y2"] += dy
                    elif m.get("type") == "hanger_skew":
                        for kx in ("hx1", "hx2", "rx", "jx"): m[kx] += dx
                        for ky in ("hy1", "hy2", "ry", "jy"): m[ky] += dy
                    elif m.get("type") in ("area", "free_highlight", "polyline"):
                        m["pts"] = [(px + dx, py + dy) for px, py in m.get("pts", [])]
                    else:
                        m["x"] += dx; m["y"] += dy
            self.update()
            return

        if self._panning and self._pan_origin is not None and self.scroll_area:
            diff = gpos - self._pan_origin
            self._pan_origin = gpos
            self.scroll_area.horizontalScrollBar().setValue(self.scroll_area.horizontalScrollBar().value() - diff.x())
            self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value() - diff.y())
            ev.accept()
            return

        if self.legend_entries and self._legend_rect_px.contains(pos):
            self.setCursor(Qt.OpenHandCursor)
        elif not self._panning and not self._dragging_selected:
            self.setCursor(Qt.OpenHandCursor if self.mode == "pan" else (Qt.ArrowCursor if self.mode == "select" else (Qt.IBeamCursor if self.mode == "text" else Qt.CrossCursor)))

        if self.mode == "free_highlight" and self._free_pts:
            if shift_held:
                p0_q = self._from_pdf_pt(*self._free_pts[0])
                snapped = self._snap_ortho(p0_q, pos, True)
                self._free_pts = [self._free_pts[0], self._to_pdf_pt(snapped)]
            else:
                self._free_pts.append(self._to_pdf_pt(pos))
            self.update()
            return
        if self.mode in ("box", "arrow", "highlight", "line", "ellipse", "angle", "cloud", "filled_box", "dashed", "callout", "weld", "centerline") and self._drag_start is not None:
            pos = self._snap_ortho(self._drag_start, pos, shift_held) if self.mode in ("arrow", "line") else pos
            self._drag_cur = pos
            self.update()
        elif (self.mode == "polyline" and self._pline_pts) or (self.mode in ("measure", "calibrate", "line", "dashed", "centerline", "arrow") and self._p1 is not None) or (self.mode == "hanger_skew" and getattr(self, "_skew_pts", None)):
            self.update()

    def mouseReleaseEvent(self, ev):
        if self._marquee_start is not None and self._marquee_cur is not None:
            p0, p1 = self._marquee_start, self._marquee_cur
            self._marquee_start = None
            self._marquee_cur = None
            sel_rect = QRect(p0, p1).normalized()
            is_crossing = p1.x() < p0.x()  # Right-to-left = Green Crossing; Left-to-right = Blue Window
            if sel_rect.width() > 4 or sel_rect.height() > 4:
                for i, m in enumerate(self.markups):
                    mr = self._markup_screen_rect(m)
                    if not mr.isNull():
                        matched = sel_rect.intersects(mr) if is_crossing else sel_rect.contains(mr)
                        if matched:
                            self.selected_indices.add(i)
                self.selected_idx = max(self.selected_indices) if self.selected_indices else -1
            self.update()
            ev.accept()
            return
        if self._dragging_legend or self._dragging_selected or self._panning:
            self._dragging_legend = False
            self._dragging_selected = False
            self._panning = False
            self._pan_origin = None
            self.setCursor(Qt.OpenHandCursor if self.mode == "pan" else (Qt.ArrowCursor if self.mode == "select" else (Qt.IBeamCursor if self.mode == "text" else Qt.CrossCursor)))
            ev.accept()
            return
        if ev.button() == Qt.LeftButton and self.mode == "free_highlight" and len(self._free_pts) >= 2:
            self.markups.append({
                "type": "free_highlight", "pts": list(self._free_pts),
                "color": QColor(self.active_color), "line_width": max(12.0, float(self.active_line_width) * 5.0)
            })
            self._free_pts.clear()
            self.selected_idx = len(self.markups) - 1
            self.update()
            return
        if ev.button() == Qt.LeftButton and self.mode in ("box", "highlight", "ellipse", "angle", "cloud", "filled_box", "callout", "weld") and self._drag_start and self._drag_cur:
            cur_mode = self.mode
            x0, y0 = self._to_pdf_pt(self._drag_start)
            x1, y1 = self._to_pdf_pt(self._drag_cur)
            rx0, rx1, ry0, ry1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
            self._drag_start = None
            self._drag_cur = None
            if cur_mode == "highlight" and (rx1 - rx0) > 8.0 and (ry1 - ry0) > 8.0:
                self.markups.append({"type": "highlight", "x1": rx0, "y1": ry0, "x2": rx1, "y2": ry1, "color": QColor(self.active_color), "line_width": float(self.active_line_width)})
                self.selected_idx = len(self.markups) - 1
            elif cur_mode in ("arrow", "line") and math.hypot(x1 - x0, y1 - y0) > 8.0:
                self.markups.append({"type": cur_mode, "x1": x0, "y1": y0, "x2": x1, "y2": y1, "color": QColor(self.active_color), "line_width": float(self.active_line_width)})
                self.selected_idx = len(self.markups) - 1
            elif cur_mode == "angle" and math.hypot(x1 - x0, y1 - y0) > 8.0:
                dx_a, dy_a = abs(x1 - x0), abs(y1 - y0)
                deg = math.degrees(math.atan2(dy_a, max(0.001, dx_a)))
                pitch = (dy_a / max(0.001, dx_a)) * 12.0
                lbl_ang = f"{deg:.1f} deg  |  {pitch:.1f}:12 Pitch"
                self.markups.append({"type": "angle", "x1": x0, "y1": y0, "x2": x1, "y2": y1, "label": lbl_ang, "color": QColor(self.active_color), "line_width": float(self.active_line_width), "font_size": int(self.font_size)})
                self.selected_idx = len(self.markups) - 1
            elif cur_mode in ("ellipse", "cloud") and (rx1 - rx0) > 8.0 and (ry1 - ry0) > 8.0:
                self.markups.append({"type": cur_mode, "x1": rx0, "y1": ry0, "x2": rx1, "y2": ry1, "color": QColor(self.active_color), "line_width": float(self.active_line_width)})
                self.selected_idx = len(self.markups) - 1
            elif cur_mode == "filled_box" and (rx1 - rx0) > 8.0 and (ry1 - ry0) > 8.0:
                self.markups.append({"type": "filled_box", "x1": rx0, "y1": ry0, "x2": rx1, "y2": ry1, "color": QColor(self.fill_color), "line_width": float(self.active_line_width)})
                self.selected_idx = len(self.markups) - 1
            elif cur_mode == "dashed" and math.hypot(x1 - x0, y1 - y0) > 8.0:
                self.markups.append({"type": "dashed", "x1": x0, "y1": y0, "x2": x1, "y2": y1, "color": QColor(self.active_color), "line_width": float(self.active_line_width)})
                self.selected_idx = len(self.markups) - 1
            elif cur_mode == "callout" and math.hypot(x1 - x0, y1 - y0) > 8.0:
                end_qpt = self._from_pdf_pt(x1, y1)
                self._start_inline_text(end_qpt, initial_text="")
                self._inline_callout_pts = (x0, y0, x1, y1)
            elif cur_mode == "weld" and math.hypot(x1 - x0, y1 - y0) > 8.0:
                from PySide6.QtWidgets import QInputDialog
                w_spec, ok = QInputDialog.getText(self, "AWS Weld Symbol", "Weld Size & Type (e.g. 1/4 FILLET, 3/16 ALL AROUND):", text="1/4 FILLET")
                if ok and w_spec.strip():
                    self.markups.append({"type": "weld", "x1": x0, "y1": y0, "x2": x1, "y2": y1, "label": w_spec.strip().upper(), "color": QColor(self.active_color), "line_width": float(self.active_line_width)})
                    self.selected_idx = len(self.markups) - 1
            elif cur_mode == "centerline" and math.hypot(x1 - x0, y1 - y0) > 8.0:
                self.markups.append({"type": "centerline", "x1": x0, "y1": y0, "x2": x1, "y2": y1, "color": QColor(self.active_color), "line_width": float(self.active_line_width)})
                self.selected_idx = len(self.markups) - 1
            elif cur_mode == "box" and (rx1 - rx0) > 15.0 and (ry1 - ry0) > 15.0:
                self.on_box_selected(pymupdf.Rect(rx0, ry0, rx1, ry1))
            self.update()

    def _draw_hanger_skew_diagram(self, p, qh1, qh2, qj, col, lw=2.0, font_pt=10):
        # Carrying header / wall face line (Click 1 -> Click 2; Click 2 is the fixed T-pivot root)
        p.setPen(QPen(col, max(2.4, lw * 1.3), Qt.SolidLine, Qt.RoundCap))
        p.drawLine(qh1, qh2)
        vx, vy = float(qh2.x() - qh1.x()), float(qh2.y() - qh1.y())
        vlen = math.hypot(vx, vy)
        if vlen < 2.0:
            return
        ux, uy = vx / vlen, vy / vlen
        qr = QPointF(qh2)
        nx, ny = -uy, ux
        sx, sy = float(qj.x() - qr.x()), float(qj.y() - qr.y())
        if (sx * nx + sy * ny) < 0:
            nx, ny = -nx, -ny
        raw_len = math.hypot(sx, sy)
        slen = max(36.0, raw_len)
        dot_n = max(-1.0, min(1.0, (sx * nx + sy * ny) / max(1.0, raw_len)))
        cross_n = (nx * sy - ny * sx) / max(1.0, raw_len)
        skew_deg = math.degrees(math.acos(dot_n))
        if skew_deg < 1.0:
            skew_deg = 0.0
            lbl = "0.0° STD (90°)"
            qj_draw = QPointF(qr.x() + nx * slen, qr.y() + ny * slen)
        else:
            side = "RIGHT" if cross_n < 0 else "LEFT"
            lbl = f"SKEW {side} {skew_deg:.1f}°"
            qj_draw = QPointF(qj) if raw_len >= 36.0 else QPointF(qr.x() + (sx / max(1.0, raw_len)) * slen, qr.y() + (sy / max(1.0, raw_len)) * slen)

        # Dashed 0° STD (90° perpendicular) T-square reference centerline
        q_norm_end = QPointF(qr.x() + nx * (slen * 1.15), qr.y() + ny * (slen * 1.15))
        p.setPen(QPen(QColor("#16a34a"), max(1.4, lw * 0.8), Qt.DashLine))
        p.drawLine(qr, q_norm_end)

        # Swung joist/hanger stem line ("I") pivoting cleanly around Click 2
        p.setPen(QPen(col, max(2.2, lw * 1.1), Qt.SolidLine, Qt.RoundCap))
        p.drawLine(qr, qj_draw)

        # Simpson-style curved skew dimension arc between 0° normal and swung stem
        arc_r = min(slen * 0.72, 68.0)
        if skew_deg >= 1.0 and arc_r > 12.0:
            a_norm = math.degrees(math.atan2(-ny, nx))
            a_joist = math.degrees(math.atan2(-(qj_draw.y() - qr.y()), qj_draw.x() - qr.x()))
            span = (a_joist - a_norm + 540.0) % 360.0 - 180.0
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor("#0284c7"), max(1.6, lw * 0.9), Qt.SolidLine))
            arc_rect = QRectF(qr.x() - arc_r, qr.y() - arc_r, arc_r * 2.0, arc_r * 2.0)
            p.drawArc(arc_rect, int(round(a_norm * 16)), int(round(span * 16)))

        # Crisp readout pill offset beyond the stem tip
        p.setFont(QFont("Segoe UI", max(10, font_pt), QFont.Bold))
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(lbl) + 22
        th = fm.height() + 8
        dir_x = (qj_draw.x() - qr.x()) / max(1.0, slen)
        dir_y = (qj_draw.y() - qr.y()) / max(1.0, slen)
        bx = int(qj_draw.x() + dir_x * 16 - (tw if dir_x < -0.2 else 0))
        by = int(qj_draw.y() + dir_y * 16 - th // 2)
        badge_r = QRect(bx, by, tw, th)
        p.setBrush(QColor(15, 23, 42, 238))
        p.setPen(QPen(QColor("#38bdf8" if skew_deg > 0 else "#22c55e"), 1.6))
        p.drawRoundedRect(badge_r, 4, 4)
        p.setPen(QColor("#f8fafc"))
        p.drawText(badge_r, Qt.AlignCenter, lbl)

    def _draw_cad_dimension(self, painter, qp1, qp2, label_str, color, selected=False, line_width=None, dim_font_size=None):
        dx, dy = float(qp2.x() - qp1.x()), float(qp2.y() - qp1.y())
        length = math.hypot(dx, dy)
        if length < 2.0:
            return
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux
        sc = max(0.45, self.zoom)
        lw = max(1.0, float(line_width if line_width is not None else self.active_line_width) * sc)
        if selected:
            painter.setPen(QPen(QColor("#0284c7"), lw + 4.0))
            painter.drawLine(qp1, qp2)
        painter.setPen(QPen(color, lw))
        painter.drawLine(qp1, qp2)
        ext = max(6.0, (8.0 + lw) * sc)
        slash = max(5.0, (6.0 + lw * 0.8) * sc)
        sx, sy = (ux + nx) * slash * 0.7071, (uy + ny) * slash * 0.7071
        for pt in (qp1, qp2):
            painter.drawLine(QPointF(pt.x() - nx * ext, pt.y() - ny * ext), QPointF(pt.x() + nx * ext, pt.y() + ny * ext))
            painter.drawLine(QPointF(pt.x() - sx, pt.y() - sy), QPointF(pt.x() + sx, pt.y() + sy))
        mx, my = (qp1.x() + qp2.x()) * 0.5, (qp1.y() + qp2.y()) * 0.5
        ang = math.degrees(math.atan2(dy, dx))
        if ang > 90.0: ang -= 180.0
        elif ang < -90.0: ang += 180.0
        painter.save()
        painter.translate(mx, my)
        painter.rotate(ang)
        base_pt = int(dim_font_size if dim_font_size is not None else self.font_size)
        dim_pt = max(6, int(round(base_pt * 0.85 * sc)))
        f_dim = QFont(self.font_family, dim_pt)
        f_dim.setBold(self.font_bold)
        painter.setFont(f_dim)
        tw = painter.fontMetrics().horizontalAdvance(label_str)
        tx, ty = int(-tw * 0.5), -max(4, int(round(4 + lw * 0.7)))
        painter.setPen(QPen(QColor(255, 255, 255, 235), 1))
        for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            painter.drawText(tx + ox, ty + oy, label_str)
        painter.setPen(QPen(color.darker(115) if color.lightness() > 170 else color, 1))
        painter.drawText(tx, ty, label_str)
        painter.restore()

    def keyPressEvent(self, ev):
        if self._inline_editor.isVisible():
            super().keyPressEvent(ev)
            return
        is_active_draw = (
            (self.mode == "polyline" and bool(self._pline_pts))
            or (self.mode == "area" and bool(getattr(self, "_poly_pts", [])))
            or (self.mode in ("line", "dashed", "centerline", "arrow", "measure", "calibrate") and self._p1 is not None)
            or (self.mode == "hanger_skew" and bool(getattr(self, "_skew_pts", [])))
        )
        if is_active_draw:
            if ev.key() == Qt.Key_C and self.mode == "polyline" and len(self._pline_pts) >= 3:
                self._finish_polyline(close_loop=True); ev.accept(); return
            if ev.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space) and not self._dyn_input_buf and not self._dyn_ang_buf:
                if self.mode == "polyline":
                    self._finish_polyline(close_loop=False)
                elif self.mode == "area" and len(getattr(self, "_poly_pts", [])) >= 3:
                    self._finish_area_polygon()
                self._p1 = None; self._p2 = None; self._skew_pts.clear()
                self._hide_hud_boxes()
                self.update(); ev.accept(); return
            if ev.key() == Qt.Key_Backspace and not self._dyn_input_buf and not self._dyn_ang_buf:
                if self.mode == "polyline" and self._pline_pts:
                    self._pline_pts.pop()
                elif getattr(self, "_skew_pts", []):
                    self._skew_pts.pop()
                else:
                    self._p1 = None; self._p2 = None; self._hide_hud_boxes()
                self.update(); ev.accept(); return
            if ev.key() in (Qt.Key_Escape, Qt.Key_Delete):
                self._pline_pts.clear(); self._p1 = None; self._p2 = None; self._drag_start = None; self._drag_cur = None
                if hasattr(self, "_skew_pts"):
                    self._skew_pts.clear()
                self._hide_hud_boxes()
                self.update(); ev.accept(); return

        active_p0 = (self._from_pdf_pt(*self._pline_pts[-1]) if (self.mode == "polyline" and self._pline_pts) else (self._p1 or self._drag_start))
        active_p1 = self._hover_pt or self._drag_cur
        if active_p0 and active_p1 and self.mode in ("measure", "polyline", "line", "arrow", "dashed", "centerline"):
            if ev.key() == Qt.Key_Tab:
                self._dyn_field = "ang" if self._dyn_field == "len" else "len"
                self.update(); ev.accept(); return
            ch = ev.text()
            if ch and ch in "0123456789.-":
                if self._dyn_field == "ang":
                    self._dyn_ang_buf += ch
                else:
                    self._dyn_input_buf += ch
                self.update(); ev.accept(); return
            if ev.key() == Qt.Key_Backspace:
                if self._dyn_field == "ang" and self._dyn_ang_buf:
                    self._dyn_ang_buf = self._dyn_ang_buf[:-1]; self.update(); ev.accept(); return
                elif self._dyn_input_buf:
                    self._dyn_input_buf = self._dyn_input_buf[:-1]; self.update(); ev.accept(); return
            if ev.key() in (Qt.Key_Return, Qt.Key_Enter) and (self._dyn_input_buf or self._dyn_ang_buf):
                try:
                    x1, y1 = self._to_pdf_pt(active_p0)
                    x2_raw, y2_raw = self._to_pdf_pt(active_p1)
                    ppf = max(1.0, self.pts_per_ft)
                    val_ft = float(self._dyn_input_buf) if self._dyn_input_buf else (math.hypot(x2_raw - x1, y2_raw - y1) / ppf)
                    ang = -math.radians(float(self._dyn_ang_buf)) if self._dyn_ang_buf else math.atan2(y2_raw - y1, x2_raw - x1)
                    self._dyn_input_buf = ""; self._dyn_ang_buf = ""; self._dyn_field = "len"
                    dist_pts = val_ft * ppf
                    x2, y2 = x1 + dist_pts * math.cos(ang), y1 + dist_pts * math.sin(ang)
                    if self.mode == "polyline":
                        self._pline_pts.append((x2, y2))
                        self.update(); ev.accept(); return
                    if self.mode == "measure":
                        self.markups.append({"type": "span", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "label": self._format_ft_in(val_ft), "ft": val_ft, "color": QColor(self.active_color), "line_width": float(self.active_line_width), "font_size": int(self.font_size)})
                        self.on_span_measured(val_ft); self._p1 = None; self._p2 = None
                    else:
                        self.markups.append({"type": self.mode, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "color": QColor(self.active_color), "line_width": float(self.active_line_width)})
                        self._drag_start = None; self._drag_cur = None
                    self.selected_idx = len(self.markups) - 1; self.update(); ev.accept(); return
                except ValueError:
                    self._dyn_input_buf = ""; self._dyn_ang_buf = ""; self._dyn_field = "len"
        if ev.key() == Qt.Key_Z and (ev.modifiers() & Qt.ControlModifier):
            self.undo_last_markup()
            ev.accept()
            return
        if ev.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected_markup()
            ev.accept()
            return
        hotkey_map = {
            Qt.Key_M: "measure", Qt.Key_P: "polyline", Qt.Key_C: "count", Qt.Key_T: "text",
            Qt.Key_Q: "callout", Qt.Key_A: "arrow", Qt.Key_L: "line",
            Qt.Key_R: "cloud", Qt.Key_W: "weld", Qt.Key_G: "grid_bubble",
            Qt.Key_V: "select",
        }
        if ev.key() in hotkey_map and not (ev.modifiers() & (Qt.ControlModifier | Qt.AltModifier)):
            self.set_interaction_mode(hotkey_map[ev.key()])
            ev.accept()
            return
        super().keyPressEvent(ev)

    def toggle_snap_grid(self):
        self.show_grid = not getattr(self, 'show_grid', False)
        self.update()
        return self.show_grid

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform, True)

        for hl in self.key_highlights:
            col = hl["color"]
            x0, y0, x1, y1 = hl["rect"]
            p.setBrush(QColor(col.red(), col.green(), col.blue(), 65))
            p.setPen(QPen(col, 2))
            p.drawRoundedRect(QRect(self._from_pdf_pt(x0, y0), self._from_pdf_pt(x1, y1)).adjusted(-1, 0, 1, 0), 2, 2)
            if hl.get("seg"):
                sx1, sy1, sx2, sy2 = hl["seg"]
                p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 190), 5, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(self._from_pdf_pt(sx1, sy1), self._from_pdf_pt(sx2, sy2))

        for idx, m in enumerate(self.markups):
            is_sel = (idx == self.selected_idx)
            mtype = m.get("type")
            if "dims" in self.hidden_layers and mtype in ("span", "angle", "area"): continue
            if "welds" in self.hidden_layers and mtype in ("weld", "grid_bubble", "centerline"): continue
            if "notes" in self.hidden_layers and mtype in ("text", "callout", "cloud", "highlight"): continue
            col = m.get("color", self.active_color)
            if mtype == "free_highlight":
                qpts = [self._from_pdf_pt(px, py) for px, py in m.get("pts", [])]
                if len(qpts) >= 2:
                    from PySide6.QtGui import QPainterPath
                    path = QPainterPath(QPointF(qpts[0]))
                    for qp in qpts[1:]:
                        path.lineTo(QPointF(qp))
                    hl_c = QColor(col.red(), col.green(), col.blue(), 95)
                    w_px = max(8.0, float(m.get("line_width", 14.0)) * self.zoom)
                    if is_sel:
                        p.setPen(QPen(QColor("#0284c7"), w_px + 3.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                        p.drawPath(path)
                    p.setBrush(Qt.NoBrush)
                    p.setPen(QPen(hl_c, w_px, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    p.drawPath(path)
            elif mtype == "highlight":
                r_hl = QRect(self._from_pdf_pt(m["x1"], m["y1"]), self._from_pdf_pt(m["x2"], m["y2"])).normalized()
                p.setBrush(QColor(col.red(), col.green(), col.blue(), 55))
                p.setPen(QPen(QColor("#0284c7") if is_sel else col, max(1.5, float(m.get("line_width", 2.0)) * self.zoom)))
                p.drawRoundedRect(r_hl, 4, 4)
            elif mtype == "filled_box":
                r_fb = QRect(self._from_pdf_pt(m["x1"], m["y1"]), self._from_pdf_pt(m["x2"], m["y2"])).normalized()
                p.setBrush(QColor(col.red(), col.green(), col.blue(), 255))
                brd_c = QColor("#0284c7") if is_sel else (QColor("#cbd5e1") if col == QColor("#ffffff") else col)
                p.setPen(QPen(brd_c, max(1.0, float(m.get("line_width", 1.5)) * self.zoom)))
                p.drawRect(r_fb)
            elif mtype in ("dashed", "centerline"):
                qp1, qp2 = self._from_pdf_pt(m["x1"], m["y1"]), self._from_pdf_pt(m["x2"], m["y2"])
                p.setPen(QPen(QColor("#0284c7") if is_sel else col, max(1.5, float(m.get("line_width", 2.0)) * self.zoom), Qt.DashDotLine))
                p.drawLine(qp1, qp2)
                if mtype == "centerline":
                    p.setFont(QFont("Arial", max(8, int(round(11 * max(0.5, self.zoom)))), QFont.Bold))
                    p.drawText(qp2.x() + 5, qp2.y() + 4, "CL")
            elif mtype == "weld":
                qp1, qp2 = self._from_pdf_pt(m["x1"], m["y1"]), self._from_pdf_pt(m["x2"], m["y2"])
                lw = max(1.5, float(m.get("line_width", 2.0)) * self.zoom)
                p.setPen(QPen(QColor("#0284c7") if is_sel else col, lw))
                dir_x = 1 if qp2.x() >= qp1.x() else -1
                tail_x = qp2.x() + dir_x * int(55 * self.zoom)
                p.drawLine(qp1, qp2); p.drawLine(qp2, QPoint(tail_x, qp2.y()))
                mid_x = (qp2.x() + tail_x) // 2
                sz = int(12 * self.zoom)
                p.drawPolygon([QPoint(mid_x - sz // 2, qp2.y()), QPoint(mid_x - sz // 2, qp2.y() - sz), QPoint(mid_x + sz // 2, qp2.y())])
                p.setFont(QFont("Arial", max(8, int(round(10 * max(0.5, self.zoom)))), QFont.Bold))
                p.drawText(min(qp2.x(), tail_x), qp2.y() - sz - 3, m.get("label", ""))
            elif mtype == "grid_bubble":
                qp = self._from_pdf_pt(m["x"], m["y"])
                r_px = max(12, int(16 * self.zoom))
                p.setBrush(QColor(255, 255, 255, 240))
                p.setPen(QPen(QColor("#0284c7") if is_sel else col, max(1.8, float(m.get("line_width", 2.0)) * self.zoom)))
                p.drawEllipse(qp, r_px, r_px)
                p.setFont(QFont("Arial", max(8, int(round(11 * max(0.5, self.zoom)))), QFont.Bold))
                p.drawText(QRect(qp.x() - r_px, qp.y() - r_px, r_px * 2, r_px * 2), Qt.AlignCenter, m.get("label", "A"))
            elif mtype == "callout":
                qp1, qp2 = self._from_pdf_pt(m["x1"], m["y1"]), self._from_pdf_pt(m["x2"], m["y2"])
                lw = max(1.5, float(m.get("line_width", 2.0)) * self.zoom)
                pen_c = QColor("#0284c7") if is_sel else col
                p.setPen(QPen(pen_c, lw))
                dir_x = 1 if qp2.x() >= qp1.x() else -1
                knee = QPoint(qp2.x() - dir_x * int(14 * self.zoom), qp2.y())
                p.drawLine(qp1, knee); p.drawLine(knee, qp2)
                ang = math.atan2(qp1.y() - knee.y(), qp1.x() - knee.x())
                ah = max(8.0, 10.0 * self.zoom)
                p.drawLine(qp1, QPointF(qp1.x() - ah * math.cos(ang - 0.42), qp1.y() - ah * math.sin(ang - 0.42)))
                p.drawLine(qp1, QPointF(qp1.x() - ah * math.cos(ang + 0.42), qp1.y() - ah * math.sin(ang + 0.42)))
                f_co = QFont(m.get("font_family", self.font_family), max(8, int(round(int(m.get("font_size", 14)) * 0.85 * self.zoom))))
                f_co.setBold(bool(m.get("bold", True)))
                f_co.setItalic(bool(m.get("italic", False)))
                p.setFont(f_co)
                fm = p.fontMetrics()
                lines_co = str(m.get("text", "")).splitlines() or ["CALLOUT"]
                bw = max(fm.horizontalAdvance(ln) for ln in lines_co) + int(14 * self.zoom)
                bh = fm.height() * len(lines_co) + int(10 * self.zoom)
                bx = qp2.x() if dir_x >= 0 else qp2.x() - bw
                by = qp2.y() - bh // 2
                box_r = QRect(bx, by, bw, bh)
                p.setBrush(QColor(255, 255, 255, 240))
                p.setPen(QPen(pen_c, lw))
                p.drawRoundedRect(box_r, 3, 3)
                p.setPen(QPen(col, 1))
                p.drawText(box_r.adjusted(int(7 * self.zoom), int(4 * self.zoom), -int(5 * self.zoom), -int(4 * self.zoom)), Qt.AlignLeft | Qt.AlignVCenter, str(m.get("text", "")))
            elif mtype == "cloud":
                r_cl = QRect(self._from_pdf_pt(m["x1"], m["y1"]), self._from_pdf_pt(m["x2"], m["y2"])).normalized()
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor("#0284c7") if is_sel else col, max(1.8, float(m.get("line_width", 2.0)) * self.zoom)))
                step = max(14, int(18 * self.zoom))
                x0, y0, x1, y1 = r_cl.left(), r_cl.top(), r_cl.right(), r_cl.bottom()
                for cx in range(x0, max(x0 + 1, x1 - step // 2), step):
                    p.drawArc(cx, y0 - step // 2, step, step, 0, 180 * 16)
                    p.drawArc(cx, y1 - step // 2, step, step, 180 * 16, 180 * 16)
                for cy in range(y0, max(y0 + 1, y1 - step // 2), step):
                    p.drawArc(x0 - step // 2, cy, step, step, 90 * 16, 180 * 16)
                    p.drawArc(x1 - step // 2, cy, step, step, 270 * 16, 180 * 16)
            elif mtype == "area":
                qpts = [self._from_pdf_pt(px, py) for px, py in m.get("pts", [])]
                if len(qpts) >= 3:
                    from PySide6.QtGui import QPolygon
                    poly = QPolygon(qpts)
                    p.setBrush(QColor(col.red(), col.green(), col.blue(), 45))
                    p.setPen(QPen(QColor("#0284c7") if is_sel else col, max(1.5, float(m.get("line_width", 2.0)) * self.zoom)))
                    p.drawPolygon(poly)
                    ctr = poly.boundingRect().center()
                    p.setFont(QFont(self.font_family, max(8, int(round(int(m.get("font_size", 14)) * 0.8 * self.zoom))), QFont.Bold))
                    p.drawText(ctr.x() - 45, ctr.y(), m.get("label", ""))
            elif mtype == "ellipse":
                r_el = QRect(self._from_pdf_pt(m["x1"], m["y1"]), self._from_pdf_pt(m["x2"], m["y2"])).normalized()
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor("#0284c7") if is_sel else col, max(1.5, float(m.get("line_width", 2.0)) * self.zoom)))
                p.drawEllipse(r_el)
            elif mtype == "polyline":
                qpts = [self._from_pdf_pt(px, py) for px, py in m.get("pts", [])]
                if len(qpts) >= 2:
                    p.setBrush(Qt.NoBrush)
                    p.setPen(QPen(QColor("#0284c7") if is_sel else col, max(2.0, float(m.get("line_width", 2.0)) * self.zoom), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    for i in range(len(qpts) - 1):
                        p.drawLine(qpts[i], qpts[i + 1])
            elif mtype == "line":
                qp1, qp2 = self._from_pdf_pt(m["x1"], m["y1"]), self._from_pdf_pt(m["x2"], m["y2"])
                p.setPen(QPen(QColor("#0284c7") if is_sel else col, max(1.5, float(m.get("line_width", 2.0)) * self.zoom)))
                p.drawLine(qp1, qp2)
            elif mtype == "angle":
                qp1, qp2 = self._from_pdf_pt(m["x1"], m["y1"]), self._from_pdf_pt(m["x2"], m["y2"])
                corner = QPoint(qp2.x(), qp1.y())
                lw = max(1.5, float(m.get("line_width", 2.0)) * self.zoom)
                p.setPen(QPen(QColor("#0284c7") if is_sel else col, lw))
                p.drawLine(qp1, qp2)
                p.setPen(QPen(col, max(1.0, lw * 0.75), Qt.DashLine))
                p.drawLine(qp1, corner); p.drawLine(corner, qp2)
                p.setFont(QFont(self.font_family, max(8, int(round(int(m.get("font_size", 14)) * 0.8 * self.zoom))), QFont.Bold))
                p.setPen(QPen(col, 1))
                p.drawText(int((qp1.x() + qp2.x()) * 0.5), int((qp1.y() + qp2.y()) * 0.5) - 6, m.get("label", ""))
            elif mtype == "arrow":
                qp1, qp2 = self._from_pdf_pt(m["x1"], m["y1"]), self._from_pdf_pt(m["x2"], m["y2"])
                lw = max(1.5, float(m.get("line_width", 2.0)) * self.zoom)
                p.setPen(QPen(QColor("#0284c7") if is_sel else col, lw))
                p.drawLine(qp1, qp2)
                ang = math.atan2(qp2.y() - qp1.y(), qp2.x() - qp1.x())
                ah = max(8.0, 11.0 * self.zoom)
                p.drawLine(qp2, QPointF(qp2.x() - ah * math.cos(ang - 0.42), qp2.y() - ah * math.sin(ang - 0.42)))
                p.drawLine(qp2, QPointF(qp2.x() - ah * math.cos(ang + 0.42), qp2.y() - ah * math.sin(ang + 0.42)))
            elif mtype == "span":
                self._draw_cad_dimension(p, self._from_pdf_pt(m["x1"], m["y1"]), self._from_pdf_pt(m["x2"], m["y2"]), m["label"], col, selected=is_sel, line_width=m.get("line_width", 2.0), dim_font_size=m.get("font_size", 18))
            elif mtype == "count":
                qpc = self._from_pdf_pt(m["x"], m["y"])
                rad = max(7, int(round(13 * self.zoom)))
                badge = QRect(qpc.x() - rad, qpc.y() - rad, rad * 2, rad * 2)
                p.setBrush(col)
                p.setPen(QPen(QColor("#0284c7") if is_sel else QColor("#ffffff"), 2.5 if is_sel else 1.5))
                p.drawEllipse(badge)
                p.setFont(QFont("Cascadia Mono", max(6, int(round(10 * self.zoom))), QFont.Bold))
                p.drawText(badge, Qt.AlignCenter, str(m["num"]))
            elif mtype == "hanger_skew":
                qh1 = self._from_pdf_pt(m["hx1"], m["hy1"])
                qh2 = self._from_pdf_pt(m["hx2"], m["hy2"])
                qj = self._from_pdf_pt(m["jx"], m["jy"])
                self._draw_hanger_skew_diagram(p, qh1, qh2, qj, col, lw=max(1.8, float(m.get("line_width", 2.0)) * self.zoom), font_pt=max(8, int(round(10 * self.zoom))))
            elif mtype == "cad_shape":
                q0 = self._from_pdf_pt(m["x"], m["y"])
                inv = (self.render_dpi * self.zoom) / 72.0
                w_px = m.get("w_pts", 180.0) * inv
                h_px = m.get("h_pts", 140.0) * inv
                sd = m.get("shape", {})
                kind = sd.get("kind", "right")
                lw = max(1.6, float(m.get("line_width", 2.0)) * self.zoom)
                if is_sel:
                    p.setBrush(Qt.NoBrush)
                    p.setPen(QPen(QColor("#0284c7"), 1.5, Qt.DashLine))
                    p.drawRect(QRect(int(q0.x() - 8), int(q0.y() - 8), int(w_px + 16), int(h_px + 16)))
                p.setFont(QFont("Segoe UI", max(7, int(round(10 * self.zoom))), QFont.Bold))
                if kind == "right":
                    p1 = QPointF(q0.x(), q0.y() + h_px)
                    p2 = QPointF(q0.x() + w_px, q0.y() + h_px)
                    p3 = QPointF(q0.x() + w_px, q0.y())
                    p.setBrush(QColor(col.red(), col.green(), col.blue(), 28))
                    p.setPen(QPen(col, lw))
                    p.drawPolygon([p1.toPoint(), p2.toPoint(), p3.toPoint()])
                    p.drawText(int(q0.x() + w_px * 0.35), int(q0.y() + h_px + 14 * self.zoom), f"Run: {sd.get('run_s', '')}")
                    p.drawText(int(q0.x() + w_px + 6 * self.zoom), int(q0.y() + h_px * 0.5), f"Rise: {sd.get('rise_s', '')}")
                    p.drawText(int(q0.x() + w_px * 0.15), int(q0.y() + h_px * 0.45), f"Hyp: {sd.get('hyp_s', '')}")
                elif kind == "oblique":
                    a, b, C_rad = float(sd.get("a", 10.0)), float(sd.get("b", 14.0)), math.radians(float(sd.get("C", 60.0)))
                    ax, ay = a * math.cos(C_rad), a * math.sin(C_rad)
                    min_x, max_x, max_y = min(0.0, b, ax), max(0.0, b, ax), max(0.01, ay)
                    sc = min(w_px / max(0.01, max_x - min_x), h_px / max_y)
                    ox = q0.x() - min_x * sc
                    oy = q0.y() + h_px
                    qp0, qp1, qp2 = QPoint(int(ox), int(oy)), QPoint(int(ox + b * sc), int(oy)), QPoint(int(ox + ax * sc), int(oy - ay * sc))
                    p.setBrush(QColor(col.red(), col.green(), col.blue(), 28))
                    p.setPen(QPen(col, lw))
                    p.drawPolygon([qp0, qp1, qp2])
                    p.drawText(int((qp0.x() + qp1.x()) * 0.5 - 20), int(oy + 14 * self.zoom), f"B: {b:.2f}'")
                    p.drawText(int((qp0.x() + qp2.x()) * 0.5 - 38), int((qp0.y() + qp2.y()) * 0.5), f"A: {a:.2f}'")
                    p.drawText(int((qp1.x() + qp2.x()) * 0.5 + 6), int((qp1.y() + qp2.y()) * 0.5), f"C: {sd.get('c_s', '')}")
                elif kind == "circle":
                    r_px = min(w_px, h_px) * 0.5
                    cx, cy = q0.x() + r_px, q0.y() + r_px
                    n = max(2, int(sd.get("n", 8)))
                    p.setBrush(Qt.NoBrush); p.setPen(QPen(col, lw))
                    p.drawEllipse(QPointF(cx, cy), r_px, r_px)
                    p.setBrush(col)
                    for bi in range(n):
                        ang = (2.0 * math.pi * bi) / n - math.pi * 0.5
                        p.drawEllipse(QPointF(cx + r_px * math.cos(ang), cy + r_px * math.sin(ang)), max(3.0, 4.0 * self.zoom), max(3.0, 4.0 * self.zoom))
                    p.drawText(int(q0.x()), int(q0.y() + r_px * 2 + 14 * self.zoom), f"BC {sd.get('dia_in', 24):.2f}\" | {n} Holes ({sd.get('bolt_chord', 0):.3f}\" chord)")
            elif mtype == "text":
                qpt = self._from_pdf_pt(m["x"], m["y"])
                pt_sz = max(7, int(round(int(m.get("font_size", 13)) * self.zoom)))
                f_obj = QFont(m.get("font_family", "Arial"), pt_sz)
                f_obj.setBold(bool(m.get("bold", True)))
                f_obj.setItalic(bool(m.get("italic", False)))
                p.setFont(f_obj)
                txt = m["text"]
                if is_sel:
                    fm = p.fontMetrics()
                    p.setBrush(Qt.NoBrush)
                    p.setPen(QPen(QColor("#0284c7"), 2, Qt.DashLine))
                    p.drawRect(QRect(qpt.x() - 4, qpt.y() - fm.ascent() - 2, fm.horizontalAdvance(txt) + 8, fm.height() + 4))
                fm_t = p.fontMetrics()
                for li, line_s in enumerate(txt.split("\n")):
                    ly = qpt.y() + li * (fm_t.lineSpacing() + 2)
                    p.setPen(QPen(QColor(255, 255, 255, 235), 1))
                    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        p.drawText(qpt.x() + ox, ly + oy, line_s)
                    p.setPen(QPen(col.darker(115) if col.lightness() > 170 else col, 1))
                    p.drawText(qpt.x(), ly, line_s)

        if self.mode in ("box", "highlight", "filled_box") and self._drag_start and self._drag_cur:
            p.setBrush(QColor(self.active_color.red(), self.active_color.green(), self.active_color.blue(), 45))
            p.setPen(QPen(self.active_color, max(1.5, float(self.active_line_width) * self.zoom), Qt.SolidLine))
            p.drawRect(QRect(self._drag_start, self._drag_cur).normalized())
        elif self.mode == "cloud" and self._drag_start and self._drag_cur:
            r_cl = QRect(self._drag_start, self._drag_cur).normalized()
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(self.active_color, 2, Qt.SolidLine))
            step = max(14, int(18 * self.zoom))
            x0, y0, x1, y1 = r_cl.left(), r_cl.top(), r_cl.right(), r_cl.bottom()
            for cx in range(x0, max(x0 + 1, x1 - step // 2), step):
                p.drawArc(cx, y0 - step // 2, step, step, 0, 180 * 16)
                p.drawArc(cx, y1 - step // 2, step, step, 180 * 16, 180 * 16)
            for cy in range(y0, max(y0 + 1, y1 - step // 2), step):
                p.drawArc(x0 - step // 2, cy, step, step, 90 * 16, 180 * 16)
                p.drawArc(x1 - step // 2, cy, step, step, 270 * 16, 180 * 16)
        elif self.mode == "ellipse" and self._drag_start and self._drag_cur:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(self.active_color, max(1.5, float(self.active_line_width) * self.zoom), Qt.SolidLine))
            p.drawEllipse(QRect(self._drag_start, self._drag_cur).normalized())
        elif self.mode == "callout" and self._drag_start and self._drag_cur:
            qp1, qp2 = self._drag_start, self._drag_cur
            p.setPen(QPen(self.active_color, max(1.5, float(self.active_line_width) * self.zoom)))
            dir_x = 1 if qp2.x() >= qp1.x() else -1
            knee = QPoint(qp2.x() - dir_x * int(14 * self.zoom), qp2.y())
            p.drawLine(qp1, knee); p.drawLine(knee, qp2)
            ang = math.atan2(qp1.y() - knee.y(), qp1.x() - knee.x())
            ah = max(8.0, 10.0 * self.zoom)
            p.drawLine(qp1, QPointF(qp1.x() - ah * math.cos(ang - 0.42), qp1.y() - ah * math.sin(ang - 0.42)))
            p.drawLine(qp1, QPointF(qp1.x() - ah * math.cos(ang + 0.42), qp1.y() - ah * math.sin(ang + 0.42)))
            p.setBrush(QColor(255, 255, 255, 235))
            bx = qp2.x() if dir_x >= 0 else qp2.x() - 120
            p.drawRoundedRect(QRect(bx, qp2.y() - 16, 120, 32), 3, 3)
        elif self.mode in ("arrow", "line", "angle", "dashed") and self._drag_start and self._drag_cur:
            p.setPen(QPen(self.active_color, max(1.5, float(self.active_line_width) * self.zoom), Qt.SolidLine))
            p.drawLine(self._drag_start, self._drag_cur)
            if self.mode == "angle":
                c_pt = QPoint(self._drag_cur.x(), self._drag_start.y())
                p.drawLine(self._drag_start, c_pt); p.drawLine(c_pt, self._drag_cur)
                dx_a, dy_a = abs(self._drag_cur.x() - self._drag_start.x()), abs(self._drag_cur.y() - self._drag_start.y())
                deg = math.degrees(math.atan2(dy_a, max(1.0, dx_a)))
                pitch = (dy_a / max(1.0, dx_a)) * 12.0
                p.drawText(self._drag_cur.x() + 8, self._drag_cur.y() - 6, f"{deg:.1f} deg | {pitch:.1f}:12")
        elif self.mode in ("measure", "calibrate") and self._p1 and self._hover_pt:
            x1, y1 = self._to_pdf_pt(self._p1)
            x2, y2 = self._to_pdf_pt(self._hover_pt)
            pts_d = math.hypot(x2 - x1, y2 - y1)
            lbl = f"Calibrate ({pts_d:.1f} pts)" if self.mode == "calibrate" else self._format_ft_in(__import__('bom_pdf_engine').round_structural_ft(pts_d / max(1.0, self.pts_per_ft)))
            self._draw_cad_dimension(p, self._p1, self._hover_pt, lbl, self.active_color)

        if self.mode == "free_highlight" and len(self._free_pts) >= 2:
            from PySide6.QtGui import QPainterPath
            qpts = [self._from_pdf_pt(px, py) for px, py in self._free_pts]
            path = QPainterPath(QPointF(qpts[0]))
            for qp in qpts[1:]:
                path.lineTo(QPointF(qp))
            hl_c = QColor(self.active_color.red(), self.active_color.green(), self.active_color.blue(), 95)
            w_px = max(8.0, max(12.0, float(self.active_line_width) * 5.0) * self.zoom)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(hl_c, w_px, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)
        if self.mode == "polyline" and self._pline_pts:
            qpts = [self._from_pdf_pt(px, py) for px, py in self._pline_pts]
            p.setPen(QPen(self.active_color, max(2.0, float(self.active_line_width) * self.zoom), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            for i in range(len(qpts) - 1):
                p.drawLine(qpts[i], qpts[i + 1])
            if self._hover_pt:
                hp = self._snap_ortho(qpts[-1], self._hover_pt, getattr(self, "ortho_lock", False))
                if getattr(self, "_dyn_input_buf", "") or getattr(self, "_dyn_ang_buf", ""):
                    try:
                        x1, y1 = self._pline_pts[-1]
                        x2_raw, y2_raw = self._to_pdf_pt(hp)
                        ppf = max(1.0, self.pts_per_ft)
                        v_ft = float(self._dyn_input_buf) if self._dyn_input_buf else (math.hypot(x2_raw - x1, y2_raw - y1) / ppf)
                        a_rad = -math.radians(float(self._dyn_ang_buf)) if self._dyn_ang_buf else math.atan2(y2_raw - y1, x2_raw - x1)
                        hp = self._from_pdf_pt(x1 + v_ft * ppf * math.cos(a_rad), y1 + v_ft * ppf * math.sin(a_rad))
                        self._hover_pt = hp
                    except ValueError:
                        pass
                p.drawLine(qpts[-1], hp)
        if self.mode in ("line", "dashed", "centerline", "arrow") and self._p1 and self._hover_pt:
            hp = self._snap_ortho(self._p1, self._hover_pt, getattr(self, "ortho_lock", False))
            x1, y1 = self._to_pdf_pt(self._p1)
            x2_raw, y2_raw = self._to_pdf_pt(hp)
            ppf = max(1.0, self.pts_per_ft)
            if getattr(self, "_dyn_input_buf", "") or getattr(self, "_dyn_ang_buf", ""):
                try:
                    v_ft = float(self._dyn_input_buf) if self._dyn_input_buf else (math.hypot(x2_raw - x1, y2_raw - y1) / ppf)
                    a_rad = -math.radians(float(self._dyn_ang_buf)) if self._dyn_ang_buf else math.atan2(y2_raw - y1, x2_raw - x1)
                    hp = self._from_pdf_pt(x1 + v_ft * ppf * math.cos(a_rad), y1 + v_ft * ppf * math.sin(a_rad))
                    x2_raw, y2_raw = self._to_pdf_pt(hp)
                except ValueError:
                    pass
            pen_style = Qt.DashLine if self.mode == "dashed" else (Qt.DashDotLine if self.mode == "centerline" else Qt.SolidLine)
            p.setPen(QPen(self.active_color, max(2.0, float(self.active_line_width) * self.zoom), pen_style, Qt.RoundCap, Qt.RoundJoin))
            p.drawLine(self._p1, hp)
        if self.mode == "hanger_skew" and self._skew_pts and self._hover_pt is not None:
            pts_iter = iter(self._skew_pts)
            p_a = next(pts_iter, None)
            p_b = next(pts_iter, None)
            if p_a is not None and p_b is None:
                qh1 = self._from_pdf_pt(*p_a)
                qh2 = self._snap_ortho(qh1, self._hover_pt, getattr(self, "ortho_lock", False))
                p.setPen(QPen(self.active_color, max(2.2, float(self.active_line_width) * self.zoom), Qt.SolidLine))
                p.drawLine(qh1, qh2)
                p.setFont(QFont("Segoe UI", 9, QFont.Bold))
                p.setPen(QColor("#0369a1"))
                p.drawText(int(qh2.x() + 12), int(qh2.y() - 8), "Click 2: Set T-pivot point on header / wall")
            elif p_a is not None and p_b is not None:
                qh1 = self._from_pdf_pt(*p_a)
                qh2 = self._from_pdf_pt(*p_b)
                self._draw_hanger_skew_diagram(p, qh1, qh2, self._hover_pt, self.active_color, lw=max(2.2, float(self.active_line_width) * self.zoom), font_pt=10)
        if self.mode == "area" and self._poly_pts:
            qpts = [self._from_pdf_pt(px, py) for px, py in self._poly_pts]
            p.setPen(QPen(self.active_color, max(1.5, float(self.active_line_width) * self.zoom), Qt.SolidLine))
            for i in range(len(qpts) - 1):
                p.drawLine(qpts[i], qpts[i + 1])
            if self._hover_pt:
                p.drawLine(qpts[-1], self._hover_pt)

        if self._inline_editor.isVisible() and self._inline_callout_pts is not None:
            cx0, cy0, cx1, cy1 = self._inline_callout_pts
            qp1, qp2 = self._from_pdf_pt(cx0, cy0), self._from_pdf_pt(cx1, cy1)
            p.setPen(QPen(self.active_color, max(1.5, float(self.active_line_width) * self.zoom)))
            dir_x = 1 if qp2.x() >= qp1.x() else -1
            knee = QPoint(qp2.x() - dir_x * int(14 * self.zoom), qp2.y())
            p.drawLine(qp1, knee); p.drawLine(knee, qp2)
            ang = math.atan2(qp1.y() - knee.y(), qp1.x() - knee.x())
            ah = max(8.0, 10.0 * self.zoom)
            p.drawLine(qp1, QPointF(qp1.x() - ah * math.cos(ang - 0.42), qp1.y() - ah * math.sin(ang - 0.42)))
            p.drawLine(qp1, QPointF(qp1.x() - ah * math.cos(ang + 0.42), qp1.y() - ah * math.sin(ang + 0.42)))

        if self.legend_entries:
            sc = max(0.45, self.zoom)
            leg_pt = max(6, int(round(10 * sc)))
            p.setFont(QFont("Cascadia Mono", leg_pt, QFont.Bold))
            fm_l = p.fontMetrics()
            row_h = fm_l.height() + max(3, int(round(6 * sc)))
            hdr_h = max(16, int(round(24 * sc)))
            pad_x = max(5, int(round(9 * sc)))
            sw_sz = max(7, int(round(12 * sc)))
            max_txt_w = max([fm_l.horizontalAdvance("STEEL COLOR KEY")] + [fm_l.horizontalAdvance(f"{pr} ({cn})") for pr, _, cn in self.legend_entries])
            box_w = max_txt_w + sw_sz + pad_x * 3 + 6
            box_h = hdr_h + max(4, int(round(6 * sc))) + len(self.legend_entries) * row_h
            tl = self._from_pdf_pt(self.legend_pdf_pos[0], self.legend_pdf_pos[1])
            self._legend_rect_px = QRect(tl.x(), tl.y(), box_w, box_h)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor("#0f172a"), max(1.0, 1.8 * sc)))
            p.drawRect(self._legend_rect_px)
            p.drawLine(tl.x(), tl.y() + hdr_h, tl.x() + box_w, tl.y() + hdr_h)
            p.setPen(QPen(QColor("#000000"), 1))
            p.drawText(QRect(tl.x() + pad_x, tl.y() + 2, box_w - pad_x * 2, hdr_h - 3), Qt.AlignLeft | Qt.AlignVCenter, "STEEL COLOR KEY")
            for i, (prof, col, cnt) in enumerate(self.legend_entries):
                ry = tl.y() + hdr_h + 3 + i * row_h
                sy = ry + max(1, (row_h - sw_sz) // 2)
                p.setBrush(col)
                p.setPen(QPen(QColor("#0f172a"), 1.0))
                p.drawRect(tl.x() + pad_x, sy, sw_sz, sw_sz)
                tx = tl.x() + pad_x * 2 + sw_sz
                tw_box = box_w - (pad_x * 2 + sw_sz) - 4
                p.setPen(QPen(QColor(255, 255, 255, 230), 1))
                for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    p.drawText(QRect(tx + ox, ry + oy, tw_box, row_h), Qt.AlignLeft | Qt.AlignVCenter, f"{prof} ({cnt})")
                p.setPen(QPen(QColor("#000000"), 1))
                p.drawText(QRect(tx, ry, tw_box, row_h), Qt.AlignLeft | Qt.AlignVCenter, f"{prof} ({cnt})")
        else:
            self._legend_rect_px = QRect()
        for g_a, g_b, g_anchor in getattr(self, "_track_guides", []):
            p.setPen(QPen(QColor(22, 163, 74, 175), 1.1, Qt.DashLine))
            p.drawLine(g_a, g_b)
            p.setPen(QPen(QColor("#16a34a"), 1.6))
            p.drawLine(g_anchor.x() - 4, g_anchor.y(), g_anchor.x() + 4, g_anchor.y())
            p.drawLine(g_anchor.x(), g_anchor.y() - 4, g_anchor.x(), g_anchor.y() + 4)
        ti = getattr(self, "_track_intersection", None)
        if ti is not None:
            p.setPen(QPen(QColor("#16a34a"), 1.8))
            p.drawLine(ti.x() - 6, ti.y(), ti.x() + 6, ti.y())
            p.drawLine(ti.x(), ti.y() - 6, ti.x(), ti.y() + 6)
        if self._snap_badge_pt is not None:
            sp = self._snap_badge_pt
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor("#16a34a"), 2.0))
            if getattr(self, "_snap_kind", "endpoint") == "midpoint":
                p.drawPolygon([QPoint(int(sp.x()), int(sp.y()) - 6), QPoint(int(sp.x()) - 6, int(sp.y()) + 5), QPoint(int(sp.x()) + 6, int(sp.y()) + 5)])
            else:
                p.drawRect(QRect(int(sp.x()) - 5, int(sp.y()) - 5, 10, 10))

        # Dynamic full-page CAD XY axis crosshairs & bottom-left UCS XY triad
        if self._hover_pt is not None and self.mode in ("measure", "polyline", "line", "arrow", "dashed", "centerline", "angle", "area", "callout", "calibrate"):
            hx, hy = int(self._hover_pt.x()), int(self._hover_pt.y())
            p.setPen(QPen(QColor(2, 132, 199, 65), 1.0, Qt.DotLine))
            p.drawLine(hx, 0, hx, self.height())
            p.drawLine(0, hy, self.width(), hy)

        # Multi-selection cyan bounding boxes & AutoCAD Window/Crossing Marquee Box
        for s_idx in getattr(self, "selected_indices", set()):
            if 0 <= s_idx < len(self.markups):
                sm = self.markups[s_idx]
                if sm.get("type") == "hanger_skew":
                    p.setBrush(QColor("#0284c7"))
                    p.setPen(QPen(QColor("#ffffff"), 1.2))
                    for gx, gy in ((sm["hx1"], sm["hy1"]), (sm["hx2"], sm["hy2"]), (sm["jx"], sm["jy"])):
                        gp = self._from_pdf_pt(gx, gy)
                        p.drawRect(QRect(gp.x() - 4, gp.y() - 4, 8, 8))
                else:
                    sr = self._markup_screen_rect(sm).adjusted(-4, -4, 4, 4)
                    if not sr.isNull():
                        p.setBrush(Qt.NoBrush)
                        p.setPen(QPen(QColor("#0284c7"), 1.5, Qt.DashLine))
                        p.drawRect(sr)
        if self._marquee_start is not None and self._marquee_cur is not None:
            mr = QRect(self._marquee_start, self._marquee_cur).normalized()
            crossing = self._marquee_cur.x() < self._marquee_start.x()
            p.setBrush(QColor(22, 163, 74, 38) if crossing else QColor(2, 132, 199, 38))
            p.setPen(QPen(QColor("#16a34a" if crossing else "#0284c7"), 1.5, Qt.DashLine if crossing else Qt.SolidLine))
            p.drawRect(mr)

        # Live 1:1 planset-scaled ghost preview for click-to-place CAD geometry
        if getattr(self, "_pending_cad_shape", None) is not None and self._hover_pt is not None:
            ps = self._pending_cad_shape
            inv = (self.render_dpi * self.zoom) / 72.0
            gx, gy = float(self._hover_pt.x()), float(self._hover_pt.y())
            p.setBrush(QColor(2, 132, 199, 36))
            p.setPen(QPen(QColor("#0284c7"), 1.6, Qt.DashLine))
            if ps.get("type") == "text":
                p.setFont(QFont("Cascadia Mono", 9, QFont.Bold))
                p.drawText(int(gx), int(gy), f"Click to place note: {ps.get('text', '')}")
            else:
                gw = max(6.0, ps.get("w_pts", 24.0) * inv)
                gh = max(6.0, ps.get("h_pts", 24.0) * inv)
                sd = ps.get("shape", {})
                kind = sd.get("kind", "right")
                if kind == "circle":
                    p.drawEllipse(QRectF(gx, gy, gw, gh))
                    n_b = max(2, int(sd.get("n", 8)))
                    cx_g, cy_g, r_g = gx + gw * 0.5, gy + gh * 0.5, min(gw, gh) * 0.5
                    for bi in range(n_b):
                        ang_b = (2.0 * math.pi * bi) / n_b - math.pi * 0.5
                        p.drawEllipse(QPointF(cx_g + r_g * math.cos(ang_b), cy_g + r_g * math.sin(ang_b)), 3.0, 3.0)
                elif kind == "oblique":
                    p.drawPolygon([QPointF(gx, gy + gh), QPointF(gx + gw, gy + gh), QPointF(gx + gw * 0.38, gy)])
                else:
                    p.drawPolygon([QPointF(gx, gy + gh), QPointF(gx + gw, gy + gh), QPointF(gx + gw, gy)])
                p.setFont(QFont("Cascadia Mono", 8, QFont.Bold))
                p.setPen(QColor("#0369a1"))
                p.drawText(int(gx), int(gy - 6), "Click to place (1:1 Plan Scale) | R = Rotate | Esc = Cancel")

        # Bottom-left CAD XY Origin Triad
        ox, oy = 26, self.height() - 26
        p.setPen(QPen(QColor("#dc2626"), 2.0))
        p.drawLine(ox, oy, ox + 28, oy)
        p.setPen(QPen(QColor("#16a34a"), 2.0))
        p.drawLine(ox, oy, ox, oy - 28)
        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.setPen(QPen(QColor("#dc2626"), 1)); p.drawText(ox + 31, oy + 4, "X")
        p.setPen(QPen(QColor("#16a34a"), 1)); p.drawText(ox - 4, oy - 31, "Y")

        hud_p0 = (self._from_pdf_pt(*self._pline_pts[-1]) if (self.mode == "polyline" and self._pline_pts) else (self._p1 or self._drag_start))
        hud_p1 = self._hover_pt or self._drag_cur
        if hud_p0 and hud_p1 and self.mode in ("measure", "polyline", "line", "arrow", "dashed", "centerline", "angle"):
            x1, y1 = self._to_pdf_pt(hud_p0)
            x2, y2 = self._to_pdf_pt(hud_p1)
            deg = abs(math.degrees(math.atan2(-(y2 - y1), x2 - x1))) % 180.0
            if any(abs(deg - a) < 3.5 for a in (0.0, 45.0, 90.0, 135.0, 180.0)):
                p.setPen(QPen(QColor(22, 163, 74, 180), 1.2, Qt.DashLine))
                vx, vy = float(hud_p1.x() - hud_p0.x()), float(hud_p1.y() - hud_p0.y())
                vlen = math.hypot(vx, vy)
                if vlen > 1.0:
                    ux, uy = vx / vlen, vy / vlen
                    p.drawLine(QPointF(hud_p0), QPointF(hud_p0.x() + ux * 2400.0, hud_p0.y() + uy * 2400.0))
            self._update_hud_boxes(hud_p0, hud_p1)
        elif hasattr(self, "_hud_len_edit") and self._hud_len_edit.isVisible():
            self._hide_hud_boxes()
        p.end()

class VisualTakeoffWorkspace(QWidget):
    SWATCH_HEXES = ["#0284c7", "#059669", "#ea580c", "#db2777", "#7c3aed", "#dc2626", "#0d9488", "#eab308"]

    def __init__(self, pdf_path, steel_matrix_data, get_page_fn, on_box_ocr, on_span_measured, on_count_changed, on_calibrated, parent=None, embed_in_main=False):
        super().__init__(parent)
        self.pdf_path = pdf_path
        self.steel_matrix_data = steel_matrix_data
        self.get_page_fn = get_page_fn
        if pdf_path and os.path.exists(str(pdf_path)):
            self._doc = pymupdf.open(pdf_path)
        else:
            self._doc = pymupdf.open()
            self._doc.new_page(width=1224, height=792)
        self.page_markups = {}
        self.global_color_key = {}
        self.sheet_color_keys = {}

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            VisualTakeoffWorkspace {
                background-color: transparent;
            }
            QComboBox QAbstractItemView { background-color: #eff6ff; color: #0f172a; selection-background-color: #0284c7; selection-color: #ffffff; border: 1.5px solid #0284c7; font-weight: bold; outline: none; } 
            QToolTip {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #94a3b8;
                border-radius: 5px;
                padding: 6px 9px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11.5px;
                font-weight: 500;
            }
        """)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        left_w = QWidget()
        left_l = QVBoxLayout(left_w)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(5)

        def _make_ribbon_group(title_text, accent_hex="#0284c7"):
            box = QFrame()
            box.setStyleSheet(
                f"QFrame {{ background-color: #cfe4fa; border: 1px solid #60a5fa; border-top: 3px solid {accent_hex}; border-radius: 6px; }} "
                f"QLabel {{ color: #0f172a; font-weight: bold; background: transparent; border: none; }} "
                f"QPushButton {{ background-color: #e8f3fe; border: 1px solid #60a5fa; color: #0f172a; font-weight: bold; padding: 5px 9px; border-radius: 5px; }} "
                f"QPushButton:hover {{ background-color: #dbeafe; border-color: {accent_hex}; color: #0f172a; }} "
                f"QComboBox, QFontComboBox, QSpinBox {{ background-color: #eff6ff; color: #0f172a; border: 1px solid #60a5fa; border-radius: 5px; padding: 4px 6px; font-weight: bold; }}"
            )
            vl = QVBoxLayout(box)
            vl.setContentsMargins(8, 6, 8, 4)
            vl.setSpacing(4)
            row = QHBoxLayout()
            row.setSpacing(5)
            vl.addLayout(row)
            cap = QLabel(title_text)
            cap.setAlignment(Qt.AlignCenter)
            cap.setStyleSheet("color: #334155; font-size: 10px; font-weight: 800; letter-spacing: 0.6px; border: none; background: transparent;")
            vl.addWidget(cap)
            return box, row

        self.inner_ribbon_box = QFrame()
        self.inner_ribbon_box.setVisible(not embed_in_main)
        ribbon = QHBoxLayout(self.inner_ribbon_box)
        ribbon.setContentsMargins(0, 0, 0, 0)
        ribbon.setSpacing(6)

        # Group 1: NAVIGATION
        g_nav, r_nav = _make_ribbon_group("NAVIGATION", "#38bdf8")
        self.btn_pan = QPushButton("Hand Pan")
        self.btn_pan.setToolTip("<b>Hand Pan</b><br>Click and drag to slide around the blueprint.<br><i>Tip: Hold Middle or Right-Click to pan in any mode.</i>")
        self.btn_fit = QPushButton("Fit Page")
        self.btn_fit.setToolTip("<b>Fit Page</b><br>Zoom the blueprint so the entire sheet fits cleanly inside the window.")
        btn_full = QPushButton("100% Size")
        btn_full.setToolTip("<b>100% Full Size</b><br>Reset blueprint zoom to native 100% scale for reading fine details.")
        self.btn_zm = QPushButton("Zoom -")
        self.btn_zm.setToolTip("<b>Zoom Out</b><br>Zoom out on the blueprint.<br><i>Shortcut: Ctrl + Mouse Wheel Down</i>")
        self.btn_zp = QPushButton("Zoom +")
        self.btn_zp.setToolTip("<b>Zoom In</b><br>Magnify blueprint details.<br><i>Shortcut: Ctrl + Mouse Wheel Up</i>")
        btn_print_direct = QPushButton("Print Sheet")
        btn_print_direct.setStyleSheet("QPushButton { background-color: rgba(5, 150, 105, 0.24); border: 2px solid #059669; color: #000000; font-weight: 700; font-weight: bold; } QPushButton:hover { background-color: rgba(5, 150, 105, 0.42); color: #0f172a; }")
        btn_print_direct.setToolTip("<b>Print Marked-Up Sheet</b><br>Send this blueprint with all color highlights, dimensions,<br>notes, and proportional legend straight to any Windows printer.")
        self.btn_print_pdf = QPushButton("Export PDF")
        self.btn_print_pdf.setStyleSheet("QPushButton { background-color: rgba(2, 132, 199, 0.24); border: 2px solid #0284c7; color: #000000; font-weight: 700; font-weight: bold; } QPushButton:hover { background-color: rgba(2, 132, 199, 0.42); color: #0f172a; }")
        self.btn_print_pdf.setToolTip("<b>Export Marked-Up PDF</b><br>Save a crisp vector PDF copy of this marked-up sheet.")
        for b in (self.btn_pan, self.btn_fit, btn_full, self.btn_zm, self.btn_zp, btn_print_direct, self.btn_print_pdf):
            r_nav.addWidget(b)
        ribbon.addWidget(g_nav)

        # Group 2: TAKEOFF & MEASURE
        g_tk, r_tk = _make_ribbon_group("TAKEOFF & MEASURE", "#34d399")
        self.btn_meas = QPushButton("Measure Span")
        self.btn_meas.setToolTip("<b>Measure Span</b><br>Click two endpoints to draw a CAD dimension line with ticks.<br><i>Hold Shift to snap straight (0?, 45?, 90?).</i>")
        self.btn_count = QPushButton("Count Marks")
        self.btn_count.setToolTip("<b>Count Marks</b><br>Click each beam or column on the plan<br>to drop numbered badges and auto-fill Qty.")
        self.btn_box = QPushButton("Box Read (OCR)")
        self.btn_box.setToolTip("<b>Box Read (OCR)</b><br>Drag a box around unselectable SHX callouts<br>on outlined or scanned sheets to extract steel.")
        self.btn_cal = QPushButton("Calibrate Scale")
        self.btn_cal.setToolTip("<b>Calibrate Scale</b><br>Click two ends of a known dimension<br>and enter its real length in feet.")
        self.scale_combo = QComboBox()
        self.scale_combo.setToolTip("<b>Drawing Scale</b><br>Select the architectural scale of this sheet<br>for accurate span measurements.")
        for sc_lbl, pts in [
            ("1/4\" = 1'-0\"", 18.0), ("1/8\" = 1'-0\"", 9.0), ("3/16\" = 1'-0\"", 13.5),
            ("3/8\" = 1'-0\"", 27.0), ("1/2\" = 1'-0\"", 36.0), ("3/4\" = 1'-0\"", 54.0), ("1\" = 1'-0\"", 72.0),
        ]:
            self.scale_combo.addItem(sc_lbl, pts)
        self.scale_combo.currentIndexChanged.connect(lambda: setattr(self.canvas, "pts_per_ft", float(self.scale_combo.currentData() or 18.0)))
        for w in (self.btn_meas, self.btn_count, self.btn_box, self.btn_cal, self.scale_combo):
            r_tk.addWidget(w)
        ribbon.addWidget(g_tk)

        # Group 3: TEXT & STYLE
        g_txt, r_txt = _make_ribbon_group("TEXT & STYLE", "#fbbf24")
        self.btn_text = QPushButton("Text Type")
        self.btn_text.setToolTip("<b>Text Type</b><br>Click anywhere on the sheet and type directly on the blueprint.<br><i>Enter = new line | Click outside = stamp note.</i>")
        r_txt.addWidget(self.btn_text)

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont("Arial"))
        self.font_combo.setMaximumWidth(130)
        self.font_combo.setToolTip("<b>Font Family</b><br>Choose the typeface for new<br>or selected text callouts.")
        r_txt.addWidget(self.font_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(18)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setToolTip("<b>Font Size</b><br>Set text & dimension number size in points<br>for new or selected markups.")
        r_txt.addWidget(self.font_size_spin)

        r_txt.addWidget(QLabel("Line:"))
        self.line_width_spin = QDoubleSpinBox()
        self.line_width_spin.setRange(0.5, 12.0)
        self.line_width_spin.setSingleStep(0.5)
        self.line_width_spin.setValue(2.0)
        self.line_width_spin.setSuffix(" pt")
        self.line_width_spin.setToolTip("<b>Dimension Line Thickness</b><br>Set line weight in points for new<br>or selected measurement lines.")
        r_txt.addWidget(self.line_width_spin)

        bi_qss = (
            "QPushButton { background-color: #e8f3fe; border: 1.5px solid #64748b; color: #0f172a; font-size: 16px; border-radius: 5px; padding: 0px; } "
            "QPushButton:hover { border-color: #fbbf24; color: #ffffff; } "
            "QPushButton:checked { background-color: #fbbf24; border: 1.5px solid #fef08a; color: #0f172a; }"
        )
        self.btn_bold = QPushButton("B")
        self.btn_bold.setCheckable(True)
        self.btn_bold.setChecked(True)
        self.btn_bold.setFixedSize(34, 28)
        self.btn_bold.setStyleSheet(bi_qss + " QPushButton { font-weight: 900; }")
        self.btn_bold.setToolTip("<b>Bold (B)</b><br>Toggle bold lettering on active or selected text.")
        r_txt.addWidget(self.btn_bold)

        self.btn_italic = QPushButton("I")
        self.btn_italic.setCheckable(True)
        self.btn_italic.setFixedSize(34, 28)
        self.btn_italic.setStyleSheet(bi_qss + " QPushButton { font-style: italic; font-weight: bold; font-family: 'Georgia', serif; }")
        self.btn_italic.setToolTip("<b>Italic (I)</b><br>Toggle slanted italic lettering on active or selected text.")
        r_txt.addWidget(self.btn_italic)

        for hex_c in self.SWATCH_HEXES:
            sw = QPushButton("")
            sw.setFixedSize(20, 20)
            sw.setToolTip(f"<b>Pen Color</b><br>Set color for new markups<br>or recolor the selected item.")
            sw.setStyleSheet(f"QPushButton {{ background-color: {hex_c}; border: 1.5px solid #cbd5e1; border-radius: 3px; padding: 0px; }} QPushButton:hover {{ border: 2px solid #ffffff; }}")
            sw.clicked.connect(lambda _=False, hc=hex_c: self._set_canvas_pen(QColor(hc)))
            r_txt.addWidget(sw)
        btn_custom_col = QPushButton("+")
        btn_custom_col.setFixedSize(20, 20)
        btn_custom_col.setToolTip("<b>Custom Color</b><br>Open full color wheel to pick<br>any custom pen color.")
        btn_custom_col.clicked.connect(self._pick_custom_pen)
        r_txt.addWidget(btn_custom_col)
        ribbon.addWidget(g_txt)

        # Group 4: EDIT & CLEANUP
        g_ed, r_ed = _make_ribbon_group("EDIT & CLEANUP", "#f87171")
        self.btn_sel = QPushButton("Select / Move")
        self.btn_sel.setToolTip("<b>Select / Move</b><br>Click any dimension, badge, or note to select and drag it.<br><i>Double-click text to edit | Press Delete to remove.</i>")
        self.btn_del_sel = QPushButton("Delete Selected")
        self.btn_del_sel.setToolTip("<b>Delete Selected</b><br>Remove only the currently selected markup.<br><i>Shortcut: Delete key</i>")
        self.btn_del_sel.setStyleSheet("QPushButton { background-color: rgba(220, 38, 38, 0.20); border: 2px solid #dc2626; color: #000000; font-weight: 700; font-weight: bold; } QPushButton:hover { background-color: rgba(220, 38, 38, 0.36); color: #7f1d1d; }")
        self.btn_undo = QPushButton("Undo Last")
        self.btn_undo.setToolTip("<b>Undo Last</b><br>Remove the most recent markup<br>you placed on this sheet.")
        self.btn_clr = QPushButton("Clear Sheet")
        self.btn_clr.setToolTip("<b>Clear Sheet</b><br>Erase all user markups<br>from the current sheet.")
        for b in (self.btn_sel, self.btn_del_sel, self.btn_undo, self.btn_clr):
            r_ed.addWidget(b)
        ribbon.addWidget(g_ed)
        ribbon.addStretch()
        left_l.addWidget(self.inner_ribbon_box)

        self.scroll = QScrollArea()
        self.scroll.setAlignment(Qt.AlignCenter)
        self.scroll.setWidgetResizable(False)
        self.scroll.viewport().setAutoFillBackground(False)
        self.scroll.setStyleSheet("QScrollArea, QScrollArea::viewport { background-color: rgba(241, 245, 249, 0.76); border: 1px solid #cbd5e1; border-radius: 8px; }")
        self.canvas = CadBlueprintCanvas(
            on_box_selected=on_box_ocr, on_span_measured=on_span_measured,
            on_count_changed=on_count_changed, on_calibrated=on_calibrated,
            scroll_area=self.scroll, parent=self.scroll,
        )
        self.scroll.setWidget(self.canvas)
        left_l.addWidget(self.scroll, 1)

        def _sync_font():
            self.canvas.font_family = self.font_combo.currentFont().family()
            self.canvas.font_size = int(self.font_size_spin.value())
            self.canvas.active_line_width = float(self.line_width_spin.value())
            self.canvas.font_bold = bool(self.btn_bold.isChecked())
            self.canvas.font_italic = bool(self.btn_italic.isChecked())
            if self.canvas._inline_editor.isVisible():
                self.canvas._apply_inline_style()
                self.canvas._resize_inline_editor()
            if 0 <= self.canvas.selected_idx < len(self.canvas.markups):
                m = self.canvas.markups[self.canvas.selected_idx]
                if m.get("type") == "text":
                    m["font_family"] = self.canvas.font_family
                    m["font_size"] = self.canvas.font_size
                    m["bold"] = self.canvas.font_bold
                    m["italic"] = self.canvas.font_italic
                elif m.get("type") == "span":
                    m["line_width"] = self.canvas.active_line_width
                    m["font_size"] = self.canvas.font_size
            self.canvas.update()

        self.font_combo.currentFontChanged.connect(lambda *_: _sync_font())
        self.font_size_spin.valueChanged.connect(lambda *_: _sync_font())
        self.line_width_spin.valueChanged.connect(lambda *_: _sync_font())
        self.btn_bold.toggled.connect(lambda *_: _sync_font())
        self.btn_italic.toggled.connect(lambda *_: _sync_font())

        self.btn_del_sel.clicked.connect(self.canvas.delete_selected_markup)
        self.btn_fit.clicked.connect(self.canvas.fit_to_viewport)
        btn_print_direct.clicked.connect(self._print_marked_sheet)
        self.btn_print_pdf.clicked.connect(self._export_marked_pdf)
        btn_full.clicked.connect(lambda: self.canvas.set_zoom(1.0))
        self.btn_zm.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom - 0.15))
        self.btn_zp.clicked.connect(lambda: self.canvas.set_zoom(self.canvas.zoom + 0.15))
        self.btn_undo.clicked.connect(self.canvas.undo_last_markup)
        self.btn_clr.clicked.connect(self.canvas.clear_markups)
        for b, m in ((self.btn_pan, "pan"), (self.btn_sel, "select"), (self.btn_meas, "measure"), (self.btn_count, "count"), (self.btn_text, "text"), (self.btn_box, "box"), (self.btn_cal, "calibrate")):
            b.clicked.connect(lambda _=False, md=m: self.set_mode(md))

        key_panel = QFrame()
        key_panel.setFixedWidth(300)
        key_panel.setStyleSheet("QFrame { background-color: #f8fafc; border: 1px solid #cbd5e1; border-top: 3px solid #0284c7; border-radius: 8px; } QLabel { color: #1e293b; font-weight: 600; border: none; background: transparent; } QComboBox { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 5px; padding: 4px 8px; font-weight: 600; } QPushButton { background-color: #ffffff; border: 1px solid #cbd5e1; color: #1e293b; font-weight: 600; border-radius: 5px; padding: 6px 10px; } QPushButton:hover { background-color: #e0f2fe; border-color: #0284c7; }")
        kl = QVBoxLayout(key_panel)
        kl.setContentsMargins(10, 10, 10, 10)
        kl.setSpacing(8)

        khdr = QLabel("STEEL MEMBER COLOR KEY")
        khdr.setStyleSheet("color: #0369a1; font-size: 15px; font-weight: 800; border: none;")
        kl.addWidget(khdr)

        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("Scope:"))
        self.key_scope_combo = QComboBox()
        self.key_scope_combo.addItem("Whole Planset (All Sheets)", "global")
        self.key_scope_combo.addItem("This Sheet Only", "sheet")
        self.key_scope_combo.currentIndexChanged.connect(self._refresh_color_key_ui)
        scope_row.addWidget(self.key_scope_combo, 1)
        kl.addLayout(scope_row)

        assign_row = QHBoxLayout()
        self.key_prof_combo = QComboBox()
        self.key_prof_combo.setEditable(True)
        for sk in ("beam", "hss_tube", "angle", "channel", "pipe"):
            for it in self.steel_matrix_data.get(sk, []):
                if it.get("designation"):
                    self.key_prof_combo.addItem(str(it["designation"]).upper())
        assign_row.addWidget(self.key_prof_combo, 1)

        self.key_col_combo = QComboBox()
        self.key_col_combo.setIconSize(QSize(16, 16))
        self.key_col_combo.setFixedWidth(54)
        for chex in self.SWATCH_HEXES:
            self.key_col_combo.addItem(make_swatch_icon(chex, 16), "", chex)
        assign_row.addWidget(self.key_col_combo)
        kl.addLayout(assign_row)

        self.chk_hl_lines = QCheckBox("Highlight Attached Beam Lines")
        self.chk_hl_lines.setChecked(False)
        self.chk_hl_lines.setStyleSheet("QCheckBox { color: #0f172a; font-weight: bold; }")
        self.chk_hl_lines.setToolTip("<b>Highlight Attached Beam Lines</b><br>When checked, highlights both the steel callout label<br>and the parallel steel beam line directly beside it.")
        self.chk_hl_lines.toggled.connect(self._refresh_color_key_ui)
        kl.addWidget(self.chk_hl_lines)

        nav_key_row = QHBoxLayout()
        nav_key_row.setSpacing(4)
        btn_key_prev = QToolButton(); btn_key_prev.setText("◀ Prev Sheet"); btn_key_prev.setFixedHeight(24)
        btn_key_next = QToolButton(); btn_key_next.setText("Next Sheet ▶"); btn_key_next.setFixedHeight(24)
        btn_key_prev.clicked.connect(lambda: self._step_color_key_sheet(-1))
        btn_key_next.clicked.connect(lambda: self._step_color_key_sheet(1))
        nav_key_row.addWidget(btn_key_prev, 1)
        nav_key_row.addWidget(btn_key_next, 1)
        kl.addLayout(nav_key_row)
        btn_assign = QPushButton("+ Assign Member to Color Key")
        btn_assign.setStyleSheet("QPushButton { border-color: #34d399; color: #34d399; } QPushButton:hover { background-color: rgba(52, 211, 153, 0.18); color: #ffffff; }")
        btn_assign.setStyleSheet("QPushButton { background-color: rgba(5, 150, 105, 0.24); border: 2px solid #059669; color: #000000; font-weight: 700; font-weight: bold; } QPushButton:hover { background-color: rgba(5, 150, 105, 0.42); color: #0f172a; }")
        btn_assign.clicked.connect(self._assign_member_color)
        kl.addWidget(btn_assign)

        btn_auto_all = QPushButton("Auto-Color All BOM Steel (Whole Planset)")
        btn_auto_all.setToolTip("<b>Auto-Generate Whole Planset Color Key</b><br>Automatically assigns a distinct color to every steel profile<br>in your BOM and highlights all of them across every sheet.")
        btn_auto_all.setStyleSheet("QPushButton { background-color: rgba(2, 132, 199, 0.24); border: 2px solid #0284c7; color: #000000; font-weight: 700; font-weight: bold; } QPushButton:hover { background-color: rgba(2, 132, 199, 0.42); color: #0f172a; }")
        btn_auto_all.clicked.connect(self._auto_color_all_bom_profiles)
        kl.addWidget(btn_auto_all)

        self.lbl_prof_sheets = QLabel("Click a key item to jump sheets:")
        self.lbl_prof_sheets.setStyleSheet("color: #1e3a8a; font-size: 11px; font-weight: bold;")
        kl.addWidget(self.lbl_prof_sheets)

        self.prof_sheets_bar = QHBoxLayout()
        self.prof_sheets_bar.setSpacing(4)
        kl.addLayout(self.prof_sheets_bar)

        self.key_list = QListWidget()
        self.key_list.setIconSize(QSize(14, 14))
        self.key_list.setStyleSheet("QListWidget { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 6px; padding: 3px; font-weight: 600; } QListWidget::item { padding: 4px 6px; border-radius: 4px; } QListWidget::item:selected { background-color: #e0f2fe; color: #0369a1; }")
        self.key_list.itemClicked.connect(self._on_key_item_clicked)
        kl.addWidget(self.key_list, 1)

        key_btns = QHBoxLayout()
        btn_rm_key = QPushButton("Remove Selected")
        btn_rm_key.setStyleSheet("QPushButton { background-color: rgba(220, 38, 38, 0.20); border: 2px solid #dc2626; color: #000000; font-weight: 700; font-weight: bold; } QPushButton:hover { background-color: rgba(220, 38, 38, 0.36); color: #7f1d1d; }")
        btn_rm_key.clicked.connect(self._remove_selected_key)
        btn_clr_key = QPushButton("Clear Key")
        btn_clr_key.clicked.connect(self._clear_active_key)
        key_btns.addWidget(btn_rm_key)
        key_btns.addWidget(btn_clr_key)
        kl.addLayout(key_btns)

        self.key_scope_combo.setToolTip("<b>Color Key Scope</b><br>Apply color rules across the whole planset<br>or customize colors for this sheet only.")
        self.key_prof_combo.setToolTip("<b>Steel Profile</b><br>Select or type a steel size (e.g. W12X30)<br>to highlight on the drawing.")
        self.key_col_combo.setToolTip("<b>Key Swatch Color</b><br>Choose the highlight color for this steel size.")
        btn_assign.setToolTip("<b>Assign Member to Color Key</b><br>Highlight all matching steel callouts on the plan<br>and update the on-sheet legend box.")
        btn_rm_key.setToolTip("<b>Remove Selected</b><br>Remove the highlighted member from the Color Key.")
        btn_clr_key.setToolTip("<b>Clear Key</b><br>Clear all color rules in the active scope.")
        outer.addWidget(left_w, 1)
        outer.addWidget(key_panel)
        self.set_mode("pan")

    def set_mode(self, mode):
        self.canvas.set_interaction_mode(mode)
        on_s = "QPushButton { background-color: rgba(2, 132, 199, 0.24); border: 2px solid #0284c7; color: #000000; font-weight: 700; font-weight: bold; padding: 5px 8px; border-radius: 5px; }"
        off_s = "QPushButton { background-color: #e8f3fe; border: 1px solid #60a5fa; color: #0f172a; font-weight: bold; padding: 5px 8px; border-radius: 5px; }"
        for b, m in ((self.btn_pan, "pan"), (self.btn_sel, "select"), (self.btn_meas, "measure"), (self.btn_count, "count"), (self.btn_text, "text"), (self.btn_box, "box"), (self.btn_cal, "calibrate")):
            b.setStyleSheet(on_s if mode == m else off_s)

    def _set_canvas_pen(self, qc):
        self.canvas.active_color = QColor(qc)
        if self.canvas._inline_editor.isVisible():
            self.canvas._apply_inline_style()
        if 0 <= self.canvas.selected_idx < len(self.canvas.markups):
            self.canvas.markups[self.canvas.selected_idx]["color"] = QColor(qc)
        self.canvas.update()

    def _pick_custom_pen(self):
        qc = QColorDialog.getColor(self.canvas.active_color, self, "Choose Markup Pen Color")
        if qc.isValid():
            self._set_canvas_pen(qc)

    def _active_key_dict(self):
        pg = self.get_page_fn()
        return self.sheet_color_keys.setdefault(pg, {}) if self.key_scope_combo.currentData() == "sheet" else self.global_color_key

    def _effective_key_for_page(self, pg):
        merged = dict(self.global_color_key)
        merged.update(self.sheet_color_keys.get(pg, {}))
        return merged

    def _assign_member_color(self):
        prof = re.sub(r"\s+", "", self.key_prof_combo.currentText().upper()).strip()
        if not prof:
            return
        qc = QColor(self.key_col_combo.currentData() or "#0284c7")
        self._active_key_dict()[prof] = qc
        self._set_canvas_pen(qc)
        self._refresh_color_key_ui()

    def _on_key_item_clicked(self, item):
        prof = item.data(Qt.UserRole)
        eff = self._effective_key_for_page(self.get_page_fn())
        if prof in eff:
            self._set_canvas_pen(eff[prof])
        self._populate_profile_sheet_pills(prof)

    def _remove_selected_key(self):
        cur = self.key_list.currentItem()
        if not cur:
            return
        prof = cur.data(Qt.UserRole)
        self._active_key_dict().pop(prof, None)
        self.global_color_key.pop(prof, None)
        self._refresh_color_key_ui()

    def _clear_active_key(self):
        self._active_key_dict().clear()
        self._refresh_color_key_ui()

    def _on_key_item_clicked(self, item):
        prof = item.data(Qt.UserRole)
        eff = self._effective_key_for_page(self.get_page_fn())
        if prof in eff:
            self._set_canvas_pen(eff[prof])
        self._populate_profile_sheet_pills(prof)

    def _remove_selected_key(self):
        cur = self.key_list.currentItem()
        if not cur:
            return
        prof = cur.data(Qt.UserRole)
        self._active_key_dict().pop(prof, None)
        self.global_color_key.pop(prof, None)
        self._refresh_color_key_ui()

    def _clear_active_key(self):
        self._active_key_dict().clear()
        self._refresh_color_key_ui()

    def render_sheet(self, page_num):
        pno = max(0, int(page_num) - 1)
        if pno >= len(self._doc):
            return
        pg = self._doc.load_page(pno)
        pix = pg.get_pixmap(dpi=150, alpha=False)
        qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
        self.canvas.load_pixmap(QPixmap.fromImage(qimg), render_dpi=150, page_markups=self.page_markups.setdefault(page_num, []))
        if not hasattr(self, "_pdf_snap_cache"):
            self._pdf_snap_cache = {}
        self.canvas._pdf_page_w = float(pg.rect.width)
        self.canvas._pdf_page_h = float(pg.rect.height)
        import bom_pdf_engine as _eng
        detected_ppf = float(_eng.get_sheet_calibration(pg))
        if pno not in self._pdf_snap_cache:
            try:
                self._pdf_snap_cache[pno] = _eng.extract_vector_snap_nodes(pg, detected_ppf)
            except Exception:
                self._pdf_snap_cache[pno] = ([], [])
        self.canvas.pdf_snap_endpoints, self.canvas.pdf_snap_midpoints = self._pdf_snap_cache[pno]
        try:
            self.canvas.pts_per_ft = detected_ppf
            p_win = self.window()
            rb = getattr(p_win, "master_ribbon", None)
            sc_cb = getattr(rb, "ribbon_scale_cb", None) if rb else None
            if sc_cb is not None:
                best_i, best_diff = 0, 999.0
                for si in range(sc_cb.count()):
                    sv = sc_cb.itemData(si) or _eng.parse_arch_scale(sc_cb.itemText(si))
                    if abs(float(sv) - detected_ppf) < best_diff:
                        best_diff = abs(float(sv) - detected_ppf)
                        best_i = si
                sc_cb.blockSignals(True)
                sc_cb.setCurrentIndex(best_i)
                sc_cb.blockSignals(False)
                if hasattr(rb, "_update_telemetry"):
                    rb._update_telemetry()
        except Exception:
            pass
        self._refresh_color_key_ui()
        QTimer.singleShot(0, self.canvas.fit_to_viewport)
        QTimer.singleShot(120, self.canvas.fit_to_viewport)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if hasattr(self, "canvas") and self.canvas._base_pix and self.scroll:
            vw = max(200, self.scroll.viewport().width() - 24)
            vh = max(200, self.scroll.viewport().height() - 24)
            self.canvas.zoom = max(0.25, min(2.5, min(vw / float(self.canvas._base_pix.width()), vh / float(self.canvas._base_pix.height()))))
            self.canvas._apply_zoom(fast=True)
            if not hasattr(self, "_resize_fit_timer"):
                self._resize_fit_timer = QTimer(self)
                self._resize_fit_timer.setSingleShot(True)
                self._resize_fit_timer.timeout.connect(lambda: self.canvas._apply_zoom(fast=False))
            self._resize_fit_timer.start(90)

    def showEvent(self, ev):
        super().showEvent(ev)
        QTimer.singleShot(0, self.canvas.fit_to_viewport)
        QTimer.singleShot(120, self.canvas.fit_to_viewport)

    def _get_cached_page_words(self, pg_idx):
        cache = getattr(self, "_page_words_cache", None)
        if cache is None:
            cache = {}
            self._page_words_cache = cache
        if pg_idx not in cache and getattr(self, "_doc", None) and 0 <= pg_idx < len(self._doc):
            cache[pg_idx] = self._doc.load_page(pg_idx).get_text("words")
        return cache.get(pg_idx, [])

    def _refresh_color_key_ui(self):
        pg_num = self.get_page_fn()
        eff_key = self._effective_key_for_page(pg_num)
        self.key_list.clear()
        for prof, qc in eff_key.items():
            it = QListWidgetItem(make_swatch_icon(qc, 14), f" {prof}")
            it.setData(Qt.UserRole, prof)
            self.key_list.addItem(it)

        highlights = []
        counts = {p: 0 for p in eff_key}
        if eff_key and 1 <= pg_num <= len(self._doc):
            pg = self._doc.load_page(pg_num - 1)
            mx = float(pg.rect.width) * 0.72
            segs = []
            if not hasattr(self, "chk_hl_lines") or self.chk_hl_lines.isChecked():
                for d in pg.get_drawings():
                    stroke_w = float(d.get("width") or 0.0)
                    if stroke_w < 1.20:
                        continue
                    for item in d.get("items", []):
                        if isinstance(item, tuple) and len(item) >= 3 and item.__getitem__(0) == "l":
                            _, p1, p2 = item[:3]
                            dx_s, dy_s = float(p2.x - p1.x), float(p2.y - p1.y)
                            L = math.hypot(dx_s, dy_s)
                            if p1.x < mx and p2.x < mx and L >= 65.0:
                                is_horiz = abs(dy_s) <= L * 0.08
                                is_vert = abs(dx_s) <= L * 0.08
                                if is_horiz or is_vert:
                                    segs.append((float(p1.x), float(p1.y), float(p2.x), float(p2.y), is_horiz))
            for wx0, wy0, wx1, wy1, wstr, *_ in pg.get_text("words"):
                if wx0 >= mx:
                    continue
                nw = re.sub(r"\s+", "", wstr.upper())
                if nw in eff_key:
                    col = eff_key[nw]
                    counts[nw] = counts.get(nw, 0) + 1
                    cx, cy = (wx0 + wx1) * 0.5, (wy0 + wy1) * 0.5
                    txt_horiz = (wx1 - wx0) >= (wy1 - wy0)
                    best_seg, best_d = None, 12.0
                    for sx1, sy1, sx2, sy2, seg_horiz in segs:
                        if seg_horiz != txt_horiz:
                            continue
                        abx, aby = sx2 - sx1, sy2 - sy1
                        ab2 = abx * abx + aby * aby
                        t = ((cx - sx1) * abx + (cy - sy1) * aby) / max(1.0, ab2)
                        if -0.05 <= t <= 1.05:
                            tc = max(0.0, min(1.0, t))
                            perp_d = math.hypot(cx - (sx1 + tc * abx), cy - (sy1 + tc * aby))
                            if perp_d < best_d:
                                best_d, best_seg = perp_d, (sx1, sy1, sx2, sy2)
                    dup = False
                    for h_prev in highlights:
                        if h_prev["profile"] == nw:
                            px0, py0, px1, py1 = h_prev["rect"]
                            if abs(((px0 + px1) * 0.5) - cx) < 18.0 and abs(((py0 + py1) * 0.5) - cy) < 18.0:
                                if wy0 < py0:
                                    h_prev["rect"] = (wx0, wy0, wx1, wy1)
                                    h_prev["seg"] = best_seg
                                dup = True
                                break
                    if not dup:
                        highlights.append({"profile": nw, "color": col, "rect": (wx0, wy0, wx1, wy1), "seg": best_seg})

        # If Scope is Whole Planset, show total checked BOM qty across the entire planset (with multi-sheet vector fallback)
        is_global = (self.key_scope_combo.currentData() == "global")
        if is_global:
            bom_totals = {}
            dlg = self.window()
            if hasattr(dlg, "tree"):
                for i in range(dlg.tree.topLevelItemCount()):
                    p_it = dlg.tree.topLevelItem(i)
                    for j in range(p_it.childCount()):
                        ch = p_it.child(j)
                        if ch.checkState(0) == Qt.Checked:
                            nm = re.sub(r"\s+", "", ch.text(3).upper()).strip()
                            try:
                                q_val = max(0, int(float(ch.text(4) or 0)))
                            except ValueError:
                                q_val = 0
                            bom_totals[nm] = bom_totals.get(nm, 0) + q_val
            for p_key in eff_key:
                if bom_totals.get(p_key, 0) > 0:
                    counts[p_key] = bom_totals[p_key]
                elif counts.get(p_key, 0) == 0:
                    tot_vec = 0
                    for p_idx in range(len(self._doc)):
                        pg_i = self._doc.load_page(p_idx)
                        mx_i = float(pg_i.rect.width) * 0.72
                        tot_vec += sum(1 for wx0, _, _, _, wstr, *_ in self._get_cached_page_words(pg_i.number) if wx0 < mx_i and re.sub(r"\s+", "", wstr.upper()) == p_key)
                    counts[p_key] = tot_vec

        self.canvas.set_color_key_overlays(highlights, [(p, eff_key[p], counts.get(p, 0)) for p in eff_key])

    def _populate_profile_sheet_pills(self, norm_prof):
        while self.prof_sheets_bar.count():
            it = self.prof_sheets_bar.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        if not norm_prof:
            self.lbl_prof_sheets.setText("Click a key item to jump sheets:")
            return
        found_pages = []
        for p_idx in range(len(self._doc)):
            pg = self._doc.load_page(p_idx)
            mx = float(pg.rect.width) * 0.72
            for wx0, _, _, _, wstr, *_ in pg.get_text("words"):
                if wx0 < mx and re.sub(r"\s+", "", wstr.upper()) == norm_prof:
                    found_pages.append(p_idx + 1)
                    break
        if found_pages:
            self.lbl_prof_sheets.setText(f"{norm_prof} found on {len(found_pages)} sheet(s):")
            for p_num in found_pages[:6]:
                btn_p = QPushButton(f"Pg {p_num}")
                btn_p.setToolTip(f"<b>Jump to Page {p_num}</b><br>Switch directly to Page {p_num} with {norm_prof} highlighted.")
                btn_p.setStyleSheet("QPushButton { background-color: #0284c7; color: #ffffff; border: 1px solid #0369a1; border-radius: 4px; padding: 3px 7px; font-size: 11px; font-weight: bold; } QPushButton:hover { background-color: rgba(2, 132, 199, 0.42); color: #0f172a; }")
                btn_p.clicked.connect(lambda _=False, pn=p_num: self._jump_page_from_pill(pn))
                self.prof_sheets_bar.addWidget(btn_p)
            self.prof_sheets_bar.addStretch()
        else:
            self.lbl_prof_sheets.setText(f"{norm_prof}: 0 vector matches")

    def _jump_page_from_pill(self, page_num):
        dlg = self._find_bom_dialog()
        if hasattr(dlg, "sheet_combo"):
            for idx in range(dlg.sheet_combo.count()):
                if dlg.sheet_combo.itemData(idx) == page_num:
                    dlg.sheet_combo.setCurrentIndex(idx)
                    break
        self.canvas.fit_to_viewport()

    def _step_color_key_sheet(self, delta: int):
        dlg = self._find_bom_dialog()
        if hasattr(dlg, "sheet_combo") and dlg.sheet_combo.count() > 0:
            nxt = max(0, min(dlg.sheet_combo.count() - 1, dlg.sheet_combo.currentIndex() + delta))
            dlg.sheet_combo.setCurrentIndex(nxt)

    def highlight_profile_and_fit(self, profile_str):
        norm = re.sub(r"\s+", "", str(profile_str).upper()).strip()
        if norm:
            eff = self._effective_key_for_page(self.get_page_fn())
            if norm not in eff:
                used = {qc.name().lower() for qc in self.global_color_key.values()}
                pick_hex = next((h for h in self.SWATCH_HEXES if h.lower() not in used), self.SWATCH_HEXES[len(self.global_color_key) % len(self.SWATCH_HEXES)])
                self.global_color_key[norm] = QColor(pick_hex)
            self.key_scope_combo.setCurrentIndex(0)
            self.key_prof_combo.setCurrentText(norm)
            self._refresh_color_key_ui()
            self._populate_profile_sheet_pills(norm)
        self.canvas.fit_to_viewport()

    def _find_bom_dialog(self):
        p = self.parent()
        while p is not None:
            if hasattr(p, "tree"):
                return p
            p = p.parent()
        return self.window()

    def _auto_color_all_bom_profiles(self):
        win = self.window()
        dlg = getattr(win, "planset_takeoff_tab", None) or win
        profs = []
        # 1. Collect from BOM tree (checked items first, or all items if none explicitly checked)
        if hasattr(dlg, "tree"):
            checked_profs, all_tree_profs = [], []
            for i in range(dlg.tree.topLevelItemCount()):
                p_it = dlg.tree.topLevelItem(i)
                for j in range(p_it.childCount()):
                    ch = p_it.child(j)
                    nm = re.sub(r"\s+", "", ch.text(3).upper()).strip()
                    if nm:
                        if nm not in all_tree_profs:
                            all_tree_profs.append(nm)
                        if ch.checkState(0) == Qt.Checked and nm not in checked_profs:
                            checked_profs.append(nm)
            profs.extend(checked_profs or all_tree_profs)
        # 2. Fallback / merge from active staged bom_items
        for bi in (getattr(self, "bom_items", None) or getattr(dlg, "bom_items", None) or getattr(dlg, "staged_bom_items", []) or []):
            nm = re.sub(r"\s+", "", str(bi.get("model") or bi.get("designation") or "").upper()).strip()
            if nm and nm not in profs:
                profs.append(nm)
        if not profs and hasattr(self, "key_prof_combo"):
            cur_p = re.sub(r"\s+", "", self.key_prof_combo.currentText().upper()).strip()
            if cur_p:
                profs.append(cur_p)
        if not profs:
            return
        extra_palette = self.SWATCH_HEXES + ["#2563eb", "#16a34a", "#d97706", "#9333ea", "#e11d48", "#0891b2", "#4f46e5", "#65a30d"]
        self.key_scope_combo.setCurrentIndex(0)
        self.sheet_color_keys.clear()
        self.global_color_key.clear()
        for idx, pr in enumerate(profs):
            self.global_color_key[pr] = QColor(extra_palette[idx % len(extra_palette)])
        self._refresh_color_key_ui()
        if profs:
            self._populate_profile_sheet_pills(profs[0])
        self.canvas.update()

    def export_pdf(self):
        self._export_marked_pdf()

    def _export_marked_pdf(self):
        pg_num = self.get_page_fn()
        base_name = os.path.splitext(os.path.basename(self.pdf_path))[0]
        default_out = os.path.join(os.path.dirname(self.pdf_path), f"{base_name}_Pg{pg_num}_Takeoff.pdf")
        out_path, _ = QFileDialog.getSaveFileName(self, "Save Printable Marked-Up Sheet PDF", default_out, "PDF Files (*.pdf)")
        if not out_path:
            return
        out_doc = pymupdf.open()
        out_doc.insert_pdf(self._doc, from_page=pg_num - 1, to_page=pg_num - 1)
        pg = out_doc.load_page(0)

        def _rgb(qc):
            return (qc.redF(), qc.greenF(), qc.blueF())

        # 1. Color Key vector highlights & steel beam strokes
        for hl in self.canvas.key_highlights:
            c = _rgb(hl["color"])
            r = pymupdf.Rect(*hl["rect"]) + (-2, -1.5, 2, 1.5)
            pg.draw_rect(r, color=c, fill=c, fill_opacity=0.25, width=1.2)
            if hl.get("seg"):
                sx1, sy1, sx2, sy2 = hl["seg"]
                pg.draw_line(pymupdf.Point(sx1, sy1), pymupdf.Point(sx2, sy2), color=c, width=3.5, stroke_opacity=0.75)

        # 2. User markups (dimensions, count badges, text notes)
        for m in self.canvas.markups:
            c = _rgb(m.get("color", self.canvas.active_color))
            mt = m.get("type")
            if mt == "span":
                p1, p2 = pymupdf.Point(m["x1"], m["y1"]), pymupdf.Point(m["x2"], m["y2"])
                pg.draw_line(p1, p2, color=c, width=float(m.get("line_width", 2.0)))
                mid = pymupdf.Point((p1.x + p2.x) * 0.5, (p1.y + p2.y) * 0.5 - 4)
                pg.insert_text(mid, m.get("label", ""), fontsize=max(7.0, float(m.get("font_size", 18)) * 0.65), color=c)
            elif mt == "count":
                cp = pymupdf.Point(m["x"], m["y"])
                pg.draw_circle(cp, 8.0, color=(1, 1, 1), fill=c, width=1.2)
                pg.insert_text(pymupdf.Point(cp.x - 3.5, cp.y + 3.0), str(m.get("num", 1)), fontsize=8, color=(1, 1, 1))
            elif mt == "cad_shape":
                sd = m.get("shape", {})
                ox, oy = m["x"], m["y"]
                wp, hp = m.get("w_pts", 180.0), m.get("h_pts", 140.0)
                if sd.get("kind") == "circle":
                    r_pt = min(wp, hp) * 0.5
                    pg.draw_circle(pymupdf.Point(ox + r_pt, oy + r_pt), r_pt, color=c, width=1.5)
                else:
                    pg.draw_polyline([pymupdf.Point(ox, oy + hp), pymupdf.Point(ox + wp, oy + hp), pymupdf.Point(ox + wp, oy)], color=c, fill=c, fill_opacity=0.12, width=1.5, closePath=True)
                pg.insert_text(pymupdf.Point(ox, oy + hp + 12), m.get("label", ""), fontsize=8.0, color=c)
            elif mt == "text":
                fsz = max(7.0, float(m.get("font_size", 18)) * 0.65)
                for li, ln in enumerate(m.get("text", "").split("\n")):
                    pg.insert_text(pymupdf.Point(m["x"], m["y"] + li * (fsz * 1.25)), ln, fontsize=fsz, color=c)

        # 3. Proportional STEEL COLOR KEY legend box at exact dragged PDF coordinates
        if self.canvas.legend_entries:
            lx, ly = self.canvas.legend_pdf_pos[0], self.canvas.legend_pdf_pos[1]
            row_h, hdr_h = 13.0, 16.0
            bw = 165.0
            bh = hdr_h + 4.0 + len(self.canvas.legend_entries) * row_h
            pg.draw_rect(pymupdf.Rect(lx, ly, lx + bw, ly + bh), color=(0, 0, 0), width=1.2)
            pg.draw_line(pymupdf.Point(lx, ly + hdr_h), pymupdf.Point(lx + bw, ly + hdr_h), color=(0, 0, 0), width=1.0)
            pg.insert_text(pymupdf.Point(lx + 6, ly + 11.5), "STEEL COLOR KEY", fontsize=8.5, color=(0, 0, 0))
            for i, (prof, col, cnt) in enumerate(self.canvas.legend_entries):
                ry = ly + hdr_h + 3.0 + i * row_h
                pg.draw_rect(pymupdf.Rect(lx + 6, ry + 1.5, lx + 14.5, ry + 10.0), color=(0, 0, 0), fill=_rgb(col), width=0.8)
                pg.insert_text(pymupdf.Point(lx + 19, ry + 9.5), f"{prof} ({cnt})", fontsize=8.0, color=(0, 0, 0))

        out_doc.save(out_path)
        out_doc.close()
        os.startfile(out_path)

    def _print_marked_sheet(self):
        from PySide6.QtPrintSupport import QPrinter, QPrintDialog
        from PySide6.QtGui import QPageLayout
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageOrientation(QPageLayout.Landscape)
        dlg = QPrintDialog(printer, self)
        dlg.setWindowTitle("Print Marked-Up Blueprint Sheet")
        if dlg.exec() != QPrintDialog.Accepted:
            return
        old_z, old_sel = self.canvas.zoom, self.canvas.selected_idx
        self.canvas.selected_idx = -1
        self.canvas.zoom = 1.0
        self.canvas._apply_zoom()
        snap = self.canvas.grab()
        self.canvas.selected_idx = old_sel
        self.canvas.set_zoom(old_z)

        painter = QPainter(printer)
        pg_rect = painter.viewport()
        scaled = snap.scaled(pg_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x_off = (pg_rect.width() - scaled.width()) // 2
        y_off = (pg_rect.height() - scaled.height()) // 2
        painter.drawPixmap(x_off, y_off, scaled)
        painter.end()

    def _centered_open_pdf_dialog(self):
        from PySide6.QtWidgets import QFileDialog
        from PySide6.QtCore import QTimer
        win = self.window()
        dlg = QFileDialog(win, "Select Structural PDF Planset", "", "PDF Drawings (*.pdf)")
        dlg.setFileMode(QFileDialog.ExistingFile)
        dlg.resize(900, 560)
        def _center():
            if win is not None:
                c = win.frameGeometry().center()
                dlg.move(c.x() - dlg.width() // 2, c.y() - dlg.height() // 2)
        QTimer.singleShot(0, _center)
        if dlg.exec() == QFileDialog.Accepted and dlg.selectedFiles():
            return dlg.selectedFiles().__getitem__(0), "PDF Drawings (*.pdf)"
        return "", ""

    def open_pdf_dialog(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        fp, _ = self._centered_open_pdf_dialog()
        if not fp:
            return
        try:
            self._doc = pymupdf.open(fp)
            self.pdf_path = fp
            self.page_markups = {}
            if hasattr(self, "page_spin"):
                self.page_spin.setMaximum(max(1, len(self._doc)))
                self.page_spin.setValue(1)
            for fn in ("render_current_page", "_render_page", "render_page", "update_canvas"):
                if hasattr(self, fn):
                    getattr(self, fn)()
                    break
        except Exception as ex:
            QMessageBox.critical(self, "PDF Load Error", f"Could not load PDF planset:\n{ex}")
