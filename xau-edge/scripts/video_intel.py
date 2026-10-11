"""Video intelligence CLI: the callable surface for the skill (see docs/video-intelligence).

Every command prints one JSON document on stdout; the exit code is 0 only when the requested step
reached a usable state. Nothing here can trade, and no credential or cookie is ever read or passed.

    uv run python scripts/video_intel.py inspect  <url|file>
    uv run python scripts/video_intel.py ingest   <url|file> [--no-asr] [--sample-fps 2]
    uv run python scripts/video_intel.py annotate <video_id> <annotations.json>
    uv run python scripts/video_intel.py show     <video_id>
    uv run python scripts/video_intel.py ask      <video_id> <concept name>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from xau_edge.video_intel import ask, ingest, media, store, transcribe
from xau_edge.video_intel.knowledge import (
    Claim,
    ExternalSource,
    ImplementationLink,
    Trace,
    TradingConcept,
    VideoKnowledge,
    VideoRecord,
    VisualEvidence,
)
from xau_edge.video_intel.source import Platform, classify_source
from xau_edge.video_intel.status import ErrorCode, SourceCheck, SourceStatus

WORK = Path("data") / "video_work"
ROOT = Path(__file__).resolve().parents[1]


def _emit(payload: dict[str, object], ok: bool) -> int:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0 if ok else 1


def _check_dict(check: SourceCheck) -> dict[str, object]:
    return check.model_dump(mode="json")


def cmd_inspect(args: argparse.Namespace) -> int:
    ref, check = classify_source(args.source)
    if ref is None:
        return _emit({"check": _check_dict(check)}, ok=False)
    if ref.platform is Platform.LOCAL:
        found = Path(ref.location).is_file()
        local = (
            check
            if found
            else SourceCheck(
                status=SourceStatus.SOURCE_UNAVAILABLE,
                code=ErrorCode.FILE_NOT_FOUND,
                message="Local file does not exist.",
            )
        )
        return _emit({"check": _check_dict(local), "platform": ref.platform.value}, ok=found)
    check, meta = ingest.inspect_url(ref)
    return _emit(
        {"check": _check_dict(check), "platform": ref.platform.value, "metadata": meta},
        ok=check.status is SourceStatus.ACCESSIBLE,
    )


def _too_long(duration_s: float | None, limit: float) -> SourceCheck | None:
    if duration_s is not None and duration_s > limit:
        return SourceCheck(
            status=SourceStatus.EXTRACTION_FAILED,
            code=ErrorCode.TOO_LONG,
            message=f"Video is {duration_s:.0f}s, over the {limit:.0f}s limit (use --max-duration).",
        )
    return None


def cmd_ingest(args: argparse.Namespace) -> int:  # noqa: PLR0911
    ref, check = classify_source(args.source)
    if ref is None:
        return _emit({"check": _check_dict(check)}, ok=False)
    video_id = store.video_id_for(ref.location)
    folder = WORK / video_id
    ffmpeg = media.find_ffmpeg()
    steps: dict[str, object] = {}
    meta: dict[str, object] | None = None
    provenance = "local file"
    if ref.platform is Platform.LOCAL:
        video_path: Path | None = Path(ref.location)
    else:
        info_check, meta = ingest.inspect_url(ref)
        steps["inspect"] = _check_dict(info_check)
        if info_check.status is not SourceStatus.ACCESSIBLE:
            return _emit({"video_id": video_id, "steps": steps}, ok=False)
        long_check = _too_long(meta.get("duration") if meta else None, args.max_duration)  # type: ignore[arg-type]
        if long_check is not None:
            steps["limit"] = _check_dict(long_check)
            return _emit({"video_id": video_id, "steps": steps}, ok=False)
        dl_check, video_path = ingest.download(ref, folder, ffmpeg=ffmpeg)
        steps["download"] = _check_dict(dl_check)
        provenance = "yt-dlp, no cookies, no credentials"
        if video_path is None:
            return _emit({"video_id": video_id, "steps": steps}, ok=False)
    pcheck, info = media.probe(video_path, ffmpeg)
    steps["probe"] = _check_dict(pcheck)
    if info is None or ffmpeg is None:
        return _emit({"video_id": video_id, "steps": steps}, ok=False)
    long_check = _too_long(info.duration_s, args.max_duration)
    if long_check is not None:
        steps["limit"] = _check_dict(long_check)
        return _emit({"video_id": video_id, "steps": steps}, ok=False)
    sha = media.sha256_file(video_path)
    twin = store.find_by_hash(sha)
    if twin is not None and twin != video_id:
        existing = store.load(twin)
        aliases = sorted(
            {*existing.video.source_aliases, ref.location} - {existing.video.source_url}
        )
        store.save(
            existing.model_copy(
                update={"video": existing.video.model_copy(update={"source_aliases": aliases})}
            )
        )
        steps["duplicate"] = {
            "code": ErrorCode.DUPLICATE_SOURCE.value,
            "message": f"Same media bytes as {twin}; recorded as an alias, nothing re-processed.",
        }
        return _emit({"video_id": twin, "duplicate_of": twin, "steps": steps}, ok=True)
    fcheck, frames = media.extract_keyframes(
        video_path,
        folder / "frames",
        ffmpeg,
        sample_fps=args.sample_fps,
        max_frames=args.max_frames,
        duration_s=info.duration_s,
    )
    steps["keyframes"] = {"check": _check_dict(fcheck), "frames": [f.model_dump() for f in frames]}
    segments, note = [], "ASR skipped (--no-asr)."
    if args.no_asr:
        steps["asr"] = {"skipped": True}
    elif not info.has_audio:
        note = "NO_AUDIO_STREAM"
        steps["asr"] = {"skipped": True, "reason": note}
    else:
        wav = folder / "audio.wav"
        acheck = media.extract_audio(video_path, wav, ffmpeg)
        if acheck.status is SourceStatus.MEDIA_READY:
            tcheck, segments, note = transcribe.transcribe_wav(
                wav, video_id, language=args.language
            )
            steps["asr"] = {"check": _check_dict(tcheck), "segments": len(segments), "note": note}
        else:
            steps["asr"] = {"check": _check_dict(acheck)}
    record = VideoRecord(
        id=video_id,
        source_url=ref.location,
        source_platform=ref.platform.value,
        title=(meta or {}).get("title") if meta else None,  # type: ignore[arg-type]
        author=(meta or {}).get("uploader") if meta else None,  # type: ignore[arg-type]
        access_status=SourceStatus.MEDIA_READY,
        access_code=ErrorCode.OK.value,
        processing_status="frames+asr" if not args.no_asr else "frames",
        duration_s=info.duration_s,
        width=info.width,
        height=info.height,
        has_audio=info.has_audio,
        file_sha256=sha,
        platform_id=str((meta or {}).get("id")) if meta and meta.get("id") else None,
        resolved_url=str((meta or {}).get("webpage_url"))
        if meta and meta.get("webpage_url")
        else None,
        keyframe_count=len(frames),
        asr_model="faster-whisper base (cpu int8)"
        if segments or note.startswith("NO_SPEECH")
        else None,
        processed_at=datetime.now(UTC).isoformat(timespec="seconds"),
        provenance=provenance,
    )
    try:
        previous = store.load(video_id)
    except (OSError, ValueError):
        previous = None
    # re-ingesting refreshes the media-derived parts; annotations a person or agent wrote are kept
    knowledge = (
        previous.model_copy(
            update={"video": record, "transcript": segments, "transcript_note": note}
        )
        if previous is not None
        else VideoKnowledge(video=record, transcript=segments, transcript_note=note)
    )
    saved = store.save(knowledge)
    return _emit(
        {
            "video_id": video_id,
            "knowledge": str(saved),
            "frames_dir": str(folder / "frames"),
            "kept_annotations": previous is not None,
            "steps": steps,
        },
        ok=True,
    )


def _upsert(existing: list, incoming: list, key: str) -> list:  # type: ignore[type-arg]
    """Replace items with the same id, append new ones: annotating twice never duplicates."""
    ids = {getattr(item, key) for item in incoming}
    return [item for item in existing if getattr(item, key) not in ids] + incoming


def cmd_annotate(args: argparse.Namespace) -> int:
    knowledge = store.load(args.video_id)
    try:
        payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
        visual = [VisualEvidence.model_validate(v) for v in payload.get("visual", [])]
        claims = [Claim.model_validate(c) for c in payload.get("claims", [])]
        concepts = [TradingConcept.model_validate(c) for c in payload.get("concepts", [])]
        links = [ImplementationLink.model_validate(x) for x in payload.get("links", [])]
        traces = [Trace.model_validate(x) for x in payload.get("traces", [])]
        sources = [ExternalSource.model_validate(x) for x in payload.get("external_sources", [])]
    except (ValidationError, ValueError, OSError) as exc:
        return _emit({"error": "INVALID_ANNOTATIONS", "detail": str(exc)[:800]}, ok=False)
    keyed = {(v.timestamp_ms, v.frame_reference) for v in visual}
    kept_visual = [v for v in knowledge.visual if (v.timestamp_ms, v.frame_reference) not in keyed]
    merged = knowledge.model_copy(
        update={
            "visual": kept_visual + visual,
            "claims": _upsert(knowledge.claims, claims, "claim_id"),
            "concepts": _upsert(knowledge.concepts, concepts, "concept_id"),
            "traces": _upsert(knowledge.traces, traces, "trace_id"),
            "external_sources": _upsert(knowledge.external_sources, sources, "source_id"),
            "links": [
                x
                for x in knowledge.links
                if (x.concept_id, x.requirement_id)
                not in {(n.concept_id, n.requirement_id) for n in links}
            ]
            + links,
        }
    )
    store.save(merged)
    return _emit(
        {
            "video_id": args.video_id,
            "added": {
                "visual": len(visual),
                "claims": len(claims),
                "concepts": len(concepts),
                "links": len(links),
                "traces": len(traces),
                "external_sources": len(sources),
            },
        },
        ok=True,
    )


def cmd_show(args: argparse.Namespace) -> int:
    return _emit(json.loads(store.load(args.video_id).model_dump_json()), ok=True)


def cmd_ask(args: argparse.Namespace) -> int:
    print(ask.answer(store.load(args.video_id), " ".join(args.question), ROOT))
    return 0


def cmd_ask_pattern(args: argparse.Namespace) -> int:
    records = [store.load(i) for i in store.list_ids()]
    print(ask.answer_pattern(" ".join(args.name), records))
    return 0


def cmd_ask_source(args: argparse.Namespace) -> int:
    print(ask.answer_source(store.load(args.video_id)))
    return 0


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]  # titles carry emoji
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, fn in (("inspect", cmd_inspect), ("ingest", cmd_ingest)):
        p = sub.add_parser(name)
        p.add_argument("source")
        if name == "ingest":
            p.add_argument("--no-asr", action="store_true")
            p.add_argument("--sample-fps", type=float, default=2.0)
            p.add_argument("--max-frames", type=int, default=60)
            p.add_argument("--max-duration", type=float, default=3600.0)
            p.add_argument("--language", default=None)
        p.set_defaults(fn=fn)
    p = sub.add_parser("annotate")
    p.add_argument("video_id")
    p.add_argument("file")
    p.set_defaults(fn=cmd_annotate)
    p = sub.add_parser("show")
    p.add_argument("video_id")
    p.set_defaults(fn=cmd_show)
    p = sub.add_parser("ask")
    p.add_argument("video_id")
    p.add_argument("question", nargs="+")
    p.set_defaults(fn=cmd_ask)
    p = sub.add_parser("ask-pattern")
    p.add_argument("name", nargs="+")
    p.set_defaults(fn=cmd_ask_pattern)
    p = sub.add_parser("ask-source")
    p.add_argument("video_id")
    p.set_defaults(fn=cmd_ask_source)
    args = parser.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
