# -*- coding: utf-8 -*-
"""Lightweight sector helpers for the screener.

The local cache intentionally stores only market and fundamental fields from
NAVER Finance; it does not carry a full industry classification.  For the
debt-ratio screen we only need to identify financial companies, so a small
set of unambiguous name patterns plus a few explicitly mapped codes is enough
and remains stable when the snapshot is refreshed.
"""

from __future__ import annotations

# Names that do not contain one of the financial keywords below.
FINANCIAL_CODES = frozenset(
    {
        "003690",  # 코리안리 (reinsurance)
        "055550",  # 신한지주 (financial holding)
        "088980",  # 맥쿼리인프라 (infrastructure fund)
        "377300",  # 카카오페이 (fintech)
    }
)

# These words are specific enough to identify financial businesses in KOSPI
# stock names.  Preferred-share suffixes (우, 우B, 2우B) do not affect them.
_FINANCIAL_TOKENS = (
    "금융",
    "은행",
    "보험",
    "증권",
    "화재",
    "카드",
    "캐피탈",
    "자산신탁",
    "토지신탁",
    "인베스트먼트",
    "뱅크",
    "해상",
    "벤처",
)


def is_financial_stock(code: str, name: str) -> bool:
    """Return True for banks, insurers, brokers, financial holdings, etc."""

    if code in FINANCIAL_CODES:
        return True
    text = (name or "").strip()
    if not text:
        return False
    if any(token in text for token in _FINANCIAL_TOKENS):
        return True
    # Life insurers end with 생명; 생명과학 is a biotechnology company.
    if "생명" in text and "생명과학" not in text:
        return True
    # REITs are financial vehicles.  메리츠 is a financial holding company,
    # not a REIT, and is already covered by the 금융 token.
    if "리츠" in text and "메리츠" not in text:
        return True
    return False
