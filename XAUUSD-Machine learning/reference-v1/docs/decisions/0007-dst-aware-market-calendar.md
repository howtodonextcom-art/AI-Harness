# ADR-0007: Market calendar is defined in New York local time

Status: accepted (2026-10-08); found by red-team during Sprint 1

**Context.** The first calendar hard-coded the weekly closure as Friday/Sunday 22:00 UTC. FX/CFD
gold conventionally closes Friday 17:00 and reopens Sunday 17:00 New York time, which is
21:00 UTC during US daylight saving and 22:00 UTC otherwise. A fixed UTC rule would report
about four phantom missing bars per week (M15) and phantom weekend-bar warnings for five
months of the year.

**Decision.** `MarketCalendar` has a `timezone` (default `America/New_York`) and local
minute-of-day thresholds. Polars converts bar-open times to that zone, so DST is handled
automatically.

**Tests.** Eight parametrised cases cover summer/winter Friday close and Sunday open on both
sides of the boundary. A mutant that reverts the default to UTC is killed (7 failures).

**Update (Sprint 2).** Real data showed the broker's session is Sunday 18:05 to Friday 16:50 New
York with a daily break 16:50-18:05, so the generic 17:00 default is only an approximation. The
FTMO profile (`configs/brokers/ftmo_demo.yaml`) carries the measured values. Holidays are still not
modelled; see ADR-0009 for how they are reported.
