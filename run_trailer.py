import sys
import qdarktheme
from PySide6.QtCore import Qt, QTimer, QObject, QEvent
from PySide6.QtGui import QFont, QColor, QPalette
from PySide6.QtWidgets import QApplication
import live_test
from trailer_demo.director import MarketingTrailerDirector


def main():
    scene_num = None
    if "--scene" in sys.argv:
        idx = sys.argv.index("--scene")
        if idx + 1 < len(sys.argv):
            scene_num = int(sys.argv[idx + 1])
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.RoundPreferFloor)
    app = QApplication.instance() or QApplication(sys.argv)
    pal = app.palette()
    pal.setColor(QPalette.ToolTipBase, QColor("#eff6ff"))
    pal.setColor(QPalette.ToolTipText, QColor("#0f172a"))
    app.setPalette(pal)
    qdarktheme.setup_theme(theme="light", corner_shape="rounded", custom_colors={"primary": "#0284c7"})
    app.setFont(QFont("Segoe UI", 10))

    class _NoTooltipFilter(QObject):
        def eventFilter(self, obj, ev):
            return ev.type() == QEvent.ToolTip

    _ntf = _NoTooltipFilter(app)
    app.installEventFilter(_ntf)

    win = live_test.StandaloneManufacturingApp()
    director = MarketingTrailerDirector(win, single_scene=scene_num)
    QTimer.singleShot(500, director.start)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
