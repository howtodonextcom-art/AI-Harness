"""Build ``docs/research/edge-program-v2/lineage.json`` from the real artefacts (read-only).

Sources: raw dataset sidecars (``*.meta.json``), ``data-manifest.json`` (validator results),
``clock-certificate.json``, ``event-counts-dev2.json`` and the Stage 1 manifests/results. Nothing is
invented: a stage with no artefact stays empty.

    uv run python scripts/build_lineage.py [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.integrity.lineage import LineageNode, as_json, verify  # noqa: E402

V2 = ROOT / "docs" / "research" / "edge-program-v2"
HISTORY = ROOT / "data" / "research_history" / "XAUUSD"
MANIFEST = ROOT / "docs" / "research" / "edge-program" / "data-manifest.json"
STAGE1 = ROOT / "experiments" / "edge_program_v2_stage1"
OUT = V2 / "lineage.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build() -> list[LineageNode]:
    nodes: list[LineageNode] = []
    manifest = load(MANIFEST)
    cert = load(V2 / "clock-certificate.json")
    source = LineageNode(
        stage="RAW_SOURCE",
        label="MetaTrader 5 history, FTMO demo server",
        source="mt5-ftmo-demo-history",
        broker="FTMO (demo)",
        symbol="XAUUSD",
        timezone="server wall clock converted to UTC at import",
        broker_clock="NY+7 assumed at import; certified only from 2021 (see clock-certificate.json)",
    )
    nodes.append(source)
    certified_years = sorted(int(y) for y, v in cert["years"].items() if v.get("certified"))
    raw_nodes: dict[str, LineageNode] = {}
    cert_nodes: dict[str, LineageNode] = {}
    for tf in ("H1", "H4", "M15"):
        metas = sorted((HISTORY / tf).glob("*.meta.json"))
        entry = manifest.get(tf)
        if not metas or not entry:
            continue
        meta = load(metas[-1])
        raw = LineageNode(
            stage="RAW_DATASET",
            label=f"XAUUSD {tf} raw parquet",
            parents=(source.id,),
            source=meta.get("source"),
            broker="FTMO (demo)",
            symbol="XAUUSD",
            timeframe=tf,
            timezone="UTC",
            broker_clock="NY+7 assumed",
            first_timestamp=meta.get("start"),
            last_timestamp=meta.get("end"),
            fetched_at=meta.get("fetched_at"),
            raw_hash=meta.get("sha256"),
            transformation="fetch (immutable raw store)",
            transform_version="raw-store-v1",
            detail={"rows": meta.get("rows")},
        )
        nodes.append(raw)
        raw_nodes[tf] = raw
        issues = entry.get("issues", [])
        errors = sum(int(i.get("count", 0)) for i in issues if i.get("severity") == "ERROR")
        certified = LineageNode(
            stage="CERTIFIED_DATASET",
            label=f"XAUUSD {tf} validation record",
            parents=(raw.id,),
            symbol="XAUUSD",
            timeframe=tf,
            raw_hash=entry.get("sha256"),
            transformation="validation, report never repair (ADR-0005)",
            transform_version="validators-v1",
            validator_result="PASSED" if entry.get("validation_passed") else "FAILED",
            detail={
                "dataset_id": entry.get("dataset_id"),
                "error_count": errors,
                "issue_codes": sorted({i.get("code") for i in issues}),
                "clock_certified_years": certified_years,
                "clock_uncertified_before": min(certified_years) if certified_years else None,
            },
        )
        nodes.append(certified)
        cert_nodes[tf] = certified
    derived: LineageNode | None = None
    if "H1" in cert_nodes:
        derived = LineageNode(
            stage="DERIVED_DATASET",
            label="H1 research frame (arrays, ATR14, trading-day key, clock-safety mask)",
            parents=tuple(n.id for n in cert_nodes.values()),
            symbol="XAUUSD",
            timeframe="H1",
            transformation="research_v2.frame.build_frame (no repair; unsafe days excluded)",
            transform_version="research_v2-1",
        )
        nodes.append(derived)
    counts_path = V2 / "event-counts-dev2.json"
    event_nodes: dict[str, LineageNode] = {}
    if derived is not None and counts_path.exists():
        for item in load(counts_path)["variants"]:
            node = LineageNode(
                stage="EVENT_DATASET",
                label=f"events {item['variant']} (Development-2)",
                parents=(derived.id,),
                transformation="research_v2.events detector",
                transform_version="events-v1",
                detail={
                    "events": item["events"],
                    "unique_days": item["unique_days"],
                    "excluded_clock_unsafe": item["excluded_clock_unsafe"],
                },
            )
            nodes.append(node)
            event_nodes[item["variant"]] = node
    for result_path in sorted(
        p for p in STAGE1.glob("*_dev2.json") if not p.name.startswith("summary")
    ):
        result = load(result_path)
        parent = event_nodes.get(result["variant"])
        if parent is None:
            continue
        experiment = LineageNode(
            stage="EXPERIMENT",
            label=f"Stage 1 experiment {result['variant']}",
            parents=(parent.id,),
            transformation="research_v2.study.study_variant",
            transform_version="research_v2-1",
            detail={
                "experiment_id": result["experiment_id"],
                "code_commit_sha": result["code_commit_sha"],
                "evidence_class": result["evidence_class"],
                "window": result["window"],
            },
        )
        nodes.append(experiment)
        study = result["study"]
        nodes.append(
            LineageNode(
                stage="RESULT",
                label=f"Stage 1 result {result['variant']}",
                parents=(experiment.id,),
                validator_result="SURVIVOR" if result["screening"]["stage1_survivor"] else "FAIL",
                detail={
                    "evidence_class": result["evidence_class"],
                    "n_events": study.get("n_events"),
                    "mean_net_base_r": study.get("mean_net_r_base", study.get("mean_net_base_r")),
                },
            )
        )
    return nodes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    nodes = build()
    report = verify(nodes)
    print(
        f"nodes={report.nodes} ok={report.ok} problems={report.problems} empty={report.empty_stages}"
    )
    if args.write:
        OUT.write_text(json.dumps(as_json(nodes), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {OUT.name}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
