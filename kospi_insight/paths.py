# -*- coding: utf-8 -*-
"""Portable application paths.

In source mode, data and exports live beside the project.  In the packaged
executable, the cache lives under %LOCALAPPDATA% so that an installed copy is
always writable, while the bundled seed database is copied on first launch.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from .constants import APP_NAME


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resource_dir() -> Path:
    if is_frozen() and getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS)
    return project_root()


def package_dir() -> Path:
    base = resource_dir()
    candidate = base / "kospi_insight"
    return candidate if candidate.exists() else project_root() / "kospi_insight"


def local_app_data() -> Path:
    root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if root:
        return Path(root) / "KOSPIInsight"
    return Path.home() / ".kospi_insight"


def data_dir() -> Path:
    override = os.environ.get("KOSPI_INSIGHT_DATA_DIR")
    path = Path(override) if override else (local_app_data() if is_frozen() else project_root() / "data")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _documents_dir() -> Path:
    """Return the user's Documents known folder (OneDrive-aware on Windows)."""
    if sys.platform == "win32":
        try:
            import ctypes

            buffer = ctypes.create_unicode_buffer(260)
            # CSIDL_PERSONAL (5) resolves redirected/OneDrive Documents folders.
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0:
                value = buffer.value.strip()
                if value:
                    return Path(value)
        except Exception:
            pass
    docs = Path.home() / "Documents"
    if docs.exists():
        return docs
    return Path.home() / "문서"


def exports_dir() -> Path:
    override = os.environ.get("KOSPI_INSIGHT_EXPORT_DIR")
    if override:
        path = Path(override)
    elif is_frozen():
        path = _documents_dir() / "KOSPI 인사이트 내보내기"
    else:
        path = project_root() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def seed_db_path() -> Path:
    candidates = [
        resource_dir() / "assets" / "seed_kospi.db",
        resource_dir() / "data" / "seed_kospi.db",
        project_root() / "assets" / "seed_kospi.db",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def db_path() -> Path:
    override = os.environ.get("KOSPI_INSIGHT_DB")
    if override:
        path = Path(override)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    target = data_dir() / "kospi_insight.db"
    if not target.exists():
        seed = seed_db_path()
        if seed.exists() and seed.resolve() != target.resolve():
            shutil.copy2(seed, target)
    return target


def assets_dir() -> Path:
    path = resource_dir() / "assets"
    if path.exists():
        return path
    return project_root() / "assets"


def naver_stock_url(code: str) -> str:
    return f"https://finance.naver.com/item/main.naver?code={code}"


def naver_finance_url(code: str) -> str:
    return f"https://finance.naver.com/item/coinfo.naver?code={code}"


def app_display_name() -> str:
    return APP_NAME
