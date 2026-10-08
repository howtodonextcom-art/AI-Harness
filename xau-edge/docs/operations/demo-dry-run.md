# Demo bot, dry-run on real data (Turn 3)

The bot reads **real XAUUSD bars** from the local MT5 **DEMO** terminal (market data only), builds the
signal, runs it through the signal bridge and journals the decision. It **never sends an order**: there
is no execution adapter yet, and `scripts/demo_trader.py` refuses to start if `XAU_EDGE_DEMO_DRY_RUN`
is false. Live trading stays impossible (ADR-0018/0019).

## Run it

Prerequisites: Windows, the MT5 terminal running and logged in to a DEMO account, `uv`.

```powershell
cd xau-edge
uv run --extra mt5 python scripts/demo_trader.py --once    # one cycle
uv run --extra mt5 python scripts/demo_trader.py           # loop: one cycle per M15 close (+20 s)
```

Set `XAU_EDGE_DEMO_MAGIC` in `.env` (any integer you choose); without it every signal is refused with
`MAGIC_NOT_CONFIGURED`. Stop with Ctrl+C.

## What each cycle does

1. Refresh the raw store with the bars that closed since the last fetch (all four timeframes).
2. Merge through the catalog and validate each timeframe; a failure skips the cycle (`DATA_INVALID`).
3. Read the account (balance, equity) from the terminal; positions are **not** read yet.
4. Decide on the latest closed M15 bar; refuse stale data (older than 30 minutes) or an already
   processed bar.
5. Pass the signal through the bridge (evidence gate, news, risk engine, safety, kill switch,
   idempotency) and append one line to `data/execution/cycles.jsonl`.

## Files

| File | Meaning |
|---|---|
| `data/execution/cycles.jsonl` | one line per decided bar: direction, reasons, intent id, data age |
| `data/execution/state.sqlite` | kill switch, seen signals, last bar, daily counter |
| `data/execution/heartbeat.json` | last cycle time and status, for an external watcher |
| `data/execution/demo_trader.lock` | single-instance lock; delete it only if no bot is running |

## Reading the result

`WAIT` with `NO_VALIDATED_EDGE` is the expected answer: no strategy has passed the pre-registered
validation (see `docs/reports/final-status.md`). `NEWS_UNKNOWN` appears until an economic calendar
is supplied. An accepted line (an intent with `dry_run: true`) can only appear after the evidence gate
opens, and still places nothing.

## Known limits

* Open positions and the day's realised statistics are not read from the terminal, so the risk engine
  sees an empty book (reconciliation arrives with the broker adapter).
* Account capital is taken from the current balance; set the real challenge size when it matters.
* The kill switch has no CLI yet; it can be tripped through the state API only.
