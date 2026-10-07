# System architecture

XAU EDGE is an explainable probabilistic decision-support system for XAUUSD. It is a research
platform: **no live trading exists in this codebase**, and `XAU_EDGE_ENABLE_LIVE_TRADING=true`
is rejected at configuration load.

## Principle: forecasting is separate from the trading decision

```
Market data -> Features -> Structure/Regime -> Pattern analogues -> Outcome statistics
     -> Forecast -> Probability calibration -> Expected value (after costs)
     -> Market context -> Entry quality -> Risk engine -> BUY | SELL | WAIT
```

A forecast never becomes an order directly. `WAIT` is a first-class output.

## Layers and status

| Layer | Package | Status |
|---|---|---|
| Domain contracts (timeframes, bars, instrument) | `xau_edge.domain` | **Sprint 1, done** |
| Settings and safety switches | `xau_edge.config` | **Sprint 1, done** |
| Data sources (interface, file adapter, MT5 adapter) | `xau_edge.market_data` | **Sprint 1, done** (MT5 not yet run against a live terminal) |
| Raw storage (immutable, content-addressed) | `xau_edge.market_data.store` | **Sprint 1, done** |
| Validation | `xau_edge.market_data.validators` | **Sprint 1, done** |
| Resampling, dataset catalog (DuckDB) | `market_data.resampling` | Sprint 2 |
| Features, structure, regimes | `features`, `structure`, `regimes` | Sprints 3-4 |
| Pattern similarity, outcomes | `patterns` | Sprints 5-6 |
| Backtest, baselines | `backtest` | Sprints 6-7 |
| ML, calibration, signal, risk | `models`, `signals`, `risk` | Later |
| API, dashboard, paper trading, execution | `apps/*`, `paper`, `execution` | Later; execution stays disabled by default |

## Contracts established in Sprint 1

* **Bar frame** (`xau_edge.domain.bars.BAR_SCHEMA`): `timestamp` (bar **open** time,
  `Datetime[us, UTC]`), `open/high/low/close` (`Float64`), `tick_volume`, `spread` (points),
  `real_volume` (nullable) as `Int64`. Column order is fixed.
* **Sources** implement `BarSource.fetch_bars(BarRequest) -> DataFrame` for `[start, end)` in UTC.
  Sources never sort, de-duplicate or repair; they return what they read.
* **Validators** report, never repair. `ERROR` means unfit for research use; `WARNING` is
  informational (weekend bars, missing bars below threshold, wide spreads).
* **Raw data is immutable**: files are named by content hash, written once, marked read-only;
  a different payload at an existing path raises.
* **Time**: everything inside the platform is UTC. MT5 reports broker server wall-clock labelled
  as UTC, so `MT5_BROKER_TIMEZONE` is mandatory and conversions raise on DST ambiguity.
* **Safety**: the MT5 adapter exposes market data only; a test fails if any order/position API
  name appears in `market_data/mt5`.

## Deviations from the original repository sketch

See `docs/decisions/`. In short: a single installable package `xau_edge` under `src/` instead of
many top-level folders (ADR-0001); `apps/` and `packages/` are created when the API and dashboard
begin; `data/` subfolders exist with `.gitkeep` and their contents are git-ignored.

## Data flow (Sprint 1)

```
CSV/Parquet or MT5 -> BarSource.fetch_bars -> RawStore.write (immutable Parquet)
                                           -> validate_bars -> ValidationReport
```
