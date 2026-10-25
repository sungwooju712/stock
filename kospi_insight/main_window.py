# -*- coding: utf-8 -*-
"""Main application window: navigation, global search and data workflows."""

from __future__ import annotations

import logging
import os
import re
from datetime import date
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCompleter,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .constants import (
    APP_NAME,
    APP_TAGLINE,
    COLORS,
    CREATOR_NAME,
    DISCLAIMER,
    SOURCE_NAME,
    VERSION,
)
from .database import Database
from .dialogs import AddStockDialog
from .excel_report import ExcelReport
from .formatters import fmt_date, fmt_int, safe_filename
from .icons import app_icon, icon, two_state_icon
from .pages.analysis import AnalysisPage
from .pages.dashboard import DashboardPage
from .pages.favorites import FavoritesPage
from .pages.screener import ScreenerPage
from .pages.settings import SettingsPage
from .paths import exports_dir
from .services import MarketService, ScreenResult
from .widgets import Badge, LogoWidget, SearchEdit, Toast, make_button, make_icon_button, set_prop
from .workers import TaskManager


LOGGER = logging.getLogger("kospi_insight")


PAGE_META = {
    "dashboard": ("대시보드", "KOSPI 시장과 내 관심종목을 한눈에"),
    "analysis": ("종목 분석", "종가 추이 · 밸류에이션 · 종목별 종가 조회"),
    "screener": ("스크리너", "재무와 밸류에이션 조건으로 종목 발굴"),
    "favorites": ("즐겨찾기 관리", "종목 · 별칭 · 메모를 정리하고 엑셀로 내보내기"),
    "settings": ("데이터 · 설정", "데이터 갱신, 기본값, 내보내기 관리"),
}

NAV_GROUPS = [
    (
        "분석",
        [
            ("dashboard", "대시보드", "dashboard"),
            ("analysis", "종목 분석", "chart"),
            ("screener", "스크리너", "filter"),
        ],
    ),
    ("내 종목", [("favorites", "즐겨찾기 관리", "star")]),
    ("시스템", [("settings", "데이터 · 설정", "settings")]),
]


class MainWindow(QMainWindow):
    def __init__(self, service: MarketService, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self.db: Database = service.db
        self._current_page = "dashboard"
        self._auto_started = False
        self._settings = QSettings("KOSPIInsight", "KOSPI Insight")

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.setMinimumSize(1180, 760)
        self.resize(1440, 920)
        self._center_window()

        self.nav_buttons: dict[str, QPushButton] = {}
        self._nav_keys: list[str] = []
        self._build_ui()
        self._build_pages()

        self.task_manager = TaskManager(self)
        self.task_manager.busy_changed.connect(self._on_busy_changed)
        self.task_manager.message.connect(self._notify)
        self.task_manager.error.connect(self._on_task_error)

        self.toast = Toast(self)
        self._connect_signals()

        self._update_data_badge()
        self._restore_geometry()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _center_window(self) -> None:
        screen = QApplication.primaryScreen()
        if not screen:
            return
        available = screen.availableGeometry()
        width = min(1440, max(1180, available.width() - 80))
        height = min(920, max(760, available.height() - 80))
        self.resize(width, height)
        self.move(
            available.x() + max(0, (available.width() - width) // 2),
            available.y() + max(0, (available.height() - height) // 2),
        )

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_sidebar())

        content = QFrame()
        content.setObjectName("ContentRoot")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self._build_topbar())

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(238)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 22, 18, 18)
        layout.setSpacing(0)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        brand.addWidget(LogoWidget(42))
        brand_box = QVBoxLayout()
        brand_box.setSpacing(1)
        brand_title = QLabel(APP_NAME)
        brand_title.setObjectName("BrandTitle")
        brand_box.addWidget(brand_title)
        brand_sub = QLabel("KOSPI INSIGHT")
        brand_sub.setObjectName("BrandSub")
        brand_box.addWidget(brand_sub)
        brand.addLayout(brand_box, 1)
        layout.addLayout(brand)
        layout.addSpacing(24)

        group = QButtonGroup(self)
        group.setExclusive(True)
        group.idClicked.connect(self._on_nav_clicked)
        self._nav_group = group
        nav_id = 0
        for group_index, (group_label, items) in enumerate(NAV_GROUPS):
            if group_index:
                layout.addSpacing(13)
            section = QLabel(group_label.upper() if group_label == "시스템" else group_label)
            section.setProperty("role", "sidebarLabel")
            layout.addWidget(section)
            layout.addSpacing(5)
            for key, label, icon_name in items:
                button = QPushButton(label)
                button.setCheckable(True)
                button.setProperty("nav", True)
                button.setIcon(two_state_icon(icon_name, "#8FA9C1", "#FFFFFF", 19))
                button.setIconSize(QSize(19, 19))
                button.setCursor(Qt.PointingHandCursor)
                button.setMinimumHeight(41)
                button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                group.addButton(button, nav_id)
                nav_id += 1
                self._nav_keys.append(key)
                self.nav_buttons[key] = button
                button.setProperty("navKey", key)
                layout.addWidget(button)
        layout.addStretch(1)

        data_card = QFrame()
        data_card.setObjectName("SidebarCard")
        data_layout = QVBoxLayout(data_card)
        data_layout.setContentsMargins(12, 10, 12, 10)
        data_layout.setSpacing(2)
        data_label = QLabel("데이터 기준일")
        data_label.setStyleSheet("font-size: 7pt; color: #8FA9C1; font-weight: 700;")
        data_layout.addWidget(data_label)
        self.sidebar_date = QLabel("–")
        self.sidebar_date.setStyleSheet("font-size: 12pt; color: #FFFFFF; font-weight: 800;")
        data_layout.addWidget(self.sidebar_date)
        data_source = QLabel("NAVER Finance / KRX")
        data_source.setStyleSheet("font-size: 7pt; color: #8FA9C1;")
        data_layout.addWidget(data_source)
        layout.addWidget(data_card)
        layout.addSpacing(9)

        self.sidebar_creator = QLabel(f"만든 사람 · {CREATOR_NAME}")
        self.sidebar_creator.setStyleSheet(
            "font-size: 7.2pt; color: #A9C4DA; font-weight: 700;"
        )
        layout.addWidget(self.sidebar_creator)
        layout.addSpacing(5)

        footer = QLabel(
            f"v{VERSION} · 정보 제공용\n{DISCLAIMER}"
        )
        footer.setWordWrap(True)
        footer.setStyleSheet("font-size: 6.8pt; color: #6F89A1; line-height: 140%;")
        layout.addWidget(footer)
        return sidebar

    def _build_topbar(self) -> QWidget:
        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(72)
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(26, 10, 24, 10)
        layout.setSpacing(11)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self.top_title = QLabel(PAGE_META["dashboard"][0])
        self.top_title.setObjectName("TopTitle")
        title_box.addWidget(self.top_title)
        self.top_subtitle = QLabel(PAGE_META["dashboard"][1])
        self.top_subtitle.setObjectName("TopSub")
        title_box.addWidget(self.top_subtitle)
        layout.addLayout(title_box)
        layout.addStretch(1)

        self.search = SearchEdit("종목명·코드 검색  (Ctrl+K)")
        self.search.setMinimumWidth(220)
        self.search.setMaximumWidth(300)
        self.search.setClearButtonEnabled(True)
        self._completer = QCompleter(self._completer_labels(), self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setMaxVisibleItems(10)
        self.search.setCompleter(self._completer)
        self._completer.activated.connect(self._on_search_activated)
        self.search.returnPressed.connect(self._run_global_search)
        layout.addWidget(self.search)

        self.data_badge = Badge("기준일 –", "teal")
        layout.addWidget(self.data_badge, 0, Qt.AlignVCenter)

        self.add_button = make_button(
            "종목 추가", icon_name="plus", icon_color="#FFFFFF", variant="primary"
        )
        self.add_button.clicked.connect(lambda: self.add_stock_dialog("global"))
        layout.addWidget(self.add_button)

        self.refresh_button = make_button("새로고침", icon_name="refresh", variant="secondary")
        self.refresh_button.setToolTip("관심종목 시세와 일별 종가를 새로고침합니다. 전체 갱신은 데이터·설정에서 실행하세요.")
        self.refresh_button.clicked.connect(self.quick_watchlist_refresh)
        layout.addWidget(self.refresh_button)
        return topbar

    def _completer_labels(self) -> list[str]:
        try:
            rows = self.db.search_stocks("", limit=1000)
        except Exception:
            return []
        return [f"{row.get('name')} ({row.get('code')})" for row in rows if row.get("name")]

    def _build_pages(self) -> None:
        self.dashboard = DashboardPage(self.service)
        self.analysis = AnalysisPage(self.service)
        self.screener = ScreenerPage(self.service)
        self.favorites = FavoritesPage(self.service)
        self.settings = SettingsPage(self.service)
        self.pages = {
            "dashboard": self.dashboard,
            "analysis": self.analysis,
            "screener": self.screener,
            "favorites": self.favorites,
            "settings": self.settings,
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        period = self.db.get_meta("chart_default_period", "full") or "full"
        if period not in {"full", "annual", "monthly", "recent"}:
            period = "full"
        self.analysis.chart_period = period
        self.analysis.period_control.set_current(period)

    def _connect_signals(self) -> None:
        for page in self.pages.values():
            page.message_requested.connect(self._notify)

        self.dashboard.navigate_requested.connect(self.navigate)
        self.dashboard.analyze_requested.connect(self.open_analysis)
        self.dashboard.add_stock_requested.connect(lambda: self.add_stock_dialog("dashboard"))
        self.dashboard.export_requested.connect(self.export_watchlist)
        self.dashboard.watchlist_changed.connect(self._after_watchlist_change)
        self.dashboard.refresh_requested.connect(self.quick_watchlist_refresh)

        self.analysis.analyze_requested.connect(self.open_analysis)
        self.analysis.add_stock_requested.connect(lambda: self.add_stock_dialog("analysis"))
        self.analysis.export_stock_requested.connect(self.export_single_stock)
        self.analysis.load_prices_requested.connect(self._load_prices_for_code)
        self.analysis.watchlist_changed.connect(self._after_watchlist_change)

        self.screener.analyze_requested.connect(self.open_analysis)
        self.screener.export_screen_requested.connect(self.export_screen)
        self.screener.watchlist_changed.connect(self._after_watchlist_change)

        self.favorites.analyze_requested.connect(self.open_analysis)
        self.favorites.add_stock_requested.connect(lambda: self.add_stock_dialog("favorites"))
        self.favorites.export_requested.connect(self.export_watchlist)
        self.favorites.watchlist_changed.connect(self._after_watchlist_change)

        self.settings.refresh_requested.connect(self.refresh_data)

        shortcuts = [
            ("Ctrl+K", self._focus_search),
            ("Ctrl+R", self.quick_watchlist_refresh),
            ("Ctrl+E", self.export_watchlist),
        ]
        for sequence, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)
        for index, key in enumerate(["dashboard", "analysis", "screener", "favorites", "settings"], start=1):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{index}"), self)
            shortcut.activated.connect(lambda target=key: self.navigate(target))

    # ------------------------------------------------------------------
    # Navigation / startup
    # ------------------------------------------------------------------
    def start(self) -> None:
        self.navigate("dashboard")
        QTimer.singleShot(900, self._maybe_auto_refresh)

    def navigate(self, key: str, code: str | None = None) -> None:
        if key not in self.pages:
            return
        page = self.pages[key]
        if key == "analysis" and code:
            self.analysis.open_stock(code)
        self.stack.setCurrentWidget(page)
        self._current_page = key
        title, subtitle = PAGE_META[key]
        self.top_title.setText(title)
        self.top_subtitle.setText(subtitle)
        for nav_key, button in self.nav_buttons.items():
            button.setChecked(nav_key == key)
        if not (key == "analysis" and code):
            page.refresh()
        if key == "analysis" and code:
            self.analysis.refresh()
        self._update_data_badge()

    def _on_nav_clicked(self, index: int) -> None:
        if 0 <= index < len(self._nav_keys):
            self.navigate(self._nav_keys[index])

    def _focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    # ------------------------------------------------------------------
    # Global search
    # ------------------------------------------------------------------
    @staticmethod
    def _code_from_completion(text: str) -> str | None:
        match = re.search(r"\((\d{6})\)\s*$", text or "")
        return match.group(1) if match else None

    def _on_search_activated(self, text: str) -> None:
        code = self._code_from_completion(text)
        if code:
            self.search.clear()
            self.open_analysis(code)

    def _run_global_search(self) -> None:
        text = self.search.text().strip()
        if not text:
            return
        code = self._code_from_completion(text)
        if code:
            self.search.clear()
            self.open_analysis(code)
            return
        rows = self.db.search_stocks(text, limit=10)
        if not rows:
            self._notify("검색 결과가 없습니다. 종목명이나 6자리 코드를 확인해 주세요.", "info")
            return
        exact = [row for row in rows if row.get("name") == text or row.get("code") == text.zfill(6)]
        target = exact[0] if exact else rows[0]
        self.search.clear()
        self.open_analysis(target["code"])

    def open_analysis(self, code: str) -> None:
        if not self.db.get_stock(code):
            self._notify("종목 정보를 찾을 수 없습니다.", "error")
            return
        self.navigate("analysis", code)
        if not self.db.price_bounds(code):
            self._ensure_prices([code], quiet=True)

    # ------------------------------------------------------------------
    # Watchlist changes and price history
    # ------------------------------------------------------------------
    def _after_watchlist_change(self, code: str) -> None:
        added = self.db.is_in_watchlist(code)
        for page in self.pages.values():
            page.on_watchlist_changed(code, added)
        if added and not self.db.price_bounds(code):
            self._ensure_prices([code], quiet=True)

    def _ensure_prices(self, codes: list[str], *, quiet: bool = True) -> bool:
        missing = [code for code in codes if code and not self.db.price_bounds(code)]
        if not missing:
            return False

        def work(progress, cancel):
            return self.service.refresh_prices(missing, progress=progress, cancel_event=cancel)

        def success(result):
            self._refresh_all_pages()
            self._update_data_badge()
            self._notify(
                f"일별 종가 {result.get('rows', 0):,}행을 불러왔습니다. "
                f"성공 {result.get('updated', 0):,}개 · 실패 {result.get('failed', 0):,}개"
            )

        return self.task_manager.run(
            "일별 종가 불러오기",
            "2023년부터 전일 종가까지 저장해 차트와 종가 조회에 사용합니다.",
            work,
            on_success=success,
            cancellable=True,
            show_dialog=not quiet,
        )

    def _load_prices_for_code(self, code: str) -> None:
        if code:
            self._ensure_prices([code], quiet=False)

    # ------------------------------------------------------------------
    # Add stock
    # ------------------------------------------------------------------
    def add_stock_dialog(self, origin: str = "global") -> None:
        if self.task_manager.busy:
            self._notify("데이터 작업이 끝난 뒤 다시 시도해 주세요.", "info")
            return
        dialog = AddStockDialog(self.service, self)
        if dialog.exec() != AddStockDialog.Accepted:
            return
        code = dialog.selected_code
        if not code:
            return
        alias, memo = dialog.alias, dialog.memo
        stock = self.db.get_stock(code)
        if dialog.needs_lookup or not stock:
            def work(progress, cancel):
                progress("네이버에서 종목 정보를 조회하는 중입니다…", 0, 0)
                return self.service.ensure_stock(code)

            def success(result):
                if not result:
                    self._notify(f"코드 {code}에 해당하는 KOSPI 종목을 찾지 못했습니다.", "error")
                    return
                self._finish_add(code, alias, memo, origin)

            self.task_manager.run(
                "종목 정보 조회",
                f"코드 {code}의 종목 정보를 네이버증권에서 확인합니다.",
                work,
                on_success=success,
                cancellable=False,
            )
            return
        self._finish_add(code, alias, memo, origin)

    def _finish_add(self, code: str, alias: str, memo: str, origin: str) -> None:
        stock = self.db.get_stock(code) or {}
        name = stock.get("name") or code
        if self.db.is_in_watchlist(code):
            self._notify(f"{name}은(는) 이미 관심종목에 있습니다.", "info")
            if origin == "analysis":
                self.analysis.open_stock(code)
            return
        if not self.service.add_watchlist(code, alias=alias, memo=memo):
            self._notify("관심종목에 추가하지 못했습니다.", "error")
            return
        self._notify(f"{name}을(를) 관심종목에 추가했습니다.")
        self._after_watchlist_change(code)
        if origin == "analysis":
            self.analysis.open_stock(code)

    # ------------------------------------------------------------------
    # Refresh workflows
    # ------------------------------------------------------------------
    def quick_watchlist_refresh(self) -> None:
        if self.task_manager.busy:
            self._notify("이미 데이터 작업이 진행 중입니다.", "info")
            return
        if not self.db.watchlist_codes():
            self._notify("관심종목이 없습니다. 먼저 종목을 추가해 주세요.", "info")
            return

        def work(progress, cancel):
            return self.service.refresh_watchlist_quotes(progress=progress, include_prices=True)

        def success(result):
            self._refresh_all_pages()
            self._update_data_badge()
            prices = result.get("prices") or {}
            self._notify(
                f"관심종목 {result.get('updated', 0):,}개 시세와 "
                f"일별 종가 {prices.get('rows', 0):,}행을 갱신했습니다."
            )

        self.task_manager.run(
            "관심종목 새로고침",
            "관심종목의 현재 시세와 2023년 이후 일별 종가를 갱신합니다.",
            work,
            on_success=success,
            cancellable=False,
        )

    def refresh_data(self, kind: str) -> None:
        if self.task_manager.busy:
            self._notify("이미 데이터 작업이 진행 중입니다.", "info")
            return
        titles = {
            "snapshot": "시세 스냅샷 갱신",
            "watchlist": "관심종목 시세·종가 갱신",
            "fundamentals": "재무·밸류에이션 갱신",
            "all": "전체 데이터 갱신",
        }
        descriptions = {
            "snapshot": "KOSPI 전 종목의 현재가·등락률·시가총액을 갱신합니다.",
            "watchlist": "관심종목의 현재 시세와 2023년 이후 일별 종가를 갱신합니다.",
            "fundamentals": "전 종목의 연간 재무제표와 PER·PBR·배당수익률을 갱신합니다. 수 분이 걸릴 수 있습니다.",
            "all": "시세 → 재무 → 관심종목 종가 순서로 전체 데이터를 갱신합니다. 수 분이 걸릴 수 있습니다.",
        }
        if kind not in titles:
            return
        if kind in {"fundamentals", "all"}:
            answer = QMessageBox.question(
                self,
                titles[kind],
                f"{titles[kind]}을(를) 시작할까요?\n\n{descriptions[kind]}\n\n"
                "진행 상황 창에서 취소할 수 있으며, 일부 데이터는 갱신된 상태로 남을 수 있습니다.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        def work(progress, cancel):
            result = {}
            if kind in {"snapshot", "all"}:
                result["snapshot"] = self.service.refresh_snapshot(progress=progress)
                if cancel.is_set():
                    return result
            if kind in {"fundamentals", "all"}:
                result["fundamentals"] = self.service.refresh_fundamentals(
                    progress=progress, cancel_event=cancel
                )
                if cancel.is_set():
                    return result
            if kind in {"watchlist", "all"}:
                result["watchlist"] = self.service.refresh_watchlist_quotes(
                    progress=progress, include_prices=True
                )
            return result

        def success(result):
            self._refresh_all_pages()
            self._update_data_badge()
            self._notify(self._refresh_summary(kind, result), "success")

        self.task_manager.run(
            titles[kind],
            descriptions[kind],
            work,
            on_success=success,
            cancellable=kind in {"fundamentals", "all"},
        )

    @staticmethod
    def _refresh_summary(kind: str, result: dict) -> str:
        if kind == "snapshot":
            snapshot = result.get("snapshot") or {}
            return f"시세 스냅샷 {snapshot.get('count', 0):,}개 종목을 갱신했습니다."
        if kind == "watchlist":
            watchlist = result.get("watchlist") or {}
            prices = watchlist.get("prices") or {}
            return (
                f"관심종목 {watchlist.get('updated', 0):,}개 시세와 "
                f"일별 종가 {prices.get('rows', 0):,}행을 갱신했습니다."
            )
        if kind == "fundamentals":
            fundamentals = result.get("fundamentals") or {}
            return (
                f"재무·밸류에이션 {fundamentals.get('updated', 0):,}개를 갱신했습니다. "
                f"실패 {fundamentals.get('failed', 0):,}개"
            )
        snapshot = result.get("snapshot") or {}
        fundamentals = result.get("fundamentals") or {}
        watchlist = result.get("watchlist") or {}
        prices = watchlist.get("prices") or {}
        return (
            f"전체 갱신 완료 · 시세 {snapshot.get('count', 0):,}개 · "
            f"재무 {fundamentals.get('updated', 0):,}개 · "
            f"관심종목 종가 {prices.get('rows', 0):,}행"
        )

    def _refresh_all_pages(self) -> None:
        for page in self.pages.values():
            try:
                page.refresh()
            except Exception:
                LOGGER.exception("페이지 새로고침 실패: %s", page.__class__.__name__)

    # ------------------------------------------------------------------
    # Startup auto refresh
    # ------------------------------------------------------------------
    def _maybe_auto_refresh(self) -> None:
        if self._auto_started:
            return
        self._auto_started = True
        if os.environ.get("KOSPI_INSIGHT_NO_AUTO_REFRESH"):
            return
        if (self.db.get_meta("auto_refresh", "1") or "1") == "0":
            return
        today = date.today().isoformat()
        meta = self.db.get_meta_many(["last_snapshot_date", "last_watchlist_refresh_at"])
        snapshot_stale = (meta.get("last_snapshot_date") or "") != today
        watch_stale = (meta.get("last_watchlist_refresh_at") or "")[:10] != today
        if not snapshot_stale and not watch_stale:
            return
        if not self.db.watchlist_codes() and not snapshot_stale:
            return

        def work(progress, cancel):
            result = {}
            if snapshot_stale:
                result["snapshot"] = self.service.refresh_snapshot(progress=progress)
            if watch_stale and self.db.watchlist_codes() and not cancel.is_set():
                result["watchlist"] = self.service.refresh_watchlist_quotes(
                    progress=progress, include_prices=True
                )
            return result

        def success(result):
            self._refresh_all_pages()
            self._update_data_badge()
            self._notify("최신 시세와 관심종목 종가로 자동 갱신했습니다.")

        self.task_manager.run(
            "데이터 자동 갱신",
            "최신 시세를 확인하고 관심종목 종가를 갱신합니다.",
            work,
            on_success=success,
            cancellable=False,
            show_dialog=False,
        )

    # ------------------------------------------------------------------
    # Excel export
    # ------------------------------------------------------------------
    def _choose_save_path(self, suggested: str) -> Path | None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "엑셀 파일 저장",
            str(exports_dir() / suggested),
            "Excel 통합 문서 (*.xlsx)",
        )
        if not path:
            return None
        target = Path(path)
        if target.suffix.lower() != ".xlsx":
            target = target.with_suffix(".xlsx")
        return target

    def _run_export(self, path: Path, function, label: str) -> None:
        def work(progress, cancel):
            progress(f"{label} 파일을 생성하는 중입니다…", 0, 0)
            return function(path)

        def success(result):
            self._show_export_success(Path(result))

        self.task_manager.run(
            "엑셀 보고서 생성",
            f"{label} 파일과 차트를 생성합니다.",
            work,
            on_success=success,
            cancellable=False,
        )

    def export_watchlist(self) -> None:
        codes = self.db.watchlist_codes()
        if not codes:
            self._notify("내보낼 관심종목이 없습니다. 먼저 종목을 추가해 주세요.", "info")
            return
        filename = safe_filename(f"KOSPI_인사이트_보고서_{date.today():%Y%m%d}") + ".xlsx"
        target = self._choose_save_path(filename)
        if not target:
            return
        report = ExcelReport(self.service)
        self._run_export(
            target,
            lambda path: report.export_watchlist(path, codes),
            f"관심종목 {len(codes)}개 보고서",
        )

    def export_single_stock(self, code: str) -> None:
        stock = self.db.get_stock(code) or {}
        name = stock.get("name") or code
        filename = safe_filename(f"KOSPI_인사이트_{name}_{date.today():%Y%m%d}") + ".xlsx"
        target = self._choose_save_path(filename)
        if not target:
            return
        report = ExcelReport(self.service)
        self._run_export(
            target,
            lambda path: report.export_watchlist(path, [code]),
            f"{name} 종목 보고서",
        )

    def export_screen(self, result: ScreenResult) -> None:
        if not result.rows:
            self._notify("내보낼 스크리닝 결과가 없습니다.", "info")
            return
        filename = safe_filename(f"KOSPI_스크리닝_{date.today():%Y%m%d}") + ".xlsx"
        target = self._choose_save_path(filename)
        if not target:
            return
        report = ExcelReport(self.service)
        self._run_export(
            target,
            lambda path: report.export_screen(path, result),
            f"스크리닝 {len(result.rows):,}개 결과",
        )

    def _show_export_success(self, path: Path) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("엑셀 저장 완료")
        box.setIcon(QMessageBox.Information)
        box.setText("엑셀 파일을 저장했습니다.")
        box.setInformativeText(str(path))
        open_button = box.addButton("엑셀 열기", QMessageBox.ActionRole)
        folder_button = box.addButton("폴더 열기", QMessageBox.ActionRole)
        box.addButton("닫기", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is open_button:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        elif box.clickedButton() is folder_button:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    # ------------------------------------------------------------------
    # Status, notifications and errors
    # ------------------------------------------------------------------
    def _update_data_badge(self) -> None:
        if getattr(self, "task_manager", None) and self.task_manager.busy:
            return
        basis = self.db.latest_price_date()
        if not basis:
            basis = (self.db.get_meta("last_snapshot_date") or date.today().isoformat())
        self.data_badge.setText(f"기준일 {fmt_date(basis)}")
        self.data_badge.set_tone("teal")
        self.sidebar_date.setText(fmt_date(basis))

    def _on_busy_changed(self, busy: bool) -> None:
        self.add_button.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        if busy:
            self.data_badge.setText("작업 진행 중…")
            self.data_badge.set_tone("amber")
        else:
            self._update_data_badge()

    def _notify(self, message: str, kind: str = "success") -> None:
        self.toast.show_message(message, kind)
        self.toast.reposition()

    def _on_task_error(self, title: str, summary: str, details: str, quiet: bool) -> None:
        LOGGER.error("%s: %s\n%s", title, summary, details)
        if quiet:
            self._notify(f"{title} 실패: {summary}", "error")
            return
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Warning)
        box.setText(summary)
        box.setInformativeText(
            "네트워크 상태를 확인한 뒤 다시 시도해 주세요. 계속 실패하면 데이터·설정에서 개별 갱신을 실행해 보세요."
        )
        box.setDetailedText(details)
        box.exec()

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------
    def _restore_geometry(self) -> None:
        geometry = self._settings.value("window_geometry")
        if geometry:
            try:
                self.restoreGeometry(geometry)
            except Exception:
                pass

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "toast"):
            self.toast.reposition()

    def closeEvent(self, event) -> None:
        if self.task_manager.busy:
            answer = QMessageBox.question(
                self,
                "작업 진행 중",
                "데이터 작업이 아직 진행 중입니다. 작업을 취소하고 종료할까요?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.task_manager.cancel_current()
        self._settings.setValue("window_geometry", self.saveGeometry())
        super().closeEvent(event)
