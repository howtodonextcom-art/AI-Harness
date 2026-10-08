<#
.SYNOPSIS
    Installs (or removes) the xau-edge bot and API as Windows services through NSSM.

.DESCRIPTION
    * Bot service  : uv run --extra mt5 python scripts/demo_trader.py   (dry-run unless .env says otherwise)
    * API service  : uv run --extra api python scripts/serve_api.py     (binds 127.0.0.1 only)
    Both: start at boot (delayed automatic), restart on ANY exit after a delay, stdout/stderr to
    size/age-rotated log files, run as a configurable account. Re-running updates the settings in
    place (idempotent). Nothing is started unless -StartNow is given.

    The script never reads .env and never prints or stores secrets. Credentials stay in .env
    (read by the application itself) or in the MT5 terminal profile.

.PARAMETER Uninstall
    Stop and remove the services (the log files are kept).

.PARAMETER WhatIf
    Dry run: print every action, change nothing. Works without admin rights and without NSSM.

.PARAMETER ServiceAccount
    Account the services run as, e.g. ".\xauedge" or "DOMAIN\svc-xauedge". Default: LocalSystem
    (not recommended: the MT5 terminal profile and uv cache belong to a normal user).

.PARAMETER ServicePassword
    SecureString password for -ServiceAccount (prompted if the account needs one and none is given).

.EXAMPLE
    .\scripts\install_services.ps1 -WhatIf
    .\scripts\install_services.ps1 -ServiceAccount ".\xauedge" -StartNow
    .\scripts\install_services.ps1 -Uninstall
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Uninstall,
    [string]$ServiceAccount = '',
    [System.Security.SecureString]$ServicePassword,
    [string]$RepoRoot = '',
    [string]$NssmPath = '',
    [string]$UvPath = '',
    [string]$LogDir = '',
    [string]$BotServiceName = 'xau-edge-bot',
    [string]$ApiServiceName = 'xau-edge-api',
    [int]$ApiPort = 8000,
    [int]$RestartDelaySeconds = 30,
    [int]$RotateMegabytes = 10,
    [switch]$SkipApi,
    [switch]$SkipBot,
    [switch]$StartNow
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Resolve-Tool([string]$Explicit, [string]$Name) {
    if ($Explicit) { return $Explicit }
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

if (-not $RepoRoot) { $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
if (-not $LogDir) { $LogDir = Join-Path $RepoRoot 'data\logs' }
$Nssm = Resolve-Tool $NssmPath 'nssm.exe'
$Uv = Resolve-Tool $UvPath 'uv.exe'

if (-not $Nssm) {
    if ($WhatIfPreference) {
        Write-Warning 'nssm.exe not found; the dry run uses a placeholder (install NSSM before the real run).'
        $Nssm = 'nssm.exe'
    } else {
        throw 'nssm.exe not found. Install NSSM (https://nssm.cc) and put it on PATH, or pass -NssmPath.'
    }
}
if (-not $Uv) {
    if ($WhatIfPreference) {
        Write-Warning 'uv.exe not found; the dry run uses a placeholder.'
        $Uv = 'uv.exe'
    } else {
        throw 'uv.exe not found. Install uv or pass -UvPath.'
    }
}
if (-not $WhatIfPreference) {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run this script from an elevated (Administrator) PowerShell, or use -WhatIf to preview.'
    }
}

function Invoke-Nssm([string]$Service, [string]$Description, [string[]]$NssmArgs) {
    if ($PSCmdlet.ShouldProcess($Service, "nssm $Description")) {
        & $Nssm @NssmArgs | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "nssm $Description failed for $Service (exit $LASTEXITCODE)" }
    }
}

function Test-ServiceExists([string]$Name) {
    return [bool](Get-Service -Name $Name -ErrorAction SilentlyContinue)
}

function Install-OneService {
    param([string]$Name, [string]$Display, [string]$Description, [string]$UvArguments, [string]$LogPrefix)

    $stdout = Join-Path $LogDir "$LogPrefix.out.log"
    $stderr = Join-Path $LogDir "$LogPrefix.err.log"
    if (-not (Test-ServiceExists $Name)) {
        Invoke-Nssm $Name 'install' @('install', $Name, $Uv, $UvArguments)
    }
    # Every setting is (re)applied each run, so a second run converges to the same state.
    $settings = [ordered]@{
        'Application'          = @($Uv)
        'AppParameters'        = @($UvArguments)
        'AppDirectory'         = @($RepoRoot)
        'DisplayName'          = @($Display)
        'Description'          = @($Description)
        'Start'                = @('SERVICE_DELAYED_AUTO_START')
        'AppExit'              = @('Default', 'Restart')
        'AppRestartDelay'      = @([string]($RestartDelaySeconds * 1000))
        'AppThrottle'          = @('15000')
        'AppStdout'            = @($stdout)
        'AppStderr'            = @($stderr)
        'AppRotateFiles'       = @('1')
        'AppRotateOnline'      = @('1')
        'AppRotateBytes'       = @([string]($RotateMegabytes * 1MB))
        'AppRotateSeconds'     = @('86400')
        'AppStopMethodConsole' = @('20000')
        'AppStopMethodWindow'  = @('0')
        'AppStopMethodThreads' = @('0')
    }
    foreach ($key in $settings.Keys) {
        Invoke-Nssm $Name "set $key" (@('set', $Name, $key) + $settings[$key])
    }
    if ($ServiceAccount) {
        $accountArgs = @('set', $Name, 'ObjectName', $ServiceAccount)
        if ($ServicePassword) {
            $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($ServicePassword)
            try {
                $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
                if ($PSCmdlet.ShouldProcess($Name, 'nssm set ObjectName (password hidden)')) {
                    & $Nssm @($accountArgs + $plain) | Out-Null
                    if ($LASTEXITCODE -ne 0) { throw "nssm set ObjectName failed for $Name" }
                }
            } finally {
                [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
                $plain = $null
            }
        } else {
            Invoke-Nssm $Name 'set ObjectName' $accountArgs
        }
    }
    if ($StartNow) {
        if ($PSCmdlet.ShouldProcess($Name, 'Start-Service')) { Start-Service -Name $Name }
    }
}

function Uninstall-OneService([string]$Name) {
    if (-not (Test-ServiceExists $Name)) {
        Write-Host "$Name is not installed; nothing to do."
        return
    }
    if ($PSCmdlet.ShouldProcess($Name, 'Stop-Service')) {
        Stop-Service -Name $Name -Force -ErrorAction SilentlyContinue
    }
    Invoke-Nssm $Name 'remove' @('remove', $Name, 'confirm')
}

$names = @()
if (-not $SkipBot) { $names += $BotServiceName }
if (-not $SkipApi) { $names += $ApiServiceName }

if ($Uninstall) {
    foreach ($n in $names) { Uninstall-OneService $n }
    Write-Host 'Services removed. Log files were kept.'
    return
}

if ($PSCmdlet.ShouldProcess($LogDir, 'Create log directory')) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}
if ($ServiceAccount -and $PSCmdlet.ShouldProcess($RepoRoot, "Grant Modify on data and logs to $ServiceAccount")) {
    $dataDir = Join-Path $RepoRoot 'data'
    New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
    & icacls.exe $dataDir /grant "${ServiceAccount}:(OI)(CI)M" /T /C | Out-Null
}

if (-not $SkipBot) {
    Install-OneService -Name $BotServiceName -Display 'xau-edge demo bot' `
        -Description 'XAUUSD demo bot (scripts/demo_trader.py). Dry-run unless .env enables demo execution.' `
        -UvArguments 'run --extra mt5 python scripts/demo_trader.py' -LogPrefix 'bot'
}
if (-not $SkipApi) {
    Install-OneService -Name $ApiServiceName -Display 'xau-edge read-only API' `
        -Description 'Read-only research API on 127.0.0.1 (scripts/serve_api.py).' `
        -UvArguments "run --extra api python scripts/serve_api.py --port $ApiPort" -LogPrefix 'api'
}

Write-Host 'Done. Check with: Get-Service xau-edge-*; logs in' $LogDir
if (-not $StartNow) { Write-Host 'Services were NOT started (use -StartNow or Start-Service).' }
