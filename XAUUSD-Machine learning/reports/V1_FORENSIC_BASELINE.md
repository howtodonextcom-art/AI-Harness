# V1 FORENSIC BASELINE (G0)

Ngày: 2026-10-12 · **V1 BASELINE HEAD: `daf22f69238efe9049e49ae562354455954a66da`** (3 file có thay đổi chưa commit từ trước khi tôi bắt đầu: `apps/dashboard/lib/action.ts`, `apps/dashboard/e2e/bias_vs_action.spec.ts`, `tests/unit/trading/test_decision_levels_sizing.py`; tôi **không sửa V1**).

Thứ tự ưu tiên nguồn khi mâu thuẫn: **mã → số đo tái lập → báo cáo hiện hành → báo cáo cũ → tài liệu kế hoạch.** Mọi con số bên dưới là số đo của tôi hôm nay (2026-10-12, buổi tối giờ VN), trừ khi ghi nguồn khác. Script tái lập: `reports/evidence/g0/`.

> **Lưu ý về phạm vi:** tin nhắn đặc tả bị cắt ở mục 119 (giới hạn 50.000 ký tự). Báo cáo này dùng các mục 0–118 nhận được.

---

## 1. Kiểm chứng độc lập các "hiện trạng V1" (mục 5 của đặc tả)

| # | Khẳng định | Kết quả | Bằng chứng |
|---|---|---|---|
| 1 | 1.204/1.204 quyết định live là WAIT trong mẫu 4 ngày | **XÁC NHẬN** | `data/trade/decisions-20261009..12.jsonl`: 1.204 dòng, 100% WAIT. Lý do hàng đầu: SPREAD_TOO_WIDE 515, VOLATILITY_TOO_LOW 359, NO_SETUP 254, NO_DIRECTION 150, TIMEFRAME_CONFLICT 86 |
| 2 | Signal starvation | **XÁC NHẬN** | Bàn PAPER: `trades: {}`, `counter: 0` (`data/trade/paper_desk.json`); `/journal` hiển thị 0 lệnh đóng; audit nội bộ: 0,10–0,28 setup/ngày |
| 3 | Hai bộ não còn trong repo | **XÁC NHẬN** | `signals/engine.py:1-14` tự ghi DEPRECATED; importer ngoài `signals/`: `api/app.py:39,175,218`, `api/service.py:28`, `control/factory.py:20`, `execution/{app,bridge,forward,order_intent,override,runner}.py`; 26 file test import nó |
| 4 | Logic cỡ lệnh trùng lặp | **XÁC NHẬN (3 hàm)** | `risk/sizing.py:15 position_size`, `trading/risk_calc.py:54 calculate`, `trading/sizing.py:57 size_for_risk`. Chênh lệch 0,25% so với 0,5% do audit nội bộ nêu: **chưa kiểm lại từng dòng** |
| 5 | Trang legacy/control tạo nợ vận hành | **XÁC NHẬN** | `/legacy`: tải 14.663 ms, dữ liệu cũ 98 giờ, heartbeat dừng 5.879 phút; `/control`: 3 phản hồi 503 mỗi lần mở (`ui_audit.json`) |
| 6 | `/legacy` cực chậm | **XÁC NHẬN** | 14,7 giây so với 3,1–3,7 giây của các trang khác (cùng đo, `networkidle` + 2,5 s) |
| 7 | Độ phủ forward dưới mục tiêu | **XÁC NHẬN** | UI: `PHỦ 76.7% / 95%`; `decision_coverage` 1.153/1.503 |
| 8 | Đĩa/log/tick cần quản lý | **XÁC NHẬN MỘT PHẦN — tôi đã nói quá ở báo cáo trước** | Ổ chứa dữ liệu thị trường (Z:) còn 81,2 GB, mức GOOD; tick 1,46 GB, tăng 0,93 MB/ngày, `estimated_days_remaining` 121.736. Cảnh báo WARN là ở **ổ C: (11,3 GB), vốn KHÔNG chứa dữ liệu thị trường** (`holds_market_data: false`). Mức độ: thấp |
| 9 | ~45k dòng Python | **XÁC NHẬN** | 44.729 dòng trong `src/xau_edge` (đo từng gói), + 218 file test (33.086 dòng) |
| 10 | ~20k dòng TypeScript | **XÁC NHẬN (có điều kiện)** | components 9.929 + lib 3.274 + app 318 = **13.521 dòng runtime**; e2e 5.070 dòng; tổng ~20,2k gồm cả test |
| 11 | Bề mặt nghiên cứu lớn ngoài runtime | **XÁC NHẬN** | Xem bảng LOC dưới đây |
| 12 | Không có edge được kiểm định | **XÁC NHẬN** | `final-verdict.md`, ledger V1/V2/V3 (0/~44 sống sót); `/research` hiển thị "Không có edge được kiểm định" |

### 1.1. Phân bố mã Python theo vai trò

| Nhóm | Gói | Dòng | Ghi chú |
|---|---|---|---|
| **Runtime sống** | trading 8.406 · market_data 5.991 · structure 1.890 · api 1.839 · news 1.073 · ops 1.062 · features 792 · domain 429 · risk 362 | **~21.844** | cộng `config`, `observability` |
| **Thực thi/điều khiển khóa + engine cũ** | execution 3.297 · control 2.903 · brokers 966 · funded 903 · signals 828 | **~8.897** | demo/funded khóa; `signals` DEPRECATED |
| **Nghiên cứu/đánh giá** | integrity 2.393 · research 2.333 · evaluation 1.660 · research_v2 1.307 · video_intel 1.175 · decision_research 980 · research_v3 833 · models 800 · strategies 751 · backtest 638 · patterns 432 · outcomes 239 · experiments 225 · forensics 222 | **~13.988** | không thuộc đường live |
| Tổng | | **44.729** | |

→ Chỉ khoảng **49%** mã Python nằm trên đường chạy sống. 20% là engine/thực thi khóa, 31% là nghiên cứu.

### 1.2. Machine Learning trong V1 (đúng như mục 4 của đặc tả)

V1 **có ML thật** (logistic, random forest, XGBoost, LightGBM; walk-forward; hiệu chỉnh Platt; 4 artefact `model.joblib` ngày 2026-10-08 với `metadata.json`) **nhưng ML không có thẩm quyền trong đường quyết định PAPER live.** Kiểm chứng: `grep` toàn `src` ngoài `models/` và `evaluation/` không có `joblib|predict_proba|sklearn|xgboost|lightgbm` nào ngoài tên hiển thị ở `research/service.py:117`; `api/service.py:249-253` chỉ đọc metadata.

---

## 2. Điều tra mới: biểu đồ chỉ hiện một đoạn lịch sử ngắn (mục 111–118)

**Kết luận: đúng, và nguyên nhân KHÔNG nằm ở thư viện biểu đồ hay ở dữ liệu. Nó nằm ở lớp frontend (cửa sổ cố định 400 nến + không có backfill) và ở hợp đồng API thiếu siêu dữ liệu.**

### 2.1. Truy vết chuỗi dữ liệu và điểm cắt

| Tầng | Thực trạng | Bằng chứng | Có phải điểm cắt? |
|---|---|---|---|
| MT5 → collector | Thu liên tục | `/md/XAUUSD/quality` | Không |
| Kho dữ liệu (Parquet) | **Rất sâu**: M1 7.065.744 nến, M5 1.500.290, M15 515.721, M30 260.769, H1 132.254, H4 34.239, tất cả **từ 2004-06-11** đến nay; tick từ 2021-09-28 | `history_depth` | Không |
| Truy vấn backend | Có tham số `before` (con trỏ lùi) và `limit` ≤ 5000: `ledger.tail(symbol, tf, limit, end=end)` | `api/market_data.py:223-241`; thử thực tế: `before=2005-01-01` trả nến 2004-12-30, `before=2010-01-01` (M1) trả nến 2009-12-31 | **Không (hỗ trợ lùi sâu tới 2004)** |
| Hợp đồng API | **Thiếu**: không có `from/to`, không trả `oldest_available`, `has_more_before`, `has_more_after`, `data_version`; `include_forming` bị bỏ khi có `before` | `market_data.py:223-263` | **Một phần** (UI không biết còn lịch sử hay không) |
| Frontend: yêu cầu | **Cố định 400 nến**: `fetchBars(tf, 400, true)`; khóa cấp 1: `fetchBars("H1", 500, true)` | `TerminalView.tsx:290`, `:190` | **ĐIỂM CẮT CHÍNH** |
| Frontend: tham số lùi | **Không bao giờ gọi `before=`**. Đo thực tế: kéo biểu đồ sang trái 25 lần → **0 request có `before=`**, chỉ 4 request `/bars` là poll định kỳ | `ui_perf.json: requestsWithBefore = 0, dragBarsRequests = 4` | **ĐIỂM CẮT CHÍNH** |
| Frontend: cập nhật | Poll mỗi 3 giây, **tải lại toàn bộ cửa sổ 400 nến (~58 KB)** và thay `bars` | `TerminalView.tsx:49,300` (`POLL_MS = 3000`) | Gây lãng phí, không phải nguyên nhân cắt |
| Biểu đồ | Cập nhật **tăng dần đúng cách** (append, giữ zoom/pan); chú thích: "a sliding 400-bar window... only appends". Khi đổi khung hoặc múi giờ thì `setData` lại toàn bộ | `TerminalChart.tsx:645-672` | Không; nhưng thiết kế giả định cửa sổ trượt |
| Cửa sổ nhìn thấy mặc định | 40–160 nến (`MIN/MAX_VISIBLE_BARS`, `TARGET_PITCH_PX = 9`) | `chartScale.ts:16-18` | Không |
| Thư viện | `lightweight-charts` 5.x có `subscribeVisibleLogicalRangeChange` (đã dùng ở `TerminalChart.tsx:553`), hỗ trợ prepend bằng `setData` | — | **Không phải nguyên nhân** |

→ Các nghi vấn trong mục 112: *hard-coded limit* (**có**, ở frontend); *pagination thiếu* (**có**, ở frontend và siêu dữ liệu); *chỉ lấy N nến mới nhất* (**có**); *state thay thế thay vì gộp* (**có**: poll thay cả mảng); *chuyển khung reset lịch sử* (**có**, vì cửa sổ cố định); *lazy backfill* (**không có**); *WebSocket ghi đè* (**không áp dụng**, V1 dùng poll, không có WebSocket); *chuẩn hóa timestamp* / *giới hạn bộ nhớ* / *autoscale* / *cache* / *resample* (**không phải nguyên nhân**: backend lùi được 22 năm).

### 2.2. Mức độ thiếu hụt (so với dữ liệu thực có)

Tính liên tục (bỏ qua nghỉ cuối tuần, nên thời gian lịch thực tế dài hơn một chút):

| Khung | 400 nến phủ ≈ | Số nến sẵn có | Phần trăm lịch sử UI cho xem | Kích thước JSON nếu tải hết (≈145 byte/nến) |
|---|---|---|---|---|
| M1 | 6,7 giờ | 7.065.744 | 0,006% | ~1,0 GB |
| M5 | 33 giờ | 1.500.290 | 0,027% | ~217 MB |
| M15 | 4,2 ngày | 515.721 | 0,078% | ~75 MB |
| M30 | 8,3 ngày | 260.769 | 0,153% | ~38 MB |
| H1 | 16,7 ngày | 132.254 | 0,302% | ~19 MB |
| H4 | 66,7 ngày | 34.239 | 1,168% | ~5 MB |

Kết luận: không được tải toàn bộ vào trình duyệt (xác nhận mục 117 của đặc tả). Cần **cửa sổ theo nhu cầu**. Chi phí phân trang thực đo trên V1: một trang 5.000 nến mất p50 **45 ms (M1), 60 ms (H1), 92 ms (H4)**, ~720 KB: đủ nhanh để backfill khi kéo.

### 2.3. Hợp đồng đề xuất cho V2 (chi tiết ở `V2_ARCHITECTURE_DECISION.md`)

`GET /market/bars?symbol&timeframe&from&to&limit&before` → `{bars, oldest_available, newest_available, has_more_before, has_more_after, data_version}` kèm sự kiện live qua WebSocket/SSE (chỉ nến đang hình thành và nến vừa đóng), **không poll toàn bộ cửa sổ**.

---

## 3. Bản đồ bộ não và luồng quyết định (rút gọn)

Một "bộ não" **sống**: `trading/market_state.py` → `trading/baseline.py` (v1.1.0 mặc định; v1.2.x opt-in) → `governor` → `paper_desk` (xem báo cáo kiểm toán mục B2–B3). Bộ não thứ hai (`signals/engine.py` + `signals/decision.py`: k-NN tương tự lịch sử và cổng bằng chứng) còn được `api/app.py` (route `/paper`) và nhánh DEMO (`execution/`) import. Hai bộ não dùng **hai schema khác nhau** (`TradingSignal` ở `trading/schema.py`, `Signal` ở `signals/schema.py`) và **hai đường cỡ lệnh**.

## 4. Kiểm kê tái sử dụng (REUSE / REWRITE / REFERENCE / DELETE)

Quy tắc của đặc tả mục 69: **không chép module chỉ vì nó đã tồn tại**. Phân loại dưới đây là *đề xuất ở G0*, được xác nhận lại ở G4 khi viết thật.

| Module V1 | Quyết định | Lý do ngắn |
|---|---|---|
| `trading/market_state.py`, `setup_machine.py`, `levels.py` | **REWRITE sạch dựa trên V1** | Logic đúng và đã qua QA nhưng gắn với snapshot nhiều khung và schema cũ; viết lại để gộp vào một bộ máy trạng thái có vòng đời 0–6 (mục 9) |
| `trading/sizing.py` (`size_for_risk`) | **REUSE LOGIC** | Đúng, đã kiểm; trở thành *hàm cỡ lệnh duy nhất* (mục 49), xóa hai hàm còn lại |
| `trading/governor.py` | **REUSE LOGIC** | Cấu hình hợp lý, độc lập chiến lược |
| `trading/paper_desk.py`, `position_manager.py` | **REWRITE** | 829 dòng, nhiều trạng thái; cần gọn và có test tính chất |
| `trading/baseline.py` | **REFERENCE ONLY** | Chuỗi quy tắc là đặc tả hành vi; V2 có Decision Governor mới (mục 40) |
| `structure/` (swings, regime, BOS/CHoCH), `features/` | **REUSE LOGIC** | Không repaint, đã test; thêm feature contract (mục 23) |
| `market_data/` (collector, ledger, validators, broker_clock) | **REUSE LOGIC có chọn lọc** | Nền tảng dữ liệu đã kiểm định; cắt phần phụ trợ |
| `news/` | **REWRITE nhỏ** | Cần nguồn lịch tin thật; hiện fail-closed |
| `risk/` (RiskEngine, prop_rules, kill_switch) | **REFERENCE ONLY** | Một phần trùng `trading/governor`; giữ ý tưởng kill switch |
| `models/` (zoo, dataset, walkforward, calibration) | **REWRITE theo mục 22** | Khung walk-forward + embargo + Platt là đúng; gắn chặt với bài toán 3 lớp hướng M15; V2 cần registry, feature contract, nhiều loại nhãn |
| `evaluation/` (edge criteria, bootstrap, periods, prop_mc) | **REUSE LOGIC** | Giá trị phương pháp lớn nhất của V1 |
| `backtest/costs.py` | **REWRITE** | Cần chi phí theo kỷ nguyên có nguồn/đơn vị/trạng thái xác minh (mục 46–47) |
| `signals/` (engine, decision, evidence) | **DELETE** (sau parity) | DEPRECATED; ý tưởng cổng bằng chứng chuyển sang Decision Governor |
| `patterns/`, `outcomes/` | **REFERENCE ONLY** | k-NN chỉ dùng trong engine cũ; chưa có bằng chứng giá trị |
| `execution/`, `brokers/`, `funded/`, `control/` | **DELETE khỏi V2** | Ngoài phạm vi PAPER (mục 50–52) |
| `integrity/`, `forensics/`, `decision_research/`, `video_intel/`, `research_v2/`, `research_v3/` | **REFERENCE ONLY** | Nghiên cứu phụ; giữ ledger K và hồ sơ giả thuyết làm dữ liệu |
| UI: logic `lib/action,honesty,lifecycle,humanState,vi` | **REWRITE sạch dựa trên V1** | Giữ hợp đồng chữ; viết lại trên mô hình 0–6 |
| UI: `TerminalChart` | **REWRITE** | Giữ lõi, thêm backfill theo cửa sổ (mục 116–118) |
| UI: research/market/control/legacy/vẽ | **DELETE** | Xem `GIA_TRI_MA_CU_VA_THIET_KE_MOT_TRANG_2026-10-12.md` |
| e2e: states, decision_contract, human_state, honesty, lifecycle, layout_stability, a11y, desktop_contract | **REUSE (hợp đồng test)** | Mục 70 |

## 5. Hiệu chỉnh và thừa nhận về các báo cáo trước của tôi

1. **Ổ C:** báo cáo kiểm toán trước liệt "Ổ C còn ~11–12 GB" là rủi ro vận hành mức Trung bình. Thực tế ổ C: **không chứa dữ liệu thị trường**; ổ dữ liệu Z: còn 81 GB và tăng rất chậm. Hạ xuống **Thấp**.
2. **Ô nhiễm dữ liệu bảo vệ:** các phép thử trên ảnh giao dịch (báo cáo `IMAGE_CLAIMS_VERIFICATION`) tôi chạy trên **toàn bộ lịch sử H1 2004–2026, gồm cả Test-H (2022-01-01..2025-04-30) và holdout (từ 2026-05)**. Theo quy tắc của chính V1 (Class D), các số đo đó là **mô tả, không phải bằng chứng**, và **các giả thuyết sinh ra từ đó (Bollinger/RSI đảo chiều) không được coi là "sạch" trên Test-H/holdout.** Chỉ dữ liệu *forward* từ nay mới sạch. Điều này được áp dụng trong `V2_ML_RESEARCH_PROTOCOL.md`: lát cắt ML của G0 cắt dữ liệu ở 2021-12-31.
3. Các số của báo cáo trước về giá trị UI không đổi.

## 6. Giới hạn của baseline này

- Một lần đo, cache nóng, Chromium headless trên cùng máy với dịch vụ; không đo cold start (cần khởi động lại stack sống), không đo FPS khi kéo (chỉ nhịp khung rảnh), không soak (để G8).
- Không đọc hết 44.729 dòng; phân loại tái sử dụng dựa trên vai trò và các module đã đọc kỹ ở báo cáo kiểm toán.
- Số dòng đo bằng `wc -l` (gồm dòng trống/chú thích); không dùng cloc.
- Chưa chạy lại bộ test của V1 đầy đủ (chỉ ~29% `tests/unit/trading` ở lần trước, không lỗi).
