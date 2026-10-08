# Sprints 11-14 - Report

Date: 2026-10-08. Scope: signal engine (Epic 13), read-only API and dashboard (Epics 15-16), paper
trading (Epic 17), forward-test tooling (Epic 18). Research only; no live execution exists.

## Sprint 11: signal engine

| Item | Where |
|---|---|
| Signal schema with every field of brief section 21, plus the candidate lean, reasons and a reproduction hash | `signals/schema.py` |
| Twelve refusal reasons (no validated edge, edge insufficient, EV not positive, poor risk/reward, regime, news risk, news unknown, spread, invalid data, model uncertainty, higher-timeframe conflict, entry quality) | `signals/decision.py` |
| EV after costs (brief section 23), plain-language explanations | `signals/expected_value.py`, `signals/explain.py` |
| Evidence gate bound to one configuration, three periods, same datasets, clean tree | `signals/evidence.py`, ADR-0017 |
| Inputs built only from bars closed at the decision time | `signals/engine.py` |

Result: with the evidence gate closed the engine always answers WAIT; on the newest real data it states
SELL as the analysis lean (analogue frequencies 60% down, EV about +0.02 R after costs) and refuses for
`NO_VALIDATED_EDGE` and `NEWS_UNKNOWN`.

Independent review (adversarial, 2 CRITICAL, 4 HIGH): a NaN or infinite expected R produced a BUY; the
schema invariant was bypassable with `model_copy`/`model_construct`; the evidence gate was not tied to
the strategy being traded and could be opened by an unrelated strategy; a decision time inside a bar
crashed and mixed in bars that closed later. All fixed with tests: every float input is checked for
finiteness, malformed context (missing H4/H1, unknown regime, inconsistent levels) refuses, `model_copy`
re-validates and `model_construct` is refused, the gate keys on exact parameters plus datasets and a
clean tree, mid-bar times use the last closed bar (poisoned future bars cannot change a signal).
Mutation spot-check: 30 mutants over the decision, schema and evidence code, all killed.

## Sprint 12: API and dashboard

* FastAPI (`/health, /market, /features, /regime, /patterns, /signals, /backtests, /backtests/{id},
  /models, /risk/status`), localhost only, CORS limited to the dashboard origins and GET.
* Next.js 16 + TypeScript strict + Tailwind + Lightweight Charts dashboard: decision card with reasons,
  probabilities (labelled as uncalibrated analogue frequencies), bias per timeframe, regime, price chart,
  analogue overlay, explanation with reproduction hash, validation status, data-staleness line, paper
  panel. Screenshots at 1440x900 and 390 px: `docs/reports/img/`.
* Independent review: no path to a real order; fixed CPU exhaustion (per-bar bounded cache, two
  concurrent computations, `at` bounded to the data range), a 500 on an out-of-range pattern query,
  misleading UI wording ("Armed"), missing staleness indicator and explicit news status, CORS headers,
  explanation list keys, chart tooltip time. `npm audit` reports high-severity issues only in
  development lint tooling (`eslint-config-next` dependency tree), not in the shipped bundle.
* CI gained a dashboard job (install from the lock file, lint, type-check, build).

## Sprint 13: paper trading

`ExecutionBroker` interface, `PaperExecutionBroker` (same fill rules as the backtest, journal of every
event with the signal hash and a mode label), `ExecutionSafety` (environment, account, symbol, lot
and order-count limits, dry-run), `PaperTrader` (signal -> risk engine -> safety -> broker), and
`POST /paper/orders` (no trade parameters from the client; refuses stale data; one order at a time).
No broker library is imported anywhere under `execution/`; a test scans for order functions.
Independent review: replay and forward runs shared one journal with no mode (now separate files plus a
`mode` field), the API paper account is only advanced when new data is loaded (documented, kill-switch
state now visible in `/risk/status`), orders on stale data were possible (`DATA_STALE`), short
modification used the bid (now the ask), non-finite order values (rejected), concurrent POSTs (lock).
Accepted and documented: paper state is in memory, sizing uses the zone midpoint for the stop distance,
the trader passes `news_blocked=False` because a BUY/SELL signal cannot exist without a clear news check.
Mutation spot-check: 18 mutants, one survivor (short target on the ask) killed by a new test.

## Sprint 14: forward testing (tooling)

`replay()` feeds M5 bars to the paper trader and decides at each M15 close; `compare_paper_to_backtest`
refuses conclusions from replays and from fewer than 100 paper trades and otherwise says whether the
backtest mean R is distinguishable from the paper result. A three-hour replay of the newest data:
9 decisions, 0 orders, every one refused. Calendar-time forward testing itself has NOT been run: it needs
weeks of new data and a candidate that passed validation, which does not exist.

## Red-team: how could these sprints be wrong?

| Question | Finding | Status |
|---|---|---|
| A BUY escapes while evidence is closed | schema, decision and gate each block it; tests construct, copy and poison | Mitigated |
| Evidence gate opened by the wrong thing | keyed on configuration, datasets and a clean tree | Mitigated; stale-data currency is not checked beyond dataset ids |
| The dashboard misleads | wording reviewed, staleness and WAIT reasons shown; no automated browser test | Open |
| Paper results mistaken for evidence | mode label, separate journals, 100-trade guard, replay never concludes | Mitigated |
| Paper vs backtest comparison is weak | CI-containment test; R defined slightly differently (fill-based risk) | Documented |
| API/paper state loss on restart | in-memory by design; journal is the record | Documented |
| News risk | no calendar; every signal is NEWS_UNKNOWN, i.e. WAIT | Open (blocks any real BUY/SELL by design) |
