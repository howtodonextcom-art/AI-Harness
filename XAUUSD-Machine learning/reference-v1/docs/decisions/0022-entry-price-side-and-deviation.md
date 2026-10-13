# ADR-0022: Entry price on the executable side, rounded levels, deviation from measured spread

Status: accepted (2026-10-08). Fixes pre-mortem blockers c2, c3, c7, d4 (CLAUDE.md).

**Problem.** A signal's price is the close of an M15 bar, which is a BID. `OrderIntent.entry_reference`
was that bid, but the executor compared it with the ASK for a BUY. With a median spread of 31 points and
a 30-point deviation, almost every BUY was refused (`ENTRY_PRICE_MOVED`). Stop and target were not
rounded to the symbol's digits, and sizing measured the stop from the bid although a BUY fills at the ask.

**Decision.**

* The bridge computes the executable entry: for a BUY, zone middle plus the current spread (the ask);
  for a SELL, the zone middle (the bid). It rounds entry, stop and target to the symbol's `digits`
  (configured on the bridge, default 2) and passes them to the intent.
* Position size uses the stop distance from that executable entry, so the real risk does not exceed
  the configured percentage because of the spread.
* The executor refuses levels that are not on the symbol's tick (`LEVELS_NOT_ON_TICK`), stops closer than
  `trade_stops_level` (`STOPS_TOO_CLOSE`), and does not close a position inside `trade_freeze_level`
  (`POSITION_FROZEN`: refused, retried later, not an unknown state).
* The deviation default is 60 points: about the 95th percentile of the measured M5 spread
  (`docs/research/edge-program/00-diagnosis.md` section 2: p95 55-60 points). The price check now
  compares like with like (ask with the ask-based entry), so the deviation measures movement since the
  decision, not the spread.
* Equality with a floor is a breach everywhere (`<=` in `RiskEngine`), including the internal buffers.

**Consequences.** Intents are slightly smaller than before (0.64 instead of 0.66 lots in the reference
test). The paper trader still sizes from the bid; it is not on the order path.
