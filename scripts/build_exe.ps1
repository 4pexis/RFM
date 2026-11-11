# Gera o executável Windows em dist\RFM\RFM.exe (PyInstaller).
#   powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Ambiente virtual nao encontrado. Execute scripts\setup.ps1 primeiro." }

& $python -m pip install -q -r requirements-dev.txt
& $python -m PyInstaller --noconfirm --clean --windowed --name RFM `
    --icon assets\icon.ico `
    --add-data "assets;assets" `
    --add-data "app\database\migrations;app\database\migrations" `
    --collect-submodules app.game_modules `
    --hidden-import logging.config `
    app\main.py
if ($LASTEXITCODE -ne 0) { throw "Falha no PyInstaller." }

Write-Host ""
Write-Host "Executavel gerado: $root\dist\RFM\RFM.exe"
Write-Host "Os dados do executavel ficam em %LOCALAPPDATA%\RFM"
