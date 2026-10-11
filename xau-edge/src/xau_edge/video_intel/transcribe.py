"""Speech to text. Never invents text: no speech means an empty transcript and an explicit note."""

from __future__ import annotations

import importlib.util
import wave
from pathlib import Path

import numpy as np

from xau_edge.video_intel.knowledge import TranscriptSegment
from xau_edge.video_intel.status import ErrorCode, SourceCheck, SourceStatus

NO_SPEECH_NOTE = (
    "NO_SPEECH_DETECTED: ASR returned no speech segments (music or silence). "
    "Nothing was transcribed."
)


def read_wav_mono16k(path: Path) -> np.ndarray:  # type: ignore[type-arg,unused-ignore]
    """Read a 16 kHz mono PCM16 WAV as float32 in [-1, 1] (avoids the container decoder)."""
    with wave.open(str(path)) as handle:
        if handle.getframerate() != 16000 or handle.getnchannels() != 1:
            raise ValueError("expected 16 kHz mono WAV")
        raw = handle.readframes(handle.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def asr_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def transcribe_wav(
    wav: Path, video_id: str, *, model_size: str = "base", language: str | None = None
) -> tuple[SourceCheck, list[TranscriptSegment], str]:
    """Local faster-whisper (CPU int8). Returns (check, segments, note)."""
    if not asr_available():
        return (
            SourceCheck(
                status=SourceStatus.EXTRACTION_FAILED, code=ErrorCode.ASR_UNAVAILABLE,
                message="faster-whisper is not installed (extra 'video').",
            ),
            [],
            "ASR_UNAVAILABLE: no transcript produced.",
        )  # fmt: skip
    from faster_whisper import WhisperModel  # noqa: PLC0415 - optional dependency

    audio = read_wav_mono16k(wav)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    raw_segments, info = model.transcribe(audio, language=language, vad_filter=True)
    segments = [
        TranscriptSegment(
            video_id=video_id,
            start_ms=round(seg.start * 1000),
            end_ms=round(seg.end * 1000),
            text=seg.text.strip(),
            language=info.language,
            low_confidence=bool(seg.avg_logprob < -1.0 or seg.no_speech_prob > 0.6),
        )
        for seg in raw_segments
    ]
    check = SourceCheck(
        status=SourceStatus.MEDIA_READY, code=ErrorCode.OK, message="ASR completed."
    )
    return check, segments, ("" if segments else NO_SPEECH_NOTE)
