# V2 — Audit "bộ não", kiến trúc Candidate V2, Preregistration và tiêu chí chấp nhận

Ngày: 2026-10-13 · Trạng thái: **CỔNG A, chờ chủ dự án duyệt. Chưa viết mã sản phẩm.** (Chỉ có hai script nghiên cứu mô tả, không đổi chiến lược.)
Dữ liệu dùng: chỉ mô tả (đếm cổng), **không dùng kết quả giá (outcome)**; Test-H và Holdout **không bị chạm**.

---
## 0. Kết luận trong 10 dòng
1. **V2 hiện là vỏ mới + bộ não V1.** `core/decision.py` là V1 baseline v1.1.0 viết lại "không đổi hành vi" (docstring dòng 3–4), kiểm bằng golden parity với V1 (`scripts/parity/golden_core.py`), rồi bị khóa bằng sha256 (`tests/unit/test_strategy_lock.py`). Đó là quyết định có chủ đích (G4: parity trước, không tuning). Lớp G10 (M1/advice) chỉ tư vấn, **không đổi** BUY/SELL.
2. **Hệ thống không "luôn WAIT" vì lỗi mã**: BUY/SELL đối xứng (tỷ lệ qua cổng tương đương). Nó hiếm tín hiệu vì **một chuỗi AND của nhãn rời rạc** cộng với **các cổng cứng có thang đo không khớp thực tế**.
3. **Cửa sổ Dev 2011–2018:** 145.241 thanh M5; chuỗi V1 (bỏ cổng cứng) cho **189 thanh tín hiệu (0,13%) ≈ 67 episode trên 25 tháng mẫu (~32/năm)**. Sau cổng cứng chỉ còn **1** thanh. Nguyên nhân số 1 là cổng `spread/ATR(M5) > 0,15`: chặn **92,7%** thanh, vì trung vị spread/ATR5 là 0,26–0,59 trong mọi năm Dev.
4. **Cửa sổ hiện đại (2025-05..2026-04, đủ 12 tháng, đếm chính xác):** 57 thanh tín hiệu chuỗi, còn **25 thanh (17 episode, ≈1,4/tháng; BUY 16, SELL 9)** sau cổng cứng. Lúc này nguyên nhân chính chuyển sang **cổng biến động theo percentile (chặn 56% thanh theo cấu trúc)** và độ sâu chuỗi.
5. Forward V1 (9–13/10/2026): 1.705 lượt quyết định, **0 BUY/SELL**. Với tần suất 1,4 episode/tháng, xác suất không có tín hiệu trong 3,7 ngày là ≈84% ⇒ **chưa phải bằng chứng lỗi**.
6. Hệ quả quan trọng nhất: ở tần suất ~17 episode/năm, quy trình forward-evidence (≥100 lệnh đã đóng) cần **~6 năm**. V1 control **không thể được kiểm chứng trong thời gian hợp lý**. Mục tiêu tăng tần suất là để **kiểm chứng được**, không phải để có nhiều lệnh hơn.
7. Bốn nguyên nhân khan hiếm xếp hạng (mục 3). Ba trong bốn là **lỗi thang đo/thiết kế** chứ không phải kỷ luật rủi ro: (a) cổng spread/ATR5, (b) cổng biến động percentile, (c) yêu cầu SETUP và TRIGGER trùng cùng một thanh.
8. Đề xuất Candidate V2 gồm 7 thay đổi **mỗi thay đổi có giả thuyết, test, ablation riêng** (mục 5). Không đổi `MIN_NET_RR=1,5`, `R_MULTIPLE=2`, rủi ro 0,25%.
9. ML SHADOW thiết kế được (mục 6) nhưng **sẽ không đủ công suất thống kê** để được cấp quyền trong thời gian gần; điều này được nói rõ trong tiêu chí.
10. **Khuyến nghị:** giữ V1 làm control; duyệt triển khai Giai đoạn 4 theo preregistration dưới đây, với hai quyết định của chủ dự án ở mục 9.

---
## 1. Vì sao V2 vẫn khóa theo V1 v1.1.0 (bằng chứng)
| Bằng chứng | Vị trí |
|---|---|
| "V1's operational baseline v1.1.0 rewritten with NO behavioural change (G4 forbids strategy tuning)" | `src/xau_edge_v2/core/decision.py:3-5` |
| `STRATEGY_VERSION = "1.1.0"`, ngưỡng mặc định "equal V1's baseline" | `decision.py:34, 64-76` |
| Hằng số khớp V1: `ATR_K 1.25`, `MAX_STOP_ATR 3.0`, `R_MULTIPLE 2.0`, `MIN_NET_RR 1.5` | `core/risk.py:17-23` |
| `WIDE_SPREAD_PERCENTILE 0.9`, `MAX_SPREAD_TO_ATR 0.15`, `LOW/HIGH_VOL_PERCENTILE 0.2/0.8` | `core/market_state.py:36-39` |
| Parity với V1 (golden), sau đó pin sha256 7 tệp chiến lược + hằng số | `scripts/parity/golden_core.py`, `tests/unit/test_strategy_lock.py` |
| Commit lịch sử: G4 "canonical core ... golden parity with V1" | `52d1fed` |
| Lớp mới (G9/G10) chỉ cộng thêm, không quyết định | `core/execution.py`, `core/advice.py` |

Giải thích trung thực: V2 được dựng để **thay hạ tầng** (dữ liệu chỉ đọc, hợp đồng, PAPER, vận hành, UI) và chứng minh parity trước. Chưa bao giờ có công việc nghiên cứu lại logic quyết định. Vì vậy tên "V2" đúng với nền tảng, **chưa đúng với bộ não**.

---
## 2. Phương pháp audit funnel
- Công cụ: `scripts/research/funnel_audit.py`, `scripts/research/funnel_report.py` (chỉ đọc, 1 lõi/worker, ưu tiên thấp). Mỗi thanh M5 đã đóng: dựng `MarketState`, chạy `decide()` hai lần (cổng cứng bị vô hiệu để thấy chuỗi thật; và nguyên bản).
- Mẫu: **Dev 2011–2018: 25 tháng** (Feb/Jun/Oct mỗi năm + 2018-03), **Validation 2019–2021: 9 tháng**, **khoảng chưa dùng 2025-05..2026-04: 12 tháng liên tục (đủ)**. Test-H (2022-01..2025-04) và Holdout (2026-05-01..2026-10-07) bị từ chối ở mức mã.
- **Quy tắc chống rò rỉ thiết kế:** mọi quyết định thiết kế dựa trên **Dev + lý thuyết**. Validation và khoảng 2025–26 chỉ để xem ổn định của số đếm; không dùng để chọn thay đổi.
- Giới hạn: bộ mẫu Dev là 3 tháng/năm nên các số "/năm" là ngoại suy; số đếm theo thanh bị tự tương quan (nên có thêm số **episode**: các thanh cùng chiều cách nhau ≤60 phút gộp thành 1).
- Ngữ cảnh mô phỏng: equity giả định 10.000$, tin tức UNKNOWN (cảnh báo, không chặn) như PAPER hiện hành.

---
## 3. Kết quả funnel (đếm, tách BUY/SELL)
### 3.1 Chuỗi tuần tự (cổng cứng đã bỏ), Dev 2011–2018
| Bước | BUY | % của H1=BUY | SELL | % của H1=SELL |
|---|---|---|---|---|
| H1 bias đúng chiều | 56.724 | 100 | 48.260 | 100 |
| H4 không phủ quyết | 51.560 | 90,9 | 46.241 | 95,8 |
| M15 không ngược chiều | 42.577 | 75,1 | 37.535 | 77,8 |
| M15 cấu trúc cùng chiều (HH+HL) | 15.704 | 27,7 | 13.620 | 28,2 |
| Pullback trong dải EMA20 (SETUP_ARMED) | 5.803 | 10,2 | 4.789 | 9,9 |
| M5 momentum cùng chiều (TRIGGER) | 720 | 1,27 | 642 | 1,33 |
| M1 thực thi ok | 714 | 1,26 | 635 | 1,32 |
| Room ≥ 1 ATR tới swing đối diện | 357 | 0,63 | 388 | 0,80 |
| Stop hợp lệ (≤3 ATR) | 346 | 0,61 | 369 | 0,77 |
| Net R:R ≥ 1,5 | **92** | 0,16 | **97** | 0,20 |
| Không cổng cứng (spread/vol) | **0** | 0 | **1** | 0 |

Đối xứng: tỷ lệ qua từng bước của BUY và SELL gần nhau ⇒ không có thiên lệch mã giữa hai phía. Chênh lệch theo năm (ví dụ 2012: BUY 9/SELL 0; 2015: BUY 0/SELL 13) là **regime xu hướng**, không phải lỗi.

### 3.2 Ba cửa sổ so sánh (thanh tín hiệu = chuỗi qua hết, sau cổng cứng)
| Cửa sổ | Thanh M5 | Chuỗi (bỏ cổng) BUY/SELL | Episode chuỗi | Sau cổng cứng BUY/SELL | Episode cuối | Thanh bị `SPREAD` | `VOL cao` | `VOL thấp` |
|---|---|---|---|---|---|---|---|---|
| Dev (25 th) | 145.241 | 92 / 97 | 67 | 0 / 1 | 1 | 179/189 | 117/189 | 15/189 |
| Validation (9 th) | 51.932 | 71 / 35 | 36 | 10 / 10 | 10 | 51/106 | 53/106 | 13/106 |
| 2025-05..2026-04 (12 th, đủ) | 70.156 | 27 / 30 | 39 | 16 / 9 | **17** | 12/57 | 18/57 | 11/57 |

(Nhiều cổng có thể cùng chặn một thanh nên các cột không cộng thành 100%.)

### 3.3 Top nguyên nhân gây khan hiếm (xếp hạng theo tác động trên thanh tín hiệu của chuỗi)
| # | Nguyên nhân | Bằng chứng (Dev) | Bằng chứng (hiện đại 2025–26) | Bản chất |
|---|---|---|---|---|
| 1 | **Cổng `spread/ATR(M5) > 0,15`** | chặn 92,7% thanh; 179/189 tín hiệu; trung vị spread/ATR5 0,26–0,59 mọi năm; ở thanh tín hiệu trung vị 0,34 | còn 7,1% thanh; 12/57 tín hiệu | **Thang đo không khớp**: so spread với nhiễu 5 phút. Phép tính R:R đã tự định giá chi phí: `net=(2R−s)/(R+s) ≥ 1,5` cho phép spread tới 0,2R ≈ 0,31 ATR15; ở thanh tín hiệu spread/ATR15 trung vị 0,14, **0% vượt 0,31** ⇒ cổng này chặn các lệnh mà chính luật R:R của V1 chấp nhận |
| 2 | **Cổng biến động theo percentile** (`LOW ≤ 20%`, `HIGH ≥ 80%` của 200 thanh ATR) | chặn 21,6% + 19,2% thanh (≈40% theo cấu trúc, bất kể mức biến động tuyệt đối); `HIGH`/H4-SHOCK chứa 117/189 tín hiệu | chặn 24,6% + 21,4%; 29/57 tín hiệu | **Thiết kế**: xếp hạng nội bộ luôn chặn ~40% thời gian; loại đúng giai đoạn xu hướng mở rộng. Tác động lên kết quả chưa biết (cần ablation) |
| 3 | **SETUP và TRIGGER phải trùng cùng một thanh** | thanh ARMED 5.803 (BUY) nhưng cùng M5 trigger chỉ 720 (12,4%). Nếu setup được "nhớ" 6 thanh M5: **1.438 (×2,0)**; 12 thanh: 1.745 (×2,4). SELL: 642 → 1.179 → 1.407 | (cùng cấu trúc) | **Thiết kế**: V1 không có vòng đời; pullback đã kết thúc khi nến bật lên xác nhận (giá rời dải EMA) |
| 4 | **Hình học: room + net R:R** | 720 → 92 BUY (−87%); `RR_TOO_LOW` 526, `TOO_CLOSE_*` 604 | 308 → 27 BUY (−91%); `RR_TOO_LOW` 222 | `room ≥ 1 ATR` thực tế bị `net R:R ≥ 1,5` chi phối: mục tiêu bị chặn ở swing M15 gần nhất, nên cần room ≈ 2,5 ATR. Một pullback nông trong xu hướng hiếm khi còn 2,5 ATR tới swing trước ⇒ xung đột cấu trúc với chính setup pullback |
| 5 | M15 cấu trúc "UP/DOWN" (HH+HL chặt) | chỉ 27,7–28,2% thanh của phía H1 | tương tự | Nhãn nhị phân dễ vỡ: một swing lệch là về RANGE; 40% thanh là `RANGE`, 11% là `REVERSAL_*` (cửa sổ CHoCH 6 thanh) |
| 6 | Tập trung phiên | **67%** tín hiệu chuỗi nằm ở **ASIA**, 20% OFF_HOURS; chỉ 7% ở London/NY | ASIA 44%, NY 30% | Setup pullback+trigger xuất hiện khi thị trường yên ắng, đúng nơi spread rộng và percentile thấp; xung đột với cổng 1 và 2 |

M1 gần như không chặn (1,3% thanh `QUIET`, 0,3% `STALE`; "SPREAD_WIDE" 93% chỉ là bản sao của cổng 1).

### 3.4 Forward hiện có (không đủ để kết luận thống kê)
- **V1** `data/trade/decisions-*.jsonl`, 2026-10-09 → 10-13: 1.705 lượt (1/phút, tự tương quan cao), **0 BUY/SELL**; có cổng cứng 60%; `SPREAD_TOO_WIDE` 788 lượt (46%), vol-thấp 480, vol-cao 195, `NO_DIRECTION` 282, `NO_SETUP` 254, `TIMEFRAME_CONFLICT` 97, `NO_TRIGGER` 35. H1 BULLISH 66%.
- **V2** `decision_log`: 43 thanh M5 (3,5 giờ), 0 tín hiệu, 41/43 bị cổng spread/vol.
- Kết luận: nhất quán với tần suất nền ~1,4 episode/tháng; mẫu quá nhỏ để nói gì thêm.

### 3.5 Giới hạn của audit
Chỉ đếm, không có outcome nên **chưa biết tín hiệu bị chặn tốt hay xấu**. Cổng có thể đang chặn đúng những tín hiệu tệ. Đó chính là lý do mỗi thay đổi dưới đây phải qua ablation có chi phí thực.

---
## 4. Nguyên tắc thiết kế Candidate V2
1. Logic quyết định **thật sự khác** V1 ở cấu trúc (có vòng đời, ngưỡng theo kinh tế học chi phí-trên-rủi ro), không phải tham số nới.
2. **Không nới ngưỡng cho có lệnh.** Mọi hằng số mới được suy từ đại số của chính luật V1 hoặc cố định a priori, **ghi trước**, tối đa một giá trị mỗi thay đổi; mức độ nhạy chỉ báo cáo, không dùng để chọn.
3. **Bất biến an toàn không đổi:** rủi ro 0,25%/lệnh, `MIN_NET_RR 1,5`, `R_MULTIPLE 2`, `MAX_STOP_ATR 3`, stop cấu trúc + ATR, governor, PAPER only, không broker.
4. **Đối xứng BUY/SELL cưỡng bức bằng test** (gương).
5. Độc lập: `strategy_id = xau_mtf_cv2`, `version 2.0.0-cand.1`, config và evidence riêng; V1 giữ nguyên làm CONTROL, các test khóa không đổi.
6. Một ứng viên được hoàn tất khi mọi thay đổi đã qua ablation; không có "vòng thử thêm" sau khi thấy Validation.

---
## 5. Các thay đổi của Candidate (giả thuyết · lý do · test · ablation · tiêu chí loại)
Ký hiệu đo: **R** = tần suất episode/năm; **E** = expectancy sau chi phí mỗi lệnh (đơn vị R); **MDD** = drawdown tối đa (R); **FP** = tỷ lệ lệnh chạm SL trong ≤ 6 thanh M5 đầu.

| ID | Thay đổi | Giả thuyết (có thể sai) | Lý do từ audit | Ablation | Loại nếu |
|---|---|---|---|---|---|
| C1 | **Vòng đời có trạng thái** `IDLE→BIASED→ARMED→TRIGGERED→EXECUTABLE→EXPIRED/INVALIDATED`. ARMED nhớ tối đa **6 thanh M5 (30 phút)**; vô hiệu khi H1 đổi chiều hoặc giá đóng ngoài swing pullback; một candidate duy nhất cho mỗi setup | Setup và trigger là hai sự kiện nối tiếp; bắt buộc trùng thanh bỏ sót setup hợp lệ mà không làm yếu từng điều kiện | mục 3.3 #3: ×2,0 thanh trigger | V1 + C1 | E hoặc FP xấu hơn control quá biên không thua kém (mục 8) |
| C2 | **Cổng chi phí theo rủi ro**: thay `spread/ATR5>0,15` và `spread percentile ≥0,9` bằng `cost/risk ≤ 0,15R` (spread + trượt giá, trên khoảng stop). 0,15 suy từ `MIN_NET_RR=1,5` (ngưỡng kinh tế 0,2R) trừ biên an toàn 25% | Cổng đúng phải đo chi phí so với **rủi ro lệnh**, không so với nhiễu 5 phút | #1: chặn 92,7% Dev; thanh tín hiệu 0% vượt 0,31 ATR15 | V1 + C2; độ nhạy 0,10/0,20 chỉ báo cáo | E sau chi phí kém; hoặc xuất hiện lệnh chi phí >0,15R |
| C3a | Bỏ cổng `VOLATILITY_TOO_LOW` percentile (đã được C2 phủ: biến động thấp ⇒ risk nhỏ ⇒ cost/risk cao) | Cổng LOW thừa khi có C2 | #2 | C2 vs C2+C3a | E kém |
| C3b | Thay cổng `HIGH` percentile + `H4 HIGH_VOLATILITY` bằng chỉ **SHOCK** (range ≥3 ATR) và M1 ABNORMAL; stop giữ theo ATR nên rủi ro tự co giãn | Tiếp diễn xu hướng sống ở biến động cao; percentile nội bộ chặn nhầm | #2: HIGH chứa 62% tín hiệu Dev | C3a vs C3a+C3b | MDD/E xấu hơn; hoặc tập trung thua trong HIGH |
| C4 | **Setup M15 theo độ hồi** thay cho dải EMA20: hồi 0,25–0,75 của chân xung H1/M15 gần nhất (dùng swing sẵn có, không chỉ báo mới), không phá gốc chân | Pullback đo theo kích thước chân, không theo khoảng cách EMA, đối xứng và không phụ thuộc thang giá | #5: HH+HL chặt 28%; dải EMA không liên hệ kích thước chân | V1 + C4 | tái hiện lỗi đối xứng, hoặc E kém |
| C5 | **Trigger M5 = BOS cùng chiều** (đóng nến vượt swing M5 gần nhất) trong khi ARMED; bỏ điều kiện RSI/ROC dư thừa | Sự kiện nhân quả là phá cấu trúc vi mô, RSI/ROC chỉ lặp lại | #3: trigger V1 12% | V1 + C1 + C5 | FP tăng quá biên |
| C6 | **Timing M1** = trạng thái G10 (`CONFIRMED/EXECUTION_WINDOW`, chất lượng ≠ BAD, không `TOO_LATE`), thay các nhãn M1 của V1 (QUIET theo tick volume) | M1 chỉ định thời điểm, không định hướng; tick volume yếu | `core/execution.py` đã có test | V1 + C6 | thời điểm vào xấu hơn (FP) |
| C7 | **Room theo mức khung lớn**: "đối diện" = swing H1 / PDH–PDL gần nhất (không phải mọi swing M15 trong 10 swing); vẫn đòi `net R:R ≥ 1,5` | Swing M15 nhỏ là nhiễu cản trở giả với pullback continuation; mức H1 mới là cản thực | #4: −87..91% | V1 + C7 | tỷ lệ chạm TP thấp hơn trên các tín hiệu mới |

**Ma trận ablation (ghi trước):** (a) V1 (control); (b) V1 + Ci cho từng i (7 lần); (c) Candidate đầy đủ; (d) Candidate trừ từng Ci (7 lần); (e) Candidate + ML shadow (không thay đổi hành động). Mỗi thay đổi **chỉ được giữ** nếu cả (b) và (d) đều ủng hộ (vào được thì có lợi, bỏ ra thì mất lợi), trên Dev; xác nhận một lần trên Validation.

---
## 6. ML SHADOW (không quyền giao dịch)
- **Vai trò:** quan sát. Không tạo/hủy/sửa BUY/SELL/WAIT (`authority: NONE`, như ADR-V2-005).
- **Mục tiêu dự đoán:** với mỗi trạng thái ARMED của Candidate (và giả định vào lệnh theo luật candidate), nhãn = kết quả triple-barrier **sau chi phí** (đạt TP1 / chạm SL / hết hạn), mô phỏng bằng đúng quy tắc fill/chi phí PAPER (SL thắng khi mơ hồ).
- **Đặc trưng (đều nhân quả, đã có trong core):** các khoảng cách theo ATR, độ hồi, tuổi setup, trạng thái H4/H1/M15/M5, spread/risk, phiên, đặc trưng M1 (G10), phân vị biến động. Không thêm chỉ báo mới.
- **Mô hình:** hai ứng viên: hồi quy logistic có chuẩn hóa (cơ sở) và LightGBM nhỏ; **bộ 5 mô hình bootstrap** để đo độ bất định; khoảng bất định bằng conformal.
- **Đầu ra live/forward:** `p_win`, khoảng bất định, **bất đồng** với rule (rule=CANDIDATE nhưng ML thấp, hoặc ngược lại), cờ "ngoài phân phối"; ghi toàn bộ vào `ml_shadow_log` (chỉ thêm) cùng `feature_hash`, `model_version`.
- **K accounting:** họ mới `K_V2_CAND_ML`, K=2 (logistic, LightGBM), một phía 97,5%; chỉ chạy trên dữ liệu bảo vệ.
- **Cảnh báo công suất (trung thực):** để phát hiện cải thiện E = +0,15R với SD ≈ 1,2R ở mức một phía 97,5%, cần ≈ **250 lệnh mỗi nhánh**. Với tần suất hiện tại, cửa sổ 2025–26 (≈17 episode) hoàn toàn không đủ; chỉ Test-H (3,3 năm) có khả năng, và Test-H đang khóa. Vì vậy **ML shadow nhiều khả năng ở trạng thái SHADOW lâu**; điều này không phải thất bại, chỉ là giới hạn dữ liệu.
- **Xung đột chỉ đạo cần xác nhận:** trước đó chủ dự án chỉ đạo "không mở họ ML mới". Chỉ đạo lần này yêu cầu ML shadow. Em coi đây là **họ mới, chỉ shadow, cần duyệt ở Cổng A** (mục 9).

---
## 7. Cửa sổ dữ liệu và quy tắc không hindsight
| Cửa sổ | Dùng cho | Trạng thái |
|---|---|---|
| Dev 2011–2018 | thiết kế, ablation, mọi lựa chọn | mở, đã "đốt" cho mô tả |
| Validation 2019–2021 | **một lần** xác nhận candidate đã đóng băng | mở nhưng chưa xem outcome của chiến lược |
| 2025-05..2026-04 | chỉ xem số đếm ổn định; **chưa** xem outcome | đề xuất làm "Confirm-C" nếu chủ dự án đồng ý (mục 9) |
| Test-H 2022-01..2025-04 | xác nhận cuối (ứng viên + ML), **một lần** | **KHÓA**, cần phê duyệt + sổ K |
| Holdout 2026-05-01..2026-10-07 | xác nhận cuối | **KHÓA** |
| Forward từ 2026-10-08 | bằng chứng sống, PAPER | đang tích lũy |

Quy tắc: không chọn tham số bằng Validation/Confirm-C/Test-H/Holdout; tất cả hằng số mới ghi ở tài liệu này **trước** khi chạy; mọi lần chạy ghi vào sổ; spec đóng băng bằng sha256 như ML V0.

---
## 8. Tiêu chí chấp nhận (ghi trước)
### 8.1 Đo (cả ba nhánh: V1 control / V2 deterministic / V2 + ML shadow)
Tần suất (episode/năm), **độ với tới của setup** (tỷ lệ thanh ARMED đi tới EXECUTABLE), **đối xứng BUY/SELL** (tỷ lệ episode trên mỗi thanh H1-bias, khoảng [0,5; 2,0]), **expectancy sau chi phí** (R/lệnh; cận dưới 97,5% một phía, bootstrap theo khối tháng), **drawdown tối đa (R)** và tháng tệ nhất, **ổn định** theo năm/regime/phiên (tỷ lệ năm không âm; không có phiên nào chiếm >60% lệnh), **tỷ lệ dương tính giả** (SL ≤6 thanh M5), độ lệch chi phí thực tế so với giả định.

### 8.2 Tiêu chí để một thay đổi Ci được giữ (Dev, rồi 1 lần Validation)
1. **Không thua kém control** về E với biên δ = 0,10R (cận dưới 97,5% của hiệu E ≥ −0,10R).
2. **MDD không tăng quá 20%** so với control trên cùng số lệnh chuẩn hóa.
3. **FP không tăng quá 5 điểm %.**
4. **Đối xứng** trong khoảng quy định.
5. Mang lại **cải thiện độ với tới** (≥ ×1,3 số episode) hoặc đơn giản hóa/chính xác hóa mà không giảm E (ghi rõ loại).
6. Không có lệnh nào vi phạm bất biến an toàn (test thuộc tính).

### 8.3 Tiêu chí cho Candidate đầy đủ
- Đạt 8.2 trên Dev và xác nhận Validation (một lần).
- **Tối thiểu 150 episode** trong Dev+Validation để ước lượng E có ý nghĩa (nếu thấp hơn ⇒ kết luận "không kiểm chứng được").
- Tần suất ước tính đủ để đạt 100 lệnh forward trong **≤ 24 tháng** (≥ 50 episode/năm). Nếu không đạt, báo "không kiểm chứng được trong thời gian hợp lý" dù E đẹp.
- **Không được tuyên bố edge.** Tuyên bố chỉ khi theo `FORWARD_EVIDENCE_PROTOCOL` (≥100 lệnh đã đóng, ≥60 ngày, độ phủ ≥95%, cận dưới >0, giả thuyết do chủ dự án duyệt).

### 8.4 Tiêu chí ML shadow để **xem xét** cấp quyền (không tự động)
Trên dữ liệu bảo vệ: Brier/log-loss tốt hơn tỷ lệ nền với cận dưới CI >0; hiệu chuẩn trong [75%, 85%] cho khoảng 80%; E của tập "ML cho phép" hơn tập không lọc ≥ +0,15R với cận dưới >0; ổn định ≥75% năm; parity live/replay đạt. **Không đạt thì ML ở shadow vĩnh viễn.**

### 8.5 Tiêu chí an toàn và UI
Strategy V1 không đổi (test khóa xanh); không đường broker (OpenAPI 3 POST, quét AST); PAPER only; UI chỉ thêm dải **BIAS → SETUP → TRIGGER → M1 TIMING → BLOCKER → CANDIDATE → HUMAN DECISION** kèm "vì sao chưa vào lệnh" và "điều kiện còn thiếu"; axe/console/API sạch.

---
## 9. Quyết định cần chủ dự án (Cổng A)
1. **Duyệt** triển khai Giai đoạn 4 theo preregistration này (C1–C7, ma trận ablation, tiêu chí mục 8)? Nếu muốn bỏ/thêm thay đổi, nói trước khi chạy.
2. **Cửa sổ xác nhận:** (a) chỉ dùng Validation (một lần) rồi forward; hay (b) cho phép dùng 2025-05..2026-04 làm "Confirm-C" (một lần), và (c) có mở **Test-H một lần** cho Candidate đã đóng băng (K=1: candidate vs control theo cặp) không? Khuyến nghị: **(a)+(b)** trước, giữ Test-H cho ML shadow.
3. **Xác nhận ML shadow là họ mới `K_V2_CAND_ML`** (mục 6), thay cho chỉ đạo trước "không mở họ ML mới".
4. **Chi phí máy:** mô phỏng đầy đủ Dev cần ~75 phút CPU một lõi cho bảng đặc trưng (một lần, dùng chung cho mọi ablation); em sẽ chạy tối đa 4 worker ưu tiên thấp, CPU dưới ~60%.

---
## 10. Câu trả lời cho các câu hỏi chốt (tạm thời, trước ablation)
| Câu hỏi | Trả lời hiện tại |
|---|---|
| Giữ V1 control? | **Có**, bất biến. Nó là mốc so sánh và vẫn là hệ thống PAPER đang chạy |
| Candidate nào đáng tiếp tục? | Một ứng viên gồm C1–C7; thứ tự ưu tiên theo mức tin cậy từ audit: **C2 (cổng chi phí), C1 (vòng đời), C3 (vol)** có bằng chứng cấu trúc mạnh nhất; C4/C5/C7 là giả thuyết yếu hơn, dễ bị loại |
| Gate nào loại/thay/giữ? | **Thay:** `spread/ATR5` → cost/risk; percentile vol → SHOCK + cost/risk. **Giữ:** H1 là nguồn hướng duy nhất, H4 phủ quyết, stop cấu trúc+ATR, `MIN_NET_RR`, governor. **Chưa kết luận** về room/swing |
| ML shadow có giá trị? | **Chưa biết**; thiết kế khả thi nhưng công suất thấp ⇒ nhiều khả năng chỉ có giá trị quan sát |
| V2 đã có bộ não mới? | **Chưa.** Hiện là V1 trong vỏ V2. Candidate là con đường để có, và chỉ được gọi là "bộ não mới" nếu qua mục 8 |

---
## 11. Tái lập
`uv run python scripts/research/funnel_audit.py --out data/research/funnel --jobs 4` rồi `funnel_report.py <thư mục> --json <tệp>`. Số liệu thô: `reports/evidence/v2_brain_audit/{dev,val,gap}_report.json`. Dữ liệu từng thanh: `xau-edge-v2/data/research/` (gitignore).
