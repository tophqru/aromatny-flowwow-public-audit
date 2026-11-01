$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
Write-Host 'Flowwow: creating isolated Python virtual environment...' -ForegroundColor Cyan
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $py) {
        & py -3 -m venv .venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv .venv
    } else {
        throw 'Python 3.10+ missing. Install Python from python.org, then re-run.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create .venv' }
}
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $python -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ required' }
& $python -m pip install --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
Write-Host 'Installing isolated Playwright Chromium (browser binaries)...' -ForegroundColor Cyan
& $python -m playwright install chromium
$browserReady = ($LASTEXITCODE -eq 0)
if (-not $browserReady) { Write-Warning 'Bundled Chromium unavailable. If Microsoft Edge is installed, use .\run_trial.ps1 -Browser msedge.' }
& $python capture.py doctor
if ($LASTEXITCODE -ne 0) { throw 'Doctor check failed' }
if ($browserReady) {
    Write-Host 'SETUP SUCCESS. Run .\run_trial.ps1 next.' -ForegroundColor Green
} else {
    Write-Host 'SETUP PARTIAL: dependencies installed, but no bundled Chromium. Use -Browser msedge only if Edge is already installed.' -ForegroundColor Yellow
    exit 1
}
