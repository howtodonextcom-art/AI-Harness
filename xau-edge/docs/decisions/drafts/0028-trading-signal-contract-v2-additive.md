# ADR-0028 (NHÁP): Contract `TradingSignal` v2 — chỉ bổ sung, không đổi tên, `source_mode` bắt buộc

Status: **SUPERSEDED** as the working copy — accepted text is `docs/decisions/0028-trading-signal-contract-v2.md` (2026-10-11). Draft kept for the closed-loop rationale.

## Bối cảnh (đã kiểm)
- `TradingSignal` (`trading/schema.py:63-129`, `extra="forbid"` tại `:66`) đã có symbol, timestamp, strategy_id/version, decision (BUY/SELL/WAIT), setup_id, entry_price, stop_loss, take_profit(+_2), risk_reward, risk_pct/risk_amount/position_size, signal_expiry, invalidation, evidence_status, reasons, warnings, code_version, inputs_hash.
- Thiếu: `schema_version`, `source_mode` (đang nằm ở engine/desk/UI: `engine.py:160`, `paper_desk.py:510`), `setup_phase` (chỉ trong `metadata`, khoảng 8 chỗ đọc), `bias` tổng hợp. Chưa có HOLD/EXIT: đó là tư vấn cho **vị thế đang mở**, không phải quyết định vào lệnh.
- Journal PAPER nhúng toàn bộ quyết định (`paper_desk.py:521`): thêm trường sẽ làm code cũ không đọc được journal mới (vì `extra="forbid"`).

## Phương án (chấm mù rubric (c))
| Phương án | Reviewer kiến trúc | Kết quả |
|---|---|---|
| **Bổ sung v2** | **4,35 PASS** | **Chọn** |
| Breaking v2 (đổi tên + HOLD/EXIT chung enum) | 2,85 FAIL (C3 = 1, C2 = 3) | Loại |
| Giữ nguyên | 3,70 PASS nhưng không đáp ứng nhu cầu Demo | Loại |

## Quyết định
1. Thêm `schema_version: int`. Thêm `source_mode: Literal["LIVE","ACCEPTANCE_REPLAY","PAPER_REPLAY","DEMO_DRY_RUN","UNKNOWN"]`, **bắt buộc** khi engine tạo signal; giá trị đọc từ dữ liệu cũ thiếu trường là `UNKNOWN`. `UNKNOWN` không bao giờ được tính vào forward evidence hay dùng để tạo intent (fail-closed).
2. `setup_phase` thành trường chính thức. `metadata["setup_phase"]` giữ làm bí danh **chỉ đọc** cho tới khi mọi chỗ đọc chuyển xong (một nguồn ghi).
3. `bias` là **property** suy ra từ `h1_bias`/`h4_bias`, không lưu.
4. Không tạo khối `provenance` lồng nhau. Engine **điền** `inputs_hash` (hiện mặc định `""`, `schema.py:101`) và git SHA vào `code_version` (hiện chứa strategy version, `baseline.py:165`). `source_mode` tham gia định danh signal để replay không bao giờ tính là LIVE.
5. Tên đích (`entry`, `sl`, `tp`, `rr`, `evidence_label`) là **property chỉ đọc**, theo mẫu `decision_id` / `expires_at` (`schema.py:117-124`).
6. Thêm **cơ sở tính lot**: `equity_basis`, `risk_pct` (đã có), `entry_basis` (ASK/BID), `spec_version`. Không có các trường này thì executor vẫn phải tính lại lot (RiskEngine 0,5% + contract_size 100 vs PaperDesk 0,25% + symbol spec — `risk/engine.py:31,40` vs `trading/sizing.py:57-88`).
7. HOLD/EXIT nằm trong một đối tượng riêng `PositionAdvice` (sprint sau, ADR riêng), không vào enum quyết định vào lệnh, không được tiêu thụ trên đường vào lệnh.
8. Đọc journal: dùng model "đọc lỏng" (bỏ qua trường lạ) cho journal; ghi vẫn `extra="forbid"`.
9. Không nới luật BUY/SELL không bao giờ VALIDATED (`schema.py:158-160`). Không đổi đầu vào `signal_id` / ngữ nghĩa `setup_id` nếu không có ghi chú migration.

## Acceptance criteria
- AC-C1 **Must:** golden JSON fixture cho mỗi `source_mode`; test cố định `signal_id`/`inputs_hash` không đổi khi chỉ thêm trường metadata.
- AC-C2 **Must:** signal thiếu `source_mode` khi đọc → `UNKNOWN` → không tính forward evidence, không tạo intent.
- AC-C3 **Must:** code v1 (trước thay đổi) đọc được journal v2 qua model đọc lỏng (test với fixture).
- AC-C4 **Must not:** đổi tên hay xoá trường hiện có; đổi kiểu dữ liệu của trường hiện có.
- AC-C5 **Must not:** thêm HOLD/EXIT vào `TradeDecision`.
