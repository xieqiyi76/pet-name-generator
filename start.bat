@echo off
chcp 65001 >nul
title Pet Name Generator V0.2
cd /d "%~dp0"

for /f "usebackq delims=" %%K in (`python "..\.temp\load_key.py"`) do set "ARK_API_KEY=%%K"

echo ================================================
echo   Pet Name Generator starting...
echo   After it says "Running on...", open browser:
echo   http://127.0.0.1:5000
echo   Close this window to STOP the server.
echo ================================================
echo.

python app.py

echo.
echo Server stopped. Press any key to close this window.
pause >nul