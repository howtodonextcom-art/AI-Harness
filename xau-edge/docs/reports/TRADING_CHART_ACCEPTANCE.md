# Nghiệm thu biểu đồ giao dịch `/trade` (TRADING_CHART_ACCEPTANCE)

Biểu đồ dùng lightweight-charts sẵn có (không thêm thư viện), dữ liệu nến từ `/md/XAUUSD/bars` (ledger MT5 chuẩn, 6 khung M1/M5/M15/M30/H1/H4, mặc định **M5**). Không có nguồn TradingView, không `data/raw`. Mọi lớp phủ chỉ đến từ đối tượng server; frontend không tự suy ra tín hiệu.

Ảnh bên dưới là **fixture có hình dạng giống dữ liệu server** (đánh dấu rõ), trừ ảnh 09 là màn hình thật trên dữ liệu sống. Không có số dư, đăng nhập hay thông tin tài khoản trong ảnh (vốn paper giả lập 10 000).

## 1. Ảnh

| # | Nội dung | Tệp |
|---|---|---|
| 01 | WAIT: "Blocked by", Why WAIT (PASS/FAIL), Waiting for | `img/trading-chart/01-wait-desktop.png` |
| 02 | BUY (fixture): đường ENTRY/SL/TP1/TP2, marker BUY, kế hoạch + lot | `img/trading-chart/02-buy-desktop.png` |
| 03 | SELL (fixture) | `img/trading-chart/03-sell-desktop.png` |
| 04 | Lệnh paper đang mở: PAPER ENTRY/SL/TP + NOW, R và P&L, thời gian giữ | `img/trading-chart/04-open-paper-desktop.png` |
| 05 | Lệnh paper đã đóng + bật "Paper trade history": marker EXIT | `img/trading-chart/05-closed-history-desktop.png` |
| 06–07 | Di động 390×844 (WAIT, BUY) | `img/trading-chart/06-wait-mobile.png`, `07-buy-mobile.png` |
| 08 | Giao diện tối | `img/trading-chart/08-buy-dark.png` |
| 09 | **Màn hình thật** trên dữ liệu FTMO sống (WAIT, bản v1.1) | `img/trading-chart/09-live-wait-real-data.png` |

Tạo lại: `SCREENSHOTS=1 npx playwright test e2e/screenshots.spec.ts` (trong `apps/dashboard`).

## 2. Đối chiếu yêu cầu

| Yêu cầu | Cách thực hiện | Bằng chứng |
|---|---|---|
| Nến + chọn khung M1–H4, mặc định M5 | `TradeChart`, nút khung | e2e: `clicking a timeframe in the matrix switches the chart` |
| Marker BUY/SELL từ `TradingDecision` | log `signals-YYYYMMDD.jsonl` (mỗi setup một lần) → `/trade/markers` | e2e: marker snap vào đúng nến chứa thời điểm tín hiệu (`data-bar-time`) |
| Đường ENTRY / SL / TP1 / TP2 có nhãn giá | `view.decision` (giá server) + legend DOM | e2e: `line-ENTRY "ENTRY 2100.50"`, SL, TP1, TP2 |
| Lệnh paper mở: entry, giá hiện tại, SL, TP, R, P&L, thời gian | `view.desk.position` | e2e: `line-PAPER-*`, `position-r`, `position-pnl` |
| Marker EXIT + tooltip (lý do, P&L, R, thời lượng) | bản ghi desk → `/trade/markers` | e2e: `EXIT STOP_LOSS @ … · P&L -27.50 · -1.10R · 15 min` |
| Lịch sử lệnh paper (tắt mặc định) | công tắc "Paper trade history" | e2e: 1 EXIT mặc định, 2 khi bật |
| Ma trận khung chart-side TF/ROLE/STATE | dải 6 ô trên biểu đồ, bấm = đổi khung | e2e + ảnh 01–08 |
| Cấu trúc tùy chọn (hỗ trợ/kháng cự/PDH/PDL) | công tắc Structure, giá từ server | e2e: `RES 2120.00`, `PDH`, `PDL` |
| Panel tick volume + trạng thái chuẩn hóa | histogram tick volume + dòng tương đối/percentile/z, nhãn "không phải volume sàn" | e2e `volume-line` (55%, không phải volume sàn) |
| Công tắc Signals/Trade Plan/Paper Trades/Structure/Volume | `Overlays` | e2e: tắt từng lớp |
| WAIT không rải nhãn; header gọn | "Blocked by: NO_SETUP" | e2e `blocked-by` |
| Why WAIT? và "Waiting for" | `why_wait.stages` suy ra từ quyết định thật; `waiting_for` chỉ nêu điều kiện kế tiếp, kèm "không phải dự báo" | e2e + test `stages_from_signal`, `waiting_for` |
| Dữ liệu cũ vô hiệu hóa biểu đồ | biểu đồ mờ, không vẽ kế hoạch, nút khóa | e2e `a BUY on stale data…` |
| Ưu tiên bố cục: biểu đồ → quyết định → kế hoạch → vị thế → ma trận → lý do → rủi ro → chẩn đoán nâng cao | thứ tự trang; telemetry trong "Chẩn đoán nâng cao" | ảnh |
| 1440×900, 390×844, zoom 200% | e2e đo kích thước biểu đồ, hộp quyết định trong khung nhìn, không tràn ngang | e2e 3 viewport |

## 3. Lỗi thật tìm thấy khi nghiệm thu biểu đồ (đã sửa)

* Tràn ngang 2 px ở 390 px (phần tử grid thiếu `min-w-0`) — sửa, có test.
* Đường TP/SL ngoài vùng giá không nhìn thấy được vì đường giá không co giãn trục — trục nay tự mở rộng để chứa các đường kế hoạch/vị thế.
* UI đọc `initial_tp` trong khi desk ghi `tp` (TP của lệnh thật hiện "—", không có đường TP) — sửa, xem `PAPER_LIFECYCLE_ACCEPTANCE.md`.
* Mũi tên "hướng" lệch nhãn trạng thái và percentile sai thang (trước đó) — đã sửa.

## 3b. Sửa thêm sau đánh giá độc lập

Marker BUY/SELL nay nằm trên **nến M5 trigger** (trước đây là giờ quyết định, tức nến hình thành kế tiếp); biểu đồ bỏ thời gian lặp/lùi khi đổi giờ mùa hè ở múi BROKER/LOCAL thay vì lỗi; nhãn đường cấu trúc là "M15 RES/SUP"; banner AUTO_PAPER khi bật; mũi tên hướng từ nhãn thô; hiệu lực tín hiệu hiển thị không dài hơn lần đóng M5 kế tiếp.

## 4. Giới hạn

Ký hiệu trên canvas (marker, nhãn đường) là canvas nên kiểm tự động dựa vào legend/danh sách marker trong DOM (cùng dữ liệu được vẽ) thay vì pixel; ảnh chụp dùng để rà soát thị giác. Không cố đạt chức năng TradingView; không có công cụ vẽ. Thời gian hiển thị theo múi giờ chọn (mặc định UTC).
