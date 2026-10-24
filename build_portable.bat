@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo [1/2] Installing build dependencies...
py -m pip install -r requirements-dev.txt
if errorlevel 1 goto :error

echo [2/2] Building portable app...
py -m PyInstaller --noconfirm --clean KOSPIInsight.spec
if errorlevel 1 goto :error

echo.
echo Build complete: dist\KOSPI Insight\KOSPI Insight.exe
pause
exit /b 0

:error
echo.
echo Build failed. Review the messages above.
pause
exit /b 1
