# ADR-0009: Check coverage against the request, and separate closures from data loss

Status: accepted (2026-10-08); found by validating real data

**Coverage.** The MT5 terminal silently drops the oldest bars beyond its bar limit. A dataset
must therefore be checked against the requested range (`check_coverage`, ERROR when an edge is
missing by more than 4 days). The dataset of record is the merge of all raw fetches
(`DatasetCatalog.load`, newest fetch wins on identical timestamps, duplicates counted), not a
single fetch.

**Calendar and bar span.** A bar is "closed" only if its whole span is inside a closure
(`closed_span_expr`). Judging by the open time alone flagged bars that open inside the daily
break but trade later in their span.

**Closures versus data loss.** A gap of at least `min_closure_minutes` (default 30) whose last
missing slot is followed by a scheduled closure, so that the next bar is the first after a
reopening, is reported as `UNSCHEDULED_CLOSURES` (WARNING, likely holiday or early close). Any
other gap is `MISSING_BARS` and counts toward `max_missing_fraction`. A genuine outage that ends
exactly at a reopening is indistinguishable from an early close; both stay visible as warnings.

**Limits.** No holiday calendar yet. Holiday sessions that reopen at an unusual time are
reported as `MISSING_BARS` warnings (12 H4 bars in the verification data).
