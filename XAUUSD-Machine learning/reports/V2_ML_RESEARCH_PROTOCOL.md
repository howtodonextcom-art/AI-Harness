# V2 ML RESEARCH PROTOCOL (G0: chọn tác vụ ML V0)

Ngày: 2026-10-12 · Trạng thái: **đề xuất G0, chờ bạn duyệt** · Nguồn: lát cắt ML do tôi chạy hôm nay (`reports/evidence/g0/ml_*`).

## 0. Sự thật nền (mục 4)

V1 **có ML thật** (logistic, RF, XGBoost, LightGBM; walk-forward; Platt) và 4 artefact đã lưu, **nhưng ML không có thẩm quyền trong đường quyết định PAPER live**. ML của V1 huấn luyện trên **M15 từ 2025-05** (≈ 17 tháng) cho bài toán 3 lớp hướng 5 giờ; không mô hình nào thắng mức nền. V2 phải có **hệ thống ML vận hành thật** (mục 16) nhưng **thẩm quyền ML phải kiếm được** (mục 17).

## 1. Quy tắc ô nhiễm dữ liệu (đọc trước khi tin bất kỳ số nào ở đây)

Các cửa sổ bảo vệ của V1: **Test-H 2022-01-01..2025-04-30** và **Holdout 2026-05-01..2026-10-07**; Dev-2 (2011–2018) và Val-2 (2019–2021) đã "burned" (Class D khi đo lại).

- **Lát cắt ML của G0 chỉ dùng dữ liệu đến 2021-12-31** (script cắt cứng `< 2022-01-01`); Test-H và holdout **chưa bị chạm bởi lát cắt này**.
- Mọi số ở đây trên Dev/Val là **Class D: mô tả để chọn tác vụ, không phải bằng chứng**, không tiêu K. Bằng chứng thật chỉ đến từ lần chạy chính thức ở G6 theo đặc tả đóng băng.
- **Công khai:** các phép thử trên ảnh giao dịch (`IMAGE_CLAIMS_VERIFICATION`) trước đây của tôi **đã dùng toàn bộ lịch sử gồm cả Test-H và holdout.** Chúng không sạch. Mọi giả thuyết sinh từ đó (đảo chiều Bollinger/RSI) phải coi là **đã bị nhìn thấy trên Test-H**; chỉ dữ liệu forward mới sạch cho chúng.

## 2. Bảy tác vụ ứng viên (mục 18) chấm theo 10 tiêu chí (mục 20)

Thang 1–5, **cao hơn = tốt hơn** (riêng "nhiễm" và "chi phí tính toán": 5 = sạch/rẻ). Mười tiêu chí do đặc tả (mục 20) quy định trước; **điểm số do tôi chấm sau khi đã có kết quả lát cắt, nên là nhận định, không phải phép đo** (điểm có thể bị ảnh hưởng bởi kết quả đã thấy, nhất là ở cột D).

| Tiêu chí | A Biên độ/biến động | B Xác suất hướng | C Hoàn tất setup | D Chạm mục tiêu trước dừng lỗ | E MFE/MAE | F Trượt giá/thực thi | G Đứng ngoài |
|---|---|---|---|---|---|---|---|
| 1 Chất lượng nhãn nhân quả | 5 | 4 | 3 | 3 | 4 | 2 | 2 |
| 2 Cỡ mẫu | 5 | 5 | 2 | 3 | 3 | 1 | 3 |
| 3 Tính dừng | 3 | 2 | 3 | 3 | 3 | 2 | 3 |
| 4 Đặc trưng có sẵn khi chạy live | 5 | 5 | 5 | 4 | 4 | 4 | 5 |
| 5 Giá trị kinh tế | 4 | 3 | 3 | 5 | 4 | 3 | 4 |
| 6 Khả năng hiệu chỉnh | 4 | 3 | 3 | 4 | 3 | 2 | 3 |
| 7 Ổn định theo chế độ | 4 | 2 | 3 | 3 | 3 | 2 | 3 |
| 8 Giá trị rủi ro | 5 | 3 | 3 | 4 | 4 | 3 | 4 |
| 9 Nhiễm nghiên cứu (5 = sạch) | 5 | 3 | 3 | 2 | 4 | 5 | 3 |
| 10 Chi phí tính toán (5 = rẻ) | 5 | 4 | 5 | 5 | 5 | 3 | 5 |
| **Tổng /50** | **45** | 34 | 33 | 36 | 37 | 27 | 35 |

Ghi chú chấm điểm: B bị trừ ở tính dừng/chế độ vì bằng chứng lịch sử cho thấy đặc trưng kỹ thuật không cho lợi thế hướng ổn định (V1: 4 mô hình thua mức nền); C có ít sự kiện (26–70 lệnh/năm theo audit V1); D có nhãn phụ thuộc hình học SL/TP và đuôi thời gian (tôi đã kiểm, mục 4); F không có dữ liệu khớp lệnh thật (chỉ PAPER); G khó định nghĩa "đáng lẽ nên đứng ngoài" một cách nhân quả.

**Chọn tác vụ chính V0 = A: dự báo biên độ/biến động tương lai** (45/50). Các tác vụ khác **chỉ là nghiên cứu phụ**, đặc biệt D (xem mục 4).

## 3. Lát cắt Task A: biên độ 24 nến H1 tới

**Nhãn:** `y = ln( (max High[t+1..t+24] − min Low[t+1..t+24]) / Close[t] )`. **Đặc trưng (tại đóng nến t):** log ATR14/giá, ATR50/giá, ATR200/giá, log biên độ 24 và 5 nến, log độ lệch chuẩn lợi suất 24 nến, |lợi suất| 1 và 5 nến, log độ rộng Bollinger, giờ và thứ (sin/cos). **Walk-forward theo năm**: huấn luyện chỉ trên hàng có chỉ số `≤ đầu năm kiểm tra − 24 − 1` (embargo = đuôi nhãn). Siêu tham số cố định *a priori*, không tinh chỉnh.

| | Dev 2015–2018 (n = 24.496) | Val 2019–2021 (n = 18.196) |
|---|---|---|
| MSE: trung bình mở rộng (B0) | 0,2100 | 0,2708 |
| MSE: ATR14 một đặc trưng (B1, "baseline ATR") | 0,1491 | 0,1725 |
| MSE: HAR/ridge nhiều đặc trưng (B2) | **0,1332** | 0,1559 |
| MSE: LightGBM (M) | 0,1333 | **0,1541** |
| R² so với B0: B1 / B2 / M | 0,290 / 0,366 / 0,366 | 0,363 / 0,424 / 0,431 |
| Cải thiện MSE so với ATR14: B2 / M | **+10,7%** / +10,6% | +9,6% / **+10,7%** |
| CI 95% (block-bootstrap theo tháng) của (MSE_ATR14 − MSE_M); dương = M tốt hơn | 0,0159 [0,0099; 0,0218] | 0,0185 [0,0101; 0,0270] |
| Tương tự cho B2 | 0,0159 [0,0111; 0,0208] | 0,0166 [0,0082; 0,0249] |
| **LightGBM so với ridge** | −0,00003 [−0,0030; 0,0024] | 0,0019 [−0,0016; 0,0053] |

**Đọc kết quả [Ý KIẾN, Class D]:**
1. **Có thông tin mới ngoài ATR14**: cải thiện MSE ≈ 10%, khoảng tin cậy loại trừ 0 ở cả Dev lẫn Val. Phần cải thiện chủ yếu đến từ việc kết hợp nhiều thang thời gian của biến động và mùa vụ trong ngày.
2. **ML cây (LightGBM) không hơn mô hình tuyến tính (ridge/HAR)**: CI của chênh lệch chứa 0 ở cả hai giai đoạn. Theo mục 21, mô hình V0 mặc định là **ridge/HAR**; LightGBM chỉ là challenger và chỉ được thăng nếu thắng ridge với CI > 0.
3. Quy mô: RMSE log ≈ 0,36–0,39 (sai số khoảng ±45% trên biên độ). **Dự báo biên độ chỉ vừa phải**; giá trị là thông tin rủi ro/chi phí, không phải tín hiệu hướng.
4. Rủi ro dịch chuyển chế độ: biên độ H1 giai đoạn 2025–26 lớn hơn 2018 gần 7 lần theo USD; đặc trưng chuẩn hóa theo giá giúp, nhưng **chỉ lần chạy Test-H (một lần) mới kiểm chứng điều này.**

## 4. Task B/D (xếp hạng chất lượng setup): kết quả bất ngờ, bị ghi nhận và **chưa chọn**

**Thiết lập:** setup xu hướng EMA50 + chạm EMA50 + nến pin/engulfing (như báo cáo ảnh mục H–I), nhãn "đạt +2R trước −1R", SL dưới/trên cực 5 nến. Mô hình: logistic (C = 0,1) và LightGBM, walk-forward theo năm; sự kiện huấn luyện phải **đã kết thúc** trước năm kiểm tra (embargo theo thời điểm kết thúc từng lệnh). Không có chi phí.

| | Dev 2015–2018 (n = 1.159) | Val 2019–2021 (n = 783) |
|---|---|---|
| Log loss: mức nền / logistic / LightGBM | 0,635 / 0,604 / 0,597 | 0,648 / 0,601 / 0,601 |
| AUC: logistic / LightGBM | **0,660** / 0,645 | **0,674** / 0,633 |
| Tỷ lệ thắng nhóm 20% điểm cao nhất / thấp nhất | 55,2% / 19,0% | 58,6% / 15,9% |

**Kiểm soát đã chạy để loại giải thích tầm thường** (đầy đủ ở `ml_B_*.py.txt`):

| Kiểm soát | Kết quả |
|---|---|
| Nhãn bị hoán vị (null) | AUC 0,53 và 0,47 (≈ ngẫu nhiên): không có rò rỉ trong khâu khớp mô hình |
| Chỉ dùng "hướng" (long/short) | AUC 0,49: không phải thiên lệch hướng/beta đơn thuần |
| Chỉ dùng r/ATR (hình học SL) | AUC 0,48 và 0,47: **không phải** nghệ thuật của nhãn/hình học |
| Giãn mẫu ≥ 24 nến giữa các sự kiện | AUC 0,671 và 0,673 (không đổi) |
| Đuôi 72 nến (có thoát theo thời gian) thay vì 2.000 | AUC 0,664 và 0,667 (không đổi) |

**Đặc trưng đơn lẻ mạnh nhất (AUC Dev/Val):** vị trí trong biên độ 50 nến hướng theo lệnh **0,377 / 0,373** (setup thắng nhiều hơn khi giá đang ở sâu trong nhịp hồi, tức mua gần đáy biên độ/bán gần đỉnh); phân vị ATR **0,600 / 0,575** (biến động cao hơn tốt hơn); cos(giờ) **0,589 / 0,599**; thân nến tín hiệu theo hướng 0,551 / 0,541.

**Vì sao KHÔNG chọn cho V0 dù kết quả hấp dẫn:**
1. **Class D**: tôi đã *nhìn* kết quả trên Dev/Val, và cả bộ định nghĩa setup đã bị phân tích ở nhiều báo cáo trước. Nó **không có giá trị bằng chứng** cho tới khi đăng ký trước và chạy Test-H **một lần**.
2. **Mâu thuẫn bề mặt**: setup không phân biệt có E[R] ≈ 0 (báo cáo ảnh mục H), nên nhóm tốt nhất phải đạt E[R] lớn (+0,5–0,8 R nếu tin số trên) để cân bằng nhóm tệ nhất (−0,4 đến −0,5 R). Một lợi thế lớn như vậy mà 44 giả thuyết đã đăng ký chưa tìm ra đáng nghi ngờ, và dễ là kết quả của sự chọn lọc đặc trưng/chọn setup (tôi đã chọn định nghĩa setup nhiều lần).
3. Sự kiện **tập trung theo thời gian** (cụm xu hướng) khiến độ không chắc thật lớn hơn CI ngây thơ (giãn mẫu giúp nhưng chưa phải suy luận chuẩn).
4. **Chưa có chi phí**, chưa so benchmark beta, chưa qua mô hình chi phí theo kỷ nguyên.

**Hành động:** ghi D là **giả thuyết nghiên cứu ưu tiên cao nhất cho V2** (`H-V2-01`, "xếp hạng chất lượng setup bằng vị trí trong biên độ + phân vị ATR + giờ"), đăng ký trước **trước khi** nhìn Test-H, tiêu K của sổ cái duy nhất, và **chỉ thăng cấp nếu qua Test-H một lần**. Nó không ảnh hưởng V0.

## 5. Đặc tả V0 (đóng băng sau khi bạn duyệt)

| Mục | Quyết định |
|---|---|
| Vai trò ML (mục 75) | **ROLE A**: ML chỉ cung cấp thông tin biên độ/rủi ro; không gợi ý hướng |
| Nhãn | `ln(range_24H1 / Close)`; version `rng24.v1` |
| Mô hình mặc định | Ridge/HAR (chuẩn hóa, alpha cố định). Challenger: LightGBM (200 cây, 8 lá, lr 0,05, seed 7) |
| Baseline bắt buộc (mục 77) | Trung bình mở rộng; ATR14 một đặc trưng; quy tắc trạng thái hiện hành (ATR percentile) |
| Hiển thị | Biên độ kỳ vọng 24 giờ (USD) và dải 80% rút từ phân vị phần dư của cửa sổ hiệu chỉnh. **Không hiển thị phần trăm "tự tin"** (mục 78) |
| Hiệu chỉnh | Độ phủ dải 80% phải trong 75–85% trên Val và Test-H; nếu không, ẩn dải |
| Ứng dụng (V0, chỉ thông tin) | (1) SL/TP có hợp lý so với biên độ kỳ vọng; (2) cổng "biên độ kỳ vọng so với chi phí quá thấp" gợi ý đứng ngoài; (3) bối cảnh cỡ lệnh. **Chưa có thẩm quyền hủy/cho phép giao dịch** |
| Đánh giá ML (mục 74) | MSE log-biên độ, QLIKE trên biên độ, độ phủ dải; **không dùng PnL để chọn mô hình** |
| Chia dữ liệu | TRAIN ≤ 2018 · VALIDATION 2019–2021 · CALIBRATION: 25% gần nhất của phần huấn luyện mỗi fold (trước embargo) · **TEST-H 2022-01-01..2025-04-30 khóa bằng mã, chạy đúng một lần** · HOLDOUT khóa |
| Walk-forward | Mở rộng, theo năm hoặc quý; embargo = đuôi nhãn (24) + 1 |
| Tiêu chí thăng `RESEARCH → VALIDATED_OFFLINE` (đăng ký trước) | (i) cải thiện MSE so với ATR14 ≥ 5% **với cận dưới CI 95% > 0** trên Val; (ii) tương tự trên Test-H (một lần); (iii) độ phủ dải 75–85%; (iv) cải thiện dương ≥ 75% số năm; (v) parity replay/live đạt |
| LightGBM thay ridge | Chỉ khi CI của (MSE_ridge − MSE_LGBM) > 0 trên Val **và** Test-H (lát cắt cho thấy hiện nay chưa) |

## 6. Hợp đồng đặc trưng (mục 23) và bộ kiểm thử bắt buộc (mục 33)

Mỗi đặc trưng khai báo: `name, version, unit, source_timeframe, lookback, available_at, missing_rule, normalization, live_availability, rationale`. Đặc trưng **không tái tạo được live bị từ chối**. Ban đầu giữ ~13 đặc trưng thuộc 4 họ: biến động, động lượng ngắn, cấu trúc biên độ, thời gian (tránh "vườn đặc trưng", mục 24).

Kiểm thử tự động bắt buộc: bất biến tiền tố (cắt dữ liệu → cùng đặc trưng); chỉ dùng nến đã đóng; danh sách cột tương lai bị cấm; chuẩn hóa chỉ khớp trên train; ranh giới walk-forward; embargo đuôi nhãn; parity replay/live; mốc `available_at`.

## 7. Registry và trạng thái mô hình (mục 36–38)

Trường bắt buộc mỗi artefact: `model_id, version, algorithm, feature_schema_hash, label_version, train/validation/calibration window, git_sha, dataset_hash, metrics, calibration_metrics, status`. Trạng thái: `RESEARCH → VALIDATED_OFFLINE → SHADOW → PAPER_ELIGIBLE → PAPER_ACTIVE → RETIRED`; **không kích hoạt bằng cách thay file**. Giám sát: trôi đặc trưng, giá trị thiếu, vi phạm biên, phân phối dự đoán, độ phủ dải, độ trễ; mất sức khỏe ⇒ đầu ra ML = không khả dụng và Governor **fail-closed**. **Cấm tự học trực tuyến** (mục 82).

## 8. Sổ cái K (mục 72)

Một nguồn sự thật duy nhất (`ledger`) cho: K đã dùng, trần K, họ ứng viên, trạng thái. V1 đã khai báo ~44 biến thể (21 + 20 + 3). **Quyết định cần bạn:** V2 kế thừa K tổng = 44 cho α Test-H (α = 0,05 / K), hay mở sổ mới? Tôi đề xuất **kế thừa** (bảo thủ). Task A không tiêu K (đánh giá dự báo, không tuyên bố giao dịch); `H-V2-01` tiêu 1.

## 9. Điều tôi không chắc

- Lát cắt dùng một khung (H1), một cửa sổ biên độ (24 nến), một tập đặc trưng; chưa thử mục tiêu khác (ví dụ 12/48 nến) vì tránh nhìn quá nhiều cấu hình (đa kiểm định).
- Hiệu năng trên giai đoạn 2022–2026 (chế độ biến động rất khác) **chưa biết**.
- Giá trị *kinh tế* thực của dự báo biên độ cho người giao dịch (SL/lot/lọc) **chưa đo** (cần journal/PAPER); đây là giả thuyết sản phẩm, không phải kết quả.
- Kết quả Task B có thể là cấu trúc thật hoặc kết quả của chọn lọc; chỉ Test-H một lần mới phân xử.
