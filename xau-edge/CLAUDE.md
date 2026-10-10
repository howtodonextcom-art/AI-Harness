# xau-edge: hướng dẫn cho agent và hiện trạng đã kiểm chứng

> Cập nhật 2026-10-10 từ mã nguồn (HEAD `e7aeddb` + NEWS-01) và quan sát trực tiếp trên dashboard
> live bằng trình duyệt. Không chép từ markdown cũ. Sơ đồ chi tiết: `docs/diagrams/end-to-end-flow.md`.
> Ảnh bằng chứng: `docs/reports/img/audit-2026-10-10/`.

## 1. Hệ thống này là gì (một đoạn)

Một bàn giao dịch **PAPER** cho XAUUSD chạy trên dữ liệu thật của terminal MT5 **FTMO-Demo** (chỉ
đọc), cộng một nền tảng nghiên cứu edge có đăng ký trước, cộng một bot demo legacy có thể gửi lệnh
MT5 nhưng đang khóa và không chạy. **Chưa có edge được kiểm định**: chiến lược đang chạy là
`xau_mtf_baseline v1.1.0`, nhãn `UNVALIDATED_OPERATIONAL_BASELINE` (`src/xau_edge/trading/engine.py:63-67`).
Không có đường nào từ quyết định trên `/trade` tới lệnh MT5.

## 2. Quy tắc bắt buộc cho agent

1. **Gate trước khi báo xong**: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`,
   `uv run pytest -m "not mt5"` (hoặc `.\scripts\dev.ps1 check`). **Luôn có `-m "not mt5"`**: test
   marker `mt5` kết nối terminal FTMO thật.
2. **Không chạm stack live** (Task Scheduler "XAU-EDGE Market Stack" → `scripts/run_market_stack.py`):
   không restart, không build vào `apps/dashboard/.next` (dashboard đang `next start` từ đó). Cần build
   thì build ở bản sao tạm. Cần thử API thì chạy một instance phụ ở cổng khác với thư mục trade tạm.
3. **Không gửi lệnh**: không chạy `scripts/smoke_demo_order.py`, không bật `XAU_EDGE_ENABLE_DEMO_TRADING`,
   `XAU_EDGE_ENABLE_FUNDED_TRADING`, `XAU_EDGE_DEMO_DRY_RUN=false`, không nhập mật khẩu.
4. **Không đọc hay in `.env`**, token, mật khẩu, số tài khoản đầy đủ (tối đa 3 số cuối).
5. **Không gỡ hoặc nới** evidence gate, risk gate, news guard, kill switch, reconcile, guard FTMO.
   Đổi phạm vi phải có ADR (`docs/decisions/`).
6. **Trên dashboard live không bấm** nút mở/đóng lệnh paper (ghi vào journal thật) và mọi nút trong
   `/control`. Modal xác nhận chỉ mở rồi Hủy.
7. **Commit**: author và committer `howtodonext.com <howtodonext.com@gmail.com>` đặt bằng biến môi
   trường `GIT_AUTHOR_*` / `GIT_COMMITTER_*` cho từng lệnh (không `git config --global`); xóa trailer
   `Co-authored-by` mà môi trường tự chèn; chỉ push lên `main` khi được yêu cầu.
8. Đừng sửa thay đổi chưa commit của người khác (ví dụ TRADE-08 trong `apps/dashboard/**`).

## 3. Tiến trình đang chạy

| Tiến trình | Entry point | Ghi chú |
|---|---|---|
| Supervisor | `scripts/run_market_stack.py` → `ops/supervisor.py` | Khởi động lại child chết; PID/heartbeat `data/run/`, log `data/logs/` |
| Collector | `scripts/run_market_collector.py` → `market_data/collector.py` | Ghi `data/market` (bar ledger M1..H4, tick store, `live.json`, `collector_status.json`) |
| API 127.0.0.1:8000 | `scripts/serve_api.py` | Chứa luôn TradeEngine (thread `EngineRunner`, 5 giây, `api/trade.py:41, 120-141`) |
| Dashboard 127.0.0.1:3000 | `next start` (`apps/dashboard`) | Trang: `/trade`, `/market`, `/journal`, `/research`, `/control` (menu "System"), `/legacy` (ẩn khỏi menu) |
| Bot demo legacy | `scripts/demo_trader.py` | **Không chạy** (heartbeat stale ~46 giờ lúc kiểm) |

## 4. Trạng thái từng tầng

| Tầng | Mức | Bằng chứng |
|---|---|---|
| Dữ liệu MT5 (`data/market`) | **Thật**, chạy liên tục, `health=GOOD` | `/md/status` 2026-10-10 11:13 UTC; `market_data/collector.py` |
| Trading Core (`trading/*`) | **Thật trên dữ liệu live, quyết định PAPER** | `trading/engine.py`, `trading/decision_core.py`, `trading/baseline.py` |
| Paper desk | **Paper**: vốn giả lập $10.000, 0 lệnh | `trading/paper_desk.py`; tab Hệ thống `/trade` |
| Lịch tin cho Trading Core | **Đã nối (NEWS-01)**, chưa có file lịch (`data/news/` trống) | `scripts/serve_api.py:76-80`, `tests/unit/api/test_trade_news_wiring.py` |
| Research (Edge Program V1/V2) | **Thật**, kết luận âm | `docs/research/edge-program/final-verdict.md`, `docs/research/edge-program-v2/STATE.json` |
| Bot demo legacy + executor | **Chỉ test bằng fake**, khóa, không chạy | `scripts/demo_trader.py:102, 382`; `brokers/mt5_demo/executor.py:347-348` (call site duy nhất của `order_send`) |
| Control plane `/control/*` | **Code có, không mount** (cần `XAU_EDGE_WEB_CONTROL=true`) | `config.py:69`, `scripts/serve_api.py:67-75`, ADR-0023 |
| Funded FTMO | **Khóa** | `config.py:51-65`, `funded/*`, ADR-0020 |
| Kho nghiên cứu `data/raw` | **Đứng yên** từ 2026-10-08 13:15 UTC | trang `/legacy` |

Quy mô: `trading` 31 file / 6,7k dòng; `market_data` 39 / 5,0k; `execution` 17 / 2,9k; `control`
11 / 2,5k; 160 file test, 2566 test (`-m "not mt5"`).

## 5. Edge: kết luận hiện hành

* Edge Program V1: **(B) NO EDGE WITHIN BUDGET**, K = 21/21, ngân sách giả thuyết 6/6 đã dùng hết
  (`docs/research/edge-program/final-verdict.md`, `ledger.md`).
* Edge Program V2: Batch A **0/20** qua Stage 1; K đã dùng 20/48 (`docs/research/edge-program-v2/STATE.json`).
* Baseline v1.2.0 / v1.2.1: cài nhưng không chạy; v1.2.0 bị loại bởi chính dải tần suất đăng ký trước
  (`api/trade.py:95-98`, tab Hệ thống).
* Tiêu chí 7 điểm và Bonferroni `0.05/K` giữ nguyên (`docs/evals/edge-criteria.md`).
* Live: 249/249 quyết định là WAIT từ 2026-10-09 12:53 UTC; 0 setup, forward acceptance **F0**.

## 6. Blocker và rủi ro hiện hành (đã kiểm lại 2026-10-10)

| # | Vấn đề | Mức | Bằng chứng | Hướng xử lý |
|---|---|---|---|---|
| 1 | Không có edge; mọi tiền thật đều là đánh cược kỳ vọng âm hoặc không biết | Blocker | mục 5 | Chỉ nghiên cứu theo protocol; không nới tiêu chí |
| 2 | Hai engine, hai kho dữ liệu: executor MT5 chỉ nối `signals.engine` trên `data/raw` cũ, không nối Trading Core | Blocker (cấu trúc) | `scripts/demo_trader.py:102, 382`; `trading/engine.py:1-11` | Gộp theo `docs/trading/LEGACY_DEMO_BOT_MIGRATION.md`, chạy shadow trước |
| 3 | Chưa có nguồn lịch tin; `/trade` báo UNKNOWN và baseline chỉ cảnh báo (`allow_unknown_news=True`) | Major | `api/trade.py`, `data/news/` trống | Chủ dự án cấp nguồn, chạy `scripts/news_update.py`, restart API |
| 4 | **Ổ C: còn ~4,5 GiB** (dưới ngưỡng critical 5 GB của chính hệ thống); terminal MT5 và Windows nằm trên C: | Major (vận hành) | `Get-PSDrive C`; test `test_status_good_then_stale_when_quote_dies` FAIL vì đo đĩa thật | Dọn ổ C:; sửa test cho hermetic |
| 5 | Telemetry thiếu ~một nửa nến M1 khi thị trường mở (234 bản ghi / ~480 phút ngày 09/10) | Major (bằng chứng forward) | `data/trade/decisions-20261009.jsonl` | Điều tra API restart / step bỏ nến; cảnh báo uptime engine |
| 6 | Trading Core coi `MarketStatus.UNKNOWN` là mở | Minor cho paper, Blocker nếu nối executor | `trading/live_source.py:90-91` | Fail-closed trước khi gộp engine |
| 7 | `data_age_seconds` đóng băng khi thị trường đóng ("dữ liệu: 13.4 giờ" cạnh "14.4 giờ trước") | Minor | `trading/engine.py:248-250` | Tính lại tuổi lúc serve |
| 8 | Biểu đồ không tự fit khi đổi kích thước cửa sổ (nến dồn 1/4 phải sau khi phóng to) | Minor (UI) | ảnh `14-trade-1920-spread-popover.png`; `TerminalChart.tsx:470-474` chỉ fit khi đổi timeframe | Fit lại khi container đổi kích thước nếu người dùng chưa zoom |
| 9 | `/control` khi không mount: ô Preflight quay mãi "Đang chạy preflight…", poll 503 liên tục | Minor (UI) | ảnh `09-control-full.png`, console 503 | Hiện trạng thái "control tắt", dừng poll |
| 10 | `POST /trade/paper/*` không có ADR riêng, không token (chỉ Host/Origin/header) | Minor (chỉ paper) | `api/trade.py:303-317` | ADR cho Trading Core |
| 11 | Luật FTMO `must_verify` chưa xác minh; mật khẩu demo từng lộ; chưa có `MT5_TRADE_PASSWORD`; Telegram chưa cấu hình | Blocker cho demo/funded (việc chủ dự án) | `configs/prop/ftmo_funded.yaml`; khóa demo trên tab Hệ thống | `docs/operations/go-live-checklist.md` |
| 12 | eslint fail trong thay đổi TRADE-08 chưa commit; e2e dashboard không chạy trong CI | Minor | `TerminalView.tsx`, `lib/action.ts`; `.github/workflows/xau-edge-ci.yml` | Sửa khi TRADE-08 hoàn tất |

Đã xử lý trong code (bảng a1..h3 cũ): sửa giá vào lệnh theo phía bid/ask và làm tròn SL/TP (ADR-0022),
reconnect và phân loại lỗi, lock theo PID, `check_account` mỗi chu kỳ, đầu ngày theo 00:00 Prague,
nhận diện tài khoản bằng whitelist + server, auto-flatten 1% (ADR-0020), notifier Telegram, NSSM
installer, lịch tin PIT. Hash commit trong bản cũ đã đổi sau khi viết lại lịch sử git: tra bằng
`git log --oneline --grep <từ khóa>`.

## 7. Bản đồ module

| Thư mục `src/xau_edge/` | Vai trò |
|---|---|
| `market_data/` | Collector MT5, ledger, tick store, broker clock, lịch thị trường |
| `trading/` | Trading Core: market state, decision core, baseline, setup machine, paper desk, telemetry, cockpit |
| `api/` | FastAPI: `/md/*`, `/trade/*`, `/research/*`, `/lifecycle/*`, `/bot/*`, legacy `/market`, `/signals`, `/paper/*`, `/control/*` (tùy chọn) |
| `news/` | Lịch tin point-in-time (`pit.py`), guard cửa sổ tin (`calendar.py`), provider, job cập nhật |
| `signals/`, `execution/`, `brokers/mt5_demo/` | Đường bot demo legacy: tín hiệu, bridge, guard, state SQLite, executor |
| `funded/`, `control/` | Funded FTMO (khóa) và control plane web (ADR-0023) |
| `research/`, `research_v2/`, `evaluation/`, `integrity/` | Edge program, sổ K, evidence class, console nghiên cứu |
| `features/`, `structure/`, `patterns/`, `outcomes/`, `models/`, `backtest/`, `strategies/` | Thư viện nghiên cứu |
| `ops/` | Supervisor, notifier, process lock, settings vận hành |

## 8. Việc tiếp theo hợp lý

1. Dọn ổ C: và làm test collector không phụ thuộc đĩa thật.
2. Chủ dự án cấp nguồn lịch tin → `news_update.py` → restart riêng API (dừng tiến trình `serve_api.py`,
   supervisor tự bật lại) để NEWS-01 có hiệu lực.
3. Điều tra telemetry thiếu nến và thêm cảnh báo uptime engine.
4. Gộp engine (Trading Core → executor mỏng) ở chế độ shadow, fail-closed với UNKNOWN; deprecate
   `demo_trader.py` và `data/raw`.
5. Sửa các lỗi UI nhỏ (fit biểu đồ khi resize, `/control` khi tắt, tuổi dữ liệu) sau khi TRADE-08 xong.
