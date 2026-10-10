# TRADE-08 — nghiệm thu trình duyệt trên stack LIVE (:3000)

**GIAO DIỆN LIVE đã được mở, dùng và kiểm bằng trình duyệt thật trên bản build mới nhất. KHÔNG có tín hiệu LIVE hành động (BUY/SELL) nào xảy ra: `LIVE ACTIONABLE SIGNAL NOT YET OBSERVED`.** Vòng đời BUY/SELL/HOLD/EXIT được nghiệm thu trên replay thật (route, engine, desk, journal thật), xem `TRADE08_FINAL_REPORT.md`.

## Môi trường

| | |
|---|---|
| build SHA | `2b50ea3` (HEAD cuối; phiên LIVE chính chạy trên `18017fa`, sau đó chỉ đổi một chuỗi nhãn giá và đã chạy lại LIVE rồi kiểm nhanh 1440 + 390) |
| khởi động lại stack | `scripts\stop_market_stack.ps1` rồi `start_market_stack.ps1 -Dashboard` (không kill MT5) ngay sau lần build cuối; kiểm API trả `hero.action.bias/missing` (mã mới) và dashboard phục vụ chuỗi UI mới |
| sức khỏe lúc khởi động | `GOOD`, collector chạy, heartbeat 4 s. Về sau `status_market_stack` báo "Feed health DEGRADED: 5–10 stored bar(s) differ from the terminal" — **vấn đề đồng nhất dữ liệu bar đã lưu của collector, không thuộc sprint UI này, không đụng tới**; bar mới nhất còn FRESH, thị trường ĐÓNG |
| công cụ trình duyệt | Playwright MCP (chuột/bàn phím thật theo tọa độ) + Chrome DevTools MCP (giả lập di động có cảm ứng) |
| thời điểm | thứ Bảy 2026-10-10, chiều–tối giờ Việt Nam; thị trường **ĐÓNG** đến 2026-10-12 05:05 (GMT+7) |
| thị trường | XAUUSD bid 4195.09 / ask 4195.52, spread 43 điểm (0.43), dữ liệu cuối 17.2 giờ trước, phiên gần nhất +62.37 (+1.51%) |

## Màn hình đầu (LIVE)

| mục | quan sát |
|---|---|
| nhãn nguồn | **LIVE · ĐÓNG CỬA** (xám, không phải "go" xanh) + "Thị trường ĐÓNG" + "PAPER · không gửi lệnh thật" |
| hành động | **CHỜ** + nhãn **KHÔNG VÀO LỆNH**; "Khi nào? Chưa làm gì. Bộ máy tự tính lại khi thị trường mở cửa." (không có dòng Thiên hướng/Setup khi đóng cửa) |
| giá | bid/ask/spread, "Giá đóng cửa gần nhất · 17.x giờ trước", biến động ngày |
| phiên / đồng hồ | "Ngoài giờ giao dịch", đồng hồ VN **tăng đều** 21:09:33 → :34 → :36 → :37 |
| đếm ngược | "Mở lại lúc 10-12 05:05 · còn 31:55:26 → :25 → :23 → :22" (**giảm đều**) |
| tuổi dữ liệu | "dữ liệu: 17.2 giờ" |
| tin tức | không có cảnh báo (thị trường đóng) |
| bàn PAPER | Equity $10000.00, 0 lệnh/6, lỗ ngày 0.00% / 2%, trạng thái "SẴN SÀNG · READY — đã khớp nhật ký" |
| System tab | tiếng Việt trước, mã sau: `ĐÓNG · CLOSED`, `ĐANG CHẠY · RUNNING`, `ĐÃ KHÓA · LOCKED`, "Baseline vận hành, chưa phải lợi thế đã kiểm chứng" |

## Màn hình và tương tác đã chạy trên LIVE

| viewport | biểu đồ nhìn thấy | tràn ngang | ảnh |
|---|---|---|---|
| 1440×900 | 608 px | không | `img/trade08/live/final-live-1440x900.png` |
| 1920×1080 | 608 px | không | `final-live-1920x1080.png` |
| 390×844 (di động, cảm ứng) | 383–411 px | không | `final-live-390x844.png`, `live-390x844-mobile.png` |
| 844×390 (ngang) | 192 px | không | `final-live-844x390-landscape.png`, `live-844x390-landscape.png` |
| 720×450 (≈ zoom 200%) | 234 px | không | `final-live-zoom200-720x450.png` |
| tối 1440×900 | 608 px | không | `final-live-dark-1440x900.png` |
| tối 390×844 | 383 px | không | `final-live-dark-390x844.png` |

Tương tác bằng chuột/bàn phím thật: đổi khung M1/H1/M5; crosshair + OHLC (đọc khác nhau theo từng nến); zoom (wheel), pan (kéo) làm theo-nến TẮT, "Về hiện tại" bật lại; Fit (F), Latest (L); toàn màn hình (X, Esc); 5 tab; tooltip Spread; đường ngang thủ công + cảnh báo giá 4300 → lưu ở khóa `xau-edge:v3:LIVE:XAUUSD:*`, nhãn **"Chỉ dùng cho: LIVE XAUUSD"**, còn sau reload, rồi dọn sạch (`final-live-tools-level-alert.png`); Journal → quay lại Trade (`final-live-journal.png`).

## Mất kết nối > 60 giây (thời gian thật, phía trình duyệt) và nối lại

| thời điểm | quan sát |
|---|---|
| trước | CHỜ, không banner |
| +20 s | hero **KHÔNG KHẢ DỤNG**, pill "Mất kết nối" |
| +66 s | hero KHÔNG KHẢ DỤNG; banner "Mất kết nối với máy chủ dữ liệu… đây KHÔNG phải trạng thái CHỜ; không được vào lệnh. Trang sẽ tự cập nhật…" (+ Chi tiết kỹ thuật); **"GIÁ CŨ · 17.4 giờ"** và **"dữ liệu: 17.3 giờ"** vẫn đếm; không có thanh hành động (`final-live-offline-66s.png`) |
| API trở lại | sau ≤ 8 s, **không reload**: CHỜ, banner biến mất, pill "Thị trường ĐÓNG" (`final-live-reconnected.png`) |

## Lỗi tìm thấy trong chính phiên LIVE / vòng nghiệm thu và cách xử lý

| lỗi | mức | commit sửa | retest |
|---|---|---|---|
| Ngang 844×390 và zoom 200%: **0 px** biểu đồ ở màn hình đầu | MEDIUM | TRADE-08b | LIVE 192 / 234 px; 14 test cổng chạy ở CI |
| Thị trường đóng nhưng thẻ vẫn nói "Thiên hướng: TRUNG TÍNH… Setup: Chưa có" | MEDIUM | TRADE-08b | LIVE: dòng đó biến mất khi đóng cửa |
| System tab tiếng Anh (`CLOSED the market is closed`) | LOW | TRADE-08b | LIVE: tiếng Việt + mã |
| Huy hiệu xanh "LIVE" cạnh dữ liệu cũ 13 giờ (người chấm five-second) | MEDIUM | TRADE-08c | LIVE: "LIVE · ĐÓNG CỬA" xám |
| Header vẫn "0s"/"Thị trường MỞ" khi mất API (red team) | MEDIUM | TRADE-08d | LIVE: "GIÁ CŨ · 17.4 giờ", "Mất kết nối" |

## Ghi chú trung thực

- Một lần `hero` không hiện trong 30 s ngay sau khi khởi động lại stack (phiên Playwright còn sót route chuyển :8000→:8100 từ phiên replay có thể là nguyên nhân; API LIVE trả lời ~25 ms, trang phục vụ 2 ms, 9 lần tải sau đó đều ổn). Chưa tái hiện được; ghi lại, không coi là lỗi đã loại trừ.
- Phía server của bài thử mất kết nối không bị đụng tới (chỉ chặn request ở trình duyệt).
- Không mở/đóng lệnh PAPER trên LIVE (thị trường đóng; không bịa BUY/SELL LIVE).
