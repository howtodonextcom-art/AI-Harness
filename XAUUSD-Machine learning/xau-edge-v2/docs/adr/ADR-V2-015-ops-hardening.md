# ADR-V2-015: củng cố vận hành (sao lưu ngoài, tự chạy, cảnh báo vận hành)

Trạng thái: **ĐÃ DUYỆT** (G8.1, 2026-10-13) · Liên quan: ADR-V2-014.

## Quyết định (theo chủ dự án 2026-10-13)

1. **Sao lưu nhiều lớp, mỗi lớp được kiểm trước khi tính:** bản sao nhất quán hằng ngày (API sao lưu của SQLite) → **bản sao thứ hai** ở một nơi khác (mặc định `D:/XAU-EDGE-V2-backups`) → **bản sao NGOÀI thiết bị** (`XAU_V2_BACKUP_OFFDEVICE_DIR`: ổ ngoài/NAS/thư mục đám mây đang đồng bộ). Mỗi bản chép được ghi dưới tên tạm, so **sha256 với nguồn**, mở bằng SQLite kiểm `integrity_check`, rồi mới đổi tên; xoay vòng từng nơi; nơi không truy cập được chỉ bị ghi nhận (không làm dịch vụ chết) và được thử lại mỗi 5 phút.
2. **Nói thật về "ngoài thiết bị":** máy chỉ có một SSD vật lý (ba phân vùng C, D, Z) nên bản sao D: chống xóa nhầm/hỏng tệp, **không** chống hỏng ổ. `/health` luôn cảnh báo "CHƯA CÓ bản sao ngoài thiết bị" cho tới khi `XAU_V2_BACKUP_OFFDEVICE_DIR` được đặt. Thư mục OneDrive tồn tại nhưng ứng dụng đồng bộ không chạy/chưa đăng nhập: **không** được tính là đám mây.
3. **Khôi phục là một thao tác có công cụ và test:** `restore_backup.py` kiểm bản sao trước, giữ tệp cũ để hoàn tác, xóa WAL/SHM cũ, từ chối khi dịch vụ còn chạy hoặc bản sao hỏng.
4. **Tự chạy:** hai tác vụ Task Scheduler cho người dùng hiện tại (không cần quản trị): người giám sát `run_v2.ps1` lúc đăng nhập (một bản duy nhất bằng mutex, chạy lại có lùi dần, không tranh cổng với bản chạy tay) và watchdog ngoài mỗi 2 phút. Không phải dịch vụ hệ thống: chỉ chạy khi tài khoản đang đăng nhập.
5. **Cảnh báo Telegram, chỉ vận hành:** nội dung chỉ là tình trạng dịch vụ (không tín hiệu, giá, lãi/lỗ; có test chặn). Bộ phát cảnh báo trong dịch vụ: vấn đề phải kéo dài ≥ 2 phút, nhắc lại tối đa mỗi giờ, một tin hồi phục khi hết, thất bại gửi được thử lại và hiện ở `/health`; lỗi của chính việc cảnh báo **không** tính vào engine. Watchdog **ngoài** (vì bộ phát trong dịch vụ nằm trong vòng nền: nếu vòng nền hoặc cả tiến trình chết thì chỉ quan sát viên bên ngoài nói được): báo khi dịch vụ không phản hồi/DOWN/vòng nền hỏng sau 2 lần kiểm liên tiếp, nhắc lại hằng giờ, báo hồi phục.
6. **Bí mật:** token ở `.env` (ngoài git), kiểu `SecretStr`, không vào nhật ký/lỗi/`/health` (có test). V2 **không** đọc thông tin xác thực của V1.

## Chưa quyết / chưa làm

- Chưa có token Telegram và chat id (cần chủ dự án tạo bot): kênh được xây và kiểm bằng máy chủ giả, **chưa gửi được một tin thật**.
- Chưa có bản sao ngoài thiết bị (cần đích do chủ dự án chọn).
- Người giám sát không tự chạy trước khi ai đó đăng nhập sau khi khởi động máy; collector của V1 nằm ngoài phạm vi.
