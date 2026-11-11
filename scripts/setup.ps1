# Prepara o ambiente: cria .venv e instala as dependencias.
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip -q
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
Write-Host "Pronto. Inicie com: run.bat"
