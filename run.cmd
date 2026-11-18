@echo off
setlocal
pushd "%~dp0"
title ReLoop - Local Development Server
set "RELOOP_PY=%~dp0.venv\Scripts\python.exe"
if exist "%RELOOP_PY%" goto ready
if exist "%~dp0..\..\work\.venv\Scripts\python.exe" (
    set "RELOOP_PY=%~dp0..\..\work\.venv\Scripts\python.exe"
    goto ready
)
echo Setting up Python dependencies for the first run...
python -m venv .venv
if errorlevel 1 goto failed
"%RELOOP_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto failed
:ready
"%RELOOP_PY%" manage.py migrate --noinput
if errorlevel 1 goto failed
"%RELOOP_PY%" manage.py seed_demo
if errorlevel 1 goto failed
echo.
echo Open http://127.0.0.1:8000/ in your browser.
echo Keep this window open while using ReLoop. Press Ctrl+C to stop.
echo.
"%RELOOP_PY%" -u manage.py runserver 127.0.0.1:8000 --noreload
if errorlevel 1 goto failed
popd
exit /b 0
:failed
echo.
echo ReLoop could not start. Read the error above or see README.md.
pause
popd
exit /b 1
