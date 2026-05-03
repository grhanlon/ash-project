# Contagion Read-Through — Streamlit on Windows VDI (PowerShell).
# Usage: powershell -ExecutionPolicy Bypass -File vdi\run-streamlit.ps1
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (Test-Path ".\.venv\Scripts\python.exe") {
    Write-Host "Using .venv"
    & .\.venv\Scripts\python.exe -m streamlit run app.py
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    Write-Host "Using py -3"
    & py -3 -m streamlit run app.py
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "Using python"
    & python -m streamlit run app.py
} else {
    Write-Host "Python not found. Run setup-venv.ps1 or setup-venv.bat first."
    exit 1
}
