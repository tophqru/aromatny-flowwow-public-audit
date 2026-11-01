param(
    [Parameter(Mandatory=$true)][string]$Manifest,
    [Parameter(Mandatory=$true)][string]$Baseline,
    [Parameter(Mandatory=$true)][string]$Output,
    [ValidateSet('chromium','msedge','chrome')][string]$Browser = 'msedge'
)
$ErrorActionPreference = 'Stop'
Write-Warning 'Legacy entry point: broad/full crawl disabled. Delegating to exact three-target pilot.'
& (Join-Path $PSScriptRoot 'run_pilot.ps1') -Manifest $Manifest -Baseline $Baseline -Output $Output -Browser $Browser
$crawlExitCode = $LASTEXITCODE
if ($crawlExitCode -ne 0) { exit $crawlExitCode }
exit 0
