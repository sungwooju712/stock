# -*- coding: utf-8 -*-
"""Vector icons rendered from small inline SVGs."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


_SVG = {
    "dashboard": """
        <rect x="3.2" y="3.2" width="7" height="8.2" rx="2"/>
        <rect x="13.8" y="3.2" width="7" height="5.2" rx="2"/>
        <rect x="3.2" y="14.4" width="7" height="6.4" rx="2"/>
        <rect x="13.8" y="11.4" width="7" height="9.4" rx="2"/>
    """,
    "chart": """
        <path d="M4 3.2v16.2c0 .8.6 1.4 1.4 1.4H21"/>
        <path d="M7.2 15.7l3.8-4.1 3.1 2.4 5.3-6.2"/>
        <path d="M16.7 7.8h3.1v3.1"/>
    """,
    "filter": """
        <path d="M4 4.2h16l-6.2 7.2v6.1l-3.6 2.1v-8.2L4 4.2z"/>
    """,
    "star": """
        <path d="M12 3.6l2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8L12 3.6z"/>
    """,
    "star_filled": """
        <path d="M12 3.6l2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8L12 3.6z"
              fill="currentColor"/>
    """,
    "database": """
        <ellipse cx="12" cy="5.5" rx="7.4" ry="2.8"/>
        <path d="M4.6 5.5v6.2c0 1.6 3.3 2.9 7.4 2.9s7.4-1.3 7.4-2.9V5.5"/>
        <path d="M4.6 11.7v6.1c0 1.6 3.3 2.9 7.4 2.9s7.4-1.3 7.4-2.9v-6.1"/>
    """,
    "settings": """
        <path d="M4 7h8M16 7h4M4 17h3M11 17h9"/>
        <circle cx="14" cy="7" r="2.2"/>
        <circle cx="9" cy="17" r="2.2"/>
    """,
    "search": """
        <circle cx="10.7" cy="10.7" r="6.4"/>
        <path d="M15.4 15.4L21 21"/>
    """,
    "plus": """
        <path d="M12 4.2v15.6M4.2 12h15.6"/>
    """,
    "minus": """
        <path d="M4.2 12h15.6"/>
    """,
    "refresh": """
        <path d="M20 7.4V3.8l-2 2A8.3 8.3 0 1 0 20.1 14"/>
        <path d="M20 3.8h-3.6"/>
    """,
    "download": """
        <path d="M12 3.6v11.2M7.8 10.9L12 15.1l4.2-4.2"/>
        <path d="M4.3 16.6v2.1c0 1 .8 1.7 1.7 1.7h12c1 0 1.7-.8 1.7-1.7v-2.1"/>
    """,
    "upload": """
        <path d="M12 15.2V4M7.8 8.1L12 3.9l4.2 4.2"/>
        <path d="M4.3 16.6v2.1c0 1 .8 1.7 1.7 1.7h12c1 0 1.7-.8 1.7-1.7v-2.1"/>
    """,
    "edit": """
        <path d="M4 20h4.1L19.4 8.7a2.1 2.1 0 0 0 0-3l-1.1-1.1a2.1 2.1 0 0 0-3 0L4 15.9V20z"/>
        <path d="M13.7 6.1l4.2 4.2"/>
    """,
    "trash": """
        <path d="M4.3 6.8h15.4M9.2 3.7h5.6l.6 3.1H8.6l.6-3.1zM6.7 6.8l.8 13.1c0 .8.7 1.4 1.5 1.4h6c.8 0 1.5-.6 1.5-1.4l.8-13.1"/>
        <path d="M10 10.5v6.8M14 10.5v6.8"/>
    """,
    "chevron_down": "<path d=\"M6 9l6 6 6-6\"/>",
    "chevron_up": "<path d=\"M6 15l6-6 6 6\"/>",
    "chevron_left": "<path d=\"M15 5l-7 7 7 7\"/>",
    "chevron_right": "<path d=\"M9 5l7 7-7 7\"/>",
    "arrow_up": "<path d=\"M12 20V5M6 11l6-6 6 6\"/>",
    "arrow_down": "<path d=\"M12 4v15M6 13l6 6 6-6\"/>",
    "external": """
        <path d="M14 4.2h5.8V10"/>
        <path d="M19.8 4.2L10.7 13.3"/>
        <path d="M18.1 13.8v4.5c0 .9-.7 1.6-1.6 1.6H5.8c-.9 0-1.6-.7-1.6-1.6V7.6c0-.9.7-1.6 1.6-1.6h4.5"/>
    """,
    "info": """
        <circle cx="12" cy="12" r="8.6"/>
        <path d="M12 10.6v5.1M12 7.4v.2"/>
    """,
    "check": "<path d=\"M4.5 12.5l4.7 4.7L19.8 6.6\"/>",
    "close": "<path d=\"M5.5 5.5l13 13M18.5 5.5l-13 13\"/>",
    "calendar": """
        <rect x="3.8" y="5.2" width="16.4" height="15" rx="2.3"/>
        <path d="M7.8 3.1v4.2M16.2 3.1v4.2M3.8 9.5h16.4"/>
    """,
    "clock": """
        <circle cx="12" cy="12" r="8.6"/>
        <path d="M12 7.2v5.2l3.6 2.1"/>
    """,
    "folder": """
        <path d="M3.6 7.3c0-1 .8-1.8 1.8-1.8h4.1l2 2.3h7.1c1 0 1.8.8 1.8 1.8v8.6c0 1-.8 1.8-1.8 1.8H5.4c-1 0-1.8-.8-1.8-1.8V7.3z"/>
    """,
    "link": """
        <path d="M9.6 14.4l4.8-4.8"/>
        <path d="M7.8 16.2l-1.2 1.2a3.4 3.4 0 0 1-4.8-4.8l3.4-3.4a3.4 3.4 0 0 1 4.8 0"/>
        <path d="M16.2 7.8l1.2-1.2a3.4 3.4 0 0 1 4.8 4.8l-3.4 3.4a3.4 3.4 0 0 1-4.8 0"/>
    """,
    "sparkles": """
        <path d="M11 3.5l1.5 4.1 4.1 1.5-4.1 1.5L11 14.7 9.5 10.6 5.4 9.1l4.1-1.5L11 3.5z"/>
        <path d="M18.2 14.8l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2z"/>
    """,
    "shield": """
        <path d="M12 3.2l7 2.7v5.2c0 4.2-2.8 7.7-7 9.7-4.2-2-7-5.5-7-9.7V5.9l7-2.7z"/>
        <path d="M8.8 12l2.2 2.2 4.4-4.6"/>
    """,
    "list": """
        <path d="M8.5 6.2h11M8.5 12h11M8.5 17.8h11"/>
        <circle cx="4.5" cy="6.2" r=".9" fill="currentColor" stroke="none"/>
        <circle cx="4.5" cy="12" r=".9" fill="currentColor" stroke="none"/>
        <circle cx="4.5" cy="17.8" r=".9" fill="currentColor" stroke="none"/>
    """,
    "warning": """
        <path d="M12 3.8L21 20H3L12 3.8z"/>
        <path d="M12 9v4.6M12 17v.2"/>
    """,
    "trend": """
        <path d="M3.5 16.5l5.1-5.2 3.7 2.8 7.8-8.2"/>
        <path d="M15.8 5.9h4.3v4.3"/>
    """,
}


@lru_cache(maxsize=512)
def _render(name: str, color: str, size: int) -> QPixmap:
    color = color if color.startswith("#") else f"#{color}"
    path = _SVG.get(name, _SVG["info"]).replace("currentColor", color)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7" '
        f'stroke-linecap="round" stroke-linejoin="round">{path}</svg>'
    )
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.transparent)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2.0)
    return pixmap


def pixmap(name: str, color: str = "#64748B", size: int = 18) -> QPixmap:
    return _render(name, color, size)


def icon(name: str, color: str = "#64748B", size: int = 18) -> QIcon:
    return QIcon(pixmap(name, color, size))


def two_state_icon(name: str, normal: str = "#8FA6BC", selected: str = "#FFFFFF", size: int = 19) -> QIcon:
    result = QIcon()
    result.addPixmap(_render(name, normal, size), QIcon.Mode.Normal, QIcon.State.Off)
    result.addPixmap(_render(name, selected, size), QIcon.Mode.Normal, QIcon.State.On)
    result.addPixmap(_render(name, selected, size), QIcon.Mode.Active, QIcon.State.On)
    result.addPixmap(_render(name, selected, size), QIcon.Mode.Selected, QIcon.State.On)
    return result


def app_icon(size: int = 64) -> QIcon:
    from .paths import assets_dir

    png = assets_dir() / "app_icon.png"
    if png.exists():
        result = QIcon()
        result.addFile(str(png))
        ico = assets_dir() / "app_icon.ico"
        if ico.exists():
            result.addFile(str(ico))
        return result
    return QIcon(pixmap("chart", "#0F9D8A", size))
