# Đánh giá độc lập (red team) sprint TRADE-04 và cách xử lý

Người đánh giá: một tác nhân riêng (không phải tác nhân đã viết mã), được giao đọc mã thật, chỉ đọc, không sửa, không chạy tác vụ nặng, và **không được báo trước kết luận**. Kết quả: **20 phát hiện: 0 CRITICAL, 1 HIGH, 6 MEDIUM, 13 LOW** (một mục được xếp MEDIUM/LOW). Không còn HIGH/CRITICAL mở. Danh sách "đã xác minh đúng" của người đánh giá (không đường tới lệnh MT5, thứ tự guard POST, v1.1 mặc định không đổi trên 6 000 trạng thái ngẫu nhiên, kỷ luật nến đã đóng, vòng đời độc lập với độ dài cửa sổ, không tín hiệu đôi, hợp đồng trường UI) được giữ nguyên làm bằng chứng.

| # | Mức | Phát hiện | Xử lý |
|---|---|---|---|
| 1 | **HIGH** | v1.2 có thể phát BUY khi cấu trúc M15 là `REVERSAL_DOWN` (CHoCH giảm) hoặc sau đó; trái với pre-đăng ký ("INVALIDATED khi cấu trúc M15 chuyển ngược") | **Sửa thành v1.2.1** (`REVERSAL_<ngược>` coi là ngược ở vòng đời và ở `decide`); v1.2.0 giữ nguyên để tái lập. 3 test. Đo lại E1/E2: **đúng 8 tín hiệu như v1.2.0** (nhãn M15 của cả 8 là UP/DOWN) nên lỗi không tạo tín hiệu sai ở hai cửa sổ này; số lượt INVALIDATED tăng 185/223 |
| 2 | MEDIUM | vòng đời đếm nến M5, không đếm thời gian: setup armed trước cuối tuần/khoảng trống dữ liệu có thể trigger ngay sau đó | **Sửa (v1.2.1)**: hết hạn khi `close − armed_at > 6×5 phút`; test có lỗ hổng 2 ngày |
| 3 | MEDIUM | hiệu lực hiển thị (15 phút) dài gấp ~3 lần thực tế (<5 phút); cảnh báo "invalidated" giả khi tín hiệu hết tuổi | **Sửa**: `cap_validity` giới hạn hiệu lực tới lần đóng M5 kế tiếp (áp cho cả v1.1 ở tầng engine, không đổi quyết định baseline); cảnh báo dùng hạn đã giới hạn |
| 4 | MEDIUM | nến chứa thời điểm khớp lệnh bị bỏ qua hoàn toàn ⇒ SL/TP trong ≤60 s đầu bị bỏ sót (lạc quan); replay khác live | **Sửa**: nến đó được xét bi quan (chỉ phía bất lợi, bỏ phía thuận lợi, không quản lý lệnh); 2 test |
| 5 | MEDIUM | live quyết định mỗi nến M1; đánh giá/parity/replay chỉ tại lần đóng M5 | **Ghi nhận giới hạn** (không đổi): số setup/ngày là cận dưới cho live; parity 0 khác biệt áp dụng cho nhịp M5. Việc mở rộng lên nhịp M1 để lại cho v1.3 |
| 6 | MEDIUM | kết quả không gắn với mã nguồn (cây làm việc chưa commit); thiếu test ghim hash v1.1 | **Sửa**: commit; `code_version` (SHA, `-dirty` nếu có thay đổi) ghi vào journal, engine và JSON đánh giá; test ghim luồng quyết định 1.1.0/1.2.0/1.2.1 (`test_golden_streams.py`). Hồi quy: luồng v1.1 và v1.2.0 trên E1/E2 **giống từng bit** với lần chạy trước |
| 7 | MEDIUM | M1 bất thường bị báo `SPREAD_TOO_WIDE`; cổng "M1 volatile" không bao giờ chạy | **Sửa (v1.2.1)**: báo `VOLATILITY_TOO_HIGH`; v1.1 giữ nhãn cũ (quyết định không đổi) |
| 8a | LOW | `m15_bar` tính từ giờ đóng nến, đếm thiếu cặp cùng nến M15 | **Sửa** (dùng nến trigger) |
| 8b | LOW | "ngày giao dịch" = 24 ngày/cửa sổ gồm cả đoạn Chủ nhật; chưa định nghĩa | **Sửa**: báo cả hai định nghĩa (ngày có nến; ngày đầy đủ ≥200 lần đóng M5 = 20 ngày/cửa sổ) |
| 8c | LOW | số mẫu quá nhỏ cho các câu "H-A/H-B được/không được ủng hộ" | **Sửa văn bản**: thêm khoảng Poisson 95%; diễn giải hạ xuống "gợi ý" |
| 8d | LOW | E1/E2 không còn "chưa xem" sau chẩn đoán spread và replay | **Ghi nhận** trong báo cáo; mọi thay đổi tiếp theo phải dùng cửa sổ khác (E3/E4) |
| 9 | LOW | mũi tên hướng dùng chuỗi hiển thị ("ARMED (UP …)") ⇒ 0 | **Sửa**: lấy từ nhãn thô; test |
| 10 | LOW | bảo vệ "chỉ dữ liệu đã đốt" chỉ kiểm `[start, end]`, còn nạp khởi động tới 200 ngày trước (qua Test-H) | **Sửa**: giới hạn mọi lần nạp vào 2025-05-01..2026-05-01 (kết quả E1/E2 không đổi); không dùng contract mặc định khi thiếu spec |
| 11 | LOW | PDH/PDL lệch 1 ngày trong giờ server đầu tiên | **Sửa** + test |
| 12 | LOW | marker dùng giờ quyết định thay vì nến trigger; chuỗi thời gian có thể lặp khi đổi giờ mùa hè (múi BROKER/LOCAL) | **Sửa**: marker = mở nến M5 trigger; biểu đồ bỏ thời gian lặp/lùi; e2e |
| 13 | LOW | đọc `desk.trades` không khóa; runner không bắt lỗi; `paper_close` không `step` trước; `step` có mã ngoài `try` | **Sửa**: khóa cho các GET đọc desk; runner bắt lỗi; `paper_close` `step` trước; toàn bộ thân `step` trong `try`. Còn lại: không có khóa ghi đơn cho `data/trade` (một tiến trình ghi duy nhất theo thiết kế) |
| 14 | LOW | AUTO_PAPER không hiển thị | **Sửa**: cờ trong view + banner; e2e |
| 15 | LOW | test cách ly dùng tên mô-đun không tồn tại | **Sửa**: cấm `brokers.mt5_demo.executor`; test kiểm mô-đun thật tồn tại |
| 16 | LOW | file trạng thái hỏng bị thay âm thầm bằng trống; PENDING kẹt khi lỗi lạ | **Sửa**: file hỏng được giữ lại (`.corrupt-<giờ>`) và báo trong view; mọi lỗi khi khớp lệnh hủy bản ghi. **Chưa làm** (ghi nhận): sập giữa `submit_order` và lưu, quy tắc đóng lệnh trước cuối tuần (hiện chỉ có thoát 120 phút; lệnh thứ Sáu thoát ở nến đầu sau khoảng trống), ngày governor theo UTC |
| 17 | LOW | spread đếm 2 lần cho BUY (bảo thủ); mức kháng cự "ảo" khi giá vượt (hiếm, chỉ gây RR_TOO_LOW); đường RES/SUP không ghi rõ M15 | **Ghi nhận**; nhãn đổi thành "M15 RES/SUP" |
| 18 | LOW | hằng `STRATEGY_VERSION` lỗi thời; cờ ablation không vào id; `setup_id` ablation đổi theo thời điểm poll | **Sửa**: hằng = mặc định thật; cờ vào id; `setup_id` ổn định theo nến trigger; test |
| 19 | LOW | dedupe telemetry không vượt qua nửa đêm UTC | **Sửa** + test |
| 20 | LOW | guard POST theo header (local client giả được); GET chưa kiểm Host | **Sửa một phần**: GET cũng kiểm Host (chống DNS rebinding); client cục bộ tự giả header là chấp nhận được (API chỉ lắng nghe 127.0.0.1); cách dashboard dev bind chưa kiểm |

Phát hiện này cho thấy hai bài học cho quy trình: (1) tự review không đủ, reviewer độc lập tìm ra lỗi hợp đồng mà test mock che; (2) mọi sửa đổi hành vi phải thành phiên bản mới (1.2.1), không sửa lặng lẽ 1.2.0.
