# Gap audit và lộ trình bot demo MT5 (2026-10-08)

Viết cho chủ dự án. Phạm vi mới được phân tích ở đây là: **bot tự động trên tài
khoản demo FTMO/MT5**, không tiền thật. Tài liệu này là kiểm toán + kế hoạch
Gate A cho giai đoạn tiếp theo; chưa thêm executor MT5 demo trong code.

## 1. Kết luận điều hành

Hệ thống hiện tại **chưa đủ điều kiện để chạy bot demo thật có gửi lệnh MT5**.
Nó đã đủ tốt để nghiên cứu và paper trading: data layer, feature engine, market
structure, pattern analogue, outcome statistics, backtest, ML benchmark, signal
engine, API/dashboard và `PaperExecutionBroker` đều đã có. Nhưng các phần biến
tín hiệu thành lệnh demo thật vẫn đang bị thiếu hoặc cố ý khóa.

Kết luận quan trọng hơn: rào cản lớn nhất không phải là thiếu hàm `order_send`.
Rào cản lớn nhất là **chưa có edge được xác thực**. Theo báo cáo cuối, baseline
và model đều không qua tiêu chí đăng ký trước, nên evidence gate đóng và signal
hợp lệ hiện tại là `WAIT`. Nếu xây executor ngay, bot đúng thiết kế vẫn sẽ không
đặt lệnh nào. Đây là hành vi đúng.

**Không nên mở demo execution ngay.** Nên mở một nhánh phát triển demo-only theo
cổng an toàn: persistent state, kill switch bền vững, broker reconciliation,
demo account guard, account/symbol whitelist, idempotency, audit journal, daemon
và chaos tests. Khi chưa có strategy qua evidence gate, executor chỉ được chạy ở
`dry_run` hoặc `pipeline_smoke` tách biệt, lot tối thiểu, không tính là bằng
chứng hiệu quả.

## 2. Đối chiếu nhanh với codebase hiện tại

| Khu vực | Hiện trạng | Nhận định |
|---|---|---|
| `src/xau_edge/execution/interface.py` | Có `ExecutionBroker`, `Order`, `Position`, `AccountInfo`, `ClosedTrade` | Hợp đồng tốt để thêm demo broker, nhưng chưa có schema broker response/reconciliation |
| `src/xau_edge/execution/paper.py` | Có `PaperExecutionBroker`, fill rule giống backtest, journal JSONL | Dùng được làm tham chiếu hành vi, nhưng state in-memory |
| `src/xau_edge/execution/trader.py` | Có signal -> risk -> safety -> paper order, reject `WAIT`, duplicate theo `inputs_hash` | Có thể tái sử dụng orchestration, nhưng cần tách generic `Trader` khỏi paper-specific broker |
| `src/xau_edge/execution/safety.py` | Có environment/account/symbol whitelist, max lot, max orders/day, dry-run | Cần mở rộng cho `demo`, account id thật, magic number, terminal trade enabled, idempotency store |
| `src/xau_edge/risk/engine.py` | Có risk per trade, daily budget, max concurrent, exposure, spread, regime, news, kill switch | Core tốt, nhưng kill switch và daily counters chưa bền vững qua restart |
| `src/xau_edge/market_data/mt5/source.py` | MT5 hiện là read-only market data, demo-only, allowlist proxy chặn order/position API | Đúng cho research; demo execution phải là module riêng, không phá allowlist market-data |
| `src/xau_edge/signals/*` | Signal mặc định `WAIT`, có reasons, expiry, EV, evidence gate | Đúng thiết kế; không được bypass evidence gate để có lệnh |
| `src/xau_edge/api/app.py` | API read-only, chỉ `POST /paper/orders` chạm paper broker | Không có endpoint demo order, và không nên thêm API public cho demo execution ở giai đoạn đầu |
| `scripts/forward_test.py` | Replay/paper forward runner thủ công | Chưa phải daemon, chưa fetch bars mới theo lịch, chưa đặt lệnh demo |
| `.env.example` | Chỉ có live=false và MT5 read-only credentials | Thiếu demo-execution flags/whitelist/dry-run nếu scope mới được duyệt |
| `docs/decisions/0018-*` | Quyết định không live execution, paper only | Cần ADR mới để mở **demo-only execution** mà vẫn giữ live trading bị cấm |

## 3. Phân loại gap từ `gap-audit.md`

| ID | Gap | Loại | Mức | Chặn bot demo? | Ghi chú xử lý |
|---|---|---|---|---|---|
| G1 | Chưa có `MT5DemoExecutionBroker` | Kỹ thuật/execution | BLOCKER | Có | Adapter MT5 phải nằm ở package broker demo riêng, ví dụ `src/xau_edge/brokers/mt5_demo/`; `execution/` vẫn broker-neutral |
| G2 | Chưa có daemon/scheduler chạy theo nến M15 | Kỹ thuật/vận hành | BLOCKER | Có | `scripts/demo_trader.py` hoặc service runner, lock chống chạy hai instance |
| G3 | Kill switch, daily counters, seen signals đang in-memory | Risk/vận hành | BLOCKER | Có | State store SQLite/DuckDB, fail-closed nếu store lỗi |
| G4 | Chưa có broker reconciliation | Execution/risk | BLOCKER | Có | Đọc account/positions/orders từ MT5 demo, so với journal nội bộ |
| G5 | News calendar chưa có dữ liệu, `NEWS_UNKNOWN` buộc WAIT | Data/research | BLOCKER cho BUY/SELL | Có | Chọn nguồn lịch, snapshot `available_at`, backtest window |
| G6 | Chưa có edge được xác thực | Quant/research | BLOCKER chiến lược | Có | Không giải quyết bằng executor; cần hypothesis mới qua protocol |
| G7 | Cost model còn giả định: slippage, commission, swap | Quant/execution | HIGH | Có, nếu muốn tin kết quả | Đo từ demo fills và cập nhật ADR/CostModel |
| G8 | Chưa có order idempotency bền vững | Execution | HIGH | Có | `signal_hash` + `decision_bar` + broker ticket lưu trong state store |
| G9 | Chưa có account/symbol whitelist cho demo thật | Safety | HIGH | Có | Env/config bắt buộc, account id match mới được gửi lệnh |
| G10 | Chưa có chaos/failure tests | QA/safety | HIGH | Có | Fake MT5: requote, reject, timeout, partial init, restart giữa chừng |
| G11 | Dashboard CI browser tests chưa có | QA/frontend | LOW | Không | Cần sau khi có monitoring panel |
| G12 | Holiday calendar chỉ ở mức validator warning | Data | LOW | Không trực tiếp | Bổ sung sau news layer |
| G13 | Docker/STUMPY/tslearn chưa dùng | Infra/research | OPTIONAL | Không | Chỉ làm khi có nhu cầu thật |

## 4. Định nghĩa scope "bot demo thật"

Bot demo được phép:

- Kết nối MT5 **demo account** và xác minh `ACCOUNT_TRADE_MODE_DEMO` trước mọi thao tác.
- Đọc bars thật, validate data, generate signal bằng pipeline hiện tại.
- Chỉ chuyển `BUY`/`SELL` đã qua evidence gate thành order intent.
- Gọi risk engine, execution safety gate và broker reconciliation trước khi gửi order.
- Gửi lệnh MT5 demo với SL/TP bắt buộc, magic number riêng, idempotency key và journal.
- Chạy `dry_run=true` mặc định; chuyển sang demo execution thật chỉ bằng flag demo riêng.
- Ghi audit trail cho signal hash, risk decision, safety decision, broker request/response.
- Trip kill switch nếu account mismatch, symbol mismatch, stale data, reconciliation mismatch,
  unknown news, broker reject bất thường, state corruption hoặc restart không khôi phục được.

Bot demo không được phép:

- Chạy trên tài khoản live hoặc contest/non-demo.
- Gửi lệnh khi `Signal.direction == WAIT`.
- Bypass evidence gate, news guard, risk guard hoặc safety guard.
- Gửi lệnh nếu signal hết hạn, không có SL/TP, data stale, spread quá rộng, regime/news unknown.
- Nhận direction/lot/SL/TP từ client API.
- Xóa hoặc reset kill switch tự động.
- Claim profitability từ demo fills.
- Thay đổi risk limits âm thầm.

## 5. Ma trận gap để có demo execution

| Hạng mục | Hiện trạng | Thiết kế cần có | Gap | Rủi ro | File/module liên quan | Acceptance criteria |
|---|---|---|---|---|---|---|
| ExecutionBroker | Interface đã có | Generic đủ cho paper + demo | Thiếu broker result/ticket metadata | HIGH | `execution/interface.py` | Schema giữ backward-compatible; paper tests vẫn pass |
| Paper broker | Có, state in-memory | Vẫn là baseline và dry-run reference | Chưa share state store | MEDIUM | `execution/paper.py` | Paper journal vẫn deterministic; không chạm MT5 |
| MT5 demo broker | Chưa có | `MT5DemoExecutionBroker` riêng trong package broker demo | BLOCKER | CRITICAL | `brokers/mt5_demo/` mới | Fake MT5 unit tests; MT5 order APIs không xuất hiện trong `execution/` |
| Account sync | Chỉ paper account | Đọc MT5 account/equity/open positions | BLOCKER | CRITICAL | `brokers/mt5_demo/`, state store | Non-demo/account mismatch -> refuse + kill |
| Position sync | Chưa có | Reconcile MT5 positions với internal journal | BLOCKER | CRITICAL | `execution/reconcile.py` mới | Mismatch ticket/lot/symbol/SL/TP -> kill switch |
| Order submit | Chưa có | Market order demo với SL/TP, magic, comment hash | BLOCKER | CRITICAL | `brokers/mt5_demo/` | WAIT/incomplete signal never reaches `order_send` |
| Order modify/close | Interface có, demo chưa có | Support close/modify only for owned magic/symbol | HIGH | HIGH | `brokers/mt5_demo/` | Cannot close/modify manual or foreign positions |
| Idempotency | In-memory `_seen` | Persistent `signal_hash + decision_bar` | HIGH | HIGH | `execution/state.py` mới | Restart cannot duplicate last signal |
| Safety flags | Paper defaults | `ENABLE_DEMO_TRADING`, `DEMO_DRY_RUN`, whitelist | BLOCKER | CRITICAL | `.env.example`, `config.py`, `execution/safety.py` | Demo disabled by default; live flag still impossible |
| Kill switch | In-memory | Persistent, fail-closed | BLOCKER | CRITICAL | `risk/kill_switch.py`, `execution/state.py` | Corrupt/missing store trips kill |
| Signal bridge | `PaperTrader` paper-specific | Generic signal -> order intent -> broker | HIGH | HIGH | `execution/trader.py` | Rejects WAIT, expired, duplicate, incomplete, stale |
| Daemon | Manual scripts | M15 loop, single-instance lock, graceful shutdown | BLOCKER | HIGH | `scripts/demo_trader.py` mới | 24h dry-run without duplicate decisions |
| Observability | Structured logs + paper journal | Execution journal + broker response + heartbeat | HIGH | HIGH | `observability.py`, state/journal | Every refusal/order reproducible by signal hash |
| News risk | Interface only | Real calendar snapshots and window study | BLOCKER for trading | HIGH | `news/`, docs/evals | Unknown calendar keeps WAIT |
| Testing | Strong unit suite | Fake MT5 + chaos + manual mt5 integration | HIGH | CRITICAL | `tests/unit/execution`, `tests/integration` | CI never sends real order; mt5 demo test marked manual/mt5 |

## 6. Kiến trúc demo execution đề xuất

```text
MT5 demo / file data
        |
        v
Market data validation + closed-bar selection
        |
        v
Feature / structure / pattern / signal engine
        |
        v
Evidence gate + decision policy
        |
        v
Signal-to-order bridge
        |
        v
RiskEngine + ExecutionSafety + persistent kill switch
        |
        v
OrderIntent (idempotency key = signal hash + decision bar)
        |
        v
Demo broker adapter (`src/xau_edge/brokers/mt5_demo/`)
        |
        v
MT5 DEMO account
        |
        v
Execution journal + reconciliation + cost measurement
```

Thiết kế giữ nguyên nguyên tắc gốc:

- Forecast không trực tiếp thành order.
- Trading decision tách khỏi execution.
- Execution chỉ nhận `OrderIntent` đã qua risk/safety.
- Default là fail-closed.
- Live trading vẫn bị cấm tuyệt đối trong release này.

## 7. File nên tạo hoặc cập nhật

| File | Hành động | Lý do |
|---|---|---|
| `docs/decisions/0019-demo-execution-scope.md` | Tạo | Ghi rõ demo-only, amend ADR-0018, không live, điều kiện mở executor |
| `docs/architecture/demo-execution.md` | Tạo | Kiến trúc signal -> risk -> safety -> demo broker |
| `docs/operations/demo-trading.md` | Tạo | Runbook: setup MT5 demo, dry-run, kill switch, incident |
| `docs/risk/demo-execution-risk.md` | Tạo | Rủi ro executor, fail-closed rules, red-team checklist |
| `configs/execution/demo.yaml` | Tạo | Whitelist account/symbol, max lot/order/day, magic number |
| `.env.example` | Cập nhật | Thêm demo flags nhưng mặc định disabled/dry-run |
| `AGENTS.md` | Cập nhật | Demo executor rules: không bypass evidence, no live path |
| `src/xau_edge/execution/state.py` | Tạo | Persistent state, idempotency, kill switch state |
| `src/xau_edge/brokers/mt5_demo/` | Tạo | Demo broker implementation với fake-testable client; đây là package duy nhất được phép chạm MT5 order API |
| `src/xau_edge/execution/reconcile.py` | Tạo | Broker/internal reconciliation |
| `src/xau_edge/execution/order_intent.py` | Tạo | Stable order intent schema trước broker |
| `scripts/demo_trader.py` | Tạo | Daemon/loop M15, dry-run default |
| `tests/unit/execution/test_mt5_demo.py` | Tạo | Fake MT5 unit tests |
| `tests/unit/execution/test_state.py` | Tạo | Persistent state/restart tests |
| `tests/integration/test_demo_execution_safety.py` | Tạo | Marked integration, no real orders in CI |

## 8. Roadmap phát triển tiếp theo

### Phase A: Gap audit finalization

- Chốt scope demo-only bằng ADR-0019.
- Cập nhật `AGENTS.md`, `.env.example`, `PROJECT_PLAN.md`.
- Định nghĩa `ENABLE_DEMO_TRADING=false` và `DEMO_DRY_RUN=true` mặc định.
- Chốt rằng `ENABLE_LIVE_TRADING=true` vẫn bị reject như hiện tại.

Done khi: tài liệu nêu rõ demo executor không phải live executor, owner duyệt Gate A.

### Phase B: Demo execution foundations

- Tạo persistent state store.
- Tạo persistent kill switch.
- Tạo `OrderIntent` và `ExecutionJournal`.
- Giữ `src/xau_edge/execution/` broker-neutral; không import `MetaTrader5` hoặc order APIs tại đây.
- Tách `PaperTrader` thành phần dùng chung nếu cần.
- Viết fake MT5 client contract trước.

Done khi: restart không làm mất kill switch, seen signal, daily counters; corrupt state -> fail-closed.

### Phase C: MT5DemoExecutionBroker

- Cài demo broker adapter trong `src/xau_edge/brokers/mt5_demo/`, không phải trong `execution/`.
- Cài `get_account`, `get_positions`, `submit_order`, `close_position`, `modify_position`.
- Chỉ chấp nhận demo account + whitelisted account id.
- Chỉ quản lý symbol/magic/comment của bot.
- SL/TP bắt buộc, lot bounded, order result được journal.

Done khi: fake MT5 test chứng minh non-demo, account mismatch, symbol mismatch, duplicate,
no-SL/TP, broker reject và retry đều không tạo lệnh nguy hiểm.

### Phase D: Signal-to-demo bridge

- Convert `Signal` thành `OrderIntent`.
- Reject `WAIT`, expired, incomplete, stale, duplicate, news unknown, evidence closed.
- Risk check trước broker.
- Safety check sau risk, trước broker.
- Idempotency persistent theo `signal_hash`.

Done khi: không có đường nào từ API/client input tới direction/lot/SL/TP; tất cả đến từ signal/risk.

### Phase E: Demo bot runner

- `scripts/demo_trader.py`: loop theo nến M15, single-instance lock.
- Fetch latest bars, validate, generate signal, reconcile, execute/reject, heartbeat.
- Graceful shutdown.
- Dry-run default.

Done khi: chạy 24h trên demo ở dry-run hoặc WAIT mode, không duplicate decision, log đầy đủ.

### Phase F: Demo forward testing

- Chạy nhiều tuần trên demo.
- Đo spread/slippage/commission/swap thực tế.
- So sánh paper/backtest/demo fills.
- Cập nhật cost model.
- Không claim edge nếu chưa đủ sample và chưa qua protocol.

Done khi: có báo cáo forward demo với ít nhất điều kiện sample đã định trước; nếu vẫn `WAIT`, báo cáo
đúng là "hạ tầng chạy an toàn, chưa có trade hợp lệ".

### Phase G: Operational hardening

- Alerting: MT5 disconnect, data stale, kill switch, reconciliation mismatch.
- Dashboard monitoring panel.
- Incident report template.
- Manual emergency stop.
- Recovery procedure.

Done khi: lỗi vận hành phổ biến được test và có runbook.

## 9. 10 bước tiếp theo theo thứ tự

1. Duyệt scope demo-only: không live, không bypass evidence gate.
2. Viết ADR-0019.
3. Thêm config/env demo execution disabled by default.
4. Tạo persistent state + persistent kill switch.
5. Viết fake MT5 client contract và safety tests.
6. Cài `MT5DemoExecutionBroker` ở dry-run/fake path trước.
7. Thêm reconciliation trước submit order.
8. Tạo signal-to-order bridge với idempotency.
9. Tạo `scripts/demo_trader.py` chạy loop M15, single-instance lock.
10. Chạy 24h demo dry-run/WAIT, sau đó mới cân nhắc bật demo order thật nếu signal không WAIT.

## 10. Điều kiện tối thiểu trước lệnh demo đầu tiên

Không gửi lệnh demo đầu tiên nếu thiếu bất kỳ điều kiện nào:

- ADR-0019 accepted.
- `ENABLE_DEMO_TRADING=true`, `DEMO_DRY_RUN=false` được đặt rõ, nhưng `ENABLE_LIVE_TRADING=false`.
- MT5 account là DEMO và account id nằm trong whitelist.
- Symbol là `XAUUSD` và nằm trong whitelist.
- Signal là `BUY` hoặc `SELL`, không expired, không duplicate, có SL/TP, có `inputs_hash`.
- Evidence gate open theo registry, không phải override thủ công.
- News status không unknown/risk.
- Risk engine allowed.
- Execution safety allowed.
- Persistent kill switch không tripped.
- Reconciliation clean trước submit.
- Order idempotency key chưa từng dùng.
- MT5 order APIs chỉ tồn tại trong package demo broker được ADR-0019 cho phép, không nằm trong `execution/`.
- Journal ghi được trước và sau broker request.
- Fake MT5 + safety tests pass.
- Có operator biết cách trip kill switch thủ công.

## 11. Red-team

| Câu hỏi | Kết luận |
|---|---|
| Executor có thể bị dùng cho tiền thật không? | Rủi ro cao nhất. Chặn bằng demo trade-mode check tại mọi broker operation, account whitelist, live flag reject, tests và ADR |
| Có thể ép bot đặt lệnh dù signal `WAIT` không? | Không được. `WAIT` phải bị reject ở bridge, trader và tests |
| Restart có thể xóa giới hạn rủi ro không? | Hiện có thể vì state in-memory. Phase B phải sửa trước broker demo |
| Broker có thể có vị thế thủ công ngoài bot không? | Có. Reconciliation phải phát hiện magic/comment mismatch và fail-closed |
| Demo profit có chứng minh live profit không? | Không. Demo chỉ kiểm tra vận hành, fill approximation và pipeline discipline |
| Có nên thêm live trading sau demo? | Không trong roadmap này. Live cần brief, ADR, legal/risk review và edge validated riêng |

## 12. Quyết định cần chủ dự án

| ID | Quyết định | Khuyến nghị |
|---|---|---|
| C1 | Có cho pipeline smoke trade khi chưa có edge? | Mặc định: không. Nếu cần, tạo mode riêng, lot tối thiểu, gắn nhãn, không tính evidence |
| C2 | Có giữ `NEWS_UNKNOWN` là blocker tuyệt đối không? | Có, nhất là với XAUUSD |
| C3 | Account demo nào được whitelist? | Chủ dự án cung cấp account id qua `.env`, không commit |
| C4 | Bot chạy trên máy local hay VPS Windows? | Local trước, VPS sau khi Phase E xanh |
| C5 | Có chấp nhận viết Sprint 15 cho persistent state/kill switch trước broker không? | Có. Đây là bước đúng thứ tự |

## 13. Kết luận

Hệ thống hiện tại là nền research/paper tốt, nhưng **chưa phải bot demo execution**. 5 blocker lớn
nhất là: chưa có MT5 demo broker, chưa có persistent state/kill switch, chưa có reconciliation,
chưa có daemon vận hành, và chưa có news data/evidence mở để có signal không `WAIT`.

Lộ trình đúng không phải "bật order_send", mà là dựng một execution subsystem demo-only, fail-closed,
có audit, có khôi phục sau restart, và chỉ được gửi lệnh khi signal/risk/safety đều đồng thuận. Nếu
không có edge, kết quả đúng của bot demo vẫn là đứng ngoài thị trường.
