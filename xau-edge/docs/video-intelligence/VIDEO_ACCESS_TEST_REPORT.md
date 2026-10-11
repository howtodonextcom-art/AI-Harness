# Video access test report

Date: 2026-10-11. Host: Windows 11 x64, no cookies, no login, no browser profile. Tools: yt-dlp 2026.08.19, ffmpeg 7.1 (imageio-ffmpeg), faster-whisper 1.2.1 `base`.

## Source tested

`https://www.facebook.com/share/r/18kMRKXFsk/?mibextid=wwXIfr` (public Reel by "Zenix Arixon"). Video id (hash of URL): `d34e96f7f2e6`.

| Step | Result | Evidence |
|---|---|---|
| classify | ACCESSIBLE, platform facebook | `source.py` |
| inspect (metadata) | ACCESSIBLE, no login needed | title, uploader, 16.685 s |
| download | MEDIA_READY | 1.37 MB mp4; video AV1 1088x1936 30 fps, audio AAC 44.1 kHz |
| probe | MEDIA_READY | duration 16.70 s, has audio |
| keyframes | 15 of 33 sampled frames kept | dense at 11-15.5 s where the chart changes |
| ASR | completed, **0 segments** | rms 0.15 (not silent), VAD found no speech: `NO_SPEECH_DETECTED` |

Provenance recorded in the knowledge file: "yt-dlp, no cookies, no credentials", SHA-256 of the file.

## What was and was not watched

The media file was downloaded and its frames were viewed (the 1 fps contact sheet, then a full-resolution frame at 12.0 s and the adaptive keyframes). This is a real read of the pixels for a 16.7 s clip. The audio contains no detected speech, so there is **no transcript**; nothing was said by a presenter that this system could capture. The caption is metadata, stored as untrusted.

## Other modes

| Mode | State |
|---|---|
| A YouTube URL | Code path and classifier IMPLEMENTED and unit tested with a fake extractor. **Not run against a real YouTube URL** (none was supplied): NOT TESTED live. |
| B Facebook | PASS for this public Reel. Login-walled Reels would return AUTH_REQUIRED (tested with a simulated login error, not with a real private video). |
| C Local MP4/MOV | PASS (integration tests on a generated clip; CLI `ingest <file>`). |
| D Direct media URL | Classified; download path shares the same code; NOT TESTED live. |
| E Transcript/screenshots only | `PARTIAL_INPUT_ONLY` exists in the enum; no CLI path yet. PLANNED. |

## Defects found by this run (all fixed)

1. ASR failed with a `TypeError` from the `av` decoder; fixed by reading the WAV into a numpy array.
2. The CLI crashed on a title containing an emoji (Windows cp1252 stdout); fixed by forcing UTF-8.
3. The first sampler kept 2 of 33 frames because it compared with the previous frame and the chart is drawn line by line; fixed by comparing with the last kept frame (unit test with gradual drawing).
4. "This video is private" was not classified as AUTH_REQUIRED; found by a unit test, fixed.
5. `uv sync` without `--extra mt5` half-removed MetaTrader5 from the live venv; repaired and recorded (see FINAL_QA_REPORT).
