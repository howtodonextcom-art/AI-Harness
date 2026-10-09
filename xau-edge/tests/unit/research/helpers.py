# ruff: noqa: E501
"""A synthetic repository tree for the research console tests (no real data, no network)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

REAL = Path(__file__).parents[3]

LEDGER = """# Ledger

* Biến thể đã khai báo: 6 giả thuyết x 3 giá trị = **18**.
* **K = 3 + 18 = 21; trần K cap = 21.** alpha = 0.05 / 21 = 0.002381.

## Bảng chạy

| # | Thời gian | Giả thuyết/biến thể | Giai đoạn | Kịch bản | Ghi chú | Registry id |
|---|---|---|---|---|---|---|
| 1 | 2026-10-08 14:50:34 UTC | H01-theta0.3 | dev-H | base + bi quan | 2727 lệnh, mean net R -0.0812 / bi quan -0.0933; FAIL | `1eb8c293cfe9074f` |
| 2 | 2026-10-08 14:50:38 UTC | H01-theta0.6 | dev-H | base + bi quan | 1461 lệnh, mean net R -0.0854 / bi quan -0.0974; FAIL | `a4d067e77ca95fb4` |
| 3 | 2026-10-08 14:51:32 UTC | H01-theta0.3 | val-H | base + bi quan | 1091 lệnh, mean net R -0.0827 / bi quan -0.0908; FAIL | `b2ec554d467c0d66` |
| 4 | 2026-10-08 14:51:33 UTC | H01-theta0.6 | val-H | base + bi quan | 600 lệnh, mean net R -0.1097 / bi quan -0.1163; FAIL | `855a09953e7a618c` |
"""

VERDICT = "# Edge Program\n\nNgày: 2026-10-08. Trạng thái: **(B) NO EDGE WITHIN BUDGET**.\n"

HYPOTHESIS = (
    "# H01: Động lượng ở giờ mở phiên\n\nĐăng ký: 2026-10-08. Trạng thái: chưa có kết quả.\n\n"
    "**Lưới.** `theta` in {0.3, 0.6, 0.9}.\n"
)

ROADMAP = """# Roadmap

## Appendix A: owner decisions

| ID | Decision | Recommended |
|---|---|---|
| **D-1** | Approve Edge Program V2 | Yes |
| D-2 | Approve read-only MT5 probes | Yes |
"""

MANIFEST = {
    "generated_at": "2026-10-08T14:10:52+00:00",
    "H1": {
        "rows": 91655,
        "first": "2010-01-24T23:00:00+00:00",
        "last": "2025-04-30T23:00:00+00:00",
        "dataset_id": "8e64dd6561015b72",
        "validation_passed": False,
        "issues": [
            {"code": "MISSING_BARS", "severity": "ERROR", "count": 1003},
            {"code": "WEEKEND_BARS", "severity": "WARNING", "count": 2226},
        ],
    },
}


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_repo(root: Path, *, git: bool = False) -> Path:
    """The minimum tree the service reads."""
    write(root, "docs/research/edge-program/ledger.md", LEDGER)
    write(root, "docs/research/edge-program/final-verdict.md", VERDICT)
    write(root, "docs/research/edge-program/hypotheses/H01.md", HYPOTHESIS)
    write(root, "docs/PROFITABILITY_ROADMAP.md", ROADMAP)
    write(root, "docs/research/edge-program/data-manifest.json", json.dumps(MANIFEST))
    write(
        root,
        "configs/research/decay.yaml",
        (REAL / "configs/research/decay.yaml").read_text("utf-8"),
    )
    broker = root / "configs/brokers"
    broker.mkdir(parents=True, exist_ok=True)
    shutil.copy(REAL / "configs/brokers/ftmo_demo.yaml", broker / "ftmo_demo.yaml")
    (root / "configs/prop").mkdir(parents=True, exist_ok=True)
    shutil.copy(REAL / "configs/prop/ftmo_funded.yaml", root / "configs/prop/ftmo_funded.yaml")
    if git:
        run_git(root, "init", "-q")
    return root


def run_git(root: Path, *args: str, when: str | None = None) -> None:
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "PATH": os.environ["PATH"],
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
    }
    if when:
        env["GIT_AUTHOR_DATE"] = when
        env["GIT_COMMITTER_DATE"] = when
    subprocess.run(["git", *args], cwd=root, env=env, check=True, capture_output=True)  # noqa: S603, S607


def commit(root: Path, message: str, when: str) -> None:
    run_git(root, "add", "-A")
    run_git(root, "commit", "-q", "-m", message, when=when)


def result_file(variant: str, period: str, *, passed: bool, trades: int = 120) -> dict[str, object]:
    criteria = {
        "min_trades": {"passed": trades >= 100, "value": trades, "threshold": 100},
        "profit_factor": {"passed": passed, "value": 1.3 if passed else 0.9, "threshold": 1.2},
    }
    return {
        "variant": variant,
        "hypothesis": variant.split("-", maxsplit=1)[0],
        "period": {"name": period},
        "stage_pass": passed,
        "variants_k": 21,
        "alpha": 0.00238,
        "dataset_ids": {"H1": "8e64dd6561015b72"},
        "recorded_at": "2026-10-08T14:51:42+00:00",
        "registry_id": "aa83ed1b697ea855",
        "scenarios": {
            "base": {
                "trades": trades,
                "mean_net_r": 0.05 if passed else -0.06,
                "metrics": {"profit_factor": 1.3 if passed else 0.9, "max_drawdown_r": 8.0},
                "verdict": {**criteria, "passed": passed},
            },
            "pessimistic": {"trades": trades, "mean_net_r": 0.03 if passed else -0.08},
        },
    }
