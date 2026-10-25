# -*- coding: utf-8 -*-
"""Market data orchestration, screening and chart/report aggregations."""

from __future__ import annotations

import bisect
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Any, Callable, Iterable, Sequence

from .constants import CHART_COLORS, DATA_START_DATE, DEFAULT_WATCHLIST
from .database import Database
from .naver import (
    NaverClient,
    NaverError,
    is_preferred_name,
    merge_fundamentals,
    parse_number,
    today_previous_close_cutoff,
)

ProgressCallback = Callable[[str, int, int], None]


@dataclass
class FilterCriteria:
    """Screening conditions.  ``None`` means the condition is disabled."""

    market_cap_min: float | None = 1000.0  # 억원
    debt_ratio_max: float | None = None
    op_margin_min: float | None = None
    per_min: float | None = None
    per_max: float | None = None
    sales_min: float | None = None
    roe_min: float | None = None
    dividend_yield_min: float | None = None
    net_income_positive: bool = False
    include_preferred: bool = True
    query: str = ""

    def active_count(self) -> int:
        checks = [
            self.market_cap_min is not None,
            self.debt_ratio_max is not None,
            self.op_margin_min is not None,
            self.per_min is not None or self.per_max is not None,
            self.sales_min is not None,
            self.roe_min is not None,
            self.dividend_yield_min is not None,
            self.net_income_positive,
            not self.include_preferred,
        ]
        return sum(checks)


@dataclass
class ScreenResult:
    rows: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0
    fundamental_ready: int = 0
    averages: dict[str, float | None] = field(default_factory=dict)
    criteria: FilterCriteria | None = None


class MarketService:
    def __init__(self, db: Database):
        self.db = db

    # ------------------------------------------------------------------
    # Bootstrap and refresh operations
    # ------------------------------------------------------------------
    def bootstrap(self) -> None:
        self.db.ensure_default_watchlist(DEFAULT_WATCHLIST)

    def refresh_snapshot(self, progress: ProgressCallback | None = None) -> dict[str, Any]:
        client = NaverClient(timeout=18, retries=2)
        try:
            stocks = client.fetch_kospi_stocks(progress=progress)
        finally:
            client.close()
        if not stocks:
            raise NaverError("KOSPI 종목 목록을 받지 못했습니다.")
        self.db.replace_stock_snapshot(stocks)
        now = datetime.now().isoformat(timespec="seconds")
        self.db.set_meta_many(
            {
                "last_snapshot_at": now,
                "last_snapshot_date": date.today().isoformat(),
                "snapshot_count": len(stocks),
                "data_source": "NAVER Finance",
            }
        )
        return {"count": len(stocks), "updated_at": now}

    def refresh_fundamentals(
        self,
        codes: Sequence[str] | None = None,
        *,
        progress: ProgressCallback | None = None,
        max_workers: int = 5,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        if codes is None:
            codes = self.db.all_active_codes()
        codes = list(dict.fromkeys(code for code in codes if code))
        stocks = {}
        for code in codes:
            row = self.db.get_stock(code)
            if row:
                stocks[code] = row
        total = len(stocks)
        if not total:
            return {"updated": 0, "failed": 0, "total": 0}

        def work(code: str, price: int | None) -> tuple[str, dict[str, Any] | None, str | None]:
            annual = None
            integration = None
            errors: list[str] = []
            client = NaverClient(timeout=16, retries=2)
            try:
                try:
                    annual = client.fetch_annual_financials(code)
                except NaverError as exc:
                    errors.append(str(exc))
                try:
                    integration = client.fetch_integration(code)
                except NaverError as exc:
                    errors.append(str(exc))
                if annual is None and integration is None:
                    return code, None, "; ".join(errors) or "재무 데이터 없음"
                merged = merge_fundamentals(annual, integration, price)
                merged["code"] = code
                if annual:
                    merged["fiscal_year"] = annual.get("fiscal_year")
                    merged["fiscal_period"] = annual.get("fiscal_period")
                return code, merged, None
            finally:
                client.close()

        updated = 0
        failed = 0
        completed = 0
        errors: dict[str, str] = {}
        executor = ThreadPoolExecutor(max_workers=max(1, min(max_workers, 8)))
        futures = {
            executor.submit(work, code, row.get("close")): code for code, row in stocks.items()
        }
        try:
            for future in as_completed(futures):
                if cancel_event is not None and cancel_event.is_set():
                    for pending in futures:
                        pending.cancel()
                    break
                code = futures[future]
                completed += 1
                try:
                    result_code, merged, error = future.result()
                    if merged:
                        self.db.save_fundamentals(merged)
                        self.db.update_quote(
                            result_code,
                            high52=merged.get("high52"),
                            low52=merged.get("low52"),
                            foreign_rate=merged.get("foreign_rate"),
                        )
                        updated += 1
                    else:
                        failed += 1
                        if error:
                            errors[result_code] = error
                except Exception as exc:  # network/parse surprises must not stop the batch
                    failed += 1
                    errors[code] = str(exc)
                if progress:
                    progress(
                        f"재무·밸류에이션 갱신 중 ({completed:,}/{total:,})",
                        completed,
                        total,
                    )
        finally:
            executor.shutdown(wait=not (cancel_event and cancel_event.is_set()), cancel_futures=True)
        now = datetime.now().isoformat(timespec="seconds")
        self.db.set_meta_many(
            {
                "last_fundamentals_at": now,
                "last_fundamentals_ok": updated,
                "last_fundamentals_failed": failed,
            }
        )
        return {
            "updated": updated,
            "failed": failed,
            "total": total,
            "errors": errors,
            "updated_at": now,
        }

    def refresh_prices(
        self,
        codes: Sequence[str],
        *,
        progress: ProgressCallback | None = None,
        max_workers: int = 4,
        cancel_event: threading.Event | None = None,
        start: date = DATA_START_DATE,
        end: date | None = None,
    ) -> dict[str, Any]:
        end = end or today_previous_close_cutoff()
        codes = list(dict.fromkeys(code for code in codes if code))
        total = len(codes)
        if not total:
            return {"updated": 0, "failed": 0, "total": 0, "rows": 0}
        if end < start:
            return {"updated": 0, "failed": 0, "total": total, "rows": 0}

        def work(code: str) -> tuple[str, list[dict[str, Any]], str | None]:
            client = NaverClient(timeout=18, retries=2)
            try:
                rows = client.fetch_daily_prices(code, start, end)
                return code, rows, None
            except Exception as exc:
                return code, [], str(exc)
            finally:
                client.close()

        updated = 0
        failed = 0
        row_count = 0
        completed = 0
        errors: dict[str, str] = {}
        executor = ThreadPoolExecutor(max_workers=max(1, min(max_workers, 6)))
        futures = {executor.submit(work, code): code for code in codes}
        try:
            for future in as_completed(futures):
                if cancel_event is not None and cancel_event.is_set():
                    for pending in futures:
                        pending.cancel()
                    break
                code = futures[future]
                completed += 1
                try:
                    result_code, rows, error = future.result()
                    if rows:
                        inserted = self.db.upsert_prices(result_code, rows)
                        row_count += inserted
                        updated += 1
                    else:
                        failed += 1
                        if error:
                            errors[result_code] = error
                except Exception as exc:
                    failed += 1
                    errors[code] = str(exc)
                if progress:
                    progress(
                        f"일별 종가 갱신 중 ({completed:,}/{total:,})",
                        completed,
                        total,
                    )
        finally:
            executor.shutdown(wait=not (cancel_event and cancel_event.is_set()), cancel_futures=True)
        now = datetime.now().isoformat(timespec="seconds")
        self.db.set_meta("last_prices_at", now)
        if not codes:
            last_date = None
        else:
            rows = self.db.price_series_many(codes)
            last_date = max((item["date"] for series in rows.values() for item in series), default=None)
        return {
            "updated": updated,
            "failed": failed,
            "total": total,
            "rows": row_count,
            "errors": errors,
            "last_date": last_date,
            "updated_at": now,
        }

    def refresh_watchlist_quotes(
        self,
        *,
        progress: ProgressCallback | None = None,
        include_prices: bool = False,
    ) -> dict[str, Any]:
        codes = self.db.watchlist_codes()
        if not codes:
            return {"updated": 0, "total": 0}
        total = len(codes)
        completed = 0
        updated = 0

        def work(code: str) -> tuple[str, dict[str, Any] | None, str | None]:
            client = NaverClient(timeout=15, retries=2)
            try:
                data = client.fetch_integration(code)
                return code, data, None
            except Exception as exc:
                return code, None, str(exc)
            finally:
                client.close()

        with ThreadPoolExecutor(max_workers=min(4, total)) as executor:
            futures = {executor.submit(work, code): code for code in codes}
            for future in as_completed(futures):
                code = futures[future]
                completed += 1
                try:
                    _, data, _ = future.result()
                    if data:
                        self.db.update_quote(
                            code,
                            close=int(data["close"]) if data.get("close") else None,
                            change=int(data["change"]) if data.get("change") is not None else None,
                            change_pct=data.get("change_pct"),
                            volume=int(data["volume"]) if data.get("volume") else None,
                            market_cap=data.get("market_value"),
                            high52=int(data["high52"]) if data.get("high52") else None,
                            low52=int(data["low52"]) if data.get("low52") else None,
                            foreign_rate=data.get("foreign_rate"),
                        )
                        updated += 1
                except Exception:
                    pass
                if progress:
                    progress(f"관심종목 시세 갱신 중 ({completed}/{total})", completed, total)

        price_result = None
        if include_prices:
            price_result = self.refresh_prices(codes, progress=progress)
        now = datetime.now().isoformat(timespec="seconds")
        self.db.set_meta("last_watchlist_refresh_at", now)
        return {"updated": updated, "total": total, "prices": price_result, "updated_at": now}

    def ensure_stock(self, code_or_query: str) -> dict[str, Any] | None:
        """Find a stock locally, or validate a 6-digit code with NAVER."""
        token = (code_or_query or "").strip()
        if not token:
            return None
        local = self.db.search_stocks(token, limit=10)
        if local:
            exact = [row for row in local if row["code"] == token or row["name"] == token]
            if exact:
                return exact[0]
        if not token.isdigit():
            return local[0] if local else None
        code = token.zfill(6)
        existing = self.db.get_stock(code)
        if existing:
            return existing
        client = NaverClient(timeout=15, retries=1)
        try:
            integration = client.fetch_integration(code)
        except NaverError:
            return None
        finally:
            client.close()
        if not integration or not integration.get("name"):
            return None
        name = integration.get("name") or code
        stock = {
            "code": code,
            "name": name,
            "market": "KOSPI",
            "is_preferred": int(is_preferred_name(name)),
            "close": int(integration["close"]) if integration.get("close") else None,
            "change": int(integration["change"]) if integration.get("change") is not None else None,
            "change_pct": integration.get("change_pct"),
            "volume": int(integration["volume"]) if integration.get("volume") else None,
            "market_cap": integration.get("market_value"),
            "high52": int(integration["high52"]) if integration.get("high52") else None,
            "low52": int(integration["low52"]) if integration.get("low52") else None,
            "active": 1,
            "source_url": f"https://finance.naver.com/item/main.naver?code={code}",
        }
        self.db.upsert_stock(stock)
        try:
            valuation = merge_fundamentals(None, integration, stock.get("close"))
            valuation["code"] = code
            valuation["source"] = "NAVER Finance"
            self.db.save_fundamentals(valuation)
        except Exception:
            pass
        return self.db.get_stock(code)

    def add_watchlist(self, code: str, alias: str = "", memo: str = "") -> bool:
        if not self.db.get_stock(code):
            self.ensure_stock(code)
        return self.db.add_to_watchlist(code, alias=alias, memo=memo)

    # ------------------------------------------------------------------
    # Screening
    # ------------------------------------------------------------------
    def screen(self, criteria: FilterCriteria) -> ScreenResult:
        all_rows = self.db.candidate_rows()
        rows: list[dict[str, Any]] = []
        query = criteria.query.strip().lower()
        fundamental_ready = 0
        for row in all_rows:
            if row.get("per") is not None or row.get("sales") is not None:
                fundamental_ready += 1
            if not criteria.include_preferred and row.get("is_preferred"):
                continue
            if query and query not in (row.get("name") or "").lower() and query not in row["code"]:
                continue
            market_cap_eok = (row.get("market_cap") or 0) / 100_000_000
            if criteria.market_cap_min is not None and market_cap_eok < criteria.market_cap_min:
                continue
            if criteria.debt_ratio_max is not None:
                value = row.get("debt_ratio")
                if value is None or value > criteria.debt_ratio_max:
                    continue
            if criteria.op_margin_min is not None:
                value = row.get("op_margin")
                if value is None or value < criteria.op_margin_min:
                    continue
            per = row.get("per")
            if criteria.per_min is not None or criteria.per_max is not None:
                if per is None:
                    continue
                if criteria.per_min is not None and per < criteria.per_min:
                    continue
                if criteria.per_max is not None and per > criteria.per_max:
                    continue
            if criteria.sales_min is not None:
                value = row.get("sales")
                if value is None or value < criteria.sales_min:
                    continue
            if criteria.roe_min is not None:
                value = row.get("roe")
                if value is None or value < criteria.roe_min:
                    continue
            if criteria.dividend_yield_min is not None:
                value = row.get("dividend_yield")
                if value is None or value < criteria.dividend_yield_min:
                    continue
            if criteria.net_income_positive:
                value = row.get("net_income")
                if value is None or value <= 0:
                    continue
            rows.append(row)

        rows.sort(key=lambda item: (item.get("market_cap") or 0), reverse=True)
        for index, row in enumerate(rows, start=1):
            row["rank"] = index
            row["market_cap_eok"] = (row.get("market_cap") or 0) / 100_000_000
        def avg(key: str) -> float | None:
            values = [row[key] for row in rows if row.get(key) is not None]
            return sum(values) / len(values) if values else None

        return ScreenResult(
            rows=rows,
            total=len(all_rows),
            fundamental_ready=fundamental_ready,
            averages={
                "per": avg("per"),
                "roe": avg("roe"),
                "op_margin": avg("op_margin"),
                "debt_ratio": avg("debt_ratio"),
                "dividend_yield": avg("dividend_yield"),
            },
            criteria=replace(criteria),
        )

    # ------------------------------------------------------------------
    # Chart data / performance
    # ------------------------------------------------------------------
    def chart_payload(
        self,
        codes: Sequence[str],
        period: str = "full",
        mode: str = "price",
    ) -> dict[str, Any]:
        """Build aligned multi-stock chart data.

        period: full | annual | monthly | recent (전일종가 기준 최근 30거래일)
        mode: price | return
        """
        codes = list(dict.fromkeys(code for code in codes if code))
        if not codes:
            return {"categories": [], "series": [], "mode": mode, "period": period, "unit": "원"}
        start = DATA_START_DATE.isoformat()
        price_map = self.db.price_series_many(codes, start=start)
        stocks = {code: self.db.get_stock(code) for code in codes}
        categories: list[str] = []
        aligned: dict[str, list[float | None]] = {}

        if period == "annual":
            years: set[int] = set()
            annual_values: dict[str, dict[int, float]] = {}
            for code in codes:
                per_year: dict[int, float] = {}
                for row in price_map.get(code, []):
                    year = int(row["date"][:4])
                    per_year[year] = float(row["close"])
                annual_values[code] = per_year
                years.update(per_year)
            if years:
                category_years = list(range(min(years), max(years) + 1))
            else:
                category_years = []
            categories = [str(year) for year in category_years]
            for code in codes:
                aligned[code] = [annual_values[code].get(year) for year in category_years]
        elif period == "monthly":
            months: set[str] = set()
            monthly_values: dict[str, dict[str, float]] = {}
            for code in codes:
                per_month: dict[str, float] = {}
                for row in price_map.get(code, []):
                    per_month[row["date"][:7]] = float(row["close"])
                monthly_values[code] = per_month
                months.update(per_month)
            categories = sorted(months)
            for code in codes:
                aligned[code] = [monthly_values[code].get(month) for month in categories]
        else:
            all_dates = sorted(
                {row["date"] for code in codes for row in price_map.get(code, [])}
            )
            if period == "recent":
                all_dates = all_dates[-30:]
            categories = all_dates
            for code in codes:
                lookup = {row["date"]: float(row["close"]) for row in price_map.get(code, [])}
                aligned[code] = [lookup.get(day) for day in categories]

        series: list[dict[str, Any]] = []
        for index, code in enumerate(codes):
            values = aligned.get(code, [])
            stock = stocks.get(code) or {}
            base = next((value for value in values if value is not None and value > 0), None)
            if mode == "return":
                values = [
                    ((value / base) - 1) * 100 if value is not None and base else None
                    for value in values
                ]
            series.append(
                {
                    "code": code,
                    "name": stock.get("name") or code,
                    "values": values,
                    "color": CHART_COLORS[index % len(CHART_COLORS)],
                    "latest": next((value for value in reversed(values) if value is not None), None),
                }
            )
        return {
            "categories": categories,
            "series": series,
            "mode": mode,
            "period": period,
            "unit": "%" if mode == "return" else "원",
        }

    def stock_metrics(self, code: str, period: str = "full") -> dict[str, Any]:
        stock = self.db.get_stock(code) or {}
        prices = self.db.price_series(code, start=DATA_START_DATE.isoformat())
        if not prices:
            return {
                "stock": stock,
                "latest": stock.get("close"),
                "change": stock.get("change"),
                "change_pct": stock.get("change_pct"),
                "high": stock.get("high52"),
                "low": stock.get("low52"),
                "period_return": None,
                "year_return": None,
                "ytd_return": None,
                "volume": stock.get("volume"),
            }
        latest = prices[-1]
        previous = prices[-2] if len(prices) > 1 else None
        latest_close = latest["close"]
        change = latest_close - previous["close"] if previous else 0
        change_pct = change / previous["close"] * 100 if previous and previous["close"] else 0.0

        window = prices
        if period == "recent":
            window = prices[-30:]
        first = window[0]
        period_return = (
            (latest_close / first["close"] - 1) * 100 if first.get("close") else None
        )
        last_2023 = next(
            (row["close"] for row in reversed(prices) if row["date"] <= "2023-12-31"), None
        )
        since_2023 = (
            (latest_close / last_2023 - 1) * 100 if last_2023 else None
        )
        previous_year_end = next(
            (
                row["close"]
                for row in reversed(prices)
                if row["date"][:4] < latest["date"][:4]
            ),
            None,
        )
        ytd = (
            (latest_close / previous_year_end - 1) * 100 if previous_year_end else None
        )
        trailing = prices[-252:] if len(prices) >= 252 else prices
        high = max(row["high"] or row["close"] for row in trailing)
        low = min(row["low"] or row["close"] for row in trailing)
        recent_volume = [row["volume"] for row in prices[-20:] if row.get("volume")]
        avg_volume = sum(recent_volume) / len(recent_volume) if recent_volume else None
        return {
            "stock": stock,
            "latest": latest_close,
            "latest_date": latest["date"],
            "change": int(change),
            "change_pct": change_pct,
            "high": high,
            "low": low,
            "period_return": period_return,
            "since_2023_return": since_2023,
            "ytd_return": ytd,
            "year_return": ytd,
            "volume": latest.get("volume"),
            "avg_volume_20": avg_volume,
            "first_date": prices[0]["date"],
        }

    def watchlist_metrics(self) -> list[dict[str, Any]]:
        rows = self.db.watchlist_rows()
        result = []
        for row in rows:
            metrics = self.stock_metrics(row["code"])
            merged = dict(row)
            merged.update(
                {
                    "metrics_latest": metrics.get("latest"),
                    "metrics_change": metrics.get("change"),
                    "metrics_change_pct": metrics.get("change_pct"),
                    "period_return": metrics.get("period_return"),
                    "since_2023_return": metrics.get("since_2023_return"),
                    "ytd_return": metrics.get("ytd_return"),
                    "latest_date": metrics.get("latest_date"),
                }
            )
            result.append(merged)
        return result

    def market_overview(self) -> dict[str, Any]:
        return self.db.market_overview()

    # ------------------------------------------------------------------
    # Per-stock close lookup
    # ------------------------------------------------------------------
    def lookup_close(self, code: str, target_date: date | str) -> dict[str, Any] | None:
        stock = self.db.get_stock(code)
        if not stock:
            return None
        target = target_date.isoformat() if isinstance(target_date, date) else str(target_date)
        rows = self.db.price_series(code, start=DATA_START_DATE.isoformat())
        if not rows:
            return None
        dates = [row["date"] for row in rows]
        index = bisect.bisect_right(dates, target) - 1
        if index < 0:
            index = 0
        selected = rows[index]
        previous = rows[index - 1] if index > 0 else None
        next_row = rows[index + 1] if index + 1 < len(rows) else None
        change = selected["close"] - previous["close"] if previous else None
        change_pct = (
            change / previous["close"] * 100 if change is not None and previous["close"] else None
        )

        def offset_return(offset: int) -> float | None:
            base_index = index - offset
            if base_index < 0:
                return None
            base = rows[base_index]["close"]
            return (selected["close"] / base - 1) * 100 if base else None

        prior_year_end = next(
            (row["close"] for row in reversed(rows[: index + 1]) if row["date"][:4] < selected["date"][:4]),
            None,
        )
        ytd = (selected["close"] / prior_year_end - 1) * 100 if prior_year_end else None
        start_index = max(0, index - 5)
        end_index = min(len(rows), index + 9)
        window = rows[start_index:end_index]
        return {
            "stock": stock,
            "requested_date": target,
            "selected": selected,
            "previous": previous,
            "next": next_row,
            "is_exact": selected["date"] == target,
            "change": change,
            "change_pct": change_pct,
            "returns": {
                "1D": offset_return(1),
                "1W": offset_return(5),
                "1M": offset_return(20),
                "3M": offset_return(60),
                "6M": offset_return(120),
                "1Y": offset_return(250),
                "YTD": ytd,
            },
            "window": window,
        }

    # ------------------------------------------------------------------
    # Report data
    # ------------------------------------------------------------------
    def report_bundle(self, codes: Sequence[str] | None = None) -> dict[str, Any]:
        codes = list(codes or self.db.watchlist_codes())
        stocks = []
        for code in codes:
            stock = self.db.get_stock(code)
            if stock:
                stock = dict(stock)
                metrics = self.stock_metrics(code)
                stock["report_metrics"] = metrics
                stocks.append(stock)
        series = self.db.price_series_many(codes, start=DATA_START_DATE.isoformat())
        all_dates = sorted({row["date"] for rows in series.values() for row in rows})
        basis = all_dates[-1] if all_dates else self.db.latest_price_date()
        return {
            "stocks": stocks,
            "codes": codes,
            "series": series,
            "basis_date": basis,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source": "NAVER Finance (KRX)",
        }
