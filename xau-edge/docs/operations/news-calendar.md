# Lịch tin tức (News calendar): định dạng, cập nhật hằng ngày, cảnh báo

> Trạng thái: **khung vận hành đã sẵn sàng, chưa có nguồn dữ liệu**. Chủ dự án chưa chỉ định nguồn
> lịch kinh tế; code không bundle và không tự lấy dữ liệu từ bất kỳ website nào. Không có lịch =
> `NEWS_UNKNOWN` = tín hiệu luôn `WAIT` (fail-closed, đúng thiết kế, xem pre-mortem b1).

## 1. Định dạng file (point-in-time)

```csv
# coverage: 2026-10-01T00:00:00Z..2026-12-31T23:59:59Z
time_utc,category,impact,available_at
2026-11-06T13:30:00Z,NFP,high,2026-10-01T08:00:00Z
2026-10-20T12:30:00Z,CPI,high,2026-10-09T08:00:00Z
```

* Dòng đầu **bắt buộc** là `# coverage: <start>Z..<end>Z` (UTC). Thiếu dòng này, file bị từ chối.
* `time_utc`: thời điểm sự kiện. `impact`: `low|medium|high`. Mọi mốc giờ phải kết thúc bằng `Z`.
* `available_at`: **lúc ta có thể biết** sự kiện này (lúc nguồn công bố lịch, hoặc lúc ta tải về).
  Đây là cột chống leakage: quyết định tại thời điểm `t` chỉ được dùng hàng có `available_at <= t`.
* File vẫn đọc được bằng `load_calendar_file` cũ (cột thừa bị bỏ qua), nên bot hiện tại không cần đổi
  để dùng file mới.

## 2. Loader chống leakage

```python
from xau_edge.news.pit import load_calendar_asof

cal = load_calendar_asof("data/news/calendar.csv", decision_time)  # live
cal = load_calendar_asof(path, decision_time, future_rows="drop")  # backtest
```

* `future_rows="raise"` (mặc định, dùng cho bot live): có hàng `available_at > decision_time` thì
  ném `CalendarLeakageError`. Với bot thật, điều đó nghĩa là file hỏng hoặc đồng hồ sai.
* `future_rows="drop"`: ẩn các hàng chưa được biết tại thời điểm đó (dùng khi replay quá khứ).
* File không có cột `available_at` bị từ chối, vì không chứng minh được là không nhìn trước tương lai.
* Ngoài vùng coverage, `news_blocked` vẫn ném `CalendarUnavailableError` (không bao giờ "không có tin").

## 3. Nguồn dữ liệu (pluggable)

Provider chỉ cần một phương thức `fetch_text() -> str` trả về văn bản đúng định dạng trên
(`xau_edge/news/providers.py`):

| Provider | Dùng khi |
|---|---|
| `LocalFileProvider(path)` | Bạn tự xuất lịch từ nguồn tin cậy ra CSV (thủ công hoặc bằng công cụ khác) |
| `HttpsCsvProvider(url)` | Có URL HTTPS bạn tin cậy trả về đúng CSV này. Chỉ HTTPS, giới hạn 5 MB, URL không được in ra trong lỗi (có thể chứa key) |
| Tự viết `CalendarProvider` | Nối tới API của nhà cung cấp dữ liệu bạn chọn |

Nếu nguồn không có `available_at`, job cập nhật gán **thời điểm tải về** cho hàng mới (trung thực:
đó là lúc ta thật sự biết). Hàng đã có trong file giữ `available_at` **sớm nhất**.

Cách trỏ vào nguồn: đặt `XAU_EDGE_NEWS_SOURCE` (đường dẫn file hoặc URL https) và
`XAU_EDGE_NEWS_CALENDAR_PATH=data/news/calendar.csv` trong `.env` (chỉ tên biến, không commit `.env`).

## 4. Job cập nhật hằng ngày

```powershell
uv run python scripts/news_update.py --source D:\feeds\calendar.csv --notify
uv run python scripts/news_update.py --check-only --notify     # chỉ kiểm coverage còn lại
```

Quy tắc an toàn (mọi vi phạm: giữ nguyên file cũ, exit 1):

* ghi **nguyên tử** (file tạm cùng thư mục, `fsync`, `os.replace`);
* nguồn không parse được, rỗng (nghi feed hỏng), hoặc coverage kết thúc **sớm hơn** file hiện có: từ chối;
* coverage mới không giao với coverage cũ (sẽ tạo lỗ hổng): từ chối;
* hợp nhất theo (time, category, impact), coverage được nới rộng, không bao giờ thu hẹp.

Exit code: `0` ổn; `1` cập nhật thất bại; `2` cập nhật xong nhưng coverage còn dưới 7 ngày.

Lập lịch (Task Scheduler, mỗi ngày 06:00 giờ máy): action
`uv run python scripts/news_update.py --notify`, thư mục làm việc là thư mục repo.

## 5. Cảnh báo coverage

`xau_edge.news.update.coverage_alert(coverage_end, now, min_days=7)` và
`calendar_file_alert(path, now)` trả về `Alert` (code `NEWS_COVERAGE_ENDING`):

* còn dưới 7 ngày: `warning`; đã hết hạn, file thiếu hoặc không đọc được: `critical`.

Gửi cảnh báo do notifier (`docs/operations/telegram-alerts.md`) đảm nhiệm:
`AlertEvent.from_alert(alert)` rồi `dispatcher.dispatch(event)`; `--notify` của script làm sẵn việc này.

## 6. Việc còn lại cho chủ dự án

1. Chọn nguồn lịch kinh tế tin cậy (CPI, NFP, FOMC, phát biểu ngân hàng trung ương) và kiểm tra điều khoản sử dụng.
2. Xuất ra CSV đúng định dạng hoặc viết một `CalendarProvider`.
3. Xác minh luật FTMO về giao dịch quanh tin (pre-mortem d3) trước khi dùng cửa sổ tin cho prop.
