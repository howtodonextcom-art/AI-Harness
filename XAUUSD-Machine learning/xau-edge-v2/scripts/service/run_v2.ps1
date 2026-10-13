# Supervisor for the XAU EDGE v2 service: keeps it running, restarting with back-off.
# Started hidden by Task Scheduler at logon (scripts/service/install_autostart.ps1); safe to run by hand.
#   - one supervisor at a time (named mutex);
#   - if something already serves the port (a manual run) it waits instead of fighting for it;
#   - a crash restarts after 5 s, doubling up to 2 min while it keeps dying, back to 5 s after 5 min up;
#   - everything is written to logs\supervisor.log.
param([int]$Port = 8200)

$ErrorActionPreference = "Continue"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $root
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
$log = Join-Path $root "logs\supervisor.log"

function Write-Log([string]$message) {
    Add-Content -Path $log -Value ("{0} {1}" -f (Get-Date).ToUniversalTime().ToString("o"), $message)
}

$mutex = New-Object System.Threading.Mutex($false, "Global\XAU_EDGE_V2_SUPERVISOR")
if (-not $mutex.WaitOne(0)) { Write-Log "another supervisor is running: exit"; exit 0 }

$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { $uv = Join-Path $env:APPDATA "Python\Python314\Scripts\uv.exe" }
Write-Log "supervisor started (uv: $uv, port: $Port)"

$backoff = 5
while ($true) {
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        Write-Log "port $Port is already served: waiting"
        Start-Sleep -Seconds 30
        continue
    }
    $started = Get-Date
    try {
        $p = Start-Process -FilePath $uv -ArgumentList @("run", "python", "-m", "xau_edge_v2") `
            -WorkingDirectory $root -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $root "logs\svc.out") -RedirectStandardError (Join-Path $root "logs\svc.err")
        Write-Log "service started (uv pid $($p.Id))"
        $p.WaitForExit()
        Write-Log "service exited (code $($p.ExitCode))"
    } catch {
        Write-Log "could not start the service: $($_.Exception.Message)"
    }
    $ran = ((Get-Date) - $started).TotalSeconds
    if ($ran -gt 300) { $backoff = 5 } else { $backoff = [Math]::Min($backoff * 2, 120) }
    Write-Log "restarting in $backoff s (it ran $([int]$ran) s)"
    Start-Sleep -Seconds $backoff
}
