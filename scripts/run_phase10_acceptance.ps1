param(
    [string]$EnvFile = ".env.acceptance",
    [ValidateRange(1, 6)][int]$Stage = 1,
    [switch]$WithBot,
    [switch]$EnableDqSandbox
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Create $EnvFile from .env.acceptance.example and use test-only Discord/OBS resources."
}

Get-Content -LiteralPath $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $parts = $line -split '=', 2
    if ($parts.Count -eq 2) { [Environment]::SetEnvironmentVariable($parts[0], $parts[1], 'Process') }
}

# `load_dotenv()` in the application must never fill absent acceptance settings
# from the operational .env. An explicitly empty process variable wins because
# python-dotenv does not override existing environment variables by default.
$isolatedSecrets = @(
    'DISCORD_BOT_TOKEN', 'DISCORD_GUILD_ID', 'STARTGG_API_TOKEN', 'GOOGLE_API_KEY',
    'CHALLONGE_API_KEY', 'CHALLONGE_OAUTH_CLIENT_ID',
    'CHALLONGE_OAUTH_CLIENT_SECRET', 'CHALLONGE_OAUTH_REDIRECT_URI'
)
foreach ($name in $isolatedSecrets) {
    if (-not [Environment]::GetEnvironmentVariable($name, 'Process')) {
        [Environment]::SetEnvironmentVariable($name, '', 'Process')
    }
}
# All application modules use `load_dotenv()` without an explicit acceptance path.
# Disable that implicit root-file load so this process can use only $EnvFile.
$env:PYTHON_DOTENV_DISABLED = '1'

if ($env:ACCEPTANCE_ENVIRONMENT -ne 'true') { throw 'ACCEPTANCE_ENVIRONMENT=true is required.' }
if ([string]::IsNullOrWhiteSpace($env:DATABASE_URL) -or $env:DATABASE_URL -notmatch '^postgres(ql)?://') {
    throw 'DATABASE_URL must identify an isolated acceptance PostgreSQL database.'
}
$env:PROVIDER_V2_CONTRACTS_ENABLED = if ($Stage -ge 1) { 'true' } else { 'false' }
$env:PROVIDER_COORDINATOR_ENABLED = if ($Stage -ge 2) { 'true' } else { 'false' }
$env:CHALLONGE_READ_ENABLED = if ($Stage -ge 3) { 'true' } else { 'false' }
$env:CHALLONGE_LOCAL_WORKFLOW_ENABLED = if ($Stage -ge 4) { 'true' } else { 'false' }
$env:CHALLONGE_SCORE_COMMANDS_ENABLED = if ($Stage -ge 5) { 'true' } else { 'false' }
# DQ is never enabled by stage alone.  It needs this explicit sandbox-only
# switch, an acceptance database, and score commands.  Production defaults
# remain false and a double DQ is still rejected by the API.
if ($EnableDqSandbox -and $Stage -lt 5) { throw 'DQ sandbox testing requires Stage 5 or later.' }
$env:CHALLONGE_DQ_COMMANDS_ENABLED = if ($EnableDqSandbox) { 'true' } else { 'false' }
# The bot resolves exactly one active test Discord account from the acceptance database.
# Multiple accounts require an explicit non-secret AITOB_DISCORD_ACCOUNT_ID process selector.

$python = Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Project .venv Python was not found.' }

Write-Host "Acceptance stage $Stage API: http://127.0.0.1:$($env:PORT) using PostgreSQL"
if ($WithBot) {
    Start-Process -FilePath $python -ArgumentList 'backend/bot/main.py' -WorkingDirectory (Join-Path $PSScriptRoot '..') -WindowStyle Hidden
}
& $python -m uvicorn backend.api.main:app --host 127.0.0.1 --port $env:PORT
