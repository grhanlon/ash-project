@echo off
setlocal EnableExtensions
REM One-time setup: create .venv in repo root and install Python deps.
REM Run from an elevated or IT-approved shell if your VDI blocks venv creation.

cd /d "%~dp0.."

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -m venv .venv
  goto :have_venv
)
where python >nul 2>nul
if %errorlevel%==0 (
  python -m venv .venv
  goto :have_venv
)

echo Install Python 3.11+ from your firm ^(or python.org^) and ensure py/python is on PATH, then re-run.
pause
exit /b 1

:have_venv
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Core packages installed.
echo For live Bloomberg on this VDI, your institutional setup may also need:
echo   pip install xbbg
echo ^(requires Bloomberg Terminal + blpapi on this machine.^)
echo.
echo To start the app: double-click vdi\run-streamlit.bat
echo Then open http://localhost:8501 in the VDI browser.
echo.
pause
endlocal
