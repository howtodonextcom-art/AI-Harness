# AGENTS.md - instructions for AI coding agents

## Mission

XAU EDGE is an explainable, probabilistic **decision-support and research** platform for
XAUUSD. It must be able to say "no statistically justified trade". Protect statistical
integrity first, capital second, and automate execution last (not in this codebase yet).

## Safety boundaries (non-negotiable)

* Live trading does not exist. `Settings.enable_live_trading` rejects `true`. Do not add any path
  that can send an order to a live account.
* Demo execution is a separate, demo-only track governed by ADR-0019. It is disabled by default
  (`XAU_EDGE_ENABLE_DEMO_TRADING=false`) and dry-run by default
  (`XAU_EDGE_DEMO_DRY_RUN=true`). Do not bypass the signal evidence gate, `RiskEngine`,
  `ExecutionSafety`, persistent idempotency, kill switch, or broker reconciliation.
* `market_data/mt5/` is read-only market data. A test forbids order/position API names there.
* `src/xau_edge/execution/` is broker-neutral orchestration. Do not import `MetaTrader5` or call
  MT5 order APIs there. Any future MT5 demo order adapter must live in a separate demo-only broker
  package, such as `src/xau_edge/brokers/mt5_demo/`, and must be covered by fake-client tests.
* Do not add dashboard/API endpoints that accept arbitrary trade direction, lots, SL or TP. The
  first manual kill-switch control should be a local CLI; any write API route needs an ADR update,
  local operator token, origin checks and route-table tests.
* Never change risk limits, prop-firm limits, or safety gates silently; any change needs an ADR
  and a test.
* Never claim profitability, show invented backtest numbers, or present synthetic data as real.
* Never commit secrets or account identifiers. Credentials and login numbers live in `.env`
  (git-ignored); `.env.example` is committed and must stay empty of real values. Use `SecretStr`.
* `scripts/verify_mt5.py` is read-only and must keep its DEMO-account guard. Never point MT5
  tooling at a live account. Prefer an investor/read-only MT5 password for market data. Future demo
  execution uses a separate `MT5_TRADE_PASSWORD`, never committed.
* Never use future information. Never shuffle time series. Never optimise on test data.
* Raw data is immutable. Do not edit files under `data/raw/`.

## Architecture

See `docs/architecture/system.md`. Forecasting is separate from the trading decision.
Package: `src/xau_edge/` (`domain`, `market_data`, later `features`, `structure`, `patterns`,
`signals`, `risk`, `backtest`, ...). Dependencies point inward: `domain` imports nothing from
other packages.

## Coding rules

* Python 3.12+, full type hints, `mypy --strict` clean, ruff clean (line length 100).
* Polars frames at module boundaries; the bar frame contract is `domain.bars.BAR_SCHEMA`.
* All timestamps are tz-aware UTC bar-OPEN times. Broker zones are explicit config.
* Validators and sources report; they never silently repair, sort or de-duplicate.
* Small composable modules, Pydantic models for config/records, no giant scripts.
* Prefer simple models when performance is comparable.

## Commands (Windows has no `make`; use the script)

```
.\scripts\dev.ps1 setup           # uv sync --extra ml --extra api
.\scripts\dev.ps1 check           # ruff + ruff format --check + mypy + pytest  (definition of done gate)
.\scripts\dev.ps1 test            # unit tests only
.\scripts\dev.ps1 test-integration
.\scripts\dev.ps1 coverage
```
Equivalent `make` targets exist. MT5 support: `uv sync --extra mt5` (Windows only).
Set `HOME` to a scratch directory if you run ECC tooling, which writes a cache under `~/.claude`.

## Folder ownership

| Path | Contents |
|---|---|
| `src/xau_edge/domain` | contracts: timeframe, bars, instrument |
| `src/xau_edge/market_data` | sources, importers, raw store, catalog, resampling, broker clock/profiles, validators |
| `configs/brokers` | measured broker profiles; every value must cite `docs/reports/mt5-verification.md` or a newer measurement |
| `src/xau_edge/{features,structure,patterns,outcomes,strategies}` | research layers; causal, tested against look-ahead |
| `src/xau_edge/{backtest,risk,news,models,evaluation,experiments}` | evaluation machinery; the pre-registered protocol is code in `evaluation/` |
| `src/xau_edge/{signals,execution,api}` + `apps/dashboard` | decision layer, paper broker, read-only API and UI |
| `src/xau_edge/brokers` | future broker adapters; only demo adapters may call broker order APIs, and only under ADR-0019 controls |
| `scripts` | operator tools (`dev.ps1`, `verify_mt5.py`, `run_backtest.py`, `run_models.py`, `serve_api.py`, `current_signal.py`, `forward_test.py`) |
| `tests/{unit,integration,regression,statistical}` | tests mirror `src` layout |
| `data/*` | git-ignored data; `.gitkeep` only |
| `docs/decisions` | ADRs; add one for any architectural change |
| `docs/reports` | sprint reports |
| `.claude/` | ECC components installed project-local (minimal profile, **no hooks**); do not hand-edit |

## Workflow (ECC) - the delivery loop is mandatory

Every change follows `docs/PROJECT_PLAN.md` ("ECC delivery loop"): research -> plan -> **Gate A**
-> failing tests first (watch them fail) -> implement -> fresh-context reviews (`code-reviewer`,
`python-reviewer`, plus `security-reviewer` for MT5, SQL, file I/O, config or CI) -> `check` ->
**Gate B** (owner confirms) -> commit. Do not commit before Gate B. ECC components live in
`.claude/` (workflow skills and the `security` capability are installed; hooks are not).

Guards stop *accidental* misuse, not deliberate in-process bypass: the MT5 read-only proxy and
`Settings` freeze are not sandboxes. Real controls: DEMO-only guard, the terminal trading switch
off, MT5 investor (read-only) password, and re-checking the live-trading flag at any future
execution entry point.

### Method details

Plan with the `planner` format (`docs/PROJECT_PLAN.md`), write tests first and watch them fail
(`tdd-workflow`), keep changes small, run `check` (`verification-loop`), then review for
security and correctness. After each phase, red-team the result: how could it be wrong?
(data errors, leakage, timestamp/timezone, repainting, overfitting, fill and cost assumptions,
sample size, regime dependence, model instability) and document findings.

## Definition of done

Code implemented, types valid, tests pass (`check` green), docs updated, acceptance criteria
met, no known critical bug, result reproducible.

## Forbidden

Enabling live trading; changing risk limits silently; removing safety gates; claiming
profitability without evidence; fabricated results; look-ahead; random shuffling of time
series; adding deep learning or reinforcement learning without benchmark evidence; adding
AGPL/GPL dependencies (ADR-0006); adding a direct `Signal -> broker` path; retrying an unknown
broker order blindly after a timeout; auto-closing positions on kill switch without an explicit ADR.
