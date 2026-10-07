# XAU EDGE

Probabilistic decision-support and research platform for XAUUSD.
**Research only. There is no live trading code and none can be enabled.**

The system is designed to answer: what is the regime and higher-timeframe bias, what happened
after historically similar structures, what are the calibrated probabilities and expected value
after costs, and should it say BUY, SELL, or **WAIT**. A high-quality "no trade" is a valid and
valuable output.

## Status

Sprint 1 complete: the market-data foundation.

| Capability | State |
|---|---|
| Domain contracts (timeframes M5/M15/H1/H4, bar schema, instrument) | done |
| Offline CSV/TSV/Parquet source (incl. MetaTrader exports, timezone-aware) | done |
| MT5 source (read-only market data) | implemented, **tested with a fake client only** |
| Immutable raw store (content-addressed Parquet) | done |
| Validation (14 issue codes, ERROR/WARNING) | done, tested on synthetic data only |
| Features, structure, patterns, backtest, signals, API, dashboard | planned (`docs/PROJECT_PLAN.md`) |

No backtest results or performance figures exist yet; none should be quoted.

## Quick start (Windows, PowerShell)

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12-3.14 (developed on 3.14.4).

```powershell
.\scripts\dev.ps1 setup      # uv sync
.\scripts\dev.ps1 check      # ruff, format check, mypy --strict, pytest
```
Linux/macOS: `make setup`, `make check`.

Optional MetaTrader 5 support (Windows only): `uv sync --extra mt5`, then copy `.env.example`
to `.env` and fill in a **demo** account and `MT5_BROKER_TIMEZONE`.

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
src/xau_edge/        domain/ market_data/ (importers, mt5, validators, store) config.py
tests/               unit/ integration/ (regression/ statistical/ arrive with their epics)
docs/                PROJECT_PLAN.md architecture/ research/ decisions/ reports/
data/                git-ignored raw/processed/features/patterns/backtests
.claude/             ECC components (project-local, minimal profile, no hooks)
```

## Documents

* `AGENTS.md`: rules for AI coding agents (safety boundaries, commands, definition of done)
* `docs/PROJECT_PLAN.md`: epics, acceptance criteria, risks, Sprint 2 recommendation
* `docs/architecture/system.md`, `docs/research/dependency-review.md`, `docs/decisions/`
* `docs/reports/sprint-1-report.md`
