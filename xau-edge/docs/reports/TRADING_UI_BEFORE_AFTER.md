# Terminal giao dịch PAPER: trước và sau (TRADING_UI_BEFORE_AFTER)

Mục tiêu: biến trang `/trade` từ "dashboard kỹ thuật có gắn một biểu đồ" thành "terminal giao dịch có bộ máy quyết định kỷ luật bên dưới". Phạm vi chỉ là sản phẩm/giao diện: không đổi chiến lược, ngưỡng, tần suất tín hiệu, SL/TP hay phiên bản mặc định; vẫn chỉ PAPER, không có lệnh MT5.

## 1. Ảnh chụp

| Trạng thái | Trước | Sau |
|---|---|---|
| LIVE 1440×900 | `img/trading-ui/before/1440x900-fold.png` (+ `-full`) | `img/trading-ui/after-live/LIVE-1440x900.png` |
| 1920×1080 | `before/1920x1080-fold.png` | `after-live/LIVE-1920x1080.png` |
| Điện thoại 390×844 | `before/390x844-fold.png` | `after-live/LIVE-390x844.png` |
| Zoom 200% (720×450 CSS px) | `before/zoom200-fold.png` | `after-live/LIVE-zoom200-720x450.png` |
| Tối | `before/dark-1440x900-fold.png` | `after-live/LIVE-dark-1440x900.png`, `LIVE-dark-390x844.png` |

Ảnh REPLAY (đã đốt, mỗi ảnh tự ghi "NOT LIVE"): `img/trading-ui/after/01…26-*.png` (CHỜ, BUY/SELL thật, hộp xác nhận mở/đóng, vị thế đang mở, chi tiết marker, toàn màn hình, thoát TP/SL/TIME, journal, journal→biểu đồ, các trạng thái lỗi, mobile, zoom, tối). Ảnh A/B: `img/trading-ui/ab/`. Tất cả "sau" là trình duyệt thật trên bản build production; ảnh LIVE là stack sống, các ảnh REPLAY đến từ `TradeEngine`/`PaperDesk` thật chạy trên dữ liệu đã đốt, không có JSON viết tay.

## 2. Vì sao chủ cảm thấy "thiếu tính năng cơ bản" (nguyên nhân gốc, đo trên ảnh trước)

1. **Giá bị chôn**: giá là một dòng chữ nhỏ trong thanh tiêu đề, cạnh 7 chip trạng thái kỹ thuật (DATA, TRADING CORE, ACTIVE STRATEGY, PAPER DESK, FORWARD, DEMO, EDGE) và một dải cảnh báo tin tức rộng, nên biểu đồ bị đẩy xuống; trên điện thoại màn hình đầu không có biểu đồ.
2. **Thiếu ngữ cảnh thị trường**: không có thay đổi/cao/thấp/biên trong ngày, phiên hiện tại chỉ ở "chẩn đoán nâng cao" bằng mã tiếng Anh, không có giờ Việt Nam, không đếm ngược nến.
3. **Biểu đồ thiếu tiện ích chuẩn**: không có OHLC khi rê chuột, không có vừa khung / về nến mới nhất / theo nến / toàn màn hình; dữ liệu mới được nạp lại toàn bộ mỗi 3 giây; marker chỉ có tooltip (hover) và đặt sai nến ở khung thấp.
4. **Quyết định bị pha loãng**: trạng thái, kế hoạch, Why WAIT, vị thế, cảnh báo, phễu, chiến lược, forward, khóa DEMO… là ~14 thẻ cạnh tranh nhau; ngôn ngữ trộn Việt/Anh ("Why WAIT?", "Waiting for", "ACTIVE BASELINE").
5. **Quy trình lệnh kém an toàn/kém rõ**: xác nhận inline trong thẻ, đóng lệnh một cú bấm, không có thước R/R.
6. **Tính năng có nhưng ẩn hoặc thiếu**: Journal→biểu đồ, cảnh báo giá, đường ngang, công cụ đo, phím tắt, nhớ tùy chọn, máy tính lệnh khi không có setup: chưa có.

## 3. Kiểm kê trước khi làm (COMPLETE / PARTIAL / MISSING / DEFERRED / N/A)

| Hạng mục | Trước | Hạng mục | Trước |
|---|---|---|---|
| Giá live, bid/ask | PARTIAL (nhỏ) | Journal→biểu đồ | MISSING |
| Spread | COMPLETE (nhỏ) | Cảnh báo setup | PARTIAL |
| Thay đổi/cao/thấp/biên ngày | MISSING | Cảnh báo giá | MISSING |
| Phiên hiện tại | PARTIAL | Hỗ trợ/kháng cự, PDH/PDL | COMPLETE |
| Giờ Việt Nam | MISSING | Tô nền phiên | MISSING |
| Đếm ngược nến | MISSING | Đường ngang tự vẽ | MISSING |
| Nến, M1–H4 | COMPLETE | Công cụ đo | MISSING |
| Crosshair + OHLC | PARTIAL / MISSING | Phím tắt | MISSING |
| Đường giá hiện tại | PARTIAL | Nhớ tùy chọn | PARTIAL (chỉ múi giờ) |
| Vừa khung / Về mới nhất / Theo nến / Toàn màn hình | MISSING | Máy tính rủi ro | MISSING |
| Tick volume, volume tương đối | COMPLETE / PARTIAL | Vé lệnh PAPER, xác nhận mở | PARTIAL (inline) |
| BUY/SELL/WAIT, setup đang hình thành | COMPLETE / PARTIAL | Vị thế đang mở | COMPLETE |
| Marker + chi tiết khi bấm | COMPLETE / PARTIAL (hover) | Xác nhận đóng | MISSING |
| Entry/SL/TP | COMPLETE | Lịch sử lệnh/tín hiệu | COMPLETE |
| R/R trực quan | MISSING | Journal | COMPLETE |
| Bối cảnh đa khung | COMPLETE (dài dòng) | Hoạt động gộp | MISSING |

## 4. Quyết định A/B (thang điểm cố định, reviewer mù)

Thang 0–5 cho: hiểu trong 5 giây · thấy giá · thấy quyết định · tập trung biểu đồ · rõ kế hoạch · rõ hành động · mật độ thông tin · quen thuộc với trader · rõ lỗi · di động · trợ năng · (độ phức tạp, khả năng bảo trì được tôi tự đánh giá). Ảnh được ẩn danh, thứ tự ngẫu nhiên, reviewer là hai subagent không biết tôi nghiêng về phương án nào.

| Quyết định | Phương án | Điểm reviewer | Chọn |
|---|---|---|---|
| Bố cục chính | A: biểu đồ + cột vé bên phải · B: biểu đồ toàn rộng + bảng nổi | A 46 / B 38 | **A**: B che đúng vùng nến mới và nhãn Entry/SL/TP, nút hành động bị cắt |
| Thẻ quyết định | A: trạng thái lớn + chỉ số · B: pipeline trước | A 44 / B 39 | **A**: trạng thái là thứ đầu tiên mắt chạm tới, kể cả trên điện thoại |
| Vé lệnh | A: danh sách dọc · B: lưới 2 cột | A 40 / B 37 | **A**: giống vé của broker, ngắn hơn, nút hành động cao hơn |
| R/R | A: vùng tô mờ trên biểu đồ · B: thước R/R trong vé | hòa 40 / 40 | **B (thước)**: rõ hơn về R/R (4 vs 3) và không che nến; vùng tô gần như vô hình vì tín hiệu mới nằm sát mép phải. Reviewer chỉ ra thước ghi 2,00R trong khi vé ghi 1,78 sau spread, nên thước nay dùng **R/R ròng** |

Mã của phương án thua đã gỡ khỏi sản phẩm. Kiểm tra "5 giây" mù trên ảnh cuối (5 ảnh, 9 câu hỏi): đúng gần như toàn bộ (giá, quyết định, Entry/SL/TP, vị thế, live/replay); lỗi duy nhất là ảnh chụp CHỜ bị cuộn mất tiêu đề (đã sửa: mọi ảnh bắt đầu từ đầu trang) và nhãn LIVE xanh cạnh "thị trường đóng" gây thắc mắc.

## 5. Những thay đổi chính

* **Thanh thị trường**: giá bid cực lớn (phần thập phân nhỏ hơn), ask, spread, thay đổi trong ngày so với đóng cửa hôm trước, cao/thấp/biên, phiên (Á/Âu/Mỹ/chồng phiên, DST đúng), đồng hồ giờ Việt Nam, đếm ngược nến theo giờ máy chủ, giờ mở lại khi thị trường đóng, nhãn LIVE/REPLAY. Mọi con số do **máy chủ** tính trên ngày broker (`market_context`), trình duyệt không đoán ranh giới ngày.
* **Biểu đồ**: thanh công cụ ổn định, crosshair OHLC + thay đổi/biên/volume, đường giá hiện tại, vừa khung/về mới nhất/theo nến/toàn màn hình (cùng một phần tử, không tạo lại), marker bấm được với bảng chi tiết, đặt marker đúng nến theo khung (M1: nến đã đóng lúc có tín hiệu; M5: nến kích hoạt; ≥M15: nến chứa tín hiệu), thước R/R, đường ngang tự vẽ, công cụ đo, cảnh báo giá, nền phiên, cập nhật dữ liệu tăng dần để không reset zoom/pan.
* **Trung tâm quyết định**: trạng thái tiếng Việt chi phối (CHỜ · SETUP ĐANG HÌNH THÀNH · SẴN SÀNG MUA/BÁN · ĐANG CÓ VỊ THẾ PAPER · HẾT HẠN · KHÔNG THỂ TÍNH…), tiến trình setup bấm được (đổi khung), CHỜ hữu ích ("Đang chờ", "Đang bị chặn bởi", xu hướng, giai đoạn setup, hoạt động thị trường), vé lệnh, xác nhận bằng hộp thoại gắn với đúng setup/SL/TP/rủi ro, bảng vị thế (P&L lớn), xác nhận đóng với giá thực thi ước tính, máy tính lệnh khi không có setup.
* **Thông tin kỹ thuật** (forward acceptance, khóa DEMO, edge, phiên bản không chạy, telemetry, phễu) nằm ở tab **Hệ thống**; **Hoạt động** gộp tín hiệu, lệnh và cảnh báo; **Journal** có bộ lọc, tỷ lệ thắng, R trung bình, đường R tích lũy, xuất CSV, "xem trên biểu đồ".
* **Điện thoại**: giá → quyết định → biểu đồ → kế hoạch; thanh hành động cố định ở đáy ("Mở lệnh…" / "Đóng lệnh…") luôn qua hộp xác nhận.
* **Trợ năng**: axe-core (WCAG 2 A/AA) sạch ở sáng/tối, mọi tab và cả hai hộp thoại; bẫy tiêu điểm, Esc đóng, trả tiêu điểm, nền inert, không chỉ dùng màu, phím tắt có thể tắt.

## 6. Hiệu năng (trước/sau, cùng dữ liệu replay, 30 giây, Chromium)

| | Trước | Sau |
|---|---|---|
| Request / 30 s | 35 | 35 (không tăng) |
| CPU tác vụ / script | 356 ms / 177 ms | 331 ms / 143 ms |
| Tác vụ dài (>50 ms) | 0 | 0 |
| Chart bị tạo lại trong cửa sổ | 0 | 0 |
| Nút DOM | 528 | 334 |
| JS heap | 9,3 MB | 8,5 MB |

## 7. Đã hoãn / không làm và lý do

* **Lệnh tự do, SL/TP tùy ý, lệnh chờ, kéo SL/TP, trailing/chốt một phần**: ranh giới an toàn của repo (AGENTS.md: không có API nhận hướng/lot/SL/TP tùy ý) — NOT APPLICABLE, không phải thiếu sót.
* **Lịch kinh tế, DXY/US10Y, chỉ báo (MA/ATR), công cụ vẽ nâng cao (Fibonacci, trendline)**: cần dữ liệu/hạ tầng chưa có hoặc mở rộng phạm vi lớn so với giá trị — DEFERRED.
* **Cảnh báo giá phía máy chủ/đẩy**: sẽ cần hạ tầng nền mới; bản này chỉ chạy khi trang đang mở và nói rõ như vậy — DEFERRED có chủ đích.
