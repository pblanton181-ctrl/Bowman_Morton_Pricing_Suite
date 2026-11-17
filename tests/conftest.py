import pytest
from PySide6.QtWidgets import QApplication
import live_test


@pytest.fixture(scope="session")
def shared_app_win():
    app = QApplication.instance() or QApplication([])
    win = live_test.StandaloneManufacturingApp()
    win.show()
    app.processEvents()
    yield win
    win.close()
    app.processEvents()


@pytest.fixture(autouse=True)
def _flush_qt_events_between_tests():
    yield
    app = QApplication.instance()
    if app is not None:
        app.processEvents()