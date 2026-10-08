"""Application settings. Live trading is hard-disabled in this release."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _csv(value: str) -> set[str]:
    """Comma separated whitelist -> set of non-empty trimmed items."""
    return {item.strip() for item in value.split(",") if item.strip()}


class Settings(BaseSettings):
    """Process-wide settings, read from ``XAU_EDGE_*`` environment variables or ``.env``.

    Instances are immutable and re-validated on every copy, so the live-trading guard holds
    after construction too (assignment and ``model_copy(update=...)`` are both refused). It
    stops accidental or careless enabling; code that deliberately bypasses pydantic
    (``model_construct``, ``object.__setattr__``) is out of scope, so any future execution entry
    point must re-check the flag itself rather than trust this object.
    """

    model_config = SettingsConfigDict(
        env_prefix="XAU_EDGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        validate_assignment=True,
    )

    enable_live_trading: bool = False
    enable_demo_trading: bool = False
    demo_dry_run: bool = True
    demo_smoke: bool = False
    demo_deviation_points: int = Field(default=60, ge=0, le=100)
    demo_allowed_accounts: str = ""
    demo_allowed_symbols: str = "XAUUSD"
    demo_magic: int | None = None
    demo_max_lots: float = Field(default=1.0, gt=0, le=5.0)
    demo_max_orders_per_day: int = 1
    demo_initial_capital: float | None = Field(default=None, gt=0)
    demo_state_path: Path = Path("data/execution/state.sqlite")
    demo_journal_path: Path = Path("data/execution/journal.jsonl")
    demo_allowed_servers: str = ""
    enable_funded_trading: bool = False
    funded_allowed_accounts: str = ""
    funded_allowed_servers: str = ""
    funded_magic: int | None = None
    funded_initial_capital: float | None = Field(default=None, gt=0)
    funded_max_lots: float = Field(default=1.0, gt=0, le=5.0)
    funded_risk_pct: float = Field(default=0.25, gt=0, le=0.25)
    """Per-trade risk ceiling of the owner-override (UNVALIDATED) path; not raisable by config."""
    funded_validated_risk_pct: float | None = Field(default=None, gt=0, le=1.0)
    funded_allow_unvalidated: bool = False
    funded_strategy_id: str = ""
    funded_profile_path: Path = Path("configs/prop/ftmo_funded.yaml")
    funded_rollout_path: Path = Path("configs/execution/rollout.yaml")
    funded_state_path: Path = Path("data/execution/funded_state.sqlite")
    funded_journal_path: Path = Path("data/execution/funded_journal.jsonl")
    news_calendar_path: Path | None = None
    data_dir: Path = Path("data")
    log_level: str = "INFO"

    @field_validator("enable_live_trading")
    @classmethod
    def _live_trading_disabled(cls, value: bool) -> bool:
        if value:
            msg = (
                "Live trading is not implemented in this release; "
                "XAU_EDGE_ENABLE_LIVE_TRADING must remain false"
            )
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _demo_execution_requires_explicit_guards(self) -> Self:
        if self.demo_smoke and not self.enable_demo_trading:
            msg = "XAU_EDGE_DEMO_SMOKE requires XAU_EDGE_ENABLE_DEMO_TRADING"
            raise ValueError(msg)
        if (self.enable_demo_trading and not self.demo_dry_run) or self.demo_smoke:
            missing: list[str] = []
            if not self.demo_allowed_accounts.strip():
                missing.append("XAU_EDGE_DEMO_ALLOWED_ACCOUNTS")
            if self.demo_magic is None:
                missing.append("XAU_EDGE_DEMO_MAGIC")
            if self.demo_initial_capital is None:
                missing.append("XAU_EDGE_DEMO_INITIAL_CAPITAL")
            if missing:
                joined = ", ".join(missing)
                msg = f"demo execution requires explicit guard setting(s): {joined}"
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _modes_and_accounts_are_separate(self) -> Self:
        """Demo and funded stay apart: exclusive flags, disjoint whitelists, explicit guards."""
        demo = _csv(self.demo_allowed_accounts)
        funded = _csv(self.funded_allowed_accounts)
        if demo & funded:
            msg = "the demo and funded account whitelists must not share an account"
            raise ValueError(msg)
        if self.enable_funded_trading and self.enable_demo_trading:
            msg = (
                "XAU_EDGE_ENABLE_FUNDED_TRADING and XAU_EDGE_ENABLE_DEMO_TRADING exclude each other"
            )
            raise ValueError(msg)
        if self.enable_funded_trading:
            missing = [
                name
                for name, ok in (
                    ("XAU_EDGE_FUNDED_ALLOWED_ACCOUNTS", bool(funded)),
                    ("XAU_EDGE_FUNDED_ALLOWED_SERVERS", bool(_csv(self.funded_allowed_servers))),
                    ("XAU_EDGE_FUNDED_MAGIC", self.funded_magic is not None),
                    ("XAU_EDGE_FUNDED_INITIAL_CAPITAL", self.funded_initial_capital is not None),
                )
                if not ok
            ]
            if missing:
                msg = f"funded execution requires explicit setting(s): {', '.join(missing)}"
                raise ValueError(msg)
        demo_files = {self.demo_state_path.resolve(), self.demo_journal_path.resolve()}
        if {self.funded_state_path.resolve(), self.funded_journal_path.resolve()} & demo_files:
            msg = "the funded state and journal files must differ from the demo ones"
            raise ValueError(msg)
        if self.funded_allow_unvalidated and not (
            self.enable_funded_trading and self.funded_strategy_id.strip()
        ):
            msg = (
                "XAU_EDGE_FUNDED_ALLOW_UNVALIDATED needs XAU_EDGE_ENABLE_FUNDED_TRADING and a "
                "specific XAU_EDGE_FUNDED_STRATEGY_ID"
            )
            raise ValueError(msg)
        return self

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> Self:
        """Copy with ``update`` applied *and validated* (pydantic's default skips validation)."""
        unknown = set(update or {}) - set(type(self).model_fields)
        if unknown:
            msg = f"unknown setting(s) in update: {sorted(unknown)}"
            raise ValueError(msg)
        data = self.model_dump()
        data.update(update or {})
        return type(self)(_env_file=None, **data)
