# NEWS-01: chọn nguồn lịch kinh tế (rubric trước, quyết định sau)

> Ngày: 2026-10-10. Phạm vi: lịch kinh tế để cổng tin tức của `/trade` biết "đang có tin mạnh hay không".
> Chỉ là công cụ hỗ trợ quyết định; người giao dịch vẫn chịu trách nhiệm kiểm tra tin. PAPER ONLY.

## 1. Rubric (định nghĩa TRƯỚC khi thử từng nguồn)

| # | Tiêu chí | Trọng số | Đạt khi |
|---|---|---|---|
| R1 | Dùng được ngay không cần khoá/tài khoản trả phí | 3 | gọi được từ máy này, không key |
| R2 | Giờ sự kiện không mơ hồ (có offset/UTC) | 3 | mỗi sự kiện mang múi giờ rõ ràng |
| R3 | Có mức tác động (impact) và tiền tệ | 3 | High/Medium/Low + currency |
| R4 | Phủ đủ tin vàng quan tâm (CPI, NFP, FOMC, phát biểu Fed) | 3 | các tin USD lớn có mặt |
| R5 | Tầm phủ (horizon) | 2 | >= 1 tuần phía trước |
| R6 | Có mốc thời gian công bố/cập nhật (point-in-time) | 2 | published/updated có sẵn |
| R7 | Ổn định/điều khoản sử dụng rõ ràng | 2 | có SLA hoặc điều khoản cho truy cập tự động |
| R8 | Chi phí | 1 | miễn phí |

Điểm: 0 = không đạt, 1 = một phần, 2 = đạt. Tối đa 38.

## 2. Ứng viên đã thử (kết quả đo thật ngày 2026-10-10)

| Ứng viên | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | Tổng | Bằng chứng |
|---|---|---|---|---|---|---|---|---|---|---|
| A. Forex Factory weekly JSON (`nfs.faireconomy.media/ff_calendar_thisweek.json`) | 2 | 2 | 2 | 2 | 1 | 0 | 0 | 2 | 28 | tải được, 83 sự kiện, 5 High; mỗi `date` có offset `-04:00`; có `impact`, `country`; chỉ tuần hiện tại (`nextweek` trả 404 cho tới cuối tuần); không có published/updated; không điều khoản chính thức; bị giới hạn tốc độ (HTTP 429 + `Retry-After`) |
| B. Finnhub `/calendar/economic` | 0 | ? | ? | ? | ? | ? | 1 | 1 | -- | HTTP 401 "Please use an API key"; chưa có key nên các tiêu chí còn lại KHÔNG đánh giá được (không bịa) |
| C. Trading Economics API | 0 | ? | ? | ? | ? | ? | 1 | 0 | -- | HTTP 410: tài khoản guest đã bị ngừng, phải mua gói |
| D. Lịch chính thức (Fed `calendar.json`, BLS, BEA) | 2 | 1 | 0 | 0 | 2 | 1 | 2 | 2 | 21 | Fed JSON tải được nhưng chỉ có sự kiện Fed, không có impact/currency, giờ dạng chuỗi địa phương; muốn đủ CPI/NFP phải ghép nhiều trang chính thức |

## 3. Quyết định

**Chọn A (Forex Factory weekly JSON)** làm nguồn mặc định (`--source forexfactory`), vì là ứng viên duy nhất
dùng được ngay không key, có giờ kèm offset và impact/currency. Nó KHÔNG hoàn hảo, và các giới hạn được thiết kế
thành hành vi, không giấu:

* **Chỉ tuần hiện tại:** coverage khai báo là tuần của feed (Chủ nhật 00:00 đến Chủ nhật kế tiếp, giờ New York).
  Hết tuần mà chưa cập nhật thì trạng thái là `STALE`, không bao giờ `CLEAR`.
* **Không có published/updated:** `available_at` là lần đầu TA thấy dòng đó (trung thực, chống leakage);
  `published_at` để trống; `updated_at` là lần fetch gần nhất xác nhận dòng.
* **Giới hạn tốc độ:** job tối thiểu cách 30 phút giữa hai lần thử (`--min-interval-minutes`), gửi User-Agent
  nhận diện, ghi lại `Retry-After` trong lỗi, và lỗi để nguyên file cũ.
* **Không có điều khoản chính thức cho truy cập tự động:** dùng như công cụ hỗ trợ cá nhân, vài lần mỗi ngày.
  Nếu sau này cần SLA thì chuyển sang B (Finnhub có key) bằng một `CalendarProvider` mới; định dạng PIT không đổi.
* **Phạm vi tiền tệ:** vàng niêm yết bằng USD nên mặc định giữ `USD` và `All`. Đây là lọc dữ liệu ở bộ chuyển đổi
  nguồn, KHÔNG đổi ngưỡng chiến lược (cửa sổ 30 phút trước / 15 phút sau tin `high` giữ nguyên).
* `Holiday` bị bỏ (không có tác động thị trường theo nguồn).

## 4. Trạng thái tin tức (đã chuẩn hoá)

`CLEAR` / `BLOCKED` / `UNKNOWN` / `NOT_CONFIGURED` / `STALE` / `ERROR` (định nghĩa trong `xau_edge/news/status.py`).
Chỉ `CLEAR` là đèn xanh. Baseline chiến lược vẫn chỉ nhìn thấy `CLEAR/BLOCKED/UNKNOWN`: mọi trạng thái còn lại
được gộp thành `UNKNOWN`, nên hành vi chiến lược không đổi.

## 5. Điều CHƯA làm được (trung thực)

* Chưa có nguồn thứ hai để đối chiếu chéo; một lỗi của feed (thiếu sự kiện) không phát hiện được tự động.
* Tin phát đột xuất (không nằm trong lịch) không bao giờ được cảnh báo; người giao dịch vẫn phải tự theo dõi.
