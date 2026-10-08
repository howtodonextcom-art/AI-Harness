"""Repository hygiene guards from the ECC review and verification-loop (F-07, F-21, V-01, V-02)."""

from __future__ import annotations

import re
import shutil
import subprocess
import tarfile
import tomllib
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

PROJECT = Path(__file__).resolve().parents[2]
REPO = PROJECT.parent
WORKFLOW = REPO / ".github" / "workflows" / "xau-edge-ci.yml"


def _git_check_ignore(path: str) -> bool | None:
    git = shutil.which("git")
    if git is None:
        return None
    result = subprocess.run(  # noqa: S603
        [git, "check-ignore", "-q", "--", path], cwd=PROJECT, capture_output=True, check=False
    )
    if result.returncode == 128:  # not a git work tree
        return None
    return result.returncode == 0


@pytest.mark.parametrize(
    "path",
    [
        "data/foo.csv",
        "data/exports/a.csv",
        "logs/a.log",
        ".tmp/spill",
        "x.duckdb",
        "x.parquet",
        "x.pem",
        "x.key",
        "credentials.json",
        ".env",
        ".env.local",
        "data/raw/a.parquet",
        "experiments/runs/r1/out.json",
        # Secret-looking names and other data formats (re-review of the first .gitignore).
        "prod.env",
        "secrets.env",
        "env.local",
        ".envrc",
        "id_rsa",
        "id_ed25519",
        "x.pfx",
        "x.p12",
        "x.crt",
        "secrets.yaml",
        "data/x.zip",
        "data/exports/x.json",
        "data/exports/deep/x.bin",
        "x.feather",
        "x.hst",
        "x.sqlite",
        "x.pkl",
        "x.csv.gz",
    ],
)
def test_sensitive_or_bulky_paths_are_git_ignored(path: str) -> None:
    ignored = _git_check_ignore(path)
    if ignored is None:
        pytest.skip("git work tree not available")
    assert ignored, f"{path} should be ignored"


@pytest.mark.parametrize(
    "path",
    [
        "src/xau_edge/__init__.py",
        "tests/unit/test_config.py",
        "configs/brokers/ftmo_demo.yaml",
        ".env.example",
        "data/raw/.gitkeep",
        "docs/PROJECT_PLAN.md",
        "uv.lock",
    ],
)
def test_source_and_templates_are_not_ignored(path: str) -> None:
    ignored = _git_check_ignore(path)
    if ignored is None:
        pytest.skip("git work tree not available")
    assert not ignored, f"{path} must stay trackable"


def test_package_version_matches_the_latest_changelog_entry() -> None:
    version = tomllib.loads((PROJECT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    changelog = (PROJECT / "CHANGELOG.md").read_text(encoding="utf-8")
    first = re.search(r"^## (\d+\.\d+\.\d+)\b", changelog, flags=re.MULTILINE)
    assert first is not None
    assert version == first.group(1)


def test_ci_installs_strictly_from_the_lock_file_with_a_pinned_uv() -> None:
    if not WORKFLOW.exists():
        pytest.skip("workflow lives in the parent repository")
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "uv sync --locked" in text
    assert "--frozen" not in text
    job = yaml.safe_load(text)["jobs"]["check"]
    assert job["timeout-minutes"] <= 30
    checkout = next(s for s in job["steps"] if "actions/checkout" in str(s.get("uses", "")))
    assert checkout["with"]["persist-credentials"] is False
    steps = job["steps"]
    setup_uv = next(s for s in steps if "setup-uv" in str(s.get("uses", "")))
    assert re.fullmatch(r"\d+\.\d+\.\d+", str(setup_uv.get("with", {}).get("version", "")))
    for step in steps:  # third-party actions are pinned to full commit SHAs
        if "uses" in step:
            assert re.search(r"@[0-9a-f]{40}\b", step["uses"]), step["uses"]


@pytest.mark.integration
def test_sdist_ships_source_but_not_secrets_data_or_tool_config(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not available")
    subprocess.run(  # noqa: S603
        [uv, "build", "--sdist", "--out-dir", str(tmp_path)],
        cwd=PROJECT,
        check=True,
        capture_output=True,
    )
    archive = next(tmp_path.glob("*.tar.gz"))
    with tarfile.open(archive) as tar:
        names = [n.split("/", 1)[1] for n in tar.getnames() if "/" in n]
    assert any(n.startswith("src/xau_edge/") for n in names)
    assert "pyproject.toml" in names
    assert "uv.lock" in names
    forbidden_prefixes = (".claude/", "data/", ".venv", "experiments/runs/")
    leaked = [n for n in names if n.startswith(forbidden_prefixes)]
    assert not leaked, leaked[:5]
    assert not [n for n in names if re.match(r"\.env(\..*)?$", n.split("/")[-1])], "env files"


@pytest.mark.integration
def test_sdist_excludes_secret_looking_files_even_inside_included_folders(tmp_path: Path) -> None:
    """Re-review: the include list covers whole folders, so the exclude list must catch leaks."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not available")
    skip = shutil.ignore_patterns(
        ".venv*", ".claude", "data", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"
    )
    work = tmp_path / "proj"
    shutil.copytree(PROJECT, work, ignore=skip)
    leaks = [
        "configs/brokers/prod.env",
        "configs/.env",
        "scripts/secrets.yaml",
        "docs/id_rsa",
        "src/xau_edge/server.pem",
        "tests/private.key",
    ]
    for rel in leaks:
        (work / rel).write_text("not-a-real-secret", encoding="utf-8")
    out = tmp_path / "dist"
    subprocess.run(  # noqa: S603
        [uv, "build", "--sdist", "--out-dir", str(out)], cwd=work, check=True, capture_output=True
    )
    with tarfile.open(next(out.glob("*.tar.gz"))) as tar:
        names = {n.split("/", 1)[1] for n in tar.getnames() if "/" in n}
    assert not (set(leaks) & names), sorted(set(leaks) & names)
    assert "configs/brokers/ftmo_demo.yaml" in names  # legitimate configs still ship
