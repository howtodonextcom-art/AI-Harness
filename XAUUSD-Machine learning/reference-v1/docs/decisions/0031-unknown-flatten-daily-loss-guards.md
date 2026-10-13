# ADR-0031: UNKNOWN fail-closed; wire flatten_required and daily_loss_guard

Status: **ACCEPTED** (2026-10-11)

## Context

Phase 1 audit found three safety gaps on the paper path:

- `LiveSnapshot.market_open` treated `MarketStatus.UNKNOWN` as open (`live_source.py`).
- `TradeGovernor.flatten_required` had no production caller.
- `ManagerContext.daily_loss_guard` defaulted false and was never set by `PaperDesk`.

New BUY/SELL on an unknown calendar is a fail-open. Flatten at the emergency daily-loss
floor never closed the paper position. The daily-loss *stop* already refused new opens
via `governor.check` (`DAILY_LIMIT`).

## Decision

1. **UNKNOWN is not tradable.** `market_open` is true only for `MarketStatus.OPEN`.
   The engine emits `MARKET_UNKNOWN` (distinct from `MARKET_CLOSED` / `STALE` /
   `UNAVAILABLE`). `decide()` returns WAIT + `UNKNOWN_STATE`. Hero state is `UNKNOWN`;
   action is `UNAVAILABLE`. UI may still display status `UNKNOWN`.
2. **`flatten_required`** (loss ≥ `daily_loss_flatten_pct` of day-start equity) sets
   `ManagerContext.daily_loss_guard` on every paper bar. The manager closes with
   `DAILY_LOSS_GUARD` and the desk journals that reason. No broker send.
3. **`daily_loss_guard` (stop)** remains `governor.check` → `DAILY_LIMIT` for new
   opens. The API `desk.limits` now exposes `daily_loss_guard` and `flatten_required`
   so the UI can explain the block. Thresholds stay at the existing `GovernorConfig`
   defaults (not invented FTMO numbers).
4. Break-even / trailing / partial exit stay OFF.

## Consequences

- Calendar UNKNOWN no longer authorizes entry.
- Emergency flatten is paper-only and deterministic.
- Demo/Funded execution stays locked.

## Tests

- `tests/unit/trading/test_unknown_fail_closed.py`
- `tests/unit/trading/test_desk_guards.py`
