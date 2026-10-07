# Windows equivalent of the Makefile (make is not installed by default).
# Usage: .\scripts\dev.ps1 <setup|lint|format|typecheck|test|test-integration|test-all|coverage|check>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('setup', 'lint', 'format', 'typecheck', 'test', 'test-integration', 'test-all', 'coverage', 'check')]
    [string]$Task
)

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

function Invoke-Step([string[]]$Command) {
    Write-Host ">> uv $($Command -join ' ')" -ForegroundColor Cyan
    & uv @Command
    if ($LASTEXITCODE -ne 0) { throw "Step failed (exit $LASTEXITCODE): uv $($Command -join ' ')" }
}

switch ($Task) {
    'setup'            { Invoke-Step @('sync') }
    'lint'             { Invoke-Step @('run', 'ruff', 'check', '.'); Invoke-Step @('run', 'ruff', 'format', '--check', '.') }
    'format'           { Invoke-Step @('run', 'ruff', 'format', '.'); Invoke-Step @('run', 'ruff', 'check', '--fix', '.') }
    'typecheck'        { Invoke-Step @('run', 'mypy') }
    'test'             { Invoke-Step @('run', 'pytest', '-m', 'not integration and not mt5') }
    'test-integration' { Invoke-Step @('run', 'pytest', '-m', 'integration') }
    'test-all'         { Invoke-Step @('run', 'pytest', '-m', 'not mt5') }
    'coverage'         { Invoke-Step @('run', 'pytest', '-m', 'not mt5', '--cov', '--cov-report=term-missing') }
    'check'            {
        Invoke-Step @('run', 'ruff', 'check', '.')
        Invoke-Step @('run', 'ruff', 'format', '--check', '.')
        Invoke-Step @('run', 'mypy')
        Invoke-Step @('run', 'pytest', '-m', 'not mt5')
    }
}
