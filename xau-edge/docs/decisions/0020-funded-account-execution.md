# ADR-0020: Funded account execution (FTMO funded)

Status: accepted (2026-10-08). Thay thế **phần phạm vi** (scope) của ADR-0018 và ADR-0019 cho riêng
tài khoản FTMO funded. Mọi phần khác của ADR-0018/0019 (API/dashboard read-only, package boundary,
không có `Signal -> order_send` trực tiếp, unknown state fail-closed, credentials) vẫn giữ nguyên.
Quyết định của chủ dự án: D2, D5, D6 trong `prompts/26-10-08-21-05-master-v2-funded-bot.md`.

**Bối cảnh.** ADR-0019 chỉ mở nhánh demo. Chủ dự án đã có tài khoản FTMO funded và muốn bot chạy
trên đó sau khi kiểm chứng trên demo. Hai khó khăn: (1) FTMO có thể báo `trade_mode` là DEMO cho cả
tài khoản funded (pre-mortem f3), nên guard "chỉ DEMO" không phân biệt được demo với funded; (2) chưa
có chiến lược VALIDATED (Track 1), nên nếu không có ngoại lệ thì funded luôn `WAIT`.

## Quyết định

**Cờ riêng, mặc định tắt.** `XAU_EDGE_ENABLE_FUNDED_TRADING=false`, tách hẳn khỏi cờ demo; bật cả
hai cùng lúc bị `Settings` từ chối. Bật funded bắt buộc khai báo `XAU_EDGE_FUNDED_ALLOWED_ACCOUNTS`,
`XAU_EDGE_FUNDED_ALLOWED_SERVERS`, `XAU_EDGE_FUNDED_MAGIC`, `XAU_EDGE_FUNDED_INITIAL_CAPITAL`. Funded
có state và journal riêng (`XAU_EDGE_FUNDED_STATE_PATH` = `data/execution/funded_state.sqlite`,
`XAU_EDGE_FUNDED_JOURNAL_PATH` = `data/execution/funded_journal.jsonl`), không được trùng file của
demo; kill switch, idempotency, request counter, trading days và rollout tier của funded không bao
giờ lẫn với demo.

**Nhận diện tài khoản bằng whitelist, không bằng `trade_mode`** (`funded/identity.py`):

* login + tên server + profile luật, so với whitelist riêng của từng mode; whitelist demo và funded
  không được có phần tử chung (`Settings` từ chối);
* cross-refusal: dry-run/demo thấy login funded thì từ chối; funded thấy login demo, login lạ, hoặc
  server không có trong `XAU_EDGE_FUNDED_ALLOWED_SERVERS` thì từ chối;
* chỉ ở funded, reader, reconciler và `Mt5BarSource` chạy với `require_demo=False` (identity đã
  được whitelist + server xác nhận). Dry-run và demo vẫn bắt buộc DEMO như cũ. `Mt5BarSource` vẫn
  chỉ giữ allowlist proxy read-only.

**Khởi động có banner và xác nhận.** `scripts/demo_trader.py` in mode, server, `trade_mode`, profile
luật và số tài khoản (chỉ 3 số cuối). DEMO và FUNDED chỉ chạy khi có `--confirm-mode DEMO` /
`--confirm-mode FUNDED` trên dòng lệnh và giá trị khớp mode đã cấu hình. Không bao giờ in login đầy
đủ, mật khẩu hay nội dung `.env`.

**D6: khóa theo file luật.** `configs/prop/ftmo_funded.yaml`: mỗi luật có `status`
(`verified_official` / `secondary` / `unverified`), `must_verify`, `verified_on`, `source`. Còn bất kỳ
luật `must_verify` nào chưa `verified_official` có ngày và nguồn thì `authorize_start` từ chối funded.
Chương trình không bao giờ tự đánh dấu một luật là verified. Sàn daily/max loss của funded lấy từ file
này (`FundedRules.to_prop_profile`).

**Một cửa duy nhất: `RunPlan`** (`funded/plan.py`, hàm thuần, không I/O). Đầu vào: settings, identity,
file luật, rollout tier đang hiệu lực, chiến lược có VALIDATED hay không, cờ `--confirm-mode`. Luôn đi
qua `authorize_start` trước. Kết quả:

| Mode | `send_orders` | `shadow` | Lot cap | Rủi ro/lệnh | Override D2 | `require_demo` |
|---|---|---|---|---|---|---|
| DRY_RUN | không | không | - | 0,5% (không gửi gì) | không | có |
| DEMO | có | không | - | 0,5% (`RiskLimits` mặc định) | không | có |
| FUNDED tier 0 `shadow` | không | có (`order_check`, không gửi) | - | ≤ 0,25% | theo cờ | không |
| FUNDED tier 1 `minimum-lot` | có | không | 0,01 | ≤ 0,25% | theo cờ | không |
| FUNDED tier 2 `quarter-percent` | có | không | - | 0,25% | theo cờ | không |
| FUNDED tier 3 `validated-sizing` | có | không | - | `XAU_EDGE_FUNDED_VALIDATED_RISK_PCT` (thiếu thì từ chối) | không (chỉ VALIDATED) | không |

**Rollout theo bậc** (`configs/execution/rollout.yaml`, `funded/rollout.py`): tier lưu trong state
funded, bắt đầu ở 0. Tiêu chí ra khỏi bậc: tier 0 ≥ 5 ngày shadow (ngày Prague có ít nhất một intent
qua `order_check`), tier 1 ≥ 10 lệnh FILLED và 0 REJECTED/UNKNOWN, tier 2 ≥ 4 tuần. Chỉ operator lên
bậc bằng `scripts/rollout.py promote --confirm`, đúng một bậc mỗi lần, khi tiêu chí đạt; không có tùy
chọn bỏ bậc hay ép buộc. Chiến lược UNVALIDATED bị chặn vĩnh viễn ở tier 2 (kể cả khi state bị sửa
tay thành 3). Sau khi lên bậc phải restart bot. Mỗi lần khởi động funded gửi alert `ROLLOUT_TIER`;
mỗi lần lên bậc ghi journal `rollout.promoted` và gửi alert `ROLLOUT_TIER_CHANGED`.

**D2: owner override cho chiến lược UNVALIDATED** (`execution/override.py`, bridge):

* chỉ ở FUNDED, chỉ khi `XAU_EDGE_FUNDED_ALLOW_UNVALIDATED=true` **và**
  `XAU_EDGE_FUNDED_STRATEGY_ID` nêu đúng một chiến lược; tín hiệu phải đến từ đúng chiến lược đó;
* chỉ áp dụng cho tín hiệu `WAIT` có **duy nhất** lý do `NO_VALIDATED_EDGE` cùng hướng nghiêng và đủ
  mức giá; mọi lý do khác (`NEWS_UNKNOWN`, `NEWS_RISK`, regime SHOCK, spread, ...) vẫn chặn; risk engine,
  `ExecutionSafety`, kill switch, idempotency, reconciliation không đổi;
* rủi ro trần **0,25%/lệnh**: `min(tier risk, XAU_EDGE_FUNDED_RISK_PCT, 0,25)`. Trường cấu hình đã
  giới hạn ≤ 0,25 và `RunPlan` lấy min với hằng số 0,25 một lần nữa (đúng cả khi `Settings` bị bỏ qua
  validation hoặc file tier ghi số lớn hơn). Mọi thứ không VALIDATED trên funded (kể cả nhãn NONE) đều
  chịu trần này;
* nhãn `UNVALIDATED` ở mọi nơi: comment lệnh `XAUEDGE:UNV:...`, metadata
  `evidence_status=UNVALIDATED_OVERRIDE` + `strategy_id` trong journal, `status.json` (`prop.evidence_label`)
  và dashboard;
* chiến lược dùng cho override là chiến lược có kết quả tốt nhất trong ledger sau chi phí ở kịch bản bi
  quan, theo quy tắc đã đăng ký trước (Track 1, T1.6), không chọn tay;
* nếu có chiến lược VALIDATED thì override tự tắt, chiến lược VALIDATED được ưu tiên.

Không có chiến lược VALIDATED và override tắt: funded vẫn chạy (theo rollout), nhưng evidence gate
giữ mọi tín hiệu ở `WAIT`.

**D5: auto-flatten.** Khi equity cách sàn daily loss (hoặc max loss) ≤ **1% vốn ban đầu**, bot đóng
**chỉ các vị thế của bot** (magic + comment + state), ghi journal (`flatten.started`/`flatten.finished`),
trip kill switch và gửi alert `AUTO_FLATTEN`. ADR này **cho phép rõ ràng** việc tự đóng vị thế mà
`AGENTS.md` cấm nếu không có ADR; phạm vi cho phép chỉ đúng trường hợp này (và ở dry-run thì chỉ trip
kill switch). Kill switch do nguyên nhân khác vẫn không tự đóng vị thế (ADR-0019).

**Request budget 900/ngày.** Mọi lời gọi terminal đi qua `CountingMt5`, đếm bền vững trong state của
mode theo ngày Prague, với hai bộ đếm:

* **trade request** (`order_send`, `order_check`, tức lời gọi đi tới trade server): trần cứng 900; lời
  gọi thứ 901 bị từ chối (`RequestBudgetExceededError`), bot dừng gửi tới 00:00 Prague kế tiếp và alert
  `REQUEST_BUDGET`;
* **mọi lời gọi khác** (đọc bar, tick, positions, deals): đếm và ghi log khi chạm 1.800/ngày nhưng
  không bao giờ bị chặn, để giám sát, reconcile và auto-flatten vẫn chạy sau khi hết ngân sách lệnh.

Ngân sách < 1.000, thấp hơn nhiều so với mức "hyperactive bot, > 2.000 requests/day" đang được hiểu từ
FTMO. Định nghĩa chính xác "request" là luật `request_definition_and_limit` (`must_verify`); nếu FTMO
xác nhận lời gọi đọc cũng tính, phải giảm số lời gọi mỗi chu kỳ (hiện khoảng 12 ở dry-run/demo, 8 ở
funded, tức 770–1.150/ngày) trước khi bật funded.

**Execution safety thật.** `ExecutionSafety` trong bridge nhận environment (`dry-run`/`demo`/`funded`)
và login thật thay cho mặc định `paper` (blocker d5); `EntryGuard` (rollover nửa đêm Prague, gần giờ
đóng cửa theo market calendar của broker profile) chạy ở mọi mode.

## Vẫn bị cấm

* Live trading: `XAU_EDGE_ENABLE_LIVE_TRADING=true` vẫn bị `Settings` từ chối; `assert_live_trading_disabled`
  vẫn chạy ở mọi entry point.
* Không gate nào bị gỡ hay nới: evidence gate, `RiskEngine`, `ExecutionSafety`, news guard, kill switch,
  reconciliation, idempotency. Override D2 là ngoại lệ duy nhất, đúng như trên.
* Không endpoint API nào nhận hướng/lot/SL/TP; không có lệnh CLI nào bỏ bậc rollout.
* AI không tự bật cờ funded, không nhập mật khẩu, không gửi lệnh trên tài khoản funded.

## Hệ quả và việc còn mở

* Bật funded cần đủ: Track 1 (A) hoặc chủ dự án ký override D2; D6 không còn mục `unverified`; soak
  dry-run và demo đạt tiêu chí (T5.2, T5.3); checklist go-live đã ký.
* **Request budget so với tải thật.** Trần cứng chỉ áp lên trade request (xem trên). Nếu FTMO xác nhận
  lời gọi đọc cũng là "request", phải giảm lời gọi mỗi chu kỳ trước khi bật funded.
* NSSM service: `scripts/install_services.ps1 -ConfirmMode DEMO|FUNDED` truyền `--confirm-mode` cho
  bot; không có tham số thì service chạy dry-run.
