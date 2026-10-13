# ADR-V2-009: tập quy tắc thời gian thị trường được viết lại, kèm chứng minh parity với V1

Trạng thái: **ĐÃ DUYỆT** (G3, 2026-10-12) · Liên quan: ADR-V2-003, ADR-V2-004, ADR-V2-006.

## Quyết định

1. **Đồng hồ broker** `NY+7` (giờ server = giờ New York + 7 giờ, nên 17:00 NY luôn là nửa đêm server) và **lịch thị trường** (đóng cửa tuần 16:50 NY thứ Sáu, mở lại 18:05 NY Chủ nhật; nghỉ giữa ngày cùng khung giờ; 1.307 cửa sổ ngày lễ/đóng sớm) được **viết lại** thành mã Python thuần trong `domain/market.py`, không import từ V1.
2. Cấu hình (profile, cửa sổ đóng cửa) được **sao chép một lần** từ V1 sang `configs/*.json` kèm nguồn gốc, hàm băm và thời điểm (`scripts/import_v1_config.py`). V2 không đọc tệp cấu hình của V1 lúc chạy.
3. Kho nến, kho tick, tệp live của V1 chỉ được **đọc** (ADR-V2-003). Ngữ nghĩa đọc giữ như V1: chỉ nến đã đóng, duy nhất theo thời điểm mở, bản lưu đầu tiên thắng, sắp xếp tăng.
4. **Parity là điều kiện, không phải ước muốn:** `scripts/parity/parity.py` (chạy bằng interpreter V1, import V1 chỉ để so sánh đầu ra) so V2 với V1 trên nến (mọi tệp tháng, cửa sổ ngẫu nhiên, qua HTTP), tick, trạng thái lịch tại hàng chục nghìn thời điểm gồm mọi mốc chuyển DST của Mỹ và EU 2004–2026, đồng hồ broker hai chiều (kể cả khoảng trống/khoảng gập DST), thông số hợp đồng, cấu hình, và quote. Mọi sai lệch là lỗi phải giải thích.
5. **Độ mới theo lịch:** một khung là CŨ chỉ khi *số giây thị trường MỞ* kể từ lần đóng cuối vượt `2 × khung + 60 giây`; cuối tuần/nghỉ giữa ngày/ngày lễ hiển thị `MARKET_CLOSED`, không báo cũ giả. Kho dừng giữa tuần vẫn bị coi là CŨ ngay cả khi thị trường đang đóng.

## Hệ quả

- Hợp đồng API đổi: `StoreStatus.calendar_aware = true`, thêm `market_status`, `TimeframeFreshness.state/open_age_seconds`.
- Khi quy tắc broker đổi (giờ giao dịch, DST), phải cập nhật cấu hình **và** chạy lại parity; parity chỉ chứng minh V2 giống V1, **không** chứng minh V1 đúng với broker thật (xem giới hạn trong báo cáo G3).
