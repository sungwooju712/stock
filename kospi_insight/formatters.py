# -*- coding: utf-8 -*-
"""Korean number/date formatting helpers shared by the UI and reports."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

DASH = "–"


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and (value != value):
        return True
    return False


def fmt_int(value: Any, suffix: str = "") -> str:
    if is_missing(value):
        return DASH
    try:
        return f"{float(value):,.0f}{suffix}"
    except (TypeError, ValueError):
        return DASH


def fmt_won(value: Any) -> str:
    return fmt_int(value, "원")


def fmt_price(value: Any) -> str:
    if is_missing(value):
        return DASH
    try:
        return f"{int(round(float(value))):,}"
    except (TypeError, ValueError):
        return DASH


def fmt_volume(value: Any) -> str:
    if is_missing(value):
        return DASH
    try:
        value = float(value)
    except (TypeError, ValueError):
        return DASH
    if value >= 100_000_000:
        return f"{value / 100_000_000:.1f}억주"
    if value >= 10_000:
        return f"{value / 10_000:.1f}만주"
    return f"{value:,.0f}주"


def fmt_market_cap(value_won: Any) -> str:
    """Format a KRW market cap in a compact, Korean-friendly form."""
    if is_missing(value_won):
        return DASH
    try:
        value = float(value_won)
    except (TypeError, ValueError):
        return DASH
    if value >= 1_0000_0000_0000:  # 1조
        return f"{value / 1_0000_0000_0000:,.1f}조원"
    if value >= 100_000_000:  # 1억
        return f"{value / 100_000_000:,.0f}억원"
    return f"{value:,.0f}원"


def fmt_eok(value: Any, suffix: str = "억원") -> str:
    if is_missing(value):
        return DASH
    try:
        return f"{float(value):,.0f}{suffix}"
    except (TypeError, ValueError):
        return DASH


def fmt_pct(value: Any, signed: bool = False, digits: int = 2) -> str:
    if is_missing(value):
        return DASH
    try:
        value = float(value)
    except (TypeError, ValueError):
        return DASH
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value:,.{digits}f}%"


def fmt_ratio(value: Any, digits: int = 2, suffix: str = "배") -> str:
    if is_missing(value):
        return DASH
    try:
        return f"{float(value):,.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return DASH


def fmt_date(value: Any, pattern: str = "%Y-%m-%d") -> str:
    if is_missing(value):
        return DASH
    if isinstance(value, (datetime, date)):
        return value.strftime(pattern)
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


def fmt_datetime(value: Any) -> str:
    if is_missing(value):
        return DASH
    text = str(value)
    if "T" in text:
        return text.replace("T", " ")[:16]
    return text


def fmt_signed_price(value: Any) -> str:
    if is_missing(value):
        return DASH
    try:
        value = int(round(float(value)))
    except (TypeError, ValueError):
        return DASH
    if value > 0:
        return f"+{value:,}"
    return f"{value:,}"


def tone_class(value: Any) -> str:
    """Return 'rise', 'fall' or 'flat' (Korean market colour convention)."""
    if is_missing(value):
        return "flat"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "flat"
    if number > 0:
        return "rise"
    if number < 0:
        return "fall"
    return "flat"


def month_label(iso_date: str) -> str:
    return iso_date[:7]


def year_label(iso_date: str) -> str:
    return iso_date[:4]


def safe_filename(text: str, fallback: str = "KOSPI_분석") -> str:
    cleaned = "".join(ch for ch in str(text) if ch not in '\\/:*?"<>|').strip()
    return cleaned or fallback
