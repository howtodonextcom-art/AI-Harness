# Register the two Task Scheduler tasks for the current user (no administrator rights needed):
#   XAU-EDGE-V2-Service   at logon: the supervisor (run_v2.ps1) that keeps the service up
#   XAU-EDGE-V2-Watchdog  every 2 minutes: the external watchdog (scripts/external_watchdog.py)
# Re-running replaces both tasks. Remove with:  .\scripts\service\install_autostart.ps1 -Remove
# Limits (by design): the tasks run while this user is logged on (they need the desktop session's
# environment); they do not run on a machine nobody has logged into.
param([switch]$Remove)

$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$names = @("XAU-EDGE-V2-Service", "XAU-EDGE-V2-Watchdog")

if ($Remove) {
    foreach ($n in $names) {
        Unregister-ScheduledTask -TaskName $n -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "removed $n"
    }
    return
}

$user = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

# 1. the supervisor, at logon
$supervisor = Join-Path $PSScriptRoot "run_v2.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$supervisor`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$trigger.Delay = "PT20S"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $names[0] -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "Keeps the XAU EDGE v2 service running (PAPER only)." -Force | Out-Null
Write-Host "registered $($names[0])"

# 2. the external watchdog, every 2 minutes (standard library only: no project environment needed)
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pythonw) { $pythonw = (Get-Command python.exe).Source -replace "python\.exe$", "pythonw.exe" }
$watchdog = Join-Path $root "scripts\external_watchdog.py"
$action2 = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$watchdog`"" -WorkingDirectory $root
$trigger2 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings2 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $names[1] -Action $action2 -Trigger $trigger2 -Settings $settings2 -Principal $principal `
    -Description "Watches the XAU EDGE v2 service from outside and alerts on Telegram (operational only)." -Force | Out-Null
Write-Host "registered $($names[1]) (python: $pythonw)"
Get-ScheduledTask -TaskName $names | Select-Object TaskName, State | Format-Table -AutoSize
