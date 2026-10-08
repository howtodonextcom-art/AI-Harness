# Prompt: Web Control Plane: vận hành bot FTMO Demo từ giao diện web (localhost)

> Dành cho Claude Code / công cụ AI gia công. Chạy trong thư mục `xau-edge/`.

## VAI TRÒ

Bạn là **Senior Full-stack Engineer (FastAPI + Next.js)** kiêm **Trading Systems Safety Engineer**. Bạn xây giao diện
điều khiển cho một bot giao dịch, nên mọi nút bấm phải an toàn kể cả khi người dùng bấm nhầm, bấm hai lần, hoặc bot
đang chạy dở một chu kỳ.

## BỐI CẢNH

- Repo: `xau-edge/` (Python/uv, FastAPI ở `src/xau_edge/api/`, dashboard Next.js ở `apps/dashboard/`).
- Tài khoản: **FTMO DEMO** (chưa phải tiền thật). Chủ dự án muốn vận hành bot hoàn toàn từ giao diện web trên máy
  chạy bot, **trước khi** thiết lập Telegram.
- Đọc trước khi làm:
  - `src/xau_edge/api/app.py`, `src/xau_edge/api/bot.py`. Hiện API chỉ có GET, bind 127.0.0.1, CORS cho
    localhost:3000. Docstring của `bot.py` ghi rõ API không có route thay đổi trạng thái (ADR-0019).
  - `apps/dashboard/components/BotPanel.tsx`, `Dashboard.tsx`, `lib/api.ts`. Panel bot hiện chỉ để xem.
  - Các script: `scripts/demo_trader.py` (vòng lặp bot, có `--confirm-mode`), `scripts/smoke_demo_order.py`,
    `scripts/kill_switch.py`, `scripts/check_health.py`, `scripts/install_services.ps1` (NSSM), `scripts/rollout.py`.
  - `src/xau_edge/execution/` (state.sqlite, journal, runner lock, guards, override),
    `src/xau_edge/brokers/mt5_demo/` (executor, reader, connect), `src/xau_edge/funded/`.
  - `docs/decisions/0019-*.md`, `0020-*.md`, `0021-*.md`; `CLAUDE.md`; `docs/reports/funded-readiness.md`.

## PHẠM VI ĐÃ CHỐT (không tự mở rộng)

Web điều khiển được năm nhóm việc sau:

1. **Preflight/Health:** kiểm tra toàn bộ điều kiện vận hành, không lộ secrets.
2. **Vòng đời bot (tối thiểu):** Start / Stop / Restart. Phần này cần để đổi được chế độ.
3. **Chuyển chế độ DRY-RUN ↔ DEMO:** chỉ cho tài khoản demo nằm trong whitelist.
4. **Smoke order:** 1 lệnh lot tối thiểu trên demo.
5. **Flatten:** đóng toàn bộ vị thế **của bot** (lọc theo magic), rồi trip kill switch.

Truy cập: chỉ localhost (127.0.0.1), một người dùng.

**Ngoài phạm vi, cấm làm:**
- Chọn FUNDED hoặc LIVE từ web.
- Reset kill switch từ web. Việc này vẫn chỉ làm qua CLI `scripts/kill_switch.py`.
- Nhập tham số lệnh tùy ý (symbol, lot, giá, SL, TP).
- Sửa `.env` từ web.
- Truy cập từ xa.
- Telegram.

## KIẾN TRÚC

- **ADR-0022 "Local web control plane".** Ghi rõ phần nào của ADR-0019 bị thay thế: API được phép có route thay đổi
  trạng thái, **nhưng** chỉ nằm trong router control, chỉ localhost, và chỉ cho demo/dry-run.
- **Router control.** Giữ nguyên mọi route GET hiện có. Tạo router mới `src/xau_edge/api/control.py`, prefix
  `/control/*`. Router chỉ được mount khi `XAU_EDGE_WEB_CONTROL=true` (mặc định `false`).
- **Process manager** `src/xau_edge/control/process.py`:
  - Nếu dịch vụ NSSM của bot đã được cài: điều khiển qua `nssm start|stop|restart <service>`, không dùng
    `shell=True`, tham số cố định.
  - Nếu chưa cài: chạy `scripts/demo_trader.py` làm subprocess tách rời và ghi PID vào file.
  - Stop là dừng mềm: bật cờ dừng (trong state, hoặc file sentinel) mà bot kiểm tra giữa các chu kỳ, chờ tối đa
    N giây, quá thời gian mới terminate.
  - Không bao giờ để hai tiến trình bot chạy cùng lúc; tôn trọng lock `data/execution/demo_trader.lock`.
- **Chế độ runtime** lưu trong `data/execution/runtime_mode.json`:
  - Chỉ nhận `DRY_RUN` hoặc `DEMO`. Bot đọc file khi khởi động.
  - File này ưu tiên hơn `.env` **chỉ** cho cặp dry-run/demo. `.env` vẫn là giới hạn trên: nếu `.env` không bật demo
    trading thì web không thể chuyển sang DEMO.
  - FUNDED không bao giờ được đọc từ file này. Validator từ chối mọi giá trị khác, và phải có test chứng minh.
- **Thao tác chạm MT5** (smoke, flatten):
  - Dùng lại đúng code hiện có: `build_smoke_intent`, `Mt5DemoExecutor.submit_smoke`, `close_position`, `Reconciler`.
    Không viết đường gửi lệnh mới.
  - Chỉ chạy khi đã lấy được lock (tức bot đã dừng). Flatten tự dừng bot trước khi đóng lệnh.
- **Journal:** mọi thao tác control ghi journal với `source="web"`, thời gian, kết quả và mã lỗi.
- **Job:**
  - Các thao tác dài (start, stop, smoke, flatten) chạy dạng job: POST trả về `job_id`, GET
    `/control/jobs/{id}` để xem tiến độ.
  - Tại một thời điểm chỉ có một job thay đổi trạng thái.
  - Mỗi job có idempotency key để bấm hai lần không chạy hai lần.

## ĐẶC TẢ TÍNH NĂNG

### F1. Preflight (`GET /control/preflight`)

Trả về danh sách check. Mỗi check gồm `id`, `label`, `status` (`ok` | `warn` | `fail` | `unknown`), `detail`,
`fix_hint`. Không bao giờ trả giá trị secret: chỉ trả "có/không", và với login thì chỉ 3 số cuối.

Các check tối thiểu:

- **Cấu hình `.env`:**
  - `.env` tồn tại; live trading = false; funded = false.
  - Demo trading đã bật; whitelist account có giá trị; whitelist symbol có XAUUSD; magic có giá trị.
  - Có hay không `MT5_TRADE_PASSWORD` (chỉ trả có/không).
- **Terminal MT5:** kết nối được không; account có trong whitelist không; server; trade_mode; trade allowed; đang dùng
  investor password hay trade password (nếu xác định được).
- **Lịch tin:** có đường dẫn không; coverage còn bao nhiêu ngày.
- **Luật FTMO:** số luật `must_verify` còn unverified (chỉ cảnh báo, vì đây là demo).
- **Kill switch:** đang tripped hay không, kèm lý do.
- **Tiến trình bot:** lock có đang bị giữ không; bot có chạy không; PID; mode hiện tại.
- **File và đồng hồ:** đường dẫn state/journal/status có ghi được không; dữ liệu mới nhất cách đây bao lâu; giờ máy
  lệch NTP bao nhiêu.
- **Strategy:** có chiến lược VALIDATED hay không. Nếu không, nói rõ bot sẽ trả `WAIT`.

Kiểm tra MT5 phải read-only và có timeout. Khi bot đang chạy thì không kết nối terminal (vì sẽ vi phạm lock), mà
đọc từ `status.json`.

### F2. Vòng đời bot (`POST /control/bot/start|stop|restart`, `GET /control/bot`)

- Start bị chặn nếu preflight có `fail`, kill switch đang tripped, hoặc bot đã chạy.
- Stop là dừng mềm, và báo lại chu kỳ cuối cùng đã hoàn tất.
- Các trạng thái hiển thị: STOPPED / STARTING / RUNNING (kèm mode) / STOPPING / ERROR.

### F3. Chuyển chế độ (`POST /control/mode`, body `{mode: "DRY_RUN" | "DEMO"}`)

- Chuyển sang DEMO cần đủ: `.env` bật demo trading, có trade password, account trong whitelist, terminal trade
  allowed, kill switch không tripped, preflight không có `fail`.
- Xác nhận 2 bước trên UI: một hộp thoại mô tả hậu quả, và người dùng phải gõ đúng chữ `DEMO`.
- Các bước thực hiện: dừng bot → ghi `runtime_mode.json` → khởi động lại bot → xác nhận bot báo đúng mode trong
  `status.json`.
- Chuyển về DRY_RUN không cần gõ xác nhận, nhưng vẫn ghi journal.

### F4. Smoke order (`POST /control/smoke`)

- Chỉ cho phép khi đủ các điều kiện:
  - Mode DEMO khả dụng theo F3.
  - Kill switch không tripped.
  - Bot không có vị thế mở.
  - Không rơi vào vùng chặn của guard FTMO (qua đêm Prague, giờ nghỉ hằng ngày, cuối tuần).
  - Không nằm trong cửa sổ tin tức (nếu đã có lịch).
- Xác nhận: gõ `SMOKE`. Giới hạn tối đa 1 lần mỗi 10 phút và 5 lần mỗi ngày.
- Thực hiện đúng như `scripts/smoke_demo_order.py`:
  1. Dừng bot nếu đang chạy.
  2. Lấy lock.
  3. Gửi lệnh 0.01 lot có comment SMOKE, giữ vài giây, rồi đóng.
  4. Reconcile.
  5. Khởi động lại bot nếu trước đó bot đang chạy.
- Hiển thị kết quả: status, retcode, giá khớp, slippage (points), thời gian round-trip, reconcile có sạch không. Ghi
  rõ "không phải bằng chứng edge".

### F5. Flatten (`POST /control/flatten`)

- Luôn được phép, kể cả khi kill switch đã tripped; không cần preflight sạch.
- Xác nhận: gõ `FLATTEN`.
- Các bước thực hiện:
  1. Trip kill switch với lý do `WEB_FLATTEN`, **trước** mọi bước khác.
  2. Dừng bot.
  3. Đóng từng vị thế có magic của bot. Không đụng vị thế mở thủ công.
  4. Reconcile.
  5. Báo kết quả từng vị thế.
- Nếu đóng thất bại: báo rõ ticket nào còn mở và hướng dẫn đóng tay trong MT5.
- Sau flatten, bot không tự khởi động lại. Reset kill switch chỉ làm qua CLI; giao diện hiển thị đúng lệnh cần chạy.

## GIAO DIỆN (`apps/dashboard`)

- Thêm trang/tab mới "Điều khiển" (hoặc mở rộng BotPanel), gồm:
  - Thẻ Preflight: danh sách check tô màu theo trạng thái, có nút Chạy lại.
  - Thẻ Bot: trạng thái kèm các nút Start/Stop/Restart.
  - Thẻ Chế độ: DRY-RUN/DEMO.
  - Thẻ Smoke.
  - Thẻ Flatten: màu cảnh báo, đặt tách xa các nút khác.
  - Log/journal cập nhật liên tục (poll mỗi 2–5 giây).
- Nút nào chưa đủ điều kiện thì bị disable kèm lý do. Lý do lấy từ API, client không tự suy luận.
- Banner luôn hiển thị: tài khoản DEMO, mode hiện tại, trạng thái kill switch, và dòng "Không có edge được kiểm định:
  bot sẽ WAIT" khi đúng như vậy.
- Không có ô nhập tham số lệnh nào.
- Token control:
  - API sinh token ngẫu nhiên mỗi lần khởi động và ghi vào file chỉ người dùng hiện tại đọc được.
  - Dashboard lấy token qua route server-side của Next.js. Không nhúng token vào bundle client, không dùng
    `NEXT_PUBLIC_`.

## BẢO MẬT (bắt buộc, phải có test)

- API control chỉ bind 127.0.0.1. Từ chối request nếu Host header không phải `127.0.0.1:<port>` hoặc
  `localhost:<port>` (chống DNS rebinding).
- Mọi POST phải có đủ: header `X-XAU-Control-Token` đúng, `Origin` thuộc `ALLOWED_ORIGINS`, Content-Type JSON. Thiếu
  một điều kiện thì trả 403.
- Không trả stack trace, đường dẫn file hay secret trong response hoặc log.
- Rate limit cho smoke và flatten như mô tả ở F4/F5.
- Không có route nào nhận mode ngoài `DRY_RUN|DEMO`, và không có route nào chạm cờ funded/live.

## TEST

- **Unit:**
  - Process manager, cả nhánh NSSM lẫn subprocess, đều dùng fake.
  - Validator của `runtime_mode`: từ chối FUNDED, LIVE và chuỗi lạ.
  - Điều kiện chặn của F2–F5.
  - Rate limit, idempotency, và không cho hai job chạy trùng.
- **API:**
  - Mọi POST thiếu token, sai Origin hoặc sai Host đều trả 403.
  - Preflight không chứa secret: dùng một `.env` giả trong test và quét response tìm các giá trị trong đó.
  - Route table không có route nào cho funded/live.
- **Smoke/flatten với fake MT5:**
  - Flatten chỉ đóng vị thế đúng magic.
  - Kill switch được trip **trước** khi đóng lệnh.
  - Smoke bị chặn khi đang có vị thế mở.
- **Dashboard:** build và type-check xanh. Thêm ít nhất một test Playwright cho luồng hiển thị preflight và hộp thoại
  xác nhận; nếu chưa có hạ tầng thì ghi rõ hạn chế.
- **Gate (tất cả phải xanh):**
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy`
  - `uv run pytest`
  - `npm run build` trong `apps/dashboard`

## RÀNG BUỘC

- AI **không** tự gửi lệnh, không bấm smoke/flatten trên terminal thật, không bật cờ demo/funded, không nhập mật khẩu.
  MT5 chỉ được kiểm thử bằng fake.
- Không gỡ hay nới evidence gate, risk gate, news guard, kill switch, reconciliation, guard FTMO.
- Không in secrets hay số tài khoản đầy đủ.
- Commit nhỏ theo tính năng, ví dụ `W1 preflight: ...`, `W2 lifecycle: ...`.
- Tài liệu mới viết bằng tiếng Việt. Cập nhật `docs/operations/demo-trading.md` với mục "Vận hành từ web", và phần
  README về cách chạy dashboard cùng `XAU_EDGE_WEB_CONTROL`.

## BÁO CÁO CUỐI

1. Tóm tắt: web làm được gì, cách bật (`XAU_EDGE_WEB_CONTROL=true`, lệnh chạy API và dashboard).
2. Bảng tính năng F1–F5: trạng thái, commit, test.
3. Kết quả gate.
4. Ảnh chụp màn hình trang Điều khiển (nếu chạy được dashboard cục bộ với dữ liệu fake).
5. Hướng dẫn cho chủ dự án:
   - Thứ tự thao tác lần đầu trên web: preflight → start dry-run → chuyển DEMO → smoke → theo dõi.
   - Những việc vẫn phải làm bằng CLI.

## DEFINITION OF DONE

- F1–F5 hoạt động với fake, đủ test, gate xanh.
- Không có đường nào từ web tới FUNDED/LIVE hay tới reset kill switch, và có test chứng minh điều đó.
- ADR-0022 và tài liệu vận hành đã được cập nhật.
- `XAU_EDGE_WEB_CONTROL` mặc định là `false`; khi bật lên, dashboard hiển thị trang Điều khiển.
