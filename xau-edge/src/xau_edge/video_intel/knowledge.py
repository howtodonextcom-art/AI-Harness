"""Knowledge schema for video-derived trading ideas.

Everything a transcript, caption or on-screen text says is *untrusted data*: it is stored and shown
as quoted evidence and is never interpreted as an instruction to this system.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from xau_edge.video_intel.status import SourceStatus


class EvidenceStatus(StrEnum):
    OBSERVED = "OBSERVED"  # visible or audible in the media, with a timestamp
    CLAIMED = "CLAIMED"  # asserted by the author
    INFERRED = "INFERRED"  # extrapolated by us
    VALIDATED = "VALIDATED"  # supported by independent evidence we actually read or ran
    UNVERIFIED = "UNVERIFIED"  # no sufficient evidence yet
    DISPROVEN = "DISPROVEN"  # credible evidence contradicts it


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VideoRecord(_Model):
    id: str
    source_url: str
    source_platform: str
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
    processed_at: str
    provenance: str  # how the bytes were obtained, e.g. "yt-dlp 2026.08.19, no cookies"


class TranscriptSegment(_Model):
    video_id: str
    start_ms: int
    end_ms: int
    text: str  # untrusted content
    language: str | None = None
    low_confidence: bool = False


class VisualEvidence(_Model):
    video_id: str
    timestamp_ms: int
    frame_reference: str
    ocr_text: str | None = None
    observations: list[str] = Field(default_factory=list)
    status: EvidenceStatus = EvidenceStatus.OBSERVED
    uncertain: bool = False


class Claim(_Model):
    claim_id: str
    video_id: str
    evidence_refs: list[str]  # e.g. "frame@8000ms"
    assertion: str
    status: EvidenceStatus
    verification: str  # what was checked and how, or why it is unverified
    citations: list[str] = Field(default_factory=list)  # only sources actually read


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
    validation_status: EvidenceStatus = EvidenceStatus.UNVERIFIED


class ImplementationLink(_Model):
    concept_id: str
    requirement_id: str
    source_file: str
    test_file: str
    implementation_status: str  # IMPLEMENTED | PLANNED | BLOCKED


class VideoKnowledge(_Model):
    """One video's complete record: what was seen, what was said, what was concluded."""

    video: VideoRecord
    transcript: list[TranscriptSegment] = Field(default_factory=list)
    transcript_note: str = ""
    visual: list[VisualEvidence] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    concepts: list[TradingConcept] = Field(default_factory=list)
    links: list[ImplementationLink] = Field(default_factory=list)


def explain_concept(knowledge: VideoKnowledge, name: str) -> str:
    """Answer "what did the video teach about X, what supports it, where is it in the code"."""
    wanted = name.strip().lower()
    concept = next(
        (c for c in knowledge.concepts if wanted in {c.name.lower(), *map(str.lower, c.alt_names)}),
        None,
    )
    if concept is None:
        return f"No concept named '{name}' in video {knowledge.video.id}."
    lines = [f"{concept.name} (video {knowledge.video.id}, status {concept.validation_status})"]
    lines.append(f"Plain language: {concept.plain_language}")
    lines.append("Evidence: " + ", ".join(concept.source_evidence))
    for claim in knowledge.claims:
        lines.append(f"- [{claim.status}] {claim.assertion} ({claim.verification})")
    for link in knowledge.links:
        if link.concept_id == concept.concept_id:
            lines.append(
                f"Code: {link.source_file} | test: {link.test_file} | {link.implementation_status}"
            )
    return "\n".join(lines)
