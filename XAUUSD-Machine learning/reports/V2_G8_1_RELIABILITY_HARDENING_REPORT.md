# V2 G8.1: củng cố vận hành (sao lưu, tự chạy, cảnh báo vận hành)

Ngày: 2026-10-13 · repo `xau-edge-v2` (local, chưa push) · V1 **không bị sửa** (không đọc thông tin xác thực của V1).

Quyết định đã áp dụng: sao lưu sang ổ khác/cloud **YES, ưu tiên ngay** · tự chạy **YES** · cảnh báo ngoài **YES, Telegram vận hành trước** · **không mở họ K forward** (chưa có giả thuyết đủ cụ thể) · ML tạm dừng · forward collection tiếp tục · trình tự: G8.1 → Human Decision Layer → M1 Execution Intelligence.

## 1. Kết quả ngắn

| Yêu cầu | Trạng thái |
|---|---|
| Tự chạy | **XONG và đã kiểm chứng trên máy thật** (hai tác vụ Task Scheduler; giết dịch vụ ⇒ tự chạy lại sau 12 giây) |
| Watchdog ngoài | **XONG, đang chạy mỗi 2 phút** (kết quả tác vụ 0, `logs/external_watchdog.log`); gửi Telegram **chưa kiểm được trên Telegram thật** |
| Telegram vận hành | **Đã xây và kiểm bằng máy chủ giả; CHƯA gửi được một tin thật vì chưa có token bot + chat id** (V1 cũng không có cấu hình Telegram) |
| Sao lưu sang ổ khác | **Bản sao thứ hai XONG** (`D:/XAU-EDGE-V2-backups`, đã kiểm). **Nhưng D: là một phân vùng của cùng SSD vật lý duy nhất** (Samsung 980 PRO: C, D, Z), nên **chưa phải bản sao ngoài thiết bị** |
| Sao lưu cloud | **CHƯA CÓ**: thư mục `C:\Users\Kieu Oanh\OneDrive` tồn tại nhưng chỉ chứa `desktop.ini` và ứng dụng OneDrive **không chạy** (chưa đăng nhập/đồng bộ). Ghi vào đó sẽ không đi đâu cả, nên tôi **không** coi nó là cloud |

Vì thế `/health` đang (đúng) báo **WARN** hai mục cho tới khi bạn cấp hai thứ chỉ bạn cấp được: `backup_offdevice` ("CHƯA CÓ bản sao ngoài thiết bị") và `alerts` ("CHƯA cấu hình Telegram").

## 2. Đã xây

### Sao lưu có kiểm chứng (`paper/backup.py`)
- Bản sao nhất quán hằng ngày (đã có) → **bản sao thứ hai** (mặc định `D:/XAU-EDGE-V2-backups`) → **bản sao ngoài thiết bị** (`XAU_V2_BACKUP_OFFDEVICE_DIR`, đặt khi có đích).
- Mỗi bản chép: ghi tên tạm → **so sha256 với nguồn** → SQLite mở (chỉ đọc, `immutable`) kiểm `integrity_check` → đổi tên → xoay vòng riêng từng nơi (giữ 14). Bản chép lệch/nửa chừng bị loại và **không để lại tệp nào** (test). Xóa bản cũ bị khóa (ví dụ do ứng dụng đồng bộ) không làm hỏng bản mới tốt.
- Nơi không truy cập được: ghi nhận lỗi, thử lại mỗi 5 phút, **tự bắt kịp** khi ổ quay lại (test mô phỏng đúng việc này). `/health`: `backup_mirror`, `backup_offdevice`.
- **Khôi phục** (`scripts/restore_backup.py` + `paper/restore.py`): kiểm bản sao trước, giữ tệp cũ (`paper-before-restore-<utc>`) để hoàn tác, xóa WAL/SHM cũ, so lại số dòng sau khi chép, từ chối khi cổng dịch vụ còn trả lời hoặc bản sao hỏng (4 test).

### Tự chạy
- `scripts/service/run_v2.ps1` (người giám sát): một bản duy nhất (mutex), không tranh cổng với bản chạy tay, chạy lại có lùi dần (5 s → 2 phút, về 5 s sau 5 phút ổn định), nhật ký `logs/supervisor.log`.
- `scripts/service/install_autostart.ps1` (đăng ký/gỡ): **XAU-EDGE-V2-Service** (lúc đăng nhập, trễ 20 s, tự chạy lại khi lỗi) và **XAU-EDGE-V2-Watchdog** (mỗi 2 phút). Không cần quyền quản trị.
- **Bài kiểm chứng thật:** giết tiến trình dịch vụ (hard kill) ⇒ dịch vụ trả lời lại sau **12 giây** (lùi 10 s sau lần chết trước), CSDL toàn vẹn, độ phủ forward chỉ thêm đúng khoảng trống của đoạn chết.

### Cảnh báo Telegram, chỉ vận hành
- `ops/alerts.py`: vấn đề phải kéo dài ≥ **2 phút** mới báo; nhắc lại ≤ mỗi **giờ**; **một** tin "ổn định lại sau N phút" khi hết (chỉ nếu đã báo); cái tự hết trước khi báo thì im lặng; gửi lỗi thì **không tính là đã gửi**, thử lại ≤ mỗi phút và hiện ở `/health`; tin "đã khởi động" tối đa 1 lần/30 phút (vòng lặp khởi động lại không spam).
- Chỉ các kiểm tra sức khỏe có thể gây báo (kho dữ liệu, độ mới, quote, đĩa, vòng nền, CSDL, lệnh mở + dữ liệu cũ, bản sao); mô hình chưa triển khai, thiếu bản sao ngoài thiết bị và chính kênh cảnh báo **không bao giờ gọi điện**.
- **Nội dung không bao giờ có tín hiệu, giá, lãi/lỗ** (test dùng biểu thức chính quy cấm).
- Lỗi của khâu cảnh báo **không** tính vào engine (test).
- **Watchdog ngoài** (`scripts/external_watchdog.py`, thư viện chuẩn): vì bộ phát trong dịch vụ nằm trong vòng nền, nếu vòng nền hay cả tiến trình chết thì chỉ quan sát viên bên ngoài nói được. Báo sau **2 lần kiểm liên tiếp** hỏng (dịch vụ không phản hồi, HTTP lỗi, `DOWN`, vòng nền WARN/FAIL), nhắc hằng giờ, báo hồi phục (cả khi lần gửi hồi phục thất bại: thử lại lần sau). Phân biệt trạng thái bình thường (`DEGRADED` do mô hình chưa triển khai) với sự cố (test).
- **Bí mật:** token ở `.env` (git bỏ qua), kiểu `SecretStr`; không xuất hiện trong repr, nhật ký, lỗi, `/health` (test); lỗi gửi chỉ ghi mã (HTTP 401, loại ngoại lệ). Công cụ: `scripts/telegram_find_chat.py` (tìm chat id), `scripts/telegram_test.py` (gửi một tin kiểm tra).
- Tài liệu: `docs/ops/RUNBOOK.md` (vận hành, khôi phục, sự cố), ADR-V2-015.

## 3. Kiểm tra chất lượng

`ruff`, `mypy --strict` (50 file) sạch · **1.763 pytest đạt** (+36: 20 ops/alerts/mirror/health, 12 watchdog, 4 restore) · `/health` thật: tất cả OK trừ hai WARN đúng như nêu ở mục 1 và mô hình NOT_DEPLOYED.

## 4. Giới hạn (nói thẳng)

- **Chưa chứng minh được một tin Telegram thật tới tay bạn.** Mã gọi API đúng định dạng (kiểm với máy chủ giả, gồm từ chối, HTTP 401 và API không với tới), nhưng chưa có token/chat id nên chưa có tin nào đi ra ngoài. Đến lúc đó tôi sẽ chạy `telegram_test.py` và ghi kết quả.
- Mọi bản sao hiện nằm trên **một SSD**: hỏng ổ là mất sổ. Điều này đã hiện ở `/health`, không bị che.
- Tác vụ chạy **khi tài khoản đăng nhập**; chưa thử khởi động lại máy thật (tôi không khởi động lại máy của bạn); đã thử giết dịch vụ nhưng **chưa thử mất điện/khởi động máy**.
- Người giám sát không chạy lại nếu tiến trình **sống nhưng kẹt** (engine kẹt thì watchdog ngoài báo, nhưng không tự tháo kẹt).
- Khôi phục đã kiểm bằng test đơn vị trên bản sao trong thư mục tạm, **chưa** làm trên sổ thật (sẽ làm mất quan sát forward sau thời điểm bản sao).
- Cảnh báo không phủ collector của V1 khi dịch vụ V2 không chạy (watchdog ngoài chỉ nhìn V2).

## 5. Cần bạn (hai việc chỉ bạn làm được)

1. **Telegram:** tạo bot với @BotFather, gửi `/start`, tạo `.env` (mẫu `.env.example`) với `XAU_V2_TELEGRAM_BOT_TOKEN=...`; chạy `uv run python scripts/telegram_find_chat.py` lấy chat id, điền `XAU_V2_TELEGRAM_CHAT_ID=...`, rồi báo tôi để chạy `telegram_test.py` và khởi động lại dịch vụ. (Hoặc gửi cho tôi hai giá trị: token là bí mật, chỉ gửi nếu bạn thấy ổn.)
2. **Đích sao lưu ngoài thiết bị:** một trong: (a) ổ ngoài/USB/NAS (cho tôi đường dẫn), (b) đăng nhập và bật đồng bộ ứng dụng OneDrive rồi tôi trỏ tới một thư mục con (kiểm lại bằng cách đọc trạng thái đồng bộ), (c) tài khoản đám mây khác có công cụ dòng lệnh. Tôi không tự đẩy dữ liệu sổ lệnh lên dịch vụ nào của bạn khi chưa có chỉ định rõ.

## 6. Bước tiếp theo

G8.1 xong về phần mã/tự chạy/khôi phục; **hai mục WARN còn lại chờ bạn**. Theo trình tự bạn đặt, bước kế là **Human Decision Layer** rồi **M1 Execution Intelligence**. Tôi không có đủ đặc tả hai phần đó trong ngữ cảnh hiện tại (bản đặc tả dài ban đầu bị cắt), nên cần bạn xác nhận phạm vi ngắn gọn trước khi bắt đầu (xem câu hỏi ở cuối thông điệp).
