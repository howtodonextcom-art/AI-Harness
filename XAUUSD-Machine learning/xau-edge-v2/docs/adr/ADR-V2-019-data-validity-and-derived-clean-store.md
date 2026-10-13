# ADR-V2-019: data validity classes and a derived clean store (PROPOSED, awaiting the owner)

Status: **ACCEPTED WITH CONDITIONS by the owner (Gate B2, 2026-10-13)**; implemented at Gate B3. Supersedes the withdrawn ADR-V2-018.

Conditions set by the owner, and how each is met: RAW data stays untouched (the build hashes the raw files before and after and aborts on any change); a separate clean store (`data/clean_store`, rebuilt by `scripts/research/build_clean_store.py`); the pseudo-bars are dropped (2,216 M1 bars; the earlier count of 2,205 missed thin-volume holiday bars); H4 restored from a verified source; a manifest with sha256 of every file, of every raw input and of the manifest; M1/M5/M15/M30/H1/H4 synchronisation checks; defective data cannot reach a backtest (`CleanBarStore` refuses anything that is not a PASS month and every file whose hash differs from the manifest; the research pipelines also refuse months with pseudo-bars).

Correction of the evidence: the re-fetch used for identity checks and for the H4 restoration came from the **MetaQuotes-Demo** server (terminal `C:\Program Files\MetaTrader 5`), a different provider than the FTMO feed of the store. The FTMO terminal itself serves the pseudo-bars today in every timeframe (see ADR-V2-020 evidence and `docs/research/ftmo_terminal_probe.json`).

## Context
Forensics (`reports/V2_DATA_PROVENANCE_FORENSIC_REPORT.md`) found one daily pseudo-bar from 2012-06-26 to 2021-01-20 (2,205 bars in M1/M5/M15/M30/H1, merged into H4). It carries the OHLC of the NEXT session, so any consumer looks up to 24 hours ahead. Everything else in those months is identical to a fresh broker re-fetch.

## Proposal
1. **Classes** per month, from evidence, never from a strategy result: `VERIFIED_VALID`, `SUSPECT`, `INVALID` (with `recoverable`), `INSUFFICIENT_EVIDENCE` (definitions in the report; computed by `scripts/research/data_forensics.py`). Autocorrelation is only one diagnostic among others and never a verdict.
2. **Derived clean store** (never the raw store): bars of the INVALID-recoverable months with pseudo-bars removed by `research/clean_view.py`; H4 replaced by the broker re-fetch; every file hashed; a manifest lists the dropped bars. The raw store, `research_history` and `raw` stay untouched.
3. **Gate:** research pipelines refuse a month that contains a pseudo-bar (`require_clean`, done) and, once this ADR is approved, accept only months that are VERIFIED_VALID or recoverable in the derived store. `SUSPECT` and `INSUFFICIENT_EVIDENCE` months are excluded from outcome work until resolved.
4. **Independent source:** a third-party series, if the owner supplies one with the right to use it, upgrades `VERIFIED_VALID` from "same broker" to "independent".
5. **Open items before any outcome rerun:** F6 (restart determinism of C1), 2022-01..03, the owner-run source experiment (`V2_DATA_RECOVERY_OPTIONS.md`, A1), and a new spec version for the windows.

## Consequences
Months 2012-07..2020-12 (and the recoverable ones) return to use after cleaning; the design window grows from about 17 to about 150 months. The statistical power problem is unchanged (about 663 trades needed for 0.20R).
