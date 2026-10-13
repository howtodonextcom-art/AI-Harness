# ADR-0026 (NHÁP): Một bộ não — `TradingSignal` → `OrderIntent` trực tiếp; bridge chỉ veto

Status: **SUPERSEDED** as the working copy — accepted text is `docs/decisions/0026-canonical-brain-direct-intent.md` (2026-10-11). Draft kept for the closed-loop rationale.

## Bối cảnh (đã kiểm 2026-10-11)
- Hai bộ não: Trading Core (`data/market` → `TradeEngine` → `TradingSignal` → `PaperDesk`) đang chạy PAPER; bot DEMO legacy (`data/raw` → `signals.engine` → `Signal` → `SignalBridge` → `OrderIntent` → executor) khoá, không chạy. Adapter `to_legacy_signal` chỉ có test (`trading/adapter.py`; importer duy nhất `tests/unit/trading/test_decision_levels_sizing.py`).
- **Bộ não thứ ba:** `serve_api.py:63-65` dựng `PaperTrader` legacy trên `/paper/*` từ `data/raw`.
- Downstream tính lại:
  - Bridge: BUY `entry = zone_mid + spread` (`execution/bridge.py:165`); baseline đã đặt entry = ask (`trading/baseline.py:336-338`); adapter đặt `entry_zone=(entry,entry)` (`adapter.py:63`) → **adapter route cộng spread hai lần trên BUY**.
  - Lot tính 3 lần, khác công thức: baseline `size_for_risk` 0,25% (`baseline.py:72,363`); PaperDesk tính lại trên quote live (`paper_desk.py:492-518`); RiskEngine 0,5% + `contract_size=100` (`risk/engine.py:31,40,148-157`) → lot màn hình và lot lệnh có thể lệch ~2×.
  - Fill drift: executor 30 điểm (`executor.py:110,308-309`); PaperDesk 0,25 × stop (`paper_desk.py:137,541-544`). Hold: bridge 300 phút (`bridge.py:60-61`) vs Trading Core 120 phút.
- Idempotence bridge theo `inputs_hash`/`signal_id` (`adapter.py:50,72`; `bridge.py:155-157`), không theo `setup_id`. `canonical-brain.md:75` giả định một intent / `setup_id` — bridge không làm vậy.
- `MarketStatus.UNKNOWN` coi là mở (`live_source.py:90-92`, `engine.py:225`).
- `TradingSignal` không bao giờ VALIDATED (`schema.py:158-160`); mọi BUY/SELL DEMO chỉ qua override ADR-0019.
- Harness so sánh quyết định A↔B (`scripts/decision_parity.py`) **chưa có**.

## Phương án (chấm mù rubric (a))
| Phương án | Reviewer kiến trúc | Reviewer rủi ro | Kết quả |
|---|---|---|---|
| P — adapter vào Signal cũ | 3,75 PASS (nhưng HIGH: double-spread + lot 3×) | 3,15 FAIL | Loại như đang viết |
| Q — không làm | 3,15 FAIL | 2,95 FAIL | Loại |
| R — intent trực tiếp | 3,90 FAIL (A2=3: thiếu RiskEngine + ExecutionSafety) | 3,30 FAIL (A2=3) | Loại như đang viết |
| **R đã sửa** (giữ RiskEngine/ExecutionSafety/lot_cap; tính lot trên equity broker) | kiến trúc: A2→5, ~4,40 | rủi ro: 3,55 PASS | **Chọn** |

Hai reviewer độc lập cùng hướng: **không đi đường adapter**; đi đường intent trực tiếp **và** giữ đủ cửa guard hiện có.

## Quyết định
1. `TradeEngine` là nơi duy nhất quyết định BUY/SELL/WAIT. Bot DEMO (khi mở) nhận `TradingSignal`, không gọi `generate_signal`.
2. Adapter mới: `intent_from_signal(TradingSignal) → OrderIntent` **sao chép** hướng, entry (ASK cho BUY, BID cho SELL, spread tính một lần), SL, TP, hạn giữ, expiry. **Không** tính lại hình học.
3. Lot **tính lại lúc tạo intent** trên equity tài khoản broker, cùng `size_for_risk` + symbol spec với PaperDesk. Lot và rủi ro sau khi tính lại được ghi log và hiện cạnh kế hoạch. `RiskEngine.evaluate` + `ExecutionSafety` + `lot_cap`/trần D2 = **veto và trần**, không phải nguồn giá.
4. Mọi intent vẫn đi qua: kill switch, evidence gate (ADR-0019), news, reconcile, expiry/staleness, `dry_run`. Không mở cửa thứ hai tới lệnh (`bridge.py:1`). Phạm vi hẹp hơn cần ADR.
5. Idempotence theo `setup_id` (một intent / setup). `UNKNOWN` thị trường = đóng.
6. Harness parity so **OrderIntent** (không so legacy `Signal`): side, `entry_reference`, SL, TP, lots, `max_hold_until`, expiry, fill-drift. Cổng: 0 lệch không giải thích được trên ≥ 1 tuần LIVE dry-run **và** độ phủ quyết định ≥ 95%.
7. `signals.engine` và các caller (`serve_api.py`, `api/service.py`, `current_signal.py`, `forward_test.py`, `execution/forward.py`, `demo_trader.py`) chỉ retire sau cổng parity. `/paper/*` legacy + `PaperTrader` retire cùng `/legacy`.
8. **Must not:** bỏ `dry_run`; bật cờ Demo/Funded; gửi lệnh.

## Thứ tự
Contract v2 (ADR-0028) → UNKNOWN=đóng → adapter intent + harness → dry-run 1 tuần → mới xét retire. Không làm song song với đổi alpha.

## Acceptance criteria
- AC-A1 **Must:** test FAIL nếu BUY intent có `entry_reference` ≠ ask (spread không cộng lần hai).
- AC-A2 **Must:** mọi intent đi qua `RiskEngine.evaluate`, `ExecutionSafety`, `lot_cap`, kill switch, reconcile, expiry/staleness.
- AC-A3 **Must:** lot intent = `size_for_risk(broker_equity, risk_pct, quote, sl)` — test với equity paper ≠ equity demo.
- AC-A4 **Must:** một `setup_id` → tối đa một intent được chấp nhận.
- AC-A5 **Must:** `UNKNOWN` → không mở, không coi là phiên mở (test).
- AC-A6 **Must:** harness OrderIntent 0 lệch trên replay xác định + lệnh `scripts/decision_parity.py` (chỉ đọc telemetry).
- AC-A7 **Must not:** retire `signals.engine` / bridge trước cổng parity; không thêm đường lệnh bỏ `dry_run`.
