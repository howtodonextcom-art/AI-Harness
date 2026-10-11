# QA /trade bằng Chrome DevTools MCP, vòng 3 (2026-10-11)

Người thực hiện: QA kiêm "người dùng thật", chỉ quan sát và ghi nhận. **Không sửa code trong bài này.**
Bản được kiểm: dashboard live build `d4351b4` (`data-build-sha`), sandbox = stack REPLAY thật (TradeEngine + PaperDesk thật, API `:8100`, dashboard `:3200`, build `.next-sandbox` từ cùng mã nguồn).

## 1. TL;DR

- **MCP điều khiển được trang Trade từ đầu đến cuối**: điều hướng, đổi khung và múi giờ, mở các tab, vẽ đường, tạo và xóa cảnh báo, toàn màn hình, modal xác nhận (focus, Tab, Escape), mở và đóng lệnh PAPER trên sandbox, đọc console và network, Lighthouse, giả lập 390x844 và 720x450.
- **12 PASS, 2 FAIL** trên 14 bước (B5 và B6 mỗi bước đạt một phần: 3 trong 4 cách thoát đạt, 7 trong 8 kịch bản chặn đạt). 0 vi phạm ranh giới an toàn; 0 lỗi console do ứng dụng gây ra trên LIVE; 0 request 5xx trên LIVE (503 trên sandbox là chủ đích của các kịch bản hỏng).
- **3 vấn đề nghiêm trọng nhất** (chưa sửa):
  1. **Cao**: khi một setup sẵn sàng bị chặn (đã vào lệnh rồi, hoặc gần giờ đóng cửa), hero nói "CHỜ" nhưng overlay vẫn vẽ huy hiệu "MUA · R:R 1:1.63" cùng Entry/SL/TP, và thanh dính trên điện thoại ghi "▲ SẴN SÀNG MUA". Hai tín hiệu trái nhau trên cùng một màn hình.
  2. **Trung bình**: trên điện thoại, hero không hiện lý do bị chặn ("Gần giờ thị trường đóng cửa..."), chỉ còn "Đừng mở lệnh cho setup này".
  3. **Trung bình**: đóng lệnh tay cho ra "CHỜ" kiểu chặn trùng lặp, không có thẻ THOÁT; lý do thoát (MANUAL_CLOSE, -$0.90, -0.04R) chỉ nằm ở tab Vị thế. Thêm nữa, khi đang GIỮ, ô ENTRY của hero hiện giá kế hoạch 4236.47 trong khi overlay và lệnh ghi giá khớp 4236.50.

## 2. Kết quả từng bước

| Bước | Kết quả | Bằng chứng |
|---|---|---|
| A1 LIVE mở trang | PASS | `A1_live_1440.png`. Bid 4195.09, ask 4195.52, spread 43 điểm; "Thị trường ĐÓNG", "Mở lại lúc 10-12 01:05 · còn 6:21:13" (giờ broker); quyết định CHỜ / MARKET_CLOSED; "UNVALIDATED · CHƯA KIỂM CHỨNG · PHỦ 48.6% / 95%"; PAPER; build `d4351b4`. Test 5 giây: làm gì = chờ, vì sao = thị trường đóng, giá = không áp dụng, rủi ro = không áp dụng, tiếp theo = mở lại 01:05 broker. |
| A2 Đổi khung M1 đến H4 | PASS | 6 khung đều `aria-pressed`, 400 nến, thân nến chiếm 0.51 đến 0.70 vùng vẽ, 5.9 đến 7.9 px mỗi nến, console trống. |
| A3 Múi giờ | PASS | VN 22:44:24, UTC 15:44:26, broker 18:44:27, máy tôi 22:44:28; giờ mở lại 05:05 / 22:05 / 01:05 / 05:05 và "còn 6:20" nhất quán; nhãn OHLC trên biểu đồ đổi đúng 7 giờ giữa VN và UTC. |
| A4 Năm tab | PASS | Tổng quan 924 ký tự, Lý do 319 ("Đang bị chặn bởi: Thị trường đóng cửa"), Vị thế ("Không có lệnh paper đang mở"), Hoạt động ("Chưa có hoạt động nào"), Hệ thống 3793. `A4_live_system_tab_full.png`. |
| A5 Công cụ | PASS (có ghi chú UX) | Đường ngang "Đường 4204.12" và cảnh báo "CẢNH BÁO ↓ 4190.00" tạo được (`A5_live_tools_line_and_alert.png`), Đo bật và thoát bằng Esc, toàn màn hình vào và ra bằng Esc (`A5_live_fullscreen.png`), bảng phím tắt (`A5_live_shortcuts.png`). Đã xóa cả hai, xem mục 5. |
| A6 390x844 | PASS | `A6_live_390.png`: hero ở y 305 đến 470, biểu đồ cao **448 px** (yêu cầu 280), không cuộn ngang. Thêm 720x450 (zoom 200%): biểu đồ cao 274 px, xem L-04. |
| A7 Console và network | PASS | LIVE: 0 console error, 0 request 4xx/5xx; nhịp poll đúng (decision 7 lần trong 19 giây, markers/signals/journal/setups mỗi 6 giây), không trùng. |
| A8 Truy cập | PASS | Tab đi tới Journal có vòng focus `2px solid rgb(3,105,161)`; Lighthouse accessibility 100, best practices 100, SEO 100. |
| B1 CHỜ | PASS | `B1_sandbox_wait_h1_conflict_2.png`: "Chưa được vào lệnh: H1 đang tăng nhưng H4 hoặc M15 đang đi ngược hướng" và "Cần xảy ra: H4 và M15 ngừng đi ngược hướng H1". Biến thể thiếu SETUP (`B1_sandbox_buy_watch.png`: "Chỉ MUA khi: M15 có nhịp pullback...") và thiếu TRIGGER (`B1_sandbox_buy_armed.png`: "nến M5 kế tiếp đóng xác nhận trigger tăng (còn 6 nến M5...)") đúng nghĩa; không có nút mở lệnh. |
| B2 MUA | PASS | `B2_sandbox_buy.png`: Entry 4236.47, SL 4229.45, TP 4250.51, R:R 1.90, rủi ro 0.25%, lot 0.03, "còn hiệu lực 5:00", "TP2 · THAM KHẢO 4257", "điều kiện vô hiệu (chỉ tham khảo, bàn không tự đóng)". Khớp 100% với `/trade/decision` và overlay. BÁN: `B2_sandbox_sell_hold.png`, 3336.41 / 3339.10 / 3331.03 khớp. |
| B3 Modal mở lệnh | PASS | `B3_sandbox_confirm_modal.png`: nội dung đầy đủ ("lệnh giả lập, không gửi tới MT5", mã setup, Entry/SL/TP/TP2, R/R, rủi ro 0.25% · -$21.07, lot), focus vào nút an toàn "Hủy", Tab bị giữ trong modal, Escape đóng và trả focus về `take-paper`. |
| B4 GIỮ | PASS (kèm L-01) | `B4_sandbox_hold.png`: "Vì sao GIỮ: Chưa chạm điều kiện thoát nào", "Bàn tự thoát khi chạm SL 4229.45 (-1R) hoặc TP 4250.51, hoặc muộn nhất lúc 23:45 GMT+7 (hết thời gian giữ), hoặc khi lỗ trong ngày chạm sàn khẩn cấp 3,5% (flatten)"; "luận điểm yếu đi KHÔNG tự đóng lệnh". Lỗi M-03 ở ô ENTRY. |
| B5 THOÁT | **FAIL (một phần)** | Thoát do SL (`B5_sandbox_exit_sl.png`: "Chạm SL · -$24.73 · -1.01R · 36 phút"), hết giờ (`B5_sandbox_exit_time.png`: "-$9.88 · -0.45R · 120 phút"), chạm TP (`B5_sandbox_exit_tp.png`: "1.98R · 86 phút") đều PASS: hero "ĐÃ THOÁT", không còn Entry/SL/TP cũ, không overlay. **Đóng tay: FAIL** (`B5_sandbox_exit_manual.png`), xem H-01 và M-02. |
| B6 Chặn | **FAIL (một phần)** | stale, expired, market_closed, writer_conflict, paper_corrupt, no_spec, collector_down: PASS (không nút mở lệnh, không số kế hoạch, lý do tiếng Việt rõ). `buy_closure_near`: **FAIL**, xem H-01 và M-01 (`B6_sandbox_buy_closure_near.png`, `B6_sandbox_buy_closure_near_390.png`). Chuyển kịch bản liên tục không tải lại trang không để lại Entry/SL/TP cũ. Khi trang mất API (chạy ngoài cầu nối) hiện đúng "Mất kết nối... KHÔNG phải trạng thái CHỜ; không được vào lệnh" (ngẫu nhiên ghi được lúc đổi viewport, cũng là một bằng chứng fail-closed). |

## 3. Danh sách lỗi (chưa sửa)

| ID | Mức | Tái hiện | Thực tế | Đề xuất sửa |
|---|---|---|---|---|
| **H-01** | **Cao** | Sandbox: nạp `buy_closure_near` (hoặc `buy_tp` rồi mở và đóng lệnh tay). Xem desktop và 390x844. | Hero "CHỜ · KHÔNG VÀO LỆNH · Có setup mua nhưng không mở được", nhưng `data-hero-state` vẫn `BUY_READY`; overlay `PLAN BUY` với huy hiệu "MUA · R:R 1:1.63" và các đường BUY ENTRY/SL/TP1; thẻ kế hoạch vẫn hiện; thanh dính điện thoại ghi "▲ SẴN SÀNG MUA, SL..., TP..., R/R 1.63" kèm nút "Mở lệnh…" (bị vô hiệu). Ảnh: `B6_sandbox_buy_closure_near_390.png`, `B5_sandbox_exit_manual.png`. | Overlay, thanh dính và thẻ kế hoạch phải theo `action.code` / `stage=BLOCKED` thay vì `hero.state`: ẩn overlay và thanh, hoặc gắn nhãn "BỊ CHẶN — không phải tín hiệu". Thêm test (hiện chỉ test nút bị khóa). |
| M-01 | Trung bình | Như trên, ở 390x844. | Dòng lý do "Có setup mua nhưng không mở được: Gần giờ thị trường đóng cửa..." tồn tại trong DOM nhưng `display:none` trên điện thoại; người dùng chỉ thấy "Đừng mở lệnh cho setup này". | Hiện lý do bị chặn trên điện thoại (một dòng ngắn). |
| M-02 | Trung bình | `buy_tp`, mở lệnh PAPER, đóng tay, xác nhận. | Không có thẻ THOÁT; hero là CHỜ do chặn trùng lặp ("Setup này đã được vào lệnh rồi, không mở lại"). Lý do thoát chỉ ở tab Vị thế (MANUAL_CLOSE, -$0.90, -0.04R). | Hiện thoát gần nhất trong hero một lúc ngắn (như SL/TP/giờ), rồi mới chuyển sang chặn. |
| M-03 | Trung bình | Sandbox, đang GIỮ lệnh `buy_tp`. | Ô ENTRY hero "4236.47" (giá kế hoạch) trong khi overlay "ACTUAL FILL 4236.50" và lệnh khớp 4236.50. Nguyên nhân: `lib/honesty.ts` `heroLevels` ưu tiên `plan` hơn `position`. **Cải chính**: báo cáo FINAL_99 mục FIX-06 ghi đã sửa, nhưng bản sửa không áp dụng (thay thế nhiều dòng trên file CRLF bị bỏ qua mà không báo lỗi) và test đi kèm đạt vì golden `openPaper` không có `trade_plan`. Đã ghi đính chính vào báo cáo đó. | Ưu tiên `position.fill_price`, `position.sl`, `position.tp` khi có lệnh mở; thêm test với view có cả plan và position. |
| M-04 | Trung bình | Bất kỳ trạng thái CHỜ có setup (expired, closure_near, sau thoát). | Hai câu mâu thuẫn cạnh nhau: "Có setup mua nhưng không mở được" và "Một nguồn sự thật: chưa có setup." (cụm "Một nguồn sự thật" là thuật ngữ nội bộ). | Chỉ hiện câu "chưa có setup" khi thật sự chưa có; đổi cụm nội bộ sang lời thường. |
| L-01 | Thấp | A5 | Ba hộp thoại có thể mở chồng (Quản lý nét vẽ, Thêm cảnh báo, Phím tắt); Esc chỉ đóng hộp trên cùng. | Mở hộp mới thì đóng hộp cũ. |
| L-02 | Thấp | A5 | Cảnh báo và đường ngang chỉ xóa được ở tab Tổng quan (✕); hộp "Báo giá" và "Nét vẽ" không liệt kê chúng. | Liệt kê và cho xóa ngay trong hộp. |
| L-03 | Thấp | A1, snapshot | Dải khung hiện "M1 thực thi DỮ LIỆU CŨ" khi thị trường đóng (bình thường nhưng nghe như lỗi). | Khi thị trường đóng ghi "ĐÓNG CỬA". |
| L-04 | Thấp | 720x450 | Biểu đồ cao 274 px (dưới 280). Yêu cầu 280 chỉ áp cho 390x844 (đạt 448). | Tăng nhẹ chiều cao tối thiểu ở màn thấp. |
| L-05 | Thấp | A5 | Phím tắt khó nhớ: 1=M1, 5=M5, 2=M15, 3=M30, H=H1, 4=H4. | Đồng bộ thứ tự hoặc ghi lý do. |
| L-06 | Thấp | B4 | Hai ngưỡng khác nhau không giải thích cạnh nhau: "giới hạn 2%" (thẻ tài khoản) và "sàn khẩn cấp 3,5%" (hero khi giữ). | Một dòng giải thích hai mức. |
| L-07 | Thấp | A1 | Múi giờ mặc định của trình duyệt kiểm là "Giờ broker (NY+7)", không phải giờ VN; người dùng Việt đọc "01:05" có thể hiểu nhầm. | Cân nhắc mặc định giờ VN và ghi rõ giờ trong dòng "Mở lại lúc". |

Mọi ảnh nằm trong `xau-edge/docs/reports/img/mcp-trade-qa3-2026-10-11/`.

## 4. Chrome DevTools MCP so với Playwright và trình duyệt Cursor (từ trải nghiệm trong bài này)

- **Chrome DevTools MCP** (đã dùng): điểm mạnh là trình duyệt thật cộng công cụ chẩn đoán mà Playwright không có sẵn: `lighthouse_audit`, `performance_start_trace` (tìm ra CLS 0.23 ở vòng trước), danh sách console và network, `emulate` thiết bị, đọc canvas bằng `evaluate_script`, cây a11y. Điểm yếu thực tế: `take_snapshot` rất dài (khoảng 15.000 token mỗi lần) và muốn `click` phải có uid từ snapshot; `emulate` tải lại trang nên mất `initScript` (cầu nối fetch sang :8100 bị mất, trang rơi vào trạng thái mất kết nối); `initScript` chỉ chạy ở lần `navigate` kế tiếp; cửa sổ không thu hẹp dưới khoảng 500 px (390 phải dùng `emulate`); ảnh chỉ lưu được trong workspace; một lần trang bị đóng đột ngột khi `resize_page`. Tôi dùng `evaluate_script` (sự kiện click thật trên DOM) cho nhiều thao tác lặp để tiết kiệm.
- **Playwright** (bộ test có sẵn trong repo: 362 test mock và 31 acceptance): nhanh (khoảng 1,5 phút cho cả bộ mock), lặp lại được, có route mock và golden. Không có đo hiệu năng và Lighthouse. Phù hợp để khóa lỗi sau khi MCP tìm ra; không thay thế được việc "nhìn" ảnh chụp từng trạng thái (ví dụ H-01 chỉ lộ ra khi nhìn ảnh).
- **Playwright MCP và trình duyệt tích hợp của Cursor**: không dùng trong bài này (chỉ dùng Chrome DevTools MCP và bộ Playwright của repo), nên không có so sánh trải nghiệm. Tôi không suy đoán.
- Kết luận thực dụng: dùng MCP để khám phá và chẩn đoán, dùng Playwright để khóa kết quả; mọi lỗi H-01 đến M-04 nên được thêm test Playwright khi sửa.

## 5. Xác nhận dọn dẹp và an toàn

- **Ghi chú vẽ và cảnh báo trên LIVE đã xóa.** Sau khi xóa, đọc lại localStorage: `xau-edge:v3:LIVE:XAUUSD:alerts = []`, `levels = []`, `drawings = []`; "Số lệnh hôm nay 0 / 6", hero `MARKET_CLOSED`. (Lần xóa đầu chỉ gỡ được cảnh báo vì nút đường bị render lại giữa hai lần bấm do kịch bản của tôi bấm cùng lúc; đã bấm lại và xác nhận.)
- **Ranh giới:** không gửi lệnh MT5, không đụng DEMO/FUNDED, không mở `/control` (trang `/trade` có liên kết "Vận hành" và Next.js tải trước trang này bằng một GET thụ động, không tương tác, không đổi trạng thái), không bấm mở/đóng lệnh trên LIVE, không build vào `.next`, không khởi động lại stack live (vẫn `:8000` và `:3000`), không đọc `.env` hay token. Mở và đóng lệnh PAPER chỉ trên sandbox (dữ liệu replay).
- **Tab:** trình duyệt MCP là phiên riêng, không thấy tab của người dùng; chỉ dùng tab do MCP mở.
- **Tiến trình đã mở và đã đóng:** `serve_acceptance.py :8100`, `next start :3200`; thư mục `.next-sandbox` đã xóa. Live không bị ảnh hưởng.
- **Hạn chế:** thao tác kéo thả trên biểu đồ và đo hai điểm không thực hiện được qua uid đơn lẻ; "Đo" chỉ được kiểm bật/tắt. Phần "5 giây" là tự đánh giá, không có người đọc độc lập.
