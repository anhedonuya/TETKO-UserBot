@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TETKO UserBot

if exist "venv\.installed" (
    if exist "venv\Scripts\python.exe" goto run
)

echo ========================================================
echo        TETKO UserBot - Setup
echo ========================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo [!] Python not found! Install Python 3.10+ and add to PATH.
        pause
        exit /b 1
    )
    set "PY_CMD=py -3"
) else (
    set "PY_CMD=python"
)

if not exist "venv\Scripts\python.exe" (
    echo [*] Creating virtual environment venv...
    %PY_CMD% -m venv venv
    if %errorlevel% neq 0 (
        echo [!] Failed to create venv.
        pause
        exit /b 1
    )
    echo [+] Venv created.
    echo.
)

echo [*] Installing requirements...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [!] Error installing dependencies.
    pause
    exit /b 1
)

echo installed > "venv\.installed"
echo.
echo [+] Setup complete!
echo.

:run
echo [*] Starting TETKO UserBot...
call venv\Scripts\activate.bat
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [!] Bot exited.
    pause
)
