# Review prompt "Demo Bot Web App" và mức hoàn thành dự kiến (2026-10-08)

Viết cho chủ dự án. Đối tượng review: `prompts/261008-18-24-demo-bot-web-app.md`. Chỉ đọc repo, không sửa code,
không sửa prompt gốc. Con số hoàn thành là **ước lượng có căn cứ, chưa kiểm chứng bằng chạy thật**.

## 1. Kết luận

1. Prompt **tốt về hướng và an toàn** (fail-closed, dry-run mặc định, không endpoint đặt lệnh tùy ý, "WAIT vẫn là đúng").
2. Prompt **cần sửa trước khi chạy**: có 3 xung đột trực tiếp với repo (test quét `execution/`, ADR-0018, route-table test)
   sẽ làm agent bế tắc hoặc xóa/né safety test.
3. Prompt **gói 3 sprint (15–17) vào một lượt** nhưng không có Gate A/B, review độc lập, commit/CI theo phase như
   vòng ECC của dự án.
4. Prompt **bỏ sót** nhiều mục của `gap-audit.md`: dữ liệu news (A6), đo chi phí thật (A7), alert (A5), chaos test (A8),
   chế độ smoke (C1), kiểm tra luật FTMO (C5).
5. Dù thực thi tốt, **bot sẽ không đặt lệnh demo nào**: evidence gate đóng và mọi tín hiệu bị `NEWS_UNKNOWN`.
   Đường gửi lệnh chỉ được kiểm bằng fake MT5, chưa bằng `order_send` thật.

Đánh giá: **cần sửa trước, rồi dùng** (không nên chạy nguyên bản).

## 2. Sai lệch với repo

| # | Prompt nói | Thực tế (bằng chứng) | Mức |
|---|---|---|---|
| D1 | Tạo `execution/mt5_demo.py` dùng MT5 | `tests/unit/execution/test_trader.py:150-154` quét **mọi** file `execution/*.py` và fail nếu có `MetaTrader5`, `order_send`, `order_check`, `positions_close`. Prompt cấm "xóa safety test" nhưng không nói sửa thế nào | **CAO** |
| D2 | ADR-0019 "demo-only" | ADR-0018 ghi "no broker order API under `execution/`" là **quyết định**, không phải thiếu sót. Prompt không nói ADR-0019 phải **amend/supersede** ADR-0018 và điều kiện (evidence, cost model, kill switch bền vững, review độc lập, quyết định chủ dự án) áp cho live hay cho demo | **CAO** |
| D3 | `POST /bot/kill-switch/trip` | `api/app.py:5` + ADR-0018: một test duyệt route table và đòi **đúng một** route ghi (`POST /paper/orders`); CORS chỉ cho GET nên nút trên dashboard không POST được. Không có xác thực, nên trang web nào trên máy cũng có thể gọi (CSRF cục bộ) | **CAO** |
| D4 | Biến `XAU_EDGE_ENABLE_DEMO_TRADING`, `XAU_EDGE_DEMO_DRY_RUN` | Chưa tồn tại. `config.py` chỉ có `enable_live_trading` (validator cấm bật). `.env.example` chỉ có `ENABLE_LIVE_TRADING` | TB (Phase A tạo được) |
| D5 | "MT5 client protocol fake-testable", "DEMO guard ở mọi operation" | `ReadOnlyMt5Client` dùng allowlist `__getattr__`, `Mt5Client` protocol không có hàm lệnh, `_require_demo` là method riêng của `Mt5BarSource`. Cần client/guard mới dùng chung, prompt không nêu | TB |
| D6 | `OrderIntent` + bridge mới | Đã có `Order` (không có magic/comment), `PaperTrader` (signal → risk → safety → broker), `ExecutionSafety`, sizing. Prompt không bảo **tái dùng** pipeline này; dễ tạo pipeline song song bỏ qua risk/safety | **CAO** |
| D7 | Persistent kill switch "không tự reset" | `KillSwitch.reset(confirm="I understand the risk")` đã có. Prompt không nói đường reset thủ công (CLI? file?) nên phát sinh mâu thuẫn "không reset" vs vận hành | TB |
| D8 | Tên file/ADR/trường tín hiệu | Đúng: ADR-0018 tên khớp; `Signal` có `inputs_hash`, `entry_zone`, `stop_loss`, `take_profit_1`, `signal_expiry`. "news status" không phải trường: suy ra từ `reasons` (`NEWS_UNKNOWN`) | Thấp |
| D9 | Credentials | `.env.example` có `MT5_PASSWORD`; docstring `source.py` nói dùng mật khẩu **investor** (chỉ đọc). Gửi lệnh cần mật khẩu giao dịch: prompt không nói tách biến, rủi ro lẫn lộn. Roadmap đã ghi mật khẩu demo từng lộ trong chat, chưa rõ đã đổi | TB |

## 3. Lỗ hổng an toàn và thiếu sót

| # | Vấn đề | Hậu quả | Mức |
|---|---|---|---|
| S1 | Không quy định hành vi khi kill switch trip: có đóng vị thế đang mở không? | Vị thế bị bỏ rơi hoặc đóng ngoài ý muốn | CAO |
| S2 | `max_hold_until` có trong `Order`, không ai đóng lệnh khi hết hạn (daemon phải làm) | Vị thế vượt thời gian giữ | CAO |
| S3 | Tham số lệnh thật: deviation/slippage, filling mode, lot step/min/max của symbol, kiểm margin, requote | Lệnh bị từ chối hoặc khớp xấu; chỉ lộ ra khi chạy thật | TB-CAO |
| S4 | Rớt kết nối giữa `order_send` và phản hồi (kết quả không xác định) | Lệnh trùng hoặc mất dấu; cần "unknown state → trip kill switch" | CAO |
| S5 | Reconcile mâu thuẫn: "chỉ quản lý vị thế có magic" vs "vị thế thủ công cùng symbol → trip" | Hành vi không xác định | TB |
| S6 | Giờ thị trường: cuối tuần, rollover, lệch giờ máy/broker (đã có `BrokerClock`, prompt không nhắc) | Quyết định trên dữ liệu cũ | TB |
| S7 | Không có alert (chỉ log + heartbeat); không ai biết bot chết | Chạy không giám sát | TB |
| S8 | Điều kiện nghiệm thu "chạy 24h" không kiểm được trong CI | Nghiệm thu bằng lời | TB |
| S9 | Single-instance lock: không nêu cơ chế chống hai tiến trình (và hai máy) | Lệnh trùng | TB |
| S10 | Không có chế độ smoke (C1): đường gửi lệnh không bao giờ chạy trên MT5 thật | Lỗi chỉ phát hiện sau này | CAO (về giá trị kiểm chứng) |

## 4. Mức hoàn thành dự kiến

Giả định: một agent giỏi, làm theo prompt đúng văn bản, có test và kiểm tra như prompt đòi, sau khi xử lý xung đột D1–D3 hợp lý.
"Hoàn thành" = đạt acceptance criteria của chính phase đó.

| Phase | Nội dung | Dự kiến | Lý do giảm |
|---|---|---|---|
| A | Scope, ADR-0019, env | 90–95% | D2/D4 cần xử lý; dễ |
| B | State bền vững, kill switch | 85–90% | Cần thiết kế fail-closed khi state hỏng; test restart được |
| C | Order intent, bridge | 75–85% | D6: nguy cơ pipeline song song; idempotency qua restart khó |
| D | MT5 demo broker | 70–80% | Chỉ fake test; S3/S4 không kiểm được; D1 |
| E | Reconcile | 70–80% | S5 mơ hồ; nhiều ca biên |
| F | Bot runner | 60–70% | S2/S8/S9; "24h" không tự kiểm chứng; phụ thuộc terminal MT5 |
| G | API + dashboard | 75–85% | D3; không CI browser test |
| H | Docs/runbook | 80–90% | Runbook đúng chỉ khi F/D đúng |
| **Tổng theo checklist của prompt** | | **≈ 75–80%** | |

Theo ba lớp:

| Lớp | Mức | Giải thích |
|---|---|---|
| (a) Hạng mục kỹ thuật prompt đòi | ≈ 75–80% | Bảng trên |
| (b) Mục tiêu `gap-audit.md` | ≈ 50–55% | Bao phủ A1–A4, một phần A5; **không** có A6 news, A7 chi phí, A8 chaos, B1–B3, C1, C5 |
| (c) "Bot demo chạy được và đặt lệnh" | **thấp (≈ 30–40%)** | Chạy được ở dry-run/WAIT. Lệnh demo thật: **không có**, vì evidence gate đóng và `NEWS_UNKNOWN`; đường lệnh chưa từng chạm MT5 thật |

Độ tin cậy ước lượng: trung bình. Ba điều làm lệch: (1) cách agent giải D1–D3 (xóa hay nới test sẽ làm giảm chất lượng,
không tăng "hoàn thành"); (2) có hay không MT5 demo chạy sẵn để test thủ công; (3) có nguồn lịch kinh tế hay không.

## 5. Sửa prompt, xếp theo ưu tiên

**Bắt buộc**

1. **D1.** Thêm vào Phase D: *"Test `test_the_execution_package_never_imports_a_broker_api` không được xóa. Đặt code gọi MT5 trong một
   package riêng `src/xau_edge/execution_mt5/` (chỉ đây được import `MetaTrader5`), và đổi test thành: `execution/` vẫn cấm, `execution_mt5/`
   chỉ cho phép trong đúng một file `client.py`, kèm test quét rằng mọi lời gọi `order_send` nằm sau hàm `_guarded_send` đã qua đủ gate."*
2. **D2.** Phase A: *"ADR-0019 phải ghi `Amends: ADR-0018`, liệt kê câu nào của ADR-0018 còn hiệu lực (live cấm) và câu nào đổi (demo executor được phép),
   và ghi các điều kiện: demo-only, evidence gate không đổi, review độc lập bắt buộc."*
3. **D3.** Phase G: *"Kill switch trip qua dashboard cần token cục bộ (header bí mật đọc từ `.env`), kiểm `Origin`, và test route-table cập nhật để cho phép
   đúng các route ghi có tên. Nếu không làm được thì bỏ endpoint, chỉ cung cấp lệnh CLI `scripts/kill_switch.py trip|reset`."*
4. **D6.** Phase C: *"`OrderIntent` chỉ là lớp ánh xạ từ `Signal` vào `PaperTrader`/`ExecutionSafety`/risk engine hiện có (thêm magic/comment vào `Order`).
   Cấm tạo đường signal → broker nào không đi qua `PaperTrader.on_signal`."*
5. **Quy trình.** Thêm: Gate A trước mỗi phase, review độc lập (code + security) cho B, C, D, E, commit + push và kiểm CI xanh sau mỗi phase; chia thành
   **ba lượt** (A+B; C+D+E; F+G+H), mỗi lượt cần duyệt.
6. **S1, S2, S4.** Thêm vào Phase E/F chính sách rõ: trip kill switch → không mở lệnh mới, **không tự đóng** vị thế (chỉ cảnh báo) hoặc đóng, do chủ dự án chọn;
   daemon đóng vị thế quá `max_hold_until`; kết quả `order_send` không xác định → trip.

**Nên có**

7. Thêm Phase I: alert (file + webhook tùy chọn), chaos test (rớt kết nối, requote, từ chối, restart giữa chừng) → A5, A8.
8. Thêm Phase J (hoặc sprint riêng): nguồn lịch kinh tế và nghiên cứu cửa sổ news → A6; đo chi phí từ demo → A7.
9. Thêm chế độ `pipeline_smoke` (C1): lot tối thiểu, nhãn riêng, không tính vào bằng chứng, cần cờ riêng và ADR; nếu không thì nêu rõ đường lệnh chưa chạm MT5 thật.
10. Tách biến credential: `MT5_TRADE_PASSWORD` khác `MT5_PASSWORD` (investor); yêu cầu đổi mật khẩu demo từng lộ.
11. Chốt S3: deviation, filling mode, lot step/min/max, kiểm margin từ `symbol_info`; S5: định nghĩa "vị thế của bot" theo magic, vị thế khác cùng symbol → trip.
12. Chuyển tiêu chí "chạy 24h" thành: test mô phỏng thời gian (clock giả) trong CI + checklist thủ công ghi lại trong runbook.

## 6. Quyết định cần chủ dự án

| Quyết định | Khuyến nghị |
|---|---|
| Có sửa prompt theo mục 5 trước khi chạy? | Có: ít nhất mục 1–6 |
| Chính sách vị thế khi kill switch trip | Không tự đóng; cảnh báo và chờ chủ dự án (tránh đóng ngoài ý muốn) |
| Có bật smoke mode (C1)? | Có, tách biệt, lot tối thiểu, để kiểm đường lệnh thật |
| Kiểm điều khoản FTMO về bot/EA (C5) | Bạn tự kiểm trước khi bật demo execution |
| Đổi mật khẩu demo đã từng lộ | Đổi ngay, trước khi nhập mật khẩu giao dịch vào `.env` |
