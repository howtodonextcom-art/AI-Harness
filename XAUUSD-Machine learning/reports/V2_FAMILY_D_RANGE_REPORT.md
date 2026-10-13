# V2 · Family D (tương tác biên RANGE): tính bền RANGE, nhân quả của biên, khả năng tạo lệnh

Dữ liệu: DEV' 2005-11..2018-12, M15 sạch. **Không outcome.** Nhãn SAU nến tín hiệu chỉ dùng để mô tả độ bền của nhãn trong báo cáo này, không bao giờ đi vào tín hiệu. Không chọn D vì kỳ vọng lợi nhuận.

## 1. Tính bền của RANGE
- Tỉ lệ nến mang nhãn RANGE: **46.2%**.
- 8,335 đoạn RANGE liên tiếp: độ dài p25 / trung vị / p75 = **3.0 / 11.0 / 25.0 nến**.
- 47.7% số đoạn dài ≥12 nến; 26.6% ≥24 nến; nhưng 64.5% số nến RANGE nằm trong các đoạn ≥24 nến (nhãn bền tập trung ở ít đoạn dài).
- Tuổi của đoạn RANGE tại nến tín hiệu D (p10/p50/p90): **2.0 / 14.0 / 43.0 nến**: một phần đáng kể tín hiệu D xảy ra khi nhãn RANGE còn rất non.
- Nhãn RANGE còn nguyên sau tín hiệu: **64.1%** (6 nến), **45.4%** (12 nến), **22.3%** (24 nến).

## 2. Nhân quả và độ ổn định của mức biên
- Biên = đỉnh/đáy của **20 nến TRƯỚC** nến tín hiệu (nhân quả theo cấu tạo; test cắt lịch sử `tests/unit/test_multifamily.py::test_the_contract_is_causal` và `test_families_are_causal_*`).
- Độ rộng biên (ATR) p10/p50/p90: **2.778 / 3.824 / 5.303**.
- Biên còn NGUYÊN SAU 6 nến chỉ **4.9%**: biên cuốn chiếu 20 nến trượt liên tục; không phải mức giá cố định. Đây là hạn chế của định nghĩa hiện tại, không sửa sau khi xem số.
- Số lần chạm cạnh biên (trong 0,25 ATR) trong 20 nến trước: p10/p50/p90 = 1.0 / 2.0 / 4.0.

## 3. Khả năng hình thành lệnh hợp lệ
- Episode D: 4,047; có lệnh hợp lệ (qua mọi cổng) **40.2%**.
- Cổng đầu tiên chặn: `{"ACCEPTED": 1626, "COST": 679, "CLEARANCE": 30, "TARGET": 1711, "STOP": 1}`.
- Stop luôn là sàn 1,25 ATR của CONTROL (biên rủi ro 0,8 ATR nhỏ hơn sàn); cổng TARGET (net R:R ≥ 1,5 với mức đối diện là biên đối diện) và COST (cost_R ≤ 0,15) chặn nhiều nhất.

## 4. Kết luận có kiểm soát
- D là họ duy nhất có đủ số tín hiệu không chồng trong DEV' để chạm cỡ mẫu 0,20R (xem báo cáo Stage A), nhưng **nhãn RANGE không bền** và biên trượt: luận điểm 'biên ổn định' chưa được dữ liệu ủng hộ. Bộ lọc độ bền (vd. tuổi RANGE tối thiểu) là biến thể mới (K+1) và **không** được thêm sau khi xem số liệu này.
- Trạng thái: **INCONCLUSIVE / NOT_TESTED** về edge; đây là kiểm tra khả thi và độ bền của nhãn, không phải kết quả giao dịch.
