"""Build the production control service (real files, real terminal probe, real NSSM lookup)."""

from __future__ import annotations

import shutil
from datetime import timedelta
from pathlib import Path

from xau_edge.brokers.mt5_demo.connect import Mt5TradeSettings
from xau_edge.config import Settings
from xau_edge.control.jobs import JobManager, RateLimiter, RateRule
from xau_edge.control.paths import ControlPaths
from xau_edge.control.process import ProcessManager
from xau_edge.control.security import generate_token, write_token
from xau_edge.control.service import ControlConfig, ControlDeps, ControlService
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.funded.wiring import strategy_validated
from xau_edge.ops.clock_check import check_clock
from xau_edge.ops.settings import OpsSettings
from xau_edge.signals.strategy_registry import default_strategy

SMOKE_RULE = RateRule(min_interval=timedelta(minutes=10), max_per_day=5)
FLATTEN_RULE = RateRule(min_interval=timedelta(seconds=30))


def build_control_service(
    *, repo_root: Path, terminal_path: str, data_dir: Path | None = None
) -> ControlService:
    """Everything wired for ``scripts/serve_api.py``; writes a fresh token file."""
    env_file = repo_root / ".env"
    paths = ControlPaths(data_dir or repo_root / "data")
    ops = OpsSettings(_env_file=env_file)
    servers = [s.strip() for s in ops.ntp_servers.split(",") if s.strip()]
    deps = ControlDeps(
        load_settings=lambda: Settings(_env_file=env_file),
        load_credentials=lambda: Mt5TradeSettings(_env_file=env_file),
        clock_offset=lambda: check_clock(servers).offset_seconds,
        max_clock_offset=ops.ntp_max_offset_seconds,
        strategy_check=lambda: strategy_validated(
            ExperimentRegistry(repo_root / "experiments" / "runs"), default_strategy()
        ),
    )
    process = ProcessManager(
        paths, repo_root=repo_root, terminal_path=terminal_path, nssm=shutil.which("nssm")
    )
    token = generate_token()
    protected = write_token(paths.token, token)
    limiter = RateLimiter(paths.limits, {"smoke": SMOKE_RULE, "flatten": FLATTEN_RULE})
    config = ControlConfig(
        repo_root=repo_root, terminal_path=terminal_path, data_dir=paths.data_dir, env_file=env_file
    )
    return ControlService(
        config,
        deps,
        process=process,
        jobs=JobManager(),
        limiter=limiter,
        token=token,
        token_protected=protected,
    )
