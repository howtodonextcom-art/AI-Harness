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

from xau_edge.video_intel import ingest, media, store, transcribe
from xau_edge.video_intel.knowledge import (
    Claim,
    ImplementationLink,
    TradingConcept,
    VideoKnowledge,
    VideoRecord,
    VisualEvidence,
    explain_concept,
)
from xau_edge.video_intel.source import Platform, classify_source
from xau_edge.video_intel.status import ErrorCode, SourceCheck, SourceStatus

WORK = Path("data") / "video_work"


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


def cmd_ingest(args: argparse.Namespace) -> int:
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
        dl_check, video_path = ingest.download(ref, folder, ffmpeg=ffmpeg)
        steps["download"] = _check_dict(dl_check)
        provenance = "yt-dlp, no cookies, no credentials"
        if video_path is None:
            return _emit({"video_id": video_id, "steps": steps}, ok=False)
    pcheck, info = media.probe(video_path, ffmpeg)
    steps["probe"] = _check_dict(pcheck)
    if info is None or ffmpeg is None:
        return _emit({"video_id": video_id, "steps": steps}, ok=False)
    fcheck, frames = media.extract_keyframes(
        video_path, folder / "frames", ffmpeg, sample_fps=args.sample_fps
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
            tcheck, segments, note = transcribe.transcribe_wav(wav, video_id)
            steps["asr"] = {"check": _check_dict(tcheck), "segments": len(segments), "note": note}
        else:
            steps["asr"] = {"check": _check_dict(acheck)}
    knowledge = VideoKnowledge(
        video=VideoRecord(
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
            file_sha256=media.sha256_file(video_path),
            processed_at=datetime.now(UTC).isoformat(timespec="seconds"),
            provenance=provenance,
        ),
        transcript=segments,
        transcript_note=note,
    )
    saved = store.save(knowledge)
    return _emit(
        {
            "video_id": video_id,
            "knowledge": str(saved),
            "frames_dir": str(folder / "frames"),
            "steps": steps,
        },
        ok=True,
    )


def cmd_annotate(args: argparse.Namespace) -> int:
    knowledge = store.load(args.video_id)
    try:
        payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
        visual = [VisualEvidence.model_validate(v) for v in payload.get("visual", [])]
        claims = [Claim.model_validate(c) for c in payload.get("claims", [])]
        concepts = [TradingConcept.model_validate(c) for c in payload.get("concepts", [])]
        links = [ImplementationLink.model_validate(x) for x in payload.get("links", [])]
    except (ValidationError, ValueError, OSError) as exc:
        return _emit({"error": "INVALID_ANNOTATIONS", "detail": str(exc)[:800]}, ok=False)
    merged = knowledge.model_copy(
        update={
            "visual": knowledge.visual + visual,
            "claims": knowledge.claims + claims,
            "concepts": knowledge.concepts + concepts,
            "links": knowledge.links + links,
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
            },
        },
        ok=True,
    )


def cmd_show(args: argparse.Namespace) -> int:
    return _emit(json.loads(store.load(args.video_id).model_dump_json()), ok=True)


def cmd_ask(args: argparse.Namespace) -> int:
    print(explain_concept(store.load(args.video_id), " ".join(args.concept)))
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
    p.add_argument("concept", nargs="+")
    p.set_defaults(fn=cmd_ask)
    args = parser.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
