# TRADE-08 — báo cáo cuối: giao diện tín hiệu cho PAPER hằng ngày

Phạm vi: `/trade`, **chỉ PAPER**. Không gửi lệnh MT5, DEMO/FUNDED vẫn khóa, không khẳng định edge, không đổi chiến lược/ngưỡng/mô hình SL-TP/phiên bản mặc định (v1.1.0), không v1.3, không nghiên cứu alpha mới. Mọi bằng chứng cuối: backend replay thật hoặc stack LIVE thật, mở bằng trình duyệt thật.

**Kết luận: SIGNAL UI COMPLETE FOR DAILY PAPER USE — LIVE ACTIONABLE SIGNAL OBSERVATION STILL PENDING**

## 1. HEAD bắt đầu
`a8d939c648ad09b978e6df86c193807be73d8db3` (khớp; nhánh `main`, cây sạch, CI xanh 7/7 job, stack LIVE chạy build cũ).

## 2. HEAD cuối
`2b50ea3` (commit cuối của sprint; commit tài liệu cuối nằm sau nó). CI trên HEAD cuối được ghi ở mục 36.

## 3. Kiểm toán khoảng trống
`TRADE08_GAP_AUDIT.md`: giả thuyết "chỉ còn chờ LIVE" **sai**. Có 5 lỗi BROKEN, 5 điểm VISUALLY AMBIGUOUS, 2 PARTIAL tự sửa được; nay đều đã xử lý (xem cột "Trạng thái" cuối tệp đó).

## 4. Vì sao TRADE-07 chưa hoàn tất
Biểu đồ phone chỉ 87–93 px; "THEO DÕI MUA/BÁN" có thể đọc nhầm thành lệnh; đồng hồ replay nhảy; công cụ cá nhân không tách LIVE/REPLAY; mã nội bộ (`WRITER_LOCK`…) đi đầu câu; không có thời hạn giữ; ngang/zoom 200% có 0 px biểu đồ; chưa có phiên trình duyệt LIVE nào trên build mới nhất.

## 5. MEDIUM của TRADE-07 trước sprint
(1) WATCH đọc nhầm; (2) biểu đồ phone cramped; (3) đồng hồ đếm ngược replay nhảy; (4) localStorage không tách nguồn; (5) mã thô; (6) thiếu giải thích thuật ngữ; (7) thiếu `max_hold`; (8) LOW còn lại (popover, journal tiếng Anh, nhãn trục chồng nhau).

## 6. Các sửa chính
Hợp đồng server `hero.action` chỉ còn WAIT/BUY/SELL/HOLD/EXIT/UNAVAILABLE + `bias`/`missing` riêng; thẻ quyết định mới; bố cục phone + "short"; đồng hồ replay; khóa lưu trữ theo `xau-edge:v3:{LIVE|REPLAY}:XAUUSD:*` + migration; câu người trước, mã sau; tooltip; hạn giữ + đếm ngược; sự kiện gần nhất + thanh vòng đời; chống chồng nhãn trục giá/marker; marker SETUP; popover; mất kết nối gập kế hoạch; sửa gốc flake TIME-exit. Commit: `deff743` (08a), `e7aeddb` (08b), `bda42fb` (08c), `6ffe47e` (08d), `18017fa` (08e), `2b50ea3` (08f).

## 7. Các biến thể WATCH
Rubric cố định TRƯỚC khi chụp: `TRADE08_AB_RUBRIC.md`. A: dải thiên hướng phía trên; B: biểu ngữ viền đứt hổ phách; C: hai ô BIAS|HÀNH ĐỘNG; D (rút từ phát hiện vòng 1): CHỜ lớn + "KHÔNG VÀO LỆNH" + thiên hướng nhỏ, có nhãn, DƯỚI hành động.

## 8. Kết quả A/B mù
4 người chấm, 20 ảnh từ backend replay thật, tên trung tính/xáo trộn: A, B, C đều qua cổng cứng nhưng có điểm yếu (C: "↑ MUA" lớn cạnh CHỜ đọc thành "mua, chờ"; B: hổ phách như cảnh báo; A: ghi chú quá nhỏ). **D thắng**: qua cổng cứng 10/10 ảnh, thiên hướng luôn được đọc là "LEAN", chưa một lần "PERMISSION".

## 9. Từ vựng hành động cuối
Chính: **CHỜ · MUA PAPER · BÁN PAPER · GIỮ VỊ THẾ · ĐÃ THOÁT · KHÔNG KHẢ DỤNG**. Phụ (không phải hành động): Thiên hướng MUA/BÁN/TRUNG TÍNH, Setup (Chưa có / Đã hình thành, còn N nến M5 / Đã kích hoạt), "KHÔNG VÀO LỆNH".

## 10. Tách thiên hướng và hành động
`hero.action.code` ∈ 6 giá trị; `bias`, `missing`, `stage` là trường riêng. UI: hành động là chữ lớn duy nhất; thiên hướng là hàng nhỏ có nhãn bên dưới "chỉ là hướng thị trường nghiêng về, không phải lệnh". Chỉ READY mới có thẻ màu xanh/đỏ và nút mở lệnh (có test tự động trên 7 trạng thái).

## 11–15. BUY / SELL / WAIT / HOLD / EXIT
- **BUY/SELL**: "MUA/BÁN PAPER", Entry, SL, TP, TP2 (tham khảo), R/R sau spread, rủi ro, lot, thời hạn hiệu lực; một nút chính **ngay dưới thẻ** (trên màn hình đầu), thanh dính trên phone.
- **WAIT**: CHỜ + "Chỉ MUA/BÁN khi: <điều kiện thiếu cụ thể do server định nghĩa>"; thị trường đóng, hết hạn, vô hiệu, bị chặn, mất kết nối đều là CHỜ/KHÔNG KHẢ DỤNG có câu rõ.
- **HOLD**: "GIỮ VỊ THẾ" + "Chưa chạm điều kiện thoát nào." + SL/TP + **muộn nhất lúc HH:MM <múi giờ>** + luận điểm; vị thế có P&L, R, khoảng cách tới SL/TP.
- **EXIT**: "ĐÃ THOÁT" + lý do (Chạm TP/SL/Hết thời gian giữ…) + P&L + R + số phút; không còn lệnh MUA/BÁN nào sót lại (BLOCKED → CHỜ).

## 16. Đếm ngược giữ tối đa
`max_hold_until` (server, sẵn trong bản ghi vị thế) hiển thị "Giữ tối đa: tới 23:45 (GMT+7) · còn 2 giờ 0 phút" và trong câu HOLD; theo múi giờ đã chọn; không có hằng số đoán ở frontend.

## 17. Sửa đếm ngược
LIVE: đồng hồ server đã hiệu chỉnh lệch, **giảm/tăng đều** (đo trên LIVE: 31:55:26 → :25 → :23 → :22). REPLAY: chỉ chạy theo đồng hồ replay (`served_at`), không bao giờ dùng đồng hồ tường để bịa thời gian; test 6 giây đứng yên.

## 18. Bố cục di động
Rubric định trước: biểu đồ ≥ 280 px, thấy giá + hành động + một câu "khi nào", không cuộn. Phương án A/B/C đo trên replay thật: B (biểu đồ trước) loại ở cổng cứng (hành động ở y≈902); người chấm mù xếp C > A > B. Trước 87–93 px → **288–352 px (replay), 383–411 px (LIVE)**. Ngang 844×390 và zoom 200% (trước **0 px**) có bố cục hai cột: **192 / 234 px (LIVE)**; nút mở lệnh với tới được không cần cuộn.

## 19. Dọn ngôn ngữ lỗi
Câu tiếng Việt trước; mã + câu của server dưới "Chi tiết kỹ thuật". Áp dụng cho banner điều kiện, mất API, hero KHÔNG KHẢ DỤNG (nói **một lần**), từ chối lệnh (`DECISION_CHANGED`… → tiếng Việt), System tab, Journal. Kiểm tự động bằng `innerText`.

## 20. Tooltip / giải thích
Bid, Ask, Spread, R/R, R, MFE, MAE, Tick volume, Thiên hướng, Setup, Trigger, SL, TP, Entry, Rủi ro, Lot, Giữ tối đa, PAPER: hover, focus bàn phím, Esc đóng, `aria-describedby`.

## 21. Namespacing localStorage
`xau-edge:v3:{LIVE|REPLAY}:XAUUSD:{alerts|levels}`; nhãn "Chỉ dùng cho: LIVE XAUUSD" ở Công cụ của tôi. Migration một lần, không phá hủy: khóa cũ chỉ được **LIVE** nhận (replay không động tới), chỉ khi scope chưa có dữ liệu riêng. Có 4 test đơn vị + e2e (LIVE không thấy công cụ REPLAY; khóa cũ).

## 22. Marker / popover
Marker SETUP; nhãn marker nhường nhau theo khoảng cách pixel (shape + chi tiết vẫn còn); popover nêu **múi giờ hiển thị**, **giờ thoát**, MUA/BÁN thống nhất, vừa màn hình phone; Esc đóng; bấm trong ±14 px.

## 23. Va chạm trục giá
Thứ hạng ENTRY/SL/TP/PAPER > giá cuối > NOW/TP2 > đường của tôi > cảnh báo > cấu trúc; nhãn trục thấp hạng nhường (đường vẫn còn, tên nằm trong legend); phone chỉ giữ nhãn giá. Test: 5 công cụ + giá cuối trong một chiều cao nhãn → nhường đúng; đường xa nhau giữ nguyên.

## 24. Mất kết nối
Đo LIVE thật 66 s (phía trình duyệt): KHÔNG KHẢ DỤNG, banner người-trước, tuổi dữ liệu **vẫn đếm** ("GIÁ CŨ · 17.4 giờ"), pill "Mất kết nối", không thanh hành động, kế hoạch cũ gập lại, biểu đồ không vẽ kế hoạch.

## 25. Nối lại
Sau ≤ 8 s API quay lại: tự hồi phục, không reload (LIVE thật + test đồng hồ giả).

## 26. Race
Double-click mở/đóng với mạng chậm → đúng 1 hoạt động PAPER (real-API acceptance + red team); setup đổi dưới modal → nút xác nhận bị vô hiệu / server từ chối `DECISION_CHANGED`; setup đã dùng → CHỜ (blocked), không BUY thứ hai.

## 27. Bằng chứng LIVE
`TRADE08_LIVE_BROWSER_ACCEPTANCE.md`; ảnh `img/trade08/live/`. 1440, 1920, 390×844, 844×390, 720×450 (≈ zoom 200%), tối desktop + di động, tương tác (khung, crosshair, zoom, pan, fit, latest, follow, fullscreen, tab, tooltip, đường ngang, cảnh báo, Journal), đồng hồ/đếm ngược, mất kết nối. **Thị trường đóng (thứ Bảy)** nên đây là bằng chứng hạ tầng/giao diện LIVE, không phải tín hiệu LIVE.

## 28. Bằng chứng replay
`img/trade08/replay/`: WAIT, WATCH BUY, WATCH SELL, BUY READY (+xác nhận), SELL READY, HOLD, EXIT, INVALIDATED, UNAVAILABLE; di động `replay-m-*`. Nhãn `ACCEPTANCE REPLAY — KHÔNG PHẢI LIVE` ở mọi ảnh.

## 29. Five-second
Ba vòng độc lập (người chấm mới, ảnh xáo trộn): vòng cuối **trên build cuối**, 11 ảnh (phone + desktop + LIVE đóng cửa): symbol, giá, hành động, **cho phép hay chỉ thiên hướng (11/11 đúng)**, hướng, điều còn thiếu, Entry/SL/TP, HOLD/EXIT + lý do/hạn, LIVE hay replay đều trả lời đúng; độ tự tin 3–5. Không ai nhầm WATCH là lệnh. Phát hiện còn lại đã sửa (huy hiệu LIVE khi đóng cửa, "GIÁ CŨ · 0s") hoặc ghi ở mục 37.

## 30. Người mới (novice)
Người kiểm mới, không tài liệu: hiểu thiên hướng ≠ cho phép, đọc Entry/SL/TP, mở PAPER an toàn (focus mặc định ở "Hủy"), hiểu HOLD/EXIT, xem lịch sử. 4 MEDIUM (Entry/Rủi ro/Lot chưa có giải thích; múi giờ không nhãn; setup vô hiệu không chỉ chỗ xem lý do; "Chưa có điều kiện thoát" dễ đọc sai) → **đã sửa** (08e).

## 31. Trader có kinh nghiệm
Hỏi không dẫn dắt. Mua/Bán/Đứng ngoài/Thoát: "PARTLY/PARTLY/YES/YES-trong-khi-mở". Ghi nhận trung thực: người chấm chỉ thấy ảnh replay (6/7 ảnh) nên nói "chưa tin trên ngày bận"; nêu thuật ngữ khó hiểu (đã thêm giải thích Entry/Rủi ro/Lot/Giữ tối đa/R), nhập nhằng "BÁN vừa mở short vừa đóng long" (hành động luôn nói "MUA/BÁN PAPER" cho mở và "ĐÃ THOÁT" cho đóng), "chạm SL" vs "đóng nến vượt SL" (kế hoạch vô hiệu và thoát lệnh paper là hai quy tắc khác nhau của server; còn ghi ở mục 37).

## 32. Red team
Hai vòng độc lập + tự kiểm: vòng 2 (14+ hướng tấn công): **1 HIGH** (từ chối lệnh lộ tiếng Anh/mã) và **4 MEDIUM** (đổi múi giờ làm mất nến hiện tại; tuổi dữ liệu "0s" khi offline; nút mở lệnh dưới màn hình ở ngang/zoom; migration vào nguồn load đầu tiên) + 5 LOW → **tất cả HIGH/MEDIUM đã sửa** (08d), mỗi lỗi có test hồi quy, mình chạy lại từng repro trên trình duyệt thật. Đã chống chịu: mọi cách làm hiện nút mở lệnh ở WATCH/ARMED (phím, Tab, fullscreen), mất API 65 s, stale, đóng cửa, hết hạn dưới modal, đổi thế giới dưới modal, double-click, rò mã, bẫy focus, đổi nhanh khung/tab. **Không chạy vòng red team thứ ba** sau các sửa (đã kiểm bằng test hồi quy + chạy lại repro).

## 33. Lỗi chỉ thấy trên trình duyệt
Marker/popover/follow (TRADE-07); ở TRADE-08: separator z-50 của thư viện đè thanh hành động; "Về hiện tại" bị tắt follow lại; 0 px biểu đồ ở ngang/zoom; chip chiến lược tràn ngang; refit khi đổi múi giờ; tuổi dữ liệu đứng 0s; huy hiệu LIVE xanh khi đóng cửa; 3 lần lặp câu lỗi; lệnh bị từ chối lộ tiếng Anh; nhãn đường đè nến cuối trên phone.

## 34. Kiểm thử tự động (chạy mới trên HEAD cuối)
- `ruff check`: pass. `ruff format --check`: 634 tệp đã định dạng. `mypy --strict`: 239 tệp, pass.
- `pytest -m "not mt5"`: **2565 passed, 1 skipped** (symlink cần quyền trên Windows), 3 deselected, 0 xfail.
- `pytest -m mt5`: **3 passed**.
- `eslint`: sạch. `tsc --noEmit`: sạch. `next build`: thành công.
- Playwright mock (có axe sáng+tối, 233→**241** test sau các vòng): **241 passed**.
- Playwright backend thật (acceptance): **31 passed**, exit 0, không lỗi worker.
- axe: nằm trong bộ mock (`a11y.spec`), sáng + tối + modal + phone: không vi phạm serious/critical.
(Python không đổi sau lần chạy đầy đủ; các commit sau đó chỉ đổi TS/tài liệu và được CI chạy lại.)

## 35. Điều tra flake
Gốc: **race của test**, không phải lỗi sản phẩm. Banner EXITED chỉ kéo dài 30 phút replay sau lúc đóng; replay bước từng nến M5; nhảy 180 phút làm lệnh thoát ở +120 đã quá 60 phút → chỉ thấy EXITED nếu một lần poll rơi đúng giữa lúc replay đang bắt kịp. Sửa: test đi 110 rồi 15 phút (trong cửa sổ), test Python ghim hành vi (HOLD → EXIT → hết banner nhưng `last_exit` còn). Không còn "chạy lại là xanh".

## 36. CI
Ghi sau khi push: xem phần "CI trên HEAD cuối" ở cuối tệp này.

## 37. LOW còn lại (trung thực)
- Nhãn marker "TP" bị cắt ở mép phải (thư viện biểu đồ), legend vẫn liệt kê đủ.
- Phone ở CHỜ không có checklist (chỉ câu "Chỉ MUA khi…"); header còn nhiều số.
- "5:00" là hiệu lực tín hiệu (có chữ "còn hiệu lực"), người chấm đôi khi nhầm với đóng nến.
- Màu đỏ mang 3 nghĩa (replay, lỗi, BÁN); dải replay chiếm ~30 px mọi màn hình.
- "Chạm SL" (thoát lệnh paper) và "đóng nến vượt SL" (kế hoạch vô hiệu) là hai quy tắc khác nhau của server; câu chữ chưa gộp.
- Một lần `hero` không hiện trong 30 s ngay sau khi khởi động lại stack LIVE (không tái hiện được; xem báo cáo LIVE).
- Sức khỏe feed của collector báo "DEGRADED: 5–10 stored bar(s) differ from the terminal" (đồng nhất bar đã lưu), ngoài phạm vi sprint này.

## 38. Tín hiệu LIVE thật
**LIVE ACTIONABLE SIGNAL NOT YET OBSERVED.** Forward acceptance vẫn F0. Replay không nâng được F-level; không bịa BUY/SELL LIVE.

## 39. Chủ sở hữu có thể làm gì hôm nay
Mở `http://127.0.0.1:3000/trade`: một từ cho biết được phép làm gì; thấy ngay hướng thị trường nghiêng về (chỉ là mô tả), điều còn thiếu để MUA/BÁN được phép, và khi đã mở PAPER thì thời hạn thoát muộn nhất; nếu API/dữ liệu hỏng, trang nói KHÔNG KHẢ DỤNG bằng câu thường. Dùng tốt nhất trên máy tính (biểu đồ lớn) hoặc điện thoại dọc/ngang. Mọi lệnh đều là PAPER.

## Bảng hoàn thành (BACKEND / API / UI / TEST / REPLAY / LIVE / REVIEWER)

| trạng thái | BACKEND | API | UI | AUTO TEST | REPLAY BROWSER | LIVE BROWSER | REVIEWER | STATUS |
|---|---|---|---|---|---|---|---|---|
| WAIT | có | có | có | có | có | **có** (thị trường đóng) | 5-giây ×3, novice | PASS |
| BIAS MUA | có | có | có | có | có | — (cần thị trường mở) | 5-giây ×4 vòng, A/B | PASS (replay) |
| BIAS BÁN | có | có | có | có | có | — | 5-giây, A/B | PASS (replay) |
| BUY READY | có | có | có | có | có | — (chưa có tín hiệu LIVE) | 5-giây, novice, trader | PASS (replay) |
| SELL READY | có | có | có | có | có | — | 5-giây, trader | PASS (replay) |
| HOLD | có | có | có | có | có | — | 5-giây, novice | PASS (replay) |
| EXIT | có | có | có | có | có | — | 5-giây, novice | PASS (replay) |
| EXPIRED | có | có | có | có | có | — | red team | PASS (replay) |
| INVALIDATED | có | có | có | có | có | — | red team, novice | PASS (replay) |
| UNAVAILABLE | có | có | có | có | có | **có** (mất kết nối 66 s) | 5-giây, red team | PASS |

Số vòng lặp: A/B thẻ hành động 2 vòng (4 người chấm) + A/B di động 1 vòng + 5 vòng sửa sau trình duyệt/độc lập (08b–08f).

## Câu hỏi cuối (từ giao diện thật)
1. **MUA / BÁN / CHỜ / GIỮ / THOÁT bây giờ?** → đúng một từ ở thẻ hành động (LIVE hiện tại: CHỜ, thị trường đóng).
2. **Nếu CHỜ, có thiên hướng không?** → hàng "Thiên hướng ↑ MUA / ↓ BÁN / TRUNG TÍNH" (chỉ khi bộ máy đang đánh giá).
3. **Điều kiện còn thiếu?** → "Chỉ MUA/BÁN khi: …" cụ thể + checklist "Điều kiện vào lệnh: đạt n/8 — cần đủ tất cả".
4–5. **Khi nào MUA/BÁN thành hành động?** → khi nến M5 đóng xác nhận trigger và kế hoạch đầy đủ, hành động chuyển thành MUA/BÁN PAPER.
6. **HOLD do đâu?** → "Chưa chạm điều kiện thoát nào" + luận điểm.
7. **Điều gì gây thoát?** → chạm SL, chạm TP, hoặc hết thời gian giữ (và đóng cửa/thị trường theo chính sách).
8. **TIME_EXIT lúc nào?** → "muộn nhất lúc HH:MM <múi giờ>" và "còn X giờ Y phút".

## CI trên HEAD cuối
(điền sau khi push)
