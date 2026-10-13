# V2 · Lộ trình nâng cấp trí tuệ (đề xuất, chờ duyệt)

Ngày: 2026-10-13 · Không bắt đầu cho đến khi chủ dự án duyệt. Mọi giai đoạn: PAPER-only, V1 CONTROL giữ nguyên, không đổi giới hạn rủi ro, không mở cửa sổ khóa.

## Giai đoạn 1: Sự thật và Quan sát (Truth & Observability)
- **Phạm vi:** render `next_condition` và thang chuỗi; tách `system_hold` / `market_blocker`; `decision_log` theo sự kiện; nhãn tuổi quote và "quyết định dựa M5 đóng lúc"; cổng chặn tick 2022-Q1; điều tra đuôi p99 quote.
- **Sản phẩm:** thay đổi UI/API không đổi logic; test parity (quyết định bit-giống trước/sau); báo cáo đo lại độ trễ.
- **Chấp nhận:** 100% trạng thái WAIT có nguyên nhân tách bạch; mọi lệnh có dòng log; quyết định giống hệt trên bộ so sánh; p99 quote ≤ 6 s hoặc nguyên nhân có biên bản.
- **Phụ thuộc:** không.
- **Rollback:** tính năng cờ; trả về giao diện hiện tại.
- **Cổng chủ dự án:** duyệt phạm vi trước, duyệt kết quả sau.

## Giai đoạn 2: Trí tuệ hỗ trợ quyết định (Decision-Support Intelligence)
- **Phạm vi:** "kịch bản thành BUY/SELL" (chuỗi điều kiện còn thiếu, khoảng giá kích hoạt tham khảo), cảnh báo gần đủ điều kiện, bối cảnh nến mô tả (không quyết định), so sánh với lệnh người đang giữ ở dạng thông tin.
- **Sản phẩm:** tính năng mô tả thuần; mọi con số lấy từ chuỗi hiện có.
- **Chấp nhận:** thử nghiệm với người dùng: thời gian để hiểu "vì sao WAIT" giảm (đo được); không thay đổi quyết định tự động.
- **Phụ thuộc:** Giai đoạn 1.
- **Rollback:** ẩn panel.
- **Cổng chủ dự án:** duyệt nội dung hiển thị, nhất là bất cứ thứ gì có thể bị hiểu là khuyến nghị.

## Giai đoạn 3: Candidate có cổng nghiên cứu (Research-Gated)
- **Phạm vi:** chốt và băm spec 1.1.0; Stage A DEV' (chỉ tín hiệu); sau đó đánh giá theo prereg trên VALIDATION' một lần; C4–C7 chỉ khi có preregistration; đo công suất.
- **Sản phẩm:** báo cáo tín hiệu, rồi báo cáo đánh giá với `SUPPORTED/REFUTED_HARM/INCONCLUSIVE`.
- **Chấp nhận:** quyết định promote/không dựa thống kê đã đăng ký; kết quả INCONCLUSIVE được chấp nhận là kết quả hợp lệ.
- **Phụ thuộc:** duyệt spec; quyết định về 2021-02..09; A1 (nếu cần).
- **Rollback:** Candidate chỉ chạy shadow; control là V1.
- **Cổng chủ dự án:** mỗi bước mở cửa sổ (Validation, Confirm-C...) cần phê duyệt riêng.

## Việc không thuộc lộ trình
Telegram, thực thi broker, Demo trading, ML live; không hồi sinh ML V0.

## Dừng tại Gate P0
Chờ anh quyết định giai đoạn nào được làm, theo thứ tự và phạm vi nào.
