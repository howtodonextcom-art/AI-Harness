# Demo bot status after turns 3-7 (2026-10-08)

Written for the project owner. Scope: MT5 DEMO only. Live trading cannot be enabled.

## What was verified on real data

* Three consecutive live cycles of `scripts/demo_trader.py` against the FTMO demo terminal
  (13:00 and 13:15 UTC bars decided 20 s after the close, data age under one minute), every one
  journalled; restart on the same bar was refused (`BAR_ALREADY_PROCESSED`); reconciliation clean
  against the real account and positions; heartbeat and `status.json` written; dashboard panel
  checked in a browser at 1440x900 and 390 px with no console errors.
* Every decision was WAIT (`NO_VALIDATED_EDGE`, `NEWS_UNKNOWN`): the evidence gate is closed.
* A real attempt to enable the smoke order was stopped by the `TRADING_NOT_ALLOWED` gate: the terminal
  is logged in with the investor password.

## What is covered by tests only (fake terminal)

Order gates, exactly-once submission, unknown-state handling (trip, no retry), partial and ambiguous
answers, protective-level check with immediate close, closing only bot-owned positions, expiry close,
broker-closed positions, trading-password connection. 1,230+ tests, ruff, mypy strict, CI green.
An independent adversarial review found 3 HIGH and several MEDIUM issues; all were fixed with tests.

## Scores (my estimate, with evidence)

| Item | Score | Why not 100 |
|---|---:|---|
| Demo bot dry-run on real data | 92 | not yet run for 24 h unattended; no alert delivery beyond files and the health command |
| Broker demo real-order readiness | 80 | the real `order_send` has never run: it needs `MT5_TRADE_PASSWORD` in `.env` (owner action) |
| `gap-audit.md` technical items | 85 | calendar data source not supplied (A6); costs not measured from real fills (A7) |
| Web app operational completeness | 88 | read-only by design; no browser test in CI; kill switch is a local command |

## What cannot reach 100 by engineering

* **Orders will not appear while no strategy passes validation.** That is the correct behaviour, not a
  defect, and is not something code can change without lowering the pre-registered criteria.
* **News calendar:** the loader and wiring exist (`XAU_EDGE_NEWS_CALENDAR_PATH`, coverage header
  required); a reliable data source must be supplied.
* **Trading password and FTMO terms on automation:** owner decisions.

## To finish the remaining engineering items

1. Put `MT5_TRADE_PASSWORD` in `.env`, set the variables in `docs/operations/demo-trading.md` section 4,
   run `scripts/smoke_demo_order.py --yes-send-one-demo-order` once, and keep the output.
2. Supply a calendar CSV and rerun the news-window study.
3. Run the bot for several days and use the journal to measure demo slippage and costs.
