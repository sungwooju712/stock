# -*- coding: utf-8 -*-
"""KOSPI 인사이트 desktop entry point."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QLocale, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from .constants import APP_NAME, APP_NAME_EN, VERSION
from .database import Database
from .icons import app_icon
from .main_window import MainWindow
from .paths import data_dir
from .services import MarketService
from .theme import apply_theme


def _configure_logging() -> Path:
    try:
        log_path = data_dir() / "kospi_insight.log"
        logging.basicConfig(
            filename=log_path,
            filemode="a",
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            encoding="utf-8",
        )
        return log_path
    except Exception:
        logging.basicConfig(level=logging.INFO)
        return Path("kospi_insight.log")


def _install_exception_hook(log_path: Path) -> None:
    def handle(exc_type, exc_value, exc_tb):
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.getLogger("kospi_insight").error("처리되지 않은 예외\n%s", details)
        try:
            box = QMessageBox()
            box.setWindowTitle("예상하지 못한 오류")
            box.setIcon(QMessageBox.Critical)
            box.setText("프로그램에서 예상하지 못한 오류가 발생했습니다.")
            box.setInformativeText(f"로그 파일: {log_path}")
            box.setDetailedText(details)
            box.exec()
        except Exception:
            pass

    sys.excepthook = handle


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("KOSPIInsight.Desktop.1")
    except Exception:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} ({APP_NAME_EN})")
    parser.add_argument("--db", help="개발용 데이터베이스 경로")
    parser.add_argument("--no-auto-refresh", action="store_true", help="시작 시 자동 갱신 비활성화")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.db:
        os.environ["KOSPI_INSIGHT_DB"] = str(Path(args.db).resolve())
    if args.no_auto_refresh:
        os.environ["KOSPI_INSIGHT_NO_AUTO_REFRESH"] = "1"

    _set_windows_app_id()
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QLocale.setDefault(QLocale(QLocale.Korean, QLocale.SouthKorea))

    app = QApplication(sys.argv[:1] if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME_EN)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("KOSPIInsight")
    app.setApplicationVersion(VERSION)
    app.setWindowIcon(app_icon())
    apply_theme(app)

    log_path = _configure_logging()
    _install_exception_hook(log_path)
    logging.getLogger("kospi_insight").info("앱 시작 v%s", VERSION)

    try:
        db = Database()
        service = MarketService(db)
        service.bootstrap()
        counts = db.counts()
        window = MainWindow(service)
        window.show()
        window.start()
        if counts.get("stocks", 0) == 0:
            QMessageBox.warning(
                window,
                "데이터 없음",
                "KOSPI 종목 데이터가 없습니다.\n데이터·설정 화면에서 '시세 갱신'을 실행해 주세요.",
            )
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("kospi_insight").exception("앱 초기화 실패")
        box = QMessageBox()
        box.setWindowTitle("시작 오류")
        box.setIcon(QMessageBox.Critical)
        box.setText("프로그램을 시작하지 못했습니다.")
        box.setInformativeText(str(exc))
        box.setDetailedText(traceback.format_exc())
        box.exec()
        return 1

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
