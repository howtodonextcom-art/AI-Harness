# ADR-0019: Demo-only execution scope and package boundary

Status: accepted (2026-10-08)

Amends: ADR-0018. ADR-0018 remains correct for live trading and for the read-only API/dashboard:
there is still no live broker path, no arbitrary order endpoint, and `market_data/mt5/` remains
read-only. This ADR opens a separate, future **demo-only** execution track so the project can test
operational mechanics on an MT5 demo account without weakening the research evidence gate.

## Decision

Demo execution may be implemented only after the safety design below is in place:

* Live trading stays impossible: `XAU_EDGE_ENABLE_LIVE_TRADING=true` is still rejected by
  `Settings`.
* Demo execution is disabled by default: `XAU_EDGE_ENABLE_DEMO_TRADING=false`.
* Demo execution starts in dry-run: `XAU_EDGE_DEMO_DRY_RUN=true`.
* Real demo order submission requires explicit account whitelist and magic number configuration.
* The existing signal evidence gate, risk engine and `ExecutionSafety` must stay in the path from
  signal to broker. No direct `Signal -> order_send` path is allowed.
* `WAIT`, expired, incomplete, duplicate, stale, news-unknown, risk-denied or safety-denied signals
  must never reach a broker adapter.
* A persistent kill switch and persistent idempotency store are required before any demo broker can
  submit orders.
* Broker reconciliation is required before submit, close or modify. Unknown broker state fails
  closed.

## Package boundary

`src/xau_edge/execution/` remains broker-neutral orchestration. It may contain order intent schemas,
state, journals, reconciliation contracts and signal/risk/safety bridges. It must not import
`MetaTrader5` or call MT5 order APIs.

Any MT5 demo order adapter must live outside `execution/`, for example under:

```text
src/xau_edge/brokers/mt5_demo/
```

That package is the only future place where MT5 order APIs such as `order_send`, `positions_get` or
`orders_get` may appear, and only behind demo-account, whitelist, dry-run, idempotency and
reconciliation checks. The existing market-data adapter in `src/xau_edge/market_data/mt5/` remains
read-only and keeps its allowlist proxy.

## API and operator control

No new write API route is part of the initial demo execution track. Manual kill switch operations
should be implemented first as local CLI commands so the existing route-table safety invariant stays
intact. If a dashboard kill-switch route is added later, it needs a new ADR update, a local operator
token, route-table tests, origin checks and no automatic reset endpoint.

## Kill-switch policy

When the kill switch trips, the system stops opening new positions. It does **not** automatically
close open positions by default. Auto-close-on-kill would be a separate owner decision because it can
create unintended exits. Any close action must be limited to bot-owned positions identified by
symbol, magic number and comment/hash.

## Order lifecycle and unknown state

Future demo execution must manage the full position lifecycle, not only submit:

* `max_hold_until` must be enforced by the runner.
* Submit/close/modify may act only on bot-owned positions.
* If an order request times out or the terminal disconnects after a possible send, the adapter must
  reconnect and query broker state by symbol, magic and idempotency comment/hash. If it cannot prove
  whether an order exists, it must trip the kill switch and must not retry blindly.

## Credentials

Data-only MT5 scripts should continue to use the investor/read-only password when the broker
supports it (`MT5_PASSWORD`). Future demo execution must use a separate `MT5_TRADE_PASSWORD` and
must never commit account identifiers or passwords.

## Non-goals

This ADR does not authorize live trading, profitability claims, lowering the edge criteria,
arbitrary order endpoints, or using demo fills as evidence of live profitability.

## Implementation status (2026-10-08)

Built and tested against a fake terminal: persistent state and kill switch (`execution/state.py`),
bridge, order intent, reconciliation, execution journal, kill-switch CLI, read-only `/bot/*` API and
dashboard panel, health alerts, and the demo executor under `brokers/mt5_demo/` with its allowlist
proxies. Package boundary as decided: `execution/` stays free of terminal calls (still scanned by a
test); the one narrowing of ADR-0018's wording is that `brokers/mt5_demo/` may import the terminal
module and call `order_send` through a single guarded function. Live trading remains impossible.

Open: the real `order_send` path has not been exercised (needs `MT5_TRADE_PASSWORD`, kept in a variable
separate from the investor password); no economic calendar is supplied; no strategy has passed
validation, so no signal is BUY/SELL. See `docs/operations/demo-trading.md`.
