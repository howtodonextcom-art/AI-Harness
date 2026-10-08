# Demo trading runbook

**Scope: an MT5 DEMO account only. No live trading exists or can be enabled (ADR-0018, ADR-0019).**
A bot that answers WAIT all day is working correctly: while no strategy has passed the pre-registered
validation, the evidence gate is closed and no order can be created.

## 1. Setup

1. Install and log in to the MT5 **demo** terminal (Windows). Note the terminal path.
2. `uv sync --extra mt5 --extra api`, `cp .env.example .env`, then fill `.env` (never commit it):
   `MT5_LOGIN`, `MT5_SERVER`, `MT5_BROKER_TIMEZONE`, `MT5_PASSWORD` (investor, read-only, used for data).
3. Check the data path works: `uv run --extra mt5 python scripts/demo_trader.py --once`.

## 2. Dry-run (default, sends nothing)

```powershell
uv run --extra mt5 python scripts/demo_trader.py            # one cycle per M15 close
uv run python scripts/serve_api.py                          # read-only API on 127.0.0.1:8000
cd apps/dashboard; npm run build; npm run start             # dashboard on http://localhost:3000
```

Set `XAU_EDGE_DEMO_MAGIC` (any integer). The dashboard "Demo bot" panel shows mode, account,
positions, reconciliation, alerts, recent decisions and the execution journal. Files live in
`data/execution/` (`cycles.jsonl`, `journal.jsonl`, `state.sqlite`, `status.json`, `heartbeat.json`).

## 3. Enable demo order sending (deliberate, explicit)

All of these are required; otherwise the bot stays in dry-run:

```
XAU_EDGE_ENABLE_DEMO_TRADING=true
XAU_EDGE_DEMO_DRY_RUN=false
XAU_EDGE_DEMO_ALLOWED_ACCOUNTS=<your demo login>
XAU_EDGE_DEMO_MAGIC=<integer>
XAU_EDGE_DEMO_MAX_LOTS=<small>            XAU_EDGE_DEMO_MAX_ORDERS_PER_DAY=<small>
XAU_EDGE_DEMO_INITIAL_CAPITAL=<challenge size>
MT5_TRADE_PASSWORD=<trading password>     (a different variable from the investor password)
```

Orders additionally need: a BUY/SELL signal (evidence gate open, news known and clear), the signal
bridge's approval, a clean reconciliation, a clear kill switch, a fresh price, one bot position at
most. Check the FTMO terms on automated trading yourself before enabling this.

## 4. Pipeline smoke test (optional, one order)

Tests the plumbing with ONE minimum-lot labelled order, closed at once. It is not evidence about
any strategy. Needs the settings of section 3 plus `XAU_EDGE_DEMO_SMOKE=true`:

```powershell
uv run --extra mt5 python scripts/smoke_demo_order.py --yes-send-one-demo-order
```

## 5. Kill switch

```powershell
uv run python scripts/kill_switch.py status
uv run python scripts/kill_switch.py trip --reason "why"
uv run python scripts/kill_switch.py reset --confirm "I understand the risk"
```

A tripped switch blocks NEW orders only. It does not close positions; closing is a separate, manual
decision (the bot closes only its own positions, at `max_hold_until`). It survives restarts and trips by
itself on: reconciliation mismatch, unknown order state, protective levels missing.

## 6. Health and recovery

* `uv run python scripts/check_health.py` exits 1 on any critical alert (stale heartbeat, tripped
  kill switch, dirty reconciliation, unreachable terminal). Run it from Task Scheduler.
* After a crash: check the state with `scripts/kill_switch.py status` and `data/execution/journal.jsonl`.
  Restarting is safe: signals already acted on and orders already sent are remembered. A submission
  with no final outcome (`UNRESOLVED_SUBMISSION`) keeps the bot stopped until you inspect the terminal.
* Orphan position (bot lost track of an order): close it by hand in the terminal, then clear the kill
  switch. The bot never touches positions it does not own.
* A stale lock (`data/execution/demo_trader.lock`): delete it only if no bot process is running.

## 7. Do not run when

The account is not DEMO or not whitelisted, the clock or data are stale, the economic calendar is
missing (signals stay WAIT anyway), you have manual positions on XAUUSD (reconciliation will stop the
bot), or the FTMO rules for automation are unverified.

## 8. Incident checklist

1. `kill_switch.py trip`; 2. read `journal.jsonl` and the dashboard alerts; 3. compare the terminal's
positions with `status.json`; 4. fix by hand in the terminal; 5. record what happened; 6. reset only
when reconciliation is clean.

## 9. Vận hành từ web (trang "Điều khiển", ADR-0023)

Trang `http://127.0.0.1:3000/control` cho phép chủ dự án kiểm tra điều kiện, bật/tắt bot, chuyển
DRY-RUN ↔ DEMO, chạy smoke test và đóng khẩn cấp vị thế của bot mà không cần gõ lệnh. Web **không**
nới bất kỳ gate nào: evidence gate, risk gate, news guard, kill switch, reconciliation và luật FTMO vẫn
quyết định y như khi chạy CLI. Khi chưa có chiến lược VALIDATED, bot vẫn trả WAIT cả ngày; đó là đúng.

### Bật

1. Trong `.env` thêm `XAU_EDGE_WEB_CONTROL=true` (mặc định `false`: không có route `/control` nào).
   Cờ này chỉ mở trang điều khiển; nó **không** bật demo hay funded.
2. Chạy API (cần cả extra `mt5` để preflight và bot dùng được terminal):

   ```powershell
   uv run --extra api --extra mt5 python scripts/serve_api.py --terminal-path "C:\Program Files\FTMO MetaTrader 5\terminal64.exe"
   ```

   Khi bật, API sinh token ngẫu nhiên vào `data/execution/control_token` (chỉ user hiện tại đọc được)
   và in `Web control plane ON`.
3. Chạy dashboard **trên cổng 3000** (API chỉ nhận `Origin` `http://localhost:3000` hoặc
   `http://127.0.0.1:3000`):

   ```powershell
   cd apps/dashboard; npm run build; npx next start -p 3000 -H 127.0.0.1
   ```

   Server Next.js đọc token từ file (mặc định `../../data/execution/control_token`, đổi bằng
   `XAU_EDGE_CONTROL_TOKEN_FILE`) và tự gắn vào yêu cầu gửi API. Token không bao giờ nằm trong
   JavaScript của trình duyệt; không có biến `NEXT_PUBLIC_` nào cho nó.

Bảo vệ: chỉ `127.0.0.1`; API kiểm Host, token, Origin, `Content-Type: application/json`, giới hạn 20
POST/phút; mỗi hành động có `Idempotency-Key` (bấm lặp không chạy hai lần) và được ghi vào
`data/execution/journal.jsonl` với `source="web"` (sự kiện `control.*`).

### Quy trình lần đầu

1. **Preflight**: bấm "Chạy lại preflight". Mỗi dòng OK / CẢNH BÁO / LỖI / CHƯA RÕ kèm cách sửa. Các nút bị
   khoá sẽ ghi rõ lý do (ví dụ `ENV_DEMO_DISABLED`, `NO_TRADE_PASSWORD`).
2. **Khởi động DRY-RUN**: thẻ Bot → "Khởi động". Bot chạy như tiến trình con của API (hoặc dịch vụ NSSM nếu
   đã cài). Theo dõi trạng thái và nhật ký thực thi ở cuối trang.
3. **Chuyển sang DEMO** (chỉ khi preflight không còn lỗi chặn demo): thẻ Chế độ → "Chuyển sang DEMO", xác
   nhận hai bước rồi gõ đúng `DEMO`. Web dừng bot, ghi `data/execution/runtime_mode.json`, khởi động lại
   và chỉ báo thành công khi `status.json` xác nhận chế độ DEMO. Nếu bị từ chối, bot quay lại chế độ cũ.
4. **Smoke test** (tuỳ chọn): gõ `SMOKE`. Một lệnh BUY 0.01 lot, giữ vài giây rồi đóng, đối soát. Tối đa
   1 lần / 10 phút và 5 lần / ngày (theo ngày Prague); bị chặn khi có tin, ngoài khung FTMO, hoặc khi bot đang
   có vị thế. Cần `XAU_EDGE_DEMO_SMOKE=true`. Kết quả **không phải bằng chứng edge**.
5. **Theo dõi**: banner trên cùng (tài khoản, chế độ, kill switch, chiến lược), thẻ Bot, nhật ký.

### Đóng khẩn cấp (FLATTEN)

Gõ `FLATTEN`. Thứ tự: bật kill switch `WEB_FLATTEN` → dừng bot → đóng mọi vị thế mang magic của bot →
đối soát. Vị thế mở tay **không bị đụng**; trang sẽ nhắc đóng chúng trong terminal. Bot **không** tự khởi
động lại. Muốn chạy tiếp, kiểm tra terminal rồi reset kill switch bằng CLI:

```powershell
uv run python scripts/kill_switch.py reset --confirm "I understand the risk"
```

### Vẫn phải làm bằng CLI / tay

* Sửa `.env` (cờ demo, whitelist, magic, vốn, mật khẩu giao dịch `MT5_TRADE_PASSWORD`). Web không đọc
  hay hiển thị secret.
* Reset kill switch (`scripts/kill_switch.py reset`).
* Chế độ FUNDED (web chỉ có DRY-RUN và DEMO; xem `go-live-checklist.md`).
* Cài/đổi dịch vụ NSSM. Nếu bot chạy dưới NSSM, chế độ DEMO cần cài dịch vụ với `-ConfirmMode DEMO`
  (`.\scripts\install_services.ps1 -ServiceAccount ".\xauedge" -ConfirmMode DEMO -StartNow`); web không
  sửa tham số dịch vụ, chỉ start/stop.
* Cập nhật lịch tin (`scripts/news_update.py`).

## Known limits

Fill prices on demo are not live fills; swap, slippage and commission are measured on demo and
approximate. The bridge, executor and reconciliation are tested against a fake terminal; the real
`order_send` path has not yet been exercised (it needs `MT5_TRADE_PASSWORD`).
