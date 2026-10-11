# QA Trade page qua Chrome DevTools MCP — retry 2026-10-11

Phạm vi: LIVE `http://127.0.0.1:3000/trade` chỉ đọc; SANDBOX `http://127.0.0.1:3210/trade` chạy `next dev` với `NEXT_DIST_DIR=.next-sandbox`, `NEXT_PUBLIC_API_URL=http://127.0.0.1:8791`, mock fixture golden. Ảnh lưu tại `docs/reports/img/mcp-trade-2026-10-11/` với tiền tố `retry-`.

## 1. TL;DR

- Chrome DevTools MCP điều khiển được trang Trade end-to-end: mở tab mới, click, gõ, phím Escape/Tab/Enter, đổi viewport mobile, đọc a11y snapshot, console, network, chụp ảnh.
- Kết quả: **10 PASS, 3 PASS có ghi chú/lỗi**. 0 console error/warn do app; 0 request 4xx/5xx. Có 3 DevTools `issue` về form field thiếu id/name.
- Ba vấn đề đáng chú ý nhất: tab Hệ thống vẫn lẫn tiếng Anh/mã kỹ thuật; toast sandbox sau mở MUA báo nhầm “Đã mở lệnh PAPER BÁN”; câu vô hiệu lệnh MUA “giá đóng nến vượt qua SL” còn mơ hồ hướng.
- Các lỗi cũ đã cải thiện: `writer_conflict` không còn hiện plan có thể dùng; `stale` gộp một dòng; Escape từ modal mở lệnh trả focus về nút “Mở lệnh PAPER MUA”.

## 2. Kết quả từng bước

| # | Kết quả | Bằng chứng |
|---|---|---|
| A1 LIVE đóng cửa | PASS | `retry-A1-live-closed.png`: giá 4195.09/4195.52, “Thị trường ĐÓNG”, mở lại `2026-10-12 05:05`, hero `CHỜ`, `UNVALIDATED · PHỦ 48.6% / 95%`. |
| A2 M1→M5→M15→M30→H1→H4 | PASS | `retry-A2-live-H4.png`; chart đổi legend và request bars trả 200. |
| A3 múi giờ | PASS | `retry-A3-timezone-vn-restored.png`; VN `10-12 05:05`, UTC `10-11 22:05`, broker/máy đổi nhất quán rồi khôi phục VN. |
| A4 5 tab | PASS có lỗi thấp | `retry-A4-tab-reasons.png`; tab Lý do/Vị thế/Hoạt động/Hệ thống không trống. Tab Hệ thống còn chuỗi tiếng Anh. |
| A5 công cụ chart | PASS có ghi chú | `retry-A5-hline.png`, `retry-A5-alert.png`, `retry-A5-fullscreen.png`, `retry-A5-shortcuts.png`. Tạo được đường ngang và alert; fullscreen/shortcuts OK. Công cụ đo không thấy nhãn delta rõ sau thao tác (`retry-A5-measure.png`). Đã dọn LIVE bằng state reset: `levels=[]`, `alerts=[]`, `drawings=[]`. |
| A6 mobile 390x844 | PASS | `retry-A6-live-mobile.png`; `scrollWidth=390`, hero nằm trong viewport, canvas cao 339px (>=280px). |
| A7 console/network LIVE | PASS có ghi chú | 0 error/warn; 0 request 4xx/5xx. DevTools issue: form field thiếu id/name. |
| B1 CHỜ | PASS có ghi chú | `retry-B1-wait.png`; fixture hiện tại nói “H1 chưa có hướng rõ”, không phải “H1 tăng nhưng khung khác ngược hướng” như kịch bản, nhưng user vẫn hiểu: chưa vào, vì sao, cần H1 rõ hướng. |
| B2 MUA | PASS | `retry-B2-buy.png`; Entry 4236.47, SL 4229.45, TP 4250.51, R:R 1.90, risk 0.25%, lot 0.03, TP2 tham khảo 4257.54, điều kiện vô hiệu ghi bàn không tự đóng. |
| B3 mở PAPER MUA | PASS có lỗi thấp | `retry-B3-open-modal.png`; modal nói không gửi MT5, focus mặc định “Hủy”, Escape đóng và trả focus về nút mở, 0 POST trước xác nhận. Xác nhận gửi 1 POST `/trade/paper/open`. Toast báo nhầm BÁN. |
| B4 GIỮ | PASS | `retry-B4-hold.png`; có “Vì sao GIỮ” và điều buộc thoát: SL, TP, hết giờ, sàn lỗ ngày 3.5%, luận điểm yếu đi không tự đóng. |
| B5 THOÁT | PASS có giới hạn mock | `retry-B5-exit-tp-after-close.png`, `retry-B5-closed-sl.png`, `retry-B5-closed-time.png`; SL và time rõ lý do/P&L/R. Đóng tay trong mock retry rơi vào fixture TP (`Chạm TP`) thay vì “Đóng tay”, nên phần manual close chưa chứng minh đúng như kịch bản. |
| B6 stale / market_closed / writer_conflict | PASS | `retry-B6-stale.png`, `retry-B6-market-closed.png`, `retry-B6-writer-conflict.png`; không có nút mở lệnh, plan bị blank, có lý do rõ. |

## 3. Lỗi

| Mức | Mô tả | Tái hiện | Ảnh | Đề xuất |
|---|---|---|---|---|
| Trung bình | Toast sau khi xác nhận mở fixture BUY nói “Đã mở lệnh PAPER BÁN”, trong khi hero/vị thế là MUA. | Sandbox `buy` → mở PAPER MUA → xác nhận. | `retry-B4-hold.png` | Không default side về SELL khi response thiếu/khác shape; dùng side từ setup đang xác nhận hoặc bắt buộc API trả side hợp lệ. |
| Thấp | Tab Hệ thống còn tiếng Anh/mã kỹ thuật trong phần người dùng đọc: `GOOD: all checks passed`, `CLEAR...`, các mã khóa DEMO. | LIVE → tab Hệ thống. | snapshot A4/Hệ thống | Dịch câu trạng thái chính sang tiếng Việt; để mã gốc trong phần chi tiết kỹ thuật. |
| Thấp | Điều kiện vô hiệu MUA ghi “giá đóng nến vượt qua SL”, chưa nói rõ là đóng dưới SL. | Sandbox `buy`. | `retry-B2-buy.png` | Viết theo hướng: MUA “đóng dưới SL”, BÁN “đóng trên SL”. |
| Thấp | DevTools báo form fields thiếu `id` hoặc `name`. | LIVE/SANDBOX console issues. | a11y issue log | Thêm `id/name` cho inputs/selects liên quan. |
| Thấp | Công cụ đo chưa tạo bằng chứng delta rõ trong lần thao tác retry. | LIVE → nút Đo → click chart. | `retry-A5-measure.png` | Tăng affordance/label khi công cụ đo đang chờ điểm đầu/cuối; bảo đảm snapshot có text delta sau khi đo. |

## 4. Chrome DevTools MCP so với Playwright MCP/Cursor browser

Chrome DevTools MCP phù hợp nhất cho bài này vì bám đúng Chrome đang chạy, đọc được console/network và a11y snapshot, bấm/gõ như người dùng, lưu ảnh thẳng vào repo. Điểm yếu: `navigate_page` với `initScript` bị treo trong retry này, nên sandbox phải đổi sang `NEXT_PUBLIC_API_URL` mock; page uid đổi thường xuyên sau reload.

Playwright MCP có lợi thế route/mock ổn định hơn cho fixture và test lặp lại; không tốt bằng DevTools khi mục tiêu là chứng minh điều khiển tab Chrome thật qua remote debugging. Cursor browser chỉ phù hợp xem nhanh, thiếu network/console/mock sâu cho bài này.

## 5. Dọn dẹp và an toàn

- LIVE: không bấm mở/đóng lệnh, không vào `/control` thủ công, không gửi MT5, không bật DEMO/FUNDED. `GET /control?_rsc` chỉ là prefetch của Next.
- Ghi chú LIVE đã dọn: `levels=[]`, `alerts=[]`, `drawings=[]`.
- SANDBOX: mock ghi nhận đúng 2 POST: open và close paper; không request tới `:8000` sau khi bật lại với `NEXT_PUBLIC_API_URL=:8791`.
- Đã đóng các tab Chrome do bài QA mở. Đã dừng mock `:8791` và sandbox `:3210`. Không sửa code sản phẩm.
