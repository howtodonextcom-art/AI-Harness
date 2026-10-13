# ADR-0015: Backtest fill and cost model

Status: accepted (2026-10-08)

**Execution data.** M5 bars with their own spread (points). A derived higher-timeframe spread is not
the broker's (mt5-verification report), so strategies on M15 or M5 are all filled on M5 bars. Bars are
bid prices; ask = bid + spread.

**Fills.** Entry at the open of the first bar at or after the decision time (never inside a gap larger
than 30 minutes). Long entry pays ask plus slippage, short entry sells at bid minus slippage. Long
exits trigger on bid prices, short exits on ask prices. A bar touching both barriers resolves to the
stop. A stop that gaps through its level fills at the open (no extra slippage on top). Other stop
fills and time exits get adverse slippage; targets fill at their level.

**Costs.** Spread comes from the data; slippage is an ASSUMPTION (3 points per market or stop fill,
not measured); commission is 0 by default and UNVERIFIED for the account type; swap uses the
terminal values read on 2026-10-08 (long -76.05, short -4.2 points per lot per night, charged per
17:00 New York rollover; Wednesday triple swap not modelled). Every report must print these.

**One position at a time.** Overlapping signals are skipped and counted. This understates
opportunity and avoids pyramiding assumptions.

**Prop-firm days.** The day boundary is midnight CE(S)T (Europe/Prague). A breach of a floor trips
the kill switch for the rest of the run; `prop_breaches` also scans the equity curve afterwards.

**Not modelled.** Partial fills, requotes, rejected orders, variable latency, stop-hunt/spread
widening at news beyond what the bar spread shows, holidays (no calendar), margin. Results are
therefore optimistic in ways that cannot be signed from data alone; edge criteria demand margin
(profit factor 1.2, lower confidence bound above zero) for that reason.
