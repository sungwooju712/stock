# -*- coding: utf-8 -*-
"""NAVER Finance data access.

Only public endpoints used by the NAVER Finance web/app are accessed.  No
private API key is needed.  The client is intentionally defensive: network
failures raise NaverError, while malformed optional fields become None.
"""

from __future__ import annotations

import ast
import json
import random
import re
import time
from datetime import date, datetime, timedelta
from typing import Any, Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .paths import naver_stock_url

MOBILE = "https://m.stock.naver.com/api"
MARKET_LIST_URL = f"{MOBILE}/stocks/marketValue/KOSPI"
INTEGRATION_URL = f"{MOBILE}/stock/{{code}}/integration"
ANNUAL_URL = f"{MOBILE}/stock/{{code}}/finance/annual"
DAILY_URL = "https://api.finance.naver.com/siseJson.naver"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class NaverError(RuntimeError):
    """Raised when a NAVER request cannot be completed."""


def parse_number(value: Any) -> float | None:
    """Parse Korean formatted numbers such as ``1,248조 1,805억`` or ``9.58배``."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"-", "N/A", "n/a", "null", "None"}:
        return None

    # Market-cap style text: 1,248조 1,805억원
    jo = re.search(r"([\d,]+(?:\.\d+)?)\s*조", text)
    eok = re.search(r"([\d,]+(?:\.\d+)?)\s*억", text)
    if jo or eok:
        total = 0.0
        if jo:
            total += float(jo.group(1).replace(",", "")) * 1_0000_0000_0000
        if eok:
            total += float(eok.group(1).replace(",", "")) * 1_0000_0000
        if total:
            return total

    match = re.search(r"-?[\d,]+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\xa0", " ").strip()


def _format_bizdate(value: Any) -> str | None:
    text = clean_text(value)
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return None


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", "", clean_text(title))


def _first(columns: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in columns:
            return columns[key]
    return None


class NaverClient:
    """Small, retrying client for the public NAVER Finance endpoints."""

    def __init__(self, timeout: int = 18, retries: int = 2):
        self.timeout = timeout
        self.session = requests.Session()
        retry = Retry(
            total=retries,
            connect=retries,
            read=retries,
            backoff_factor=0.55,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Referer": "https://finance.naver.com/",
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
            }
        )

    def close(self) -> None:
        self.session.close()

    def _get(self, url: str, *, params: dict[str, Any] | None = None) -> requests.Response:
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                return response
            raise NaverError(f"NAVER 응답 오류 HTTP {response.status_code}")
        except requests.RequestException as exc:
            raise NaverError(f"NAVER 연결 실패: {exc}") from exc

    def _get_json(self, url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._get(url, params=params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise NaverError("NAVER 응답을 해석할 수 없습니다.") from exc
        if not isinstance(payload, dict):
            raise NaverError("예상하지 못한 NAVER 응답 형식입니다.")
        return payload

    # ------------------------------------------------------------------
    # Stock universe / market snapshot
    # ------------------------------------------------------------------
    def fetch_kospi_stocks(self, *, page_size: int = 100, progress=None) -> list[dict[str, Any]]:
        """Return all KOSPI common/preferred stocks (ETFs/ETNs excluded)."""
        stocks: list[dict[str, Any]] = []
        page = 1
        total = None
        while True:
            payload = self._get_json(
                MARKET_LIST_URL, params={"page": page, "pageSize": page_size}
            )
            rows = payload.get("stocks") or []
            total = int(payload.get("totalCount") or total or 0)
            for row in rows:
                if row.get("stockEndType") != "stock":
                    continue
                stocks.append(self._parse_market_row(row))
            if progress:
                progress(f"KOSPI 종목 목록 {page}페이지 수집 중", len(stocks), total)
            if not rows or page * page_size >= (total or 0):
                break
            page += 1
            time.sleep(0.06 + random.random() * 0.04)
        # De-duplicate by code, preserving market-cap order.
        unique: dict[str, dict[str, Any]] = {}
        for stock in stocks:
            unique[stock["code"]] = stock
        return list(unique.values())

    def _parse_market_row(self, row: dict[str, Any]) -> dict[str, Any]:
        code = clean_text(row.get("itemCode")).zfill(6)
        name = clean_text(row.get("stockName"))
        close = parse_number(row.get("closePriceRaw") or row.get("closePrice"))
        change = parse_number(
            row.get("compareToPreviousClosePriceRaw")
            or row.get("compareToPreviousClosePrice")
        )
        change_pct = parse_number(row.get("fluctuationsRatio"))
        volume = parse_number(
            row.get("accumulatedTradingVolumeRaw") or row.get("accumulatedTradingVolume")
        )
        market_cap = parse_number(row.get("marketValueRaw") or row.get("marketValue"))
        exchange = (row.get("stockExchangeType") or {}).get("nameKor", "코스피")
        return {
            "code": code,
            "name": name,
            "market": "KOSPI" if "코스피" in str(exchange) else "KOSPI",
            "close": int(close) if close is not None else None,
            "change": int(change) if change is not None else None,
            "change_pct": change_pct,
            "volume": int(volume) if volume is not None else None,
            "market_cap": int(market_cap) if market_cap is not None else None,
            "is_preferred": int(is_preferred_name(name)),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "source_url": naver_stock_url(code),
        }

    # ------------------------------------------------------------------
    # Current quote / valuation
    # ------------------------------------------------------------------
    def fetch_integration(self, code: str) -> dict[str, Any]:
        payload = self._get_json(INTEGRATION_URL.format(code=code))
        infos: dict[str, Any] = {}
        for item in payload.get("totalInfos") or []:
            key = clean_text(item.get("code") or item.get("key"))
            infos[key] = item
        result: dict[str, Any] = {
            "code": code,
            "name": clean_text(payload.get("stockName")),
        }
        mapping = {
            "lastClosePrice": "last_close",
            "marketValue": "market_value",
            "highPriceOf52Weeks": "high52",
            "lowPriceOf52Weeks": "low52",
            "per": "per",
            "eps": "eps",
            "pbr": "pbr",
            "bps": "bps",
            "dividendYieldRatio": "dividend_yield",
            "dividend": "dps",
            "foreignRate": "foreign_rate",
        }
        for source_key, target_key in mapping.items():
            item = infos.get(source_key)
            if not item:
                continue
            value = parse_number(item.get("value"))
            if value is None:
                continue
            if target_key in {"market_value"}:
                result[target_key] = int(value)
            elif target_key == "foreign_rate":
                result[target_key] = value
            else:
                result[target_key] = value

        # totalInfos.lastClosePrice is the *previous* session close ("전일").
        # The latest completed session is the first row of dealTrendInfos.
        trends = payload.get("dealTrendInfos") or []
        if trends:
            latest = trends[0]
            close = parse_number(latest.get("closePrice"))
            change = parse_number(latest.get("compareToPreviousClosePrice"))
            volume = parse_number(latest.get("accumulatedTradingVolume"))
            if close is not None:
                result["close"] = int(close)
                result["quote_date"] = _format_bizdate(latest.get("bizdate"))
            if change is not None:
                result["change"] = int(change)
                if close is not None and close - change:
                    result["change_pct"] = change / (close - change) * 100
            if volume is not None:
                result["volume"] = int(volume)
        return result

    # ------------------------------------------------------------------
    # Annual financial statements
    # ------------------------------------------------------------------
    def fetch_annual_financials(self, code: str) -> dict[str, Any]:
        payload = self._get_json(ANNUAL_URL.format(code=code))
        info = payload.get("financeInfo") or {}
        period_list = info.get("trTitleList") or []
        rows = info.get("rowList") or []
        if not period_list or not rows:
            raise NaverError("연간 재무 데이터가 없습니다.")

        row_map: dict[str, dict[str, Any]] = {}
        for row in rows:
            title = _normalize_title(row.get("title", ""))
            if title:
                row_map[title] = row.get("columns") or {}

        # Prefer the latest *confirmed* fiscal year.  Consensus periods use
        # isConsensus=Y and are not suitable for screening.
        confirmed = [p for p in period_list if str(p.get("isConsensus", "N")).upper() != "Y"]
        candidates = confirmed or period_list
        candidates = sorted(candidates, key=lambda p: str(p.get("key", "")), reverse=True)

        selected = None
        for period in candidates:
            key = str(period.get("key", ""))
            sales = _first(row_map.get("매출액", {}), key)
            op = _first(row_map.get("영업이익", {}), key)
            if parse_number(sales) is not None or parse_number(op) is not None:
                selected = period
                break
        if selected is None:
            selected = candidates[0]
        key = str(selected.get("key", ""))
        title = clean_text(selected.get("title", ""))
        year_match = re.match(r"(\d{4})", title)
        fiscal_year = int(year_match.group(1)) if year_match else int(key[:4])

        def metric(*titles: str) -> float | None:
            for title_ in titles:
                columns = row_map.get(_normalize_title(title_))
                if columns is not None:
                    value = parse_number(columns.get(key, {}).get("value"))
                    if value is not None:
                        return value
            return None

        sales = metric("매출액")
        operating_profit = metric("영업이익")
        net_income = metric("당기순이익")
        op_margin = metric("영업이익률")
        net_margin = metric("순이익률")
        if op_margin is None and sales and operating_profit is not None and sales != 0:
            op_margin = operating_profit / sales * 100
        if net_margin is None and sales and net_income is not None and sales != 0:
            net_margin = net_income / sales * 100

        return {
            "code": code,
            "fiscal_year": fiscal_year,
            "fiscal_period": title or key,
            "sales": sales,
            "operating_profit": operating_profit,
            "net_income": net_income,
            "op_margin": op_margin,
            "net_margin": net_margin,
            "debt_ratio": metric("부채비율"),
            "roe": metric("ROE"),
            "eps": metric("EPS"),
            "bps": metric("BPS"),
            "pbr": metric("PBR"),
            "per_annual": metric("PER"),
            "dps": metric("주당배당금"),
            "total_equity": metric("자본총계"),
            "retention_ratio": metric("유보율"),
            "periods": [
                {
                    "key": str(p.get("key", "")),
                    "title": clean_text(p.get("title", "")),
                    "is_consensus": str(p.get("isConsensus", "N")).upper() == "Y",
                }
                for p in period_list
            ],
            "source": "NAVER Finance",
        }

    # ------------------------------------------------------------------
    # Daily prices
    # ------------------------------------------------------------------
    def fetch_daily_prices(self, code: str, start: date, end: date) -> list[dict[str, Any]]:
        if start > end:
            return []
        params = {
            "symbol": code,
            "requestType": 1,
            "startTime": start.strftime("%Y%m%d"),
            "endTime": end.strftime("%Y%m%d"),
            "timeframe": "day",
        }
        response = self._get(DAILY_URL, params=params)
        text = response.text.strip()
        if not text:
            return []
        try:
            data = ast.literal_eval(text)
        except (ValueError, SyntaxError) as exc:
            raise NaverError("일별 시세 응답을 해석할 수 없습니다.") from exc
        if not isinstance(data, list) or len(data) < 2:
            return []
        rows: list[dict[str, Any]] = []
        for raw in data[1:]:
            if not isinstance(raw, (list, tuple)) or len(raw) < 5:
                continue
            day_text = clean_text(raw[0])
            if not re.fullmatch(r"\d{8}", day_text):
                continue
            try:
                close = float(raw[4])
            except (TypeError, ValueError):
                continue
            def safe_int(index: int) -> int | None:
                try:
                    return int(float(raw[index]))
                except (TypeError, ValueError, IndexError):
                    return None
            rows.append(
                {
                    "code": code,
                    "date": f"{day_text[:4]}-{day_text[4:6]}-{day_text[6:8]}",
                    "open": safe_int(1),
                    "high": safe_int(2),
                    "low": safe_int(3),
                    "close": int(close),
                    "volume": safe_int(5),
                }
            )
        return rows


_PREFERRED_SUFFIX = re.compile(r"(\d?우B?|\d?우C|\d우)$")


def is_preferred_name(name: str) -> bool:
    text = re.sub(r"\s+", "", name or "")
    if not text:
        return False
    # Common KOSPI preferred-share naming patterns: 삼성전자우, 현대차2우B,
    # LG화학우, CJ4우(전환) etc.
    return bool(_PREFERRED_SUFFIX.search(text)) or "우선주" in text


def merge_fundamentals(
    annual: dict[str, Any] | None,
    integration: dict[str, Any] | None,
    price: int | None,
) -> dict[str, Any]:
    annual = annual or {}
    integration = integration or {}
    merged = dict(annual)
    if integration:
        merged.update(
            {
                "per": integration.get("per"),
                "pbr": integration.get("pbr") or annual.get("pbr"),
                "eps": integration.get("eps") or annual.get("eps"),
                "bps": integration.get("bps") or annual.get("bps"),
                "dividend_yield": integration.get("dividend_yield"),
                "dps": integration.get("dps") or annual.get("dps"),
                "high52": integration.get("high52"),
                "low52": integration.get("low52"),
                "foreign_rate": integration.get("foreign_rate"),
            }
        )
    if merged.get("per") is None and price and merged.get("eps"):
        eps = merged["eps"]
        if eps > 0:
            merged["per"] = price / eps
    if merged.get("dividend_yield") is None and price and merged.get("dps"):
        merged["dividend_yield"] = merged["dps"] / price * 100
    merged["updated_at"] = datetime.now().isoformat(timespec="seconds")
    return merged


def today_previous_close_cutoff() -> date:
    """The previous calendar day.  Holidays are naturally skipped by NAVER."""
    return date.today() - timedelta(days=1)
