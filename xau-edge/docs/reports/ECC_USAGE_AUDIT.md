# ECC_USAGE_AUDIT: ECC đã cài và đã dùng hiệu quả cho xau-edge chưa?

> Viết cho: chủ dự án (đọc tiếng Việt, hiểu giao dịch, không rành cấu hình Claude Code).
> Ngày 2026-10-11. Chỉ đọc: không sửa mã, không cài/gỡ/cập nhật ECC, không bật hook, không đọc `.env`.
> Nhãn: **ĐÃ CÀI**, **ĐÃ DÙNG** (có dấu vết), **ĐÃ DÙNG NHƯNG KHÔNG HIỆU QUẢ**, **CHỈ TRÊN GIẤY**.
> File chủ dự án mở, `docs/26-10-11-13-32-ecc-tinh-nang.md`, là tài liệu tổng quan 718 dòng về ECC (từ repo `ECC/`): nó mô tả tính năng của ECC, KHÔNG phải bằng chứng xau-edge đã dùng chúng.

## 1. Kết luận

* **A. Đã thiết lập và cài đặt chưa? — MỘT PHẦN, ở mức "đã cài dạng file, chưa cài dạng plugin".** Cài vào `xau-edge/.claude/` ngày 2026-10-08 (profile `minimal` + 9 thành phần chọn thêm, **hook bị từ chối**, từ ECC 2.2.2 commit `c70874f`). `ecc doctor` hiện báo **ERROR**: 2 file nguồn trong install-state không còn ở upstream, và bản đã cài (2.2.2) lệch bản upstream hiện tại (2.2.3). Plugin `ecc@ecc` **không** được bật ở cấp người dùng (chỉ có `vercel@claude-plugins-official`), nên các agent ECC không gọi được như sub-agent.
* **B. Đã khai thác trong việc code và có hiệu quả chưa? — MỘT PHẦN, hiệu quả ở khâu quy trình và review, yếu ở khâu cưỡng chế.** Dấu vết cho thấy các *ý tưởng* ECC (test trước, review độc lập, Gate A/B, santa, council, ADR) được áp dụng và bắt được lỗi thật nhiều lần. Nhưng phần lớn là làm theo tinh thần bằng sub-agent đa năng và quy trình tay, **không phải chạy thành phần ECC theo tên**. Không có hook nên không có gì cưỡng chế, và các quy tắc ECC đang nạp vào ngữ cảnh bị vi phạm mà không ai chặn (mục 5).
* Điểm nghẽn thật của xau-edge là bằng chứng edge và vận hành, không phải việc thiếu ECC. ECC giúp chất lượng quy trình; nó không tạo ra edge.

## 2. Kiểm kê cài đặt — ĐÃ KIỂM (đếm trên đĩa, `ecc list-installed`, `ecc doctor`)

| Nhóm | Upstream `ECC/` (2.2.3) | Có trong `xau-edge/.claude` | Ghi chú |
|---|---|---|---|
| Agents | 71 | 68 | gần đủ, nhưng 19 file là agent ngôn ngữ không dùng (cpp, csharp, dart, go, java, kotlin, php, rust, swift, django, flutter, harmonyos) |
| Skills | 302 | 75 thư mục | 25%; có ít nhất 15 skill không liên quan (healthcare x4, hipaa, django/laravel/perl/quarkus/springboot-security, evm-token-decimals, nodejs-keccak256, defi-amm-security, dev-team, plan-canvas) |
| Commands | 95 | 94 | gần đủ |
| Rules | 122 file | 122 | common + nhiều ngôn ngữ; chỉ common + python thực sự nạp vào ngữ cảnh phiên làm việc |
| Hooks | có | **0** | `hookConsent: "declined"`; `settings.json` chỉ có `includeCoAuthoredBy: false` |
| Plugin `ecc@ecc` (cấp người dùng) | có | **không bật** | `~/.claude/settings.json` không có hook, chỉ plugin vercel |
| Install-state | — | 520 file trên đĩa / 518 ghi trong state | lệch 2 file |
| Phiên bản | 2.2.3 `4eb71d92` | 2.2.2 `c70874f` | cũ hơn một bản |

`ecc doctor --target claude-project`: `Status: ERROR` (`missing-source-files`: 2 file `.agents/skills/everything-claude-code/...` đã đổi chỗ upstream) và `warning repo-version-mismatch`.
`harness-audit.js` cho 16/39, nhưng con số này **không đáng tin**: công cụ tìm `.github/workflows/` trong `xau-edge/`, trong khi CI thực ở `AI-Harness/.github/` (một cấp trên) nên nó báo "không có CI" sai. Các mục thật sự yếu mà nó chỉ ra (Eval Coverage 0/10, Security Guardrails 3/10) chưa được kiểm chứng riêng.

## 3. Dấu vết theo vòng ECC — ĐÃ KIỂM một phần

Vòng quy định ở `docs/PROJECT_PLAN.md` (E0 research, E1 plan, Gate A, E2 test trước, E3 code, E4 review, E5 verify, Gate B, E6 commit, E7 ADR/ghi nhớ). Bằng chứng theo giai đoạn:

| Giai đoạn | Trạng thái | Bằng chứng |
|---|---|---|
| E0 research/reuse | Một phần | `search-first`, `code-explorer` được ghi trong `CONSOLIDATION_AUDIT_AND_EDGE_PATH.md` (phiên khác); sprint WORKSTATION tự khảo sát nguồn tin, không qua skill |
| E1 plan | Có | kế hoạch/prompt do người dùng đưa, kèm `PROJECT_PLAN.md`; `planner` nhắc ở 5 tài liệu |
| Gate A/B | Theo prompt của chủ dự án | mỗi sprint có câu "OK" của bạn; audit 10-08 từng kết luận chỉ là chỉ dẫn chung, không phải cổng riêng từng thay đổi |
| E2 test trước | Một phần | audit 10-08: RED quan sát được ở Sprint 1 và một đợt Sprint 2, nhưng không phải mọi đợt. Sprint WORKSTATION: nhiều test viết cùng lúc với mã, không lưu bằng chứng "thấy FAIL trước" |
| E4 review độc lập | **Có, đều đặn** | 6 commit mang chữ "independent review fixes" (TRADE-04c, 05e, 06d, 07f, 08a, 08c); sprint WORKSTATION: 1 A/B mù, 2 reviewer năm giây, 1 red team; phiên khác: Santa 2 vòng với điểm số (vòng 1 FAIL, vòng 2 PASS) |
| E5 verify | Có | ruff, mypy `--strict`, pytest, eslint, tsc, Playwright (mock + backend thật) chạy trước mỗi lần push; CI 8 job |
| E7 ADR/ghi nhớ | Có | 31 ADR (`docs/decisions/0001-0031`); bộ nhớ dùng cơ chế tự động của Claude (`MEMORY.md`), không dùng `ecc memory` |

Điều quan trọng: trong sprint WORKSTATION, **tôi không gọi skill ECC nào** (không có lần gọi `tdd-workflow`, `verification-loop`, `santa-method`, `council`, `orch-*`), và không gọi được agent ECC (danh sách loại sub-agent của phiên không có agent ECC). Các review là sub-agent đa năng đọc mã theo rubric tôi viết. Tinh thần giống ECC, nhưng không phải ECC chạy thật.
Phiên khác (consolidation, Phase 2, V3) ghi rõ đã dùng `search-first`, `code-explorer`, `refactor-cleaner`, `silent-failure-hunter`, `architect`, `council`, `intent-driven-development`, `santa-method`: đó là dấu vết dùng thật, nhưng ở khâu kiểm toán và tài liệu nhiều hơn khâu viết mã.

## 4. Hiệu quả — ĐÃ KIỂM (không có tỷ lệ tổng; chỉ ví dụ có thật)

**ECC/quy trình review bắt được lỗi thật:**
* Review hồi tố 2026-10-08: 0 CRITICAL, **1 HIGH, 12 MEDIUM**, 8 LOW mà tự review bỏ sót (F-01..F-21 trong `ECC_ALIGNMENT_AUDIT.md`).
* Santa trên báo cáo hợp nhất: vòng 1 **FAIL** (điểm 3,40 và 3,88), vòng 2 PASS sau khi sửa lỗi dữ kiện.
* Red team sprint WORKSTATION: 0 HIGH, 7 MEDIUM, 5 LOW (tin chưa được coi là "tươi" khi dấu thời gian ở tương lai, tuần feed cụt, chuyển hướng https xuống http...); đã sửa.
* Năm vòng "independent review fixes" của sprint TRADE: từ lỗi giao diện đến lỗi cho phép nút mở lệnh.

**Lỗi lọt qua dù có quy trình:**
* NEWS-01 (`e8e8fc3`) làm CI đỏ vì chưa chạy bộ test Python đầy đủ trước khi push. `verification-loop` thật sự chạy sẽ chặn việc này.
* DATA-01: khẳng định "chênh lệch giá vẫn hiện cho tới khi người quyết định" sai (health chỉ đếm sự kiện trong 1 giờ), do tự review không bắt được.
* Tài liệu lệch mã: `canonical-brain.md` (của tôi) nói "cần thêm `schema_version`" trong khi phiên khác đã làm xong; báo cáo cuối kèm số liệu cũ.
* Giao diện: test axe chế độ tối chập chờn rồi cố định thất bại sau commit hero của phiên khác; test ghi đè 36 ảnh trong thư mục `docs` được git theo dõi.
* Độ phủ test không còn được đo: audit 10-08 ghi 98%; `AI-Harness/.github/workflows/xau-edge-ci.yml` không có `--cov`, nên quy tắc ECC "tối thiểu 80%" không được cưỡng chế. **CHƯA KIỂM** con số hiện tại.

## 5. Lệch giữa lời hứa và thực tế

| Lời hứa | Thực tế |
|---|---|
| Quy tắc ECC (nạp vào ngữ cảnh): tệp nguồn tối đa 800 dòng | 4 file `src` vượt: `research/service.py` 1139, `trading/engine.py` 1049, `control/service.py` 1048, `paper_desk.py` 829; thêm `TerminalChart.tsx` 969. Không có hook hay CI chặn |
| ECC: coverage ≥ 80% | CI không đo coverage |
| `CLAUDE.md` mục 7: bỏ trailer `Co-authored-by` | 110 trên 166 commit có trailer (9 trong 24 commit từ `4d85be4`); prompt gốc của chủ dự án yêu cầu thêm, nên hai nguồn mâu thuẫn nhau |
| Hook ECC (`gateguard`, `delivery-gate`, `safety-guard`) có sẵn skill | Không bật hook nào; chủ đích ("no hooks") nên là cân nhắc, nhưng cũng là lý do nhiều quy tắc chỉ nằm trên giấy |
| `ECC_CATALOG.md` ghi 577 mục, tổng 590 trong cùng file | số liệu tự mâu thuẫn; `prompts/` ghi 293 skill, thực tế đếm 302 |
| ADR chuẩn dùng `docs/adr/` | dự án dùng `docs/decisions/` (không có chỉ mục) |

## 6. Chi phí và độ rối

* Mỗi phiên làm việc dưới `xau-edge/` liệt kê khoảng 75 skill và nạp 12+ file quy tắc ECC, trong khi ít nhất 15 skill và 19 agent là của stack khác (y tế, Laravel, Rust, Swift...). Đó là ngữ cảnh tiêu tốn mà không mang lại lợi ích.
* Ba nguồn quy tắc cùng tồn tại và đôi khi mâu thuẫn: `AGENTS.md`, `CLAUDE.md`, `.claude/rules/ecc/`. Ví dụ: trailer commit (mục 5); quy tắc "đổi guard cần ADR" của dự án thắng, còn quy tắc ECC "review mọi thay đổi" không phân biệt rủi ro.
* Tài liệu về ECC nhiều và chồng lấp (`ECC-Guide.md`, `ECC_ALIGNMENT_AUDIT.md`, `ECC_CATALOG.md`, tổng quan 13:32, 6 prompt có chữ ECC): dễ lệch nhau (mục 5).

## 7. Điểm số (0-5; mỗi điểm kèm bằng chứng ở các mục trên)

| Trục | Điểm | Lý do chính |
|---|---|---|
| Cài đặt đầy đủ | 3 | file đã cài, `doctor` ERROR, lệch phiên bản, không có plugin cấp người dùng |
| Cấu hình/cưỡng chế | 1 | không hook, không coverage trong CI, quy tắc 800 dòng không ai chặn |
| Mức sử dụng thực tế | 3 | ý tưởng ECC dùng nhiều; thành phần ECC chạy theo tên chủ yếu ở phiên kiểm toán, không ở sprint viết mã |
| Hiệu quả chất lượng mã | 3 | review bắt được lỗi thật nhiều lần; vẫn lọt CI đỏ, lỗi health 1 giờ, tài liệu lệch |
| Khớp tài liệu và thực tế | 2 | số liệu tự mâu thuẫn, mâu thuẫn trailer, tài liệu cũ |
| Chi phí/độ rối (5 = nhẹ) | 2 | thành phần không liên quan, 3 nguồn quy tắc, nhiều tài liệu chồng |

## 8. Việc đáng giữ, đáng bỏ

* **Dùng thật và đáng giữ:** review độc lập có rubric trước khi commit; Santa cho báo cáo rủi ro cao; ADR; `verification-loop` dưới dạng chạy bộ test đầy đủ; kiểm tra mù khi chọn thiết kế UI.
* **Cài mà không dùng:** hầu hết `commands/` và `agents/` (agent ECC không gọi được như sub-agent); `unified-memory`, `strategic-compact`, `context-budget`, `eval-harness`; hook.
* **Gây rối nên gỡ hoặc hợp nhất:** 15 skill và 19 agent không liên quan; quy tắc trailer mâu thuẫn.

## 9. Đề xuất (tối đa 5, theo tác động)

1. **Cưỡng chế bằng CI thay vì hook:** thêm bước đo coverage và kiểm tra số dòng tối đa mỗi file (hoặc danh sách ngoại lệ có lý do). Chi phí thấp; kiểm: CI đỏ khi vi phạm.
2. **Chạy bộ test đầy đủ trước mỗi push** bằng một script duy nhất (`scripts/dev.ps1 check`). Chi phí thấp; kiểm: không còn CI đỏ vì test cũ.
3. **Gỡ skill/agent không liên quan** khỏi `xau-edge/.claude` (cài lại bằng `ecc install` với danh sách thành phần chọn). Có rủi ro nhỏ phải thử lại; kiểm: danh sách skill của phiên ngắn lại.
4. **Cập nhật hoặc sửa install-state** (`ecc doctor` hiện ERROR) và thống nhất quy tắc trailer commit giữa `CLAUDE.md` và prompt gốc. Chi phí thấp.
5. **Quyết định dùng ECC kiểu nào:** hoặc bật plugin để gọi agent theo tên và chạy `orch-*` thật, hoặc chính thức coi ECC là bộ quy tắc/quy trình và bỏ bớt phần không dùng. Hiện đang ở giữa hai kiểu, nên vừa tốn ngữ cảnh vừa không có lợi ích của cả hai.

## 10. Điều chưa kiểm

* Không chạy lại cổng chất lượng trong lần kiểm này (đã chạy trước đó trong phiên: ruff, mypy, 2601 test Python, eslint, tsc, Playwright). Độ phủ test hiện tại chưa đo.
* Chưa đo thời gian hay chi phí ngữ cảnh thực tế của ECC mỗi phiên.
* Chưa đọc `~/.claude` cấp người dùng ngoài cấu hình plugin; chưa kiểm xem agent ECC có gọi được sau khi bật plugin hay không.
* Không có tỷ lệ "lỗi bắt trước merge / sau merge": chỉ có các ví dụ ở mục 4.
