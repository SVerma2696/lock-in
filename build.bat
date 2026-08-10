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

REM Make a real Windows icon file (.ico) out of the app's own picture.
REM An .exe's icon has to be this specific format -- a plain .png won't
REM work here, even though a .png works fine for the window itself.
python -c "from lock_in.visuals import load_app_icon; load_app_icon().save('lock_in_icon.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"

pyinstaller --noconfirm --onefile --windowed ^
    --name "Lock In" ^
    --icon lock_in_icon.ico ^
    --add-data "lock_in/assets;lock_in/assets" ^
    --collect-all customtkinter ^
    --hidden-import win32gui ^
    --hidden-import win32process ^
    --hidden-import win32con ^
    --hidden-import psutil ^
    main.py

echo.
echo Built: dist\Lock In.exe
pause