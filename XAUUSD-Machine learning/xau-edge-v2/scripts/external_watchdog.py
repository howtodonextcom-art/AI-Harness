"""External watchdog: watches the V2 service FROM OUTSIDE, so a dead process still gets reported.

Run by Task Scheduler every 2 minutes (``scripts/service/install_autostart.ps1``). Standard library
only (it must work even when the project's environment is broken). Operational messages only: it
never reads or mentions a signal, a price or a PnL.

It reports (after 2 consecutive failed checks, then at most hourly):
  * the service does not answer on its port, or answers an HTTP error;
  * ``/api/v2/health`` says DOWN;
  * the paper engine loop is WARN/FAIL (the in-process alerter lives in that loop, so when the loop
    is the thing that died only an outside observer can say so).
It announces recovery once. Credentials come from ``.env`` (``XAU_V2_TELEGRAM_BOT_TOKEN`` and
``XAU_V2_TELEGRAM_CHAT_ID``); without them it only writes its log.

    python scripts/external_watchdog.py [--dry-run] [--port 8200]
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "watchdog_state.json"
LOG = ROOT / "logs" / "external_watchdog.log"
FAILURES_BEFORE_ALERT = 2
RENOTIFY_SECONDS = 3600.0
TELEGRAM_API = "https://api.telegram.org"


def read_env(path: Path = ROOT / ".env") -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                out[key.strip()] = value.strip().strip("\"'")
    except OSError:
        pass
    return out


def check_health(port: int, timeout: float = 10.0) -> tuple[bool, str]:
    """(healthy, problem text). Unreachable, HTTP error, DOWN or a dead engine loop are problems."""
    url = f"http://127.0.0.1:{port}/api/v2/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - the local service
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return False, f"dịch vụ trả lỗi HTTP {exc.code}"
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
        return False, f"dịch vụ không phản hồi ({type(exc).__name__})"
    if body.get("status") == "DOWN":
        failing = [c.get("label") for c in body.get("checks", []) if c.get("state") == "FAIL"]
        return False, "dịch vụ báo DOWN: " + (", ".join(map(str, failing)) or "không rõ")
    for check in body.get("checks", []):
        if check.get("id") == "engine_loop" and check.get("state") in ("WARN", "FAIL"):
            return False, f"vòng nền PAPER {check['state']}: {check.get('detail', '')}"
    return True, ""


def send_telegram(token: str, chat_id: str, text: str, api: str = TELEGRAM_API) -> bool:
    body = json.dumps(
        {"chat_id": chat_id, "text": text[:3500], "disable_web_page_preview": True}
    ).encode()
    request = urllib.request.Request(  # noqa: S310
        f"{api}/bot{token}/sendMessage", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            return bool(json.loads(response.read().decode("utf-8")).get("ok") is True)
    except (urllib.error.URLError, OSError, ValueError):
        return False


def load_state(path: Path = STATE) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state: dict[str, object], path: Path = STATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    tmp.replace(path)


def step(  # noqa: PLR0913 - the whole decision, with everything injectable for tests
    state: dict[str, object], healthy: bool, problem: str, now: datetime, send, host: str
) -> list[str]:  # type: ignore[no-untyped-def]
    """Advance the failure counter and send at most one message; returns the messages sent."""
    sent: list[str] = []
    failures = int(state.get("failures", 0))  # type: ignore[call-overload]
    if healthy:
        if state.get("alerted_at"):
            since = datetime.fromisoformat(str(state["down_since"]))
            minutes = (now - since).total_seconds() / 60
            text = f"✅ XAU EDGE V2: dịch vụ hoạt động lại sau {minutes:.0f} phút (máy {host})"
            if send(text):
                sent.append(text)
            else:
                return sent  # keep the state: announce the recovery on the next run
        state.clear()
        state["failures"] = 0
        return sent
    failures += 1
    state["failures"] = failures
    state.setdefault("down_since", now.isoformat())
    state["problem"] = problem
    if failures < FAILURES_BEFORE_ALERT:
        return sent
    last = state.get("alerted_at")
    due = (
        last is None
        or (now - datetime.fromisoformat(str(last))).total_seconds() >= RENOTIFY_SECONDS
    )
    if due:
        since = datetime.fromisoformat(str(state["down_since"]))
        text = f"⛔ XAU EDGE V2: {problem} (từ {since:%H:%M} UTC, máy {host})"
        if send(text):
            state["alerted_at"] = now.isoformat()
            sent.append(text)
    return sent


def log(message: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now(UTC).isoformat()} {message}\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true", help="print the decision, send nothing")
    args = ap.parse_args()
    env = read_env()
    port = args.port or int(env.get("XAU_V2_PORT", "8200"))
    token, chat = env.get("XAU_V2_TELEGRAM_BOT_TOKEN"), env.get("XAU_V2_TELEGRAM_CHAT_ID")
    healthy, problem = check_health(port)

    def send(text: str) -> bool:
        if args.dry_run or not token or not chat:
            log(f"(not sent: {'dry run' if args.dry_run else 'no channel configured'}) {text}")
            return not args.dry_run and bool(token and chat)
        ok = send_telegram(token, chat, text)
        log(f"{'sent' if ok else 'SEND FAILED'}: {text}")
        return ok

    state = load_state()
    messages = step(state, healthy, problem, datetime.now(UTC), send, socket.gethostname())
    if not args.dry_run:
        save_state(state)
    print(
        json.dumps(
            {"healthy": healthy, "problem": problem, "sent": len(messages)}, ensure_ascii=True
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
