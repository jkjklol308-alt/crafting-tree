@echo off
rem Crafting Tree - Create Mod Factory Manager
rem Launches the app (creates a .venv on first run if PySide6 is missing)
title Crafting Tree
cd /d "%~dp0"

echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python 3.9+ was not found on PATH.
    echo Install Python from python.org, then run this again.
    pause
    exit /b 1
)

python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo PySide6 not found in system Python - creating a virtual environment...
    if not exist .venv (
        python -m venv .venv
        if errorlevel 1 (
            echo Could not create a virtual environment.
            pause
            exit /b 1
        )
    )
    echo Installing dependencies (this can take a few minutes)...
    .venv\Scripts\python.exe -m pip install --upgrade pip >nul
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Dependency installation failed. Check the error messages above.
        pause
        exit /b 1
    )
    .venv\Scripts\python.exe app.py
    goto :finish
)

python app.py

:finish
pause
