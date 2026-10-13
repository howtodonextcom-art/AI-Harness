"""docs/openapi.json is committed; the web types are generated from it. It must not drift."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "export_openapi.py"


def _load() -> object:
    spec = importlib.util.spec_from_file_location("export_openapi", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_openapi_matches_the_code() -> None:
    module = _load()
    expected = module.render()  # type: ignore[attr-defined]
    committed = module.OUT.read_text(encoding="utf-8")  # type: ignore[attr-defined]
    assert committed == expected, (
        "run: uv run python scripts/export_openapi.py (then npm run types)"
    )


def test_ws_event_is_part_of_the_contract() -> None:
    module = _load()
    assert '"WsEvent"' in module.render()  # type: ignore[attr-defined]
