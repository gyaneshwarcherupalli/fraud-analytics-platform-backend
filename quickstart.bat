@echo off
REM Quick Start Script for Windows
REM Run this script to set up and start the Fraud Analytics Platform

echo ============================================================
echo Fraud Analytics Platform - Quick Start
echo ============================================================

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    exit /b 1
)

echo.
echo Creating virtual environment...
python -m venv venv

echo.
echo Activating virtual environment...
call .\venv\Scripts\activate.bat

echo.
echo Installing dependencies...
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

echo.
echo Configuration...
if not exist .env (
    echo Creating .env file from template...
    copy .env.example .env
    echo Please update .env with your configuration before running the app
) else (
    echo .env file already exists
)

echo.
echo ============================================================
echo Setup Complete!
echo ============================================================
echo.
echo Next steps:
echo 1. Update .env with your configuration (database, API keys, etc.)
echo 2. Run the application:
echo    python -m uvicorn app.main:app --reload
echo 3. Open http://localhost:8000 in your browser
echo 4. API documentation: http://localhost:8000/docs
echo.
echo For more information, see README.md
echo ============================================================
