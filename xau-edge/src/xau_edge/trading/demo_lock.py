"""Why DEMO execution is locked, in words the owner can act on (booleans only, no secrets).

This module answers a question; it enables nothing. The paper desk never sends an order. Credentials
are read only to learn whether they EXIST: no value is returned, logged or shown.
"""

from __future__ import annotations

from typing import Any

from xau_edge.brokers.mt5_demo.connect import Mt5TradeSettings
from xau_edge.config import Settings

HOW_TO_UNLOCK = (
    "See docs/PAPER_TRADING_WORKFLOW.md section 'Demo execution contract'. Demo execution is a "
    "separate sprint: it needs your trade password and explicit flags, and is NOT part of "
    "this desk."
)


def demo_lock_status(collector: dict[str, Any] | None) -> dict[str, Any]:
    """LOCKED with every reason, or UNLOCKED_BY_CONFIG (still nothing is sent by this desk)."""
    reasons: list[dict[str, str]] = []
    if collector is not None and collector.get("account_trade_allowed") is False:
        reasons.append(
            {
                "code": "TRADING_NOT_ALLOWED",
                "why": "the terminal is logged in with the investor (read-only) password, "
                "so the account cannot trade",
            }
        )
    try:
        creds = Mt5TradeSettings()
        has_password = creds.trade_password is not None and bool(
            creds.trade_password.get_secret_value()
        )
    except Exception:
        has_password = False
    if not has_password:
        reasons.append(
            {
                "code": "MT5_TRADE_PASSWORD_MISSING",
                "why": "no MT5 trade password is configured (MT5_TRADE_PASSWORD)",
            }
        )
    try:
        settings = Settings()
        enabled, dry_run = settings.enable_demo_trading, settings.demo_dry_run
        accounts = settings.demo_allowed_accounts.strip()
    except Exception:
        enabled, dry_run, accounts = False, True, ""
    if not enabled:
        reasons.append(
            {"code": "DEMO_TRADING_DISABLED", "why": "XAU_EDGE_ENABLE_DEMO_TRADING is false"}
        )
    if dry_run:
        reasons.append(
            {
                "code": "DEMO_DRY_RUN",
                "why": "XAU_EDGE_DEMO_DRY_RUN is true: the bot only logs decisions",
            }
        )
    if not accounts:
        reasons.append(
            {
                "code": "DEMO_ALLOWED_ACCOUNTS_EMPTY",
                "why": "no account is whitelisted for demo orders",
            }
        )
    return {
        "status": "LOCKED" if reasons else "UNLOCKED_BY_CONFIG",
        "reasons": reasons,
        "paper_desk_sends_orders": False,
        "how_to_unlock": HOW_TO_UNLOCK,
    }
