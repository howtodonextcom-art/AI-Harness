<#
.SYNOPSIS
    Starts the market data stack in the right order: FTMO MT5 terminal -> supervisor (collector,
    API, optional dashboard) -> health check. Safe to run repeatedly: it never starts a duplicate.

.PARAMETER Dashboard
    Also supervise the dashboard (needs `npm run build` once in apps/dashboard).
.PARAMETER Open
    Open http://127.0.0.1:3000/market in the browser when the stack is healthy (needs -Dashboard
    or an already running dashboard).
.PARAMETER NoTerminal
    Do not start the MT5 terminal (it is already running, or you start it yourself).
.PARAMETER TerminalPath
    terminal64.exe of the FTMO terminal.
.PARAMETER WaitSeconds
    How long to wait for the first healthy collector update (default 120).
.EXAMPLE
    .\scripts\start_market_stack.ps1 -Dashboard -Open
#>
[CmdletBinding()]
param(
    [switch]$Dashboard,
    [switch]$Open,
    [switch]$NoTerminal,
    [string]$TerminalPath = 'C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe',
    [int]$WaitSeconds = 120
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RunDir = Join-Path $Repo 'data\run'
$Market = Join-Path $Repo 'data\market'
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

function Test-PidAlive([string]$File) {
    if (-not (Test-Path $File)) { return $false }
    $id = 0
    if (-not [int]::TryParse((Get-Content $File -Raw).Trim(), [ref]$id)) { return $false }
    return [bool](Get-Process -Id $id -ErrorAction SilentlyContinue)
}

# 1. Terminal (a desktop application: started in this user session, never as a service)
if (-not $NoTerminal) {
    if (Get-Process -Name terminal64 -ErrorAction SilentlyContinue) {
        Write-Host '[1/3] MT5 terminal already running.'
    } elseif (Test-Path $TerminalPath) {
        Write-Host '[1/3] Starting the FTMO MT5 terminal...'
        Start-Process -FilePath $TerminalPath | Out-Null
        $deadline = (Get-Date).AddSeconds(60)
        while (-not (Get-Process -Name terminal64 -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 2
        }
        if (-not (Get-Process -Name terminal64 -ErrorAction SilentlyContinue)) { throw 'The MT5 terminal did not start.' }
        Start-Sleep -Seconds 15   # give it time to log in and synchronise; the collector keeps retrying anyway
    } else {
        throw "terminal64.exe not found at $TerminalPath (pass -TerminalPath, or -NoTerminal)."
    }
} else {
    Write-Host '[1/3] Skipping the terminal (-NoTerminal).'
}

# 2. Supervisor (one owner for collector + API + dashboard)
$pidFile = Join-Path $RunDir 'supervisor.pid'
if (Test-PidAlive $pidFile) {
    Write-Host '[2/3] Supervisor already running (no duplicate started).'
} else {
    $py = Join-Path $Repo '.venv\Scripts\python.exe'
    if (-not (Test-Path $py)) { throw 'Run `uv sync --extra mt5` first (.venv is missing).' }
    $args = @('scripts\run_market_stack.py')
    if ($Dashboard) { $args += '--dashboard' }
    Write-Host '[2/3] Starting the supervisor (collector, API' $(if ($Dashboard) { ', dashboard' }) ').'
    Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory $Repo -WindowStyle Hidden | Out-Null
}

# 3. Wait for a fresh collector heartbeat, then run the health gate
$status = Join-Path $Market 'collector_status.json'
$deadline = (Get-Date).AddSeconds($WaitSeconds)
$fresh = $false
while ((Get-Date) -lt $deadline) {
    if (Test-Path $status) {
        $age = ((Get-Date) - (Get-Item $status).LastWriteTime).TotalSeconds
        if ($age -lt 20) { $fresh = $true; break }
    }
    Start-Sleep -Seconds 3
}
if (-not $fresh) {
    Write-Warning "No fresh collector update within $WaitSeconds s. Run .\scripts\status_market_stack.ps1 to see why."
}
Push-Location $Repo
try {
    & uv run python scripts/check_market_data_health.py --allow-degraded | Select-String '"health"|"market_status"|"collector_running"' | ForEach-Object { Write-Host $_.Line.Trim() }
    $code = $LASTEXITCODE
} finally { Pop-Location }
if ($Open) { Start-Process 'http://127.0.0.1:3000/market' }
if ($code -ne 0) { Write-Warning "health gate exit code $code (see status_market_stack.ps1)"; exit $code }
Write-Host '[3/3] Market data stack is healthy.'
