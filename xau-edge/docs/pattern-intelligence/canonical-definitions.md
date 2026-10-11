# Canonical pattern definitions

Status per rule: CONSENSUS, VARIANT, DISPUTED, UNKNOWN. A rule is UNKNOWN when no source that was actually read states it (many families here were read only through the author's drawings and Bulkowski's pages; the others are marked "not read"). "Code" is the repository implementation.

The Wolfe Wave table is in `docs/video-intelligence/pattern-research/WOLFE_CANONICAL_DEFINITION.md`; it is the most complete (rows for P1-P5, EPA, ETA, entry modes).

## Double top / double bottom (including Adam and Eve)

| Rule | Status | Evidence | Code |
|---|---|---|---|
| Two peaks (bottoms) of similar height with a valley (peak) between | CONSENSUS | Bulkowski ("the two should look similar"), the reels | `equal_tolerance` x height |
| Adam = narrow, pointed (often one-bar spike); Eve = wider, rounded | VARIANT (Bulkowski's labelling; he notes it is hard) | Bulkowski | not implemented |
| Confirmation = a close beyond the centre peak (valley for a top) | CONSENSUS | Bulkowski ("only when price closes above the centre peak"), the reels draw the entry at the break | trigger on closed bar |
| Separation between the two bottoms | VARIANT | Bulkowski: usually weeks apart, median 16 days (daily stocks) | `min_bars_between`, `max_pattern_bars` |
| Entering before confirmation | DISPUTED | Bulkowski: price continues lower 48% of the time; the series enters at the break | never before confirmation |
| Stop | UNKNOWN as a rule | none of the four Adam and Eve reels (1, 3, 19, 22) draws a stop | reference at the peak |
| Target | VARIANT | measured move equal to the pattern height (reels 19, 22); Bulkowski measures to the ultimate high in "perfect trades" | measured-move reference |
| Actionable timestamp | defined here | closed bar beyond the neckline after the second peak is confirmed (3 bars) | `actionable_at` |

## Head and shoulders / inverse

| Rule | Status | Evidence |
|---|---|---|
| Three peaks, the middle (head) highest, shoulders similar, two valleys | CONSENSUS | textbook description; **no source for this family was opened in this phase and no Reel is dedicated to it** |
| Neckline through the two valleys, close beyond it confirms | CONSENSUS (not read) | same |
| Shoulder symmetry tolerance, head prominence | UNKNOWN | code uses `equal_tolerance` for both |

## Wedges (falling, rising)

| Rule | Status | Evidence |
|---|---|---|
| Two trendlines converging in the same direction | CONSENSUS | Bulkowski, the reels |
| At least five touches (three on one line, two on the other) | VARIANT | Bulkowski only; the reels draw 4-6 touches by eye |
| Minimum 3 weeks, otherwise a pennant | VARIANT | Bulkowski (daily stocks) |
| Confirmation = a close outside a trendline | CONSENSUS | Bulkowski |
| Breakout direction | DISPUTED | falling wedge: up 68% (Bulkowski) and the reels always show up; rising wedge: down 60% and the reels always show down |
| Reliability | CONTRADICTED_EXTERNALLY for the reels' claim | Bulkowski: falling wedge a poor performer (26% / 29% break-even failure); rising wedge down breakouts rank 36 of 36 (51%) |
| Detector | none: needs line fitting with touch counts and tolerance (rubric: formal definability 4 but causal detectability 3) |

## Triangles, flags, pennants

Defined in the reels by the diagram only (an ascending triangle has a horizontal top and rising bottom line; a flag follows a flagpole). Sources read for these in this phase: none. Rules UNKNOWN beyond "close outside the boundary"; flag pole size and consolidation depth are not agreed. Not implemented.

## Cup and handle

| Rule | Status | Evidence |
|---|---|---|
| U-shaped cup (not V), handle on the right in the upper half, rims at about the same price | CONSENSUS | Bulkowski, the reels |
| Cup length 7-65 weeks, handle at least one week | VARIANT | Bulkowski (daily stocks); the reels show a few hours or days |
| How round is "U-shaped" | UNKNOWN | Bulkowski: "allow variations", "flexible"; no curvature measure |
| Reliability | VARIANT | Bulkowski rank 3 of 39 (idealised); 47% of 300 recent patterns dropped substantially within two months |

## Diamond, butterfly, dragon, three valleys and a river

* **Diamond:** two bulls-and-bears halves, a widening then narrowing range; no shared geometry in the sources read: UNKNOWN. The reels draw a diamond over a range after a trend. Not implemented.
* **Butterfly (harmonic):** the reel prints ratios: B at 78.6% of XA, D at 127-141% of XA, BC extension 161.8-224%, AB retracement 38.2-88.6% as labelled on its diagram; entry at D before any reversal. The ratio ranges are the author's; not checked against an independent harmonic reference (not read). The entry is at an unconfirmed completion point.
* **Dragon, three valleys and a river:** appear in one Reel each; the diagram is the only definition; UNKNOWN beyond it.

## Structure and liquidity

| Concept | Status | Where |
|---|---|---|
| BOS / CHoCH: a close beyond the latest confirmed swing in or against the prior trend | defined and implemented | `structure/swings.py` (ADR-0012), used by the baseline |
| Break and retest: a break, then a retest that holds | VARIANT in X educational posts (retest confirmed on 5 minutes, stop below the invalidating level) | overlaps V2 H08 |
| Liquidity sweep / fake breakout: a brief move beyond a level that reverses; entry after a close back inside | VARIANT in X posts (stop beyond the wick); definitions are educational only | is V2 H07 |
| Equal highs / lows as liquidity pools, supply and demand zones | UNKNOWN: no shared construction found | none |
