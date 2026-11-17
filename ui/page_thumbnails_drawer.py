import os
import fitz
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QImage, QPixmap, QIcon
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QToolButton
)


class PageThumbnailsDrawer(QFrame):
    """Adobe Acrobat-style collapsible left page thumbnail drawer for PDF plansets."""
    page_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self._pdf_path = None
        self.setFixedWidth(148)
        self.setStyleSheet(
            "PageThumbnailsDrawer { background-color: #f8fafc; border-right: 1px solid #cbd5e1; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(2, 0, 2, 0)
        self.lbl_title = QLabel("SHEETS")
        self.lbl_title.setStyleSheet("color: #475569; font-size: 10px; font-weight: 800; letter-spacing: 0.6px;")
        self.btn_toggle = QToolButton()
        self.btn_toggle.setText("◀")
        self.btn_toggle.setFixedSize(20, 20)
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.setToolTip("Collapse / Expand Sheet Thumbnails")
        self.btn_toggle.setStyleSheet(
            "QToolButton { background: transparent; border: 1px solid transparent; border-radius: 3px; color: #475569; font-size: 10px; } "
            "QToolButton:hover { background-color: #e2e8f0; }"
        )
        self.btn_toggle.clicked.connect(self.toggle_drawer)
        hdr.addWidget(self.lbl_title)
        hdr.addStretch(1)
        hdr.addWidget(self.btn_toggle)
        root.addLayout(hdr)

        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setIconSize(QSize(104, 134))
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setMovement(QListWidget.Static)
        self.list_widget.setSpacing(8)
        self.list_widget.setWordWrap(True)
        self.list_widget.setStyleSheet(
            "QListWidget { background: transparent; border: none; outline: none; } "
            "QListWidget::item { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px; color: #1e293b; font-size: 10.5px; font-weight: 600; } "
            "QListWidget::item:hover { border: 1.5px solid #0284c7; background-color: #f0f9ff; } "
            "QListWidget::item:selected { border: 2px solid #0284c7; background-color: #e0f2fe; color: #0369a1; }"
        )
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        root.addWidget(self.list_widget, 1)

    def toggle_drawer(self):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self.list_widget.setVisible(False)
            self.lbl_title.setVisible(False)
            self.btn_toggle.setText("▶")
            self.setFixedWidth(28)
        else:
            self.setFixedWidth(148)
            self.lbl_title.setVisible(True)
            self.list_widget.setVisible(True)
            self.btn_toggle.setText("◀")

    def load_pdf(self, pdf_path: str, sheet_labels=None):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self._pdf_path = pdf_path
        if not pdf_path or not os.path.exists(pdf_path):
            self.list_widget.blockSignals(False)
            return
        try:
            doc = fitz.open(pdf_path)
            max_pages = min(len(doc), 120)
            for idx in range(max_pages):
                page = doc[idx]
                scale = 104.0 / max(1.0, page.rect.width)
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
                pm = QPixmap.fromImage(qimg)
                lbl = sheet_labels[idx] if (sheet_labels and idx < len(sheet_labels)) else f"Sheet {idx + 1}"
                item = QListWidgetItem(QIcon(pm), lbl)
                item.setTextAlignment(Qt.AlignHCenter | Qt.AlignBottom)
                self.list_widget.addItem(item)
            doc.close()
            if self.list_widget.count() > 0:
                self.list_widget.setCurrentRow(0)
        except Exception:
            pass
        self.list_widget.blockSignals(False)

    def set_active_page(self, page_idx: int):
        if 0 <= page_idx < self.list_widget.count() and self.list_widget.currentRow() != page_idx:
            self.list_widget.blockSignals(True)
            self.list_widget.setCurrentRow(page_idx)
            self.list_widget.blockSignals(False)

    def _on_row_changed(self, row: int):
        if row >= 0:
            self.page_selected.emit(row)
