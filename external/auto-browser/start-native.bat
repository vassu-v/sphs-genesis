@echo off
REM Start Auto Browser natively (no Docker). Run this in YOUR OWN terminal window
REM so the Chromium window it launches appears on your desktop.
cd /d "%~dp0controller"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
