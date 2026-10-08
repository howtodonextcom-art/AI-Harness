# Sprint 8 - Report

Date: 2026-10-08. Scope: Epic 14 (risk engine core and prop profiles), Epic 10 part 1 (backtest engine
with costs, fills and sizing), Epic 19 part 1 (news interface). Research only; live trading does not exist.

## Delivered

| Item | Module / file |
|---|---|
| Position sizing (rounds down, never exceeds the budget) | `risk/sizing.py` |
| FTMO 2-Step and 1-Step profiles, verified against ftmo.com on 2026-10-08 | `configs/prop/*.yaml`, `risk/prop_rules.py` |
| Risk engine: 12 refusal reasons, all reported; latching kill switch with reset phrase | `risk/engine.py`, `risk/kill_switch.py`, `docs/risk/risk-engine.md` |
| News interface, CSV loader, window guard that refuses to answer outside coverage | `news/calendar.py` |
| Backtest engine: bid/ask fills, spread from the data, slippage, commission, swap, gaps, one position, risk checks, prop days | `backtest/engine.py`, `backtest/costs.py`, ADR-0015 |

## Evidence

* **Tests first:** fill-model expectations were computed by hand from the reference numbers in the
  test header (entry 100.23, stop 97.23, target 106.23, 1.66 lots, 498 USD risk, exactly 2.00 R);
  the engine matched on the first run.
* **Mutation spot-check:** 31 mutants first pass (sizing rounding, floors, every guard boundary, kill
  switch latching, news window, rollover counting, bid/ask handling, stop/target triggers, gap fills,
  slippage, commission, swap, counters, entry gap, hold conversion, floating mark). 7 survived; tests
  added for inclusive limits, a max-loss-only breach, short target on the ask, swap in net P&L,
  win-resets-streak, the exit-bar signal and the short floating mark; after the review fixes another
  11 mutants, one survivor (daily risk accumulation), killed by a same-day budget test.
* **Independent review (1 reviewer, risk + security stance):** found 3 HIGH, all fixed with tests:
  a NaN spread passed the spread guard (now `MARKET_STATE_INVALID`); an unknown regime or missing
  news calendar silently disabled a guard (now refused by default, research runs must opt out
  explicitly); corrupt bars (NaN low) produced normal-looking results (now rejected). MEDIUM fixed:
  floors are scanned against intrabar worst-case equity (`equity_low`); risk is credited to the entry
  day; non-UTC and naive decision times; calendar window must lie inside the coverage; weekends no
  longer charge two extra swap nights. No fill-model, sizing or look-ahead defect found.
* 806 tests, 98% coverage, ruff and `mypy --strict` clean.

## Not done on purpose or not possible

* **Holiday calendar:** deferred again. It only reclassifies validator warnings, nothing consumes it
  yet, and the backtest treats market closures through gaps in the data.
* **News data:** no calendar data source exists in the project; the guard and interface are tested,
  but the pre-registered news-window backtest (5-60 minutes) cannot be run without data. Backtests
  in Sprint 9 therefore run with `require_news_calendar=False`, which the reports must state.
* **Wednesday triple swap, partial fills, requotes, latency, margin:** not modelled (ADR-0015).
* **Kill-switch persistence across restarts and operator-token reset:** not needed until live
  execution exists (review finding, accepted).
* **Rules not verified from the FTMO objectives page:** restrictions on automated trading, news
  trading, hedging and copy trading are marked `unverified` in the profiles.

## Red-team: how could this sprint be wrong?

| Question | Finding | Status |
|---|---|---|
| Slippage assumption | 3 points per stop/market fill is not measured | Open; Sprint 9 reports sensitivity |
| Commission | 0 for the account type is unverified | Open |
| Swap values | Read once on 2026-10-08; they change | Documented |
| Bars are bid with a per-bar spread | The spread inside a bar can be wider than the bar's recorded value, especially at news | Open |
| Entry at the next open | Real latency can be worse | Open |
| One position at a time | Understates opportunity | By design |
| FTMO rule drift | Profiles carry a verification date; rules change | Re-verify before use |
| Fail-open paths | Three found and fixed; more may exist in code written later | Reviews continue each sprint |
