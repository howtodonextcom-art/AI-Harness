# V2 Candidate: triển khai, ablation trên Dev, và phát hiện lỗi dữ liệu làm KẾT QUẢ DEV VÔ HIỆU

Ngày: 2026-10-13 · Spec đóng băng `cand-v2-core 1.0.0` (sha256 `f9bb929e…`, commit `130277d`) · Chế độ PAPER only
**Kết luận ngắn: DỪNG TẠI CỔNG. Không chọn, không đóng băng candidate. Chưa mở Validation, Confirm-C, Test-H, Holdout.**

---
## 0. Điều quan trọng nhất
Ablation trên Dev cho CORE (C1+C2+C3a+C3b) **E = +0,68R/lệnh, thắng 57%** trên hình học 2R/1R, dương mọi năm. Quá đẹp, nên em kiểm tra dữ liệu trước khi tin. Kết quả:

1. Kho dữ liệu dùng chung có **lỗi nguồn cấp** từ **2012-06 đến 2021-01 (104 tháng)**, cộng 2004-06..2005-08, 2006-03, 2021-08: hệ số tự tương quan bậc 1 của lợi suất M5 là **−0,33** ở cả M1, M5, H1 (vàng thật ≈ 0 ± 0,05). Biến động cũng bị thổi phồng; `real_volume` khác 0 từ 2012-04 đến 2018-01 (một nguồn khác). Chuỗi như vậy làm mọi luật pullback/hồi quy trông có lãi mà không có cơ sở kinh tế.
2. Bằng chứng artefact: CORE **tháng sạch (trước 2012-06): N=28, E=+0,12R, thắng 39%**; **tháng lỗi: N=201, E=+0,76R, thắng 60%**. X_CORE_C7: −0,05R/33% so với +0,37R/47%.
3. Đối chứng (placebo): vào ngược chiều cùng thời điểm thắng 13%; trễ 24 giờ cùng chiều thắng 29%. Mô phỏng tái lập đúng (0,568/0,689 khi chạy lại), không có lỗi nhìn trước (độ trễ 1–240 phút làm giảm dần trơn, căn chỉnh thời gian H1/M5/M1 khớp 100%).
4. **Dev 2011–2018 có 79/96 tháng lỗi (82%); Validation 2019–2021 có 26/36 tháng lỗi (72%).** Kết quả Stage B và mọi số "Dev" từ 2012-06 trở đi **vô hiệu**, em không dùng để chọn gì.

Hệ quả cho báo cáo trước (Gate A): các số funnel cho Dev sau 2012-05 và Validation 2019–2020 nằm trên dữ liệu lỗi. Các số của cửa sổ hiện đại (2025-05..2026-04, sạch, đủ 12 tháng) **vẫn đứng vững**: ≈17 episode/năm của V1 control, cổng biến động percentile là nguyên nhân chính. Mục "spread gate chặn 92,7%" đúng cho 2011 (sạch, spread 60 điểm), nhưng con số 92,7% lấy trung bình trên cả giai đoạn lỗi nên **không dùng**.

---
## 1. Đã làm xong (và đã kiểm thử)
| Hạng mục | Trạng thái |
|---|---|
| ADR-V2-016 (CONTROL_V1_COMPAT và Candidate), ADR-V2-017 (K_V2_CAND_ML, công suất đã sửa), `GATE_A_REVISIONS.md` (thay đổi, 8 mâu thuẫn, cách giải quyết), `contamination_ledger.json` | xong |
| Spec đóng băng `docs/research/cand_v2_spec.json` + sha256 + test khóa (`test_cand_freeze.py`) | xong, commit trước mọi outcome |
| `core/candidate.py`: lớp mỏng GỌI `decide()` của control; C1, C2, C3a, C3b, C7 (exploratory); guard SHOCK và spike; 14 biến thể đóng | xong |
| Control không đổi (test khóa sha256 xanh); tất cả cờ tắt ⇒ giống control từng bit trên 1.500 trạng thái ngẫu nhiên | xong |
| `research/backtest.py` (luật fill PAPER, governor V1, episode→trade), `research/stats.py` (bootstrap theo tháng, 3 trạng thái, trần an toàn tuyệt đối) | xong |
| Công suất sửa lại + kiểm bằng Monte Carlo: 295 / 663 / 1.178 / 2.649 lệnh cho 0,30 / 0,20 / 0,15 / 0,10R (số cũ thiếu số hạng công suất) | xong |
| Kiểm thử: 60 test mới (tổng 1.872 xanh) (parity, từng thay đổi, guard, bất biến, đối xứng, tất định, vô hiệu hóa vòng đời, mô phỏng fill, governor, thống kê, đóng băng) | xanh |
| Stage A (tín hiệu 14 biến thể × 96 tháng) và Stage B (mô phỏng) trên Dev | chạy xong, **kết quả vô hiệu** |
| Tính toán: tối đa 4 worker ưu tiên thấp, CPU ≈ 35–50%, có checkpoint theo tháng; không chạm dịch vụ :8200, sổ PAPER, collector | tuân thủ |

---
## 2. Báo cáo tách biệt (trên Dev, DỮ LIỆU LỖI, chỉ để lưu vết, **không dùng để quyết định**)
Bảng đầy đủ: `reports/evidence/cand_stage_b/INVALID_dev_report_noisy_data.md`.

**Structural reachability / episode frequency / executed PAPER trades** (8 năm, 549.025 thanh M5, 4.069 setup ARMED của control):
| Biến thể | episode | /năm | lệnh thực thi | BUY/SELL |
|---|---|---|---|---|
| CTRL | 7 | 0,9 | 6 | 3/3 |
| A_C2 | 69 | 8,6 | 67 | 35/32 |
| CORE | 248 | 31,0 | 229 | 117/112 |
| X_CORE_C7 | 470 | 58,8 | 407 | 199/208 |

**Expectancy sau chi phí và độ bất định** (cận 97,5% một phía, bootstrap theo tháng): CORE E=+0,680R [+0,462; +0,912], N=229. **Trạng thái: INCONCLUSIVE** (N < 663 cần cho 0,20R) cho mọi biến thể. Hai biến thể có cận trên < 0 ở mức điểm (X_C7 −0,52R, N=17) vẫn INCONCLUSIVE vì N < 30.

**Vi phạm an toàn:** 0 vi phạm trên tín hiệu (net_rr ≥ 1,5, stop ≤ 3 ATR, rủi ro 0,25%, cost_R ≤ 0,15, không spike, không tín hiệu trong SHOCK); MDD CORE 10,2R, tháng tệ nhất −3,15R (trần 20R và −8R); X_CORE_C7 vượt trần (MDD 25,9R, tháng −10,2R). 3 lần mở cửa qua stop (gap) ở CORE được ghi, không chỉnh fill.

**Candidate versus control, INCONCLUSIVE:** control chỉ có 6 lệnh, nên không có kiểm định hiệu số; chỉ có phân tích lệnh tăng thêm (incremental), toàn INCONCLUSIVE.

**Quy tắc chọn đã preregister** cho ra "cả bốn thay đổi đều vào, candidate = CORE". **Em không công nhận kết quả này**: nó được áp trên dữ liệu lỗi và em không đóng băng candidate nào.

---
## 3. Vì sao em tin đó là artefact
- Đơn thuần: 28 lệnh sạch cho E=+0,12R và 39% thắng (gần hòa vốn cho 2R/1R), không phân biệt được với 0.
- Độ phủ theo giờ: 104/229 lệnh nằm ở 23:00–01:00 UTC (mở cửa Á), nơi nhiễu của nguồn lỗi lớn nhất.
- Lag-1 autocorr −0,33 đồng nhất ở mọi khung thời gian, bất khả với dữ liệu thật.
- Hệ quả khái quát: **bất kỳ kết quả nào trên 2012-06..2021-01 đều không đáng tin**, gồm cả nghiên cứu cũ của V1 (edge_program, baselines, H01…) và ML V0 (đã retired).

Dữ liệu sạch hiện có: 2005-09..2012-05 (không kể 2006-03), 2021-02..2026-10 (không kể 2021-08).

---
## 4. Đề xuất sửa (ADR-V2-018, **chờ chủ dự án duyệt**; cần spec 1.1.0 mới)
1. Luật hợp lệ theo tháng: |lag-1 autocorr M5| ≤ 0,10, chỉ dựa trên giá, áp đồng nhất cho mọi cửa sổ.
2. Chỉ đánh giá outcome trên tháng hợp lệ: **DEV'** = 2005-09..2012-05 (80 tháng, trừ 2006-03); **VALIDATION'** = 2021-02..2021-12 trừ 2021-08 (10 tháng); **CONFIRM_C** giữ nguyên; Test-H và Holdout vẫn khóa.
3. Chạy lại Stage A và B trên DEV' (cùng mã, cùng 14 biến thể, cùng quy tắc chọn). Ước tính: ~110–140 lệnh cho CORE nếu giữ tần suất của các tháng sạch ⇒ vẫn INCONCLUSIVE về expectancy; kết luận chủ yếu về độ với tới và an toàn.
4. Công khai trong ledger: Dev đã bị "đốt" cho outcome chiến lược; quyết định đổi cửa sổ được đưa ra **sau** khi thấy kết quả Dev (nhưng căn cứ là chất lượng dữ liệu, không phải hiệu suất).
5. Trước khi tin bất kỳ số nào từ kho dữ liệu: kiểm tra nguồn nhập (`xau-edge/data/research_history`, `raw`) cho giai đoạn 2012-06..2021-01 và sửa hoặc loại ở nguồn.

---
## 5. Quyết định cần chủ dự án
1. **Duyệt ADR-V2-018** (luật hợp lệ + DEV' + VALIDATION') và phát hành spec 1.1.0, hay chọn hướng khác (ví dụ chỉ dùng dữ liệu từ 2021-02 trở đi).
2. Có điều tra nguồn dữ liệu lỗi (V1 collector/nhập lịch sử) trước khi chạy tiếp không (em khuyến nghị: có).
3. Xác nhận: kết quả cũ của V1 và ML V0 trên giai đoạn lỗi bị coi là không đáng tin.

## 6. Giới hạn trung thực
Chưa có outcome hợp lệ nào cho candidate. Mẫu sạch rất nhỏ nên kể cả sau khi sửa, expectancy sẽ INCONCLUSIVE. Chiến lược vẫn UNVALIDATED, không có tuyên bố edge. Forward PAPER vẫn tích lũy; ở ≈17 episode/năm cần nhiều năm mới đủ 100 lệnh.
