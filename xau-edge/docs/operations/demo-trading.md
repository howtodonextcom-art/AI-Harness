# Demo trading runbook

**Scope: an MT5 DEMO account only. No live trading exists or can be enabled (ADR-0018, ADR-0019).**
A bot that answers WAIT all day is working correctly: while no strategy has passed the pre-registered
validation, the evidence gate is closed and no order can be created.

## 1. Setup

1. Install and log in to the MT5 **demo** terminal (Windows). Note the terminal path.
2. `uv sync --extra mt5 --extra api`, `cp .env.example .env`, then fill `.env` (never commit it):
   `MT5_LOGIN`, `MT5_SERVER`, `MT5_BROKER_TIMEZONE`, `MT5_PASSWORD` (investor, read-only, used for data).
3. Check the data path works: `uv run --extra mt5 python scripts/demo_trader.py --once`.

## 2. Dry-run (default, sends nothing)

```powershell
uv run --extra mt5 python scripts/demo_trader.py            # one cycle per M15 close
uv run python scripts/serve_api.py                          # read-only API on 127.0.0.1:8000
cd apps/dashboard; npm run build; npm run start             # dashboard on http://localhost:3000
```

Set `XAU_EDGE_DEMO_MAGIC` (any integer). The dashboard "Demo bot" panel shows mode, account,
positions, reconciliation, alerts, recent decisions and the execution journal. Files live in
`data/execution/` (`cycles.jsonl`, `journal.jsonl`, `state.sqlite`, `status.json`, `heartbeat.json`).

## 3. Enable demo order sending (deliberate, explicit)

All of these are required; otherwise the bot stays in dry-run:

```
XAU_EDGE_ENABLE_DEMO_TRADING=true
XAU_EDGE_DEMO_DRY_RUN=false
XAU_EDGE_DEMO_ALLOWED_ACCOUNTS=<your demo login>
XAU_EDGE_DEMO_MAGIC=<integer>
XAU_EDGE_DEMO_MAX_LOTS=<small>            XAU_EDGE_DEMO_MAX_ORDERS_PER_DAY=<small>
XAU_EDGE_DEMO_INITIAL_CAPITAL=<challenge size>
MT5_TRADE_PASSWORD=<trading password>     (a different variable from the investor password)
```

Orders additionally need: a BUY/SELL signal (evidence gate open, news known and clear), the signal
bridge's approval, a clean reconciliation, a clear kill switch, a fresh price, one bot position at
most. Check the FTMO terms on automated trading yourself before enabling this.

## 4. Pipeline smoke test (optional, one order)

Tests the plumbing with ONE minimum-lot labelled order, closed at once. It is not evidence about
any strategy. Needs the settings of section 3 plus `XAU_EDGE_DEMO_SMOKE=true`:

```powershell
uv run --extra mt5 python scripts/smoke_demo_order.py --yes-send-one-demo-order
```

## 5. Kill switch

```powershell
uv run python scripts/kill_switch.py status
uv run python scripts/kill_switch.py trip --reason "why"
uv run python scripts/kill_switch.py reset --confirm "I understand the risk"
```

A tripped switch blocks NEW orders only. It does not close positions; closing is a separate, manual
decision (the bot closes only its own positions, at `max_hold_until`). It survives restarts and trips by
itself on: reconciliation mismatch, unknown order state, protective levels missing.

## 6. Health and recovery

* `uv run python scripts/check_health.py` exits 1 on any critical alert (stale heartbeat, tripped
  kill switch, dirty reconciliation, unreachable terminal). Run it from Task Scheduler.
* After a crash: check the state with `scripts/kill_switch.py status` and `data/execution/journal.jsonl`.
  Restarting is safe: signals already acted on and orders already sent are remembered. A submission
  with no final outcome (`UNRESOLVED_SUBMISSION`) keeps the bot stopped until you inspect the terminal.
* Orphan position (bot lost track of an order): close it by hand in the terminal, then clear the kill
  switch. The bot never touches positions it does not own.
* A stale lock (`data/execution/demo_trader.lock`): delete it only if no bot process is running.

## 7. Do not run when

The account is not DEMO or not whitelisted, the clock or data are stale, the economic calendar is
missing (signals stay WAIT anyway), you have manual positions on XAUUSD (reconciliation will stop the
bot), or the FTMO rules for automation are unverified.

## 8. Incident checklist

1. `kill_switch.py trip`; 2. read `journal.jsonl` and the dashboard alerts; 3. compare the terminal's
positions with `status.json`; 4. fix by hand in the terminal; 5. record what happened; 6. reset only
when reconciliation is clean.

## Known limits

Fill prices on demo are not live fills; swap, slippage and commission are measured on demo and
approximate. The bridge, executor and reconciliation are tested against a fake terminal; the real
`order_send` path has not yet been exercised (it needs `MT5_TRADE_PASSWORD`).
