<#
.SYNOPSIS
    One-glance status of the market data stack and, when something is wrong, why the UI is stale.
.EXAMPLE
    .\scripts\status_market_stack.ps1
#>
[CmdletBinding()]
param([int]$ApiPort = 8000, [int]$DashboardPort = 3000)

Set-StrictMode -Off
$ErrorActionPreference = 'Continue'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Run = Join-Path $Repo 'data\run'
$Market = Join-Path $Repo 'data\market'

function Read-Json([string]$Path) {
    if (-not (Test-Path $Path)) { return $null }
    try { return Get-Content $Path -Raw | ConvertFrom-Json } catch { return $null }
}
function Test-Port([int]$Port) {
    try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', $Port); $c.Close(); return $true } catch { return $false }
}
function Age([string]$Iso) {
    if (-not $Iso) { return $null }
    try { return [math]::Round(((Get-Date).ToUniversalTime() - [datetime]::Parse($Iso).ToUniversalTime()).TotalSeconds) } catch { return $null }
}

$problems = @()
$mt5 = Get-Process -Name terminal64 -ErrorAction SilentlyContinue
$sup = Read-Json (Join-Path $Run 'supervisor.json')
$supPid = $null
$supFile = Join-Path $Run 'supervisor.pid'
if (Test-Path $supFile) { $supPid = [int](Get-Content $supFile -Raw).Trim() }
$supAlive = ($null -ne $supPid) -and [bool](Get-Process -Id $supPid -ErrorAction SilentlyContinue)
$col = Read-Json (Join-Path $Market 'collector_status.json')
$colAge = if ($col) { Age $col.updated_at } else { $null }
$apiUp = Test-Port $ApiPort
$webUp = Test-Port $DashboardPort

"{0,-22}{1}" -f 'MT5 terminal', $(if ($mt5) { "RUNNING (pid $($mt5[0].Id))" } else { 'NOT RUNNING' })
"{0,-22}{1}" -f 'Supervisor', $(if ($supAlive) { "RUNNING (pid $supPid)" } else { 'NOT RUNNING' })
if ($sup) { foreach ($p in $sup.children.PSObject.Properties) { "{0,-22}{1}" -f ('  ' + $p.Name), $(if ($p.Value.alive) { "alive pid $($p.Value.pid), restarts $($p.Value.restarts)" } else { "DOWN (last exit $($p.Value.last_exit), restarts $($p.Value.restarts))" }) } }
"{0,-22}{1}" -f 'Collector heartbeat', $(if ($null -ne $colAge) { "$colAge s ago" } else { 'no status file' })
"{0,-22}{1}" -f ('API :' + $ApiPort), $(if ($apiUp) { 'listening' } else { 'NOT listening' })
"{0,-22}{1}" -f ('Dashboard :' + $DashboardPort), $(if ($webUp) { 'listening' } else { 'NOT listening' })
if ($col) {
    "{0,-22}{1}" -f 'Feed health', "$($col.health)  (market: $($col.market_status))"
    if ($col.quote) { "{0,-22}{1}" -f 'Quote', "bid $($col.quote.bid) / ask $($col.quote.ask), age $([math]::Round([double]$col.quote.age_seconds,1)) s" }
    "{0,-22}{1}" -f 'Last M1 close', $col.last_closed.M1
    "{0,-22}{1}" -f 'Freshness', (($col.freshness.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ' ')
    if ($col.tick_store -and $col.tick_store.enabled) { "{0,-22}{1}" -f 'Tick store', "covered until $($col.tick_store.covered_until)" }
    if ($col.disk) { "{0,-22}{1}" -f 'Disk', "$($col.disk.level), $($col.disk.free_gb) GB free" }
}

if (-not $mt5) { $problems += 'The MT5 terminal is not running: start it (or run start_market_stack.ps1), then log in.' }
if (-not $supAlive) { $problems += 'The supervisor is not running: run .\scripts\start_market_stack.ps1.' }
elseif ($null -ne $colAge -and $colAge -gt 60) { $problems += "The collector has not updated for $colAge s (it is stuck or the terminal is not connected): see data\logs\collector.log." }
if ($col -and $col.health -ne 'GOOD') { $problems += "Feed health is $($col.health): $($col.reasons -join '; ')" }
if ($sup) { foreach ($p in $sup.children.PSObject.Properties) { if (-not $p.Value.alive) { $problems += "Supervised child '$($p.Name)' is DOWN (last exit $($p.Value.last_exit)): see data\logs\$($p.Name).log." } } }
if (-not $apiUp) { $problems += 'The API is down: the web page cannot load data.' }
Write-Host ''
if ($problems.Count -eq 0) { Write-Host 'OK: everything is running and healthy.' }
else { Write-Host 'WHY THE UI MAY BE STALE:'; $problems | ForEach-Object { Write-Host " - $_" } }
exit $(if ($problems.Count -eq 0) { 0 } else { 1 })
