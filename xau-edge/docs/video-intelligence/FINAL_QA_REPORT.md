# Final QA report: video intelligence

Date: 2026-10-11. Scope: new `video_intel` package, Wolfe Wave research detector, CLI, skill. Nothing was wired into the Trading Core, API or dashboard.

## Verdict

**PARTIAL DELIVERY.** The ingestion-to-knowledge pipeline and one detector work and are tested. Several gates are not met or not applicable; they are listed below, not rounded up.

## Test evidence (run in this session)

| Check | Result |
|---|---|
| `pytest -m "not mt5"` (full) | **2690 passed, 1 skipped, 3 deselected**; coverage 90% (previous baseline 2635 passed: +55 new tests, nothing regressed) |
| New unit tests | `tests/unit/video_intel` (40), `tests/unit/structure/test_wolfe.py` (10) |
| New integration tests | `tests/integration/test_video_pipeline.py` (5, real ffmpeg and ASR on a generated clip; skipped when the extra is absent) |
| `ruff check`, `ruff format --check` | clean (726 files) |
| `mypy` (strict) | no issues (469 files) |
| Live stack after all work | `/md/status` health GOOD, all four children alive |

## Gate matrix

| # | Gate | State | Note |
|---|---|---|---|
| 1 | Repository inspected | PASS | `REPOSITORY_BASELINE.md` |
| 2 | Architecture selected with rationale | PASS | `VIDEO_INTELLIGENCE_ARCHITECTURE.md` |
| 3 | YouTube URL processed | **NOT TESTED** | no YouTube URL supplied; code path unit-tested with a fake extractor only |
| 4 | Facebook URL with legitimate access + fallback | PASS (access) / PARTIAL (fallback) | public Reel downloaded without login; the AUTH_REQUIRED fallback was simulated, not seen on a real private video |
| 5 | Local video processed | PASS | integration tests; CLI accepts a file |
| 6 | Transcript with real timestamps | **PARTIAL** | ASR ran and timestamps are produced by the code, but the only real video has no speech, so no timestamped text exists. Not demonstrated on speech. |
| 7 | Frames extracted and interpreted | PASS | 15 keyframes; frames read at 12.0 s and by contact sheet |
| 8 | Diagrams converted to structured rules | PASS | Wolfe Wave concept in `knowledge/d34e96f7f2e6.json` |
| 9 | One pattern implemented | PASS | `structure/wolfe.py` |
| 10 | Deterministic detector tests | PASS | positive, mirror, negatives, no-look-ahead, spread, filters |
| 11 | Historical validation | **BLOCKED** | protected data and closed research programme; only a synthetic frequency measurement exists |
| 12 | Skill/MCP callable from Claude Code | **PARTIAL** | the CLI was run from Claude Code and works; the skill file exists but was not invoked as a registered skill in this session (it loads at session start); no MCP server was built |
| 13 | Existing regression tests pass | PASS | 2690 |
| 14 | Browser E2E | **NOT APPLICABLE** | no frontend file was changed; dashboard E2E was not re-run for this work. No claim of a browser test is made. |
| 15 | Red Team: no unresolved critical issue | PASS with limits | see below |

## Red Team

Tested and holding: instruction text inside a transcript stays inert data; the package has no order, MetaTrader5, broker or secret access; credential flags are refused; unsupported schemes and hosts refused; silence gives an empty transcript, not invented text; failed extraction never reports MEDIA_READY; bullish and bearish are exact mirrors; candidates never use later bars.

Findings:

1. **Pattern frequency is high by chance.** On seeded random walks the default detector fires about 46 times per 10,000 bars (20 seeds: min 30, max 60); 36 with a minimum R:R of 2. A geometric match is therefore weak evidence by itself; this is synthetic data, not XAUUSD, and says nothing about profitability either way.
2. **The video is hindsight.** One curated example, no losing cases, no instrument or timeframe, annotations drawn after the move. Recorded as UNVERIFIED.
3. Entry trigger is a contested convention; only one mode is implemented.

Not tested: misreading of real candlesticks by an automated vision step (frame reading was manual by the agent, with an `uncertain` flag), cost modelling beyond a fixed spread, parameter and timeframe sensitivity on real data.

## Incident (environment)

Running `uv sync --extra ml --extra api --extra video` (without `--extra mt5`) tried to remove MetaTrader5 from the live `.venv`. Windows blocked the locked `.pyd`, but `MetaTrader5/__init__.py` was already deleted. The running collector kept its loaded module and stayed healthy. Repaired by installing the same version into a temp directory and copying only the missing `__init__.py` (the `.pyd` was byte-identical), then `uv sync --locked ... --extra mt5 --extra video`; import and `/md/status` verified. A restart of the collector before the repair would have failed to import MetaTrader5. Rule recorded: always include `--extra mt5` and dry-run first.

## Remaining limitations

* One video, 16.7 s, no speech, instrument unknown. Everything about the Wolfe Wave's usefulness is UNVERIFIED.
* ASR quality on real speech (Vietnamese, English) is untested here.
* Windows host, not the Mac M1 the brief assumed.
* The 11-tool MCP interface from the brief is not built.
