"""Which account is this, and may the bot act on it in this mode? (ADR-0020)

The terminal's ``trade_mode`` is NOT used to tell demo from funded: FTMO may report DEMO for a
funded account too. The mode comes from the configuration, and the account is identified by
login, server and the profile of rules in force, all checked against separate whitelists:

* dry-run and demo mode refuse a login that is on the funded whitelist;
* funded mode refuses a login that is on the demo whitelist, or on neither;
* the server name must be on the mode's server whitelist when one is configured (always for
  funded);
* the account number is only ever printed as its last three digits.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from xau_edge.config import Settings


class RunMode(StrEnum):
    """What the process is allowed to do."""

    DRY_RUN = "DRY-RUN"
    DEMO = "DEMO"
    FUNDED = "FUNDED"


class ModeError(RuntimeError):
    """The account or the confirmation does not match the requested mode; nothing may run."""


@dataclass(frozen=True)
class AccountIdentity:
    """What the terminal says about the logged-in account."""

    login: str
    server: str
    trade_mode_demo: bool


def _csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def requested_mode(settings: Settings) -> RunMode:
    """The mode the configuration asks for (funded wins only when its own flag is set)."""
    if settings.enable_funded_trading:
        return RunMode.FUNDED
    if settings.enable_demo_trading and not settings.demo_dry_run:
        return RunMode.DEMO
    return RunMode.DRY_RUN


def mask_login(login: str) -> str:
    """The account number reduced to its last three digits."""
    return "***" + login[-3:] if len(login) > 3 else "***"


def resolve_mode(settings: Settings, identity: AccountIdentity) -> RunMode:
    """The mode to run in, or ``ModeError`` if the account does not fit it."""
    mode = requested_mode(settings)
    demo_accounts = _csv(settings.demo_allowed_accounts)
    funded_accounts = _csv(settings.funded_allowed_accounts)
    demo_servers = _csv(settings.demo_allowed_servers)
    funded_servers = _csv(settings.funded_allowed_servers)
    on_demo = identity.login in demo_accounts
    on_funded = identity.login in funded_accounts
    if mode is RunMode.FUNDED:
        if on_demo:
            msg = "a DEMO-whitelisted account was seen in FUNDED mode"
            raise ModeError(msg)
        if not on_funded:
            msg = "the logged-in account is not on the funded whitelist"
            raise ModeError(msg)
        if identity.server not in funded_servers:
            msg = "the logged-in server is not on the funded server whitelist"
            raise ModeError(msg)
        return mode
    if on_funded:
        msg = f"a FUNDED-whitelisted account was seen in {mode.value} mode; refusing"
        raise ModeError(msg)
    if mode is RunMode.DEMO and not on_demo:
        msg = "the logged-in account is not on the demo whitelist"
        raise ModeError(msg)
    if demo_servers and identity.server not in demo_servers:
        msg = "the logged-in server is not on the demo server whitelist"
        raise ModeError(msg)
    return mode


def banner(mode: RunMode, identity: AccountIdentity, profile: str) -> str:
    """The start-up line: mode, server, trade_mode, rules profile, masked account."""
    trade_mode = "DEMO" if identity.trade_mode_demo else "NOT-DEMO"
    return (
        f"MODE={mode.value} server={identity.server} trade_mode={trade_mode} "
        f"profile={profile} account={mask_login(identity.login)}"
    )


def require_confirmation(mode: RunMode, confirmed: str | None) -> None:
    """Order-sending modes need ``--confirm-mode <MODE>`` on the command line."""
    if mode is RunMode.DRY_RUN:
        return
    if (confirmed or "").upper() != mode.value:
        msg = f"{mode.value} mode needs the command-line flag --confirm-mode {mode.value}"
        raise ModeError(msg)
