# XAU EDGE — Mức hoàn thành và lộ trình tiếp theo (khai thác ECC)

Ngày: 2026-10-11 (GMT+7). HEAD `origin/main` = `3ee3990` (CI `xau-edge-ci` xanh; `b57e07d` xanh).
Phương pháp: chỉ đọc. Số đo LIVE lấy từ `GET /trade/decision` lúc ~01:36 GMT+7; log từ `data/logs/api.log`; telemetry từ `data/trade/decisions-*.jsonl`.
Nhãn nguồn: **[đo]** = đo trực tiếp hôm nay; **[báo cáo]** = trích `WORKSTATION_COMPLETION_FINAL.md` (2026-10-11); **[suy luận]**.

## 1. TL;DR

1. Bàn làm việc desktop gần xong (~90%), nhưng **mức sẵn sàng kiếm tiền chỉ ~25%**: bằng chứng (edge, forward) và đường thực thi mới là phần chặn.
2. Độ phủ quyết định 48,64% **không phải lỗi telemetry**: engine ngừng chạy 2 lần — một lần dừng tay khi dev (30 phút) và một lần supervisor chết cùng console lúc 00:15 GMT+7 rồi không ai khởi động lại trong 8 giờ (215 phút cuối phiên thứ Sáu) [đo].
3. Chiến lược `xau_mtf_baseline v1.1.0` không có edge được kiểm định (Edge Program V1 NO EDGE, V2 Batch A 0/20) [báo cáo]; UI tốt hơn không đổi được điều này.
4. Việc số 1 tuần này (thị trường mở lại 05:05 GMT+7 thứ Hai 12/10): **chạy stack như dịch vụ, không restart stack live khi dev**, để có ≥ 95% độ phủ cho mỗi phiên.
5. Dừng mở rộng chart (chỉ báo, BOS/CHoCH, 2 chart, thêm công cụ vẽ); dồn sức vào: liên tục vận hành → bằng chứng forward → chương trình edge preregister → guard FTMO → bộ não chính tắc → rà cổng Demo.
6. Hai quyết định của chủ dự án (nguồn tin SLA, quản lý vị thế tự động) có khuyến nghị ở mục 7; mặc định an toàn: giữ Forex Factory cho PAPER, KHÔNG bật quản lý vị thế tự động.

## 2. Scorecard 6 trụ cột

| Trụ cột | % | Nhãn | Bằng chứng | Chặn tiền thật? |
|---|---|---|---|---|
| (a) Dữ liệu & feed | 90 | COMPLETE (còn nợ nhỏ) | parity 0 chênh lệch/14 ngày/6 khung; health GOOD; tick trễ ~4 s [đo]. Nợ: chart chỉ tải 400 bar, không D1/W1, không lazy-load (`TerminalView.tsx:279`); store `data/raw` cũ còn tồn tại | Không |
| (b) Quyết định & Signal UI | 90 | COMPLETE | ma trận: SIGNAL UI, CHART, DRAWINGS, JOURNAL, ALERTS, SYSTEM HEALTH = COMPLETE; Playwright mock 291, backend thật 31 [báo cáo] | Không |
| (c) Rủi ro & guard FTMO | 55 | PARTIAL | có SL/TP/hạn giữ 120 phút, giới hạn rủi ro [báo cáo §16]; `governor.flatten_required` không có caller (`trading/governor.py:78`) [đo]; `daily_loss_guard` không bao giờ được gán [đo]; luật FTMO chưa được chủ dự án xác minh | **Có** (Demo/Funded) |
| (d) Thực thi & bộ não chính tắc | 30 | PARTIAL (chỉ thiết kế) | hai bộ não: TradeEngine cho /trade, `signals.engine` cho bot DEMO legacy; `trading/adapter.py` chỉ được test, chưa nối [báo cáo §17] | **Có** (Demo) |
| (e) Bằng chứng (telemetry, forward, edge) | 15 | BLOCKED | độ phủ 48,64% (232/477), forward F0 "FORWARD EVIDENCE INCOMPLETE", 0 setup LIVE [đo]; edge: NO EDGE [báo cáo §24] | **Có — chặn chính** |
| (f) Vận hành | 60 | PARTIAL | supervisor + news refresher + health 12 dòng + CI trình duyệt [đo/báo cáo]; nhưng supervisor không phải dịch vụ (chết theo console), `scripts/install_services.ps1` (NSSM) có nhưng chưa dùng; Telegram chưa cấu hình; tin từ nguồn không chính thức; C: còn 11,7 GB (WARN) [đo] | Có (gián tiếp: làm hỏng (e)) |

**Tổng:** Workstation cho PAPER hằng ngày ≈ 90%. Sẵn sàng tiền thật ≈ 25% [suy luận: trung bình có trọng số, (e) nặng nhất].

## 3. Chẩn đoán độ phủ 48,64%

Số đo [đo] (`/trade/decision → decision_coverage`):

| Trường | Giá trị |
|---|---|
| Cửa sổ | 2026-10-09 12:53 UTC (dòng telemetry đầu tiên) → hiện tại |
| expected / recorded | 477 / 232 |
| missing_intervals | 14:43–15:12 UTC (30 phút); 17:14–20:48 UTC (215 phút, tới lúc đóng cửa thứ Sáu) |
| duplicate / late / approx / outside | 5 / 4 / 233 / 19 |

Đối chiếu log (giờ log = GMT+7):

| Khoảng trống (UTC) | Giờ local | Bằng chứng | Nguyên nhân |
|---|---|---|---|
| 14:43–15:12 | 21:43–22:12 ngày 09/10 | dòng telemetry cuối 14:43:26, tiếp 15:14:57; `api.log`: `2026-10-09 22:14:56 SUPERVISOR started` | **Dừng tay rồi khởi động lại stack** khi dev |
| 17:14–20:48 | 00:14 → 03:48 ngày 10/10 | dòng cuối 17:14:22; `api.log`: `2026-10-10 00:15:14 SUPERVISOR child exited code=1073807364 after 5163s; restart in 2s`, rồi **không có gì đến `08:25:09 SUPERVISOR started`** | Mã `0x40010004` (DBG_TERMINATE_PROCESS — tiến trình bị kết thúc từ bên ngoài, thường do đóng console/kill cây tiến trình). Supervisor định restart sau 2 s nhưng **chính nó cũng chết** → stack tắt 8 giờ |

Loại trừ: không phải collector lỡ nến (ledger có đủ 137/137 nến cuối phiên, [đo] ở audit dữ liệu trước); không phải lỗi ghi telemetry (không có exception trong log; file ghi liên tục tới lúc dừng); không phải kỳ vọng lịch sai (expected lấy từ nến thật của ledger, `trading/coverage.py:7-11`).

Phụ: `approx_rows=233` — các dòng ghi trước khi có trường `m1_bar` nên được ánh xạ theo giờ đồng hồ (`coverage.py:39-44`); không làm sai số đếm nhưng làm giảm độ chính xác LATE. Khoảng 20 lần khởi động supervisor bằng tay trong 2 ngày dev (`api.log`, `collector.log`) cho thấy **stack LIVE đang được dùng làm môi trường dev** — đây là nguyên nhân gốc vận hành.

**Kết luận:** sửa ở vận hành, không ở code telemetry: (1) chạy supervisor như dịch vụ Windows có tự khởi động lại; (2) quy tắc: dev/kiểm thử dùng sandbox `serve_acceptance.py` :8100/:3200, không restart stack LIVE khi thị trường mở; (3) cảnh báo khi API/engine ngừng > 2 phút. Kỳ vọng: phiên đầu tiên chạy liên tục sẽ đạt ≥ 95% [suy luận — kiểm chứng sau phiên 12/10].

## 4. Backlog 4 rổ

Tiêu chí: tác động lên North Star (kiếm tiền an toàn), rủi ro mất tiền, chi phí, phụ thuộc, có phải thay đổi alpha không.

**LÀM NGAY (tuần 12–16/10)**
- Supervisor thành dịch vụ (NSSM qua `scripts/install_services.ps1` hoặc Task Scheduler "restart on failure") + supervisor sống sót khi console đóng — gốc của độ phủ thấp.
- Chính sách "freeze LIVE": dev chỉ trên sandbox; restart LIVE chỉ khi thị trường đóng; ghi vào `AGENTS.md`/`CLAUDE.md` (cần chủ dự án duyệt).
- Cảnh báo ngừng engine/API (Telegram — chủ dự án tạo bot) — không có cảnh báo thì gap 8 giờ sẽ lặp lại.
- Độ phủ theo từng phiên (ngoài số tích luỹ) để cổng 95% đo được từng ngày.
- Dọn ổ C: (11,7 GB) — cache, temp, `node_modules` trùng; không đụng dữ liệu thị trường.
- Viết preregistration cho Edge Program V3 (chỉ tài liệu, trước khi chạy bất cứ backtest nào).

**LÀM SAU (tuần 2–5)**
- Nối guard FTMO: `flatten_required` vào vòng chạy, gán `daily_loss_guard`, xác minh luật FTMO với chủ dự án — cần ADR.
- Bộ não chính tắc: adapter + decision-parity harness ở dry-run (BRAIN-01), phân loại legacy KEEP/ADAPT/DEPRECATE.
- Ngừng `data/raw` cho mọi đường mới (council + ADR), giữ đọc-only cho legacy đến khi parity xong.
- Nguồn tin thứ hai để đối chiếu (nếu Q1 = chưa mua SLA) hoặc tích hợp nguồn SLA (nếu Q1 = có).
- Chart: lazy-load lịch sử + D1/W1 (rẻ, tăng niềm tin dữ liệu; API đã cho 5000 bar).
- Red team vòng 2 cho các sửa của sprint WORKSTATION (báo cáo §21 ghi "chưa có vòng hai").

**HOÃN (sau cổng Demo hoặc khi có bằng chứng)**
- Chỉ báo (EMA/RSI/ATR/Bollinger/VWAP), BOS/CHoCH overlay, chế độ 2 chart, thêm công cụ vẽ.
- Pha di động (báo cáo đã kết luận SHOULD WAIT).
- Quản lý vị thế tự động (break-even, trailing, partial) — chỉ được xét như **giả thuyết preregister** trong chương trình edge.
- Điều tra marker TP bị cắt (không tái hiện được).
- `mypy --strict scripts` (37 lỗi ở script cũ).

**BỎ**
- Thêm vòng A/B và 4 reviewer cho thay đổi UI nhỏ — chi phí cao, lợi ích giảm dần.
- Mở rộng thêm bảng/thẻ UI trên màn giao dịch.
- Tải lại 205M tick (không có bằng chứng cần).
- Bất kỳ việc "đánh bóng" nào không thay đổi một trong: độ phủ, bằng chứng forward, edge, guard, đường thực thi.

## 5. Lộ trình theo pha (tới Demo Preparation Gate — không vượt cổng)

| Pha | Mục tiêu | Definition of Done (đo được) | Ước tính | Cổng ra |
|---|---|---|---|---|
| **1. Liên tục vận hành** | Engine chạy suốt giờ mở cửa | 5 phiên liên tiếp độ phủ mỗi phiên ≥ 95%; 0 gap > 5 phút không giải thích; cảnh báo Telegram khi ngừng > 2 phút được thử | 1 tuần (12–16/10) | Báo cáo độ phủ 5 phiên |
| **2. Bằng chứng forward + chương trình edge** (song song) | Biết chiến lược có edge hay không | Preregistration commit TRƯỚC khi chạy; Dev/Val/Test + holdout không chạm; Monte Carlo; verdict EDGE / NO EDGE được 2 reviewer độc lập duyệt; forward ≥ F1 với độ phủ hợp lệ | 2–4 tuần | `final-verdict` mới; nếu NO EDGE → dừng lộ trình Demo, quay lại nghiên cứu |
| **3. Guard FTMO** | Không vi phạm luật quỹ dù tín hiệu sai | `flatten_required` và daily-loss guard được nối, mỗi luật có test FAIL-trước; luật FTMO đã được chủ dự án xác minh bằng văn bản; ADR | 1 tuần (trong tuần 2–3) | ADR + test xanh |
| **4. Bộ não chính tắc (dry-run)** | Một bộ não, nhiều adapter | adapter Paper/Demo nhận cùng TradingSignal; decision-parity harness 0 khác biệt ≥ 1 tuần LIVE; `data/raw` không còn trong đường mới | 2 tuần (tuần 3–5) | Báo cáo parity + ADR migration |
| **5. Rà cổng Demo** | Quyết định có mở Demo hay không | 7 điều kiện của `canonical-brain.md` §6 đều xanh: dry-run, parity ≥ 1 tuần, độ phủ ≥ 95%, dữ liệu và tin sạch, forward ≥ F2, chủ dự án xác nhận bằng văn bản, FUNDED vẫn khoá | 1–2 ngày | GO/NO-GO có chữ ký chủ dự án |

Điều kiện dừng: nếu Pha 2 kết luận NO EDGE, các Pha 4–5 chỉ làm phần hạ tầng (không mở Demo) và quay về nghiên cứu.

## 6. ECC playbook theo pha

ECC `affaan-m/ECC` @ `4eb71d92` (2.2.3); danh mục: `docs/reports/ECC_CATALOG.md`. Ưu tiên thành phần đã cài trong `.claude/`.

| Pha / việc | ECC | Cách gọi | Input → Output | Gate |
|---|---|---|---|---|
| 1 · Supervisor chết theo console | `orch-fix-defect` + `python-testing` | `/orch-fix-defect` "supervisor exits with child on console close" | log `api.log` 00:15:14 → test tái hiện (FAIL) → sửa → review | A + B |
| 1 · Dịch vụ + cảnh báo | `intent-driven-development` + `production-audit` | skill | yêu cầu "engine luôn chạy" → AC-NNN (ví dụ: gap > 2 phút ⇒ cảnh báo trong 60 s) → audit ship/block | A |
| 1 · Freshness/canary | `latency-critical-systems` (chỉ trong ECC — đọc trực tiếp từ `ECC/skills/`) | đọc skill | feed + engine → chỉ số tuổi p50/p95, canary dữ liệu cũ | B |
| 1 · Độ phủ theo phiên | `tdd-workflow` + `/python-review` | skill + command | `coverage.py` → test trước → hàm theo phiên | B |
| 2 · Preregister edge | `eval-harness` + `council` | skill | giả thuyết H01–H06 → định nghĩa eval và ngưỡng TRƯỚC khi chạy; council chọn danh sách | A |
| 2 · Kiểm định kết quả | `santa-method` + `mle-reviewer` | skill + agent | kết quả backtest/forward → 2 reviewer độc lập PASS; soát leakage, point-in-time | B (claim) |
| 3 · Guard FTMO | `orch-fix-defect` + `security-reviewer` + `prediction-market-risk-review` | command + agent + skill | `governor.py:78`, `position_manager.py` → test FAIL-trước → nối → review "circuit breaker / human approval" | A + B + ADR |
| 3 · Ghi quyết định | `architecture-decision-records` | skill | thay đổi guard → ADR trong `docs/decisions/` (ADR-0026+) | sau B |
| 4 · Thiết kế adapter | `code-architect` + `architect` | agent | `canonical-brain.md` → blueprint file/interface/thứ tự build | A |
| 4 · Xây adapter + harness | `/orch-add-feature` + `ai-regression-testing` + `pr-test-analyzer` | command + skill + agent | blueprint → TDD → test parity vĩnh viễn → báo khoảng trống test | A + B |
| 4 · Retire `data/raw` | `council` → `architecture-decision-records`; `silent-failure-hunter` | skill + agent | 1 store hay 2 → ADR; tìm chỗ đọc store cũ không cảnh báo | A + B |
| 5 · Rà cổng | `production-audit` + `santa-method` + `council` | skill | 7 điều kiện + bằng chứng → ship/block, 2 reviewer, go/no-go | GO/NO-GO |
| Xuyên suốt · Tài liệu | `living-docs-governance` + `docs-governance` (🆕, chưa cài) + `/update-docs` | skill + command | tài liệu ↔ code; audit chỉ đọc `--scope adr` cho chỉ mục ADR | B |
| Xuyên suốt · Commit | `commit-reviewer` (🆕, chưa cài) | agent | diff đã stage → message Conventional Commits theo lịch sử repo | trước commit |
| Xuyên suốt · Kết thúc mỗi việc | `verification-loop` + `/checkpoint` | skill + command | `scripts/dev.ps1 check` → READY / NOT READY | B |

ECC **không** làm được: tạo edge hay chọn chiến lược; hiểu MT5/`copy_rates_*`/giờ server; biết luật FTMO; cài dịch vụ Windows hay tạo bot Telegram (việc của chủ dự án); cưỡng chế bằng hook (dự án chạy "no hooks", `AGENTS.md:93`).

## 7. Quyết định cần chủ dự án

| # | Câu hỏi | Lựa chọn | Khuyến nghị | Mặc định an toàn nếu chưa quyết |
|---|---|---|---|---|
| Q1 | Nguồn tin có SLA? | (a) giữ Forex Factory weekly; (b) thêm nguồn miễn phí thứ hai để đối chiếu; (c) mua nguồn có SLA (ví dụ Finnhub) | **(a)+(b) cho PAPER bây giờ**; **(c) là điều kiện trước cổng Demo** (Demo dùng tin để chặn lệnh thật — không nên dựa vào nguồn không chính thức) | (a); STALE/ERROR đã chặn vào lệnh |
| Q2 | Bật quản lý vị thế tự động (hoà vốn/trailing/partial)? | (a) không; (b) đưa vào chương trình edge như giả thuyết preregister; (c) bật ngay | **(b)**: đây là thay đổi alpha, đổi kỳ vọng R; chỉ bật khi Val/Test chứng minh | (a) — giữ tắt như hiện tại |
| Q3 (mới) | Cài supervisor thành dịch vụ Windows (cần quyền admin) | NSSM / Task Scheduler / giữ console | **Đã chọn Task Scheduler (2026-10-11).** Task `XAU-EDGE Market Stack` đã đăng ký (`install_market_autostart.ps1`). NSSM chỉ dành bot DEMO/FUNDED sau này. | Không mở supervisor từ console |
| Q4 (mới) | Chính sách "freeze LIVE" khi thị trường mở | áp dụng / không | **Áp dụng**: dev và acceptance chỉ trên sandbox :8100/:3200 | — |
| Q5 (mới) | Tạo bot Telegram cho cảnh báo vận hành | có / không | **Có** — không cảnh báo thì gap 8 giờ sẽ lặp lại | — |

## 8. Những điều không được làm trong lộ trình

- Không chỉnh ngưỡng v1.1, không áp v1.2/v1.3, không chạm Test-H/holdout nếu chưa preregister; không đào alpha, không tinh chỉnh nhìn lại.
- Không bật Demo/Funded, không đổi cờ thực thi, không gửi lệnh MT5, không chạy `smoke_demo_order.py`.
- Không nới guard (evidence/risk/news/kill-switch/reconcile/FTMO); thay đổi guard/scope đều cần ADR.
- Không restart stack LIVE khi thị trường mở; không build vào `apps/dashboard/.next` khi stack LIVE đang chạy.
- Không xoá dữ liệu thị trường; không xoá legacy trước khi parity được chứng minh.
- Không mở pha di động trước khi có độ phủ ≥ 95% và ít nhất một tín hiệu LIVE thật.
