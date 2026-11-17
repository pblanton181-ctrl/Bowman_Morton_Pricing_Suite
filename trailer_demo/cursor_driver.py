import ctypes
import time
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QColor, QPainter, QPen, QBrush
from PySide6.QtWidgets import QLabel


def set_os_cursor(x, y):
    try:
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
    except Exception:
        pass


class TopClickHalo(QLabel):
    """Top-level translucent click ring that floats above both main window & dialogs."""

    def __init__(self):
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFixedSize(76, 76)
        self._alpha = 0
        self._radius = 8
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def pulse_at(self, gpos):
        self.move(gpos.x() - 38, gpos.y() - 38)
        self._alpha = 240
        self._radius = 8
        self.show()
        self.raise_()
        self._timer.start(18)

    def _tick(self):
        self._radius += 3
        self._alpha -= 22
        if self._alpha <= 0:
            self._timer.stop()
            self.hide()
        else:
            self.update()

    def paintEvent(self, ev):
        if self._alpha <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(QColor(14, 165, 233, max(0, self._alpha)), 3.0))
        p.setBrush(QBrush(QColor(56, 189, 248, max(0, self._alpha // 4))))
        p.drawEllipse(QPoint(38, 38), self._radius, self._radius)
        p.end()


class TrailerCaptionCard(QLabel):
    """Floating lower-third caption overlay explaining every step to viewers."""

    def __init__(self, parent_win):
        super().__init__(parent_win)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setWordWrap(True)
        self.setStyleSheet(
            "QLabel {"
            "  background-color: rgba(15, 23, 42, 0.93);"
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
        self.setFixedWidth(840)
        self.setMinimumHeight(64)
        self.hide()

    def show_step(self, tag, title, subtitle):
        self.setText(
            f"<span style='color:#38bdf8; font-weight:800; font-size:11px; letter-spacing:1px;'>{tag}</span><br>"
            f"<span style='color:#ffffff; font-weight:700; font-size:15px;'>{title}</span> "
            f"<span style='color:#cbd5e1; font-size:13px;'>— {subtitle}</span>"
        )
        self.adjustSize()
        pw = self.parent().width()
        ph = self.parent().height()
        self.move(max(24, (pw - self.width()) // 2), max(24, ph - self.height() - 26))
        self.raise_()
        self.show()


class SmoothCursorAnimator:
    """Moves the real Windows hardware cursor along an ease-in-out curve with click halos."""

    def __init__(self, parent_win):
        self.halo = TopClickHalo()
        self._timer = QTimer(parent_win)
        self._timer.timeout.connect(self._step)
        self._p0 = QPoint(600, 400)
        self._p1 = QPoint(600, 400)
        self._cur = QPoint(600, 400)
        self._t0 = 0.0
        self._dur = 0.50
        self._on_move = None
        self._on_done = None

    def warp(self, gpos):
        self._cur = QPoint(gpos)
        set_os_cursor(gpos.x(), gpos.y())

    def glide_to_widget(self, widget, duration_ms=520, click_pulse=True, on_done=None):
        if widget is None or not widget.isVisible():
            if on_done:
                QTimer.singleShot(80, on_done)
            return
        target = widget.mapToGlobal(QPoint(widget.width() // 2, widget.height() // 2))
        self.glide_to(target, duration_ms=duration_ms, click_pulse=click_pulse, on_done=on_done)

    def glide_to(self, target_gpos, duration_ms=520, click_pulse=True, on_move=None, on_done=None):
        self._p0 = QPoint(self._cur)
        self._p1 = QPoint(target_gpos)
        self._t0 = time.perf_counter()
        self._dur = max(0.10, duration_ms / 1000.0)
        self._on_move = on_move

        def _finish():
            if click_pulse:
                self.halo.pulse_at(target_gpos)
            if on_done:
                QTimer.singleShot(110, on_done)

        self._on_done = _finish
        self._timer.start(16)

    def _step(self):
        u = min(1.0, (time.perf_counter() - self._t0) / self._dur)
        eased = 4 * u * u * u if u < 0.5 else 1 - pow(-2 * u + 2, 3) / 2
        nx = int(round(self._p0.x() + (self._p1.x() - self._p0.x()) * eased))
        ny = int(round(self._p0.y() + (self._p1.y() - self._p0.y()) * eased))
        self._cur = QPoint(nx, ny)
        set_os_cursor(nx, ny)
        if self._on_move:
            try:
                self._on_move(self._cur)
            except Exception:
                pass
        if u >= 1.0:
            self._timer.stop()
            cb = self._on_done
            self._on_done = None
            if cb:
                cb()