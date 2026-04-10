# cwm - ConnectWise Manage TUI launcher for Windows
# Requires: Python 3.10+, Windows Terminal

$ErrorActionPreference = "Stop"

$venvPath = Join-Path $PSScriptRoot ".venv"

if (-not (Test-Path (Join-Path $venvPath "Scripts" "python.exe"))) {
    Write-Host "Creating virtual environment..."
    python -m venv $venvPath
    & (Join-Path $venvPath "Scripts" "pip.exe") install -e $PSScriptRoot
}

& (Join-Path $venvPath "Scripts" "cwm.exe") @args
