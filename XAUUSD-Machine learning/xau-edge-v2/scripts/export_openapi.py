"""Write the OpenAPI contract to docs/openapi.json (the web build generates its types from it)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from xau_edge_v2.api.app import create_app
from xau_edge_v2.config import Settings

OUT = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"


def render() -> str:
    app = create_app(Settings(log_dir=Path(tempfile.mkdtemp())))
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    text = render()
    if "--check" in sys.argv:
        sys.exit(0 if OUT.read_text(encoding="utf-8") == text else 1)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
