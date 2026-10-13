# V2 · Báo cáo thời gian thực và hiệu năng (đo, không tuyên bố "zero latency")

Ngày: 2026-10-13 · Dịch vụ V2 đã khởi động lại với bản mới (pid 18260 tại thời điểm đo). Dữ liệu: `reports/evidence/intel/latency.json`; nền tảng tick→UI từ P0: `reports/evidence/audit_p0/`.

## 1. Bảng độ trễ
| Đoạn | Chỉ số | Kết quả | Nhãn |
|---|---|---|---|
| MT5 → hiển thị V2 (khớp cùng bid/ask) | p50 / p95 / p99 | 0,47 s / 3,78 s / 10,9 s (n=40) | P0, chưa lặp lại |
| Tuổi quote tại V2 | p50 / p95 | 0,86–0,95 s / 2,7–3,4 s | P0 |
| `GET /api/v2/intelligence` (200 lần) | p50 / p95 / p99 | **6,6 / 42,3 / 69,1 ms** (18,6 KB) | đo hôm nay |
| `GET /api/v2/state` (200 lần) | p50 / p95 / p99 | 6,3 / 48,9 / 69,1 ms (2,1 KB) | đo hôm nay |
| Tính một lần (xoá cache) | trung bình | ~28 ms (phân tích ~17 + mô tả ~10); lần đầu 103 ms | đo hôm nay |
| Cập nhật UI cho mô tả | | sự kiện `state` → refetch; ngoài ra poll 4 s | thiết kế (chưa đo từ trình duyệt) |
| Render trình duyệt, WS→DOM | | **NOT MEASURED** | |
| Phục hồi sau mất kết nối | | e2e xác nhận retry/refetch hoạt động (đúng/sai), không đo thời gian | |
| Quyết định theo nến đóng | | engine tick 3 s; `decision_events` ghi chuyển trạng thái | |
Đuôi p95/p99 của REST trùng giữa hai endpoint vì dùng chung cache 1 s: đuôi là lần tính bỏ cache, không phải đường dữ liệu mới.

## 2. Tần suất hiển thị ≠ tần suất quyết định
- Hiển thị: quote ≤~1 Hz (snapshot từ collector); mô tả/cấu trúc: theo nến đóng (cache theo (khung, số nến, nến cuối)).
- Quyết định: hàm của nến **đã đóng** + spread; tính lại mỗi ≥1 s (cache chung), không tính lại theo từng tick.
- Phần nặng (swing/BOS/nến) chỉ tính lại khi có nến đóng mới ở khung đó.

## 3. Tài nguyên
Dịch vụ rảnh (60 s, engine tick 3 s, UI không mở): **2,66% một lõi, 149 MB** (trước thay đổi, khi đo P0: 3,6% / 112 MB trong điều kiện khác ⇒ **không so sánh trực tiếp**; mức tăng bộ nhớ ~+37 MB hợp lý với memo + mã mới). Bộ sưu tập V1 và collector không bị chạm.

## 4. Kiểm tra an toàn
- Không sửa collector, `live.json`, quyền đọc chỉ-đọc kho. Dịch vụ V2 được khởi động lại (không ảnh hưởng PAPER: SQLite WAL, bảng mới `CREATE IF NOT EXISTS`, restore xử lý bảng thiếu).
- `decision_events` ghi chuyển trạng thái mỗi tick engine (`INSERT` nhỏ, khi thay đổi thật sự).

## 5. Việc còn lại (không tuyên bố đã xong)
Đo từ trình duyệt (Performance API) thời gian WS `state` → DOM; điều tra đuôi p99 10,9 s của quote ở collector (cần cửa sổ bảo trì + kế hoạch rollback); đo nhiều client; đo qua phiên Á/Âu/Mỹ.
