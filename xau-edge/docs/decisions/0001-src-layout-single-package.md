# ADR-0001: One installable package under `src/`

Status: accepted (2026-10-08)

**Context.** The brief sketches many top-level folders (`src/market_data`, `src/features`, ...)
plus `apps/` and `packages/`.

**Decision.** A single package `xau_edge` in `src/xau_edge/` with sub-packages named as in the
brief. `apps/` (API, dashboard) is created when those epics start.

**Why.** Top-level module names such as `features` or `patterns` collide easily and are not
importable after installation. A `src` layout forces tests to run against the installed package.

**Consequences.** Imports are `xau_edge.market_data...`. Folder names in the brief map 1:1 under
`src/xau_edge/`.
