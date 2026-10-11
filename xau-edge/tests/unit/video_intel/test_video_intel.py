"""Video intelligence: source validation, failure classification, credentials ban, media, schema."""

from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np
import pytest

from xau_edge.video_intel import ingest, media, store, transcribe
from xau_edge.video_intel.knowledge import (
    Claim,
    EvidenceStatus,
    ImplementationLink,
    TradingConcept,
    VideoKnowledge,
    VideoRecord,
    explain_concept,
)
from xau_edge.video_intel.source import Platform, classify_source
from xau_edge.video_intel.status import ErrorCode, SourceStatus

pytestmark = pytest.mark.unit

FB = "https://www.facebook.com/share/r/18kMRKXFsk/?mibextid=wwXIfr"


@pytest.mark.parametrize(
    ("value", "platform"),
    [
        (FB, Platform.FACEBOOK),
        ("https://youtu.be/abc", Platform.YOUTUBE),
        ("https://www.youtube.com/watch?v=abc", Platform.YOUTUBE),
        ("https://cdn.example.com/clip.mp4", Platform.DIRECT),
        ("clips/lesson.mov", Platform.LOCAL),
    ],
)
def test_supported_sources_are_classified(value: str, platform: Platform) -> None:
    ref, check = classify_source(value)
    assert ref is not None and ref.platform is platform
    assert check.status is SourceStatus.ACCESSIBLE


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("", ErrorCode.BAD_URL),
        ("http://www.youtube.com/watch?v=abc", ErrorCode.UNSUPPORTED_SCHEME),
        ("file:///etc/passwd", ErrorCode.UNSUPPORTED_SCHEME),
        ("https://evil.example.com/page", ErrorCode.UNSUPPORTED_HOST),
        ("https://evil.example.com/redirect?u=https://youtube.com/x", ErrorCode.UNSUPPORTED_HOST),
        ("notes.txt", ErrorCode.UNSUPPORTED_HOST),
    ],
)
def test_unsafe_or_unsupported_sources_are_refused(value: str, code: ErrorCode) -> None:
    ref, check = classify_source(value)
    assert ref is None
    assert check.code is code
    assert check.status is SourceStatus.SOURCE_UNAVAILABLE


@pytest.mark.parametrize(
    ("stderr", "status", "code"),
    [
        (
            "ERROR: Login required to view this video",
            SourceStatus.AUTH_REQUIRED,
            ErrorCode.LOGIN_REQUIRED,
        ),
        ("This video is private", SourceStatus.AUTH_REQUIRED, ErrorCode.LOGIN_REQUIRED),
        (
            "not available in your country (geo restricted)",
            SourceStatus.RESTRICTED,
            ErrorCode.RESTRICTED_CONTENT,
        ),
        ("Read timed out", SourceStatus.SOURCE_UNAVAILABLE, ErrorCode.NETWORK),
        ("HTTP Error 404: Not Found", SourceStatus.SOURCE_UNAVAILABLE, ErrorCode.NOT_FOUND),
        ("something odd happened", SourceStatus.EXTRACTION_FAILED, ErrorCode.EXTRACTOR_ERROR),
    ],
)
def test_extractor_failures_map_to_explicit_statuses(
    stderr: str, status: SourceStatus, code: ErrorCode
) -> None:
    check = ingest.classify_failure(stderr)
    assert (check.status, check.code) == (status, code)
    assert check.message  # a person can read why


def test_missing_extractor_is_reported_not_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "extractor_argv", lambda: None)
    ref, _ = classify_source(FB)
    assert ref is not None
    check, meta = ingest.inspect_url(ref)
    assert check.code is ErrorCode.EXTRACTOR_MISSING and meta is None
    check, path = ingest.download(ref, Path("unused"), ffmpeg=None)
    assert check.code is ErrorCode.EXTRACTOR_MISSING and path is None


@pytest.mark.parametrize(
    "flag", ["--cookies", "--cookies-from-browser=chrome", "--password=x", "--netrc"]
)
def test_credential_flags_are_always_refused(flag: str) -> None:
    with pytest.raises(ValueError, match="credential"):
        ingest.assert_no_credentials(["yt-dlp", flag, "https://x"])


def test_inspect_never_sends_credentials_and_reads_metadata() -> None:
    seen: list[list[str]] = []

    def runner(argv: object) -> tuple[int, str, str]:
        seen.append(list(argv))  # type: ignore[call-overload]
        return 0, json.dumps({"title": "T", "uploader": "U", "duration": 16.7, "id": "1"}), ""

    ref, _ = classify_source(FB)
    assert ref is not None
    check, meta = ingest.inspect_url(ref, runner=runner, argv=["yt-dlp"])
    assert check.status is SourceStatus.ACCESSIBLE and meta is not None and meta["title"] == "T"
    assert "--skip-download" in seen[0]
    assert not any(a.startswith(("--cookies", "--username", "--password")) for a in seen[0])


def test_inspect_login_wall_is_auth_required_not_success() -> None:
    ref, _ = classify_source(FB)
    assert ref is not None
    check, meta = ingest.inspect_url(
        ref,
        runner=lambda _a: (1, "", "ERROR: [facebook] Cannot parse data; Login required"),
        argv=["y"],
    )
    assert check.status is SourceStatus.AUTH_REQUIRED and meta is None


def test_inspect_garbage_output_is_a_failure() -> None:
    ref, _ = classify_source(FB)
    assert ref is not None
    check, meta = ingest.inspect_url(ref, runner=lambda _a: (0, "<html>", ""), argv=["y"])
    assert check.status is SourceStatus.EXTRACTION_FAILED and meta is None


def test_download_requires_a_real_file_before_reporting_media_ready(tmp_path: Path) -> None:
    ref, _ = classify_source(FB)
    assert ref is not None
    empty, path = ingest.download(
        ref, tmp_path, ffmpeg=None, runner=lambda _a: (0, "", ""), argv=["y"]
    )
    assert path is None and empty.status is SourceStatus.EXTRACTION_FAILED  # exit 0 but no file

    def writes_file(_argv: object) -> tuple[int, str, str]:
        (tmp_path / "video.mp4").write_bytes(b"data")
        return 0, "", ""

    ok, path = ingest.download(ref, tmp_path, ffmpeg="ff", runner=writes_file, argv=["y"])
    assert ok.status is SourceStatus.MEDIA_READY and path == tmp_path / "video.mp4"


def test_download_failure_keeps_the_classified_status(tmp_path: Path) -> None:
    ref, _ = classify_source(FB)
    assert ref is not None
    check, path = ingest.download(
        ref, tmp_path, ffmpeg=None, runner=lambda _a: (1, "", "Login required"), argv=["y"]
    )
    assert path is None and check.status is SourceStatus.AUTH_REQUIRED


PROBE = """Input #0, mov,mp4, from 'x.mp4':
  Duration: 00:00:16.70, start: 0.000000, bitrate: 657 kb/s
  Stream #0:0(und): Video: av1 (libaom-av1) (Main) (av01 / 0x31307661), yuv420p, 1088x1936, 30 fps
  Stream #0:1(und): Audio: aac (HE-AAC), 44100 Hz, stereo, fltp
"""


def test_probe_parser_reads_duration_size_and_audio() -> None:
    info = media.parse_probe(PROBE)
    assert info is not None
    assert (info.duration_s, info.width, info.height, info.has_audio) == (16.7, 1088, 1936, True)
    assert media.parse_probe("garbage") is None
    assert media.parse_probe(PROBE.replace("Audio:", "Data:")).has_audio is False  # type: ignore[union-attr]


def test_probe_reports_missing_file_ffmpeg_and_unreadable(tmp_path: Path) -> None:
    missing, info = media.probe(tmp_path / "none.mp4", "ffmpeg")
    assert missing.code is ErrorCode.FILE_NOT_FOUND and info is None
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"x")
    assert media.probe(clip, None)[0].code is ErrorCode.FFMPEG_MISSING
    assert (
        media.probe(clip, "ff", runner=lambda _a: (1, "", "nope"))[0].code is ErrorCode.PROBE_FAILED
    )
    ok, info = media.probe(clip, "ff", runner=lambda _a: (1, "", PROBE))
    assert ok.status is SourceStatus.MEDIA_READY and info is not None and info.width == 1088


def _flat(value: float) -> np.ndarray:  # type: ignore[type-arg,unused-ignore]
    return np.full((4, 4), value)


def test_keyframe_selection_keeps_first_changes_and_last_and_drops_duplicates() -> None:
    frames = [_flat(v) for v in (0, 0.1, 0.1, 9, 9.2, 9, 20, 20.1)]
    picked = media.select_keyframes(frames, threshold=3.0)
    assert [(i, reason) for i, reason, _ in picked] == [
        (0, "first"), (3, "scene_change"), (6, "scene_change"), (7, "last"),
    ]  # fmt: skip
    assert media.select_keyframes([], threshold=3.0) == []
    assert media.select_keyframes([_flat(0)], threshold=3.0) == [(0, "first", 0.0)]
    two = media.select_keyframes([_flat(0), _flat(0)], threshold=3.0, always_last=False)
    assert [i for i, _, _ in two] == [0]


def test_gradual_drawing_is_caught_by_accumulated_change() -> None:
    """A chart drawn line by line changes ~1 per step: consecutive diffs never reach 3."""
    frames = [_flat(float(v)) for v in range(0, 10)]
    assert max(abs(float(frames[i][0, 0] - frames[i - 1][0, 0])) for i in range(1, 10)) < 3
    kept = [i for i, reason, _ in media.select_keyframes(frames, threshold=3.0) if reason != "last"]
    assert kept == [0, 3, 6, 9]


def test_sha256_is_stable(tmp_path: Path) -> None:
    f = tmp_path / "a.bin"
    f.write_bytes(b"abc")
    assert media.sha256_file(f).startswith("ba7816bf")


def test_wav_reader_and_silence_means_empty_transcript_not_invented_text(tmp_path: Path) -> None:
    wav = tmp_path / "a.wav"
    with wave.open(str(wav), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes((np.zeros(16000, dtype=np.int16)).tobytes())
    audio = transcribe.read_wav_mono16k(wav)
    assert audio.shape == (16000,) and float(abs(audio).max()) == 0.0
    stereo = tmp_path / "s.wav"
    with wave.open(str(stereo), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * 4)
    with pytest.raises(ValueError, match="16 kHz mono"):
        transcribe.read_wav_mono16k(stereo)
    assert "Nothing was transcribed" in transcribe.NO_SPEECH_NOTE


def _knowledge() -> VideoKnowledge:
    video = VideoRecord(
        id="v1", source_url=FB, source_platform="facebook", access_status=SourceStatus.MEDIA_READY,
        access_code="OK", processing_status="done", processed_at="2026-10-11T00:00:00Z",
        provenance="yt-dlp, no cookies",
    )  # fmt: skip
    concept = TradingConcept(
        concept_id="wolfe", name="Wolfe Wave", alt_names=["Wolf Wave"], video_id="v1",
        source_evidence=["frame@8000ms"], plain_language="five-point wedge", rules={"r": "x"},
        invalidation=["p5 inside wedge"], entry="close at P5 confirmation", stop_loss="P5",
        target="P1-P4 line", repaint_risk="none after confirmation", failure_modes=["fakeout"],
    )  # fmt: skip
    claim = Claim(
        claim_id="c1", video_id="v1", evidence_refs=["frame@8000ms"],
        assertion="price reaches the target", status=EvidenceStatus.UNVERIFIED,
        verification="single curated example; no statistics",
    )  # fmt: skip
    link = ImplementationLink(
        concept_id="wolfe", requirement_id="REQ-1", source_file="src/xau_edge/structure/wolfe.py",
        test_file="tests/unit/structure/test_wolfe.py", implementation_status="IMPLEMENTED",
    )  # fmt: skip
    return VideoKnowledge(video=video, concepts=[concept], claims=[claim], links=[link])


def test_store_round_trip_and_ids(tmp_path: Path) -> None:
    knowledge = _knowledge()
    path = store.save(knowledge, tmp_path)
    assert path.is_file() and not list(tmp_path.rglob("*.tmp"))
    assert store.load("v1", tmp_path) == knowledge
    assert store.list_ids(tmp_path) == ["v1"] and store.list_ids(tmp_path / "none") == []
    assert (
        store.video_id_for(" " + FB) == store.video_id_for(FB) and len(store.video_id_for(FB)) == 12
    )


def test_concept_query_answers_with_evidence_and_code_links() -> None:
    answer = explain_concept(_knowledge(), "wolf wave")  # alternative name, any case
    assert "Wolfe Wave" in answer and "frame@8000ms" in answer
    assert "[UNVERIFIED]" in answer and "src/xau_edge/structure/wolfe.py" in answer
    assert "No concept named" in explain_concept(_knowledge(), "diamond")
