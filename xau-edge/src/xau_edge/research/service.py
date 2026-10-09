"""The research console's read-only views, assembled from files that already exist.

Every method returns a JSON-safe dict with ``status`` ("ok" or "unknown") and the ``source`` paths
the numbers came from. A missing or corrupt source gives "unknown", never an implicit "ok". Nothing
here writes, runs an experiment, opens a locked period or reaches a terminal.
"""

from __future__ import annotations

import contextlib
import json
import math
import re
import threading
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import numpy as np
import polars as pl

from xau_edge.backtest.costs import CostModel
from xau_edge.integrity.dependence import effective_n
from xau_edge.integrity.evidence import EvidenceClass, Label, Proof, can_display
from xau_edge.integrity.forward_power import INCONCLUSIVE
from xau_edge.integrity.forward_power import readiness as fp_readiness
from xau_edge.market_data.profiles import BrokerProfile
from xau_edge.research import decay as decay_mod
from xau_edge.research import hypotheses as hyp
from xau_edge.research import integrity_views as iv
from xau_edge.research import power as power_mod
from xau_edge.research.ledger import LedgerParse, parse_ledger
from xau_edge.research.lifecycle import LifecycleError, LifecycleStore
from xau_edge.research.paths import ResearchRoot, SourceUnavailableError, unknown

V1_LEDGER = "docs/research/edge-program/ledger.md"
V2_LEDGER = "docs/research/edge-program-v2/ledger.md"
V2_STATE = "docs/research/edge-program-v2/STATE.json"
VERDICT = "docs/research/edge-program/final-verdict.md"
ROADMAP = "docs/PROFITABILITY_ROADMAP.md"
MANIFEST = "docs/research/edge-program/data-manifest.json"
CLOCK_CERT = "docs/research/edge-program-v2/clock-certificate.json"
LIFECYCLE = "data/execution/lifecycle.jsonl"
DECAY_CONFIG = "configs/research/decay.yaml"
FUNDED_RULES = "configs/prop/ftmo_funded.yaml"
BROKER_PROFILE = "configs/brokers/ftmo_demo.yaml"
NO_EDGE_BANNER = "Không có edge được kiểm định."
MIN_FORWARD_TRADES = 100
MAX_SOAK_SPAN_DAYS = 400
STALE_CYCLES_HOURS = 2.0
STALE_CALIBRATION_HOURS = 24.0 * 30

SPLITS: tuple[dict[str, Any], ...] = (
    {
        "id": "dev2",
        "name": "Development-2",
        "from": "2011-01-01",
        "to": "2018-12-31",
        "use": "thiết kế, Stage 1",
        "burned": True,
    },
    {
        "id": "val2",
        "name": "Validation-2",
        "from": "2019-01-01",
        "to": "2021-12-31",
        "use": "Stage 1/2 cho giả thuyết đã đăng ký",
        "burned": True,
    },
    {
        "id": "testH",
        "name": "Test-H",
        "from": "2022-01-01",
        "to": "2025-04-30",
        "use": "xác nhận, MỘT lần cho mỗi ứng viên",
        "burned": False,
    },
    {
        "id": "holdout",
        "name": "Holdout",
        "from": "2026-05-01",
        "to": "2026-10-07",
        "use": "cuối cùng, MỘT ứng viên, MỘT lần",
        "burned": False,
    },
    {
        "id": "forward",
        "name": "Forward",
        "from": "2026-10-09",
        "to": None,
        "use": "paper rồi demo",
        "burned": False,
    },
    {
        "id": "recent",
        "name": "Burned recent",
        "from": "2025-05-01",
        "to": "2026-04-30",
        "use": "chỉ mô tả",
        "burned": True,
    },
)
PLANNED: tuple[dict[str, str], ...] = (
    {"id": "H07", "name": "Liquidity-sweep reversal", "batch": "A"},
    {"id": "H08", "name": "Breakout acceptance / continuation", "batch": "A"},
    {"id": "H09", "name": "Session-transition structure", "batch": "A"},
    {"id": "H10", "name": "Conditional volatility expansion", "batch": "A"},
    {"id": "H11", "name": "Impulse, pullback, re-expansion", "batch": "B"},
    {"id": "H12", "name": "Market-structure failure", "batch": "B"},
    {"id": "H13", "name": "Scheduled-news regime", "batch": "B"},
    {"id": "H14", "name": "Cross-asset confirmation (filter only)", "batch": "B"},
)
_SEED_REJECTED = (
    "baseline_a", "baseline_b", "baseline_c", "analogue_study",
    "model_logistic", "model_random_forest", "model_xgboost", "model_lightgbm",
)  # fmt: skip
_GATES = ("cost_stress", "parameter_stability", "temporal_stability", "broker_robustness")
_DECISION = re.compile(r"^\|\s*\**(D-\d)\**\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$")


def _safe(source: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return fn()
    except (
        SourceUnavailableError,
        LifecycleError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        OverflowError,
    ) as exc:
        return unknown(source, str(exc)[:160])


class ResearchService:
    """Read-only views over the repository's research files."""

    def __init__(
        self, root: Path, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self.files = ResearchRoot(root)
        self._local = threading.local()
        self.root = root
        self.clock = clock

    @property
    def problems(self) -> list[str]:
        """Problems of the last ``_variants`` call IN THIS THREAD (requests run in a pool)."""
        if not hasattr(self._local, "problems"):
            self._local.problems = []
        return cast("list[str]", self._local.problems)

    @problems.setter
    def problems(self, value: list[str]) -> None:
        self._local.problems = value

    # -- shared helpers ------------------------------------------------------------------------

    def _ledger(self, rel: str) -> LedgerParse | None:
        try:
            return parse_ledger(self.files.read_text(rel))
        except SourceUnavailableError:
            return None

    def _state(self) -> dict[str, Any]:
        try:
            data = self.files.read_json(V2_STATE)
        except SourceUnavailableError:
            return {}
        return data if isinstance(data, dict) else {}

    def _candidate_files(self) -> list[str]:
        out: list[str] = []
        for folder in ("experiments/edge_program", "experiments/edge_program_v2"):
            out += [p for p in self.files.list(folder, "*.json") if not p.endswith("verdict.json")]
        return out

    def _variants(self) -> dict[str, dict[str, Any]]:
        """Per variant: periods with base and pessimistic results (from the result files).

        Problems (unreadable or malformed files, a period recorded twice) are collected in
        ``self.problems`` and make the candidate views "unknown": a missing or duplicated result
        must never make a variant look better.
        """
        variants: dict[str, dict[str, Any]] = {}
        self.problems = []
        for rel in self._candidate_files():
            try:
                raw = self.files.read_json(rel)
            except SourceUnavailableError:
                self.problems.append(f"không đọc được {rel}")
                continue
            if not isinstance(raw, dict) or "variant" not in raw or "scenarios" not in raw:
                self.problems.append(f"{rel} không đúng cấu trúc kết quả")
                continue
            scen = raw["scenarios"]
            base = scen.get("base") if isinstance(scen, dict) else None
            pess = scen.get("pessimistic") if isinstance(scen, dict) else None
            if not isinstance(base, dict) or not isinstance(pess, dict):
                self.problems.append(f"{rel} thiếu kịch bản base hoặc bi quan")
                continue
            name = str(raw["variant"])
            period = raw.get("period", {})
            period_name = str(period.get("name") if isinstance(period, dict) else period)
            verdict = base.get("verdict", {})
            verdict = verdict if isinstance(verdict, dict) else {}
            criteria = {k: v for k, v in verdict.items() if isinstance(v, dict) and "passed" in v}
            entry = variants.setdefault(
                name,
                {"variant": name, "hypothesis": raw.get("hypothesis"), "periods": {}, "files": []},
            )
            entry["files"].append(rel)
            if period_name in entry["periods"]:
                self.problems.append(f"{name}: giai đoạn {period_name} được ghi hai lần")
            metrics = base.get("metrics", {})
            metrics = metrics if isinstance(metrics, dict) else {}
            passed_count = sum(1 for c in criteria.values() if c["passed"])
            pess_mean = pess.get("mean_net_r")
            consistent = (
                raw.get("stage_pass") is True
                and bool(criteria)
                and passed_count == len(criteria)
                and isinstance(pess_mean, int | float)
                and pess_mean > 0
            )
            entry["periods"][period_name] = {
                "trades": base.get("trades"),
                "mean_net_r_base": base.get("mean_net_r"),
                "mean_net_r_pessimistic": pess_mean,
                "stage_pass": consistent,
                "stage_pass_claimed": raw.get("stage_pass") is True,
                "criteria": criteria,
                "criteria_passed": passed_count,
                "criteria_total": len(criteria),
                "metrics": {
                    k: metrics.get(k)
                    for k in ("profit_factor", "max_drawdown_r", "win_rate", "net_return")
                },
                "variants_k": raw.get("variants_k"),
                "alpha": raw.get("alpha"),
                "dataset_ids": raw.get("dataset_ids"),
                "code_version": raw.get("code_version"),
                "recorded_at": raw.get("recorded_at"),
                "registry_id": raw.get("registry_id"),
            }
        return variants

    @staticmethod
    def _is_survivor(entry: dict[str, Any]) -> bool:
        """Both the development and the validation period exist and each passes consistently."""
        periods = entry["periods"]
        return all(name in periods and periods[name]["stage_pass"] for name in ("dev", "val"))

    def lifecycle_store(self) -> LifecycleStore:
        """The lifecycle store (the only thing the web may write to, and only downwards)."""
        return self._store()

    def _store(self) -> LifecycleStore:
        seed = dict.fromkeys(_SEED_REJECTED, "REJECTED")
        variants = self._variants()
        for name, entry in variants.items():
            ok = not self.problems and self._is_survivor(entry)
            seed[name] = "RESEARCH" if ok else "REJECTED"
        return LifecycleStore(self.files.resolve(LIFECYCLE), seed)

    # -- W-R1 ----------------------------------------------------------------------------------

    def overview(self) -> dict[str, Any]:
        v1 = self._ledger(V1_LEDGER)
        verdict: dict[str, Any]
        try:
            text = self.files.read_text(VERDICT)
            match = re.search(r"Trạng thái:\s*\*\*(.+?)\*\*", text)
            verdict = (
                {"status": "ok", "label": match.group(1), "source": VERDICT}
                if match
                else unknown(VERDICT, "không đọc được dòng trạng thái")
            )
        except SourceUnavailableError as exc:
            verdict = unknown(VERDICT, str(exc))
        v1_view: dict[str, Any]
        if v1 is None:
            v1_view = unknown(V1_LEDGER, "không đọc được ledger")
        else:
            used = sorted({r.hypothesis for r in v1.runs})
            budget_match = None
            with contextlib.suppress(SourceUnavailableError):
                budget_match = re.search(r"(\d+)\s*giả thuyết", self.files.read_text(V1_LEDGER))
            v1_view = {
                "status": "ok" if v1.runs else "unknown",
                "source": V1_LEDGER,
                "runs": len(v1.runs),
                "malformed_rows": v1.malformed,
                "k": v1.k,
                "k_cap": v1.k_cap,
                "alpha": v1.alpha,
                "hypotheses_used": len(used),
                "hypotheses_budget": int(budget_match.group(1)) if budget_match else None,
            }
        state = self._state()
        v2_ledger = self._ledger(V2_LEDGER)
        started = bool(state) or v2_ledger is not None
        v2_view = (
            {
                "status": "ok",
                "started": True,
                "sprint": state.get("sprint"),
                "k_declared": (
                    v2_ledger.k
                    if v2_ledger is not None and v2_ledger.k
                    else state.get("k_declared")
                ),
                "k_source": V2_LEDGER if v2_ledger is not None and v2_ledger.k else V2_STATE,
                "k_cap": state.get("k_cap", 48),
                "hypotheses_used": (
                    len({r.hypothesis for r in v2_ledger.runs})
                    if v2_ledger is not None and v2_ledger.runs
                    else state.get("hypotheses_used")
                ),
                "hypotheses_budget": state.get("hypotheses_budget", 8),
                "runs": len(v2_ledger.runs) if v2_ledger else 0,
                "source": V2_STATE,
            }
            if started
            else {
                "status": "ok",
                "started": False,
                "message": "chưa bắt đầu V2 (cần quyết định D-1 của chủ dự án)",
                "k_cap": 48,
                "hypotheses_budget": 8,
                "source": V2_STATE,
            }
        )
        decisions = self._decisions(state)
        try:
            states = self._store().states()
        except (LifecycleError, SourceUnavailableError):
            states = {}
            lifecycle_ok = False
        else:
            lifecycle_ok = True
        validated = [s for s, st in states.items() if st in ("VALIDATED", "FUNDED")]
        stops: list[str] = []
        if v1_view.get("status") == "ok":
            used_n, budget = v1_view.get("hypotheses_used"), v1_view.get("hypotheses_budget")
            if used_n is not None and budget is not None and used_n >= budget:
                stops.append("V1: đã dùng hết ngân sách giả thuyết")
            if (
                v1_view.get("k") is not None
                and v1_view.get("k_cap") is not None
                and v1_view["k"] >= v1_view["k_cap"]
            ):
                stops.append("V1: K chạm trần")
        banner = (
            NO_EDGE_BANNER
            if lifecycle_ok and not validated
            else None
            if lifecycle_ok
            else "KHÔNG RÕ: không đọc được vòng đời chiến lược"
        )
        return {
            "status": "ok" if verdict.get("status") == "ok" else "unknown",
            "generated_at": self.clock().isoformat(),
            "verdict": verdict,
            "v1": v1_view,
            "v2": v2_view,
            "decisions": decisions,
            "stop_conditions_reached": stops,
            "validated_strategies": validated,
            "banner": banner,
            "sources": [VERDICT, V1_LEDGER, V2_STATE, ROADMAP],
        }

    def _decisions(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            text = self.files.read_text(ROADMAP)
        except SourceUnavailableError:
            return []
        given = state.get("decisions", {}) if isinstance(state.get("decisions"), dict) else {}
        out: list[dict[str, Any]] = []
        for line in text.splitlines():
            m = _DECISION.match(line.strip())
            if m and not m.group(2).lower().startswith("decision"):
                out.append(
                    {
                        "id": m.group(1),
                        "text": m.group(2),
                        "recommended": m.group(3),
                        "state": str(given.get(m.group(1), "pending")),
                    }
                )
        return out

    # -- W-R2 ----------------------------------------------------------------------------------

    def ledger(
        self,
        programme: str = "v1",
        hypothesis: str | None = None,
        period: str | None = None,
        scenario: str | None = None,
    ) -> dict[str, Any]:
        rel = V2_LEDGER if programme == "v2" else V1_LEDGER
        parsed = self._ledger(rel)
        if parsed is None:
            return unknown(rel, "chưa có ledger" if programme == "v2" else "không đọc được ledger")
        runs = [
            r
            for r in parsed.runs
            if (hypothesis is None or r.hypothesis == hypothesis)
            and (period is None or r.period == period)
            and (scenario is None or scenario in r.scenario)
        ]
        counts = Counter(r.verdict or "?" for r in runs)
        return {
            "status": "ok",
            "source": rel,
            "programme": programme,
            "k": parsed.k,
            "k_cap": parsed.k_cap,
            "alpha": parsed.alpha,
            "malformed_rows": parsed.malformed,
            "total_runs": len(parsed.runs),
            "shown": len(runs),
            "verdicts": dict(counts),
            "runs": [r.as_dict() for r in runs],
            "legacy_k": {"baselines": 3, "programme_1": parsed.k if programme == "v1" else None},
        }

    def power(self, k: int, n: int, sd: float) -> dict[str, Any]:
        points = [
            {"n": m, "mde": power_mod.mde(k, m, sd)} for m in (100, 200, 500, 1000, 2000, 3000)
        ]
        return {
            "status": "ok",
            "k": k,
            "n": n,
            "sd": sd,
            "alpha": power_mod.BASE_ALPHA / k,
            "mde": power_mod.mde(k, n, sd),
            "underpowered_by_design": power_mod.underpowered(k, n, sd),
            "underpowered_threshold": power_mod.UNDERPOWERED_MDE,
            "trades_needed": {
                str(e): power_mod.trades_needed(k, e, sd) for e in (0.05, 0.10, 0.15, 0.20)
            },
            "curve": points,
            "formula": "(z(1-0.05/K) + z(0.8)) * sd / sqrt(n), one-sided, i.i.d. approximation",
            "source": ROADMAP + " (section 5.1)",
        }

    # -- W-R3 ----------------------------------------------------------------------------------

    def hypotheses(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        runs: list[Any] = []
        for rel in (V1_LEDGER, V2_LEDGER):
            parsed = self._ledger(rel)
            if parsed:
                runs += parsed.runs
        for programme, folder in (("V1", hyp.V1_DIR), ("V2", hyp.V2_DIR)):
            try:
                files = self.files.list(folder, "H*.md")
            except SourceUnavailableError:
                files = []
            for rel in files:
                file = hyp.read_hypothesis(self.files, rel, programme)
                if file is None:
                    continue
                rows.append(
                    {
                        "id": file.id,
                        "programme": programme,
                        "title": file.title,
                        "registered": file.registered,
                        "grid": file.grid,
                        "path": file.path,
                        "results": hyp.summarise_results(runs, file.id),
                        "preregistration": hyp.preregistration_check(
                            self.files, file, runs, file.id
                        ),
                        "registration": (
                            iv.registration(self.files, file.id)
                            if programme == "V2"
                            else {"status": "legacy", "reason": "chương trình V1 không có sidecar"}
                        ),
                        "registration_commit": hyp.commit_info(self.files, file.path),
                        "first_result_commit": (
                            hyp.first_commit_mentioning(self.files, V2_LEDGER, file.id)
                            if programme == "V2"
                            else hyp.first_commit_mentioning(self.files, V1_LEDGER, file.id)
                        ),
                    }
                )
        registered = {r["id"] for r in rows if r["programme"] == "V2"}
        planned = [p for p in PLANNED if p["id"] not in registered]
        return {
            "status": "ok",
            "hypotheses": rows,
            "planned": planned,
            "violations": [r["id"] for r in rows if r["preregistration"]["state"] == "VIOLATION"],
            "source": f"{hyp.V1_DIR}, {hyp.V2_DIR}, {V1_LEDGER}",
        }

    # -- W-R4 ----------------------------------------------------------------------------------

    def _gates(self, variant: str) -> dict[str, Any]:
        rel = f"experiments/edge_program_v2/robustness/{variant}.json"
        try:
            raw = self.files.read_json(rel)
        except SourceUnavailableError:
            return {g: {"state": "CHƯA CHẠY"} for g in _GATES}
        if not isinstance(raw, dict):
            return {g: {"state": "KHÔNG RÕ"} for g in _GATES}
        out: dict[str, Any] = {}
        for gate in _GATES:
            item = raw.get(gate)
            if isinstance(item, dict) and isinstance(item.get("passed"), bool):
                out[gate] = {
                    "state": "PASS" if item["passed"] else "FAIL",
                    "detail": item.get("detail"),
                }
            else:
                out[gate] = {"state": "CHƯA CHẠY"}
        return out

    def candidates(self) -> dict[str, Any]:
        variants = self._variants()
        rows = []
        for name, entry in sorted(variants.items()):
            periods = entry["periods"]
            rows.append(
                {
                    "variant": name,
                    "hypothesis": entry["hypothesis"],
                    "periods": {
                        k: {
                            "trades": v["trades"],
                            "mean_net_r_base": v["mean_net_r_base"],
                            "mean_net_r_pessimistic": v["mean_net_r_pessimistic"],
                            "stage_pass": v["stage_pass"],
                            "criteria_passed": v["criteria_passed"],
                            "criteria_total": v["criteria_total"],
                        }
                        for k, v in periods.items()
                    },
                    "survivor": not self.problems and self._is_survivor(entry),
                    "gates": self._gates(name),
                }
            )
        status = "ok" if rows and not self.problems else "unknown"
        return {
            "status": status,
            "source": "experiments/edge_program, experiments/edge_program_v2",
            "survivors": [r["variant"] for r in rows if r["survivor"]],
            "variants": rows,
            "problems": list(self.problems),
            "note": (
                "Một biến thể chỉ là ứng viên khi qua cả hai giai đoạn dev và val, mỗi giai đoạn "
                "đủ 7 tiêu chí và dương trong kịch bản bi quan; cổng robustness chưa chạy luôn "
                "hiện CHƯA CHẠY."
            ),
        }

    def candidate(self, variant: str) -> dict[str, Any]:
        entry = self._variants().get(variant)
        if entry is None:
            return unknown("experiments/edge_program", "không có biến thể này")
        return {
            "status": "ok",
            "variant": variant,
            "hypothesis": entry["hypothesis"],
            "periods": entry["periods"],
            "gates": self._gates(variant),
            "gross_mid_r": None,
            "gross_mid_note": "chưa có: cột gross-at-mid thuộc sprint P1 của roadmap",
            "equity_curve": None,
            "equity_note": "file kết quả không chứa đường vốn",
            "sources": entry["files"],
        }

    # -- W-R5 ----------------------------------------------------------------------------------

    def data(self) -> dict[str, Any]:
        try:
            manifest = self.files.read_json(MANIFEST)
        except SourceUnavailableError as exc:
            return unknown(MANIFEST, str(exc))
        if not isinstance(manifest, dict):
            return unknown(MANIFEST, "manifest không phải đối tượng JSON")
        frames = []
        for tf in ("M5", "M15", "H1", "H4"):
            item = manifest.get(tf)
            if not isinstance(item, dict):
                continue
            issues = [i for i in item.get("issues", []) if isinstance(i, dict)]
            frames.append(
                {
                    "timeframe": tf,
                    "rows": item.get("rows"),
                    "first": item.get("first"),
                    "last": item.get("last"),
                    "dataset_id": item.get("dataset_id"),
                    "validation_passed": item.get("validation_passed"),
                    "errors": [i for i in issues if i.get("severity") == "ERROR"],
                    "warnings": [i for i in issues if i.get("severity") != "ERROR"],
                }
            )
        years: list[dict[str, Any]] = []
        try:
            cert = self.files.read_json(CLOCK_CERT)
            cert_years = cert.get("years", {}) if isinstance(cert, dict) else {}
            cert_ok = isinstance(cert_years, dict)
            cert_years = cert_years if cert_ok else {}
        except SourceUnavailableError:
            cert_years, cert_ok = {}, False
        for year in range(2010, 2026):
            item = cert_years.get(str(year))
            certified = bool(isinstance(item, dict) and item.get("certified") is True)
            years.append(
                {
                    "year": year,
                    "certified": certified,
                    "state": "CHỨNG NHẬN" if certified else "CHƯA CHỨNG NHẬN",
                    "offset": item.get("offset") if isinstance(item, dict) else None,
                }
            )
        blocked = [y["year"] for y in years if not y["certified"]]
        return {
            "status": "ok" if frames else "unknown",
            "source": MANIFEST,
            "generated_at": manifest.get("generated_at"),
            "frames": frames,
            "clock_certificate": {
                "source": CLOCK_CERT,
                "present": cert_ok,
                "years": years,
                "session_hypotheses_blocked_years": blocked,
                "message": "H09 và mọi giả thuyết theo phiên bị chặn ở các năm chưa chứng nhận"
                if blocked
                else "mọi năm đã chứng nhận",
            },
        }

    def locks(self) -> dict[str, Any]:  # noqa: PLR0912, PLR0915 - several independent evidences
        """Test-H and holdout read NGUYÊN VẸN only on positive evidence from SEVERAL sources.

        Registry (local, may be absent), result files, ledger rows and freeze records are all
        checked. Any use found anywhere means ĐÃ DÙNG. Anything missing, unreadable or inconsistent
        (for example fewer registry records than ledger runs) means KHÔNG RÕ, never NGUYÊN VẸN.
        """
        reasons: list[str] = []
        testh_used = holdout_used = False
        try:
            records = self.files.list("experiments/runs", "*.json")
        except SourceUnavailableError as exc:
            records = []
            reasons.append(str(exc))
        unreadable = 0
        edge_records = 0
        for rel in records:
            try:
                raw = self.files.read_json(rel)
            except SourceUnavailableError:
                unreadable += 1
                continue
            if not isinstance(raw, dict):
                unreadable += 1
                continue
            period, family = str(raw.get("period")), str(raw.get("family"))
            if family == "edge-program":
                edge_records += 1
            if period == "test" and family == "edge-program":
                testh_used = True
            if period == "test" and family in {"backtest", "model", "analogue-study"}:
                holdout_used = True
        if not records:
            reasons.append("không có sổ đăng ký thí nghiệm cục bộ (experiments/runs)")
        if unreadable:
            reasons.append(f"{unreadable} bản ghi của sổ đăng ký không đọc được")
        for rel in self._candidate_files():
            try:
                raw = self.files.read_json(rel)
            except SourceUnavailableError:
                reasons.append(f"không đọc được {rel}")
                continue
            file_period = raw.get("period") if isinstance(raw, dict) else None
            name = str(file_period.get("name") if isinstance(file_period, dict) else file_period)
            if name.lower() in {"test", "test-h", "testh"}:
                testh_used = True
        try:
            stage1_files = self.files.list(iv.STAGE1_DIR, "*.json")
        except SourceUnavailableError:
            stage1_files = []
        for rel in stage1_files:
            try:
                raw = self.files.read_json(rel)
            except SourceUnavailableError:
                reasons.append(f"không đọc được {rel}")
                continue
            window = str(raw.get("window", "")).lower() if isinstance(raw, dict) else ""
            if window in {"testh", "test", "test-h"}:
                testh_used = True
            if window == "holdout":
                holdout_used = True
        ledger_runs = 0
        for rel in (V1_LEDGER, V2_LEDGER):
            parsed = self._ledger(rel)
            if parsed is None:
                if rel == V1_LEDGER:
                    reasons.append("không đọc được ledger V1")
                continue
            ledger_runs += sum(
                1 for r in parsed.runs if not r.period.lower().startswith(("dev", "val"))
            )
            if any("holdout" in r.period.lower() for r in parsed.runs):
                holdout_used = True
            if any(r.period.lower().replace("-", "").startswith("test") for r in parsed.runs):
                testh_used = True
        if ledger_runs:
            testh_used = True
        v1 = self._ledger(V1_LEDGER)
        if v1 is not None and edge_records != len(v1.runs):
            reasons.append(
                f"sổ đăng ký có {edge_records} bản ghi edge-program, "
                f"ledger có {len(v1.runs)} lần chạy"
            )
        try:
            freezes = self.files.list("docs/research/edge-program-v2", "freeze-*.md")
        except SourceUnavailableError:
            freezes = []
        blind = bool(reasons)
        locks = []
        for split in SPLITS:
            state: str
            if split["id"] in {"testH", "holdout"}:
                used = testh_used if split["id"] == "testH" else holdout_used
                state = "ĐÃ DÙNG" if used else "KHÔNG RÕ" if blind else "NGUYÊN VẸN"
            elif split["id"] == "forward":
                state = "ĐANG TÍCH LŨY"
            else:
                state = "ĐÃ DÙNG THIẾT KẾ" if split["burned"] else "—"
            locks.append(
                {
                    **split,
                    "state": state,
                    "outcome_state": self._outcome_state(split, state, bool(freezes)),
                }
            )
        return {
            "status": "unknown" if blind else "ok",
            "source": "experiments/runs, experiments/edge_program*, ledger, freeze records",
            "registry_records": len(records),
            "unreadable_records": unreadable,
            "reasons_unknown": reasons,
            "locks": locks,
            "freeze_records": freezes,
        }

    def _freshness(self, rel: str, limit_hours: float) -> dict[str, Any]:
        """File age and a staleness warning (a stale or unreadable age is never "fresh")."""
        age = self.files.age_hours(rel, self.clock())
        return {
            "age_hours": None if age is None else round(age, 2),
            "limit_hours": limit_hours,
            "stale": age is None or age > limit_hours,
            "warning": (
                "KHÔNG RÕ: không đọc được tuổi file"
                if age is None
                else f"DỮ LIỆU CŨ: {age:.1f} giờ (giới hạn {limit_hours:g})"
                if age > limit_hours
                else ""
            ),
        }

    def _outcome_state(
        self, split: dict[str, Any], lock_state: str, has_freeze: bool
    ) -> str | None:
        """PASS, FAIL, INCONCLUSIVE, LOCKED or UNKNOWN for the confirmatory splits only."""
        if split["id"] not in {"testH", "holdout"}:
            return None
        rel = f"experiments/edge_program_v2/{split['id']}-outcome.json"
        try:
            raw = self.files.read_json(rel)
        except SourceUnavailableError:
            raw = None
        recorded = raw.get("state") if isinstance(raw, dict) else None
        valid = {"PASS", "FAIL", "INCONCLUSIVE"}
        if lock_state == "NGUYÊN VẸN":
            return (
                "LOCKED" if raw is None else "UNKNOWN"
            )  # an outcome on a pristine lock is a conflict
        if lock_state == "ĐÃ DÙNG":
            # a confirmatory result without its freeze record is not confirmatory evidence
            return recorded if recorded in valid and has_freeze else "UNKNOWN"
        return "UNKNOWN"

    # -- W-R6 ----------------------------------------------------------------------------------

    def strategies(self) -> dict[str, Any]:
        def build() -> dict[str, Any]:
            store = self._store()
            states = store.states()
            rows = [
                {
                    "strategy_id": sid,
                    "state": st,
                    "history": [e.__dict__ for e in store.history(sid)],
                    "web_demotable": st
                    in ("PAPER", "DEMO", "VALIDATED", "FUNDED", "WATCH", "DEGRADED"),
                }
                for sid, st in sorted(states.items())
            ]
            return {
                "status": "ok",
                "source": LIFECYCLE,
                "strategies": rows,
                "states": [
                    "RESEARCH",
                    "REJECTED",
                    "PAPER",
                    "DEMO",
                    "VALIDATED",
                    "FUNDED",
                    "WATCH",
                    "DEGRADED",
                    "DISABLED",
                    "RETIRED",
                ],
                "web_rule": (
                    "Từ web chỉ được HẠ xuống WATCH, DEGRADED hoặc DISABLED; không nâng bậc."
                ),
            }

        return _safe(LIFECYCLE, build)

    def forward(self, strategy_id: str) -> dict[str, Any]:
        if not re.match(r"^[A-Za-z0-9_.\-]{1,60}$", strategy_id):
            return unknown("data/forward", "mã chiến lược không hợp lệ")
        rel = f"data/forward/{strategy_id}/summary.json"

        def finite(value: Any, name: str) -> float:
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(value)
            ):
                msg = f"thiếu hoặc không hợp lệ: {name}"
                raise ValueError(msg)
            return float(value)

        def build() -> dict[str, Any]:
            raw = self.files.read_json(rel)
            if not isinstance(raw, dict):
                msg = "summary không phải đối tượng JSON"
                raise ValueError(msg)
            trades = [finite(x, "trades_net_r") for x in raw.get("trades_net_r", [])]
            n = raw.get("n_trades")
            if isinstance(n, bool) or not isinstance(n, int) or n != len(trades):
                msg = "n_trades không khớp số lệnh trong trades_net_r"
                raise ValueError(msg)
            config = decay_mod.load_decay_config(self.files.resolve(DECAY_CONFIG))
            readiness = self._forward_readiness(raw, trades)
            decay = None
            interval = raw.get("mean_r_expected")
            if n >= config.window_trades and isinstance(interval, dict):
                result = decay_mod.evaluate_decay(
                    trades,
                    ci_lower=finite(interval.get("lo"), "mean_r_expected.lo"),
                    validated_max_dd_r=finite(raw.get("validated_max_dd_r"), "validated_max_dd_r"),
                    cost_drift=finite(raw.get("cost_drift"), "cost_drift"),
                    config=config,
                )
                decay = {
                    "suggestion": result.suggestion,
                    "reasons": list(result.reasons),
                    "window_means": list(result.window_means),
                    "max_drawdown_r": result.max_drawdown_r,
                    "advisory_only": readiness["conclusion"] == INCONCLUSIVE,
                }
            conclusion = readiness["conclusion"]
            return {
                "status": "ok",
                "source": rel,
                "strategy_id": strategy_id,
                "n_trades": n,
                "legacy_reference_trades": MIN_FORWARD_TRADES,
                "legacy_reference_note": (
                    "100 lệnh chỉ là mốc tham chiếu cũ, không đủ để kết luận; "
                    "kết luận dựa trên N hiệu dụng, thời gian và chế độ thị trường"
                ),
                "readiness": readiness,
                "conclusion": conclusion,
                "expected_vs_realised": {
                    k: raw.get(k)
                    for k in (
                        "signals_per_week_expected",
                        "signals_per_week_realised",
                        "mean_r_expected",
                        "mean_r_realised",
                        "mfe_expected",
                        "mfe_realised",
                        "mae_expected",
                        "mae_realised",
                        "spread_assumed",
                        "spread_observed",
                        "slippage_assumed",
                        "slippage_observed",
                        "latency_ms",
                    )
                },
                "decay": decay,
                "updated_at": raw.get("updated_at"),
            }

        out = _safe(rel, build)
        if out["status"] == "unknown":
            out["message"] = "KHÔNG CÓ MẪU FORWARD hợp lệ cho chiến lược này"
        return out

    def _forward_readiness(self, raw: dict[str, Any], trades: list[float]) -> dict[str, Any]:
        """Candidate-specific readiness; INCONCLUSIVE whenever an input is missing."""
        need = ("trade_day_ids", "calendar_days", "regimes_seen", "target_effect", "expected_sd")
        missing = [k for k in need if raw.get(k) is None]
        interval = raw.get("mean_r_expected")
        if not isinstance(interval, dict) or interval.get("lo") is None:
            missing.append("mean_r_expected.lo")
        days = raw.get("trade_day_ids")
        if not missing and (not isinstance(days, list) or len(days) != len(trades)):
            missing.append("trade_day_ids (độ dài khác n_trades)")
        if missing or not trades:
            return {
                "conclusion": INCONCLUSIVE,
                "raw_n": len(trades),
                "effective_n": None,
                "reasons": [f"thiếu dữ liệu để kết luận: {', '.join(missing) or 'không có lệnh'}"],
                "legacy_reference_trades": MIN_FORWARD_TRADES,
            }
        days_list = cast("list[int]", days)
        interval_map = cast("dict[str, Any]", interval)
        values = np.asarray(trades, dtype=np.float64)
        eff = effective_n(values, np.asarray(days_list, dtype=np.int64))
        sd = float(values.std(ddof=1)) if len(values) > 1 else 0.0
        result = fp_readiness(
            raw_n=len(trades),
            effective_n=eff,
            calendar_days=float(raw["calendar_days"]),
            regimes_seen=int(raw["regimes_seen"]),
            observed_mean=float(values.mean()),
            observed_sd=sd,
            expected_lower_bound=float(interval_map["lo"]),
            target_effect=float(raw["target_effect"]),
            expected_sd=float(raw["expected_sd"]),
        )
        out = dict(result.__dict__)
        out["reasons"] = list(result.reasons)
        return out

    # -- research integrity layer (RI) ---------------------------------------------------------

    def provenance(self) -> dict[str, Any]:
        """When a view was generated and from which code (never a path or a secret)."""
        sha = (hyp._git(self.files, "rev-parse", "HEAD") or "").strip()
        return {"generated_at": self.clock().isoformat(), "code_commit": sha[:12] or None}

    def stage1(self) -> dict[str, Any]:
        return _safe(iv.STAGE1_DIR, lambda: iv.stage1(self.files, self.clock()))

    def lineage(self) -> dict[str, Any]:
        return _safe(iv.LINEAGE, lambda: iv.lineage(self.files))

    def prospective(self) -> dict[str, Any]:
        return _safe(iv.PROSPECTIVE, lambda: iv.prospective(self.files, self.clock()))

    def rollout(self) -> dict[str, Any]:
        return _safe(iv.ROLLOUT, lambda: iv.rollout(self.files))

    def gate_calibration(self) -> dict[str, Any]:
        return _safe(iv.GATE_CAL, lambda: iv.gate_calibration(self.files))

    # -- W-R7 ----------------------------------------------------------------------------------

    def calibration(self) -> dict[str, Any]:
        costs = CostModel()
        assumed = {
            "slippage_points": costs.slippage_points,
            "commission_per_lot_per_side": costs.commission_per_lot_per_side,
            "swap_long_points": costs.swap_long_points,
            "swap_short_points": costs.swap_short_points,
        }
        rel = "data/execution/calibration.json"
        try:
            measured = self.files.read_json(rel)
        except SourceUnavailableError:
            measured = None
        proof = Proof(
            EvidenceClass.EXECUTION,
            broker_evidence_present=isinstance(measured, dict) and bool(measured),
        )
        labels = {
            "EXECUTION_VALIDATED": {
                "allowed": can_display(Label.EXECUTION_VALIDATED, proof).allowed,
                "reasons": list(can_display(Label.EXECUTION_VALIDATED, proof).reasons),
            }
        }
        if not isinstance(measured, dict) or not measured:
            return {
                "status": "unknown",
                "source": rel,
                "labels": labels,
                "evidence_class": "EXECUTION",
                "assumed": assumed,
                "measured": None,
                "message": "chưa đo chi phí thật (sprint P12); các số trên là GIẢ ĐỊNH",
            }
        return {
            "status": "ok",
            "source": rel,
            "labels": labels,
            "evidence_class": "EXECUTION",
            "freshness": self._freshness(rel, STALE_CALIBRATION_HOURS),
            "assumed": assumed,
            "measured": measured,
        }

    def soak(self) -> dict[str, Any]:  # noqa: PLR0915 - one report over three logs
        cycles_rel = "data/execution/cycles.jsonl"
        try:
            lines = self.files.read_text(cycles_rel).splitlines()
            rows = [json.loads(ln) for ln in lines if ln.strip()]
        except (SourceUnavailableError, json.JSONDecodeError):
            return {
                **unknown(cycles_rel, "chưa có hoặc không đọc được cycles.jsonl"),
                "alerts": None,
            }
        decided: list[datetime] = []
        for row in rows:
            if not isinstance(row, dict):
                return {**unknown(cycles_rel, "một dòng không phải đối tượng JSON"), "alerts": None}
            raw = row.get("decision_time")
            if not raw or row.get("skipped"):
                continue
            try:
                stamp = datetime.fromisoformat(raw)
            except (TypeError, ValueError):
                return {**unknown(cycles_rel, "decision_time không hợp lệ"), "alerts": None}
            if stamp.tzinfo is None:
                return {**unknown(cycles_rel, "decision_time thiếu múi giờ"), "alerts": None}
            decided.append(stamp.astimezone(UTC))
        unique = sorted(set(decided))
        duplicates = len(decided) - len(unique)
        expected: int | None = None
        uptime: float | None = None
        days: float | None = None
        over_count = False
        problem: str | None = None
        now = self.clock()
        if len(unique) >= 2:
            first, last = unique[0], max(unique[-1], now)
            days = (unique[-1] - first).total_seconds() / 86400
            if (last - first) > timedelta(days=MAX_SOAK_SPAN_DAYS) or first.year < 2000:
                problem = f"khoảng thời gian vượt {MAX_SOAK_SPAN_DAYS} ngày hoặc ngày bất thường"
            else:
                try:
                    cal = BrokerProfile.from_yaml(
                        self.files.resolve(BROKER_PROFILE)
                    ).validation.calendar
                    stamps = pl.datetime_range(
                        first, last, interval="15m", time_zone="UTC", eager=True
                    )
                    frame = pl.DataFrame({"t": stamps})
                    closed = frame.select(cal.closed_expr(pl.col("t")).alias("c"))["c"]
                    expected = frame.height - int(closed.sum())
                    uptime = len(unique) / expected if expected else None
                    over_count = bool(uptime is not None and uptime > 1.0)
                except (SourceUnavailableError, ValueError, OSError, pl.exceptions.PolarsError):
                    expected = uptime = None
                    problem = "không tính được số bar kỳ vọng"
        alerts: dict[str, int] | None = None
        try:
            alerts = {
                "lines": len(self.files.read_text("data/execution/alerts.jsonl").splitlines())
            }
        except SourceUnavailableError:
            alerts = None
        funded: dict[str, Any]
        try:
            from xau_edge.funded.rules import load_funded_rules  # noqa: PLC0415 - optional view

            rules = load_funded_rules(self.files.resolve(FUNDED_RULES))
            pending = rules.pending()
            funded = {
                "status": "ok",
                "source": FUNDED_RULES,
                "pending": pending,
                "total": len(rules.rules),
            }
        except (SourceUnavailableError, ValueError, OSError):
            funded = unknown(FUNDED_RULES, "không đọc được luật funded")
        return {
            "status": "unknown" if problem else "ok",
            "source": cycles_rel,
            "problem": problem,
            "cycles": len(rows),
            "decided_bars": len(unique),
            "duplicate_bars": duplicates,
            "expected_bars": expected,
            "uptime_m15": uptime,
            "uptime_over_count": over_count,
            "days_covered": days,
            "measured_until": now.isoformat(),
            "freshness": self._freshness(cycles_rel, STALE_CYCLES_HOURS),
            "target": {"soak_days": 14, "uptime_min": 0.99, "duplicates_max": 0, "demo_weeks": 4},
            "alerts": alerts,
            "funded_rules": funded,
        }
