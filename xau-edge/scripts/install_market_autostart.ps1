<#
.SYNOPSIS
    Registers (or removes) ONE Windows Task Scheduler task that starts the market data stack when you
    log on: FTMO MT5 terminal first, then the supervisor (collector + API [+ dashboard]).

.DESCRIPTION
    Why Task Scheduler and not a service: MetaTrader 5 is a desktop GUI application and does not
    run reliably in Session 0, so the terminal must start in the logged-on user session. The task
    runs as the current user, at logon, after a delay, hidden, and is restarted by Task Scheduler if
    it exits abnormally. It runs scripts\start_market_stack.ps1, which never starts duplicates.
    No NSSM and no second supervisor: the Python supervisor owns the children.

    Nothing here reads .env or stores a password (the task runs as you, interactive-only).

.PARAMETER Uninstall   Remove the task.
.PARAMETER Dashboard   Also start the dashboard.
.PARAMETER DelaySeconds Delay after logon before starting (default 45).
.PARAMETER WhatIf      Print what would be registered; change nothing.
.EXAMPLE
    .\scripts\install_market_autostart.ps1 -WhatIf
    .\scripts\install_market_autostart.ps1 -Dashboard
    .\scripts\install_market_autostart.ps1 -Uninstall
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Uninstall,
    [switch]$Dashboard,
    [int]$DelaySeconds = 45,
    [string]$TaskName = 'XAU-EDGE Market Stack'
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Script = Join-Path $Repo 'scripts\start_market_stack.ps1'

if ($Uninstall) {
    if ($PSCmdlet.ShouldProcess($TaskName, 'Unregister-ScheduledTask')) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "Removed task '$TaskName' (if it existed)."
    }
    return
}

$argText = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Script`" -WaitSeconds 30"
if ($Dashboard) { $argText += ' -Dashboard' }
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argText -WorkingDirectory $Repo
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trigger.Delay = 'PT{0}S' -f $DelaySeconds
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if ($PSCmdlet.ShouldProcess($TaskName, "Register-ScheduledTask (at logon of $env:USERNAME, delay ${DelaySeconds}s): powershell $argText")) {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
        -Principal $principal -Description 'Starts the FTMO MT5 terminal and the XAU EDGE market data supervisor.' -Force | Out-Null
    Write-Host "Registered '$TaskName'. It starts at your next logon; run .\scripts\start_market_stack.ps1 to start now."
    Write-Host 'This is CONFIGURED, not VERIFIED: verify with a real logon (docs/operations/market-data-operations.md).'
}
