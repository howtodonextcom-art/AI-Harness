# V1 vs V2: so sánh dựa trên bằng chứng (mốc G0)

Ngày: 2026-10-12 · **V1** = `xau-edge` HEAD `daf22f6` (đang chạy, **đã đo**). **V2** = **chưa tồn tại**; mọi ô V2 là **[DỰ KIẾN]**, lấy từ đặc tả của bạn và các báo cáo G0. Không ô V2 nào được hiểu là đã làm hoặc đã chứng minh tốt hơn (mục 100).

Loại khác biệt: **[THẬT SỰ]** = đổi hành vi/giá trị cho người dùng hoặc vận hành · **[BỀ MẶT]** = đổi tổ chức/giao diện mà kết quả gần như không đổi · **[CHƯA XÁC ĐỊNH]** = phụ thuộc phép đo chưa làm.

## A. Câu trả lời ngắn

1. **Tính năng:** khác thật ở *biểu đồ lịch sử sâu* (V1 chỉ cho xem 400 nến vì frontend khóa cứng, dù dữ liệu có từ 2004) và ở *bảng sức khỏe tín hiệu + vòng đời 0–6*. Phần còn lại (một trang thay nhiều trang) chủ yếu là **bề mặt/tổ chức**, giá trị thật là giảm nợ vận hành.
2. **Bộ não:** khác thật ở *một Decision Governor duy nhất* (bỏ hai bộ não và ba hàm cỡ lệnh). Logic quy tắc đa khung của V1 **gần như được giữ**: V2 không tạo ra "bộ não thông minh hơn" chỉ nhờ viết lại.
3. **Machine learning:** V1 **có ML thật nhưng không có thẩm quyền**; V2 dự kiến có ML **vận hành** (registry, suy luận, shadow, health) nhưng **cũng không có thẩm quyền ban đầu**. Khác biệt thật là *hạ tầng và kỷ luật*, **không phải lợi thế dự báo hướng**. Tác vụ V0 (dự báo biên độ) chỉ cải thiện ~10% MSE so với ATR14 (Class D).
4. **Học tập và áp dụng 75.md/báo cáo ảnh:** V1 **đã hiện thực hóa gần như nguyên văn** quy trình trong 75.md (xu hướng → pullback → xác nhận → R:R → lot), và các kiểm chứng cho thấy **quy trình đó không tạo lợi thế đo được**. V2 dự kiến giữ nó như **quy trình kỷ luật** (PROCESS RULE), không như alpha. Đây là khác biệt về **cách đối xử với tri thức**, không phải về kết quả giao dịch.
5. **Khác biệt thật sự lớn nhất:** (i) lịch sử biểu đồ theo nhu cầu, (ii) một nguồn quyết định, một nguồn cỡ lệnh, một sổ K, (iii) hạ tầng ML có phiên bản, (iv) loại bỏ ~31% mã nghiên cứu và ~20% mã khóa khỏi đường chạy. **Khác biệt bề mặt:** số trang, màu sắc, đổi framework. **Chưa có bằng chứng** rằng V2 nhanh hơn, ổn định hơn, hay có lợi thế giao dịch.

## B. Bảng so sánh chính

| Trục | V1 (có nguồn/đo) | V2 [DỰ KIẾN] | Loại khác biệt | Lý do |
|---|---|---|---|---|
| T1 Mục đích | Nền tảng nghiên cứu và hỗ trợ quyết định, PAPER; README + BRIEF | Bàn đọc thị trường liên tục + cấp phép giao dịch chọn lọc + kỷ luật rủi ro (đặc tả §6) | **BỀ MẶT** | cùng sứ mệnh, đổi cách nhấn mạnh |
| T2a Số trang | 5 mục nav, 17 file `page.tsx` (`/trade /market /journal /research /control /legacy`) | Một route `/` + ngăn kéo (§7) | **THẬT SỰ (vận hành) / BỀ MẶT (người dùng)** | giảm nợ (`/legacy` 14,7 s, `/control` 503) nhưng chỉ `/trade` giúp ra quyết định (audit V1) |
| T2b Lịch sử biểu đồ | **400 nến cố định** (≈ 6,7 giờ M1, 4,2 ngày M15, 16,7 ngày H1); 0 request `before`; poll toàn cửa sổ mỗi 3 s; dữ liệu có từ 2004 (M1 7,07 triệu nến) | Khoảng/`before` + backfill lười + WebSocket delta (§114–118) | **THẬT SỰ** | khả năng mới cho người dùng; backend V1 đã có `before` |
| T2c Checklist trước lệnh / tự đánh dấu | Chuỗi trạng thái tự động, không để người dùng tự đánh dấu khi giao dịch tay | Có (hướng (i)) | **THẬT SỰ (nhỏ)** | chưa đo giá trị thực dụng |
| T2d Chi phí/swap hiển thị | Spread hiển thị; swap có trong `backtest/costs.py` nhưng không là cảnh báo trên bàn | Cảnh báo swap và chi phí theo kỷ nguyên | **THẬT SỰ (nhỏ)** | swap mua −76 điểm/lot/đêm |
| T2e Journal | Có, 0 lệnh đóng | Thêm chi phí/R, bất đồng rule/ML, benchmark beta, vi phạm quy tắc | **CHƯA XÁC ĐỊNH** | giá trị phụ thuộc có dữ liệu lệnh |
| T2f Bảng sức khỏe tín hiệu | Có `decision_coverage` 76,7% và lý do chặn; không có mức "bias/watch/near-miss" theo ngày | Có đủ (§43–44) | **THẬT SỰ (vừa)** | giúp nhìn thấy "gần tới đâu" khi 100% là CHỜ |
| T3a Số bộ não | **2** (`trading/` live; `signals/` DEPRECATED còn ≥ 9 importer, 26 file test) | **1** Decision Governor | **THẬT SỰ** | xóa nguồn lệch và nợ |
| T3b Logic quy tắc | Chuỗi H4 chặn → H1 hướng → M15 setup → M5 trigger → M1 chặn (`trading/baseline.py`), v1.1.0, UNVALIDATED | Vòng đời xác định 0–6 + Governor; quy tắc an toàn ML không ghi đè | **BỀ MẶT / CHƯA XÁC ĐỊNH** | V1 đã có vòng đời v1.2 (opt-in); V2 chưa chứng minh nhiều tín hiệu/độ chính xác hơn; tần suất tín hiệu ≠ edge (§45) |
| T3c Cỡ lệnh | **3 hàm** (`risk/sizing.py`, `trading/risk_calc.py`, `trading/sizing.py`) | **1** hàm | **THẬT SỰ (an toàn)** | xóa nguy cơ lệch 0,25%/0,5% |
| T4 ML | Có ML thật: logistic/RF/XGBoost/LightGBM, walk-forward, Platt, 4 artefact; **không thẩm quyền**; huấn luyện M15 từ 2025-05 | ML vận hành (registry, suy luận, shadow, health); V0 = dự báo biên độ H1; không thẩm quyền; huấn luyện trên H1 từ 2004 | **THẬT SỰ (hạ tầng) / CHƯA XÁC ĐỊNH (giá trị)** | lát cắt: +~10% MSE so với ATR14, LightGBM ≈ ridge |
| T5 Học tập và áp dụng | 75.md được hiện thực hóa trong baseline; ảnh được kiểm chứng ngoài hệ thống (báo cáo) | Phân loại tri thức (PROCESS RULE/DESCRIPTIVE FEATURE/TESTABLE/REJECTED/UNVERIFIED), cổng "formalize → preregister → test → benchmark → multiple-testing → Validation" | **THẬT SỰ (kỷ luật)** | xem bảng §D; không đổi kết quả giao dịch |
| T6 Dữ liệu và rò rỉ | Parquet bất biến, nến chỉ khi đóng, swing không repaint, k-NN loại chồng lấn, embargo; kiểm test | Giữ; thêm feature contract, parity replay/live | **BỀ MẶT / THẬT SỰ (nhỏ)** | V1 đã mạnh; V2 chuẩn hóa và đo parity |
| T7 An toàn thực thi | Một `order_send` (`executor.py:348`); khóa DEMO/funded; governor | Không có đường gửi lệnh (chỉ PAPER, `ExecutionPort` không cài) | **THẬT SỰ (loại bỏ bề mặt tấn công)** | V1 an toàn nhưng giữ ~8,9k dòng mã khóa |
| T8 Kiểm chứng thống kê | Đăng ký trước, K=44, 7 tiêu chí, Test-H/holdout chưa chạm; **K có mâu thuẫn giữa file** (audit nội bộ: 24 vs 48) | Một sổ K; khóa Test-H/holdout bằng mã; so benchmark beta; chi phí theo kỷ nguyên | **THẬT SỰ** | sửa lỗ hổng đã biết; **không** tạo edge |
| T9a Quy mô mã | Python 44.729 dòng (runtime ~21,8k; khóa ~8,9k; nghiên cứu ~14,0k); TS runtime 13,5k + e2e 5,1k | Nhỏ hơn đáng kể (chưa số) | **CHƯA XÁC ĐỊNH** | chỉ đo được sau khi viết |
| T9b Nợ kỹ thuật | 2 não, 3 hàm cỡ lệnh, trang legacy/control, K lệch | Loại bỏ theo thiết kế | **THẬT SỰ** | cần test chứng minh (Y1–Y10) |
| T10a Hiệu năng V1 | API p95: decision 63,5 ms, bars 23–37 ms; load 332 ms; FCP 324; LCP 776; JS 291 KB nén; 80 req/phút; ~1,4 MB/phút | Mục tiêu: **không tệ hơn V1** (cổng G2) | **CHƯA XÁC ĐỊNH** | V1 đã đạt ngưỡng của đặc tả; "nhanh hơn" chưa có cơ sở |
| T10b Ổn định | Tiến trình: 5 Python + 1 Node, ~620 MB (collector 397 MB); chưa soak | Ít tiến trình hơn, soak ≥ 8 giờ | **CHƯA XÁC ĐỊNH** | chỉ khẳng định sau G8 |
| T10c Hiệu suất giao dịch | Không có edge; 0 lệnh forward; 0/~44 giả thuyết sống sót | **Chưa có**; không hứa | **KHÔNG KHÁC (hiện tại)** | V2 không thay đổi bản chất thị trường |

## C. Bảng riêng T4: Machine learning

| Mục | V1 (đã xác minh) | V2 [DỰ KIẾN] |
|---|---|---|
| Có ML được huấn luyện? | **Có**: logistic, RF, XGBoost, LightGBM (`models/zoo.py:25-124`) | Có: ridge/HAR mặc định + LightGBM challenger |
| Bài toán | Hướng 3 lớp (DOWN/NEUTRAL/UP) sau 20 nến M15 | **Biên độ H1 24 nến** (log-range); hướng là tác vụ phụ nghiên cứu |
| Dữ liệu huấn luyện | M15 từ 2025-05 (~17 tháng) | H1 từ 2004; Dev ≤ 2018, Val 2019–2021, Test-H khóa |
| Đặc trưng | 54 cột kỹ thuật | ~13 cột có hợp đồng đặc trưng |
| Chống rò rỉ | Walk-forward theo tháng, embargo, Platt | Giữ + 8 loại test bắt buộc + parity replay/live |
| Kết quả | **Không mô hình nào thắng mức nền ngoài mẫu** (log loss Val 1,022–1,024 so với 1,017) | Class D: ~+10% MSE so với ATR14 (CI loại trừ 0); LightGBM ≈ ridge |
| Artefact | `model.joblib` + metadata cơ bản | Registry đầy đủ (feature_schema_hash, label_version, cửa sổ, git SHA, dataset hash, trạng thái) |
| Chạy trong live? | **Không**; API chỉ đọc metadata | Suy luận trong tiến trình, **chế độ SHADOW**, không thẩm quyền |
| Ảnh hưởng BUY/SELL? | **Không** | **Không** ở V0; thẩm quyền chỉ qua thang RESEARCH → … → PAPER_ACTIVE |
| Học trực tuyến | Không | **Cấm** |

→ **Khác biệt thật là hạ tầng + kỷ luật + bài toán chọn có bằng chứng**, không phải "ML thông minh hơn quyết định".

## D. Bảng riêng T5: tri thức từ `75.md` và báo cáo ảnh đi vào hệ thống thế nào

Phân loại theo mục 25 của đặc tả. "Kiểm chứng" lấy từ `IMAGE_CLAIMS_VERIFICATION` (lưu ý: các phép thử đó chạy trên toàn lịch sử, **gồm Test-H và holdout, nên là Class D**).

| Khẳng định (nguồn) | Kiểm chứng đã có | V1 hiện thực? | Phân loại → V2 dự kiến |
|---|---|---|---|
| Rủi ro 1–2%, đặt SL, R:R ≥ 1:2, cỡ lệnh từ SL (Bài 74, ảnh rủi ro) | Toán đúng; "backtest 50–100 lệnh là đủ" **sai** (±10–14 điểm % sai số) | Có (0,25%, net R:R ≥ 1,5, `tick_value`) | **PROCESS RULE** → giữ, hàm duy nhất |
| ATR đo biến động, đặt SL/lot (Bài 66) | Đúng: ATR cao ⇒ biên độ 24 nến lớn 1,28× | Một phần (SL từ ATR) | **DESCRIPTIVE FEATURE** → đặc trưng + tác vụ ML V0 |
| Xu hướng: giá/EMA50 + HH/HL (Bài 75) | Nghiêng nhẹ đúng hướng, không đạt ý nghĩa (+0,08 ATR, t ≈ 1,5); V1-H04 −0,144 R | Có (`_h1_trend`) | **TESTABLE, yếu** → mô tả thiên hướng, không alpha |
| Pullback + xác nhận nến (Bài 57, 71–74) | Trùng ngẫu nhiên (thắng 33,2% so với 33,3%, N = 5.338) | Có (vòng đời setup) | **TESTABLE, không được ủng hộ** → vòng đời kỷ luật, nhãn UNVALIDATED |
| "Không có setup thì không giao dịch" (Bài 73) | Lọc đi ngang/giữa vùng không cải thiện kết quả | Có (WAIT mặc định) | **PROCESS RULE** → giữ như kỷ luật |
| RSI 70/30 là Sell/Buy (Bài 63–64) | Đảo chiều 12 nến mạnh ở 2004–2018, yếu 2019+, mất 2025+ (**Class D, đã nhìn Test-H**) | Chỉ là đặc trưng | **REJECTED làm luật tự động**; ứng viên nghiên cứu chỉ với dữ liệu forward |
| MACD cắt = tín hiệu (Bài 65) | Không lợi thế; đảo chiều ở 12 nến | Chỉ đặc trưng | **REJECTED** |
| Bollinger squeeze → biến động lớn (Bài 67) | Sai khi đo biên độ thô (1,718% so với 1,746%) | Không | **REJECTED** |
| Chạm dải Bollinger → đảo chiều (Bài 67) | Bền ở bên mua, bị trộn beta, Class D | Không | **UNVERIFIED / ứng viên nghiên cứu** |
| Xếp chồng EMA 20/50/100/200 (Bài 62); EMA cắt (ảnh 036) | Không lợi thế | Đặc trưng | **REJECTED làm tín hiệu** |
| Quét thanh khoản / SMC: FVG, OB, BOS, CHoCH (Bài 58, loạt ICT) | Quét thanh khoản: không ổn định (val ≈ 0); phần còn lại chưa hình thức hóa | BOS/CHoCH có trong `structure/` | **UNVERIFIED** → cần định nghĩa máy đọc được trước khi thử |
| Fibonacci (ảnh 001, 068) | Không được ủng hộ (z từ −2,9 đến −4,9 ở mức nông) | Không | **REJECTED** |
| Mẫu nến (14 loại) | Không có lợi thế theo hướng khẳng định | Chỉ cờ mô tả | **REJECTED** |
| Đỉnh đôi/đáy đôi | Không lợi thế (607 lệnh, thắng 58% so với 60%) | Không | **REJECTED** |
| Nhiều indicator ≠ tốt hơn; overfitting (Bài 68) | Đúng về nguyên lý, minh họa ngay trong kiểm chứng | — | **PROCESS RULE** → **không bỏ phiếu chỉ báo** (§41) |
| Bảng lot 1 lot/10k (ảnh 076) | **Nguy hiểm**: đòn bẩy ~41,7× | Không | **REJECTED** |
| Ranking chất lượng setup bằng vị trí trong biên độ + phân vị ATR + giờ (khám phá mới của tôi) | AUC 0,66/0,67 (Dev/Val), qua các kiểm soát; **Class D** | Không | **TESTABLE → `H-V2-01`**, đăng ký trước, Test-H một lần |

## E. Xếp hạng khác biệt theo tác động lên người dùng

| Hạng | Khác biệt | Loại | Cơ sở |
|---|---|---|---|
| 1 | Lịch sử biểu đồ theo nhu cầu (kéo trái xem nhiều ngày/năm) | **THẬT SỰ** | V1 chỉ 400 nến, nguyên nhân đã truy vết |
| 2 | Một bộ não, một hàm cỡ lệnh, một sổ K | **THẬT SỰ (an toàn/đúng đắn)** | 2 não, 3 hàm, K lệch trong V1 |
| 3 | Bảng sức khỏe tín hiệu và vòng đời 0–6 | **THẬT SỰ (vừa)** | 100% CHỜ trong 1.204 quyết định |
| 4 | Hạ tầng ML có phiên bản + shadow + health | **THẬT SỰ (hạ tầng)** | V1 có ML nhưng không dùng; giá trị chưa đo |
| 5 | Dự báo biên độ trên bàn | **CHƯA XÁC ĐỊNH** | ~+10% MSE (Class D), giá trị kinh tế chưa đo |
| 6 | Bỏ ~20% mã (khóa + engine cũ, 8,9k dòng) khỏi đường chạy; ít tiến trình | **THẬT SỰ (vận hành)** | 8.897/44.729 dòng; 5 Python + 1 Node |
| 7 | Một trang thay nhiều trang | **BỀ MẶT cho người dùng** | chỉ `/trade` giúp ra quyết định |
| 8 | Đổi framework (Next → Vite), đổi màu, thêm card | **BỀ MẶT** | không đổi quyết định |
| — | Hiệu suất giao dịch | **KHÔNG KHÁC** | không edge ở cả hai |

## F. Điều kiện để các khác biệt dự kiến thành THẬT, và rủi ro của việc xây lại

| Khác biệt dự kiến | Bằng chứng cần có |
|---|---|
| Lịch sử sâu không nhảy/không trùng | Test Playwright: kéo trái N lần, `data-bars` tăng, 0 timestamp trùng, độ nhảy ≈ 0, FPS ≥ 55 |
| Một bộ não/một hàm cỡ lệnh | Test: không còn import `signals`; một hàm; so khớp golden với V1 |
| Bảng sức khỏe tín hiệu | Test trạng thái 14 loại; so với log quyết định V1 |
| ML vận hành | Test rò rỉ 8 loại; parity replay/live; registry; shadow ghi bất đồng |
| Ít tiến trình, nhẹ hơn | Đo G2/G8 so với số V1 ở `V2_PERFORMANCE_BASELINE.md` |
| Ổn định | Soak ≥ 8 giờ, mất kết nối MT5, hồi phục dữ liệu cũ |

**Ít nhất 3 lý do việc xây lại có thể KHÔNG tạo khác biệt thật:**
1. **Điểm nghẽn là thiếu lợi thế thống kê, không phải phần mềm.** ~44 giả thuyết đều thất bại; viết lại giao diện/kiến trúc không đổi điều đó.
2. **V1 đã nhanh và đạt ngưỡng hiệu năng** (tải 332 ms, quyết định p95 63,5 ms); "nhanh hơn" gần như không thể là khác biệt có thể cảm nhận.
3. **Nhiều lợi ích có thể đạt bằng sửa V1 (O1):** thêm `before`/backfill vào frontend, gỡ `/legacy`, gộp hàm cỡ lệnh, sửa K: các việc nhỏ hơn nhiều so với viết lại ~35k dòng. Viết lại chỉ đáng khi giá trị nằm ở thiết kế một-nguồn-sự-thật và ML vận hành.
4. Rủi ro hồi quy: V1 đã qua nhiều vòng QA bằng trình duyệt; viết lại làm mất các sửa lỗi ẩn nếu test hành vi không được chuyển sang đủ.

## G. Điều tôi không chắc

- Giá trị thực của dự báo biên độ trên quyết định của người dùng (cần PAPER/journal).
- Ước lượng ~35k dòng viết lại là suy ra từ quy mô V1 (runtime ~21,8k Python + 13,5k TS), chưa phải ước lượng công sức.
- Lát cắt ML chỉ H1, Class D; hiệu năng ở 2022–2026 (chế độ biến động khác) chưa biết.
- Nhiều hàng "CHƯA XÁC ĐỊNH" chỉ thành "THẬT/BỀ MẶT" sau G2, G5, G8.
