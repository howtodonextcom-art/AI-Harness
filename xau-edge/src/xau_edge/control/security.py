"""The control token: random per API start, in a file only the current user can read (ADR-0023).

The token never travels to the browser: the dashboard's Next.js server reads the file and adds the
``X-XAU-Control-Token`` header itself. ``check_token`` compares in constant time.
"""

from __future__ import annotations

import hmac
import os
import secrets
import shutil
import sys
from pathlib import Path

from xau_edge.control.process import run_command

TOKEN_HEADER = "X-XAU-Control-Token"  # noqa: S105 - a header name, not a secret


def generate_token() -> str:
    """256 bits of randomness, URL-safe."""
    return secrets.token_urlsafe(32)


def restrict_to_current_user(path: Path) -> bool:
    """Remove every other account's access to ``path``; ``True`` when that succeeded."""
    if sys.platform != "win32":
        path.chmod(0o600)
        return True
    user = os.environ.get("USERNAME", "")
    domain = os.environ.get("USERDOMAIN", "")
    icacls = shutil.which("icacls")
    if not user or icacls is None:
        return False
    principal = f"{domain}\\{user}" if domain else user
    args = [icacls, str(path), "/inheritance:r", "/grant:r", f"{principal}:F"]
    return run_command(args, 30.0).returncode == 0


def write_token(path: Path, token: str) -> bool:
    """Write the token (replacing any old one); returns whether the file is user-only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(token)
    return restrict_to_current_user(path)


def check_token(expected: str, given: str | None) -> bool:
    """Constant-time comparison; an empty or missing token never matches."""
    if not expected or not given:
        return False
    return hmac.compare_digest(expected.encode("utf-8"), given.encode("utf-8"))
