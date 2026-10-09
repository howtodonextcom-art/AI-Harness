# Phân tích phễu tín hiệu (SIGNAL_FUNNEL_ANALYSIS)

Dữ liệu: ledger FTMO MT5 đã đốt. Công cụ: `src/xau_edge/trading/funnel.py` (vector mọi cổng, không đoản mạch), `scripts/signal_funnel_dump.py`, `scripts/signal_funnel_analyze.py`, `scripts/signal_geometry_diag.py`. Không tối ưu hóa, không dùng PnL.

## 1. Xác minh trạng thái v1.1.0 (HEAD 0d6cd51)

Replay lại cửa sổ gốc 2025-11-03→12-01: **5 406 quyết định, 0 BUY, 0 SELL, 5 406 WAIT**, khớp báo cáo. Lý do chặn đầu tiên tính lại bằng `scripts/trade_replay_smoke.py --skip-parity`: VOLATILITY_TOO_LOW 1465, NO_SETUP 1311, VOLATILITY_TOO_HIGH 1015, NO_DIRECTION 423, TIMEFRAME_CONFLICT 277, NO_TRIGGER 245, SPREAD_TOO_WIDE 243, RR_TOO_LOW 9, TOO_CLOSE_TO_RESISTANCE 5, TOO_CLOSE_TO_SUPPORT 4 (khớp). Lưu ý: các số này là *lý do đầu tiên*; cổng spread/biến động nằm trước chuỗi nên che mọi cổng phía sau.

Mở rộng ba cửa sổ đã đốt (16 270 quyết định): **2 BUY**, 16 268 WAIT (cả 3 cửa sổ cho tổng 2 tín hiệu).

## 2. Phễu đầy đủ (v1.1, 3 cửa sổ, 16 270 quyết định)

Tỉ lệ qua độc lập của từng cổng (trên mọi quyết định; cổng theo hướng tính trên số có H1 có hướng = 12 219):

| Cổng | Qua |
|---|---|
| spread_ok | 88.1% |
| vol_not_high | 80.3% |
| vol_not_low | 70.2% |
| h4_regime_ok | 83.1% |
| h1_directional | 75.1% |
| h4_not_against (| H1 có hướng) | 96.8% |
| m15_not_against | 84.1% |
| m15_structure_with | 35.9% |
| m15_pullback | 12.4% |
| m15_setup (cả hai) | 11.6% |
| m5_trigger | 21.3% |
| m1_not_quiet / not_noisy / not_volatile | 79.8% / 86.7% / 100% |
| clearance_ok | 75.1% |
| stop_ok | 92.8% |
| rr_ok | 38.9% |
| risk_ok | 89.0% |

Sống sót tuần tự theo thứ tự chuỗi: 16 270 → spread 14 334 → vol cao 11 443 → vol thấp 7 385 → H4 6 369 → H1 có hướng 4 912 → H4 không ngược 4 731 → M15 không ngược 3 976 → **M15 setup 573 (độ dẫn có điều kiện 14%)** → **M5 trigger 53 (9%)** → M1 45 → clearance 23 → **RR 2 (8.7%)** → rủi ro 2.

## 3. Phản chứng theo cổng (chẩn đoán, không phải chiến lược)

| Phản chứng | Tín hiệu |
|---|---|
| tất cả cổng v1.1 | 2 |
| bỏ vol_not_high | 3 |
| bỏ vol_not_low | 6 |
| bỏ cả hai cổng biến động | 7 |
| bỏ m1_not_quiet | 2 |
| bỏ spread_ok | 2 |
| bỏ cổng H4 | 3 |
| bỏ m5_trigger (chỉ setup) | 112 |
| bỏ m15_setup (chỉ trigger) | 120 |
| bỏ biến động + m1 quiet | 7 |
| bỏ biến động + spread | 8 |
| bỏ MỌI cổng ngữ cảnh | 10 |

Kết luận: cổng ngữ cảnh *không phải* nút thắt (gỡ hết chỉ 2 → 10). Nút thắt nằm ở chuỗi setup/trigger/kế hoạch.

## 4. Dư thừa và mâu thuẫn giữa cổng

| Cặp | Phân loại | Ghi chú |
|---|---|---|
| m15_setup × m5_trigger (nghịch: cùng thất bại) | STRONGLY REDUNDANT theo mức đồng-thất-bại (phi 0.52) *và* tương quan âm khi cùng qua | cùng nến: 156 thực tế vs 304 kỳ vọng nếu độc lập |
| m15_setup × rr_ok | STRONGLY REDUNDANT (P(RR fail|setup fail) 0.87) | đều gắn với vị trí giá |
| clearance_ok × rr_ok | RR bao hàm clearance: ở 91 nến qua clearance (trong tập setup+trigger) chỉ 11 qua RR | clearance không có tác dụng độc lập |
| m15_structure_with × m15_pullback | pullback đòi `structure_trend>0` ⇒ structure là tập cha của pullback ngoại trừ CHOCH (93/12 219) | trùng lặp một phần (không đáng kể về số lượng) |
| vol_not_high × vol_not_low | hai đầu của cùng phân vị (loại trừ nhau, phi −0.32) | một đại lượng, hai veto |
| H4 SHOCK/HIGH_VOLATILITY × vol_not_high | độc lập về số liệu (không đồng thất bại) | H4 vẫn là bảo vệ độc lập |

Không có cặp CONTRADICTORY tuyệt đối (mọi tổ hợp đều có thể cùng qua).

## 5. Khả đạt của setup

M15 setup sẵn sàng + M5 trigger cùng nến **có xảy ra** (46 / 46 / 64 theo cửa sổ) nhưng ít hơn kỳ vọng nếu độc lập (70 / 129 / 105): pullback là nhịp ngược xu hướng; trigger là sự quay lại; khi động lượng quay lại giá thường đã rời vùng EMA. Chuỗi sự kiện (trigger hiện tại, setup sẵn sàng trong N nến M5 trước, cùng chiều): N=3 → 294, N=6 → 411, N=12 → 591 so với 156 cùng nến. Ví dụ nến trigger có setup sẵn sàng trước: 2025-06-02 11:10, 17:05, 17:45 UTC.

Định nghĩa trong mã (xác minh): **M15 SETUP READY** = H1 có hướng, cấu trúc M15 (HH/HL hoặc LH/LL, không có CHoCH trong 6 nến) cùng hướng và giá đóng cửa cách EMA20 M15 trong [−0.3, +0.7] ATR (BUY) hoặc [−0.7, +0.3] (SELL). **M5 TRIGGER** = ROC(5) cùng hướng, RSI >52 (BUY) hoặc <48 (SELL), và (BOS cùng hướng trong 6 nến hoặc thân nến mạnh), hoặc BOS cùng hướng + ROC. Đều dùng nến đã đóng (kiểm test hiện có).

## 6. Hình học kế hoạch (nguyên nhân chính)

Tại 156 nến setup+trigger cùng nến: stop trung vị 1.47 ATR(M15) (sàn 1.25 ràng buộc ở 53 nến); ATR(M5)/ATR(M15) = 0.53; chỗ trống tới mức M15 đối diện trung vị **1.15 ATR(M15)** (p25 0.71) so với cần **2.21** cho R/R ròng 1.5; **90% thiếu chỗ**; qua RR: 11/156 (7%). Toàn bộ tập setup (1 418 nến có stop hợp lệ): qua RR 483 (34%). Kết luận: thang đo stop (M15) không nhất quán với trigger (M5) và mức mục tiêu bị chặn ở mức M15 gần nhất ⇒ R/R ≥ 1.5 hầu như không đạt với entry sau pullback.

## 7. Biến động (đã kiểm)

Định nghĩa: nhãn LOW nếu phân vị của ATR(M15) hiện tại trong 200 giá trị ATR(M15) gần nhất ≤ 0.20; HIGH nếu ≥ 0.80. Phân phối theo cửa sổ: LOW 21.9 / 32.1 / 35.5%; HIGH 23.5 / 20.3 / 15.4%. Theo phiên: LONDON LOW 39.8%, OVERLAP HIGH 38.6% (phụ thuộc phiên mạnh). Độ dài một đợt LOW trung bình 40 nến M5. ATR(M15) tuyệt đối: p10 4.37 / p50 7.65 / p90 17.58 USD; trung vị khi nhãn LOW 7.06, HIGH 8.79. Nhãn LOW gần như không khác mức trung vị tuyệt đối (−8%), HIGH +15%: đo mức *tương đối với 2 ngày gần nhất*, không phải biến động bất thường. Giữ làm veto cứng là không có cơ sở; giữ làm ngữ cảnh/cảnh báo là hợp lý.

## 8. Spread và M1

Spread trung vị 24 điểm; spread/ATR(M5) p50 0.061, p90 0.110 (giới hạn 0.15); execution POOR 11.9% (chủ yếu phân vị spread ≥0.9; M1 ABNORMAL chỉ 0.2%). **Lưu ý trực tiếp (live)**: spread FTMO hiện ~41 điểm, ATR(M5) thấp ⇒ spread/ATR gần ngưỡng; xem quan sát forward. M1 quiet loại 24/156 tại nến setup+trigger nhưng gỡ nó không thêm tín hiệu nào (thất bại ở RR trước) ⇒ không phải nút thắt, giữ nguyên.

## 9. Phân loại nguyên nhân (A–J)

| | Kết luận |
|---|---|
| A thị trường chưa bao giờ có setup | KHÔNG: setup và trigger tồn tại nhiều (156 cùng nến, 411 tuần tự N=6) |
| B từng cổng quá chặt | Không phải ngưỡng riêng lẻ |
| C nhiều cổng mã hóa cùng thông tin | CÓ (clearance ⊂ RR; vol cao/thấp một đại lượng; structure ⊃ pullback) |
| D thứ tự cổng che khuất | CÓ (spread/biến động đứng trước che 55% trạng thái, tín hiệu ảnh hưởng ít) |
| E định nghĩa trạng thái không nhất quán | **CÓ**: thang thời gian stop (M15) ≠ trigger (M5) |
| F căn chỉnh khung làm setup bất khả | Không bất khả, nhưng tương quan âm |
| G ngưỡng biến động bệnh lý | Một phần: phân vị tương đối, nhãn gần ngẫu nhiên so với tuyệt đối |
| H pullback và trigger không thể cùng tồn tại về nhân quả | **CÓ một phần** (cùng nến chỉ 156, ít hơn nửa kỳ vọng) ⇒ cần vòng đời tuần tự |
| I bộ lọc thực thi chặn setup hợp lệ | Không đáng kể |
| J lỗi cài đặt | Không tìm thấy lỗi tính toán; hạn chế thiết kế E/H |

## 10. Kết quả v1.2

Xem mục bổ sung ở cuối tài liệu sau khi chạy (sau commit pre-đăng ký).
