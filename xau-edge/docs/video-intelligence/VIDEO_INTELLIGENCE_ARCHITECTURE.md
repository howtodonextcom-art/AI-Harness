# Video Intelligence: architecture (as implemented)

Status date: 2026-10-11. Everything below marked IMPLEMENTED exists in the repository and is tested; PLANNED items are not built.

## Placement

`src/xau_edge/video_intel/` is a self-contained package with no import of `trading/`, `execution/`, `brokers/`, `api/` or the dashboard. It cannot place an order, change a decision or touch the live stack. The only trading-side artefact is a research detector, `src/xau_edge/structure/wolfe.py`, which reuses `structure/swings.py` and is not called by any engine.

Chosen over two alternatives:

| Option | Why not |
|---|---|
| New MCP server | More moving parts; the agent already runs shell commands. The CLI emits JSON, so wrapping it later is mechanical. PLANNED. |
| Hook into Trading Core / dashboard | Violates the freeze and the closed research programme; no requirement justifies it. |
| **Isolated package + CLI + skill (chosen)** | Smallest blast radius, reversible, testable without network. |

## Pipeline (IMPLEMENTED unless noted)

```
source -> classify (https only, host allow-list) -> inspect (metadata only)
       -> download (yt-dlp, no cookies/credentials, 200 MB cap) -> probe (ffmpeg)
       -> keyframes (2 fps sample, keep frames that differ from the last kept frame, + first/last)
       -> audio (16 kHz mono) -> ASR (faster-whisper base, CPU int8, VAD)
       -> knowledge.json (video, transcript, visual, claims, concepts, links)
```

Frame interpretation is done by the agent reading the kept frames (the CLI does not call a vision API, so there is no recurring cost). OCR (EasyOCR) was deliberately not added: it is a heavy dependency and the agent reads on-screen text directly from the frames. PLANNED if unattended batch use appears.

## Status model

`SourceStatus`: ACCESSIBLE, AUTH_REQUIRED, RESTRICTED, EXTRACTION_FAILED, SOURCE_UNAVAILABLE, MEDIA_READY, PARTIAL_INPUT_ONLY. Every step returns a `SourceCheck(status, code, message, detail)`; codes include LOGIN_REQUIRED, RESTRICTED_CONTENT, NOT_FOUND, NETWORK, EXTRACTOR_MISSING, FFMPEG_MISSING, PROBE_FAILED, ASR_UNAVAILABLE. A download counts as MEDIA_READY only if a non-empty file exists. `PARTIAL_INPUT_ONLY` exists in the enum; a CLI path for transcript/screenshot-only input is PLANNED.

## Safety properties (each has a test)

* Credential flags (`--cookies`, `--cookies-from-browser`, `--username`, `--password`, `--netrc`) are refused in code.
* Non-https, unknown hosts and non-media files are refused before any network call.
* Silence yields an empty transcript plus `NO_SPEECH_DETECTED`; text is never synthesised.
* Transcript, caption and OCR text are stored as data and never interpreted.
* The package source contains no order, MetaTrader5, broker or `.env` access (a test greps for it).

## Dependencies (extra `video`, optional)

yt-dlp (Unlicense), faster-whisper (MIT, pulls ctranslate2, onnxruntime, av), imageio-ffmpeg (bundles an ffmpeg binary), Pillow. CI does not install the extra: integration tests skip, mypy ignores the missing stubs. Used from the brief's list: yt-dlp, faster-whisper (instead of whisper.cpp, which needs a native build on Windows), ffmpeg via imageio-ffmpeg. Not used: PySceneDetect (accumulated pixel change was enough and is tested), EasyOCR, browser-use and Playwright MCP (no logged-in browsing is needed, and logging in is out of scope). **Not evaluated in this session:** khou/watch-video and stevederico/video-understanding; their licences and code were not reviewed, nothing was copied from them, and no claim is made about them.

Host note: the prompt assumed a Mac M1; this machine is Windows 11 x64 (CPU int8 ASR, about 8 s for a 17 s clip including model load).

## Cost

All local. No paid API. Model download (faster-whisper base, about 140 MB) happens once.
