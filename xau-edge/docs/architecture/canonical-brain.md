# BRAIN-01: một bộ não chính tắc (thiết kế, KHÔNG kích hoạt thực thi)

> Ngày: 2026-10-11. Tài liệu THIẾT KẾ. Không đổi hành vi, không bật DEMO/FUNDED, không đổi ngưỡng hay phiên bản
> chiến lược (mặc định `v1.1.0`). Mọi mệnh đề "hiện trạng" dưới đây được kiểm tra trong mã nguồn ngày 2026-10-11.

## 1. Hiện trạng đã kiểm chứng: HAI bộ não, không phải một

| | Trading Core (`xau_edge/trading/`) | Bot DEMO legacy (`signals/`, `strategies/`, `execution/`) |
|---|---|---|
| Ai quyết định | `TradeEngine` → `baseline.py` (`xau_mtf_baseline` v1.1.0) | `signals.engine.generate_signal` + `strategy_registry` (`scripts/demo_trader.py:102,143`) |
| Đối tượng quyết định | `TradingSignal` (`trading/schema.py`) | `Signal` (`signals/schema.py`) |
| Dùng ở đâu | `/trade`, bàn PAPER, telemetry, alert | `scripts/demo_trader.py`, `BotApp`, `SignalBridge`, executor MT5 DEMO |
| Đường tới lệnh | `PaperDesk` (broker giả lập riêng, không tới MT5) | `SignalBridge` → `OrderIntent` → `Mt5DemoExecutor` (bị khoá theo thiết kế) |
| Dữ liệu | bộ nhớ nến `data/market` do collector ghi | `MarketFrames` tải riêng từ MT5/RawStore |
| Bằng chứng | forward F0 (chưa thấy setup LIVE) | không có edge VALIDATED nên luôn `WAIT` |

Cầu nối `trading/adapter.py::to_legacy_signal` ĐÃ có (chỉ được test trong
`test_decision_levels_sizing.py`) nhưng KHÔNG nối vào `demo_trader.py`: bot DEMO không bao giờ chạy cùng bộ não với màn hình
`/trade`. Hệ quả: một setup trên `/trade` KHÔNG có nghĩa bot DEMO sẽ hành động giống vậy, và ngược lại.

## 2. Kiến trúc đích

```
market data (collector) ──► TradeEngine ──► TradingSignal (CANONICAL, một nơi duy nhất quyết định)
                                              │
                         ┌────────────────────┼──────────────────────────┐
                         ▼                    ▼                          ▼
                  Paper adapter         Demo adapter (KHOÁ)        Funded adapter (KHOÁ)
                  PaperDesk             SignalBridge→OrderIntent     không tồn tại
                  (ĐANG CHẠY)           →Mt5DemoExecutor             (cần quyết định riêng)
                         │                    │
                         ▼                    ▼
                    Execution Intent  ◄── cùng một định nghĩa
                    (broker-neutral, idempotent, không nhận tham số từ trình duyệt)
```

Nguyên tắc:
1. **Một nơi quyết định.** `TradeEngine` là bộ não duy nhất; bot DEMO nhận `TradingSignal` (qua adapter), không tự tạo `Signal`.
2. **Intent trung lập broker.** `OrderIntent` (`execution/order_intent.py`) đã đúng vai trò: id xác định, không bí mật,
   không tham số từ client. Giữ nguyên.
3. **Adapter chỉ dịch, không quyết định lại.** Không adapter nào được đổi hướng, SL, TP, lot sau khi `TradingSignal` đã ký.
4. **Khoá theo tầng.** Paper: mở. Demo: khoá bằng `demo_lock` + cờ cấu hình + bridge. Funded: không có adapter; muốn có
   phải qua quyết định riêng (`XAU_EDGE_ENABLE_FUNDED_TRADING` vẫn tắt).

## 3. Hợp đồng `TradingSignal` chính tắc

Đã có trong `trading/schema.py` (xác định, kiểm tra tính nhất quán bằng `model_validator`). Nhóm trường:

| Nhóm | Trường (hiện có) | Ghi chú |
|---|---|---|
| Định danh | `signal_id` (hash của đầu vào), `setup_id` (ổn định theo nến trigger M5), `decision_id` (bí danh) | cùng nến đóng ⇒ cùng id |
| Quyết định | `decision` (BUY/SELL/WAIT), `refusal_reasons`, `reasons`, `warnings`, `invalidation` | WAIT bắt buộc có lý do; BUY/SELL cấm lý do từ chối |
| Chiến lược | `strategy_id`, `strategy_version`, `evidence_status` (không bao giờ VALIDATED cho baseline), `code_version`, `inputs_hash` | |
| Ngữ cảnh | `h4_bias`, `h1_bias`, `m30_state`, `m15_setup`, `m5_trigger`, `m1_execution_state`, `market_regime`, `volatility_regime`, `spread_state`, `volume_state/type`, `news_state` | |
| Mức giá | `entry_type`, `entry_price`, `stop_loss`, `take_profit`, `take_profit_2`, `risk_reward`, `required_win_rate`, `stop_model`, `entry_quality` | ràng buộc hình học BUY: SL<entry<TP; SELL ngược lại |
| Rủi ro | `risk_pct`, `risk_amount`, `position_size` | kích thước do `risk_calc`/`sizing` tính, không do client |
| Thời gian | `timestamp`, `generated_at`, `signal_expiry`, `data_age_seconds`, `bid`, `ask`, `spread` | BUY/SELL bắt buộc có hạn dùng |

**Cần thêm khi triển khai (đề xuất, chưa làm):** `schema_version` (số nguyên, tăng khi đổi trường), `source_mode`
(LIVE/ACCEPTANCE_REPLAY) và `news_status` chi tiết (6 trạng thái của NEWS-01) để một nơi thực thi nào cũng thấy tín hiệu
đến từ đâu và tin có được xác minh không. Không đổi trường nào đang dùng; chỉ thêm tuỳ chọn có mặc định.

## 4. Decision-parity harness (thiết kế)

Mục tiêu: chứng minh hai đường (PAPER và DEMO-dry-run) nhận CÙNG quyết định trên CÙNG dữ liệu.

* Đầu vào: một dãy thời điểm quyết định `T` (từ replay `AcceptanceWorld` hoặc từ telemetry LIVE đã ghi: `m1_bar`, `run`).
* Đường A: `TradeEngine.step(t)` → `TradingSignal`.
* Đường B (khi nối adapter): `to_legacy_signal(TradingSignal)` → `SignalBridge` ở chế độ **dry-run** (đã có `DryRunCycle`).
* Khẳng định (mỗi `t`): (1) hướng giống nhau: `TradingSignal.decision` BUY/SELL phải bằng `Signal.candidate_direction`
  (adapter CỐ Ý đặt `direction=WAIT` + `NO_VALIDATED_EDGE` cho mọi BUY/SELL: đây là cổng bằng chứng ADR-0019, bridge từ chối nếu
  không có override tường minh); (2) `entry/SL/TP1/TP2/RR/expiry` bằng nhau; (3) lý do từ chối: ánh xạ hiện là HÀM RIÊNG PHẦN
  (7 lý do rơi vào `EDGE_INSUFFICIENT`: `NO_DIRECTION`, `NO_SETUP`, `TOO_CLOSE_TO_RESISTANCE`, `TOO_CLOSE_TO_SUPPORT`,
  `RISK_LIMIT`, `DAILY_LIMIT`, `COOLDOWN`), nên harness phải báo từng lý do bị gộp thay vì coi là khớp, và triển khai thật phải
  bổ sung `NoTradeReason` tương ứng hoặc ghi nhận mất thông tin; (4) `signal_id` = `inputs_hash`; (5) cùng `setup_id` bridge
  chỉ tạo MỘT intent (idempotence).
* Báo cáo: số `t` so sánh, số khác biệt theo lớp, danh sách `t` lệch. Cổng: 0 khác biệt trên ≥ 1 tuần dữ liệu LIVE.
* Chạy ở đâu: unit (replay nhỏ, deterministic) + một lệnh `scripts/decision_parity.py` đọc telemetry thật (chỉ đọc).

## 5. Phân loại mã legacy (kế hoạch di chuyển)

| Thành phần | Quyết định | Lý do |
|---|---|---|
| `trading/*` (engine, baseline, paper_desk, position_manager, governor) | **KEEP** | bộ não và bàn PAPER chính tắc |
| `trading/adapter.py` | **ADAPT** | nối vào bot DEMO thay cho `generate_signal`; thêm test parity |
| `execution/order_intent.py`, `bridge.py`, `safety.py`, `guards.py`, `state.py`, `reconcile.py`, `override.py` | **KEEP** | cửa duy nhất tới lệnh; đã có idempotence, kill switch, ngân sách request |
| `brokers/mt5_demo/*` | **KEEP (khoá)** | executor DEMO; chỉ mở khi qua cổng ở mục 6 |
| `execution/paper.py`, `execution/trader.py` (paper trader legacy) | **DEPRECATE** | `PaperDesk` thay thế; giữ tới khi bot DEMO không còn dùng |
| `signals/engine.py`, `signals/decision.py`, `signals/strategy_registry.py`, `signals/expected_value.py` | **ADAPT → DEPRECATE** | không còn là nơi quyết định; `Signal` chỉ còn là định dạng đầu vào của bridge |
| `strategies/baselines.py`, `strategies/pattern.py`, `strategies/edge_program.py` | **KEEP cho research** | dùng cho nghiên cứu/đánh giá, không dùng để ra lệnh |
| `scripts/demo_trader.py::generate_signal_for` | **DELETE LATER** | thay bằng `TradeEngine` qua adapter sau khi parity đạt |
| `trading/replay.py`, `acceptance.py` | **KEEP** | nguồn của parity và goldens |

"DELETE LATER" chỉ sau khi: parity 0 khác biệt, bot DEMO chạy dry-run ≥ 1 tuần bằng bộ não chính tắc, và test legacy
tương ứng được chuyển sang adapter.

## 6. Cổng chuẩn bị DEMO (checklist, chưa mở)

Tất cả phải đúng và có bằng chứng ghi trong `docs/reports/`:

1. Bot DEMO chạy dry-run bằng `TradingSignal` (không còn `generate_signal`), parity 0 khác biệt ≥ 1 tuần LIVE.
2. Độ phủ quyết định ≥ 95% trong cùng thời gian (TELEMETRY-01: `decision_coverage.complete`).
3. Dữ liệu: parity nến 0 chênh lệch không giải thích được (DATA-01), ổ đĩa không CRITICAL, collector heartbeat tươi.
4. Tin tức: lịch `CLEAR/BLOCKED` tươi (không `STALE/ERROR`) trong suốt thời gian chạy (NEWS-01).
5. Forward F2 trở lên trên bàn PAPER (đã thấy và mở lệnh trên setup LIVE), không có lỗi tính đúng.
6. Chủ dự án xác nhận bằng văn bản; cờ DEMO bật bằng cấu hình, không bằng nút web; kill switch bền đã diễn tập.
7. FUNDED vẫn khoá; không điều kiện nào trên đây thay thế quyết định riêng cho FUNDED.

## 7. Điều thiết kế này KHÔNG làm

Không bật DEMO/FUNDED, không gửi lệnh MT5, không đổi `v1.1.0`, không sửa ngưỡng, không thêm endpoint nhận hướng/lot/SL/TP.
Không khẳng định edge: nhãn bằng chứng vẫn `UNVALIDATED_BASELINE`.
