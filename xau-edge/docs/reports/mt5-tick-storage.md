# Lưu trữ tick MT5: đo đạc, kiến trúc, retention

Lớp D (kỹ thuật dữ liệu; không phân tích kết quả thị trường, không dùng tick lịch sử để tạo giả thuyết
alpha). Số liệu thô: `mt5-tick-sizing.json` (mẫu đo), `mt5-tick-backfill.json` (backfill thật).

## 1. Đo thật (không đoán)

Mẫu 10 phút trên 3 ngày thường gần nhất tại 6 vùng giờ + một cửa sổ biến động cao (NFP 2026-10-02 12:25 UTC):

| Vùng | Tick/giây |
|---|---|
| Á yên tĩnh 03:00 UTC | 2,2 – 3,0 |
| London mở 07:30 | 3,3 – 3,6 |
| London giữa ngày 10:30 | 2,4 – 3,7 |
| Chồng London/NY 13:30 | 4,6 – 5,3 |
| NY chiều 17:00 | 3,0 – 5,0 |
| Rollover 21:30 UTC | 0 (nghỉ giữa ngày) |
| NFP | 5,6 (đỉnh mẫu) |

Backfill thật toàn bộ lịch sử server giữ (xác minh bằng `scripts/verify_tick_ledger.py`):

* tick sớm nhất server còn giữ: **2021-10-01 11:32 UTC**; đến nay **205.083.656 tick** trong **1.563 file ngày**;
* dung lượng thực tế: **1,46 GB** (≈ 7,1 byte/tick sau nén zstd; mẫu 10 phút ước 10,5 byte vì file ngày
  nén tốt hơn mẫu nhỏ), trung bình **≈ 131.000 tick và ≈ 0,93 MB mỗi ngày có tick**;
* tốc độ tăng: **≈ 0,3 GB/năm**. Ổ hiện còn ~76 GB trống → dư cho hàng trăm năm ở tốc độ này;
* thời gian backfill 5 năm: ≈ 7 phút cho lần chạy cuối (chia cửa sổ 6 giờ, tự chia đôi khi chạm giới hạn
  200.000 tick/lần gọi; không có cửa sổ nào không chia được; 0 xung đột).

## 2. Kiến trúc đã đánh giá

| Phương án | Kết luận | Lý do |
|---|---|---|
| **A. Parquet theo ngày UTC (zstd), chỉ thêm** | **CHỌN** | ~1 MB/ngày, một file ngày đọc trọn trong ms, thêm nguyên tử, hash từng file, không cần dịch vụ, polars đọc sẵn |
| B. Parquet theo giờ | Loại | 24× số file (≈ 37.000) mà không có lợi: một ngày chỉ ~1 MB |
| C. DuckDB quản lý Parquet | Loại | thêm phụ thuộc nặng; khóa ghi một-writer khó chung với collector + backfill; không cần SQL cho truy vấn khoảng thời gian |
| D. SQLite | Loại | 205 triệu hàng, lớn gấp nhiều lần, quét khoảng chậm, VACUUM/lock |
| E. Một file Parquet lớn | Loại | mỗi lần thêm phải ghi lại toàn bộ |

## 3. `TickLedger` (src/xau_edge/market_data/tick_ledger.py)

* Bố cục `data/market/<SYMBOL>/ticks/<YYYY>/<YYYY-MM-DD>.parquet` + `coverage.json` + `events.jsonl`.
* Lược đồ cố định: `timestamp_msc` (epoch ms UTC), `timestamp` (UTC, ms), `bid`, `ask`, `last`, `volume`, `flags`.
  Không có tài khoản/đăng nhập/số dư. `last` và `volume` luôn 0 với CFD vàng FTMO (đo trên 237.306 tick của 2026-10-07).
* Chỉ thêm, idempotent; tick trùng hệt bị bỏ, tick khác nhau cùng mili-giây đều giữ.
* **Coverage**: chỉ ghi khoảng đã lấy TRỌN VẸN. Trong khoảng đã phủ, dữ liệu đã lưu là chuẩn; nếu terminal trả
  khác thì ghi sự kiện `TICKS_CHANGED` thay vì trộn (lịch sử không bị âm thầm viết lại).
* Ghi nguyên tử (file tạm + đổi tên) dưới khóa liên tiến trình, nên collector và backfill chạy cùng lúc không
  làm mất hàng của nhau (khóa được thêm sau khi một lần chạy thử phát hiện đúng cuộc đua này).
* Bộ nhớ chặn bởi 1 ngày; manifest SHA-256 từng file; `scripts/verify_tick_ledger.py` kiểm hash, thứ tự,
  trùng lặp, ask < bid, tick ngoài ngày, cửa sổ phủ chồng nhau (kết quả: sạch).
* API: `/md/{sym}/ticks` (200–500 tick gần nhất cho UI) và `/md/{sym}/ticks/history` (bắt buộc `from`, `to`,
  `limit`; tối đa 60 phút và 5.000 hàng mỗi lần, trả cả vùng chưa phủ; không có đường tải hàng loạt).

## 4. Chính sách retention (cấu hình được, mặc định GIỮ TẤT CẢ)

| Lớp | Nội dung | Chính sách |
|---|---|---|
| HOT | 200 tick gần nhất trong `live.json` + các file ngày của 7 ngày gần nhất | luôn có, phục vụ UI và đo thực thi |
| WARM | mọi file ngày Parquet zstd | giữ vĩnh viễn theo mặc định (≈ 0,3 GB/năm) |
| ARCHIVE | tùy chọn: chuyển file ngày cũ sang ổ khác | `scripts/archive_ticks.py --before YYYY-MM-DD --archive-root PATH --apply` |

Không có gì tự động xóa tick. Lệnh archive mặc định là dry-run, sao chép + kiểm hash rồi mới gỡ bản gốc, giữ
nguyên coverage để lỗ hổng vẫn nhìn thấy. Giám sát dung lượng: `data/market/collector_status.json` có
`disk.level` (GOOD/WARN/CRITICAL) và số ngày ước tính còn lại theo tốc độ ghi đo thật; ngưỡng cấu hình qua
`DiskThresholds` (mặc định cảnh báo < 20 GB hoặc < 60 ngày, nghiêm trọng < 5 GB hoặc < 14 ngày).

## 5. Ranh giới nghiên cứu

Kho tick là hạ tầng đo chi phí thực thi (spread, trượt giá). Tick từ 2022 trở đi thuộc giai đoạn dữ liệu
nghiên cứu đã khóa; chúng KHÔNG được dùng để sinh giả thuyết alpha mới ở giai đoạn này (xem
`docs/research/` và các cổng khóa của Research Console).
