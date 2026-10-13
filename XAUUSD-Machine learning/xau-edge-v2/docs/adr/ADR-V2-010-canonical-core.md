# ADR-V2-010: lõi quyết định chuẩn (canonical core), chỉ một hàm cỡ lệnh, parity quyết định với V1

Trạng thái: **ĐÃ DUYỆT** (G4, 2026-10-13) · Liên quan: ADR-V2-006, ADR-V2-007, ADR-V2-008, ADR-V2-009.

## Quyết định

1. **Lõi thuần** `src/xau_edge_v2/core/` (NumPy, không polars, không I/O, không import V1): `indicators`, `structure` (swing không repaint, BOS/CHoCH, regime), `frames` (kỷ luật nến đã đóng), `market_state`, `risk` (SL, TP, **hàm cỡ lệnh duy nhất `size_for_risk`**), `costs`, `decision`. Lớp `data/frames.py` chuyển polars sang mảng NumPy; lớp `api/state.py` chuyển `Decision` sang `StateSnapshot`.
2. **Không chỉnh chiến lược trong G4.** Baseline là **V1 v1.1.0** (mặc định của V1; lifecycle 1.2.x chưa mang sang). Mọi hằng số bằng V1. Nhãn bằng chứng luôn `UNVALIDATED`; `mode` luôn `PAPER`; không có trường lệnh/ticket/broker trong `Decision`.
3. **Chỉ một hàm cỡ lệnh.** V1 có ba hàm cỡ lệnh; V2 chỉ có `core.risk.size_for_risk` (làm tròn xuống theo bước lot, tính lại rủi ro thật sau làm tròn, từ chối khi lô tối thiểu vượt trần hoặc SL gần hơn mức tối thiểu của broker). Test thuộc tính (hypothesis) chặn vượt trần rủi ro.
4. **Vòng đời 0..6** là độ sâu của chuỗi, xác định, không phải xác suất: 0 NEUTRAL, 1 BIAS, 2 WATCH, 3 SETUP_ARMED, 4 TRIGGER, 5 PLAN_VALID, 6 READY. READY chỉ tồn tại cùng một BUY/SELL có kế hoạch. Cổng cứng (dữ liệu cũ, thị trường đóng, spread, tin, giới hạn) ép WAIT và chặn mức tối đa ở 5, nhưng **không che** việc chuỗi chưa sẵn sàng (mức vẫn phản ánh đúng).
5. **Mô hình chi phí** không bao giờ ngầm bằng 0: spread (đo từ quote live; thống kê từ tick qua `spread_stats_from_ticks`), trượt giá 3 điểm/lệnh **ASSUMED** (giả định nghiên cứu của V1), hoa hồng 0 **ASSUMED/UNVERIFIED**, swap đọc từ terminal ngày 2026-10-08 và chỉ hiển thị, không cộng vào ước tính. Trạng thái tổng = thành phần yếu nhất (`MEASURED` / `ASSUMED` / `UNKNOWN`). Equity paper là giả định cấu hình (`XAU_V2_PAPER_EQUITY`, 10.000) cho đến khi có paper desk.
6. **Parity quyết định với V1 là điều kiện:** `scripts/parity/golden_core.py` (chạy bằng interpreter của V1) so nhân số học (chỉ báo, cấu trúc, regime, mẫu nến, SL/TP, cỡ lệnh), trạng thái thị trường từ nến thật (mọi trường chuỗi đọc, snapshot từng khung) và quyết định đầy đủ (hành động, lý do từ chối, chuỗi lý do, cảnh báo, mức, cỡ lệnh, id) dưới nhiều ngữ cảnh (cổng, tin, equity, quote). **Không lấy mẫu cửa sổ Test-H và Holdout** (so hai cách cài đặt cùng một phép tính, không đo hiệu suất). Kết quả được đóng băng thành fixture (`tests/golden/*.json`) để pytest chạy **không cần V1**.
7. **Không gồm:** ML, đăng ký giả thuyết/K, tick streaming, thay đổi UI (G5), lifecycle 1.2.x, paper desk/vị thế (G7).

## Hệ quả

- Hợp đồng đổi (`2.0.0-g4`): `StateSnapshot` có thêm `decision_id`, `strategy_version`, `chain`, `warnings`, `expires_at`; thêm `GET /api/v2/market/ticks`.
- Khi muốn đổi bất kỳ ngưỡng nào của chuỗi, đó là **thay đổi chiến lược**: phải qua giai đoạn riêng, có đăng ký và chính sách K (ADR-V2-007); golden fixture phải sinh lại có chủ đích.
