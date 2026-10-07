# Dependency review

Date: 2026-10-08. Environment: Windows 11, Python 3.14.4, uv.

**Method.** Versions, release dates, `requires-python`, and Windows wheel availability come from
the PyPI JSON API; npm versions from the npm registry; repository activity from the GitHub API
(unauthenticated). Licenses use PyPI metadata first and GitHub's detection second, and are flagged
where the two disagree or one is blank. Nothing here is a legal opinion: licenses marked
"verify" need a human check of the actual `LICENSE` text before redistribution.
GitHub rate limiting prevented reading `vercel/next.js` and `stumpy-dev/stumpy`; Next.js data
below is from npm only.

Decision vocabulary: **ADOPT** (direct dependency), **WRAP** (use only behind our own
interface), **DEFER** (planned, not needed yet), **AVOID** (do not depend on it),
**REFERENCE** (read for ideas, copy no code).

## Python runtime

| Package | Version (release) | License | Python / Windows | Role | Decision | Notes |
|---|---|---|---|---|---|---|
| numpy | 2.5.3 (2026-09-06) | BSD-3 + permissive bundle | needs >=3.12; win wheels cp312-cp314 | arrays, TA-Lib/STUMPY interop | ADOPT | Sets our Python floor at 3.12 |
| polars | 2.0.0 (2026-10-06) | MIT (PyPI classifier; license text also credits NVIDIA for some portions) | pure wheel + `polars-runtime-32` | frames, Parquet I/O | ADOPT, pinned `>=2,<3` | **Major version released 2 days before this review**; last 1.x is 1.44.2 (2026-09-09). Risk accepted: API confined to the data layer, `uv.lock` committed, fallback to 1.44 is possible. Re-evaluate after 2.0.x patch releases |
| pydantic | 2.13.5 (2026-08-28) | MIT | pure | models, schemas | ADOPT | |
| pydantic-settings | 2.15.0 (2026-08-07) | MIT | pure | env/.env settings, `SecretStr` | ADOPT | |
| PyYAML | 6.0.3 (2025-09-25) | MIT | win wheels | config files | ADOPT (declared; first used in Sprint 2) | Always `safe_load` |
| tzdata | 2026.5 | Apache-2.0 | pure | IANA zones for `zoneinfo` on Windows | ADOPT (Windows marker) | Windows ships no tz database |
| MetaTrader5 | 5.0.6231 (2026-09-27) | PyPI says MIT; binary from MetaQuotes, **verify** | **Windows only**; cp312-cp314 win_amd64 wheels, no sdist; imports OK on 3.14 (verified) | MT5 terminal market data | WRAP, optional extra `mt5` | Talks to a locally running terminal. Only `copy_rates_range` is used; trading calls are forbidden by test |
| DuckDB | 1.5.6 (2026-09-28) | MIT | win wheels cp312-cp314 | SQL over Parquet | DEFER to Sprint 2 | Will back dataset queries; also reads Parquet directly |
| PyArrow | 25.0.1 (2026-08-10) | Apache-2.0 | win wheels | Arrow interop | DEFER | Polars and DuckDB already read/write Parquet; add only if a consumer needs Arrow objects |
| pandas | 3.0.6 (2026-09-17) | BSD-3 | win wheels | frames | AVOID as core | Not needed; allowed at library boundaries if a dependency demands it |
| TA-Lib | 0.8.1 (2026-09-21) | BSD-2 (GitHub); PyPI license blank, **verify** | win wheels incl. cp314, no C library build needed | indicators | ADOPT in Sprint 3 behind an `indicators` interface | Active (GitHub push 2026-09-21). "Never blindly trust indicator libraries": every indicator gets a golden test against an independent reference, and Wilder-smoothing conventions (RSI/ATR/ADX) are pinned explicitly |
| STUMPY | 1.14.1 (2026-02-08) | BSD-3 (PyPI); GitHub shows "NOASSERTION", **verify** | pure wheel; depends on numba (0.68.0 has win cp312-cp314 wheels) | Matrix Profile | WRAP, Phase 4 | GitHub push 2026-10-03. JIT warm-up cost; benchmark against plain NumPy distance search before committing |
| tslearn | 0.9.0 (2026-07-02) | BSD-2 | pure wheel; needs numba, scikit-learn | DTW | WRAP, Phase 4 | Active (push 2026-10-07). Keep DTW behind the unified similarity interface |
| scikit-learn | 1.9.1 (2026-09-10) | BSD-3 | needs >=3.11; win wheels | logistic, RF, calibration | DEFER to Phase 8 | |
| XGBoost | 3.4.1 (2026-08-15) | Apache-2.0 | needs >=3.12; `py3-none-win_amd64` wheel | gradient boosting | DEFER to Phase 8 | |
| LightGBM | 4.7.0 (2026-07-18) | PyPI license fields blank, **verify** (not checked against the upstream repo here) | `py3-none-win_amd64` wheel | gradient boosting | DEFER to Phase 8 | |
| FastAPI | 0.142.4 (2026-10-07) | MIT | pure | HTTP API | DEFER to Epic 15 | Pre-1.0 versioning: pin tightly |
| vectorbt | 1.1.1 (2026-09-26) | **PyPI blank, GitHub NOASSERTION** | needs `>=3.11,<3.15`; pure wheel | vectorised backtests | **AVOID** | Licence cannot be confirmed from metadata (historically tied to a Commons-Clause-style restriction; unverified here). Heavy numba stack. We need custom cost/fill modelling anyway, so a small in-house vectorised engine is lower risk |
| backtesting.py | 0.6.6 (2026-07-22) | **AGPL-3.0** | pure wheel | event backtests | **AVOID** | Network-copyleft: serving results through an API could create obligations. Reference only |
| hypothesis | 6.168.5 (2026-10-05) | MPL-2.0 | | property tests | ADOPT (dev only) | File-level copyleft is acceptable for a dev-only tool |
| pytest / pytest-cov | 9.1.1 / 7.1.0 | MIT | | tests | ADOPT (dev) | |
| ruff | 0.16.10 (2026-10-01) | MIT | win wheels | lint + format | ADOPT (dev) | |
| mypy | 2.4.0 (2026-10-01) | MIT | | typing | ADOPT (dev) | strict mode + pydantic plugin |
| pandera | 0.34.1 (2026-10-06) | MIT | pure | dataframe schemas | AVOID | Our validators must report, not raise, and must encode market calendars; pydantic plus purpose-built checks is simpler |

## Frontend (Epic 16, not installed yet)

| Package | Version (npm latest) | License | Decision |
|---|---|---|---|
| Next.js | 16.4.0 | MIT | ADOPT |
| TypeScript | 7.0.2 | Apache-2.0 | ADOPT, strict |
| Tailwind CSS | 4.3.3 | MIT | ADOPT |
| lightweight-charts (TradingView) | 5.2.1 | Apache-2.0 | ADOPT. GitHub: 17.5k stars, last push 2026-10-07. Check the attribution notice requirement before shipping |

## Projects reviewed as references

| Project | License | Activity (GitHub) | Decision | Reason |
|---|---|---|---|---|
| QuantConnect LEAN | Apache-2.0 | push 2026-10-07, 21.9k stars | REFERENCE | C#-centred engine; adopting it would replace this architecture. Useful for fill/fee/slippage model design |
| Freqtrade | **GPL-3.0** | push 2026-10-07, 55k stars | REFERENCE (no code copying) | Crypto-focused, copyleft |
| backtrader | **GPL-3.0** | **last push 2024-08-19** | AVOID | Copyleft and stale |
| FinRL | MIT | push 2026-10-06, 16.6k stars | AVOID for MVP | Reinforcement learning is out of scope until baselines are beaten out-of-sample |

## Consequences for the project

1. **Python floor 3.12** (numpy 2.5 and XGBoost 3.4 require it). Only 3.14.4 was available and
   tested locally; 3.12 and 3.13 are supported on paper but **untested** (see sprint report).
2. **Copyleft guard**: AGPL/GPL packages are not dependencies (ADR-0006).
3. **Polars 2.0.0 is a risk to monitor**, not a settled choice.
4. **Windows wheels exist for every adopted compiled dependency on cp312-cp314**, so no C toolchain is needed. This was checked from wheel filenames, not by installing all of them; only the Sprint 1 set (numpy, polars, pydantic, pydantic-settings, pyyaml, tzdata, MetaTrader5, dev tools) was actually installed and exercised.
