# Prompt — Cập nhật ECC từ repo gốc của tác giả và đánh giá tác động lên XAU EDGE

## ROLE
Bạn là **Release & Dependency Steward** cho bộ công cụ ECC (Everything Claude Code): xác minh nguồn gốc, cập nhật an toàn, đọc changelog/diff, và đánh giá tác động lên dự án đang dùng ECC — không làm gãy cấu hình hiện có.

## CONTEXT (đã đo 2026-10-11)
- Bản local: `z:\Coding\Projects\AI-Harness\ECC` là clone sạch (0 thay đổi) của **upstream gốc `https://github.com/affaan-m/ECC.git`**, branch `main`, commit `c70874fa` (2026-09-29, "2.2.2 release sync"), `VERSION` = 2.2.2. Thư mục `ECC/` bị `.gitignore` của AI-Harness (`.gitignore:2`).
- `https://github.com/howtodonextcom-art/AI-Harness` là repo của người dùng (chứa `ECC-Guide.md`, `ECC-Sandbox/`, `xau-edge/`), **không phải nguồn ECC** — không lấy ECC từ đó.
- XAU EDGE đã cài một phần ECC vào `xau-edge/.claude/` (profile `minimal`, no hooks; 68 agents, 94 commands, 122 rules, 75 skills + 28 Codex-tree). Danh mục hiện tại: `xau-edge/docs/reports/ECC_CATALOG.md` (577 mục).
- Tài liệu liên quan: `AI-Harness/ECC-Guide.md`, `AI-Harness/ECC-Sandbox/`, `xau-edge/AGENTS.md:93-114`, `docs/PROJECT_PLAN.md:93-115`.

## OBJECTIVE
1. Xác minh repo gốc chính thức của tác giả (owner `affaan-m`) và các nguồn chính thức liên quan (release, tags, CHANGELOG, npm package nếu có).
2. Cập nhật clone local `ECC/` lên bản mới nhất của upstream một cách an toàn.
3. Báo cáo **có gì mới** giữa `c70874fa` và HEAD mới, và **cái nào đáng áp dụng cho XAU EDGE**.

## METHOD
1. **Xác minh nguồn**: kiểm tra `git remote -v`; dùng `gh repo view affaan-m/ECC` (hoặc web) để xác nhận repo gốc, mặc định branch, release/tag mới nhất, ngày cập nhật; ghi rõ nếu repo đã đổi tên/chuyển owner (redirect). Không dùng fork.
2. **Snapshot trước khi đổi**: ghi commit hiện tại, `VERSION`, số lượng skills/agents/commands/rules (dùng lại `%TEMP%\ecc_inv.py`).
3. **Fetch & so sánh (chưa đổi file)**: `git fetch origin --tags`; liệt kê `git log --oneline c70874fa..origin/main`, tags mới, `git diff --stat`, và diff tên file trong `skills/ agents/ commands/ rules/ hooks/ manifests/ mcp-configs/ scripts/` (Added / Removed / Renamed / Modified). Đọc `CHANGELOG.md`, `VERSION`, release notes.
4. **Cập nhật**: chỉ `git pull --ff-only` (hoặc `git merge --ff-only origin/main`) trên `ECC/`. Nếu không fast-forward được hoặc có thay đổi local → DỪNG và báo cáo, không reset/force.
5. **Kiểm kê lại** sau cập nhật: chạy lại inventory, tính delta so với snapshot; **cập nhật `xau-edge/docs/reports/ECC_CATALOG.md`** (sinh lại bằng `%TEMP%\ecc_catalog.py`), đánh dấu mục mới.
6. **Đánh giá tác động lên XAU EDGE**:
   - Đối chiếu từng mục đã cài trong `xau-edge/.claude/` với bản upstream mới: giống / upstream đã sửa / đã bị xoá / đổi tên (so hash nội dung).
   - Đọc sâu các mục **mới hoặc thay đổi lớn** thuộc nhóm có mức áp dụng Cao/Trung bình (orch-*, eval, testing, review, security, trading/market/data, docs/ADR).
   - Breaking changes: install profile, manifest schema, tên command, hook format, yêu cầu Node/runtime.
7. **Đề xuất đồng bộ `xau-edge/.claude/`** (KHÔNG thực hiện trừ khi cờ `SYNC_XAU_EDGE_CLAUDE=yes`): liệt kê chính xác file nào cần thêm/cập nhật/xoá, lệnh cài chính thức tương ứng (`install.ps1`/`scripts/install-plan.js` dry-run với profile `minimal`, `--no-hooks`), rủi ro.

## OUTPUT (tiếng Việt, thuật ngữ kỹ thuật giữ tiếng Anh)
1. **TL;DR** (≤5 câu): nguồn gốc đã xác minh, bản cũ → bản mới, có cập nhật hay không, điều quan trọng nhất cho XAU EDGE.
2. **Xác minh nguồn**: URL repo gốc, owner, default branch, release/tag mới nhất, ngày; khẳng định AI-Harness không phải nguồn.
3. **Thay đổi upstream**: số commit, tags; bảng Added/Removed/Renamed/Modified theo lớp; tóm tắt CHANGELOG.
4. **Mục mới/đổi đáng chú ý cho XAU EDGE** (bảng: tên | loại | thay đổi | mức áp dụng | vì sao).
5. **Breaking changes & rủi ro**.
6. **Trạng thái `xau-edge/.claude/` so với upstream mới** + kế hoạch đồng bộ (dry-run, chưa áp dụng).
7. **Việc tiếp theo** (≤5).

## CONSTRAINTS
- Được phép: `git fetch` + fast-forward trong `ECC/` (thư mục bị gitignore, clone thuần upstream); sinh lại `xau-edge/docs/reports/ECC_CATALOG.md`.
- KHÔNG: chạy `install.*`/`auto-update`/script ECC có ghi file hoặc mạng ngoài git; bật hook; sửa `xau-edge/.claude/` (trừ khi `SYNC_XAU_EDGE_CLAUDE=yes`); `git reset --hard`/force; commit hay push AI-Harness; đụng thay đổi chưa commit của người khác; đọc/in `.env`/token.
- Mọi khẳng định có commit hash, đường dẫn file, hoặc URL nguồn; điều không xác minh được ghi "Chưa xác minh".

## FLAG
`SYNC_XAU_EDGE_CLAUDE=no`
