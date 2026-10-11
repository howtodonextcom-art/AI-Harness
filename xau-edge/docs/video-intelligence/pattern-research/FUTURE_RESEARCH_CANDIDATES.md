# Future research candidates and contamination analysis

Status: **documentation only. NOT AUTHORIZED. NOT RUN.** Edge Program V3 is closed with NO VIABLE EDGE
FOUND; new outcome research needs a new charter, a new preregistration, a new trial count K and
untouched evaluation data. Nothing here opens any of that.

## Classification of every pattern

| Pattern | Class | Why |
|---|---|---|
| Wolfe Wave | DETECTOR ONLY | rules are disputed (P5 overshoot, entry, ETA), the only large study is idealised (stocks, daily, perfect entry), real-data frequency equals a shuffled null |
| Double Top / Bottom | FUTURE RESEARCH CANDIDATE (low prior) | best rubric score; enough events to test (287 in Development-2 H1); but its frequency on real data is at the null level and no mechanism beyond textbook folklore is supported by evidence here |
| Head and Shoulders / Inverse | DETECTOR ONLY | too rare to test: 7 events in 48,470 H1 bars (8 years); even doubling the history would stay far below a usable count |
| Break-and-Retest | REJECT as new research | overlaps V2 H08 (breakout acceptance and continuation, closed) |
| Liquidity Sweep + Reclaim | REJECT | is V2 H07 (closed); a new level definition is the same mechanism |
| Triangle, Flag, Diamond, Cup and Handle, Supply/Demand | DOCUMENT ONLY | not implemented; no formal shared definition or too rare |

The F1 opposite-direction observation remains **POST-HOC, NOT VALIDATED, NOT AUTHORIZED**; none of the
pattern work is a route to it, and no pattern was evaluated in its reverse direction.

## Candidate contract: Double Top / Bottom with a neckline-close trigger

Written so that a later, separately authorised charter can start from it. It is not a hypothesis that
anyone has registered.

* **Mechanism and why it might hold information.** A second failed attempt at the same level with
  the neckline then breaking on a close could mark exhaustion of buyers. The honest status is that this
  is a textbook story: nothing in this repository or in the sources opened here supports it for gold, and
  Wolfe/double-top statistics found are for stocks on daily bars. The prior is low.
* **How it differs from V1-V3.** V1: session momentum, Asia range break, volatility compression, daily
  trend with EMA pullback, exhaustion fade, Donchian trend. V2: liquidity sweep reversal, breakout
  acceptance, session transition, conditional volatility expansion. V3: USD residual (closed), US-session
  momentum (closed), macro reaction (deferred). None defines a *two-touch swing structure with a
  closed-bar neckline trigger*, so it is a different event definition. It shares the "reversal after a
  failed push" intuition with H05 (exhaustion fade) and H07 (sweep reversal), which is a reason for a low prior.
* **Entry timing.** Close of the first bar that closes beyond the neckline after the second peak is
  confirmed; the first executable price is the next bar's open. Median wait from geometry known to
  trigger is 7 H1 bars (Development-2 counts), confirmation lag is exactly the right-hand pivot window.
* **What the shape itself offers (geometry at detection, no outcome).** With the textbook levels (entry
  at the trigger close, stop at the peak, target the measured move) the gross reward-to-risk of a detected
  double top/bottom has median **0.72** (quartiles 0.43-0.88) on Development-2 H1 and **0 of 287**
  reach 1.5; the break happens below the neckline so the risk is already larger than the height. At 0.72 a
  strategy needs a hit rate above 58% before costs just to break even, and XAU EDGE's own net R:R >= 1.5
  gate would refuse every one of these setups. For comparison, the Wolfe picture displays a gross R:R
  with median 3.6 (90% above 1.5) because the stop sits at the extreme; that figure is the appeal in the
  reel and it exists only if the extreme is known in advance. Head and shoulders: median 1.46, 29% above 1.5.
  Consequence: the double top candidate needs a different, preregistered exit definition, and it
  does not help a system whose problem is a net R:R gate. This lowers its priority further.
* **Exit definition.** Not defined here; it would have to be fixed in the preregistration before any
  outcome is read (stop at the invalidation reference, target as a fixed R multiple or the measured move
  are the textbook options; choosing among them after looking is forbidden).
* **Parameter budget.** Seven parameters (see the inventory). A preregistration would fix all of them
  at library defaults and count one variant per direction rule, so K would grow by the number of
  registered variants only.
* **Expected frequency.** About 59 detections per 10,000 H1 bars on XAUUSD (143 tops and 144 bottoms in
  2011-2018), roughly 36 per year in total (about 18 per direction), with 12.5% overlapping the previous detection.
* **Required data.** XAUUSD H1 with certified clocks, spread and commission, causal pivots only.
* **Cost model.** Must use the project's measured cost model (`foundation/cost_model_v2.json`), never zero costs.

## Contamination analysis

What has already influenced idea selection, parameter choice and direction choice:

| Influence | By what | Which data touched |
|---|---|---|
| Idea selection | a social-media Reel and a YouTube tutorial (Wolfe), then a rubric (double top, head and shoulders) | no market data |
| Parameter defaults | textbook conventions and synthetic geometry tests | synthetic data only |
| Descriptive counts | one run per detector with fixed defaults on Development-2 H1, no sweep, no outcome | **Development-2 (2011-2018)**: counts, geometry, timing |
| Block-shuffle frequency null | 20 shuffles of Development-2 returns | Development-2 |
| Direction choice | each pattern keeps its textbook bias; no reverse direction was examined | none |
| Prior outcome tests of other hypotheses | V1/V2/V3 Stage 1 and earlier Dev-H/Val-H runs | Development-2 and the earlier Dev-H/Val-H windows |

Datasets and what remains suitable for an honest evaluation:

| Dataset | State | Usable for a future outcome study? |
|---|---|---|
| Development-2, 2011-01-01..2018-12-31 | BURNED: outcome-tested by other hypotheses, now also described by pattern counts | only as a development set for a new idea, never as evidence |
| Validation-2, 2019-01-01..2021-12-31 | untouched for outcomes (no Stage 1 survivor); **not opened in this work** | the cleanest remaining data: reserve it for the first honest evaluation of a registered candidate |
| Test-H, 2022-01-01..2025-04-30 | LOCKED, not opened; K already 44 in the shared accounting | once, per candidate, after a frozen record and independent review; alpha 0.05 / (44 + new K) |
| Holdout, 2026-05-01..2026-10-07 | LOCKED, not opened | same rule, and last |
| `data/raw` FTMO 2025-05-01..2026-10-07 | contains the Holdout | forbidden |
| Live ledger and anything after 2026-10-07 | forward data | the only data that cannot have influenced the idea; needs continuous collection (decision coverage is 48.6% of the 95% gate) |

The practical consequence: any outcome study of these ideas starts with Development-2 for development
only, spends Validation-2 once, and treats Test-H and Holdout as locked; forward data is the cleanest
evidence but is slow.

## What would make a candidate worth authorising

A mechanism with support beyond folklore, a rare enough event with at least a few hundred
non-overlapping instances, a cost model that makes the expected edge exceed spread, and a
preregistration (all parameters, direction, exit, K) committed before any outcome is read.
