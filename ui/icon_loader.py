import os
import re
import sys
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

_ICON_CACHE = {}

SEMANTIC_BASE = {
    "folder-open": "#b45309",
    "file-up": "#b45309",
    "file-output": "#b91c1c",
    "table-2": "#107c41",
    "file-spreadsheet": "#107c41",
    "check-circle": "#107c41",
    "plus-circle": "#107c41",
    "stamp": "#107c41",
    "bar-chart-3": "#107c41",
    "trending-up": "#107c41",
    "percent": "#107c41",
    "trash-2": "#b91c1c",
    "cloud": "#b91c1c",
    "circle-dot": "#b91c1c",
    "eraser": "#c2410c",
    "flame": "#c2410c",
    "highlighter": "#ca8a04",
    "scan": "#6d28d9",
    "sparkles": "#6d28d9",
}

def _icons_dir():
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", getattr(sys, "_MEIPASS", getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", "icons")

def _render_svg_pm(raw_svg: str, hex_col: str, px: int) -> QPixmap:
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    tinted = re.sub(r'fill="[^"]*"', "", raw_svg)
    tinted = tinted.replace("<svg ", f'<svg fill="{hex_col}" ', 1)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    QSvgRenderer(tinted.encode("utf-8")).render(p, QRectF(0, 0, px, px))
    p.end()
    pm.setDevicePixelRatio(2.0)
    return pm

def get_icon(name: str, color_hex: str = None, size: int = 20) -> QIcon:
    base_col = color_hex or SEMANTIC_BASE.get(name, "#334155")
    cache_key = f"dyn_thin:{name}:{base_col}:{size}"
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    svg_path = os.path.join(_icons_dir(), f"{name}.svg")
    ic = QIcon()
    if os.path.exists(svg_path):
        with open(svg_path, "r", encoding="utf-8-sig") as f:
            raw_svg = f.read()
        px = size * 2
        pm_normal = _render_svg_pm(raw_svg, base_col, px)
        pm_hover  = _render_svg_pm(raw_svg, "#0284c7", px)
        pm_armed  = _render_svg_pm(raw_svg, "#0369a1", px)
        pm_dis    = _render_svg_pm(raw_svg, "#94a3b8", px)
        ic.addPixmap(pm_normal, QIcon.Normal, QIcon.Off)
        ic.addPixmap(pm_hover,  QIcon.Active, QIcon.Off)
        ic.addPixmap(pm_armed,  QIcon.Normal, QIcon.On)
        ic.addPixmap(pm_armed,  QIcon.Active, QIcon.On)
        ic.addPixmap(pm_dis,    QIcon.Disabled, QIcon.Off)

    _ICON_CACHE[cache_key] = ic
    return ic