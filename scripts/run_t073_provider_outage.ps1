param(
    [ValidateRange(1, 6)][int]$Stage = 6
)

# Process-scoped only: the unreachable proxy simulates provider-network loss
# without changing any credential or the machine firewall configuration.
$env:HTTPS_PROXY = "http://127.0.0.1:9"
$env:HTTP_PROXY = "http://127.0.0.1:9"
$env:ALL_PROXY = "http://127.0.0.1:9"
& $PSScriptRoot\run_phase10_acceptance.ps1 -Stage $Stage
