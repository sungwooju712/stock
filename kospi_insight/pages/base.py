# -*- coding: utf-8 -*-
"""Base classes and shared helpers for application pages."""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence

from PySide6.QtCore import QPoint, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..constants import COLORS
from ..formatters import DASH
from ..icons import icon, pixmap
from ..paths import naver_stock_url
from ..services import MarketService
from ..tables import show_stock_menu
from ..widgets import set_prop


class PageBase(QWidget):
    message_requested = Signal(str, str)
    watchlist_changed = Signal(str)
    analyze_requested = Signal(str)
    add_stock_requested = Signal()

    def __init__(self, service: MarketService, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self.db = service.db

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Reload page data.  Safe to call whenever a page becomes visible."""

    def on_watchlist_changed(self, code: str, added: bool) -> None:
        """React to a favorite change triggered elsewhere in the app."""

    def notify(self, message: str, kind: str = "success") -> None:
        self.message_requested.emit(message, kind)

    def basis_date(self) -> str:
        return self.db.latest_price_date() or date.today().isoformat()

    # ------------------------------------------------------------------
    def toggle_favorite(self, code: str) -> bool:
        stock = self.db.get_stock(code)
        name = (stock or {}).get("name") or code
        if self.db.is_in_watchlist(code):
            self.db.remove_from_watchlist(code)
            self.watchlist_changed.emit(code)
            self.notify(f"{name}을(를) 관심종목에서 제거했습니다.", "info")
            return False
        added = self.service.add_watchlist(code)
        if added:
            self.watchlist_changed.emit(code)
            self.notify(f"{name}을(를) 관심종목에 추가했습니다.")
        else:
            self.notify(f"{name}은(는) 이미 관심종목에 있습니다.", "info")
        return added

    def show_stock_context(
        self,
        parent: QWidget,
        position: QPoint,
        code: str,
        extras: Sequence[tuple[str, Any]] = (),
    ) -> None:
        stock = self.db.get_stock(code) or {}
        show_stock_menu(
            parent,
            position,
            code=code,
            name=stock.get("name") or code,
            is_favorite=self.db.is_in_watchlist(code),
            on_analyze=self.analyze_requested.emit,
            on_toggle_favorite=lambda target: self.toggle_favorite(target),
            extras=extras,
        )

    @staticmethod
    def open_naver(code: str) -> None:
        QDesktopServices.openUrl(QUrl(naver_stock_url(code)))


class ScrollPage(PageBase):
    """Page with a vertical scroll area and a ready-to-use body layout."""

    def __init__(
        self,
        service: MarketService,
        *,
        margins: tuple[int, int, int, int] = (26, 22, 26, 28),
        spacing: int = 16,
        parent: QWidget | None = None,
    ):
        super().__init__(service, parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName("PageRoot")
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(*margins)
        self.body.setSpacing(spacing)
        self.scroll.setWidget(self.content)
        outer.addWidget(self.scroll)


class KeyValueRow(QWidget):
    """Compact label/value row used in data tables and settings."""

    def __init__(
        self,
        label: str,
        value: str = DASH,
        *,
        label_width: int | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.key_label = QLabel(label)
        self.key_label.setStyleSheet("font-size: 8.5pt; color: #718096;")
        if label_width:
            self.key_label.setFixedWidth(label_width)
        layout.addWidget(self.key_label)
        layout.addStretch(1)
        self.value_label = QLabel(value)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_label.setStyleSheet("font-size: 9pt; color: #122033; font-weight: 700;")
        layout.addWidget(self.value_label)

    def set_value(self, value: str, color: str | None = None) -> None:
        self.value_label.setText(value)
        tone = {
            "rise": COLORS["rise"],
            "fall": COLORS["fall"],
            "muted": COLORS["muted"],
            "teal": COLORS["teal_dark"],
        }.get(color or "")
        self.value_label.setStyleSheet(
            f"font-size: 9pt; color: {tone or '#122033'}; font-weight: 700;"
        )


def icon_label(name: str, color: str = COLORS["teal"], size: int = 18) -> QLabel:
    label = QLabel()
    label.setFixedSize(size, size)
    label.setPixmap(pixmap(name, color, size))
    return label


def text_icon_button(text: str, icon_name: str, *, variant: str = "secondary"):
    from ..widgets import make_button

    return make_button(text, icon_name=icon_name, variant=variant)


def date_korean(iso_date: str) -> str:
    try:
        parsed = date.fromisoformat(iso_date)
    except (TypeError, ValueError):
        return str(iso_date)
    weekday = ["월", "화", "수", "목", "금", "토", "일"][parsed.weekday()]
    return f"{parsed.isoformat()} ({weekday})"
