@echo off
title LIFE OS
cd /d "%~dp0"
echo.
echo  ==============================
echo   LIFE OS - Living World Lab
echo  ==============================
echo.

rem Find Python: the "py" launcher first, then "python"
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY (python --version >nul 2>nul && set "PY=python")
if not defined PY (py --version >nul 2>nul && set "PY=py")
if not defined PY goto nopython
echo  Using Python:
%PY% --version

rem First run only: make a private copy of the libraries the app needs
if exist ".venv\installed.ok" goto run
echo  First time setup. This takes a minute or two and needs internet.
echo.
if exist ".venv" rmdir /s /q ".venv"
%PY% -m venv .venv
if errorlevel 1 goto nopython
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo ok> ".venv\installed.ok"
echo.
echo  Setup finished.

:run
echo.
echo  LIFE OS is opening in your web browser.
echo  Keep this window open while you use it. Close it to stop LIFE OS.
echo  (If the browser didn't open, go to http://127.0.0.1:8765)
echo.
".venv\Scripts\python.exe" run.py
echo.
echo  LIFE OS stopped.
pause
exit /b

:nopython
echo  Couldn't find Python on this computer.
echo  Install it from https://www.python.org/downloads/
echo  On the first screen of the installer, tick "Add python.exe to PATH".
echo  Then double-click this file again.
pause
exit /b

:failed
echo.
echo  Setup didn't finish. Check your internet connection and double-click this file again.
if exist ".venv" rmdir /s /q ".venv"
pause
exit /b
