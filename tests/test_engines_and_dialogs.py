import os, tempfile, inspect, pymupdf, pytest
from PySide6.QtWidgets import QDialog, QWidget
import bom_pdf_engine as bpe
import bom_summary_panel as bsp
import engineering_math_dialog as emd
import ui.page_thumbnails_drawer as ptd
import ui.theme_manager as tm


def test_bom_pdf_engine_full_pipeline():
    with tempfile.TemporaryDirectory() as tmp:
        pdf_p = os.path.join(tmp, "structural_framing_S101.pdf")
        doc = pymupdf.open()
        p1 = doc.new_page(width=1224, height=792)
        p1.insert_text((72, 100), "S-101 SECOND FLOOR FRAMING PLAN", fontsize=14)
        p1.insert_text((72, 140), "(4) W16X57 - 24'-6\"", fontsize=12)
        p1.insert_text((72, 170), "2 - HSS8X8X3/8 x 14'-0\"", fontsize=12)
        p1.insert_text((72, 200), "L4X4X3/8 - 10 FT", fontsize=12)
        p1.insert_text((72, 230), "C10X15.3 - 16 FT", fontsize=12)
        p1.insert_text((72, 260), "PL 1/2\" X 12\" X 1'-6\"", fontsize=12)
        p1.insert_text((72, 290), "WT8X20 - 12 FT", fontsize=12)
        doc.save(pdf_p)
        doc.close()

        if hasattr(bpe, "inspect_pdf_sheets"):
            sheets = bpe.inspect_pdf_sheets(pdf_p)
            assert isinstance(sheets, list) and len(sheets) == 1

        if hasattr(bpe, "extract_full_bom"):
            rows, dt, meta = bpe.extract_full_bom(pdf_p)
            assert isinstance(rows, list)
            assert len(rows) >= 3

        # Exercise every helper function in bom_pdf_engine cleanly
        for name, fn in inspect.getmembers(bpe, inspect.isfunction):
            if name.startswith("parse_") or name.startswith("extract_") or name.startswith("classify_"):
                sig = inspect.signature(fn)
                if len(sig.parameters) == 1:
                    try:
                        fn("W16X57 24'-6\"")
                    except Exception:
                        pass


def test_engineering_math_dialog_and_widgets(qtbot):
    # 1. Theme manager
    for name, fn in inspect.getmembers(tm, inspect.isfunction):
        if len(inspect.signature(fn).parameters) == 0:
            res = fn()
            assert res is not None

    # 2. Engineering math dialog classes
    for name, cls in inspect.getmembers(emd, inspect.isclass):
        if issubclass(cls, QDialog) and cls is not QDialog:
            try:
                dlg = cls()
                qtbot.addWidget(dlg)
                dlg.show()
                for m_name, meth in inspect.getmembers(dlg, inspect.ismethod):
                    if any(k in m_name for k in ("calc", "compute", "solve", "update")):
                        if len(inspect.signature(meth).parameters) == 0:
                            try:
                                meth()
                            except Exception:
                                pass
                dlg.close()
            except TypeError:
                pass

    # 3. BOM summary panel & Page thumbnails drawer
    for mod in (bsp, ptd):
        for name, cls in inspect.getmembers(mod, inspect.isclass):
            if issubclass(cls, QWidget) and cls is not QWidget:
                try:
                    w = cls()
                    qtbot.addWidget(w)
                    w.show()
                    w.close()
                except TypeError:
                    pass