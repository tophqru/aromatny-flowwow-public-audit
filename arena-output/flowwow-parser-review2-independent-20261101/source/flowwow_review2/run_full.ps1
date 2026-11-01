param([ValidateSet("chromium", "msedge", "chrome")][string]$Browser = "chromium")
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'First run .\setup_windows.ps1' }
Write-Host 'Full single-session crawl. It still cannot claim seller-wide completeness without verification.' -ForegroundColor Cyan
& $python capture.py crawl --browser $Browser --max-categories 0 --max-products 0 --download-new-media --pause-min 5 --pause-max 12
$crawlExitCode = $LASTEXITCODE
if ($crawlExitCode -ne 0) { Write-Warning "Capture stopped with exit code $crawlExitCode. No hidden retries. Resume manually later." }
& $python capture.py export
$exportExitCode = $LASTEXITCODE
if ($exportExitCode -ne 0) { throw "Report export failed (exit $exportExitCode)" }
Write-Host 'Review output\review\report.html; do not publish the raw output/ folder.' -ForegroundColor Yellow

if ($crawlExitCode -ne 0) { exit $crawlExitCode }
