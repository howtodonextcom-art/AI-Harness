"""Knowledge schema for video-derived trading ideas.

Everything a transcript, caption or on-screen text says is *untrusted data*: it is stored and shown
as quoted evidence and is never interpreted as an instruction to this system.

Schema version 2 (version 1 records still load; see ``migrate_status``). Every knowledge item
carries one of six provenance classes (``EvidenceStatus``) and a confidence, and a ``Trace`` ties an
observation to the media asset, the interpretation, the concept and the code that implements it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from xau_edge.video_intel.status import SourceStatus

SCHEMA_VERSION = 2
STALE_AFTER_DAYS = 30


class EvidenceStatus(StrEnum):
    OBSERVED = "OBSERVED"  # visible or audible in the media, with a locator
    INFERRED = "INFERRED"  # our interpretation of an observation
    CLAIMED_BY_AUTHOR = "CLAIMED_BY_AUTHOR"  # the author asserts it; not independently checked
    SUPPORTED_EXTERNALLY = "SUPPORTED_EXTERNALLY"  # an independent source we opened agrees
    CONTRADICTED_EXTERNALLY = "CONTRADICTED_EXTERNALLY"  # an independent source disagrees
    UNKNOWN = "UNKNOWN"  # nothing establishes it


class Confidence(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SourceQuality(StrEnum):
    HIGH = "HIGH"  # source code, official documentation, reproducible method
    MEDIUM = "MEDIUM"  # detailed explanation, long-form review
    LOW = "LOW"  # short clip, marketing, vendor page, anonymous post


_LEGACY = {
    "CLAIMED": "CLAIMED_BY_AUTHOR",
    "VALIDATED": "SUPPORTED_EXTERNALLY",
    "DISPROVEN": "CONTRADICTED_EXTERNALLY",
    "UNVERIFIED": "UNKNOWN",
}


def migrate_status(value: Any) -> Any:
    """Map a version-1 status word to its version-2 name; anything else passes through."""
    return _LEGACY.get(value, value) if isinstance(value, str) else value


Status = Annotated[EvidenceStatus, BeforeValidator(migrate_status)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VideoRecord(_Model):
    id: str
    source_url: str
    source_platform: str
    source_aliases: list[str] = Field(default_factory=list)  # other URLs that gave the same file
    platform_id: str | None = (
        None  # the platform's own id for the media (stable across share links)
    )
    resolved_url: str | None = None  # the canonical page the extractor resolved the link to
    title: str | None = None
    author: str | None = None
    access_status: SourceStatus
    access_code: str
    processing_status: str
    duration_s: float | None = None
    width: int | None = None
    height: int | None = None
    has_audio: bool | None = None
    file_sha256: str | None = None
    keyframe_count: int | None = None
    asr_model: str | None = None  # None when ASR did not run
    processed_at: str
    provenance: str  # how the bytes were obtained, e.g. "yt-dlp 2026.08.19, no cookies"


class TranscriptSegment(_Model):
    video_id: str
    start_ms: int
    end_ms: int
    text: str  # untrusted content; ASR can mishear numbers ("1.37.2" for 127.2)
    language: str | None = None  # "und" when the detector was not confident
    language_probability: float | None = None
    low_confidence: bool = False


class VisualEvidence(_Model):
    video_id: str
    timestamp_ms: int
    frame_reference: str
    ocr_text: str | None = None
    observations: list[str] = Field(default_factory=list)
    status: Status = EvidenceStatus.OBSERVED
    confidence: Confidence = Confidence.MEDIUM
    uncertain: bool = False


class ExternalSource(_Model):
    """An independent source. ``opened`` is False when it was seen only in a search summary."""

    source_id: str
    url: str
    title: str
    quality: SourceQuality
    opened: bool
    retrieved_at: str
    says: str  # what the source states, in our words, no more


class Claim(_Model):
    claim_id: str
    video_id: str
    evidence_refs: list[str]  # e.g. "frame@8000ms", "asr@106560ms"
    assertion: str
    status: Status
    verification: str  # what was checked and how, or why it is unknown
    citations: list[str] = Field(default_factory=list)  # source_ids or URLs actually read
    confidence: Confidence = Confidence.MEDIUM


class Trace(_Model):
    """SOURCE -> MEDIA ASSET -> LOCATOR -> OBSERVATION -> INTERPRETATION -> CONCEPT -> CODE."""

    trace_id: str
    source_url: str
    asset_sha256: str | None
    locator: str  # "frame@11200ms" or "asr@106560ms"
    observation: str  # what is there, no interpretation
    interpretation: str  # what we think it means (status INFERRED)
    concept_id: str
    rule: str | None = None  # the rule name inside the concept, e.g. "stop"
    code_ref: str | None = None  # file:symbol that implements it, if any
    confidence: Confidence = Confidence.MEDIUM


class TradingConcept(_Model):
    concept_id: str
    name: str
    alt_names: list[str] = Field(default_factory=list)
    video_id: str
    source_evidence: list[str]
    plain_language: str
    rules: dict[str, str]  # rule name -> precise statement
    configurable_disagreements: list[str] = Field(default_factory=list)
    invalidation: list[str]
    entry: str
    stop_loss: str
    target: str
    repaint_risk: str
    failure_modes: list[str]
    validation_status: Status = EvidenceStatus.UNKNOWN
    confidence: Confidence = Confidence.LOW


class ImplementationLink(_Model):
    concept_id: str
    requirement_id: str
    source_file: str
    test_file: str
    implementation_status: str  # IMPLEMENTED | PLANNED | BLOCKED


class VideoKnowledge(_Model):
    """One video's complete record: what was seen, what was said, what was concluded."""

    schema_version: int = SCHEMA_VERSION
    video: VideoRecord
    transcript: list[TranscriptSegment] = Field(default_factory=list)
    transcript_note: str = ""
    visual: list[VisualEvidence] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    traces: list[Trace] = Field(default_factory=list)
    external_sources: list[ExternalSource] = Field(default_factory=list)
    concepts: list[TradingConcept] = Field(default_factory=list)
    links: list[ImplementationLink] = Field(default_factory=list)


def staleness(knowledge: VideoKnowledge, now: datetime | None = None) -> str | None:
    """A warning when the record is older than ``STALE_AFTER_DAYS`` (sources and pages change)."""
    try:
        done = datetime.fromisoformat(knowledge.video.processed_at.replace("Z", "+00:00"))
    except ValueError:
        return "STALE: processed_at is not a valid timestamp"
    age = ((now or datetime.now(UTC)) - done).days
    if age > STALE_AFTER_DAYS:
        return f"STALE: processed {age} days ago; re-run inspect before relying on this record"
    return None


def _find_concept(knowledge: VideoKnowledge, name: str) -> TradingConcept | None:
    wanted = name.strip().lower()
    return next(
        (c for c in knowledge.concepts if wanted in {c.name.lower(), *map(str.lower, c.alt_names)}),
        None,
    )


def explain_concept(knowledge: VideoKnowledge, name: str, root: Path | None = None) -> str:
    """What the video says, what external sources say, what the code implements, what is unknown."""
    concept = _find_concept(knowledge, name)
    if concept is None:
        return f"No concept named '{name}' in video {knowledge.video.id}."
    sources = {s.source_id: s for s in knowledge.external_sources}
    video_says: list[str] = []
    external: list[str] = []
    unknown: list[str] = []
    for claim in knowledge.claims:
        line = f"[{claim.status}/{claim.confidence}] {claim.assertion}"
        if claim.status in (EvidenceStatus.OBSERVED, EvidenceStatus.CLAIMED_BY_AUTHOR):
            video_says.append(f"{line} (at {', '.join(claim.evidence_refs) or 'n/a'})")
        elif claim.status in (
            EvidenceStatus.SUPPORTED_EXTERNALLY,
            EvidenceStatus.CONTRADICTED_EXTERNALLY,
        ):
            cited = []
            for ref in claim.citations:
                src = sources.get(ref)
                cited.append(
                    f"{ref} ({src.quality}, {'opened' if src.opened else 'search only'})"
                    if src
                    else ref
                )
            external.append(f"{line} ({claim.verification}) sources: {'; '.join(cited) or 'none'}")
        elif claim.status is EvidenceStatus.INFERRED:
            video_says.append(f"{line} (our inference from {', '.join(claim.evidence_refs)})")
        else:
            unknown.append(f"{line} ({claim.verification})")
    code = []
    for link in knowledge.links:
        if link.concept_id != concept.concept_id:
            continue
        present = ""
        if root is not None and link.source_file not in ("n/a", ""):
            present = " [file exists]" if (root / link.source_file).is_file() else " [FILE MISSING]"
        code.append(
            f"{link.requirement_id}: {link.source_file} | test {link.test_file} | {link.implementation_status}{present}"  # noqa: E501 - one readable message
        )
    out = [
        f"{concept.name} (video {knowledge.video.id}, concept status {concept.validation_status}, confidence {concept.confidence})"  # noqa: E501 - one readable message
    ]
    out.append(f"Plain language: {concept.plain_language}")
    warning = staleness(knowledge)
    if warning:
        out.append(warning)
    for title, items in (
        ("VIDEO SAYS", video_says),
        ("EXTERNAL SOURCES SAY", external),
        ("CODE IMPLEMENTS", code),
        ("UNKNOWN", unknown),
    ):
        out.append(f"{title}:")
        out.extend(f"  - {item}" for item in (items or ["(nothing recorded)"]))
    return "\n".join(out)


def provenance_breakdown(knowledge: VideoKnowledge) -> str:
    """Counts and listing of every item by provenance class (observed vs inferred and so on)."""
    buckets: dict[str, list[str]] = {s.value: [] for s in EvidenceStatus}
    for v in knowledge.visual:
        buckets[v.status.value].append(
            f"visual@{v.timestamp_ms}ms: {'; '.join(v.observations)[:120]}"
        )
    for c in knowledge.claims:
        buckets[c.status.value].append(f"claim {c.claim_id}: {c.assertion[:120]}")
    for t in knowledge.traces:
        buckets[EvidenceStatus.INFERRED.value].append(
            f"trace {t.trace_id}: {t.interpretation[:120]}"
        )
    lines = [f"Provenance of video {knowledge.video.id}:"]
    for status, items in buckets.items():
        lines.append(f"{status} ({len(items)})")
        lines.extend(f"  - {i}" for i in items)
    return "\n".join(lines)
