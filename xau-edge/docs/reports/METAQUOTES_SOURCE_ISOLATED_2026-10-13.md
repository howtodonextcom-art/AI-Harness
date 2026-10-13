# MetaQuotes-Demo as an isolated market source (2026-10-13)

Request: the FTMO terminal lost its login (`MT5 initialize failed: (-6, 'Authorization failed')`), a MetaQuotes-Demo terminal is logged in; connect the code to it. Option A was chosen: a second, isolated and labelled source. FTMO stays the research baseline.

## What was found (read-only probe of the MetaQuotes terminal)

| | FTMO (baseline) | MetaQuotes-Demo |
|---|---|---|
| Terminal | `C:\Program Files\FTMO Global Markets MT5 Terminal` | `C:\Program Files\MetaTrader 5` |
| Server clock | NY+7 | NY+7 (tick time was UTC+3 in October, same scheme), so `BrokerClock` needs no change |
| XAUUSD | digits 2, contract 100 | digits 2, contract 100, volume min 0.01 |
| Spread at probe | about 40 points | 26 points |
| Account | demo | demo |
| History | deep | M1 from 2026-06-29 (Max bars 100000), M5 from 2025-05, M15 from 2022, H1 from 2009, H4 from 2004 |

Only one place was hard-wired to FTMO for the live feed: the terminal path (collector, API, backfill, start script) and the `data/market` and `data/trade` roots.

## Design

- `market_data/source_profile.py`: profiles `ftmo` (default) and `metaquotes`, selected by `XAU_EDGE_MARKET_SOURCE`. Each has its own terminal, bar store (`data/market-metaquotes`) and desk store (`data/trade-metaquotes`).
- Two guards that configuration cannot switch off: the connected account server must contain the profile marker (collector and backfill refuse a foreign terminal, nothing is written), and each store records its first writer in `source.json` and refuses any other source.
- `/trade/decision` carries `market_source {id, label, server, research_baseline}`; the header shows a violet pill "Nguồn MetaQuotes-Demo · không phải FTMO" when the source is not the baseline. FTMO shows no extra badge.
- `scripts\start_market_stack.ps1 -Source metaquotes [-Dashboard]` starts the whole stack on that source (terminal, roots, health check). Default stays `ftmo`.

## What did not change

Strategy, gates, thresholds, risk, news guard, demo/funded locks, calendar template (still the FTMO weekly template: if MetaQuotes gold closes at other hours the effect is fail-closed, MARKET_CLOSED or STALE_DATA), cost model (still the FTMO calibration, so net R:R on this source is an approximation).

## Evidence

- FTMO store untouched: M1 parquet fingerprint `e29c00b4a50f2014` and 4596 files before and after; no `source.json` was written there.
- MetaQuotes store: `source.json` = metaquotes; backfill wrote H4 to M1; collector health GOOD, quote and last bar FRESH, `/trade/decision` shows `market_source` MetaQuotes-Demo, decision WAIT (SPREAD_TOO_WIDE judged against this feed's own recent spreads).
- Tests: `tests/unit/market_data/test_source_profile.py` (5), Playwright `e2e/market_source.spec.ts` (2), contract goldens regenerated; ruff, mypy strict clean.

## Limits to know

- Data from this source is NOT research evidence: spread, session and costs differ, and forward evidence, coverage and the "no edge" conclusions remain FTMO-only. Nothing from this store may be mixed into `data/market`.
- Its M1 history is shorter (about 3.5 months), so the percentile-based regime gates warm up on less data.
- To return to FTMO: log the FTMO terminal in again and start with `-Source ftmo` (or no flag).
