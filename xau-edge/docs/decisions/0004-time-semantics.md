# ADR-0004: Timestamps are UTC bar-open times; broker zone is explicit

Status: accepted (2026-10-08); live MT5 behaviour unverified

**Decision.** Every frame stores the bar OPEN time as tz-aware UTC. Naive or non-UTC frames are
a validation ERROR. Sources that read broker-local times take an explicit IANA zone
(`source_timezone`, `MT5_BROKER_TIMEZONE`) and convert; ambiguous and non-existent local times
raise rather than being guessed. `broker_timezone` has no default.

**Why.** MetaTrader reports server wall-clock labelled as UTC; silently treating it as UTC shifts
sessions by hours and corrupts session features and news windows.

**H4 alignment.** Broker H4 bars start at server midnight, so in UTC they need not be multiples of
4h. Alignment checks therefore require whole hours for H4 (minute and second zero).

**Open item.** Determine the real broker zone and confirm the request-bound shift against a live
demo terminal (Sprint 2).
