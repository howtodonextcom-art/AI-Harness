"""Funded-account rules with a verification status per rule (ADR-0020, decision D6).

Each rule in ``configs/prop/ftmo_funded.yaml`` carries a status (``verified_official``,
``secondary`` or ``unverified``), a ``must_verify`` flag, the date it was verified and its source.
Funded trading is refused while ANY rule marked ``must_verify`` is not ``verified_official`` with a
date and a source. The owner verifies the rules with FTMO and edits the file; the program never
marks a rule verified by itself.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from xau_edge.risk.prop_rules import PropProfile

RuleStatus = Literal["verified_official", "secondary", "unverified"]


class FundedRulesNotVerifiedError(RuntimeError):
    """One or more rules marked ``must_verify`` are not verified; funded trading is refused."""


class FundedRule(BaseModel):
    """One rule: its value (if numeric/structured), status, flag, date and source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: RuleStatus = "unverified"
    must_verify: bool = True
    verified_on: date | None = None
    source: str | None = None
    value: Any = None
    note: str = ""

    @property
    def satisfied(self) -> bool:
        """True when the rule is verified official, dated and sourced."""
        return (
            self.status == "verified_official"
            and self.verified_on is not None
            and bool(self.source and self.source.strip())
        )


class FundedRules(BaseModel):
    """The whole file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    rules: dict[str, FundedRule] = Field(default_factory=dict)

    def pending(self) -> list[str]:
        """Names of the ``must_verify`` rules that are not yet verified (sorted)."""
        return sorted(k for k, r in self.rules.items() if r.must_verify and not r.satisfied)

    def require_verified(self) -> None:
        """Raise unless every ``must_verify`` rule is verified."""
        pending = self.pending()
        if pending:
            msg = (
                "funded trading is refused: these rules are marked must_verify but are not "
                f"verified_official with a date and a source: {', '.join(pending)}"
            )
            raise FundedRulesNotVerifiedError(msg)

    def to_prop_profile(self) -> PropProfile:
        """The loss-limit profile the risk engine uses (values come from this file only)."""
        try:
            daily = float(self.rules["daily_loss_limit_pct"].value)
            maximum = float(self.rules["max_loss_limit_pct"].value)
            kind = str(self.rules["max_loss_kind"].value)
        except (KeyError, TypeError, ValueError) as exc:
            msg = "the funded rules need daily_loss_limit_pct, max_loss_limit_pct, max_loss_kind"
            raise ValueError(msg) from exc
        dates = [r.verified_on for r in self.rules.values() if r.verified_on is not None]
        return PropProfile(
            name=self.name,
            source="configs/prop/ftmo_funded.yaml",
            verified_on=max(dates) if dates else date(1970, 1, 1),
            daily_loss_limit_pct=daily,
            max_loss_limit_pct=maximum,
            max_loss_kind=kind,
            internal_buffer_pct_of_limit=float(
                self.rules.get("internal_buffer_pct_of_limit", FundedRule(value=40.0)).value
            ),
            ea_restrictions=self.rules["ea_automated_trading"].status
            if "ea_automated_trading" in self.rules
            else "unverified",
        )


def load_funded_rules(path: Path | str) -> FundedRules:
    """Read and validate the funded rules file."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{path}: the funded rules must be a YAML mapping"
        raise ValueError(msg)
    return FundedRules.model_validate(raw)
