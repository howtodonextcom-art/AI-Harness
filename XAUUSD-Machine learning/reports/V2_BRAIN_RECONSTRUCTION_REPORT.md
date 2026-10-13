# V2 · Báo cáo tái cấu trúc "bộ não" (Master Directive: phá trần trí tuệ V1)

Ngày: 2026-10-13 · Viết cho: chủ dự án. Mọi con số đo được có nguồn trong `reports/evidence/intel/` và `xau-edge-v2/docs/research/intel_descriptive_dev.json`.

## 0. Phân loại trung thực (không có "10/10", không có tuyên bố edge)
| Thành phần | Phân loại |
|---|---|
| Lớp quan sát thị trường (nến, cấu trúc, biến động, kịch bản, "cái gì đổi") nối vào runtime và UI | **MARKET_INTELLIGENCE_IMPROVEMENT** (mô tả, không dự đoán), kèm test |
| Tách lý do WAIT: thị trường / cổng an toàn / bộ giới hạn tài khoản | **OBSERVABILITY_IMPROVEMENT** + sửa lỗi hiển thị (hard gate che chuỗi) |
| Nhật ký chuyển trạng thái theo sự kiện (`decision_events`) | **DATA_CORRECTNESS_IMPROVEMENT** (sửa lỗi mất sự kiện giữa hai lần đóng M5) |
| Ba họ chiến lược B/C/D (điều kiện đủ điều kiện, không có kết quả) | **STRATEGY_HYPOTHESIS**, `NOT_TESTED` |
| Chiến lược live | Vẫn là baseline v1.1.0 (bất biến): `candidate_active=false` |
| Edge | **Không có** `VALIDATED_TRADING_EDGE`. Không có kết quả bảo vệ nào được mở |

## 1. Vì sao V2 vẫn hành xử như V1 (Q-cuối của chỉ thị)
Quyết định kiến trúc chịu trách nhiệm: **V2 bê nguyên `decide()` của V1 làm đường duy nhất từ dữ liệu tới hành động, và dùng đầu ra ba trạng thái BUY/SELL/WAIT làm toàn bộ "giao diện" của trí tuệ.** Mọi thứ thị trường đang làm mà chuỗi V1 không dùng (đảo chiều, nén, phá vỡ, quét thanh khoản, chuyển cấu trúc) bị thu về chữ "WAIT". Thay đổi cụ thể đã thực hiện: tách *mô tả thị trường* (không quyền) khỏi *ủy quyền chiến lược* (V1 v1.1.0, bất biến), và phơi bày chuỗi điều kiện đầy đủ. Quyết định giao dịch vẫn là V1; điều đã thay đổi là trader **thấy** thị trường và lý do chờ ở ba tầng.

## 2. Bằng chứng về trần V1 (đã có sẵn trong repo, em chỉ đối chiếu)
`xau-edge/docs/reports/SIGNAL_FUNNEL_ANALYSIS.md`: replay v1.1 trên 16.270 quyết định (3 cửa sổ đã đốt) cho **2 BUY, 16.268 WAIT**. Qua độc lập của từng cổng: m15_pullback 12,4%; m15_setup 11,6%; m5_trigger 21,3%; rr_ok 38,9%. V1 đã phát hiện pullback và trigger **tương quan âm** trên cùng một nến và thiết kế vòng đời ARMED→TRIGGERED (`baseline_v12.py`, `setup_machine.py`, pre-đăng ký `BASELINE_V1_2_PREREGISTRATION.md`); V1 v1.2 **không phải CONTROL** và V2 không chọn nó. Candidate C1 của V2 là cùng ý tưởng (6 M5 bar, planned stop cố định). Đây là tài sản bị bỏ rơi, không phải phát minh mới.

## 3. Giả định V1 dẫn tới trần (đã phân tích; chưa đổi quy tắc nào)
| Giả định | Bằng chứng | Hệ quả | Hành động trong chỉ thị này |
|---|---|---|---|
| H1 là nguồn hướng duy nhất | khi H1 NEUTRAL mọi thứ khác bị che (hard gate còn che cả điều đó) | không có kịch bản thay thế | **Không đổi** quy tắc. Thêm kịch bản độc lập (đảo chiều, nén-phá vỡ, biên) ở dạng mô tả |
| Pullback và trigger cùng một nến | tương quan âm (V1 funnel) | phễu 11,6% × 21,3% | Đã có sẵn v1.2/C1; chờ phê duyệt, không bật |
| Nhãn BOS/CHoCH như tín hiệu | **48,0%** BOS/CHoCH mất lại mức đã phá trong ≤3 nến (DEV' M15 và H1) | nhãn cấu trúc nhiễu; không dùng làm trigger đơn độc | Ghi vào hypothesis ledger (HC1 known_issue) |
| Nhãn chế độ ổn định | trung vị một chế độ chỉ kéo dài **5 nến**, ~87 lần đổi/1000 nến (M15 và H1) | nhãn RANGE/TREND không đủ bền để mang một luận điểm | Ghi vào HD1; bất kỳ bộ lọc bền = biến thể mới (K+1) |
| Hard gate đứng trước chuỗi | `decide()` trả lý do gate dù chuỗi đã fail trước | WAIT "vì spread" khi H1 không có hướng | **Sửa hiển thị** (không đổi quyết định): `ungated_decision` |

## 4. Năng lực thực thi mới (code chạy được)
- `core/intelligence/price_action.py`: 10 mô tả nến (bấc, nhấn chìm, trong/ngoài, displacement, quét thất bại), `known_at` = đóng nến.
- `core/intelligence/structure_events.py`: swing xác nhận/tạm thời, BOS/CHoCH, phá vỡ thất bại, độ trễ xác nhận 3 nến.
- `core/intelligence/volatility.py`: nén / bình thường / mở rộng, hộp nén và phá hộp.
- `core/intelligence/observe.py`: 5 kịch bản có mức xác nhận/vô hiệu, mức quan trọng, diff "cái gì vừa đổi".
- `core/intelligence/funnel.py`: lý do thị trường (chạy lại `decide()` với cổng tắt, **không đổi quyết định thật**), cổng, giới hạn tài khoản, 11 bước.
- `api/intelligence.py` + `GET /api/v2/intelligence`, bảng `decision_events`, UI (`SystemPanel`, ngăn "Thị trường").
- `core/intelligence/families.py`: B/C/D đủ điều kiện (research only, test cấm import từ live).

## 5. Trung thực về giới hạn
Nhãn biến động EXPANSION chiếm 28% mẫu M15 (hằng số tiên nghiệm, chưa hiệu chỉnh): nhãn này chưa mang nhiều thông tin; không chỉnh sau khi nhìn kết quả, ghi nhận để tiền đăng ký lại. Mô tả ≠ dự đoán: chưa có đo "thông tin gia tăng" (HB1/HC1/HD1 NOT_TESTED). Độ trễ render trình duyệt chưa đo.
