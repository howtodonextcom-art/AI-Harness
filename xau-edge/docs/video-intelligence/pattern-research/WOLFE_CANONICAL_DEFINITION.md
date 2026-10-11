# Wolfe Wave: canonical rule table (bullish; the bearish case is the exact mirror)

Built from sources that were actually opened or ingested. No false consensus is forced: where sources
disagree the row says so. Source quality is stated in each source row.

## Sources

| Id | What | Quality | How it was used |
|---|---|---|---|
| BULK | Bulkowski, thepatternsite.com bullish Wolfe Wave (opened) | MEDIUM: explicit identification rules and a 6,269-pattern study; statistics idealised | rules and statistics |
| LUX | LuxAlgo library, Wolfe Waves (opened) | LOW: vendor education | rules, caveats |
| ATAS | ATAS Wolfe Wave guide (opened) | LOW: vendor education | entry, stop, target, ETA |
| QUANT | Quantum Algo guide (opened) | LOW: repeats Bulkowski with a different number | only to show a misquote |
| REEL | Facebook Reel, "Zenix Arixon" (media ingested, frames read, no speech) | LOW: 16.7 s clip, one example | what is drawn |
| YT | YouTube "Wolfe Wave Pattern Strategy Explained" (media and speech ingested) | LOW: commercial tutorial, ASR with errors | a variant with Fibonacci limits |
| TV | TradingView open-source scripts (UAlgo, BigBeluga, LuxAlgo detector, a community script) | search summaries only; source code not retrieved | how scripts are built, not what they do |
| BP | BabyPips thread (opened) | LOW: anecdotes | no rules, no statistics |
| PDF | MQL5 `wolfe_waves.pdf` | not read: scanned images, no OCR performed | none |

## Rules

Status: CONSENSUS (every source that speaks to it agrees), VARIANT (some sources add or drop it),
DISPUTED (sources contradict), UNKNOWN (no source gives it).

| # | Rule | Status | Evidence | Code (`structure/wolfe.py`) | Match |
|---|---|---|---|---|---|
| 1 | Five alternating swing points: P1 low, P2 high, P3 low, P4 high, P5 low | CONSENSUS | BULK, LUX, ATAS, REEL, YT | confirmed pivots, strictly alternating | yes |
| 2 | P3 below P1 | CONSENSUS | BULK ("point 3 has surpassed point 1"), LUX, REEL | `p3 < p1` | yes |
| 3 | P4 below P2 | CONSENSUS | BULK ("must be below the price of 2"), LUX, REEL | `p4 < p2` | yes |
| 4 | P4 above P3 | CONSENSUS (implied by alternating swings; explicit only in YT) | BULK, YT | flag `require_p4_inside_p2_p3` (default on) | yes |
| 5 | Lines 1-3 and 2-4 converge | CONSENSUS | BULK ("if they do not, you do not have a Wolfe Wave"), LUX | flag `require_converging` (default on) | yes |
| 6 | No other higher peak or lower valley between points 1 and 5 | UNKNOWN beyond BULK | BULK only | only approximated: of two same-kind pivots in a row the more extreme is kept | partial |
| 7 | P5 beyond line 1-3 (overshoot) | **DISPUTED** | REEL, LUX, YT: yes. BULK: P5 "need not bottom on line 13", uses a "sweet spot" (between P5 and a line through P3 parallel to line 2-4) | flag `require_p5_beyond_line13` (default on) | choice documented |
| 8 | P5 below P3 | CONSENSUS (implied) | BULK sweet spot geometry | `p5 < p3` always | yes |
| 9 | Fibonacci limits on P3 (127.2-161.8% of 1-2) and on P5 (127.2-161.8% of 3-4) | VARIANT (YT only) | YT; absent from BULK and LUX | not implemented (PLANNED) | not implemented |
| 10 | Waves 3-4 similar in size to 1-2 | VARIANT | YT; LUX "similar duration and slope preferred"; BULK silent | not implemented | not implemented |
| 11 | EPA (target) is line 1-4 extended | CONSENSUS | BULK, LUX, ATAS, REEL, YT | target on the P1-P4 line | yes |
| 12 | ETA (when): where lines 2-4 and 1-3 intersect | VARIANT | LUX, ATAS | **P5 index + (P5 - P3) bars by default; no source uses this** (see mismatches); option `LINES_INTERSECTION` | mismatch fixed by option |
| 13 | Entry at P5 | **DISPUTED** | REEL and BULK's study: at P5 (BULK: the exact low, "cannot be duplicated"); ATAS: at P5 "with nuances"; LUX and YT: after a close back inside line 1-3 | `entry_trigger`: `P5_CONFIRMED` (default) or `LINE13_RECLAIM`; the exact extreme is unknowable until P5 is confirmed | both modes |
| 14 | Stop beyond P5 | CONSENSUS on direction, UNKNOWN on distance | REEL, YT, ATAS ("beyond P5"), LUX ("beyond the sweet zone") | exactly at P5, no buffer | mismatch: sources say beyond |
| 15 | Single target at the EPA line | VARIANT | ATAS also mentions conservative targets at support or resistance | one target on line 1-4 | yes |
| 16 | Timeframe | DISPUTED / UNKNOWN | ATAS: "any"; BULK: daily; LUX (via QUANT): lower timeframes give more false patterns | none (timeframe-free) | n/a |
| 17 | Bearish case is the mirror | CONSENSUS | all | exact mirror by negating prices | yes |

## Mismatches between the code and the sources

1. **Target time (row 12).** The default horizon is `P5.bar - P3.bar` bars after P5. That is this
   project's own convention; LUX and ATAS define the ETA as the intersection of lines 2-4 and 1-3. The
   option `target_time="LINES_INTERSECTION"` implements the sourced rule; the old default is kept so
   existing results do not change, and it is labelled UNSOURCED.
2. **Stop (row 14).** The code stops exactly at P5; the sources say "beyond". There is no sourced
   distance, so none was invented.
3. **Overshoot (row 7).** Bulkowski does not require it. The default follows REEL, LUX and YT.
4. **Fibonacci and symmetry (rows 9, 10).** Not implemented because only one commercial tutorial states
   them and the numbers come from a transcript with recognition errors ("1.37.2" for 127.2).

## What no source gives

A tested rule for gold or intraday data, a stop distance, a repaint statement for any specific
script, or independent statistics for the entry modes. Bulkowski's 47% reaching the EPA is for stocks on
daily bars with entry at the exact P5 low; the 41%/35% figures on a secondary page do not match his page.
