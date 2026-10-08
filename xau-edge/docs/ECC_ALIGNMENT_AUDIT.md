# Kiểm toán tuân thủ lộ trình ECC (XAU EDGE, sau Sprint 2)

Ngày: 2026-10-08. Phạm vi: Sprint 1-2 (`b38b786`..`5f49e71`). Không có mã nguồn nào bị sửa trong lần
kiểm toán này; chỉ thêm tài liệu này và cập nhật `docs/PROJECT_PLAN.md`.

Quy ước bằng chứng: **ĐÃ CHẠY** (có output), **ĐÃ ĐỌC** (code/tài liệu), **SUY LUẬN**.

## 1. Câu trả lời thẳng

**Đúng một phần.** Chúng ta đã dùng ECC như một *phương pháp*: định dạng plan của `planner`,
test trước (có bằng chứng RED), `verification-loop` làm thủ công, red-team, kiểm tra đột biến.
Nhưng chúng ta **chưa theo đúng lộ trình ECC** ở ba điểm có hậu quả thật:

1. **Không có lớp review độc lập** trước khi commit (`code-reviewer`, `python-reviewer`,
   `security-reviewer`). Khi chạy review hồi tố hôm nay, ba reviewer tìm ra **1 lỗi HIGH và 12 lỗi
   MEDIUM** mà tự review của tôi bỏ sót. Lỗi HIGH nằm trong chính phân loại "đóng cửa" tôi viết ở
   Sprint 2 (mục 5, F-01). Đây là bằng chứng trực tiếp rằng bỏ bước review có cái giá thật.
2. **Không có cổng người duyệt (Gate A/B)** theo đúng nghĩa: plan được đưa ra rồi code ngay theo
   chỉ dẫn "tiếp tục", commit không có bước xác nhận riêng.
3. **Bộ ECC cài đặt không đủ để chạy quy trình.** `minimal` thiếu các skill mà lệnh và agent ECC
   gọi tới: 79/162 file command/agent có tham chiếu tới skill không tồn tại, trong đó `/orch-*`,
   `/security-scan` và `/python-review` không chạy trọn vẹn (mục 3).

Điều làm đúng và có bằng chứng: TDD (RED quan sát được ở Sprint 1 và ở đợt sửa validator Sprint 2;
đợt test đầu Sprint 2 chưa từng được chạy để thấy RED), coverage 98%, verification, ADR, không dùng
hook ngoài ý muốn, danh tính commit và đẩy thẳng `main` theo yêu cầu.

## 2. Bảng tuân thủ quy trình ECC

Nguồn quy trình: `ECC/rules/common/development-workflow.md`, `ECC/agents/*.md`,
`ECC/skills/{tdd-workflow,verification-loop,orch-pipeline}`. [ĐÃ ĐỌC]

| # | Bước ECC | Trạng thái | Bằng chứng | Ghi chú |
|---|---|---|---|---|
| 1 | Research & reuse trước khi viết | Làm một phần | `docs/research/dependency-review.md` (PyPI/npm/GitHub API) | Không dùng `gh search`/Context7/`search-first` như quy tắc ECC; dùng API trực tiếp |
| 2 | Lập plan (`planner`) | Làm một phần | `docs/PROJECT_PLAN.md` theo định dạng planner | Không gọi `/plan`; plan do tôi viết tay |
| 3 | **Gate A: người duyệt plan** | **Chưa** | Sprint 1: prompt người dùng đã duyệt; Sprint 2: chỉ "Ok. Tiếp tục" | Không có điểm dừng chờ xác nhận riêng |
| 4 | TDD: RED trước, GREEN sau (`tdd-guide`) | Làm phần lớn | RED quan sát được: lỗi import (Sprint 1), 7 test fail (đợt sửa validator Sprint 2). **Đợt test đầu của Sprint 2** (broker clock, resample, catalog, profile) viết trước mã nhưng **không chạy để thấy RED**; chạy lần đầu sau khi cài đặt (150 qua) | Làm bằng quy trình, không chạy agent `tdd-guide`; test không từng thấy fail thì chưa chứng minh được là bắt được lỗi (đã bù một phần bằng kiểm tra đột biến) |
| 5 | Coverage >= 80% | **Đã làm** | 98% (889 stmt), 173 test, 3 phiên bản Python | |
| 6 | `/code-review` ngữ cảnh mới (`code-reviewer`) | **Chưa** (trước hôm nay) | Hôm nay: review hồi tố | |
| 7 | Reviewer theo ngôn ngữ (`python-reviewer`) | **Chưa** (trước hôm nay) | Hôm nay: review hồi tố | Agent cần skill `python-patterns`/`python-testing` chưa cài |
| 8 | `security-reviewer` + `security-review` | **Chưa** (trước hôm nay) | Chỉ có grep bí mật thủ công | Skill `security-review` chưa cài |
| 9 | `verification-loop` (6 pha) | Làm một phần | `dev.ps1 check` mỗi sprint; **pha build chưa chạy** trước commit | Hôm nay chạy đủ 6 pha: phát hiện V-01, V-02 |
| 10 | **Gate B: người xác nhận commit** | **Chưa** | Commit theo chỉ dẫn "push all lên main" | Chỉ dẫn chung, không phải xác nhận theo từng thay đổi |
| 11 | `santa-method` / `council` cho quyết định rủi ro cao | Chưa dùng | ADR-0008 dựa trên đo đạc, không cần; nhưng chưa có cơ chế đối kháng | Cả hai skill đã cài, chưa dùng |
| 12 | `eval-harness` (định nghĩa eval trước) | Chưa áp dụng | Chưa có chiến lược/mô hình | Bắt buộc từ Epic 09 |
| 13 | ADR (`architecture-decision-records`) | Làm một phần | `docs/decisions/0001-0009` | Skill chuẩn dùng `docs/adr/` và README chỉ mục; ta dùng `docs/decisions/`, chưa có chỉ mục |
| 14 | Bộ nhớ / bàn giao (`unified-memory`, `ecc memory`) | Chưa | - | |
| 15 | `strategic-compact`, `context-budget` | Chưa | - | Phiên đã rất dài |
| 16 | Hook ECC | Cố ý tắt | `hookConsent: "declined"` | Đúng với quyết định đã đưa ra |
| 17 | Họ `orch-*` | Không dùng được | Lệnh đã cài, skill động cơ chưa cài | Mục 3 |

## 3. Thành phần ECC thực sự dùng được

[ĐÃ CHẠY] trên `xau-edge/.claude` (profile `minimal`, `ecc doctor`: OK):

* **Agent đã cài:** planner, architect, tdd-guide, code-reviewer, python-reviewer, security-reviewer,
  database-reviewer, mle-reviewer, e2e-runner, build-error-resolver, refactor-cleaner, doc-updater,
  harness-optimizer (68 file agent). **Không gọi được như sub-agent trong phiên này**: danh sách
  loại sub-agent của phiên không có agent ECC. Cách làm hôm nay: giao cho sub-agent ngữ cảnh mới
  *đọc nguyên văn định nghĩa agent ECC rồi áp dụng* (không phải agent ECC gốc).
* **Skill có:** tdd-workflow, verification-loop, santa-method, council, eval-harness,
  strategic-compact, unified-memory, context-budget, agent-sort, e2e-testing,
  architecture-decision-records, ai-regression-testing, agent-self-evaluation.
* **Skill thiếu mà quy trình cần:** python-patterns, python-testing, search-first, security-review,
  security-scan, orch-pipeline, orch-add-feature (+ 3 skill orch khác), coding-standards,
  documentation-lookup, mle-workflow, api-design.
* **Tham chiếu đứt:** 79/162 file command + agent nhắc tới ít nhất một skill chưa cài. Với các
  mục then chốt: `/orch-add-feature` -> orch-add-feature, orch-pipeline, security-review;
  `/orch-fix-defect`; `/orch-review` -> orch-pipeline; `/python-review` -> python-patterns,
  python-testing; `/security-scan` -> security-review, security-scan; agent `python-reviewer`,
  `security-reviewer`, `database-reviewer`, `mle-reviewer` đều thiếu skill phụ trợ.
* **Đính chính:** trong prompt kiểm toán tôi ghi `council` là thiếu trong `minimal`; thực tế
  `council` **có** (cùng `santa-method`, `eval-harness`).

## 4. Mức độ lệch và hậu quả

| Lệch | Mức | Hậu quả đã xảy ra / có thể xảy ra |
|---|---|---|
| Không có review độc lập trước commit | **Nghiêm trọng** | 1 HIGH + 12 MEDIUM bị bỏ sót, đã vào `main` (mục 5) |
| Bộ ECC thiếu skill, nhiều lệnh đứt | **Nghiêm trọng** | Không thể chạy `/orch-*`, `/python-review`, `/security-scan` đúng thiết kế |
| Không có Gate A/B | Vừa | Không có điểm dừng để phát hiện sớm; phụ thuộc vào phản hồi ngẫu nhiên |
| `verification-loop` bỏ pha build | Vừa | Phiên bản gói 0.1.0 lệch CHANGELOG 0.2.0; sdist chứa 491 file ECC và `.env.example` (V-01, V-02) |
| Chưa dùng santa/council/eval/memory | Nhẹ hiện tại | Trở thành bắt buộc từ Epic 07-10 |
| ADR khác chuẩn skill (`docs/decisions`, không có chỉ mục) | Nhẹ | Dễ sửa |

## 5. Review hồi tố bằng reviewer độc lập (B2)

Ba reviewer ngữ cảnh mới, chỉ đọc, mỗi người đọc định nghĩa agent ECC tương ứng, lọc độ tin cậy
>= 80%, kèm kịch bản tái hiện. Tôi đã **tái hiện độc lập** các mục đánh dấu ✔.
Tổng sau khi gộp trùng: **0 CRITICAL, 1 HIGH, 12 MEDIUM, 8 LOW**.

| ID | Mức | Phát hiện | Vị trí | Nguồn | Xác minh |
|---|---|---|---|---|---|
| F-01 | **HIGH** | Khoảng trống nhiều ngày kết thúc đúng lúc mở cửa lại được xếp là `UNSCHEDULED_CLOSURES` (chỉ WARNING), không có trần độ dài, nên mất dữ liệu 13,4% vẫn "PASSED" | `validators/checks.py:100-117` | code-reviewer | ✔ tái hiện: 2730 -> 2363 dòng, PASSED |
| F-02 | MEDIUM | `Settings.enable_live_trading = True` gán được sau khi tạo (không frozen/validate_assignment), phá chốt "không live trading" | `config.py:11-31` | python-reviewer | ✔ tái hiện |
| F-03 | MEDIUM | Chốt chỉ-DEMO nằm trong script; `Mt5BarSource.connect()` không kiểm tra loại tài khoản, caller khác có thể nối tài khoản live | `mt5/source.py:88-102` | security-reviewer | ✔ grep: không có kiểm tra |
| F-04 | MEDIUM | Adapter nhận cả module MetaTrader5 (có `order_send`); đảm bảo "không có API lệnh" chỉ là kiểm tra tĩnh hẹp | `mt5/source.py`, `test_mt5_source.py:202-215` | security-reviewer | ĐÃ ĐỌC |
| F-05 | MEDIUM | `Mt5BarSource.fetch_bars` có thể trả về nến đang hình thành; chỉ script mới loại bỏ | `mt5/source.py:117-139` | code-reviewer | ĐÃ ĐỌC |
| F-06 | MEDIUM | `DatasetCatalog.load` không xác minh nội dung file; `dataset_id` không phản ánh dữ liệu thật nếu file bị sửa | `catalog.py:61-72` | code + security | ĐÃ ĐỌC (2 reviewer độc lập) |
| F-07 | MEDIUM | `.gitignore` quá hẹp: `data/*.csv`, `*.parquet`, `*.duckdb`, `*.pem`, `credentials.json`, `logs/` không bị bỏ qua | `xau-edge/.gitignore` | security-reviewer | ✔ `git check-ignore` |
| F-08 | MEDIUM | `cross_check` báo `exact=True` khi một bên có timestamp trùng | `cross_check.py:52-72` | python-reviewer | ✔ tái hiện |
| F-09 | MEDIUM | `cross_check` coi null/NaN ở cột giá là sai khác, trái với docstring | `cross_check.py:59-60` | python-reviewer | ĐÃ ĐỌC |
| F-10 | MEDIUM | `coerce_bars` cắt cụt số thực sang Int64 không báo (10.9 -> 10, 25.7 -> 25) | `domain/bars.py:77-80` | python-reviewer | ✔ tái hiện |
| F-11 | MEDIUM | `FileBarSource` đọc nhầm timestamp số nguyên (mili-giây trả rỗng; `20250303` thành 1970) | `file_source.py:182-185` | python-reviewer | ĐÃ ĐỌC |
| F-12 | MEDIUM | `FileBarSource.name` (`file:...`) bị `RawStore` từ chối làm tên nguồn | `file_source.py:103`, `store.py` | python-reviewer | ĐÃ ĐỌC |
| F-13 | MEDIUM | Chất lượng test: fixture vòng tròn (`ftmo_like_m5` dùng cùng luật với `FTMO_CALENDAR`); `FakeMt5` bỏ qua biên; thiếu test cho F-01/F-05/F-06 | `tests/synthetic.py`, `test_mt5_source.py` | code-reviewer | ĐÃ ĐỌC |
| F-14 | LOW-MED | DuckDB không giới hạn tài nguyên (`memory_limit`, thời gian); truy vấn nặng treo máy | `catalog.py:85` | security-reviewer | ĐÃ ĐỌC |
| F-15 | LOW | `RawStore.verify` nuốt mọi ngoại lệ (báo sai nguyên nhân); `datasets()`/`load()` không kiểm tên (đi ra ngoài thư mục gốc) | `store.py` | 3 reviewer | ✔ `_check_name` chỉ ở `write` |
| F-16 | LOW | Nghỉ hằng ngày cấu hình thiếu một đầu bị bỏ qua im lặng | `market_calendar.py:67-68` | code-reviewer | ĐÃ ĐỌC |
| F-17 | LOW | `resample_bars` đếm cả nến trong khung giờ đóng cửa vào "đủ nến" | `resampling.py:102` | code-reviewer | ĐÃ ĐỌC |
| F-18 | LOW | `spread_policy` sai gây `AttributeError` khó hiểu | `resampling.py:28-38` | python-reviewer | ĐÃ ĐỌC |
| F-19 | LOW | Kiểm tra căn H4 chỉ xét phút, không xét giờ | `checks.py:272` | python-reviewer | ĐÃ ĐỌC (đã nêu trong ADR-0004) |
| F-20 | LOW | Lỗi nhỏ: mẫu timestamp lỗi báo sai dòng; so khớp chuỗi trong ngoại lệ; `Bar` nhận `inf`; docstring MT5 lỗi thời | nhiều nơi | python + code | ĐÃ ĐỌC |
| F-21 | LOW | CI dùng `uv sync --frozen` (nên `--locked`) và không ghim phiên bản uv | `xau-edge-ci.yml:31-33` | security-reviewer | ✔ |

Hai reviewer độc lập cùng tìm ra F-06 và F-15, tăng độ tin cậy. Mọi khu vực reviewer ghi "sạch" (xử
lý múi giờ/DST, `Instrument`/`Bar`, ghi `RawStore`, bề mặt SQL chống ghi, YAML an toàn, không có
exec/pickle/subprocess) cũng là kết quả có giá trị.

**Việc của chủ sở hữu (không phải lỗi mã):** `xau-edge/.env.example` có số tài khoản MT5 thật trong
cây làm việc (chưa commit). Chuyển sang `.env` và trả `.env.example` về trống.

## 6. verification-loop đầy đủ 6 pha (B3)

[ĐÃ CHẠY]

| Pha | Kết quả |
|---|---|
| 1 Build (`uv build`) | Thành công nhưng **V-01**: wheel mang `0.1.0` trong khi CHANGELOG ghi `0.2.0` (chưa nâng `pyproject.toml`). **V-02**: sdist 922 KB chứa 491 file `.claude/`, `data/.gitkeep` và `.env.example` (kể cả bản có số tài khoản nếu build từ cây làm việc). Wheel không đóng gói `configs/brokers` (V-03: hồ sơ broker chỉ dùng được từ cây nguồn) |
| 2 Types | `mypy --strict`: sạch, 46 file |
| 3 Lint | `ruff check` và `ruff format --check`: sạch |
| 4 Test + coverage | 173 qua, 98% (>= 80%) |
| 5 Quét bí mật | 2 khớp, cả hai là mật khẩu giả `s3cret` trong test; không có `print`/`breakpoint` trong `src` |
| 6 Rà soát diff | Sprint 2 vs 1: 24 file, +1.822/-63 dòng |

## 7. Đề xuất sửa hướng (B1) - cần Cổng 1

**Bổ sung ECC tối thiểu** (đã dry-run, `claude-project`, `--no-hooks`, HOME giả):

| Thêm | File mới | Mở khóa |
|---|---|---|
| `skill:python-patterns`, `skill:python-testing`, `skill:search-first` | 3 | `/python-review`, E0 research |
| `skill:orch-pipeline`, `orch-add-feature`, `orch-fix-defect`, `orch-change-feature`, `orch-refine-code` | 5 | họ `/orch-*` với 2 cổng người duyệt |
| `capability:security` (kéo `security-review`, `security-scan`, `safety-guard`, `llm-trading-agent-security`, `gateguard` dạng tài liệu) | 21 (15 skill ngành không liên quan) | `security-reviewer`, `/security-scan` |

Tập 8 file đầu đã đo đúng 8 file mới. **Không** nên cài lúc này: `coding-standards` (117 file, kéo cả
module ngôn ngữ), `mle-workflow` (168 file), `lang:python`/`developer` (117-130 file). Hoãn
`mle-workflow` tới Sprint 10 và `api-design`/frontend tới Sprint 12, lúc đó đo lại bằng dry-run.

**Hook:** giữ tắt. Xem lại ở Sprint 5 khi đã có số đo độ trễ; ứng viên đầu tiên là `config-protection`
(chặn sửa cấu hình lint) và `block-no-verify`.

**Chạy phiên Claude Code ngay trong `xau-edge/`** để thử xem lệnh `/plan`, `/code-review` và agent
ECC có dùng native được không. [CHƯA KIỂM CHỨNG] Nếu không, tiếp tục cách "sub-agent áp dụng định
nghĩa ECC" đã dùng hôm nay và ghi nhãn rõ.

## 8. Lộ trình hoàn thiện

Toàn văn trong `docs/PROJECT_PLAN.md` (mục "ECC delivery loop" và "Roadmap to a complete
application"): vòng E0-E7 cho mọi epic, Gate A/B, bảng 12 sprint tới Epic 18, và một **điểm rẽ
nhánh bắt buộc sau Sprint 9**: nếu không baseline nào còn lợi thế sau chi phí ngoài mẫu, kết luận
đúng là dừng và báo cáo "không có giao dịch được biện minh về thống kê".

**Sprint 3 đề xuất, theo đúng vòng ECC:**
1. Gate A: bạn duyệt plan của Sprint 3.
2. Cài 8 + 21 file ECC nêu trên (dry-run trước).
3. Khắc phục theo thứ tự: F-01 (HIGH), F-02, F-03, F-04, F-05, F-06, F-07, F-08, V-01, V-02, rồi các
   mục MEDIUM/LOW còn lại; mỗi mục có test RED trước, fix, review lại.
4. Epic 04 phần 1 (chỉ báo kèm test đối chiếu tham chiếu độc lập).
5. Gate B: bạn xác nhận commit.

## 9. Quyết định cần bạn (Cổng 1)

| # | Quyết định | Khuyến nghị |
|---|---|---|
| D1 | Cài bộ bổ sung 8 file (workflow) và 21 file (security) | Có |
| D2 | Hook ECC | Giữ tắt; xem lại ở Sprint 5 |
| D3 | Thứ tự Sprint 3: khắc phục F-01..F-08 và V-01/V-02 *trước* Epic 04 | Có |
| D4 | Cách review từ nay | Mỗi sprint: `code-reviewer` + `python-reviewer` (+ `security-reviewer` khi đụng MT5/SQL/I-O) trước Gate B |
| D5 | Chạy Claude Code từ `xau-edge/` để thử agent native | Thử ở đầu Sprint 3 |
| D6 | Xử lý `.env.example` (số tài khoản) | Việc của bạn: chuyển sang `.env` |

## 10. Kết quả khắc phục và review lần 2 (cập nhật sau khi bạn duyệt D1-D5)

Thực hiện đúng vòng ECC: cài thành phần còn thiếu, viết test RED, sửa, review lại bằng ba reviewer
độc lập mới, sửa phát hiện mới, xác minh lại. Chưa commit (chờ Gate B).

**Cài đặt ECC (D1):** thêm 29 file, tất cả `copy-file`, không hook, không sửa `settings.json`:
`python-patterns`, `python-testing`, `search-first`, `orch-*` (5 skill) và `capability:security`
(21 file). Số file command/agent tham chiếu tới skill chưa cài giảm từ 79 xuống 17 trên 162; các
lệnh/agent then chốt (`/orch-*`, `/python-review`, `/security-scan`, `python-reviewer`,
`security-reviewer`) không còn tham chiếu đứt. `ecc doctor`: OK.

**RED -> GREEN:** 40 test thất bại + 4 module không import được trước khi sửa; sau khi sửa không
còn test nào thất bại. Vòng review thứ hai thêm 33 test RED và đã xanh.

| ID | Trạng thái | Cách đóng | Bằng chứng |
|---|---|---|---|
| F-01 HIGH | **Đã sửa** | `max_closure_minutes` (mặc định 24 h; FTMO 28 h theo đo Giáng sinh 25,8 h) | test tái hiện 31 h mất dữ liệu: ERROR; test biên 240/235 phút |
| F-02 | Đã sửa (giới hạn nêu bên dưới) | `Settings` frozen + validate_assignment + `model_copy` kiểm tra và từ chối khóa lạ | 5 test |
| F-03 | Đã sửa | kiểm tra DEMO ở `connect` và mọi `fetch_bars`; tắt terminal khi có bất kỳ lỗi nào | test contest/real/none/exception |
| F-04 | Đã sửa một phần | proxy allowlist runtime + test allowlist AST; **không phải sandbox** (xem giới hạn) | test proxy |
| F-05 | Đã sửa | bỏ nến đang hình thành trong adapter (đồng hồ truyền vào) | test biên |
| F-06 | Đã sửa | `read_verified`: hash nội dung + đối chiếu sidecar (tên file, số dòng, khoảng thời gian, symbol, timeframe) | test sửa file / sửa sidecar / tráo cả hai; dữ liệu thật 101.135 dòng vẫn nạp được |
| F-07 | Đã sửa | `.gitignore` mở rộng (dữ liệu, khóa, tên bí mật) | 30+ đường dẫn kiểm bằng `git check-ignore` |
| F-08, F-09 | Đã sửa | trùng timestamp làm `exact=False`; null/NaN so sánh nhất quán | 5 test |
| F-10 | Đã sửa | từ chối làm tròn số thực/Decimal thành số nguyên | 6 test |
| F-11, F-12 | Đã sửa | suy luận đơn vị epoch, từ chối số dạng ngày, tên nguồn luôn hợp lệ | test cho mọi dạng tên file |
| F-13 | Đã sửa một phần | mốc thời gian lấy từ đo thật; `FakeMt5` tôn trọng cận; test cho F-01/05/06 | 8 test mốc phiên |
| F-14 | Đã sửa | giới hạn bộ nhớ/luồng, timeout, trần số dòng kết quả | 3 test (có truy vấn không thể rút gọn) |
| F-15 | Đã sửa | tên đọc/ghi cùng kiểm tra; tên Windows dành riêng; `fullmatch` | test tham số hóa |
| F-16, F-17, F-18, F-20 | Đã sửa | xem CHANGELOG 0.2.1 | test riêng từng mục |
| F-19 | **Hoãn có chủ đích** | kiểm tra giờ của H4 cần đồng hồ broker; ADR-0004 đã ghi nhận | - |
| F-21 | Đã sửa | `uv sync --locked`, uv ghim 0.11.14, `persist-credentials: false`, `timeout-minutes` | test đọc workflow |
| V-01, V-02 | Đã sửa | phiên bản 0.2.1 khớp CHANGELOG (có test); sdist 922 KB -> 142 KB, không còn `.claude`, `data`, tệp env | test dựng sdist, kể cả tệp rò rỉ giả |

**Review lần 2 (3 reviewer độc lập):** `code-reviewer` APPROVE; `python-reviewer` Warning (gần
Approve); `security-reviewer` CONDITIONAL PASS. Không có CRITICAL/HIGH. Phát hiện mới đều đã sửa:
`available()` hỏng khi có thư mục lạ (3 reviewer cùng thấy), sidecar chưa xác thực, kết quả SQL
không giới hạn, `connect` chưa tắt terminal khi lỗi bất kỳ, `fullmatch`, tên file có `..`,
`model_copy` nuốt khóa gõ sai, Decimal, thông báo lỗi lặp, `.gitignore`/sdist/CI.
Thêm một lỗi chỉ lộ ra khi chạy Python 3.12: `ZoneInfo("Europe")` ném `PermissionError`.

**Kiểm chứng:** 298 test qua trên Python 3.12.13, 3.13.13 và 3.14.4; `mypy --strict` và ruff sạch;
độ phủ 98% (1.048 câu lệnh); 20 đột biến thủ công của hai vòng đều bị bắt; chạy lại
`verify_mt5.py` trên terminal FTMO demo thật cho kết quả y hệt Sprint 2.

**Giới hạn còn lại (trung thực):**
* Proxy MT5 và chốt `Settings` ngăn dùng nhầm, **không** ngăn mã độc chạy cùng tiến trình
  (`proxy._inner`, `model_construct`, `object.__setattr__`). Biện pháp thực sự: guard DEMO, công
  tắc giao dịch của terminal, và dùng mật khẩu *investor* (chỉ đọc) của MT5.
* `fetched_at` trong sidecar không tự chứng thực được; ai có quyền ghi vào kho có thể lùi ngày để
  đổi bản thắng khi trùng timestamp (hash, số dòng, khoảng thời gian thì được kiểm tra).
* Khoảng đóng cửa tới 28 h kết thúc đúng giờ mở lại vẫn chỉ là cảnh báo (đánh đổi đã ghi rõ).
* Chưa có bước `pip-audit` trong CI (cần chạy CI thật trước); CI vẫn chưa chạy trên GitHub.
* Các reviewer vẫn là sub-agent đọc định nghĩa agent ECC, không phải agent ECC native.

## 11. Giới hạn của lần kiểm toán này (ban đầu)

* Các "reviewer" là sub-agent đa dụng đọc định nghĩa agent ECC; chưa phải agent ECC chạy native.
  Chất lượng review phụ thuộc vào prompt tôi viết, nhưng các phát hiện chính đã được tái hiện độc lập.
* Mỗi mục F-xx đánh dấu "ĐÃ ĐỌC" chưa được tôi tái hiện; cần test RED khi sửa.
* Tôi đo số file cài thêm bằng dry-run, chưa cài thật.
* Mức "Nghiêm trọng/Vừa/Nhẹ" là phán đoán của tôi dựa trên hậu quả quan sát được.
