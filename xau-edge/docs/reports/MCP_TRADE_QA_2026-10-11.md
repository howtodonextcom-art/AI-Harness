# QA Trade page qua Chrome DevTools MCP — 2026-10-11

Người thực hiện: agent (vai QA + trader), Chrome Dev 157 qua `chrome-devtools-mcp --autoConnect --channel=dev`.
LIVE: `http://127.0.0.1:3000/trade` (chỉ đọc, thị trường ĐÓNG). SANDBOX: `next start` cổng 3210 từ build hiện có + API giả cổng 8791 phục vụ fixture golden của repo; mọi `fetch` tới :8000 và `/api/trade/*` bị chuyển hướng vào mock bằng `initScript`; proxy POST của sandbox trỏ vào cổng chết (`XAU_EDGE_API_URL=http://127.0.0.1:9`).
Ảnh: `docs/reports/img/mcp-trade-2026-10-11/`.

## 1. TL;DR

- Agent điều khiển được Trade page end-to-end bằng Chrome DevTools MCP: click, gõ, phím tắt, Tab/Escape, emulate mobile, đọc console/network, chụp ảnh.
- **12/13 kịch bản ĐẠT, 1 ĐẠT CÓ LỖI (B6).** 0 lỗi console, 0 request 4xx/5xx, 0 vi phạm an toàn.
- Lỗi đáng sửa nhất (Trung bình): ở trạng thái `writer_conflict`, hero ghi **KHÔNG KHẢ DỤNG** nhưng vẫn hiện ENTRY/SL/TP/R:R/RỦI RO/LOT như một kế hoạch có thể làm theo.
- Còn lại là lỗi nhỏ: focus không quay về nút sau khi đóng modal, lý do trùng lặp ở `stale`, chữ "KHÔNG KHẢ DỤNG" xuống dòng, tab Hệ thống lẫn tiếng Anh, poll dày khi thị trường đóng.

## 2. Kết quả

| # | Kịch bản | Kết quả | Bằng chứng |
|---|---|---|---|
| A1 | Giá, trạng thái đóng, giờ mở lại, CHỜ, huy hiệu bằng chứng | ĐẠT | `A1-live-1440.png`; CHỜ · "Thị trường đóng cửa" · mở lại 10-12 05:05 · `honesty[data-level=UNVALIDATED]` "PHỦ 48.6% / 95%" |
| A2 | Khung M1→H4 | ĐẠT | network: `bars?timeframe=M1/M15/M30/H1/H4` đều 200 |
| A3 | Múi giờ VN/UTC/broker/máy | ĐẠT | VN 03:45 = UTC 20:45 = broker 23:45 |
| A4 | 5 tab | ĐẠT | Lý do: "Đang bị chặn bởi: Thị trường đóng cửa"; Hệ thống: DEMO ĐÃ KHÓA |
| A5 | Đo, đường ngang, báo giá, xóa; toàn màn hình; phím tắt | ĐẠT | `A5-hline.png`, `A5-alert-line.png`, `A5-measure.png` (Δ +0.00 · 0 điểm · 0 nến), `A5-fullscreen.png` (1425×900, Esc thoát), `A5-shortcuts.png` ("Không có phím tắt nào mở hay đóng lệnh", focus trong dialog). Sau khi xóa: `levels=[]`, `alerts=[]`, `drawings=[]` |
| A6 | 390×844, chart ≥280px | ĐẠT | `A6-mobile-390.png`; scrollWidth 390 (không tràn), chữ CHỜ ở top 320px cỡ 30px, canvas cao 339px |
| A7 | Console / network | ĐẠT | 0 error/warn; 0 response ≥400 (31 request DevTools + Resource Timing) |
| B1 | CHỜ có xung đột khung | ĐẠT | `B1-wait-conflict.png`; "H1 đang tăng nhưng H4 hoặc M15 đang đi ngược hướng" + "Cần xảy ra: …"; không có nút mở lệnh |
| B2 | Hero MUA | ĐẠT | `B2-buy.png`; 4236.47 / 4229.45 / 4250.51 · R:R 1.90 · 0.25% · 0.03 lot; "TP2 tham khảo 4257.54"; "điều kiện vô hiệu (chỉ tham khảo, bàn không tự đóng)" |
| B3 | Modal xác nhận, focus/Escape, xác nhận | ĐẠT (lỗi nhỏ #2) | `B3-confirm-modal.png`; `role=dialog aria-modal=true`; "không có lệnh nào được gửi tới MT5"; focus mặc định = Hủy; Tab vòng trong modal; Esc đóng và **0 POST**; Enter xác nhận → mock nhận đúng 1 POST `/api/trade/paper/open {"setup_id":"ade8bf4c07b2b1153240","risk_pct":0.25}` |
| B4 | GIỮ | ĐẠT | `B4-hold.png`; "Vì sao GIỮ: …SL 4229.45 (-1R) hoặc TP 4250.51, muộn nhất 23:45, sàn khẩn cấp 3,5% (flatten)… luận điểm yếu đi KHÔNG tự đóng lệnh" |
| B5 | Đóng tay → THOÁT có lý do; closed_sl, closed_time | ĐẠT | `B5-exit-manual.png`; modal đóng: focus mặc định "Giữ lệnh"; "ĐÃ THOÁT · Đóng tay · +$42.04 · 1.99R"; SL: "Chạm SL · -$24.73 · -1.01R"; time: "Hết thời gian giữ · -$9.88 · -0.45R" |
| B6 | stale / market_closed / writer_conflict chặn vào lệnh | ĐẠT CÓ LỖI (#1, #3) | `B6-stale.png`, `B6-writer-conflict.png`; cả 3 không có nút mở lệnh và nêu lý do ("Dữ liệu giá đã quá cũ", "Thị trường đóng cửa", "Một tiến trình khác đang giữ quyền ghi bàn PAPER") |

Hiểu trong ≤5 giây: ĐẠT. Từ hành động (CHỜ / MUA PAPER / GIỮ VỊ THẾ / ĐÃ THOÁT / KHÔNG KHẢ DỤNG) luôn là chữ lớn nhất, nằm trên màn hình đầu ở cả 1440 và 390.

Ghi chú: đồng hồ "còn hiệu lực 5:00" đứng yên trên sandbox vì nó tính theo giờ máy chủ, mà mock trả giờ cố định. Đây không phải lỗi. Lý do "Đóng tay" được kiểm bằng biến thể mock `closedManual`, tương ứng với `exit_reason=MANUAL_CLOSE` mà API thật trả về.

## 3. Lỗi

| # | Mức | Mô tả | Tái hiện | Ảnh | Đề xuất sửa (chưa sửa code) |
|---|---|---|---|---|---|
| 1 | Trung bình | `writer_conflict`: hero KHÔNG KHẢ DỤNG nhưng vẫn hiện ENTRY/SL/TP/R:R/RỦI RO/LOT đầy đủ, dễ bị đọc như kế hoạch vào lệnh | fixture `writer_conflict` → /trade | `B6-writer-conflict.png` | Trong `HeroLevels`, khi mã hành động là UNAVAILABLE thì hiện "—" hoặc làm mờ kèm nhãn "kế hoạch bị chặn, không dùng" |
| 2 | Thấp | Đóng modal xác nhận bằng Escape thì focus rơi về `BODY`, không quay lại nút "Mở lệnh PAPER MUA" (WCAG 2.4.3) | fixture `buy` → bấm nút → Esc → `document.activeElement` | `B3-confirm-modal.png` | Lưu ref của nút kích hoạt và gọi `focus()` khi modal đóng (có thể liên quan test focus-trap đang lỗi sẵn trong `terminal.spec`) |
| 3 | Thấp | `stale`: hai dòng lý do gần như trùng nhau ("Dữ liệu giá đã quá cũ…" và "Báo giá đã quá cũ…") | fixture `stale` | `B6-stale.png` | Gộp lý do theo mã trước khi render |
| 4 | Thấp | "KHÔNG KHẢ DỤNG" xuống 2 dòng ở 1440 ("KHÔNG KHẢ / DỤNG") | fixture `stale`/`writer_conflict` | `B6-writer-conflict.png` | Giảm cỡ chữ cho từ dài hoặc dùng `whitespace-nowrap` kèm co chữ |
| 5 | Thấp | Tab Hệ thống còn tiếng Anh: "GOOD: all checks passed", "CLEAR: no high-impact event…", các lý do khóa DEMO | LIVE → tab Hệ thống | — | Ánh xạ sang tiếng Việt, giữ mã gốc trong "Chi tiết kỹ thuật" |
| 6 | Thấp | Khi thị trường ĐÓNG vẫn poll decision+bars ~3s, markers/signals/journal/setups ~6s | LIVE, xem network | — | Giãn poll lên 30–60s khi `market_open=false` |
| 7 | Thấp | Đường ngang không làm tăng "☷ Nét vẽ (0)" (được tính riêng là "Đường"), dễ khiến người dùng tưởng vẽ thất bại | LIVE → T → bấm chart | `A5-hline.png` | Hiện số đường ngang cạnh nút, ví dụ "— Đường (1)" |
| 8 | Thấp | GIỮ: ô R:R hiện "—" dù R:R kế hoạch đã biết (1.90) | fixture `open_paper` | `B4-hold.png` | Hiện R:R kế hoạch, hoặc bỏ ô |
| 9 | Thấp | MUA: "giá đóng nến vượt qua SL" mơ hồ về hướng | fixture `buy` | `B2-buy.png` | Viết "giá đóng nến dưới SL" (MUA) hoặc "trên SL" (BÁN) |

## 4. So sánh công cụ trình duyệt

| | Chrome DevTools MCP | Playwright MCP | Cursor browser |
|---|---|---|---|
| Dùng tab/hồ sơ thật của người dùng | Có (`--autoConnect`) | Không (trình duyệt riêng) | Không |
| Console / network / performance | Đầy đủ | Có (`--caps devtools`) | Qua CDP |
| Chèn script trước khi tải trang (`initScript`) | Có, nhờ vậy dựng được sandbox | Có (`run_code`) | Không |
| Lưu ảnh ra file | Chỉ trong thư mục workspace root (Temp được, Z: thì không) | Sandbox không thấy Z: | Ảnh hiện ngay trong chat |
| Upload file | Có | Lỗi khi lấy từ đĩa, chỉ dùng được buffer | Không |
| Điểm yếu | Page id đổi số khi người dùng đóng tab; emulation mất khi id đổi; mỗi lệnh liệt kê lại toàn bộ tab của người dùng (lộ URL riêng tư); không có lệnh "xóa emulation" | Không thấy trạng thái người dùng | Ít công cụ |

Kết luận: Chrome DevTools MCP phù hợp nhất cho QA kiểu "người dùng thật" kèm chẩn đoán. Playwright MCP phù hợp cho kịch bản cô lập, có thể lặp lại.

## 5. Dọn dẹp và an toàn

- Không gửi lệnh MT5, không bật DEMO/FUNDED, không đổi cờ. Không vào và không thao tác `/control`. Request `GET /control?_rsc` trong network là prefetch tự động của Next `<Link>`.
- LIVE: không bấm Mở lệnh / Đóng lệnh. Đường ngang 4147.50 và cảnh báo 4300.00 đã xóa qua UI; localStorage LIVE `levels=[]`, `alerts=[]`, `drawings=[]`. Bàn PAPER LIVE vẫn 0 lệnh.
- SANDBOX: mock ghi nhận 3 POST (open, close, close), không request nào tới :8000.
- Không build vào `.next`, không khởi động lại stack. Supervisor: collector/news/api/dashboard đều alive, restarts=0.
- Chỉ mở 1 tab mới (sandbox) và đã đóng nó. Không đọc hay chụp tab khác. Tab LIVE có sẵn đã được trả viewport về mặc định.
- Đã dừng `next start` :3210 và mock :8791. Không sửa code sản phẩm.
