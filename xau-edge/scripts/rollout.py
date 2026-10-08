"""Operator CLI for the funded rollout tiers (ADR-0020, T4.3). Never touches the MT5 terminal.

    uv run python scripts/rollout.py status
    uv run python scripts/rollout.py promote --confirm

``status`` shows the tier in force, its limits, the evidence label and which exit criteria are
met or unmet. ``promote`` moves up exactly ONE tier, only with ``--confirm`` and only when the
criteria are met; it writes the funded journal and sends the ``ROLLOUT_TIER_CHANGED`` alert. There
is no option to skip a tier or force a promotion; an UNVALIDATED strategy stops at tier 2.
Restart the bot afterwards: it reads the tier at start.

Exit codes: 0 done; 2 promotion refused (criteria unmet or no --confirm); 3 configuration error.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from xau_edge.config import Settings
from xau_edge.execution.journal import ExecutionJournal
from xau_edge.execution.safety import assert_live_trading_disabled
from xau_edge.execution.state import ExecutionState
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.funded.operator import format_report, promote, rollout_report
from xau_edge.funded.plan import evidence_label
from xau_edge.funded.rollout import RolloutController, RolloutError, load_rollout
from xau_edge.funded.wiring import alert_fn, strategy_validated
from xau_edge.ops.notifier import build_dispatcher
from xau_edge.ops.settings import OpsSettings
from xau_edge.signals.strategy_registry import default_strategy

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_CONFIG = 3


def build_parser() -> argparse.ArgumentParser:
    """``status`` or ``promote --confirm``; nothing else."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="show the tier, its limits and the promotion criteria")
    up = sub.add_parser("promote", help="move up exactly one tier when the criteria are met")
    up.add_argument("--confirm", action="store_true", help="required: I have read the status")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    assert_live_trading_disabled()
    settings = Settings()
    try:
        config = load_rollout(settings.funded_rollout_path)
    except (OSError, ValueError) as exc:
        print(f"rollout file unreadable: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    validated = strategy_validated(ExperimentRegistry("experiments/runs"), default_strategy())
    label = evidence_label(settings, validated=validated)
    controller = RolloutController(
        ExecutionState(settings.funded_state_path), config, validated=validated
    )
    now = datetime.now(UTC)
    if args.command == "status":
        print(format_report(rollout_report(controller, now, evidence_label=label)))
        return EXIT_OK
    journal = ExecutionJournal(settings.funded_journal_path)
    dispatcher = build_dispatcher(
        OpsSettings(), fallback_path=settings.data_dir / "execution" / "alerts.jsonl"
    )
    try:
        decision = promote(
            controller,
            journal,
            alert_fn(dispatcher),
            now,
            confirm=args.confirm,
            evidence_label=label,
        )
    except RolloutError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    print(f"promoted to tier {decision.target}; restart the bot to apply it")
    print(format_report(rollout_report(controller, now, evidence_label=label)))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
