# -*- coding: utf-8 -*-
import os, sys, json, datetime, traceback
from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import (
    QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QComboBox,
    QAbstractSpinBox, QCheckBox, QAbstractButton
)


def _logs_dir():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(base, "logs")
    os.makedirs(d, exist_ok=True)
    return d


def record_shop_error_ticket(exc_type, exc_val, exc_tb, context_hint=""):
    ldir = _logs_dir()
    seq_file = os.path.join(ldir, "error_seq.json")
    seq = 1001
    try:
        if os.path.exists(seq_file):
            with open(seq_file, "r", encoding="utf-8") as f:
                seq = int(json.load(f).get("next_seq", 1001))
        with open(seq_file, "w", encoding="utf-8") as f:
            json.dump({"next_seq": seq + 1}, f)
    except Exception:
        pass

    code = f"BM-ERR-{seq}"
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tb_str = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
    short_msg = f"{getattr(exc_type, '__name__', 'Error')}: {exc_val}"

    log_txt_path = os.path.join(ldir, "shop_error_log.txt")
    try:
        with open(log_txt_path, "a", encoding="utf-8") as lf:
            lf.write(f"\n{'='*68}\n[{ts}] TICKET: {code} | CONTEXT: {context_hint}\n{short_msg}\n{'-'*68}\n{tb_str}\n")
    except Exception:
        pass

    app = QApplication.instance()
    if app is None:
        return code

    from PySide6.QtWidgets import QMessageBox
    box = QMessageBox(app.activeWindow())
    box.setIcon(QMessageBox.Critical)
    box.setWindowTitle(f"Bowman-Morton Pricing Suite - Error {code}")
    box.setText(f"An unexpected action occurred (Error Code: {code}).")
    box.setInformativeText(
        f"Share Error Code {code} with Admin/Dev.\n"
        f"Technical details were saved to logs/shop_error_log.txt so you can keep working safely."
    )
    box.setDetailedText(f"Ticket: {code}\nTime: {ts}\nContext: {context_hint}\nSummary: {short_msg}\n\n{tb_str}")
    btn_copy = box.addButton(f"Copy Code ({code})", QMessageBox.ActionRole)
    box.addButton(QMessageBox.Ok)
    box.exec()
    if box.clickedButton() == btn_copy:
        QApplication.clipboard().setText(f"{code}: {short_msg}")
    return code


def install_global_error_catcher():
    def _excepthook(exc_type, exc_val, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_val, exc_tb)
            return
        app = QApplication.instance()
        win = app.activeWindow() if app else None
        ctx = win.windowTitle() if win else "Main Workspace"
        record_shop_error_ticket(exc_type, exc_val, exc_tb, context_hint=ctx)

    sys.excepthook = _excepthook


class UniversalSummaryTooltipFilter(QObject):
    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Enter, QEvent.ToolTip) and isinstance(obj, QWidget):
            cur_tip = (obj.toolTip() or "").strip()
            if not cur_tip:
                generated = self._describe_widget(obj)
                if generated:
                    obj.setToolTip(generated)
        return False

    def _find_neighbor_label(self, w):
        p = w.parentWidget()
        if p is None:
            return ""
        sibs = p.findChildren(QLabel)
        wy = w.geometry().center().y()
        wx = w.geometry().left()
        best_txt, best_dx = "", 9999
        for lbl in sibs:
            if not lbl.isVisible():
                continue
            t = lbl.text().replace(":", "").strip()
            if not t or len(t) > 55:
                continue
            if abs(lbl.geometry().center().y() - wy) <= 18 and lbl.geometry().right() <= wx + 12:
                dx = wx - lbl.geometry().right()
                if dx < best_dx:
                    best_dx, best_txt = dx, t
        return best_txt

    def _describe_widget(self, w):
        if isinstance(w, QAbstractButton):
            txt = w.text().replace("\n", " ").replace("&&", "&").strip()
            if not txt:
                return ""
            return f"{txt}\nClick to run '{txt}' in the active workspace."
        if isinstance(w, QLineEdit):
            ph = (w.placeholderText() or "").strip()
            lbl = self._find_neighbor_label(w)
            title = lbl or ph or "Text / Numeric Input"
            desc = ph if (ph and ph != title) else f"Enter {title.lower()} for the active calculation or quote."
            return f"{title}\n{desc}"
        if isinstance(w, QComboBox):
            lbl = self._find_neighbor_label(w) or "Selection Dropdown"
            cur = w.currentText().strip()
            return f"{lbl}\nChoose an option from the dropdown list (Current: {cur or 'None'})."
        if isinstance(w, QAbstractSpinBox):
            lbl = self._find_neighbor_label(w) or "Numeric Value"
            return f"{lbl}\nType a number or use the up/down arrows to adjust {lbl.lower()}."
        if isinstance(w, QCheckBox):
            txt = w.text().strip() or "Option Toggle"
            return f"{txt}\nCheck or uncheck to include '{txt}' in the calculation."
        return ""
