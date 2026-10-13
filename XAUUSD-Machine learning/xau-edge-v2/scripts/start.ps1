# One command: build the web page if needed, then serve API + WebSocket + page on one port.
# Usage:  .\scripts\start.ps1            (default http://127.0.0.1:8200)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
if (-not (Test-Path "apps\web\dist\index.html")) {
    Push-Location apps\web
    if (-not (Test-Path node_modules)) { npm ci }
    npm run build
    Pop-Location
}
uv run python -m xau_edge_v2
