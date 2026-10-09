<#
.SYNOPSIS
    Stops the market data stack (dashboard, API, collector) through its supervisor. Data is kept.
    The MT5 terminal is NOT touched unless -StopTerminal is given explicitly.

.PARAMETER StopTerminal
    Also close the MT5 terminal (asks it to close its main window; never kills it).
.EXAMPLE
    .\scripts\stop_market_stack.ps1
#>
[CmdletBinding()]
param([switch]$StopTerminal)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RunDir = Join-Path $Repo 'data\run'
$pidFile = Join-Path $RunDir 'supervisor.pid'
$stopFile = Join-Path $RunDir 'supervisor.stop'

function Get-AlivePid([string]$File) {
    if (-not (Test-Path $File)) { return $null }
    $id = 0
    if (-not [int]::TryParse((Get-Content $File -Raw).Trim(), [ref]$id)) { return $null }
    if (Get-Process -Id $id -ErrorAction SilentlyContinue) { return $id }
    return $null
}

$supervisor = Get-AlivePid $pidFile
if ($null -eq $supervisor) {
    Write-Host 'Supervisor is not running.'
} else {
    New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
    Set-Content -Path $stopFile -Value 'stop' -Encoding ascii
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Process -Id $supervisor -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 1 }
    if (Get-Process -Id $supervisor -ErrorAction SilentlyContinue) {
        Write-Warning 'Supervisor did not stop in 30 s; stopping its process.'
        Stop-Process -Id $supervisor -Force
    }
    Write-Host 'Supervisor and its children stopped; data preserved.'
}
if ($StopTerminal) {
    $mt5 = Get-Process -Name terminal64 -ErrorAction SilentlyContinue
    if ($mt5) { $mt5 | ForEach-Object { [void]$_.CloseMainWindow() }; Write-Host 'Asked the MT5 terminal to close.' }
}
