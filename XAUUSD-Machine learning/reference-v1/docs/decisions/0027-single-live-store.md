# ADR-0027: One live store `data/market`

Status: **ACCEPTED** (2026-10-11). Full rationale: `docs/decisions/drafts/0027-single-live-store-raw-archive.md`.

- Live / Trading Core / dashboard: `data/market` only. No fourth store.
- `data/research_history`: immutable V1/V2 research history.
- `data/raw`: read-only legacy until `/legacy` and `/paper/*` retire.
- Manifests: `data/raw/MANIFEST.json`, `data/research_history/MANIFEST.json` (inventory + sha256).
- Do not delete either archive. Do not back-fill bars from `data/raw` into the ledger.
