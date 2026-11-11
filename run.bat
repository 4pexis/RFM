@echo off
rem Inicia o Roblox Farm Manager (sem janela de console).
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Ambiente nao configurado. Execute: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m app.main
