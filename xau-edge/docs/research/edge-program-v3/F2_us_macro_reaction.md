# F2 — Phản ứng sau tin vĩ mô Mỹ đã lên lịch (đăng ký trước, HOÃN)

Trạng thái: **ĐĂNG KÝ, HOÃN** (2026-10-11). Biến thể duy nhất: `F2-MACRO-SETB-15-120`. Giao thức chung: `COMMON_PROTOCOL.md`.

Hai lý do hoãn, cả hai đã đo:

1. **ECONOMICALLY IMPRACTICAL theo quy tắc tần suất**: tập sự kiện dưới đây ~108/năm < 150/năm; kiểm chứng forward +0.15R cần 3.3–5.5 năm (`foundation/power_v3.json`); MDE Test-H 0.20–0.25R > mục tiêu 0.15R. Chỉ được chạy nếu chủ dự án chấp nhận ngoại lệ tần suất bằng văn bản.
2. **Dữ liệu chặn**: chưa có lịch tin lịch sử PIT (`data/news/calendar.csv` chỉ phủ 2026-10-04..2026-10-11). Không chạy trước khi QA lịch tin PASS.

Khe K của F2 vẫn được tính vào K_tổng = 44 (bảo thủ).

## Identity

- Mechanism: tin vĩ mô Mỹ đã lên lịch là cú sốc thông tin công khai; nếu thị trường phản ứng thiếu, hướng của 15 phút đầu tiếp diễn trong ~2 giờ.
- Hypothesis: vị thế cùng dấu với return XAUUSD [t, t+15′] sau giờ công bố t, vào ở t+15′ và giữ tới t+120′, có mean net R > 0 (base).

## Tập sự kiện (đóng băng, theo loại tin, không theo nhãn "impact" của nguồn)

Nonfarm Payrolls; CPI (headline m/m); FOMC rate decision/statement; Retail Sales (m/m); Core PCE (m/m); ISM Manufacturing PMI; ISM Services PMI; PPI (m/m); GDP Advance; JOLTS. ≈ 12+12+8+12+12+12+12+12+4+12 = **108/năm**.

- Nhiều tin cùng một phút tính là **một** sự kiện. Hai sự kiện cách nhau < 120 phút: chỉ lấy sự kiện đầu.

## Dữ liệu tin (PIT, bắt buộc)

- Trường bắt buộc mỗi sự kiện: `scheduled_at` (UTC), `available_at` (lúc lịch được công bố), `currency` = USD, `impact`, `event_type` (một trong 10 loại trên), `source`.
- Chỉ dùng **giờ đã lên lịch**; không dùng actual/forecast/revision ⇒ không có hindsight do số liệu bị sửa.
- `available_at`: các tin trên được cơ quan phát hành công bố lịch năm trước (BLS, BEA, Fed, ISM). Quy tắc: available_at = thời điểm lịch được công bố; nếu nguồn không ghi, dùng scheduled_at − 7 ngày và đánh dấu `available_at_rule = "official_schedule_7d"`.
- Tin bị dời (đóng cửa chính phủ 2013, 2018–19, 2025): chỉ dùng giờ mới nếu được công bố ≥ 24 giờ trước; nếu không, loại sự kiện.
- Nguồn ứng viên (chủ dự án chọn): lịch phát hành chính thức BLS/BEA/Fed/ISM (ưu tiên, PIT tốt nhất) hoặc lưu trữ ForexFactory có `available_at`. QA: số sự kiện/năm theo loại, so với số kỳ vọng; lệch giờ DST; trùng lặp.

## Setup (đóng băng)

- Hướng: s = sign(close M1 của phút t+14 − open M1 của phút t), giá bid; s = 0: bỏ.
- Entry: open nến M1 t+15′. Exit: SL 1 × ATR(M15, 14) tính tại t; TP 2 × ATR(M15, 14); hết giờ ở t+120′. Barrier trên M1, SL trước.
- R: 1 × ATR(M15, 14) tại t.
- Chi phí: như `COMMON_PROTOCOL.md`, thêm giãn spread quanh tin: đo 2021-10..2026-09 trên NFP proxy, trung vị spread phút 0–2 là 31 điểm so với 26 ở thứ Sáu đối chứng, về bình thường từ phút 3–5 (`foundation/cost_model_v2.json`); vào ở t+15′ nên dùng spread của chính phút vào, bi quan × 2.
- Mẫu tối thiểu: Dev ≥ 600; Val ≥ 250.

## Must not

- Thêm/bớt loại tin, đổi 15′/120′ hoặc barrier sau khi thấy kết quả.
- Dùng giá trị actual/forecast.
- Chạy khi lịch tin chưa qua QA, hoặc khi chưa có văn bản chấp nhận ngoại lệ tần suất.
