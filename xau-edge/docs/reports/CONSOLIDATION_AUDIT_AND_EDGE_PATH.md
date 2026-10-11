# Consolidation Audit & Edge Path

Ngày: 2026-10-11 (GMT+7). Audit chụp tại HEAD `3ee3990`. Sau Gate A hẹp: `a004958` (`k_cap` ledger) + `d732602` (thẻ B sandbox). LIVE `:3000` **không** nhận hai commit đó (không rebuild `.next`).

Phương pháp: search-first + import graph + đo LIVE (chỉ xem) + chẩn đoán Dev (output `%TEMP%\xau_diag`) + closed-loop 14 bước (tới bước 6) với reviewer mù, nhãn xáo. Mỗi khẳng định có file:line, số đo hôm nay, hoặc trích báo cáo (ngày). Điều chưa chắc: **Giả thuyết – chưa xác minh**.

## 1. TL;DR

1. Workstation PAPER gần xong; **không có edge được kiểm định**. Số −0,054R / −0,078R / n=135 lấy từ chẩn đoán Dev `%TEMP%\xau_diag` (cùng n với `data/backtests/trades_baseline_a_development.parquet`). `strategies/baselines.py:36-45` chỉ là mặc định cấu hình Baseline A (RSI/ATR/hold) — **không** chứa các số R. **Không** phải live `xau_mtf_baseline v1.1.0`. Desk live UNVALIDATED vì V1/V2, không vì backtest RSI này.
2. **Hai engine quyết định:** TradeEngine trên `data/market`; `signals.engine.generate_signal` (`signals/engine.py:188`) dùng bởi cả `demo_trader.py:397` và `/paper/*` (`api/app.py:218-219`). Đường thứ ba = `PaperTrader` vốn $100k (`serve_api.py:64-65`) đọc `DatasetCatalog` (`serve_api.py:50-58`), journal `data/paper`. Adapter (tests-only) cộng spread hai lần trên BUY (`adapter.py:63` + `bridge.py:165`). Live PAPER: mặc định 0,25% tại `trading/baseline.py:72`, gọi `size_for_risk` tại `:363`, desk size lại tại `paper_desk.py:495-497`. 0,5% + `contract_size=100` chỉ trên đường legacy/demo (`risk/engine.py:31,40,148-157`).
3. Ba kho dữ liệu: `data/market` (~1,5 GB, live), `data/raw` (~8,4 MB, đóng từ 2026-10-08 13:15 UTC, vẫn phục vụ `/legacy`), `data/research_history` (~3,5 MB — **nguồn thật của Edge V1/V2**, không phải `data/raw`).
4. UI `/trade` 1440×900 **FAIL bài 5 giây**: UNVALIDATED không nằm trên `HeroCard` (ở vùng hệ thống, ảnh `trade-1440-current.png` không có badge bằng chứng). Pixel y≈1179/1651 = đo `getBoundingClientRect` qua Playwright `browser_evaluate` lúc audit; không phải số thiết kế.
5. Không giữ họ giả thuyết A/B/C. Việc edge tiếp theo: **chốt trần K** (ledger 24 vs `STATE.json`/console 48 vs `registration.py` mặc định 24) **trước** mọi giả thuyết mới.
6. Gate A hẹp (prompt `26-10-11-10-00`): **thẻ B trên sandbox** + **một nguồn `k_cap`**. Contract v2 / UNKNOWN=đóng / họ giả thuyết mới **không** làm. Bàn LIVE `:3000` vẫn fold cũ (`trade-1440-current.png`) cho tới restart khi thị trường đóng.

**ECC đã dùng:** giai đoạn 0 `search-first` / `code-explorer`; 1 `refactor-cleaner` (chỉ phân tích) / `silent-failure-hunter`; 2 `architect` + `council`; 3 `intent-driven-development` / `type-design-analyzer`; 4 `product-lens` / `click-path-audit` / `browser-qa`; 5 `eval-harness` / `mle-reviewer`; 6 `santa-method` (2 reviewer / quyết định); 7 `architecture-decision-records` (nháp); 8 `/plan` (Gate A, mục 14).

**ECC không làm được:** tạo edge; hiểu luật FTMO của chủ tài khoản; biết mật khẩu / cấu hình Telegram. Q3: chủ đã chọn Task Scheduler (task `XAU-EDGE Market Stack` đã đăng ký).

## 2. Bảng codebase

Importer = số file `.py` **ngoài** package (đếm ripgrep `from xau_edge.<pkg>`, [inventory](2495056d-21c1-40df-b5a9-a9aa1ffb0e82)). LOC = `Get-Content | Measure-Object -Line` — **ước lượng**, không phải cloc. Live path = stack `run_market_stack.py`.

| MODULE | CURRENT ROLE | KEEP / MERGE / DEPRECATE / ARCHIVE / DELETE LATER | WHY | DEPENDENCIES | MIGRATION STEP | RISK |
|---|---|---|---|---|---|---|
| `market_data/` (40 / 5,2k) | Ledger, collector, tick | **KEEP** | Nguồn live duy nhất | runtime 6 | — | Thấp |
| `trading/` (33 / 7,0k) | Bộ não PAPER | **KEEP** | North Star | runtime 2 | ADR-0026/0028 | Thấp |
| `trading/adapter.py` | TradingSignal→Signal | **KEEP rồi ADAPT** | Tests-only hôm nay | 1 test | Đổi thành `intent_from_signal` | Trung |
| `trading/arming.py` | Tests-only | **DELETE LATER** | 0 importer ngoài test | 1 test | Sau khi xác nhận không dùng | Thấp |
| `api/` (8 / 1,6k) | FastAPI | **KEEP**; DEPRECATE route legacy | `/trade` + `/md` sống | `serve_api` | Retire `/signals` `/paper` cùng `/legacy` | Trung |
| `ops/` (9 / 848) | Supervisor, notifier | **KEEP** | Live stack | `run_market_stack` | Task Scheduler (đã chọn); NSSM chỉ bot sau này | Thấp |
| `news/` (7 / 909) | 6 trạng thái + `news_blocked` | **KEEP cả hai lớp** | UI vs bool guard | engine + signals | — | Thấp |
| `domain/` (5 / 335) | Timeframe, types | **KEEP** | Ubiquitous | nhiều | — | Thấp |
| `features/`, `structure/` | Chỉ báo / regime cho desk | **KEEP** | `market_state.py:24-28` | via trading | — | Thấp |
| `strategies/` | Baseline + clock | **KEEP** (research + clock) | `api/trade.py:28` | mixed | Không dùng để ra lệnh | Thấp |
| `execution/` paper | PaperDesk broker | **KEEP** | Bàn PAPER | trade | — | Thấp |
| `execution/` bridge/runner | Bot DEMO | **DEPRECATE** sau parity | Đường lệnh duy nhất tới MT5 | `demo_trader` | ADR-0026: giữ cửa, bỏ pricing | Cao |
| `signals/` (8 / 689) | Engine legacy | **ADAPT → DEPRECATE** | Bộ não B | `app.py:166`, demo_trader | Sau parity 0 lệch | Cao |
| `brokers/mt5_demo` | Executor khoá | **KEEP (khoá)** | `order_send` duy nhất | demo/control | Cổng Demo §11 | Cao |
| `risk/` | RiskEngine + prop | **KEEP**; **MERGE** sizing về `trading.sizing` cho desk | `risk/engine.py:31` = 0,5%; desk = 0,25% | bridge + serve_api | Một hàm `size_for_risk` | Cao |
| `backtest/` CostModel | Chi phí | **KEEP** (CostModel) | `paper_desk.py:31` | live paper | — | Thấp |
| `experiments/` | Registry | **KEEP** hẹp | `serve_api.py:30` | legacy signal | — | Thấp |
| `research/`, `integrity/` | Console `/research` | **KEEP** | Live console | `api/research.py` | Sửa đọc `k_cap` từ ledger | Trung |
| `patterns/` similarity | Analogue search | **ARCHIVE** (API legacy) | ≠ `trading/patterns.py` | `/patterns` | Đổi tên khi retire `/legacy` | Thấp |
| `models/` | ML metadata | **ARCHIVE** | `/models` | metadata | — | Thấp |
| `control/` | Web control ADR-0023 | **DEPRECATE** (off) | 503 khi tắt; console bẩn | flag | Giữ khoá | Trung |
| `funded/` | FTMO funded | **KEEP khoá** | ADR-0020 | không default | — | Cao nếu mở |
| `evaluation/`, `outcomes/` | Edge programs | **KEEP thư viện**; ARCHIVE runner | Research | scripts | — | Thấp |
| `research_v2/` | V2 runner | **KEEP** (nghiên cứu) | Scripts only | 4 scripts | — | Thấp |
| `forensics/` | Class D | **ARCHIVE** | 1 script + 1 test | gần unused | — | Thấp |
| `integrity/{cost_distribution,dof,events}` | Tests-only | **DELETE LATER** | 0 non-test | 1–2 test | — | Thấp |
| `market_data/importers/file_source.py` | Tests-only | **DELETE LATER** | — | 3 test | — | Thấp |
| `research_v2/stream.py` | Tests-only | **DELETE LATER** | — | 1 test | — | Thấp |

**Script:** 29 được tham chiếu (CI / ops / supervisor). 38 không nằm trong corpus đó — phần lớn là research/ops; **`scripts/dev.ps1` không được ARCHIVE** (cổng ngày, `AGENTS.md`). Không xoá script trong sprint này.

**Trùng trách nhiệm (file:line):** `TradingSignal` `trading/schema.py:63` vs `Signal` `signals/schema.py:50`; `size_for_risk` `trading/sizing.py:57` vs `position_size` `risk/sizing.py:8`; `PropProfile` `risk/prop_rules.py:13` vs `FundedRule` `funded/rules.py:28`; `news_blocked` `news/calendar.py:85` vs `news_status` `news/status.py:95` (lớp khác nhau — KEEP cả hai); `BarLedger` vs `DatasetCatalog`.

## 3. Two-brain & data store

### Hiện trạng

| Não | Entry | Store | Schema | Runtime |
|---|---|---|---|---|
| A Trading Core | `serve_api.py:78-82,103` → `build_trade_engine` (`api/trade.py:44-117`) → `EngineRunner` (`api/trade.py:41,120-141`) | `data/market` | `TradingSignal` | **LIVE PAPER** |
| B Demo + `/paper` | `generate_signal` `signals/engine.py:188` ← `demo_trader.py:397` và `api/app.py:218-219` | `data/raw` via catalog | `Signal` | Bot khoá; `/paper/*` sống |
| Đường paper legacy | `PaperTrader` + broker $100k (`serve_api.py:64-65`); journal `data/paper`; frames `serve_api.py:50-58` | `data/raw` | cùng `Signal` (não B) | UI chỉ `/legacy` |

Tái tạo logic downstream: live PAPER tính lot hai lần ở 0,25% (baseline `baseline.py:72` rồi PaperDesk `paper_desk.py:495-497`). Bridge (đường B) tính lại entry BUY +spread (`bridge.py:165`) và lot qua RiskEngine 0,5% (`risk/engine.py:31,148-157`) — không nằm trên path PAPER live. Executor không thiết kế lại SL/TP (trừ smoke `executor.py:642-655`).

Guard: `flatten_required` không caller ngoài test (`governor.py:78`). `daily_loss_guard` mặc định False (`position_manager.py:106`), không được gán trên `ManagerContext` tại `paper_desk.py:765-777`. Lệnh mới vẫn qua `governor.check` (`paper_desk.py:394`). UNKNOWN=mở chỉ ở `live_source.py:90-92` — không cite `engine.py:225` (đó là `closure_probe`).

### Data stores (đo 2026-10-11)

| Store | Size | Newest | Role |
|---|---|---|---|
| `data/market` | 1526 MB (tick 1392) | `live.json` snapshot lúc đo inventory (~02:27 UTC); file trôi theo collector | Live + desk |
| `data/raw` | 8,4 MB / 75 files | **2026-10-08 13:15 UTC** | Legacy API + `/legacy` |
| `data/research_history` | ~3,5 MB / 6 files | 2026-10-08 21:14 +07 | **V1/V2** (H1 từ 2010, H4 từ 2004, M15 từ 2022-07; không M5) |
| `data/trade` | 24 MB | hôm nay | Telemetry + paper journal |
| `data/backtests` | 9,6 MB | research | Gồm `trades_baseline_a_development.parquet` |

### Kế hoạch 3 bước

1. **Contract v2** (ADR-0028) — chỉ bổ sung trường; **không** gói UNKNOWN=đóng. UNKNOWN=đóng đổi hành vi (hiện coi là mở → bắt WAIT); cấm gói vào contract; giữ ngoài sprint cho tới ADR guard riêng đã duyệt.
2. **`intent_from_signal` + harness OrderIntent** (ADR-0026), dry-run ≥ 1 tuần **và** độ phủ đạt cổng evidence **đã có** (95% trong `trading/coverage.py`, không đặt cổng mới). Adapter cũ không dùng làm đường lệnh (double-spread).
3. **Retire** `signals.engine` / `/paper/*` / `/legacy` / `PaperTrader` khi: no runtime dep, no research dep, parity 0 lệch, migration documented, tests green.

Điều kiện xoá (không phải ngày): parity OrderIntent 0 lệch ≥ 1 tuần LIVE dry-run; coverage ≥ 95%; không còn importer runtime; test legacy chuyển sang adapter; `/legacy` gỡ khỏi app.

**Quyết định (b) — store:** đóng băng `data/raw` **và** `data/research_history` (manifest sha256); `data/market` là kho live + nghiên cứu mới; cutoff theo **đóng nến**; không kho thứ tư; không xoá. ADR-0027.

## 4. Canonical TradingSignal contract + AC

Hiện có (`trading/schema.py:68-115`): xem ADR-0028. So với target:

| Target | Status |
|---|---|
| symbol, timestamp, strategy_id/version, setup_id, reasons, warnings, invalidation, code_version | PRESENT |
| decision | PARTIAL — BUY/SELL/WAIT, không HOLD/EXIT |
| entry/sl/tp/rr/risk/expiry/evidence_label | PARTIAL — tên khác (`entry_price`, `stop_loss`, `evidence_status`, …) |
| bias, setup_phase, provenance | PARTIAL — bias tách H4/H1; phase trong metadata; `inputs_hash` mặc định `""`; `code_version` = strategy version (`baseline.py:165`) |
| source_mode, schema_version | **MISSING** trên model (source_mode gắn sau ở `engine.py:760`) |

**Chọn: bổ sung v2** (reviewer 4,35 / 4,15 PASS). Breaking FAIL. AC: ADR-0028 AC-C1…C5. HOLD/EXIT trên thẻ vị thế (#3) nếu thiếu trên fold. Hợp đồng v2 / `PositionAdvice` / `source_mode` **không** phục vụ quyết định 5 giây tuần này — Gate A riêng, **không vào TOP tuần này**. Hàng #4 của bảng lịch sử §8 vẫn liệt kê v2 (điểm 4,7) như backlog.

## 5. UI — bài 5 giây (LIVE, chỉ xem, 1440×900)

Ảnh: `docs/reports/img/consolidation-2026-10-11/trade-1440-current.png` (viewport), `trade-1440-full.png`, `trade-1920-current.png`. Thị trường đóng; bid 4195.09; CHỜ; PAPER $10.000; 0 lệnh.

| ELEMENT | KEEP / MOVE / COLLAPSE / REMOVE / BUILD | WHY | USER VALUE | PRIORITY |
|---|---|---|---|---|
| Symbol + bid/ask + spread | KEEP | P0 | Biết giá | P0 |
| Thị trường mở/đóng + countdown | KEEP | P0 | Biết có được vào không | P0 |
| Badge `LIVE · ĐÓNG CỬA` | **BUILD** đổi thành `DỮ LIỆU LIVE` | "LIVE" cạnh PAPER đọc như tiền thật (2 reviewer) | Trung thực | P0 |
| Hành động CHỜ + Không vào lệnh | KEEP | P0 | Quyết định | P0 |
| UNVALIDATED / CHƯA KIỂM CHỨNG | **MOVE** lên thẻ quyết định (hiện y=1179, dưới fold) | Honesty | P0 |
| Độ phủ 48,64% (232/477) | **MOVE** cạnh hành động (hiện y=1431+) | Đo trong `docs/reports/WORKSTATION_COMPLETION_FINAL.md` (cùng ngày sprint); cổng 95% = `COVERAGE_OK_PCT` `trading/coverage.py:25`. Sprint này **không** đọc lại `/trade/decision`. | P0 |
| Entry / SL / TP / R:R | **BUILD** trên thẻ (kể cả "— / — / — chưa có setup"); tách 3 dòng khi có số | P0 thiếu trên fold | P0 |
| Thiên hướng (không phải lệnh) | KEEP trên thẻ | P0 | Tránh nhầm bias = lệnh | P0 |
| Rủi ro 0,25%/lệnh + lỗ ngày | KEEP một chỗ; **COLLAPSE** bản trùng ở account card | Reviewer: 3 chỗ | P0 |
| Vị thế | KEEP | P0 | HOLD/EXIT | P0 |
| Khi nào / tiếp theo | KEEP; mượn câu A khi đóng cửa | P0 | Không phải canh màn | P0 |
| Dải MTF H4…M1 | KEEP; **sửa mâu thuẫn** "M15 PULLBACK ↑" vs "chưa có setup" | Giả thuyết – chưa xác minh trên LIVE đóng cửa; `engine.py:364` vs `action.ts:66-72` là hai nguồn | P0 |
| Tab Hệ thống mặc định + 12 thẻ | **MOVE** sang `/system` (menu đã có "Hệ thống" = `/control` — cần đổi nhãn) | Không giúp quyết định trong 5 giây | P1 |
| Cảnh báo Telegram chưa bật (cam, to) | **COLLAPSE** thành 1 dòng trên thẻ; tăng tương phản | Nhiễu màu | P1 |
| Đoạn văn lặp thẻ | REMOVE | Nhiễu | P1 |
| Máy tính lệnh | KEEP collapsed | What-if, không phải tín hiệu | P2 |
| Chart + vẽ | KEEP | Ngữ cảnh | P1 |
| `/market` | KEEP | Chart đầy đủ /md | — |
| `/research` | KEEP | Bằng chứng (banner NO EDGE đúng) | — |
| `/journal` | KEEP | Kết quả PAPER | — |
| `/legacy` | DEPRECATE với route | Ẩn menu | P2 |
| `/control` | KEEP khoá | Poll 503 đã dừng (`ControlPanel.tsx:186-208`, CONSIST-01); còn tối đa 3 lần 503 lúc vào trang. Không phải P1 | P2 |

**Quyết định (d):** mock B (thẻ+). Reviewer 1: B 4,75 PASS, C 3,50 FAIL (D2=3), A 2,55 FAIL. Reviewer 2: B 4,50 PASS, C 3,85 PASS, A 2,70 FAIL. Nhãn xáo: A=current, B=card+, C=strip — map đã check-in `docs/reports/img/consolidation-2026-10-11/ui_label_map.json` (seed 20261011). Rubric: `docs/reports/img/consolidation-2026-10-11/rubrics.md` (gốc `%TEMP%\xau_cons\rubrics.md`, 09:35 GMT+7, trước khi chấm). Ảnh mock: `mock-A.png` / `mock-B.png` / `mock-C.png`.

Defect B đưa vào AC triển khai: coverage tương phản + tiếng Việt + hệ quả; `DỮ LIỆU LIVE`; tách Entry/SL/TP + R:R; pill `⏸ CHỜ · CHƯA KIỂM CHỨNG` trên header; không hiện `/system` cho user; giải thích M1 CŨ.

## 6. Chẩn đoán Dev & họ giả thuyết

Nguồn số R: `%TEMP%\xau_diag` (tái lập `uv run python $env:TEMP\xau_diag\dev_diag.py`). Dev = 2025-05-01 .. &lt; 2026-01-01 (`evaluation/periods.py:12`). Luật Strategy A = Baseline A `strategies/baselines.py:36-45` (tham số, không phải bảng R). n=135 khớp `data/backtests/trades_baseline_a_development.parquet`.

| | Mean R | 95% CI (percentile bootstrap 5000, seed 7 — **không** phải day-block theo `edge-criteria.md`) |
|---|---|---|
| Gross trước chi phí | −0,054 | [−0,279; +0,175] |
| Spread / slip / swap / comm | 0,059 / 0,012 / 0,009 / 0 (unverified) | |
| Net | −0,135 | [−0,359; +0,093] |
| Frictionless re-sim | −0,078 | [−0,301; +0,151] |

Kết luận mô tả: **không phát hiện mean hướng ở n=135**. "EDGE TOO THIN AFTER COSTS" sai. Win rate 31,1%; PF 0,91→0,80. Các số 23 nến M5 / 1,94R / 97,8% là **mô tả hình học luật**, không phải ngưỡng đề xuất và không phải "next edge". Exit: SL 68,1% / TP 27,4% / TIME 4,4%; give-back khớp random walk (−1R/+2R). BE/trailing **có trong Trading Core, tắt mặc định** (`position_manager.py:56-62`); `paper_desk.py:140-142` là invalidation / `NO_TIME_EXIT`, không phải BE. **Thiếu** trong backtester A (`backtest/engine.py:243-274`). Partial TP **missing**. Script: `%TEMP%\xau_diag\dev_diag.py`.

Hạn chế thống kê (`mle-reviewer`): bootstrap không phải day-block; nhóm phiên post-hoc ≥9 so sánh, n=9–42; "CI chồng" không phải test; MDE ~0,3R &gt; bound 0,20R → đọc là **"không phát hiện được edge ở cỡ mẫu này"**; Dev 2025 đã burned (E1/E2). Kết luận giữ họ: không đổi.

**Quyết định (e):** không giữ họ nào (L: reviewer 4,20 / 3,85). A/B/C FAIL E1. Test-H không có M5 (M15 từ 2022-07) — ý tưởng M5 không kiểm được trên Test-H. ADR-0030.

## 7. Roadmap

| Pha | Việc | DoD | Gate ECC |
|---|---|---|---|
| **P0 Operations** | Chủ giữ stack sống bằng Task Scheduler đã có (không NSSM). Agent không sửa module LIVE, không đặt ngưỡng gap mới. Freeze-LIVE = dev trên sandbox. | Uptime hết là nguyên nhân của coverage 48,64% (232/477, `WORKSTATION_COMPLETION_FINAL.md`); 95% là cổng evidence **đã có** (`coverage.py:25`), không phải DoD sprint 14 ngày | Không mở supervisor từ console; agent không viết coverage-phiên khi downtime còn là gốc |
| **P1 Edge Research** | Chủ ký trần K; không chạy A/B/C; template V3 **chỉ khi** có giả thuyết thật | Dòng ledger có chữ ký | `eval-harness` + `mle-reviewer` + ADR-0030 |
| **P2 Canonical Brain** | Contract v2 (sau Gate A riêng) → ADR guard UNKNOWN → intent + harness → dry-run | AC-A* / AC-C*; 0 lệch OrderIntent | `tdd-workflow` + `santa-method` + ADR-0026/0028 |
| **P3 Demo Preparation** | 7 điều kiện mục 11; FTMO `must_verify` | Checklist `go-live-checklist.md` đủ bằng chứng | `/checkpoint` + `production-audit` |
| **P4 Funded** | ADR-0020 riêng; không suy từ Demo | Quyết định chủ + cờ | ADR mới |

UI chỉ **maintenance** (thẻ B + honesty). Không redesign, không chỉ báo mới.

## 8. TOP 10 và TOP 5 ngay

Score = (North Star + Edge + Risk Reduction + Maintenance) / Cost, mỗi mục 1–5.

| # | Task | Why | Files | Risk | DoD | Dep | Score | Cỡ | Chuỗi ECC |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Freeze-LIVE (chính sách, không code): dev trên sandbox; không sửa module mà stack LIVE đang import | Coverage 48,64% = uptime, không phải thiếu telemetry (`WORKSTATION_COMPLETION_FINAL.md`) | Không đụng `coverage.py` / `data_health.py` / engine trên process LIVE | Thấp | 0 merge vào process LIVE tuần này | Q4 chủ | 12/1=12 | S | docs only |
| 2 | Một nguồn `k_cap` + test lệch FAIL | Console 48 vs ledger 24 vs `registration.py:91` = 24 | `_v2_k_cap` `research/service.py:175-192` (gọi ở `:325`); `STATE.json`; `integrity/registration.py` | Trung (governance) | AC-E1; không chạy giả thuyết | Chủ ký ADR-0030 | 15/2=7.5 | S | 7, 9–12 |
| 3 | Thẻ quyết định B (honesty + 12 P0 trên fold) | Bài 5 giây FAIL | `HeroCard.tsx`, `action.ts`, `TerminalView.tsx`, e2e goldens | Thấp UI | 12/12 trên fold 1440; UNVALIDATED cạnh action; 0 mâu thuẫn M15 vs setup (hoặc chú thích) | — | 14/3=4.7 | M | 7–14, 1 reviewer mù |
| 4 | `TradingSignal` v2 additive (`schema_version`, `source_mode` bắt buộc, sizing basis) | Não C/B không đọc đủ | `trading/schema.py`, engine, journal reader, fixtures | Trung (journal `extra=forbid`) | AC-C1–C5 | ADR-0028 duyệt | 14/3=4.7 | L | đủ 14 |
| 5 | UNKNOWN = đóng + nối `flatten_required` / gán `daily_loss_guard` | Fail-open trước Demo | `live_source.py:90-92`; `position_manager.py:106,142`; `paper_desk.py:394` (governor lúc mở); `governor.py:78` (flatten chết) | **Cần ADR** | Không làm tuần này | ADR guard | 15/3=5 | M | ngoài sprint |
| 6 | Manifest đóng băng raw + research_history | 3 kho; writer vẫn ghi raw | scripts writer, loader | Thấp | AC-B1, B2, B4 | ADR-0027 | 12/3=4 | M | 7–12 |
| 7 | `intent_from_signal` + `scripts/decision_parity.py` (dry-run) | Hai/ba não | `trading/adapter.py`, `execution/bridge.py`, tests | Cao | AC-A1–A6; 0 lệnh | #4, ADR-0026 | 16/5=3.2 | L | đủ 14 |
| 8 | Task Scheduler (đã chọn, đã đăng ký `XAU-EDGE Market Stack`) | Khoảng thiếu 215′ = 17:14–20:48 UTC (`WORKSTATION_COMPLETION_FINAL.md` §3). `api.log` ghi `SUPERVISOR child exited` 0x40010004 — **Giả thuyết – chưa xác minh lại** trong sprint này. Script `install_market_autostart.ps1` không chứa số 215. | `install_market_autostart.ps1` (NSSM/`install_services.ps1` = bot sau này) | Thấp | Chỉ start bằng script/task; diễn tập reboot khi rảnh | Chủ đã chọn 2026-10-11 | 15/1=15 | S | không cài thêm |
| 9 | Template preregistration V3 + luật Test-H/Holdout | Không đốt Test-H | `docs/research/edge-program-v2/` | Governance | AC-E2–E4 | #2 | 13/2=6.5 | S | docs + `mle-reviewer` |
| 10 | Retire `/legacy` + `/paper/*` + PaperTrader | Não C | `api/app.py`, `serve_api.py`, dashboard | Trung | Điều kiện xoá §3 | #7 parity | 10/4=2.5 | L | sau Demo dry-run |

**TOP tuần này (sau Gate A) — chỉ hai việc, không theo cột Score:** **#3 thẻ B** (sandbox đã ship, `d732602`) và **#2 `k_cap`** (`a004958`). `#4` contract v2 và `#5` UNKNOWN=đóng **không** thuộc TOP tuần này dù điểm số bảng trên ≥ #3 — đó là backlog, không phải việc Gate A. Q3 Task Scheduler đã có. Còn của chủ: ký dòng K trên ledger nếu muốn đổi 24; không mở stack từ console; restart LIVE khi đóng cửa nếu muốn fold honesty lên `:3000`.

## 8b. Loop log

### (a) Hai engine
1 Ý tưởng: BUY trên `/trade` có thể khác lệnh DEMO. 2 P adapter / Q không / R intent. 3 Rubric `docs/reports/img/consolidation-2026-10-11/rubrics.md` (09:35, trước chấm). 4 Bảng phương án. 5 [kiến trúc](a2183b1e-2e90-402d-a322-92f771c3e7f3) P 3,75 PASS, R-sửa ước ~4,40 nếu A2=5; [rủi ro](a14182a0-59d5-4257-8cce-f2c246b0da30) R-sửa 3,55 PASS. R-sửa chấm **sau** khi unblind defect — ghi rõ, không phải vòng mù thứ hai. 6 **Chọn R-sửa**. ADR-0026.

### (b) Store
1 Ba kho; V1/V2 trên `research_history` (`run_edge_program.py:56`). 2 P migrate / Q freeze / R không. 3 Cùng `rubrics.md` mục (b), trước chấm. 4 Không prototype UI. 5 [kiến trúc](a2183b1e-2e90-402d-a322-92f771c3e7f3) Q 4,35 PASS; [rủi ro](a14182a0-59d5-4257-8cce-f2c246b0da30) Q 3,85 PASS. 6 **Chọn Q**. ADR-0027.

### (c) Contract
1 Executor không tính lại; journal `extra=forbid`. 2 P additive / Q breaking / R giữ. 3 `rubrics.md` mục (c), trước chấm. 4 Bảng trường. 5 [kiến trúc](a2183b1e-2e90-402d-a322-92f771c3e7f3) P 4,35 PASS; [rủi ro](a14182a0-59d5-4257-8cce-f2c246b0da30) P 4,15 PASS. 6 **Chọn P**, **không** vào sprint này. ADR-0028.

### (d) UI
1 5 giây, 12 P0, honesty. 2 A current / B card+ / C strip; mock `%TEMP%\xau_cons\mock`. 3 Rubric (d) trước. 4 Ảnh `mock-*.png`. 5 [R1](cfb8d6f9-67f6-4720-adb0-e616cc6cb6b9) B 4,75; [R2](cfe97757-e3e2-4da1-9bec-5ad761b21e06) B 4,50. 6 **Chọn B** + defect list §5.

### (e) Edge families
1 Dev mô tả, không tune. 2 K exit / L không họ / M geometry / N session. 3 Rubric (e) trong `rubrics.md` (cùng file, trước chấm — bước 3 đã có trên đĩa; log vòng (e) trước đây sót số 3). 4 `%TEMP%\xau_diag`. 5 [mle](01f58647-2305-4802-a2ec-f9cef9bdd9c3) L 3,85; [trader](955dc897-9040-40ef-840b-50c3766b24c5) L 4,20. 6 **Chọn L**. ADR-0030.

### (f) Gate A hẹp (thẻ B + `k_cap` + NSSM portable)
1 Prompt `26-10-11-10-00` (chủ OK). 2 Không có phương án mới (B đã thắng). 3 Rubric (d) + santa S1–S5 giữ nguyên. 4 Sandbox e2e + WhatIf NSSM. 5 [Santa 2 vòng 2](a5d4281e-61dd-4107-9e50-a17a611c9c92) 4,34 PASS; [Santa 1 vòng 2](802978d5-60bc-4598-ba00-5c23f07525c1) 4,20 PASS; [Santa 3b](9e885ba8-733a-4293-8870-7c63fe3df3c5) 3,60 PASS. 6 Ship sandbox only. LIVE `:3000` không rebuild.

## 9. STOP BUILDING / DEFER / KEEP FROZEN

**STOP:** chỉ báo mới, BOS/CHoCH, 2 chart, thêm tool vẽ, redesign `/trade`, A/B 4 reviewer cho việc nhỏ, giả thuyết trend-pullback/session/exit từ Dev này, back-fill quyết định, xoá `data/raw` hay `research_history`, bật DEMO/FUNDED, gửi lệnh, nới evidence gate.

**DEFER:** lazy-load chart + D1; nguồn tin SLA (Q1); quản lý vị thế tự động (Q2 — alpha, không UX); Telegram (Q5); retire legacy engine; Funded.

**KEEP FROZEN:** `xau_mtf_baseline` v1.1.0 ngưỡng; Test-H; Holdout; v1.2/v1.3 không chạy; control plane off; funded flags off; V2 Batch B chưa được D-1.

## 10. Final product shape

- **Core (hiện tại):** `data/market` → TradeEngine → `TradingSignal` (schema hiện có) → PaperDesk. `TradingSignal` v2 / `OrderIntent` = ADR-0026/0028, **chưa ship**. `/trade` = quyết định 5 giây. `/research` = bằng chứng. `/system` = runtime. `/journal` = kết quả.
- **Legacy:** `signals.engine`, `/legacy`, `/paper/*`, `data/raw`, `data/research_history` — đóng băng, đọc khi cần tái lập, xoá sau điều kiện §3.
- **UI:** thẻ B + chart + MTF; hệ thống xuống `/system`; không che UNVALIDATED.

## 11. Mười câu hỏi

1. **Code bỏ?** Tests-only listed §2; 38 script không trong corpus — ARCHIVE, không xoá tuần này. Não B + đường paper legacy: DEPRECATE sau parity.
2. **Code giữ?** `trading/*` (trừ arming), `market_data`, `ops`, `news`, `research` console, `evaluation` thư viện, executor khoá.
3. **Code hợp nhất?** Sizing → `trading.sizing`; một bộ não (ADR-0026); một kho live (ADR-0027).
4. **UI bỏ?** Đoạn văn lặp; tab Hệ thống mặc định trên `/trade`; badge "LIVE" dễ hiểu nhầm; `/legacy` sau parity.
5. **UI giữ?** Hero CHỜ + không vào lệnh; chart; research banner NO EDGE; journal.
6. **UI thiếu thật?** UNVALIDATED + coverage trên fold; Entry/SL/TP/R:R trên thẻ; `DỮ LIỆU LIVE`; giải thích M1 CŨ / M15 vs setup.
7. **Không nên làm?** Retune v1.1; chạy Test-H/Holdout; giả thuyết A/B/C; redesign; chỉ báo; bật Demo; cài NSSM cho market stack (đã loại).
8. **Tới Edge nhanh nhất không tự lừa?** L: chốt K → cơ chế **mới** (sự kiện/vĩ mô, DXY/lợi suất thực, lịch) diễn đạt được trên H1/M15 Test-H → preregister → power check. Không đào Dev 2025.
9. **Khi nào xoá legacy signal engine?** Khi AC-A6 đạt + không còn importer runtime + `/legacy` gỡ + test chuyển — **không** hẹn ngày.
10. **Khi nào mở Demo?** Cả 7 (`canonical-brain.md` §6): (1) dry-run TradingSignal ≥1 tuần, parity 0 lệch; (2) coverage ≥95% cùng kỳ; (3) bar parity 0 + đĩa không CRITICAL + heartbeat tươi; (4) news không STALE/ERROR suốt kỳ; (5) forward F2+ trên PAPER; (6) chủ xác nhận văn bản, cờ cấu hình, kill switch diễn tập; (7) FUNDED vẫn khoá.

## 12. Verdict

- **CURRENT PRODUCT:** Bàn PAPER, hai engine + đường paper legacy, không edge. **Sandbox** (`:3210` / ảnh `trade-1440-card-b.png`) có UNVALIDATED + độ phủ + Entry/SL/TP trên fold. **LIVE `:3000` vẫn fold cũ** (`trade-1440-current.png`: badge `LIVE · ĐÓNG CỬA`, không honesty trên thẻ) — chưa rebuild.
- **TARGET PRODUCT:** Một não, một kho live, thẻ 5 giây có evidence trên **cả** LIVE, research đóng băng đúng luật K, Demo chỉ sau 7 cổng.
- **NEXT PHASE:** Chủ giữ stack sống + ký K nếu đổi 24. Đưa thẻ B lên LIVE chỉ khi thị trường đóng, bằng restart/build **được phép** (không đụng giờ mở). Không schema v2, không alert gap, không UNKNOWN=đóng.
- **DO NOT BUILD:** (1) họ A/B/C; (2) đường adapter như đang viết; (3) gộp/xoá `data/raw`; (4) telemetry downtime mới (coverage-phiên / alert 2 phút) khi gốc vẫn là console chết.
- **BUILD NEXT:** (1) restart LIVE khi đóng cửa nếu chủ muốn fold honesty trên `:3000`; (2) chủ ký trần K trên `ledger.md` nếu đổi số; (3) chỉ start stack qua Task Scheduler / `start_market_stack.ps1`.

## 13. Santa-method trên báo cáo này

Rubric báo cáo (cố định trước khi sửa bản cuối): (S1) mọi số có cite; (S2) không đề xuất threshold; (S3) 5 quyết định có loop log + reviewer ≠ tác giả; (S4) TOP 5 khớp North Star; (S5) không chỉ thị triển khai trước Gate A.

Điểm đã sửa theo review **trước** khi đóng bản này (không tự duyệt):
- Brief sai "V1/V2 trên data/raw" → `research_history` (F1).
- Brief sai "entry = zone_mid ± spread" → BUY +spread, SELL +0 (F4).
- Đường paper legacy = consumer của não B + broker $100k, không phải engine thứ ba.
- Lot 0,5% chỉ trên đường legacy/demo, không trên PAPER live.
- Chẩn đoán: đổi wording "NO EDGE" → "không phát hiện được ở n=135"; ghi bootstrap không phải day-block.
- (a) thắng = R-sửa, không phải P.
- (e) 0 họ; K-cap phải khoá trước khi soạn giả thuyết.

### 13b. Santa trên văn bản (vòng 1)

| Reviewer | Weighted | S2 | S4 | Verdict |
|---|---|---|---|---|
| [Santa 2 — product/risk](e2e70f70-59fb-48ba-a380-aa68db3ca23e) | 3,88 | 3,5 | 3,2 | **FAIL** (S2) |
| [Santa 1 — factual](c107b04c-c9db-49ad-9fd0-b5db50c7ba07) | 3,40 | 4 | 3 | **FAIL** (trung bình &lt; 3,5; S3=2) |

Sửa vòng 2 (Santa 1): cite `daily_loss_guard` / UNKNOWN / `FundedRule` / `news_status:95` / `EngineRunner` 120-141; hai engine không phải ba; lot 0,5% chỉ legacy; Strategy A ≠ desk live; check-in rubric + label map; TOP = một việc (#3); ID reviewer cho (b)/(c); bỏ 3×503 P1; bỏ SLA 60 s.

### 13b (tiếp). Santa vòng 2 (sau sửa, trước/khi Gate A) — cả hai PASS

| Reviewer | Weighted | S2 | S4 | Verdict |
|---|---|---|---|---|
| [Santa 1 — factual](802978d5-60bc-4598-ba00-5c23f07525c1) | 4,20 | 5 | 3 | **PASS** |
| [Santa 2 — product/risk](a5d4281e-61dd-4107-9e50-a17a611c9c92) | 4,34 | 4,5 | 4,2 | **PASS** |

S4=3 (Santa 1): bảng TOP 5 vẫn xếp việc chủ / contract trên #3 — đã tách “TOP tuần này” khỏi cột Score.

### 13b (tiếp). Gate A hẹp — việc đã làm (2026-10-11)

Prompt `26-10-11-10-00` (chủ OK): Gate A = **thẻ B + một nguồn `k_cap`**. Không contract v2, không UNKNOWN=đóng, không alert 2 phút, không họ giả thuyết mới.

| Việc | Kết quả (đo) |
|---|---|
| NSSM | Portable `%LOCALAPPDATA%\xau-edge\nssm\nssm-2.24\win64\nssm.exe`. Lệnh: `install_services.ps1 -WhatIf -SkipApi -SkipBot`. Artifact `%TEMP%\xau_nssm\whatif.txt` **không** in lại tên cờ; chỉ ghi “Services were NOT started”. 0 dịch vụ `xau-edge-*`. Không bind. |
| Task Scheduler | `XAU-EDGE Market Stack` Ready, Last Run 2026-10-11 08:45:40, Last Result 0. Không NSSM-ôm `run_market_stack.py`. |
| `k_cap` | Console đọc ledger. Test `test_v2_k_cap_follows_ledger_when_state_disagrees`: STATE 48 + ledger 24 → 24, `k_cap_mismatch`. Không sửa `ledger.md`. Commit `a004958`. |
| Thẻ B | Sandbox Playwright (`.next-sandbox`, không rebuild LIVE `.next`): 5/5 `honesty.spec.ts`. Ảnh `trade-1440-card-b.png`, `trade-1920-card-b.png` — **70,4% là mock** `coverage_incomplete.json`, không phải 48,6% live. Commit `d732602`. |
| LIVE `:3000` | Không rebuild, không restart. 0 lệnh. Fold cũ vẫn đúng với `trade-1440-current.png`. |

### 13b (tiếp). Santa vòng 3 (sau Gate A)

| Reviewer | Weighted | S2 | S4 | Verdict |
|---|---|---|---|---|
| [Santa 3a — factual](a82711f9-801d-4812-9359-d0361d79511e) | 3,40 | 4 | 3 | **FAIL** (weighted &lt; 3,5) |
| [Santa 3b — product/risk](9e885ba8-733a-4293-8870-7c63fe3df3c5) | 3,60 | 4,5 | 3,0 | **PASS** |

Sửa theo 3a (không tự tuyên PASS, không mở vòng 4): số R ← `%TEMP%\xau_diag` không phải `baselines.py:36-45`; lot ← `baseline.py:72`+`:363` + `paper_desk.py:495-497`; `k_cap` ← `service.py:175-192`; 48,64% / 215′ ← `WORKSTATION_COMPLETION_FINAL.md`; WhatIf artifact không echo cờ; v2 = backlog #4 không phải TOP tuần này.

**Santa đóng (3 vòng):** vòng 1 FAIL/FAIL; vòng 2 PASS/PASS; vòng 3 FAIL/PASS. Còn BLOCKED: S3 (reviewer (a)–(e) cùng phiên / R-sửa unblind) không chữa được bằng cite. Không chạy vòng 4.

## 14. Gate A — đã duyệt hẹp

1. **Sandbox:** thẻ B honesty (`next dev` `:3210`, `NEXT_DIST_DIR=.next-sandbox`). Không merge/restart process LIVE. Thị trường mở lại **2026-10-12 05:05 GMT+7**.
2. **Q3:** Task Scheduler giữ market stack (Ready, last result 0). NSSM portable sẵn, **chưa bind** API/bot (`-SkipApi -SkipBot`).
3. **`k_cap`:** reader theo ledger (24). Chủ vẫn phải ký dòng append trên `ledger.md` nếu muốn đổi số; agent không sửa sổ.
4. Nháp ADR 0026–0030 giữ draft. **#4 / #9 / contract v2 / UNKNOWN=đóng / alert 2 phút / họ giả thuyết mới không làm.**
5. Q1 (news SLA), Q2 (auto position), Q4 (thói quen freeze-LIVE), Q5 (Telegram) vẫn mở của chủ.

**Tuyên đúng:** sandbox `/trade` trung thực hơn (UNVALIDATED + độ phủ trên fold). **Bàn LIVE `:3000` chưa đổi.** Edge vẫn UNVALIDATED. Không sẵn sàng tiền thật.
