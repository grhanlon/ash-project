# One-time: create .venv and pip install requirements (Windows VDI).
# Usage: powershell -ExecutionPolicy Bypass -File vdi\setup-venv.ps1
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m venv .venv
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m venv .venv
} else {
    Write-Host "Install Python 3.11+ first."
    exit 1
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -r requirements.txt

Write-Host ""
Write-Host "Done. For Bloomberg: .\.venv\Scripts\pip.exe install xbbg"
Write-Host "Start app: vdi\run-streamlit.bat or run-streamlit.ps1"
