# Pattern taxonomy

Columns: where the family was seen (FB = the 29 Reels, X = search snippets, Bk = Bulkowski page read), the detector, the rubric v2 rank (`scripts/pattern_rubric.py v2`), and the research class. Nothing here has outcome evidence.

| Category | Family | Seen | Detector | Rubric v2 | Class |
|---|---|---|---|---|---|
| Reversal | Double Top / Double Bottom (incl. Adam and Eve) | FB x4 (1, 3, 19, 22), X, Bk | yes (`reversal.py`, lifecycle `formation.py`) | 2nd, 67.4 | FUTURE RESEARCH CANDIDATE (low prior) |
| Reversal | Head and Shoulders / Inverse | X (snippets) | yes | 3rd, 64.2 | DETECTOR ONLY (rare) |
| Reversal | Wolfe Wave | FB x5 (5, 20, 26, 27, 28) + earlier reel, YouTube, Bk | yes (`wolfe.py`) | 10th, 50.5 | DETECTOR ONLY |
| Reversal | Diamond top / bottom | FB x4 (8, 18, 23, 29) | no | disqualified (no formal definition) | DOCUMENT ONLY |
| Reversal | Quasimodo | none | no | 12th, 48.4 | DOCUMENT ONLY |
| Reversal | Failed breakout / false breakout | X | no | see liquidity | REJECT as new research (V2 H07) |
| Reversal | Liquidity sweep + reclaim | X | no | disqualified (V2 H07) | REJECT |
| Reversal / harmonic | Butterfly, Dragon, Three valleys and a river | FB x3 (4, 7, 6) | no | 14th, 45.3 | DOCUMENT ONLY |
| Continuation | Bull / bear flag, pennant | FB x1 (9), 15 | no | 11th, 49.5 | DOCUMENT ONLY |
| Continuation | Triangle (asc/desc/sym) | FB x3 (16, 21, 25), X | no | 9th, 51.6 | DOCUMENT ONLY |
| Continuation | Rising wedge / falling wedge | FB x4 (13; 2, 10, 14), Bk | no | 8th 51.6 / 6th 54.7 | DOCUMENT ONLY |
| Continuation | Rectangle | none | no | not scored | DOCUMENT ONLY |
| Continuation | Cup and handle | FB x3 (11, 12, 17), Bk | no | 13th, 45.3 | DOCUMENT ONLY |
| Structure | BOS / CHoCH | X | yes, in the baseline (`swings.py`) | 1st, 69.5 | existing infrastructure, not new |
| Structure | Break and retest, support/resistance flip | X | no | 4th, 56.8 | REJECT as new research (V2 H08) |
| Structure | Supply / demand interaction | X | no | disqualified | DOCUMENT ONLY |
| Liquidity | Equal highs / lows, stop sweep, liquidity grab | X | no | 5th, 55.8 (levels only) | REJECT / DOCUMENT ONLY |

Eleven distinct families appear in the 29 Reels (Adam and Eve, falling wedge, rising wedge, butterfly, Wolfe Wave, three valleys and a river, dragon, diamond, flag, cup and handle, triangle), plus two compilations.

Implementation limit of this phase (at most three detectors including Wolfe) is reached: Wolfe Wave, double top/bottom and head and shoulders. No indicator zoo.
