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
    app.setStyleSheet(app.styleSheet() + """
        QToolTip, QTipLabel {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border: 1px solid #94a3b8 !important;
            border-radius: 5px;
            padding: 7px 10px;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 11.5px;
        }
    """)


    win = live_test.StandaloneManufacturingApp()
    director = MarketingTrailerDirector(win, single_scene=scene_num)
    QTimer.singleShot(500, director.start)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
