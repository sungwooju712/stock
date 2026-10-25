# -*- coding: utf-8 -*-
"""Sortable stock tables shared by the dashboard, screener and reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPoint, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTableView,
    QWidget,
)

from .constants import COLORS
from .formatters import DASH
from .paths import naver_stock_url


@dataclass(frozen=True)
class Column:
    """A display/sort definition for :class:`StockTableModel`."""

    key: str
    label: str
    width: int = 100
    align: Qt.AlignmentFlag = Qt.AlignLeft | Qt.AlignVCenter
    formatter: Callable[[dict[str, Any]], str] | None = None
    color: Callable[[dict[str, Any]], str | None] | None = None
    sort_key: Callable[[dict[str, Any]], Any] | None = None
    bold: bool = False
    tooltip: Callable[[dict[str, Any]], str] | None = None


class StockTableModel(QAbstractTableModel):
    def __init__(
        self,
        columns: Sequence[Column],
        rows: Sequence[dict[str, Any]] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.columns = list(columns)
        self.rows: list[dict[str, Any]] = list(rows or [])
        self._sort_column = -1
        self._sort_order = Qt.DescendingOrder

    # ------------------------------------------------------------------
    # Qt model API
    # ------------------------------------------------------------------
    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation != Qt.Horizontal or not (0 <= section < len(self.columns)):
            return None
        column = self.columns[section]
        if role == Qt.DisplayRole:
            return column.label
        if role == Qt.TextAlignmentRole:
            return int(column.align)
        if role == Qt.FontRole:
            font = QFont("Malgun Gothic", 8)
            font.setWeight(QFont.DemiBold)
            return font
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.rows)):
            return None
        row = self.rows[index.row()]
        column = self.columns[index.column()]
        if role == Qt.DisplayRole:
            if column.formatter is not None:
                try:
                    return column.formatter(row)
                except Exception:
                    return DASH
            value = row.get(column.key)
            if value is None or value == "":
                return DASH
            return str(value)
        if role == Qt.TextAlignmentRole:
            return int(column.align)
        if role == Qt.ForegroundRole:
            color = None
            if column.color is not None:
                try:
                    color = column.color(row)
                except Exception:
                    color = None
            if not color:
                value = row.get(column.key)
                if isinstance(value, (int, float)) and column.key in {
                    "change_pct",
                    "change",
                    "period_return",
                    "since_2023_return",
                    "ytd_return",
                }:
                    color = COLORS["rise"] if value > 0 else COLORS["fall"] if value < 0 else COLORS["muted"]
            if color:
                return QColor(color)
            return None
        if role == Qt.FontRole:
            if column.bold or column.key in {"name", "stock_name"}:
                font = QFont("Malgun Gothic", 9)
                font.setWeight(QFont.DemiBold)
                return font
            return None
        if role == Qt.ToolTipRole:
            if column.tooltip is not None:
                try:
                    return column.tooltip(row)
                except Exception:
                    pass
            code = row.get("code")
            name = row.get("name") or row.get("stock_name")
            if code:
                return f"{name or ''} ({code})"
            return None
        if role == Qt.UserRole:
            return row
        return None

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def set_rows(self, rows: Sequence[dict[str, Any]]) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()
        if self._sort_column >= 0:
            self._apply_sort()

    def update_watchlist_flags(self, codes: set[str]) -> None:
        if not self.rows:
            return
        for row in self.rows:
            row["in_watchlist"] = row.get("code") in codes
        if any(column.key == "star" for column in self.columns):
            top_left = self.index(0, 0)
            bottom = self.index(len(self.rows) - 1, 0)
            self.dataChanged.emit(top_left, bottom, [Qt.DisplayRole, Qt.ForegroundRole, Qt.UserRole])

    def row_at(self, row: int) -> dict[str, Any] | None:
        if 0 <= row < len(self.rows):
            return self.rows[row]
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:  # type: ignore[override]
        if not (0 <= column < len(self.columns)):
            return
        self._sort_column = column
        self._sort_order = order
        self._apply_sort()

    def _sort_value(self, column: Column, row: dict[str, Any]):
        if column.sort_key is not None:
            try:
                return column.sort_key(row)
            except Exception:
                return None
        return row.get(column.key)

    def _apply_sort(self) -> None:
        if self._sort_column < 0 or not self.rows:
            return
        column = self.columns[self._sort_column]
        present: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []
        for row in self.rows:
            value = self._sort_value(column, row)
            if value is None or value == "":
                missing.append(row)
            else:
                present.append(row)

        def key(row):
            value = self._sort_value(column, row)
            if isinstance(value, str):
                return value.casefold()
            return value

        try:
            present.sort(key=key, reverse=self._sort_order == Qt.DescendingOrder)
        except TypeError:
            present.sort(key=lambda row: str(key(row)).casefold(), reverse=self._sort_order == Qt.DescendingOrder)
        self.layoutAboutToBeChanged.emit()
        self.rows = present + missing
        self.layoutChanged.emit()


class StockTableView(QTableView):
    stock_activated = Signal(str)
    star_toggle_requested = Signal(str)
    context_menu_requested = Signal(str, object)

    def __init__(
        self,
        columns: Sequence[Column],
        *,
        stretch_last: bool = True,
        row_height: int = 42,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.columns = list(columns)
        self.stock_model = StockTableModel(self.columns, parent=self)
        self.setModel(self.stock_model)
        self.setObjectName("StockTable")
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setSortingEnabled(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(row_height)

        header = self.horizontalHeader()
        header.setHighlightSections(False)
        header.setSectionsMovable(False)
        header.setSectionsClickable(True)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setMinimumSectionSize(36)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSortIndicatorShown(True)
        for index, column in enumerate(self.columns):
            self.setColumnWidth(index, column.width)
        if stretch_last and self.columns:
            header.setSectionResizeMode(len(self.columns) - 1, QHeaderView.Stretch)
        self.horizontalHeader().setMinimumHeight(38)
        self.setStyleSheet("QTableView { background: #FFFFFF; }")

        self.doubleClicked.connect(self._on_double_click)
        self.clicked.connect(self._on_click)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def set_rows(self, rows: Sequence[dict[str, Any]]) -> None:
        self.stock_model.set_rows(rows)
        self.clearSelection()

    def sort_by(self, key: str, order: Qt.SortOrder = Qt.DescendingOrder) -> None:
        for index, column in enumerate(self.columns):
            if column.key == key:
                self.sortByColumn(index, order)
                return

    def update_watchlist_flags(self, codes: set[str]) -> None:
        self.stock_model.update_watchlist_flags(codes)

    def row_at(self, row: int) -> dict[str, Any] | None:
        return self.stock_model.row_at(row)

    def current_row_data(self) -> dict[str, Any] | None:
        index = self.currentIndex()
        if not index.isValid():
            return None
        return self.stock_model.row_at(index.row())

    def selected_code(self) -> str | None:
        row = self.current_row_data()
        return row.get("code") if row else None

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def _code_at(self, index: QModelIndex) -> str | None:
        if not index.isValid():
            return None
        row = self.stock_model.row_at(index.row())
        return row.get("code") if row else None

    def _on_double_click(self, index: QModelIndex) -> None:
        code = self._code_at(index)
        if code:
            self.stock_activated.emit(code)

    def _on_click(self, index: QModelIndex) -> None:
        if index.column() == 0 and self.columns and self.columns[0].key == "star":
            code = self._code_at(index)
            if code:
                self.star_toggle_requested.emit(code)

    def _on_context_menu(self, position: QPoint) -> None:
        index = self.indexAt(position)
        code = self._code_at(index)
        if code:
            self.setCurrentIndex(index)
            self.context_menu_requested.emit(code, self.viewport().mapToGlobal(position))

    def mouseMoveEvent(self, event) -> None:
        index = self.indexAt(event.position().toPoint())
        if index.isValid() and index.column() == 0 and self.columns and self.columns[0].key == "star":
            self.viewport().setCursor(Qt.PointingHandCursor)
        else:
            self.viewport().setCursor(Qt.ArrowCursor)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self.viewport().setCursor(Qt.ArrowCursor)
        super().leaveEvent(event)


def star_column() -> Column:
    return Column(
        key="star",
        label="",
        width=34,
        align=Qt.AlignCenter,
        formatter=lambda row: "★" if row.get("in_watchlist") else "☆",
        color=lambda row: COLORS["amber"] if row.get("in_watchlist") else "#C3CFDB",
        sort_key=lambda row: 1 if row.get("in_watchlist") else 0,
    )


def show_stock_menu(
    parent: QWidget,
    position: QPoint,
    *,
    code: str,
    name: str,
    is_favorite: bool,
    on_analyze: Callable[[str], None],
    on_toggle_favorite: Callable[[str], None],
    extras: Sequence[tuple[str, Callable[[], None]]] = (),
) -> None:
    """Show the consistent stock context menu used across pages."""

    menu = QMenu(parent)
    analyze_action = menu.addAction("종목 분석 열기")
    analyze_action.triggered.connect(lambda: on_analyze(code))
    menu.addSeparator()
    favorite_action = menu.addAction(
        "관심종목에서 제거" if is_favorite else "관심종목에 추가"
    )
    favorite_action.triggered.connect(lambda: on_toggle_favorite(code))
    if extras:
        menu.addSeparator()
        for label, callback in extras:
            action = menu.addAction(label)
            action.triggered.connect(callback)
    menu.addSeparator()
    naver_action = menu.addAction("네이버증권에서 열기")
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    naver_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(naver_stock_url(code))))
    copy_action = menu.addAction("종목 코드 복사")
    copy_action.triggered.connect(lambda: QGuiApplication.clipboard().setText(code))
    menu.exec(position)
