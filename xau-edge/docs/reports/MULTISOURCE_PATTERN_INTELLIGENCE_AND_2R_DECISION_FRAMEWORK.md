# Multi-source pattern intelligence and the 2R decision framework

Date: 2026-10-11. Scope: knowledge, detection, descriptive characterisation and research-programme design. **No outcome research was performed, Test-H, Holdout and Validation-2 were not opened, nothing is connected to the TradeEngine, TradingSignal, PaperDesk, demo or funded paths, and no probability or BUY/SELL percentage was added anywhere.** Detail lives in `docs/pattern-intelligence/`.

## 1. Executive verdict

* All 29 supplied Reels were ingested (29/29) and read frame by frame. They are **one author's series** built from a single template; every one of the 27 single-pattern examples ends in the predicted direction, none shows a failure, and the audio contains no explanation (music lyrics or nothing). A repeatable trading method cannot be extracted; a repeatable *presentation* can.
* Independent evidence (Bulkowski's pages, opened) contradicts the series' confidence for two of its most frequent families: rising wedge down breakouts rank last of 36 (51% break-even failure), falling wedge is "a poor performer".
* No pattern in the taxonomy provides earlier, causal information than the current M5 trigger. The ones that look earlier (Wolfe at P5, butterfly at D) are earlier only by acting before the point can be known.
* The textbook geometry of the double top/bottom offers a gross R:R of about **0.72**: under the 2.0 policy it has no entry-eligible exit today.
* A decision framework for the future was built and tested (net R:R, break-even, preregistered margins, probability contract, entry state machine, formation lifecycle). **Today every call ends in WAIT** because no validated probability and no preregistered threshold exist.
* A popular third-party library's swing labels repaint at the live edge (reproduced on one random walk).
* Project trading logic: no change warranted.

## 2. Git reality

Local `main` at the start: HEAD `a939602`, five commits ahead of `origin/main` (`930c692`, pushed by another actor). This phase's work is committed locally and **not pushed**. Another session's uncommitted dashboard work and screenshots in the tree were left untouched. The pre-commit `mypy --strict` hook checks the whole working tree (including untracked files), so parts that share tests are committed together.

## 3. Facebook source ingestion

29 of 29 public Reels ingested without cookies or login (yt-dlp, ffmpeg, local ASR); 10-34 s each, 1,072-1,088 px wide; adaptive keyframes 5-38 per Reel (budgeted). Every URL maps to one media id and one knowledge record (`docs/pattern-intelligence/knowledge/`, transcripts not committed). Each was read through six evenly spaced keyframes (a contact sheet per four Reels) plus the metadata; this is not a read of every frame, and symbol, timeframe and price levels are not legible in any Reel. The catalog (`source-catalog.json/.md`) records, per Reel, the family, side, where the entry marker sits, the stop and target as drawn, the final frames and notes. The knowledge records carry OBSERVED, INFERRED, CLAIMED_BY_AUTHOR, SUPPORTED_EXTERNALLY, CONTRADICTED_EXTERNALLY and UNKNOWN items with confidence, a trace from the frame timestamp to the concept and to the code, and external sources with their quality.

## 4. X research

About 35 posts and accounts appeared in four searches (double top, Wolfe Wave, liquidity sweep and reclaim, failed breakout and retest). **None could be opened**: every status URL returned HTTP 402, so they are search-result snippets only. What they show: signal-seller levels with prices of different dates, a few educational definitions (the four steps of break-and-retest with a retest confirmed on five minutes and a stop below the invalidating level; fake breakouts as stop hunts; a Japanese definition of a liquidity sweep) and Elliott Wave accounts. **No post timestamped before a move and followed by its outcome was found; no Wolfe Wave post for gold was found.** X is a LOW-quality source here and contributed definitions only.

## 5. Other-source research

Opened and read: five Bulkowski pages (Wolfe, Adam-and-Adam double bottom, falling wedge, rising wedge, cup with handle), LuxAlgo, ATAS, Quantum Algo, a BabyPips thread, and a YouTube Wolfe tutorial (media and speech). GitHub: README pages of smart-money-concepts, pt-lib, chart_patterns, Sweep and (earlier) watch-video, video-understanding, playwright-mcp; one library was executed (section 10). Search-snippets only (not opened): TradingView scripts, ProRealCode, TheRightTrader, EBC, Alpha Ex, a Chinese summary; MQL5's PDF is scanned images and was not read. Reddit and ForexFactory were **not searched** in this phase; MQL5 appeared only as the scanned PDF.

## 6. Source deduplication

Same file hash: none among the 29 (the earlier Wolfe reel's two share links are one file, handled by the alias rule). Perceptual hash of the chart region (dHash 16x16 on the middle and last keyframes): the closest pair is Reels 19 and 22 (34 of 256 bits apart: the same chart recording re-edited); every other pair is at least 62 apart. So: **1 near-duplicate pair**, 0 identical files. More important is source independence: all 29 are one author, so they count as one voice. Reels 23, 25, 27 and 28 carry third-party film or TV clips (23 also an "EASY TRADING" watermark) and 26 shares the zoomed style: possibly another editor or a re-upload; not established.

## 7. Pattern taxonomy

`taxonomy.md`. Eleven families appear in the Reels: Adam and Eve double top/bottom, falling wedge, rising wedge, butterfly, Wolfe Wave, three valleys and a river, dragon, diamond, flag, cup and handle, triangle (plus two compilations). The taxonomy also covers head and shoulders, Quasimodo, break and retest, BOS/CHoCH, liquidity, supply and demand.

## 8. Canonical definitions

`canonical-definitions.md`, with CONSENSUS / VARIANT / DISPUTED / UNKNOWN per rule and the Wolfe table from the previous phase. Honest limit: rules are quoted only for what was opened (Bulkowski for the double bottom, wedges, cup, Wolfe; the repository for the double top and BOS/CHoCH); triangles, flags, diamond, harmonics and head and shoulders rely on the author's diagrams or textbook description and say so.

## 9. Contradictions

Between the series and the evidence: falling wedge as a "powerful bullish reversal" (Bulkowski: poor performer); the rising-wedge breakdown (Bulkowski: worst of 36); entries at Wolfe P5 and at butterfly D before confirmation (Bulkowski: buying a double bottom before confirmation fails 48% of the time; confirmation is a close beyond the centre); a 90% hook ("traders miss") that is not a win rate; 27 of 27 favourable examples against Bulkowski's break-even failure rates of 5-51% for the same families. Between sources: Wolfe P5 overshoot, entry and ETA (previous phase). Between claims about code: the third-party library's README is silent on repaint, our run shows it repaints.

## 10. Repaint and look-ahead audit

Classes (`NON_REPAINT PROVEN`, `POTENTIAL REPAINT`, `REPAINTING`, `UNKNOWN`). Proven non-repainting by prefix invariance and mutation checks: Wolfe (both entry modes), double top/bottom, head and shoulders, the formation lifecycle. **REPAINTING:** `smart-money-concepts.swing_highs_lows` (swing_length 5, 400-bar random walk, 127 prefix cuts): in 124 cases a swing label near the live edge disappeared from the full output; confirmed labels appear 5 bars late but sit on the pivot's own row, so a backtest reading that row sees 5 future bars. Its `fvg` does not repaint but every label is retroactive (known 1-2 bars after its row). The library also crashes on import in a Windows cp1252 console. One series, two functions: it reproduces a public concern, it is not a full audit. **POTENTIAL REPAINT:** the author's live-drawn Wolfe and butterfly entries and every pattern drawn by hand. **UNKNOWN:** all TradingView scripts (source not retrievable).

## 11. Pattern framework

`structure/detection.py` (contract with geometry-known, detected and actionable times, always `GEOMETRY_ONLY` / outcome `NONE`, and the causality harness), `pivots.py`, `formation.py` (lifecycle), `registry.py` (what is known about each family), `pattern_stats.py` (statistics from detections only), `descriptive_data.py` (data policy). Formation state is implemented for the double top/bottom only; Wolfe and head and shoulders report confirmed detections.

## 12. Detector audit

`detector-status.md`. Defects found and fixed in the lifecycle (45 initial differences from the detector, a too-tight equal-peak band, an unreachable late start, unstable ids); each fix is covered by a mutation-checked test. Lifecycle versus detector parity: 192 of 192 confirmed structures on random walks.

## 13. New detectors

None in this phase: the limit of three (Wolfe, double top/bottom, head and shoulders) was already reached, and the new rubric (below) does not select a fourth.

## 14. Random controls

Gaussian random walk (20 x 10,000 bars): Wolfe 46.5, double top/bottom 58.5, head and shoulders 4.3 per 10,000 bars. Block-shuffled Development-2 H1 (20 shuffles, 48-bar blocks): 15.8, 55.8, 2.7. Real Development-2 H1 (48,470 bars): 14.6, 59.2, 1.4. Geometric existence is common by chance; only double top/bottom sits about 6% above the null range.

## 15. Formation-state model

POSSIBLE (25) -> DEVELOPING (50) -> NEAR_CONFIRMATION (75) -> CONFIRMED = ACTIONABLE (100), or INVALIDATED with a reason; progress is a milestone count labelled FORMATION_PROGRESS, never a probability. On Development-2 H1: 3,456 structures reached POSSIBLE; 31.7% reached DEVELOPING, 24.2% NEAR_CONFIRMATION, 8.3% CONFIRMED (random walk 6.5%). Failures: second peak not equal 1,298, neckline broken first 871, break window expired 352, peak band exceeded 339, peak exceeded 192, valley superseded 115. POSSIBLE is therefore mostly noise (713 per 10,000 bars) and should not be surfaced as news. Median 28 bars from the first point to confirmation; median 7 from near-confirmation to the break.

## 16. XAU EDGE comparison

Same mechanism reading as the previous phase. The baseline (H4 veto, H1 direction, M15 pullback band, M5 momentum trigger on a closed bar, M1 blocks, hybrid stop of at least 1.25 ATR, 2R target capped by structure, net R:R >= 1.5 now 2.0 in the candidate policy) shares the closed-bar, non-repainting discipline with the proven detectors and has no pattern, liquidity-sweep or supply/demand concept in the trading code (the research code tested sweeps as V2 H07). Nothing in the 29 Reels, X, YouTube or Bulkowski contradicts the baseline's structure, and nothing supports changing it.

## 17. Earlier timing analysis

`research-candidates.md`. Causal trigger lag: pivot confirmation 3 bars on the pattern's own timeframe, then a boundary close (double top median +7 H1 bars; head and shoulders +1; Wolfe reclaim adds a median of 0 after P5 is confirmed on a synthetic walk, so the confirmation lag dominates). The series' "earlier" entries (Wolfe P5, butterfly D) act before the point is knowable. **No pattern is shown to give earlier, causal information than the M5 trigger.** A lower timeframe moves the clock but not the lag in bars, and shrinks the structure against the cost.

## 18. Net R:R framework

`rr-and-ev-framework.md`, `decision_research/rr.py`. Net R:R = (reward - costs) / (risk + costs); costs = spread + slippage + commission + swap; minimum **2.0** by default; below it the answer is WAIT. A gross 2.0 can be a net failure (tested). What the shapes themselves offer at detection, on Development-2 H1: double top/bottom median gross 0.72 (0 of 287 reach 1.5); head and shoulders 1.46 (29% reach 1.5); Wolfe 3.6 (90% reach 1.5) but only with the stop at an unknowable extreme.

## 19. 1R / 2R / 3R interpretation

R:R is payoff geometry, not probability: 1:1 does not mean 50%, 2:1 does not mean 66%. Break-even win rates before costs: 50%, 33.3%, 25%; after costs they rise. 1:1 is not "gambling" by itself, it needs a higher win probability to overcome costs; no multiple is declared optimal without evidence. 2R is necessary, not sufficient.

## 20. Structure-room gate

`room_to_target < gross_reward` (or unknown room) means WAIT even if 2R exists on paper (tested, including that unknown room is not free room).

## 21. Probability architecture

`probability-contract.md`, `decision_research/probability.py`. Three probabilities kept apart (completion, direction, trade success = P(TP before SL within T)); the trade-success object requires horizon, N, interval, calibration status and an evidence reference; unvalidated means every field is null; no function maps a shape or ratio to a number (a test scans for it). **Today no BUY or SELL probability, no EV and no break-even-plus-margin decision is available.**

## 22. Calibration requirements

Frozen before any out-of-sample result: method (Platt or isotonic or another justified one), Brier, log loss, reliability curve, ECE where useful, horizon, cost model, minimum sample, interval width, era and regime stability. Model-complexity order for a future programme: conditional statistics, Bayesian, calibrated logistic, trees, complex ML only if necessary. No feature mining; no image-only alpha model; social images teach definitions only.

## 23. Expected value framework

EV (in R) = p * net_rr - (1 - p), with costs inside net_rr and `p` a calibrated out-of-sample probability of the specific trade. Required probability = break-even + preregistered calibration margin + preregistered uncertainty margin; EV must exceed a preregistered positive threshold. Win rate alone is not the goal: the UI should show net R:R, break-even rate, estimated probability with its interval and N, EV and the evidence level, never one "AI confidence score".

## 24. WAIT / abstention logic

`authorization.authorize`: NO_PATTERN, POSSIBLE, DEVELOPING, NEAR_CONFIRMATION and INVALIDATED are WAIT with the stage as the reason; then levels, net R:R, room, preregistered thresholds, publishable probability, probability above the requirement, EV; both sides pass means WAIT (conflict, never a vote); data not trusted or a blocker means WAIT. Reasons are Vietnamese for a human, for example "CHỜ: Net R:R hiện 1.4R, dưới ngưỡng 2R" and "CHỜ: MUA và BÁN cùng đủ điều kiện, không chọn bừa". 22 tests, five gate mutants all killed; `BUY_CANDIDATE` is a research-design output, not an order.

## 25. Take-profit research

External practice in the series: a single arrow (most), a measured-move box equal to the pattern height (19, 22, 25), several target lines (11), three take-profit levels (10, the only one), point 6 on the 1-4 line (Wolfe), Fibonacci projections (butterfly), none managed. No Reel shows partial closing, trailing or break-even. Catalogued, not adopted.

## 26. Exit-policy boundaries

TP is a mechanical planning target defined before entry; if no realistic 2R target with room exists, WAIT. Dynamic exit: UNVALIDATED. Emergency exit: existing risk guards. **Partial take profit: DISABLED. Break-even and trailing: UNVALIDATED / DISABLED.** Valid future exits: TP, SL, time exit, formal invalidation, emergency guard, manual close; "price looks weak" is not an exit.

## 27. V4 candidate shortlist

`research-candidates.md`. Rubric v2 (written before scoring; 10 criteria including earlier timing and relevance to the XAU failures): BOS/CHoCH 69.5 (already in the baseline, no new information), double top/bottom 67.4, head and shoulders 64.2, break and retest 56.8, falling wedge 54.7, Wolfe 50.5; liquidity sweep disqualified (V2 H07), diamond and supply/demand disqualified (no formal definition); no candidate reaches 70 or shows earlier timing. Shortlist: **Double Top/Bottom, low prior, conditional** on a preregistered exit that can reach net 2.0R with room (the textbook exit cannot). Wolfe and head and shoulders: detector only. The F1 opposite-direction idea stays POST-HOC, NOT VALIDATED, NOT AUTHORIZED.

## 28. Contamination map

`contamination-map.md`. Development-2 (burned) was used for counts, geometry, timing, lifecycle statistics and a shuffled null, run twice with unchanged detector defaults and no parameter sweep. The idea-selection step (which detectors stay DETECTOR ONLY, the low prior on the double top) has seen Development-2 detection geometry, not outcomes. Validation-2, Test-H, Holdout, the raw FTMO files and the live ledger were not opened. Clean for an honest evaluation: Validation-2 (once), Test-H and Holdout (locked, K_total 44 + new), forward data.

## 29. Stop-doing list

* No more families and no more detectors: the limit is reached and the rubric selects none.
* No outcome statistics, reverse directions, best timeframe, tolerance or session on any pattern; no parameter sweeps on market data.
* No probability, win rate or "confidence" number from geometry, R:R, popularity or a model.
* No wiring of detectors, formation state or the authorization module into the engine, the API or the UI.
* No treating one author's reposts as independent evidence; no treating a search snippet as an opened source.
* No vendoring GPL code; no installing third-party packages into the live environment.
* No activating partial take profit, break-even or trailing.

## 30. Owner decisions

1. **Close pattern work here (recommended), or write a V4 charter for the single conditional candidate** (double top/bottom) with a new preregistered exit that can reach net 2.0R. This also settles the pending question from the previous phase: whether counts-only descriptive use of the burned Development-2 window is permitted for pattern studies (done here twice with fixed defaults, relying on the `event-counts-dev2.json` precedent), or is revoked.
2. Push of the local commits (not done).

Limits of this phase: Reels were read through six frames each; X could not be opened; symbol, timeframe and prices are unknown for all Reels; rubric scores are one rater's judgement; the third-party audit is one series; forward evidence is blocked by decision coverage of 48.6% against the 95% gate; the formation lifecycle covers only the double top/bottom.

```
FACEBOOK SOURCES INGESTED:
29/29

X SOURCES REVIEWED:
0 opened (about 35 search snippets seen; every status URL returned HTTP 402)

OTHER INDEPENDENT SOURCES:
10 pattern sources read (5 Bulkowski pages, LuxAlgo, ATAS, Quantum Algo, BabyPips, one YouTube tutorial) plus 7 repositories at README level and 1 library executed

UNIQUE PATTERN FAMILIES:
11 in the Reels (13 items counting two compilations)

DUPLICATE / MIRRORED SOURCES:
1 near-duplicate pair (Reels 19 and 22); 0 identical files; all 29 are one author, so one voice

PATTERN KNOWLEDGE GRAPH:
PARTIAL

PATTERN FRAMEWORK:
PARTIAL

CAUSAL DETECTORS VERIFIED:
Wolfe Wave (both entry modes); Double Top / Double Bottom (detector and formation lifecycle); Head and Shoulders / Inverse

DETECTORS WITH REPAINT RISK:
third-party smart-money-concepts swing_highs_lows (REPAINTING, reproduced on one series); the author's live-drawn Wolfe and butterfly entries (POTENTIAL REPAINT); all TradingView scripts (UNKNOWN); every family without a detector (POTENTIAL REPAINT as drawn by hand)

TOP 3 PATTERN FAMILIES:
1. BOS / CHoCH (already in the baseline: no new information)
2. Double Top / Double Bottom (including Adam and Eve)
3. Head and Shoulders / Inverse

PATTERNS THAT MAY PROVIDE EARLIER TIMING:
NONE demonstrated (Wolfe at P5 and butterfly at D are earlier only by acting before the point is knowable)

MINIMUM NET R:R POLICY:
2.0

R:R < 2.0:
WAIT BY DEFAULT

R:R 1:1 MEANS 50/50:
NO

WHY:
R:R describes payoff geometry, not win probability.

BUY WIN PROBABILITY AVAILABLE:
NO

SELL WIN PROBABILITY AVAILABLE:
NO

EXPECTED VALUE AVAILABLE:
NO

FORMATION-PROGRESS SUPPORT:
YES (double top/bottom only; structural milestones 25/50/75/100, not a probability)

TAKE-PROFIT POLICY:
mechanical planning target only; WAIT if no realistic 2R with room; exit research UNVALIDATED

PARTIAL TAKE PROFIT:
DISABLED

BREAK-EVEN / TRAILING:
DISABLED (UNVALIDATED)

XAU EDGE LOGIC:
NEEDS FUTURE RESEARCH (nothing found supports or requires a change now)

NEW V4 RESEARCH CANDIDATES:
Double Top / Double Bottom (low prior; conditional on a new preregistered exit able to reach net 2.0R; not authorized)

OUTCOME RESEARCH PERFORMED:
NO

PRODUCTION TRADE ENGINE MODIFIED:
NO

TEST-H TOUCHED:
NO

HOLDOUT TOUCHED:
NO

REAL-MONEY SIGNALS ADDED:
NO

NEXT OWNER DECISION:
Close pattern work here, or authorise a V4 charter for the double top/bottom candidate with a new net-2.0R exit (this also settles whether counts-only use of the burned Development-2 window stays permitted).

OVERALL VERDICT:
The 29 Reels are one author's template series whose every single-pattern example ends favourably, with no spoken explanation, no instrument, no timeframe and no statistics; independent evidence contradicts its confidence for the rising and falling wedge, and no pattern in the taxonomy gives earlier causal information than the current M5 trigger. Three detectors (Wolfe, double top/bottom, head and shoulders) are causal, geometry-only and appear about as often in real gold data as in shuffled copies of it; the textbook double top offers a gross R:R of about 0.72, below the 2.0 policy. A tested decision framework (net R:R, break-even, probability contract, formation lifecycle, abstention logic) now says WAIT for everything because no validated probability exists, and nothing in the trading engine changed.
```
