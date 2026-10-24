# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the portable KOSPI 인사이트 build."""

from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

ROOT = Path(SPECPATH).resolve()
ASSET_DIR = ROOT / "assets"

# Only runtime assets are bundled; development fonts and screenshots are not.
ASSET_FILES = [
    path
    for path in ASSET_DIR.iterdir()
    if path.is_file() and path.suffix.lower() in {".db", ".ico", ".png"}
]
datas = [(str(path), "assets") for path in ASSET_FILES]

version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(1, 0, 0, 0),
        prodvers=(1, 0, 0, 0),
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "KOSPI Insight"),
                        StringStruct("FileDescription", "KOSPI 인사이트"),
                        StringStruct("FileVersion", "1.0.0"),
                        StringStruct("InternalName", "KOSPIInsight"),
                        StringStruct("OriginalFilename", "KOSPI Insight.exe"),
                        StringStruct("ProductName", "KOSPI 인사이트"),
                        StringStruct("ProductVersion", "1.0.0"),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pandas", "numpy", "matplotlib", "scipy", "PIL"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KOSPI Insight",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSET_DIR / "app_icon.ico"),
    version=version_info,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="KOSPI Insight",
)
