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

## 10. Kết quả v1.2 (đối chiếu pre-đăng ký, commit `97afc2c`)

Dữ liệu chấp nhận **chưa từng được xem lúc thiết kế**: E1 2025-08-04→09-01 (5 460 quyết định M5) và E2 2025-12-01→12-29 (5 149), cùng 24 ngày giao dịch mỗi cửa sổ (48 ngày). Công cụ: `scripts/trade_v12_eval.py` (một tiến trình/cửa sổ, tất cả biến thể dùng chung một trạng thái). Chỉ khả thi vận hành; kết quả mô phỏng ở mục 11.

### 10.1 Tần suất (setup riêng biệt)

| Biến thể | E1 (BUY+SELL) | E2 | Gộp | Setup/ngày |
|---|---|---|---|---|
| v1.1.0 | 2+3 | 0 | 5 | 0.104 |
| none (v1.2 code, cả ba thay đổi tắt) | 2+3 | 0 | 5 | 0.104 |
| A (vòng đời) | 2+2 | 1+0 | 5 | 0.104 |
| B (hình học M5, bỏ clearance) | 2+4 | 4+1 | 11 | **0.229** |
| C (biến động → cảnh báo) | 2+3 | 0 | 5 | 0.104 |
| A+B | 2+2 | 3+1 | 8 | 0.167 |
| **A+B+C = v1.2** | 2+2 | 3+1 | **8** | **0.167** |

Chẩn đoán thêm (cửa sổ đã xem, KHÔNG dùng để chấp nhận): gỡ veto spread tương đối: v1.1+D 6 (0.125/ngày), v1.2+D 10 (0.208/ngày).

### 10.2 Tiêu chí pre-đăng ký

| # | Tiêu chí | Kết quả |
|---|---|---|
| 1 | Nhân quả, không nhìn tương lai | ĐẠT: quyết định tại t không đổi khi cắt bỏ nến sau t (test `test_the_lifecycle_never_looks_ahead`), parity full vs tail |
| 2 | Xác định + parity | ĐẠT: parity ABC **0 khác biệt / 10 609 quyết định**; hash luồng quyết định lặp lại bằng bản cũ |
| 3 | Kế hoạch hợp lệ 100% | ĐẠT: 0 vi phạm (SL/TP đúng phía, lot ≥ min và đúng bước, rủi ro ≤0.5%, R/R ≥1.5, stop ≥ mức broker) cho 8 tín hiệu |
| 4 | Dải [0.25, 8] setup/ngày | **KHÔNG ĐẠT: 0.167** |
| 5 | Không trùng lặp | ĐẠT: 0 setup có >1 quyết định; 0 trùng cùng hướng cùng nến M15 |
| 6 | Giải thích được | ĐẠT (phễu suy ra từ quyết định thật) |

**Kết luận theo quy tắc đã đăng ký: v1.2 BỊ LOẠI khỏi vai trò mặc định vận hành** (không đạt tiêu chí 4). Không chỉnh N, hệ số hay ngưỡng để "đạt". v1.1.0 vẫn là mặc định; v1.2.0 vẫn chọn được bằng `XAU_EDGE_BASELINE_VERSION=1.2.0` như một quyết định có chủ đích của chủ dự án (nó đạt mọi tiêu chí trừ dải tần suất).

### 10.3 Diễn giải (không vượt quá dữ liệu)

* **H-B (hình học đúng thang)**: được ủng hộ. Một mình B nâng 5 → 11 setup (2.2×) và là thay đổi duy nhất đưa tần suất gần dải (0.229).
* **H-A (vòng đời tuần tự)**: KHÔNG được ủng hộ trên E1/E2: A một mình không thêm setup (5 → 5), và A+B (8) *ít hơn* B (11) vì quy tắc "một tín hiệu mỗi pullback" loại các trigger lặp mà B (cùng nến) vẫn phát. Phân bố giai đoạn của v1.2: nhiều setup ARMED hết hạn mà không trigger (E1: EXPIRED 480 so với TRIGGERED 75 lượt quyết định; E2: 763 so với 88).
* **H-C (biến động là cảnh báo)**: trung tính về tần suất (5 → 5); lợi ích là minh bạch (không che 54% trạng thái).
* Cổng đứng đầu theo lý do chặn đầu tiên của v1.2: E1: NO_SETUP 2093, SPREAD_TOO_WIDE 1841, NO_DIRECTION 820, TIMEFRAME_CONFLICT 491, NO_TRIGGER 168; E2: NO_SETUP 2554, NO_DIRECTION 1284, SPREAD_TOO_WIDE 530, TIMEFRAME_CONFLICT 449, NO_TRIGGER 267. Sau khi trigger bắn: RR_TOO_LOW 6+9, INVALID_STOP_DISTANCE 5+2, VOLUME_TOO_LOW 4+6.
* Phân phối 8 tín hiệu v1.2: BUY 5 / SELL 3; phiên: New York 4, London-NY overlap 2, London 1, Asia 1; giờ UTC 2, 9, 14, 15, 16, 18, 18, 20.
* **Kết luận cấu trúc**: khái niệm setup hiện tại (pullback nông về EMA20 M15 khi cấu trúc M15 còn UP, trigger M5 động lượng, R/R ròng ≥1.5 với mục tiêu bị chặn bởi mức M15) cho khoảng 0.1–0.23 setup/ngày trên XAUUSD (tương đương 1 setup mỗi 4–10 ngày). Với tần suất này, chỉ forward paper không thể thực hành vòng đời ổn định; đó là lý do cần Acceptance Replay. Phần "TIMEFRAME_CONFLICT" 17% ở v1.2 gồm cả pullback sâu (cấu trúc M15 đảo tạm thời) mà định nghĩa hiện tại coi là xung đột — đây là hướng thiết kế mới hợp lý nhất, nhưng phải là v1.3 có pre-đăng ký riêng trên cửa sổ chưa dùng (E3 2025-09-08→10-06, E4 2026-03-09→04-06), không phải chỉnh tại chỗ.

## 11. Kết quả mô phỏng vòng đời paper (THĂM DÒ, dữ liệu đã đốt, không phải bằng chứng edge)

`scripts/trade_acceptance_replay.py` (AUTO_PAPER, bàn paper thật): v1.2 E1: 3 lệnh, 3 SL, −3.02R; v1.2 E2: 4 lệnh, 1 TP + 3 SL, −1.03R; v1.1 E1: 4 lệnh, 1 TP + 2 SL + 1 TIME_EXIT, −0.47R (đã trừ chi phí). Mẫu quá nhỏ để kết luận; **không có lý do để coi kết quả này là dấu hiệu của edge, và nó không bị che giấu**: trong 11 lệnh chỉ 2 chạm TP. Edge validation vẫn 0%.
