$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ is required.' }
}
& ./.venv/Scripts/python.exe -m pip --isolated --disable-pip-version-check --no-input install --index-url https://pypi.org/simple --timeout 30 --retries 2 --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check network/proxy configuration.' }
& ./.venv/Scripts/python.exe -m pip --isolated --disable-pip-version-check --no-input install --index-url https://pypi.org/simple --timeout 30 --retries 2 --no-build-isolation -e '.[gui,dev]'
if ($LASTEXITCODE -ne 0) { throw 'AstroBridge installation failed.' }
& ./.venv/Scripts/python.exe -m astrobridge doctor
Write-Host 'Ready. Launch start_gui.cmd or use astrobridge.cmd --help.'
