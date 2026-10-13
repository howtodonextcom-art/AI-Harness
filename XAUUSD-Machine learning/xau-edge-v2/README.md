# XAU EDGE v2 (PAPER only)

Bàn quyết định XAUUSD **một trang**. Trạng thái: **G8.1 (củng cố vận hành)** + **G8 (độ tin cậy + forward evidence)** + **G7 (Paper Desk)**; ML V0 (G6) đã bị LOẠI tại Kiểm định trên **G5 (biểu đồ + giao diện quyết định)** và **G4 (lõi quyết định)**: dữ liệu chỉ-đọc + parity với V1 (G3), **lõi chuẩn** `core/` (chỉ báo, cấu trúc, trạng thái thị trường, SL/TP, một hàm cỡ lệnh, mô hình chi phí, chuỗi quyết định baseline v1.1.0, vòng đời 0..6) đã **chứng minh khớp V1 bằng golden test**, `/api/v2/state` trả quyết định thật (PAPER, UNVALIDATED). Biểu đồ nến + khối lượng, lịch sử tới hết kho, nến live, Entry/SL/TP trên biểu đồ, bảng 6 khung (G5). Sổ lệnh PAPER (mở/quản lý/đóng, bộ kiểm soát, nhật ký chỉ-thêm) trong SQLite riêng. ML V0 (dự báo biên độ) đã chạy chính thức trên Phát triển+Kiểm định, ở mức RESEARCH, **không thẩm quyền, không hiển thị dự báo**; Test-H/Holdout khóa (xem `../reports/V2_G3_DATA_PARITY_REPORT.md`, `../reports/V2_G4_CORE_PARITY_REPORT.md`, `../reports/V2_G5_CHART_UI_REPORT.md`, `../reports/V2_G7_PAPER_DESK_REPORT.md`, `../reports/V2_G6_ML_V0_REPORT.md`, `../reports/V2_G8_RELIABILITY_FORWARD_REPORT.md`, `../reports/V2_G8_1_RELIABILITY_HARDENING_REPORT.md`).

- V2 **không gửi lệnh tới broker** (sổ PAPER chỉ ghi vào `data/paper.sqlite3` của riêng nó) và không có đường gửi lệnh (ADR-V2-008). `mode` chỉ có thể là `PAPER`.
- V2 đọc kho dữ liệu của V1 **chỉ đọc** (`XAU_V2_DATA_ROOT`), không bao giờ ghi vào đó (ADR-V2-003).
- Không import mã từ V1 hay `reference-v1` (ADR-V2-006, có test).

## Chạy

```powershell
.\scripts\start.ps1            # build web nếu cần, rồi phục vụ API + WebSocket + trang tại http://127.0.0.1:8200
.\scripts\check.ps1            # ruff, mypy --strict, pytest, hợp đồng, build web, test trình duyệt
```

Cần `uv`, `node`/`npm`. Test trình duyệt dùng Playwright; nếu chưa cài trình duyệt của Playwright, đặt `XAU_V2_CHROMIUM` trỏ tới một Chromium đã có.

## Cấu hình (biến môi trường `XAU_V2_*`)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `PORT` | 8200 | cổng duy nhất của dịch vụ |
| `DATA_ROOT` | `Z:/Coding/Projects/AI-Harness/xau-edge/data/market` | kho Parquet dùng chung (chỉ đọc) |
| `LOG_DIR` | `./logs` | nhật ký JSON, xoay vòng 5 MB × 5 |
| `HEARTBEAT_SECONDS` | 5 | nhịp WebSocket |
| `LIVE_POLL_SECONDS` / `STATE_POLL_SECONDS` | 1 / 3 | nhịp socket tìm quote mới / quyết định đổi |
| `PAPER_EQUITY` | 10000 | equity khởi đầu của sổ PAPER (GIẢ ĐỊNH, ghi một lần) |
| `PAPER_DB` | `./data/paper.sqlite3` | tệp duy nhất V2 ghi (ngoài git, không sao lưu) |
| `BACKUP_KEEP` | 14 | số bản sao lưu hằng ngày của sổ PAPER (`data/backups`, cùng ổ đĩa) |
| `AUTO_PAPER` | true | tự mở lệnh PAPER khi có BUY/SELL hợp lệ (không bao giờ tới broker) |
| `ENGINE_ENABLED` / `PAPER_POLL_SECONDS` | true / 3 | vòng nền quản lý lệnh |

## Endpoint (đều chỉ đọc)

| Endpoint | Ý nghĩa |
|---|---|
| `GET /api/v2/health` | kho dữ liệu, độ mới theo lịch thị trường, quote live, đĩa, engine, mô hình |
| `GET /api/v2/state` | quyết định hiện tại: BUY/SELL/WAIT (hoặc UNAVAILABLE khi thiếu kho), lý do, chuỗi, mức 0..6, kế hoạch + rủi ro + chi phí |
| `GET /api/v2/market/bars?timeframe&limit&before` hoặc `&from&to` | lịch sử nến đã đóng, tăng dần, kèm `oldest_available`, `newest_available`, `has_more_before/after`, `data_version` |
| `GET /api/v2/forward/summary` | bằng chứng forward: độ phủ, phễu quyết định, lệnh, mua-và-giữ, mức tối thiểu của giao thức (luôn là MÔ TẢ) |
| `GET /api/v2/model` | trạng thái ML V0, khóa Test-H/Holdout, tiêu chí đạt/không đạt (không có dự báo) |
| `GET /api/v2/paper/summary`, `/positions`, `/journal` | sổ PAPER: equity, lệnh, nhật ký chỉ-thêm, bộ kiểm soát, giả định |
| `POST /api/v2/paper/open-current`, `/positions/{id}/close` | **hai thao tác ghi duy nhất** (PAPER; server tự tính; từ chối Origin lạ) |
| `GET /api/v2/market/forming` | nến đang hình thành của từng khung (từ collector) |
| `GET /api/v2/market/ticks?from&to&limit` | tick trong `[from, to)` (tối đa 20.000, `has_more`), cho mô hình chi phí |
| `GET /api/v2/market/quote` | bid/ask/spread từ tệp live của collector (FRESH / STALE / MARKET_CLOSED / UNAVAILABLE) |
| `GET /api/v2/market/symbol` | thông số hợp đồng của broker (tick size/value, bước lot…) |
| `WS /ws` | `hello`, `live` (quote + nến forming), `state` (quyết định đã đổi), `paper` (lệnh đổi), `heartbeat`; `seq` tăng 1 mỗi sự kiện |

Mọi lỗi API có dạng `{"error_code", "message"}` (không bao giờ HTML, không 503 cho tính năng thiếu).

## Parity với V1 (G3 dữ liệu, G4 lõi)

`scripts/parity/parity.py` (chạy bằng interpreter của V1): so nến, tick, lịch/đồng hồ, spec, cấu hình, quote. Xem `../reports/V2_G3_DATA_PARITY_REPORT.md`. Lõi: `scripts/parity/golden_core.py` (chạy bằng interpreter V1) sinh fixture `tests/golden/*.json`; pytest chạy fixture **không cần V1**.

## Hợp đồng

`docs/openapi.json` là nguồn sự thật (sinh bằng `scripts/export_openapi.py`); kiểu TypeScript sinh từ đó (`npm run types`). Một test thất bại nếu hợp đồng lệch mã.

## Cấu trúc

```
src/xau_edge_v2/   core/ (indicators, structure, frames, market_state, risk, costs, decision: thuần NumPy) · domain/{contract,market}.py (hợp đồng + đồng hồ/lịch, thuần) · data/ (bar_store, tick_store, live_feed, store_status, broker_profile: đọc chỉ-đọc) · api/ (REST, WS, tĩnh) · config · observability
apps/web/          Vite + React + TypeScript (một trang) · e2e/ (Playwright + axe)
docs/adr/          ADR-V2-001..015 · docs/openapi.json
tests/             unit · api · contract
```

## ML V0 (offline)

```powershell
uv run python -m xau_edge_v2.ml.run_v0        # lần chạy chính thức Phát triển + Kiểm định (không đọc Test-H/Holdout)
uv run python scripts/ml_register.py          # ghi registry RESEARCH + artifact từ kết quả chạy
uv run python scripts/ml_ledger_init.py       # đăng ký họ K cho băm đặc tả hiện hành (một lần)
```

`lightgbm` và `scikit-learn` nằm trong nhóm `ml` (mặc định của `uv sync`). Test-H/Holdout chỉ mở bằng `ml.guard.issue_unlock` với tệp duyệt của chủ dự án (xem `docs/adr/ADR-V2-007`, `ADR-V2-013`).

## Độ tin cậy và forward evidence

```powershell
uv run python scripts/soak.py --minutes 15 --out soak.json   # soak chỉ-đọc trên dịch vụ đang chạy
```

Giao thức bằng chứng forward: `docs/forward/FORWARD_EVIDENCE_PROTOCOL.md`. Sổ PAPER: `data/paper.sqlite3` (+ `data/backups/`, cùng ổ; sao lưu ra ổ khác là việc của chủ dự án).

## Vận hành, tự chạy, sao lưu, cảnh báo

`docs/ops/RUNBOOK.md`: hai tác vụ Task Scheduler (`scripts/service/install_autostart.ps1`), sao lưu có kiểm chứng + khôi phục (`scripts/restore_backup.py`), cảnh báo Telegram chỉ vận hành (`.env.example`, `scripts/telegram_find_chat.py`, `scripts/telegram_test.py`), watchdog ngoài (`scripts/external_watchdog.py`).
