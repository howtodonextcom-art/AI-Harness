# Demo execution architecture

```
M15 close
  -> refresh_market_data (read-only MT5, closed bars only)      market_data/refresh.py
  -> validate + merge (catalog)                                  market_data/
  -> generate_signal (evidence gate, news, regime, analogues)    signals/
  -> DemoReader.snapshot (account, positions, closed deals)      brokers/mt5_demo/reader.py
  -> Reconciler.check (broker vs persistent state)               execution/reconcile.py
  -> SignalBridge (kill switch, freshness, duplicate, risk,
                   safety, exactly-once record)                  execution/bridge.py
  -> OrderIntent (deterministic id, SL/TP, magic, comment)       execution/order_intent.py
  -> Mt5DemoExecutor.submit  (only if demo mode is on)           brokers/mt5_demo/executor.py
  -> journal, status.json, heartbeat                             execution/{journal,status}.py
  -> read-only API (/bot/*) -> dashboard "Demo bot" panel        api/bot.py, apps/dashboard
```

Package boundary (ADR-0019): `execution/` is broker-neutral and contains no terminal calls (a test
scans it). `brokers/mt5_demo/` is the only place that talks to the terminal about positions and orders,
through two allowlist proxies (query-only reader, executor). `order_send` has exactly one call site
(`_guarded_send`), enforced by a test.

State (`state.sqlite`, fail-closed): kill switch, seen signals and approvals, last decision bar, daily
order counter and risk, bot positions, submissions (exactly-once), account baseline (initial capital,
day start, high-water mark). A corrupt or unexpected file is never repaired or recreated.

Failure policy: any gate error refuses; an outcome that cannot be proven (no answer, ambiguous
retcode, position not found) trips the kill switch and nothing is retried; a position whose stop or
target is not as ordered is closed at once and stops the bot.
