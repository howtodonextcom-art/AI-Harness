# F1 — Phần chuyển động riêng của vàng sau khi loại thành phần USD (đăng ký trước)

Trạng thái: **ĐĂNG KÝ, CHƯA CHẠY** (2026-10-11). Biến thể duy nhất: `F1-USDRES-z2.0`. Giao thức chung: `COMMON_PROTOCOL.md`.

## Identity

- Mechanism: return giờ của XAUUSD = phần USD (đồng pha với EURUSD/USDJPY, mang thông tin vĩ mô) + phần riêng của vàng. Phần riêng lớn bất thường trong một giờ phần lớn là dòng lệnh không mang thông tin (thanh lý, rebalancing, lệnh lớn) nên tạo price impact tạm thời và **hồi một phần**.
- Hypothesis: sau một giờ có residual chuẩn hóa |z| ≥ 2.0, vị thế ngược dấu residual có mean net R > 0 (base) trong 24 giờ kế tiếp.
- Family / multiple-testing group: V3, K_V3 = 3 (`ledger.md`).
- Author / date: XAU EDGE research, 2026-10-11.

## Setup (đóng băng)

- Symbol / session: XAUUSD, mọi giờ giao dịch; EURUSD và USDJPY chỉ là yếu tố (không giao dịch).
- Return: log return close-to-close của nến H1 bid, căn theo timestamp H1 UTC. Giờ thiếu nến ở bất kỳ symbol nào: loại (không nội suy).
- Yếu tố USD: u_t = ½ · (r_USDJPY,t − r_EURUSD,t) (dương = USD mạnh lên).
- Hồi quy cuốn chiếu: α_t, β_t = OLS của r_XAU trên u trong **500 nến H1 kết thúc ở t−1** (không nhìn trước). σ_t = độ lệch chuẩn residual của chính cửa sổ đó.
- Residual: e_t = r_XAU,t − (α_t + β_t · u_t); z_t = e_t / σ_t.
- Sự kiện: |z_t| ≥ **2.0** (một giá trị, không quét).
- Loại trừ: nến H1 đầu tiên của tuần; nến đứng sau một khoảng trống > 1 giờ (nghỉ hằng ngày 21–22 UTC, ngày lễ); khi đang có vị thế F1 mở.
- Entry: open nến H1 kế tiếp (t+1), hướng = **−sign(e_t)**. Mua ở ask = bid + spread.
- Exit: SL = 1 × ATR(H1, 14) tính tại t; TP = 2 × ATR(H1, 14); hết giờ sau 24 nến H1 (đóng ở open nến thứ 25). Barrier được xét trên nến M1 (SL trước nếu cùng nến).
- R: 1 × ATR(H1, 14) tại t.
- Parameters (danh sách đóng): lookback 500 H1; z* = 2.0; ATR 14; barrier −1R/+2R; timeout 24 H1. Không có tham số nào khác.
- Cost model: `COMMON_PROTOCOL.md` §Chi phí (có swap vì có thể giữ qua đêm).

## Sample and power

- Sample definition: mọi sự kiện đủ điều kiện trong vùng, một vị thế tại một thời điểm.
- Expected events: ~250/năm (giá trị lập kế hoạch, chưa đo kết quả) ⇒ Dev ~2,000, Val ~750, Test-H ~830, Holdout ~110.
- MDE (một phía, power 0.8, σ = 1.0–1.3R; `foundation/power_v3.json`): Dev 0.06–0.08R; Val 0.11–0.14R; Test-H (α = 0.05/44) 0.135–0.175R; Holdout 0.29–0.37R.
- Mẫu tối thiểu: Dev ≥ 1,000 sự kiện; Val ≥ 400.
- Dev window: 2011-01-01..2018-12-31. Val window: 2019-01-01..2021-12-31.
- Test-H (protected): 2022-01-01..2025-04-30, chỉ sau Dev PASS + Val PASS + review độc lập.
- Holdout (protected, cuối): 2026-05-01..2026-10-07.

## Metrics and gates

- Primary metric: mean net R (base). Secondary: net bi quan, gross, PF, MDD (R), win rate, placebo percentile, kết quả trước/sau 2015, theo phiên.
- Pass / fail: đúng `COMMON_PROTOCOL.md` §Thống kê và cổng (Stage 1 α = 0.0333, sàn +0.10R, bi quan > 0, không artefact).
- Multiple-testing policy: K từ `ledger.md` (K_V3 = 3, K_tổng = 44 cho Test-H/Holdout).
- Evidence label if pass: Dev PASS ⇒ DEVELOPMENT CANDIDATE; Dev + Val PASS ⇒ VALIDATED CANDIDATE. Vẫn **UNVALIDATED** trên `/trade` cho tới khi engine giao dịch đúng quy tắc này và thang bằng chứng được nâng bằng một quyết định có chữ ký.

## Must not

- Quét z*, lookback hoặc barrier sau khi thấy kết quả.
- Đổi hướng (tiếp diễn thay vì hồi) nếu kết quả âm: đó là một giả thuyết mới, tính K mới, và không được chạy trên Dev-2 đã thấy.
- Touch Test-H or Holdout.
