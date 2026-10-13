# ADR-V2-018: data validity gate (PROPOSED, awaiting owner approval)

Status: **WITHDRAWN by its author on 2026-10-13 (Gate B).** The diagnosis below is wrong: the negative autocorrelation is a symptom, not the cause, and an |autocorrelation| <= 0.10 rule is NOT a validity test. Kept for the record. Replaced by ADR-V2-019 (proposed). Never applied to any spec.

## Context
Stage B of the candidate evaluation (Dev 2011-2018) showed CORE at +0.68R per trade, 57% wins on a 2R/1R geometry, positive in every year. Placebos showed the signal times carried direction (opposite side 13% wins). The edge was too good, so the data was checked before any claim.

Finding (`scripts/research/data_integrity.py`, price data only): the lag-1 autocorrelation of M5 log returns of XAUUSD is about 0 in real gold (+/-0.05) but about **-0.33 at M1, M5 and H1 alike from 2012-06 to 2021-01 (104 months)**, also 2004-06..2005-08, 2006-03 and 2021-08. Volatility is inflated in the same period and `real_volume` is non-zero (a different feed) from 2012-04 to 2018-01. A pullback or mean-reversion rule looks profitable on such a series for no economic reason.

Evidence that the apparent edge is the artefact: CORE trades in the clean months before 2012-06: N=28, E=+0.12R, 39% wins; in the defective months: N=201, E=+0.76R, 60% wins. The same split for X_CORE_C7: -0.05R / 33% versus +0.37R / 47%.

## Proposal (needs the owner; it changes the frozen windows, so it is a NEW spec version 1.1.0)
1. A month is VALID iff |lag-1 autocorrelation of M5 returns| <= 0.10. The rule uses price data only, is applied to every window the same way, and is never a function of a strategy result.
2. Outcome evaluation uses VALID months only. Design (DEV'): valid months from 2005-09 to 2012-05 (80 months, without 2006-03). VALIDATION': valid months of 2021 (2021-02..2021-12 without 2021-08, 10 months). CONFIRM_C unchanged (2025-05..2026-04, all valid). Test-H and Holdout stay locked (all their months are valid; that does not open them).
3. Stage A for the invalid months is discarded for outcome purposes. Counts from them are reported only as "on defective data".

## What this does not fix
The valid design window is short for such a rare strategy (the clean part of CORE produced about 28 trades in 17 months), so the outcome of every comparison will still be INCONCLUSIVE; the power table is unchanged.

## Consequences already visible
- The Gate A report's numbers for Dev after 2012-05 and for Validation 2019-2020 are on defective data (errata in the Stage B report). The modern-window numbers (2025-05..2026-04) stand.
- ML V0 (retired) was trained on H1 data that includes the defective months; its metrics were never to be trusted for authority.
- Any V1 research that used 2012-06..2021-01 (edge_program, baselines, H01..) needs the same check before anyone relies on it.
