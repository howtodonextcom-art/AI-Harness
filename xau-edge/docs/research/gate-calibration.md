# Hiệu chuẩn cổng robustness và công suất (RI-05, RI-11)

Ngày: 2026-10-09. Seed 20261009. Mô phỏng chiến lược "gieo" (planted): hiệu ứng thật 0.00R, 0.05R, 0.10R,
0.20R, sd 1.3R mỗi lệnh. Mã: `src/xau_edge/integrity/gates.py`, `power2.py`; tái lập bằng

```
uv run python -c "from xau_edge.integrity.gates import calibrate; print(calibrate(sims=1500, seed=20261009))"
uv run python -c "from xau_edge.integrity.power2 import planted_edge_table; print(planted_edge_table(k=21, sims=600, seed=20261009))"
```

Đây là **chẩn đoán Class D**: không tạo bằng chứng edge và **không đổi ngưỡng nào** của roadmap mục 21.

## 1. Cổng chính ở K = 21 (250 ngày x 3 lệnh = 750 lệnh, kiểm định one-sided alpha/K)

Tỷ lệ bác bỏ H0 (cột 0.00R là tỷ lệ dương tính giả; các cột còn lại là công suất):

| Hiệu ứng thật | Độc lập | Gộp theo ngày (rho 0.3) | Kết quả chồng lấn (giữ 4 lệnh) |
|---|---|---|---|
| 0.00R | 0.3% | 0.2% | 2.2% |
| 0.05R | 3.8% | 2.0% | 5.0% |
| 0.10R | 21.7% | 11.5% | 12.0% |
| 0.20R | 88.3% | 64.2% | 45.7% |

Kết luận: với cỡ mẫu này cổng **không phát hiện được +0.10R** (công suất 12-22%) và chỉ phát hiện +0.20R một
cách đáng tin khi mẫu độc lập. Dependence làm giảm công suất rõ (0.20R: 88% -> 46-64%). Hệ quả: một kết quả
"NO EDGE" từ 750 lệnh **không bác bỏ** một edge +0.10R. Console phải hiển thị MDE theo effective N, không theo
raw N (đã hiện thực ở `power_report`).

## 2. Cổng robustness (mục 21), 8 năm x 150 lệnh, 1500 mô phỏng

| Cổng | FP (0.00R) | 0.05R | 0.10R | 0.20R | Phân loại | Nhận xét |
|---|---|---|---|---|---|---|
| Temporal (>=70% năm dương, không năm nào >40% lợi nhuận) | 4.9% | 32.5% | 74.6% | 99.7% | **SUPPORTED** | FP thấp, công suất tốt từ 0.10R |
| Parameter stability (láng giềng >0 và >=50% của biến thể tốt nhất) | 14.1% | 56.8% | 89.5% | 100% | **CONSERVATIVE** | FP 14% > 10%: một mình nó chưa đủ lọc |
| Broker robustness (cùng dấu, >=50% của broker A) | **44.9%** | 82.9% | 97.6% | 100% | **UNDER-STRICT** | xem dưới |

**Phát hiện quan trọng về Broker robustness.** Hai broker nhìn **cùng một lịch sử giá**; biến thể được chọn vì
may mắn ở broker A mang phần may mắn đó sang broker B. Vì vậy cổng này phát hiện *artefact riêng của broker*
(chi phí, đồng hồ, dữ liệu) nhưng **không lọc được overfitting do chọn lọc** (FP 45%). Quy tắc kết luận:

* Cổng broker **không được dùng làm bằng chứng ý nghĩa thống kê**; chỉ là kiểm tra artefact.
* Không đổi ngưỡng. Nếu muốn một cổng chống chọn lọc, cần một cổng khác (Reality Check / DSR / PBO,
  `integrity/dof.py`) đăng ký trước cho thí nghiệm tương lai.

## 3. Quy tắc phân loại (cố định trước khi xem kết quả)

UNDER-STRICT nếu FP > 20%; OVER-STRICT nếu công suất ở 0.10R < 40%; SUPPORTED nếu FP <= 10% và công suất ở
0.10R >= 70%; còn lại CONSERVATIVE. Mọi đề xuất đổi ngưỡng cần tài liệu có phiên bản, được duyệt và chỉ áp
dụng cho thí nghiệm đăng ký **sau** đó.

## 4. Giới hạn của mô phỏng

Mô hình chuẩn, sd đồng nhất, láng giềng tham số tương quan 0.8 và broker B tương quan 0.7 là **giả định**;
số thật có thể khác. Các tỷ lệ chỉ có giá trị tương đối để so các cổng và để thấy công suất của thiết kế.
