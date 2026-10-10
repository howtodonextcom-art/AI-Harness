# Nghiệm thu vòng đời BUY / SELL / HOLD / EXIT trên trình duyệt thật (TRADE-07)

Phạm vi: terminal `/trade`, **chỉ PAPER**. Không gửi lệnh MT5, DEMO/FUNDED vẫn khóa, không khẳng định edge, không đụng strategy/ngưỡng/SL-TP (mặc định v1.1.0). Mọi bằng chứng dưới đây là app thật + backend thật (acceptance replay qua đúng các route thật, nhãn `ACCEPTANCE REPLAY — KHÔNG PHẢI LIVE`). Không có fixture viết tay làm bằng chứng cuối.

**Kết luận: FUNCTIONALLY COMPLETE — LIVE-STACK BROWSER ACCEPTANCE PENDING** (xem mục 15). Lý do không ghi PASS: chưa có phiên trình duyệt nào trên stack LIVE (:3000) với bản build mới nhất, nên ảnh "LIVE" bắt buộc chưa có; và còn các điểm MEDIUM/LOW mở ở mục 11/12.

## Mỗi trạng thái trả lời "tôi nên làm gì bây giờ?"

Server quyết định `hero.action {code, stage, side, thesis, blocked_by?}`; trình duyệt chỉ dựng câu chữ. 8 mã: WAIT, WATCH BUY, WATCH SELL, BUY, SELL, HOLD, EXIT, UNAVAILABLE, kèm câu "Khi nào?".

## 1. Công cụ trình duyệt đã dùng

- chrome-devtools MCP (phiên của tôi: `evaluate_script`, `take_screenshot`, `emulate`, `press_key`, `navigate_page` với `initScript` chuyển `:8000 → :8100`).
- Playwright MCP (`browser_run_code_unsafe`: chuột/bàn phím thật theo tọa độ cho crosshair, kéo/zoom, click marker, resize, dark mode).
- Hai reviewer độc lập (agent mới, không biết kết luận trước) dùng Playwright MCP / chỉ đọc ảnh.

## 2. Số phiên trình duyệt thật

- 2 công cụ MCP của tôi, nhiều phiên liên tiếp (mobile, desktop, dark, 1920, zoom 200%, landscape).
- Red team độc lập: 1 phiên dài (92 lần gọi công cụ, ~20 phút).
- Fresh user-flow reviewer: 1 phiên (35 lần gọi công cụ).
- Five-second blind review: đọc 9 ảnh (không điều khiển trình duyệt).

## 3. Flow đã chạy (19 flow bắt buộc)

| Flow | Trình duyệt thật | Ảnh |
|---|---|---|
| WAIT (replay) | có | desk `01-replay-wait` |
| BUY WATCH | có | `mcp-` series, `lifecycle-buy_watch` |
| BUY ARMED | có | `mcp-13-buy-armed` |
| BUY READY | có | `mcp-16-mobile-buy`, `mcp-18-desktop-dark-buy` |
| SELL WATCH | có | `mcp-14-sell-watch` |
| SELL ARMED / SELL READY | có | `mcp-05-sell-confirm`, `lifecycle-sell_armed` |
| Xác nhận PAPER BUY (hủy + xác nhận) | có | `mcp-02-buy-confirm`, `mcp-17-mobile-modal` |
| Xác nhận PAPER SELL | có | `mcp-05-sell-confirm` |
| OPEN POSITION / HOLD | có | `mcp-03-hold`, `mcp-26-phone-hold-no-hscroll` |
| TP EXIT | có | `mcp-04-exit-tp`, `mcp-21-exit-marker-crosshair` |
| SL EXIT | có | `mcp-06-sell-sl-exit` |
| TIME EXIT | có (-0.45R, "Hết thời gian giữ") | `mcp-15-exit-time` |
| EXPIRED | có | `mcp-09-expired` |
| INVALIDATED | có | `mcp-08-sell-invalidated` |
| STALE | có | `mcp-10-stale` |
| MARKET CLOSED | có | `mcp-12-market-closed` |
| ERROR/UNAVAILABLE (writer lock, API down, no_spec, paper_corrupt) | có | `mcp-11-unavailable-writer-lock`, `redteam/` |
| **LIVE WAIT trên stack LIVE** | **chưa** | — |

Tương tác biểu đồ bằng chuột/phím thật: crosshair + OHLC theo bar, wheel zoom, kéo pan, follow (W), "Về hiện tại" (L), fit (F), toàn màn hình (X, Esc), phím khung giờ (1/5/2/3/H/4), click marker BUY và EXIT (popover có giờ, giá, lý do, P&L, R, phiên bản, nguồn). Viewport: 1440×900, 1920×1080, 390×844, 844×390, 720×450 (zoom 200%), dark mode (desktop + phone).

## 4. Ảnh chụp

`docs/reports/img/trading-ui/lifecycle/` (mcp-02 … mcp-26, `ab/`, `before/`), `redteam/`, `userflow/`, `after/` (acceptance suite). Mọi ảnh replay mang banner "ACCEPTANCE REPLAY — KHÔNG PHẢI LIVE".

## 5. A/B variants

3 biến thể trung tâm hành động (action-first) được dựng thật và chấm mù; thắng: trung tâm hành động với từ lớn + câu "Khi nào?" (commit `d564d22`, ảnh `lifecycle/ab/`). Ánh xạ ngẫu nhiên A/B/C được giữ riêng tới khi chấm xong.

## 6. Rubric cố định (định nghĩa TRƯỚC khi dựng prototype)

15 tiêu chí: hiểu trong 5 giây, rõ hành động, thấy giá, thấy BUY/SELL, WAIT hữu ích, HOLD rõ, EXIT rõ, thấy Entry/SL/TP, thấy rủi ro, chart là trọng tâm, quen thuộc với trader, dùng được trên mobile, accessibility, độ phức tạp triển khai, khả năng bảo trì.

## 7. Kết quả blind review

- Chấm A/B (3 biến thể × 4 trạng thái, ảnh xáo trộn): thắng như mục 5.
- Five-second review mới (9 ảnh cuối, tên trung tính, người chấm chưa biết gì): đúng symbol, giá, hành động, lý do, SL/TP, replay trong 9/9 ảnh; độ tự tin 3–5. Rủi ro hàng đầu họ nêu: (a) chữ lớn "THEO DÕI MUA/BÁN" có thể đọc nhầm thành lệnh dù đã viền nét đứt hổ phách + biểu tượng mắt; (b) mã thô `WRITER_LOCK` lộ ra trader và lặp 3 lần ở trạng thái UNAVAILABLE; (c) hai giá entry (kế hoạch 4236.47 / khớp 4236.50) — đúng nghiệp vụ nhưng dễ rối; (d) TP2 cạnh TP1. **Chưa sửa (a),(b)**: ghi ở mục 12.

## 8. Lỗi chỉ thấy trên trình duyệt thật (đã sửa + test hồi quy)

1. Modal xác nhận thiếu Setup ID.
2. Banner "đã mở lệnh" cũ không tự tắt (giờ tự ẩn sau 12 s).
3. Marker EXIT trễ.
4. Chip WATCH mâu thuẫn với hành động ("SẴN SÀNG" khi chưa có setup).
5. "Về hiện tại" bấm trong 2,5 s sau khi kéo biểu đồ làm follow tắt lại (cửa sổ quán tính bị coi là thao tác người dùng).
6. Esc không đóng popover marker khi focus ở chỗ khác.
7. Trên phone, dòng OHLC xuống hàng chồng lên chú giải Entry/SL/TP.
8. Trang cuộn ngang trên phone ở tab Hệ thống khi có vị thế mở (chip chiến lược dài, scrollWidth 536 vs 390).
9. Nút xác nhận/hủy ra ngoài màn hình ở phone nằm ngang.
10. Marker chỉ bấm được đúng cột 3–6 px của nến (nay bấm trong ±14 px).

## 9. Lỗi test tự động đã bỏ sót

Các mục 8.5–8.10 đều qua toàn bộ suite mock trước khi có trình duyệt thật/độc lập (test cũ chờ 3,5 s nên né cửa sổ quán tính; layout test không mở vị thế ở tab Hệ thống; không test chuột thật lệch khỏi marker). Hai lỗi HIGH của red team (mục 11) cũng lọt qua suite xanh.

## 10. Bằng chứng sửa / chạy lại

Mỗi lỗi có test hồi quy; test cuộn ngang được chứng minh **đỏ (146 px) trước khi sửa, xanh sau**, test "Về hiện tại" cũng đỏ trước khi sửa. Commit: `22ffb9b` (07b), `3499bda` (07c), `057c0e1` (07d), `97f2b9d` (07e), `3533e52` (07f), trên nền `d564d22` (07a).

## 11. Red team độc lập (agent mới, 14 hướng tấn công)

Không có CRITICAL.
- **HIGH 1** hero vẫn BUY xanh khi API mất kết nối → đã sửa: hero chuyển UNAVAILABLE "Mất kết nối API" (test acceptance thật).
- **HIGH 2** setup đã vào lệnh và đóng vẫn hiện BUY xanh (chỉ nút bị vô hiệu) → đã sửa ở server: `WAIT` giai đoạn `BLOCKED` kèm lý do của bàn (test Python + acceptance thật).
- **MEDIUM 3** nút xác nhận ngoài màn hình ở phone landscape → đã sửa (hàng nút dính đáy modal, `dvh`).
- **MEDIUM 4** giá trị cảnh báo giá/đường kẻ localStorage không tách replay/live: **mở**. Giảm nhẹ: replay và live chạy origin khác nhau (:3200 vs :3000); cảnh báo giá vốn chỉ kích hoạt với dữ liệu LIVE. Chưa kiểm chứng trên trình duyệt.
- **LOW 5** cuộn ngang phone → đã sửa. **LOW 6–9** (câu "Khi nào?" bị cắt trên phone, popover thiếu múi giờ/giờ thoát/lẫn SELL-BÁN, nhãn trục giá chồng nhau, một thông điệp tiếng Anh): **mở**.
- Giữ vững: stale giữa phiên, thế giới đổi dưới modal (server từ chối `DECISION_CHANGED`), đổi khung/tab nhanh, resize khi modal mở, double-click xác nhận/đóng (đúng 1 lệnh), hết hạn, mở rồi reload ngay, múi giờ, dark mode, bẫy focus bàn phím, biểu đồ không giật khi poll.

## 12. Còn mở (ghi thẳng)

- MEDIUM: "THEO DÕI MUA/BÁN" vẫn có thể bị đọc nhầm khi lướt (rủi ro hàng đầu của five-second review).
- MEDIUM: biểu đồ trên phone chỉ cao ~100 px ngay trên thanh hành động; chỉ ở landscape biểu đồ nằm dưới màn hình đầu.
- MEDIUM: bộ đếm hiệu lực nhảy 4:59/4:58/5:00 trên replay (đồng hồ replay đứng yên, trình duyệt đếm tiếp; trên LIVE đồng hồ server chạy). Chưa kiểm chứng trên LIVE.
- LOW: mã thô `WRITER_LOCK` / `API_UNAVAILABLE` hiện cho trader; thuật ngữ R/R, MFE/MAE, BID/Âu-Mỹ chồng phiên chưa có tooltip; chưa hiển thị giới hạn thời gian giữ (120 phút) vì view vị thế chưa trả `max_hold_until`; vạch giá cuối khi kéo xa; Journal "nguồn gốc" dùng tiếng Anh.

Không phải lỗi (đã kiểm): "Xem chi tiết" dưới legend là danh sách marker cho trình đọc màn hình (đi bằng bàn phím); chart không tự theo trong phiên reviewer là do tùy chọn follow bị lưu từ phiên thử trước (mặc định BẬT).

## 13. Five-second result

9/9 ảnh trả lời đúng symbol, giá, hành động, lý do, replay; SL/TP đúng ở các ảnh có kế hoạch; trạng thái "không có kế hoạch" (WATCH/WAIT/UNAVAILABLE/EXIT) ghi NOT FOUND cho Entry/SL/TP đúng như thiết kế.

## 14. Kịch bản live và replay

- **LIVE**: chưa có phiên trình duyệt trên stack LIVE với bản build này; chưa từng thấy setup LIVE thật (F0 — forward acceptance vẫn chờ). Không có ảnh gắn nhãn LIVE trong báo cáo này.
- **ACCEPTANCE REPLAY** (thật, qua cùng route/engine/desk/journal): wait, buy_watch, buy_armed, buy_tp, buy_time, sell_watch, sell_armed, sell_sl, sell_tp, sell_invalidated, expired, stale, market_closed, writer_conflict, no_spec, paper_corrupt, api down.

## 15. Chưa kiểm chứng trên trình duyệt

LIVE WAIT / MARKET CLOSED trên stack LIVE; bộ đếm hiệu lực trên đồng hồ LIVE; rò rỉ LIVE↔REPLAY qua localStorage (cùng origin); offline > 60 s; TIME EXIT chiều SELL (có trong acceptance suite tự động, chưa xem bằng mắt).

---

## Bảng bằng chứng hoàn thành

| Tính năng | SOURCE | API | AUTO TEST | BROWSER THẬT | REVIEWER | LIVE/REPLAY | STATUS |
|---|---|---|---|---|---|---|---|
| Hành động WAIT/WATCH/BUY/SELL/HOLD/EXIT/UNAVAILABLE | cockpit.py, action.ts | hero.action | Python + 200 mock + 30 acceptance | có | five-second 9/9, user-flow, red team | REPLAY | PASS (REPLAY) |
| WATCH BUY/SELL, ARMED | có | có | có | có | five-second (rủi ro đọc nhầm) | REPLAY | PASS, MEDIUM mở |
| BUY/SELL READY + xác nhận PAPER | có | có | có | có (hủy + xác nhận) | user-flow | REPLAY | PASS |
| HOLD + luận điểm | có | có | có | có | user-flow | REPLAY | PASS |
| EXIT (TP/SL/TIME) + marker | có | có | có | có | user-flow | REPLAY | PASS |
| Setup đã dùng / bị chặn = WAIT | có | `BLOCKED` | Python + acceptance | có (red team) | red team | REPLAY | PASS (sau sửa) |
| Mất API → UNAVAILABLE | có | — | acceptance | có (red team) | red team | REPLAY | PASS (sau sửa) |
| EXPIRED / INVALIDATED / STALE / CLOSED | có | có | có | có | red team | REPLAY | PASS |
| Chart tương tác thật | có | có | có | có | user-flow | REPLAY | PASS |
| Mobile 390 / landscape / dark / 1920 / zoom 200% | có | — | có | có | red team | REPLAY | PASS (landscape: biểu đồ dưới màn hình đầu) |
| Trạng thái trên stack LIVE | có | có | một phần | **chưa** | — | LIVE | **PENDING** |

Số vòng lặp: 1 vòng A/B + 5 vòng sửa sau trình duyệt/độc lập (07b–07f).

## Kiểm tra cuối

Python: ruff, format, mypy --strict xanh; pytest -m "not mt5": 2558 passed, 1 skipped; dashboard: eslint + tsc sạch, 200/200 mock (có axe sáng/tối), 30/30 acceptance thật (một lần TIME EXIT trên replay lỡ nhịp thời gian, chạy lại xanh; ghi nhận là flake thời gian của test, không phải hồi quy).
