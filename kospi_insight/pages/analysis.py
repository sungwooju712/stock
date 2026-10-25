# -*- coding: utf-8 -*-
"""Stock analysis: comparison chart, fundamentals and per-stock close lookup."""

from __future__ import annotations

from datetime import date
from typing import Any

from PySide6.QtCore import QDate, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QBoxLayout,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..charts import PerformanceChart
from ..constants import COLORS, DATA_START_DATE
from ..formatters import DASH, fmt_date, fmt_eok, fmt_market_cap, fmt_pct, fmt_price, fmt_volume, tone_class
from ..widgets import (
    Badge,
    Card,
    EmptyState,
    MetricTile,
    SectionHeader,
    SegmentedControl,
    make_button,
    make_icon_button,
    set_prop,
)
from .base import PageBase, date_korean, icon_label


class AnalysisPage(PageBase):
    export_stock_requested = Signal(str)
    load_prices_requested = Signal(str)

    PERIODS = [
        ("full", "전체기간"),
        ("annual", "연간"),
        ("monthly", "월간"),
        ("recent", "전일종가"),
    ]
    MODES = [("price", "주가"), ("return", "수익률")]
    RETURN_LABELS = [
        ("1D", "1일"),
        ("1W", "1주"),
        ("1M", "1개월"),
        ("3M", "3개월"),
        ("6M", "6개월"),
        ("1Y", "1년"),
        ("YTD", "YTD"),
    ]

    def __init__(self, service, parent: QWidget | None = None):
        super().__init__(service, parent)
        self.current_code: str | None = None
        self.chart_period = "full"
        self.chart_mode = "price"
        self._detail_code: str | None = None
        self._checked_codes: set[str] = set()
        self._checks_initialized = False
        self._list_signature: tuple | None = None
        self._rebuilding_list = False
        self._updating_lookup = False
        self._last_lookup: dict[str, Any] | None = None
        self._watch_rows: dict[str, dict[str, Any]] = {}

        outer = QHBoxLayout(self)
        outer.setContentsMargins(26, 20, 26, 20)
        outer.setSpacing(14)

        # ------------------------------------------------------------------
        # Left: watchlist
        # ------------------------------------------------------------------
        left = Card(padding=(12, 14, 12, 12), spacing=8)
        left.setFixedWidth(268)
        self.left_card = left
        left_header = SectionHeader(
            "관심종목",
            "체크한 종목을 차트에서 비교",
            trailing=make_icon_button("plus", "관심종목 추가", color=COLORS["teal_dark"], variant="soft"),
        )
        left_header.trailing.clicked.connect(self.add_stock_requested.emit)
        left.body.addWidget(left_header)
        self.stock_list = QListWidget()
        self.stock_list.setObjectName("WatchList")
        self.stock_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.stock_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.stock_list.setSpacing(1)
        self.stock_list.currentItemChanged.connect(self._on_current_changed)
        self.stock_list.itemChanged.connect(self._on_item_changed)
        self.stock_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.stock_list.customContextMenuRequested.connect(self._on_list_context)
        left.body.addWidget(self.stock_list, 1)
        self.list_hint = QLabel("현재 종목 + 체크 종목 비교 · 최대 8개")
        self.list_hint.setStyleSheet("font-size: 7.5pt; color: #94A3B8;")
        self.list_hint.setWordWrap(True)
        left.body.addWidget(self.list_hint)
        self.add_button = make_button("종목 추가", icon_name="plus", variant="secondary")
        self.add_button.clicked.connect(self.add_stock_requested.emit)
        left.body.addWidget(self.add_button)
        outer.addWidget(left)

        # ------------------------------------------------------------------
        # Right stack
        # ------------------------------------------------------------------
        self.right_stack = QStackedWidget()
        outer.addWidget(self.right_stack, 1)

        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.setContentsMargins(20, 20, 20, 20)
        empty_layout.addStretch(1)
        empty_empty = EmptyState(
            "분석할 종목을 선택하세요",
            "관심종목을 추가하거나 검색에서 종목을 열면 종가·재무·차트를 확인할 수 있습니다.",
            icon_name="chart",
            action=make_button("관심종목 추가", icon_name="plus", variant="primary"),
        )
        empty_empty.action.clicked.connect(self.add_stock_requested.emit)
        empty_layout.addWidget(empty_empty, 0, Qt.AlignHCenter)
        empty_layout.addStretch(1)
        self.right_stack.addWidget(empty_page)

        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setFrameShape(QScrollArea.NoFrame)
        self.detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        detail_content = QWidget()
        self.detail_body = QVBoxLayout(detail_content)
        self.detail_body.setContentsMargins(0, 0, 4, 12)
        self.detail_body.setSpacing(14)
        self.detail_scroll.setWidget(detail_content)
        self.right_stack.addWidget(self.detail_scroll)

        self._build_hero()
        self._build_metric_row()
        self._build_chart_card()
        self._build_bottom_cards()

        self.detail_note = QLabel(
            "출처 NAVER Finance / KRX · 재무 지표는 최근 확정 연간 실적 기준 · "
            "종가는 2023-01-02부터 전일 종가까지 · 투자 권유가 아닙니다."
        )
        self.detail_note.setStyleSheet("font-size: 7.5pt; color: #94A3B8;")
        self.detail_note.setWordWrap(True)
        self.detail_body.addWidget(self.detail_note)
        self.detail_body.addStretch(1)

        self.right_stack.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------
    def _build_hero(self) -> None:
        hero = Card(padding=(22, 18, 22, 18), spacing=10, variant="dark")
        top = QHBoxLayout()
        top.setSpacing(12)
        name_box = QVBoxLayout()
        name_box.setSpacing(4)
        self.hero_name = QLabel("–")
        self.hero_name.setObjectName("HeroName")
        name_box.addWidget(self.hero_name)
        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        self.hero_meta = QLabel("–")
        self.hero_meta.setObjectName("HeroMeta")
        meta_row.addWidget(self.hero_meta)
        self.hero_market_badge = Badge("KOSPI", "dark")
        self.hero_market_badge.setStyleSheet(
            "background: #173B59; color: #D8E8F5; border: 1px solid #245175; "
            "border-radius: 10px; padding: 2px 8px; font-size: 7.5pt; font-weight: 700;"
        )
        meta_row.addWidget(self.hero_market_badge)
        self.hero_preferred_badge = Badge("우선주", "amber")
        self.hero_preferred_badge.setVisible(False)
        meta_row.addWidget(self.hero_preferred_badge)
        meta_row.addStretch(1)
        name_box.addLayout(meta_row)
        top.addLayout(name_box, 1)

        self.favorite_button = make_button("관심종목", icon_name="star_filled", icon_color="#C17A0A", variant="soft")
        self.favorite_button.clicked.connect(self._toggle_current_favorite)
        top.addWidget(self.favorite_button, 0, Qt.AlignTop)
        naver_button = make_button("네이버", icon_name="external", variant="secondary")
        naver_button.clicked.connect(lambda: self.open_naver(self.current_code or ""))
        top.addWidget(naver_button, 0, Qt.AlignTop)
        export_button = make_button("엑셀", icon_name="download", variant="secondary")
        export_button.clicked.connect(self._export_current)
        top.addWidget(export_button, 0, Qt.AlignTop)
        hero.body.addLayout(top)

        price_row = QHBoxLayout()
        price_row.setSpacing(12)
        self.hero_price = QLabel("–")
        self.hero_price.setObjectName("HeroPrice")
        price_row.addWidget(self.hero_price)
        price_box = QVBoxLayout()
        price_box.setSpacing(2)
        self.hero_change = QLabel("–")
        self.hero_change.setStyleSheet("font-size: 10pt; color: #9DB3C7; font-weight: 700;")
        price_box.addWidget(self.hero_change)
        self.hero_date = QLabel("–")
        self.hero_date.setStyleSheet("font-size: 7.5pt; color: #7F99B0;")
        price_box.addWidget(self.hero_date)
        price_row.addLayout(price_box)
        price_row.addStretch(1)

        range_box = QVBoxLayout()
        range_box.setSpacing(3)
        range_title = QLabel("52주 범위")
        range_title.setStyleSheet("font-size: 7.5pt; color: #7F99B0; font-weight: 700;")
        range_box.addWidget(range_title)
        self.hero_range = QLabel("–")
        self.hero_range.setStyleSheet("font-size: 8.5pt; color: #D8E8F5; font-weight: 600;")
        self.hero_range.setWordWrap(True)
        range_box.addWidget(self.hero_range)
        price_row.addLayout(range_box)
        hero.body.addLayout(price_row)
        self.detail_body.addWidget(hero)

    def _build_metric_row(self) -> None:
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self._metric_grid = grid
        self._metric_columns = 3
        self.metric_tiles: dict[str, MetricTile] = {}
        for key, label, note in [
            ("market_cap", "시가총액", "KOSPI"),
            ("per", "PER", "현재가 기준"),
            ("pbr", "PBR", "현재가 기준"),
            ("roe", "ROE", "최근 연간"),
            ("dividend_yield", "배당수익률", "현재가 기준"),
            ("debt_ratio", "부채비율", "최근 연말"),
        ]:
            tile = MetricTile(label, "–", note=note)
            tile.setMinimumHeight(74)
            tile.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.metric_tiles[key] = tile
        self._relayout_metric_tiles(3)
        self.detail_body.addLayout(grid)

    def _relayout_metric_tiles(self, columns: int) -> None:
        columns = max(1, columns)
        if columns == self._metric_columns and self._metric_grid.count():
            return
        for tile in self.metric_tiles.values():
            self._metric_grid.removeWidget(tile)
        for index, tile in enumerate(self.metric_tiles.values()):
            self._metric_grid.addWidget(tile, index // columns, index % columns)
        for column in range(max(3, columns)):
            self._metric_grid.setColumnStretch(column, 1 if column < columns else 0)
        self._metric_columns = columns

    def _build_chart_card(self) -> None:
        card = Card(padding=(18, 15, 18, 12), spacing=7)
        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(7)
        self.period_control = SegmentedControl(self.PERIODS, current="full", compact=True)
        self.mode_control = SegmentedControl(self.MODES, current="price", compact=True)
        self.period_control.changed.connect(self._on_period_changed)
        self.mode_control.changed.connect(self._on_mode_changed)
        controls_layout.addWidget(self.period_control)
        controls_layout.addWidget(self.mode_control)
        self.chart_header = SectionHeader("주가 추이", "종목을 선택하세요", trailing=controls)
        card.body.addWidget(self.chart_header)
        self.chart = PerformanceChart()
        self.chart.setMinimumHeight(370)
        card.body.addWidget(self.chart, 1)
        self.detail_body.addWidget(card)

    def _build_bottom_cards(self) -> None:
        bottom = QBoxLayout(QBoxLayout.LeftToRight)
        bottom.setSpacing(14)
        self.bottom_layout = bottom

        lookup_card = Card(padding=(18, 15, 18, 15), spacing=9)
        lookup_header = SectionHeader("종가 조회", "거래일별 종가와 전후 흐름을 확인합니다")
        lookup_card.body.addWidget(lookup_header)
        controls = QHBoxLayout()
        controls.setSpacing(7)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setMinimumDate(QDate(DATA_START_DATE.year, DATA_START_DATE.month, DATA_START_DATE.day))
        self.date_edit.setMaximumDate(QDate.currentDate())
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._on_date_changed)
        controls.addWidget(self.date_edit, 1)
        lookup_button = make_button("조회", icon_name="search", variant="primary")
        lookup_button.clicked.connect(self._lookup_current)
        controls.addWidget(lookup_button)
        latest_button = make_button("최근 종가", variant="link")
        latest_button.clicked.connect(self._set_latest_date)
        controls.addWidget(latest_button)
        lookup_card.body.addLayout(controls)

        result_frame = QFrame()
        result_frame.setProperty("card", "soft")
        result_layout = QVBoxLayout(result_frame)
        result_layout.setContentsMargins(13, 11, 13, 11)
        result_layout.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.lookup_date_label = QLabel("–")
        self.lookup_date_label.setStyleSheet("font-size: 8pt; color: #718096; font-weight: 600;")
        top.addWidget(self.lookup_date_label)
        self.lookup_exact_label = QLabel("")
        self.lookup_exact_label.setStyleSheet("font-size: 7.5pt; color: #A96700;")
        top.addWidget(self.lookup_exact_label)
        top.addStretch(1)
        self.load_prices_button = make_button("일별 종가 불러오기", icon_name="download", variant="link")
        self.load_prices_button.clicked.connect(
            lambda: self.load_prices_requested.emit(self.current_code or "")
        )
        self.load_prices_button.setVisible(False)
        top.addWidget(self.load_prices_button)
        result_layout.addLayout(top)

        price_line = QHBoxLayout()
        price_line.setSpacing(9)
        self.lookup_price = QLabel("–")
        self.lookup_price.setStyleSheet("font-size: 22pt; font-weight: 800; color: #122033;")
        price_line.addWidget(self.lookup_price)
        self.lookup_change = QLabel("–")
        self.lookup_change.setStyleSheet("font-size: 9pt; color: #64748B; font-weight: 700;")
        price_line.addWidget(self.lookup_change)
        price_line.addStretch(1)
        result_layout.addLayout(price_line)

        stats = QGridLayout()
        stats.setHorizontalSpacing(10)
        stats.setVerticalSpacing(6)
        self.lookup_stats: dict[str, tuple[QLabel, QLabel]] = {}
        for index, (key, label) in enumerate(
            [
                ("open", "시가"),
                ("high", "고가"),
                ("low", "저가"),
                ("previous", "전일 종가"),
                ("volume", "거래량"),
                ("change_pct", "등락률"),
            ]
        ):
            box = QVBoxLayout()
            box.setSpacing(1)
            label_widget = QLabel(label)
            label_widget.setStyleSheet("font-size: 7.5pt; color: #94A3B8;")
            box.addWidget(label_widget)
            value_widget = QLabel("–")
            value_widget.setStyleSheet("font-size: 8.5pt; color: #334155; font-weight: 700;")
            box.addWidget(value_widget)
            stats.addLayout(box, index // 3, index % 3)
            self.lookup_stats[key] = (label_widget, value_widget)
        result_layout.addLayout(stats)

        returns_row = QHBoxLayout()
        returns_row.setSpacing(5)
        self.return_labels: dict[str, QLabel] = {}
        for key, label in self.RETURN_LABELS:
            box = QVBoxLayout()
            box.setSpacing(1)
            title = QLabel(label)
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet("font-size: 7pt; color: #94A3B8;")
            box.addWidget(title)
            value = QLabel("–")
            value.setAlignment(Qt.AlignCenter)
            value.setStyleSheet("font-size: 8pt; color: #64748B; font-weight: 700;")
            box.addWidget(value)
            returns_row.addLayout(box, 1)
            self.return_labels[key] = value
        result_layout.addLayout(returns_row)
        lookup_card.body.addWidget(result_frame)

        table_header = QHBoxLayout()
        table_header.setContentsMargins(0, 2, 0, 0)
        table_title = QLabel("전후 거래일")
        table_title.setStyleSheet("font-size: 8pt; color: #718096; font-weight: 700;")
        table_header.addWidget(table_title)
        table_header.addStretch(1)
        self.lookup_hint = QLabel("")
        self.lookup_hint.setStyleSheet("font-size: 7pt; color: #94A3B8;")
        table_header.addWidget(self.lookup_hint)
        lookup_card.body.addLayout(table_header)

        self.price_table = QTableWidget(0, 5)
        self.price_table.setHorizontalHeaderLabels(["거래일", "종가", "전일대비", "등락률", "거래량"])
        self.price_table.verticalHeader().setVisible(False)
        self.price_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.price_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.price_table.setFocusPolicy(Qt.NoFocus)
        self.price_table.setShowGrid(False)
        self.price_table.setAlternatingRowColors(True)
        self.price_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.price_table.horizontalHeader().setStretchLastSection(True)
        self.price_table.setColumnWidth(0, 92)
        self.price_table.setColumnWidth(1, 84)
        self.price_table.setColumnWidth(2, 80)
        self.price_table.setColumnWidth(3, 70)
        self.price_table.verticalHeader().setDefaultSectionSize(30)
        self.price_table.setFixedHeight(30 * 8 + 37)
        lookup_card.body.addWidget(self.price_table)
        self.lookup_card = lookup_card
        bottom.addWidget(lookup_card, 3)

        finance_card = Card(padding=(18, 15, 18, 15), spacing=8)
        self.finance_header = SectionHeader("재무·밸류에이션", "최근 확정 연간 실적")
        finance_card.body.addWidget(self.finance_header)
        self.finance_rows: dict[str, QLabel] = {}
        for key, label in [
            ("fiscal", "재무 기준"),
            ("sales", "매출액"),
            ("operating_profit", "영업이익"),
            ("net_income", "당기순이익"),
            ("op_margin", "영업이익률"),
            ("net_margin", "순이익률"),
            ("debt_ratio", "부채비율"),
            ("roe", "ROE"),
            ("eps", "EPS"),
            ("bps", "BPS"),
            ("dps", "주당배당금"),
            ("retention_ratio", "유보율"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(8)
            key_label = QLabel(label)
            key_label.setStyleSheet("font-size: 8pt; color: #718096;")
            row.addWidget(key_label)
            row.addStretch(1)
            value_label = QLabel("–")
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_label.setStyleSheet("font-size: 8.5pt; color: #122033; font-weight: 700;")
            row.addWidget(value_label)
            finance_card.body.addLayout(row)
            self.finance_rows[key] = value_label
        finance_card.body.addStretch(1)
        bottom.addWidget(finance_card, 2)
        self.detail_body.addLayout(bottom)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        available = self.width() - 52 - self.left_card.width() - 14
        horizontal = available >= 780
        direction = QBoxLayout.LeftToRight if horizontal else QBoxLayout.TopToBottom
        if self.bottom_layout.direction() != direction:
            self.bottom_layout.setDirection(direction)
            self.bottom_layout.setStretch(0, 3 if horizontal else 0)
            self.bottom_layout.setStretch(1, 2 if horizontal else 0)
        self._relayout_metric_tiles(3 if available >= 540 else 2)

    # ------------------------------------------------------------------
    # Navigation / list
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        rows = [dict(row, in_watchlist=True) for row in self.db.watchlist_rows()]
        self._watch_rows = {row["code"]: row for row in rows}
        available: list[dict[str, Any]] = [dict(row) for row in rows]
        if self.current_code and self.current_code not in self._watch_rows:
            stock = self.db.get_stock(self.current_code)
            if stock:
                temporary = dict(stock)
                temporary["in_watchlist"] = False
                temporary["alias"] = None
                temporary["memo"] = None
                available.insert(0, temporary)

        codes = [row["code"] for row in available]
        if not self._checks_initialized:
            for code in codes[:4]:
                self._checked_codes.add(code)
            self._checks_initialized = True
        self._checked_codes &= set(codes)
        if self.current_code not in codes and codes:
            self.current_code = codes[0]

        signature = tuple(
            (
                row.get("code"),
                row.get("name"),
                row.get("alias"),
                row.get("close"),
                bool(row.get("in_watchlist")),
                row.get("change_pct"),
            )
            for row in available
        ) + ((self.current_code,))
        if signature != self._list_signature:
            self._rebuild_list(available)
            self._list_signature = signature

        if self.current_code:
            self.right_stack.setCurrentIndex(1)
            self._load_detail()
        else:
            self.right_stack.setCurrentIndex(0)
            self.chart.set_payload({"categories": [], "series": [], "mode": "return", "period": "recent"})

    def open_stock(self, code: str) -> None:
        if not code:
            return
        if not self.db.get_stock(code):
            self.notify("종목 정보를 찾을 수 없습니다.", "error")
            return
        self.current_code = code
        self._list_signature = None
        self.refresh()

    def _rebuild_list(self, rows: list[dict[str, Any]]) -> None:
        self._rebuilding_list = True
        self.stock_list.blockSignals(True)
        self.stock_list.clear()
        selected_item = None
        for row in rows:
            code = row["code"]
            name = row.get("name") or code
            alias = row.get("alias") or ""
            price = row.get("close")
            secondary = [code, f"{fmt_price(price)}원"]
            if alias:
                secondary.insert(0, name)
            if not row.get("in_watchlist"):
                secondary.append("관심종목 아님")
            primary = alias or name
            item = QListWidgetItem(f"{primary}\n{' · '.join(secondary)}")
            item.setData(Qt.UserRole, code)
            item.setSizeHint(QSize(0, 54))
            item.setToolTip(
                f"{name} ({code})\n체크하면 차트에서 비교할 수 있습니다.\n"
                "우클릭으로 관심종목을 편집할 수 있습니다."
            )
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if code in self._checked_codes else Qt.Unchecked)
            self.stock_list.addItem(item)
            if code == self.current_code:
                selected_item = item
        self.stock_list.blockSignals(False)
        self._rebuilding_list = False
        if selected_item is None and self.stock_list.count():
            selected_item = self.stock_list.item(0)
            self.current_code = selected_item.data(Qt.UserRole)
        if selected_item is not None:
            self.stock_list.setCurrentItem(selected_item)
        count = len(rows)
        self.list_hint.setText(f"총 {count}개 · 현재 종목 + 체크 종목 비교 (최대 8개)")

    def _on_current_changed(self, current: QListWidgetItem | None, previous) -> None:
        if self._rebuilding_list or current is None:
            return
        code = current.data(Qt.UserRole)
        if not code:
            return
        self.current_code = code
        self._load_detail()

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        if self._rebuilding_list:
            return
        code = item.data(Qt.UserRole)
        if not code:
            return
        checked = item.checkState() == Qt.Checked
        if checked:
            if len(self._checked_codes) >= 8 and code not in self._checked_codes:
                self._rebuilding_list = True
                item.setCheckState(Qt.Unchecked)
                self._rebuilding_list = False
                self.notify("차트 비교는 최대 8개 종목까지 가능합니다.", "info")
                return
            self._checked_codes.add(code)
        else:
            self._checked_codes.discard(code)
        self._update_chart()

    def _on_list_context(self, position: QPoint) -> None:
        item = self.stock_list.itemAt(position)
        if not item:
            return
        code = item.data(Qt.UserRole)
        extras = ()
        if code not in self._watch_rows:
            extras = (("관심종목에 추가", lambda: self.toggle_favorite(code)),)
        self.show_stock_context(self.stock_list, self.stock_list.viewport().mapToGlobal(position), code, extras)

    # ------------------------------------------------------------------
    # Detail rendering
    # ------------------------------------------------------------------
    def _load_detail(self) -> None:
        code = self.current_code
        if not code:
            return
        stock = self.db.get_stock(code)
        if not stock:
            self.right_stack.setCurrentIndex(0)
            return
        metrics = self.service.stock_metrics(code)
        is_new_stock = self._detail_code != code
        self._detail_code = code
        self._update_hero(stock, metrics)
        self._update_metrics(stock, metrics)
        self._update_financials(stock)
        self._update_chart()
        self._update_lookup(reset_date=is_new_stock)

    def _update_hero(self, stock: dict[str, Any], metrics: dict[str, Any]) -> None:
        name = stock.get("name") or stock.get("code")
        alias = (self._watch_rows.get(stock["code"]) or {}).get("alias")
        self.hero_name.setText(name)
        meta_parts = [stock.get("code") or ""]
        if alias:
            meta_parts.insert(0, f"별칭: {alias}")
        self.hero_meta.setText(" · ".join(part for part in meta_parts if part))
        self.hero_preferred_badge.setVisible(bool(stock.get("is_preferred")))
        self.hero_market_badge.setText("KOSPI")

        latest = metrics.get("latest") or stock.get("close")
        self.hero_price.setText(f"{fmt_price(latest)}원")
        change = metrics.get("change")
        change_pct = metrics.get("change_pct")
        if change is None:
            change = stock.get("change")
        if change_pct is None:
            change_pct = stock.get("change_pct")
        if change is not None or change_pct is not None:
            sign = "+" if (change or 0) > 0 else ""
            text = f"{sign}{int(change):,}원" if change is not None else ""
            if change_pct is not None:
                text += f"  {fmt_pct(change_pct, signed=True)}"
            self.hero_change.setText(text)
            tone = tone_class(change_pct if change_pct is not None else change)
            self.hero_change.setStyleSheet(
                "font-size: 10pt; font-weight: 700; color: "
                + ("#FF8C8C" if tone == "rise" else "#7CB2FF" if tone == "fall" else "#9DB3C7")
                + ";"
            )
        else:
            self.hero_change.setText(DASH)
        date_text = metrics.get("latest_date") or self.basis_date()
        self.hero_date.setText(f"{fmt_date(date_text)} 종가 기준")

        high = metrics.get("high") or stock.get("high52")
        low = metrics.get("low") or stock.get("low52")
        if high and low:
            self.hero_range.setText(f"최고 {fmt_price(high)}원  ·  최저 {fmt_price(low)}원")
        else:
            self.hero_range.setText("데이터 없음")

        is_favorite = self.db.is_in_watchlist(stock["code"])
        self.favorite_button.setText("관심종목" if is_favorite else "관심종목 추가")
        from ..icons import icon

        self.favorite_button.setIcon(
            icon("star_filled" if is_favorite else "star", "#C17A0A" if is_favorite else COLORS["teal_dark"], 16)
        )

    def _update_metrics(self, stock: dict[str, Any], metrics: dict[str, Any]) -> None:
        values = {
            "market_cap": fmt_market_cap(stock.get("market_cap")),
            "per": f"{stock.get('per'):,.2f}배" if stock.get("per") is not None else DASH,
            "pbr": f"{stock.get('pbr'):,.2f}배" if stock.get("pbr") is not None else DASH,
            "roe": fmt_pct(stock.get("roe")),
            "dividend_yield": fmt_pct(stock.get("dividend_yield")),
            "debt_ratio": fmt_pct(stock.get("debt_ratio")),
        }
        for key, text in values.items():
            self.metric_tiles[key].set_value(text)
        self.metric_tiles["market_cap"].note_label.setText(
            f"52주 최고 {fmt_price(metrics.get('high'))}원" if metrics.get("high") else "KOSPI"
        )

    def _update_financials(self, stock: dict[str, Any]) -> None:
        fiscal_year = stock.get("fiscal_year")
        self.finance_header.set_subtitle(
            f"{fiscal_year} 확정 연간 실적" if fiscal_year else "재무 데이터 없음"
        )
        self.finance_rows["fiscal"].setText(f"{fiscal_year}년" if fiscal_year else DASH)
        self.finance_rows["sales"].setText(fmt_eok(stock.get("sales")))
        self.finance_rows["operating_profit"].setText(fmt_eok(stock.get("operating_profit")))
        self.finance_rows["net_income"].setText(fmt_eok(stock.get("net_income")))
        for key in ("op_margin", "net_margin", "debt_ratio", "roe", "retention_ratio"):
            self.finance_rows[key].setText(fmt_pct(stock.get(key)))
        self.finance_rows["eps"].setText(fmt_price(stock.get("eps")) + "원" if stock.get("eps") is not None else DASH)
        self.finance_rows["bps"].setText(fmt_price(stock.get("bps")) + "원" if stock.get("bps") is not None else DASH)
        self.finance_rows["dps"].setText(fmt_price(stock.get("dps")) + "원" if stock.get("dps") is not None else DASH)
        self.finance_rows["net_income"].setStyleSheet(
            "font-size: 8.5pt; font-weight: 700; color: "
            + (COLORS["rise"] if (stock.get("net_income") or 0) > 0 else COLORS["fall"] if (stock.get("net_income") or 0) < 0 else COLORS["muted"])
            + ";"
        )

    def _chart_codes(self) -> list[str]:
        ordered: list[str] = []
        for index in range(self.stock_list.count()):
            item = self.stock_list.item(index)
            code = item.data(Qt.UserRole)
            if code in self._checked_codes and code not in ordered:
                ordered.append(code)
        if self.current_code and self.current_code not in ordered:
            ordered.insert(0, self.current_code)
        return ordered[:8]

    def _update_chart(self) -> None:
        codes = self._chart_codes()
        if not codes:
            self.chart.set_payload({"categories": [], "series": [], "mode": self.chart_mode, "period": self.chart_period})
            return
        payload = self.service.chart_payload(codes, period=self.chart_period, mode=self.chart_mode)
        self.chart.set_payload(payload)
        period_label = dict(self.PERIODS).get(self.chart_period, "전체기간")
        mode_label = dict(self.MODES).get(self.chart_mode, "주가")
        basis = self.basis_date()
        self.chart_header.set_subtitle(
            f"{len(codes)}개 종목 · {period_label} · {mode_label} · 기준 {basis}"
        )

    # ------------------------------------------------------------------
    # Close lookup
    # ------------------------------------------------------------------
    def _latest_price_date(self) -> str:
        bounds = self.db.price_bounds(self.current_code) if self.current_code else None
        return (bounds or {}).get("last_date") or self.basis_date()

    def _update_lookup(self, *, reset_date: bool = False) -> None:
        code = self.current_code
        if not code:
            return
        bounds = self.db.price_bounds(code)
        has_prices = bool(bounds)
        self.load_prices_button.setVisible(not has_prices)
        if reset_date:
            target = (bounds or {}).get("last_date") or self.basis_date()
            self._updating_lookup = True
            self.date_edit.setDate(QDate.fromString(target, "yyyy-MM-dd"))
            self._updating_lookup = False
        if not has_prices:
            self._clear_lookup("일별 종가 데이터가 없습니다", "데이터·설정에서 종가를 갱신하거나 위 버튼을 눌러주세요.")
            return
        self._lookup_current()

    def _set_latest_date(self) -> None:
        target = self._latest_price_date()
        self._updating_lookup = True
        self.date_edit.setDate(QDate.fromString(target, "yyyy-MM-dd"))
        self._updating_lookup = False
        self._lookup_current()

    def _on_date_changed(self, qdate: QDate) -> None:
        if self._updating_lookup or not self.current_code:
            return
        self._lookup_current()

    def _lookup_current(self) -> None:
        if not self.current_code:
            return
        target = self.date_edit.date().toString("yyyy-MM-dd")
        result = self.service.lookup_close(self.current_code, target)
        if not result:
            self._clear_lookup("조회 결과가 없습니다", "선택한 날짜의 종가 데이터를 찾을 수 없습니다.")
            return
        self._last_lookup = result
        selected = result["selected"]
        self.lookup_date_label.setText(date_korean(selected["date"]))
        exact = result.get("is_exact")
        target_date = result.get("requested_date")
        if exact:
            self.lookup_exact_label.setText("")
        elif target_date < (self.db.price_bounds(self.current_code) or {}).get("first_date", "9999"):
            self.lookup_exact_label.setText("데이터 시작일 기준")
        else:
            self.lookup_exact_label.setText("휴장일 · 직전 거래일 기준")
        self.lookup_price.setText(f"{fmt_price(selected.get('close'))}원")
        change = result.get("change")
        change_pct = result.get("change_pct")
        if change is None:
            self.lookup_change.setText(DASH)
            self.lookup_change.setStyleSheet("font-size: 9pt; color: #64748B; font-weight: 700;")
        else:
            tone = tone_class(change_pct if change_pct is not None else change)
            color = COLORS["rise"] if tone == "rise" else COLORS["fall"] if tone == "fall" else COLORS["muted"]
            sign = "+" if change > 0 else ""
            self.lookup_change.setText(f"{sign}{change:,}원  {fmt_pct(change_pct, signed=True)}")
            self.lookup_change.setStyleSheet(f"font-size: 9pt; color: {color}; font-weight: 700;")
        previous = result.get("previous") or {}
        stats = {
            "open": fmt_price(selected.get("open")) + "원" if selected.get("open") is not None else DASH,
            "high": fmt_price(selected.get("high")) + "원" if selected.get("high") is not None else DASH,
            "low": fmt_price(selected.get("low")) + "원" if selected.get("low") is not None else DASH,
            "previous": fmt_price(previous.get("close")) + "원" if previous.get("close") is not None else DASH,
            "volume": fmt_volume(selected.get("volume")),
            "change_pct": fmt_pct(change_pct, signed=True),
        }
        for key, text in stats.items():
            self.lookup_stats[key][1].setText(text)
        tone = tone_class(change_pct)
        self.lookup_stats["change_pct"][1].setStyleSheet(
            "font-size: 8.5pt; font-weight: 700; color: "
            + (COLORS["rise"] if tone == "rise" else COLORS["fall"] if tone == "fall" else COLORS["muted"])
            + ";"
        )
        for key, label in self.return_labels.items():
            value = result.get("returns", {}).get(key)
            label.setText(fmt_pct(value, signed=True))
            label_tone = tone_class(value)
            label.setStyleSheet(
                "font-size: 8pt; font-weight: 700; color: "
                + (COLORS["rise"] if label_tone == "rise" else COLORS["fall"] if label_tone == "fall" else "#64748B")
                + ";"
            )
        self._populate_price_table(result)

    def _clear_lookup(self, title: str, hint: str) -> None:
        self.lookup_date_label.setText(title)
        self.lookup_exact_label.setText("")
        self.lookup_price.setText(DASH)
        self.lookup_change.setText(DASH)
        self.lookup_hint.setText(hint)
        for _, value in self.lookup_stats.values():
            value.setText(DASH)
        for label in self.return_labels.values():
            label.setText(DASH)
            label.setStyleSheet("font-size: 8pt; font-weight: 700; color: #64748B;")
        self.price_table.setRowCount(0)

    def _populate_price_table(self, result: dict[str, Any]) -> None:
        window = result.get("window") or []
        if not window:
            self.price_table.setRowCount(0)
            return
        selected_date = result["selected"]["date"]
        dates = [row["date"] for row in window]
        selected_index = dates.index(selected_date) if selected_date in dates else 0
        start = max(0, selected_index - 3)
        end = min(len(window), start + 8)
        start = max(0, end - 8)
        rows = window[start:end]
        self.price_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            previous = window[start + row_index - 1] if start + row_index - 1 >= 0 else None
            change = None
            change_pct = None
            if previous and previous.get("close"):
                change = row["close"] - previous["close"]
                change_pct = change / previous["close"] * 100
            values = [
                row["date"],
                f"{fmt_price(row.get('close'))}",
                f"{change:+,}" if change is not None else DASH,
                fmt_pct(change_pct, signed=True),
                fmt_volume(row.get("volume")),
            ]
            selected = row["date"] == selected_date
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                alignment = Qt.AlignLeft | Qt.AlignVCenter if column == 0 else Qt.AlignRight | Qt.AlignVCenter
                item.setTextAlignment(alignment)
                if selected:
                    item.setBackground(QColor(COLORS["teal_soft"]))
                    font = QFont("Malgun Gothic", 8.5)
                    font.setWeight(QFont.DemiBold)
                    item.setFont(font)
                if column in {2, 3}:
                    tone = tone_class(change if column == 2 else change_pct)
                    item.setForeground(
                        QColor(
                            COLORS["rise"] if tone == "rise" else COLORS["fall"] if tone == "fall" else COLORS["muted"]
                        )
                    )
                self.price_table.setItem(row_index, column, item)
        self.price_table.setRowCount(len(rows))
        self.lookup_hint.setText("선택일 강조 · 전후 8거래일")
        selected_row = next((i for i, row in enumerate(rows) if row["date"] == selected_date), None)
        if selected_row is not None:
            self.price_table.scrollToItem(
                self.price_table.item(selected_row, 0),
                QAbstractItemView.PositionAtCenter,
            )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _toggle_current_favorite(self) -> None:
        if self.current_code:
            self.toggle_favorite(self.current_code)

    def _export_current(self) -> None:
        if self.current_code:
            self.export_stock_requested.emit(self.current_code)

    def _on_period_changed(self, key: str) -> None:
        self.chart_period = key
        self._update_chart()

    def _on_mode_changed(self, key: str) -> None:
        self.chart_mode = key
        self._update_chart()

    def on_watchlist_changed(self, code: str, added: bool) -> None:
        self._list_signature = None
        self.refresh()
