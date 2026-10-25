# -*- coding: utf-8 -*-
"""Application-wide constants and design tokens."""

from __future__ import annotations

from datetime import date

APP_NAME = "KOSPI 인사이트"
APP_NAME_EN = "KOSPI Insight"
APP_TAGLINE = "가치 분석 · 종가 조회 · 스크리너"
VERSION = "1.0.0"
DATA_START_DATE = date(2023, 1, 1)
DEFAULT_WATCHLIST = ("005930", "000660", "105560", "055550")
SOURCE_NAME = "네이버증권 (KRX 시세·재무)"
SOURCE_URL = "https://finance.naver.com/"
DISCLAIMER = "본 프로그램은 정보 제공용이며 투자 권유가 아닙니다. 데이터 오류 및 지연 가능성을 확인하세요."

COLORS = {
    "navy": "#0B1F33",
    "navy_2": "#102A44",
    "navy_3": "#173754",
    "teal": "#0F9D8A",
    "teal_dark": "#0A7C6D",
    "teal_soft": "#E7F8F4",
    "amber": "#F2A93B",
    "amber_soft": "#FFF5E4",
    "bg": "#F3F6FA",
    "surface": "#FFFFFF",
    "surface_alt": "#F8FAFC",
    "border": "#E2E8F0",
    "border_dark": "#CBD5E1",
    "text": "#122033",
    "text_2": "#334155",
    "muted": "#718096",
    "muted_2": "#94A3B8",
    "rise": "#E23D3D",
    "fall": "#2563EB",
    "flat": "#64748B",
    "positive_soft": "#FEF2F2",
    "negative_soft": "#EFF6FF",
    "chart": ["#0F9D8A", "#F2A93B", "#3B82F6", "#E45757", "#8B5CF6", "#06B6D4", "#64748B", "#EC4899"],
}

CHART_COLORS = COLORS["chart"]
CURRENCY_UNIT = "원"
MARKET_CAP_UNIT = "억원"
MAX_CHART_POINTS = 1200
