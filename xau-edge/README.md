# XAU EDGE

Probabilistic decision-support and research platform for XAUUSD.
**Research only. There is no live trading code and none can be enabled.**

The system is designed to answer: what is the regime and higher-timeframe bias, what happened
after historically similar structures, what are the calibrated probabilities and expected value
after costs, and should it say BUY, SELL, or **WAIT**. A high-quality "no trade" is a valid and
valuable output.

## Status

All planned components are built and tested; the research conclusion so far is **no validated edge**.

| Area | State |
|---|---|
| Market data: MT5 (read-only, demo-guarded) and file sources, immutable store, validators, broker clock, resampling, DuckDB catalog | done, verified on an FTMO demo feed |
| Features (indicators checked against TA-Lib, candle/volume/session), market structure, regimes | done, no look-ahead by test |
| Pattern similarity (5 measures, leakage-safe search), outcome statistics | done |
| Backtest engine (bid/ask, spread, slippage, commission, swap, risk engine, FTMO profiles), metrics, pre-registered edge criteria | done |
| ML benchmark (logistic, forest, XGBoost, LightGBM) with calibration | done |
| Signal engine (BUY/SELL/**WAIT**, 12 refusal reasons, evidence gate), read-only API, dashboard, paper trading | done |
| Forward test on new data (calendar-time bound), news calendar data, live execution | **not done** (live execution is out of scope by decision) |

**Result.** Three pre-specified baselines and four models failed the pre-registered criteria on the
development and validation periods; the test period was never touched. The signal engine therefore
answers WAIT. See `docs/reports/checkpoint-1.md`, `docs/research/model-evaluation.md` and
`docs/reports/final-status.md`. No performance claim should be made from this repository.

## Quick start (Windows, PowerShell)

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12-3.14 (tested on 3.12.13, 3.13.13 and 3.14.4).

```powershell
.\scripts\dev.ps1 setup      # uv sync --extra ml --extra api
.\scripts\dev.ps1 check      # ruff, format check, mypy --strict, pytest
```
Linux/macOS: `make setup`, `make check`.

Run the application (research only, localhost):

```powershell
uv run python scripts/serve_api.py                     # read-only API on 127.0.0.1:8000
cd apps/dashboard; npm ci; npm run build; npx next start -p 3000   # dashboard on :3000
uv run python scripts/current_signal.py                # the current signal as JSON
```

Optional MetaTrader 5 support (Windows only): `uv sync --extra mt5`, then copy `.env.example`
to `.env` (git-ignored) and fill in a **demo** account and `MT5_BROKER_TIMEZONE` (`NY+7` for the FTMO
demo server; see ADR-0008). To verify a terminal end to end:
`uv run --extra mt5 python scripts/verify_mt5.py`.
Never put account numbers or passwords in `.env.example`; that file is committed.

## Example: offline file to validation report

```python
from datetime import UTC, datetime
from xau_edge.domain.bars import BarRequest
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.importers.file_source import FileBarSource
from xau_edge.market_data.validators import validate_bars

tf = Timeframe.M15
source = FileBarSource(
    "XAUUSD15.csv", symbol="XAUUSD", timeframe=tf, source_timezone="Europe/Athens"
)  # zone of the file's timestamps
bars = source.fetch_bars(
    BarRequest(
        symbol="XAUUSD",
        timeframe=tf,
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2025, 1, 1, tzinfo=UTC),
    )
)
print(validate_bars(bars, tf).summary())
```

## Layout

```
src/xau_edge/        domain/ market_data/ features/ structure/ patterns/ outcomes/ strategies/
                     backtest/ risk/ news/ models/ evaluation/ experiments/ signals/ execution/
                     api/ observability.py config.py
apps/dashboard/      Next.js dashboard (read-only)
configs/             brokers/ (measured profiles) prop/ (FTMO rules, verified 2026-10-08)
tests/               unit/ integration/ regression/ statistical/ fixtures/
docs/                PROJECT_PLAN.md BRIEF.md ROADMAP_TRACEABILITY.md architecture/ research/
                     decisions/ (ADR-0001..0018) evals/ risk/ testing/ operations/ reports/
data/ models/ experiments/runs/   git-ignored local data, artifacts and run records
.claude/             ECC components (project-local, minimal profile, no hooks)
```

## Documents

* `AGENTS.md`: rules for AI coding agents (safety boundaries, commands, definition of done)
* `docs/reports/final-status.md`: where the product stands against the brief (start here)
* `docs/PROJECT_PLAN.md`, `docs/ROADMAP_TRACEABILITY.md`, `docs/BRIEF.md`
* `docs/evals/edge-criteria.md`: the pre-registered rules that decide whether anything "works"
* `docs/architecture/`, `docs/research/`, `docs/risk/`, `docs/operations/`, `docs/decisions/`
* `docs/reports/`: one report per sprint, `checkpoint-1.md`, `mt5-verification.md`
