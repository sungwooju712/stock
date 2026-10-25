# -*- coding: utf-8 -*-
"""Favorites management with inline alias/memo editing and ordering."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..constants import COLORS
from ..formatters import DASH, fmt_date, fmt_market_cap, fmt_pct, fmt_price, tone_class
from ..widgets import (
    Card,
    EmptyState,
    MetricTile,
    SectionHeader,
    make_button,
    make_icon_button,
)
from .base import PageBase


class FavoritesPage(PageBase):
    export_requested = Signal()

    def __init__(self, service, parent: QWidget | None = None):
        super().__init__(service, parent)
        self._loading = False
        self._ignore_external_refresh = False
        self._rows: list[dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 20, 26, 20)
        layout.setSpacing(12)

        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.stat_count = MetricTile("즐겨찾기", "–", note="관심종목 수")
        self.stat_average = MetricTile("평균 수익률", "–", note="2023-01-02 이후")
        self.stat_rising = MetricTile("상승 종목", "–", note="2023 이후 기준")
        self.stat_cap = MetricTile("총 시가총액", "–", note="관심종목 합계")
        for tile in (self.stat_count, self.stat_average, self.stat_rising, self.stat_cap):
            tile.setMinimumHeight(72)
            stats.addWidget(tile, 1)
        layout.addLayout(stats)

        card = Card(padding=(16, 13, 16, 8), spacing=7)
        actions = QWidget()
        action_layout = QHBoxLayout(actions)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)
        add_button = make_button("종목 추가", icon_name="plus", variant="primary")
        add_button.clicked.connect(self.add_stock_requested.emit)
        action_layout.addWidget(add_button)
        self.export_button = make_button("엑셀 보고서", icon_name="download", variant="soft")
        self.export_button.clicked.connect(self.export_requested.emit)
        action_layout.addWidget(self.export_button)
        self.header = SectionHeader(
            "즐겨찾기 관리",
            "별칭과 메모를 클릭해 바로 수정할 수 있습니다 · 자동 저장",
            trailing=actions,
        )
        card.body.addWidget(self.header)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            ["순서", "종목명", "코드", "별칭", "메모", "현재가", "등락률", "2023 이후", "시가총액", "관리"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        self.table.setRowHeight(0, 50)
        self.table.verticalHeader().setDefaultSectionSize(52)
        header = self.table.horizontalHeader()
        header.setHighlightSections(False)
        header.setMinimumHeight(38)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        widths = [40, 108, 68, 82, 104, 84, 64, 90, 88, 104]
        for index, width in enumerate(widths):
            self.table.setColumnWidth(index, width)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context)

        self.empty_state = EmptyState(
            "즐겨찾기가 비어 있습니다",
            "관심종목을 추가하면 별칭·메모를 관리하고 엑셀 보고서를 만들 수 있습니다.",
            icon_name="star",
            action=make_button("첫 종목 추가", icon_name="plus", variant="primary"),
        )
        self.empty_state.action.clicked.connect(self.add_stock_requested.emit)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.table)
        self.stack.addWidget(self.empty_state)
        card.body.addWidget(self.stack, 1)
        footer = QHBoxLayout()
        note = QLabel("이름·별칭·메모 셀을 더블클릭하거나 선택 후 입력하세요 · ↑/↓ 버튼으로 순서 변경")
        note.setStyleSheet("font-size: 7.5pt; color: #94A3B8;")
        footer.addWidget(note)
        footer.addStretch(1)
        self.save_hint = QLabel("")
        self.save_hint.setStyleSheet("font-size: 7.5pt; color: #0A7C6D; font-weight: 600;")
        footer.addWidget(self.save_hint)
        card.body.addLayout(footer)
        layout.addWidget(card, 1)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        rows = self.service.watchlist_metrics()
        self._rows = rows
        self._loading = True
        self.table.setRowCount(0)
        for index, row in enumerate(rows):
            self._add_row(index, row)
        self.table.setRowCount(len(rows))
        self._loading = False
        self.stack.setCurrentIndex(0 if rows else 1)
        self.export_button.setEnabled(bool(rows))
        self._update_summary(rows)
        self.save_hint.setText("")

    def _add_row(self, index: int, row: dict[str, Any]) -> None:
        self.table.insertRow(index)
        code = row.get("code") or ""
        name = row.get("name") or code
        values = {
            0: str(index + 1),
            1: name,
            2: code,
            3: row.get("alias") or "",
            4: row.get("memo") or "",
            5: fmt_price(row.get("metrics_latest") or row.get("close")),
            6: fmt_pct(row.get("metrics_change_pct"), signed=True),
            7: fmt_pct(row.get("since_2023_return"), signed=True),
            8: fmt_market_cap(row.get("market_cap")),
        }
        for column, text in values.items():
            item = QTableWidgetItem(text)
            if column == 0:
                item.setTextAlignment(Qt.AlignCenter)
            elif column in {2, 3, 4}:
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            else:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if column == 1:
                font = QFont("Malgun Gothic", 9)
                font.setWeight(QFont.DemiBold)
                item.setFont(font)
                item.setToolTip(f"{name} ({code})\n추가일 {fmt_date((row.get('added_at') or '')[:10])}")
            if column in {3, 4}:
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                item.setToolTip("클릭 후 바로 수정할 수 있습니다.")
            else:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if column == 1:
                item.setData(Qt.UserRole, code)
            if column in {6, 7}:
                tone = tone_class(row.get("metrics_change_pct") if column == 6 else row.get("since_2023_return"))
                item.setForeground(
                    QColor(COLORS["rise"] if tone == "rise" else COLORS["fall"] if tone == "fall" else COLORS["muted"])
                )
                if column == 6:
                    font = QFont("Malgun Gothic", 8.5)
                    font.setWeight(QFont.DemiBold)
                    item.setFont(font)
            self.table.setItem(index, column, item)

        manage = QWidget()
        manage_layout = QHBoxLayout(manage)
        manage_layout.setContentsMargins(0, 0, 0, 0)
        manage_layout.setSpacing(1)
        up = make_icon_button("arrow_up", "위로 이동", color=COLORS["muted"])
        up.setEnabled(index > 0)
        up.clicked.connect(lambda checked=False, target=code: self._move(target, -1))
        manage_layout.addWidget(up)
        down = make_icon_button("arrow_down", "아래로 이동", color=COLORS["muted"])
        down.setEnabled(index < len(self._rows) - 1)
        down.clicked.connect(lambda checked=False, target=code: self._move(target, 1))
        manage_layout.addWidget(down)
        analyze = make_icon_button("chart", "종목 분석", color=COLORS["teal_dark"])
        analyze.clicked.connect(lambda checked=False, target=code: self.analyze_requested.emit(target))
        manage_layout.addWidget(analyze)
        remove = make_icon_button("trash", "관심종목에서 제거", color=COLORS["rise"])
        remove.clicked.connect(lambda checked=False, target=code, target_name=name: self._remove(target, target_name))
        manage_layout.addWidget(remove)
        self.table.setCellWidget(index, 9, manage)

    def _update_summary(self, rows: list[dict[str, Any]]) -> None:
        returns = [row["since_2023_return"] for row in rows if row.get("since_2023_return") is not None]
        average = sum(returns) / len(returns) if returns else None
        rising = sum(1 for value in returns if value > 0)
        total_cap = sum(row.get("market_cap") or 0 for row in rows)
        self.stat_count.set_value(f"{len(rows):,}", "관심종목 수")
        self.stat_average.set_value(
            fmt_pct(average, signed=True) if average is not None else DASH,
            "2023-01-02 이후",
            color="rise" if (average or 0) > 0 else "fall" if (average or 0) < 0 else None,
        )
        self.stat_rising.set_value(
            f"{rising:,} / {len(returns):,}" if returns else DASH,
            "2023 이후 상승",
        )
        self.stat_cap.set_value(fmt_market_cap(total_cap) if total_cap else DASH, "관심종목 합계")

    # ------------------------------------------------------------------
    def _code_for_row(self, row: int) -> str | None:
        item = self.table.item(row, 1)
        return item.data(Qt.UserRole) if item else None

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading or item.column() not in {3, 4}:
            return
        row_index = item.row()
        code = self._code_for_row(row_index)
        if not code:
            return
        alias_item = self.table.item(row_index, 3)
        memo_item = self.table.item(row_index, 4)
        alias = alias_item.text().strip() if alias_item else ""
        memo = memo_item.text().strip() if memo_item else ""
        self.db.update_watchlist_item(code, alias=alias, memo=memo)
        self.save_hint.setText("저장됨")
        self._emit_change(code)

    def _emit_change(self, code: str) -> None:
        """Notify other pages without rebuilding this table mid-edit."""
        self._ignore_external_refresh = True
        try:
            self.watchlist_changed.emit(code)
        finally:
            self._ignore_external_refresh = False

    def _move(self, code: str, direction: int) -> None:
        self.db.move_watchlist(code, direction)
        self.refresh()
        self._emit_change(code)
        self.notify("관심종목 순서를 변경했습니다.", "info")

    def _remove(self, code: str, name: str) -> None:
        answer = QMessageBox.question(
            self,
            "관심종목 제거",
            f"'{name}'을(를) 관심종목에서 제거할까요?\n종목 데이터와 일별 종가는 유지됩니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.db.remove_from_watchlist(code)
        self.refresh()
        self._emit_change(code)
        self.notify(f"{name}을(를) 관심종목에서 제거했습니다.", "info")

    def _on_double_click(self, row: int, column: int) -> None:
        if column in {3, 4}:
            return
        code = self._code_for_row(row)
        if code:
            self.analyze_requested.emit(code)

    def _on_context(self, position) -> None:
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        code = self._code_for_row(index.row())
        if not code:
            return
        extras = (("종목 분석", lambda: self.analyze_requested.emit(code)),)
        self.show_stock_context(self.table, self.table.viewport().mapToGlobal(position), code, extras)

    def on_watchlist_changed(self, code: str, added: bool) -> None:
        if self._ignore_external_refresh:
            return
        self.refresh()
