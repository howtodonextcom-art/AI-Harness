# Prompt: Demo Bot Final Activation & Operational Verification

Bạn là **Principal Trading Systems Engineer, MT5 Demo Execution Engineer, Risk/Safety Engineer, DevOps Operator và QA Lead**.

Bạn đang làm việc trong repo:

`xau-edge/`

Mục tiêu: **đưa XAU EDGE vào trạng thái vận hành demo hoàn chỉnh nhất có thể**, dựa trên báo cáo:

`docs/reports/demo-bot-status.md`

Hệ thống đã có demo bot, dashboard, MT5 demo adapter, reconciliation, journal, heartbeat, status, smoke script và CI xanh. Nhiệm vụ của bạn là **kiểm tra, hoàn thiện các mảnh còn thiếu, chạy các bước preflight và chuẩn bị bot chạy như một ứng dụng demo thực tế**, nhưng **không được hạ safety/evidence gate**.

---

## 0. Giới hạn bắt buộc

Không được:

- Bật live trading.
- Bỏ evidence gate.
- Bỏ risk gate.
- Bỏ news guard.
- Bỏ kill switch.
- Bỏ reconciliation.
- Ép bot vào lệnh khi signal là `WAIT`.
- Hard-code secrets.
- In `.env`, password, account number.
- Claim profitability.
- Tạo lệnh thật nếu terminal vẫn đang dùng investor password.
- Vượt qua `TRADING_NOT_ALLOWED` bằng code.
- Tắt safety test để pass.

Được phép:

- Hoàn thiện vận hành demo.
- Kiểm tra cấu hình demo.
- Chạy preflight.
- Chạy dry-run.
- Chạy smoke demo order **chỉ khi operator đã cấu hình rõ**.
- Tạo checklist để user tự điền `MT5_TRADE_PASSWORD`.
- Kiểm tra dashboard/API/status/journal.
- Tạo báo cáo vận hành cuối.

---

## 1. Đọc trước khi làm

Đọc kỹ:

1. `docs/reports/demo-bot-status.md`
2. `docs/reports/gap-audit.md`
3. `docs/operations/demo-trading.md`
4. `docs/architecture/demo-execution.md`
5. `docs/risk/demo-execution-risk.md`
6. `docs/decisions/0019-demo-execution-scope.md`
7. `.env.example`
8. `src/xau_edge/config.py`
9. `scripts/smoke_demo_order.py`
10. `scripts/check_health.py`
11. `scripts/kill_switch.py`
12. `scripts/demo_trader.py`
13. `apps/dashboard/`
14. `src/xau_edge/brokers/mt5_demo/`
15. `src/xau_edge/execution/`

Không bắt đầu sửa code nếu chưa hiểu báo cáo hiện tại.

---

## 2. Mục tiêu thực tế

Đưa hệ thống tới trạng thái:

- Web app chạy được.
- API chạy được.
- Dashboard hiển thị panel Demo bot.
- Bot runner chạy được ở dry-run.
- MT5 demo terminal kết nối được.
- Reconciliation sạch.
- Journal ghi được.
- Heartbeat/status ghi được.
- Health check chạy được.
- Smoke order path được kiểm tra.
- Nếu operator cung cấp `MT5_TRADE_PASSWORD` và bật đúng flags, smoke demo order có thể chạy.
- Nếu không có edge hoặc không có news calendar, bot tiếp tục `WAIT` và đó là đúng.

---

## 3. Nhiệm vụ cụ thể

### Phase A: Repo & CI Verification

Chạy:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -m "not mt5"
```

Nếu dashboard liên quan:

```powershell
cd apps/dashboard
npm run build
```

Kết quả phải được ghi lại.

### Phase B: Operational Preflight

Kiểm tra nhưng không in secrets:

- `.env` có tồn tại không.
- `XAU_EDGE_ENABLE_LIVE_TRADING=false`.
- `XAU_EDGE_ENABLE_DEMO_TRADING=true` nếu muốn vận hành demo.
- `XAU_EDGE_DEMO_DRY_RUN=true` cho dry-run.
- Nếu muốn smoke order thật:
  - `XAU_EDGE_DEMO_DRY_RUN=false`
  - `MT5_TRADE_PASSWORD` tồn tại
  - account nằm trong whitelist
  - symbol nằm trong whitelist
  - magic number có cấu hình
- `XAU_EDGE_NEWS_CALENDAR_PATH` có tồn tại không.
- News calendar file có dòng coverage hợp lệ không.
- State path, journal path, heartbeat/status path ghi được không.
- Kill switch có đang tripped không.
- Terminal MT5 có đang login demo không.
- Terminal có cho trading không.

Nếu thiếu điều kiện, không sửa bằng cách bỏ guard. Báo rõ thiếu gì.

### Phase C: Dry-run Bot Operation

Chạy bot ở dry-run theo runbook.

Yêu cầu:

- Chạy ít nhất vài chu kỳ hoặc theo thời lượng cấu hình an toàn.
- Không duplicate decision bar.
- Journal ghi quyết định.
- Heartbeat cập nhật.
- `status.json` cập nhật.
- Reconciliation sạch.
- Nếu signal là `WAIT`, không gửi lệnh.

Nếu không thể chạy lâu, ghi rõ lý do và command để operator chạy tiếp.

### Phase D: Health Check

Chạy:

```powershell
uv run python scripts/check_health.py
```

hoặc command tương ứng trong docs.

Kiểm tra:

- API status.
- Bot status.
- Journal freshness.
- Heartbeat freshness.
- Reconciliation.
- Kill switch.
- Data staleness.
- News status.

### Phase E: Smoke Demo Order Gate

Chỉ chuẩn bị và kiểm tra smoke order. Không ép gửi lệnh.

Nếu user đã tự đặt `MT5_TRADE_PASSWORD` trong `.env`, bật demo trading, dry-run false, account whitelist đúng, terminal trade allowed, và hiểu rủi ro, thì chạy:

```powershell
uv run python scripts/smoke_demo_order.py --yes-send-one-demo-order
```

Nếu thiếu bất cứ điều kiện nào:

- Không bypass.
- Không sửa code để vượt.
- Báo chính xác blocker:
  - thiếu trade password
  - terminal investor password
  - trading not allowed
  - account không whitelist
  - symbol không whitelist
  - kill switch tripped
  - news unknown
  - evidence gate closed

Smoke order phải:

- lot tối thiểu
- comment/magic riêng
- journal đầy đủ
- không tính là bằng chứng edge
- có cleanup/close theo thiết kế nếu script hỗ trợ

### Phase F: Dashboard Verification

Chạy API và dashboard nếu cần.

Kiểm tra:

- Panel Demo bot hiển thị.
- Bot mode đúng: disabled / dry-run / demo.
- Kill switch status đúng.
- Account/positions/reconciliation hiển thị đúng.
- Journal hiển thị hoặc status đọc được.
- Không có UI nhập arbitrary trade params.
- Không có lỗi console nếu có browser test/tool.

Nếu chưa có browser CI test, ghi limitation.

---

## 4. Tuyệt đối không "unlock" bằng cách hạ chuẩn

Nếu bot không có lệnh vì:

- evidence gate đóng
- news unknown
- terminal investor password
- trading not allowed
- kill switch
- reconciliation mismatch

thì đó là hệ thống đang hoạt động đúng. Không được sửa để ép bot vào lệnh.

Nếu chủ dự án muốn kiểm tra đường lệnh, chỉ dùng **smoke mode đã thiết kế**, có gắn nhãn, lot tối thiểu, không tính evidence.

---

## 5. Báo cáo cuối

Trả về báo cáo gồm:

- Repo status
- Tests run
- Test results
- API/dashboard status
- Bot dry-run status
- MT5 terminal status
- Reconciliation result
- Journal/heartbeat/status file result
- News calendar status
- Smoke order readiness
- Smoke order result nếu đã chạy
- Remaining blockers
- Exact commands để operator chạy tiếp
- Không in secrets

Chấm điểm:

| Layer | Score | Evidence |
|---|---:|---|
| Dry-run on real data | x/100 | ... |
| Demo broker real-order readiness | x/100 | ... |
| Smoke order verified | x/100 | ... |
| Web app operational completeness | x/100 | ... |
| Gap-audit target | x/100 | ... |

Nếu chưa chạy được `order_send` thật, phải nói rõ:

> “Demo broker path is implemented and gated, but real MT5 order submission has not been proven in this run.”

Nếu vẫn chỉ `WAIT`, phải nói rõ:

> “The bot is operational, but strategy authorization remains closed because no validated edge/news clearance is available.”

---

## 6. Definition of Done

Chỉ được coi là hoàn tất lượt này khi:

- Full Python gate xanh.
- Dashboard build xanh nếu chạm frontend.
- Bot dry-run chạy được hoặc có blocker vận hành rõ.
- Health check chạy được hoặc có blocker rõ.
- Smoke order readiness được xác định.
- Không có live trading path.
- Không có bypass evidence/risk/safety.
- Báo cáo cuối có bằng chứng cụ thể.
