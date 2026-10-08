# Sprint 3 - Report

Date: 2026-10-08. Scope: ECC remediation (commit `270e484`), roadmap debt found by
`docs/ROADMAP_TRACEABILITY.md`, and Epic 04 part 1 (indicators). Research only; no live trading.

## What was delivered

| Area | Delivered | Evidence |
|---|---|---|
| ECC remediation | F-01..F-21 fixed, workflow skills installed | `270e484`, `docs/ECC_ALIGNMENT_AUDIT.md` |
| Roadmap audit | 56-section matrix, 15 gaps, run-ladder L0-L5 | `docs/ROADMAP_TRACEABILITY.md`, independent review |
| Logging (G-1) | `observability.py`; events `raw.write`, `validation.result`, `catalog.load` | `tests/unit/test_observability*.py` |
| Indicators (Epic 04 part 1) | 12 functions, causal, `NaN` warm-up | golden tests vs TA-Lib, ADR-0010 |
| Docs (G-5, G-11) | BRIEF, data-flow, testing-strategy, ADR-0010, plan updates | files in `docs/` |
| Test layout (G-6) | `tests/regression` (pinned hashes), `tests/statistical` (README only) | |
| pre-commit (G-8) | configuration and `.env` guard script; hooks not installed | `tests/unit/test_precommit.py` |

## ECC loop evidence

* **E0:** TA-Lib considered and rejected as a dependency (native build, wheel matrix); used only to
  record reference output (ADR-0010).
* **Gate A:** owner approved the prompt and scope, including indicators ("chon (b)").
* **E2 RED:** observability tests failed with `ModuleNotFoundError: xau_edge.observability`;
  indicator tests failed at collection (`xau_edge.features` absent); hardening tests failed with
  `ImportError: XauHandler` before the review fixes.
* **E4:** round 1, two independent reviewers (code + Python; security) found 2 HIGH and 6 MEDIUM
  issues, all fixed with tests: the redaction regex wiped the `passed` field; the pre-commit YAML
  did not parse; credential key gaps (`pwd`, `auth`, `bearer`, `cookie`); secrets inside strings;
  cyclic data crashed the caller; `NaN` produced invalid JSON; `adx`/`rsi` accepted period 1;
  no overflow guard; logging setup was not thread-safe and propagated twice. Round 2 (one
  reviewer): numpy scalars logged as `<int64>`, compound keys (`access_token=`) and `Authorization:`
  headers not scrubbed, huge ints unbounded: fixed with tests. Found by running the fix: the new
  scrub pattern was quadratic on a 1 MB word (test hung), so strings are truncated before scrubbing.
  Accepted: key-name over-redaction (`key_count`, `max_tokens` are hidden; fail-safe).
* **E5:** `dev.ps1 check` green; mutation spot-check: 27 hand-made mutants over indicators and
  redaction (15 first pass + 12 after fixes), one survivor (non-finite float handling) found and
  killed by a stronger assertion.

## Quality gate

`dev.ps1 check`-equivalent (ruff, ruff format, `mypy --strict`, pytest): 486 passed on Python
3.13; 484 passed and 2 skipped (MetaTrader5 package absent) on 3.12 and 3.14; 98% line+branch
coverage (1390 statements, 20 missed). CI result for the pushed commit is recorded in the final
hand-off message.

## Red-team: how could this sprint be wrong?

| Question | Finding | Status |
|---|---|---|
| Golden reference shared convention | One reference (TA-Lib). A convention shared by TA-Lib and us would pass unnoticed | Accepted; conventions listed in ADR-0010 |
| Synthetic golden input | Random walk; no gaps, no holiday sessions, no extreme moves | Open; real-data sanity checks come with the feature set (Sprint 4) |
| Strict finite-input rule | One `NaN` in a series raises instead of propagating | Deliberate: validators gate input; revisit with feature sets |
| Look-ahead | Every indicator has an append-future-bars test with exact equality | Mitigated for indicators; patterns/outcomes later |
| Warm-up bias | Early `NaN` rows will have to be excluded consistently by consumers | Open until feature sets |
| MACD/Stochastic first-valid index | Ours start earlier than TA-Lib's trimmed output; values match where TA-Lib reports | Documented in tests |
| Redaction is key-based | Unknown secret under an innocent key and shape is not caught | Mitigated by value scrub, bounded output; call sites log metadata only |
| Performance | 100k bars: ADX 0.13 s, others < 0.06 s | Accepted |
| Overfitting / leakage | Not applicable yet (no models or backtests) | Deferred |

## Not done on purpose

Candle, volume and session features and the versioned feature set (Sprint 4); structure, regime,
patterns; experiment registry (Sprint 7); news layer; risk engine and `configs/prop` (Sprint 8);
make targets for later epics; Docker; installing pre-commit hooks.
