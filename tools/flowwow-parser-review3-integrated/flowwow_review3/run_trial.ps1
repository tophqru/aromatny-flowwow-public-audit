param([ValidateSet("chromium", "msedge", "chrome")][string]$Browser = "chromium")
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'First run .\setup_windows.ps1' }
Write-Host 'Trial: one visible local browser, shop homepage + 2 priority products.' -ForegroundColor Cyan
& $python capture.py crawl --browser $Browser --max-categories 1 --max-products 2 --max-load-cycles 5 --pause-min 5 --pause-max 12
$crawlExitCode = $LASTEXITCODE
if ($crawlExitCode -ne 0) { Write-Warning "Capture finished with exit code $crawlExitCode (access/error). Existing data remain in output/." }
& $python capture.py export
$exportExitCode = $LASTEXITCODE
if ($exportExitCode -ne 0) { throw "Report export failed (exit $exportExitCode)" }
Write-Host 'Review output\review\report.html and output\review\products.json.' -ForegroundColor Yellow

if ($crawlExitCode -ne 0) { exit $crawlExitCode }
