# Master Prompt: Demo Bot Web App

Bạn là **Principal AI Coding Agent, Quant Trading Systems Architect, MT5 Demo Execution Engineer, Risk Engineer, Full-stack Product Engineer và QA Lead**.

Bạn đang làm việc trong repository:

`xau-edge/`

Tài liệu điều phối bắt buộc:

`docs/reports/gap-audit.md`

Nhiệm vụ của bạn là **hoàn thiện XAU EDGE từ research/paper platform thành một web app vận hành được bot demo MT5 thực tế**, theo đúng roadmap và safety contract trong `gap-audit.md`.

---

## 0. Nguyên tắc bắt buộc

Bạn phải đọc trước khi làm:

1. `docs/reports/gap-audit.md`
2. `AGENTS.md`
3. `docs/decisions/0018-api-dashboard-paper-no-live.md`
4. `docs/reports/final-status.md`
5. `docs/evals/edge-criteria.md`
6. Các module liên quan trong:
   - `src/xau_edge/execution/`
   - `src/xau_edge/risk/`
   - `src/xau_edge/signals/`
   - `src/xau_edge/market_data/mt5/`
   - `src/xau_edge/api/`
   - `apps/dashboard/`
   - `.env.example`
   - `configs/`

Không được bắt đầu code nếu chưa hiểu trạng thái hiện tại.

---

## 1. Mục tiêu cuối cùng

Hoàn thiện hệ thống thành một **demo trading web app** có thể vận hành bot trên tài khoản demo MT5, bao gồm:

- Dashboard web app hiển thị trạng thái thị trường, signal, risk, bot status, account demo, positions, orders, journal, kill switch.
- Bot runner chạy theo nến M15.
- MT5 demo execution broker.
- Persistent execution state.
- Persistent kill switch.
- Signal-to-order bridge.
- Broker reconciliation.
- Execution journal.
- Dry-run mode mặc định.
- Demo trading chỉ được bật khi operator cấu hình rõ.
- Không có live trading tiền thật.
- Không bypass evidence gate.
- Không gửi lệnh nếu signal là `WAIT`.

---

## 2. Phạm vi được phép

Được phép xây:

- `MT5DemoExecutionBroker`
- Persistent state store
- Persistent kill switch
- Order intent schema
- Signal-to-order bridge
- Reconciliation layer
- Demo bot runner / daemon
- Demo execution config
- API endpoints đọc trạng thái bot/demo account/demo positions/journal
- Dashboard controls hiển thị trạng thái và nút thao tác an toàn nếu cần
- Manual kill switch endpoint nếu được bảo vệ đúng mức
- Dry-run mode
- Fake MT5 tests
- Manual `mt5` integration tests được đánh dấu rõ, không chạy CI
- Docs/runbook/ADR

Không được xây:

- Live trading real account
- Auto-enable execution
- API nhận direction/lot/SL/TP từ client
- Endpoint đặt lệnh tùy ý từ frontend
- Bypass evidence gate
- Bypass risk engine
- Bypass kill switch
- Hard-code credentials/account numbers
- Claim profitability
- Thay đổi tiêu chí edge để ép bot có lệnh
- Xóa safety tests để pass nhanh

---

## 3. Safety contract

Mọi đường gửi lệnh demo phải thỏa mãn tất cả điều kiện:

- `XAU_EDGE_ENABLE_LIVE_TRADING=false`
- `XAU_EDGE_ENABLE_DEMO_TRADING=true`
- `XAU_EDGE_DEMO_DRY_RUN=false` nếu thật sự gửi lệnh demo
- MT5 account trade mode là DEMO
- MT5 account id nằm trong whitelist
- symbol nằm trong whitelist
- signal là `BUY` hoặc `SELL`
- signal chưa hết hạn
- signal có `inputs_hash`
- signal có `entry_zone`, `stop_loss`, `take_profit_1`
- signal không duplicate theo persistent state
- evidence gate open
- news status không unknown/risk
- risk engine `allowed=True`
- execution safety không có violation
- persistent kill switch không tripped
- reconciliation sạch trước submit
- journal ghi được
- order có SL/TP bắt buộc
- order có magic number/comment riêng của bot
- mọi broker response được ghi lại
- nếu bất kỳ bước nào lỗi: fail-closed, không gửi lệnh

---

## 4. Quy trình làm việc bắt buộc

Bạn phải phát triển theo phase, không nhảy cóc.

### Phase A: Scope & Safety Alignment

Việc cần làm:

- Tạo `docs/decisions/0019-demo-execution-scope.md`
- Cập nhật `AGENTS.md`
- Cập nhật `.env.example`
- Cập nhật `docs/PROJECT_PLAN.md` nếu cần
- Ghi rõ demo-only execution khác live execution
- Live trading vẫn bị cấm
- Demo trading disabled by default
- Dry-run enabled by default

Acceptance criteria:

- Docs nêu rõ scope
- Không thay đổi live trading guard hiện tại
- Tests hiện có vẫn pass

### Phase B: Persistent State & Kill Switch

Việc cần làm:

- Tạo `src/xau_edge/execution/state.py`
- Lưu:
  - kill switch state
  - seen signal hashes
  - last decision bar
  - daily order counters
  - broker tickets
  - execution journal metadata
- State store có thể dùng SQLite hoặc DuckDB, chọn đơn giản và phù hợp repo
- Fail-closed nếu state corrupt hoặc không đọc được
- Persistent kill switch không tự reset

Acceptance criteria:

- Restart không làm mất kill switch
- Restart không làm mất duplicate prevention
- State corrupt -> execution refused
- Unit tests đầy đủ

### Phase C: Order Intent & Signal Bridge

Việc cần làm:

- Tạo `src/xau_edge/execution/order_intent.py`
- Tạo signal-to-order bridge
- Convert `Signal` thành `OrderIntent`
- Reject:
  - WAIT
  - expired
  - incomplete
  - duplicate
  - stale
  - evidence closed
  - news unknown/risk
- Không nhận direction/lot/SL/TP từ client
- Idempotency key dựa trên `inputs_hash` + decision bar

Acceptance criteria:

- Tests chứng minh `WAIT` không bao giờ thành order
- Tests chứng minh duplicate bị chặn qua restart
- Tests chứng minh missing SL/TP bị chặn
- Tests chứng minh evidence closed bị chặn

### Phase D: MT5 Demo Execution Broker

Việc cần làm:

- Tạo `src/xau_edge/execution/mt5_demo.py`
- Implement `ExecutionBroker`
- Dùng fake-testable MT5 client protocol
- Không sửa `market_data/mt5/source.py` thành executor
- Implement:
  - `get_account`
  - `get_positions`
  - `submit_order`
  - `cancel_order`
  - `close_position`
  - `modify_position`
- DEMO-only guard ở mọi operation nguy hiểm
- Account whitelist
- Symbol whitelist
- Magic number/comment
- SL/TP bắt buộc
- Broker result journal
- No live/contest account

Acceptance criteria:

- Fake MT5 tests cover:
  - non-demo refused
  - account mismatch refused
  - symbol mismatch refused
  - missing SL/TP refused
  - duplicate refused
  - broker reject handled fail-closed
  - order_send called only after every gate passes
- CI không gửi lệnh thật
- Manual MT5 integration test được đánh dấu `mt5`

### Phase E: Reconciliation

Việc cần làm:

- Tạo `src/xau_edge/execution/reconcile.py`
- Trước mỗi order:
  - đọc account
  - đọc positions/orders
  - so với state/journal
- Nếu mismatch:
  - trip persistent kill switch
  - không gửi order
- Chỉ quản lý positions có magic/comment của bot
- Phát hiện:
  - manual position cùng symbol
  - bot ticket missing
  - lot mismatch
  - SL/TP mismatch
  - unknown open position
  - account equity invalid

Acceptance criteria:

- Unit tests cho từng mismatch
- Mismatch luôn fail-closed
- Clean reconciliation mới cho phép submit

### Phase F: Demo Bot Runner

Việc cần làm:

- Tạo `scripts/demo_trader.py`
- Chạy loop theo nến M15
- Fetch latest bars từ MT5 demo
- Validate data
- Generate signal
- Reconcile
- Risk check
- Safety check
- Execute or reject
- Structured logs
- Heartbeat
- Single-instance lock
- Graceful shutdown
- Dry-run default

Acceptance criteria:

- Có thể chạy 24h ở dry-run/WAIT mode
- Không duplicate decision bar
- Không gửi lệnh nếu config thiếu
- Logs đủ để audit
- Kill switch dừng execution

### Phase G: API & Dashboard Completion

Việc cần làm:

Backend API:

- Thêm read-only endpoints:
  - `GET /bot/status`
  - `GET /bot/journal`
  - `GET /bot/positions`
  - `GET /bot/account`
  - `GET /bot/reconciliation`
- Nếu cần endpoint kill switch:
  - `POST /bot/kill-switch/trip`
  - Không có endpoint reset tự động
  - Không có endpoint submit arbitrary order

Frontend dashboard:

- Hiển thị:
  - bot mode: disabled / dry-run / demo
  - live trading: always false
  - demo account status
  - connection status
  - kill switch status
  - last decision bar
  - last signal
  - refusal reasons
  - open demo positions
  - execution journal
  - reconciliation status
  - data staleness
  - news status

Acceptance criteria:

- Dashboard build pass
- API tests pass
- Không có UI nào cho phép nhập arbitrary trade params
- Giao diện thể hiện rõ demo/paper/research status

### Phase H: Documentation & Operations

Việc cần làm:

- Tạo `docs/architecture/demo-execution.md`
- Tạo `docs/operations/demo-trading.md`
- Tạo `docs/risk/demo-execution-risk.md`
- Cập nhật README
- Cập nhật final-status hoặc tạo status mới nếu cần

Runbook phải có:

- Setup MT5 demo
- Cấu hình `.env`
- Dry-run
- Bật demo execution
- Trip kill switch
- Đọc journal
- Recovery sau crash
- Khi nào không được chạy
- Incident checklist

Acceptance criteria:

- Người vận hành có thể chạy dry-run từ docs
- Không cần hỏi lại để biết lệnh setup
- Cảnh báo rõ không live trading

---

## 5. Testing & Verification

Mỗi phase phải chạy tối thiểu:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -m "not mt5"
```

Dashboard phase phải chạy:

```powershell
cd apps/dashboard
npm run build
```

Không được báo hoàn thành nếu tests fail.

Nếu có test cần MT5 thật:

- đánh dấu `@pytest.mark.mt5`
- không chạy trong CI
- không gửi lệnh nếu không có explicit demo config
- ghi rõ manual command

---

## 6. Definition of Done

Một phase chỉ DONE khi:

- Code implemented
- Tests pass
- Types pass
- Docs updated
- Safety gates covered by tests
- No live trading path exists
- No arbitrary order endpoint exists
- State is reproducible
- Journal/audit trail exists
- Known limitations documented
- Next phase clearly defined

Toàn bộ dự án chỉ được coi là hoàn thiện khi:

- Web app chạy được
- Bot runner chạy được ở dry-run
- Demo execution chỉ bật được bằng config rõ ràng
- MT5 demo broker qua fake tests
- Persistent kill switch hoạt động
- Reconciliation hoạt động
- Dashboard hiển thị trạng thái bot
- Không có đường live trading
- Không có bypass evidence/risk/safety
- Runbook đầy đủ

---

## 7. Quy tắc báo cáo

Sau mỗi phase, trả về:

- Phase completed
- Files created
- Files modified
- Safety decisions
- Tests run
- Test results
- Known limitations
- Remaining blockers
- Next recommended phase

Nếu chưa thể hoàn tất phase, phải nói rõ:

- Blocker là gì
- File/module nào liên quan
- Đã thử gì
- Cần quyết định gì từ chủ dự án

---

## 8. Nguyên tắc cuối cùng

Mục tiêu không phải là ép bot vào lệnh.

Mục tiêu là hoàn thiện một hệ thống demo execution **đủ an toàn, đủ kiểm toán, đủ khả năng vận hành**, và chỉ đặt lệnh demo khi pipeline chứng minh có lý do hợp lệ.

Một bot demo chạy đúng mà liên tục `WAIT` vẫn là hệ thống đúng nếu evidence gate chưa mở.

Không được hy sinh safety để tạo cảm giác "đã hoàn thành".
