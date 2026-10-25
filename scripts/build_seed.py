# -*- coding: utf-8 -*-
"""Build the bundled seed database used on first launch.

Usage:
    py scripts/build_seed.py            # full KOSPI universe + fundamentals
    py scripts/build_seed.py --sample   # quick smoke test with 12 stocks

This script intentionally uses the same production service layer as the app.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kospi_insight.database import Database  # noqa: E402
from kospi_insight.paths import exports_dir  # noqa: E402
from kospi_insight.services import MarketService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true", help="only fetch a small subset")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--skip-prices", action="store_true")
    parser.add_argument("--db", default=str(ROOT / "assets" / "seed_kospi.db"))
    global_start = time.time()
    args = parser.parse_args()

    db_file = Path(args.db)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    os.environ["KOSPI_INSIGHT_DB"] = str(db_file)
    db = Database(db_file)
    service = MarketService(db)

    def progress(message: str, done: int, total: int) -> None:
        if done == total or done == 1 or done % 25 == 0:
            print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)

    print(f"DB: {db_file}", flush=True)
    print("1/3 KOSPI 종목 목록 수집...", flush=True)
    snapshot = service.refresh_snapshot(progress=progress)
    print(f"    완료: {snapshot['count']:,}개", flush=True)
    service.bootstrap()

    codes = db.all_active_codes()
    if args.sample:
        priority = ["005930", "000660", "105560", "055550", "005380", "000270", "068270", "035420", "051910", "006400", "012330", "066570"]
        codes = [code for code in priority if code in codes] or codes[:12]

    print(f"2/3 재무·밸류에이션 수집 ({len(codes):,}개)...", flush=True)
    result = service.refresh_fundamentals(codes, progress=progress, max_workers=args.workers)
    print(
        f"    완료: 성공 {result['updated']:,} / 실패 {result['failed']:,} "
        f"/ 전체 {result['total']:,}",
        flush=True,
    )
    if result.get("errors"):
        error_path = ROOT / "data" / "seed_errors.log"
        error_path.parent.mkdir(exist_ok=True)
        with error_path.open("w", encoding="utf-8") as handle:
            for code, error in sorted(result["errors"].items()):
                handle.write(f"{code}\t{error}\n")
        print(f"    오류 로그: {error_path}", flush=True)

    watch_codes = db.watchlist_codes()
    if not watch_codes:
        watch_codes = [code for code in ["005930", "000660", "105560", "055550"] if code in codes]
    if not args.skip_prices:
        print(f"3/3 관심종목 일별 종가 수집 ({len(watch_codes):,}개)...", flush=True)
        prices = service.refresh_prices(watch_codes, progress=progress)
        print(
            f"    완료: 성공 {prices['updated']:,} / 실패 {prices['failed']:,}, "
            f"{prices['rows']:,}행, 기준일 {prices['last_date']}",
            flush=True,
        )
    else:
        print("3/3 일별 종가 수집 건너뜀", flush=True)

    db.set_meta_many(
        {
            "seed_built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "seed_source": "NAVER Finance",
        }
    )
    counts = db.counts()
    print(f"DB 요약: {counts}", flush=True)
    print(f"총 소요: {time.time() - global_start:.1f}초", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
