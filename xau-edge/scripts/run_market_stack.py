"""Supervise the market data stack: collector, API and (optionally) the dashboard.

    uv run python scripts/run_market_stack.py [--no-api] [--dashboard]

The ONE supervisor of these processes: it restarts a dead child with backoff, writes PID and
heartbeat files under ``data/run/`` and rotating logs under ``data/logs/``. Start it with
``scripts/start_market_stack.ps1`` (or the logon task from ``install_market_autostart.ps1``); stop
it with ``scripts/stop_market_stack.ps1``. It never starts or stops the MT5 terminal.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.ops.supervisor import ChildSpec, Supervisor  # noqa: E402


def python_argv() -> list[str]:
    venv = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv.exists():
        return [str(venv)]
    unix = ROOT / ".venv" / "bin" / "python"
    return [str(unix)] if unix.exists() else [sys.executable]


def build_children(*, api: bool, dashboard: bool, port: int) -> list[ChildSpec]:
    py = python_argv()
    children = [ChildSpec("collector", [*py, "scripts/run_market_collector.py"], ROOT)]
    if api:
        children.append(ChildSpec("api", [*py, "scripts/serve_api.py", "--port", str(port)], ROOT))
    if dashboard:
        npx = shutil.which("npx") or "npx"
        children.append(
            ChildSpec(
                "dashboard",
                [npx, "next", "start", "-p", "3000", "-H", "127.0.0.1"],
                ROOT / "apps" / "dashboard",
            )
        )
    return children


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-api", action="store_true")
    parser.add_argument("--dashboard", action="store_true")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    supervisor = Supervisor(
        build_children(api=not args.no_api, dashboard=args.dashboard, port=args.port),
        run_dir=ROOT / "data" / "run",
        log_dir=ROOT / "data" / "logs",
    )
    code = supervisor.run()
    if code == 3:
        print("the market stack supervisor is already running")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
