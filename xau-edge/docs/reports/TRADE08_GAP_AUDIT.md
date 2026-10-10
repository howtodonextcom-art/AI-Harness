# TRADE-08 — kiểm toán khoảng trống so với tuyên bố "FUNCTIONALLY COMPLETE" của TRADE-07

HEAD thực tế khi bắt đầu: `a8d939c648ad09b978e6df86c193807be73d8db3`, nhánh `main`, cây làm việc sạch, CI xanh (7/7 job). Stack LIVE (:3000/:8000) đang chạy bản build cũ; đã khởi động lại bằng `stop_market_stack.ps1` + `start_market_stack.ps1 -Dashboard`, sức khỏe GOOD, thị trường ĐÓNG (thứ Bảy). Ảnh "trước" LIVE: `img/trade08/before/live-1440-market-closed.png`.

Giả thuyết cần phản bác: "giao diện tín hiệu đã xong, chỉ còn chờ nghiệm thu LIVE". Kết luận kiểm toán: **giả thuyết sai** — còn lỗi sản phẩm tự sửa được (mục BROKEN / VISUALLY AMBIGUOUS), không chỉ chờ LIVE.

## CONFIRMED COMPLETE (đã kiểm bằng trình duyệt thật, giữ nguyên)

- Máy trạng thái server `hero.action` + stage BLOCKED + lifecycle replay thật (watch, armed, ready, hold, TP/SL/TIME exit, expired, invalidated, stale, unavailable).
- Mở/đóng PAPER an toàn: xác nhận, từ chối setup cũ (`DECISION_CHANGED`), double-click chỉ tạo 1 lệnh, fail-closed khi mất API.
- Crosshair/OHLC/zoom/pan/follow/fullscreen/marker click bằng chuột thật; hold/exit hiển thị; journal → quay lại biểu đồ.
- Chủ quyền server: frontend không tự tính BUY/SELL/HOLD/EXIT.

## PARTIAL

- **max_hold**: server đã có `max_hold_until` trong bản ghi vị thế nhưng UI chưa hiển thị (chỉ nói "hết thời gian giữ"). → sửa.
- **Journal/Provenance**: cột nguồn gốc dùng nhãn tiếng Anh/jargon.
- **LIVE**: chưa có một phiên trình duyệt LIVE nào với bản build mới nhất.

## BROKEN (lỗi thật, tự sửa được)

1. Phone 390×844: chỉ **87–93 px** biểu đồ trong màn hình đầu (đo trước khi sửa: market bar 242 px, hero 204–269 px, toolbar 104 px). Ngưỡng định trước 280 px.
2. Bộ đếm hiệu lực replay nhảy 4:59 → 4:58 → 5:00 (client tự cộng đồng hồ tường vào đồng hồ replay đứng yên).
3. localStorage cảnh báo giá/đường kẻ không tách LIVE/REPLAY (khóa chung `xau-edge.trade.*.v1`).
4. Mã nội bộ (`WRITER_LOCK`, `API_UNAVAILABLE`, `CHART_DATA_UNAVAILABLE`, `DATA_STALE`, …) hiện ngay trước mặt trader ở banner/hero/vé lệnh.
5. Thanh hành động dính phone có thể bị phần tử "separator" của thư viện biểu đồ (z-index 50) che mất nút khi chồng lên (lộ ra khi gọn layout) — phát hiện bằng test.

## VISUALLY AMBIGUOUS

1. "THEO DÕI MUA/BÁN": chữ lớn MUA/BÁN trên trạng thái không được phép giao dịch (rủi ro hàng đầu của five-second review TRADE-07).
2. Checklist "Đạt 5/8" kèm "Setup M15 ✓" trong khi hero nói "đang hình thành" → mâu thuẫn bề mặt.
3. Cùng một thông tin lặp 3–4 lần ở cột quyết định (Đang chờ / Mã chặn / Xu hướng / Setup).
4. Thiếu giải thích R/R, MFE/MAE, Bid/Ask/Spread, Tick volume, SL/TP, Bias, Setup.
5. Popover marker thiếu múi giờ và giờ thoát; trục giá chồng nhãn.

## LIVE UNVERIFIED

Toàn bộ giao diện trên stack :3000 với bản build mới nhất; bộ đếm LIVE; header thị trường đóng cửa; nhiều khung giờ/crosshair/zoom/pan/follow/fullscreen trên dữ liệu thật. → làm trong TRADE-08 (xem `TRADE08_LIVE_BROWSER_ACCEPTANCE.md`).
