# Sprint 6 - Report

Date: 2026-10-08. Scope: Epic 07, pattern similarity with leakage protection.

## Delivered

Representation (six scale-free channels), five distance methods behind one interface plus an FFT
distance profile and a reference matrix profile, and a leakage-safe k-NN search. Details and the
benchmark: `docs/research/pattern-similarity.md`; rule: ADR-0013.

## Evidence

* **Leakage tests first** (plan requirement): the search tests and `tests/statistical/test_pattern_leakage.py`
  were written before `search.py`. RED: collection failed (module absent).
* **Future leakage:** for every method, on 16 random (seed, query) pairs, replacing all bars after
  the query with large random values (and NaN) leaves matches and distances identical.
* **Overlap and self-match:** on 30 queries per method, no match has an outcome window touching the
  query window; the query itself is never returned; planted future twins and twins inside the
  forbidden zone are never matched; a twin at the last admissible end index IS matched and one bar
  stricter excludes it (off-by-one pinned both ways).
* **Mutation spot-check:** 20 mutants over search, distances and representation. First pass left 7
  survivors; new tests (ties with many candidates, inclusive separation, default separation,
  constant-window MASS values, gapped bars so ret_atr and wicks cannot be confused, single-NaN
  window validity) killed them. Two remain, both equivalent today: the `q + 1` slice (guard for
  future methods, ADR-0013) and `kind="stable"` (NumPy happens to keep order for the tested sizes).
* **Independent review (1 reviewer, adversarial):** index alignment verified for all methods
  including more than one 4,096-candidate chunk; edge queries; representation causality bit-for-bit.
  Fixed with tests: infinity in history raised under warnings-as-errors (now masks the window);
  MASS lost accuracy at large price offsets (now centred; error 0.0047 at 1e6 and a wrong self
  distance at 1e9 before); Pearson threshold was not scale-free; `k=0` silently meant the default.
* Real data (M15): best match is typically 0.5-0.65 of the median candidate distance; DTW costs
  about 1.2 s per query (see the research note).

## Red-team: how could this sprint be wrong?

| Question | Finding | Status |
|---|---|---|
| Leakage through shared bars | Strict rule `e <= q - W - H`; tested | Mitigated |
| Leakage through the outcome engine | Not built yet; Sprint 7 must read only `e+1..e+h` and test it | Open |
| Analogues are weak | Best matches are only about half the median distance (high dimension) | Open: Sprint 7 compares outcomes with the base rate |
| Tuning window, method, k on the same data | Would overfit | Open: evaluation criteria are fixed before Sprint 9 |
| Same-episode duplicates | Separation rule | Mitigated |
| Volume channel is a broker tick count | May add noise | Open |
| DTW cost | Not usable for bar-by-bar backtests | Accepted |
