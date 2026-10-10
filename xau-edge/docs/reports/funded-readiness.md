# Mức sẵn sàng chạy bot trên tài khoản FTMO funded (T5.5)

Ngày: 2026-10-08. Theo prompt `prompts/26-10-08-21-05-master-v2-funded-bot.md`.

## Kết luận

**Chưa sẵn sàng bật funded.** Code của Track 2, 3, 4 đã xong và chỉ được kiểm bằng fake terminal. Track 1
kết thúc ở **(B) NO EDGE WITHIN BUDGET**:

> Không có edge được kiểm định; bot funded chỉ chạy ở chế độ UNVALIDATED theo override D2, rủi ro
> trần 0,25%/lệnh, tối đa bậc 2.

Các điều kiện bật funded (mục "Thứ tự và phụ thuộc" của prompt) hiện chưa đạt:

| Điều kiện | Trạng thái |
|---|---|
| Track 1 đạt (A), hoặc chủ dự án ký override D2 | ❌ (B); chưa ký override |
| Track 4 xong | ✅ code + test fake |
| T5.2 soak 14 ngày và T5.3 demo 4 tuần đạt | ❌ chưa chạy (cần thời gian thực) |
| D6 không còn luật `unverified` | ❌ 13 luật `must_verify` chưa xác minh trong `configs/prop/ftmo_funded.yaml` |
| Checklist `docs/operations/go-live-checklist.md` đã ký | ❌ |

Cờ `XAU_EDGE_ENABLE_FUNDED_TRADING` **vẫn tắt**. Repository này chưa gửi lệnh nào lên bất kỳ tài khoản nào.

## Bảng điểm theo track

| Track | Mục | Trạng thái | Commit |
|---|---|---|---|
| 1 Edge | T1.1 strategy registry | ✅ | `fbc45d1` |
| | T1.2 dữ liệu read-only, splits mới | ✅ | `a840fe7` |
| | T1.3 đăng ký trước H01–H06 | ✅ | `a840fe7` |
| | T1.4 thực nghiệm Dev → Val (Test không chạy vì không ai PASS Val) | ✅ | `eaffe46`, `d28a3d0`, `102a753` |
| | T1.5 prop filter Monte Carlo | ✅ (trên lựa chọn quy tắc 6: H03-c1.0) | `eaffe46`, `102a753` |
| | T1.6 `final-verdict.md` | ✅ (B) | `102a753` |
| 2 Thực thi | T2.1–T2.2, T2.4–T2.6, T2.9–T2.10 | ✅ | `e5362af` |
| | T2.3 (c4) | ✅ | `3ab4a6c`, `244d750` |
| | T2.7, T2.8, T2.13 | ✅ | `3ab4a6c` |
| | T2.11 (d5) | ✅ | `244d750` |
| | T2.12 guard luật FTMO, ngân sách request | ✅ | `3ab4a6c`, `244d750` |
| 3 Vận hành | T3.1 lịch tin | ✅ code + nguồn Forex Factory weekly (NEWS-01); 🟠 chưa có nguồn có SLA | `b511afd`, `e8e8fc3` |
| | T3.2 raw store | ✅ | `8d78120` |
| | T3.3 supervisor NSSM | ✅ code; 🟠 cần cài | `dde466c`, `244d750` |
| | T3.4 Telegram | ✅ code; 🟠 cần token | `ba8007f`, `dde466c` |
| | T3.5 log INFO, NTP | ✅ | `ba8007f` |
| | T3.6 tài liệu lệch code, `/risk/status` | ✅ | `6524313`, `244d750`, `01d4364`, lượt này |
| 4 Funded | T4.1 ADR-0020, identity, banner, `--confirm-mode` | ✅ | `2eb58b1`, `244d750` |
| | T4.2 `ftmo_funded.yaml` + khóa `must_verify` | ✅ | `2eb58b1` |
| | T4.3 rollout theo bậc | ✅ | `2eb58b1`, `244d750` |
| | T4.4 override D2, trần 0,25%, nhãn UNVALIDATED | ✅ | `3ab4a6c`, `244d750`, `01d4364` |
| | T4.5 dashboard, `status.json` | ✅ | `4bda4c3`, `6524313` |
| | T4.6 ma trận test | ✅ | `2eb58b1`, `244d750` |
| 5 Nghiệm thu | T5.1 Phase A–F | 🟠 Phase A (gate) đạt; B–F cần terminal + chủ dự án | — |
| | T5.2 soak 14 ngày | ❌ cần thời gian thực | — |
| | T5.3 demo 4 tuần | ❌ cần T5.1 Phase E + thời gian thực | — |
| | T5.4 go-live checklist | ✅ viết xong; ❌ chưa ký | lượt này |
| | T5.5 báo cáo này | ✅ | lượt này |

## Blocker còn lại và người xử lý

| # | Blocker | Ai làm | Cách làm |
|---|---|---|---|
| 1 | Không có edge (B) | Chủ dự án quyết định | Ký override D2 (checklist 3.1–3.2) hoặc dừng ở demo. Một chương trình nghiên cứu mới cần ngân sách giả thuyết mới, đăng ký trước, và vẫn không chạm holdout. |
| 2 | Chiến lược override H03-c1.0 chưa có bản live | Lượt code tiếp theo | `StrategySpec` cho H03-c1.0 trong `signals/strategy_registry.py`, ADR cho phép chạy UNVALIDATED, parity test giữa `strategies/edge_program.py` và signal engine. Không được đặt `XAU_EDGE_FUNDED_STRATEGY_ID=baseline_c`: quy tắc 6 của ledger đã chọn H03-c1.0 trước khi có kết quả. |
| 3 | 13 luật FTMO `must_verify` chưa xác minh (D6) | Chủ dự án | Đọc điều khoản funded hiện hành, hỏi support bằng văn bản, sửa `configs/prop/ftmo_funded.yaml` (`status: verified_official`, `verified_on`, `source`). |
| 4 | Định nghĩa "request" của FTMO | Chủ dự án | Hỏi support; bot giới hạn 900 trade request/ngày, lệnh đọc chỉ được đếm. |
| 5 | Mật khẩu demo từng lộ | Chủ dự án | Đổi master + investor password. |
| 6 | Trade password, smoke order (T5.1 Phase E) | Chủ dự án | Đặt `MT5_TRADE_PASSWORD` trong `.env`, tự chạy smoke (lệnh bên dưới). |
| 7 | Lịch tin: đã có nguồn Forex Factory weekly (NEWS-01, 2026-10-10) nhưng không chính thức, chỉ phủ tuần hiện tại, không có published/updated | Chủ dự án | Chấp nhận giới hạn cho PAPER, hoặc cấp nguồn có SLA (provider mới, định dạng PIT không đổi); xem `docs/reports/NEWS_SOURCE_DECISION.md`. |
| 8 | Telegram | Chủ dự án | Tạo bot với BotFather, điền `XAU_EDGE_TELEGRAM_BOT_TOKEN`, `XAU_EDGE_TELEGRAM_CHAT_ID`; xem `docs/operations/telegram-alerts.md`. |
| 9 | Soak 14 ngày, demo 4 tuần | Thời gian thực | Lịch bên dưới. |
| 10 | Tần suất lệnh thấp | Lưu ý kế hoạch | H03-c1.0 có 211 lệnh trong 8 năm Dev-H và 119 lệnh trong 3 năm Val-H (khoảng 26–40 lệnh/năm): bậc 1 (≥ 10 lệnh) có thể mất 3–5 tháng. |

## Lệnh chính xác cho operator

Chạy trong thư mục `xau-edge`, PowerShell, terminal MT5 đã đăng nhập. Không dán `.env` hay mật khẩu vào
chat. Mọi lệnh dưới đây do **chủ dự án** chạy.

### 0. Kiểm tra gate (Phase A)

```powershell
uv run ruff check .; uv run ruff format --check .; uv run mypy; uv run pytest -m "not mt5"
cd apps/dashboard; npm run build; cd ../..
```

### 1. Dry-run và soak 14 ngày (T5.2)

`.env`: `XAU_EDGE_ENABLE_DEMO_TRADING=false`, `XAU_EDGE_ENABLE_FUNDED_TRADING=false`,
`XAU_EDGE_NEWS_CALENDAR_PATH=<file lịch tin>`.

```powershell
uv run --extra mt5 python scripts/demo_trader.py --once          # một chu kỳ thử
.\scripts\install_services.ps1 -ServiceAccount ".\xauedge" -StartNow   # dịch vụ dry-run (không -ConfirmMode)
uv run python scripts/check_health.py                              # mỗi 5 phút qua Task Scheduler
uv run python scripts/news_update.py --notify                      # mỗi ngày qua Task Scheduler
```

Trong 14 ngày: rút mạng ít nhất 1 lần, khởi động lại terminal ít nhất 1 lần. Đạt khi uptime ≥ 99% số
bar M15, 0 bar trùng trong `data/execution/cycles.jsonl`, mọi sự cố tự hồi phục hoặc có cảnh báo.

### 2. Smoke order demo (T5.1 Phase E), một lần

`.env`: `XAU_EDGE_ENABLE_DEMO_TRADING=true`, `XAU_EDGE_DEMO_DRY_RUN=false`,
`XAU_EDGE_DEMO_ALLOWED_ACCOUNTS`, `XAU_EDGE_DEMO_ALLOWED_SERVERS`, `XAU_EDGE_DEMO_MAGIC`,
`XAU_EDGE_DEMO_INITIAL_CAPITAL`, `MT5_TRADE_PASSWORD` (chủ dự án tự nhập).

```powershell
uv run --extra mt5 python scripts/smoke_demo_order.py --yes-send-one-demo-order
```

### 3. Demo có lệnh từ tín hiệu ≥ 4 tuần (T5.3)

```powershell
.\scripts\install_services.ps1 -Uninstall
.\scripts\install_services.ps1 -ServiceAccount ".\xauedge" -ConfirmMode DEMO -StartNow
```

Đạt khi tỷ lệ reject/UNKNOWN < 2%; cập nhật slippage/commission thật vào ADR-0015. Lưu ý: khi chưa có
chiến lược VALIDATED, evidence gate giữ mọi tín hiệu ở `WAIT` trên demo (override D2 chỉ có ở funded).

### 4. Funded, từng bậc (chỉ sau khi checklist đã ký)

`.env`: `XAU_EDGE_ENABLE_DEMO_TRADING=false`, `XAU_EDGE_ENABLE_FUNDED_TRADING=true`,
`XAU_EDGE_FUNDED_ALLOWED_ACCOUNTS`, `XAU_EDGE_FUNDED_ALLOWED_SERVERS`, `XAU_EDGE_FUNDED_MAGIC`,
`XAU_EDGE_FUNDED_INITIAL_CAPITAL`; nếu ký override D2: `XAU_EDGE_FUNDED_ALLOW_UNVALIDATED=true`,
`XAU_EDGE_FUNDED_STRATEGY_ID=H03-c1.0` (chỉ có tác dụng sau khi blocker 2 được làm).

```powershell
uv run --extra mt5 python scripts/demo_trader.py --once --confirm-mode FUNDED   # kiểm banner + D6
uv run python scripts/rollout.py status
.\scripts\install_services.ps1 -Uninstall
.\scripts\install_services.ps1 -ServiceAccount ".\xauedge" -ConfirmMode FUNDED -StartNow
```

| Bậc | Hành vi | Tiêu chí lên bậc (tự kiểm) | Lệnh lên bậc |
|---|---|---|---|
| 0 shadow | sinh intent + `order_check`, **không gửi lệnh** | ≥ 5 ngày giao dịch | `uv run python scripts/rollout.py promote --confirm`, rồi `Restart-Service xau-edge-bot` |
| 1 | lot 0.01 | ≥ 10 lệnh, 0 reject/UNKNOWN | như trên |
| 2 | rủi ro 0,25%/lệnh | ≥ 4 tuần | UNVALIDATED **dừng vĩnh viễn ở bậc 2** |
| 3 | chỉ chiến lược VALIDATED, rủi ro theo T1.5 | — | — |

Dừng khẩn cấp: `uv run python scripts/kill_switch.py trip --reason "manual stop"` (theo đúng state
funded khi mode funded bật). Kill switch chặn lệnh mới, không đóng vị thế; auto-flatten chỉ chạy khi
cách sàn daily/max loss ≤ 1% (ADR-0020 D5).

## Lịch chạy đề xuất

| Giai đoạn | Sớm nhất bắt đầu | Thời lượng tối thiểu | Điều kiện vào |
|---|---|---|---|
| Việc của chủ dự án (blocker 3–8) | ngay | vài ngày (chờ FTMO trả lời) | — |
| Soak dry-run (T5.2) | khi có lịch tin + Telegram + dịch vụ | 14 ngày | Phase A–D đạt |
| Smoke demo (T5.1 Phase E) | song song soak | 1 lần | trade password đã đặt |
| Demo 4 tuần (T5.3) | sau soak | 4 tuần | soak + smoke đạt |
| Funded bậc 0 | sau T5.3 + checklist ký + D6 xác minh | ≥ 5 ngày giao dịch | — |
| Funded bậc 1 → 2 | theo tiêu chí bậc | ≥ 10 lệnh, rồi ≥ 4 tuần | — |

Tính từ hôm nay, funded bậc 0 sớm nhất khoảng 7–8 tuần nữa nếu mọi việc của chủ dự án xong trong tuần đầu.
