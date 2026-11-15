@echo off
rem Starts Smart-Shelf (Architecture A: Pipe-and-Filter) in your web browser.
rem The first run creates a private Python environment (.venv) and installs packages.
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py -3
%PY% -c "import sys; sys.exit(sys.version_info < (3, 12))" 2>nul
if errorlevel 1 (
  echo Smart-Shelf needs Python 3.12 or newer: https://www.python.org/downloads/
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  echo First run: setting up Python packages ^(about a minute^)...
  %PY% -m venv .venv || goto failed
  .venv\Scripts\python -m pip install -r requirements.txt || goto failed
)
echo Smart-Shelf is starting at http://localhost:8501  ^(close this window to stop it^)
start "" cmd /c "timeout /t 4 >nul & start http://localhost:8501"
.venv\Scripts\python -m streamlit run smart_shelf\ui\app.py --server.headless true --server.port 8501
pause
exit /b 0
:failed
echo Setup failed. See the messages above.
pause
exit /b 1
