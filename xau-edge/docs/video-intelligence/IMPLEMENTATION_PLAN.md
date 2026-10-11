# Implementation plan and state

## Done (tested)

| Item | Where |
|---|---|
| Source validation, status model, failure classification, credential ban | `video_intel/source.py`, `status.py`, `ingest.py` |
| Download, probe, adaptive keyframes, audio, ASR | `ingest.py`, `media.py`, `transcribe.py` |
| Knowledge schema and store, concept query | `knowledge.py`, `store.py` |
| CLI and skill | `scripts/video_intel.py`, `.claude/skills/video-intel/SKILL.md` |
| Wolfe Wave detector (bullish and bearish), non-repainting, configurable | `structure/wolfe.py` |
| First video recorded with evidence | `knowledge/d34e96f7f2e6.json` |

## Planned, not built

1. Entry-trigger mode "break of the 1-3 line" for Wolfe (sources disagree; only "at P5 confirmation" exists).
2. `PARTIAL_INPUT_ONLY` CLI path (transcript, audio or screenshots only).
3. MCP server wrapper around the CLI (the 11 tools in the brief are covered by 5 CLI commands plus the agent's own frame reading; a wrapper is mechanical).
4. More detectors from the video family (diamond, flags, double bottom, triangles, cup and handle). Each needs its own precise rule and synthetic tests; none was built from thumbnails alone.
5. OCR for unattended batch use.

## Blocked

Historical precision, recall and out-of-sample behaviour on XAUUSD: the closed research programme forbids new edge research and protects Test-H and Holdout. Unprotected development data could support a descriptive frequency study only after an explicit owner decision and a pre-registered protocol. No performance number exists or is implied.

## Rules for any future detector

Precise rule first; contested definitions as flags; synthetic positive and negative tests; prefix-equality (no look-ahead) test; spread-aware R:R; random-walk false-positive rate reported; never wired into the engine without an ADR and the evidence gates.
