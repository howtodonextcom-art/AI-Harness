# ADR-V2-014: độ tin cậy của sổ PAPER và nền tảng bằng chứng forward

Trạng thái: **ĐÃ DUYỆT** (G8, 2026-10-13) · Liên quan: ADR-V2-012 (paper desk), ADR-V2-007, `docs/forward/FORWARD_EVIDENCE_PROTOCOL.md`.

## Bối cảnh

Sau khi chủ dự án loại ML V0 tại Kiểm định (không đổi tiêu chí, không mở Test-H), nguồn bằng chứng còn lại là **forward**: tín hiệu tự nhiên của baseline v1.1.0 trong chế độ PAPER. Một mẫu forward chỉ có giá trị nếu hệ thống **chạy liên tục, không mất dữ liệu âm thầm và không tự thay đổi**.

## Quyết định

1. **Nhật ký quyết định theo nến M5 đã đóng** (`decision_log`, SQLite, khóa duy nhất theo nến, dòng đầu thắng): ghi cả những nến WAIT và lý do (phễu quyết định), để biết tín hiệu hiếm đến mức nào mà không cần chờ lệnh.
2. **Độ phủ quan sát là số liệu hạng nhất:** so nến đã ghi với nến M5 đã đóng trong kho; mọi khoảng trống được liệt kê và hiển thị. Giao thức đòi độ phủ ≥ 95% trước khi cho phép kết luận.
3. **Giao thức đăng ký trước** (`FORWARD_EVIDENCE_PROTOCOL.md`): kết luận về lợi thế chỉ được phép khi ≥ 100 lệnh đã đóng cùng `strategy_version`, ≥ 60 ngày, độ phủ ≥ 95%, **và** một giả thuyết forward do chủ dự án duyệt (họ K riêng). Mọi thứ khác là MÔ TẢ, `claim_allowed = false`. Đổi phiên bản chiến lược ⇒ đặt lại đồng hồ.
4. **Độ tin cậy của sổ PAPER:** kiểm tra toàn vẹn SQLite khi khởi động (kết quả hiển thị ở `/health`, FAIL nếu có vấn đề); **sao lưu trực tuyến mỗi ngày UTC** (API sao lưu của SQLite, giữ 14 bản gần nhất); **watchdog** của vòng nền (lượt cuối, số lỗi, thời gian; FAIL nếu chưa xong lượt nào, WARN nếu quá ngưỡng 3 × nhịp + 10 giây hoặc lượt gần nhất lỗi); cảnh báo khi **có lệnh mở nhưng dữ liệu M1 cũ** (không có nến để quản lý SL/TP). Một lượt lỗi không dừng engine nhưng được đếm và hiển thị; không bao giờ được báo là thành công.
5. **Bằng chứng về sập tiến trình:** test giết tiến trình (`os._exit`) giữa một giao dịch (không còn nửa nào) và ngay sau commit (đủ cả hai nửa).
6. **Soak:** `scripts/soak.py` đo độ trễ, lỗi, khoảng hở `seq`, xu hướng bộ nhớ, sức khỏe engine trên dịch vụ đang chạy (chỉ đọc).

## Hệ quả

- Hợp đồng `2.0.0-g8`; `GET /api/v2/forward/summary` (chỉ đọc); ngăn "Bằng chứng" hiển thị độ phủ, phễu, tín hiệu, lệnh, mua-và-giữ và các mức tối thiểu.
- Sao lưu nằm cùng ổ với tệp gốc: **không phải** sao lưu chống mất ổ đĩa. Sao lưu ra ổ khác/đám mây là việc của chủ dự án (nằm trong "Cần bạn").
- Chưa làm: thông báo ngoài (e-mail/Telegram) khi watchdog cảnh báo; tự khởi động lại dịch vụ khi máy khởi động lại (cần dịch vụ Windows/Task Scheduler, thuộc chủ dự án).
