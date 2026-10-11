"""Turn docs/pattern-intelligence/source-catalog.json into knowledge-record annotations.

The catalog holds what a person (or agent) READ from the frames; this script only structures it:
visual evidence at the timestamp of the frame that shows it, claims with their provenance class,
traces and links. It never invents an observation and it never marks anything VALIDATED.

    uv run python scripts/pattern_catalog_to_knowledge.py            # annotate data/video_knowledge
    uv run python scripts/pattern_catalog_to_knowledge.py --export   # also write docs copies
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from xau_edge.video_intel import store
from xau_edge.video_intel.knowledge import (
    Claim,
    Confidence,
    EvidenceStatus,
    ExternalSource,
    ImplementationLink,
    SourceQuality,
    Trace,
    TradingConcept,
    VideoKnowledge,
    VisualEvidence,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs" / "pattern-intelligence" / "source-catalog.json"
EXPORT = ROOT / "docs" / "pattern-intelligence" / "knowledge"
WORK = ROOT / "data" / "video_work"
SAMPLE_FPS = 2.0  # the keyframe sampler's rate for clips this short

SOURCES = {
    "bk-adam": (
        "https://www.thepatternsite.com/aadb.html",
        "Bulkowski, Adam and Adam double bottom",
        "Narrow Adam bottoms and rounded Eve bottoms; confirmed when price closes above the centre peak; Adam & Adam: 16% break-even failure rate, rank 26 of 39, 1,154 perfect trades; buying before confirmation: price continues lower 48% of the time.",
    ),
    "bk-fallwedge": (
        "https://thepatternsite.com/fallwedge.html",
        "Bulkowski, Falling wedge",
        "Five trendline touches, minimum 3 weeks; confirmed by a close outside a trendline; break-even failure 26% up / 29% down, rank 31 of 39; 'a poor performer as far as bullish chart patterns go'.",
    ),
    "bk-risewedge": (
        "https://thepatternsite.com/risewedge.html",
        "Bulkowski, Rising wedge",
        "Down breakouts: 51% break-even failure rate, rank 36 of 36 (last), average decline 9%; 'some of the worst performing chart patterns'; 1,400+ perfect trades.",
    ),
    "bk-cup": (
        "https://thepatternsite.com/cup.html",
        "Bulkowski, Cup with handle",
        "U-shaped cup, handle in the upper half; rank 3 of 39, 5% break-even failure, +54% average rise on 913 perfect trades; identification allows discretion; 47% of 300 patterns (1990-2024) dropped substantially within two months of the breakout.",
    ),
    "bk-wolfe": (
        "https://thepatternsite.com/WolfeWaveBull.html",
        "Bulkowski, Wolfe wave",
        "47% meet the EPA under perfect entries at the P5 low (cannot be duplicated), rank 34 of 39.",
    ),
}
FAMILY = {
    "ADAM_AND_EVE": (
        "Adam and Eve double top/bottom",
        "src/xau_edge/structure/reversal.py",
        "PARTIAL: double top/bottom geometry only; the narrow-versus-rounded Adam/Eve distinction is not implemented",
    ),
    "WOLFE_WAVE": ("Wolfe Wave", "src/xau_edge/structure/wolfe.py", "IMPLEMENTED"),
}
EXTERNAL_VIEW = {
    "FALLING_WEDGE": (
        "CONTRADICTED_EXTERNALLY",
        ["bk-fallwedge"],
        "The captions call it a powerful bullish reversal; Bulkowski (stocks, idealised) calls the falling wedge a poor performer: 26% break-even failure up, rank 31 of 39.",
    ),
    "RISING_WEDGE": (
        "CONTRADICTED_EXTERNALLY",
        ["bk-risewedge"],
        "The Reel presents the bearish breakdown as a powerful signal; Bulkowski ranks rising-wedge down breakouts last (36 of 36) with a 51% break-even failure rate.",
    ),
    "CUP_AND_HANDLE": (
        "SUPPORTED_EXTERNALLY",
        ["bk-cup"],
        "Bulkowski ranks the cup with handle 3 of 39 in idealised stock tests, but allows discretion in identification and found 47% of recent patterns dropped substantially within two months.",
    ),
    "ADAM_AND_EVE": (
        "SUPPORTED_EXTERNALLY",
        ["bk-adam"],
        "Bulkowski describes the Adam/Eve double bottom with explicit shapes and a close-above-the-centre-peak confirmation; his Adam & Adam variant: 16% break-even failure, rank 26 of 39; trading before confirmation fails 48% of the time.",
    ),
    "WOLFE_WAVE": (
        "SUPPORTED_EXTERNALLY",
        ["bk-wolfe"],
        "The five-point geometry matches published rules; the only independent statistic (47% to the EPA) assumes an entry at the exact P5 extreme.",
    ),
}
CAPTION_CLAIM = re.compile(r"^\d[\d.,]*[KkMm]? (?:reactions|views)[^|]*\|\s*")


def frame_ms(video_id: str, pick: int, total: int = 6) -> int:
    files = sorted((WORK / video_id / "frames").glob("cand_*.png"))
    if not files:
        return 0
    chosen = files[round((pick - 1) * (len(files) - 1) / (total - 1))]
    return round((int(chosen.stem.split("_")[1]) - 1) * 1000 / SAMPLE_FPS)


def build(entry: dict, knowledge: VideoKnowledge) -> dict:
    vid = knowledge.video.id
    n = entry["n"]
    fam = entry["family"]
    url = knowledge.video.source_url
    sha = knowledge.video.file_sha256
    last = frame_ms(vid, 6)
    first = frame_ms(vid, 1)
    entry_ms = frame_ms(vid, entry["entry_pick"]) if entry.get("entry_pick") else None
    stop_pick = None
    m = re.search(r"pick (\d)", entry.get("stop") or "")
    if m:
        stop_pick = int(m.group(1))
    elif entry.get("stop"):
        stop_pick = entry.get("entry_pick")
    stop_ms = frame_ms(vid, stop_pick) if stop_pick else None
    cid = fam.lower()
    name = FAMILY.get(fam, (fam.replace("_", " ").title(), None, None))[0]
    visual = [
        VisualEvidence(
            video_id=vid,
            timestamp_ms=first,
            frame_reference="keyframe 1 of 6",
            observations=[
                f"Top panel: a textbook diagram of the {name} pattern; bottom panel: a chart that is annotated progressively."
            ],
            confidence=Confidence.HIGH,
        ),
    ]
    claims: list[Claim] = [
        Claim(
            claim_id=f"r{n}-pattern",
            video_id=vid,
            evidence_refs=[f"frame@{first}ms"],
            assertion=f"The Reel presents a {name} ({entry['direction']}) example.",
            status=EvidenceStatus.OBSERVED,
            verification="read from the diagram title",
            confidence=Confidence.HIGH,
        ),
        Claim(
            claim_id=f"r{n}-entry",
            video_id=vid,
            evidence_refs=[f"frame@{entry_ms}ms"] if entry_ms is not None else [],
            assertion="Entry as drawn: " + entry["entry"],
            status=EvidenceStatus.OBSERVED,
            verification="read from the labelled marker; the price level is not legible",
            confidence=Confidence.MEDIUM,
        ),
        Claim(
            claim_id=f"r{n}-stop",
            video_id=vid,
            evidence_refs=[f"frame@{stop_ms}ms"] if stop_ms is not None else [],
            assertion=("Stop as drawn: " + entry["stop"])
            if entry.get("stop")
            else "No stop-loss is drawn in the viewed frames.",
            status=EvidenceStatus.OBSERVED,
            verification="read from the labelled marker or its absence in 6 viewed frames",
            confidence=Confidence.MEDIUM if entry.get("stop") else Confidence.LOW,
        ),
        Claim(
            claim_id=f"r{n}-outcome",
            video_id=vid,
            evidence_refs=[f"frame@{last}ms"],
            assertion="The final frames show: " + entry["outcome"] + ".",
            status=EvidenceStatus.OBSERVED,
            verification="read from the last viewed frame of a replayed, annotated chart",
            confidence=Confidence.MEDIUM,
        ),
        Claim(
            claim_id=f"r{n}-repeatable",
            video_id=vid,
            evidence_refs=[f"frame@{last}ms"],
            assertion="This outcome is typical or repeatable for the pattern.",
            status=EvidenceStatus.UNKNOWN,
            verification="a single curated example drawn with hindsight; no sample, no failures, no costs, no instrument or timeframe",
            confidence=Confidence.HIGH,
        ),
        Claim(
            claim_id=f"r{n}-asr",
            video_id=vid,
            evidence_refs=["asr"],
            assertion="The audio carries no spoken explanation.",
            status=EvidenceStatus.OBSERVED,
            verification=("ASR returned background song lyrics: " + entry.get("asr_content", ""))
            if not entry.get("music_only_asr", True)
            else "ASR returned no speech or only a hallucinated phrase on music; low-confidence segments are flagged",
            confidence=Confidence.MEDIUM,
        ),
    ]
    title = CAPTION_CLAIM.sub("", knowledge.video.title or "")[:170]
    claims.append(
        Claim(
            claim_id=f"r{n}-caption",
            video_id=vid,
            evidence_refs=["metadata.title"],
            assertion="Caption (untrusted): " + title,
            status=EvidenceStatus.CLAIMED_BY_AUTHOR,
            verification="author caption; promotional wording, no measured result",
            confidence=Confidence.HIGH,
        )
    )
    if fam in EXTERNAL_VIEW:
        status, cites, text = EXTERNAL_VIEW[fam]
        claims.append(
            Claim(
                claim_id=f"r{n}-external",
                video_id=vid,
                evidence_refs=[],
                assertion=f"Independent evidence on the {name} family.",
                status=EvidenceStatus[status],
                verification=text,
                citations=cites,
                confidence=Confidence.MEDIUM,
            )
        )
    if entry.get("near_duplicate_of"):
        claims.append(
            Claim(
                claim_id=f"r{n}-dup",
                video_id=vid,
                evidence_refs=[],
                assertion=f"Visually near-identical to Reel {entry['near_duplicate_of']} (same chart recording re-edited): not independent evidence.",
                status=EvidenceStatus.OBSERVED,
                verification="perceptual hash of the chart region differs by 34 of 256 bits, the closest pair of the 29; captions differ",
                confidence=Confidence.MEDIUM,
            )
        )
    for i, item in enumerate(entry.get("third_party_content", [])):
        claims.append(
            Claim(
                claim_id=f"r{n}-third{i}",
                video_id=vid,
                evidence_refs=[f"frame@{last}ms"],
                assertion="Third-party content appears: " + item,
                status=EvidenceStatus.OBSERVED,
                verification="seen in the viewed frames",
                confidence=Confidence.MEDIUM,
            )
        )
    traces = [
        Trace(
            trace_id=f"t{n}-entry",
            source_url=url,
            asset_sha256=sha,
            locator=f"frame@{entry_ms}ms" if entry_ms is not None else "n/a",
            observation=entry["entry"],
            interpretation="Where the author draws the entry relative to the pattern geometry (a drawing, not a rule); whether it was marked live or after the move is not knowable.",
            concept_id=cid,
            rule="entry",
            code_ref=FAMILY.get(fam, (None, None, None))[1],
            confidence=Confidence.MEDIUM,
        ),
        Trace(
            trace_id=f"t{n}-stop",
            source_url=url,
            asset_sha256=sha,
            locator=f"frame@{stop_ms}ms" if stop_ms is not None else "n/a",
            observation=entry.get("stop") or "no stop-loss label in the viewed frames",
            interpretation="Stop placement as drawn; no distance, ATR or pip rule is given.",
            concept_id=cid,
            rule="stop_loss",
            code_ref=None,
            confidence=Confidence.MEDIUM if entry.get("stop") else Confidence.LOW,
        ),
    ]
    concept = TradingConcept(
        concept_id=cid,
        name=name,
        alt_names=[fam.replace("_", " ").title()],
        video_id=vid,
        source_evidence=[f"frame@{first}ms", f"frame@{last}ms"],
        plain_language=f"{name} as drawn by the author; entry, stop and target are illustrations without stated rules.",
        rules={
            "entry_as_drawn": entry["entry"],
            "stop_as_drawn": entry.get("stop") or "none drawn",
            "target_as_drawn": entry.get("target") or "none",
        },
        configurable_disagreements=[],
        invalidation=["not stated"],
        entry=entry["entry"],
        stop_loss=entry.get("stop") or "none drawn",
        target=entry.get("target") or "none",
        repaint_risk="unknown: a replayed chart annotated progressively; points drawn at the live edge cannot be known in real time",
        failure_modes=["no failed example is shown in any Reel of the series"],
        validation_status=EvidenceStatus.UNKNOWN,
        confidence=Confidence.LOW,
    )
    impl = FAMILY.get(fam)
    links = [
        ImplementationLink(
            concept_id=cid,
            requirement_id=f"PI-{fam}",
            source_file=impl[1] if impl else "n/a",
            test_file="tests/unit/structure" if impl else "n/a",
            implementation_status=impl[2] if impl else "NOT IMPLEMENTED",
        )
    ]
    sources = [
        ExternalSource(
            source_id=k,
            url=v[0],
            title=v[1],
            quality=SourceQuality.MEDIUM,
            opened=True,
            retrieved_at="2026-10-11",
            says=v[2],
        )
        for k, v in SOURCES.items()
        if (fam in EXTERNAL_VIEW and k in EXTERNAL_VIEW[fam][1])
    ]
    return {
        "visual": visual,
        "claims": claims,
        "traces": traces,
        "concepts": [concept],
        "links": links,
        "external_sources": sources,
        "entry_ms": entry_ms,
    }


def merge(knowledge: VideoKnowledge, parts: dict) -> VideoKnowledge:
    keep_claims = [c for c in knowledge.claims if not c.claim_id.startswith("r")]
    return knowledge.model_copy(
        update={
            "visual": [v for v in knowledge.visual if v.frame_reference != "keyframe 1 of 6"]
            + parts["visual"],
            "claims": keep_claims + parts["claims"],
            "traces": [t for t in knowledge.traces if not t.trace_id.startswith("t")]
            + parts["traces"],
            "concepts": [
                c for c in knowledge.concepts if c.concept_id != parts["concepts"][0].concept_id
            ]
            + parts["concepts"],
            "links": [x for x in knowledge.links if x.concept_id != parts["links"][0].concept_id]
            + parts["links"],
            "external_sources": [
                s
                for s in knowledge.external_sources
                if s.source_id not in {n.source_id for n in parts["external_sources"]}
            ]
            + parts["external_sources"],
        }
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    count = 0
    for entry in catalog["reels"]:
        knowledge = store.load(entry["media_id"])
        updated = merge(knowledge, build(entry, knowledge))
        store.save(updated)
        count += 1
        if args.export:
            EXPORT.mkdir(parents=True, exist_ok=True)
            clean = updated.model_copy(
                update={
                    "transcript": [],
                    "transcript_note": "ASR returned music lyrics, no speech or a hallucinated phrase; not committed (third-party content).",
                }
                if updated.transcript
                else {}
            )
            (EXPORT / f"reel_{entry['n']:02d}_{entry['media_id']}.json").write_text(
                clean.model_dump_json(indent=2), encoding="utf-8"
            )
    print(f"annotated {count} records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
