# Roadmap traceability audit

Ngày: 2026-10-08 (cập nhật sau đợt xử lý nợ lộ trình, mục 11). Phạm vi: đối chiếu **brief 56 mục** của chủ dự án với `PROJECT_PLAN.md`, mã nguồn
hiện có (HEAD `73f2585`, 298 test pass, coverage 98%, CI main = passing) và quy trình ECC
(E0-E7, Gate A/B). Brief gốc chỉ tồn tại trong hội thoại, không nằm trong repo (xem mục 7, quyết định D-1).

Trạng thái: `DONE` (có bằng chứng) · `PARTIAL` · `NOT DUE` (có trong kế hoạch, chưa tới sprint) ·
`GAP` (brief yêu cầu nhưng **kế hoạch chưa có**) · `DEVIATION` (cố ý khác brief, có ADR) ·
`SKIPPED` (đáng lẽ đã làm nhưng bỏ qua).

## 1. Kết luận ngắn

* Không bỏ phase nào của brief: phase 0-1 đã xong, phase 2+ đúng thứ tự theo `PROJECT_PLAN.md`.
* **Có bỏ qua quy trình ECC ở Sprint 1-2** (đã sửa từ Sprint 3, xem mục 4).
* **Có các yêu cầu của brief chưa nằm trong kế hoạch nào** (mục 3, trạng thái `GAP`): logging có cấu trúc,
  news layer, model versioning/experiment registry, tài liệu data-flow / pattern-similarity / model-evaluation /
  risk-engine / testing-strategy / paper-trading, tests/regression + tests/statistical, configs/prop, pre-commit, Docker, red-team cuối mỗi phase.
  Đề xuất gán vào sprint ở mục 3.
* Chưa có lần "chạy thật" nào theo nghĩa sản phẩm (tín hiệu). Mức hiện tại: **L1** (mục 5).

## 2. Ma trận theo từng mục của brief

| § | Yêu cầu (rút gọn) | Epic / Sprint | Trạng thái | Bằng chứng / hành động |
|---|---|---|---|---|
| 0 | Vai trò, ECC loop | toàn dự án | PARTIAL | Sprint 1-2 làm "theo phương pháp" không chạy sub-agent; từ Sprint 3 có review độc lập (mục 4) |
| 1 | Mission: 8 câu hỏi hệ thống phải trả lời | 04-13 | NOT DUE | Chưa có câu nào trả lời được; map ở mục 6 |
| 2 | Tách forecast / decision | 13, 14 | NOT DUE | Kiến trúc nêu trong `architecture/system.md`; code chưa có |
| 3 | 13 phase, không bỏ qua | roadmap | DONE (thứ tự) | Phase 0, 1 xong; 2-11 map vào sprint 3-13; phase 12-13 **cố ý ngoài phạm vi** (xem §31-32) |
| 4 | Quality gate mỗi phase | quy trình | PARTIAL | Gate = `dev.ps1 check` + CI. Gate A/B chính thức chỉ có từ Sprint 3 |
| 5 | Research thư viện trước khi code | Sprint 1 | DONE | `dependency-review.md` nêu đủ các thư viện trong danh sách (reviewer độc lập xác nhận); độ sâu từng mục được làm mới ở bước E0 của sprint liên quan |
| 6 | Kiến trúc tổng | `architecture/system.md` | DONE | |
| 7 | Cây thư mục | - | DEVIATION | ADR-0001: src layout `src/xau_edge`, chưa tạo `apps/`, `packages/`, `notebooks/`, `experiments/` (tạo khi cần). `data/` có, bị gitignore |
| 8 | Stack | ADR-0001, dep review | DEVIATION | Polars thay pandas (ADR); TA-Lib/STUMPY/tslearn/XGBoost/LightGBM/FastAPI/Next.js chưa cài (đúng sprint); **pre-commit và Docker: GAP** |
| 9 | Dữ liệu M5-H4, MT5 + CSV/Parquet, raw bất biến, pipeline RAW->CLEAN->RESAMPLED->FEATURES | 02, Sprint 1-2 | PARTIAL | RAW (RawStore bất biến), RESAMPLED, catalog: DONE. Bước FEATURES: Sprint 3-4 |
| 10 | 8 loại validator + **ghi log kết quả** | 03 | PARTIAL | 16 issue code DONE. Ghi log: **GAP** (chưa có module logging) |
| 11 | Feature engine | 04, Sprint 3-4 | NOT DUE | Chưa có code feature nào |
| 12 | Market structure | 05, Sprint 5 | NOT DUE | |
| 13 | Regime | 06, Sprint 5 | NOT DUE | |
| 14 | Pattern similarity (6 phương pháp, interface chung) | 07, Sprint 6 | NOT DUE | |
| 15 | Leakage safety + 3 loại test | 07, Sprint 6 | NOT DUE | Test viết trước (đã ghi trong roadmap). `tests/statistical/` chưa tồn tại |
| 16 | Outcome engine (5/10/20/30/60 bar, MFE, MAE, percentile, expected R) | 08, Sprint 7 | NOT DUE | |
| 17 | Baseline A/B/C | 09, Sprint 7 | NOT DUE | |
| 18 | ML theo thứ tự LR, RF, XGB, LGBM; DL chỉ khi có bằng chứng | 11, Sprint 10 | NOT DUE | Sau checkpoint. Plan chưa nói rõ loại DL/LSTM/Transformer/RL khỏi MVP: thêm vào acceptance epic 11 (G-14) |
| 19 | Validation theo thời gian + walk-forward | 10-11, Sprint 9-10 | NOT DUE | |
| 20 | Calibration (curve, Brier, log loss, Platt, isotonic) | 12, Sprint 10 | NOT DUE | |
| 21 | Signal schema + điều kiện NO TRADE | 13, Sprint 11 | NOT DUE | |
| 22 | Explainability | 13, Sprint 11 | NOT DUE | |
| 23 | EV engine (spread, commission, slippage, swap) | 10/13, Sprint 8, 11 | NOT DUE | Dữ liệu spread M5 đã đo; commission/swap lấy từ broker profile (chưa có trường) |
| 24 | Backtest engine + báo cáo (equity, DD, trade list, theo tháng/regime/session) | 10, Sprint 8-9 | NOT DUE | Acceptance của epic 10 chưa liệt kê equity curve, drawdown curve, trade list, monthly summary: bổ sung ở Gate A Sprint 8-9 (G-14) |
| 25 | 16 metric | 10, Sprint 9 | NOT DUE | |
| 26 | Chống overfitting (8 kiểm tra) | 10-11 | NOT DUE | Cần checklist riêng + `santa-method`; xem H-9 |
| 27 | News risk layer, backtest cửa sổ 5-60 phút | **không có epic** | **GAP** | Đề xuất: epic 19 "News risk" (interface + backtest cửa sổ), Sprint 8-9; nguồn dữ liệu lịch kinh tế chưa chọn |
| 28 | Risk engine (11 thành phần) | 14, Sprint 8-9 | PARTIAL (**GAP**) | Epic 14 chỉ liệt kê sizing, exposure, drawdown, kill switch, spread/vol/news guard, prop profile. **Thiếu trong kế hoạch:** risk per trade, max concurrent trades, daily risk budget, consecutive-loss guard, account-state validation (G-12) |
| 29 | Prop-firm profile YAML (`configs/prop/`) | 14 | NOT DUE | `configs/prop/` chưa có; **phải xác minh luật FTMO hiện hành trước khi ship** |
| 30 | Paper trading | 17, Sprint 13 | NOT DUE | |
| 31 | `ExecutionBroker` interface, Paper trước, MT5 sau | 17, Sprint 13 | PARTIAL | Interface + Paper: trong kế hoạch. `MT5ExecutionBroker`: **cố ý không làm** (phase 12-13 ngoài phạm vi) |
| 32 | Live execution tắt mặc định, nhiều lớp an toàn | Sprint 1-3 | PARTIAL | DONE: cờ tắt (Settings frozen), DEMO guard, ReadOnlyMt5Client. **Hoãn cùng phase 13:** max lot, max order count, account/symbol whitelist, xác nhận môi trường, dry-run (không epic nào chứa). Kill switch ở epic 14 |
| 33 | API FastAPI (11 endpoint) | 15, Sprint 12 | NOT DUE + DEVIATION | Plan ghi "không có endpoint ghi/lệnh" nhưng brief có `POST /paper/orders`. Quyết định D-5: thêm endpoint paper ở Sprint 13, kèm test chứng minh không chạm broker thật (G-13) |
| 34-36 | Dashboard, analogue viz, decision card | 16, Sprint 12 | NOT DUE | |
| 37 | Logging & observability; signal tái lập được | **không có** | **GAP** | Đề xuất: Sprint 4, `xau_edge.logging` (structlog hoặc stdlib JSON) + log ingestion/validation ngay; thêm dần mỗi epic |
| 38 | Model versioning (8 trường) | **không có** | **GAP** | Đề xuất: gộp vào Sprint 10 (ML) nhưng chốt schema artifact ở Gate A của Sprint 10 |
| 39 | Experiment registry (dataset version, params, seed, code version) | **không có** | **GAP** | Cần **trước** backtest đầu tiên: đề xuất Sprint 7 (cùng eval-harness). Dataset id đã có (Sprint 2) |
| 40 | Test strategy 4 loại | liên tục | PARTIAL | unit: DONE; integration: có test MT5 đánh dấu `mt5`, chưa chạy CI; **regression + statistical: chưa có thư mục**, đến với epic 07/10 |
| 41 | Bảo mật secrets | Sprint 1-3 | DONE | `.env` ignored, secret scan, lịch sử sạch; mật khẩu demo từng bị lộ trong chat, đã khuyến nghị đổi |
| 42 | Chất lượng code | liên tục | DONE | ruff, mypy strict, type hints |
| 43 | 9 tài liệu bắt buộc | rải rác | PARTIAL | Có: README, system.md, dependency-review.md, decisions/. **Chưa có:** `architecture/data-flow.md`, `research/pattern-similarity.md`, `research/model-evaluation.md`, `risk/risk-engine.md`, `testing/testing-strategy.md`, `operations/paper-trading.md`. Phần lớn "tới hạn" cùng epic; `data-flow.md` và `testing-strategy.md` nên viết ngay Sprint 4 |
| 44 | AGENTS.md | Sprint 1 | DONE | Bổ sung delivery loop Sprint 3 |
| 45 | Lệnh phát triển | Sprint 1 | PARTIAL | `dev.ps1`/Makefile có setup, lint, typecheck, test, test-integration; **thiếu** `backtest`, `api`, `dashboard`, `research` (tới hạn theo epic) |
| 46 | PROJECT_PLAN | Sprint 1 | DONE | Có đủ epic/dependency/acceptance/risk/size |
| 47 | 18 epic | PROJECT_PLAN | DONE | Đủ 18 epic, đủ thứ tự |
| 48 | Phạm vi Phase 1: không ML tới khi pipeline xác định chạy được | roadmap | DONE | ML sau checkpoint Sprint 9 |
| 49 | 12 tiêu chí MVP | - | xem mục 6 | 1, 2, 3, 11 đạt; 12 một phần |
| 50 | Quy trình mỗi chu kỳ | ECC loop | DONE từ Sprint 3 | Sprint 1-2 thiếu bước "state the task"/báo cáo chuẩn ở một số chu kỳ |
| 51 | Danh sách DO NOT | liên tục | DONE (đến nay) | Không backtest giả, không bật live, không commit secret |
| 52 | Red-team cuối mỗi phase | liên tục | PARTIAL | E5 đã có "red-team"; report Sprint 1-2 có bảng. **Chưa bắt buộc có mục red-team viết ra trong mọi sprint report** (G-9) |
| 53 | Definition of Done | AGENTS.md | DONE | |
| 54 | Delivery format A-E | Sprint 1 | DONE | |
| 55 | First execution task (10 mục) | Sprint 1 | DONE | |
| 56 | Nguyên tắc "NO TRADE hợp lệ" | thiết kế | NOT DUE | Phải được thể hiện bằng test ở Sprint 11 (WAIT là mặc định an toàn) |

## 3. Các GAP cần quyết định (brief có, kế hoạch chưa có)

| ID | Nội dung | Đề xuất | Sprint |
|---|---|---|---|
| G-1 | Logging có cấu trúc, signal tái lập (§10, §37) | Module logging + log ingestion/validation | 4 |
| G-2 | News risk layer (§27, §28 news guard) | Thêm epic 19; chọn nguồn lịch kinh tế bằng `search-first`; nếu không có dữ liệu thì chỉ làm interface + ghi rõ giới hạn | 8-9 |
| G-3 | Experiment registry (§39) | Registry nhẹ (JSONL/Parquet + dataset id + git hash + seed) trước backtest đầu tiên | 7 |
| G-4 | Model versioning (§38) | Schema artifact chốt trước ML | 10 |
| G-5 | Tài liệu §43 còn thiếu | Viết cùng epic; `data-flow.md`, `testing-strategy.md` ngay | 4 (+ rải rác) |
| G-6 | `tests/regression`, `tests/statistical` (§40) | Tạo thư mục cùng epic 07/10 | 6, 9 |
| G-7 | `configs/prop` + xác minh luật FTMO (§29) | Cùng Risk engine; xác minh bằng nguồn chính thức, ghi ngày | 8 |
| G-8 | pre-commit, Docker (§8) | pre-commit: tùy chọn, rẻ, đề xuất làm Sprint 4. Docker: hoãn tới API/dashboard (§8 "where useful") | 4 / 12 |
| G-9 | Checklist overfitting §26 + mục red-team viết ra bắt buộc trong mỗi sprint report (§52) | Đưa vào tiêu chí đóng sprint | từ Sprint 4 |
| G-10 | Make targets `backtest/api/dashboard/research` | Thêm khi epic tương ứng có code | 9, 12 |
| G-12 | 5 thành phần risk còn thiếu trong epic 14 (§28) | Bổ sung vào task epic 14 | 8 |
| G-13 | `POST /paper/orders` (§33) | Quyết định D-5 | 13 |
| G-14 | Acceptance thiếu: báo cáo backtest (equity/DD/trade list/monthly), loại bỏ DL khỏi MVP | Bổ sung vào epic 10, 11 | 8-10 |
| G-15 | `PROJECT_PLAN.md` có hai cách đánh số sprint mâu thuẫn (bảng epic vs bảng roadmap) | Lấy bảng roadmap làm chuẩn; sửa cột Sprint của bảng epic (đã sửa trong lần cập nhật này) | xong |
| G-11 | Brief chưa nằm trong repo | Xem D-1 | ngay |

## 4. Kiểm tra theo ECC (E0-E7) cho từng sprint

| Bước | Sprint 1 | Sprint 2 | Sprint 3 (đến nay) |
|---|---|---|---|
| E0 Research & reuse | có (dependency review) | một phần (duckdb/pyarrow) | có |
| E1 Plan | có (PROJECT_PLAN) | có (nhưng không qua `/plan` agent) | có |
| Gate A | **bỏ qua** (chưa có khái niệm Gate) | **bỏ qua** | có ("ok, thực hiện như đề xuất") |
| E2 Tests first | một phần | một phần; lô test đầu không quan sát RED | có RED -> GREEN |
| E3 Implement | có | có | có |
| E4 Review độc lập | **bỏ qua** (chỉ tự review) | **bỏ qua** | có (code, python, security; 2 vòng) |
| E5 Verify | có, mutation spot-check | có | có |
| Gate B | **bỏ qua** | **bỏ qua** | commit `270e484` do chủ dự án yêu cầu push; PROJECT_PLAN còn ghi "awaiting Gate B" (lỗi thời, sửa) |
| E6 Commit | có | có | có |
| E7 Record | ADR, report | ADR, report | `ECC_ALIGNMENT_AUDIT.md`; `unified-memory` chưa dùng |

Hệ quả: Sprint 1-2 đã được **review bù** bằng đợt audit Sprint 3 (F-01..F-21 sửa xong). Không cần làm lại.

ECC skill/agent chưa dùng nhưng roadmap đã gán: `eval-harness`, `santa-method`, `council`,
`unified-memory`, `strategic-compact`, `context-budget`, `mle-reviewer`, `api-design`, `e2e-runner`, `browser-qa`.
Không phải lỗi: chúng tới hạn ở sprint tương ứng (mục 2, bảng roadmap).

## 5. Run-ladder: khi nào "chạy thật"?

"Chạy thật" ở đây chưa bao giờ có nghĩa là giao dịch tiền thật (L5, ngoài phạm vi).

| Mức | Tên | Điều kiện vào (đã đạt cái trước + ...) | Điều kiện ra / bằng chứng | Sprint |
|---|---|---|---|---|
| L0 | Nền tảng | repo, lint, type, CI | CI xanh | 1 (xong) |
| L1 | Dữ liệu thật tin cậy | kéo MT5 demo, validate, resample, catalog | dataset id tái lập, verification report | 2 (xong) **<- hiện tại** |
| L2 | Nghiên cứu offline | features, structure, regime, pattern, outcomes chạy trên dữ liệu thật; có `make research` | thống kê analogue trên lịch sử thật, test leakage pass | 3-7 |
| L3 | Backtest có chi phí | engine + risk + walk-forward, 3 baseline | báo cáo tái lập; **Checkpoint**: có edge sau chi phí ngoài mẫu hay không | 8-9 |
| L4a | Tín hiệu offline | ML + calibration + signal engine + API/dashboard | tín hiệu BUY/SELL/WAIT có giải thích trên dữ liệu lịch sử | 10-12 |
| L4b | Paper trading | `PaperExecutionBroker` chạy với dữ liệu demo trực tiếp | nhật ký lệnh mô phỏng cùng schema | 13 |
| L4c | Forward test | paper chạy nhiều tuần | so sánh ngoài mẫu với backtest, đủ cỡ mẫu | 14+ (tính theo lịch) |
| L5 | Giao dịch thật | - | **ngoài phạm vi**; cần quyết định riêng và brief phase 12-13 | không có |

**Lần "chạy thật" đầu tiên có ý nghĩa sản phẩm**: kết quả L3 ở cuối Sprint 9 (ước lượng 7 sprint nữa, mỗi sprint M-L
khoảng 3-10 ngày làm việc tập trung). Lần đầu thấy **tín hiệu** trên dashboard: Sprint 12. Nếu Checkpoint kết luận
không có edge thì kết quả đúng là dừng và báo cáo, không phải làm tiếp ML.

## 6. Sản phẩm cuối cùng và tiêu chí MVP (§49)

Sản phẩm: một nền tảng nghiên cứu, chạy cục bộ, nhận dữ liệu XAUUSD từ MT5 (demo) hoặc file, và với mỗi thời điểm
cho ra BUY / SELL / WAIT kèm xác suất đã calibrate cho UP/DOWN/NEUTRAL, kỳ vọng sau chi phí, bối cảnh nhiều khung
thời gian, các analogue lịch sử và lời giải thích. WAIT là kết quả hợp lệ và thường gặp. Hệ thống **không đặt lệnh thật**
và không hứa lợi nhuận; mọi nhận định đều kèm bằng chứng ngoài mẫu.

| # | Tiêu chí MVP | Trạng thái |
|---|---|---|
| 1 | Import XAUUSD từ MT5 | DONE (demo, đã xác minh) |
| 2 | Validation thành công | DONE |
| 3 | Dataset M5/M15/H1/H4 truy vấn được | DONE (DuckDB SQL read-only) |
| 4 | Feature engine tái lập | NOT DUE (Sprint 3-4) |
| 5 | HH/HL/LH/LL/BOS/CHoCH | NOT DUE (Sprint 5) |
| 6 | Analogue lịch sử | NOT DUE (Sprint 6) |
| 7 | Xác suất UP/DOWN/NEUTRAL | NOT DUE (Sprint 7) |
| 8 | Backtest baseline | NOT DUE (Sprint 8-9) |
| 9 | Có chi phí | NOT DUE (Sprint 8) |
| 10 | Dashboard | NOT DUE (Sprint 12) |
| 11 | Không thể gửi lệnh thật | DONE (settings frozen, DEMO guard, allowlist; chưa có code gửi lệnh) |
| 12 | Module quan trọng có test | PARTIAL (module hiện có: 98% coverage) |

Ánh xạ 8 câu hỏi của §1: (1) regime -> S5; (2) bias HTF -> S5; (3) analogue -> S6; (4) kết quả sau analogue -> S7;
(5) xác suất -> S7 (thô), S10 (calibrate); (6) expected move -> S7; (7) edge sau chi phí -> S8-9; (8) BUY/SELL/WAIT -> S11.

## 7. Quyết định cần chủ dự án

* **D-1**: thêm brief gốc vào repo (`docs/BRIEF.md`) để các lần kiểm tra sau không phụ thuộc hội thoại? (đề xuất: có)
* **D-2**: chấp nhận gán G-1..G-10 vào các sprint như mục 3 (kèm epic 19 News risk)?
* **D-3**: xác nhận phase 12-13 (bán tự động, thực thi tự động) **vĩnh viễn ngoài phạm vi** cho tới khi có quyết định riêng.
* **D-5**: có thêm `POST /paper/orders` (chỉ paper, có test không chạm broker thật) ở Sprint 13 như brief §33 không? (đề xuất: có)
* **D-4**: bắt đầu Sprint 3 bước 4 (indicators) bằng `/plan` và Gate A mới?

## 8. Ghi chú vị trí

Workflow CI nằm ở gốc git (`.github/workflows/xau-edge-ci.yml`), không nằm trong `xau-edge/`.

## 9. Phương pháp và giới hạn của bản kiểm tra này

Ma trận do tác giả dự án (cùng một agent) lập, sau đó một reviewer độc lập (ngữ cảnh mới) đối chiếu brief gốc
với ma trận; kết quả ở bên dưới. Mức độ "bằng chứng" của các dòng `NOT DUE` chỉ là sự tồn tại của mục trong
kế hoạch, không phải bằng chứng rằng phần đó sẽ đạt.

## 10. Kết quả review độc lập (ngữ cảnh mới)

Reviewer xác nhận mọi mục §0-§56 đều có dòng; 9 phát hiện CONFIRMED/PLAUSIBLE đã được tích hợp: test-integration đã có (sửa
§45), red-team đã có trong E5 (sửa §52), `POST /paper/orders` (G-13), hai cách đánh số sprint mâu thuẫn (G-15),
5 thành phần risk thiếu (G-12), mức độ hoàn thành §32 (tách DONE/hoãn), §5 nâng lên DONE, acceptance backtest/DL (G-14),
vị trí CI. Không có phát hiện về logging, `configs/prop`, pre-commit/Docker (xác nhận GAP đúng) hay run-ladder (nhất quán).
Chưa được reviewer kiểm tra: từng bản sửa F-xx và số liệu 298 test/98% (tác giả đã chạy lại gate trong phiên này).

## 11. Cập nhật sau khi xử lý nợ (cùng ngày)

| ID | Kết quả |
|---|---|
| G-1 logging | Đã làm: `observability.py`, log `raw.write`, `validation.result`, `catalog.load`; redaction có test và mutation |
| G-2 news | Đã thêm epic 19 vào kế hoạch (Sprint 8-9) |
| G-3 registry | Gán Sprint 7 trong roadmap |
| G-4 model versioning | Giữ Sprint 10, schema chốt ở Gate A |
| G-5 tài liệu | Đã viết `architecture/data-flow.md`, `testing/testing-strategy.md`; còn lại viết cùng epic |
| G-6 test dirs | Đã tạo `tests/regression` (pin hash) và `tests/statistical` (README, chưa có test giả) |
| G-7 configs/prop | Ghi vào epic 14 (cần xác minh luật FTMO) |
| G-8 pre-commit | `.pre-commit-config.yaml` (chỉ cấu hình, chưa cài hook); Docker hoãn |
| G-9 red-team | Thêm tiêu chí đóng sprint vào PROJECT_PLAN |
| G-10 make targets | Chưa tới hạn |
| G-11 brief | `docs/BRIEF.md` |
| G-12..14 | Đã bổ sung vào epic 10, 11, 14, 15 |
| G-15 | Đã sửa cột Sprint của bảng epic |
| D-4 Sprint 3 bước 4 | Đã làm: `features/indicators.py`, ADR-0010 |
