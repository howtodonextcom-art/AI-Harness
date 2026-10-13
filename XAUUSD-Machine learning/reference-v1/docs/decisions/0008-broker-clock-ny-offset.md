# ADR-0008: Broker clock is modelled as "New York + N hours", not only as an IANA zone

Status: accepted (2026-10-08); amends ADR-0004

**Context.** ADR-0004 required an explicit broker timezone and assumed an IANA name such as
`Europe/Athens`. Measurement on the FTMO demo server (`docs/reports/mt5-verification.md`) showed
that the server clock is New York time plus 7 hours: the weekly close/open labels (`Fri 23:45`,
`Mon 01:05`) stayed constant through the weeks when US and EU daylight saving disagree, and the
live offset (+3 h in October) equals NY (-4) + 7. An IANA zone follows EU rules and is wrong
for roughly three to four weeks a year.

**Decision.** `BrokerClock` accepts either `NY+<hours>` or an IANA zone. Conversions go through
New York for `NY+N`. Both `MT5_BROKER_TIMEZONE` and `FileBarSource(source_timezone=...)` take the
same token. Ambiguous and non-existent local times still raise (strict) or become null (only
when computing expected slots that fall in closed hours).

**Verification procedure.** `infer_broker_clock` ranks candidates by stability of the weekly
close in New York time. Clocks that differ only by a constant shift tie on stability, so a live
tick-time offset measurement is required to choose among them.

**Consequences.** Broker profiles (`configs/brokers/*.yaml`) carry the clock, calendar and
thresholds. Every profile must cite its measurements. Prop-firm rules stay separate.
