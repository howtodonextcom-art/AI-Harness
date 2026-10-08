# MT5 verification (FTMO demo, XAUUSD)

Measured on 2026-10-08 with `scripts/verify_mt5.py` against a locally installed FTMO Global
Markets MT5 terminal (build 6241). The script is read-only, refuses to run unless the account
is a DEMO account, and does not record account identifiers or balances. The terminal itself had
algorithmic trading disabled (`trade_allowed = False`).

**Scope of these findings:** one broker, one demo server (`FTMO-Demo`), one symbol, 17 months of
history (2025-05-01 .. 2026-10-08). Nothing here is evidence about live accounts, other brokers,
or other symbols. Re-run the script before relying on it elsewhere.

## 1. Symbol specification (matches the `Instrument` defaults)

`digits 2`, `point 0.01`, `contract size 100`, `tick size 0.01`, `tick value 1.0 USD`,
`min volume 0.01`, `volume step 0.01`, profit currency USD, floating spread.
The Sprint 1 assumption (2 digits, contract 100) is now confirmed for this server. Swap rates
(long -76.05, short -4.2, mode 1) are recorded here for the cost model; they change over time
and must be read from the terminal when costs are modelled.

## 2. Server clock: New York + 7 hours (not an IANA zone)

* Live tick time minus real UTC = **+3.0 h** on 2026-10-08, equal to the profile's prediction
  (NY is UTC-4 in October, +7 = +3).
* Over 77 weekly session boundaries the last bar of the week always carries the server label
  `Fri 23:45` and the first bar the label `Mon 01:05`, including the weeks where US and EU
  daylight saving disagree (2025-10-27..11-01 and 2026-03-09..03-28).
* Scoring each candidate clock by how constant the weekly close is in New York time:

  | Clock | Consistency | Note |
  |---|---:|---|
  | `NY+7`, `NY+6`, `NY+8`, ... | 0.9675 | tie by construction (a constant shift); the live +3 h offset selects `NY+7`, and the 17:00 rollover anchor agrees (closest, 15 min) |
  | `Europe/Athens`, `Europe/Helsinki` | 0.9156 | wrong for the US/EU mismatch weeks |

  The 3.25% shortfall below 1.0 comes from holiday weeks with irregular closes, not from clock error.
* Consequence: `Europe/Athens` would shift bars by one hour for about 3-4 weeks per year.
  ADR-0008 records the decision.

## 3. Trading session (New York time)

* First bar of the week: Sunday 18:05. Last bar of the week: Friday 16:45 (closes 16:50).
* A **daily break 16:50-18:05** repeats every weekday (server 23:50-01:05): no bars exist for
  70 minutes, which is 15 missing M5 bars per day.
* US holidays show up as early closes (server 21:25 = NY 14:25 on 6 Mondays and 2 Thursdays in the
  sample) and a few irregular multi-hour or multi-day closures around Christmas, New Year,
  and Thanksgiving.

## 4. Terminal behaviour that affects data handling

* **Silent history truncation.** The terminal returns at most about 100,000 M5 bars and drops the
  oldest ones without any error: three consecutive fetches of the same request returned
  101,128, 99,999 and 100,000 rows. Row-level validation cannot see a missing prefix, so
  `check_coverage` compares the data with the requested range, and the append-only raw store plus
  `DatasetCatalog` merges fetches so earlier history is kept. Raising "Max bars in chart" in the
  terminal options (Tools, Options, Charts) is a manual step that was not changed.
* **Time arguments.** `copy_rates_range` treats the epoch of a timezone-aware datetime as server
  wall-clock. Naive datetimes are interpreted in the machine's local zone by the Python package
  (a 3-day request returned 734 rows with naive and 818 with aware datetimes). The adapter always
  passes aware datetimes shifted into server wall-clock.
* **History depth.** No data before 2025-05-01 for this symbol on this server (Jan-Apr 2025 return
  a single bar).
* **Forming bar.** The newest bar is still open; the script drops it.

## 5. Data quality on the dataset of record (merged fetches)

| Timeframe | Rows | Result | Findings |
|---|---:|---|---|
| M5 | 101,129 (3 fetches merged) | passed | 2 missing bars (single-bar gaps, Fri 11:30 and Mon 01:15 server time), 1,243 bars in holiday/early-close closures (warning), 7 spreads above 200 points |
| M15 | 34,073 | passed | 426 bars in closures, 1 wide spread |
| H1 | 8,522 | passed | 102 bars in closures |
| H4 | 2,228 | passed | 12 bars missing around irregular holiday schedules, 9 in closures |

Before the validator was corrected by this data it reported 372 false `WEEKEND_BARS` warnings on
M15/H1/H4 (a bar labelled inside the daily break but trading later in its span is not closed) and
counted holiday early closes as data loss, which made M5 fail. Both are fixed and covered by tests.

Spread over 101,150 M5 bars: median 31, p95 57, p99 67, p99.9 105, maximum 942 points; 120 bars
above 100, 7 above 200, 1 above 500. The profile warns above 200.

## 6. Derived bars versus the broker's own bars

M5 was resampled to M15, H1 and H4 on server-clock boundaries and compared with the broker's bars:

| Target | Compared | Exact matches (open, high, low, close, tick volume) | Differences | Not comparable |
|---|---:|---:|---:|---|
| M15 | 34,073 | 34,071 | **0** | 2 broker bars have no complete derived bucket |
| H1 | 8,522 | 8,510 | **0** | 12 |
| H4 | 2,228 | 2,216 | **0** | 12 |

The "not comparable" bars belong to buckets that the calendar-aware completeness rule rejected
(3, 13 and 14 incomplete buckets), i.e. holiday partial sessions. No matched bar differs in any
price or tick-volume value, which confirms the clock, the H4 alignment (server 00:00, 04:00, ...)
and the aggregation rules.

**Spread does not reproduce.** No aggregation of M5 spreads (first, last, max, mean) equals the
broker's higher-timeframe spread. The best, `last`, still differs on 26% of M15 bars, 40% of H1
and 48% of H4. Derived spreads are therefore approximations and must not be treated as broker
values; cost modelling should use M5 (or tick) spread directly.

## 7. Limits and open items

* One account type (demo) and one 17-month window; live-account feeds, spreads and sessions can differ.
* Only one US/EU daylight-saving mismatch pair per season type is inside the history.
* Holiday closures are detected, not modelled; irregular holiday sessions appear as warnings.
* The `Fri 11:30` and `Mon 01:15` single-bar gaps are unexplained and are left as reported.
* Tick data was not examined.
