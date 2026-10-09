# Master Prompt: Web app hoàn chỉnh theo PROFITABILITY_ROADMAP (Research Console)

> Dành cho Claude Code, chạy trong `xau-edge/`. Chia việc theo "web slice" (W-R1 ... W-R8) bên dưới;
> mỗi slice là một commit nhỏ. Có thể dùng subagent song song cho các slice không dùng chung file.

---

## VAI TRÒ

Bạn là **Principal Full-stack Engineer** kiêm **Quant Research Tooling Engineer**, **Risk/Safety
Engineer** và **QA Lead**. Bạn xây một web app phục vụ MỘT mục tiêu: giúp chủ dự án chạy chương trình
nghiên cứu edge (`docs/PROFITABILITY_ROADMAP.md`) một cách **kỷ luật, nhìn thấy được và không thể
gian lận với chính mình**. Thứ tự ưu tiên: **tính toàn vẹn thống kê > an toàn vốn > tiện dụng > đẹp**.

## BỐI CẢNH

* Repo `xau-edge/`: API FastAPI (`src/xau_edge/api/`), control plane cục bộ (`src/xau_edge/control/`,
  ADR-0023), dashboard Next.js 16 + React 19 + TypeScript strict + Tailwind 4
  (`apps/dashboard/`: `app/`, `app/control/`, `components/{Dashboard,BotPanel,ControlPanel,...}`,
  `lib/{api,control}.ts`, Playwright e2e có mock).
* Đã có: panel Demo bot (read-only), trang Control (preflight, bot, mode, smoke, flatten, gõ xác nhận,
  token phía server), dashboard thị trường/tín hiệu/analogue.
* **Roadmap nói rõ**: polish dashboard, animation, biểu đồ thêm, tính năng web mới là **DEFERRED** trừ
  khi mở khóa nghiên cứu (mục 24.3). Vì vậy prompt này **chỉ** cho phép web làm các việc phục vụ
  roadmap (Research Console, ledger/K, cổng, forward, vòng đời, suy giảm edge, vận hành). Mọi thứ
  khác: không làm.
* Quyết định chủ dự án đã chốt (không tự đổi): xem `docs/PROFITABILITY_ROADMAP.md` Phụ lục A. Nếu
  D-1 (Edge Program V2) **chưa được duyệt**, bạn vẫn xây phần đọc/hiển thị, nhưng **không** thêm bất kỳ
  nút nào chạy thực nghiệm, và ghi rõ điều đó trên UI.

## ĐỌC TRƯỚC KHI LÀM (bắt buộc)

1. `docs/PROFITABILITY_ROADMAP.md` (toàn bộ; đặc biệt mục 9-13, 21-23, 25-30).
2. `AGENTS.md`, `CLAUDE.md`, `apps/dashboard/AGENTS.md` (Next.js 16 khác bản bạn biết: đọc hướng dẫn
   trong `node_modules/next/dist/docs/` trước khi viết code Next).
3. ADR-0018, 0019, 0020, 0021, 0022, 0023.
4. `docs/evals/edge-criteria.md`, `docs/research/edge-program/{ledger,final-verdict}.md`.
5. `src/xau_edge/api/{app,bot,control,service}.py`, `src/xau_edge/control/*`,
   `apps/dashboard/{app,components,lib}`.
6. `docs/operations/{demo-trading,go-live-checklist}.md`, `docs/reports/funded-readiness.md`.

## RÀNG BUỘC BẤT BIẾN (vi phạm = hủy kết quả)

1. **Không tiền thật, không bật funded/live.** Web **không** có đường bật `ENABLE_FUNDED_TRADING`, không
   có nút gửi lệnh, không nhận hướng/lot/SL/TP từ client. Control plane giữ nguyên giới hạn của
   ADR-0023 (DRY_RUN|DEMO, gõ xác nhận, token, Host/Origin guard). Mọi route ghi mới cần ADR và test
   route-table.
2. **Web không được mở holdout hay Test-H.** Không có nút "run Test-H" hoặc "run holdout". Web chỉ
   **hiển thị** trạng thái khóa, freeze record và kết quả đã có. Việc chạy do script CLI có guard
   (`freeze record`, review) thực hiện, và web chỉ đọc kết quả.
3. **Web không chạy thực nghiệm tạo bằng chứng.** Không có nút chạy backtest/Stage 1/Stage 2 từ trình
   duyệt. Web đọc ledger, registry, manifest, report. (Chạy thực nghiệm từ web sẽ phá quy tắc "mỗi lần
   chạy đếm vào K, có freeze".)
4. **Không sửa dữ liệu nghiên cứu hay ledger từ web.** Ledger/K là append-only và do code nghiên cứu
   ghi. Web read-only với `experiments/`, `docs/research/`, `data/research_history`.
5. **Không hiển thị thứ gì giống "lợi nhuận được bảo đảm".** Ngôn ngữ cho phép: candidate, evidence,
   positive expectancy, validated, not validated, rejected, uncertain. Cấm: "profit", "winning
   strategy", "will make money". Mọi đại lượng kỳ vọng phải kèm khoảng tin cậy, n, K, nhãn VALIDATED /
   UNVALIDATED / REJECTED.
6. **Không in secrets, số tài khoản đầy đủ (chỉ 3 số cuối), token, mật khẩu.** Không đọc `.env` từ
   frontend. Token control chỉ phía server (như hiện tại).
7. **Không hạ evidence gate, risk gate, news guard, kill switch, reconciliation.** Chỉ nâng cấp.
8. **Mọi thay đổi code có test trước (RED -> GREEN).** Gate bắt buộc xanh trước mỗi commit:
   `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`,
   `uv run pytest -m "not mt5"`, và trong `apps/dashboard`: `npm run lint`, `npx tsc --noEmit`,
   `npm run build`, `npm run test:e2e` (nếu có). Không dùng `--no-verify`.
9. Commit nhỏ theo slice; danh tính `git -c user.name="howtodonext.com" -c
   user.email="howtodonext.com@gmail.com"`; kết thúc message bằng
   `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; push thẳng `main`; kiểm CI sau mỗi lượt.
   Message bắt đầu bằng mã slice, ví dụ `W-R3: ...`.
10. Tài liệu viết tiếng Việt, thuật ngữ kỹ thuật giữ tiếng Anh. UI: tiếng Việt, có thể kèm nhãn
    tiếng Anh cho thuật ngữ (K, MDE, Stage 1, ...).

## KIẾN TRÚC YÊU CẦU

* **Một nguyên tắc dữ liệu:** web đọc **file/registry đã có** qua API **GET-only** mới dưới tiền tố
  `/research/*` và `/lifecycle/*`. API chỉ đọc, giới hạn đường dẫn trong thư mục cho phép
  (`docs/research/`, `experiments/`, `data/execution/`, `configs/`), chống path traversal, chặn file
  `.env*` và `*.sqlite` ghi (state chỉ qua lớp `ExecutionState`).
* **Fail-closed hiển thị:** file thiếu hoặc hỏng -> trạng thái "KHÔNG RÕ" màu cảnh báo, không bao giờ
  "OK" mặc định. Dữ liệu cũ (quá hạn) hiển thị tuổi dữ liệu.
* **Nhãn trạng thái chiến lược** theo vòng đời của roadmap (mục 23.5): RESEARCH, REJECTED, PAPER, DEMO,
  VALIDATED, FUNDED, WATCH, DISABLED, RETIRED, hiển thị bằng một component duy nhất.
* **Giao diện:** giữ phong cách hiện có (Tailwind, card, dark/light); trang mới trong `app/research/*`.
  Responsive 1440x900 và 390 px, không cuộn ngang, có `aria` cơ bản. Không thêm thư viện nặng; biểu đồ
  dùng lightweight-charts hoặc SVG sẵn có.

## CÁC SLICE (làm tuần tự theo thứ tự; slice sau phụ thuộc slice trước)

### W-R1. Research Overview ("Chúng ta đang ở đâu?")
* Trang `/research`: trạng thái chương trình lấy từ `ledger.md` (đã parse), `final-verdict.md`,
  `PROFITABILITY_ROADMAP.md` (sprint hiện tại do file `docs/research/edge-program-v2/STATE.json`
  khai báo; nếu chưa có thì "chưa bắt đầu V2").
* Hiển thị: kết luận chương trình trước (B), số giả thuyết đã dùng / ngân sách (`x/8`), `K` đã dùng /
  trần, các điều kiện dừng đã đạt hay chưa, quyết định chủ dự án đang chờ (D-1...D-5 từ roadmap
  Phụ lục A), và một dòng cố định: "Không có edge được kiểm định" khi đúng.
* API: `GET /research/overview`. Test: parse ledger mẫu, ledger hỏng -> KHÔNG RÕ.

### W-R2. Ledger & K Explorer
* Bảng mọi lần chạy (kể cả hỏng/bỏ dở), lọc theo giả thuyết/giai đoạn/kịch bản, cột: thời gian,
  giả thuyết/biến thể, giai đoạn, số lệnh, mean net R (cơ sở/bi quan), PASS/FAIL, registry id.
* Bộ đếm K: legacy (baselines, analogue, ML, Programme 1) chỉ đọc, và `K_V2`. Hiển thị `alpha = 0.05/K`.
* **MDE calculator hiển thị:** với (K, n, sd) tính và vẽ đường MDE; đánh dấu "underpowered by design"
  khi MDE > +0,20 R (khớp mục 13.3 roadmap). Dùng cùng công thức với `evaluation/power.py`; nếu P1
  chưa có, hiển thị phép tính từ một hàm thuần Python dùng chung, có test trùng bảng mục 5.1.
* API: `GET /research/ledger`, `GET /research/power?k=&n=&sd=`. Test: bảng mục 5.1 tái lập số liệu.

### W-R3. Hypothesis Registry viewer
* Danh sách H01...H14 (V1 và V2): trạng thái (đã đăng ký / đang chạy / kết quả / bị loại),
  commit đăng ký, MDE, n_events dự kiến, lưới biến thể, điều kiện làm giả thuyết sai.
* Hiển thị **bằng chứng đăng ký trước**: commit hash của file giả thuyết phải **cũ hơn** commit kết
  quả; nếu không thì nhãn đỏ "VI PHẠM ĐĂNG KÝ TRƯỚC". (Kiểm bằng `git log` phía server, chỉ đọc.)
* API: `GET /research/hypotheses`. Test: giả thuyết có kết quả trước đăng ký -> cảnh báo.

### W-R4. Candidate Report & Robustness Gates
* Với mỗi ứng viên (biến thể sống sót): bảng 7 tiêu chí (giá trị, ngưỡng, đạt/không), gross-mid so với
  net R, đường vốn, drawdown, 4 fold, loại bỏ best 5%, tập trung theo phiên/chế độ.
* Bốn cổng robustness (mục 21): Cost Stress, Parameter stability, Temporal stability, Broker
  robustness; mỗi cổng PASS / FAIL / CHƯA CHẠY, hiển thị điều kiện đã cố định trước.
* Không có nút chạy. API: `GET /research/candidates`, `GET /research/candidates/{id}`.
* Test: ứng viên thiếu cổng -> "CHƯA CHẠY", không bao giờ ngầm "PASS".

### W-R5. Data & Clock Certificates
* Hiển thị bảng dữ liệu theo timeframe/giai đoạn: số hàng, ngày đầu/cuối, dataset id, lỗi validator,
  tỷ lệ bar thiếu, **chứng nhận giờ broker theo năm** (kết quả P0), cảnh báo "session hypothesis bị
  chặn" khi năm chưa được chứng nhận.
* Hiển thị trạng thái khóa dữ liệu: Development-2, Validation-2, **Test-H (pristine / đã dùng)**,
  **Holdout (pristine / đã dùng)**, Forward; đọc từ registry/freeze record. Nhãn "burned" cho dữ liệu
  đã dùng thiết kế.
* API: `GET /research/data`, `GET /research/locks`. Test: dữ liệu không có chứng nhận -> không "OK".

### W-R6. Forward & Edge Decay Monitor
* Forward paper: **expected vs realised** (tần suất tín hiệu, mean R, MFE, MAE, spread giả định vs thực,
  slippage giả định vs thực, độ trễ), kèm n và khoảng tin cậy; dưới 100 lệnh hiển thị "KHÔNG KẾT LUẬN".
* Edge decay: rolling expectancy, PF, Sharpe, drawdown, cost drift; trạng thái VALIDATED -> WATCH ->
  DEGRADED -> DISABLED -> RESEARCH theo quy tắc mục 23.4. Ngưỡng cố định ở file cấu hình đã commit.
* **Nút duy nhất có tác động:** "Hạ trạng thái chiến lược" (demote). Quy tắc: chỉ **hạ bậc**
  (WATCH/DEGRADED/DISABLED), không bao giờ nâng bậc từ web; cần gõ xác nhận, đi qua control plane và
  journal; không đụng vị thế. Nâng bậc chỉ qua ledger/ADR/CLI.
* API: `GET /lifecycle/strategies`, `GET /lifecycle/{id}/forward`, `POST /control/lifecycle/demote`
  (route ghi duy nhất của slice này; cần ADR addendum, test route-table).
* Test: nâng bậc từ web bị từ chối (4xx); demote không có xác nhận bị từ chối.

### W-R7. Execution Calibration & Operations
* Trang đo chi phí thật (sau P12): spread/slippage/commission/swap đo được so với giả định của
  `CostModel`, tỷ lệ reject/UNKNOWN, độ trễ lệnh; cảnh báo khi vượt ngưỡng Cost Stress.
* Hiển thị tiến độ soak 14 ngày và demo 4 tuần (uptime M15, bar trùng, sự cố) từ `cycles.jsonl`,
  `journal.jsonl`, `alerts.jsonl`; tiến độ rollout tier và 13 luật `must_verify` (chỉ đọc
  `ftmo_funded.yaml`, hiển thị còn bao nhiêu chưa xác minh; **không có nút sửa**).
* API: `GET /research/calibration`, `GET /research/soak`. Test: thiếu dữ liệu -> "KHÔNG RÕ".

### W-R8. Quality, an toàn và tài liệu
* Playwright e2e có mock cho mọi trang mới (1440x900 và 390 px, không lỗi console), test an toàn:
  trang không có control cho bất kỳ hành động bị cấm nào (không có nút Test-H, holdout, backtest, funded).
* Test an toàn: route-table (chỉ các route ghi đã được duyệt), path traversal, `.env*` bị chặn,
  secrets không xuất hiện trong response, ngôn ngữ cấm ("profit", "guaranteed") bị quét trong bundle UI.
* Tài liệu: `docs/operations/research-console.md` (cách dùng, nguồn dữ liệu của từng trang, ý nghĩa
  nhãn), cập nhật `README.md`, `docs/architecture/`, ADR addendum cho route ghi mới.
* Chụp ảnh màn hình mỗi trang vào `docs/reports/img/`. Review độc lập bằng agent riêng (bảo mật +
  tính toàn vẹn thống kê của hiển thị) trước commit cuối; sửa mọi phát hiện HIGH.

## ĐỊNH NGHĨA XONG (DoD)

* Cả 8 slice xong, test xanh, CI xanh, ảnh chụp và tài liệu có mặt.
* Web **hiển thị đúng** trạng thái nghiên cứu hiện tại ("(B) NO EDGE WITHIN BUDGET", K, ngân sách,
  khóa Test-H/holdout còn nguyên, quyết định D-1... đang chờ) và **không** có đường nào chạy thí
  nghiệm, mở holdout, bật funded hay gửi lệnh từ trình duyệt.
* Mọi số liệu trên UI truy ngược được tới file nguồn (đường dẫn hiển thị khi rê chuột/chi tiết).

## BÁO CÁO CUỐI MỖI LƯỢT

Slice nào xong (commit hash), test và kết quả (số thật), ảnh chụp, lỗi đã tìm và sửa, quyết định đang
chờ chủ dự án, và dòng cố định nếu còn đúng: "Không có edge được kiểm định; web chỉ hiển thị và theo
dõi, không chạy thí nghiệm, không mở holdout, không bật funded."

## ĐIỀU KIỆN DỪNG

Dừng và báo cáo nếu: (1) một slice đòi một route ghi hoặc nút bị cấm ở trên; (2) cần nới guard hoặc
sửa safety test để pass; (3) cần dữ liệu/quyết định chỉ chủ dự án có (D-1..D-5, nguồn lịch tin, mật
khẩu giao dịch); (4) gate không xanh sau hai lần sửa có lý do.
