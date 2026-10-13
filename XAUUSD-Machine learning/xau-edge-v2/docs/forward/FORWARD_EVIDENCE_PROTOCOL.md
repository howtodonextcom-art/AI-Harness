# Giao thức bằng chứng forward (đăng ký trước)

Phiên bản 1.0 · 2026-10-13 · Trạng thái: **ĐANG TÍCH LŨY (chưa có giả thuyết được duyệt)** · Liên quan: ADR-V2-007, ADR-V2-012, ADR-V2-014.

Mục đích: bất kể ML hay quy tắc, bằng chứng thật cuối cùng cho hệ thống này là dữ liệu **forward** (tương lai thật, PAPER, không nhìn thấy khi thiết kế). Giao thức này đóng đinh **trước khi có số liệu** những gì được ghi, những gì được phép nói và khi nào.

## 1. Cái được ghi (tự động, chỉ thêm)

1. **Nhật ký quyết định** (`decision_log`): mỗi nến M5 **đã đóng** (khóa duy nhất theo thời điểm mở nến) ghi một dòng: hành động (BUY/SELL/WAIT), mức sẵn sàng 0..6, thiên hướng, **các mã từ chối**, giá, spread (điểm), ATR M15, trạng thái thị trường, chất lượng dữ liệu, `decision_id`, `strategy_version`, `setup_id`. Không ghi dòng nào khi không có quyết định (không bịa). Dòng đầu tiên thắng; không sửa.
2. **Sổ lệnh PAPER** (ADR-V2-012): vào/ra, R, MAE/MFE, chi phí giả định, nguồn (AUTO/MANUAL), cờ nến mơ hồ.
3. **Độ phủ quan sát:** số nến M5 đã đóng trong kho trong khoảng quan sát so với số nến đã ghi; mọi **khoảng trống** (engine dừng/kẹt) được liệt kê. Một mẫu forward có khoảng trống âm thầm **không phải** mẫu forward.
4. **Đồng hồ chiến lược:** `strategy_version` ghi cho mỗi quyết định. Nếu phiên bản đổi giữa chừng (kể cả đổi ngưỡng), **đồng hồ quan sát phải đặt lại** và hệ thống ghi rõ.

## 2. Cái được phép nói, và khi nào

| Mức | Được nói | Điều kiện |
|---|---|---|
| Mô tả | số nến quan sát, phễu quyết định, số tín hiệu, lệnh đã đóng, R, tỉ lệ thắng kèm khoảng Wilson, so với mua-và-giữ | luôn luôn; luôn kèm nhãn **MÔ TẢ, UNVALIDATED** |
| **Kết luận về lợi thế** | "R ròng trung bình > 0 trên forward" | **tất cả**: (a) ≥ **100 lệnh đã đóng** cùng một `strategy_version`; (b) ≥ **60 ngày** lịch quan sát; (c) độ phủ ≥ **95%**; (d) **một giả thuyết forward được chủ dự án duyệt trước**, thuộc một họ K riêng (ADR mới), nêu trước thống kê kiểm định và mức α/K; (e) phân tích theo kế hoạch ở mục 3 |

Trước khi đủ (a)-(e), giao diện và API ghi `claim_allowed = false` kèm lý do. **Không có quy tắc nào cho phép đổi các mức này sau khi đã thấy số liệu.**

## 3. Kế hoạch phân tích (cố định trước)

- Đơn vị: lệnh PAPER đã đóng. Thước đo: **R ròng** = (PnL + swap giả định) / rủi ro tại giá khớp.
- Thống kê chính: R ròng trung bình; khoảng tin cậy bootstrap khối theo **ngày** (2.000 lần, hạt giống 7), cận dưới **một phía** ở mức 1 − α/K của họ được duyệt.
- Độ nhạy bắt buộc báo cáo: trượt giá ×2 và hoa hồng giả định > 0; loại các lệnh có nến mơ hồ; theo phiên (Á/Âu/Mỹ).
- Chuẩn so sánh: mua-và-giữ cùng kỳ (đã có) và baseline "không giao dịch" (R = 0).
- Không dùng: lọc lệnh theo kết quả, bỏ lệnh "bất thường" sau khi đã thấy kết quả, đổi cửa sổ quan sát.

## 4. Những gì giao thức này KHÔNG làm

Không tự đăng ký giả thuyết; không đổi nhãn bằng chứng (`UNVALIDATED`, không bao giờ tự thành `FORWARD_VALIDATED`); không mở Test-H/Holdout; không thay thế sổ cái K. Mở một giả thuyết forward cần quyết định của chủ dự án.

## 5. Nhịp báo cáo

Tóm tắt có thể xem bất kỳ lúc nào (`GET /api/v2/forward/summary`, ngăn "Bằng chứng"), nhưng **không có điểm dừng sớm**: không kết luận giữa chừng, dù số liệu đẹp hay xấu, trước khi đủ mục 2.
