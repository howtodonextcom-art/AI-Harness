# V2 · Lộ trình nghiên cứu ML (khung chặt, không có tín hiệu bịa)

Ngày: 2026-10-13 · Trạng thái hiện tại: ML V0 = CONTAMINATED trong `research_status_register.json`; `ModelStatus` hiển thị RETIRED/không quyền; **không suy luận live, không shadow trên đường quyết định**. Trong đợt này **không huấn luyện, không retrain, không bật ML**.

## 1. Mục đích khoa học duy nhất đáng theo đuổi
ML chỉ có lý do khi nó **thêm thông tin** vượt các đường cơ sở tất định đã có. Bài toán giới hạn, theo thứ tự:
| # | Bài toán | Nhãn | Lý do chính đáng | Đường cơ sở để thắng |
|---|---|---|---|---|
| 1 | Xác suất pha biến động (nén→mở rộng) | pha ở N nến sau (từ nến, không từ giá lệnh) | không cần PnL; nhãn nhân quả; đo hiệu chuẩn được | tần suất nền + ATR percentile |
| 2 | Xác suất "mất mức BOS trong 3 nến" | nhãn cấu trúc (không PnL) | đã đo 48% nền; ML có thể phân biệt | tần suất nền theo khung/phiên |
| 3 | Chất lượng setup / xác suất kết quả sự kiện | outcome | cần outcome ⇒ chỉ sau phê duyệt, trên VALIDATION' | bảng tra theo (họ, phiên, ATR bucket) |
| 4 | Bất định phân phối / OOD | khoảng cách tới phân phối huấn luyện | cổng an toàn "đừng tin" | ngưỡng z-score |
Thứ tự 1→2 được làm được **không mở outcome** ⇒ có thể bắt đầu sau khi chủ dự án duyệt phạm vi.

## 2. Quy tắc bắt buộc (mọi mô hình)
1. Đặc trưng **điểm-thời-gian** (chỉ nến đã đóng; kiểm `known_at`), mỗi đặc trưng có nguồn gốc và khung.
2. Tách thời gian có **purge + embargo** (≥ độ dài nhãn ở mỗi biên) trên kho sạch DEV'; chọn mô hình chỉ trên DEV'; VALIDATION' dùng một lần.
3. Phân tích công suất trước khi huấn luyện; cỡ mẫu thấp ⇒ báo `INCONCLUSIVE`.
4. Hiệu chuẩn (reliability, Brier, ECE) báo cùng mọi xác suất; **không gọi "đã hiệu chuẩn" khi chưa có bằng chứng**.
5. Registry mô hình có băm dữ liệu/mã/spec; ghi mọi dự báo (`prediction_log`), theo dõi drift (PSI/KS trên đặc trưng; sụt hiệu chuẩn theo thời gian).
6. Báo bất định (khoảng/entropy). Quyền hạn **NONE** cố định trong contract; muốn đổi cần cổng duyệt riêng.
7. Cấm: huấn luyện bằng dữ liệu có bar giả; tái dùng ML V0; chọn siêu tham số trên cửa sổ đánh giá; báo xác suất mà không có đường cơ sở.

## 3. Giai đoạn đề xuất (chưa thực hiện)
| Giai đoạn | Nội dung | Điều kiện dừng |
|---|---|---|
| M0 | bộ nhãn nhân quả cho bài #1, #2 trên kho sạch + phân tích công suất | báo cáo power |
| M1 | đường cơ sở tất định → hồi quy logistic → mô hình nhẹ (cây nông); so sánh trên DEV' có purge | không thắng cơ sở ⇒ dừng, ghi `REFUTED/INCONCLUSIVE` |
| M2 | hiệu chuẩn + drift + registry + log dự báo ở chế độ **shadow hiển thị** (không quyền) | chủ dự án duyệt hiển thị |
| M3 | outcome-based (bài #3) trên VALIDATION' một lần | duyệt riêng |

## 4. Không làm trong đợt này (nêu rõ để không hiểu nhầm)
Không có mô hình mới, không có số xác suất nào hiển thị, không có tuyên bố "AI dự đoán". Khung này là kế hoạch + quy tắc, kết quả `NOT_TESTED`.
