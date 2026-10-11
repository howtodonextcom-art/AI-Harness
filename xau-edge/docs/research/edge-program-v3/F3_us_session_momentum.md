# F3 — Intraday momentum phiên Mỹ (đăng ký trước)

Trạng thái: **ĐĂNG KÝ, CHƯA CHẠY** (2026-10-11). Biến thể duy nhất: `F3-USMOM-0930-1400-1500-1645`. Giao thức chung: `COMMON_PROTOCOL.md`.

## Identity

- Mechanism: thông tin của phiên Mỹ (dữ liệu 08:30, mở cổ phiếu 09:30) được hấp thụ dần: nhà đầu tư chậm thông tin và hedging cuối ngày giao dịch theo cùng chiều với phần đầu phiên, nên hướng phần đầu phiên tiếp diễn ở cuối phiên. Đã ghi nhận ở cổ phiếu/ETF và một số futures; với spot XAU **CHƯA XÁC MINH**.
- Hypothesis: vị thế cùng dấu với return XAUUSD từ 09:30 tới 14:00 giờ New York, giữ từ 15:00 tới 16:45 giờ New York, có mean net R > 0 (base).
- Family / multiple-testing group: V3, K_V3 = 3 (`ledger.md`).
- Author / date: XAU EDGE research, 2026-10-11.

## Setup (đóng băng)

- Symbol / session: XAUUSD, ngày giao dịch Mỹ. Giờ theo **America/New_York** (tự động theo DST), quy ra UTC bằng `zoneinfo`.
- Tín hiệu: s = sign(open của nến M1 14:00 NY − open của nến M1 09:30 NY), giá bid. s = 0: không giao dịch.
- Entry: open của nến M1 15:00 NY theo hướng s (mua ở ask = bid + spread).
- Exit: open của nến M1 16:45 NY (thoát theo thời gian). Stop thảm họa 3 × ATR(H1, 14) tính lúc 15:00 NY (xét trên M1; hiếm khi chạm, chỉ để R có nghĩa về rủi ro).
- R: 1 × ATR(H1, 14) lúc 15:00 NY. Kết quả R = (giá thoát − giá vào) · s / ATR − chi phí theo R.
- Loại trừ: ngày lễ Mỹ và ngày đóng cửa sớm (theo `MarketCalendar` của dự án); ngày thiếu > 5% nến M1 trong 09:30–16:45 NY; ngày thiếu đúng một trong bốn nến mốc.
- Parameters (danh sách đóng): bốn mốc giờ 09:30 / 14:00 / 15:00 / 16:45 NY; ATR 14; stop thảm họa 3 ATR. Không có ngưỡng độ lớn.
- Cost model: `COMMON_PROTOCOL.md` §Chi phí (không giữ qua đêm, không swap).

## Sample and power

- Expected events: ~250/năm (một lần mỗi ngày giao dịch) ⇒ Dev ~2,000, Val ~750, Test-H ~830, Holdout ~110.
- MDE (một phía, power 0.8, σ = 1.0–1.3R): Dev 0.06–0.08R; Val 0.11–0.14R; Test-H 0.135–0.175R; Holdout 0.29–0.37R.
- Lưu ý chi phí: cửa sổ giữ 105 phút nên biên độ theo ATR(H1) nhỏ; chi phí 2 lần khớp ở 2011–2018 là ~0.07–0.13 ATR(H1) mỗi phía theo trung vị nến (×1.6 base) — rủi ro lớn nhất của họ này là chi phí ở Dev-2.
- Mẫu tối thiểu: Dev ≥ 1,500 ngày; Val ≥ 600.
- Dev / Val / Test-H / Holdout: như `COMMON_PROTOCOL.md`.

## Metrics and gates

- Primary metric: mean net R (base). Secondary: như F1, thêm theo ngày trong tuần và theo độ lớn |return 09:30–14:00| (chỉ mô tả, không phải bộ lọc).
- Pass / fail: `COMMON_PROTOCOL.md` §Thống kê và cổng.
- Multiple-testing policy: K từ `ledger.md`.
- Evidence label if pass: như F1.

## Must not

- Dời bất kỳ mốc giờ nào sau khi thấy kết quả (không post-hoc chọn giờ).
- Thêm ngưỡng độ lớn hay bộ lọc biến động sau khi thấy kết quả.
- Touch Test-H or Holdout.
