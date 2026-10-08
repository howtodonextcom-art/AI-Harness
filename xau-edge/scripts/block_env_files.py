"""Pre-commit guard: refuse to commit environment/secret files (templates are allowed)."""

from __future__ import annotations

import re
import sys

_BLOCKED = re.compile(r"(^|/)(\.env(\..+)?|[^/]*\.env|\.envrc)$", re.IGNORECASE)
_TEMPLATES = re.compile(r"\.(example|sample|template)$", re.IGNORECASE)


def is_blocked(path: str) -> bool:
    """True for ``.env``, ``.env.*``, ``*.env`` and ``.envrc`` unless it is a template."""
    normalised = path.replace("\\", "/")
    return bool(_BLOCKED.search(normalised)) and not _TEMPLATES.search(normalised)


def main(paths: list[str]) -> int:
    """Return 1 (and say why) when any path is a secret-bearing env file."""
    blocked = [p for p in paths if is_blocked(p)]
    if blocked:
        print("refusing to commit env/secret file(s): " + ", ".join(blocked), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
