# XAU EDGE — Báo cáo hoàn thành theo Execution Charter V4 (chỉ thêm vào cuối)

Mỗi mục: DATE · SHA · STATE · WHAT CHANGED · TESTS · EVIDENCE · VERDICT · NEXT GATE. Số liệu chỉ lấy từ artifact có đường dẫn; bước chưa chạy ghi **NOT RUN**.

## Bảng công việc

| Milestone | Trạng thái | Bằng chứng |
|---|---|---|
| M0 kiểm tra trạng thái | XONG | prereg `4a03273`; Test-H/Holdout không chạm (`research_v3/data.py` chặn mọi dữ liệu ≥ 2022-01-01) |
| M1 sửa lỗi UI QA #1 #2 #3 + ma trận 6 trạng thái × 3 khung | CODE XONG, test xanh; commit + deploy LIVE chờ xác nhận | `e2e/qa_2026_10_11.spec.ts`, `e2e/terminal.spec.ts` |
| M2 nguyên nhân độ phủ 48.6% + telemetry | XONG (nguyên nhân + watchdog collector); lỗi do máy chủ (phiên Windows kết thúc) chờ chủ dự án | mục M2 dưới đây |
| M3 cost model v2 đóng băng | XONG | `docs/research/edge-program-v3/foundation/cost_model_v2.json` không đổi từ `4a03273` |
| M4 F1 | **FAIL Stage 1 — ĐÓNG** | `results/F1_stage1.json` (`00fafe9`) |
| M5 F3 | **FAIL Stage 1 — ĐÓNG** | `results/F3_stage1.json` (`8da3b87`) |
| F2 | HOÃN (ECONOMICALLY IMPRACTICAL + thiếu dữ liệu lịch tin lịch sử) | `F2_us_macro_reaction.md` |
| M6 Validation / Test-H / Holdout | NOT RUN — không ứng viên nào qua Stage 1 | ledger |
| M7 báo cáo | file này | |

---

## M4 — F1-USDRES-z2.0

- DATE: 2026-10-11 · SHA: implementation `d949b20`, kết quả `00fafe9` · STATE: ĐÓNG.
- WHAT CHANGED: `src/xau_edge/research_v3/{data,execution,stats,f1}.py`, `scripts/run_v3_f1.py`, `tests/research_v3/test_f1_runner.py`.
- TESTS: `pytest tests/research_v3` → `16 passed`; oracle parity 2012H1: 132 sự kiện, 123 lệnh, 0 khác biệt (`results/F1_parity.json`). Review độc lập trước khi chạy: FAIL → sửa 7 điểm trước mọi outcome → re-review PASS WITH NON-BLOCKING NOTES.
- EVIDENCE: `docs/research/edge-program-v3/results/F1_stage1.json` (sha256 563D79B83A556A81…), lệnh `scripts/run_v3_f1.py --stage1`, chạy đúng 1 lần.
- VERDICT: **FAIL**. n = 1601 (200/năm). Gross −0.144R; base −0.283R (CI95 −0.346..−0.220); pessimistic −0.354R; p = 1.0; 0/8 năm dương; placebo percentile 0 (median placebo −0.080R). Win rate gross 29.7% < 33.3% hoà vốn của khung 1:2. Tín hiệu “fade residual” đi ngược thị trường; đảo chiều là kiểm định post-hoc nên **không làm**.
- NEXT GATE: không có. Không F1b.

## M5 — F3-USMOM-0930-1400-1500-1645

- DATE: 2026-10-11 · SHA: sửa đổi prereg `6ca3342` (trước khi viết code), implementation `0651972`, kết quả `8da3b87` · STATE: ĐÓNG.
- WHAT CHANGED: `F3_amendment_1.md` (mặt nạ đồng hồ cho năm chưa chứng nhận, cố định cách đọc), `src/xau_edge/research_v3/f3.py`, `scripts/run_v3_f3.py`, `tests/research_v3/test_f3_runner.py`.
- TESTS: `pytest tests/research_v3` → `21 passed`; oracle parity 2012-01..06 và 2012-10..11 (gồm tuần lệch DST mùa thu): 144 lệnh, 0 khác biệt, gồm ATR tra độc lập và đường pessimistic (`results/F3_parity.json`). Review độc lập: PASS WITH NON-BLOCKING NOTES; đã xử lý 5/6 ghi chú trước khi chạy (ghi chú 6 là đặc điểm của lịch suy luận, xem dưới).
- EVIDENCE: `docs/research/edge-program-v3/results/F3_stage1.json` (sha256 1FE606351FA80DF6…), lệnh `scripts/run_v3_f3.py --stage1`, chạy đúng 1 lần.
- VERDICT: **FAIL**. n = 1735 (217/năm; loại: mặt nạ đồng hồ 135, lễ/đóng sớm 86, thiếu nến mốc 126, độ phủ thấp 3, s=0 1). Gross −0.010R (không có thông tin hướng); spread + trượt giá ≈ −0.20R; base −0.214R (CI95 −0.240..−0.188); pessimistic −0.327R; p = 1.0; 0/8 năm dương; placebo percentile 16.3.
- Ghi chú dữ liệu: lịch nghỉ lễ là lịch suy luận từ nến thiếu của broker. MLK/Presidents/Memorial Day 2012 không có trong lịch nhưng bị loại nhờ quy tắc nến mốc. Tháng 3/2012 có một lỗ dữ liệu M1 thật (09:30 và 16:45 NY thiếu nhiều ngày).
- NEXT GATE: không có.

## M2 — Độ phủ quyết định 48.6%: nguyên nhân gốc

- DATE: 2026-10-11 · STATE: nguyên nhân xác định bằng log runtime; không backfill.
- EVIDENCE (đọc chỉ-đọc `data/trade/decisions-202610*.jsonl` + `data/market/XAUUSD/M1/2026-10.parquet` bằng `trading/coverage.py`): cửa sổ 2026-10-09T12:53Z → 2026-10-11T06:00Z, expected 477, recorded 232, **48.64%**, duplicate 8, late 7, approx 233. Toàn bộ 245 phút thiếu nằm trong **2 khoảng**, không có lỗ lẻ 1 phút:
  1. 2026-10-09 14:43–15:12 UTC (30 phút). `data/logs/collector.log`: `21:43:53 (giờ VN) collector session 2 ended: RuntimeError: copy_rates_from_pos failed: (-10001, 'IPC send failed')`; sau đó **không có** dòng “session 3 started” hay “ended” trong 31 phút, tức lần `connect()`/reconcile kế tiếp bị treo. Chỉ hết khi cả stack khởi động lại lúc 22:14:56 (collector và dashboard cùng giây).
  2. 2026-10-09 17:14 UTC → đóng cửa tuần (215 phút). Quyết định cuối lúc 17:14:22Z; `00:15:14 (VN) SUPERVISOR child exited code=1073807364` (0x40010004, mã Windows khi console bị đóng hoặc phiên kết thúc), sau đó supervisor **không** khởi động lại gì: chính supervisor đã chết theo phiên. Stack chỉ chạy lại vào thứ Bảy.
- WHAT CHANGED: `src/xau_edge/ops/supervisor.py` thêm watchdog heartbeat. Nếu child còn sống nhưng file heartbeat cũ hơn 300 s thì kill + restart, ghi `SUPERVISOR child hung: …`. Thêm `last_restart_reason` và `hung_kills` vào `data/run/supervisor.json` (cùng với `restarts`, `last_exit`, `uptime_seconds` đã có). `scripts/run_market_stack.py` gắn heartbeat `data/market/collector_status.json` (collector ghi mỗi 5 s, cả khi thị trường đóng) cho collector. Khoảng 1 sẽ còn ≈ 5–6 phút thay vì 31.
- TESTS: `pytest tests/unit/ops` → `41 passed` (test mới: child treo bị kill, restart, có lý do trong snapshot và log).
- VERDICT: đồng hồ 15 ngày **chưa bắt đầu** (độ phủ < 95%). Khoảng 2 là vận hành máy chủ (phiên Windows/console kết thúc), code không tự sửa được. Cần chủ dự án chọn: chạy stack bằng Task Scheduler “Run whether user is logged on or not” hoặc không cho máy ngủ/đăng xuất khi thị trường mở. Charter cấm đổi credential nên agent không tự làm.
- NEXT GATE: deploy watchdog khi thị trường ĐÓNG; đo lại độ phủ sau ≥ 1 ngày giao dịch.

## M3 — Cost model

- `foundation/cost_model_v2.json` không đổi từ `4a03273` (git log, working tree sạch). MEASURED: spread tick từ 2021-10, spread nến trước đó. ASSUMED: hệ số spread 1.6/2.4 (2011–2023), trượt giá 3/6 điểm mỗi lần khớp. UNKNOWN: commission (0, báo cáo break-even), swap lịch sử (chỉ có swap MT5 hiện tại −69.25/−4.2 điểm đọc 2026-10-11T06:16Z).
