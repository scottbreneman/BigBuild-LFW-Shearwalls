@echo off
cd /d "%~dp0"
title Shear Wall Stack
if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  echo No .venv folder here, so using the Python found on your PATH.
  set "PY=py"
)
"%PY%" -c "import streamlit, pandas" 2>nul
if errorlevel 1 (
  echo Streamlit or pandas is missing. Installing them now...
  "%PY%" -m pip install streamlit pandas
)
echo.
echo Starting the app. Your browser should open. Close this window to stop it.
"%PY%" -m streamlit run src\ui\app.py
echo.
echo The app has stopped. If you see an error above, copy all of it.
echo To check the install, run:  "%PY%" check_app.py
pause
