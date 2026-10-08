"""The one door to an order-sending mode: every condition, in one place, all required (T4.1, T4.6).

``authorize_start`` returns the run mode only when the account fits the mode (whitelists, server),
the confirmation flag was given on the command line, and, for funded, every ``must_verify`` rule is
verified. Anything else raises and the process must not send an order.
"""

from __future__ import annotations

from xau_edge.config import Settings
from xau_edge.funded.identity import (
    AccountIdentity,
    ModeError,
    RunMode,
    require_confirmation,
    resolve_mode,
)
from xau_edge.funded.rules import FundedRules


def authorize_start(
    settings: Settings,
    identity: AccountIdentity,
    *,
    confirm: str | None,
    rules: FundedRules | None,
) -> RunMode:
    """The mode to run in, or an exception: account, server, rules and confirmation all checked."""
    mode = resolve_mode(settings, identity)
    if mode is RunMode.FUNDED:
        if rules is None:
            msg = "funded mode needs the funded rules file (configs/prop/ftmo_funded.yaml)"
            raise ModeError(msg)
        rules.require_verified()
    require_confirmation(mode, confirm)
    return mode
