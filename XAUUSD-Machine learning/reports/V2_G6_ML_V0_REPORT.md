# V2 G6: ML V0 (dự báo biên độ H1 24 nến, vai trò A, không thẩm quyền)

> **KẾT CỤC (2026-10-13, chủ dự án):** Test-H **không mở**; **giữ nguyên tiêu chí đăng ký trước và LOẠI V0 tại Kiểm định**; họ K đóng (K không bị tiêu); registry **RETIRED**; CI hiệu chỉnh K được làm rõ là **cận dưới một phía 97,5%** (ADR-V2-007). Các mục 5 và 7 bên dưới là đề xuất trước quyết định và chỉ còn giá trị lịch sử. Tạm dừng ML; chuyển G8.

Ngày: 2026-10-13 · repo `xau-edge-v2` (local, chưa push) · V1 **không bị sửa**.

Quyết định đã áp dụng: G7 PASS · chấp nhận chưa có lệnh PAPER tự nhiên · auto PAPER mặc định BẬT (PAPER-only) · **ADR-V2-007 được duyệt, có làm rõ HAR/Ridge** · bước tiếp G6 · forward evidence chạy song song · **H-V2-01 vẫn khóa, không trộn vào G6** · không có lệnh broker · tiền thật KHÓA.

## 1. Kết luận ngắn

- **ML V0 đã được xây và chạy chính thức trên Phát triển + Kiểm định** (không chạm Test-H/Holdout). Mô hình mặc định ridge/HAR cải thiện MSE so với ATR14 một đặc trưng **9,6% trên Kiểm định 2019–2021** (8,6% trên Phát triển 2012–2018), cận dưới CI 95% **và** CI 97,5% hiệu chỉnh K đều > 0.
- **Nhưng một tiêu chí đăng ký trước KHÔNG đạt ở Kiểm định:** "cải thiện dương ≥ 75% số năm": 2/3 năm (2020 âm, −1,6%) = 67%. Theo đặc tả đã đóng băng, mô hình **chưa đủ điều kiện** để vào Test-H như một ứng viên thăng cấp. Tôi **không** đổi tiêu chí (xem mục 5).
- **LightGBM không hơn ridge** (CI của chênh lệch chứa 0 ở cả hai giai đoạn): ridge/HAR vẫn là mặc định.
- Trạng thái registry: **RESEARCH, authority NONE**. Dự báo **không hiển thị ở bất cứ đâu**. Test-H và Holdout **vẫn khóa** (bằng mã, mỗi cái một lần, cần tệp duyệt của chủ dự án + sổ cái K).

## 2. Đã xây (`src/xau_edge_v2/ml/`)

| Module | Nội dung |
|---|---|
| `features.py` | 13 đặc trưng và nhãn `rng24.v1` đúng đặc tả; ATR là **SMA của true range** (không phải Wilder như lõi quyết định); hàng bị loại tới khi đủ lookback (không nội suy); `live_row` (đường live chỉ giữ ~260 nến) phải bằng giá trị batch |
| `models.py` | `HarRidge` (NumPy, chuẩn hóa + ridge α=10, tung độ gốc không phạt; **bằng scikit-learn** trong test), 3 baseline (trung bình mở rộng, ATR14 một đặc trưng, bảng theo phân vị ATR 250 nến), LightGBM (tham số đóng băng, 1 luồng, seed 7) |
| `walkforward.py` | mở rộng theo năm, embargo 25 nến, ≥ 3.000 hàng huấn luyện, không xáo trộn; dải 80% từ **phần dư ngoài mẫu của cửa sổ hiệu chỉnh** (25% cuối của hàng huấn luyện, cách hàng khớp bằng embargo) |
| `metrics.py` | MSE log-biên độ (chính), QLIKE trên mức biên độ, độ phủ dải, kỹ năng so với tham chiếu, **bootstrap khối theo tháng** (2.000 lần, seed 7) ở 95% và 97,5% |
| `guard.py` | **khóa cửa sổ**: mã phát triển chỉ thấy nến có nhãn hoàn tất trước 2022-01-01; Test-H/Holdout cần tệp duyệt khớp băm đặc tả + họ K, sổ cái K không có lần nhìn trước; **lần nhìn được ghi vào sổ cái TRƯỚC khi đọc dữ liệu** (sập giữa chừng vẫn tính là lần chạy duy nhất) |
| `registry.py` | bản ghi đủ trường (mục 36), bắt đầu RESEARCH/NONE, thăng **từng bước** có bằng chứng (VALIDATED_OFFLINE cần một lần chạy Test-H có trong sổ cái và mọi tiêu chí đạt); **không bước nào cấp thẩm quyền** |
| `run.py` / `run_v0.py` | lần chạy chính thức, kết quả JSON đầy đủ + định danh (băm đặc tả, băm lược đồ đặc trưng, băm dữ liệu, git sha, phiên bản thư viện) |
| API/UI | `GET /api/v2/model` (trạng thái, khóa, tiêu chí, **không có trường dự báo**), `state.model` = RESEARCH, ngăn Mô hình hiển thị bảng tiêu chí và những gì KHÔNG đạt |

**Sửa đặc tả (đúng quy tắc sửa đổi):** `ml_v0_spec.json` **1.0.0 → 1.1.0**, chỉ đổi `k_accounting` (và `spec_version`, `amendment`); bản 1.0.0 và băm của nó được giữ nguyên; một test chứng minh mọi khóa khác **giống hệt** và băm 1.0.0 không đổi. Nội dung `k_accounting`: họ `K_V2_VOL_V0`, K = 2, ứng viên `har_ridge` và `lightgbm_regressor` (Ridge/HAR là **một** ứng viên: hồi quy ridge trên đặc trưng kiểu HAR; ba baseline là mốc, không tiêu K), Kiểm định là Class D và không tiêu K, thêm ứng viên cần ADR + họ mới **trước** khi thấy kết quả confirmatory. Sổ cái `docs/ml/k_ledger.json` đã ghi họ này gắn với băm đặc tả.

## 3. Kết quả chính thức (Phát triển + Kiểm định; `docs/ml/runs/v0_dev_validation_run.json`)

Dữ liệu: 103.996 nến H1 (2004-06-11 … 2021-12-31), 103.710 hàng dùng được; băm dữ liệu `f0bef61b…`, băm đặc tả `ede09f4d…`. Chạy lại lần hai cho **kết quả giống hệt từng bit** (trừ dấu thời gian).

| | Phát triển 2012–2018 (n = 42.744) | Kiểm định 2019–2021 (n = 18.196) |
|---|---|---|
| MSE: trung bình mở rộng / ATR14 1 đặc trưng / bảng phân vị ATR | 0,2223 / 0,1646 / 0,2140 | 0,2708 / 0,1725 / 0,2591 |
| MSE: **ridge/HAR** / LightGBM | **0,1504** / 0,1513 | **0,1559** / 0,1539 |
| Cải thiện so với ATR14: ridge / LightGBM | **+8,6%** / +8,0% | **+9,6%** / +10,8% |
| R² so với trung bình mở rộng (ridge) | 0,323 | 0,424 |
| QLIKE (ridge / ATR14) | 0,0780 / 0,0842 | 0,0819 / 0,0886 |
| CI 95% của (MSE_ATR14 − MSE_ridge), dương = ridge tốt hơn | [0,0100; 0,0182] | [0,0082; 0,0249] |
| CI 97,5% (hiệu chỉnh K = 2) | [0,0092; 0,0188] | [0,0067; 0,0258] |
| LightGBM so với ridge, CI 95% | [−0,0029; 0,0008] | [−0,0015; 0,0055] |
| Độ phủ dải 80% (ridge) | 82,8% | **76,9%** |
| Cải thiện theo năm (ridge) | 2012 +7,4% · 2013 +4,6% · 2014 +7,1% · 2015 +3,3% · 2016 +3,9% · 2017 +18,0% · 2018 +17,9% | 2019 +14,3% · **2020 −1,6%** · 2021 +15,1% |

Tiêu chí đăng ký trước (mỗi giai đoạn): ≥ 5% ✓/✓ · CI 95% > 0 ✓/✓ · CI hiệu chỉnh K > 0 ✓/✓ · độ phủ 75–85% ✓/✓ (Kiểm định sát cận dưới) · dương ≥ 75% số năm **✓ (7/7) / ✗ (2/3)**.

## 4. Kiểm tra chất lượng

| Kiểm tra | Kết quả |
|---|---|
| `ruff`, `mypy --strict` (44 file nguồn) | sạch |
| `pytest` | tất cả đạt (xem số ở ledger): thêm 25 test ML + 3 test đóng băng |
| Không rò rỉ | đặc trưng tại t không đổi khi cắt/đổi nến tương lai; nhãn chỉ nhìn t+1..t+24 (đổi nến t+25 hay đỉnh của chính nến t không đổi nhãn); walk-forward: nhãn huấn luyện cuối cùng kết thúc trước đặc trưng kiểm tra đầu tiên; **phá hủy mọi nhãn từ năm kiểm tra trở đi không đổi dự báo** |
| Parity live | `live_row` (chỉ 260 nến cuối) bằng hàng batch tại nhiều điểm cắt (tiêu chí (v) của đặc tả đạt ở mức mã) |
| Khóa | không có tệp duyệt / sai băm / sai họ / chưa ký / họ chưa có trong sổ cái ⇒ từ chối; mở lần hai ⇒ từ chối; lần nhìn được ghi trước khi đọc; `load_h1` mặc định không trả nến ≥ 2022-01-01 dù kho có |
| Registry | chặn bước nhảy, chặn VALIDATED_OFFLINE khi chưa có lần chạy Test-H trong sổ cái hoặc tiêu chí chưa đạt, authority luôn NONE |
| Trình duyệt | 33 test Playwright + axe (4 mới cho ngăn Mô hình); không có chữ "tự tin/xác suất/biên độ kỳ vọng" trên trang |

Một lỗi **sản xuất** được phát hiện và sửa nhờ test dao động: ổ cắm lấy "mốc đầu" của sự kiện `paper` **sau** khi tính vân tay quyết định (chậm), nên một lệnh mở đúng lúc kết nối có thể không bao giờ được báo. Đã đưa các mốc đầu lên trước.

## 5. Điều cần bạn quyết định (và khuyến nghị)

**Test-H có nên mở không?** Theo đặc tả, `RESEARCH → VALIDATED_OFFLINE` cần *cả* Kiểm định *và* Test-H đạt đủ tiêu chí. Ở Kiểm định tiêu chí "≥ 75% số năm" không đạt (2/3: 2020 là năm bùng nổ biến động, ridge −1,6%).

- **Khuyến nghị: chưa mở Test-H.** Test-H chỉ chạy một lần; mở nó cho một mô hình đã không đạt tiêu chí đăng ký trước là đốt cửa sổ khi kết quả tốt nhất cũng không đủ để thăng cấp.
- Nếu muốn tiếp tục, có hai đường, và tôi nêu rõ rủi ro: (a) **giữ nguyên tiêu chí** và coi V0 là *thất bại ở Kiểm định* (sạch nhất về thống kê; mô hình vẫn là RESEARCH có giá trị mô tả); (b) **sửa tiêu chí (iv)** bằng một `spec_version` mới có lý do được duyệt, ví dụ tính trên *mọi* năm walk-forward (9/10 năm dương = 90%). Đây là **sửa sau khi đã thấy kết quả** (bậc tự do của người nghiên cứu): chỉ chấp nhận được nếu bạn ghi rõ vào hồ sơ; số 9/10 trong báo cáo này là mô tả sau-hậu-nghiệm, **không phải một lần đạt**.
- Tôi **không** đề xuất bất kỳ thay đổi nào khác (đặc trưng, nhãn, siêu tham số, thêm ứng viên): K = 2 chỉ đúng nếu danh sách ứng viên không đổi.

## 6. Giới hạn (nói thẳng)

- **Kiểm định 2019–2021 đã bị đốt** (Class D) từ lát cắt thăm dò G0 và các lần đo trước: số trên đây là mô tả nhất quán với lát cắt đó (+10,7%/+9,6% khi đó, nay +8,6%/+9,6%), **không phải bằng chứng**. Chỉ Test-H (một lần) là bằng chứng; hiện **chưa có bằng chứng**.
- **Phiên bản CI hiệu chỉnh K = Bonferroni 97,5%** là cách *tôi* hiện thực hóa "K = 2" (ADR-007 không nêu mức cụ thể); cần bạn xác nhận khi quyết định Test-H.
- Độ phủ dải trôi từ 82,8% xuống 76,9% (sát cận 75%): dải 80% **sẽ bị ẩn** theo đặc tả nếu độ phủ ra ngoài 75–85%.
- RMSE log ≈ 0,39 (sai số lớn): giá trị là thông tin rủi ro/chi phí, không phải tín hiệu; **kinh tế học của dự báo biên độ với người giao dịch chưa đo**.
- **Chưa làm:** giám sát vận hành (trôi đặc trưng, giá trị thiếu, vi phạm biên, phân phối dự đoán, độ phủ, độ trễ; mất sức khỏe ⇒ fail-closed) vì chưa có dịch vụ suy luận; việc này là điều kiện của SHADOW, không phải của V0 này. Artifact ridge `docs/ml/artifacts/har_ridge_0.1.0.json` đã xuất (băm trong registry) nhưng **không được nạp ở đâu**.
- Sử dụng ML trong quyết định (SL/TP sanity, gợi ý đứng ngoài, cỡ lệnh) **không có** và bị cấm ở V0.
- H-V2-01 và mọi giả thuyết giao dịch **không** nằm trong G6.

## 7. Bước tiếp theo

Cần bạn: (1) chọn (a) hoặc (b) ở mục 5 (hoặc "tạm dừng ML"); (2) xác nhận cách hiểu K = 2 → CI 97,5%; (3) nếu mở Test-H sau này: tạo tệp duyệt `docs/ml/approvals/test_h_approval.json` (mẫu và điều kiện trong `ml/guard.py`); tôi sẽ không tự tạo. Forward evidence (sổ PAPER) vẫn chạy song song.
