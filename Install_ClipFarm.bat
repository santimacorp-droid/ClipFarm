@echo off
title ClipFarm Studio Setup Wizard
setlocal EnableDelayedExpansion

cd /d "%~dp0"

echo ===================================================
echo         ClipFarm Studio - Setup Wizard
echo ===================================================

if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=python"
    ) else (
        echo [ERROR] Python 3.10+ is required. Please install Python from python.org
        pause
        exit /b 1
    )
)

"%PYTHON_EXE%" "%~dp0installer_wizard.py" %*

if !errorlevel! neq 0 (
    echo.
    echo Setup encountered an issue or was cancelled.
    pause
)
