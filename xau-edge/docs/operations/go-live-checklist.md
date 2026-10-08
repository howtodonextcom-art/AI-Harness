# Checklist go-live tài khoản FTMO funded (T5.4)

Chủ dự án ký từng mục (ghi ngày + chữ ký/viết tắt). **Chưa ký đủ thì không đặt
`XAU_EDGE_ENABLE_FUNDED_TRADING=true`.** AI agent không ký, không bật cờ, không nhập mật khẩu thay chủ
dự án. Code đã tự chặn các mục có thể kiểm tra bằng máy (cột "Code chặn"); phần còn lại chỉ con người
xác nhận được.

Trạng thái lúc viết (2026-10-08): **chưa mục nào được ký**. Cờ funded tắt.

## 1. Luật FTMO (D6)

| # | Mục | Cách kiểm | Code chặn | Ký |
|---|---|---|---|---|
| 1.1 | Mọi luật `must_verify: true` trong `configs/prop/ftmo_funded.yaml` đã được xác minh bằng văn bản (trang điều khoản FTMO hiện hành hoặc email support), điền `status: verified_official`, `verified_on`, `source` | Đọc từng luật; lưu bản PDF/email vào nơi riêng (không commit thông tin tài khoản) | Có: bot thoát mã 3 khi còn luật chưa xác minh | |
| 1.2 | FTMO xác nhận EA/bot tự động được phép trên tài khoản funded và bot này không bị xếp vào "AI tool" bị cấm | Email support | Có (qua 1.1) | |
| 1.3 | FTMO xác nhận định nghĩa "request" và giới hạn/ngày; bot giới hạn cứng 900 trade request (`order_check` + `order_send`) mỗi ngày Prague, các lệnh đọc chỉ được đếm | Email support; nếu FTMO tính cả lệnh đọc thì phải sửa ngân sách trước khi chạy | Một phần (ngân sách 900) | |
| 1.4 | Cửa sổ tin tức, giữ lệnh qua đêm/cuối tuần, hedging khớp với cấu hình guard | So `ftmo_funded.yaml` với điều khoản | Một phần | |

## 2. Bảo mật và tài khoản

| # | Mục | Cách kiểm | Code chặn | Ký |
|---|---|---|---|---|
| 2.1 | Mật khẩu demo từng bị lộ trong chat đã được đổi (cả master và investor) | Đổi trong FTMO Client Area / MT5 | Không | |
| 2.2 | `.env` chỉ có trên máy chạy bot, không commit, không gửi qua chat; `MT5_TRADE_PASSWORD` do chủ dự án tự nhập | `git status` không thấy `.env`; hook pre-commit chặn `.env` | Có (hook) | |
| 2.3 | `XAU_EDGE_FUNDED_ALLOWED_ACCOUNTS` chỉ chứa login funded đúng; `XAU_EDGE_FUNDED_ALLOWED_SERVERS` đúng server funded; không trùng whitelist demo | So với FTMO Client Area; banner khởi động in 3 số cuối login và server | Có: whitelist trùng → `Settings` báo lỗi; login/server lạ → thoát mã 3 | |
| 2.4 | `XAU_EDGE_FUNDED_MAGIC` khác magic demo; `XAU_EDGE_FUNDED_INITIAL_CAPITAL` = vốn ban đầu thật của tài khoản funded | Đọc `.env` (không dán ra ngoài) | Có: thiếu → `Settings` báo lỗi | |

## 3. Chiến lược và rủi ro (D2)

| # | Mục | Cách kiểm | Code chặn | Ký |
|---|---|---|---|---|
| 3.1 | Track 1 kết thúc ở (A) **hoặc** chủ dự án ký chấp nhận override D2 | `docs/research/edge-program/final-verdict.md` hiện là **(B)** | Có: không VALIDATED và không override → không lệnh nào | |
| 3.2 | Nếu ký override D2: đã đọc và chấp nhận rằng "Không có edge được kiểm định; bot funded chỉ chạy ở chế độ UNVALIDATED theo override D2, rủi ro trần 0,25%/lệnh, tối đa bậc 2", và chiến lược được chọn (H03-c1.0) có **mean net R bi quan âm** ở cả Dev-H và Val-H | Đọc `final-verdict.md` | Có: trần 0,25% và bậc 2 là hằng số trong code | |
| 3.3 | Chiến lược override có bản live trong strategy registry, ADR và parity test với bản nghiên cứu | Hiện **chưa có** (chỉ `baseline_c`) | Có: `strategy_id` không khớp → override không mở | |

## 4. Nghiệm thu thời gian thực

| # | Mục | Tiêu chí | Code chặn | Ký |
|---|---|---|---|---|
| 4.1 | Phase A–F của `prompts/26-10-08-20-31-demo-bot-final-activation.md` đạt (gồm 1 smoke order demo do chủ dự án tự chạy) | Theo prompt | Không | |
| 4.2 | Soak dry-run ≥ 14 ngày (T5.2), có ≥ 1 lần ngắt mạng và ≥ 1 lần restart terminal | Uptime ≥ 99% số bar M15; 0 bar trùng; mọi sự cố tự hồi phục hoặc đã cảnh báo | Không | |
| 4.3 | Demo có lệnh từ tín hiệu ≥ 4 tuần (T5.3) | Tỷ lệ reject/UNKNOWN < 2%; chi phí thật cập nhật vào ADR-0015 | Không | |
| 4.4 | Lịch tin có nguồn thật, coverage > 7 ngày, job hằng ngày chạy | `uv run python scripts/news_update.py --check-only --notify` | Có: thiếu lịch → `NEWS_UNKNOWN` → `WAIT` | |

## 5. Vận hành

| # | Mục | Cách kiểm | Code chặn | Ký |
|---|---|---|---|---|
| 5.1 | Đã nhận cảnh báo Telegram thử trên điện thoại | `docs/operations/telegram-alerts.md` | Không | |
| 5.2 | Dịch vụ NSSM tự khởi động lại; MT5 tự đăng nhập sau reboot | `docs/operations/vps-setup.md` | Không | |
| 5.3 | Biết cách trip kill switch bằng tay và đọc dashboard | `uv run python scripts/kill_switch.py --help`; dashboard hiện mode FUNDED, nhãn UNVALIDATED, bậc, khoảng cách sàn | Không | |
| 5.4 | Bắt đầu ở bậc 0 (shadow) và chỉ lên bậc bằng `scripts/rollout.py promote --confirm` khi đủ tiêu chí | `uv run python scripts/rollout.py status` | Có: bậc tự kiểm tiêu chí | |

## Ký xác nhận cuối

Tôi đã kiểm tra mọi mục trên và chấp nhận rủi ro mất tài khoản funded.

Chủ dự án: ____________________ Ngày: ______________
