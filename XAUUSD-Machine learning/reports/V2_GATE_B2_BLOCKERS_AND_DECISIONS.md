# V2 · Cổng B2: blockers và quyết định cần chủ dự án

Ngày: 2026-10-13 · **Dừng tại Cổng B2. Chưa chạy lại outcome backtest. Chưa mở Validation, Confirm-C, Test-H, Holdout. Candidate chưa đóng băng.**

## Đã làm trong Gate B (xem 5 báo cáo)
Pháp y nguồn gốc dữ liệu; rà soát mã Candidate (3 lỗi sửa, 1 lỗi mở, chốt chặn dữ liệu); ma trận ảnh hưởng nghiên cứu cũ; ba phương án khôi phục; kiểm thử hồi quy. ADR-V2-018 **rút lại**; ADR-V2-019 **đề xuất**.

## Kết luận về dữ liệu (tóm tắt)
Nguyên nhân là **bar giả hằng ngày** mang OHLC phiên kế tiếp (2012-06-26 → 2021-01-20, 2.205 bar, 104 tháng), tức **nhìn trước 24 giờ**; không phải nhiễu. Bỏ bar giả thì H1 trùng khít với tải lại mới từ broker. Nguồn gốc chính xác của bar giả **chưa biết**; hôm nay terminal không phục vụ chúng.

## Blockers (chặn việc chạy lại outcome)
| # | Blocker | Ai | Hậu quả nếu bỏ qua |
|---|---|---|---|
| B1 | ADR-V2-019 chưa được duyệt (lớp hợp lệ + kho dẫn xuất sạch) | chủ dự án | không có định nghĩa tháng hợp lệ ⇒ không chạy lại được |
| B2 | Spec 1.1.0 (cửa sổ DEV/VALIDATION mới, dùng dữ liệu đã làm sạch, quy tắc H4 thay bằng tải lại) | chủ dự án + em soạn | Spec 1.0.0 gắn Dev 2011–2018 trên dữ liệu lỗi |
| B3 | Lỗi mở **F6**: `planned_stop` phụ thuộc điểm bắt đầu phát lại (C1) | chủ dự án chọn phương án 1/2/3 | kết quả Stage A phụ thuộc cách cắt tháng ở các setup hiếm |
| B4 | Bất thường **2022-01..03** (khớp tick 54–86%, chênh tới $7,8) | em điều tra khi được phép; chủ dự án quyết nếu cần | không ai được xin mở Test-H khi 3 tháng đầu chưa rõ |
| B5 | Tháng **2021-02..09** thiếu bằng chứng (không tick, tải lại đã khác) | chủ dự án: loại khỏi mọi outcome hoặc cung cấp nguồn | cửa sổ Validation' bị thu hẹp xuống ≈ 2021-10..12 |
| B6 | Thí nghiệm nguồn **A1** (tải M1 cũ trên terminal riêng) | chủ dự án (đụng cấu hình terminal) | không biết pseudo-bar là của broker hay do chế độ unlimited |
| B7 | Không có nguồn bên thứ ba có giấy phép | chủ dự án | "VERIFIED_VALID" mãi chỉ nghĩa là "cùng broker" |

## Quyết định cần chủ dự án phê duyệt
1. **ADR-V2-019:** duyệt, sửa, hoặc bác. (Em khuyến nghị duyệt với phương án **B làm chính, A1 đối chứng**.)
2. **Lỗi F6:** chọn (1) làm mới mức vô hiệu theo bar armed gần nhất (khuyến nghị), (2) lưu bộ nhớ bền, hay (3) chạy liên tục không cắt tháng.
3. **Cửa sổ trong spec 1.1.0:** (a) DEV' = các tháng VERIFIED hoặc recoverable từ 2005-06 đến 2021-01 (≈ 150 tháng) trừ SUSPECT; (b) VALIDATION' = 2021-10..2021-12 (chỉ 3 tháng đã kiểm); (c) Confirm-C giữ nguyên; (d) Test-H và Holdout **vẫn khóa**. Hay chọn cửa sổ khác?
4. **Thí nghiệm A1:** có cho phép (trên terminal portable riêng, không đụng collector) hay không.
5. **Kết quả nghiên cứu cũ:** đồng ý gắn nhãn "KHÔNG TIN CẬY" cho V1 Edge Program (H01–H10) và đánh dấu bằng chứng của ML V0 là "bị nhiễm rò rỉ", **không mở lại** họ K.
6. **Cho phép em điều tra 2022-Q1** (chỉ dữ liệu giá, không outcome).

## Việc em KHÔNG làm cho đến khi được phê duyệt
Chạy lại Stage A/B hoặc bất kỳ outcome nào; chọn hay đóng băng candidate; mở Validation/Confirm-C/Test-H/Holdout; sửa ngưỡng chiến lược; thay V1 control; ghi/xóa/sửa kho dữ liệu thô; kích hoạt giao dịch thật hoặc broker.
