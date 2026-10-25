# -*- coding: utf-8 -*-
"""Data maintenance, preferences and application information."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..constants import DISCLAIMER, SOURCE_NAME, SOURCE_URL, VERSION
from ..dialogs import AboutDialog
from ..formatters import fmt_datetime, fmt_int
from ..paths import data_dir, exports_dir
from ..widgets import (
    Card,
    IconCircle,
    MetricTile,
    SectionHeader,
    make_button,
)
from .base import ScrollPage


class DataActionRow(QFrame):
    def __init__(
        self,
        icon_name: str,
        title: str,
        description: str,
        *,
        button_text: str = "갱신",
        accent: str = "#0F9D8A",
        soft: str = "#E7F8F4",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setProperty("card", "soft")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(13, 10, 13, 10)
        layout.setSpacing(11)
        layout.addWidget(IconCircle(icon_name, color=accent, soft=soft, size=36, icon_size=17))
        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 9pt; color: #122033; font-weight: 700;")
        text_box.addWidget(title_label)
        desc = QLabel(description)
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 8pt; color: #718096;")
        text_box.addWidget(desc)
        layout.addLayout(text_box, 1)
        self.button = make_button(button_text, variant="secondary")
        layout.addWidget(self.button)


class PathRow(QFrame):
    def __init__(self, label: str, path: str, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        name = QLabel(label)
        name.setStyleSheet("font-size: 8pt; color: #718096; font-weight: 600;")
        text_box.addWidget(name)
        path_label = QLabel(path)
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_label.setStyleSheet("font-size: 8pt; color: #334155;")
        text_box.addWidget(path_label)
        layout.addLayout(text_box, 1)
        self.button = make_button("폴더 열기", icon_name="folder", variant="secondary")
        self.button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(path)))
        layout.addWidget(self.button)


class SettingsPage(ScrollPage):
    refresh_requested = Signal(str)

    def __init__(self, service, parent: QWidget | None = None):
        super().__init__(service, parent=parent, spacing=15)

        # Data status ----------------------------------------------------
        status_card = Card(padding=(18, 15, 18, 15), spacing=10)
        self.status_header = SectionHeader(
            "데이터 현황",
            "네이버증권 공개 데이터를 로컬 SQLite 캐시에 저장합니다.",
            trailing=self._status_badge(),
        )
        status_card.body.addWidget(self.status_header)
        status_grid = QHBoxLayout()
        status_grid.setSpacing(9)
        self.tile_stocks = MetricTile("KOSPI 종목", "–", note="활성 종목")
        self.tile_fundamentals = MetricTile("재무 데이터", "–", note="최근 확정 연간")
        self.tile_prices = MetricTile("일별 종가", "–", note="2023년 이후")
        self.tile_basis = MetricTile("최근 종가일", "–", note="차트·조회 기준")
        for tile in (self.tile_stocks, self.tile_fundamentals, self.tile_prices, self.tile_basis):
            tile.setMinimumHeight(74)
            status_grid.addWidget(tile, 1)
        status_card.body.addLayout(status_grid)
        self.status_note = QLabel("")
        self.status_note.setStyleSheet("font-size: 8pt; color: #718096;")
        self.status_note.setWordWrap(True)
        status_card.body.addWidget(self.status_note)
        self.body.addWidget(status_card)

        # Refresh actions ------------------------------------------------
        refresh_card = Card(padding=(18, 15, 18, 15), spacing=9)
        refresh_card.body.addWidget(
            SectionHeader(
                "데이터 갱신",
                "갱신 중에는 진행 상황을 취소할 수 있습니다. 재무 전체 갱신은 수 분이 걸릴 수 있습니다.",
            )
        )
        actions = [
            (
                "snapshot",
                "trend",
                "시세 스냅샷",
                "KOSPI 전 종목의 현재가·등락률·시가총액을 새로 받아옵니다. (약 10~20초)",
                "시세 갱신",
                "#0F9D8A",
                "#E7F8F4",
            ),
            (
                "watchlist",
                "star",
                "관심종목 시세·일별 종가",
                "관심종목의 현재 시세와 2023년부터 전일 종가까지 다시 받아옵니다. (약 5~15초)",
                "관심종목 갱신",
                "#C17A0A",
                "#FFF5E4",
            ),
            (
                "fundamentals",
                "database",
                "재무·밸류에이션 갱신",
                "전 종목의 연간 재무제표, PER·PBR·배당수익률을 새로 받아옵니다. (약 3~5분)",
                "재무 갱신",
                "#2563EB",
                "#EFF6FF",
            ),
            (
                "all",
                "refresh",
                "전체 데이터 갱신",
                "시세 스냅샷 → 재무·밸류에이션 → 관심종목 종가 순서로 전체 데이터를 갱신합니다.",
                "전체 갱신",
                "#0B1F33",
                "#EAF2F8",
            ),
        ]
        for kind, icon_name, title, description, button_text, accent, soft in actions:
            row = DataActionRow(
                icon_name,
                title,
                description,
                button_text=button_text,
                accent=accent,
                soft=soft,
            )
            row.button.clicked.connect(lambda checked=False, target=kind: self.refresh_requested.emit(target))
            if kind == "all":
                row.button.setProperty("variant", "primary")
                row.button.style().unpolish(row.button)
                row.button.style().polish(row.button)
            refresh_card.body.addWidget(row)
        self.body.addWidget(refresh_card)

        # Preferences ----------------------------------------------------
        settings_card = Card(padding=(18, 15, 18, 15), spacing=12)
        settings_card.body.addWidget(SectionHeader("앱 설정", "스크리너 기본값과 시작 동작을 설정합니다."))
        form = QGridLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)

        self.cap_default = QDoubleSpinBox()
        self.cap_default.setRange(0, 1_000_000)
        self.cap_default.setDecimals(0)
        self.cap_default.setSingleStep(100)
        self.cap_default.setGroupSeparatorShown(True)
        self.cap_default.setSuffix(" 억원")
        self._add_form_field(form, 0, 0, "기본 시가총액 필터", self.cap_default, "스크리너 초기화 시 적용")

        self.chart_period = QComboBox()
        for key, label in [
            ("full", "전체기간"),
            ("annual", "연간"),
            ("monthly", "월간"),
            ("recent", "전일종가 (최근 30거래일)"),
        ]:
            self.chart_period.addItem(label, key)
        self._add_form_field(form, 0, 2, "기본 차트 기간", self.chart_period, "종목 분석 첫 화면")

        self.preferred_default = QCheckBox("우선주를 기본 포함")
        self._add_form_field(form, 1, 0, "종목 필터 기본값", self.preferred_default, "스크리너 초기화 시 적용")
        self.auto_refresh = QCheckBox("앱 시작 시 데이터 자동 갱신")
        self._add_form_field(form, 1, 2, "시작 동작", self.auto_refresh, "시세와 관심종목 종가를 갱신")
        settings_card.body.addLayout(form)

        footer = QHBoxLayout()
        hint = QLabel("설정은 이 컴퓨터에만 저장됩니다.")
        hint.setStyleSheet("font-size: 8pt; color: #94A3B8;")
        footer.addWidget(hint)
        footer.addStretch(1)
        save = make_button("설정 저장", icon_name="check", variant="primary")
        save.clicked.connect(self._save_settings)
        footer.addWidget(save)
        settings_card.body.addLayout(footer)
        self.body.addWidget(settings_card)

        # Files ----------------------------------------------------------
        files_card = Card(padding=(18, 15, 18, 15), spacing=10)
        files_card.body.addWidget(
            SectionHeader("파일 위치", "데이터베이스와 엑셀 내보내기 폴더를 바로 열 수 있습니다.")
        )
        self.data_path_row = PathRow("데이터·캐시 폴더", str(data_dir()))
        files_card.body.addWidget(self.data_path_row)
        self.export_path_row = PathRow("엑셀 내보내기 폴더", str(exports_dir()))
        files_card.body.addWidget(self.export_path_row)
        self.body.addWidget(files_card)

        # About ----------------------------------------------------------
        about_card = Card(padding=(18, 15, 18, 15), spacing=10)
        about_card.body.addWidget(SectionHeader("프로그램 정보", "데이터 출처와 버전을 확인합니다."))
        lines = QGridLayout()
        lines.setHorizontalSpacing(16)
        lines.setVerticalSpacing(6)
        for row, (label, value) in enumerate(
            [
                ("버전", f"KOSPI 인사이트 v{VERSION}"),
                ("데이터 출처", SOURCE_NAME),
                ("종가 범위", "2023-01-02 ~ 전일 종가"),
                ("라이선스", "개인·업무용 무료 사용 (데이터는 각 제공자 약관을 따름)"),
            ]
        ):
            key = QLabel(label)
            key.setStyleSheet("font-size: 8pt; color: #718096; font-weight: 700;")
            lines.addWidget(key, row, 0)
            value_label = QLabel(value)
            value_label.setStyleSheet("font-size: 8.5pt; color: #334155;")
            value_label.setWordWrap(True)
            lines.addWidget(value_label, row, 1)
        lines.setColumnStretch(1, 1)
        about_card.body.addLayout(lines)
        disclaimer = QLabel(DISCLAIMER)
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet("font-size: 7.5pt; color: #94A3B8;")
        about_card.body.addWidget(disclaimer)
        about_buttons = QHBoxLayout()
        about_buttons.addStretch(1)
        source_button = make_button("네이버증권", icon_name="external", variant="secondary")
        source_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(SOURCE_URL)))
        about_buttons.addWidget(source_button)
        about_button = make_button("프로그램 정보", icon_name="info", variant="soft")
        about_button.clicked.connect(lambda: AboutDialog(self).exec())
        about_buttons.addWidget(about_button)
        about_card.body.addLayout(about_buttons)
        self.body.addWidget(about_card)
        self.body.addStretch(1)

    # ------------------------------------------------------------------
    def _status_badge(self):
        from ..widgets import Badge

        return Badge("SQLite 캐시", "teal")

    @staticmethod
    def _add_form_field(
        layout: QGridLayout,
        row: int,
        column: int,
        label: str,
        widget: QWidget,
        hint: str,
    ) -> None:
        box = QVBoxLayout()
        box.setSpacing(4)
        label_widget = QLabel(label)
        label_widget.setStyleSheet("font-size: 8pt; color: #718096; font-weight: 700;")
        box.addWidget(label_widget)
        box.addWidget(widget)
        hint_widget = QLabel(hint)
        hint_widget.setStyleSheet("font-size: 7.5pt; color: #94A3B8;")
        box.addWidget(hint_widget)
        layout.addLayout(box, row, column, 1, 2)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        counts = self.db.counts()
        latest = self.db.latest_price_date() or "–"
        meta = self.db.get_meta_many(
            [
                "last_snapshot_at",
                "last_fundamentals_at",
                "last_prices_at",
                "data_source",
            ]
        )
        self.tile_stocks.set_value(f"{counts.get('stocks', 0):,}", f"관심종목 {counts.get('watchlist', 0):,}개")
        self.tile_fundamentals.set_value(
            f"{counts.get('fundamentals', 0):,}",
            f"최근 갱신 {fmt_datetime(meta.get('last_fundamentals_at'))}" if meta.get("last_fundamentals_at") else "갱신 이력 없음",
        )
        self.tile_prices.set_value(
            f"{counts.get('prices', 0):,}",
            f"{counts.get('price_stocks', 0):,}개 종목 · 일별 행",
        )
        self.tile_basis.set_value(latest, "차트·종가 조회 기준")
        self.status_note.setText(
            f"시세 스냅샷 {fmt_datetime(meta.get('last_snapshot_at'))} · "
            f"재무 {fmt_datetime(meta.get('last_fundamentals_at'))} · "
            f"관심종목 종가 {fmt_datetime(meta.get('last_prices_at'))} · "
            f"출처 {meta.get('data_source') or 'NAVER Finance'}"
        )
        self.data_path_row.button.setEnabled(data_dir().exists())
        self.export_path_row.button.setEnabled(exports_dir().exists())
        self._load_settings()

    def _load_settings(self) -> None:
        try:
            cap = float(self.db.get_meta("filter_market_cap_min", "1000") or "1000")
        except ValueError:
            cap = 1000.0
        self.cap_default.setValue(cap)
        self.preferred_default.setChecked(self.db.get_meta("filter_include_preferred", "1") != "0")
        self.auto_refresh.setChecked(self.db.get_meta("auto_refresh", "1") != "0")
        period = self.db.get_meta("chart_default_period", "full") or "full"
        index = self.chart_period.findData(period)
        self.chart_period.setCurrentIndex(index if index >= 0 else 0)

    def _save_settings(self) -> None:
        self.db.set_meta_many(
            {
                "filter_market_cap_min": f"{self.cap_default.value():g}",
                "filter_include_preferred": "1" if self.preferred_default.isChecked() else "0",
                "auto_refresh": "1" if self.auto_refresh.isChecked() else "0",
                "chart_default_period": self.chart_period.currentData() or "full",
            }
        )
        self.notify("설정을 저장했습니다.")
