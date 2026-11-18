param([int]$Port = 8000, [switch]$Demo)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create a virtual environment. Install Python 3.10 or newer.' }
}
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $projectPython -m pip install --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check your internet connection.' }
& $projectPython manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw 'Database setup failed.' }
if ($Demo) {
    & $projectPython manage.py seed_demo
    if ($LASTEXITCODE -ne 0) { throw 'Demo data setup failed.' }
}
Write-Host "Open http://127.0.0.1:$Port/ in your browser. Press Ctrl+C to stop."
& $projectPython manage.py runserver "127.0.0.1:$Port"
