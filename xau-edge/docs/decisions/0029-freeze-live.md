# ADR-0029: Freeze-LIVE — develop on sandbox

Status: **ACCEPTED** (2026-10-11). Full rationale: `docs/decisions/drafts/0029-freeze-live-dev-on-sandbox.md`.

Codified in `AGENTS.md`, `CLAUDE.md`, and `docs/operations/market-data-operations.md`.

- Live `:8000`/`:3000` is observation. Rebuild `.next` and restart only when the market is CLOSED.
- Development uses sandbox (`NEXT_DIST_DIR=.next-sandbox`, non-3000 port).
- Owner: Windows Task Scheduler `XAU-EDGE Market Stack`. Not NSSM for the market stack.
- Do not back-fill missed decisions. Coverage gate stays 95%.
