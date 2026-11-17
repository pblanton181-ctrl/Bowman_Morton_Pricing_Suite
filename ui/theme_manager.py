import os
import sys
from PySide6.QtWidgets import QApplication

def apply_unified_theme(app: QApplication = None):
    if app is None:
        app = QApplication.instance()
    if app is None:
        return
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    qss_path = os.path.join(base, "ui", "theme.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
