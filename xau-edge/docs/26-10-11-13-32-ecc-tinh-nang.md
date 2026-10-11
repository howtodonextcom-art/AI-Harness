# ECC - Tổng Quan Tính Năng Và Cách Sử Dụng

Thời gian tạo: 2026-10-11 13:32  
Nguồn đọc: `Z:\Coding\Projects\AI-Harness\ECC`  
Mục đích: tài liệu nhanh để dùng ECC khi code dự án và khi cần mở rộng/tích hợp harness agent.

## 1. Tổng quan dự án

ECC là một "agent harness operating system" cho workflow lập trình bằng AI. Repo này đóng gói agent chuyên biệt, skill, slash command, hook tự động, rule theo ngôn ngữ/framework, MCP config, installer đa harness, memory vault, control plane và dashboard. Mục tiêu chính là chuẩn hóa vòng lặp:

```text
plan -> test -> implement -> review -> verify -> remember -> improve
```

Các số liệu tự mô tả trong repo:

- Version: `2.2.3`
- Package npm: `ecc-universal`
- Plugin Claude Code: `ecc@ecc`
- Agents: khoảng 71 agent
- Skills: khoảng 302 skill
- Commands: khoảng 95 command shim
- Runtime chính: Node.js >= 18
- Phần phụ: Python package `llm-abstraction`, Rust TUI `ecc2`

## 2. Công nghệ và entrypoint

| Loại | File/thư mục | Vai trò |
|---|---|---|
| npm package | `package.json` | Khai báo package `ecc-universal`, `bin`, scripts test/build/release |
| CLI chính | `scripts/ecc.js` | Router lệnh `ecc <command>` |
| Installer | `scripts/install-apply.js`, `scripts/install-guided.js`, `scripts/install-plan.js`, `scripts/setup.js` | Cài ECC vào Claude/Codex/Cursor/Gemini/OpenCode/... |
| Plugin Claude | `.claude-plugin/plugin.json` | Manifest plugin `ecc@ecc`, trỏ tới `skills/` và `commands/` |
| Plugin Codex | `.codex-plugin/plugin.json` | Manifest Codex plugin, trỏ tới `skills/`, `.mcp.json`, `hooks/codex-hooks.json` |
| Hooks | `hooks/hooks.json`, `scripts/hooks/` | Tự động chạy trước/sau tool, session start/stop, compact |
| Agents | `agents/*.md` | Subagent chuyên môn |
| Skills | `skills/*/SKILL.md` | Workflow/domain skill |
| Commands | `commands/*.md` | Slash-command compatibility layer |
| Rules | `rules/` | Quy tắc coding/security/testing theo ngôn ngữ/framework |
| MCP | `.mcp.json`, `mcp-configs/mcp-servers.json` | Cấu hình server MCP gợi ý |
| Dashboard | `ecc_dashboard.py`, `scripts/dashboard-web.js` | Dashboard/console vận hành |
| Rust TUI | `ecc2/` | TUI control plane dùng `ratatui`, SQLite, git2 |
| Python LLM layer | `src/llm/` | Abstraction provider OpenAI/Claude/Ollama/Atlas/Astraflow |

## 3. Cài đặt và bootstrap

### Tính năng

Cài ECC vào nhiều harness khác nhau, gồm Claude Code, Codex, Kimi, Cursor, Gemini, OpenCode, CodeBuddy, Qwen, Zed, Hermes, OpenClaw, Copilot CLI và các target khác.

### File liên quan

- `scripts/ecc.js`
- `scripts/setup.js`
- `scripts/install-guided.js`
- `scripts/install-apply.js`
- `scripts/install-plan.js`
- `scripts/lib/install-lifecycle.js`
- `scripts/lib/install-manifests.js`
- `manifests/install-profiles.json`
- `manifests/install-modules.json`
- `manifests/install-components.json`

### Cách sử dụng

```powershell
cd Z:\Coding\Projects\AI-Harness\ECC
node scripts/ecc.js setup
node scripts/ecc.js install --guided
node scripts/ecc.js install --guided --harness claude --harness codex --harness kimi
node scripts/ecc.js install --profile developer --target claude
node scripts/ecc.js plan --profile core --target cursor
node scripts/ecc.js list-installed --json
node scripts/ecc.js doctor --target cursor
node scripts/ecc.js repair --dry-run
node scripts/ecc.js uninstall --target antigravity --dry-run
```

Có thể gọi qua package nếu đã cài/publish:

```powershell
npx ecc-universal@2.2.3 setup
npx ecc-universal@2.2.3 install --guided
```

### Ghi chú kỹ thuật

- `ecc [args...]` không có command sẽ route về `install`.
- `--dry-run` đặt `ECC_DRY_RUN=1` để preview.
- Không nên cài chồng nhiều phương thức vào cùng một harness vì có thể trùng skills/hooks/commands.

## 4. Selective install, profiles và modules

### Tính năng

Cho phép chọn profile/module/component thay vì copy toàn bộ ECC. Phù hợp khi muốn giảm context, chỉ cài phần cần thiết cho một stack.

### File liên quan

- `scripts/profile.js`
- `scripts/catalog.js`
- `scripts/consult.js`
- `scripts/lib/context-profiles.js`
- `scripts/lib/context-selection.js`
- `scripts/lib/context-pack-registry.js`
- `manifests/*.json`

### Cách sử dụng

```powershell
node scripts/ecc.js catalog profiles
node scripts/ecc.js catalog components --family language
node scripts/ecc.js catalog show framework:nextjs
node scripts/ecc.js consult "security reviews"
node scripts/ecc.js profile show lean@1 --json
node scripts/ecc.js profile preview lean@1 --target codex --selection auto --json
node scripts/ecc.js profile explain skill:tdd-workflow --target codex
```

Installer cũng hỗ trợ:

```powershell
node scripts/install-apply.js --target codex --profile core --dry-run
node scripts/install-apply.js --target claude --modules language:typescript,workflow:tdd --dry-run
node scripts/install-apply.js --target claude --skills continuous-learning-v2
```

## 5. Agents

### Tính năng

`agents/` chứa subagent Markdown cho planning, review, build repair, security, architecture, frontend/backend/domain review và các workflow đặc thù.

### File liên quan

- `agents/*.md`
- `AGENTS.md`
- `scripts/ci/validate-agents.js`
- `tests/ci/validate-agents-tools.test.js`

### Nhóm agent chính

| Nhóm | Agent tiêu biểu | Khi dùng |
|---|---|---|
| Planning/architecture | `planner`, `architect`, `code-architect`, `spec-miner` | Lập kế hoạch, thiết kế module, phân tích brownfield |
| Review | `code-reviewer`, `security-reviewer`, `python-reviewer`, `typescript-reviewer`, `react-reviewer`, `database-reviewer` | Sau khi sửa code hoặc trước commit |
| Build resolver | `build-error-resolver`, `go-build-resolver`, `rust-build-resolver`, `react-build-resolver`, `django-build-resolver` | Khi build/test lỗi |
| Testing/E2E | `tdd-guide`, `e2e-runner`, `pr-test-analyzer` | TDD, Playwright, đánh giá test coverage |
| UI/product | `a11y-architect`, `performance-optimizer`, `seo-specialist` | UI, accessibility, performance, SEO |
| Operations | `loop-operator`, `harness-optimizer`, `chief-of-staff` | Vòng lặp tự động, tối ưu harness, giao tiếp |
| OSS/release | `opensource-forker`, `opensource-sanitizer`, `opensource-packager` | Chuẩn bị open-source release |

### Cách sử dụng

Trong harness có hỗ trợ agent, gọi theo tên agent hoặc dùng prompt định hướng. Ví dụ:

```text
Use ecc:planner to plan this refactor.
Use ecc:security-reviewer to review this auth change.
Use ecc:typescript-reviewer after implementing the dashboard changes.
```

Với Copilot CLI target, installer copy agents vào `.github/agents/` và có thể dùng theo cơ chế native của Copilot CLI.

## 6. Skills

### Tính năng

`skills/` là bề mặt workflow chính, mỗi skill là một thư mục có `SKILL.md`, đôi khi kèm `agents/`, `references/`, `scripts/`, `assets/`. Skill dùng để dạy agent cách thực hiện tác vụ chuyên môn.

### File liên quan

- `skills/*/SKILL.md`
- `scripts/ci/validate-skills.js`
- `scripts/skills-health.js`
- `scripts/skill-create-output.js`
- `docs/SKILL-DEVELOPMENT-GUIDE.md`

### Nhóm skill quan trọng

| Nhóm | Ví dụ | Công dụng |
|---|---|---|
| Core engineering | `tdd-workflow`, `verification-loop`, `security-review`, `coding-standards`, `git-workflow` | Quy trình code an toàn, test trước, verify |
| Language/framework | `python-patterns`, `python-testing`, `typescript`, `react-patterns`, `nextjs-turbopack`, `django-*`, `laravel-*`, `rust-*`, `go-*` | Pattern theo stack |
| Agent/harness | `configure-ecc`, `autonomous-agent-harness`, `agent-security-hardening`, `mcp-server-patterns` | Cấu hình và vận hành agent system |
| Research/ops | `deep-research`, `market-research`, `automation-audit-ops`, `project-flow-ops` | Nghiên cứu và vận hành |
| UI/media | `frontend-patterns`, `frontend-design-direction`, `browser-qa`, `manim-video`, `fal-ai-media` | Giao diện, QA browser, media |
| Memory/learning | `continuous-learning`, `continuous-learning-v2`, `prompt-caching-strategy`, `context-budget` | Ghi nhớ, tối ưu context |

### Cách sử dụng

Trong Claude/Codex sau khi plugin được cài:

```text
Use the tdd-workflow skill for this bug fix.
Use the security-review skill before shipping this endpoint.
Use configure-ecc to update the ECC install.
```

Cài riêng skill:

```powershell
node scripts/ecc.js install --target codex --skills continuous-learning-v2 --dry-run
```

## 7. Commands

### Tính năng

`commands/` là lớp slash-command tương thích cũ, giúp gọi nhanh workflow. Theo `AGENTS.md`, hướng dài hạn là skills-first; command vẫn tồn tại để migration/cross-harness parity.

### File liên quan

- `commands/*.md`
- `COMMANDS-QUICK-REF.md`
- `scripts/ci/validate-commands.js`
- `scripts/ci/generate-command-registry.js`

### Command tiêu biểu

| Nhóm | Commands |
|---|---|
| Lập kế hoạch | `plan`, `plan-prd`, `multi-plan`, `prp-plan`, `project-init` |
| Build/test/review | `build-fix`, `quality-gate`, `test-coverage`, `code-review`, `security-scan` |
| Language | `python-review`, `react-test`, `go-build`, `rust-review`, `kotlin-test`, `flutter-build`, `vue-review` |
| Orchestration | `orch-add-feature`, `orch-build-mvp`, `orch-fix-defect`, `multi-workflow`, `loop-start`, `loop-status` |
| Docs/memory | `update-docs`, `update-codemaps`, `save-session`, `resume-session`, `learn`, `evolve` |
| Ops | `harness-audit`, `hookify`, `sessions`, `setup-pm`, `auto-update`, `checkpoint` |

### Cách sử dụng

Trong host có slash command:

```text
/plan
/code-review
/quality-gate
/security-scan
/python-review
```

Từ CLI, dùng các script tương ứng khi có:

```powershell
node scripts/ecc.js loop-status --json
node scripts/ecc.js session-inspect claude:latest
node scripts/ecc.js work-items upsert manual-1 --source manual --title "Review API" --status open
```

## 8. Hooks và automation

### Tính năng

Hooks tự động kiểm tra lệnh shell, bảo vệ file cấu hình, gợi ý compact, ghi governance/memory, track skill, format/typecheck khi stop, session-end, desktop notify, MCP health check.

### File liên quan

- `hooks/hooks.json`
- `hooks/codex-hooks.json`
- `scripts/hooks/*.js`
- `scripts/lib/hooks-config.js`
- `scripts/lib/powershell-destructive-command.js`
- `tests/hooks/*.test.js`

### Luồng chính

| Event | Hook tiêu biểu | Công dụng |
|---|---|---|
| `PreToolUse` | `pre-bash-dispatcher.js`, `gateguard-fact-force.js`, `doc-file-warning.js`, `config-protection.js` | Chặn/cảnh báo lệnh nguy hiểm, bảo vệ config |
| `UserPromptSubmit` | `hookify-runtime.js` | Hook runtime theo prompt |
| `PreCompact` | `pre-compact.js` | Chuẩn bị trước compact |
| `SessionStart` | `session-start-bootstrap.js`, `plan-canvas-sessions.js` | Khởi tạo session |
| `PostToolUse` | `posttooluse-dispatcher.js` | Đồng bộ hậu tool |
| `PostToolUseFailure` | `mcp-health-check.js`, `skill-run-tracker.js` | Theo dõi MCP/skill lỗi |
| `Stop` | `stop-format-typecheck.js`, `session-end.js`, `cost-tracker.js`, `desktop-notify.js` | Kiểm tra và tổng kết phiên |

### Cách sử dụng

Hooks được cài qua plugin/setup, không nên copy thủ công nếu đang dùng Claude plugin:

```powershell
node scripts/ecc.js setup --mode claude-plugin --scope user --hooks standard --yes
```

Profile hook:

- `minimal`: ít can thiệp
- `standard`: mặc định
- `strict`: nhiều guard hơn

## 9. Rules

### Tính năng

`rules/` chứa guideline luôn nạp cho common và từng stack/ngôn ngữ.

### File liên quan

- `rules/common/*.md`
- `rules/typescript/*.md`
- `rules/python/*.md`
- `rules/react/*.md`
- `rules/web/*.md`
- các thư mục `rules/<language>/`

### Cách sử dụng

Cài theo target/profile hoặc copy có chọn lọc. Với Claude plugin, README khuyến cáo chỉ thêm rule pack thật sự cần:

```powershell
node scripts/ecc.js install --target claude-project --profile core --with rules --dry-run
```

Khi code dự án Python/TypeScript, nên chọn `rules/common` + đúng ngôn ngữ/framework thay vì nạp tất cả.

## 10. MCP config

### Tính năng

ECC cung cấp danh sách MCP server mẫu để tích hợp GitHub, Jira, Firecrawl, Supabase, Memory, Context7, Playwright, Vercel, Railway, Cloudflare, ClickHouse, Exa, filesystem, browser tools, v.v.

### File liên quan

- `.mcp.json`: config repo hiện tại, đang bật `chrome-devtools`
- `mcp-configs/mcp-servers.json`: catalog MCP mẫu
- `scripts/mcp-inventory.js`
- `scripts/lib/mcp-config.js`

### Cách sử dụng

Copy server cần thiết từ `mcp-configs/mcp-servers.json` sang config host, thay placeholder `YOUR_*_HERE`.

Ví dụ kiểm tra inventory:

```powershell
node scripts/mcp-inventory.js
```

Ghi chú quan trọng:

- Không bật quá nhiều MCP cùng lúc vì tốn context.
- `ECC_DISABLED_MCPS=github,context7,...` là filter trong install/sync, không phải runtime toggle live.
- Secrets/API key phải ở env/config riêng, không commit.

## 11. Memory Vault

### Tính năng

Memory Vault lưu ngữ cảnh bền vững giữa Claude, Codex, Hermes và các harness khác. Có thể lưu note, decision, handoff, lesson, runbook.

### File liên quan

- `scripts/memory.js`
- `scripts/memory-mcp.mjs`
- `scripts/lib/memory-vault.js`
- `scripts/lib/memory-vault-format.js`

### Cách sử dụng

```powershell
node scripts/ecc.js memory init --scope project
"Continue migration from API routes" | node scripts/ecc.js memory save --title "API migration note" --stdin
"State summary..." | node scripts/ecc.js memory handoff --from codex --target claude --title "Continue migration" --stdin
node scripts/ecc.js memory search "migration blockers" --target-harness hermes
node scripts/ecc.js memory read <memory-id>
node scripts/ecc.js memory doctor --scope project
ecc-memory-mcp
```

### Ghi chú kỹ thuật

- Memory do tool tạo là context chưa review, không phải policy executable.
- Write là create-only và reject các mẫu credential đã biết.
- Default recall là project + team; user scope phải yêu cầu rõ.

## 12. Plan Canvas

### Tính năng

Plan Canvas mở một phiên review plan/HTML artifact trong browser, cho phép agent chờ phản hồi người dùng.

### File liên quan

- `scripts/plan-canvas.js`
- `scripts/hooks/plan-canvas-sessions.js`
- `scripts/hooks/plan-canvas-pending.js`
- `tests/lib/plan-canvas-*.test.js`

### Cách sử dụng

```powershell
node scripts/plan-canvas.js
node scripts/plan-canvas.js open path\to\plan.md
node scripts/plan-canvas.js await path\to\plan.md
node scripts/plan-canvas.js pending
node scripts/plan-canvas.js typing path\to\plan.md --state thinking
node scripts/plan-canvas.js end path\to\plan.md
node scripts/plan-canvas.js stop
node scripts/plan-canvas.js server --port 8765 --host 127.0.0.1
```

Env:

- `ECC_PLAN_CANVAS_PORT`
- `ECC_PLAN_CANVAS_STATE_DIR`
- `ECC_PLAN_CANVAS_IDLE_MS`

## 13. Control pane, dashboard và session/status

### Tính năng

ECC có nhiều công cụ quan sát trạng thái: local control pane, dashboard web, status SQLite store, session inspect, loop-status, work-items.

### File liên quan

- `scripts/control-pane.js`
- `scripts/dashboard-web.js`
- `ecc_dashboard.py`
- `scripts/status.js`
- `scripts/sessions-cli.js`
- `scripts/session-inspect.js`
- `scripts/loop-status.js`
- `scripts/work-items.js`
- `ecc2/`

### Cách sử dụng

```powershell
node scripts/ecc.js control-pane --port 8765
node scripts/ecc.js status --json
node scripts/ecc.js status --markdown --write status.md
node scripts/ecc.js sessions
node scripts/ecc.js sessions session-active --json
node scripts/ecc.js session-inspect claude:latest
node scripts/ecc.js loop-status --json
node scripts/ecc.js dashboard:web
python ecc_dashboard.py
```

Rust TUI:

```powershell
cd ecc2
cargo run
```

## 14. Multi-harness adapters

### Tính năng

ECC có scaffold/plugin/config cho nhiều môi trường agent:

- Claude Code: `.claude-plugin/`, `.claude/`
- Codex: `.codex-plugin/`, `.codex/`, `scripts/codex/*`
- Cursor: `.cursor/`, `scaffolds/cursor/`
- Gemini: `.gemini/`
- Kimi: `.kimi/`
- OpenCode: `.opencode/`
- OpenClaw: `.openclaw/`
- Qwen: `.qwen/`
- Zed: `.zed/`
- CodeBuddy: `.codebuddy/`
- Hermes: `.hermes/`
- ADAL: `.adal/`

### Cách sử dụng

```powershell
node scripts/ecc.js install --guided --harness claude --harness codex --harness kimi
node scripts/ecc.js install --target cursor --profile core --dry-run
node scripts/ecc.js install --target opencode --profile core --dry-run
node scripts/ecc.js doctor --target kimi
```

Codex cache check:

```powershell
node scripts/codex/check-plugin-cache.js
```

Legacy Codex sync:

```powershell
bash scripts/sync-ecc-to-codex.sh
```

## 15. LLM abstraction Python package

### Tính năng

`src/llm` là package Python nhỏ để route provider LLM. `pyproject.toml` đặt tên package là `llm-abstraction`, hỗ trợ OpenAI và Anthropic, có provider thêm như Ollama/Atlas/Astraflow trong cây nguồn.

### File liên quan

- `src/llm/providers/*.py`
- `src/llm/tools/executor.py`
- `pyproject.toml`
- `tests/test_provider_tools.py`
- `tests/test_claude_provider.py`
- `tests/test_atlas_provider.py`
- `tests/test_astraflow_provider.py`

### Cách sử dụng

```powershell
python -m pytest tests/ -q
```

Script entry khai báo:

```text
llm-select = "llm.cli.selector:main"
```

Lưu ý: trong cây nguồn hiện tại không thấy `src/llm/cli/selector.py`; cần kiểm tra thêm trước khi dùng entrypoint này.

## 16. Rust ECC2 TUI

### Tính năng

`ecc2/` là control plane TUI viết bằng Rust, dùng `ratatui`, `crossterm`, `tokio`, `rusqlite`, `git2`, `clap`.

### File liên quan

- `ecc2/Cargo.toml`
- `ecc2/src/main.rs`
- `ecc2/src/tui/`
- `ecc2/src/session/`
- `ecc2/src/worktree/`
- `ecc2/src/config/`

### Cách sử dụng

```powershell
cd Z:\Coding\Projects\AI-Harness\ECC\ecc2
cargo run
cargo test
cargo build --release
```

## 17. Security và supply-chain

### Tính năng

ECC có guard cho shell command, hook/config scanning, AgentShield workflow guidance, supply-chain IOC scan, workflow security tests.

### File liên quan

- `SECURITY.md`
- `the-security-guide.md`
- `scripts/ci/scan-supply-chain-iocs.js`
- `scripts/ci/supply-chain-advisory-sources.js`
- `scripts/lib/powershell-destructive-command.js`
- `commands/security-scan.md`
- `skills/security-review/`
- `skills/agent-security-hardening/`
- `tests/ci/*security*.test.js`

### Cách sử dụng

```powershell
node scripts/ecc.js security-ioc-scan --home
npm run security:ioc-scan
npm run security:advisory-sources
```

Nếu dùng AgentShield bên ngoài:

```powershell
agentshield scan --path .
agentshield scan --path . --fix
```

## 18. Test, lint, build

### Tính năng

Repo có test JS, Python, CI validators, coverage và build OpenCode.

### File liên quan

- `tests/run-all.js`
- `tests/**/*.test.js`
- `tests/**/*.py`
- `scripts/ci/*.js`
- `eslint.config.js`
- `.markdownlint.json`

### Cách sử dụng

```powershell
npm test
npm run test:validators
npm run test:js
npm run test:python
npm run coverage
npm run lint
npm run build:opencode
```

Python:

```powershell
python -m pytest tests/ -q
```

Rust:

```powershell
cd ecc2
cargo test
```

## 19. Release và package

### Tính năng

ECC xuất bản npm package, build OpenCode plugin, kiểm tra packed artifact, release approval gate và video suite.

### File liên quan

- `package.json`
- `scripts/build-opencode.js`
- `scripts/preview-pack-smoke.js`
- `scripts/release-approval-gate.js`
- `scripts/release-video-suite.js`
- `scripts/release.sh`
- `tests/ci/packed-artifact-lifecycle.test.js`

### Cách sử dụng

```powershell
npm run preview-pack:smoke
npm run release:approval-gate
npm run release:video-suite
npm pack --dry-run
```

`prepack` tự chạy:

```powershell
npm run build:opencode
```

## 20. Cấu trúc thư mục quan trọng

| Path | Nội dung |
|---|---|
| `agents/` | Agent Markdown chuyên môn |
| `skills/` | Skill catalog canonical |
| `commands/` | Slash command compatibility layer |
| `hooks/` | Hook manifests và metadata |
| `scripts/` | CLI/runtime utilities |
| `scripts/lib/` | Library JS dùng lại cho installer, profile, memory, session |
| `rules/` | Guideline theo common/language/framework |
| `mcp-configs/` | MCP server catalog |
| `manifests/` | Install profiles/modules/components |
| `.claude-plugin/` | Claude plugin manifest |
| `.codex-plugin/` | Codex plugin manifest |
| `.opencode/` | OpenCode plugin package |
| `ecc2/` | Rust TUI/control plane |
| `src/llm/` | Python provider abstraction |
| `tests/` | JS/Python test suite |
| `docs/` | Tài liệu đa ngôn ngữ, design docs, release docs |

## 21. Luồng dùng ECC để code dự án

1. Cài hoặc kiểm tra ECC:

   ```powershell
   node scripts/ecc.js doctor --target codex
   node scripts/ecc.js list-installed --json
   ```

2. Chọn profile/context vừa đủ:

   ```powershell
   node scripts/ecc.js profile preview lean@1 --target codex --selection auto
   node scripts/ecc.js consult "python tdd security review"
   ```

3. Khi bắt đầu task, dùng planning/TDD:

   ```text
   Use planner for an implementation plan.
   Use tdd-workflow to write failing tests first.
   ```

4. Sau khi code, dùng review và verify:

   ```text
   Use code-reviewer and security-reviewer.
   Run the project test/lint/typecheck commands.
   ```

5. Ghi nhớ/handoff nếu task dài:

   ```powershell
   node scripts/ecc.js memory save --title "Decision: API route layout" --stdin
   node scripts/ecc.js memory handoff --from codex --target claude --title "Continue task" --stdin
   ```

## 22. Điểm cần lưu ý khi phát triển tiếp

- `skills/` là surface canonical; chỉ thêm `commands/` khi cần shim tương thích.
- Đừng bật tất cả MCP; README khuyến cáo giữ ít hơn khoảng 10 MCP và dưới 80 tools để tiết kiệm context.
- Không hardcode secret trong MCP config, hooks, agents hoặc installer.
- Với Claude plugin hiện đại, không thêm trường `hooks` vào `.claude-plugin/plugin.json`; repo có test để tránh duplicate hook loading.
- Dùng `--dry-run` trước các lệnh install/repair/uninstall.
- Khi sửa installer/hook, chạy ít nhất `npm run test:validators` và test liên quan trong `tests/scripts/`, `tests/hooks/`, `tests/lib/`.
- Khi sửa skill/agent/command, chạy validators tương ứng: `validate-skills`, `validate-agents`, `validate-commands` qua `npm run test:validators`.

## 23. Phần chưa chắc chắn

- Tài liệu này không chạy full test/build vì yêu cầu hiện tại là đọc mã nguồn và tạo docs.
- Một số số lượng như agent/skill/command lấy từ README/AGENTS/package metadata; số thực tế có thể thay đổi nếu catalog chưa regenerate.
- `pyproject.toml` khai báo entrypoint `llm-select = llm.cli.selector:main`, nhưng trong khảo sát nhanh chưa thấy file `src/llm/cli/selector.py`; cần kiểm tra sâu nếu định dùng Python CLI này.
- Repo có nhiều tài liệu dịch và generated/cached package files; tài liệu này tập trung vào phần dùng để code và vận hành ECC.
