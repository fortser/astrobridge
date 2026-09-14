@echo off
setlocal

title OpenAI Codex UTF-8
chcp 65001 >nul

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

where codex.cmd >nul 2>nul
if not errorlevel 1 (
    call codex.cmd %*
    set "CODEX_EXIT=%ERRORLEVEL%"
    endlocal & exit /b %CODEX_EXIT%
)

if exist "%APPDATA%\npm\codex.cmd" (
    call "%APPDATA%\npm\codex.cmd" %*
    set "CODEX_EXIT=%ERRORLEVEL%"
    endlocal & exit /b %CODEX_EXIT%
)

echo [ERROR] codex.cmd not found.
echo Install Codex or add C:\Users\Taras\AppData\Roaming\npm to PATH.
endlocal & exit /b 1
