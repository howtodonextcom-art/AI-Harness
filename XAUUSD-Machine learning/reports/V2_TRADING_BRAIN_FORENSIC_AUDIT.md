# V2 · Kiểm toán pháp y "bộ não" giao dịch

Ngày: 2026-10-13 · Không mở cửa sổ khóa; không tinh chỉnh; không dùng outcome.

## 1. Vì sao WAIT nhiều (Q3)
Mẫu `decision_log` (chỉ M5 close, VERIFIED): hard gate spread ~33%, hard gate biến động ~27%, governor RISK_LIMIT/COOLDOWN ~24%, chuỗi NO_DIRECTION/NO_SETUP ~24% (các nhóm chồng lấn theo cách hiển thị: hard gate ưu tiên, nên "NO_DIRECTION" thực có thể lớn hơn).

| Giả thuyết | Kết luận | Căn cứ |
|---|---|---|
| WAIT hợp lệ (kỷ luật) | **Chủ yếu** | spread/ATR, percentile biến động là cổng an toàn theo thiết kế |
| Starvation do cổng | **Có khả năng một phần**: tổng các cổng chặn >60% bar; chưa chứng minh cổng nào quá chặt (không được nới) | phân bố trên |
| Độ trễ dữ liệu | **Không** | quote p50 0,9 s; khung quyết định M5 |
| Lỗi ánh xạ UI | **Có, nhỏ**: hard gate che lý do chuỗi; governor lẫn vào lý do thị trường; `next_condition` không hiển thị | `SystemPanel.tsx`, `decision.py` |
| Lỗi logic quyết định | **Không phát hiện** | test parity, đọc mã |
Hạn chế: `decision_log` chỉ lấy mẫu tại M5 close, bỏ lỡ lệnh AUTO 07:43 (VERIFIED); engine chạy chu kỳ ~3 s nhưng không ghi mọi chuyển trạng thái ⇒ mẫu thiên lệch.

## 2. Phủ chế độ thị trường
Regime V2 (`core/structure.py`): SHOCK, HIGH_VOLATILITY, TREND_UP/DOWN, LOW_VOLATILITY, RANGE.
| Chế độ | Có trong live? | Ghi chú |
|---|---|---|
| Trend | Có (H1) | hướng duy nhất |
| Range | Phát hiện, nhưng chuỗi không giao dịch phản ứng range | WAIT |
| Breakout / compression / vol expansion | Chỉ qua hard gate biến động (chặn), không như setup | V1 có `compression`, `breakout`, `range_expansion` trong `trading/patterns.py` — không dùng trong quyết định baseline |
| Pullback | Có (M15 setup) | |
| Reversal / exhaustion | Không | |
| Shock | Có (veto) | |
Kết luận: V2 là hệ **trend-pullback duy nhất**; mọi chế độ khác ⇒ WAIT. Hợp lệ như thiết kế nhưng hạn chế số cơ hội.

## 3. Trách nhiệm đa khung
H4 chỉ veto, H1 sở hữu hướng, M15 setup, M5 trigger, M1 chặn. **Đúng với thiết kế** (đọc mã). Rủi ro: một hướng duy nhất từ H1 NEUTRAL ⇒ toàn chuỗi dừng dù M15/M5 có tín hiệu (có thể thiếu cơ hội nhưng đúng quy ước "H1 là chủ").

## 4. Diễn giải nến
| Khái niệm | Trạng thái |
|---|---|
| Bấc nến, engulfing, pin bar, inside/outside | V1 có thư viện (`trading/patterns.py`, `features/candles.py`); **V2 live: không**; V1 baseline: không gọi |
| Failed breakout | thư viện V1; không live |
| Liquidity sweep, BOS/CHoCH | chỉ ở nghiên cứu V1 `structure/*` / swings; không live ở V2 |
| Pullback continuation | live (M15 + M5) |
| Exhaustion | không |
**Kết luận:** không có diễn giải nến trong quyết định live V2. Nếu UI từng gợi ý "nến" thì chỉ là hiển thị. Không có gì bị khẳng định sai, nhưng trader có thể kỳ vọng nhiều hơn.

## 5. Candidate C1/C2/C3a/C3b/C7 (đọc mã, không outcome)
- C1 lifecycle memory (6 M5 bar, planned stop cố định): hợp lý, đã sửa F6 (replay tất định).
- C2 cost_R ≤ 0,15 bằng spread thực thi: loại bớt lệnh chi phí cao; không thêm hướng.
- C3a/C3b: biến thể.
- C7 exploratory.
Cả 14 biến thể là **lớp mỏng quanh `decide()` của V1** (lọc/giữ trạng thái), không phải logic mới; hứa hẹn tối đa là *giảm lệnh xấu/giữ lệnh tốt*, không tạo cơ hội mới. Chưa có outcome hợp lệ (UNVALIDATED). Công suất: ~663 lệnh cho 0,20R.

## 6. ML thực tế
ML V0 (G6): CONTAMINATED trong register; không có suy luận live/shadow trên đường quyết định; có `ModelPanel` và endpoint model (hiển thị trạng thái). Không có hiệu chỉnh/độ bất định/drift được xác nhận vận hành. **Không có tuyên bố ML nào được hỗ trợ.** Em không hồi sinh ML V0.

## 7. Bằng chứng giá trị dự đoán
Forward PAPER: 1 lệnh AUTO, −1,0R. Backtest hợp lệ: không có. **Điểm giá trị dự đoán đã chứng minh: 1/10.**

## 8. Giới hạn
Không chạy lại so khớp V1↔V2 trực tiếp; không phân tích phân bố cổng theo thời gian trong ngày; mẫu `decision_log` nhỏ và lệch.
