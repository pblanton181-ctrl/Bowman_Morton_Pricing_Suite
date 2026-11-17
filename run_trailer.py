import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import live_test
from trailer_demo.director import MarketingTrailerDirector


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    win = live_test.StandaloneManufacturingApp()
    director = MarketingTrailerDirector(win)
    QTimer.singleShot(500, director.start)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()