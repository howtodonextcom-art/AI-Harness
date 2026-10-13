# Vận hành XAU EDGE v2 (PAPER)

Cập nhật 2026-10-13 · Không có đường gửi lệnh tới broker; mọi thứ ở đây chỉ nói về dịch vụ và sổ PAPER.

## Thành phần đang chạy

| Thành phần | Cách chạy | Ghi chú |
|---|---|---|
| Dịch vụ V2 (`http://127.0.0.1:8200`) | tác vụ **XAU-EDGE-V2-Service** (Task Scheduler, lúc đăng nhập) chạy `scripts/service/run_v2.ps1` (người giám sát) | tự chạy lại sau sự cố: 5 s, gấp đôi tới 2 phút nếu chết liên tục, về 5 s sau 5 phút ổn định |
| Watchdog ngoài | tác vụ **XAU-EDGE-V2-Watchdog**, mỗi 2 phút, `pythonw scripts/external_watchdog.py` (chỉ dùng thư viện chuẩn) | báo khi dịch vụ chết/không phản hồi/DOWN/vòng nền hỏng (cần Telegram) |
| Collector dữ liệu | của V1 (không thuộc V2) | V2 chỉ đọc; nếu dừng, `/health` báo độ mới dữ liệu cũ |

Giới hạn: hai tác vụ chạy khi **tài khoản này đang đăng nhập** (không cần quyền quản trị, nhưng không chạy trên máy chưa ai đăng nhập).

## Lệnh hay dùng (PowerShell, trong `xau-edge-v2`)

```powershell
Get-ScheduledTask XAU-EDGE-V2-* | Get-ScheduledTaskInfo      # trạng thái tác vụ
Get-Content logs\supervisor.log -Tail 20                       # nhật ký người giám sát
Get-Content logs\external_watchdog.log -Tail 20                # nhật ký watchdog ngoài
(Invoke-RestMethod http://127.0.0.1:8200/api/v2/health).checks # sức khỏe từng phần
Stop-ScheduledTask XAU-EDGE-V2-Service                         # dừng người giám sát (rồi dừng tiến trình python trên cổng 8200)
Start-ScheduledTask XAU-EDGE-V2-Service                        # chạy lại
.\scripts\service\install_autostart.ps1                        # (cài lại) đăng ký hai tác vụ
.\scripts\service\install_autostart.ps1 -Remove                # gỡ hai tác vụ
```

Sau khi sửa mã Python hoặc build lại giao diện: dừng tiến trình python trên cổng 8200; người giám sát tự chạy lại bản mới.

## Sao lưu sổ PAPER

- Tệp sống: `data/paper.sqlite3`. Mỗi ngày UTC (và khi khởi động) có một bản sao trực tuyến nhất quán trong `data/backups/` (giữ 14 bản).
- **Bản sao thứ hai** (mặc định `D:/XAU-EDGE-V2-backups`) được chép và **kiểm byte-theo-byte + integrity_check** trước khi tính. Nếu nơi đó không truy cập được, thử lại mỗi 5 phút; `/health` mục `backup_mirror` báo WARN nếu quá 26 giờ.
- **Bản sao NGOÀI thiết bị**: đặt `XAU_V2_BACKUP_OFFDEVICE_DIR` (trong `.env`) tới ổ ngoài, NAS hoặc thư mục đám mây **đã đăng nhập và đang đồng bộ**. Cho tới khi đặt, `/health` mục `backup_offdevice` luôn WARN: "CHƯA CÓ". Hiện máy chỉ có **một SSD vật lý** chia ba phân vùng (C, D, Z), nên D: bảo vệ trước xóa nhầm/hỏng tệp, **không** bảo vệ trước hỏng ổ.

### Khôi phục

```powershell
Stop-ScheduledTask XAU-EDGE-V2-Service        # và dừng tiến trình python trên cổng 8200
uv run python scripts\restore_backup.py data\backups\paper-YYYYMMDD-HHMMSS.sqlite3          # chạy thử (không đổi gì)
uv run python scripts\restore_backup.py data\backups\paper-YYYYMMDD-HHMMSS.sqlite3 --yes    # khôi phục
Start-ScheduledTask XAU-EDGE-V2-Service
```

Công cụ kiểm bản sao trước, giữ tệp cũ thành `paper-before-restore-<utc>.sqlite3` (có thể hoàn tác), xóa `-wal/-shm` cũ, và từ chối nếu cổng vẫn trả lời. Phần quan sát/giao dịch **sau** thời điểm bản sao sẽ mất (độ phủ forward sẽ hiện khoảng trống).

## Cảnh báo Telegram (chỉ vận hành)

1. Telegram: nhắn `@BotFather` → `/newbot` → lấy **token**. Mở bot mới và gửi `/start`.
2. Tạo `.env` (sao từ `.env.example`), điền `XAU_V2_TELEGRAM_BOT_TOKEN=...`.
3. `uv run python scripts/telegram_find_chat.py` in ra **chat id**; điền `XAU_V2_TELEGRAM_CHAT_ID=...`.
4. `uv run python scripts/telegram_test.py` gửi một tin kiểm tra; khởi động lại dịch vụ để nạp `.env`.

Nội dung tin luôn là tình trạng dịch vụ (vòng nền, dữ liệu cũ, CSDL, sao lưu, dịch vụ không phản hồi), **không bao giờ** có tín hiệu, giá hay lãi/lỗ. Quy tắc: vấn đề phải kéo dài ≥ 2 phút mới báo; nhắc lại tối đa mỗi giờ; một tin "ổn định lại" khi hết; thất bại gửi được thử lại mỗi phút và hiện ở `/health` mục `alerts`. Token không bao giờ vào nhật ký, lỗi hay `/health`.

## Khi có sự cố

| Dấu hiệu | Việc làm |
|---|---|
| `engine_loop` WARN/FAIL | xem `logs\xau_edge_v2.jsonl` tìm `paper engine pass failed`; người giám sát không chạy lại nếu tiến trình vẫn sống: dừng tiến trình python trên cổng 8200 |
| `freshness`/`live` WARN khi thị trường mở | collector (V1) dừng hoặc MT5 đóng: mở lại; lệnh PAPER đang mở không được quản lý SL/TP khi không có nến mới |
| `paper_db` FAIL | **đừng** tiếp tục ghi: dừng dịch vụ, khôi phục từ bản sao gần nhất (mục trên) |
| `backup_mirror` WARN | kiểm tra ổ D: (dung lượng, quyền); sẽ tự bắt kịp khi truy cập lại |
| Không có Telegram | `/health` mục `alerts` cho biết thiếu cấu hình hay lỗi gửi (mã HTTP) |
