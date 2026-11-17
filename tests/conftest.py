import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(autouse=True)
def _flush_qt_events_between_tests():
    yield
    app = QApplication.instance()
    if app is not None:
        app.processEvents()