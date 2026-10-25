# -*- coding: utf-8 -*-
"""Developer UI smoke test and screenshot capture.

Runs against the real Windows Qt platform when a desktop session is available
(so Korean text is rendered correctly).  Pass ``--offscreen`` on headless
machines; geometry is still useful there, but glyphs will be boxes.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def pump(app, seconds: float = 0.15) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)
        app.processEvents()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offscreen", action="store_true", help="force Qt offscreen platform")
    args = parser.parse_args()
    if args.offscreen:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["KOSPI_INSIGHT_NO_AUTO_REFRESH"] = "1"

    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from kospi_insight.database import Database
    from kospi_insight.icons import app_icon
    from kospi_insight.main_window import MainWindow
    from kospi_insight.services import MarketService
    from kospi_insight.theme import apply_theme

    QSettings("KOSPIInsight", "KOSPI Insight").clear()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("KOSPI Insight")
    app.setWindowIcon(app_icon())
    apply_theme(app)

    db = Database(ROOT / "data" / "kospi_insight.db")
    service = MarketService(db)
    service.bootstrap()
    window = MainWindow(service)
    window.resize(1440, 920)
    window.show()
    window.start()
    pump(app, 0.4)

    pages = [
        ("dashboard", None),
        ("analysis", "005930"),
        ("screener", None),
        ("favorites", None),
        ("settings", None),
    ]
    for width, height, folder in ((1440, 920, ""), (1180, 760, "1180")):
        window.resize(width, height)
        pump(app, 0.3)
        out_dir = ROOT / "exports" / "ui"
        if folder:
            out_dir /= folder
        out_dir.mkdir(parents=True, exist_ok=True)
        for key, code in pages:
            if key == "analysis":
                window.navigate(key, code)
            else:
                window.navigate(key)
            pump(app, 0.35)
            for chart_page in (window.dashboard, window.analysis):
                if hasattr(chart_page, "chart"):
                    chart_page.chart._hover_index = None
                    chart_page.chart.update()
            pump(app, 0.05)
            path = out_dir / f"{key}.png"
            window.grab().save(str(path))
            page = window.pages[key]
            print(
                f"{width}x{height} {key}: window={window.width()}x{window.height()} "
                f"page={page.width()}x{page.height()} -> {path}"
            )
        if not folder:
            print(
                "screener rows:",
                len(window.screener._last_result.rows) if window.screener._last_result else 0,
            )
            print("watchlist:", window.db.watchlist_codes())
            print("chart series:", len(window.analysis.chart.payload.get("series") or []))
            print(
                "analysis current:",
                window.analysis.current_code,
                "lookup:",
                window.analysis.date_edit.date().toString("yyyy-MM-dd"),
            )
    pump(app, 0.1)
    window.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
