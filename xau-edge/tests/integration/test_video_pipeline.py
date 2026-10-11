"""Real ffmpeg pipeline on a synthetic clip. Skipped when the optional 'video' extra is absent."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pytest

from xau_edge.video_intel import media, transcribe
from xau_edge.video_intel.status import SourceStatus

FFMPEG = media.find_ffmpeg()
pytest.importorskip("PIL", reason="extra 'video' not installed")
pytestmark = [pytest.mark.integration, pytest.mark.skipif(FFMPEG is None, reason="no ffmpeg")]


@pytest.fixture(scope="module")
def clip(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """4 s: 2 s of one colour, then 2 s of another (one scene change), 440 Hz tone as audio."""
    path = tmp_path_factory.mktemp("clip") / "c.mp4"
    assert FFMPEG is not None
    cmd = [
        FFMPEG, "-v", "error", "-y",
        "-f", "lavfi", "-i", "color=c=red:s=320x240:d=2:r=10",
        "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=2:r=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
        "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(path),
    ]  # fmt: skip
    done = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
    if done.returncode != 0:
        pytest.skip(f"ffmpeg cannot build the test clip here: {done.stderr[-200:]}")
    return path


def test_probe_reads_the_real_clip(clip: Path) -> None:
    check, info = media.probe(clip, FFMPEG)
    assert check.status is SourceStatus.MEDIA_READY and info is not None
    assert (info.width, info.height, info.has_audio) == (320, 240, True)
    assert info.duration_s == pytest.approx(4.0, abs=0.2)


def test_keyframes_keep_first_scene_change_and_last_only(clip: Path, tmp_path: Path) -> None:
    assert FFMPEG is not None
    check, frames = media.extract_keyframes(clip, tmp_path, FFMPEG, sample_fps=2.0, threshold=20.0)
    assert check.status is SourceStatus.MEDIA_READY
    reasons = [f.reason for f in frames]
    assert reasons[0] == "first" and "scene_change" in reasons and reasons[-1] == "last"
    assert len(frames) < 8  # 8 sampled; duplicates removed
    change = next(f for f in frames if f.reason == "scene_change")
    assert 1500 <= change.timestamp_ms <= 2500  # the colour switch is at 2 s
    assert sorted(p.name for p in tmp_path.glob("cand_*.png")) == sorted(f.path for f in frames)


def test_audio_extraction_yields_16k_mono_wav(clip: Path, tmp_path: Path) -> None:
    assert FFMPEG is not None
    wav = tmp_path / "a.wav"
    assert media.extract_audio(clip, wav, FFMPEG).status is SourceStatus.MEDIA_READY
    audio = transcribe.read_wav_mono16k(wav)
    assert audio.size == pytest.approx(4 * 16000, rel=0.05) and float(np.abs(audio).max()) > 0.1


def test_asr_on_a_pure_tone_returns_no_invented_text(clip: Path, tmp_path: Path) -> None:
    if not transcribe.asr_available():
        pytest.skip("faster-whisper not installed")
    assert FFMPEG is not None
    wav = tmp_path / "a.wav"
    media.extract_audio(clip, wav, FFMPEG)
    _check, segments, note = transcribe.transcribe_wav(wav, "vid")
    assert segments == [] and note.startswith("NO_SPEECH_DETECTED")


def test_audio_extraction_fails_clearly_for_a_non_media_file(tmp_path: Path) -> None:
    assert FFMPEG is not None
    bad = tmp_path / "x.mp4"
    bad.write_bytes(b"not a video")
    result = media.extract_audio(bad, tmp_path / "o.wav", FFMPEG)
    assert result.status is SourceStatus.EXTRACTION_FAILED
