import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap
from blueprint_takeoff_ui import CadBlueprintCanvas

def test_cad_tools_pressure_suite(qtbot):
    canvas = CadBlueprintCanvas(lambda *a: None, lambda *a: None)
    canvas.resize(900, 700)
    pm = QPixmap(900, 700)
    pm.fill(Qt.white)
    canvas.setPixmap(pm)
    qtbot.addWidget(canvas)
    canvas.show()

    # 1. Pressure test 3-click Hanger Skew T-Square tool & live pivot swing
    canvas.set_mode("hanger_skew")
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(200, 300))
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(400, 300))
    assert len(canvas._skew_pts) == 2
    qtbot.mouseMove(canvas, pos=QPoint(460, 420))
    canvas.repaint()
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(460, 420))
    assert len(canvas.markups) == 1
    assert canvas.markups[-1]["type"] == "hanger_skew"
    assert "SKEW" in canvas.markups[-1]["label"]

    # 2. Pressure test click-click Line drawing + Enter chain break
    canvas.set_mode("line")
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(100, 100))
    qtbot.mouseClick(canvas, Qt.LeftButton, pos=QPoint(250, 100))
    assert len(canvas.markups) == 2
    qtbot.keyClick(canvas, Qt.Key_Return)
    assert canvas._p1 is None and canvas.mode == "line"

    # 3. Pressure test Undo removes last markup cleanly
    canvas.undo_last_markup()
    assert len(canvas.markups) == 1
