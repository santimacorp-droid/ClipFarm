@echo off
title ClipFarm Studio Launcher
setlocal EnableDelayedExpansion

cd /d "%~dp0"

echo ===================================================
echo             ClipFarm Studio Launcher
echo ===================================================

:: Check for virtual environment python
if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=python"
    ) else (
        echo [ERROR] Python not found. Please install Python 3.10+ from python.org
        pause
        exit /b 1
    )
)

echo Starting ClipFarm Studio...
"%PYTHON_EXE%" "%~dp0desktop_app.py" %*

if !errorlevel! neq 0 (
    echo.
    echo [INFO] ClipFarm has closed or encountered an error.
    pause
)
