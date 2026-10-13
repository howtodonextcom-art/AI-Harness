# XAU EDGE: kiểm toán kỹ thuật và hướng xây dựng thực dụng

Ngày: 2026-10-12 · Đối tượng kiểm toán: `Z:\Coding\Projects\AI-Harness\xau-edge` (206 commit, từ 2026-10-01 đến 2026-10-12; HEAD `daf22f6`) · Tài liệu đối chiếu: `75.md` (bản gộp Bài 57–75 của "Ci") và [báo cáo kiểm chứng ảnh](IMAGE_CLAIMS_VERIFICATION_2026-10-12.md).

Quy ước: **[SỰ THẬT TỪ CODE]** có `file:dòng` · **[SỐ LIỆU]** có nguồn tái lập được · **[Ý KIẾN CỦA TÔI]** là nhận định, có thể sai. Chỗ nào không kiểm chứng được tôi ghi **[SUY ĐOÁN]**. Đây là phân tích kỹ thuật, không phải lời khuyên đầu tư.

---

## A. Tóm tắt cho người không chuyên

1. **Dự án là gì:** một "bàn quyết định" cho XAUUSD: lấy dữ liệu MT5 → làm sạch → tính trạng thái thị trường → trả lời **MUA / BÁN / CHỜ** kèm giá vào, cắt lỗ, chốt lời, cỡ lệnh. Chế độ duy nhất đang chạy là **PAPER (giả lập)**; không gửi lệnh thật.
2. **Có đưa ra thời điểm MUA/BÁN không?** Có, về thiết kế. Trên thực tế **1.204/1.204 quyết định trong 4 ngày live đều là CHỜ**, và bàn giả lập chưa từng có lệnh nào.
3. **Có dùng Machine Learning thật không?** **Có, ML thật** (logistic, random forest, XGBoost, LightGBM, huấn luyện walk-forward, có hiệu chỉnh xác suất). **Nhưng ML không nằm trong đường quyết định đang chạy.** Quyết định live là một chuỗi quy tắc đa khung thời gian (H4 → H1 → M15 → M5 → M1), không có mô hình học máy.
4. **Kết quả:** toàn bộ ~44 biến thể giả thuyết đã đăng ký trước, 4 mô hình ML và 3 baseline **đều không có lợi thế sau chi phí**. Kết luận chính thức của dự án: *"NO EDGE WITHIN BUDGET"*. Tôi đối chiếu độc lập bằng 100+ ảnh giao dịch và dữ liệu của chính dự án: **cùng kết luận**.
5. **Chất lượng kỹ thuật:** rất cao so với mặt bằng (kỷ luật chống rò rỉ dữ liệu, đăng ký giả thuyết trước, không chạm tập kiểm tra, chi phí thật, chỉ một điểm gọi `order_send`, luôn khóa giao dịch thật). Rủi ro nằm ở **phạm vi**: ~45.000 dòng mã Python để chứng minh... chưa có lợi thế.
6. **Điểm mấu chốt tôi tìm ra:** chi phí giao dịch so với biên độ giá **giảm 4–7 lần** từ 2018 đến 2026 (vàng từ 1.260 lên 4.500 USD, ATR giờ từ 2,8 lên 19 USD, trong khi spread gần như không đổi). Các thí nghiệm của dự án dùng giai đoạn 2011–2018 làm chuẩn, nên **có thể đánh giá quá bi quan về môi trường chi phí hiện nay**. Nhưng cũng chính giai đoạn 2025–26 là xu hướng tăng rất mạnh, dễ nhầm **beta (vàng tăng) với alpha (lợi thế)**.
7. **Nếu tôi là chủ dự án:** đóng băng bộ não quy tắc hiện tại, biến sản phẩm thành **bàn kỷ luật và rủi ro cho giao dịch thủ công** (phần đã gần xong), và chạy song song một **chương trình tìm lợi thế giới hạn 60 ngày** với cổng dừng rõ ràng. Nếu không giả thuyết nào sống sót, dừng tìm edge và giữ nền tảng dữ liệu.
8. **Việc cần làm tuần này:** xem mục D.7.

---

## B. Trả lời năm câu hỏi

### B1. Mục đích của dự án

**Kết luận:** nền tảng nghiên cứu và hỗ trợ ra quyết định xác suất cho XAUUSD, **không phải** "AI dự đoán giá". *Mức tin cậy: CAO.*

- **[SỰ THẬT TỪ CODE/TÀI LIỆU]** `README.md`: "Probabilistic decision-support and research platform for XAUUSD"; trả lời BUY, SELL hoặc **WAIT**, và "a high-quality 'no trade' is a valid and valuable output". `docs/BRIEF.md` §1–2: "The project must NOT be designed as 'AI predicts gold price'", tách **dự báo** khỏi **quyết định giao dịch**.
- **Đầu vào:** nến MT5 (M1–H4) và tick (từ 2021-10), đọc qua một "collector" chỉ-đọc từ terminal FTMO Demo.
- **Đầu ra:** `TradingSignal` (BUY/SELL/WAIT, entry, SL, TP1/TP2, R:R ròng sau spread, rủi ro %, cỡ lot theo thông số hợp đồng của broker, lý do từ chối, mức bằng chứng).
- **Ranh giới an toàn [SỰ THẬT TỪ CODE]:** `config.py:37,72-78` cấm bật `enable_live_trading`; **chỉ có một lời gọi `order_send`** trong toàn bộ `src` (`brokers/mt5_demo/executor.py:348`); `trading/demo_lock.py` giải thích vì sao DEMO đang khóa; bàn PAPER "never sends an order". Tài khoản funded khóa cho tới khi mọi quy tắc FTMO được xác minh.

### B2. Dòng dữ liệu (dữ liệu → quyết định)

```
MT5 terminal (FTMO Demo, chỉ-đọc)
   │  collector (market_data/, ~6.000 dòng): nến M1-H4, tick, đồng hồ broker NY+7, lịch nghỉ
   ▼
data/market  (Parquet + DuckDB, 1,8 GB; M1 từ 2004-06, tick từ 2021-10; không sửa tại chỗ)
   │  validators (16 mã lỗi), resample, kiểm tra độ mới
   ▼
trading/market_state.py  ── mỗi khung: ATR, EMA20/50, ADX, RSI, ROC, swing/BOS/CHoCH,
   │                          regime, tick-volume z, spread percentile
   ▼
trading/baseline.py  (chuỗi quy tắc, KHÔNG có ML)
   │  H4 chặn → H1 hướng → M15 setup (pullback) → M5 trigger → M1 chặn → vị trí S/R →
   │  SL (cấu trúc/ATR) → TP (2R, giới hạn bởi S/R, ròng sau spread) → cỡ lot (tick_value broker)
   ▼
trading/governor.py + paper_desk.py  (giới hạn lệnh/ngày, cooldown, lỗ ngày 2%/3,5%) → bàn PAPER
   ▼
API (FastAPI :8000)  →  Dashboard (Next.js :3000): /trade /dữ liệu /journal /research
```

Song song, **ngoài đường live**: pattern similarity, outcomes, ML, backtest, evaluation/edge-program (nghiên cứu).

### B3. Machine Learning có thật không?

**Kết luận:** có ba loại thành phần khác nhau; chỉ loại (a) là ML đúng nghĩa, và loại (a) **không** điều khiển tín hiệu live. *Mức tin cậy: CAO (đã đọc code và kiểm tra nơi gọi).*

**(a) ML được huấn luyện thật [SỰ THẬT TỪ CODE]**

| Mục | Chi tiết | Nguồn |
|---|---|---|
| Thuật toán | Logistic regression, Random Forest, XGBoost, LightGBM | `models/zoo.py:25-124` |
| Siêu tham số | Cố định *a priori*, không tinh chỉnh: logistic C=0,1; RF 200 cây, depth 6, min leaf 50; XGB 200 cây, depth 3, lr 0,05; LGBM 200 cây, 8 lá, lr 0,05; seed 7 | `models/zoo.py:25-53` |
| Bài toán | Phân loại 3 lớp: sau 20 nến M15 (5 giờ) giá **DOWN / NEUTRAL / UP** (vùng trung tính 0,5 ATR) | `models/dataset.py:129-175`, `docs/research/model-evaluation.md` |
| Đặc trưng | 54 cột không phụ thuộc mức giá: lợi suất, khoảng cách tới EMA 9/20/50/200, ADX/DI, RSI, MACD/ATR, stochastic, Bollinger, biến động, nến, tick-volume, giờ/thứ dạng sin-cos, phiên, regime, trạng thái cấu trúc thị trường | `models/dataset.py:30-79` |
| Chống rò rỉ | Walk-forward theo tháng, cửa sổ mở rộng; nhãn nhìn trước 20 nến nên huấn luyện chỉ dùng hàng có chỉ số ≤ `f−21`; có thêm 20 nến "embargo" giữa tập fit và tập hiệu chỉnh | `models/walkforward.py:80-101` |
| Hiệu chỉnh xác suất | Platt/sigmoid (mặc định), isotonic và không hiệu chỉnh cũng đã thử; 25% hàng gần nhất để hiệu chỉnh | `models/walkforward.py:39-101`, `models/calibration.py` |
| Chuyển tín hiệu | Cần `P(up)−P(down) ≥ 0,15` và xác suất phía chọn ≥ 0,40, nếu không là CHỜ | `models/signals.py:27-51` |
| Artefact | `models/{logistic,random_forest,xgboost,lightgbm}/1-20261008T070815/{metadata.json,model.joblib}` | thư mục `models/` |

**Kết quả ML [SỐ LIỆU, `docs/research/model-evaluation.md`]:**

| Mô hình | Log loss Dev (nền) | Log loss Val (nền) | Lệnh Dev/Val | PF Dev/Val |
|---|---|---|---|---|
| logistic | 1,0132 (1,0159) | 1,0235 (1,0170) | 418 / 264 | 1,14 / 0,81 |
| random forest | 1,0172 | 1,0231 | 563 / 281 | 0,99 / 0,89 |
| XGBoost | 1,0199 | 1,0218 | 539 / 317 | 0,95 / 0,84 |
| LightGBM | 1,0211 | 1,0220 | 561 / 295 | 1,02 / 0,86 |

Chỉ logistic hơn mức nền ở Dev (hơn 0,003), rồi thua ở Val. **Không mô hình nào thắng mức nền ngoài mẫu.** Dự án đã chạy kiểm tra "nhìn thấy edge" (cấy một edge nhân tạo thì qua cả 7 tiêu chí, thị trường thật không), nên kết quả âm đáng tin hơn là "pipeline hỏng".

**Giới hạn của phần ML [SỰ THẬT + Ý KIẾN]:** dữ liệu M15 chỉ từ 2025-05 (≈ 17 tháng, trong đó vàng tăng mạnh nên tỷ lệ các lớp lệch theo thời kỳ); chỉ đặc trưng kỹ thuật (không tin tức, không chéo tài sản, không order flow); không tinh chỉnh siêu tham số (cố ý, nhưng cũng nghĩa là chưa tìm cấu hình tốt nhất). *Điều này không chứng minh không tồn tại mô hình tốt hơn; chỉ cho thấy cấu hình đã đăng ký không thắng.*

**(b) Không phải ML: quy tắc, thống kê, heuristic**

| Thành phần | Bản chất | Nguồn |
|---|---|---|
| Regime (TREND_UP/DOWN, RANGE, HIGH/LOW_VOLATILITY, SHOCK) | Quy tắc: ADX ≥ 25, tỷ lệ ATR/median ATR 500 nến (1,5 và 0,67), "shock" khi biên độ ≥ 3× ATR trước | `structure/regime.py:86-125` |
| Cấu trúc thị trường (HH/HL/LH/LL, BOS, CHoCH, S/R) | Fractal swing trái/phải 3 nến, **không repaint** (swing chỉ hiện sau `right` nến) | `structure/swings.py:1-20` |
| Xu hướng H1, pullback M15, kích hoạt M5 | Quy tắc EMA20/EMA50 + cấu trúc; pullback = giá cách EMA nhanh trong [−0,3; +0,7] ATR; trigger = ROC và RSI vượt 52/48 cộng BOS hoặc thân nến mạnh | `trading/market_state.py:301-340` |
| Vòng đời setup | Máy trạng thái ARMED → TRIGGERED / EXPIRED / INVALIDATED, trigger trong ≤ 6 nến M5 | `trading/setup_machine.py:45-168` |
| Stop / Target | SL = max(cấu trúc + 0,1 ATR, 1,25 ATR), từ chối nếu > 3 ATR; TP1 = 2R, giới hạn bởi S/R đối diện, **phải đạt R:R ròng ≥ 1,5 sau spread** | `trading/levels.py:25-128` |
| Cỡ lệnh | Từ `tick_value`/`tick_size` của broker, làm tròn xuống theo bước lot, tính lại rủi ro thực sau làm tròn | `trading/sizing.py:57-88` |
| Bộ giới hạn | 1 vị thế, 2 lệnh/giờ, 6/ngày, cooldown 30′ sau thua, 4 giờ sau 3 thua liên tiếp, dừng lệnh mới ở lỗ ngày 2%, flatten ở 3,5% | `trading/governor.py:19-121` |

**(c) "Pattern similarity" (tìm mẫu giống trong lịch sử):** phương pháp **dựa trên ví dụ (instance-based, họ k-NN)**, không huấn luyện tham số. Mỗi nến thành vector 6 chiều chuẩn hóa theo ATR (`patterns/representation.py:25-53`), cửa sổ 30 nến M15, tìm k = 20 láng giềng gần nhất theo Euclid (cũng có cosine, Pearson, DTW, z-norm, MASS/matrix profile), **loại các ứng viên có cửa sổ kết quả chồng lên cửa sổ truy vấn** (ADR-0013, `patterns/search.py:28-92`). Xác suất = tần suất kết quả của các láng giềng, được dán nhãn rõ "uncalibrated frequencies" (`signals/engine.py:178`). **Nằm trong engine cũ `signals/engine.py`, đã đánh dấu DEPRECATED** (`signals/engine.py:1-14`).

**(d) ML có ảnh hưởng tín hiệu BUY/SELL/WAIT cuối cùng không?** **Không.**
- `trading/baseline.py` (đường PAPER live) **không import** bất kỳ gói ML nào; tôi kiểm tra bằng `grep`: ngoài `models/` và `evaluation/`, chỉ `research/service.py` nhắc tên mô hình để hiển thị.
- `api/service.py:249-253` chỉ **đọc metadata** của mô hình, "never loads the pickled models".
- Mức bằng chứng của quyết định live là `UNVALIDATED_BASELINE` (`trading/baseline.py:413`).

### B4. Kết quả: hệ thống có "đúng" không?

**Kết luận:** về **phương pháp** là đúng và rất nghiêm; về **lợi thế giao dịch** là chưa có bằng chứng, và nhiều dấu hiệu chống lại một edge lớn. *Mức tin cậy: CAO cho "chưa có edge trong phạm vi đã thử"; TRUNG BÌNH cho "không tồn tại edge nào".*

**Bảng kết quả đã đăng ký trước [SỐ LIỆU, các `final-verdict.md`, ledger, `batch-a-stage1-report.md`]:**

| Chương trình | K | Kết quả |
|---|---|---|
| Baseline A/B/C + 4 mô hình ML (Epic 8–12) | 7→10 | Tất cả trượt tiêu chí, kết quả đổi dấu giữa các giai đoạn |
| Edge Program V1 (H01–H06, 18 biến thể) | 21 | **(B) NO EDGE WITHIN BUDGET**; tốt nhất −0,066 R/lệnh (bi quan); chỉ 3/36 lần chạy dương và đều mẫu nhỏ |
| Edge Program V2 Batch A (H07–H10, 20 biến thể) | 20 | 0/20 sống sót Stage 1; net bi quan âm ở cả 20 |
| V3: F1 (dư thừa vàng-USD) | 1 | **FAIL**: n = 1.601, −0,354 R bi quan, 0/8 năm dương → họ đóng |
| V3: F3 (động lượng phiên Mỹ) | 1 | **FAIL**: n = 1.735, gross −0,010 R, chi phí ≈ −0,20 R lớn hơn mọi tín hiệu → họ đóng |
| Baseline MTF đang chạy (v1.1.0) | — | Replay 11 lệnh, thắng 18%, trung bình −0,41 R (**mẫu quá nhỏ để kết luận**); forward live 0 lệnh |

Tổng khoảng **44 biến thể đã khai báo, 0 sống sót**. Tiêu chí đạt gồm 7 điều kiện *đồng thời* (`evaluation/edge.py:21-28,107-156`): ≥ 100 lệnh, cận dưới khoảng tin cậy block-bootstrap theo ngày > 0 (α hiệu chỉnh theo K), PF ≥ 1,2, drawdown ≤ 15 R, ≥ 3/4 fold dương, vẫn dương sau khi bỏ 5% lệnh tốt nhất, không phụ thuộc quá 60% lợi nhuận vào một phiên hoặc regime.

**Điểm mạnh về phương pháp [SỰ THẬT]:**
1. Giả thuyết **đăng ký trước** (commit trước kết quả), Test-H và holdout 2026-05..10 **chưa bao giờ bị chạm**.
2. Chống rò rỉ ở mọi tầng: nến chỉ dùng khi đã đóng (`available_at`), swing không repaint, k-NN loại cửa sổ chồng lấp, walk-forward có embargo; có test cắt dữ liệu rồi so sánh kết quả.
3. Chi phí thật: spread theo từng nến, trượt giá, hoa hồng, **swap theo hướng** (`backtest/costs.py:19-53`; swap mua −76,05 điểm/lot/đêm, bán −4,2 — **rất bất đối xứng, ≈ 76 USD/lot/đêm cho vị thế mua**).
4. Chặn đa kiểm định: α = 0,05/K; có Monte Carlo prop-firm (P vi phạm FTMO 90 ngày; mức tối đa an toàn 0,35%/lệnh).
5. Kiểm tra pipeline "nhìn thấy edge" bằng edge cấy nhân tạo.

**Lỗ hổng và rủi ro còn lại [SỰ THẬT + Ý KIẾN]:**

| # | Vấn đề | Mức độ | Chi tiết |
|---|---|---|---|
| 1 | **Hai "bộ não" cùng tồn tại** | Cao | Engine mới `trading/` (live PAPER) và engine cũ `signals/engine.py` (DEPRECATED nhưng vẫn được `demo_trader.py` và route `/paper` import). Audit nội bộ ghi rõ 2 chỗ tính lot khác nhau (0,25% so với 0,5%) và entry BUY cộng spread hai lần ở nhánh adapter. Chưa phải lỗi trên đường live, nhưng là **nợ kỹ thuật gần nút gửi lệnh** |
| 2 | **Tần suất tín hiệu quá thấp để tự kiểm chứng** | Cao | Audit: 0,10–0,28 setup/ngày → 26–70 lệnh/năm → cần 3,7–10 năm forward để phát hiện +0,20 R. Tôi đo thêm: 1.204 quyết định 4 ngày, **100% CHỜ**; lý do hàng đầu: SPREAD_TOO_WIDE 515 (43%), VOLATILITY_TOO_LOW 359, NO_SETUP 254, NO_DIRECTION 150 |
| 3 | **Độ phủ forward 76,7% < cổng 95%** | Trung bình | UI hiển thị `PHỦ 76.7% / 95%`; theo thiết kế bằng chứng forward chưa hợp lệ |
| 4 | **Sai lệch thời kỳ chi phí** | Cao (cơ hội) | Xem B4.1 dưới đây |
| 5 | **Dữ liệu 2025–26 thiên về một chiều (xu hướng tăng mạnh)** | Trung bình | Chiến lược nghiêng mua dễ trông tốt vì beta; swap mua đắt bù một phần |
| 6 | **Ổ C: còn ~11–12 GB** | Trung bình (vận hành) | UI /trade cảnh báo `WARN`; collector ghi tick liên tục |
| 7 | **Quy mô mã** | Trung bình | ~44.700 dòng Python (`src`), 218 file test (~33.000 dòng), ~20.000 dòng TypeScript, 206 commit trong 12 ngày. Khó duy trì nếu chỉ một người; nhiều gói (`video_intel`, `forensics`, `decision_research`, `research_v2/v3`) ngoài đường lõi |

**B4.1. Phát hiện của tôi về chi phí theo thời kỳ [SỐ LIỆU, `evidence/cost_by_era.py.txt`]**

Chi phí khứ hồi theo ATR(H1) với sàn spread 30 điểm + trượt giá 3 điểm/lần khớp mà dự án dùng (0,36 USD):

| Năm | ATR H1 trung vị (USD) | Giá trung vị | Chi phí ÷ ATR |
|---|---|---|---|
| 2011 | 4,68 | 1.547 | 0,077 |
| 2015 | 3,48 | 1.167 | 0,103 |
| 2018 | 2,77 | 1.262 | **0,130** |
| 2022 | 4,48 | 1.805 | 0,080 |
| 2024 | 5,77 | 2.381 | 0,062 |
| 2025 | 9,96 | 3.345 | 0,036 |
| 2026 | 19,12 | 4.499 | **0,019** |

Giai đoạn Development-2 (2011–2018) của V1/V2/V3 có chi phí trên 1 đơn vị ATR **gấp khoảng 4–7 lần** môi trường 2025–26. Một tín hiệu nhỏ thật sự (ví dụ +0,10 R gộp) bị chi phí 2011–2018 nuốt sạch có thể sống được ở môi trường hiện tại. **Ngược lại**, khoảng thời gian 2025–26 ngắn (≈ 1,5 năm), dữ liệu M5 chỉ từ 2025-05, và là một xu hướng tăng rất mạnh. Hàm ý: **cần kiểm chứng riêng theo thời kỳ 2024–2026 với mô hình chi phí tick thật** (dự án đã có `research_v3/foundation/cost_model_v2.json` và tick từ 2021-10), và **luôn so với benchmark mua-và-giữ cùng thời gian vị thế**.

**Độ tin cậy cho mục B4:** CAO cho các con số trích từ ledger/báo cáo (tôi đối chiếu nhiều nguồn); TRUNG BÌNH cho các diễn giải.

### B5. Đối chiếu với `75.md` và các ảnh

`75.md` (Bài 57–75, bản chữ của các infographic "Ci") mô tả đúng một quy trình mà **baseline MTF của dự án đã hiện thực hóa gần như từng chữ**:

| Quy tắc trong 75.md / ảnh | Hiện thực trong dự án | Kết quả kiểm chứng |
|---|---|---|
| Xác định xu hướng lớn (H1/H4), EMA50 + HH/HL | `_h1_trend`: giá và EMA nhanh trên EMA50 và cấu trúc ≥ 0 (`market_state.py:301-308`); H4 chỉ có quyền chặn | Xu hướng EMA50 chỉ nghiêng nhẹ đúng hướng, không đạt ý nghĩa (ảnh, mục G: Δ +0,08 ATR, t = +1,5) |
| Chờ pullback về hỗ trợ/EMA (Bài 57) | `_pullback` ±0,3–0,7 ATR quanh EMA20 M15 (`market_state.py:319-327`) | Pullback + nến xác nhận **trùng ngẫu nhiên**: thắng 33,2% so với kỳ vọng 33,3% (ảnh, mục H, N = 5.338) |
| Xác nhận bằng nến/cấu trúc (Bài 72) | Trigger M5 (ROC/RSI/BOS/thân nến, `market_state.py:330-340`) và vòng đời setup | Xác nhận bằng phá đỉnh nâng tỷ lệ thắng bên mua, bên bán không đổi (ảnh, mục I); **V1-H04 (xu hướng ngày + hồi EMA) âm rõ nhất: −0,144 R** |
| "Không có setup thì không giao dịch" (Bài 73) | CHỜ là mặc định; 12 lý do từ chối | Đúng về quy trình; lọc theo đi ngang/giữa vùng **không cải thiện** kết quả |
| Rủi ro 1%, R:R ≥ 1:2, cỡ lệnh từ SL (Bài 74) | 0,25%/lệnh; R:R ròng ≥ 1,5 sau spread; `size_for_risk` từ `tick_value` | **Làm đúng và an toàn hơn** ảnh (ảnh nhầm "100 USD/lot", code dùng thông số broker) |
| RSI 70/30, MACD, Bollinger, quét thanh khoản (Bài 58, 63–67) | Chỉ là *đặc trưng* trong ML và `market_state`, không phải tín hiệu | Cực trị RSI/Bollinger có xu hướng đảo chiều 12 nến ở 2004–2018, yếu từ 2019, gần như mất từ 2025 (ảnh, mục J); MACD cắt, xếp chồng EMA, quét thanh khoản không có lợi thế |
| ATR dùng đặt SL và cỡ lot (Bài 66) | SL = max(cấu trúc, 1,25 ATR), tối đa 3 ATR; lot theo SL | **Đúng và đã kiểm chứng**: ATR đo biến động, không đo hướng |
| Backtest, ghi lệnh, demo trước live (Bài 69–70) | Có đầy đủ: backtest chi phí thật, journal, paper desk, khóa demo | Dự án vượt xa chuẩn của ảnh |

**Kết luận [Ý KIẾN CỦA TÔI]:** loạt bài "Ci" là một **quy trình kỷ luật** hợp lý, không phải nguồn lợi thế; dự án của bạn đã làm đúng phần quy trình **và đã kiểm tra thực nghiệm rằng quy trình đó, định nghĩa theo cách này, không sinh ra lợi thế vượt chi phí**. Điều đó nhất quán giữa ba nguồn độc lập: ledger của dự án, 5 phép thử trên ảnh của tôi, và log live 4 ngày.

---

## C. Bảng thành phần

| Thành phần | Loại | Thuật toán cụ thể | Ảnh hưởng tín hiệu live? | Bằng chứng |
|---|---|---|---|---|
| `market_data/` (MT5 collector, ledger, validators, broker clock) | Hạ tầng | Đọc MT5 chỉ-đọc, Parquet bất biến, 16 mã lỗi, đồng hồ NY+7 | Có (nguồn dữ liệu) | `README.md`, `docs/MT5_DATA_PLATFORM.md` |
| `features/` | Thống kê | EMA, ATR (Wilder), ADX, RSI, MACD, Bollinger, stochastic; đối chiếu TA-Lib | Có | README, test hồi quy |
| `structure/swings.py`, `regime.py` | Quy tắc | Fractal 3-3, BOS/CHoCH không repaint; ADX ≥ 25 + tỷ lệ ATR | Có | `swings.py:1-20`, `regime.py:86-125` |
| `trading/market_state.py`, `setup_machine.py` | Quy tắc | Xu hướng EMA20/50, pullback ±ATR, trigger ROC/RSI/BOS, máy trạng thái ARMED/TRIGGERED | **Có (lõi quyết định)** | `market_state.py:301-340`, `setup_machine.py:108-168` |
| `trading/baseline.py` | Quy tắc | Chuỗi H4→H1→M15→M5→M1, 12 lý do từ chối, nhãn UNVALIDATED | **Có (quyết định live)** | `baseline.py:278-440` |
| `trading/levels.py`, `sizing.py`, `governor.py` | Quản trị rủi ro | SL cấu trúc/ATR, TP 2R chặn bởi S/R, lot từ `tick_value`, giới hạn lệnh và lỗ ngày | Có | các file nêu trên |
| `trading/paper_desk.py`, `position_manager.py` | Mô phỏng | Khớp ở bid/ask, thoát SL/TP/hết giờ 120′/đóng cửa/kill-switch | Có (PAPER) | `docs/reports/PAPER_LIFECYCLE_ACCEPTANCE.md` |
| `patterns/` (+ `outcomes/`) | **Instance-based** | Cửa sổ 30 nến × 6 đặc trưng chuẩn ATR, k = 20, Euclid/DTW/MASS, loại chồng lấp | Không (engine cũ DEPRECATED) | `patterns/search.py`, `signals/engine.py:1-14` |
| `models/` | **ML được huấn luyện** | Logistic, RF, XGBoost, LightGBM; walk-forward tháng; Platt | **Không** (chỉ benchmark và hiển thị metadata) | `models/zoo.py`, `api/service.py:249-253` |
| `evaluation/` | Thống kê | 7 tiêu chí, block-bootstrap theo ngày, Holm-Bonferroni, Monte Carlo prop-firm | Không (nghiên cứu) | `evaluation/edge.py`, `prop_mc.py` |
| `backtest/` | Mô phỏng | Engine bid/ask, spread nến, trượt giá, swap theo hướng | Không | `backtest/costs.py`, `engine.py` |
| `signals/` | Quy tắc + k-NN | Cổng bằng chứng (ADR-0017/0021), 12 lý do từ chối, xác suất từ láng giềng | **Không** (DEPRECATED) nhưng còn importer | `signals/decision.py:132-246` |
| `brokers/mt5_demo/`, `funded/`, `execution/` | Hạ tầng thực thi (khóa) | Executor có một `order_send`, shadow `order_check`, whitelist, khóa luật FTMO D6, tầng 0–2 | Không (khóa) | `executor.py:348`, `config.py:37` |
| `api/`, `apps/dashboard/` | Giao diện | FastAPI chỉ-đọc, Next.js (/trade, /dữ liệu, /journal, /research) | Hiển thị | UI đã kiểm tra, mục D.6 |
| `news/` | Quy tắc | Lịch tin theo thời điểm; mặc định fail-closed (NEWS_UNKNOWN → CHỜ) | Có (chặn) | `README.md` |
| `video_intel/`, `forensics/`, `decision_research/`, `research_v2/`, `research_v3/` | Nghiên cứu phụ | Phụ trợ nghiên cứu | Không | **[SUY ĐOÁN]** đọc tên và README, chưa đọc từng file |

---

## D. Hướng xây dựng thực dụng (nếu tôi là chủ sở hữu)

### D.1. Nguyên tắc dẫn đường [Ý KIẾN CỦA TÔI]

1. **Bằng chứng trước, công cụ sau.** Sau ~44 giả thuyết thất bại, thêm chỉ báo/mô hình/đồ họa là cách tiêu tiền nhanh nhất. Điểm nghẽn không phải mô hình, mà là **tỷ lệ tín hiệu/chi phí/tần suất**.
2. **Sản phẩm có giá trị ngay cả khi không có edge.** Bàn kỷ luật + rủi ro + nhật ký là thứ chủ tài khoản dùng hằng ngày; thuật toán tìm edge là thí nghiệm có hạn mức.
3. **Không nhầm beta với alpha.** Vàng tăng 2,4 lần từ đầu 2024: mọi hệ thống nghiêng mua trông có lời. Chuẩn mực: so với mua-và-giữ cùng thời gian vị thế, và trừ swap mua (−76 điểm/lot/đêm).
4. **Giữ cổng an toàn nguyên vẹn.** Đừng sửa 3 thứ: khóa giao dịch thật, `order_send` duy nhất, quy tắc không chạm Test-H/holdout.

### D.2. Ba hướng và khuyến nghị

| Hướng | Mục tiêu | Ưu | Nhược | Khả thi |
|---|---|---|---|---|
| **(i) Bàn kỷ luật & rủi ro cho giao dịch thủ công** | Giúp một người giao dịch XAUUSD đúng quy trình: cảnh báo setup, cỡ lệnh từ SL, giới hạn lỗ ngày, nhật ký, đánh giá hậu kiểm | Gần xong (`/trade`, `/journal`, governor, `size_for_risk`, alerts); có giá trị độc lập với edge | Không tạo ra lợi nhuận; cần người dùng kỷ luật | **Cao** |
| **(ii) Tiếp tục tìm edge để chạy bot** | Tìm một cơ chế dương sau chi phí và đưa qua DEMO | Nếu thắng, giá trị cao nhất | ~44/44 giả thuyết đã thất bại; mỗi giả thuyết mới tốn "ngân sách K"; nguy cơ tự lừa (đa kiểm định) | **Thấp–trung bình** |
| **(iii) Đóng băng, chỉ giữ nền tảng dữ liệu** | Duy trì MT5 collector, tick, kiểm định; ngừng phát triển chiến lược | Chi phí thấp nhất, an toàn nhất | Bỏ dở giá trị đã xây | Cao |

**Khuyến nghị: (i) làm chính, (ii) làm giới hạn 60 ngày với cổng dừng, (iii) là phương án khi (ii) thất bại.** Lý do: (i) có kết quả chắc chắn; (ii) đáng thử một lần nữa nhưng **chỉ trong ngân sách đã khai báo**, và có thông tin mới (chi phí thời kỳ 2025–26 thấp hơn nhiều) thay đổi bài toán.

### D.3. Giữ / Cắt / Viết lại

| Hành động | Hạng mục | Lý do |
|---|---|---|
| **GIỮ nguyên** | `market_data/` + collector, `data/market` (M1 2004, tick 2021), validators | Tài sản lớn nhất, đã kiểm định |
| | `trading/` (state, baseline, levels, sizing, governor, paper_desk), `/trade`, `/journal`, `/research` | Đã hoạt động, trung thực, khóa an toàn |
| | Khung đánh giá (7 tiêu chí, ledger K, đăng ký trước, tập khóa) | Phần giá trị nhất về phương pháp |
| | Khóa giao dịch thật, một `order_send`, funded khóa | An toàn |
| **CẮT / ĐÓNG BĂNG** | `signals/engine.py` + `/paper` + `/legacy` | DEPRECATED, trang cũ lệch 98 giờ và tải chậm (14,7 giây), gây nhầm lẫn |
| | `control/` (web control), `funded/` | Đang tắt, rủi ro cao nếu mở khi chưa có edge |
| | Mở rộng thêm `models/`, `video_intel/`, `forensics/` | Không thay đổi quyết định; chỉ giữ để tái lập |
| **VIẾT LẠI / BỔ SUNG** | Gộp một nơi tính cỡ lệnh (`trading.sizing`) cho mọi đường | Xóa nguồn lệch 0,25%/0,5% |
| | Bộ lọc thời kỳ chi phí trong đánh giá (ATR-scaled, tick thật 2021→nay) | Giải bài toán B4.1 |
| | Journal hậu kiểm: chi phí theo R, swap, so với mua-và-giữ, tuân thủ quy tắc | Hướng (i) |
| | Dọn nợ: ổ C, ngưỡng cảnh báo đĩa, xoay vòng log | Vận hành |

### D.4. Hướng (i): bàn kỷ luật cho giao dịch thủ công, những gì còn thiếu

Dự án đã có phần khó. Phần thiếu, theo thứ tự giá trị:

1. **Danh sách kiểm tra trước lệnh** hiển thị cố định trong `/trade`, lấy từ 75.md: xu hướng lớn · vùng · xác nhận · R:R ròng ≥ 1,5 · lot theo SL · không vào khi tin lớn/spread rộng. Dự án đã có chuỗi này ở dạng trạng thái; cần cho **người dùng tự đánh dấu** khi giao dịch tay.
2. **Cảnh báo chi phí trung thực:** spread hiện tại theo ATR, **swap nếu giữ qua đêm** (mua −76 điểm/lot/đêm), cảnh báo khi đòn bẩy thực vượt ngưỡng (ảnh #076 cho thấy bảng lot thực tế nguy hiểm).
3. **Nhật ký hậu kiểm:** R thực, MFE/MAE, chi phí theo R, vi phạm quy tắc, so với mua-và-giữ. Hiện `/journal` đã có R/MFE/MAE; thêm 3 cột trên.
4. **Chế độ biến động:** hiển thị percentile ATR hiện tại và nhắc "ATR đo biến động, không đo hướng". Dữ liệu cho thấy ATR dự báo biên độ 24 nến sau tốt (cao gấp 1,28 lần nhóm thấp).
5. **Dừng thông minh:** khóa lệnh mới khi lỗ ngày chạm 2% (đã có), thêm khóa sau N lệnh vi phạm quy tắc.

**Không nên:** tự động hóa gửi lệnh, thêm "độ tự tin AI", thêm chỉ báo mới.

### D.5. Hướng (ii): chương trình tìm edge giới hạn 60 ngày, tối đa 5 giả thuyết

Điều kiện chung (đúng ADR-0030 của dự án): chốt trần K trước (ledger 24, `STATE.json` ghi 48, `registration.py` mặc định 24: audit nội bộ đã chỉ ra mâu thuẫn); mỗi giả thuyết ghi mô hình chi phí tick thật theo từng năm; mỗi giả thuyết một biến thể; fail thì **đóng họ, không tinh chỉnh**; Test-H và holdout chỉ chạm một lần.

| # | Giả thuyết | Logic kinh tế | Định nghĩa máy đọc được | Dữ liệu | Căn cứ hiện có | Xác suất sống (Ý KIẾN) |
|---|---|---|---|---|---|---|
| 1 | **Đảo chiều ngắn hạn ở cực trị Bollinger/RSI, giữ ≤ 12 nến H1, thoát theo thời gian có SL thảm họa** | Thanh khoản bị tiêu hóa, giá hồi về trung bình sau cú đẩy | BB(20,2) đóng ngoài dải **hoặc** RSI(14) cắt ngoài 30/70; vào ở nến kế; thoát sau 12 nến | H1/M5 + tick từ 2021 | Mua dưới dải dưới: dương sau spread ở Dev (+2,02 USD, z 9,4) và Val (+2,06, z 2,5), nhưng 2025+ chỉ z 0,5; bán trên dải trên: Val ≈ 0, 2025+ âm. (Báo cáo ảnh, mục J). **V1-H05 (fade bar xung lực) từng âm −0,14 R**, nên đây là hướng cần cẩn trọng | Thấp–trung bình |
| 2 | **Lọc theo chế độ biến động cao cho setup xu hướng-pullback** | Biên độ lớn hơn khiến chi phí cố định nhỏ, xu hướng tiếp diễn | Setup hiện có, chỉ giao dịch khi percentile ATR ≥ 67% | Có sẵn | Nhóm biến động cao: thắng 36,1% so với 33,3% (z +2,2), Dev z +2,1, Val z +0,8 (mục H); không vượt Bonferroni | Thấp |
| 3 | **Chiến lược xu hướng nhiều ngày có kiểm soát beta** | Vàng có động lượng dài hạn | EMA200 ngày + vào khi pullback; **so với mua-và-giữ cùng thời gian vị thế, trừ swap** | D1/H4 từ 2004 | Chưa thử (H06 Donchian H4 âm −0,43 R nhưng ít lệnh) | Thấp |
| 4 | **Mô hình dự báo BIÊN ĐỘ (không phải hướng) để chỉnh SL/lot và lọc "không giao dịch"** | Biến động tụ cụm, dự báo được hơn hướng | Hồi quy/quantile cho range 24 nến; chấm bằng log-likelihood/QLIKE, không bằng lợi nhuận | Có sẵn | ATR cao → biên độ 24 nến sau lớn hơn 1,28 lần (mục J). **Đây là ứng dụng ML thực dụng nhất**: giảm rủi ro, không cần edge hướng | Cao (cho mục tiêu rủi ro) |
| 5 | **Dữ liệu chéo/macro với lịch tin lịch sử thật** | Phản ứng với dữ liệu vĩ mô | V3-F2 đã đăng ký nhưng hoãn vì thiếu lịch tin | Cần nguồn lịch tin | V3 §F2 | Chưa biết (thiếu dữ liệu) |

**Cổng dừng (đặt trước, tính theo ngày lịch):**
- **Ngày 14:** trần K và mô hình chi phí tick đã chốt bằng văn bản; nếu chưa, dừng hướng (ii).
- **Ngày 30:** giả thuyết 1–3 chạy Stage 1 (Dev). Mỗi giả thuyết trượt = đóng.
- **Ngày 45:** giả thuyết sống sót chạy Validation; chỉ tiếp nếu **cả Dev lẫn Val dương** sau chi phí bi quan và vượt mua-và-giữ.
- **Ngày 60:** nếu không giả thuyết nào qua Validation, **kết luận "không tìm thấy edge khả thi" và chuyển sang (iii)**. Không gia hạn, không thêm biến thể.

**Tiêu chí thành công của hướng (ii):** ít nhất một biến thể có cận dưới khoảng tin cậy > 0 ở cả Dev và Val sau chi phí bi quan, ≥ 100 lệnh mỗi giai đoạn, vượt benchmark beta. Nếu đạt, bước kế là Test-H (một lần) rồi forward paper ≥ 3 tháng trước khi nghĩ đến DEMO.

### D.6. Tình trạng UI [SỐ LIỆU, kiểm tra bằng Playwright, 1440×900]

**Ghi chú phương pháp:** máy chủ **Playwright MCP không khởi chạy được trình duyệt** (`chrome-for-testing is not installed`; tôi đã cài trình duyệt theo hướng dẫn chính thức nhưng MCP vẫn không nhận, có thể cần khởi động lại máy chủ MCP). Tôi dùng **Playwright của chính dự án** (`@playwright/test` trong `apps/dashboard`) với Chromium cài kèm để tải trực tiếp các trang đang chạy trên `:3000`. Kết quả tương đương về mặt kiểm tra; ảnh trong `reports/ui/`.

| Trang | HTTP | Tải (ms) | Lỗi console | Nhận xét |
|---|---|---|---|---|
| `/trade` | 200 | 3.389 | 0 | Hero "CHỜ · KHÔNG VÀO LỆNH", nhãn `UNVALIDATED · PHỦ 76.7% / 95%`, banner "PAPER · không gửi lệnh thật", lý do chặn chính, dải MTF (H4 ĐI NGANG/CHẶN, H1 TRUNG TÍNH, M30, M15, M5, M1). Trang cao 2.132 px: khung "Execution" bị cắt ở màn hình 900 px, người dùng phải cuộn |
| `/market` (Dữ liệu) | 200 | 3.281 | 0 | Trạng thái MT5, collector, API, tick, độ mới từng khung. Cảnh báo ổ C còn 11,3 GB |
| `/journal` | 200 | 3.153 | 0 | **0 lệnh đóng**, đường R "cần ít nhất 2 lệnh" |
| `/research` | 200 | 3.701 | 0 | "(B) NO EDGE WITHIN BUDGET", K V1 21/21, V2 20/24, quyết định D-1..D-5 |
| `/control` | 200 | 3.213 | 3 phản hồi 503 | **Đúng thiết kế**: "CONTROL DISABLED", trang giải thích rõ vì sao. Nhưng 3 lỗi 503 hiện trong console mỗi lần mở, nên dọn |
| `/legacy` | 200 | **14.663** | 0 | "LEGACY / NOT ACTIVE", dữ liệu cũ 98 giờ, heartbeat dừng 5.879 phút. Chậm và gây nhầm; nên gỡ |

**Nhận định UI [Ý KIẾN CỦA TÔI]:** UI trung thực hiếm có: không có "Strong Buy", không có độ tin cậy giả, luôn hiện mức bằng chứng. Hai thứ cần sửa nhỏ: (1) `/control` sinh 503 khi tắt; (2) `/legacy` nên bị gỡ khỏi build. Không cần thêm trang.

### D.7. Lộ trình và việc cần làm tuần này

**Giai đoạn 0 (tuần 1), dọn nợ rẻ, rủi ro thấp:**
1. Giải phóng ổ C và đặt xoay vòng log/tick (cảnh báo `WARN` hiện hữu).
2. Chốt một con số K trong một file duy nhất (ledger), sửa `STATE.json` và `registration.py`.
3. Gỡ `/legacy` và `/paper` khỏi build; để `signals/engine.py` ở chế độ chỉ-đọc cho tới khi `demo_trader` không còn gọi.
4. Một hàm tính cỡ lệnh cho mọi đường.
5. Ngăn `/control` sinh 503 khi tắt (trả 204 hoặc không gọi API).

**Giai đoạn 1 (tuần 2–5), hướng (i):** danh sách kiểm tra trước lệnh, cảnh báo chi phí + swap, journal hậu kiểm (D.4). Tiêu chí hoàn thành: trong 2 tuần dùng thử, mọi lệnh (kể cả tay) đều có bản ghi đầy đủ và R thực.

**Giai đoạn 2 (tuần 2–9), hướng (ii) giới hạn:** các giả thuyết 1–5 theo cổng dừng D.5.

**Giai đoạn 3 (tuần 10–13), quyết định:** nếu (ii) có ứng viên qua Validation: Test-H một lần, forward paper; nếu không: chuyển (iii).

**Ước lượng công sức (tương đối):** G0 nhỏ; G1 vừa; G2 lớn; G3 nhỏ đến vừa.

**Rủi ro chính:** (a) mẫu forward quá nhỏ vẫn là điểm nghẽn bất kể giả thuyết nào; (b) nhầm beta với alpha trong 2025–26; (c) đa kiểm định (mỗi giả thuyết thêm làm tăng ngưỡng chứng minh); (d) kỷ luật của chính người giao dịch.

---

## E. Rủi ro, hạn chế của kiểm toán này và điều tôi không chắc

**Phạm vi thực tế của tôi.** Đã đọc **toàn bộ hoặc phần lớn** các file lõi: `signals/{engine,decision,evidence,strategy_registry}`, `models/{zoo,dataset,walkforward,signals}`, `trading/{baseline,market_state (nửa đầu),levels,sizing,governor,setup_machine,demo_lock,engine (260 dòng đầu)}`, `patterns/{representation,search (đầu)}`, `structure/{regime,swings (đầu)}`, `evaluation/edge.py`, `backtest/costs.py`, `outcomes/engine (đầu)`, cùng các báo cáo nghiên cứu và audit nội bộ. **Chưa đọc** phần lớn `paper_desk.py` (829 dòng), `baseline_v12.py`, `execution/`, `brokers/`, `funded/`, `control/`, `api/` ngoài các điểm đã kiểm tra, và các thành phần nghiên cứu phụ. Tổng cộng tôi đọc kỹ khoảng 5–6 nghìn dòng trên ~45 nghìn.

**Chưa chạy / chưa xác minh:**
- Chưa chạy lại ML hay backtest của dự án; số liệu ML và V1–V3 trích từ tài liệu và ledger của dự án (tôi đối chiếu chéo nhiều nguồn, nhưng không tái lập từng số).
- Test: tôi chạy `pytest tests/unit/trading` có giới hạn thời gian; **đến ≈ 29% bộ test, không có lỗi nào**, rồi hết thời gian. README ghi "1.030+ tests, 97% coverage"; tôi **không** xác minh con số này (đếm được 218 file test, ~33.000 dòng).
- `video_intel`, `forensics`, `decision_research`, `research_v2/v3` và các ghi chú trạng thái memory chỉ dựa vào tên và đọc nhanh [SUY ĐOÁN].
- Con số "ảnh" trong mục B5 lấy từ báo cáo kiểm chứng ảnh trước (các điều kiện và giới hạn ghi trong báo cáo đó).

**Giới hạn của các phép đo của tôi:** một cặp, một khung chính (H1), tham số mặc định; "chi phí ÷ ATR" dùng sàn spread 30 điểm + trượt giá 3 điểm của dự án (spread lịch sử trong dữ liệu H1 trước 2022 không đáng tin theo chính README); log quyết định chỉ 4 ngày (1.204 dòng).

**Việc tôi đã làm trên máy bạn:** cài trình duyệt Playwright (~120 MB, thư mục `%LOCALAPPDATA%\ms-playwright`) khi thử khởi động MCP. Không sửa mã dự án, không commit, không gửi lệnh, không chạm cấu hình.

**Điều tôi không chắc:**
1. Hiệu ứng "chi phí thời kỳ" (B4.1) có đủ lớn để biến một tín hiệu dương nhỏ thành khả thi hay không: cần thử nghiệm thật, tôi chỉ chỉ ra khả năng.
2. Có edge nào ở tần suất cao hơn H1 hay không: dự án có M1/tick nhưng chưa khai thác giả thuyết tần suất cao, vì mô hình chi phí tick chỉ vừa sẵn sàng.
3. Có nên ưu tiên (i) hay (ii) tùy mục tiêu thực của bạn (giao dịch thật hay nghiên cứu): đây là quyết định của bạn, không phải kỹ thuật.

**Phản biện chính mình.** Khuyến nghị "đóng băng chiến lược, làm bàn kỷ luật" có thể sai nếu bạn thật sự muốn một bot kiếm tiền: khi đó (ii) đáng được nhiều ngân sách hơn 60 ngày. Ngược lại, tôi có thể đã đánh giá thấp khả năng rằng chính dữ liệu 2025–26 (ATR gấp 7 lần 2018) mở ra cơ hội thật. Hai điều đó chỉ phân xử được bằng thí nghiệm đăng ký trước, đúng như dự án đã làm.

---

### Phụ lục: bằng chứng và cách tái lập

| Mục | File |
|---|---|
| Ảnh chụp UI 1440×900 | `reports/ui/{trade,market,journal,research,control,legacy}-1440.png` |
| Kết quả kiểm tra UI (HTTP, lỗi, văn bản) | `reports/evidence/ui_audit.json`, `ui_audit.cjs.txt` |
| Chi phí theo thời kỳ | `reports/evidence/cost_by_era.py.txt` |
| Thống kê log quyết định live (1.204 dòng) | `reports/evidence/decision_log_stats.py.txt` |
| Kiểm chứng ảnh giao dịch | `reports/IMAGE_CLAIMS_VERIFICATION_2026-10-12.md` |

Các script `.txt` đổi đuôi thành `.py`/`.cjs` để chạy; cần `.venv` của `xau-edge` (polars, numpy) hoặc `node` với `@playwright/test` của `apps/dashboard`.
