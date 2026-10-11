# F3 — Sửa đổi 1 (v1.1), đăng ký trước khi chạy

Ngày: 2026-10-11. Áp cho `F3-USMOM-0930-1400-1500-1645` (`F3_us_session_momentum.md`, v1.0, prereg commit `4a03273`). **v1.0 chưa từng được chạy**: không có kết quả, không có số liệu outcome nào của F3 đã được xem. Sửa đổi này **không thêm biến thể**, không đổi mốc giờ, tham số, cổng hay ngưỡng; K_V3 giữ nguyên = 3 (F3 vẫn là một khe).

## Lý do

`docs/research/edge-program-v2/clock-certificate.json` không chứng nhận đồng hồ broker cho 2010–2020 (giờ đóng tuần đi theo DST châu Âu). Trong những ngày DST Mỹ và DST châu Âu lệch nhau, giờ UTC lưu trong dữ liệu của các năm đó lệch một giờ. F3 dùng mốc giờ New York theo phút, nên những ngày đó sẽ lấy nhầm nến. F1 không bị ảnh hưởng vì mọi symbol cùng một đồng hồ, và F1 không có mốc giờ tuyệt đối.

## A1 — Mặt nạ an toàn đồng hồ (thêm vào danh sách loại trừ)

Một ngày giao dịch Mỹ d bị loại nếu năm của d **không** được chứng nhận trong certificate **và** ở 12:00 UTC ngày d, độ lệch giữa Europe/Athens và America/New_York khác 7 giờ. Đây đúng là quy tắc `_mismatch_days` + `uncertified_years` của V2 (`src/xau_edge/research_v2/frame.py`), dùng lại nguyên văn. Năm được chứng nhận (2021–2024) không bị loại. Không dịch giờ, không sửa dữ liệu.

## A2 — Cách đọc đã cố định (trước đây chỉ viết bằng lời)

* Ngày lễ / đóng cửa sớm: loại ngày d nếu bất kỳ cửa sổ `closures` nào của `ftmo_calendar()` (HOLIDAY hoặc EARLY_CLOSE) giao với [09:30, 17:00) New York của ngày d.
* Bốn nến mốc: phải có nến M1 mở **đúng** 09:30, 14:00, 15:00, 16:45 NY. Thiếu bất kỳ nến nào thì loại ngày đó (được đếm).
* Thiếu > 5% nến M1: cửa sổ 09:30–16:44 NY có 435 phút; loại nếu số nến có mặt < 435 × 0.95 (tức thiếu từ 22 nến trở lên).
* ATR(H1, 14) “lúc 15:00 NY”: ATR (`features.indicators.atr`) của nến H1 mở lúc 14:00 NY (đóng lúc 15:00, không nhìn trước). Không có nến H1 đó hoặc ATR không dương thì loại ngày đó (được đếm).
* Stop thảm họa 3 ATR từ giá vào, kiểm tra trên mọi nến M1 từ 15:00 tới trước 16:45 NY. Khớp lệnh và chi phí dùng `research_v3/execution.py`, giống F1: mua ở ask, short chạm barrier theo ask, gap qua stop khớp ở giá mở, mỗi round trip trả một lần spread.
* Chi phí: kịch bản base (1.6 lần spread nến, trượt giá 3 điểm mỗi lần khớp) và pessimistic (2.4 lần, 6 điểm) cho 2011–2018. Không có swap vì vị thế đóng trước 17:00 NY.
* s = 0 (hai giá mở bằng nhau): không giao dịch (được đếm).
* Thống kê: khóa ngày = ngày giao dịch (New York + 7 giờ), cùng block bootstrap, lịch, placebo và cổng Stage 1 như F1. n tối thiểu 1,500, α = 0.0333. Nếu mặt nạ A1 làm n < 1,500 thì kết quả là **FAIL (thiếu mẫu)**; không nới tiêu chí.
* Phần mô tả phụ (không phải bộ lọc): kết quả theo ngày trong tuần và theo ngũ phân vị của |return 09:30–14:00|.

## Must not

Như v1.0. Không dời mốc giờ, không thêm bộ lọc, không chạm Test-H hay Holdout.
