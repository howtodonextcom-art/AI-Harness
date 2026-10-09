# Bản đồ module -> tính năng

Ngày: 2026-10-09, HEAD `195c04b`. Cột "Ai gọi" và "Gọi tới" được TÍNH từ các câu lệnh `import` thật của `src/xau_edge`
(không phải từ README). "Web" = có được dashboard/API phơi ra không. "Ảnh hưởng BUY/SELL/WAIT" = có nằm trên đường tạo quyết định hoặc chặn quyết định.
Số dòng là dòng mã Python (không tính test). Chú giải hành động: FREEZE = giữ nguyên, không phát triển thêm; DEFER = chưa cần; CONSOLIDATE = gộp
với bản trùng; KEEP = tiếp tục dùng.

## 1. Bảng tổng

| Module (đường dẫn) | Dòng | Là gì / vì sao có | Ai gọi (module) | Gọi tới | Web phơi ra? | Ảnh hưởng BUY/SELL/WAIT? | Đóng băng? | Xóa? | Hoãn? | Hành động |
|---|---|---|---|---|---|---|---|---|---|---|
| `src/xau_edge/trading/` | 2.228 | Trading Core: trạng thái đa khung, baseline BUY/SELL/WAIT, SL/TP, định cỡ lệnh, quản lý lệnh, governor, replay | **không module sản xuất nào** (chỉ `scripts/trading_baseline_sanity.py`) | config, domain, features, market_data, signals, structure | KHÔNG | CÓ (là bộ quyết định mới) | Không | Không | Không | **KEEP + NỐI VÀO API/UI (ưu tiên 1)** |
| `src/xau_edge/signals/` | 824 | Quyết định legacy từ analogue + cổng bằng chứng + registry chiến lược | api, control, execution, funded, trading | domain, evaluation, experiments, news, observability, outcomes, patterns, strategies, structure | CÓ (`/signals`, trang chủ) | CÓ (hiện luôn WAIT) | Một phần: giữ `evidence.py`, `schema.py`; đóng băng phần analogue | Không | Không | **CONSOLIDATE** vào Trading Core, giữ cổng bằng chứng |
| `src/xau_edge/structure/` | 351 | Swing/BOS/CHoCH không repaint + regime | models, signals, strategies, trading | domain, features | Gián tiếp | CÓ | Không | Không | Không | KEEP; hợp nhất regime (2 bản) |
| `src/xau_edge/features/` | 792 | Chỉ báo, hình học nến, phiên, volume bản cũ, feature store | evaluation, models, patterns, research_v2, strategies, structure, trading | domain, market_data, observability | `/features` | Gián tiếp (ATR, EMA) | Chỉ báo không dùng: FREEZE | Không | Không | KEEP lõi; `volume.py` CONSOLIDATE với `trading/activity.py` |
| `src/xau_edge/patterns/` + `outcomes/` | 432 + 239 | Tìm mẫu tương tự và thống kê kết cục (nuôi xác suất legacy) | api, signals, strategies, models | domain, features | `/patterns` | CÓ (xác suất legacy, chưa hiệu chuẩn) | **FREEZE** | Ứng viên xóa sau | Có | FREEZE |
| `src/xau_edge/risk/` | 343 | Risk engine, kill switch, hồ sơ prop, định cỡ cũ | api, backtest, evaluation, execution, funded | observability | `/risk/status` | CÓ (chặn lệnh) | Không | `sizing.py` trùng `trading/sizing.py` | Không | KEEP; CONSOLIDATE sizing |
| `src/xau_edge/news/` | 577 | Lịch tin kinh tế, chặn quanh tin, cập nhật hằng ngày | backtest, control, signals | execution (cho cảnh báo) | Chỉ nhãn "News unknown" | **CÓ - đang chặn mọi quyết định** (chưa có lịch) | Không | Không | Không | KEEP; chủ dự án quyết định nguồn lịch |
| `src/xau_edge/market_data/` | 5.765 | Dữ liệu: feed MT5, ledger nến/tick, collector, lịch phiên, kho thô cũ, validator | api, brokers, control, evaluation, execution, experiments, features, ops, research, strategies, trading (+34 script) | domain, observability | CÓ (`/md/*`, `/market`) | CÓ (nguồn của mọi thứ) | Phần kho thô cũ: FREEZE | Không | Không | KEEP; **CONSOLIDATE kho thô cũ `store/catalog/refresh/compact` vào ledger** |
| `src/xau_edge/execution/` | 3.261 | Bot demo: chu kỳ, cầu nối, paper, trạng thái, đối soát, guard FTMO, nhật ký | api, brokers, control, funded, news, ops | backtest, brokers, config, domain, evaluation, market_data, observability, risk, signals | CÓ (`/bot/*`, `/paper/*`, trang chủ) | CÓ (tiêu thụ quyết định) | Không | Không | Không | KEEP; đơn giản hóa phụ thuộc vào `evaluation`/`backtest` |
| `src/xau_edge/brokers/mt5_demo/` | 966 | Đường DUY NHẤT gửi lệnh (demo) | control, execution, funded | execution, market_data, observability | Qua `/control/smoke` | CÓ (thực thi) | Không | Không | Không | KEEP (đang bị khóa bởi quyền) |
| `src/xau_edge/control/` | 2.903 | Mặt phẳng điều khiển web: bật/tắt bot, chế độ, smoke, flatten, preflight | api | brokers, config, execution, experiments, funded, market_data, news, observability, ops, signals | CÓ (`/control`, cần cờ) | Gián tiếp | Không | Không | Giảm: 1.048 dòng `service.py` | KEEP; đơn giản hóa sau |
| `src/xau_edge/funded/` | 903 | Rollout, định danh, luật cho tài khoản funded | control, research | brokers, config, execution, experiments, ops, risk, signals | Không | Chặn (funded tắt) | **FREEZE** | Không | **DEFER** | FREEZE |
| `src/xau_edge/ops/` | 815 | Telegram, NTP, logging, supervisor | control, funded | execution, market_data, observability | Không | Không | Không | Không | Không | KEEP |
| `src/xau_edge/api/` | 1.501 | FastAPI: `/md`, `/signals`, `/bot`, `/paper`, `/risk`, `/research`, `/control` | (điểm vào) | control, domain, execution, experiments, market_data, models, observability, patterns, research, risk, signals, strategies | - | Gián tiếp | Không | Không | Không | KEEP; thêm `/trade/*` (ưu tiên 1) |
| `src/xau_edge/backtest/` | 638 | Backtest event-driven | evaluation, execution, research | domain, news, observability, risk | `/backtests` | Không | **FREEZE** | Không | Có | FREEZE (cần cho kiểm định sau) |
| `src/xau_edge/evaluation/` | 1.660 | Tiêu chí edge, runner, edge program, Monte Carlo prop | execution, signals | backtest, domain, experiments, features, market_data, models, risk, strategies | Không | Chỉ qua cổng bằng chứng | **FREEZE** | Không | Có | FREEZE; **gỡ phụ thuộc `signals -> evaluation`** (kéo cả backtest vào đường quyết định) |
| `src/xau_edge/strategies/` | 751 | Baseline A/B/C, giả thuyết H01-H06 | api, evaluation, models, signals | domain, features, market_data, outcomes, patterns, structure | Không | Qua F20 (Baseline C) | **FREEZE** | Ứng viên xóa H01-H06 sau khi lưu trữ | Có | FREEZE |
| `src/xau_edge/models/` | 800 | ML benchmark (logistic, forest, xgboost, lightgbm), hiệu chuẩn, walk-forward | api, evaluation | domain, features, outcomes, strategies, structure | `/models` | Không | **FREEZE** | Ứng viên xóa | Có | FREEZE (không thêm ML) |
| `src/xau_edge/integrity/` | 2.393 | Lớp toàn vẹn nghiên cứu (18 file) | research, research_v2 | research | Qua Research Console | Không | **FREEZE** | Không | Có | FREEZE (hạ tầng nền) |
| `src/xau_edge/research/` | 2.313 | Research Console backend (service 1.119 dòng) | api, integrity | backtest, funded, integrity, market_data | CÓ (`/research/*`) | Không | **FREEZE** | Không | Có | FREEZE |
| `src/xau_edge/research_v2/` | 1.307 | Edge Program V2: Batch A, event study | (chỉ scripts) | features, integrity | Không | Không | **FREEZE** | Không | Có | FREEZE |
| `src/xau_edge/experiments/` | 225 | Sổ thí nghiệm | api, control, evaluation, funded, signals | domain, market_data | `/backtests` | Qua cổng bằng chứng | Không | Không | Không | KEEP |
| `src/xau_edge/forensics/` | 222 | Điều tra đồng hồ theo năm | (chỉ scripts) | - | Không | Không | **FREEZE** | Không | Có | FREEZE |
| `src/xau_edge/domain/` | 429 | Hợp đồng dữ liệu (bar, tick, timeframe) | 13 module | - | - | Nền | Không | Không | Không | KEEP |
| `src/xau_edge/config.py`, `observability.py` | 324 | Cấu hình cờ an toàn, log che bí mật | nhiều | - | - | Nền | Không | Không | Không | KEEP |

## 2. Phụ thuộc đáng lo

1. **`trading` không có người gọi sản xuất.** 2.228 dòng quyết định mới không tới được người dùng, API hay bot.
2. **`signals` -> `evaluation` -> `backtest`/`strategies`/`models`.** Đường tạo tín hiệu kéo theo toàn bộ máy nghiên cứu (chỉ để tra cổng bằng chứng
   và lấy tham số baseline C). Làm đường quyết định khó hiểu và khó thay.
3. **`news` -> `execution`.** Module lịch tin phụ thuộc vào thực thi (để cảnh báo), đảo chiều phụ thuộc.
4. **Hai kho bar:** `market_data/store+catalog` (data/raw, nuôi signals/research/bot) và `market_data/ledger` (data/market, nuôi `/md`, `/market`).
   Hai cài đặt: regime (`structure/regime.py` và `trading/market_state.py`), volume (`features/volume.py` và `trading/activity.py`), định cỡ lệnh
   (`risk/sizing.py` và `trading/sizing.py`), ba hệ thống trạng thái (bot `status.json`, `collector_status.json`, supervisor).
5. **`control/service.py` 1.048 dòng, `research/service.py` 1.119 dòng**: hai file lớn nhất của dự án phục vụ màn hình ít dùng hằng ngày.

## 3. Dashboard (TypeScript)

| Nhóm | Dòng | Ghi chú |
|---|---|---|
| `app/research/**`, `components/research/*`, `lib/research.ts` | 3.726 (61%) | 9 trang nghiên cứu |
| Điều khiển + bot (`ControlPanel`, `BotPanel`, `lib/control.ts`) | 1.043 (17%) | `/control` cần `XAU_EDGE_WEB_CONTROL=true` |
| `/market` (`components/market/*`, `lib/market.ts`, `lib/time.ts`) | 677 (11%) | Màn hình quan sát duy nhất đang sống và đúng |
| Trang chủ legacy (`Dashboard.tsx`, `AnalogueChart`, `PriceChart`, `lib/api.ts`) | 706 (11%) | Quyết định WAIT trên dữ liệu cũ |
| **Màn hình giao dịch** | **0** | chưa tồn tại |
