"""Failure modes of the video pipeline, driven through the real CLI with real ffmpeg.

Every case here is a defect found (or a risk named) in the field; a fixed bug has a regression test.
Skipped when the optional 'video' extra or ffmpeg is absent.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from xau_edge.video_intel import media, store
from xau_edge.video_intel.knowledge import (
    Claim,
    EvidenceStatus,
    VideoKnowledge,
    VideoRecord,
)
from xau_edge.video_intel.source import classify_source
from xau_edge.video_intel.status import ErrorCode, SourceStatus

pytest.importorskip("PIL", reason="extra 'video' not installed")
FFMPEG = media.find_ffmpeg()
pytestmark = [pytest.mark.integration, pytest.mark.skipif(FFMPEG is None, reason="no ffmpeg")]
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "video_intel.py"


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    monkeypatch.chdir(tmp_path)  # store and work folders are relative to the working directory
    spec = importlib.util.spec_from_file_location("video_intel_cli_it", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ffmpeg(*args: str) -> None:
    assert FFMPEG is not None
    done = subprocess.run(  # noqa: S603
        [FFMPEG, "-v", "error", "-y", *args], capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        pytest.skip(f"ffmpeg cannot build the test clip here: {done.stderr[-200:]}")


def _clip(path: Path, *, seconds: float = 3.0, audio: bool = True, color: str = "red") -> Path:
    args = ["-f", "lavfi", "-i", f"color=c={color}:s=160x120:d={seconds}:r=10"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:a", "aac"]
    _ffmpeg(*args, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-shortest", str(path))
    return path


def _run(
    cli: ModuleType, *argv: str, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    code = cli.main(list(argv))
    out = capsys.readouterr().out
    return code, json.loads(out)


def test_no_audio_stream_is_recorded_not_a_failure(
    cli: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clip = _clip(tmp_path / "silent.mp4", audio=False)
    code, out = _run(cli, "ingest", str(clip), capsys=capsys)
    assert code == 0
    assert out["steps"]["asr"] == {"skipped": True, "reason": "NO_AUDIO_STREAM"}  # type: ignore[index]
    assert store.load(str(out["video_id"])).transcript_note == "NO_AUDIO_STREAM"


def test_very_short_video_still_gets_a_first_frame(
    cli: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clip = _clip(tmp_path / "tiny.mp4", seconds=0.3, audio=False)
    code, out = _run(cli, "ingest", str(clip), "--no-asr", capsys=capsys)
    frames = out["steps"]["keyframes"]["frames"]  # type: ignore[index]
    assert code == 0 and frames and frames[0]["reason"] == "first"


def test_over_long_video_is_refused_with_a_code(
    cli: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clip = _clip(tmp_path / "long.mp4", seconds=4.0, audio=False)
    code, out = _run(cli, "ingest", str(clip), "--no-asr", "--max-duration", "2", capsys=capsys)
    assert code == 1
    assert out["steps"]["limit"]["code"] == ErrorCode.TOO_LONG.value  # type: ignore[index]
    assert store.list_ids() == []  # nothing recorded for a refused video


def test_broken_and_truncated_media_never_become_media_ready(
    cli: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"this is not a video" * 50)
    code, out = _run(cli, "ingest", str(broken), "--no-asr", capsys=capsys)
    assert code == 1 and out["steps"]["probe"]["code"] == ErrorCode.PROBE_FAILED.value  # type: ignore[index]
    good = _clip(tmp_path / "good.mp4", seconds=2.0)
    partial = tmp_path / "partial.mp4"  # an interrupted download: the moov atom sits at the end
    partial.write_bytes(good.read_bytes()[: good.stat().st_size // 3])
    code, out = _run(cli, "ingest", str(partial), "--no-asr", capsys=capsys)
    assert code == 1 and "probe" in out["steps"]  # type: ignore[operator]
    assert store.list_ids() == []


def test_same_media_under_two_names_is_one_record_with_an_alias(
    cli: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = _clip(tmp_path / "a.mp4", audio=False)
    second = tmp_path / "b.mp4"
    second.write_bytes(first.read_bytes())
    _, one = _run(cli, "ingest", str(first), "--no-asr", capsys=capsys)
    code, two = _run(cli, "ingest", str(second), "--no-asr", capsys=capsys)
    assert code == 0 and two["duplicate_of"] == one["video_id"]
    assert store.list_ids() == [one["video_id"]]
    assert str(second) in store.load(str(one["video_id"])).video.source_aliases


def test_reingest_refreshes_media_but_keeps_annotations(
    cli: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clip = _clip(tmp_path / "c.mp4", audio=False)
    _, out = _run(cli, "ingest", str(clip), "--no-asr", capsys=capsys)
    vid = str(out["video_id"])
    knowledge = store.load(vid)
    claim = Claim(
        claim_id="c1", video_id=vid, evidence_refs=["frame@0ms"], assertion="kept",
        status=EvidenceStatus.OBSERVED, verification="test",
    )  # fmt: skip
    store.save(knowledge.model_copy(update={"claims": [claim]}))
    code, again = _run(cli, "ingest", str(clip), "--no-asr", capsys=capsys)
    assert code == 0 and again["kept_annotations"] is True
    assert [c.claim_id for c in store.load(vid).claims] == ["c1"]


def test_annotate_twice_does_not_duplicate(
    cli: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clip = _clip(tmp_path / "d.mp4", audio=False)
    _, out = _run(cli, "ingest", str(clip), "--no-asr", capsys=capsys)
    vid = str(out["video_id"])
    note = tmp_path / "n.json"
    claim = {"claim_id": "c1", "video_id": vid, "evidence_refs": [], "assertion": "x"}
    claim |= {"status": "OBSERVED", "verification": "t"}
    note.write_text(json.dumps({"claims": [claim]}))
    for _ in range(2):
        assert cli.main(["annotate", vid, str(note)]) == 0
        capsys.readouterr()
    assert len(store.load(vid).claims) == 1


def test_progressive_drawing_is_caught_even_when_each_step_is_tiny(
    cli: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    boxes = ",".join(
        f"drawbox=x={10 + 18 * i}:y=40:w=12:h=12:color=white:t=fill:enable='gte(t,{i + 1})'"
        for i in range(8)
    )
    clip = tmp_path / "draw.mp4"
    _ffmpeg(
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s=160x120:d=10:r=10,{boxes}",
        "-pix_fmt",
        "yuv420p",
        str(clip),
    )
    code, out = _run(cli, "ingest", str(clip), "--no-asr", capsys=capsys)
    frames = out["steps"]["keyframes"]["frames"]  # type: ignore[index]
    assert code == 0
    assert sum(1 for f in frames if f["reason"] == "scene_change") >= 2  # tiny steps accumulate


def test_emoji_title_survives_a_legacy_windows_console(tmp_path: Path) -> None:
    video = VideoRecord(
        id="emoji1", source_url="https://youtu.be/x", source_platform="youtube",
        title="Wolf 🐺 Wave 📈",
        access_status=SourceStatus.MEDIA_READY, access_code="OK", processing_status="done",
        processed_at="2026-10-11T00:00:00Z", provenance="test",
    )  # fmt: skip
    store.save(VideoKnowledge(video=video), tmp_path / "data" / "video_knowledge")
    env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
    done = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), "show", "emoji1"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")[-300:]
    assert "\U0001f43a" in done.stdout.decode("utf-8")


@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com.evil.example/watch?v=x",  # host suffix spoof
        "https://evil.example/?u=https://www.youtube.com/watch?v=x",  # host only in a parameter
        "https://www.youtube.com@evil.example/watch",  # userinfo trick
        "javascript:alert(1)",
        "ftp://www.youtube.com/x.mp4",
    ],
)
def test_spoofed_hosts_and_schemes_are_refused(url: str) -> None:
    ref, check = classify_source(url)
    assert ref is None and check.status is SourceStatus.SOURCE_UNAVAILABLE


def test_the_record_keeps_its_provenance_fields(
    cli: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clip = _clip(tmp_path / "prov.mp4", audio=False)
    _, out = _run(cli, "ingest", str(clip), "--no-asr", capsys=capsys)
    video = store.load(str(out["video_id"])).video
    frames = out["steps"]["keyframes"]["frames"]  # type: ignore[index]
    assert video.keyframe_count == len(frames) >= 1
    assert video.file_sha256 and len(video.file_sha256) == 64
    assert video.asr_model is None  # ASR did not run, so no model is claimed
    assert video.platform_id is None and video.resolved_url is None  # a local file has neither
    assert video.provenance == "local file"
