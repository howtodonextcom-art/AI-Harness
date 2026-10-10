# Terminal giao dịch PAPER: báo cáo cuối (TRADING_TERMINAL_UI_FINAL)

HEAD khởi đầu `6d75582efac82b71b22815f3771c8c7a3473f76a`. Các commit của sprint: `38a45ac` (06a), `56370f4` (06b), `e4fe16f` (06c), `b9396b7` (06d), `7ecd477` (06e), `b4d6391` (06f), `06g` (xem `git log`). Phạm vi: sản phẩm và giao diện. Không đổi chiến lược, ngưỡng, tần suất tín hiệu, SL/TP, phiên bản mặc định (v1.1.0); không có lệnh MT5; DEMO/FUNDED vẫn KHÓA. Ảnh trước/sau, quyết định A/B và đo hiệu năng: `TRADING_UI_BEFORE_AFTER.md`.

## 1. Kỹ năng ECC và cách dùng

Đã tìm trong `ECC/skills` (293 skill), `AGENTS.md`, `CLAUDE.md`, `.claude/`.

| Skill | Mục đích | Dùng? |
|---|---|---|
| `frontend-design-direction` | hướng thiết kế: công cụ dùng hằng ngày thì dày, yên tĩnh, dễ quét, không thẻ-trong-thẻ, thanh công cụ ổn định | Có: thanh thị trường, bố cục, kiểm kê kiểm tra bằng checklist |
| `frontend-a11y` | modal, tab, form, ARIA, focus | Có: bẫy tiêu điểm, roving tabindex, `inert`, nhãn |
| `browser-qa` | ảnh 3 breakpoint + axe-core | Có: Playwright trên build production, axe WCAG 2 A/AA sáng/tối |
| `e2e-testing` | mẫu Playwright, chống test flaky | Có: chờ hydrate, golden thật thay mock viết tay |
| `react-patterns`, `react-performance` | hook/effect/re-render | Có: tránh setState trong effect, cập nhật tăng dần, đo trước/sau |
| `verification-loop` | build, type, lint, test, diff | Có: gate đầy đủ mỗi vòng |
| `product-lens` | hành trình người dùng | Có: kiểm kê "5 giây" và các vòng review trader |
| `design-system`, `dashboard-builder`, `tdd-workflow`, `security-review` | khác | Xem xét, không cần thêm |

Chỉ dẫn repo cao hơn prompt: `AGENTS.md` cấm API nhận hướng/lot/SL/TP tùy ý và mọi đường gửi lệnh. Vì thế "lệnh tự do" và "kéo SL/TP" là NOT APPLICABLE, không phải thiếu sót.

## 2. Các vấn đề của UI ban đầu, ý tưởng, A/B

Nguyên nhân gốc "thiếu tính năng cơ bản" (đo trên ảnh baseline thật 1440/1920/390/zoom200/tối): giá nhỏ giữa 7 chip kỹ thuật, không có ngữ cảnh ngày/phiên/đồng hồ/đếm ngược, biểu đồ thiếu tiện ích chuẩn và bị đẩy xuống, ~14 thẻ cạnh tranh, ngôn ngữ trộn, xác nhận inline và đóng lệnh một cú bấm. Mỗi vấn đề có 2–3 hướng; bốn quyết định lớn được A/B bằng ảnh thật với thang điểm cố định và reviewer mù (thứ tự ngẫu nhiên, tên trung tính):

| Quyết định | A | B | Chọn |
|---|---|---|---|
| Bố cục chính | biểu đồ + cột vé 46 | bảng nổi trên biểu đồ 38 | **A** |
| Thẻ quyết định | trạng thái chi phối 44 | pipeline trước 39 | **A** |
| Vé lệnh | danh sách dọc 40 | lưới 37 | **A** |
| R/R | vùng tô mờ 40 | thước R/R 40 (rõ hơn 4 vs 3) | **B**, dùng R/R ròng |

Mã phương án thua đã gỡ. Bằng chứng thêm: bài kiểm tra "5 giây" mù (đúng gần như toàn bộ), và bốn vòng review trader (mục 52).

## 3. Báo cáo 61 mục

1. **HEAD khởi đầu:** `6d75582`.
2. **HEAD cuối:** xem `git log` (commit `TRADE-06h` là commit tài liệu cuối).
3. **Skill ECC tìm thấy:** 293 trong `ECC/skills`; liên quan: 11 (mục 1).
4. **Skill thực dùng:** frontend-design-direction, frontend-a11y, browser-qa, e2e-testing, react-patterns, react-performance, verification-loop, product-lens.
5. **Vấn đề UI baseline:** mục 2 và `TRADING_UI_BEFORE_AFTER.md` §2.
6. **Ý tưởng đã sinh:** thanh giá 3 kiểu (hai ô bid/ask · một giá giữa · header kiểu TradingView → chọn bid lớn + ask/spread nhỏ); bố cục 2; thẻ quyết định 2; vé 2; R/R 2 (vùng tô, thước); mobile (thanh hành động cố định, bottom sheet → chọn thanh cố định).
7. **Biến thể A/B đã thử:** 4 quyết định × 2 phương án = 8 biến thể, chụp desktop và điện thoại.
8. **Thang điểm:** 11 tiêu chí 0–5 cố định (hiểu 5 giây, thấy giá, thấy quyết định, tập trung biểu đồ, rõ kế hoạch, rõ hành động, mật độ, quen thuộc, rõ lỗi, di động, trợ năng) + độ phức tạp/bảo trì tôi tự chấm; thang không đổi sau khi thấy kết quả.
9. **Người thắng:** bố cục A, thẻ A, vé A, thước R/R (B).
10. **Bố cục chính:** thanh thị trường → lưới (biểu đồ + cột quyết định, dải đa khung dưới biểu đồ) → tab; điện thoại: giá → quyết định → biểu đồ → kế hoạch.
11. **Thanh thị trường:** có (`MarketBar`).
12. **Giá live:** bid cỡ lớn, ask, spread (điểm và giá).
13. **Thay đổi ngày/cao/thấp/biên:** có, tính ở máy chủ trên ngày broker (`market_context`), so với đóng cửa hôm trước.
14. **Phiên:** có, Á/Âu/Mỹ/chồng phiên, DST đúng, bảng ghim giữa Python và trình duyệt.
15. **Đếm ngược:** có, theo lưới nến đã đóng và giờ máy chủ; khi đóng cửa hiện giờ mở lại (`next_open`).
16. **Crosshair OHLC:** có (O/H/L/C, thay đổi, biên, volume; nến cuối khi không rê).
17. **Đường giá hiện tại:** có, khác biệt với ENTRY/PAPER ENTRY/SL/TP.
18. **Thanh công cụ biểu đồ:** M1–H4, vừa khung, mới nhất, theo nến, toàn màn hình, đo, đường ngang, cảnh báo giá, lớp phủ, phím tắt.
19. **Toàn màn hình:** có, cùng một phần tử (không tạo lại), giữ khung/marker/Entry/SL/TP/vị thế và nút hành động; Esc thoát.
20. **Fit/Latest/Follow:** có; chỉ thao tác kéo/lăn của người dùng mới tắt Follow; nến mới không kéo biểu đồ về; cập nhật tăng dần nên không reset zoom/pan.
21. **Tương tác marker:** có, bấm vào nến có marker mở bảng chi tiết (cả bằng bàn phím).
22. **Sửa lệch marker:** có; M1: nến đã đóng lúc có tín hiệu; M5: nến kích hoạt; ≥M15: nến chứa tín hiệu; test đơn vị + 4 khung trong trình duyệt.
23. **Entry/SL/TP:** ENTRY nét liền, SL nét đứt, TP chấm; nhãn trục và chú giải; không chỉ màu.
24. **Trực quan R/R:** thước R/R ròng trong vé; vùng tô thua A/B và đã gỡ.
25. **Trung tâm quyết định:** có, 11 trạng thái tiếng Việt, tính ở máy chủ.
26. **Trải nghiệm CHỜ:** tiến trình "đạt x/8", "Đang chờ", xu hướng, giai đoạn setup, hoạt động thị trường, cảnh báo tin tức.
27. **Pipeline setup:** có, bấm đổi khung.
28. **Dải đa khung:** có, bấm đổi khung.
29. **Hoạt động thị trường:** biến động / tick / spread (tab Tổng quan và thẻ CHỜ).
30. **Vé lệnh:** có (Entry, SL, TP, TP2, R/R ròng, rủi ro %, tiền, lot, lãi nếu TP, thước R/R, điều kiện vô hiệu).
31. **Xác nhận mở:** hộp thoại gắn với đúng setup/SL/TP/rủi ro; kế hoạch đổi thì vô hiệu; hiện độ lệch giá theo R và giới hạn hủy 0,25R.
32. **Bảng vị thế:** P&L lớn, R, giá vào/kế hoạch/hiện tại, SL/TP, khoảng cách tới SL/TP (giá và R), lot, thời gian, MFE/MAE.
33. **Xác nhận đóng:** có, giá thực thi ước tính, P&L, R, mã lệnh; cảnh báo khi mất kết nối.
34. **Hoạt động gần đây:** tab gộp tín hiệu, setup đã hình thành (kể cả hết hạn khi chưa ai mở), lệnh, cảnh báo; bấm để nhảy tới biểu đồ.
35. **Journal → biểu đồ:** có (liên kết `/trade?focus=…&tf=…`; focus một lần).
36. **Cảnh báo:** cảnh báo setup (Telegram/file), thông báo "setup sẵn sàng" (tiêu đề tab, Notification, âm báo tùy chọn), thông báo kênh ngoài trình duyệt.
37. **Máy tính rủi ro:** có, "CHỈ LÀ MÁY TÍNH — KHÔNG PHẢI TÍN HIỆU".
38. **Cảnh báo giá:** có, lưu cục bộ, chỉ khi trang mở và dữ liệu LIVE, báo một lần; hỗ trợ dấu phẩy thập phân.
39. **Đường ngang tự vẽ:** có, nhớ lại, xóa được.
40. **Công cụ đo:** có (chênh giá, điểm, %, số nến, phút).
41. **Nền phiên:** có, DST đúng (Intl + bảng ghim với Python).
42. **Phím tắt:** có, an toàn (không phím nào mở/đóng lệnh), có thể tắt (WCAG 2.1.4).
43. **Lưu tùy chọn:** khung, lớp phủ, theo nến, múi giờ, tab, mức rủi ro, phím tắt, thông báo; kiểm tra khi đọc; không lưu quyền giao dịch/chiến lược/thông tin đăng nhập (có test).
44. **Desktop 1440×900 và 1920×1080:** đạt; giá, quyết định, biểu đồ, dải đa khung đều trong màn hình đầu.
45. **Điện thoại 390×844:** đạt; biểu đồ trong màn hình đầu, thanh hành động cố định, không cuộn ngang.
46. **Zoom 200%:** đạt (720×450 CSS px), không cuộn ngang.
47. **Chế độ tối:** đạt; ảnh LIVE + replay.
48. **Trợ năng:** axe-core WCAG 2 A/AA sạch (sáng/tối × 7 trạng thái × mọi tab × hai modal × điện thoại); bẫy tiêu điểm, Esc, trả tiêu điểm, nền inert, roving tab, không chỉ dùng màu.
49. **Hiệu năng (đo ở commit 06b):** cùng 35 request/30 s, CPU tác vụ 331 vs 356 ms, 0 tác vụ dài, 0 lần tạo lại chart, DOM 334 vs 528.
50. **Kịch bản LIVE thật:** thị trường đóng (cuối tuần) trên stack sống, 6 ảnh LIVE sáng/tối/mobile/zoom; BUY/SELL live chưa xảy ra (tần suất thấp).
51. **Kịch bản replay:** BUY/SELL thật, mở, đóng tay, SL/TP/TIME, stale, expired, paper hỏng, hai writer, API down, thị trường đóng, gần giờ đóng; 21 ca trình duyệt thật trên API replay thật.
52. **Review UX độc lập:** 4 vòng (xem mục 4); vòng cuối: **YES, dùng được hằng ngày**.
53. **Review kỹ thuật độc lập:** 2 vòng (xem mục 4).
54. **Lỗi tìm thấy:** mục 4 (3 HIGH, 9 MEDIUM, thêm các LOW).
55. **Lỗi đã sửa:** tất cả HIGH và MEDIUM xác nhận được; test hồi quy cho từng lỗi.
56. **LOW còn lại:** mục 5.
57. **Ma trận tính năng cơ bản:** mục 6.
58. **Tính năng hoãn và lý do:** mục 7.
59. **Số test:** `pytest -m "not mt5"` 2545 passed, 1 SKIP (symlink cần quyền trên Windows), 0 XFAIL; `pytest -m mt5` 3 passed; dashboard 175 test (89 e2e mock trên golden thật, unit thuần, 17 axe, journal, các hồi quy review) + 21 ca nghiệm thu trình duyệt thật trên API replay; ruff, `mypy --strict`, eslint, `tsc`, `next build` PASS.
60. **CI:** xanh trên `384db68` (Windows và Ubuntu py3.12–3.14, dashboard lint/types/build); commit tài liệu cuối chỉ đổi Markdown
61. **Chủ có thể làm gì hôm nay:** mở `/trade`, đọc giá/ngữ cảnh/trạng thái, xem kế hoạch, mở và đóng lệnh paper qua hộp xác nhận, xem vị thế, hoạt động, journal (lọc, thống kê, CSV), đặt cảnh báo giá, vẽ đường ngang, đo, bật thông báo setup. Việc của chủ: cấu hình Telegram (cảnh báo khi đóng trình duyệt), cung cấp nguồn lịch kinh tế nếu muốn.

## 4. Các lỗi tìm thấy qua review độc lập và cách xử lý

**Review kỹ thuật vòng 1** (đọc mã, 11 mục): 2 HIGH (focus của biểu đồ áp lại mỗi 3 giây kéo người dùng về; nến sai khung sau khi đổi khung hoặc lỗi tải), 6 MEDIUM (đường giá tạo lại mỗi poll, phản hồi cũ ghi đè mới sau thao tác, leak listener, dấu phẩy thập phân bị từ chối, vé hết hạn/API lỗi vẫn như còn hiệu lực, a11y), LOW. Tất cả đã sửa và có test hồi quy (`e2e/review_fixes.spec.ts`).

**Review kỹ thuật vòng 2** (xác minh bản sửa): 1 HIGH mới do bản sửa gây ra (đổi múi giờ làm chart trộn hai gốc thời gian), 3 MEDIUM (dấu phẩy nghìn, CSV, khóa đường giá), vài LOW. Đã sửa (chart dựng lại khi đổi múi giờ, `data-bars` kiểm chứng được, `parseDecimal` hiểu dấu nghìn, CSV đúng RFC 4180 + BOM + chặn công thức, `title` trong khóa đường giá, guard NaN, timeout cho POST, trình tự cho poll).

**Review UX vòng 1–4** (trader lần đầu, ảnh thật): vòng 1/2/3 trả lời "NO" kèm đề xuất (lệnh tự do/quản lý SL-TP: ranh giới an toàn; thông báo setup; thống kê hiệu suất; lịch sử setup; thẻ lệnh gần nhất; khoảng cách SL/TP; lỗi hierarchy; điện thoại; tài khoản). Đã làm tất cả mục trong phạm vi: thanh tài khoản PAPER và giới hạn lỗ ngày, giờ mở lại, thông báo setup, Journal có lọc/tỷ lệ thắng/R trung bình/đường R/theo lý do/theo tuần/CSV, lịch sử setup (suýt có và hết hạn khi chưa ai mở), thẻ lệnh gần nhất, nút hành động khi toàn màn hình, TP2 tham khảo, độ lệch giá trong xác nhận, độ khẩn của đếm ngược, gọn bảng CHỜ, header điện thoại. **Vòng 4: YES, dùng được hằng ngày**, các điểm còn lại chỉ là gợi ý nhỏ (đã làm: nhãn marker chồng nhau, thanh tab điện thoại, một thông điệp thị trường đóng).

**Bài kiểm tra "5 giây" mù** (5 ảnh × 9 câu): đúng gần như toàn bộ (giá, quyết định, Entry/SL/TP, vị thế, live/replay); lỗi duy nhất do ảnh test chụp lúc trang cuộn mất tiêu đề (đã sửa, mọi ảnh bắt đầu từ đầu trang).

Bài học vận hành: dashboard sống trả 500 cho các chunk JS khi `.next` bị build lại trong lúc `next start` đang chạy; cần khởi động lại stack (`scripts\start_market_stack.ps1 -Dashboard`) sau mỗi lần build.

## 5. LOW còn lại (không ảnh hưởng đúng đắn, không gây nhầm lệnh, không hỏng dữ liệu)

* Giá trị tự gõ vào ô giá của cảnh báo/máy tính không có thông báo lỗi chi tiết ngoài việc không tính (có hướng dẫn "nhập entry, SL và rủi ro").
* Cảnh báo giá hai tab ghi đè lẫn nhau theo "ghi sau thắng" (có đồng bộ qua sự kiện `storage`).
* Nến tích lũy không cắt bớt trong phiên rất dài ở M1 (khoảng 1.440 nến/ngày, nhỏ).
* Thanh tab hẹp trên điện thoại vẫn có thể cuộn ngang ở màn rất nhỏ.
* Khi mất kết nối mà một POST mở lệnh đã tới máy chủ, thông báo nói "hãy kiểm tra vị thế" (không thể biết chắc từ phía trình duyệt).

## 6. Ma trận tính năng terminal cơ bản

| Tính năng | Kết quả | Tính năng | Kết quả |
|---|---|---|---|
| Giá live | YES | Xác nhận mở | YES |
| Bid/Ask | YES | Quản lý vị thế | YES (không sửa SL/TP: ranh giới an toàn) |
| Spread | YES | Xác nhận đóng | YES |
| Thay đổi ngày | YES | Lịch sử | YES |
| Cao/thấp ngày | YES | Journal → biểu đồ | YES |
| Phiên | YES | Cảnh báo | YES (trong trình duyệt + Telegram/file; Telegram chờ chủ cấu hình) |
| Giờ Việt Nam | YES | Máy tính rủi ro | YES |
| Đếm ngược nến | YES | Hỗ trợ/kháng cự | YES |
| Nến | YES | PDH/PDL | YES |
| Khung thời gian | YES | Nền phiên | YES |
| Crosshair OHLC | YES | Cảnh báo giá | YES (chỉ khi trang mở) |
| Đường giá hiện tại | YES | Đường ngang | YES |
| Fit / Latest / Follow | YES | Công cụ đo | YES |
| Toàn màn hình | YES | Phím tắt | YES |
| Volume | YES (tick volume) | Lưu tùy chọn | YES |
| BUY/SELL/WAIT | YES | Setup progress | YES |
| Marker + chi tiết | YES | Entry/SL/TP | YES |
| Trực quan R/R | YES | Đa khung | YES |
| Hoạt động thị trường | YES | Vé lệnh PAPER | YES |
| Lịch tin kinh tế | DEFERRED (cần nguồn dữ liệu ngoài; trang ghi rõ "chưa xác minh") | Push khi đóng trình duyệt | DEFERRED (cần token Telegram của chủ; hạ tầng phía máy chủ đã có) |

## 7. Hoãn và lý do

* **Lệnh tự do, SL/TP tùy ý, lệnh chờ, kéo SL/TP, break-even/chốt một phần bằng tay:** NOT APPLICABLE theo `AGENTS.md` (không có API nhận hướng/lot/SL/TP tùy ý).
* **Lịch kinh tế:** cần nhà cung cấp dữ liệu ngoài; chưa có trong repo.
* **Cảnh báo đẩy khi đóng trình duyệt:** cần thông tin xác thực Telegram của chủ; trang cảnh báo trạng thái "CHƯA BẬT".
* **Chỉ báo (MA/ATR), công cụ vẽ nâng cao, watchlist DXY/US10Y:** mở rộng phạm vi lớn so với giá trị cho một bộ máy quyết định đa khung cố định.

## 8. Phán quyết

TRADING TERMINAL UI READY FOR DAILY PAPER USE
