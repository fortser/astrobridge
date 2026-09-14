@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run install.ps1 first. See README.md.
  exit /b 1
)
".venv\Scripts\python.exe" -m astrobridge %*
exit /b %errorlevel%
