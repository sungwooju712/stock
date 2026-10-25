# -*- coding: utf-8 -*-
"""Dashboard: market pulse, watchlist chart and quick actions."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..charts import PerformanceChart
from ..constants import COLORS
from ..formatters import (
    DASH,
    fmt_market_cap,
    fmt_pct,
    fmt_price,
    tone_class,
)
from ..tables import Column, StockTableView, star_column
from ..widgets import (
    Badge,
    BreadthBar,
    Card,
    EmptyState,
    KpiCard,
    SectionHeader,
    make_button,
)
from .base import ScrollPage


class DashboardPage(ScrollPage):
    export_requested = Signal()
    refresh_requested = Signal()
    navigate_requested = Signal(str)

    def __init__(self, service, parent: QWidget | None = None):
        super().__init__(service, parent=parent)
        self._watch_codes: list[str] = []

        # KPI row ---------------------------------------------------------
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)
        self.kpi_universe = KpiCard(
            "KOSPI 유니버스", "–", "종목 데이터를 불러오는 중", "database",
            accent=COLORS["teal"], soft=COLORS["teal_soft"],
        )
        self.kpi_breadth = KpiCard(
            "상승 / 하락", "–", "시장 흐름", "trend",
            accent=COLORS["rise"], soft=COLORS["positive_soft"],
        )
        self.kpi_watchlist = KpiCard(
            "관심종목", "–", "즐겨찾기 기준", "star",
            accent="#C17A0A", soft=COLORS["amber_soft"],
        )
        self.kpi_cap = KpiCard(
            "KOSPI 시가총액", "–", "전체 상장 종목 합계", "chart",
            accent=COLORS["navy_2"], soft="#EAF2F8",
        )
        for card in (self.kpi_universe, self.kpi_breadth, self.kpi_watchlist, self.kpi_cap):
            card.setMinimumHeight(120)
            kpi_row.addWidget(card, 1)
        self.body.addLayout(kpi_row)

        # Chart + right rail ---------------------------------------------
        middle = QHBoxLayout()
        middle.setSpacing(14)

        chart_card = Card(padding=(18, 16, 18, 14), spacing=8)
        chart_actions = make_button("종목 분석", variant="link")
        chart_actions.clicked.connect(lambda: self.navigate_requested.emit("analysis"))
        self.chart_header = SectionHeader(
            "관심종목 흐름",
            "최근 30거래일 수익률",
            trailing=chart_actions,
        )
        chart_card.body.addWidget(self.chart_header)
        self.chart = PerformanceChart()
        self.chart.setMinimumHeight(300)
        chart_card.body.addWidget(self.chart, 1)
        middle.addWidget(chart_card, 7)

        rail = QVBoxLayout()
        rail.setSpacing(14)

        breadth_card = Card(padding=(16, 14, 16, 14), spacing=9)
        breadth_card.body.addWidget(SectionHeader("시장 온도", "KOSPI 등락 분포"))
        self.breadth_bar = BreadthBar()
        breadth_card.body.addWidget(self.breadth_bar)
        breadth_labels = QHBoxLayout()
        breadth_labels.setSpacing(8)
        self.rising_label = self._breadth_label(COLORS["rise"])
        self.flat_label = self._breadth_label(COLORS["muted"])
        self.falling_label = self._breadth_label(COLORS["fall"])
        breadth_labels.addWidget(self.rising_label)
        breadth_labels.addWidget(self.flat_label)
        breadth_labels.addWidget(self.falling_label)
        breadth_card.body.addLayout(breadth_labels)
        self.breadth_note = QLabel("")
        self.breadth_note.setStyleSheet("font-size: 8pt; color: #718096;")
        self.breadth_note.setWordWrap(True)
        breadth_card.body.addWidget(self.breadth_note)
        rail.addWidget(breadth_card, 0)

        quick_card = Card(padding=(16, 14, 16, 14), spacing=9)
        quick_card.body.addWidget(SectionHeader("빠른 작업", "자주 쓰는 기능을 바로 실행"))
        quick_buttons = [
            ("종목 추가", "plus", "primary", self.add_stock_requested.emit),
            ("스크리너 열기", "filter", "secondary", lambda: self.navigate_requested.emit("screener")),
            ("관심종목 관리", "star", "secondary", lambda: self.navigate_requested.emit("favorites")),
            ("엑셀 보고서", "download", "secondary", self.export_requested.emit),
        ]
        for text, icon_name, variant, callback in quick_buttons:
            button = make_button(text, icon_name=icon_name, variant=variant)
            button.clicked.connect(callback)
            quick_card.body.addWidget(button)
        rail.addWidget(quick_card, 0)
        rail.addStretch(1)
        middle.addLayout(rail, 4)
        self.body.addLayout(middle)

        # Tables ---------------------------------------------------------
        tables = QBoxLayout(QBoxLayout.LeftToRight)
        tables.setSpacing(14)
        self._tables_layout = tables

        top_card = Card(padding=(16, 14, 16, 7), spacing=7)
        top_header = SectionHeader(
            "시가총액 상위",
            "KOSPI 대표 종목",
            trailing=self._link("스크리너", lambda: self.navigate_requested.emit("screener")),
        )
        top_card.body.addWidget(top_header)
        self.top_table = StockTableView(
            [
                star_column(),
                Column(
                    "rank", "#", 38, Qt.AlignCenter,
                    formatter=lambda row: str(row.get("rank", "")),
                ),
                Column("name", "종목명", 128, formatter=lambda row: row.get("name") or row.get("code")),
                Column(
                    "close", "현재가", 90, Qt.AlignRight | Qt.AlignVCenter,
                    formatter=lambda row: fmt_price(row.get("close")),
                ),
                Column(
                    "change_pct", "등락률", 74, Qt.AlignRight | Qt.AlignVCenter,
                    formatter=lambda row: fmt_pct(row.get("change_pct"), signed=True),
                    color=lambda row: COLORS[tone_class(row.get("change_pct")) if tone_class(row.get("change_pct")) != "flat" else "muted"],
                ),
                Column(
                    "market_cap", "시가총액", 105, Qt.AlignRight | Qt.AlignVCenter,
                    formatter=lambda row: fmt_market_cap(row.get("market_cap")),
                ),
            ],
            stretch_last=True,
            row_height=41,
        )
        self.top_table.setFixedHeight(41 * 5 + 42)
        self.top_table.stock_activated.connect(self.analyze_requested.emit)
        self.top_table.star_toggle_requested.connect(self.toggle_favorite)
        self.top_table.context_menu_requested.connect(
            lambda code, pos: self.show_stock_context(self.top_table, pos, code)
        )
        top_card.body.addWidget(self.top_table)
        tables.addWidget(top_card, 1)

        watch_card = Card(padding=(16, 14, 16, 7), spacing=7)
        watch_header = SectionHeader(
            "내 관심종목",
            "즐겨찾기 종목의 최근 흐름",
            trailing=self._link("관리", lambda: self.navigate_requested.emit("favorites")),
        )
        watch_card.body.addWidget(watch_header)
        self.watch_table = StockTableView(
            [
                star_column(),
                Column("name", "종목명", 128, formatter=lambda row: row.get("name") or row.get("code")),
                Column(
                    "latest", "현재가", 88, Qt.AlignRight | Qt.AlignVCenter,
                    formatter=lambda row: fmt_price(row.get("metrics_latest") or row.get("close")),
                ),
                Column(
                    "change_pct", "등락률", 72, Qt.AlignRight | Qt.AlignVCenter,
                    formatter=lambda row: fmt_pct(row.get("metrics_change_pct"), signed=True),
                    color=lambda row: COLORS[tone_class(row.get("metrics_change_pct")) if tone_class(row.get("metrics_change_pct")) != "flat" else "muted"],
                ),
                Column(
                    "since_2023_return", "2023 이후", 90, Qt.AlignRight | Qt.AlignVCenter,
                    formatter=lambda row: fmt_pct(row.get("since_2023_return"), signed=True),
                    color=lambda row: COLORS[tone_class(row.get("since_2023_return")) if tone_class(row.get("since_2023_return")) != "flat" else "muted"],
                ),
                Column(
                    "market_cap", "시가총액", 100, Qt.AlignRight | Qt.AlignVCenter,
                    formatter=lambda row: fmt_market_cap(row.get("market_cap")),
                ),
            ],
            stretch_last=True,
            row_height=41,
        )
        self.watch_empty = EmptyState(
            "아직 관심종목이 없습니다",
            "관심종목을 추가하면 최근 종가와 수익률을 비교할 수 있습니다.",
            icon_name="star",
            action=self._action_button("첫 종목 추가", self.add_stock_requested.emit),
        )
        self.watch_stack = QStackedWidget()
        self.watch_stack.addWidget(self.watch_table)
        self.watch_stack.addWidget(self.watch_empty)
        self.watch_stack.setFixedHeight(41 * 5 + 42)
        self.watch_table.stock_activated.connect(self.analyze_requested.emit)
        self.watch_table.star_toggle_requested.connect(self.toggle_favorite)
        self.watch_table.context_menu_requested.connect(
            lambda code, pos: self.show_stock_context(self.watch_table, pos, code)
        )
        watch_card.body.addWidget(self.watch_stack)
        tables.addWidget(watch_card, 1)
        self.body.addLayout(tables)

        self.footnote = QLabel("")
        self.footnote.setStyleSheet("font-size: 7.5pt; color: #94A3B8;")
        self.footnote.setWordWrap(True)
        self.body.addWidget(self.footnote)
        self.body.addStretch(1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "_tables_layout"):
            return
        horizontal = self.width() >= 1100
        direction = QBoxLayout.LeftToRight if horizontal else QBoxLayout.TopToBottom
        if self._tables_layout.direction() == direction:
            return
        self._tables_layout.setDirection(direction)
        for index in (0, 1):
            self._tables_layout.setStretch(index, 1 if horizontal else 0)

    # ------------------------------------------------------------------
    @staticmethod
    def _breadth_label(color: str) -> QLabel:
        label = QLabel(DASH)
        label.setStyleSheet(f"font-size: 8pt; color: {color}; font-weight: 700;")
        return label

    @staticmethod
    def _link(text: str, callback):
        button = make_button(text, variant="link")
        button.clicked.connect(callback)
        return button

    @staticmethod
    def _action_button(text: str, callback):
        button = make_button(text, icon_name="plus", variant="primary")
        button.clicked.connect(callback)
        return button

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        counts = self.db.counts()
        overview = self.service.market_overview()
        watchlist = self.service.watchlist_metrics()
        self._watch_codes = [row["code"] for row in watchlist]

        total = int(overview.get("total") or counts.get("stocks") or 0)
        rising = int(overview.get("rising") or 0)
        falling = int(overview.get("falling") or 0)
        flat = int(overview.get("flat") or 0)
        total_cap = overview.get("total_market_cap") or 0
        over_1000 = overview.get("over_1000") or 0

        self.kpi_universe.set_data(
            f"{total:,}",
            f"보통주·우선주 포함 · 재무 {counts.get('fundamentals', 0):,}개",
        )
        self.kpi_breadth.set_data(
            f"{rising:,} / {falling:,}",
            f"보합 {flat:,}개 · 상승 비율 {rising / total * 100 if total else 0:.1f}%",
        )
        returns = [
            row["since_2023_return"]
            for row in watchlist
            if row.get("since_2023_return") is not None
        ]
        average_return = sum(returns) / len(returns) if returns else None
        self.kpi_watchlist.set_data(
            f"{len(watchlist):,}",
            f"평균 2023 이후 {fmt_pct(average_return, signed=True)}"
            if average_return is not None
            else "2023 이후 수익률 계산 대기",
        )
        self.kpi_cap.set_data(
            fmt_market_cap(total_cap),
            f"1,000억원 이상 {int(round(over_1000 * total)):,}개",
        )

        self.breadth_bar.set_values(rising, falling, flat)
        self.rising_label.setText(f"상승 {rising:,}")
        self.flat_label.setText(f"보합 {flat:,}")
        self.falling_label.setText(f"하락 {falling:,}")
        self.breadth_note.setText(
            f"상승 {rising:,}개 ({rising / total * 100 if total else 0:.1f}%) · "
            f"하락 {falling:,}개 ({falling / total * 100 if total else 0:.1f}%)\n"
            f"시가총액 1,000억원 이상 {int(round(over_1000 * total)):,}개"
        )

        top_rows = []
        for index, row in enumerate(overview.get("top") or [], start=1):
            item = dict(row)
            item["rank"] = index
            item["in_watchlist"] = self.db.is_in_watchlist(item["code"])
            top_rows.append(item)
        self.top_table.set_rows(top_rows)

        for row in watchlist:
            row["in_watchlist"] = True
        self.watch_table.set_rows(watchlist)
        self.watch_stack.setCurrentIndex(0 if watchlist else 1)

        if watchlist:
            chart_codes = self._watch_codes[:8]
            payload = self.service.chart_payload(chart_codes, period="recent", mode="return")
            self.chart.set_payload(payload)
            self.chart_header.set_subtitle(
                f"최근 30거래일 수익률 · {len(chart_codes)}개 종목"
                + (" (최대 8개 표시)" if len(self._watch_codes) > 8 else "")
            )
        else:
            self.chart.set_payload({"categories": [], "series": [], "mode": "return", "period": "recent"})
            self.chart_header.set_subtitle("관심종목을 추가하면 최근 흐름이 표시됩니다")

        self.footnote.setText(
            f"기준일 {self.basis_date()} · 출처 NAVER Finance / KRX · "
            "재무 지표는 최근 확정 연간 실적 기준 · 정보 제공용이며 투자 권유가 아닙니다."
        )

    def on_watchlist_changed(self, code: str, added: bool) -> None:
        self.refresh()
