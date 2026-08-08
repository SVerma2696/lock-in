@echo off
REM ---------------------------------------------------------------------------
REM This turns the app into one "Lock In.exe" file, put inside the dist folder.
REM
REM We keep --collect-all customtkinter here on purpose. The app's look and
REM feel (colors, fonts) live in extra files that the builder wouldn't grab
REM by itself, and skipping this makes the finished .exe crash right away.
REM ---------------------------------------------------------------------------
cd /d "%~dp0"

pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed ^
    --name "Lock In" ^
    --collect-all customtkinter ^
    --hidden-import win32gui ^
    --hidden-import win32process ^
    --hidden-import win32con ^
    --hidden-import psutil ^
    main.py

echo.
echo Built: dist\Lock In.exe
pause