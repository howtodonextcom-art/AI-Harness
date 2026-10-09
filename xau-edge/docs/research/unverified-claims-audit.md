# Rà soát các khẳng định "chưa xác minh" trong tài liệu nghiên cứu MT5

Phạm vi: `mt5-data-integration-options.md` và `tradingview-data-role.md` (viết 2026-10-09 từ các trang chính
thức, mỗi chỗ không chứng minh được đều ghi "chưa xác minh bằng trang hiện tại"). Phân loại:

* **MARKET-DATA CRITICAL**: ảnh hưởng độ đúng dữ liệu → xác minh ngay bằng đo thực trên terminal FTMO DEMO;
* **RESEARCH-ONLY**: không ảnh hưởng nền tảng dữ liệu → để mở, không chặn READY;
* **COSMETIC/DOC**: thương mại/giấy phép/mô tả.

## MARKET-DATA CRITICAL (đã xác minh bằng thực nghiệm)

| # | Khẳng định chưa rõ | Kết quả đo | Bằng chứng |
|---|---|---|---|
| 1 | Timestamp trả về là UTC thật hay giờ server? | **Giờ server gắn nhãn UTC**; server = New York + 7 h (UTC+3 vào mùa hè Mỹ). Đổi bằng `BrokerClock NY+7`; tuổi tick ≈ 0 s | `docs/reports/mt5-verification.md`, kiểm tra sống mỗi lần chạy; 240 nến khớp qua đường `zoneinfo` độc lập |
| 2 | Thứ tự trả về của `copy_rates_*`/`copy_ticks_*` | Tăng dần theo thời gian (cũ → mới) | kiểm tra numpy trên 50 nến và 1.150 tick thô |
| 3 | `datetime` không múi giờ truyền vào Python được hiểu thế nào | **Là giờ cục bộ của máy** (máy này UTC+7: `12:17` trần trả nến 05:17 UTC) | script `verify_visual_parity.py`; mọi mã dự án truyền datetime có múi giờ |
| 4 | Nến cuối có phải nến đang hình thành | Có (`pos=0` là nến hiện tại); loại bằng đồng hồ + `is_closed` | test `test_feed_latest_bars_excludes_forming_by_default`, trang `/market` đánh dấu riêng |
| 5 | Giới hạn "Max bars in chart" ảnh hưởng thế nào | Cắt lịch sử M1/M5/M15/M30/H1; 100.000 → "Invalid params", 99.000 chạy; truy vấn theo ngày thêm ~900 nến rồi `Terminal: Call failed` | `mt5-history-depth.json`, `mt5-backfill-final.md` |
| 6 | `last`/`volume` của tick CFD vàng có rỗng không | **Luôn 0** (0% trên 237.306 tick); chỉ có bid/ask | `docs/reports/mt5-tick-storage.md` |
| 7 | Độ sâu tick | Server giữ từ 2021-10-01 11:32 UTC | backfill 205 triệu tick |
| 8 | Đồng bộ lịch sử khi gọi lần đầu có thiếu không | Terminal đã đồng bộ trả đủ ngay; vẫn coi lần đầu có thể thiếu và đối chiếu bằng reconcile mỗi lần khởi động | collector reconcile 200 nến/khung |
| 9 | `real_volume` có nghĩa gì | **Chưa xác minh được nghĩa**; chỉ khác 0 ở H1/H4 2012-03-28..2018-02-09 (nhập cũ) | chính sách `UNVERIFIED_LEGACY_REAL_VOLUME`: không hiển thị, không dùng |
| 10 | Đăng nhập bằng read-only/investor password | **Không áp dụng**: dự án dùng phiên đã đăng nhập của terminal, không nhận/lưu mật khẩu | `ReadOnlyMt5Client`, test cấm tên hàm giao dịch |

## RESEARCH-ONLY (để mở, không chặn READY)

* FTMO có API gốc cho MT5 không (chỉ thấy Open API cho cTrader).
* FTMO có hạn chế đăng nhập đồng thời nhiều phiên không.
* Khác biệt spread/nguồn symbol giữa TradingView và MT5 FTMO (TradingView chỉ là tham chiếu hình ảnh).

## COSMETIC/DOC (để mở)

* Thời hạn Free Trial FTMO (hai trang mâu thuẫn).
* Yêu cầu attribution của Lightweight Charts (biểu đồ hiện hiển thị logo TradingView theo mặc định).
* Điều kiện cấp phép Advanced Charts cho dự án nội bộ (không dùng).
* ZeroMQ/WebTerminal: không dùng.
