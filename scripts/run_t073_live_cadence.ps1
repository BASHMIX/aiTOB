param(
    [string]$EnvFile = ".env.acceptance"
)

$ErrorActionPreference = "Stop"
$values = @{}
Get-Content -LiteralPath $EnvFile | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') {
        $values[$Matches[1].Trim()] = $Matches[2].Trim()
    }
}

$headers = @{ "X-Hub-Password" = $values["HUB_PASSWORD"] }
$env:DATABASE_URL = $values["DATABASE_URL"]
if ([string]::IsNullOrWhiteSpace($env:DATABASE_URL) -or $env:DATABASE_URL -notmatch '^postgres(ql)?://') {
    throw "The acceptance env file must contain a PostgreSQL DATABASE_URL."
}
$tournament = @(
    (Invoke-RestMethod -Headers $headers -Uri "http://127.0.0.1:8001/api/tournaments").tournaments |
    Where-Object { $_.provider_type -eq "challonge" }
)[0]
if (-not $tournament) { throw "No acceptance Challonge tournament." }

$slug = [uri]::EscapeDataString([string]$tournament.slug)
$settingsUrl = "http://127.0.0.1:8001/api/tournaments/$slug/settings"
$statusUrl = "http://127.0.0.1:8001/api/tournaments/$slug/sync-status"
function Get-ChallongeUsageCount {
    # The acceptance database records one row per coordinator-owned provider
    # request.  It is a stronger cadence proof than a timestamp alone: a stale
    # snapshot can legitimately leave the visible projection unchanged.
    $script = @'
import os
import psycopg
with psycopg.connect(os.environ["DATABASE_URL"]) as db:
    print(db.execute("SELECT COUNT(*) FROM provider_api_usage WHERE provider_type='challonge'").fetchone()[0])
'@
    return [int]($script | .\.venv\Scripts\python.exe -)
}

# Stop any previous live loop before starting the measured one.
Invoke-RestMethod -Headers $headers -Uri $settingsUrl -Method Patch -ContentType "application/json" -Body '{"challonge_sync_mode":"economy"}' | Out-Null
Start-Sleep -Seconds 2
$beforeLive = Get-ChallongeUsageCount
Invoke-RestMethod -Headers $headers -Uri $settingsUrl -Method Patch -ContentType "application/json" -Body '{"challonge_sync_mode":"live"}' | Out-Null
Start-Sleep -Seconds 310

$live = Invoke-RestMethod -Headers $headers -Uri $statusUrl
$afterLive = Get-ChallongeUsageCount
if ($live.mode -ne "live" -or $afterLive -le $beforeLive) {
    throw "Live cadence did not issue a coordinator-owned Challonge request."
}

Invoke-RestMethod -Headers $headers -Uri $settingsUrl -Method Patch -ContentType "application/json" -Body '{"challonge_sync_mode":"economy"}' | Out-Null
$economy = Invoke-RestMethod -Headers $headers -Uri $statusUrl
$beforeEconomy = Get-ChallongeUsageCount
Start-Sleep -Seconds 310

$after = Invoke-RestMethod -Headers $headers -Uri $statusUrl
$afterEconomy = Get-ChallongeUsageCount
if ($after.mode -ne "economy") { throw "Economy mode was not retained." }
if ($afterEconomy -ne $beforeEconomy) {
    throw "Scheduled provider sync continued after Economy."
}

Write-Output "live_five_minute_cadence=pass"
Write-Output "economy_schedule_stop=pass"
