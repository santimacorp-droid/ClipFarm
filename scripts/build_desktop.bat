@echo off
setlocal

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python is required to run build_desktop.py
    exit /b 1
)

python "%~dp0build_desktop.py" %*
