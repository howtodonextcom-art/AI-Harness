# V2 · Giao thức nghiên cứu đa họ chiến lược (chưa chạy outcome)

Ngày: 2026-10-13 · Sổ giả thuyết: `xau-edge-v2/docs/research/hypothesis_ledger.json` (PROPOSED). Mã đủ điều kiện: `core/intelligence/families.py` (research only, test cấm import từ live). Không có kết quả giao dịch của họ nào đã được mở.

## 1. Ngân sách nghiên cứu
3 giả thuyết chính (HB1, HC1, HD1), **0 biến thể thăm dò**. Thêm một biến thể ⇒ K tăng và ngưỡng bootstrap tăng theo. Mọi hằng số là giá trị tiên nghiệm trong mã.

## 2. Cơ hội quan sát được (DEV' 2016–2018, M15, 70.466 nến; **đủ điều kiện ≠ lệnh**)
| Họ | Đủ điều kiện /1000 nến | n | Mua/Bán | Rủi ro trung vị (ATR) | p90 |
|---|---|---|---|---|---|
| B phá vỡ tiếp diễn | 20,66 | 1.456 | 745/711 | **2,82** | 4,05 |
| C đảo chiều sau quét | 16,80 | 1.184 | 583/601 | **2,67** | 3,89 |
| D tương tác biên (RANGE) | 18,95 | 1.335 | 682/653 | **0,81** | 1,34 |
So với V1 v1.1: 2 tín hiệu / 16.270 quyết định (0,12 / 1000 quyết định, đơn vị M5). Cơ hội **đủ điều kiện** ở các họ mới cao hơn nhiều bậc, nhưng chưa qua cổng chi phí, đối kháng, R:R, governor, cooldown; chồng lấn lẫn nhau chưa đo.

## 3. Đặc tả từng họ
| | B | C | D |
|---|---|---|---|
| Giả định thị trường | nén rồi mở rộng một chiều | quét thanh khoản thất bại + xác nhận cấu trúc | biên ổn định, bấc từ chối |
| Đủ điều kiện | đóng ngoài hộp 12 nến chặt (≤3 ATR, TB range ≤0,8 ATR), thân ≥0,5 range | quét 10 nến + CHoCH/BOS cùng hướng ≤6 nến | RANGE + bấc chạm biên 20 nến (≤0,25 ATR) |
| Vô hiệu | cạnh đối của hộp | cực trị nến quét | đỉnh/đáy bấc |
| Stop/target | **chưa chốt**: cần đặc tả hình học trước khi mở outcome (xem cảnh báo) | như B | stop theo vô hiệu (0,8 ATR); target chưa chốt |
| Chi phí | spread thực thi theo nến (`core/costs`), chi phí không rõ ≠ 0 | | |
| Chế độ hỏng chính | phá vỡ giả; rủi ro 2,8 ATR ⇒ cần target ≥4 ATR | 48% BOS mất mức | nhãn RANGE đổi mỗi ~5 nến |
| Cỡ mẫu cần | theo công thức `research/stats.py` (≈663 lệnh cho 0,20 R) | | |
**Cảnh báo hình học**: với rủi ro 2,7–2,8 ATR (B, C), R:R ròng 1,5 đòi hỏi mục tiêu >4 ATR; V1 đã cho thấy `rr_ok` qua 38,9%. Họ có thể "chết đói" vì hình học, không vì edge. Đặc tả stop/target phải được duyệt **trước** khi chạy outcome và không được chọn theo kết quả.

## 4. Thiết kế thử nghiệm
1. Chốt spec (băm sha256) cho 3 họ + kiểm soát khớp. Chủ dự án duyệt.
2. Stage A: tín hiệu trên DEV' (không outcome) bằng `cand_replay`-kiểu, một tiến trình liên tục, ≤4 worker ưu tiên thấp.
3. Ablation: (a) chỉ đủ điều kiện, (b) + cổng chi phí/đối kháng, (c) + governor; báo từng bước lượng cơ hội còn lại.
4. VALIDATION' **một lần** (24 tháng PASS, 2019-01..2020-12): so với kiểm soát khớp (ATR-percentile, phiên, khoảng cách tới biên), lợi nhuận ròng sau chi phí, bootstrap theo tháng 97,5% một phía.
5. Trạng thái cho phép: `SUPPORTED`, `REFUTED_HARM`, `INCONCLUSIVE` (kết quả hợp lệ; INCONCLUSIVE được kỳ vọng khi mẫu ít).
6. Test-H, Holdout, Confirm-C: chỉ sau phê duyệt riêng.

## 5. Điều đã làm / chưa làm
Đã làm: mã đủ điều kiện, test nhân quả, tần suất DEV', sổ giả thuyết. **Chưa làm (cần phê duyệt)**: chốt spec, Stage A, outcome. Trạng thái các họ: `NOT_TESTED`.
