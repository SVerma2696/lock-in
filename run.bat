@echo off
REM ---------------------------------------------------------------------------
REM This double-click file starts Lock In for you.
REM
REM It uses pythonw.exe so no black terminal window pops up behind the app.
REM If something breaks and you want to see the error messages, change
REM "pythonw" below to "python" instead.
REM ---------------------------------------------------------------------------
cd /d "%~dp0"

where pythonw >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH.
    echo Install it from python.org and tick "Add Python to PATH".
    pause
    exit /b 1
)

start "" pythonw main.py