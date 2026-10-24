@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

where pyw >nul 2>nul
if not errorlevel 1 (
    start "" pyw -3 -m kospi_insight
    exit /b 0
)

where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw -m kospi_insight
    exit /b 0
)

echo Python 3.12 or newer is required.
echo Install the dependencies first: py -m pip install -r requirements.txt
pause
