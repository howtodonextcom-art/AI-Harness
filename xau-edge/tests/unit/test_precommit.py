"""The pre-commit configuration must parse and its .env guard must block the right files."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import yaml

ROOT = Path(__file__).parents[2]


def _guard() -> ModuleType:
    path = ROOT / "scripts" / "block_env_files.py"
    spec = importlib.util.spec_from_file_location("block_env_files", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_precommit_config_is_valid_yaml_with_expected_hooks() -> None:
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = {h["id"] for repo in config["repos"] for h in repo["hooks"]}
    assert {"ruff-check", "ruff-format", "mypy", "block-env-files"} <= hooks


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "xau-edge/.env",
        ".env.local",
        ".env.prod",
        "prod.env",
        "a/secrets.env",
        ".envrc",
        "A/.ENV",
    ],
)
def test_guard_blocks_env_files(path: str) -> None:
    assert _guard().is_blocked(path)


@pytest.mark.parametrize(
    "path", [".env.example", "xau-edge/.env.sample", "src/environment.py", "docs/env.md"]
)
def test_guard_allows_templates_and_lookalikes(path: str) -> None:
    assert not _guard().is_blocked(path)


def test_guard_exit_codes(capsys: pytest.CaptureFixture[str]) -> None:
    guard = _guard()
    assert guard.main(["README.md", ".env.example"]) == 0
    assert guard.main(["a/.env"]) == 1
    assert "a/.env" in capsys.readouterr().err
