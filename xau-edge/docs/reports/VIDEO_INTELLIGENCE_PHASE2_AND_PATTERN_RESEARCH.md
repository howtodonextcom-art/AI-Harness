# Video intelligence, phase 2, and pattern research

Date: 2026-10-11. Scope: verify what phase 1 delivered, harden the pipeline on a real YouTube source,
research the Wolfe Wave and its author independently, build a pattern framework, implement at most two
more detectors, characterise timing and frequency, and document future research. **No outcome research
was performed. Test-H, Holdout and Validation-2 were not opened. Nothing is connected to any engine.**

## 1. Executive verdict

* Phase 1 was real but had gaps that only a real run exposed (a sampler that kept every frame, a wrong
  ASR language, annotations lost on re-ingest, duplicate records, a defect in a detector's trigger
  order). All are fixed with regression tests; mutation checks show the key tests fail when the code
  is broken.
* The Wolfe detector is causal (0 violations on 2,520 cuts; a look-ahead mutant gave 49) and its rules
  now have a sourced table with the places where the code does **not** match the sources.
* The "46 matches per 10,000 bars" figure reproduces (46.5, range 30-60) but is specific to a Gaussian
  random walk: real Development-2 H1 shows 14.6 per 10,000 and a block-shuffled null 15.8. The
  geometry is common by chance; matching it is not evidence.
* Two detectors were added by a pre-written rubric: double top/bottom and head and shoulders.
  **The textbook double top offers a gross R:R of about 0.72**, so it cannot help a system whose gate is
  net R:R >= 1.5. The Wolfe picture shows R:R 3.6 only because its stop sits at an extreme that cannot be
  known in advance.
* No pattern here addresses the "late entry" worry: every trigger in this family carries a pivot
  confirmation lag. The only way to be earlier is to act before the pivot exists, which is hindsight.
* Author research: the account "Zenix Arixon" left no trace outside the login-walled Facebook profile;
  same-author cluster is empty. Independent sources agree on geometry and disagree on entry, P5 and ETA;
  no independent statistic transfers to gold or intraday.
* Project trading logic: no change warranted.

## 2. Git reality

Read from the repository, not from the previous message:

* A phase-1 summary quoted commit SHAs that are not current: the history was rewritten locally for
  this phase's own unpushed commits (see below), and `origin/main` was advanced by someone else.
* `origin/main` is at `930c692` ("feat: add automatic trade plan overlay", another session's commit) and
  already contains the phase-1 commits `c624650`, `c20c81b`, `ebd4d46`. I did not push; the push was
  made by another actor.
* Local `main` is ahead of `origin/main`; see `git log origin/main..HEAD` for the exact commits.
* Another session's uncommitted dashboard work and screenshots under `docs/reports/img/` exist in
  the tree; they were left untouched.
* Commit discipline: the pre-commit `mypy --strict` hook checks the whole working tree including new
  untracked files, so two parts that share tests could not be committed separately; the code is one
  commit with a message that says so. Three local, unpushed commits were rebuilt twice to fix an
  accidental merge of two parts; no pushed history and no research history was rewritten.

## 3. Phase-1 delivery verification

| Claim (phase 1) | Actual code | Tested | Runtime verified | Status |
|---|---|---|---|---|
| Isolated `video_intel` package | `src/xau_edge/video_intel/` (9 modules); `grep` shows no import of trading, execution, brokers, funded, control, signals, api, ops, MetaTrader5 | yes: a test greps the package | n/a | VERIFIED |
| Nothing uses the new code | no module outside `video_intel` and `structure` imports it | grep | n/a | VERIFIED |
| Source validation, https and host allow-list | `source.py` | spoofed hosts, userinfo, schemes | n/a | VERIFIED |
| No cookies or credentials | `assert_no_credentials` | flags refused | real runs used none | VERIFIED |
| Real Facebook download | `ingest.py` | fake extractor | **yes, twice**, same SHA-256 from two share links | VERIFIED |
| Real YouTube | not tested in phase 1 | fake extractor | **yes now** (4.5 min, 86 speech segments) | VERIFIED in phase 2 |
| Transcript with real timestamps | `transcribe.py` | WAV and no-speech tests | **yes now** on real speech; the reel has none | VERIFIED in phase 2 |
| Adaptive keyframes | `media.py` | unit + integration | real runs | **was defective** (kept 540/540), fixed |
| ASR language | stored from the detector | none | real run | **was wrong** (English as Yoruba), fixed |
| Wolfe non-repainting | `structure/wolfe.py` | one prefix test | not proven | now PROVEN by the harness |
| Skill callable from Claude Code | `.claude/skills/video-intel/SKILL.md` | none | the CLI was run from the agent; the skill was **not** discovered as a registered skill in this session | NOT VERIFIED |
| "No liquidity concept" | `trading/`, `structure/`, `features/` have none | grep | n/a | **true but too narrow**: `research_v2` tested sweeps (H07) |
| 11-tool MCP | not built | n/a | n/a | DEFERRED (not needed) |
| `PARTIAL_INPUT_ONLY` | enum value only | n/a | n/a | NOT BUILT |

Tests now: video_intel 46 unit, 5 + 15 integration, structure 13 + 7 + 19 + 14 (Wolfe, reclaim,
reversal, policy and statistics), all in the full run below.

## 4. Original Reel provenance

Record `d34e96f7f2e6` (`docs/video-intelligence/knowledge/d34e96f7f2e6.json`):

* canonical share URL `.../share/r/18kMRKXFsk/...`; the second link `.../share/r/1AteztJsfX/...` is
  recorded as an **alias**: the two downloads are byte-identical (SHA-256 `1348521a...4e28`);
* resolved page `https://m.facebook.com/watch/?v=1363296065794611&_rdr`, platform id `1363296065794611`;
* account "Zenix Arixon" (numeric profile id 61592920220642 from the extractor; identity unknown);
* 16.685 s, 1088x1936, AAC audio; 33 frames sampled, 15 kept; ASR `faster-whisper base` found 0 speech
  segments (audio rms 0.15) so the transcript is empty and says why;
* labels read from frames at 0, 9, 12 and 15.5 s with confidence; three traces (entry, stop, target) each
  with locator, observation, interpretation, concept and code reference;
* confidences: geometry SUPPORTED_EXTERNALLY (MEDIUM), outcome UNKNOWN (HIGH confidence that it is
  unknown), caption CLAIMED_BY_AUTHOR;
* ingest time and provenance string ("yt-dlp, no cookies, no credentials") are stored; history of the
  record is kept (4 versions after the re-ingests of this phase).

No re-download was needed for verification; the media was re-fetched only to refresh the record with the
new code, and that run also proved re-ingest keeps annotations.

## 5. Author-source cluster

**0 related same-author sources accessible.** The Facebook profile and its reels tab require a login and
were not bypassed. Searches for the exact name, the Hinglish caption, the hashtags and Vietnamese
queries returned no Instagram, YouTube, TikTok, TradingView or website for "Zenix Arixon" and no repost
of the reel. A numeric-id profile with a mixed-language caption fits a content-farm format, which is an
observation about format, not about a person. Whether the author has a stable method or posts selected
examples cannot be decided: **INSUFFICIENT**.

## 6. Independent Wolfe sources

Read in full (6): Bulkowski (statistics and identification rules), LuxAlgo, ATAS, Quantum Algo, a
BabyPips thread, and a YouTube tutorial whose media and speech were ingested ("Wolfe Wave Pattern
Strategy Explained", commercial, 4.5 min). Seen only in search summaries (about 10): TheRightTrader,
Bajaj Finserv, FBS, UAlgo and BigBeluga TradingView scripts, LuxAlgo's detector, a community zigzag script,
ProRealCode, Apex Edge, a gold chart idea. An MQL5 PDF was fetched but is scanned images and was not read.
TradingView source code could not be retrieved, so no claim is made about what any script does.

Contradictory or critical material: LuxAlgo ("no rigorous public statistics", "everywhere in hindsight"),
ATAS (subjective, no accuracy figures), BabyPips (indicator code problems, no results), Bulkowski himself
("cannot be duplicated in real life", rank 34 of 39), and the Quantum Algo page that misquotes him.

## 7. Wolfe canonical definition

Full table: `docs/video-intelligence/pattern-research/WOLFE_CANONICAL_DEFINITION.md`. Summary: CONSENSUS on
the five alternating points, P3 below P1, P4 below P2, converging lines, EPA on the 1-4 line, the mirror;
DISPUTED on P5 overshoot (the reel, LuxAlgo and the YouTube tutorial require it; Bulkowski does not),
entry (at P5 versus after a close back inside line 1-3), and timeframe; VARIANT: Fibonacci limits and
symmetry (one commercial tutorial); UNKNOWN: stop distance, repaint behaviour of any script, statistics
for gold. Mismatches found in the code: the target time (`P5 - P3` bars after P5) is this project's own
convention that no source uses, so the sourced ETA (where lines 2-4 and 1-3 meet) was added as an option;
the stop is exactly at P5 while sources say "beyond".

## 8. Wolfe detector audit

Read deeply (`structure/wolfe.py`, `pivots.py`):

* swings: confirmed pivots from `analyse_structure`, left=right=3; a pivot is knowable at `bar + 3`;
* alternation: of two same-kind pivots in a row the more extreme replaces the earlier one; a pattern built
  on a replaced pivot is retired (for the new detectors) - for Wolfe both candidates were emitted in real
  time, which is correct for a stream but yields near-duplicates;
* geometry: rules 1-5, 8 and 17 of the table; rule 6 (no higher peak or lower valley between points) is
  only approximated; overlap handling is absent;
* complexity: linear; 100,000 bars in 1.1 s;
* a gap was found: Wolfe uses a sliding window of the last five pivots, so on a random walk **94% of
  detections overlap the previous one and 28% are nested**, which means the effective number of
  independent patterns is far below the count. On real Development-2 data the overlap is 14%.

## 9. Lookahead and confirmation audit

* `causality_violations`: run the detector on data up to each cut and require the same detections as the
  full run's `actionable_at <= cut`. Wolfe: 40 random series, 2,520 cuts, **0 violations**; the same
  harness gave 49 violations for a deliberate look-ahead mutant, so it is not vacuous. The new reversal
  detectors, the reclaim mode and the contract adapter pass the same test.
* mutation checks that the tests must (and do) catch: pivots treated as known at formation; a trigger
  scan running past the available data; a trigger reported before it is knowable; ignoring supersession;
  trigger on the low instead of the close; ignoring the stop breach.
* the supersession mutant was **not** caught at first; that exposed a real defect in the reversal
  detector (a pattern on a replaced peak could fire at the same bar as the new one: 3 duplicates in 150
  random walks). The processing order was changed (pivots first, then triggers); duplicates are now 0 and a
  property test fails on the mutant (35 duplicates).

## 10. Detection time versus pattern time

The contract carries three bar indexes: `geometry_known_at` (last point confirmed), `detected_at`
(trigger known) and `actionable_at` (close of this bar is the earliest moment to act), plus each
point's `confirmed_at` and `trigger_delay_bars`. A point labelled at its formation bar before its
`confirmed_at` would be hidden hindsight; the model validator rejects disordered times. For example the
bullish Wolfe test: P5 forms at bar 90, is known at bar 93, and in `LINE13_RECLAIM` mode the entry is the
first close above line 1-3 (a later bar unless price already reclaimed during the confirmation window).

## 11. Random-walk control (reproduced)

`scripts/pattern_descriptive.py random_walk` (20 seeds x 10,000 bars; defaults; fixed before the run):

| Detector | per 10,000 bars (mean, min-max) | overlap with previous |
|---|---|---|
| Wolfe | **46.5** (30-60) | 94% |
| Double top/bottom | 58.5 (44-72) | 94% |
| Head and shoulders | 4.3 (1-9) | 38% |

The earlier 46 figure is reproduced exactly, by the same author with the same generator, so this is a
reproduction, not an independent check. On a random walk about 94% of Wolfe and of double top/bottom
detections overlap the previous one (sliding windows over the same pivots), so the count overstates the
number of independent patterns; on real Development-2 data the overlap is 14% and 12.5%. A Gaussian random walk is not a good null for real data, so a
second null was built from Development-2 itself: bars cut into 48-bar blocks and re-ordered (20 shuffles).

| Detector | real Development-2 H1 | block-shuffled null (mean, range) |
|---|---|---|
| Wolfe | 14.6 (71 detections) | 15.8 (14.4-18.6) |
| Double top/bottom | 59.2 (287) | 55.8 (53.6-58.6) |
| Head and shoulders | 1.4 (7) | 2.7 (1.2-3.9) |

Real frequencies are inside or just above the shuffled range (double top/bottom about 6% above its
maximum, which is small and not interpreted). Geometric existence is therefore common by construction.

## 12. Pattern framework

`structure/detection.py`, `pivots.py`, `pattern_stats.py`, `descriptive_data.py`; decision and criteria in
`pattern-research/PATTERN_FRAMEWORK.md`. Option B (shared contract plus empirical causality harness) was
chosen over per-pattern functions and over streaming classes. Detector quality and strategy quality are
separated by constants (`evidence = GEOMETRY_ONLY`, `outcome_evidence = NONE`) that a detector cannot
change, and the statistics module takes detections only, so it cannot compute an outcome.

## 13. Candidate inventory and prioritisation

Rubric written first (`rubric.json`), then scores (`scores.json`), arithmetic by `scripts/pattern_rubric.py`:
double top/bottom 78.8, head and shoulders 73.8, break-and-retest 62.5, Wolfe 57.5, triangle and flag 55.0,
cup and handle 47.5, supply/demand 36.2 (disqualified), diamond 33.8 (disqualified); liquidity sweep
disqualified (it is V2 H07). Robustness: top two in 100% of random weightings and 99.9% / 97.7% under
scoring noise. See `PATTERN_INVENTORY.md`. Single rater; the scores are judgement.

## 14. Additional detectors

Implemented (the maximum of two): **double top/bottom** and **head and shoulders / inverse**
(`structure/reversal.py`): closed-bar neckline break trigger, seven parameters, mirror-symmetric, causal by
construction. Plus a Wolfe `LINE13_RECLAIM` entry mode and a sourced `LINES_INTERSECTION` ETA. Not
implemented: everything else.

## 15. XAU EDGE comparison

(Code read in the previous report: H1 direction from EMA and structure; H4 veto; M15 pullback band; M5
momentum trigger on a closed bar; M1 blocks; hybrid stop of at least 1.25 ATR; 2R target capped by
structure; net R:R >= 1.5.) The mechanism questions:

* **Late entry:** pattern triggers here are not earlier than the M5 trigger. A Wolfe point is known 3 bars
  after it forms; a neckline break comes a median 7 H1 bars after the second peak is confirmed (head and
  shoulders: 1). Earlier means acting on an unconfirmed pivot.
* **R:R collapse:** the shape itself gives double top/bottom a gross R:R of median 0.72 (0 of 287 reach 1.5)
  and head and shoulders 1.46 (29% reach 1.5); XAU EDGE would refuse these setups at its own gate.
  Wolfe's displayed R:R (median 3.6, 90% above 1.5) comes from a stop at the extreme.
* **Too much confirmation / setup scarcity:** frequency of a pattern is not comparable with XAU EDGE's
  decision counts (per-minute decisions, 2 BUYs in 16,270), so no scarcity claim is made.
* Net: none of these patterns fixes a known weakness. The earlier funnel evidence (scarcity before the
  trigger, not after) stands.

## 16. Timing implications

Entry timing mapped, descriptive only: pivot confirmation lag is exactly the right-hand window (3 bars) for
every pattern here; double top/bottom adds a median 7 bars (up to 20) from geometry known to the neckline
close, with a trigger already made inside the confirmation window in a minority of cases (median delay 0,
maximum 2); Wolfe `LINE13_RECLAIM` on a synthetic random walk adds a median of **0 extra bars** after P5
is confirmed (75th percentile 0, maximum 18) and 70% of geometries ever reclaim (synthetic only; not
computed on market data because it is price behaviour after the pattern). The dominant source of lateness
is the pivot confirmation itself, not an extra confirmation step.

## 17. Descriptive data findings

Dataset classification before any access: `random_walk` SYNTHETIC; `dev2_h1` (Development-2 2011-01-01 to
2018-12-31) BURNED and open for counts only by the precedent `event-counts-dev2.json`; `val2_h1` RESERVED
(untouched, kept clean) and refused; `testH`, `holdout` LOCKED and refused; `ftmo_2025_plus` and the
live ledger FORBIDDEN (they contain the Holdout) and refused; anything else UNKNOWN and refused. The
loader reads Development-2 only through a filtered scan and asserts no later bar was loaded; the policy
and the loader are tested, including a file that spans the boundary.

48,470 H1 bars: Wolfe 71 detections (26, 12, 4, 7, 5, 7, 4, 6 per year 2011-2018: not interpreted),
double top/bottom 287 (143 tops, 144 bottoms), head and shoulders 7. Durations, legs, overlap and
hour-of-day counts are in `dev2_h1_descriptive.json` (hour-of-day is informational: the broker clock is
certified for only some years). **No returns, win rates, target hits, "best" timeframe, tolerance or
session were computed.** Defaults were fixed in advance and never swept on market data.

## 18. GitHub repository review

Reviewed from their GitHub pages only (README level; code and licence files were not read):

| Repository | What it is | Licence, activity (as shown) | Decision |
|---|---|---|---|
| khou/watch-video | agent skill: yt-dlp, platform captions first then whisper.cpp, ffmpeg adaptive frames, markdown summary, cost modes | MIT; 13 commits, 5 stars | **BORROW IDEA**: use platform captions before ASR; cost modes. Not adopted as code. |
| stevederico/video-understanding | two-stage skill: deterministic extraction (frames at timestamps, SRT, manifest) then agent reads; local, BYOK and grok modes | MIT; 34 commits, 1 star | **BORROW IDEA**: manifest plus timestamp-named frames, refusing post links. **REJECT** the BYOK modes (video leaves the machine). |
| microsoft/playwright-mcp | MCP server for browser automation | Apache-2.0; active, 38k stars | **NOT NEEDED**: no logged-in browsing is allowed here. |

## 19. CLI versus skill versus MCP

| Criterion | CLI | Claude skill | MCP server |
|---|---|---|---|
| Repeatability | high: same command, JSON out | high: documents the workflow | high |
| Tool discovery | by help text | by the skill listing at session start | native |
| Session persistence | files (`data/video_knowledge`) | n/a | process state, not needed |
| Security | stateless, no network listener | none | a long-running process with network and file access |
| Maintenance | one script | one markdown file | a server, a protocol version, packaging |
| Workflow benefit now | the agent already runs shell commands | steers the agent | would help only for non-shell clients |

Decision: **CLI plus skill; MCP NOT NEEDED.** Revisit only if a non-shell client or a multi-user setting
appears.

## 20. Real YouTube acceptance

Public video "Wolfe Wave Pattern Strategy Explained | How to Trade Reversals Like a Pro" (4 min 30 s,
`HfsBmSDwhgE`), no cookies: metadata ACCESSIBLE; download MEDIA_READY (1914x1080, AAC); probe; frames: 540
sampled, **29 kept** after the budget fix (540 before); ASR 86 segments with real timestamps; knowledge
record with 7 claims, 4 traces, 2 external sources, 1 concept, 3 links; query retrieval via `ask` splits
VIDEO SAYS, EXTERNAL SOURCES SAY, CODE IMPLEMENTS and UNKNOWN. **PASS.** Content: a Fibonacci variant
(P3 and P5 within 127.2-161.8% extensions, symmetric legs), entry only after a close beyond and then back
inside line 1-3, stop at P5, exit at the 1-4 line, and commercial claims ("sniper entries, minimal risk")
with a disclaimer ("not saying this is perfect") and an offer to build trading bots. Findings: the ASR
mishears numbers ("1.37.2" for 127.2) and the detected language was wrong (fixed). The third-party
transcript is stored locally and **not committed**.

## 21. Knowledge-store audit

| Aspect | Before | Now |
|---|---|---|
| Deduplication | two records for one file | same SHA-256 becomes an alias; test |
| Source hashing | stored | stored, used for dedupe |
| Versioning | overwrite | history kept on change; re-ingest keeps annotations; annotate upserts by id |
| Evidence classes | five-way, mixed | six-way provenance with confidence; v1 migrates |
| Citations | free text | `ExternalSource` with quality and `opened`; a claim cites ids |
| Stale sources | none | warning after 30 days |
| Query | one concept view | questions routed to provenance, summary, rule, code |
| Untrusted text | quoted | unchanged; a test confirms injected instructions stay inert |

## 22. Future research candidates

`pattern-research/FUTURE_RESEARCH_CANDIDATES.md`. Classification: Wolfe DETECTOR ONLY; double top/bottom
FUTURE RESEARCH CANDIDATE with a low prior and a textbook exit that fails (R:R 0.72); head and shoulders
DETECTOR ONLY (7 events in 8 years); break-and-retest and liquidity sweep REJECT (V2 H08 and H07); others
DOCUMENT ONLY. The F1 opposite-direction idea stays POST-HOC, NOT VALIDATED, NOT AUTHORIZED.

## 23. Contamination analysis

Idea selection used a social-media reel, a tutorial and a rubric (no market data). Parameters are textbook
defaults tested on synthetic geometry. Development-2 was described once with fixed defaults (counts,
geometry, timing) and used for a block-shuffle null: it is already burned for outcomes, so this adds no
outcome contamination, but it is no longer "unseen". Validation-2 was not opened and is the cleanest
remaining historical data; Test-H and Holdout are locked (K already 44 in the shared accounting); forward
data is the only data that cannot have influenced the idea. See the table in the candidates document.

## 24. Stop-doing list

* No more patterns: the rubric cap is reached and the next candidates score below the threshold.
* No outcome statistics for any pattern, no reverse-direction look, no parameter sweeps on market data.
* No claim about what any TradingView script does without its source code.
* No wiring into the engine, the API or the dashboard; no UI overlay of patterns that looks like a signal.
* No MCP server, no more repositories.
* Not repeating phase 1's mistakes: a search-summary is not "opened"; an LLM-free router must not invent;
  a test that cannot fail is not a test (checked with mutants).

Defects and limits still open: skill registration not demonstrated; `PARTIAL_INPUT_ONLY` has no CLI path;
no OCR; platform captions are not used before ASR; the progressive-drawing integration test does not
discriminate (compression noise) while its unit twin does; the double top/bottom detector's parameter
count is 7, above the 6 in the rubric score (recorded, not re-ranked); rubric scoring is a single rater;
the Wolfe detector still emits near-duplicate overlapping candidates by design.

## 25. Final verdict

The pipeline works on real sources and is better tested than at the end of phase 1, mainly because
running it found bugs and mutation checks found a weak test and a real detector defect. Wolfe, double
top/bottom and head and shoulders are causal, well-defined, geometry-only detectors that appear about as
often in real gold data as in a shuffled copy of it, offer no evidence of predictive value, and do not
address XAU EDGE's late-entry or R:R concerns. The reel's author cannot be traced beyond a login wall and
the one rigorous independent statistic does not transfer. Nothing about trading logic should change.

```
VIDEO INTELLIGENCE PIPELINE:
PARTIAL

ORIGINAL FACEBOOK SOURCE:
VERIFIED

AUTHOR CLUSTER:
0 related sources

WOLFE DETECTOR:
VERIFIED

WOLFE LOOKAHEAD SAFETY:
PASS

RANDOM-WALK MATCH RATE:
46.5 per 10,000 bars on a Gaussian random walk (range 30-60); 15.8 on block-shuffled Development-2; real Development-2 14.6

PATTERN FRAMEWORK:
COMPLETE

ADDITIONAL DETECTORS IMPLEMENTED:
Double Top / Double Bottom; Head and Shoulders / Inverse Head and Shoulders

REAL YOUTUBE ACCEPTANCE:
PASS

MCP SERVER:
NOT NEEDED

EXTERNAL REPOS:
watch-video: borrow idea (captions first, cost modes); video-understanding: borrow idea (manifest, deterministic stage), reject BYOK; playwright-mcp: not needed. Reviewed at README level only.

XAU EDGE LOGIC FINDINGS:
No pattern trigger is earlier than the M5 trigger (every one carries a pivot confirmation lag); textbook double top/bottom R:R is about 0.72 gross and would fail XAU EDGE's own 1.5 gate; Wolfe's displayed R:R (median 3.6) exists only with a stop at an extreme that is unknowable in advance; funnel evidence still points at scarcity before the trigger.

FUTURE RESEARCH CANDIDATES:
Double Top / Double Bottom (low prior, conditional on a new preregistered exit; not authorized)

OUTCOME RESEARCH PERFORMED:
NO

TEST-H TOUCHED:
NO

HOLDOUT TOUCHED:
NO

ENGINE INTEGRATION:
NO

PROJECT SHOULD CHANGE TRADING LOGIC NOW:
NO

NEXT OWNER DECISION:
Rule on whether counts-only descriptive use of the burned Development-2 window (done once here, fixed defaults, relying on the event-counts-dev2.json precedent) is permitted for pattern studies, or revoke it.
```
