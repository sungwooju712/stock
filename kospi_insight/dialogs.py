# -*- coding: utf-8 -*-
"""Application dialogs: add stock, about and small helpers."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .constants import (
    APP_NAME,
    APP_TAGLINE,
    CREATOR_NAME,
    DISCLAIMER,
    SOURCE_NAME,
    SOURCE_URL,
    VERSION,
)
from .formatters import fmt_pct, fmt_price, tone_class
from .icons import icon
from .services import MarketService
from .widgets import Badge, LogoWidget, SearchEdit, make_button, set_prop


class StockResultRow(QWidget):
    def __init__(self, row: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        name_box = QVBoxLayout()
        name_box.setContentsMargins(0, 0, 0, 0)
        name_box.setSpacing(2)
        name = QLabel(row.get("name") or "직접 코드 조회")
        name.setStyleSheet("font-size: 9.5pt; font-weight: 700; color: #122033;")
        name_box.addWidget(name)
        meta_text = row.get("code") or ""
        if row.get("_lookup"):
            meta_text = f"{row.get('code')} · 네이버에서 직접 조회"
        elif row.get("is_preferred"):
            meta_text = f"{meta_text} · 우선주"
        code = QLabel(meta_text)
        code.setStyleSheet("font-size: 7.5pt; color: #94A3B8;")
        name_box.addWidget(code)
        layout.addLayout(name_box, 1)

        right_box = QVBoxLayout()
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(2)
        price = QLabel(fmt_price(row.get("close")))
        price.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        price.setStyleSheet("font-size: 9.5pt; font-weight: 700; color: #122033;")
        right_box.addWidget(price)
        change_pct = row.get("change_pct")
        change = QLabel(fmt_pct(change_pct, signed=True))
        change.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        color = {
            "rise": "#E23D3D",
            "fall": "#2563EB",
            "flat": "#94A3B8",
        }.get(tone_class(change_pct))
        change.setStyleSheet(f"font-size: 8pt; font-weight: 700; color: {color};")
        right_box.addWidget(change)
        layout.addLayout(right_box, 0)

        if row.get("in_watchlist"):
            badge = Badge("관심종목", "teal")
            layout.addWidget(badge, 0, Qt.AlignVCenter)


class AddStockDialog(QDialog):
    def __init__(
        self,
        service: MarketService,
        parent: QWidget | None = None,
        initial_query: str = "",
    ):
        super().__init__(parent)
        self.service = service
        self.db = service.db
        self.selected_code: str | None = None
        self.selected_name: str = ""
        self.needs_lookup = False
        self.alias = ""
        self.memo = ""

        self.setWindowTitle("관심종목 추가")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setModal(True)
        self.setFixedWidth(560)
        self.setMinimumHeight(560)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 20)
        outer.setSpacing(14)

        heading = QHBoxLayout()
        heading.setSpacing(12)
        icon_label = QLabel()
        icon_label.setFixedSize(42, 42)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setPixmap(icon("plus", "#FFFFFF", 20).pixmap(20, 20))
        icon_label.setStyleSheet(
            "background: #0F9D8A; border-radius: 12px;"
        )
        heading.addWidget(icon_label)
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        title = QLabel("관심종목 추가")
        title.setStyleSheet("font-size: 14pt; font-weight: 800; color: #122033;")
        title_box.addWidget(title)
        subtitle = QLabel("종목명 또는 6자리 코드로 KOSPI 종목을 찾아보세요.")
        subtitle.setStyleSheet("font-size: 8.5pt; color: #64748B;")
        title_box.addWidget(subtitle)
        heading.addLayout(title_box, 1)
        outer.addLayout(heading)

        self.search = SearchEdit("종목명 또는 코드 검색 (예: 삼성전자, 005930)")
        self.search.setText(initial_query)
        self.search.textChanged.connect(self._schedule_search)
        self.search.returnPressed.connect(self._accept_selected)
        outer.addWidget(self.search)

        self.result_list = QListWidget()
        self.result_list.setObjectName("StockResultList")
        self.result_list.setMinimumHeight(270)
        self.result_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.result_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.result_list.itemDoubleClicked.connect(lambda _: self._accept_selected())
        outer.addWidget(self.result_list, 1)

        self.state_label = QLabel("")
        self.state_label.setStyleSheet("font-size: 8pt; color: #0A7C6D; font-weight: 600;")
        self.state_label.setVisible(False)
        outer.addWidget(self.state_label)

        form = QHBoxLayout()
        form.setSpacing(10)
        alias_box = QVBoxLayout()
        alias_box.setSpacing(4)
        alias_label = QLabel("별칭 (선택)")
        alias_label.setStyleSheet("font-size: 8pt; color: #718096; font-weight: 600;")
        alias_box.addWidget(alias_label)
        self.alias_edit = QLineEdit()
        self.alias_edit.setPlaceholderText("예: 장기 보유")
        self.alias_edit.setMaxLength(40)
        alias_box.addWidget(self.alias_edit)
        form.addLayout(alias_box, 1)

        memo_box = QVBoxLayout()
        memo_box.setSpacing(4)
        memo_label = QLabel("메모 (선택)")
        memo_label.setStyleSheet("font-size: 8pt; color: #718096; font-weight: 600;")
        memo_box.addWidget(memo_label)
        self.memo_edit = QLineEdit()
        self.memo_edit.setPlaceholderText("간단한 투자 메모")
        self.memo_edit.setMaxLength(120)
        memo_box.addWidget(self.memo_edit)
        form.addLayout(memo_box, 1)
        outer.addLayout(form)

        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = make_button("취소")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        self.add_button = make_button("관심종목에 추가", icon_name="star", icon_color="#FFFFFF", variant="primary")
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(self._accept_selected)
        footer.addWidget(self.add_button)
        outer.addLayout(footer)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._populate)
        self._populate()
        QTimer.singleShot(50, self.search.setFocus)

    # ------------------------------------------------------------------
    def _schedule_search(self) -> None:
        self._search_timer.start()

    def _populate(self) -> None:
        query = self.search.text().strip()
        rows = self.db.search_stocks(query, limit=60) if query else self.db.search_stocks("", limit=40)
        exact_codes = {row["code"] for row in rows}
        if query.isdigit() and len(query) == 6 and query.zfill(6) not in exact_codes:
            rows.append(
                {
                    "code": query.zfill(6),
                    "name": "직접 코드 조회",
                    "close": None,
                    "change_pct": None,
                    "in_watchlist": False,
                    "_lookup": True,
                }
            )
        self.result_list.blockSignals(True)
        self.result_list.clear()
        for row in rows:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, row.get("code"))
            item.setData(Qt.UserRole + 1, row.get("name"))
            item.setData(Qt.UserRole + 2, bool(row.get("in_watchlist")))
            item.setData(Qt.UserRole + 3, bool(row.get("_lookup")))
            item.setSizeHint(QSize(0, 58))
            self.result_list.addItem(item)
            self.result_list.setItemWidget(item, StockResultRow(row))
        self.result_list.blockSignals(False)
        if rows:
            self.result_list.setCurrentRow(0)
        else:
            self._set_state("검색 결과가 없습니다. 종목명이나 6자리 코드를 확인해 주세요.", warning=True)
        self._on_selection_changed()

    def _on_selection_changed(self) -> None:
        item = self.result_list.currentItem()
        if item is None:
            self.selected_code = None
            self.add_button.setEnabled(False)
            return
        self.selected_code = item.data(Qt.UserRole)
        self.selected_name = item.data(Qt.UserRole + 1) or ""
        self.needs_lookup = bool(item.data(Qt.UserRole + 3))
        already = bool(item.data(Qt.UserRole + 2))
        if already:
            self._set_state("이미 관심종목에 등록된 종목입니다.", warning=False)
        elif self.needs_lookup:
            self._set_state("DB에 없는 코드입니다. 추가 시 네이버에서 종목 정보를 조회합니다.", warning=False)
        else:
            self._set_state("")
        self.add_button.setEnabled(not already)
        self.add_button.setText("이미 등록됨" if already else "관심종목에 추가")

    def _set_state(self, text: str, *, warning: bool = False) -> None:
        self.state_label.setText(text)
        self.state_label.setVisible(bool(text))
        color = "#B45309" if warning else "#0A7C6D"
        self.state_label.setStyleSheet(f"font-size: 8pt; color: {color}; font-weight: 600;")

    def _accept_selected(self) -> None:
        if not self.selected_code or not self.add_button.isEnabled():
            return
        self.alias = self.alias_edit.text().strip()
        self.memo = self.memo_edit.text().strip()
        self.accept()


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} 정보")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setFixedWidth(560)
        self.setModal(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 26, 28, 24)
        outer.setSpacing(17)

        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(LogoWidget(52))
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        title = QLabel(APP_NAME)
        title.setStyleSheet("font-size: 18pt; font-weight: 800; color: #0B1F33;")
        title_box.addWidget(title)
        tagline = QLabel(f"{APP_TAGLINE} · v{VERSION}")
        tagline.setStyleSheet("font-size: 8.5pt; color: #718096;")
        title_box.addWidget(tagline)
        top.addLayout(title_box, 1)
        outer.addLayout(top)

        about_text = QLabel(
            "2023년부터 전일 종가까지의 KOSPI 종목을 분석하는 데스크톱 도구입니다. "
            "관심종목 비교 차트, 재무·밸류에이션 스크리너, 종목별 종가 조회와 "
            "엑셀 보고서 내보내기를 제공합니다."
        )
        about_text.setWordWrap(True)
        about_text.setStyleSheet(
            "background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; "
            "padding: 14px; color: #334155; line-height: 150%;"
        )
        outer.addWidget(about_text)

        for label, value in [
            ("만든 사람", CREATOR_NAME),
            ("데이터 출처", SOURCE_NAME),
            ("데이터 범위", "2023-01-02 ~ 전일 종가 (일별 종가 기준)"),
            ("재무 기준", "네이버증권 최근 확정 연간 재무제표"),
            ("저장 위치", "%LOCALAPPDATA%\\KOSPIInsight (설치형 실행 시)"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(12)
            key = QLabel(label)
            key.setFixedWidth(84)
            key.setStyleSheet("font-size: 8.5pt; color: #718096; font-weight: 700;")
            row.addWidget(key)
            value_label = QLabel(value)
            value_label.setWordWrap(True)
            value_label.setStyleSheet("font-size: 8.5pt; color: #334155;")
            row.addWidget(value_label, 1)
            outer.addLayout(row)

        source_button = make_button("네이버증권 열기", icon_name="external", variant="soft")
        source_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(SOURCE_URL)))
        disclaimer = QLabel(DISCLAIMER)
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet("font-size: 7.5pt; color: #94A3B8;")
        footer = QHBoxLayout()
        footer.addWidget(source_button)
        footer.addStretch(1)
        close = make_button("확인", variant="primary")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        outer.addWidget(disclaimer)
        outer.addLayout(footer)
