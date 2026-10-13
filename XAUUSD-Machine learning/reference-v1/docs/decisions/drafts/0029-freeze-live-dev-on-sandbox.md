# ADR-0029 (NHÁP): Freeze-LIVE — stack live chỉ để quan sát; phát triển chạy trên sandbox

Status: **SUPERSEDED** as the working copy — accepted text is `docs/decisions/0029-freeze-live.md` (2026-10-11). Draft kept for the closed-loop rationale.

## Bối cảnh (đã kiểm)
- Độ phủ quyết định 48,6% (232/477), hai khoảng thiếu 30 và 215 phút (`/trade/decision` → `decision_coverage`; `trading/coverage.py`, `COVERAGE_OK_PCT=95`).
- Nguyên nhân theo `data/logs/api.log`: (1) restart tay trong sprint dev; (2) `SUPERVISOR child exited code=1073807364` (0x40010004, DBG_TERMINATE_PROCESS: console bị đóng) và supervisor chết theo, không có gì khởi động lại tới khi chạy tay. Khoảng 20 lần khởi động supervisor bằng tay trong sprint.
- Task Scheduler **đã đăng ký**: tên `XAU-EDGE Market Stack`, Enabled, Interactive, At logon, Last Run 2026-10-11 08:45:40, Last Result 0 (đo lúc ghi ADR). Script: `scripts/install_market_autostart.ps1` (`RestartCount 3`, `RestartInterval` 1 phút). NSSM/`install_services.ps1` **không** dùng cho market stack (MT5 là GUI, Session 0 không ổn — `docs/operations/market-data-operations.md:18-21`).
- Engine không ghi bù quyết định đã bỏ lỡ, và điều đó là đúng (không bịa dữ liệu). Vì vậy forward evidence chỉ tích luỹ khi stack chạy liên tục.

## Quyết định
1. **Stack live (:8000 / :3000) chỉ để quan sát.** Không build vào `apps/dashboard/.next`, không restart, không chạy thử trên stack live trong giờ thị trường mở. Mọi thử nghiệm dùng sandbox `scripts/serve_acceptance.py --port 8100` + `next start -p 3200` với thư mục trade tạm.
2. **Cửa sổ triển khai:** chỉ khi thị trường đóng (cuối tuần, hoặc ngoài phiên theo `market_data/calendars.py`), có ghi lại lý do restart.
3. **Supervisor tự hồi phục bằng Task Scheduler, không NSSM** (chủ dự án chọn 2026-10-11): không cài phần mềm thứ ba; đủ để sống sót khi đóng console / restart máy; Windows có restart-on-failure. Task đã có (`XAU-EDGE Market Stack`, đo 2026-10-11: Enabled/Ready, Last Result 0). NSSM **không** ôm market stack và **không** bind API/bot ở sprint này. **Hạn chế đã kiểm:** Task Scheduler chỉ khởi động lại *tác vụ khởi động* (`start_market_stack.ps1`) khi *nó* thoát lỗi — không trông một supervisor bạn mở tay từ console. Gap 215′ xảy ra vì stack chạy từ console rồi bị kill (DBG_TERMINATE_PROCESS), không phải vì thiếu task. Cách dùng đúng: chỉ `start_market_stack.ps1` / task; không mở `run_market_stack.py` trong cửa sổ.
   - **NSSM portable sẵn, chưa bind:** `nssm.exe` local tại `%LOCALAPPDATA%\xau-edge\nssm\nssm-2.24\win64\nssm.exe` (không system-wide). `install_services.ps1 -WhatIf -SkipApi -SkipBot` đã chạy (`%TEMP%\xau_nssm\whatif.txt`): WhatIf sạch; cả hai skip nên không đăng ký `xau-edge-api` / `xau-edge-bot` (API live đã do supervisor trên :8000; bot không có edge). `Get-Service xau-edge-*` = không có. Không `-StartNow`, không `-ConfirmMode`, không đọc `.env`. Bind API/bot là việc sau, khi có edge và cổng 8000 trống.
4. **Cảnh báo / SLA:** không đặt ngưỡng gap mới trong sprint audit. Phân phối khoảng chết đã quan sát gồm 30′ (restart tay) và 215′ (supervisor chết theo console). Chủ chọn SLA; agent không ship alert 2 phút.
5. **Báo cáo độ phủ theo phiên** chỉ viết sau khi uptime hết là nguyên nhân (dịch vụ đã chạy). 95% là cổng evidence **đã có** (`trading/coverage.py`), không phải DoD sprint 14 ngày.

## Acceptance criteria
- AC-F1 **Must:** chủ diễn tập kill supervisor và ghi thời gian tự lên lại (SLA do chủ chọn; agent không đặt ≤ 60 s). ~20 lần start tay trong sprint WORKSTATION: **Giả thuyết – chưa xác minh** (không đếm lại `api.log` trong audit này).
- AC-F2 **Must not:** agent đặt ngưỡng gap mới (kể cả 2 phút) trước khi chủ chọn SLA.
- AC-F3 Cổng evidence **đã có** 95% (`coverage.py`) vẫn dùng khi đánh giá forward; không biến thành DoD sprint 14 ngày.
- AC-F4 **Must not:** back-fill quyết định.

## Hệ quả
Dev chậm hơn một chút (phải dựng sandbox), đổi lại forward evidence được tích luỹ. Freeze-LIVE không thay đổi guard nào.
