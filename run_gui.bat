@echo off
REM Quick start script for Chess Master GUI

echo.
echo ================================
echo   Chess Master GUI
echo ================================
echo.
echo Checking dependencies...

python -m pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -q -r requirements-gui.txt
)

echo.
echo Starting server on http://localhost:5000
echo.
echo Press Ctrl+C to stop
echo.

python -m uvicorn app:socket_app --host 0.0.0.0 --port 5000
