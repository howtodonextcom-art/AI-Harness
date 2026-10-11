# Repository baseline (inspected 2026-10-11, before the video work)

Inspected from the real tree, not assumed. Sources: `CLAUDE.md`, `pyproject.toml`, `src/xau_edge/**`, `.github/workflows/xau-edge-ci.yml`, `docs/reports/FINAL_PRODUCT_CLOSURE.md`, git state.

## Architecture

`xau-edge` is a PAPER-only XAUUSD decision desk on live MT5 (FTMO-Demo, read-only) data, plus a pre-registered edge research platform, plus a locked legacy demo bot. Python 3.12-3.14 (uv, Polars, pydantic, FastAPI, pytest, ruff, `mypy --strict`); Next.js 16 dashboard with Playwright. A supervisor runs collector, news refresher, API (:8000, hosts the trade engine) and dashboard (:3000). No path leads from a decision to an MT5 order; demo and funded adapters are disabled.

## Existing capabilities relevant to this work

| Area | Present |
|---|---|
| Swing structure, BOS/CHoCH, S/R | `structure/swings.py`, non-repainting (pivots confirmed `right` bars late) |
| Pattern similarity search | `patterns/` (matrix profile, DTW, z-norm); not rule-based chart patterns |
| Chart drawing tools (manual) | dashboard DrawingLayer |
| Backtesting, strategies, outcomes | `backtest/`, `strategies/`, `outcomes/`, `evaluation/` |
| Trading engine | `trading/` baseline v1.1.0, label UNVALIDATED_OPERATIONAL_BASELINE |
| Research governance | Edge Programs V1-V3, trial ledger K, Test-H and Holdout locked, procedural freeze guard |
| Browser E2E | Playwright mock suite (331) and real-backend acceptance (31) |
| Video, ASR, OCR, media | **none** (no ffmpeg, yt-dlp or whisper on the host either) |
| LLM integrations | none in the runtime |

## Gaps

No ingestion of external media; no rule-based classic chart-pattern detectors; no store linking an external idea to code and tests.

## Constraints that shaped the design

* Research is closed: NO VIABLE EDGE FOUND, new edge research NOT AUTHORIZED, Test-H and Holdout untouched. So: no tuning or scoring on protected data, no wiring into the engine.
* Freeze-LIVE rule: do not rebuild or restart the live stack while the market is open; this work touches only new files plus `pyproject.toml`/`uv.lock` (optional extra).
* Another session had uncommitted dashboard work (TerminalChart, SystemTradePlanOverlay); it was left untouched.

## Affected code

New: `src/xau_edge/video_intel/`, `src/xau_edge/structure/wolfe.py`, `scripts/video_intel.py`, `tests/unit/video_intel/`, `tests/unit/structure/test_wolfe.py`, `tests/integration/test_video_pipeline.py`, `.claude/skills/video-intel/`, `docs/video-intelligence/`. Modified: `pyproject.toml` (extra `video`, mypy overrides), `uv.lock`.

## Regression risks and validation

Risk: optional dependencies leaking into CI (mitigated: lazy imports, skip markers, mypy overrides); touching the live venv (an incident happened, see FINAL_QA_REPORT). Validation: full `pytest -m "not mt5"`, ruff, mypy strict, plus the new tests; dashboard E2E is unaffected because no frontend file changed.
