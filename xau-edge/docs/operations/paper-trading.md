# Paper trading and forward testing

Brief sections 30-32 and Epics 17-18. Code: `xau_edge.execution`, `POST /paper/orders`,
`scripts/forward_test.py`. Decisions: ADR-0018.

## What exists

* **`ExecutionBroker` interface** (`execution/interface.py`): `get_account`, `get_positions`,
  `submit_order`, `cancel_order`, `close_position`, `modify_position`. Trading logic depends on this,
  not on any broker.
* **`PaperExecutionBroker`**: simulated broker with the backtest's fill rules (bid bars plus spread,
  ask for long entries, slippage, stop first when both levels are touched, gap fills, commission, swap,
  floating equity). Every event is appended to `data/paper/journal.jsonl` with the signal hash.
* **`PaperTrader`**: the only way a signal becomes a paper order. Order of checks: WAIT never trades;
  expired signals and repeats are refused; the risk engine sizes and may refuse; the safety limits
  (environment, account, symbol, maximum lots, orders per day, dry-run) may refuse; only then the
  broker fills. Levels and size come from the signal and the risk engine, never from a client.
* **API**: `POST /paper/orders` accepts no trade parameters (only an optional decision time, which must
  be the latest bar); `GET /paper/account`, `GET /paper/positions`. No other route can write.
* **No live broker.** There is no `MT5ExecutionBroker`, nothing in `execution/` imports a broker
  library, a test scans for order functions, and `Settings` rejects `ENABLE_LIVE_TRADING=true`.

## Running it

```text
uv run python scripts/serve_api.py          # API on 127.0.0.1:8000, paper trader attached
cd apps/dashboard && npm run build && npx next start -p 3000
uv run python scripts/forward_test.py --hours 6      # replay recent bars through the paper trader
```

Paper session state is held in memory (it resets when the API restarts); the journal file is the
durable record.

## Replay is not forward evidence

`forward_test.py` on bars that already exist is a replay: it checks that the whole pipeline works and
counts every refusal reason. A forward test is the same loop run repeatedly on bars that did not
exist when the rules were fixed (append new bars to the raw store, rerun, keep the journal). Judge it
with `compare_paper_to_backtest`, which refuses any conclusion below 100 paper trades and then
reports whether the backtest's mean R lies inside the paper trades' day-block bootstrap interval.

## Current state (2026-10-08)

The evidence gate is closed (no configuration passed the pre-registered criteria), so every signal is
WAIT and the paper trader places no orders; a three-hour replay of the newest data produced 9 decisions and
0 orders, all refused with `NO_VALIDATED_EDGE` and `NEWS_UNKNOWN` (no news calendar), several also
for `EDGE_INSUFFICIENT`, `EV_NOT_POSITIVE` or `ENTRY_QUALITY_POOR`. The machinery is tested with injected valid signals, not by relaxing the gate.

## Before any real use of the results

Calendar-time forward testing has not started (it needs weeks of new data and a candidate that passed
validation); a news calendar must be supplied; slippage, commission and swap assumptions must be
measured on the account type; the kill switch is in-process only. Live execution would be a separate
project decision with its own review.
