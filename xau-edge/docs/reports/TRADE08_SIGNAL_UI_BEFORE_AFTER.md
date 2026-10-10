# TRADE-08 — giao diện tín hiệu: trước / sau

Mọi ảnh "sau" là backend replay thật (nhãn `ACCEPTANCE REPLAY — KHÔNG PHẢI LIVE`) hoặc stack LIVE thật (`:3000`). Không có ảnh viết tay.

## 1. WATCH không được giống một lệnh

| | Trước (TRADE-07) | Sau (TRADE-08) |
|---|---|---|
| ảnh | `img/trading-ui/lifecycle/mcp-13-buy-armed.png` | `img/trade08/replay/replay-watch-buy.png` |
| từ chính | **THEO DÕI MUA** (chữ MUA lớn, mũi tên + mắt) | **CHỜ** (lớn) + nhãn viền đứt **KHÔNG VÀO LỆNH** |
| hướng thị trường | trộn vào từ chính | **Thiên hướng ↑ MUA — chỉ là hướng thị trường nghiêng về, không phải lệnh** (nhỏ, có nhãn, nằm DƯỚI hành động) |
| điều kiện thiếu | "Mua khi: (1)… (2)… (3)…" | **Chỉ MUA khi:** M15 có nhịp pullback tạo setup, rồi nến M5 đóng xác nhận trigger tăng… |
| kết quả chấm mù | người chấm của TRADE-07: rủi ro đọc nhầm hàng đầu | 4 người chấm mù, 20 ảnh: không ai đọc thiên hướng là "được phép" |

Ví dụ ARMED: `replay-watch-sell.png`. Hành động duy nhất có thẻ màu + nút mở lệnh: MUA/BÁN PAPER (`replay-buy-ready.png`, `replay-sell-ready.png`).

## 2. Điện thoại 390×844

| | Trước | Sau |
|---|---|---|
| ảnh | `img/trade08/before/mobile-390-buy_tp.png` | `img/trade08/replay/replay-m-buy-ready.png`, LIVE `img/trade08/live/live-390x844-mobile.png` |
| biểu đồ nhìn thấy | **93 px** (WAIT: 87 px) | **288–352 px** replay, **411 px** LIVE |
| thanh thị trường | 242 px | ~120 px (chi tiết ngày + múi giờ gấp lại sau "Chi tiết thị trường") |
| thanh công cụ biểu đồ | 104 px (3 hàng) | 1 hàng + nút ⋯ |

Ngang 844×390 và zoom 200% (720×450): trước **0 px** biểu đồ trong màn hình đầu; sau bố cục hai cột (biểu đồ | quyết định): `live-844x390-landscape.png`, `final-live-zoom200-720x450.png` (≥ 160 px, có test chạy ở CI).

## 3. Lỗi kỹ thuật → câu tiếng Việt trước

| | Trước | Sau |
|---|---|---|
| ảnh | `img/trading-ui/lifecycle/mcp-11-unavailable-writer-lock.png` | `img/trade08/replay/replay-unavailable.png` |
| thẻ | "…chỉ đọc. **WRITER_LOCK**" lặp 3 lần | một câu: "Một tiến trình khác đang giữ quyền ghi bàn PAPER…" + **Chi tiết kỹ thuật ▸ WRITER_LOCK** |
| mất API | "Không kết nối được API… `API_UNAVAILABLE`" | "Mất kết nối với máy chủ dữ liệu… Trang sẽ tự cập nhật khi kết nối trở lại." + Chi tiết kỹ thuật |
| System tab | `CLOSED / the market is closed`, `UNVALIDATED_OPERATIONAL_BASELINE` (`before/live-system-tab.png`) | `ĐÓNG · CLOSED / Thị trường đang đóng cửa`, "Baseline vận hành, chưa phải lợi thế đã kiểm chứng" |
| Journal | `ACCEPTANCE_REPLAY`, `BULLISH`, `UNKNOWN`, `NEWS_UNKNOWN` | "ACCEPTANCE REPLAY — dữ liệu lịch sử phát lại, KHÔNG PHẢI LIVE", "tăng", "chưa rõ", "chưa xác minh" |

## 4. HOLD: thời hạn thoát

| | Trước | Sau |
|---|---|---|
| ảnh | `img/trading-ui/lifecycle/mcp-03-hold.png` | `img/trade08/replay/replay-hold.png` |
| hạn giữ | "hoặc khi hết thời gian giữ" (không có số) | "hoặc **muộn nhất lúc 23:45** (hết thời gian giữ)" và dòng **Giữ tối đa: tới 23:45 · còn 2 giờ 0 phút** (từ `max_hold_until` của server, theo múi giờ đã chọn) |
| từ chính | GIỮ LỆNH | **GIỮ VỊ THẾ** + "Chưa có điều kiện thoát." |

## 5. Các thay đổi nhỏ khác (có ảnh trong `img/trade08/`)

- Đồng hồ replay không còn nhảy 4:59 → 4:58 → 5:00 (chạy theo đồng hồ replay; LIVE theo đồng hồ server đã hiệu chỉnh lệch).
- Công cụ của tôi (đường ngang, cảnh báo giá) gắn với **một nguồn**: nhãn "Chỉ dùng cho: LIVE XAUUSD" (`live/final-live-tools-level-alert.png`).
- Thị trường đóng cửa: huy hiệu "LIVE · ĐÓNG CỬA" (xám), bỏ dòng Thiên hướng/Setup vô nghĩa (`live/final-live-1440x900.png`).
- Từ vựng có giải thích ngắn: Bid, Ask, Spread, R/R, MFE, MAE, Tick volume, Thiên hướng, Setup, SL, TP, Giữ tối đa.
- Biểu đồ: nhãn trục giá nhường nhau theo thứ hạng (ENTRY/SL/TP > giá cuối > NOW/TP2 > đường của tôi > cảnh báo); nhãn marker nhường nhau theo khoảng cách pixel; marker SETUP; popover có múi giờ, giờ thoát và MUA/BÁN.
- Khi mất kết nối, kế hoạch cũ gập lại ("Kế hoạch cuối cùng đã cũ — không dùng để vào lệnh"), không còn nút mở lệnh.
