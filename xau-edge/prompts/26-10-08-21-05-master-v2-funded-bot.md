# Prompt: Master v2: Từ demo tới bot FTMO funded hoàn chỉnh

> Dành cho Claude Code. Chạy trong thư mục `xau-edge/`. Prompt này dài và có nhiều track độc lập:
> hãy dùng subagent song song theo track, nhưng quản lý K, ledger và ADR tập trung ở agent chính.

---

## VAI TRÒ

Bạn là **Principal Trading Systems Engineer** kiêm **Lead Quant Researcher**, **Risk Engineer** (chuyên luật
prop firm FTMO) và **DevOps** cho hệ thống chạy 24/5 trên Windows. Bạn xây hệ thống để chạy tiền thật, nên
thứ tự ưu tiên là: **không mất tài khoản > không bỏ lỡ lệnh > tối ưu lợi nhuận**.

## BỐI CẢNH

- Repo: `xau-edge/` (XAUUSD, MT5, Python/uv, dashboard Next.js).
- Chủ dự án đã PASS thi quỹ FTMO và có tài khoản **FUNDED**. Mục tiêu: bot chạy trực tiếp trên tài khoản
  funded, sau khi đã kiểm chứng trên demo.
- Đọc trước khi làm (bắt buộc):
  1. `CLAUDE.md`: pre-mortem với mã blocker a1…h3.
  2. `docs/research/edge-program/00-diagnosis.md`: Phase 0 đã xong; Cổng duyệt 1 **đã được duyệt** (xem D1).
  3. `docs/research/ftmo-rules-from-source.md`: luật FTMO và các gap của bot (mục 5, 7).
  4. `docs/evals/edge-criteria.md`, `docs/reports/checkpoint-1.md`, `docs/reports/final-status.md`.
  5. `docs/decisions/0018-*.md`, `docs/decisions/0019-demo-execution-scope.md`.
  6. `prompts/26-10-08-20-31-demo-bot-final-activation.md` (Phase A–F, chưa chạy).
  7. `docs/diagrams/end-to-end-flow.md`.
- Hiện trạng:
  - Nghiên cứu đã xong với kết quả âm tính.
  - Bot demo dry-run chạy được nhưng luôn trả về `WAIT`.
  - Đường lệnh có lỗi c2 (so giá bid với ask) và c3 (SL/TP chưa làm tròn).
  - Chưa có supervisor hay cảnh báo đẩy.
  - Live/funded đang bị chặn có chủ đích.

---

## KHỐI QUYẾT ĐỊNH CỦA CHỦ DỰ ÁN (đã chốt, AI KHÔNG được tự đổi)

- **D1. Cổng duyệt 1 của edge program: ĐÃ DUYỆT.**
  - N = 6 giả thuyết.
  - **Giữ nguyên 7 tiêu chí** trong `edge-criteria.md`, không sửa đổi.
  - Được đọc thêm lịch sử MT5 ở chế độ read-only (M15/H1/H4/D1, xa nhất có thể). Phải định nghĩa splits
    MỚI cho phần dữ liệu MỚI và commit TRƯỚC khi xem bất kỳ kết quả nào.
  - Test cũ (2026-05-01..2026-10-07) giữ làm holdout khóa.
  - Điều kiện dừng: hết 6 giả thuyết hoặc K chạm trần đã ghi trong ledger.
- **D2. Chính sách edge cho funded: (b) owner-override.** Cho phép chạy chiến lược chưa VALIDATED trên funded,
  với các điều kiện:
  - Rủi ro trần **0,25%/lệnh**.
  - Gắn nhãn `UNVALIDATED` trên journal, status, dashboard và comment lệnh.
  - Bắt buộc đi qua rollout theo bậc (T4.3).
  - Nếu có chiến lược VALIDATED thì ưu tiên chiến lược đó và áp dụng mức rủi ro theo Monte Carlo (T1.5).
  - Chiến lược dùng cho override phải là chiến lược có kết quả tốt nhất trong ledger **sau chi phí ở kịch bản
    bi quan**, được chọn bằng quy tắc ghi trước, không chọn tay.
- **D3. Kênh cảnh báo:** Telegram (bot token và chat id đọc từ `.env`).
- **D4. Nơi chạy:** VPS Windows; supervisor là NSSM.
- **D5. Auto-flatten:** đóng vị thế của bot và trip kill switch khi equity còn cách sàn ngày ≤ **1%** vốn ban đầu.
- **D6. Luật FTMO** về EA, news window, định nghĩa "request", giờ đóng cửa: chủ dự án tự xác minh với FTMO và ghi
  vào `configs/prop/ftmo_funded.yaml`. Khi còn mục `must_verify` ở trạng thái `unverified`, code **phải từ
  chối** bật funded.

---

## TRACK 1: EDGE PROGRAM (tiếp từ Phase 1)

- **T1.1 Strategy registry.**
  - Tách binding Baseline C khỏi `src/xau_edge/signals/engine.py` và `src/xau_edge/signals/evidence.py`.
  - Evidence tra theo `strategy_id` + config hash + dataset hash. Viết ADR mới.
  - Khi chưa có chiến lược VALIDATED, hành vi `WAIT` không đổi (trừ khi D2 override được bật ở T4.4).
- **T1.2 Mở rộng dữ liệu read-only** theo D1: ghi dataset hash, định nghĩa splits mới vào `edge-criteria.md`,
  commit TRƯỚC khi chạy bất kỳ backtest nào trên dữ liệu mới.
- **T1.3 Đăng ký trước 6 giả thuyết** tại `docs/research/edge-program/hypotheses/H01..H06.md`.
  - Ưu tiên các hiệu ứng có cơ sở trong `00-diagnosis.md` mục 4: London/NY open, London fix, volatility regime,
    daily momentum/mean-reversion, Asia range.
  - Ưu tiên khung M15/H1/H4 và session London vì chi phí thấp hơn.
  - Tối đa 2 tham số × 3 giá trị mỗi giả thuyết; mọi biến thể đều đếm vào K.
  - Commit file đăng ký trước file kết quả.
- **T1.4 Thực nghiệm:** Dev → Val → Test (đúng một lần cho mỗi ứng viên PASS Val), theo 7 tiêu chí với `0.05/K`.
  Kịch bản chi phí bi quan (slippage ×2) phải vẫn dương. Ghi tất cả vào `docs/research/edge-program/ledger.md`.
- **T1.5 Prop filter Monte Carlo** (bootstrap theo khối ngày):
  - Tính xác suất vi phạm 5% daily và 10% max loss trong 30/60/90 ngày.
  - Chọn mức rủi ro mỗi lệnh giữ xác suất vi phạm ≤ 5% trong 90 ngày.
  - Áp dụng cho cả chiến lược VALIDATED lẫn chiến lược override của D2 (lấy giá trị nhỏ hơn giữa mức này và 0,25%).
- **T1.6 Kết luận:** `docs/research/edge-program/final-verdict.md` ở trạng thái **(A) EDGE VALIDATED** hoặc
  **(B) NO EDGE WITHIN BUDGET**.
  - Nếu (A): nối vào registry bằng ADR ủy quyền và parity test giữa backtest và signal engine.
  - Nếu (B): ghi rõ chiến lược nào được chọn cho override theo D2 và vì sao.

**Quy tắc chống overfitting (vi phạm thì hủy kết quả):**

1. Không nhìn dữ liệu Val/Test khi thiết kế.
2. Mọi lần chạy, kể cả lỗi hay bỏ dở, đều đếm vào K.
3. Không sửa giả thuyết sau khi đã thấy kết quả.
4. Không chạy lại Test.
5. Một reviewer độc lập (subagent khác) kiểm tra lại mọi ứng viên PASS: đảo dấu tín hiệu, tính tay vài lệnh từ bar thô.

---

## TRACK 2: SỬA LỖI ĐƯỜNG LỆNH VÀ LỚP RỦI RO (song song với Track 1)

Với mỗi lỗi: viết test FAIL trước, sửa, rồi chạy cho test PASS. Ghi mã blocker vào commit message.

- **T2.1 (c2)** `entry_reference` và kiểm tra deviation theo đúng phía giá: ask cho BUY, bid cho SELL. Deviation dựa
  trên phân phối spread đo được (`00-diagnosis.md` mục 2). Viết ADR. Test dùng fake có spread 31 point.
- **T2.2 (c3/c7)** Làm tròn SL/TP theo `symbol_info.digits`; kiểm tra `trade_stops_level` và `trade_freeze_level`
  trước khi gửi lệnh.
- **T2.3 (c4)** Bọc mọi chu kỳ trong try/except có phân loại lỗi, kèm backoff và reconnect MT5. Lỗi tạm thời không
  được làm tiến trình thoát (`scripts/demo_trader.py`).
- **T2.4 (c5)** Khi lệnh ở trạng thái UNKNOWN: truy vấn lại positions/deals theo magic + comment trong N giây trước
  khi trip kill switch.
- **T2.5 (c6)** Lock file ghi PID và thời gian; tự giải phóng nếu PID không còn sống (`execution/runner.py`).
- **T2.6 (c8)** Partial fill: ghi nhận và reconcile đúng volume thực, không gửi bù.
- **T2.7 (d1)** Gọi `RiskEngine.check_account` ở **mọi** chu kỳ, kể cả khi đang có vị thế.
- **T2.8 (d2)** Balance đầu ngày = balance hiện tại trừ net P/L của các deal đóng từ 00:00 Europe/Prague (lấy từ lịch
  sử deal). Giá trị đang lưu chỉ dùng làm dự phòng. Bắt buộc khai báo `*_INITIAL_CAPITAL`.
- **T2.9** Equity **bằng đúng** ngưỡng sàn là vi phạm: đổi `<` thành `<=` ở `src/xau_edge/risk/engine.py:130` và ở
  mọi phép so sánh buffer.
- **T2.10 (d4)** Sizing theo giá khớp dự kiến (ask/bid), không theo giá close.
- **T2.11 (d5)** `ExecutionSafety` trong bridge nhận đúng account thật, thay cho mặc định `"paper"`.
- **T2.12 Guard luật FTMO** (theo `ftmo-rules-from-source.md` mục 7):
  - Không mở lệnh nếu vị thế có thể còn mở qua 00:00 Prague trong vùng cảnh báo.
  - Không mở lệnh trong biên trước giờ nghỉ hằng ngày (16:50 NY) và trước giờ đóng cửa cuối tuần.
  - Đếm request mỗi ngày trong journal, với ngân sách cứng < 1.000.
  - Đếm số ngày giao dịch theo ngày Prague.
- **T2.13 Auto-flatten** theo D5: đóng vị thế của bot, ghi journal, trip kill switch, gửi cảnh báo.

---

## TRACK 3: VẬN HÀNH 24/5 VÀ DỮ LIỆU TIN TỨC (song song)

- **T3.1 Lịch tin:**
  - Viết loader từ nguồn có `available_at`, kèm job cập nhật hằng ngày và dòng coverage.
  - Gửi cảnh báo khi coverage còn dưới 7 ngày.
  - Khi không có dữ liệu thì giữ fail-closed.
- **T3.2 Raw store (b2):**
  - Gộp các file parquet theo tháng.
  - Catalog cache hash theo mtime.
  - Benchmark độ trễ chu kỳ trước và sau khi sửa.
- **T3.3 Supervisor:**
  - Viết script cài NSSM cho bot và API: tự restart khi lỗi, tự chạy khi khởi động máy.
  - Viết hướng dẫn auto-login terminal MT5 trên VPS.
- **T3.4 Cảnh báo Telegram** cho các sự kiện: kill switch trip, reconcile mismatch, dữ liệu cũ, heartbeat chết, gần
  sàn daily loss, lệnh bị từ chối, coverage lịch tin sắp hết, auto-flatten, chuyển bậc rollout.
- **T3.5** Ghi log ở mức INFO ra file xoay vòng. Kiểm tra lệch giờ máy (NTP) mỗi chu kỳ; trip nếu lệch > 5 giây.
- **T3.6 Sửa tài liệu lệch code:**
  - Docstring trong `scripts/demo_trader.py`.
  - `docs/reports/final-status.md`.
  - `AGENTS.md`.
  - `README.md` (thêm ADR-0019, ADR-0020).
  - `/risk/status` phải hiển thị kill switch thật.

---

## TRACK 4: ĐƯỜNG CHẠY FUNDED (code xong, khóa cho tới khi đạt nghiệm thu)

- **T4.1 ADR-0020 "Funded account execution"**, thay thế phần phạm vi của ADR-0018/0019:
  - Cờ riêng `XAU_EDGE_ENABLE_FUNDED_TRADING` (mặc định `false`), tách hẳn khỏi cờ demo.
  - **Không** nhận diện tài khoản bằng `trade_mode`, vì FTMO có thể báo DEMO cho cả tài khoản funded:
    - Dùng whitelist login + tên server + profile tài khoản.
    - Whitelist của demo và funded riêng biệt, không được trùng nhau.
    - Bot chạy chế độ demo mà thấy login funded thì từ chối, và ngược lại.
  - Kiểm tra khi khởi động:
    - In ra mode, server, `trade_mode` và profile luật đang áp dụng. Số tài khoản chỉ in 3 số cuối.
    - Chỉ chạy tiếp khi có cờ xác nhận trên dòng lệnh.
- **T4.2 `configs/prop/ftmo_funded.yaml`:**
  - Ghi luật funded, mỗi luật có trạng thái (`verified_official` / `secondary` / `unverified`), cờ `must_verify`,
    `verified_on` và nguồn.
  - Code từ chối bật funded khi còn bất kỳ luật `must_verify` nào chưa được xác minh.
- **T4.3 Rollout theo bậc.** Cấu hình trong file; mỗi bậc tự kiểm tra tiêu chí trước khi cho lên bậc tiếp:
  - Bậc 0: shadow (sinh intent + `order_check`, không gửi lệnh), ≥ 5 ngày giao dịch.
  - Bậc 1: lot tối thiểu, ≥ 10 lệnh, reject/UNKNOWN = 0.
  - Bậc 2: rủi ro 0,25%/lệnh, ≥ 4 tuần.
  - Bậc 3: chỉ dành cho chiến lược VALIDATED, mức rủi ro theo T1.5. Chiến lược `UNVALIDATED` dừng vĩnh viễn ở bậc 2.
- **T4.4 Cưỡng chế D2 = (b) trong code:**
  - Override chỉ bật được bằng cờ `XAU_EDGE_FUNDED_ALLOW_UNVALIDATED=true` kèm `strategy_id` cụ thể.
  - Rủi ro trần 0,25% không thể vượt bằng cấu hình.
  - Nhãn `UNVALIDATED` xuất hiện ở mọi nơi.
- **T4.5 Dashboard** hiển thị:
  - Mode (DRY-RUN / DEMO / FUNDED) và nhãn VALIDATED/UNVALIDATED.
  - Bậc rollout hiện tại.
  - Khoảng cách tới sàn daily/max loss theo luật FTMO.
  - Số request trong ngày và số ngày giao dịch.
- **T4.6 Test:**
  - Ma trận demo/funded × whitelist × cờ × trạng thái luật × override.
  - Phải chứng minh không thể gửi lệnh funded khi thiếu bất kỳ điều kiện nào.

---

## TRACK 5: NGHIỆM THU VÀ GO-LIVE

- **T5.1** Chạy Phase A–F của `prompts/26-10-08-20-31-demo-bot-final-activation.md` sau khi Track 2 xong.
- **T5.2 Soak dry-run ≥ 14 ngày**, có ít nhất 1 lần ngắt mạng và 1 lần restart terminal:
  - Uptime ≥ 99% số bar M15.
  - 0 bar trùng.
  - Mọi sự cố đều tự hồi phục hoặc đã gửi cảnh báo.
- **T5.3 Demo với lệnh từ tín hiệu ≥ 4 tuần:** tỷ lệ reject/UNKNOWN < 2%; chi phí thật được cập nhật vào ADR-0015.
- **T5.4 `docs/operations/go-live-checklist.md`**, chủ dự án ký từng mục:
  - Luật FTMO đã xác minh bằng văn bản.
  - Mật khẩu demo từng lộ đã được đổi.
  - Whitelist funded đúng.
  - Trạng thái Track 1 (A), hoặc đã ký chấp nhận override D2.
  - Soak và demo đạt tiêu chí.
  - Đã nhận được cảnh báo Telegram trên điện thoại.
- **T5.5 Báo cáo cuối `docs/reports/funded-readiness.md`:** bảng điểm từng track, blocker còn lại, và lệnh chính xác
  để operator bật từng bậc rollout.

---

## RÀNG BUỘC

- AI **KHÔNG** tự bật cờ funded, không nhập mật khẩu, không gửi lệnh trên tài khoản funded. Trên demo, chỉ gửi
  lệnh smoke khi operator đã cấu hình đúng như trong prompt kích hoạt.
- Không gỡ hay nới evidence gate, risk gate, news guard, kill switch, reconciliation. Chỉ được **nâng cấp**
  chúng. Mọi thay đổi phạm vi phải đi qua ADR. Override D2 là ngoại lệ duy nhất, và chỉ theo đúng T4.4.
- Không in secrets hay số tài khoản đầy đủ.
- Mọi thay đổi code phải có test. Các lệnh sau phải xanh:
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy`
  - `uv run pytest`
  - `npm run build` trong `apps/dashboard` (nếu có chạm vào dashboard)
- Commit nhỏ theo từng mục; message ghi mã track và blocker, ví dụ `T2.1 c2: ...`.
- Được chia subagent song song theo track. K, ledger và ADR được quản lý tập trung.
- Tài liệu viết bằng tiếng Việt, thuật ngữ kỹ thuật giữ nguyên tiếng Anh.

## THỨ TỰ VÀ PHỤ THUỘC

- Track 1, 2 và 3 chạy song song ngay từ đầu.
- Track 4 code song song nhưng chỉ test với fake.
- T5.1 cần Track 2 xong. T5.2 cần Track 2 và Track 3 xong.
- **Bật funded cần đủ tất cả:**
  - Track 1 đạt (A), hoặc chủ dự án đã ký override D2.
  - Track 4 xong.
  - T5.2 và T5.3 đạt.
  - D6 không còn mục `unverified`.
  - Checklist đã ký.

## BÁO CÁO SAU MỖI LƯỢT

- Track nào xong mục nào (kèm commit hash), test đã chạy và kết quả.
- Cập nhật bảng blocker trong `CLAUDE.md` (a1…h3) theo ký hiệu ✅ / 🟠 / ❌.
- Quyết định nào đang chờ chủ dự án.
- Nếu Track 1 kết thúc ở (B), phải nói rõ: "Không có edge được kiểm định; bot funded chỉ chạy ở chế độ
  UNVALIDATED theo override D2, rủi ro trần 0,25%/lệnh, tối đa bậc 2."

## DEFINITION OF DONE

- Track 2, 3, 4 xong với toàn bộ test xanh. Track 1 có `final-verdict.md` ở trạng thái (A) hoặc (B).
- Soak 14 ngày và demo 4 tuần đạt tiêu chí. Nếu cần thêm thời gian thực, bàn giao lịch chạy kèm lệnh chính xác.
- `funded-readiness.md` và `go-live-checklist.md` hoàn chỉnh. Cờ funded **vẫn tắt**, chờ chủ dự án tự bật.
