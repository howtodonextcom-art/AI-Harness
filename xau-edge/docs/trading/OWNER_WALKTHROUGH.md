# Hướng dẫn dùng bàn PAPER hằng ngày (không cần Python hay log)

Bàn giao dịch chỉ là **PAPER** (giả lập). Nó không gửi lệnh nào tới MT5, DEMO luôn KHÓA, và nó **không chứng minh có lợi thế**. Mọi con số là mô phỏng để theo dõi quy trình.

Mở trình duyệt: `http://127.0.0.1:3000/trade`. Nếu trang không mở được, khởi động stack bằng `scripts\start_market_stack.ps1 -Dashboard` (xem `docs/OPERATIONAL_BASELINE.md`).

## Cách đọc màn hình (từ trên xuống)

1. **Thanh trạng thái**: DATA · TRADING CORE · ACTIVE STRATEGY · PAPER DESK · FORWARD ACCEPTANCE · DEMO · EDGE. Một chip đỏ/vàng nghĩa là có điều cần chú ý. DEMO luôn `LOCKED`, EDGE luôn `UNVALIDATED`.
2. **Biểu đồ** (M5 mặc định; nút M1–H4): nến, đường Entry/SL/TP, mũi tên BUY/SELL, dấu EXIT, lệnh paper đang mở. Bấm một ô trong "ma trận khung thời gian" hoặc một dòng trong "Why WAIT?" để chuyển biểu đồ sang khung đó.
3. **Ô quyết định (bên phải)**: trạng thái lớn do **server** tính, luôn kèm biểu tượng + chữ (không chỉ màu).

| Trạng thái | Ý nghĩa | Làm gì |
|---|---|---|
| `WAIT` | Engine đã đánh giá và không có lệnh | Đọc "Blocked by" và "Waiting for". Đó là mô tả trạng thái, không phải dự báo |
| `SETUP ARMED` | Có setup đang hình thành, chưa kích hoạt | Chờ |
| `BUY READY` / `SELL READY` | Có kế hoạch đầy đủ, còn hiệu lực (đếm ngược) | Xem kế hoạch; có thể mở lệnh paper |
| `POSITION OPEN` | Đang có lệnh paper | Theo dõi ở thẻ "Lệnh paper đang mở" |
| `EXITED` | Vừa thoát lệnh paper | Xem lịch sử/journal |
| `EXPIRED SETUP` | Kế hoạch hết hạn | Không mở được; chờ setup mới |
| `STALE` | Dữ liệu cũ, không tin được | Không có kế hoạch; kiểm tra stack. **Không phải WAIT** |
| `DECISION UNAVAILABLE` | Engine không tính được (thiếu spec, mất collector, hai tiến trình ghi...) | Đọc dòng điều kiện đỏ. **Không phải WAIT** |
| `MARKET CLOSED` | Thị trường nghỉ | Không có quyết định |

Nếu cả trang báo **API UNAVAILABLE** thì mọi thứ đang hiển thị có thể đã cũ; không được vào lệnh.

## Các tình huống

**A. Thấy WAIT.** Không cần làm gì. Mở "Why WAIT?" để biết tầng nào đang chặn (Market & data → Spread & regime → H1 → H4/M15 → M15 setup → M5 trigger → M1 execution → Trade plan). Tần suất setup của baseline rất thấp (khoảng 0,1–0,25 setup/ngày), nên WAIT cả ngày là bình thường.

**B. Thấy BUY READY.** Đọc: Entry (giá ask khi MARKET), Stop loss, Take profit, R/R sau spread, Rủi ro %, Lot, "Vô hiệu khi". Số lot tính theo đặc tả hợp đồng của broker. Chọn rủi ro 0,10 / 0,25 (mặc định) / 0,50 %. Đồng hồ "còn hiệu lực" cho biết còn bao lâu. Một cảnh báo "SETUP READY" được gửi **một lần** cho mỗi setup (Telegram nếu cấu hình, nếu không ghi file).

**C. Thấy SELL READY.** Giống B, hướng ngược lại (▼, màu đỏ).

**D. Mở lệnh PAPER.** Bấm "Mở lệnh PAPER BUY/SELL" → thẻ xác nhận hiện đủ Entry, SL/TP, rủi ro, lot, R/R → bấm "Xác nhận". Server tự kiểm lại mọi điều kiện (setup còn là setup hiện tại, chưa hết hạn, dữ liệu tươi, không bị chặn); nếu từ chối bạn sẽ thấy lý do chính xác. Nút bị khóa khi: setup chưa đầy đủ, đã hết hạn, dữ liệu cũ, đang có lệnh, nghỉ sau lệnh trước, giới hạn ngày, gần giờ thị trường đóng cửa (`CLOSURE_NEAR`), trạng thái paper hỏng (`PAPER_STATE_ERROR`), hoặc có tiến trình khác đang giữ quyền ghi.

**E. Theo dõi.** Thẻ "Lệnh paper đang mở": giá vào (khớp) và giá kế hoạch, giá hiện tại, SL/TP, R hiện tại, lãi/lỗ tạm tính, MFE/MAE, thời gian giữ. Biểu đồ vẽ PAPER ENTRY/SL/TP và NOW.

**F. Thoát lệnh.** Tự động khi chạm SL, TP hoặc hết thời gian giữ (TIME_EXIT); hoặc bấm "Đóng lệnh paper ngay" (đọc lại giá mới nhất rồi đóng đúng một lần). Dấu EXIT trên biểu đồ ghi lý do, giá, P&L, R, thời gian.

**G. Xem lại.** "Lệnh paper gần đây" và "Tín hiệu LIVE gần đây" ngay trong trang (bấm một dòng để biểu đồ nhảy tới đó). Trang **Journal** liệt kê từng lệnh: setup, hướng, giờ mở, vào/thoát, SL/TP, lot, lý do thoát, R, P&L, MFE/MAE, phút, phiên bản chiến lược, `code_version`; nút "nguồn gốc" hiện ảnh chụp quyết định và thị trường lúc vào lệnh.

## Phiên bản chiến lược đang chạy

Thẻ "Chiến lược" luôn ghi **ACTIVE BASELINE** (mặc định v1.1.0). v1.2.0 và v1.2.1 chỉ được cài đặt, ghi `AVAILABLE / INACTIVE`, không chạy.

## Những gì CHƯA được kiểm chứng (đừng hiểu nhầm)

* Không có edge được chứng minh; baseline chỉ là quy trình vận hành minh bạch.
* **Tin tức: NOT VERIFIED** (chưa có lịch kinh tế). Tự kiểm tra tin trước khi tin vào một setup.
* Volume là **tick volume**, không phải volume sàn.
* Mức "Forward acceptance" ở F0 cho đến khi có một setup LIVE thật; replay không nâng được mức này.
* Chưa có thực thi DEMO; không có lệnh nào đi tới MT5.

## Khi có lỗi

| Thấy | Nghĩa | Việc cần làm |
|---|---|---|
| `PAPER_STATE_ERROR` | File trạng thái paper không khớp journal | Dừng mở lệnh mới; chạy khôi phục (xem `docs/trading/PAPER_RECOVERY.md`) |
| `WRITER_LOCK` | Một tiến trình API khác đang giữ bàn paper | Tắt tiến trình thừa (chỉ một API được chạy) |
| `DATA STALE` / collector dừng | Dữ liệu không tươi | `scripts\status_market_stack.ps1` |
| `NO SPEC` | Thiếu đặc tả hợp đồng broker | Kiểm tra collector/MT5 |
