# Prompt — Consolidation Audit: GIỮ / HỢP NHẤT / DEPRECATE / XOÁ SAU PARITY + UI tối giản + Lộ trình tới Edge (chạy theo vòng ECC)

## ROLE
Bạn là **Principal Architect + Quant Research Lead + Trading Product Lead + Technical Debt Auditor**, làm việc theo **vòng giao hàng ECC** của dự án. Bạn đánh giá mọi thứ bằng một câu hỏi: *nó có giúp human ra quyết định MUA / BÁN / ĐỨNG NGOÀI / GIỮ / CHỐT LỜI / CẮT LỖ đúng hơn, với mức bằng chứng trung thực, hay không?*

## NORTH STAR
XAU EDGE là Desktop XAUUSD Decision Terminal giúp human biết: nên làm gì bây giờ, vì sao, Entry/SL/TP, khi nào HOLD/EXIT, điều gì xảy ra tiếp — **và quyết định đó có evidence level nào**. Khi chiến lược chưa có edge được kiểm định, sản phẩm trung thực phải nói rõ điều đó (UNVALIDATED), không che bằng UI đẹp.

## SỰ THẬT ĐÃ XÁC MINH (2026-10-11 — kiểm lại, không tin mù)
- HEAD `3ee3990` (CI xanh). Báo cáo: `docs/reports/WORKSTATION_COMPLETION_FINAL.md` (FUNCTIONALLY COMPLETE — FORWARD LIVE SIGNAL OBSERVATION PENDING), `docs/reports/PROJECT_COMPLETION_AND_ROADMAP.md` (workstation ~90%, sẵn sàng tiền thật ~25%).
- Hai bộ não: `data/market → TradeEngine → TradingSignal → PaperDesk` và `data/raw → signals.engine → SignalBridge → executor` (`docs/architecture/canonical-brain.md`; `trading/adapter.py` chỉ có test).
- Coverage 48,64% = vận hành (stack dừng tay 30′ + supervisor chết theo console 215′), không phải lỗi telemetry.
- Guard: `governor.flatten_required` (`trading/governor.py:78`) không có caller; `daily_loss_guard` không được gán.
- Edge: `xau_mtf_baseline v1.1.0` UNVALIDATED; Edge V1 NO EDGE, V2 Batch A 0/20; strategy A −0.135R Dev / −0.099R Val.
- Quyết định chủ dự án còn mở: Q1 nguồn tin SLA, Q2 quản lý vị thế tự động (alpha), Q3 supervisor thành dịch vụ, Q4 freeze-LIVE, Q5 Telegram.
- ECC `affaan-m/ECC` @ `4eb71d92` (2.2.3); danh mục `docs/reports/ECC_CATALOG.md`; dự án dùng profile minimal, **no hooks**; vòng bắt buộc `AGENTS.md:93-114`, `docs/PROJECT_PLAN.md:93-115`.

## CHẾ ĐỘ CỦA SPRINT NÀY
**Giai đoạn 1 — AUDIT + THIẾT KẾ (mặc định).** Kết quả là quyết định có bằng chứng và kế hoạch được duyệt ở Gate A. Trong giai đoạn này, vòng closed-loop (mục dưới) chạy đến bước **chọn phương án**; "prototype" chỉ là mockup/spike **ngoài repo** (`%TEMP%`, sandbox `serve_acceptance.py` :8100/:3200, git worktree tạm) — không sửa code trong repo. Ngoại lệ: chẩn đoán số học trên **Dev** khi `RUN_DEV_DIAGNOSTICS=yes`.
**Giai đoạn 2 — TRIỂN KHAI TOP 5 (chỉ khi `IMPLEMENT_AFTER_GATE_A=yes` VÀ chủ dự án đã duyệt Gate A).** Mỗi task chạy trọn vòng closed-loop tới **PASS**, mỗi task một commit riêng, chỉ trên sandbox cho tới bước restart cuối.

## CLOSED-LOOP AUTONOMOUS WORKFLOW (gắn ECC — bắt buộc cho mọi quyết định/task)
| # | Bước | ECC dùng | Đầu ra / bằng chứng bắt buộc |
|---|---|---|---|
| 1 | **Ý tưởng** (vấn đề, người dùng, quyết định nào được cải thiện) | `search-first` (đã có sẵn chưa?), `product-lens` (vì sao làm) | 1 đoạn problem statement + quyết định MUA/BÁN/CHỜ/GIỮ/CHỐT/CẮT nào được hưởng lợi |
| 2 | **Tạo 2–3 phương án** thật sự khác nhau (gồm "không làm") | agent `architect` / `code-architect`; `council` khi có đánh đổi lớn | bảng phương án: cách làm, chi phí, rủi ro, file chạm tới |
| 3 | **Đặt tiêu chí TRƯỚC** khi xem kết quả | `eval-harness` (capability + regression eval, pass^3), `intent-driven-development` (AC-NNN có "Must not") | rubric có trọng số + ngưỡng PASS, commit/ghi lại trước bước 4 |
| 4 | **Prototype nhẹ** cho từng phương án | UI: `/gan-design` (generator–evaluator, giới hạn vòng) hoặc mockup tĩnh; backend: spike trong worktree/sandbox | ảnh/mockup/spike cho mỗi phương án, cùng điều kiện so sánh |
| 5 | **Reviewer độc lập, mù nhãn** | `santa-method` (2 reviewer cùng rubric), agent `agent-evaluator`; nhãn ngẫu nhiên A/B/C, reviewer không biết bản nào mới/được ưa/tốn công | điểm theo rubric của từng reviewer; reviewer ≠ người tạo |
| 6 | **Chọn phương án mạnh nhất** | `council` nếu điểm sát nhau; `architecture-decision-records` | quyết định + lý do loại phương án còn lại (ADR nháp cho việc lớn) |
| 7 | **Code** (chỉ giai đoạn 2) | `/orch-add-feature` · `/orch-change-feature` · `/orch-fix-defect` · `/orch-refine-code` (bên trong: `tdd-workflow`, agent `tdd-guide`) | test FAIL trước → GREEN; diff nhỏ, một mục đích |
| 8 | **Browser test thật** | `browser-qa`, agent `e2e-runner`, Playwright MCP: sandbox trước, LIVE chỉ xem sau restart có phép | ảnh 1440×900 + 1920×1080, console/network sạch, bài 5 giây |
| 9 | **Automated test** | `e2e-testing`, `python-testing`, `verification-loop` (= `scripts/dev.ps1 check` + eslint/tsc/next build/Playwright), `/test-coverage` | số test chính xác, 0 fail |
| 10 | **Phát hiện bug** | agent `silent-failure-hunter`, `/review-pr` (6 reviewer), `click-path-audit`, `/python-review`, `/react-review` | danh sách bug phân loại CRITICAL/HIGH/MEDIUM/LOW |
| 11 | **Fix** | `/orch-fix-defect` (regression test trước), `ai-regression-testing` | mỗi bug có test hồi quy vĩnh viễn |
| 12 | **Chạy lại** bước 8–9 | `verification-loop`, `/checkpoint` | cùng bộ bằng chứng như lần đầu, 0 hồi quy |
| 13 | **Red team** | agent `security-reviewer`, `prediction-market-risk-review` (khi chạm execution/guard), `loop-design-check` (verifier có bị "lách"?), agent `pr-test-analyzer` | 0 CRITICAL/HIGH; MEDIUM ảnh hưởng dùng hằng ngày đã sửa |
| 14 | **PASS chỉ khi thật sự đạt** | `production-audit` (ship/block), `santa-method` lần cuối | tất cả: eval pass^3 · browser thật trên build mới nhất · automated xanh · 2 reviewer PASS · red team sạch · tài liệu khớp code |

**Quy tắc vòng lặp**
- **Tương xứng theo cỡ việc:** **L** (brain, data store, guard, contract, research/edge) = đủ 14 bước. **M** (thay đổi UI/API có hành vi mới) = 2 phương án, 1 reviewer mù, bước 7–14 (red team gọn). **S** (bug, wording, refactor nhỏ) = bước 7, 9–12 với 1 reviewer. Ghi cỡ việc trước khi bắt đầu.
- **Chống vòng lặp vô tận:** tối đa 3 lần fix cho cùng một bug, 2 vòng `/gan-design` mỗi phương án; quá giới hạn → dừng, ghi BLOCKED + nguyên nhân + đề xuất, chuyển việc tiếp.
- **Không tự duyệt:** người/agent tạo phương án hoặc code không được là reviewer của chính nó (bước 5, 10, 13, 14).
- **Không được kết luận PASS vì:** test xanh, CI xanh, tính năng có trong code, báo cáo dài, reviewer "gần như thích".
- **Biến thể cho nghiên cứu edge** (không có browser): bước 4 = chẩn đoán trên Dev; bước 3 = preregistration (giả thuyết, metric, ngưỡng, phân vùng) commit trước; bước 5 = `mle-reviewer` + `santa-method`; bước 8–9 = replay/Val theo đúng thứ tự pha; bước 13 = soát leakage, multiple-testing, hindsight; PASS chỉ khi qua đúng pha, không nhảy pha.
- **Ghi vết:** mỗi quyết định/task có một "loop log" (bước → ECC dùng → bằng chứng → kết quả) trong báo cáo.

## RESEARCH GOVERNANCE (bắt buộc)
- Chỉ dùng phân vùng **Dev** (đã "burned") cho chẩn đoán mô tả: cost decomposition, entry geometry, exit efficiency. **Không chạm Val mới, Test-H, holdout.** Không retune, không đề xuất ngưỡng.
- Kết quả chẩn đoán chỉ được dùng để **viết giả thuyết preregister**; kiểm định phải chạy trên dữ liệu chưa dùng, theo thứ tự Dev → Val → Test-H → Holdout → Forward PAPER → Demo. Không nhảy pha.
- Output chẩn đoán ghi ra `%TEMP%` và trích số vào báo cáo; không ghi vào `data/` hay `docs/research/` của dự án.

## VÒNG ECC ÁP DỤNG (mỗi giai đoạn phải ghi đã dùng thành phần nào và kết quả)
| Giai đoạn | ECC | Đầu ra bắt buộc |
|---|---|---|
| 0. Tìm cái đã có | `search-first`, `codebase-onboarding` / agent `code-explorer` | bản đồ module + import graph thật (không đoán) |
| 1. Kiểm kê code chết / trùng | agent `refactor-cleaner` (chỉ phân tích, không xoá), `silent-failure-hunter` | danh sách unused/duplicate kèm bằng chứng (rg import, caller, test) |
| 2. Hai bộ não + store | agent `architect`, skill `council` (khi KEEP/DELETE tranh cãi) | khuyến nghị + phương án loại trừ |
| 3. Contract TradingSignal | `intent-driven-development`, agent `type-design-analyzer` | contract v-next + acceptance criteria AC-NNN |
| 4. UI | `product-lens` (vì sao tồn tại), `click-path-audit`, `browser-qa` (Playwright MCP, chỉ xem) | bảng KEEP/MOVE/COLLAPSE/REMOVE/BUILD có ảnh chụp |
| 5. Lộ trình edge | `eval-harness` (định nghĩa eval trước), agent `mle-reviewer` (leakage, point-in-time) | khung preregistration TOP ≤3 họ giả thuyết |
| 6. Xác nhận kết luận | `santa-method` (2 reviewer độc lập, cùng rubric) | PASS/FAIL cho báo cáo; sửa đến khi cả hai PASS |
| 7. Ghi quyết định | `architecture-decision-records`, `living-docs-governance` / `docs-governance` | **bản nháp** ADR (chưa merge): canonical brain, data store, TradingSignal contract, freeze-LIVE |
| 8. Gate A | `/plan` + `verification-loop` (với tài liệu: link/đường dẫn/số liệu) | kế hoạch chờ chủ dự án duyệt |
Ghi rõ những gì ECC **không** làm được (tạo edge, hiểu MT5/FTMO, cài dịch vụ Windows).

## METHOD
1. **Inventory có bằng chứng**: mọi package trong `src/xau_edge/**`, `scripts/**`, `apps/dashboard/**` (đặc biệt market_data, trading, signals, strategies, features, structure, patterns, evaluation, experiments, risk, execution, funded, control, api, ops, brokers, dashboard). Mỗi module: purpose, ai import (đếm caller), có trên runtime path không (API/supervisor/collector/bot), research-only, legacy, duplicate, test phủ, giá trị tương lai.
2. **Xác minh two-brain** bằng trace import và entrypoint (`demo_trader.py`, bridge, executor, API routes legacy). Liệt kê điểm logic BUY/SELL bị tái tạo downstream.
3. **Data stores**: `data/market`, `data/raw`, tick ledger, research datasets — ai đọc/ghi, kích thước, quy tắc merge; phân loại KEEP / READ-ONLY LEGACY / DEPRECATE / DELETE LATER; không đề xuất store thứ ba.
4. **Signal/strategy layers**: source of truth hiện tại, legacy, research-only, cần cho Demo migration; số schema BUY/SELL đang tồn tại và lộ trình về **một**.
5. **Canonical TradingSignal contract**: symbol, timestamp, strategy_id, strategy_version, source_mode, decision, bias, setup_phase, setup_id, entry, sl, tp, rr, risk, expiry, invalidation, evidence_label, reasons, warnings, provenance (+ schema_version, code_version). So với `TradingSignal` hiện có — chỉ ra trường thiếu/thừa; adapters không được tái tạo logic.
6. **UI audit thật trên `localhost:3000`** (Playwright MCP, chỉ xem, 1440×900): bài 5 giây với 12 mục P0 (symbol, bid/ask, open/closed, bias, action, why, entry, SL, TP, risk, next condition, position). Mọi phần tử khác phải trả lời "giúp quyết định nào?". Tách rõ /trade (quyết định), /research (bằng chứng), /system (runtime), /journal (kết quả). Không đề xuất redesign toàn bộ.
7. **Research code**: giữ evaluation/preregistration/registry/backtest/walk-forward/statistics/holdout governance; tìm hypothesis bỏ dở, runner trùng, script không còn caller, báo cáo stale → ARCHIVE thay vì DELETE nếu còn giá trị audit.
8. **Chẩn đoán Dev** (nếu cờ yes): (a) cost decomposition: gross directional R vs spread vs slippage vs swap vs commission → kết luận NO DIRECTIONAL EDGE hay EDGE TOO THIN AFTER COSTS; (b) entry geometry: setup→trigger thời gian, price drift, stop distance, target room, RR suy giảm do xác nhận M5; (c) exit: TP/SL/TIME/invalidation phân bố, MFE/MAE; break-even/trailing/partial phân loại existing / disabled / missing / research candidate. Chỉ số, không tuning.
9. **Chấm ưu tiên** mỗi task: North Star Impact, Edge Impact, Risk Reduction, Maintenance Reduction (1–5) và Cost (1–5) → score = tổng lợi ích / cost.
10. **Áp closed-loop cho các quyết định của audit** (giai đoạn 1, bước 1–6): tối thiểu cho (a) chiến lược hợp nhất hai bộ não, (b) data store, (c) contract TradingSignal, (d) dọn UI /trade (2–3 mockup, review mù bằng bài 5 giây), (e) chọn TOP ≤3 họ giả thuyết edge. Mỗi cái có loop log.
11. **Gắn cỡ việc L/M/S và chuỗi ECC** cho từng task trong TOP 10 để sprint sau chạy được ngay.

## OUTPUT
Tạo **`docs/reports/CONSOLIDATION_AUDIT_AND_EDGE_PATH.md`** và các bản nháp ADR trong `docs/decisions/drafts/` (chỉ những file này; không sửa file khác). Trong chat: tóm tắt.
1. TL;DR (≤6 câu) + ECC đã dùng ở mỗi giai đoạn.
2. Bảng codebase: MODULE | CURRENT ROLE | KEEP / MERGE / DEPRECATE / ARCHIVE / DELETE LATER | WHY | DEPENDENCIES (số caller) | MIGRATION STEP | RISK.
3. Two-brain & data store: hiện trạng có bằng chứng + kế hoạch 3 bước (adapter + parity harness → dry-run Demo dùng TradingSignal → retire legacy) + điều kiện xoá (no runtime dep, no research dep, parity complete, migration documented, tests green).
4. Canonical TradingSignal contract + AC.
5. Bảng UI: ELEMENT | KEEP / MOVE / COLLAPSE / REMOVE / BUILD | WHY | USER VALUE | PRIORITY, kèm ảnh 5 giây trước/đề xuất.
6. Chẩn đoán Dev (hoặc "chưa chạy" + cách chạy) và TOP ≤3 họ giả thuyết được giữ (A entry geometry, B cost-aware session, C exit efficiency — chỉ giữ cái có bằng chứng).
7. Roadmap P0 Operations → P1 Edge Research → P2 Canonical Brain → P3 Demo Preparation → P4 Funded Readiness (UI chỉ maintenance), mỗi pha có DoD và gate ECC.
8. TOP 10 task (Why, files, risk, DoD, dependency, score, **cỡ L/M/S, chuỗi ECC closed-loop**) và TOP 5 ngay (≥2 Edge, ≥1 Ops, ≥1 Architecture).
8b. **Loop log** cho 5 quyết định của audit (a–e) và — nếu giai đoạn 2 chạy — cho từng task TOP 5 (kèm ảnh browser, số test, kết quả red team, PASS/BLOCKED).
9. STOP BUILDING / DEFER / KEEP FROZEN.
10. Final product shape (core / legacy / UI).
11. Trả lời 10 câu hỏi: code bỏ / giữ / hợp nhất; UI bỏ / giữ / thiếu thật; việc không nên làm; việc tới Edge nhanh nhất; khi nào xoá legacy signal engine (điều kiện, không phải ngày đoán); khi nào mở Demo (7 điều kiện).
12. Verdict: CURRENT PRODUCT / TARGET PRODUCT / NEXT PHASE (mỗi cái 1 câu) + DO NOT BUILD (top 3) + BUILD NEXT (top 3).
13. Kết quả `santa-method` (2 reviewer) và các điểm đã sửa theo review.

## CONSTRAINTS
- Giai đoạn 1: không sửa/xoá code trong repo, không commit/push. Giai đoạn 2 (khi được phép): commit theo quy ước author `howtodonext.com`, push main chỉ khi chủ dự án yêu cầu, không trailer Co-authored-by.
- Không stash, không đụng thay đổi chưa commit của người khác.
- Không restart stack LIVE khi thị trường mở; restart chỉ ở giai đoạn 2, khi thị trường đóng và có phép. Không build vào `apps/dashboard/.next` khi stack LIVE đang chạy; không chạy collector/supervisor/bot, không gửi lệnh, không kết nối MT5, không đọc/in `.env`; số tài khoản tối đa 3 số cuối.
- Không chạm Val mới/Test-H/holdout; không đề xuất threshold; thay đổi guard/scope ghi "cần ADR".
- Mỗi khẳng định có file:line, số đo hôm nay, hoặc trích báo cáo (ghi ngày); điều chưa xác minh ghi "Giả thuyết – chưa xác minh".

## FLAGS
- `RUN_DEV_DIAGNOSTICS=yes` (chỉ Dev, output ra `%TEMP%`; đặt `no` để chỉ lập kế hoạch đo)
- `IMPLEMENT_AFTER_GATE_A=yes` (đặt `yes` để sau khi chủ dự án duyệt Gate A, chạy trọn closed-loop cho TOP 5)
