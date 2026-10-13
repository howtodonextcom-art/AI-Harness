# Quality gate: backend (ruff, mypy --strict, pytest, contract in sync) + web (types, build, browser tests).
# Set XAU_V2_CHROMIUM to an installed Chromium if Playwright's own browser is not installed.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run python scripts\export_openapi.py --check
if ($LASTEXITCODE -ne 0) { throw "docs/openapi.json is out of date (run scripts/export_openapi.py, then npm run types)" }
uv run pytest
Push-Location apps\web
npm run types
git diff --quiet -- src/api/schema.d.ts 2>$null
npm run build
npm run test:unit
npx playwright test
Pop-Location
