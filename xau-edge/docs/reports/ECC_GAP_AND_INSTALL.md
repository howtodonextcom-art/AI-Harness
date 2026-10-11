# ECC_GAP_AND_INSTALL: so sánh, phân tích và kế hoạch cài đặt ECC cho xau-edge

> Viết cho: chủ dự án (đọc tiếng Việt, hiểu giao dịch, không rành cấu hình Claude Code).
> Ngày 2026-10-11. **Trạng thái: GIAI ĐOẠN 1-2 XONG (chỉ đọc). GIAI ĐOẠN 3 (cài đặt) CHƯA CHẠY, đang chờ cổng duyệt ở mục 5.**
> Nhãn: **ĐÃ KIỂM** (có lệnh/đếm), **CHƯA KIỂM**, **SUY LUẬN**. Mọi lệnh ECC chạy với HOME tạm; không file nào của dự án bị sửa ngoài file báo cáo này.
> Điểm xuất phát: `ECC_USAGE_AUDIT.md`. Hai kết luận trong đó được **sửa lại** ở mục 3 (đề xuất tỉa skill, và độ tin của điểm `harness-audit`).

## 1. So sánh: ECC đúng thiết kế và xau-edge hiện tại — ĐÃ KIỂM

| Khía cạnh | ECC đúng thiết kế | xau-edge hiện tại | Khoảng cách |
|---|---|---|---|
| Cách cài | Plugin `ecc@ecc` (cấp người dùng) hoặc cài file theo target | Cài file vào `xau-edge/.claude/` (target `claude-project`, 2026-10-08) | Không có plugin; `.claude/` nằm ở `xau-edge/`, còn gốc git và thư mục làm việc phổ biến là `AI-Harness/` |
| Phiên bản | upstream 2.2.3 `4eb71d92` | cài 2.2.2 `c70874f` | Cũ một bản. Changelog 2.2.3 chỉ đổi tên hiển thị và quy trình phát hành: **không có tính năng mới đáng giá** |
| Sức khoẻ cài đặt | `ecc doctor` OK | `ERROR`: 2 file nguồn đã bị upstream đổi tên (`.agents/skills/everything-claude-code/...`); `ecc repair` cũng dừng vì lý do này | Cần cài lại để làm mới install-state |
| Profile và thành phần | chọn đúng nhu cầu | `minimal` + 9 thành phần: 15 module, 520 file | Xem mục 3: bộ cài chia theo module, không chọn lẻ từng skill được |
| Hook | 27 mục hook (PreToolUse trên mọi Bash/Write/Edit, Stop, SessionStart...) | 0 (`hookConsent: declined`) | Cố ý; xem phân tích hook ở mục 2 |
| Agent gọi được như sub-agent | có (qua plugin) | không trong phiên đã kiểm | **CHƯA KIỂM** nguyên nhân: do thiếu plugin, hay do `.claude/` ở `xau-edge/` mà phiên chạy ở `AI-Harness/` |
| Rules nạp vào ngữ cảnh | common + ngôn ngữ | common + python (16 file, ~5,8k token) | khớp |
| Vòng delivery (plan, test trước, review độc lập, Gate A/B, verify) | do skill/agent thực thi | thực hiện bằng quy trình tay + sub-agent đa năng + `scripts/dev.ps1 check`; 31 ADR | Dùng tinh thần, không dùng thành phần theo tên (xem `ECC_USAGE_AUDIT.md` mục 3) |
| Cưỡng chế bằng máy | hook Claude + CI | **git pre-commit** (ruff, ruff format, mypy `--strict`, chặn `.env`) + CI 8 job | Có cưỡng chế, nhưng CI **không đo coverage** và không giới hạn kích thước file (4 file `src` > 800 dòng) |
| Bộ nhớ/handoff | `unified-memory`, `ecc memory` | bộ nhớ tự động của Claude (`MEMORY.md`), không dùng `ecc memory` | Khác cơ chế, đủ dùng |
| Quy ước commit | ECC mặc định không trailer | `CLAUDE.md` mục 7: bỏ trailer; prompt gốc + nhắc của môi trường: thêm trailer; 110/166 commit có trailer | **Mâu thuẫn giữa hai nguồn của chủ dự án** |
| `harness-audit.js` | công cụ đo | 16/39 chạy ở `xau-edge/`; **12/39 chạy ở gốc `AI-Harness/`** | Hai điểm khác nhau cho cùng một dự án: công cụ tìm `.claude/` và `.github/` ở thư mục gốc nó được chạy. Không dùng làm thước đo |

## 2. Phân tích khoảng cách — ĐÃ KIỂM trừ khi ghi khác

Thang: Giá trị cho xau-edge 0-3; Rủi ro khi thay đổi 0-3; Chi phí; Đảo ngược.

| # | Khoảng cách | Giá trị | Rủi ro | Chi phí | Đảo ngược | Quyết định |
|---|---|---|---|---|---|---|
| G1 | `doctor` ERROR + lệch phiên bản | 1 | 1 | thấp | dễ (sao lưu, git) | **LÀM** |
| G2 | CI không đo coverage | 2 | 0 | thấp | dễ | **LÀM** (đo trước, ngưỡng sau) |
| G3 | 4 file `src` > 800 dòng, không gì chặn tăng thêm | 2 | 1 | thấp | dễ | **LÀM** (chặn tăng, không ép tách ngay) |
| G4 | Bật plugin `ecc@ecc` ở cấp người dùng | 1 | 3 | thấp | vừa | **KHÔNG LÀM** |
| G5 | Bật hook ECC | 1 | 3 | vừa | vừa | **KHÔNG LÀM** |
| G6 | Tỉa 15 skill và 19 agent không liên quan | 0 | 2 | vừa | khó | **KHÔNG LÀM** |
| G7 | Agent ECC không gọi được | 2 | 1 | thấp để kiểm | dễ | **CÂN NHẮC** (kiểm trước) |
| G8 | Mâu thuẫn trailer commit | 1 | 0 | thấp | dễ | **CẦN BẠN QUYẾT** |
| G9 | Quy trình tối thiểu chưa được viết ra một chỗ | 2 | 0 | thấp | dễ | **LÀM** |

**G4, plugin `ecc@ecc`: không làm.** Bật ở cấp người dùng nạp 302 skill, 71 agent, 95 command và toàn bộ hook cho **mọi** dự án của bạn, không chỉ xau-edge. Lợi ích duy nhất là gọi agent theo tên, mà việc đó có thể đạt bằng cách khác (G7). Rủi ro: cao.

**G5, hook ECC: không làm.** Ba hook có mô tả nặng với dự án này:
* `pre:config-protection` chặn sửa file cấu hình lint/format. Trong sprint vừa rồi chúng ta sửa `eslint.config.mjs` một cách chính đáng; hook này sẽ chặn.
* `pre:edit-write:gateguard-fact-force` chặn lần Edit/Write đầu tiên của **mỗi file** cho tới khi trả lời một bộ câu hỏi: ma sát lớn với công việc nhiều file.
* `stop:format-typecheck` chạy Biome/Prettier/`tsc` cho JS/TS: dự án dùng eslint và đã có pre-commit cho Python, nên trùng lặp.
Không có hook nào trong 27 mục là dành cho Python/ruff/mypy. Phần cưỡng chế thật sự cần (ruff, mypy, chặn `.env`) đã nằm ở git pre-commit và CI.

**G6, tỉa skill/agent: không làm, và đây là điểm sửa lại báo cáo trước.**
* `ecc install-plan` cho thấy bộ cài chia theo **module**, không chọn lẻ được từng skill: bất kỳ skill nào (kể cả `santa-method`) kéo theo cả hai module `workflow-quality` (48 skill) và `security` (22 skill). Một kế hoạch "chỉ 17 skill cần thiết" cho ra **78** thư mục skill, nhiều hơn hiện tại (75).
* Muốn bớt phải xoá tay file trong `.claude/`, trái với `AGENTS.md` ("không sửa tay") và làm `ecc doctor` báo lệch vĩnh viễn.
* Giá trị thấp: ước tính 15 skill không liên quan chỉ tốn khoảng **1,4k token** mỗi phiên (tổng danh sách skill ~7k, rules nạp ~5,8k, `AGENTS.md` + `CLAUDE.md` ~5,6k). Các agent ngôn ngữ nằm trên đĩa, không được liệt kê vào ngữ cảnh.

**G7, agent không gọi được: kiểm trước khi tốn công.** Giả thuyết (SUY LUẬN): Claude Code đọc `.claude/agents/` của **thư mục gốc dự án nơi phiên khởi chạy**; ở đây `.claude/` của ECC nằm ở `xau-edge/` trong khi thư mục làm việc/gốc git là `AI-Harness/` (nơi `.claude/` chỉ có `settings.local.json`). Cách kiểm rẻ: mở một phiên Claude Code với thư mục làm việc là `xau-edge/` và xem danh sách agent. Nếu gọi được, không cần cài thêm gì.

**G2 và G3, cưỡng chế bằng CI thay cho hook.** `pyproject.toml` đã có cấu hình coverage (`branch = true`) nhưng CI không chạy `--cov`. Chặn tăng kích thước file có thể làm bằng một script ngắn với danh sách ngoại lệ ghi lý do cho 4 file hiện tại.

**G8, trailer.** Hai nguồn của chính bạn mâu thuẫn: `CLAUDE.md` mục 7 nói xoá trailer `Co-authored-by`; prompt gốc yêu cầu `Co-Authored-By: Claude Sonnet 5.5`; 110 trên 166 commit đã có trailer. Tôi không tự chọn thay bạn.

**Chi phí ngữ cảnh ước tính (SUY LUẬN từ số ký tự chia 4):** danh sách skill ~7k token, rules ECC ~5,8k, `AGENTS.md`+`CLAUDE.md` ~5,6k: tổng khoảng 18k token mỗi phiên.

## 3. Hai điều sửa lại trong `ECC_USAGE_AUDIT.md`

1. Đề xuất #3 ("gỡ skill/agent không liên quan") **không khả thi bằng installer** và giá trị thấp: rút lại.
2. Điểm `harness-audit` (16/39) không phản ánh chất lượng: cùng dự án cho 12/39 khi chạy từ thư mục khác. Mục nói cưỡng chế "bằng 0" cũng cần sửa: git pre-commit đã cưỡng chế ruff, format, mypy và chặn `.env`.

## 4. Kế hoạch thay đổi (mỗi mục độc lập, làm từng mục một)

| # | Việc | File chạm | Lệnh dự kiến | Kiểm tra thành công | Hoàn tác |
|---|---|---|---|---|---|
| C1 | Cài lại ECC để làm mới install-state lên 2.2.3 và hết `ERROR` | `xau-edge/.claude/**` (đã theo dõi bởi git) | sao lưu `.claude/` ra thư mục có ngày giờ ngoài git; `node ECC/scripts/install-plan.js` rồi `ecc install --target claude-project --profile minimal` với đúng 9 thành phần đang dùng, **không hook**, HOME tạm | `ecc doctor` OK; số agent/skill/command/rule không giảm; `git diff --stat .claude` chỉ đổi file ECC | `git checkout -- xau-edge/.claude` hoặc chép lại bản sao lưu |
| C2 | CI đo coverage (không ngưỡng) | `AI-Harness/.github/workflows/xau-edge-ci.yml` | thêm `--cov` vào một job Python (ví dụ ubuntu py3.13), in `term-missing` | CI xanh; số coverage hiện trong log | `git revert` commit |
| C3 | Script chặn file nguồn vượt 800 dòng với danh sách ngoại lệ có lý do | `xau-edge/scripts/check_file_sizes.py` (+ test), workflow | thêm bước chạy script trong CI và pre-commit (tuỳ chọn) | CI xanh với 4 ngoại lệ; thêm 1 dòng vào file ngoại lệ thì CI đỏ | `git revert` |
| C4 | Viết "Quy trình tối thiểu" một chỗ trong `CLAUDE.md` (chạy bộ test đầy đủ trước push, review độc lập cho thay đổi guard/thực thi, Santa cho báo cáo rủi ro cao, ADR) và sửa `ECC_USAGE_AUDIT.md` theo mục 3 | `CLAUDE.md`, `docs/reports/ECC_USAGE_AUDIT.md` | chỉ sửa tài liệu | chủ dự án đọc và đồng ý | `git revert` |
| C5 | Kiểm giả thuyết G7: mở phiên với thư mục làm việc `xau-edge/` | không file nào | do bạn mở phiên, tôi đọc danh sách agent | agent ECC xuất hiện hay không | không cần |
| C6 | Quyết định trailer (G8) | `CLAUDE.md` mục 7 | chỉ sửa một dòng sau khi bạn chọn | một nguồn duy nhất | `git revert` |

Không làm: bật plugin, bật hook ECC, xoá skill/agent bằng tay.

**Cách đo hiệu quả và mốc đánh giá lại (2026-11-11):** (a) số lần CI đỏ do quy trình (test cũ, lint) so với tháng trước; (b) coverage đo được ở C2 và xu hướng; (c) số file `src` vượt 800 dòng (không được tăng); (d) số lỗi bắt bởi review độc lập so với lỗi phát hiện sau merge, ghi vào báo cáo từng sprint.

## 5. CỔNG DUYỆT (đang dừng ở đây)

Giai đoạn 3 chỉ chạy các mục bạn trả lời rõ. Cần bạn chọn:
* C1: có / không.
* C2 và C3: có / không (mỗi mục).
* C4: có / không.
* C5: tôi chờ bạn mở phiên mới ở `xau-edge/`, hoặc bỏ qua.
* C6: giữ trailer, hay bỏ trailer (và sửa dòng nào).

## 6. Điều chưa kiểm

* Nguyên nhân thật của việc agent ECC không gọi được (G7).
* Chi phí token là ước tính theo số ký tự, chưa đo bằng công cụ đếm token.
* `ecc install` với đúng 9 thành phần hiện tại chưa chạy ở chế độ ghi: mới chỉ lập kế hoạch (`install-plan`) và `doctor`/`repair --dry-run`.
* Chưa đo coverage hiện tại của dự án.
