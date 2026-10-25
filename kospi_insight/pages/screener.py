# -*- coding: utf-8 -*-
"""Screener: fundamental/valuation filters and exportable result table."""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..constants import COLORS
from ..formatters import DASH, fmt_int, fmt_market_cap, fmt_pct, fmt_ratio, fmt_price
from ..services import FilterCriteria, ScreenResult
from ..tables import Column, StockTableView, star_column
from ..widgets import (
    Badge,
    Card,
    EmptyState,
    MetricTile,
    SearchEdit,
    SectionHeader,
    make_button,
)
from .base import PageBase


class NumberField(QWidget):
    def __init__(
        self,
        label: str,
        suffix: str,
        *,
        placeholder: str = "제한 없음",
        tooltip: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label_widget = QLabel(label)
        label_widget.setStyleSheet("font-size: 8pt; color: #718096; font-weight: 600;")
        layout.addWidget(label_widget)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setClearButtonEnabled(True)
        if tooltip:
            self.edit.setToolTip(tooltip)
        row.addWidget(self.edit, 1)
        suffix_label = QLabel(suffix)
        suffix_label.setStyleSheet("font-size: 8pt; color: #94A3B8; font-weight: 600;")
        suffix_label.setMinimumWidth(26)
        row.addWidget(suffix_label, 0)
        layout.addLayout(row)

    def set_text(self, text: str) -> None:
        self.edit.setText(text)

    def clear(self) -> None:
        self.edit.clear()

    def value(self, label: str) -> float | None:
        text = self.edit.text().strip().replace(",", "").replace(" ", "")
        if not text:
            return None
        try:
            value = float(text)
        except ValueError as exc:
            raise ValueError(f"{label} 값이 올바르지 않습니다.") from exc
        if not math.isfinite(value):
            raise ValueError(f"{label} 값이 올바르지 않습니다.")
        return value


class ScreenerPage(PageBase):
    export_screen_requested = Signal(object)

    PRESETS: dict[str, dict[str, Any]] = {
        "기본": {"market_cap": 1000},
        "저평가 가치주": {
            "market_cap": 1000,
            "per_max": 10,
            "debt_max": 150,
            "roe_min": 5,
            "net_income": True,
        },
        "고배당주": {
            "market_cap": 1000,
            "dividend_min": 3.0,
            "debt_max": 200,
            "net_income": True,
        },
        "우량 성장주": {
            "market_cap": 2000,
            "op_margin_min": 10,
            "roe_min": 10,
            "debt_max": 100,
        },
        "재무 건전성": {
            "market_cap": 1000,
            "debt_max": 80,
            "op_margin_min": 5,
            "roe_min": 5,
            "net_income": True,
        },
    }

    def __init__(self, service, parent: QWidget | None = None):
        super().__init__(service, parent)
        self._last_result: ScreenResult | None = None
        self._last_criteria: FilterCriteria | None = None
        self._fields: dict[str, NumberField] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 20, 26, 20)
        layout.setSpacing(12)

        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.stat_universe = MetricTile("KOSPI 유니버스", "–", note="보통주·우선주")
        self.stat_matched = MetricTile("조건 충족", "–", note="현재 필터 기준")
        self.stat_per = MetricTile("평균 PER", "–", note="통과 종목")
        self.stat_roe = MetricTile("평균 ROE", "–", note="통과 종목")
        for tile in (self.stat_universe, self.stat_matched, self.stat_per, self.stat_roe):
            tile.setMinimumHeight(72)
            stats.addWidget(tile, 1)
        layout.addLayout(stats)

        filter_card = Card(padding=(16, 13, 16, 13), spacing=9)
        filter_header = SectionHeader(
            "스크리닝 조건",
            "값을 비우면 해당 조건은 적용되지 않습니다 · 재무 지표는 최근 확정 연간 기준",
            trailing=self._make_reset_link(),
        )
        filter_card.body.addWidget(filter_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(9)
        definitions = [
            ("market_cap", "시가총액 최소", "억원", "예: 1,000 = 1,000억원"),
            ("debt_ratio", "부채비율 최대", "%", "예: 150 = 부채비율 150% 이하"),
            ("op_margin", "영업이익률 최소", "%", "최근 연간 영업이익률"),
            ("per_min", "PER 최소", "배", "주가수익비율 하한"),
            ("per_max", "PER 최대", "배", "주가수익비율 상한"),
            ("sales", "매출액 최소", "억원", "최근 연간 매출액"),
            ("roe", "ROE 최소", "%", "자기자본이익률"),
            ("dividend", "배당수익률 최소", "%", "현재가 기준 배당수익률"),
        ]
        for index, (key, label, suffix, tooltip) in enumerate(definitions):
            field = NumberField(label, suffix, tooltip=tooltip)
            field.edit.returnPressed.connect(self.apply_filters)
            self._fields[key] = field
            grid.addWidget(field, index // 4, index % 4)
        filter_card.body.addLayout(grid)

        presets_row = QHBoxLayout()
        presets_row.setSpacing(6)
        preset_label = QLabel("빠른 조건")
        preset_label.setStyleSheet("font-size: 8pt; color: #718096; font-weight: 700;")
        presets_row.addWidget(preset_label)
        for preset in self.PRESETS:
            button = make_button(preset, variant="chip")
            button.clicked.connect(lambda checked=False, name=preset: self.apply_preset(name))
            presets_row.addWidget(button)
        presets_row.addStretch(1)
        filter_card.body.addLayout(presets_row)

        option_row = QHBoxLayout()
        option_row.setSpacing(10)
        self.income_check = QCheckBox("당기순이익 흑자")
        self.share_type = QComboBox()
        self.share_type.addItem("전체 (보통+우선)", "all")
        self.share_type.addItem("보통주만", "common")
        self.share_type.addItem("우선주만", "preferred")
        self.share_type.setMinimumWidth(132)
        self.share_type.setToolTip("전체: 보통주와 우선주 · 보통주만 · 우선주만")
        self.financial_check = QCheckBox("부채비율 금융주 제외")
        self.financial_check.setChecked(True)
        self.financial_check.setToolTip(
            "부채비율 조건을 사용할 때 금융주(은행·보험·증권·금융지주)를 결과에서 제외합니다."
        )
        option_row.addWidget(self.income_check)
        option_row.addWidget(self.share_type)
        option_row.addWidget(self.financial_check)
        self.query_edit = SearchEdit("종목명·코드 검색")
        self.query_edit.setMaximumWidth(220)
        self.query_edit.returnPressed.connect(self.apply_filters)
        option_row.addWidget(self.query_edit, 1)
        self.filter_count = Badge("필터 1개", "teal")
        option_row.addWidget(self.filter_count)
        apply_button = make_button("조건 적용", icon_name="filter", icon_color="#FFFFFF", variant="primary")
        apply_button.clicked.connect(self.apply_filters)
        option_row.addWidget(apply_button)
        filter_card.body.addLayout(option_row)
        layout.addWidget(filter_card)

        results_card = Card(padding=(16, 13, 16, 6), spacing=7)
        self.result_actions = QWidget()
        action_layout = QHBoxLayout(self.result_actions)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)
        self.analyze_button = make_button("선택 종목 분석", icon_name="chart", variant="secondary")
        self.analyze_button.setEnabled(False)
        self.analyze_button.clicked.connect(self._analyze_selected)
        action_layout.addWidget(self.analyze_button)
        self.export_button = make_button("엑셀 저장", icon_name="download", variant="soft")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._export)
        action_layout.addWidget(self.export_button)
        self.result_header = SectionHeader("스크리닝 결과", "조건을 적용해 주세요", trailing=self.result_actions)
        results_card.body.addWidget(self.result_header)

        self.table = StockTableView(self._columns(), stretch_last=False, row_height=39)
        self.table.stock_activated.connect(self.analyze_requested.emit)
        self.table.star_toggle_requested.connect(self._toggle_star)
        self.table.context_menu_requested.connect(self._on_context)
        self.table.selectionModel().selectionChanged.connect(self._update_selection_actions)
        self.empty_state = EmptyState(
            "조건에 맞는 종목이 없습니다",
            "필터를 완화하거나 빠른 조건을 선택해 다시 검색해 보세요.",
            icon_name="filter",
            action=make_button("조건 초기화", icon_name="refresh", variant="secondary"),
        )
        self.empty_state.action.clicked.connect(self.reset_filters)
        self.result_stack = QStackedWidget()
        self.result_stack.addWidget(self.table)
        self.result_stack.addWidget(self.empty_state)
        results_card.body.addWidget(self.result_stack, 1)
        layout.addWidget(results_card, 1)

        self._apply_defaults()
        self._update_filter_count()

    # ------------------------------------------------------------------
    def _make_reset_link(self):
        button = make_button("초기화", variant="link")
        button.clicked.connect(self.reset_filters)
        return button

    def _columns(self) -> list[Column]:
        return [
            star_column(),
            Column(
                "rank", "순위", 44, Qt.AlignCenter,
                formatter=lambda row: str(row.get("rank", "")),
            ),
            Column("name", "종목명", 122, formatter=lambda row: row.get("name") or row.get("code")),
            Column("code", "코드", 68, formatter=lambda row: row.get("code") or ""),
            Column(
                "close", "현재가", 82, Qt.AlignRight | Qt.AlignVCenter,
                formatter=lambda row: fmt_price(row.get("close")),
            ),
            Column(
                "change_pct", "등락률", 67, Qt.AlignRight | Qt.AlignVCenter,
                formatter=lambda row: fmt_pct(row.get("change_pct"), signed=True),
            ),
            Column(
                "market_cap", "시가총액", 95, Qt.AlignRight | Qt.AlignVCenter,
                formatter=lambda row: fmt_market_cap(row.get("market_cap")),
            ),
            Column(
                "per", "PER", 62, Qt.AlignRight | Qt.AlignVCenter,
                formatter=lambda row: fmt_ratio(row.get("per")),
            ),
            Column(
                "pbr", "PBR", 62, Qt.AlignRight | Qt.AlignVCenter,
                formatter=lambda row: fmt_ratio(row.get("pbr")),
            ),
            Column(
                "roe", "ROE", 64, Qt.AlignRight | Qt.AlignVCenter,
                formatter=lambda row: fmt_pct(row.get("roe")),
            ),
            Column(
                "op_margin", "영업이익률", 76, Qt.AlignRight | Qt.AlignVCenter,
                formatter=lambda row: fmt_pct(row.get("op_margin")),
            ),
            Column(
                "debt_ratio", "부채비율", 70, Qt.AlignRight | Qt.AlignVCenter,
                formatter=lambda row: fmt_pct(row.get("debt_ratio")),
            ),
            Column(
                "dividend_yield", "배당수익률", 76, Qt.AlignRight | Qt.AlignVCenter,
                formatter=lambda row: fmt_pct(row.get("dividend_yield")),
            ),
            Column(
                "sales", "매출액", 74, Qt.AlignRight | Qt.AlignVCenter,
                formatter=lambda row: fmt_int(row.get("sales")),
                tooltip=lambda row: f"최근 연간 매출액 {fmt_int(row.get('sales'))}억원",
            ),
            Column(
                "net_income", "당기순이익", 82, Qt.AlignRight | Qt.AlignVCenter,
                formatter=lambda row: fmt_int(row.get("net_income")),
                color=lambda row: COLORS["rise"] if (row.get("net_income") or 0) > 0 else COLORS["fall"] if (row.get("net_income") or 0) < 0 else COLORS["muted"],
                tooltip=lambda row: f"최근 연간 당기순이익 {fmt_int(row.get('net_income'))}억원",
            ),
        ]

    # ------------------------------------------------------------------
    # Filter handling
    # ------------------------------------------------------------------
    def _apply_defaults(self) -> None:
        cap_default = self.db.get_meta("filter_market_cap_min", "1000") or "1000"
        try:
            cap_value = float(cap_default)
            self._fields["market_cap"].set_text(f"{cap_value:,.0f}")
        except ValueError:
            self._fields["market_cap"].set_text("1,000")
        include_preferred = self.db.get_meta("filter_include_preferred", "1") != "0"
        self._set_share_type("all" if include_preferred else "common")

    def _set_share_type(self, value: str) -> None:
        index = self.share_type.findData(value)
        self.share_type.setCurrentIndex(index if index >= 0 else 0)

    def _set_field(self, key: str, value: Any) -> None:
        if value is None:
            self._fields[key].clear()
        else:
            self._fields[key].set_text(f"{float(value):g}")

    def apply_preset(self, name: str) -> None:
        preset = self.PRESETS.get(name)
        if not preset:
            return
        for field in self._fields.values():
            field.clear()
        self.query_edit.clear()
        self.income_check.setChecked(bool(preset.get("net_income", False)))
        self._set_share_type("all" if preset.get("include_preferred", True) else "common")
        self.financial_check.setChecked(True)
        self._set_field("market_cap", preset.get("market_cap", 1000))
        self._set_field("debt_ratio", preset.get("debt_max"))
        self._set_field("op_margin", preset.get("op_margin_min"))
        self._set_field("per_min", preset.get("per_min"))
        self._set_field("per_max", preset.get("per_max"))
        self._set_field("sales", preset.get("sales_min"))
        self._set_field("roe", preset.get("roe_min"))
        self._set_field("dividend", preset.get("dividend_min"))
        self.apply_filters()

    def reset_filters(self) -> None:
        for field in self._fields.values():
            field.clear()
        self.query_edit.clear()
        self.income_check.setChecked(False)
        self.financial_check.setChecked(True)
        self._apply_defaults()
        self.apply_filters()

    def _criteria(self) -> FilterCriteria:
        values = {
            key: field.value(label)
            for key, field, label in [
                ("market_cap", self._fields["market_cap"], "시가총액 최소"),
                ("debt_ratio", self._fields["debt_ratio"], "부채비율 최대"),
                ("op_margin", self._fields["op_margin"], "영업이익률 최소"),
                ("per_min", self._fields["per_min"], "PER 최소"),
                ("per_max", self._fields["per_max"], "PER 최대"),
                ("sales", self._fields["sales"], "매출액 최소"),
                ("roe", self._fields["roe"], "ROE 최소"),
                ("dividend", self._fields["dividend"], "배당수익률 최소"),
            ]
        }
        if (
            values["per_min"] is not None
            and values["per_max"] is not None
            and values["per_min"] > values["per_max"]
        ):
            raise ValueError("PER 최소값이 최대값보다 클 수 없습니다.")
        share_type = self.share_type.currentData() or "all"
        return FilterCriteria(
            market_cap_min=values["market_cap"],
            debt_ratio_max=values["debt_ratio"],
            op_margin_min=values["op_margin"],
            per_min=values["per_min"],
            per_max=values["per_max"],
            sales_min=values["sales"],
            roe_min=values["roe"],
            dividend_yield_min=values["dividend"],
            net_income_positive=self.income_check.isChecked(),
            include_preferred=share_type != "common",
            preferred_only=share_type == "preferred",
            debt_ratio_exclude_financials=self.financial_check.isChecked(),
            query=self.query_edit.text().strip(),
        )

    def apply_filters(self) -> None:
        self._apply_filters(notify=True)

    def _apply_filters(self, *, notify: bool) -> None:
        try:
            criteria = self._criteria()
        except ValueError as exc:
            self.notify(str(exc), "error")
            return
        self._last_criteria = criteria
        result = self.service.screen(criteria)
        self._set_result(result)
        if notify:
            self.notify(
                f"조건에 맞는 종목 {len(result.rows):,}개를 찾았습니다."
                if result.rows
                else "조건에 맞는 종목이 없습니다.",
                "success" if result.rows else "info",
            )

    def _set_result(self, result: ScreenResult) -> None:
        self._last_result = result
        self.table.set_rows(result.rows)
        self.table.sort_by("market_cap", Qt.DescendingOrder)
        has_rows = bool(result.rows)
        self.result_stack.setCurrentIndex(0 if has_rows else 1)
        self.export_button.setEnabled(has_rows)
        self._update_selection_actions()
        self._update_filter_count()

        average_per = result.averages.get("per")
        average_roe = result.averages.get("roe")
        average_margin = result.averages.get("op_margin")
        self.result_header.set_subtitle(
            f"{len(result.rows):,}개 종목 · 평균 PER {fmt_ratio(average_per) if average_per is not None else DASH} · "
            f"평균 ROE {fmt_pct(average_roe) if average_roe is not None else DASH} · "
            f"평균 영업이익률 {fmt_pct(average_margin) if average_margin is not None else DASH}"
        )
        self.stat_universe.set_value(f"{result.total:,}", "KOSPI 전체")
        self.stat_matched.set_value(f"{len(result.rows):,}", "현재 조건 충족")
        self.stat_per.set_value(
            fmt_ratio(average_per) if average_per is not None else DASH,
            "통과 종목 평균",
        )
        self.stat_roe.set_value(
            fmt_pct(average_roe) if average_roe is not None else DASH,
            "통과 종목 평균",
        )

    def _update_filter_count(self) -> None:
        try:
            criteria = self._criteria()
        except ValueError:
            self.filter_count.setText("입력 확인")
            return
        active = criteria.active_count() + (1 if criteria.query else 0)
        self.filter_count.setText(f"필터 {active}개")
        self.filter_count.set_tone("teal" if active else "default")

    def _update_selection_actions(self, *args) -> None:
        self.analyze_button.setEnabled(self.table.current_row_data() is not None)

    def _analyze_selected(self) -> None:
        row = self.table.current_row_data()
        if row:
            self.analyze_requested.emit(row["code"])

    def _export(self) -> None:
        if self._last_result and self._last_result.rows:
            self.export_screen_requested.emit(self._last_result)

    def _toggle_star(self, code: str) -> None:
        self.toggle_favorite(code)
        self.table.update_watchlist_flags(set(self.db.watchlist_codes()))

    def _on_context(self, code: str, position) -> None:
        self.show_stock_context(self.table, position, code)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        if self._last_criteria is None:
            self._apply_filters(notify=False)
            return
        result = self.service.screen(self._last_criteria)
        self._set_result(result)

    def on_watchlist_changed(self, code: str, added: bool) -> None:
        self.table.update_watchlist_flags(set(self.db.watchlist_codes()))
