"""Deterministic question router for a knowledge record (no LLM, no network).

Questions it understands (case-insensitive keywords):

* "observed vs inferred", "provenance", "evidence"     -> breakdown by provenance class
* "implement", "code", "how does the code" + a concept  -> VIDEO SAYS / EXTERNAL / CODE / UNKNOWN
* "teach", "summary", "what does this video"           -> concepts, speech summary, caveats
* a concept name anywhere in the question               -> that concept's full answer
* "entry"/"stop"/"target" + a concept                  -> that rule with its provenance

Anything else returns the list of things that can be asked, never an invented answer.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from xau_edge.structure.registry import lookup
from xau_edge.video_intel.knowledge import (
    EvidenceStatus,
    VideoKnowledge,
    explain_concept,
    provenance_breakdown,
    staleness,
)

_RULE_WORDS = {
    "entry": "entry",
    "stop": "stop_loss",
    "target": "target",
    "invalidation": "invalidation",
}


def _concept_in(knowledge: VideoKnowledge, question: str) -> str | None:
    q = question.lower()
    for concept in knowledge.concepts:
        for name in (concept.name, *concept.alt_names):
            if name.lower() in q:
                return concept.name
    return None


def _teaching_summary(knowledge: VideoKnowledge) -> str:
    video = knowledge.video
    lines = [
        f"Video {video.id}: {video.title or '(no title)'} ({video.source_platform}, {video.duration_s or '?'} s)"  # noqa: E501 - one readable message
    ]
    warning = staleness(knowledge)
    if warning:
        lines.append(warning)
    if knowledge.transcript:
        spoken = " ".join(s.text for s in knowledge.transcript)
        lines.append(
            f"SPEECH ({len(knowledge.transcript)} segments, untrusted ASR; numbers may be misheard):"  # noqa: E501 - one readable message
        )
        lines.append(f"  {spoken[:600]}{'...' if len(spoken) > 600 else ''}")
    else:
        lines.append(f"SPEECH: none. {knowledge.transcript_note or 'No transcript recorded.'}")
    if knowledge.concepts:
        lines.append("CONCEPTS:")
        for c in knowledge.concepts:
            lines.append(
                f"  - {c.name}: {c.validation_status}, confidence {c.confidence}. {c.plain_language}"  # noqa: E501 - one readable message
            )
    else:
        lines.append("CONCEPTS: none recorded yet (run annotate).")
    unknown = [c.assertion for c in knowledge.claims if c.status is EvidenceStatus.UNKNOWN]
    if unknown:
        lines.append("NOT ESTABLISHED:")
        lines.extend(f"  - {u}" for u in unknown)
    return "\n".join(lines)


def _rule_answer(knowledge: VideoKnowledge, concept_name: str, key: str) -> str:
    concept = next(c for c in knowledge.concepts if c.name == concept_name)
    value = getattr(concept, key)
    text = "; ".join(value) if isinstance(value, list) else value
    related = [
        f"[{c.status}/{c.confidence}] {c.assertion} (at {', '.join(c.evidence_refs)})"
        for c in knowledge.claims
        if key.split("_", maxsplit=1)[0] in c.assertion.lower()
        or concept.name.lower() in c.assertion.lower()
    ]
    traces = [
        f"{t.locator}: observed '{t.observation}' -> inferred '{t.interpretation}' ({t.confidence})"
        for t in knowledge.traces
        if t.concept_id == concept.concept_id and t.rule in (key, key.split("_", maxsplit=1)[0])
    ]
    out = [f"{concept.name} / {key}: {text}"]
    out.append("TRACE (observation -> interpretation):")
    out.extend(f"  - {t}" for t in (traces or ["(no trace recorded for this rule)"]))
    out.append("CLAIMS:")
    out.extend(f"  - {r}" for r in (related or ["(none recorded)"]))
    return "\n".join(out)


def answer(knowledge: VideoKnowledge, question: str, root: Path | None = None) -> str:
    q = question.lower().strip()
    concept = _concept_in(knowledge, question)
    if any(w in q for w in ("observed", "inferred", "provenance", "evidence")) and concept is None:
        return provenance_breakdown(knowledge)
    if concept is not None:
        for word, key in _RULE_WORDS.items():
            if word in q and "implement" not in q and "code" not in q:
                return _rule_answer(knowledge, concept, key)
        return explain_concept(knowledge, concept, root)
    if any(w in q for w in ("teach", "summary", "what does this video", "about")):
        return _teaching_summary(knowledge)
    names = ", ".join(c.name for c in knowledge.concepts) or "(no concepts recorded)"
    return (
        "I can answer: what the video teaches; observed vs inferred (provenance); "
        f"a concept by name ({names}); and its entry, stop, target or code. "
        "No answer was invented for this question."
    )


def _concept_matches(knowledge: VideoKnowledge, names: tuple[str, ...]) -> bool:
    for concept in knowledge.concepts:
        labels = [concept.name.lower(), *(a.lower() for a in concept.alt_names)]
        if any(n in label or label in n for n in names for label in labels):
            return True
    return False


def answer_pattern(name: str, records: Sequence[VideoKnowledge]) -> str:
    """Everything the store knows about one pattern family across all records and the code."""
    status = lookup(name)
    names = status.names if status else (name.strip().lower(),)
    matched = [k for k in records if _concept_matches(k, names)]
    out = [f"PATTERN: {status.key if status else name}"]
    if status is None:
        out.append("No entry in the pattern registry: no detector or research status is claimed.")
    if not matched:
        out.append("SOURCES: no knowledge record mentions this pattern.")
    else:
        authors = sorted({k.video.author or "unknown" for k in matched})
        counts: Counter[str] = Counter()
        for k in matched:
            counts.update(c.status.value for c in k.claims)
        dup = sum(1 for k in matched for c in k.claims if c.claim_id.endswith("-dup"))
        out.append(
            f"SOURCES: {len(matched)} records by {len(authors)} author(s) ({', '.join(authors)}); "
            f"repeated reels by one author are one voice, not independent evidence; "
            f"{dup} near-duplicate flag(s)"
        )
        out.append(
            "PROVENANCE OF THEIR CLAIMS: "
            + ", ".join(f"{s} {n}" for s, n in sorted(counts.items()))
        )
        contradicted = {
            (c.verification, tuple(c.citations))
            for k in matched
            for c in k.claims
            if c.status is EvidenceStatus.CONTRADICTED_EXTERNALLY
        }
        supported = {
            (c.verification, tuple(c.citations))
            for k in matched
            for c in k.claims
            if c.status is EvidenceStatus.SUPPORTED_EXTERNALLY
        }
        out.append("EXTERNAL SOURCES SAY (support):")
        out.extend(f"  - {v} {list(c)}" for v, c in sorted(supported)) if supported else out.append(
            "  - (none)"
        )
        out.append("EXTERNAL SOURCES SAY (contradiction):")
        out.extend(
            f"  - {v} {list(c)}" for v, c in sorted(contradicted)
        ) if contradicted else out.append("  - (none)")
        drawn = sorted(
            {c.assertion for k in matched for c in k.claims if c.claim_id.endswith("-entry")}
        )
        out.append("ENTRY AS DRAWN BY THE AUTHOR:")
        out.extend(f"  - {d}" for d in drawn[:6])
    if status is not None:
        out.append(f"CONFIRMATION RULE: {status.confirmation}")
        out.append(f"DETECTOR: {status.detector or 'none'}")
        out.append(f"CAUSALITY: {status.causality}")
        out.append(f"REPAINT CLASS: {status.repaint_class}")
        out.append(f"RESEARCH STATUS: {status.research_status}")
        if status.note:
            out.append(f"NOTE: {status.note}")
    out.append(
        "UNKNOWN: whether acting on this pattern has positive expectancy (no outcome study exists)."
    )
    return "\n".join(out)


def answer_source(knowledge: VideoKnowledge) -> str:
    """Observed, inferred, author claim, external support and code mapping for one source."""
    parts = [_teaching_summary(knowledge), "", provenance_breakdown(knowledge)]
    mapped = [
        f"{x.requirement_id}: {x.source_file} [{x.implementation_status}]" for x in knowledge.links
    ]
    parts.append("CODE MAPPING:")
    parts.extend(f"  - {m}" for m in (mapped or ["(none)"]))
    return "\n".join(parts)
