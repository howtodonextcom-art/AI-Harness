# Chạy bot 24/5 trên Windows VPS (NSSM)

Phạm vi: bot **DEMO** (dry-run theo mặc định, ADR-0019). Tài liệu này chỉ về hạ tầng vận hành; nó không
cho phép giao dịch live. Mọi lệnh dưới đây do chủ dự án chạy trên VPS; chưa có lệnh nào được chạy trong khi viết.

## 1. Kiến trúc dịch vụ

| Service | Lệnh (do `scripts/install_services.ps1` cấu hình) | Ghi chú |
|---|---|---|
| `xau-edge-bot` | `uv run --extra mt5 python scripts/demo_trader.py` | Một chu kỳ mỗi nến M15 đóng; khóa file chống chạy đôi |
| `xau-edge-api` | `uv run --extra api python scripts/serve_api.py --port 8000` | Chỉ bind `127.0.0.1` (cố định trong code) |
| Task Scheduler | `scripts/news_update.py --notify` hằng ngày; `scripts/check_health.py` mỗi 5 phút | Cảnh báo qua Telegram, xem `telegram-alerts.md` |

## 2. Chuẩn bị VPS

1. Windows Server 2022 / Windows 11, tối thiểu 2 vCPU, 4 GB RAM, ổ SSD. Múi giờ **UTC** hoặc giữ nguyên nhưng bot luôn dùng UTC nội bộ.
2. Tạo user Windows riêng, ví dụ `xauedge` (không dùng Administrator hằng ngày). Đặt mật khẩu mạnh, **không** dán vào chat/tài liệu.
3. Cài Git, `uv` (https://docs.astral.sh/uv/), NSSM (https://nssm.cc, đưa `nssm.exe` vào PATH), terminal MT5 của broker (FTMO).
4. Clone repo vào ví dụ `C:\xau-edge`, chạy `uv sync --extra mt5 --extra api`.
5. Tạo `.env` từ `.env.example` bằng trình soạn thảo trên VPS (mật khẩu/token chỉ nằm ở đó, không commit).
6. Kiểm tra kết nối bằng chính user dịch vụ: `uv run --extra mt5 python scripts/verify_mt5.py`.

## 3. Cài dịch vụ

```powershell
# xem trước, không thay đổi gì (không cần quyền admin, không cần NSSM)
.\scripts\install_services.ps1 -WhatIf
# cài thật (PowerShell chạy bằng Administrator); mặc định KHÔNG khởi động dịch vụ
.\scripts\install_services.ps1 -ServiceAccount ".\xauedge"
Start-Service xau-edge-bot, xau-edge-api
# gỡ (giữ lại log)
.\scripts\install_services.ps1 -Uninstall
```

Script idempotent: chạy lại sẽ áp lại toàn bộ cấu hình. Những gì nó đặt:

* **Start**: `SERVICE_DELAYED_AUTO_START` (khởi động sau khi mạng và các dịch vụ hệ thống đã lên).
* **Restart khi lỗi**: `AppExit Default Restart`, chờ `-RestartDelaySeconds` (mặc định 30 giây), `AppThrottle` 15 giây.
  Mọi lần thoát đều được khởi động lại; kill switch và lock được xử lý bên trong bot (bot thoát với mã khác 0
  khi lock còn giữ hoặc khi từ chối khởi động; NSSM sẽ thử lại, nên xem log nếu thấy vòng lặp khởi động).
* **Log**: `data\logs\bot.out.log`, `bot.err.log`, `api.*.log`, xoay vòng theo 10 MB hoặc 24 giờ (`AppRotateFiles/Online/Bytes/Seconds`).
  Log ứng dụng dạng JSON, đã che bí mật (`xau_edge.ops.logging_setup.setup_service_logging`, xem 8).
* **Dừng êm**: gửi Ctrl+C trước (`AppStopMethodConsole` 20 giây).
* **Tài khoản**: `-ServiceAccount` (+ `-ServicePassword` kiểu SecureString, hoặc để NSSM hỏi). Script cấp quyền Modify cho thư mục `data`.

> Giới hạn cần biết: dịch vụ Windows chạy ở session 0, không có desktop. Gói `MetaTrader5` kết nối terminal bằng
> IPC cục bộ và có thể tự mở `terminal64.exe` ở session của dịch vụ. Cách này **chưa được kiểm chứng trên máy thật**
> trong dự án. Nếu `verify_mt5.py` chạy được dưới user dịch vụ thì dùng được. Nếu không, phương án dự phòng:
> chạy bot bằng Task Scheduler "At log on" của user tự đăng nhập (mục 4) thay vì dịch vụ.

## 4. MT5 terminal tự đăng nhập trên VPS

1. Đăng nhập terminal một lần bằng tài khoản DEMO, tích **Save password** (mật khẩu được terminal lưu; bot chỉ dùng investor/trade password theo `.env`).
2. Terminal: `Tools > Options > Server` bật tự kết nối; `Expert Advisors` bật **Allow algorithmic trading** nếu cần (bot dùng API Python, không dùng EA).
3. Windows auto-logon cho user `xauedge` (Sysinternals `Autologon.exe`, mật khẩu được LSA mã hóa) để terminal và session luôn tồn tại sau reboot.
   Đặt terminal vào Startup của user đó (`shell:startup`, shortcut tới `terminal64.exe`).
4. Đặt `--terminal-path` của bot đúng đường dẫn terminal (mặc định trong `demo_trader.py`).
5. Chặn khóa màn hình/ngủ: `powercfg /change standby-timeout-ac 0`, `powercfg /change monitor-timeout-ac 0`.
6. Khi VPS bị ngắt RDP, đóng bằng **Disconnect** (không Sign out) để session còn nguyên.

## 5. Windows Update và reboot

* Đặt Active hours và tắt tự khởi động lại tức thời: Group Policy `Configure Automatic Updates` = 4 (tải tự động, cài theo lịch), `No auto-restart with logged on users` = Enabled.
* Cửa sổ bảo trì cố định: **cuối tuần**, sau khi thị trường đóng cửa (thứ Sáu 22:00 UTC đến Chủ nhật 22:00 UTC). Cài update và reboot trong khoảng đó; sau reboot dịch vụ tự lên (delayed auto start).
* Không cài update giữa phiên khi bot có vị thế. Sau mỗi reboot: `Get-Service xau-edge-*`, rồi `uv run python scripts/check_health.py`.
* Bot sau reboot phải qua reconcile trước khi gửi lệnh (đã có trong `execution/`); lock file cũ do crash xem `demo-trading.md` mục 6.

## 6. Tường lửa và mạng

* API chỉ lắng nghe `127.0.0.1:8000`; **không** mở cổng 8000 ra ngoài. Xác minh: `Get-NetTCPConnection -LocalPort 8000` phải cho `LocalAddress 127.0.0.1`.
* Chặn inbound mặc định (`Set-NetFirewallProfile -All -DefaultInboundAction Block`). Chỉ mở RDP nếu cần và giới hạn theo IP của bạn (`New-NetFirewallRule ... -RemoteAddress <ip của bạn>`), hoặc dùng VPN/Tailscale thay vì mở RDP ra Internet.
* Outbound cần: máy chủ broker (cổng do terminal dùng), `api.telegram.org:443`, NTP `udp/123`, nguồn lịch tin (nếu dùng URL).
* Đổi cổng RDP hoặc bật Network Level Authentication, khóa tài khoản sau nhiều lần sai.

## 7. Đồng bộ thời gian

* `w32tm /config /manualpeerlist:"time.windows.com pool.ntp.org" /syncfromflags:manual /update` rồi `Restart-Service w32time`; kiểm tra `w32tm /query /status`.
* Bot kiểm độc lập bằng SNTP: `xau_edge.ops.clock_check.check_clock()` trả độ lệch (giây) so với trung vị các máy chủ NTP.
  `clock_alert(result)` trả `CLOCK_DRIFT` (critical) khi lệch hơn 5 giây, và `CLOCK_UNVERIFIED` (warning) khi không máy chủ nào trả lời.
  Bên gọi (bot) phải chặn lệnh mới khi critical.

## 8. Logging

`xau_edge.ops.logging_setup.setup_service_logging("data/logs/xau_edge.log")` ghi **INFO** vào file xoay vòng (5 MB x 10)
bằng chính JSON formatter đã che bí mật của `observability.py`, và chỉ WARNING lên console (stderr, NSSM gom vào `bot.err.log`).
Thay cho `configure_logging("WARNING")` ở `demo_trader.py` (pre-mortem e5).

## 9. Raw store gọn và nhanh (T3.2)

Mỗi chu kỳ refresh ghi thêm một file Parquet nhỏ cho mỗi khung giờ; `DatasetCatalog.load` trước đây đọc và hash lại **mọi** file mỗi chu kỳ.

* `DatasetCatalog.load` giờ cache kết quả đã merge theo (tên, mtime, size) của mọi file Parquet và sidecar (cache cấp tiến trình, tối đa 32 mục). File đổi hoặc thêm file thì tự nạp lại và hash đầy đủ. `load(..., use_cache=False)` ép kiểm toàn vẹn đầy đủ.
* `scripts/compact_raw.py` gộp file nhỏ thành file theo tháng: ghi dataset mới (hash mới), **chứng minh** nội dung merge giống hệt, rồi **di chuyển** (không xóa) file cũ cùng sidecar sang `data/raw/_archive/<symbol>/<tf>/<compaction-id>/` kèm `manifest.json`. `dataset_id` đổi (vì nó băm danh sách hash file) nhưng nội dung bar y hệt; manifest ghi cả hai.
  Chạy lúc bot rảnh (cuối tuần): `uv run python scripts/compact_raw.py --dry-run`, rồi chạy thật.
* Archive có thể xóa tay sau khi bạn tự tin (ví dụ sau 30 ngày); công cụ không bao giờ xóa.

### Số đo độ trễ chu kỳ (`scripts/bench_cycle.py`)

BENCH_PLACEHOLDER

## 10. Checklist trước khi để chạy không người trực

- [ ] `verify_mt5.py` chạy được dưới user dịch vụ; terminal tự đăng nhập sau reboot.
- [ ] Telegram: tin thử đến điện thoại; `alerts.jsonl` ghi được khi rút mạng.
- [ ] `news_update.py` có nguồn thật và coverage > 7 ngày (nếu chưa: bot sẽ `NEWS_UNKNOWN` và chỉ `WAIT`).
- [ ] Đã thử: kill process bot, dịch vụ tự lên lại sau ~30 giây; reboot VPS, mọi thứ tự lên.
- [ ] `Get-NetTCPConnection -LocalPort 8000` chỉ thấy `127.0.0.1`.
- [ ] Đồng hồ: `check_clock()` lệch dưới 5 giây.
