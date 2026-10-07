# ADR-0006: No copyleft or licence-ambiguous runtime dependencies

Status: accepted (2026-10-08)

**Decision.** Do not depend on AGPL/GPL packages or on packages whose licence cannot be
confirmed. Currently excluded: `backtesting.py` (AGPL-3.0), `freqtrade` and `backtrader`
(GPL-3.0), `vectorbt` (licence metadata blank / not detected). They may be read for ideas; no
code is copied.

**Why.** The platform may be exposed through an API and may be commercialised. Network-copyleft
and unclear terms create avoidable legal risk.

**Consequence.** An in-house vectorised backtester with explicit cost modelling is built in
Epic 10. Dev-only tools under MPL-2.0 (Hypothesis) are acceptable.
