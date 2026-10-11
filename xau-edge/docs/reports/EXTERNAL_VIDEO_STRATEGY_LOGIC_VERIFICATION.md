# External video strategy logic verification

Date: 2026-10-11. Subject: `https://www.facebook.com/share/r/1AteztJsfX/?mibextid=wwXIfr`.
Scope: read-only research. No backtest was run, no research programme was reopened (V3 stays closed: NO VIABLE EDGE FOUND), no project logic was changed, no Test-H or Holdout data was touched.

**Headline: the reel is a 16.7 second educational illustration of one chart pattern (a bullish Wolfe Wave). It is not an indicator, a signal system or a complete strategy.** Most of the questions in the brief (trend filter, BUY/SELL/WAIT rules, alerts, repaint, win rate, multi-target management) have no answer in it, and this report says UNKNOWN rather than filling the gaps.

## 1. Original link access result

| Check | Result |
|---|---|
| Metadata without login | readable: title, uploader "Zenix Arixon", duration 16.685 s, media id 1363296065794611 |
| Media | downloaded without cookies or credentials (yt-dlp), AV1 1088x1936, 30 fps, with audio |
| Same file as the previous Wolfe Wave link? | **Yes, byte-identical** (same SHA-256 `1348521a...4e28`); the two share links resolve to one Reel |
| Frames | 33 sampled, 15 kept by the adaptive sampler; frames read at 0, 3, 6, 9, 11, 12 s and by contact sheet |
| Speech | none detected (faster-whisper with VAD, 0 segments, audio rms 0.15). No transcript exists. |
| Visible on screen | title "Wolf Wave Pattern", numbered points 1-6, "Entry in this area", "Target", "ENTRY LONG", "STOP-LOSS" |
| Not visible | symbol, price axis, timeframe label, indicator names, any win-rate or profit figure |

Access status: ACCESSIBLE, MEDIA_READY. The caption is untrusted metadata: "Bullish Wolf Wave Pattern Mila! Kya Market Ab Powerful Breakout Ke Liye Ready Hai?" (Hinglish: roughly "found a bullish Wolf Wave; is the market ready for a powerful breakout?"), hashtags #BullishWolfWave #TechnicalAnalysis #trading #PriceAction #tradingstrategy.

## 2. Author identification

* Account: **Zenix Arixon** (Facebook; numeric profile id 61592920220642 from the extractor). Real identity, location, credentials and any website: **UNKNOWN**.
* The profile and its reels tab require a login (`AUTH_REQUIRED`); I did not try to get around it.
* A web search for the name returned only unrelated companies and tokens; no Instagram, YouTube, TikTok or website was found. Absence from one search engine is not proof the author has no other presence.
* A numeric-id Facebook profile with mixed-language captions is consistent with a content-farm style account, but that is an observation about format, not a finding about the person.

## 3. Related author content

**Accessible related same-author sources: 0.** The brief asks for an author cluster so that logic is not inferred from one video; that is **not possible here**. The earlier user-supplied screenshots listed other pattern topics from the same page (flags, triangles, diamond, cup and handle, and others), but they are thumbnails: I did not open those videos and make no claim about their content. A repeated-logic analysis is therefore **INSUFFICIENT**.

## 4. Independent related sources

Opened and read (4):

| Source | Type | Quality | What it gives |
|---|---|---|---|
| Bulkowski, thepatternsite.com bullish Wolfe Wave | statistics page | MEDIUM-HIGH (explicit method, large sample) but self-declared idealised | 6,269 patterns on 3,522 stocks (daily); headline 47% meet the EPA target, 15% break-even failure, rank 34 of 39; "perfect trades": entry at the exact point-5 low; the page states this performance "cannot be duplicated in real life" |
| LuxAlgo library, Wolfe Waves | vendor education | LOW-MEDIUM | rules; "no rigorous public statistics exist"; points are "drawn rather than detected"; loose rules find waves "everywhere in hindsight"; recommends a reversal-bar confirmation; does not address repainting |
| ATAS, Wolfe Wave guide | vendor education | LOW-MEDIUM | entry at point 5 "may involve certain nuances"; Wolfe "did not offer strict guidelines" for stops; target is the 1-4 line; no accuracy figures; subjective recognition; does not address repainting |
| Quantum Algo, Wolfe Wave guide | vendor education | LOW | cites Bulkowski as 41% (bullish) and 35% (bearish) reaching the EPA; **this does not match Bulkowski's own page (47% headline; his page is internally inconsistent, 41% in a second table)**. A secondary figure was repeated without checking. |

Seen only in search-result summaries, not opened (6): TheRightTrader, Bajaj Finserv, UAlgo and BigBeluga TradingView scripts, ProRealCode forum thread, BrokerXplorer. They were used only as pointers, never as the sole support of a conclusion.

Critical or contradictory material found: no independent study of Wolfe Wave profitability on gold or intraday data; vendor pages and a forum thread with unverified testimonials; the generic advice that a win rate above about 75% should be checked for look-ahead. **Independent sources opened: 4.**

## 5. Strategy rule extraction

Machine: REGIME, DIRECTION, SETUP, TRIGGER, ENTRY, STOP, TARGET, EXIT.

| Stage | Content | Status |
|---|---|---|
| REGIME | none stated; chart shows a descending channel before the pattern | UNKNOWN (rule), OBSERVED (picture) |
| DIRECTION | counter-trend: bullish reversal at the end of a falling wedge | OBSERVED |
| SETUP | five alternating points: 1 low, 2 high, 3 lower low, 4 lower high, 5 undercut of the 1-3 line; 1-3 and 2-4 lines converge | OBSERVED (diagram and chart); matches LuxAlgo and ATAS |
| TRIGGER | none beyond "Entry in this area" at point 5; no confirmation candle, no break rule | OBSERVED label, rule UNKNOWN |
| ENTRY | "ENTRY LONG" arrow at point 5 | OBSERVED; price level unreadable |
| STOP | red STOP-LOSS line at the point-5 level | OBSERVED; derivation (structure, ATR, pips) UNKNOWN |
| TARGET | point 6 on the line from point 1 through point 4, extended | OBSERVED; time or price of arrival UNKNOWN |
| EXIT | none beyond reaching the target; no partial, trailing or break-even | UNKNOWN |
| Symbol, timeframe, session, spread | not shown | UNKNOWN |

**Verdict: strategy logic extracted = PARTIAL.** What exists is a pattern definition with a drawn entry, stop and target, not a trading system.

## 6. Entry logic

* Entry is drawn at point 5, the extreme of the fifth leg. Independent sources split between entering at point 5 and waiting for a break back through the 1-3 line or a reversal bar (LuxAlgo recommends confirmation). The video shows no confirmation.
* **What appears when (from the contact sheets):** 0 s: only a falling channel, price at the right edge already sliding. 3 s: points 1-4 drawn, the blue 1-4 line extended to the right, price at the right edge at the lower line. 6 s: points 1-5 labelled and the yellow target arrow to point 6 drawn, **before any entry label**. 9 s: red zone and ENTRY LONG appear. 11 s: STOP-LOSS appears, **after** the entry label. 12-16 s: candles to the right rise toward the target.
* **Levels do not move** once drawn; no label is redrawn or removed.
* **Hindsight risk: HIGH.** Point 5 is marked at the live right edge, but a pivot cannot be known until bars after it have printed (the repository's detector confirms it 3 bars late). The post-point-5 rise is then revealed. Whether this was drawn live or is a scripted replay cannot be established from the video. It is a single curated winning example.

## 7. Stop-loss logic

Drawn at the point-5 level (just beyond the extreme). How wide it is in price, ATR or pips is UNKNOWN; there is no price axis. ATAS says Wolfe gave no strict stop rule. A stop placed right at the extreme is tight by construction, which makes the displayed reward-to-risk look large; that figure is a property of the drawing, not a result.

## 8. Take-profit logic

* DISPLAYED target: one target (point 6) on the extended 1-4 line (the "EPA" line). No TP2, TP3, fixed R multiple, partial close or trailing is shown.
* ACTUALLY MANAGED target: UNKNOWN (no management shown).
* LuxAlgo notes waves "often stall short" of the EPA line and ATAS mentions more conservative targets at nearby support or resistance.

## 9. Alert and repaint analysis

* The video has no alert, no indicator and no bar-close concept: **alert logic UNKNOWN**; intrabar vs bar close UNKNOWN.
* Visual labels were static once drawn (no redraw observed over the visible frames).
* Technique-level repaint risk: a Wolfe point is a swing pivot, and a swing pivot needs bars to its right. Any tool that marks point 5 at the live edge repaints or anticipates; a tool that waits for a confirmed pivot (for example the UAlgo script as described in search results: pivots via `ta.pivothigh/low` with a right-hand wait) does not peek but signals late. Whether the tools the web pages mention repaint was **not verified** (no source code was read). **Repaint risk for this video: UNKNOWN; for a live-drawn point 5: HIGH.**

## 10. Performance-claim audit

| Claim | Where | Verdict |
|---|---|---|
| Any win rate, profit or "non-repaint" claim | not made in the video; the caption is a question | none to verify |
| Implied: price reaches the target after ENTRY LONG | one example | **UNVERIFIED**, hindsight, n = 1, no costs, no instrument |
| Independent hit rate | Bulkowski: 47% reach the EPA, about 49% stopped out, on stocks, daily, perfect-entry; ranked 34 of 39 patterns | **not transferable** to gold, to intraday, or to a real entry; the author says it cannot be duplicated |
| Secondary 41% / 35% | Quantum Algo | misquote of the primary page |

Views, reactions and shares (1.9K reactions, 183-184 shares, 76,902 views at the time) are popularity, not evidence, and were not used.

## 11. Comparison with XAU EDGE (from the actual code)

Files read: `trading/baseline.py`, `trading/levels.py`, `trading/market_state.py`, `trading/setup_alerts.py`, `structure/swings.py`. Running version: v1.1.0 (1.2.x opt-in, not running).

| Concept | External (this reel) | XAU EDGE (code) | Same / different | More explicit | Testable? |
|---|---|---|---|---|---|
| Trend direction | none; counter-trend reversal | H1 only: BULLISH if close > slow EMA and fast > slow and structure trend >= 0 (`market_state.py:301`) | different | XAU EDGE | yes |
| Regime | none | H4 vetoes the opposite side; SHOCK and HIGH_VOLATILITY blocked; volatility high/low gates (`baseline.py` `_gates`) | different | XAU EDGE | yes |
| Setup definition | 5-point wedge with overshoot | M15 structure with the trend and a pullback to the fast EMA within -0.3..+0.7 ATR (`market_state.py:319`) | different family (reversal vs continuation) | both usable; Wolfe rules are convention-dependent | yes |
| Trigger timing | at point 5, no confirmation | M5 momentum: ROC and RSI beyond 52/48 plus BOS or strong body, on a closed bar (`market_state.py:330`) | different | XAU EDGE | yes |
| Pullback logic | none (the wedge is a counter-trend leg) | explicit EMA-distance band | different | XAU EDGE | yes |
| Structure | pivots implicit (hand drawn) | confirmed swings left=right=3, BOS/CHoCH, S/R (`swings.py`, ADR-0012) | partly same idea | XAU EDGE | yes |
| Liquidity concept | none | **none** (0 code hits for liquidity, sweep, order block, fair value) | same absence | n/a | no definition exists |
| Supply/demand, premium/discount | none | none; support/resistance from swings | same absence | n/a | no definition exists |
| Entry timing | at the extreme (drawn) | market at ask/bid after the trigger, setup expires after 3 M5 bars | different | XAU EDGE | yes |
| Stop placement | at point 5 | HYBRID: larger of structure swing + 0.1 ATR and 1.25 ATR; refused above 3 ATR (`levels.py`) | different | XAU EDGE | yes |
| Target placement | point 6 on the 1-4 line | 2R, capped by the next opposing level minus 0.1 ATR (`levels.py`) | different | XAU EDGE | yes |
| Risk/reward | not stated | net R:R >= 1.5 after spread, refused otherwise | external silent | XAU EDGE | yes |
| Multiple targets | single displayed target | TP1 (2R) and TP2 (3R) when not capped; no partial, break-even or trailing in the desk | external silent | XAU EDGE | yes |
| Confirmation delay | none shown (hindsight) | closed bars only; pivots known 3 bars late; M5 close | different | XAU EDGE | yes |
| Alert timing | none | one message per setup, on closed-bar decisions, with the evidence line "UNVALIDATED" | external silent | XAU EDGE | yes |
| Repaint risk | UNKNOWN / HIGH if live-drawn | non-repainting by construction (closed bars, confirmed pivots) | different | XAU EDGE | yes |

## 12. Possible design mismatches (brief section 15 and 16)

The brief's assumptions about XAU EDGE are accurate: H1 is the sole direction source, H4 only vetoes, M15 is the setup, M5 the trigger, M1 only blocks, net R:R >= 1.5, hybrid stop, 2R/3R targets capped by structure. **This video cannot judge them**: it contains no trend filter, no timeframe stack, no trigger rule and no risk rule. Different is not wrong.

Could "enter earlier" explain XAU EDGE's late entries or R:R refusals? The mechanism is real in principle: entering at a structural extreme with a stop just beyond it gives a small risk and therefore a large R:R by construction; entering after an M5 confirmation with a stop of at least 1.25 ATR does not. But three facts block a conclusion:

1. The tight-stop entry at point 5 is only achievable with hindsight (the extreme is unknowable until later); Bulkowski's own figures use that unachievable entry.
2. The repository's measured funnel (`docs/reports/SIGNAL_FUNNEL_ANALYSIS.md`, three burnt windows, 16,270 decisions, v1.1) shows only **2 BUY signals**, and the gates that remove most decisions come **before** the trigger: volatility low/high (about 70% and 80% independent pass rates), spread (88%), M15 setup (11.6% pass: pullback alone 12.4%), M5 trigger (21.3%). After the trigger, RR_TOO_LOW and INVALID_STOP_DISTANCE account for tens of decisions, not thousands. Late entry is a hypothesis; the funnel points mainly at setup and regime scarcity.
3. XAU EDGE's lateness buys non-repainting. The video's apparent earliness is the repaint/hindsight problem seen from the other side.

## 13. UI lessons (separate from strategy quality)

The reel's presentation is good even though its strategy evidence is nil:

1. **Staged plan overlay on the chart:** numbered pattern points, a target arrow, a red risk zone from entry to stop, and "ENTRY LONG" / "STOP-LOSS" labels, with levels that stay fixed once shown.
2. **A visible risk zone** (shaded entry-to-stop) makes the cost of being wrong as visible as the target.
3. **One explained concept per screen:** a clean reference diagram above the live chart makes the rule readable without sound.

XAU EDGE already shows an Entry/SL/TP plan card and has a plan overlay in progress in the dashboard working tree (another session's uncommitted `SystemTradePlanOverlay.tsx`; not touched here). Nothing in this report argues for changing strategy code to match a good picture.

## 14. Future research candidates (NOT AUTHORIZED, POST-HOC, NOT VALIDATED)

Recorded as ideas only. Each would need a new charter, a new preregistration, a new trial count K, and untouched evaluation data; none is run here.

1. **Entry-timing sensitivity:** does an earlier, structure-based entry (before M5 confirmation) change net R:R and signal count without increasing false entries? Mechanism: stop distance shrinks when the entry is nearer the swing. Risk: it is the repaint trap above; must use only closed bars.
2. **Wolfe geometric frequency study** on unprotected development data, descriptive only (how often, how long to the EPA line, how often stopped first), with the random-walk match rate (about 46 per 10,000 bars in the repository's synthetic test) as the null.
3. **Reversal-at-extreme with confirmation bar** (LuxAlgo's variant) versus the continuation baseline, as a different strategy family, not an adjustment of v1.1.

## 15. Evidence matrix

| Claim | Source | Support | Contradict | Quality | Confidence |
|---|---|---|---|---|---|
| The reel shows a bullish Wolfe Wave with entry, stop and target | the media itself | frames at 0-12 s | none | high (primary, observed) | high |
| The author is "Zenix Arixon" | extractor metadata | uploader field | none | medium (metadata) | high for the name, none for identity |
| The reel gives a trading system | n/a | none | no trend, trigger, risk or management rules | n/a | high that it does not |
| No spoken explanation | ASR | 0 segments | none | medium (one ASR model) | medium-high |
| Wolfe geometry: converging wedge, point-5 overshoot, 1-4 target | LuxAlgo, ATAS, Quantum Algo (opened) | consistent | entry trigger and stop rules differ | low-medium | medium |
| Target is reached often | Bulkowski | 47% under perfect entry | rank 34/39; "cannot be duplicated"; secondary sources quote 41/35 | medium-high but idealised | the number is not usable for trading |
| The pattern is reliable or profitable | any | none credible | LuxAlgo: no rigorous public statistics | n/a | none |
| Signal exists in real time | the reel | ENTRY label appears with price still near point 5 | point 5 needs later bars; continuation revealed afterwards | observed | unknown, hindsight risk high |
| The tool does not repaint | none | none | none | none | UNKNOWN |

## 16. Final verdict

Strategy logic components:

| Component | Verdict |
|---|---|
| Pattern geometry (wedge, overshoot, 1-4 target) | SUPPORTED as a common convention (education sources), not as a profitable rule |
| Entry at point 5 | PLAUSIBLE as a description, UNSUPPORTED as a real-time rule |
| Stop at point 5 | PLAUSIBLE, derivation UNKNOWN |
| Single target on the EPA line | SUPPORTED as convention; arrival timing UNKNOWN |
| Win rate / profitability | UNSUPPORTED |
| Alerts / repaint behaviour | UNKNOWN |
| Trend, regime, sizing, management | UNKNOWN |

XAU EDGE components: **CONSISTENT WITH EXTERNAL PRACTICE:** closed-bar, non-repainting signals; a stop beyond structure; a target on the next level. **NEED EMPIRICAL TEST (not decided by this video):** the M5 trigger delay, the 1.25 ATR stop floor, the pullback band. **UNRELATED:** liquidity and supply/demand (absent in both). **NOT SUPPORTED OR CONTRADICTED BY THIS SOURCE:** nothing.

Top five findings, by potential impact on timing, R:R, false signals, risk and usability:

1. The reel is an illustration, not a strategy; no XAU EDGE logic can be validated or refuted from it.
2. The pattern's appeal (tight stop, large R:R, early entry) depends on knowing the extreme in advance; the best independent statistic uses that unachievable entry.
3. The only credible independent number (Bulkowski 47% reaching the EPA, rank 34/39) is for daily stocks with perfect entries and is misquoted by secondary pages.
4. XAU EDGE's measured bottleneck is regime and setup scarcity before the trigger, not the post-trigger R:R gate; "late entry" stays an unproven hypothesis.
5. The presentation (fixed-level staged overlay with an entry-to-stop risk zone) is worth reusing; its strategy content is not.

```
ORIGINAL VIDEO ACCESSED:
YES

AUTHOR IDENTIFIED:
Zenix Arixon (Facebook account; real identity UNKNOWN)

RELATED SAME-AUTHOR SOURCES:
0

INDEPENDENT SOURCES:
4 opened (plus 6 seen only in search summaries)

STRATEGY LOGIC EXTRACTED:
PARTIAL

REPAINT RISK:
UNKNOWN (video has no indicator or alert); HIGH if point 5 is marked live

PERFORMANCE CLAIM VERIFIED:
INSUFFICIENT (the video makes none; independent statistics are idealised and not transferable)

XAU EDGE LOGIC CONSISTENCY:
Different strategy family (reversal at an extreme vs trend pullback); XAU EDGE is more explicit on every compared element and non-repainting by construction; nothing in the video contradicts it.

POSSIBLE XAU EDGE DESIGN ISSUES:
1. Entry timing: market entry after M5 confirmation with a stop floor of 1.25 ATR may lower R:R versus structure-based entries; plausible mechanism, unproven, and the internal funnel points elsewhere.
2. Setup scarcity: M15 pullback band (-0.3..+0.7 ATR) passes about 12% of decisions; thresholds are arbitrary and untested in isolation.
3. No liquidity-sweep or supply/demand concept exists; whether it would add anything is UNKNOWN.

UI LESSONS WORTH ADOPTING:
1. Staged plan overlay with fixed Entry, Stop and Target levels.
2. Shaded entry-to-stop risk zone.
3. One explained concept per screen (reference diagram plus live chart).

NEW RESEARCH REQUIRED:
NO (optional future candidates need a new charter, preregistration, K and untouched data)

CURRENT PROJECT SHOULD BE MODIFIED NOW:
NO

OVERALL CONCLUSION:
The link is a 16.7 second public Reel from the account "Zenix Arixon" that illustrates a bullish Wolfe Wave with a drawn entry, stop and target; it contains no speech, no indicator, no alert, no trend or risk rules and no performance claim, and the author's other content is behind a login. Independent sources agree on the pattern's geometry but give no tradable statistics: the one rigorous source (Bulkowski) reports 47% reaching the target only under an entry that cannot be reproduced, ranks the pattern 34th of 39, and is misquoted by secondary pages. The comparison with the real XAU EDGE code shows a different, more explicit, non-repainting trend-pullback design, with no contradiction from this source and no justification to change the project; the one actionable item is presentational (a staged overlay with a visible risk zone), and any entry-timing question belongs to a future, separately authorised study.
```
