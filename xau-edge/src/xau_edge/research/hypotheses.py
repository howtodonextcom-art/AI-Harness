"""Hypothesis registry viewer: files, ledger results and the pre-registration order check.

A hypothesis counts as properly pre-registered only if the commit that added its file is OLDER
than its first run in the ledger. The check uses ``git log`` read-only. If git or the ledger
cannot answer, the check is "unknown", never "ok". A hypothesis with runs but no file, or a file
committed after its first run, is flagged VIOLATION.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from xau_edge.research.ledger import LedgerRun
from xau_edge.research.paths import ResearchRoot, SourceUnavailableError

V1_DIR = "docs/research/edge-program/hypotheses"
V2_DIR = "docs/research/edge-program-v2/hypotheses"
_FILE = re.compile(r"^(H\d{2})\.md$")


@dataclass(frozen=True)
class HypothesisFile:
    """What a hypothesis file says about itself."""

    id: str
    programme: str
    title: str
    registered: str | None
    status_line: str | None
    grid: str | None
    path: str


def _line(text: str, prefix: str) -> str | None:
    for raw in text.splitlines():
        if raw.strip().lower().startswith(prefix.lower()):
            return raw.strip()
    return None


def read_hypothesis(root: ResearchRoot, rel: str, programme: str) -> HypothesisFile | None:
    """Parse one file; ``None`` if it cannot be read or is not named ``Hnn.md``."""
    match = _FILE.match(rel.rsplit("/", 1)[-1])
    if match is None:
        return None
    try:
        text = root.read_text(rel)
    except SourceUnavailableError:
        return None
    first = next((ln for ln in text.splitlines() if ln.startswith("# ")), "")
    registered = _line(text, "Đăng ký:") or _line(text, "Registered:")
    grid = _line(text, "**Lưới.**") or _line(text, "**Grid.**")
    return HypothesisFile(
        id=match.group(1),
        programme=programme,
        title=first[2:].strip() or match.group(1),
        registered=registered,
        status_line=registered,
        grid=grid,
        path=rel,
    )


def _git(root: ResearchRoot, *args: str) -> str | None:
    try:
        out = subprocess.run(  # noqa: S603 - fixed argument list, no shell
            ["git", *args],  # noqa: S607
            cwd=root.root,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def last_commit_time(  # noqa: PLR0911 - one answer per reason the time cannot be trusted
    root: ResearchRoot, rel: str
) -> tuple[datetime | None, str]:
    """Time of the LAST commit that touched the file, and why it may not be trusted.

    The second value is empty when the answer is trustworthy; otherwise it says why not: a shallow
    clone, uncommitted edits, or no history. The last (not the first) commit is used: a stub
    committed early and filled in after the runs must not count as an early registration.
    """
    try:
        real = str(root.resolve(rel))
    except SourceUnavailableError:
        return None, "đường dẫn không hợp lệ"
    shallow = _git(root, "rev-parse", "--is-shallow-repository")
    if shallow is None:
        return None, "git không trả lời"
    if shallow.strip() == "true":
        return None, "kho git là bản sao nông (shallow): lịch sử không đầy đủ"
    dirty = _git(root, "status", "--porcelain", "--", real)
    if dirty is None:
        return None, "git không trả lời"
    if dirty.strip():
        return None, "file giả thuyết có thay đổi chưa commit"
    stamps = (_git(root, "log", "-1", "--format=%ct", "--", real) or "").split()
    if not stamps or not stamps[0].isdigit():
        return None, "file chưa được commit"
    return datetime.fromtimestamp(int(stamps[0]), UTC), ""


def preregistration_check(
    root: ResearchRoot, file: HypothesisFile | None, runs: list[LedgerRun], hypothesis_id: str
) -> dict[str, Any]:
    """OK, VIOLATION, NO_RESULTS or UNKNOWN for one hypothesis of one programme."""
    mine = [r for r in runs if r.hypothesis == hypothesis_id]
    if not mine:
        return {"state": "NO_RESULTS", "detail": "chưa có kết quả"}
    if file is None:
        return {"state": "VIOLATION", "detail": "có kết quả nhưng không có file đăng ký trước"}
    times = [r.when() for r in mine]
    if any(t is None for t in times):
        return {
            "state": "UNKNOWN",
            "detail": "có dòng ledger không ghi thời gian UTC rõ ràng, không thể so thứ tự",
        }
    registered, why_not = last_commit_time(root, file.path)
    if registered is None:
        return {"state": "UNKNOWN", "detail": why_not}
    first_run = min(t for t in times if t is not None)
    if registered <= first_run:
        return {
            "state": "OK",
            "detail": "đăng ký trước kết quả",
            "registered_at": registered.isoformat(),
            "first_run_at": first_run.isoformat(),
        }
    return {
        "state": "VIOLATION",
        "detail": "VI PHẠM ĐĂNG KÝ TRƯỚC: file giả thuyết được commit SAU lần chạy đầu tiên",
        "registered_at": registered.isoformat(),
        "first_run_at": first_run.isoformat(),
    }


def summarise_results(runs: list[LedgerRun], hypothesis_id: str) -> dict[str, Any]:
    """Counts and the best maximin pessimistic score among variants with results in 2 periods."""
    mine = [r for r in runs if r.hypothesis == hypothesis_id]
    variants = sorted({r.variant for r in mine})
    best: tuple[str, float] | None = None
    for variant in variants:
        scores = [
            r.mean_net_r_pessimistic
            for r in mine
            if r.variant == variant and r.mean_net_r_pessimistic is not None
        ]
        if len(scores) >= 2:
            score = min(scores)
            if best is None or score > best[1]:
                best = (variant, score)
    return {
        "runs": len(mine),
        "variants": len(variants),
        "any_pass": any(r.verdict == "PASS" for r in mine),
        "best_pessimistic_min": None if best is None else {"variant": best[0], "value": best[1]},
    }
