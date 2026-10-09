# Kiểm thử hỗn loạn (chaos) của nền tảng dữ liệu MT5

Chạy trên stack thật (terminal FTMO DEMO + supervisor) ngày 2026-10-09 và bằng test tự động (CI không cần
MT5). Nguyên tắc: **lỗi phải hiện ra, hồi phục sạch, không hỏng dữ liệu âm thầm.**

| # | Sự cố | Cách thử | Kết quả | Bằng chứng |
|---|---|---|---|---|
| A | Collector bị giết | `Stop-Process` tiến trình collector | Supervisor phát hiện, chạy lại sau 2 s; collector reconcile và lấp nến thiếu; trạng thái GOOD | live + `test_supervisor.py` |
| B | API bị giết | giết tiến trình API | Supervisor chạy lại; `/health` 200 sau ≤ 3 s | live |
| C | MT5 đóng/mất kết nối | KHÔNG đóng terminal thật của chủ (quy tắc: không tự tắt MT5). Mô phỏng: kết nối thất bại / mất giữa chừng | trạng thái DISCONNECTED hiện ra, 5 s sau mở phiên mới, reconcile lấp nến bỏ lỡ | `test_collector_runner.py` (3 test); **việc đóng MT5 thật ở danh sách kiểm tay** |
| D | Mạng không khả dụng | không áp dụng: terminal cục bộ, API chỉ 127.0.0.1; mất mạng của terminal = trường hợp C (broker ngắt) | — | — |
| E | File trạng thái/live hỏng | ghi `{torn` đè `collector_status.json` và `live.json` khi stack đang chạy | API trả `STOPPED/UNKNOWN` (nhìn thấy được), không crash; tự lành ≤ 8 s khi collector ghi lại | live + `test_corrupt_status_file...` |
| E2 | Đọc/ghi đồng thời | 3 reader quay liên tục + 300 lần ghi | không có JSON bị cắt; ghi thử lại khi Windows từ chối đổi tên | `test_live_and_status_files_are_never_torn...` |
| F | Nến trùng | nạp lại cùng nến | đếm là duplicate, không đổi kho | `test_ledger_append_is_idempotent` |
| G | Nến đã đổi | cùng thời điểm khác giá | giữ bản đã lưu, ghi sự kiện `BAR_CHANGED`, health DEGRADED | `test_ledger_never_overwrites...`, `test_reconcile_after_restart...` |
| H | Ổ đĩa gần đầy | ngưỡng giả lập | `disk.level = CRITICAL`, health DEGRADED với lý do | `test_disk_report_levels_and_growth`, `test_evaluate_health_stale...` |
| I | Hai tiến trình ghi cùng file | khóa ghi liên tiến trình | không mất hàng; khóa treo (tiến trình chết) tự dọn sau 300 s | `test_file_lock_serialises_writers...` |
| J | Dừng stack | `stop_market_stack.ps1` | mọi tiến trình con (kể cả cây node/uv) bị dừng, cổng 3000/8000 được giải phóng, dữ liệu giữ nguyên | live (đã sửa lỗi cây tiến trình sau khi phát hiện node mồ côi giữ cổng 3000) |
| K | Collector dừng, trang đang mở | chạy stack không collector, rồi bật collector | trang tự chuyển STALE → hiển thị cách khắc phục → bình thường mà KHÔNG tải lại trang (tuổi tick 1 s) | live (Playwright) + e2e |
| L | Chủ dự án thoát (File → Exit) terminal thật khi collector chạy | quan sát thật 2026-10-09 | terminal bị collector TỰ MỞ LẠI (pid đổi) và collector nối lại không cần can thiệp: đúng hành vi "không cần chạy lại collector"; hệ quả vận hành được ghi vào §4 tài liệu vận hành (phải tắt stack trước khi sửa/đóng terminal) | live |

## Lỗi thật tìm ra nhờ các bài thử (đã sửa)

1. Backfill tick chạy song song với collector làm hỏng ghi `coverage.json` (WinError 32) → khóa ghi + ghi thử lại.
2. Dừng supervisor chỉ giết `npx`, để node mồ côi giữ cổng 3000 → giết cả cây tiến trình; chạy node trực tiếp.
3. API tin trạng thái "FRESH" mà collector đã chết để lại → API tự tính độ mới từ kho nến + lịch.
4. Gọi trạng thái/báo giá tốn 0,5–0,9 s vì chuỗi OR hàng trăm cửa sổ ngày lễ → tìm nhị phân (480 → 4 ms).
5. Kiểm tra bất biến coi mọi file tháng đổi hash là "lịch sử bị sửa", nên báo sai khi backfill THÊM nến cũ vào tháng đầu → giờ
   phân biệt "file chỉ tăng dòng và không có sự kiện BAR_CHANGED" (hợp lệ) với nến bị đổi (lỗi).
6. Suy luận ngày lễ từ M1 2004→nay gán nhầm 5.000+ khoảng thiếu phút của thị trường mỏng là "đóng cửa sớm" → chỉ chấp nhận
   khoảng liên tục ≥ 60 phút và ≤ 5 ngày; kiểm tra cả ngày nằm giữa khoảng (Lễ Tạ ơn nằm giữa hai đầu).

## Danh sách kiểm tay (không thể tự động hóa an toàn)

1. **Đóng terminal MT5 thật khi collector chạy**: trang phải báo MT5/Collector mất kết nối; mở lại terminal, đăng
   nhập → sau vài giây GOOD không cần chạy lại lệnh nào; nến đóng trong lúc vắng được lấp (`RECONCILED`).
2. **Khởi động lại máy / đăng xuất rồi đăng nhập**: xem `docs/operations/market-data-operations.md` mục 6.
