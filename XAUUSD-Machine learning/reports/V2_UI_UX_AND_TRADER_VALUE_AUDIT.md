# V2 · Kiểm toán UI/UX và giá trị cho trader

Ngày: 2026-10-13.

**Cảnh báo bằng chứng:** ảnh chụp FTMO BUY/V2 WAIT anh cung cấp **không đến được em**. Phân tích dựa trên ảnh em chụp V2 đang chạy: `reports/evidence/audit_p0/ui_1440x900.png`, `ui_1152x720.png`, `ui_1920x1080.png`, cộng đọc mã `apps/web/src/components/*` (1.164 dòng). Không dùng lệnh BUY FTMO làm chân lý.

## 1. Cái gì dùng được ngay / mơ hồ / dư / thiếu
| Nhóm | Nội dung |
|---|---|
| Hành động được | trạng thái BUY/SELL/WAIT; blocker hiện tại; nút mở PAPER; panel quyết định của người; AutoPaperStrip |
| Mơ hồ | "WAIT" đi cùng blocker có thể là cổng an toàn (spread) trong khi H1 thực ra NEUTRAL: chuỗi bị che; RISK_LIMIT/COOLDOWN (trạng thái hệ thống) hiện như lý do thị trường |
| Dư | nhiều khối trạng thái hệ thống/health/model chiếm không gian ngang hàng với quyết định |
| Thiếu | **`next_condition` không render** ở SystemPanel (API có); không có "cần X để thành BUY" theo từng tầng; không cảnh báo "sắp đủ điều kiện"; không so sánh với lệnh người đang giữ |
| Có | `readiness_level/6` ở ChartPanel (nhỏ, trong header chart), MtfStrip 37 dòng |

## 2. Giá / nến đã đóng / nến đang hình thành
Có endpoint `/market/forming` và `withForming` trong ChartPanel (nến đang hình thành được vẽ). Quyết định chỉ dựa nến đã đóng — đúng thiết kế. Cần đánh dấu rõ trên UI "quyết định dựa M5 đóng lúc HH:MM"; chưa xác minh UI có nhãn này hay không (NOT VERIFIED). Hạn chế: trader nhìn giá live và nến đang chạy có thể kỳ vọng tín hiệu theo giá live.

## 3. Độ tươi dữ liệu
API có `age_seconds`, `collector_age_seconds`. Quote p95 ~3 s. UI nên nổi bật tuổi quote và cảnh báo khi >5 s (đề xuất). Mức hiển thị hiện tại: không xác minh đủ.

## 4. Màn hình
- **1440×900**: bố cục dùng được; phần quan trọng thấy được.
- **1152×720 (nhỏ)**: panel quyết định/key panel bị đẩy xuống dưới, phải cuộn (VERIFIED ở ảnh; ≤900 px chiều cao).
- **1920×1080**: dư không gian, nhưng không thêm thông tin quyết định.
- Phone: đóng băng theo quyết định chủ dự án (desktop-only), không đánh giá.

## 5. Trader có thấy "phải đổi gì trước khi BUY/SELL"?
**Không đầy đủ.** Thấy blocker hiện tại, không thấy chuỗi điều kiện còn thiếu. Đây là khoảng trống giá trị lớn nhất của UX.

## 6. Kế hoạch UX ưu tiên (đề xuất, không thực thi)
| # | Việc | Tiêu chí kiểm |
|---|---|---|
| 1 | Render `next_condition` + thang chuỗi H1→M15→M5→M1 với trạng thái từng tầng | test UI: 6 tình huống blocker hiển thị đúng; ảnh 1152×720 vẫn thấy không cuộn |
| 2 | Tách dải "an toàn hệ thống" (governor/cooldown/spread) khỏi "ý kiến thị trường" | mỗi trạng thái WAIT có đúng một nhãn thuộc 2 nhóm |
| 3 | Nổi bật tuổi quote và "quyết định dựa M5 đóng lúc…" | kiểm thị giác + test snapshot |
| 4 | Panel quyết định trong 720 px không cuộn | đo vị trí phần tử |
| 5 | Gỡ trùng lặp giữa health/system | giảm số khối |

## 7. Điểm giá trị
Hỗ trợ quyết định **4/10**, thông tin **7/10** (xem `V2_INDEPENDENT_EXECUTIVE_AUDIT.md`).

## 8. Giới hạn
Chưa kiểm khả năng truy cập, màu/độ tương phản, phản hồi người dùng thật; chưa lặp lại trên trình duyệt khác.
