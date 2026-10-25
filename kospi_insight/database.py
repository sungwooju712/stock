# -*- coding: utf-8 -*-
"""SQLite persistence layer.

A fresh connection is opened for each operation so background workers do not
share connection state.  WAL mode keeps UI reads responsive during refreshes.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from .paths import db_path


SCHEMA = """
CREATE TABLE IF NOT EXISTS stocks (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'KOSPI',
    is_preferred INTEGER NOT NULL DEFAULT 0,
    close INTEGER,
    change INTEGER,
    change_pct REAL,
    volume INTEGER,
    market_cap INTEGER,
    high52 INTEGER,
    low52 INTEGER,
    foreign_rate REAL,
    active INTEGER NOT NULL DEFAULT 1,
    source_url TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS fundamentals (
    code TEXT PRIMARY KEY,
    fiscal_year INTEGER,
    fiscal_period TEXT,
    sales REAL,
    operating_profit REAL,
    net_income REAL,
    op_margin REAL,
    net_margin REAL,
    debt_ratio REAL,
    roe REAL,
    eps REAL,
    bps REAL,
    pbr REAL,
    per REAL,
    dividend_yield REAL,
    dps REAL,
    total_equity REAL,
    retention_ratio REAL,
    high52 INTEGER,
    low52 INTEGER,
    foreign_rate REAL,
    updated_at TEXT,
    source TEXT DEFAULT 'NAVER Finance',
    FOREIGN KEY(code) REFERENCES stocks(code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prices (
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    open INTEGER,
    high INTEGER,
    low INTEGER,
    close INTEGER,
    volume INTEGER,
    PRIMARY KEY(code, date),
    FOREIGN KEY(code) REFERENCES stocks(code) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);

CREATE TABLE IF NOT EXISTS watchlist (
    code TEXT PRIMARY KEY,
    sort_order INTEGER NOT NULL DEFAULT 0,
    alias TEXT,
    memo TEXT,
    added_at TEXT NOT NULL,
    FOREIGN KEY(code) REFERENCES stocks(code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class Database:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.executescript(SCHEMA)
            conn.commit()

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    def get_meta(self, key: str, default: str | None = None) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )
            conn.commit()

    def set_meta_many(self, values: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.executemany(
                "INSERT INTO meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                [(key, str(value)) for key, value in values.items()],
            )
            conn.commit()

    def get_meta_many(self, keys: Iterable[str]) -> dict[str, str]:
        keys = list(keys)
        if not keys:
            return {}
        placeholders = ",".join("?" for _ in keys)
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT key, value FROM meta WHERE key IN ({placeholders})", keys
            ).fetchall()
        return {row["key"]: row["value"] for row in rows}

    # ------------------------------------------------------------------
    # Stock master / quotes
    # ------------------------------------------------------------------
    def replace_stock_snapshot(self, stocks: Sequence[dict[str, Any]]) -> None:
        if not stocks:
            return
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE stocks SET active = 0 WHERE code NOT IN (SELECT code FROM watchlist)"
            )
            for stock in stocks:
                conn.execute(
                    """
                    INSERT INTO stocks(
                        code, name, market, is_preferred, close, change, change_pct,
                        volume, market_cap, active, source_url, updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,1,?,?)
                    ON CONFLICT(code) DO UPDATE SET
                        name = excluded.name,
                        market = excluded.market,
                        is_preferred = excluded.is_preferred,
                        close = excluded.close,
                        change = excluded.change,
                        change_pct = excluded.change_pct,
                        volume = excluded.volume,
                        market_cap = excluded.market_cap,
                        active = 1,
                        source_url = excluded.source_url,
                        updated_at = excluded.updated_at
                    """,
                    (
                        stock["code"],
                        stock["name"],
                        stock.get("market", "KOSPI"),
                        int(stock.get("is_preferred", 0)),
                        stock.get("close"),
                        stock.get("change"),
                        stock.get("change_pct"),
                        stock.get("volume"),
                        stock.get("market_cap"),
                        stock.get("source_url"),
                        now,
                    ),
                )
            conn.commit()

    def upsert_stock(self, stock: dict[str, Any]) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO stocks(
                    code, name, market, is_preferred, close, change, change_pct,
                    volume, market_cap, active, source_url, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,1,?,?)
                ON CONFLICT(code) DO UPDATE SET
                    name = COALESCE(NULLIF(excluded.name, ''), stocks.name),
                    market = excluded.market,
                    is_preferred = excluded.is_preferred,
                    close = COALESCE(excluded.close, stocks.close),
                    change = COALESCE(excluded.change, stocks.change),
                    change_pct = COALESCE(excluded.change_pct, stocks.change_pct),
                    volume = COALESCE(excluded.volume, stocks.volume),
                    market_cap = COALESCE(excluded.market_cap, stocks.market_cap),
                    active = 1,
                    source_url = COALESCE(excluded.source_url, stocks.source_url),
                    updated_at = excluded.updated_at
                """,
                (
                    stock["code"],
                    stock.get("name", stock["code"]),
                    stock.get("market", "KOSPI"),
                    int(stock.get("is_preferred", 0)),
                    stock.get("close"),
                    stock.get("change"),
                    stock.get("change_pct"),
                    stock.get("volume"),
                    stock.get("market_cap"),
                    stock.get("source_url"),
                    now,
                ),
            )
            conn.commit()

    def update_quote(
        self,
        code: str,
        *,
        close: int | None = None,
        change: int | None = None,
        change_pct: float | None = None,
        volume: int | None = None,
        market_cap: int | None = None,
        high52: int | None = None,
        low52: int | None = None,
        foreign_rate: float | None = None,
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE stocks SET
                    close = COALESCE(?, close),
                    change = COALESCE(?, change),
                    change_pct = COALESCE(?, change_pct),
                    volume = COALESCE(?, volume),
                    market_cap = COALESCE(?, market_cap),
                    high52 = COALESCE(?, high52),
                    low52 = COALESCE(?, low52),
                    foreign_rate = COALESCE(?, foreign_rate),
                    updated_at = ?
                WHERE code = ?
                """,
                (
                    close,
                    change,
                    change_pct,
                    volume,
                    market_cap,
                    high52,
                    low52,
                    foreign_rate,
                    now,
                    code,
                ),
            )
            conn.commit()

    def save_fundamentals(self, data: dict[str, Any]) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        fields = [
            "fiscal_year",
            "fiscal_period",
            "sales",
            "operating_profit",
            "net_income",
            "op_margin",
            "net_margin",
            "debt_ratio",
            "roe",
            "eps",
            "bps",
            "pbr",
            "per",
            "dividend_yield",
            "dps",
            "total_equity",
            "retention_ratio",
            "high52",
            "low52",
            "foreign_rate",
            "source",
        ]
        values = [data.get(field) for field in fields]
        with self.connect() as conn:
            conn.execute(
                f"""
                INSERT INTO fundamentals(
                    code, {", ".join(fields)}, updated_at
                ) VALUES(?, {", ".join("?" for _ in fields)}, ?)
                ON CONFLICT(code) DO UPDATE SET
                    {", ".join(f"{field} = COALESCE(excluded.{field}, fundamentals.{field})" for field in fields)},
                    updated_at = excluded.updated_at
                """,
                [data["code"], *values, now],
            )
            conn.commit()

    def get_stock(self, code: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT s.*, f.fiscal_year, f.sales, f.operating_profit, f.net_income,
                       f.op_margin, f.net_margin, f.debt_ratio, f.roe, f.eps, f.bps,
                       f.pbr, f.per, f.dividend_yield, f.dps, f.retention_ratio,
                       f.updated_at AS fundamentals_updated_at
                FROM stocks s
                LEFT JOIN fundamentals f ON f.code = s.code
                WHERE s.code = ?
                """,
                (code,),
            ).fetchone()
        return dict(row) if row else None

    def search_stocks(self, query: str, *, limit: int = 60) -> list[dict[str, Any]]:
        query = (query or "").strip()
        with self.connect() as conn:
            if query:
                like = f"%{query}%"
                rows = conn.execute(
                    """
                    SELECT s.*, w.code IS NOT NULL AS in_watchlist,
                           CASE WHEN s.code = ? OR s.name = ? THEN 0
                                WHEN s.name LIKE ? THEN 1 ELSE 2 END AS relevance
                    FROM stocks s
                    LEFT JOIN watchlist w ON w.code = s.code
                    WHERE (s.code LIKE ? OR s.name LIKE ?) AND s.active = 1
                    ORDER BY relevance, s.market_cap DESC
                    LIMIT ?
                    """,
                    (query, query, f"{query}%", like, like, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT s.*, w.code IS NOT NULL AS in_watchlist
                    FROM stocks s LEFT JOIN watchlist w ON w.code = s.code
                    WHERE s.active = 1
                    ORDER BY s.market_cap DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    def all_active_codes(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT code FROM stocks WHERE active = 1 ORDER BY code"
            ).fetchall()
        return [row["code"] for row in rows]

    def candidate_rows(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT s.code, s.name, s.market, s.is_preferred, s.close, s.change,
                       s.change_pct, s.volume, s.market_cap, s.high52, s.low52,
                       f.fiscal_year, f.sales, f.operating_profit, f.net_income,
                       f.op_margin, f.net_margin, f.debt_ratio, f.roe, f.eps,
                       f.pbr, f.per, f.dividend_yield, f.dps,
                       w.code IS NOT NULL AS in_watchlist
                FROM stocks s
                LEFT JOIN fundamentals f ON f.code = s.code
                LEFT JOIN watchlist w ON w.code = s.code
                WHERE s.active = 1 AND s.market = 'KOSPI'
                ORDER BY s.market_cap DESC, s.name
                """
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Watchlist / favorites
    # ------------------------------------------------------------------
    def watchlist_rows(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT s.*, w.sort_order, w.alias, w.memo, w.added_at,
                       f.fiscal_year, f.sales, f.operating_profit, f.net_income,
                       f.op_margin, f.net_margin, f.debt_ratio, f.roe, f.eps,
                       f.pbr, f.per, f.dividend_yield, f.dps
                FROM watchlist w
                JOIN stocks s ON s.code = w.code
                LEFT JOIN fundamentals f ON f.code = s.code
                ORDER BY w.sort_order, w.added_at
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def watchlist_codes(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT code FROM watchlist ORDER BY sort_order, added_at"
            ).fetchall()
        return [row["code"] for row in rows]

    def is_in_watchlist(self, code: str) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT 1 FROM watchlist WHERE code = ?", (code,)).fetchone()
        return row is not None

    def add_to_watchlist(self, code: str, alias: str = "", memo: str = "") -> bool:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            exists = conn.execute("SELECT 1 FROM watchlist WHERE code = ?", (code,)).fetchone()
            if exists:
                return False
            row = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order FROM watchlist"
            ).fetchone()
            conn.execute(
                "INSERT INTO watchlist(code, sort_order, alias, memo, added_at) VALUES(?,?,?,?,?)",
                (code, int(row["next_order"]), alias or None, memo or None, now),
            )
            conn.commit()
        return True

    def remove_from_watchlist(self, code: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM watchlist WHERE code = ?", (code,))
            self._normalize_sort_orders(conn)
            conn.commit()

    def update_watchlist_item(self, code: str, *, alias: str = "", memo: str = "") -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE watchlist SET alias = ?, memo = ? WHERE code = ?",
                (alias.strip() or None, memo.strip() or None, code),
            )
            conn.commit()

    def move_watchlist(self, code: str, direction: int) -> None:
        if direction == 0:
            return
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT code FROM watchlist ORDER BY sort_order, added_at"
            ).fetchall()
            codes = [row["code"] for row in rows]
            if code not in codes:
                return
            index = codes.index(code)
            target = index + direction
            if target < 0 or target >= len(codes):
                return
            codes[index], codes[target] = codes[target], codes[index]
            for order, item_code in enumerate(codes):
                conn.execute(
                    "UPDATE watchlist SET sort_order = ? WHERE code = ?", (order, item_code)
                )
            conn.commit()

    def _normalize_sort_orders(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            "SELECT code FROM watchlist ORDER BY sort_order, added_at"
        ).fetchall()
        for order, row in enumerate(rows):
            conn.execute(
                "UPDATE watchlist SET sort_order = ? WHERE code = ?", (order, row["code"])
            )

    def ensure_default_watchlist(self, codes: Iterable[str]) -> None:
        with self.connect() as conn:
            count = conn.execute("SELECT COUNT(*) AS n FROM watchlist").fetchone()["n"]
            if count:
                return
            existing = {
                row["code"]
                for row in conn.execute(
                    f"SELECT code FROM stocks WHERE code IN ({','.join('?' for _ in list(codes))})",
                    tuple(codes),
                ).fetchall()
            }
        for code in codes:
            if code in existing:
                self.add_to_watchlist(code)

    # ------------------------------------------------------------------
    # Prices
    # ------------------------------------------------------------------
    def upsert_prices(self, code: str, rows: Sequence[dict[str, Any]]) -> int:
        if not rows:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO prices(code, date, open, high, low, close, volume)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(code, date) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume
                """,
                [
                    (
                        code,
                        row["date"],
                        row.get("open"),
                        row.get("high"),
                        row.get("low"),
                        row.get("close"),
                        row.get("volume"),
                    )
                    for row in rows
                ],
            )
            conn.commit()
        return len(rows)

    def price_series(self, code: str, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        clauses = ["code = ?"]
        params: list[Any] = [code]
        if start:
            clauses.append("date >= ?")
            params.append(start)
        if end:
            clauses.append("date <= ?")
            params.append(end)
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT date, open, high, low, close, volume FROM prices "
                f"WHERE {' AND '.join(clauses)} ORDER BY date",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def price_series_many(self, codes: Sequence[str], start: str | None = None, end: str | None = None) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {code: [] for code in codes}
        if not codes:
            return result
        placeholders = ",".join("?" for _ in codes)
        clauses = [f"code IN ({placeholders})"]
        params: list[Any] = list(codes)
        if start:
            clauses.append("date >= ?")
            params.append(start)
        if end:
            clauses.append("date <= ?")
            params.append(end)
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT code, date, open, high, low, close, volume FROM prices "
                f"WHERE {' AND '.join(clauses)} ORDER BY code, date",
                params,
            ).fetchall()
        for row in rows:
            result[row["code"]].append(dict(row))
        return result

    def price_bounds(self, code: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT MIN(date) AS first_date, MAX(date) AS last_date, COUNT(*) AS n "
                "FROM prices WHERE code = ?",
                (code,),
            ).fetchone()
        if not row or not row["n"]:
            return None
        return dict(row)

    def latest_price_date(self) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT MAX(date) AS d FROM prices").fetchone()
        return row["d"] if row else None

    def close_on_or_before(self, code: str, iso_date: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT code, date, close, open, high, low, volume FROM prices "
                "WHERE code = ? AND date <= ? ORDER BY date DESC LIMIT 1",
                (code, iso_date),
            ).fetchone()
        return dict(row) if row else None

    def recent_prices(self, code: str, limit: int = 60) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT date, close, open, high, low, volume FROM prices "
                "WHERE code = ? ORDER BY date DESC LIMIT ?",
                (code, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def price_rows_around(self, code: str, iso_date: str, before: int = 5, after: int = 8) -> list[dict[str, Any]]:
        with self.connect() as conn:
            prior = conn.execute(
                "SELECT date, close, open, high, low, volume FROM prices "
                "WHERE code = ? AND date <= ? ORDER BY date DESC LIMIT ?",
                (code, iso_date, before + 1),
            ).fetchall()
            later = conn.execute(
                "SELECT date, close, open, high, low, volume FROM prices "
                "WHERE code = ? AND date > ? ORDER BY date LIMIT ?",
                (code, iso_date, after),
            ).fetchall()
        rows = [dict(row) for row in reversed(prior)] + [dict(row) for row in later]
        return rows

    # ------------------------------------------------------------------
    # Aggregate information
    # ------------------------------------------------------------------
    def counts(self) -> dict[str, int]:
        with self.connect() as conn:
            result: dict[str, int] = {}
            result["stocks"] = conn.execute(
                "SELECT COUNT(*) AS n FROM stocks WHERE active = 1"
            ).fetchone()["n"]
            result["watchlist"] = conn.execute("SELECT COUNT(*) AS n FROM watchlist").fetchone()["n"]
            result["fundamentals"] = conn.execute(
                "SELECT COUNT(*) AS n FROM fundamentals"
            ).fetchone()["n"]
            result["prices"] = conn.execute("SELECT COUNT(*) AS n FROM prices").fetchone()["n"]
            result["price_stocks"] = conn.execute(
                "SELECT COUNT(DISTINCT code) AS n FROM prices"
            ).fetchone()["n"]
        return result

    def market_overview(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END) AS rising,
                       SUM(CASE WHEN change_pct < 0 THEN 1 ELSE 0 END) AS falling,
                       SUM(CASE WHEN change_pct = 0 OR change_pct IS NULL THEN 1 ELSE 0 END) AS flat,
                       SUM(market_cap) AS total_market_cap,
                       AVG(CASE WHEN market_cap >= 100000000000 THEN 1.0 ELSE 0 END) AS over_1000
                FROM stocks WHERE active = 1 AND market = 'KOSPI'
                """
            ).fetchone()
            top = conn.execute(
                "SELECT code, name, close, change_pct, market_cap FROM stocks "
                "WHERE active = 1 AND market = 'KOSPI' ORDER BY market_cap DESC LIMIT 5"
            ).fetchall()
        result = dict(row) if row else {}
        result["top"] = [dict(item) for item in top]
        return result

    def transactions_count(self, table: str) -> int:
        allowed = {"stocks", "fundamentals", "prices", "watchlist"}
        if table not in allowed:
            raise ValueError("invalid table")
        with self.connect() as conn:
            return conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]

    def reset_runtime_cache(self) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM prices")
            conn.execute("DELETE FROM meta WHERE key LIKE 'last_%'")
            conn.commit()
