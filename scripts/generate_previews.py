# -*- coding: utf-8 -*-
"""Regenerate the sample Excel workbooks under ``exports/``."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kospi_insight.database import Database  # noqa: E402
from kospi_insight.excel_report import ExcelReport  # noqa: E402
from kospi_insight.paths import exports_dir  # noqa: E402
from kospi_insight.services import FilterCriteria, MarketService  # noqa: E402


def main() -> int:
    db = Database(ROOT / "data" / "kospi_insight.db")
    service = MarketService(db)
    service.bootstrap()
    report = ExcelReport(service)
    out = exports_dir()

    codes = db.watchlist_codes()
    if not codes:
        print("관심종목이 없어 보고서를 만들 수 없습니다.")
        return 1
    report_path = out / "preview_report.xlsx"
    report.export_watchlist(report_path, codes)
    print(f"보고서: {report_path} ({report_path.stat().st_size:,} bytes)")

    screen = service.screen(FilterCriteria(market_cap_min=1000))
    screen_path = out / "preview_screen.xlsx"
    report.export_screen(screen_path, screen)
    print(
        f"스크리닝: {screen_path} ({screen_path.stat().st_size:,} bytes, "
        f"{len(screen.rows):,}개 종목)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
