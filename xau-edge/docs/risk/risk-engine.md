# Risk engine

Brief sections 28-29 and 32. Code: `xau_edge.risk`. Independent of forecasting: it sees a trade request
(direction, stop distance), an account snapshot and the market state, and answers allowed/refused.

## What it checks (all reasons are reported, not just the first)

| Reason | Rule |
|---|---|
| `KILL_SWITCH` | the latching stop is tripped; only a human can reset it (exact confirmation phrase) |
| `ACCOUNT_STATE_INVALID` | non-finite or non-positive balances, negative lots/risk: refuse, never trust |
| `SIZE_TOO_SMALL` | even the minimum lot would exceed the risk budget (stop too wide) |
| `DAILY_LOSS_BUFFER` | equity after the stop would fall below the daily-loss floor plus the internal buffer |
| `MAX_LOSS_BUFFER` | same for the maximum-loss floor |
| `MAX_CONCURRENT` | open positions at the configured limit (default 1) |
| `MAX_EXPOSURE` | open lots plus the new lots above the cap (inclusive limit) |
| `DAILY_RISK_BUDGET` | risk already taken today plus this trade above the day's budget |
| `CONSECUTIVE_LOSSES` | the configured number of losses in a row today (a win or a new day resets) |
| `SPREAD` | spread above the limit (inclusive limit) |
| `VOLATILITY` | the regime is blocked (default `SHOCK`) |
| `NEWS` | inside a configured window around a high-impact event |

Size: `lots = floor(equity x risk_fraction / (stop_distance x contract_size))` to the lot step, never
rounded up, so the stop can never lose more than the budget.

## Where the numbers live

* Trade limits: `RiskLimits` (defaults: 0.5% risk per trade, 1 position, 10 lots, 2% daily risk budget,
  3 consecutive losses, 120 points spread).
* Prop-firm rules: `configs/prop/ftmo_2step.yaml` and `ftmo_1step.yaml`, with the source URL and the
  date they were verified (2026-10-08). Nothing is hard-coded in trading logic. Re-verify before use:
  FTMO changes its rules. Restrictions on automated trading, news trading, hedging and copy trading
  are marked `unverified` because the objectives page does not state them.
* Internal buffer: the engine keeps 40% of each loss limit unused by default, so a stop-out cannot
  take the account to the limit.

## FTMO floors as implemented

* Daily: floor = balance at 00:00 CE(S)T minus 5% (2-Step) or 3% (1-Step) of the initial capital;
  measured on equity.
* Maximum loss: 2-Step static floor = initial capital minus 10%; 1-Step trailing = highest end-of-day
  balance minus 10% (never below the static floor).
* Equity below either floor trips the kill switch.

## News

`xau_edge.news` defines the interface and a CSV loader; no calendar data is bundled. Asking about a
time outside the declared coverage raises `CalendarUnavailableError`: a missing calendar must never
look like "no news". The window sizes (5-60 minutes) are parameters to be backtested, not assumed.

## Limits of this component

The kill switch is in-process state (not persisted), live execution does not exist, and the
account snapshot is trusted to be honest once it passes validation. Before any live use, account
state would have to come from the broker, the switch would have to persist across restarts, and
a second independent check would be required.
