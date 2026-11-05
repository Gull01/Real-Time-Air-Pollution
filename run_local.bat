@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Real-Time Air Pollution Monitor (local)

rem ---- find Python 3
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python 3 was not found. Install Python 3.10 or newer from python.org
  echo and tick "Add python.exe to PATH" during setup, then run this again.
  pause
  exit /b 1
)

rem ---- private environment so nothing else on your PC is touched
if not exist ".venv\Scripts\python.exe" (
  echo Creating a virtual environment in .venv ...
  %PY% -m venv .venv
  if errorlevel 1 ( pause & exit /b 1 )
)
set "VPY=.venv\Scripts\python.exe"

echo Installing requirements (first run takes a minute or two) ...
"%VPY%" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 ( echo Install failed, see the message above. & pause & exit /b 1 )

rem ---- API keys (only asked once, saved to .streamlit\secrets.toml which git ignores)
if exist ".streamlit\secrets.toml" goto run
echo.
echo Paste your AQICN token (the same one in your Streamlit Cloud secrets),
echo or just press Enter to run on CAMS model data only.
set "TOKEN="
set /p "TOKEN=AQICN token: "
echo Optional: paste an OpenAQ API key, or press Enter to skip.
set "OAQ="
set /p "OAQ=OpenAQ key: "
(
  echo AQICN_API_TOKEN = "!TOKEN!"
  echo OPENAQ_API_KEY = "!OAQ!"
) > ".streamlit\secrets.toml"
echo Saved to .streamlit\secrets.toml

:run
rem ---- pick the first free port from 8611 upward (8501 and others may be in use)
set "PORT="
for /f "usebackq delims=" %%p in (`"%VPY%" -c "import socket as S;c=lambda p:(lambda s:(s.settimeout(0.3),s.connect_ex(('127.0.0.1',p)))[1])(S.socket());print(next(p for p in range(8611,8700) if c(p)))"`) do set "PORT=%%p"
if not defined PORT set "PORT=8611"
echo.
echo Starting the app at http://localhost:!PORT!  (close this window to stop it)
"%VPY%" -m streamlit run AP.py --server.headless false --server.port !PORT!
pause
