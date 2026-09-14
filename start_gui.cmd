@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\astrobridge-gui.exe" (
  echo Run install.ps1 first. See README.md.
  pause
  exit /b 1
)
start "" ".venv\Scripts\astrobridge-gui.exe"
