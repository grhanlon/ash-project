@echo off
setlocal EnableExtensions
REM Contagion Read-Through — run Streamlit inside the VDI (Windows).
REM Double-click this file, or run from Command Prompt. Uses repo root (parent of vdi\).

cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" (
  echo Using virtual env: .venv
  ".venv\Scripts\python.exe" -m streamlit run app.py
  goto :done
)

where py >nul 2>nul
if %errorlevel%==0 (
  echo Using Python launcher: py -3
  py -3 -m streamlit run app.py
  goto :done
)

where python >nul 2>nul
if %errorlevel%==0 (
  echo Using: python
  python -m streamlit run app.py
  goto :done
)

echo.
echo Python was not found. Run setup-venv.bat once ^(requires IT-approved Python^), or add Python to PATH.
echo.
pause
exit /b 1

:done
if errorlevel 1 (
  echo.
  echo Streamlit exited with an error. If imports failed, run setup-venv.bat and: pip install xbbg
  echo.
  pause
)

endlocal
