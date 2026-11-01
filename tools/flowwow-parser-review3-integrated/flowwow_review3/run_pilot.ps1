param(
    [Parameter(Mandatory=$true)][string]$Manifest,
    [Parameter(Mandatory=$true)][string]$Baseline,
    [Parameter(Mandatory=$true)][string]$Output,
    [ValidateSet('chromium','msedge','chrome')][string]$Browser = 'msedge',
    [switch]$RetryFailed,
    [switch]$RecheckUnverified
)
$ErrorActionPreference = 'Stop'
$Manifest = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Manifest)
$Baseline = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Baseline)
$Output = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Output)
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'First run .\setup_windows.ps1' }
Write-Warning 'Strict three-target read-only pilot. DOM expansion/gallery clicks NOT_PROVEN; PARTIAL is not success.'
$extra = @()
if ($RetryFailed) { $extra += '--retry-failed' }
if ($RecheckUnverified) { $extra += '--recheck-unverified' }
& $python capture.py crawl --browser $Browser --pilot-manifest $Manifest --baseline $Baseline --output $Output --max-products 3 --max-categories 1 --max-load-cycles 5 --max-scroll-steps 40 --pause-min 5 --pause-max 12 @extra
$crawlExitCode = $LASTEXITCODE
# Export diagnostics even on access block, but never mask capture failure.
& $python capture.py export --output $Output
$exportExitCode = $LASTEXITCODE
if ($crawlExitCode -ne 0) { exit $crawlExitCode }
if ($exportExitCode -ne 0) { exit $exportExitCode }
Write-Host 'Review pilot-acceptance.json. No publication or import is authorized.'
exit 0
