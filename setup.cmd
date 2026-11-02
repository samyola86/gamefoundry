@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3.11 bootstrap.py
) else (
  python bootstrap.py
)
if errorlevel 1 (
  echo Setup failed. Install Python 3.11, then retry. See README.md.
  pause
  exit /b 1
)
echo Setup complete. Open Start-GameFoundry.cmd.
pause
