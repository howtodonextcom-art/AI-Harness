# ADR-0011: Session definitions, feature timing and consecutive-bar windows

Status: accepted (2026-10-08)

**Sessions** use local exchange hours so daylight saving follows the time-zone database instead of
fixed UTC hours: Asia 09:00-18:00 Asia/Tokyo, London 08:00-17:00 Europe/London, New York
08:00-17:00 America/New_York. Both London and New York active is `LONDON_NY_OVERLAP`; London wins
over Asia where they touch; no session is `OFF_HOURS` (an addition to the four labels in the brief,
needed so every bar has a label). The label uses the bar open time. These hours are a modelling
convention, not a statement about liquidity; Sprint 7-9 results must report by session before any
session is treated as meaningful.

**Timing.** A feature row is keyed by the bar OPEN time and carries `available_at` = open +
timeframe length: the earliest moment its values were knowable. Any later join to outcomes or
signals must use `available_at`, never `timestamp`, to avoid look-ahead.

**Consecutive bars.** Indicators run over consecutive rows. Weekend and holiday gaps are not
filled, so the first bars after a reopening mix pre-gap history (a deliberate simplification;
a `gap_before` column marks bars that do not directly follow the previous row, so consumers can
filter or discount them; gap-aware windows would be a new `FEATURE_SET_VERSION`).

**Identity.** `feature_id` = hash(version, dataset id, timeframe, config). The feature store is
write-once; a different payload under an existing id is an error.

**Deferred.** A holiday calendar would only reclassify validator warnings (`UNSCHEDULED_CLOSURES`)
and does not change any feature; it is moved to Sprint 8, where cost and fill realism need it.
