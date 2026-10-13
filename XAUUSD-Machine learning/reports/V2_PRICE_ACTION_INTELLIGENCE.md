# V2 · Trí tuệ hành động giá (nến và M1): mô tả, không dự đoán

Ngày: 2026-10-13 · Mã: `core/intelligence/price_action.py`, test `tests/unit/test_intelligence.py`, tần suất `docs/research/intel_descriptive_dev.json`.

## 1. Nguyên tắc
Mỗi mẫu là **mô tả điều nến đã làm**, không phải dự báo nến sau. Không mẫu nào tạo BUY/SELL. Mỗi sự kiện có: loại, nến, `known_at` (= đóng nến), mức tham chiếu, **mức vô hiệu**, độ mạnh theo ATR.

## 2. Định nghĩa (r = high−low, body = |close−open|, ATR = Wilder 14 tại nến)
| Loại | Điều kiện | Mức vô hiệu |
|---|---|---|
| Từ chối bằng bấc (trên/dưới) | r ≥ 0,5 ATR; bấc ≥ 0,6 r và ≥ 2 body | đỉnh/đáy nến |
| Nhấn chìm tăng/giảm | màu ngược nến trước; thân phủ thân trước; thân ≥ 0,3 ATR | đáy/đỉnh nến nhấn chìm |
| Nến trong / ngoài | nằm trong / vượt cả hai đầu nến trước | — |
| Displacement | r ≥ 1,5 ATR và thân ≥ 0,6 r | mở cửa nến |
| Phá vỡ thất bại (quét) | vượt đỉnh/đáy 10 nến trước nhưng **đóng** lại bên trong | cực trị nến quét |
Hằng số tiên nghiệm, chưa fit. Mẫu "volume bất thường" và "mở rộng spread" chưa đưa vào lớp này (M1 execution của V2 đã có `VOLATILE/QUIET/SPREAD_WIDE` trong chuỗi, không đổi).

## 3. Kiểm chứng
- Mỗi loại có test tổng hợp kích hoạt đúng nến và **không** kích hoạt trên nến nhỏ/không đủ điều kiện (`test_wick_rejection_both_sides`, `test_engulfing_needs_opposite_colours_and_cover`, ...).
- Không repaint: `detect(head(k)) == [e for e in detect(full) if e.index < k]` ở 4 seed × 3 điểm cắt; trên DEV' thật 25 điểm cắt ngẫu nhiên × 2 khung: 0 sai lệch.
- `known_at ≥ mở nến + độ dài khung` cho mọi sự kiện trên API (`test_every_event_is_known_no_earlier_than_its_bar_closes`).
- Nến phẳng/ATR 0: không phát sinh sự kiện, không lỗi.

## 4. Tần suất trên DEV' (M15, trên 1.000 nến; H1 trong JSON)
Bấc trên 74,5 · bấc dưới 78,5 · nhấn chìm tăng 68,5 · nhấn chìm giảm 67,0 · nến trong 167,4 · nến ngoài 95,0 · displacement tăng/giảm 31,9/31,8 · quét đỉnh 77,5 · quét đáy 72,6.
Hầu hết là sự kiện thường xuyên (nhiều % nến) ⇒ **một mẫu đứng riêng không đủ phân biệt** để làm cơ sở lệnh. Đây là lý do chúng nằm trong lớp mô tả và trong điều kiện đủ của họ C/D (kết hợp với cấu trúc/chế độ), không là luật BUY/SELL.

## 5. Trên M1
M1 xuất hiện trong lớp mô tả như mọi khung (thời điểm), dùng để người đọc thấy bối cảnh nến vi mô; `core/execution.py` (chỉ chặn) không đổi. Dự đoán nến kế tiếp: **không làm**.

## 6. Thông tin gia tăng
Chưa đo (cần xác suất có điều kiện của nến sau/lệnh, thuộc outcome). Phân loại: `NOT_TESTED`. Giao thức: `V2_MULTI_STRATEGY_RESEARCH_PROTOCOL.md` (so với kiểm soát khớp ATR-percentile/phiên, chỉ trên VALIDATION' sau khi chốt spec).
