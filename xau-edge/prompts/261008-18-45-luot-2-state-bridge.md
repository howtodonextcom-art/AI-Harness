# Prompt Cho Claude Code: Lượt 2 State + Bridge

Bạn là **Senior Python Engineer, Trading Systems Safety Engineer và QA Lead** đang gia công tiếp repository:

`xau-edge/`

Repository này là hệ thống **XAU EDGE**, một nền tảng research/paper/demo-only trading support cho XAUUSD. Live trading tiền thật bị cấm tuyệt đối.

Bạn phải tiếp tục từ trạng thái hiện tại sau **Lượt 1: Safety Alignment & Design Lock** đã hoàn tất.

Các thay đổi đã có:

- `docs/decisions/0019-demo-execution-scope.md`
- demo settings trong `src/xau_edge/config.py`
- demo flags trong `.env.example`
- cập nhật `AGENTS.md`
- cập nhật `docs/PROJECT_PLAN.md`
- cập nhật `docs/reports/gap-audit.md`

Nhiệm vụ của bạn trong lượt này là thực hiện:

## Lượt 2: Persistent State + Kill Switch + Order Intent + Signal Bridge

Không làm MT5 broker thật trong lượt này.

---

## 0. Bắt buộc đọc trước khi code

Đọc kỹ các file sau:

1. `AGENTS.md`
2. `docs/decisions/0018-api-dashboard-paper-no-live.md`
3. `docs/decisions/0019-demo-execution-scope.md`
4. `docs/reports/gap-audit.md`
5. `docs/reports/prompt-review-demo-bot.md` nếu tồn tại
6. `docs/PROJECT_PLAN.md`
7. `src/xau_edge/config.py`
8. `src/xau_edge/execution/interface.py`
9. `src/xau_edge/execution/trader.py`
10. `src/xau_edge/execution/safety.py`
11. `src/xau_edge/risk/engine.py`
12. `src/xau_edge/risk/kill_switch.py`
13. `src/xau_edge/signals/schema.py`
14. `src/xau_edge/signals/decision.py`
15. Existing tests under:
    - `tests/unit/execution/`
    - `tests/unit/risk/`
    - `tests/unit/signals/`
    - `tests/unit/test_config.py`

Không được bắt đầu code nếu chưa hiểu các safety constraints hiện tại.

---

## 1. Scope của lượt này

Bạn được phép tạo/sửa các phần sau:

### Được phép tạo

- `src/xau_edge/execution/state.py`
- `src/xau_edge/execution/order_intent.py`
- `src/xau_edge/execution/bridge.py`
- Tests tương ứng:
  - `tests/unit/execution/test_state.py`
  - `tests/unit/execution/test_order_intent.py`
  - `tests/unit/execution/test_bridge.py`

### Được phép sửa nếu cần

- `src/xau_edge/execution/__init__.py`
- `src/xau_edge/execution/safety.py`
- `src/xau_edge/execution/trader.py`, nhưng chỉ nếu thật sự cần refactor nhỏ để tái dùng logic
- `src/xau_edge/config.py`, nếu cần expose path/config đã có
- `tests/unit/execution/test_trader.py`, nếu cần thêm test bảo vệ
- docs ngắn nếu có quyết định mới

---

## 2. Không được làm trong lượt này

Tuyệt đối không:

- Tạo `src/xau_edge/brokers/mt5_demo/`
- Import `MetaTrader5`
- Gọi `order_send`
- Gọi `positions_get`
- Gọi `orders_get`
- Thêm endpoint API mới
- Thêm dashboard UI
- Thêm write route
- Sửa/xóa safety test để pass nhanh
- Bypass `RiskEngine`
- Bypass `ExecutionSafety`
- Bypass evidence gate
- Tạo đường `Signal -> broker` trực tiếp
- Claim bot đã chạy demo thật

Lượt này chỉ tạo nền **state + bridge**, chưa có broker thật.

---

## 3. Mục tiêu kỹ thuật

### 3.1 Persistent Execution State

Tạo `src/xau_edge/execution/state.py`.

Yêu cầu:

- Dùng SQLite chuẩn thư viện Python hoặc DuckDB nếu repo đã dùng sẵn. Ưu tiên SQLite vì đơn giản, không thêm dependency.
- State store lưu được:
  - kill switch state
  - kill switch reason
  - seen signal hashes
  - decision bar timestamp
  - order intent id
  - daily order count
  - broker ticket placeholder nếu sau này có
  - created/updated timestamp
- State path lấy từ settings hoặc truyền trực tiếp.
- Nếu DB corrupt, không đọc được, schema sai, hoặc write fail:
  - phải fail-closed
  - không được silently continue
- Không tự reset kill switch.
- Reset kill switch, nếu có, phải cần confirm phrase hiện có hoặc cơ chế explicit tương đương.

Acceptance tests:

- New state starts safe: no seen signals, kill switch not tripped.
- Trip kill switch persists across new instance.
- Seen signal persists across restart.
- Daily order counter persists.
- Duplicate signal after restart is detected.
- Corrupt DB or invalid path raises explicit exception.
- State write failure does not silently pass.

### 3.2 Persistent Kill Switch Wrapper

Không phá `risk/kill_switch.py`.

Tạo wrapper hoặc adapter trong `execution/state.py` hoặc module riêng nếu hợp lý.

Yêu cầu:

- Có thể trip persistent kill switch.
- Có thể đọc trạng thái persistent kill switch.
- Reset nếu có thì explicit, test rõ.
- Khi tripped, bridge phải refuse order intent.
- Kill switch policy theo ADR-0019:
  - không tự đóng vị thế
  - chỉ chặn lệnh mới
  - operator xử lý thủ công

Acceptance tests:

- Tripped state blocks bridge.
- Restart vẫn blocked.
- Reset không xảy ra tự động.

### 3.3 Order Intent

Tạo `src/xau_edge/execution/order_intent.py`.

Yêu cầu schema:

- `intent_id`
- `signal_hash`
- `symbol`
- `direction`
- `lots` hoặc `risk_amount` tùy thiết kế tốt hơn
- `entry_reference`
- `stop_loss`
- `take_profit`
- `max_hold_until`
- `decision_time`
- `created_at`
- `magic`
- `comment`
- `dry_run`
- metadata cần cho audit

Lưu ý:

- Không nhận params từ frontend/client.
- Order intent chỉ được tạo từ `Signal` đã qua bridge.
- `intent_id` deterministic dựa trên `signal.inputs_hash` + decision bar hoặc timestamp phù hợp.
- Không được chứa secrets.
- Không gọi broker.

Acceptance tests:

- Same signal/time creates same intent id.
- Different signal/time creates different intent id.
- Missing SL/TP raises/refuses.
- WAIT never creates intent.
- Comment contains enough traceability but không chứa secret.

### 3.4 Signal-to-Order Bridge

Tạo `src/xau_edge/execution/bridge.py`.

Mục tiêu:

Chuyển `Signal` thành `OrderIntent` **chỉ sau khi** qua đầy đủ guard.

Bridge phải tái dùng hoặc tương thích với:

- `RiskEngine`
- `ExecutionSafety`
- `AccountState`
- `MarketState`
- `Signal`
- `EvidenceStatus`
- persistent state

Bridge phải reject:

- `WAIT`
- expired signal
- missing `inputs_hash`
- missing `entry_zone`
- missing `stop_loss`
- missing `take_profit_1`
- duplicate signal
- persistent kill switch tripped
- evidence gate closed
- news unknown/risk
- risk denied
- safety violation
- stale decision bar nếu bạn thiết kế được check hợp lý

Không được:

- tự tính lot nếu risk engine đã có sizing logic
- bỏ qua risk engine
- bỏ qua safety
- tạo intent khi rejected
- ghi duplicate as seen nếu chưa accepted

Acceptance tests:

- WAIT rejected, no state mutation as accepted order.
- Evidence closed rejected.
- NEWS_UNKNOWN rejected.
- Missing SL/TP rejected.
- Duplicate signal rejected after first accepted.
- Persistent kill switch rejected.
- RiskEngine denial rejected.
- ExecutionSafety violation rejected.
- Accepted bridge output stores signal hash as seen.
- Accepted bridge output produces deterministic `OrderIntent`.

---

## 4. Integration với PaperTrader

Nếu có thể, bridge nên tận dụng logic/khái niệm từ `PaperTrader` thay vì tạo đường song song nguy hiểm.

Tuy nhiên không được làm refactor lớn làm vỡ paper trading.

Nếu cần refactor:

- giữ backward compatibility
- tests hiện có phải pass
- thêm tests chứng minh paper trading vẫn hoạt động

Mục tiêu cuối:

- Paper path vẫn như cũ
- Demo path tương lai có thể dùng bridge/state
- Không có broker thật trong lượt này

---

## 5. Security và Safety Tests

Phải giữ test hiện có:

`test_the_execution_package_never_imports_a_broker_api`

Lượt này không được thêm bất kỳ string/import nào khiến test này fail:

- `MetaTrader5`
- `order_send`
- `order_check`
- `positions_close`

Nếu cần nói về các từ đó trong docs thì được, nhưng không trong `src/xau_edge/execution/*.py`.

---

## 6. Testing bắt buộc

Sau khi code xong, chạy:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -m "not mt5"
```

Nếu chỉ chạy targeted tests trước thì cuối cùng vẫn phải chạy full gate trên.

Không báo hoàn thành nếu gate fail.

---

## 7. Output báo cáo cuối

Khi hoàn tất, trả về báo cáo ngắn gồm:

- Lượt completed: Lượt 2
- Files created
- Files modified
- Safety decisions
- Tests run
- Test results
- What is now possible
- What is still not possible
- Remaining blockers for Lượt 3
- Completion scoring:

| Layer | Score | Evidence |
|---|---:|---|
| Lượt 2 scope | x/100 | ... |
| Gap-audit target | x/100 | ... |
| Demo bot dry-run readiness | x/100 | ... |
| Demo broker real-order readiness | x/100 | ... |
| Web app operational completeness | x/100 | ... |

---

## 8. Thành công của lượt này là gì?

Lượt này thành công khi:

- persistent state có tests
- persistent kill switch có tests
- duplicate prevention qua restart có tests
- order intent deterministic có tests
- signal bridge reject đúng các case nguy hiểm
- không có broker API trong `execution/`
- full quality gate pass

Lượt này **không cần** bot gửi lệnh demo.

Không được claim “demo bot hoàn thiện”. Chỉ claim:

> “State và signal-to-order bridge đã sẵn sàng cho Lượt 3 fake/demo broker adapter.”
