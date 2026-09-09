<#
Starts aiTOB for hands-on local testing without Codex's in-app browser.
It keeps the services detached, then opens the user's default desktop browser.

Usage (from the repository root):
  .\start-local.ps1
#>

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment Python was not found: $python"
}

Push-Location $projectRoot
try {
    # Start outside the calling shell's job. This matters when the launcher is
    # invoked from Codex: its short-lived command host must not terminate the
    # API and Discord Python processes when it returns.
    Start-Process -FilePath $python -ArgumentList @('run.py', '--detached') -WorkingDirectory $projectRoot -WindowStyle Hidden

    $deadline = (Get-Date).AddSeconds(20)
    do {
        try {
            $health = Invoke-RestMethod 'http://127.0.0.1:8001/health' -TimeoutSec 2
            if ($health.status -eq 'ok') { break }
        } catch { }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    if (-not $health -or $health.status -ne 'ok') {
        throw 'API did not become ready within 20 seconds.'
    }

    Start-Process 'http://127.0.0.1:5173/admin/hub'
    Write-Host 'aiTOB is ready in your default browser: http://127.0.0.1:5173/admin/hub' -ForegroundColor Green
    Write-Host 'Stop later with: .\.venv\Scripts\python.exe stop.py' -ForegroundColor Yellow
} finally {
    Pop-Location
}
