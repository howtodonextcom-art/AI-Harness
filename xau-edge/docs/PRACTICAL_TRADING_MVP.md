# XAU EDGE TRADING DESK MVP: lộ trình thực dụng

Ngày: 2026-10-09, HEAD `195c04b`. Đây là sản phẩm của một cuộc KIỂM TOÁN + THU GỌN SẢN PHẨM. **Chưa xây gì.** Chủ dự án phải duyệt năm
tính năng ở mục 9 trước khi bắt đầu sprint. Số liệu gốc: `docs/reports/FEATURE_REALITY_AUDIT.md`; bản đồ module:
`docs/reports/MODULE_FEATURE_MAP.md`; danh mục: `docs/FEATURE_CATALOG.md`; màn hình: `docs/TRADER_SCREEN_SPEC.md`.

## 1. Chẩn đoán trong một đoạn

61 tính năng có ý nghĩa; **8 (13%) chủ dự án dùng được hôm nay** (4 dùng ngay) và **không cái nào là quyết định mua/bán dùng được**. 29 tính năng
(48%) đã chạy được ở backend nhưng không tới được người dùng. Mã Python: 33% nghiên cứu/kiểm định, 21% hạ tầng dữ liệu, 24% thực thi, chỉ 16% là
quan sát+quyết định+rủi ro, và gần hết phần 16% đó (Trading Core) chưa được nối vào đâu. Giao diện: 61% là trang nghiên cứu, 0% là màn hình giao
dịch. Dữ liệu MT5 sống hoàn hảo nhưng **tín hiệu vẫn đọc kho dữ liệu cũ** (`data/raw`, cũ 23 giờ). Sản phẩm hiện là một phòng thí nghiệm rất tốt
chưa có bàn giao dịch.

## 2. Chủ dự án dùng được GÌ hôm nay (trung thực)

| Việc | Dùng được? | Ở đâu | Thật hay mô phỏng | Giới hạn |
|---|---|---|---|---|
| Xem giá XAUUSD sống, spread, tuổi tick | CÓ | `/market` | thật (terminal FTMO DEMO) | chỉ xem |
| Xem nến M1-H4 từ 2004, tick volume, spread | CÓ | `/market` | thật | không có mức giá/chỉ báo vẽ trên biểu đồ |
| Biết dữ liệu tin được không, vì sao cũ, cách khắc phục | CÓ | `/market`, `status_market_stack.ps1` | thật | - |
| Bật/tắt cả hệ thống dữ liệu một lệnh | CÓ | `start/stop_market_stack.ps1` | thật | chưa thử đăng nhập thật |
| Xem nhãn bằng chứng (NONE) và luật rủi ro | CÓ | `/` | thật | chỉ đọc |
| Kill switch bằng dòng lệnh | CÓ | `scripts/kill_switch.py` | thật | kỹ thuật |
| Bot demo DRY-RUN | CÓ (kỹ thuật) | `scripts/demo_trader.py` | thật nhưng không gửi lệnh | chỉ ra WAIT |
| Research Console | CÓ (nâng cao) | `/research` | tệp thật | cho thấy "không có edge" |

KHÔNG dùng được: quyết định BUY/SELL (trang chủ luôn WAIT trên dữ liệu cũ), Entry/SL/TP dùng được, máy tính rủi ro, paper trade, lệnh demo thật.

## 3. Hai phát hiện quyết định hướng đi

1. **Trading Core đã chạy được trên dữ liệu sống nhưng cô lập.** Kiểm toán này nạp ledger vào Trading Core (script tạm, chỉ-đọc) và nhận được:
   `WAIT [NEWS_WINDOW, VOLATILITY_TOO_LOW]`, chuỗi `H4 RANGE | H1 BULLISH | M30 RANGE | M15 RANGE/NONE | M5 FLAT | M1 QUIET | SPREAD GOOD | VOLUME LOW`.
   Nghĩa là phần khó (trạng thái đa khung, lý do, từ chối) đã làm xong; thiếu đúng phần nối.
2. **Baseline gần như luôn WAIT.** Replay 2 tuần đã "đốt" (2025-09-01..15): 2.702 mốc -> 3 BUY, 0 SELL (0,1%), cả hai lệnh đã vào đều dính SL. Từ chối nhiều
   nhất: biến động quá thấp 636, quá cao 629, không có setup 611, xung đột khung 391, spread rộng 389. Đây là kiểm tra mô tả (Class D), KHÔNG phải
   bằng chứng edge và KHÔNG dùng để chỉnh tham số. Nhưng nó cảnh báo: nếu giữ ngưỡng hiện tại, bàn giao dịch sẽ "im lặng" gần hết thời gian.
   Chủ dự án cần quyết định tần suất mong muốn (mục 12), không phải để tôi chỉnh cho đến khi có lệnh.

## 4. Phân loại phức tạp: giữ, đóng băng, hoãn, gộp, ứng viên xóa

| Phân loại | Mục | Lý do |
|---|---|---|
| **KEEP (lõi bàn giao dịch)** | `trading/*` (market_state, baseline, levels, sizing, position_manager, governor), `market_data/ledger+mt5+collector`, `risk/engine+kill_switch`, `execution/paper+bridge+app`, `news/*`, `ops/notifier`, cổng bằng chứng `signals/evidence.py` | nằm trên đường quan sát -> quyết định -> bảo vệ -> thực thi |
| **KEEP (nền, ẩn)** | `integrity/*`, `research/*` (backend), supervisor, verify/parity/snapshot, CI | bảo vệ tính trung thực; không được chi phối trải nghiệm hằng ngày |
| **FREEZE** | Edge Program V1/V2, `research_v2`, `strategies` (H01-H06), `models/*` ML, `backtest/*`, `evaluation/*`, Research Console (9 trang), `funded/*`, `forensics/*`, trang `/research` | đã trả lời câu hỏi "có edge không" (chưa); không thêm gì cho đến khi có lý do |
| **DEFER** | `trading/arming`, API tick lịch sử, NSSM installer, tự động hóa bot không giám sát | cần sau khi có paper + thủ công |
| **CONSOLIDATE** | kho bar thô cũ `market_data/store+catalog+refresh+compact` vào ledger; hai regime; hai định cỡ lệnh; hai volume; 4 lộ trình/kế hoạch trong `docs/`; 3 hệ thống trạng thái | giảm số nguồn sự thật |
| **REMOVE-CANDIDATE (chưa xóa)** | `patterns/*`+`outcomes/*` (xác suất analogue chưa hiệu chuẩn), `signals` analogue path, H01-H06 | sau khi Trading Core thay thế đường quyết định; lưu trữ trước khi xóa |

Quy tắc: **không xóa gì trong sprint tới.** Chỉ nối (wiring), vì nối rẻ hơn viết lại.

## 5. Quyết định BUY/SELL/WAIT: kiến trúc đề xuất

Dùng đúng Trading Core hiện có; chỉ thêm đường nối. Không bỏ phiếu chỉ báo (không "EMA +1, RSI +1"); chuỗi ngữ nghĩa:

```
dữ liệu sống (ledger 6 khung, đã đóng)            [có]  market_data/ledger.py
 -> trạng thái đa khung có thứ bậc                  [có]  trading/market_state.py
 -> REGIME -> HƯỚNG -> SETUP -> TRIGGER -> CHẤT LƯỢNG VÀO LỆNH -> RỦI RO   [có]  trading/baseline.py
 -> Entry/SL/TP/RR + cỡ lot                         [có]  trading/levels.py, sizing.py
 -> TradingDecision (một đối tượng chuẩn)           [có]  trading/schema.py::TradingSignal
 -> API /trade/decision                             [THIẾU]  api/
 -> màn hình /trade                                 [THIẾU]  apps/dashboard
 -> paper / demo / bot (qua cầu nối hiện có)        [có]  trading/adapter.py -> execution/bridge.py
```

Hai khái niệm tách bạch, hiển thị cạnh nhau:

* **OPERATIONAL SIGNAL**: `BUY` + nhãn `UNVALIDATED_BASELINE` (cho phép; để vận hành, đo thực thi, thu thập forward).
* **VALIDATED EDGE**: `NONE` (Edge Program V1 = "(B) NO EDGE WITHIN BUDGET", V2 Batch A 0/20). Không bao giờ hiển thị "có lãi kỳ vọng".

Đối tượng `TradingDecision` đã có (`TradingSignal`): timestamp, symbol, decision, regime, h4/h1 bias, m30/m15/m5/m1 state, entry_type/price, SL, TP1/TP2,
risk_reward, required_win_rate, stop_model, risk_pct, position_size, spread, atr, volume_state/type, signal_expiry, reasons, refusal_reasons,
strategy_id/version, evidence_status, inputs_hash. Thiếu duy nhất: `spread_state`, `structure_state` dạng nhãn (hiện nằm trong `reasons`).
Mỗi BUY/SELL/WAIT phải giải thích bằng ngôn ngữ thường (xem SPEC mục 6).

## 6. Vai trò các khung thời gian (đối chiếu với mã hiện có)

Mã hiện có (`trading/market_state.py`, `baseline.py`) đã theo một thứ bậc: H4 regime (chỉ VETO: `BLOCKING_H4`), H1 trend (nguồn DUY NHẤT của hướng),
M30 cấu trúc, M15 cấu trúc + pullback (setup), M5 momentum (trigger), M1 vi mô (veto), spread, volume. Quy tắc quan trọng đã đúng: **khung thấp có
thể CHẶN nhưng không bao giờ đảo hướng của H1.** Chưa có bằng chứng thực nghiệm cho bất kỳ thứ bậc nào, nên đây là giả thuyết vận hành, không phải edge.

Thứ bậc đơn giản nhất đề xuất (một chỗ thay đổi so với mã: hạ M30 xuống chỉ hiển thị):

| Khung | Vai trò | Có quyền | Hiện trong mã |
|---|---|---|---|
| H4 | Chế độ thị trường | chỉ VETO (ngược xu hướng H4) | có |
| H1 | HƯỚNG chính (BUY hay SELL) | quyết định hướng | có |
| M30 | Cấu trúc | chỉ hiển thị, không veto (giảm xung đột khung) | có (đang tham gia veto) -> đổi |
| M15 | SETUP (pullback hoàn tất) | điều kiện cần | có |
| M5 | TRIGGER (xác nhận vào lệnh) | điều kiện cần | có |
| M1 | Chất lượng/timing thực thi | chỉ VETO (bất thường/im ắng) | có |

Cân nhắc đã ghi: replay 2 tuần cho thấy `TIMEFRAME_CONFLICT` 391 lần; hạ M30 xuống thông tin sẽ giảm xung đột nhưng đó là thay đổi cần chủ dự án
duyệt và phải ghi trước khi nhìn kết quả (không tinh chỉnh theo kết quả).

## 7. M1 và volume

**M1 có thể cho biết:** spread tại thời điểm vào lệnh; tick volume đột biến kèm biên độ mở rộng (`ABNORMAL`: range_expansion và z-score > 3 -> không vào);
im ắng (`QUIET`: z-score < -1 -> không vào); động lượng vi mô (thân nến mạnh); thời điểm vào lệnh trong một trigger M5.
**M1 KHÔNG cho biết một cách đáng tin:** hướng (không bao giờ đảo H1/H4), xu hướng, hay edge độc lập. Tick volume không phải volume sàn. M1 của 2004-2012 rất thưa
(broker chỉ có nến khi có tick) nên chỉ M1 hiện đại đáng tin cho thống kê.

**Volume đang được lưu thế nào:** mỗi nến có `tick_volume` (Int64, số lần giá đổi) và `real_volume` (luôn bị bỏ qua; chỉ khác 0 ở H1/H4 2012-2018, nhãn
`UNVERIFIED_LEGACY_REAL_VOLUME`, `domain/market.py`). `trading/activity.py` xác định loại volume rồi chuẩn hóa **theo chính từng khung** (không so M1=100
với M5=500):

| Đo lường | Có trong mã? | Dùng vào quyết định? | Hiện trên UI? |
|---|---|---|---|
| Tỷ lệ so với trung bình 20 nến (`volume_ratio`) | CÓ | KHÔNG (tính được, chưa dùng) | chưa |
| Percentile 100 nến (`volume_percentile`) | CÓ | KHÔNG (tính được, chưa dùng) | chưa |
| z-score 20 nến | CÓ | **CÓ, chỉ ở M1**: nhãn `VOLUME` HIGH (z >= 1) / NORMAL / LOW (z <= -1); M1 `ABNORMAL` (z > 3 + biên độ mở rộng) và `QUIET` (z < -1) | chưa |
| Gia tốc (`volume_acceleration`) | CÓ | KHÔNG | chưa |
| Volume so với biên độ nến | KHÔNG | - | - (rẻ để thêm, nhưng chưa cần) |
| Volume xác nhận breakout | một phần (chỉ M1: biên độ mở rộng + z cao = bất thường) | có, như veto | chưa |
| Phân kỳ volume | KHÔNG (không định nghĩa khách quan được) | - | **không làm** |

Nhận xét: volume hiện chỉ tham gia như một chốt chặn ở M1, chưa xác nhận setup ở M5/M15. Thêm xác nhận volume cho M5 là mở rộng quy tắc (cần chủ dự án
duyệt và ghi trước); sprint tới chỉ HIỂN THỊ các đo đã có trên `/trade`.

## 7b. Mẫu giá, vào lệnh, SL, TP

* **Mẫu giá đã có** (`trading/patterns.py`, nhân quả, không repaint, có test): thân mạnh, pin bar, engulfing, inside/outside bar, mở rộng biên độ, nén, breakout,
  breakout thất bại; cấu trúc HH/HL/LH/LL, BOS, CHoCH ở `structure/swings.py`. Dùng trong trạng thái đa khung (đường quyết định mới); **chưa hiện trên UI**.
* **Vào lệnh:** schema hỗ trợ MARKET/LIMIT/STOP; baseline chỉ dùng **MARKET** (trả nửa spread), hết hạn sau 3 nến M5; bản legacy dùng vùng vào lệnh.
  **Khuyến nghị: một chế độ duy nhất = MARKET ngay sau khi nến trigger M5 đóng** (đã là mặc định).
* **SL:** đã có mô hình HYBRID (`levels.py`): swing cấu trúc gần nhất + đệm, tối thiểu `1,25 x ATR`, tối đa `3 x ATR`. Khớp khuyến nghị "dựa cấu trúc, có sàn ATR"; không dùng SL cố định.
* **TP:** TP1 = 2R (cấu hình), TP2 = 3R, tính trên net-RR sau chi phí, tối thiểu `1,5R`, tôn trọng kháng cự gần nhất (`min_clear_atr = 1`). Tất cả cấu hình được; không tối ưu ở đây.

## 8. Rủi ro, thoát lệnh, paper, demo, cảnh báo

| Hạng mục | Hiện trạng thật | Khoảng trống nhỏ nhất |
|---|---|---|
| Máy tính rủi ro | `trading/sizing.py::size_for_risk` (equity, risk %, entry, SL, thông số hợp đồng broker) -> lot, từ chối nếu dưới lot tối thiểu. Không có API/UI. | endpoint + ô nhập; lấy equity từ `/bot/account` hoặc nhập tay |
| SL/TP broker | gửi kèm lệnh (bot demo); `paper.py` mô phỏng SL/TP/gap | - |
| Thoát theo thời gian / hết hạn tín hiệu | bot: đóng khi hết hạn (đã test); `position_manager` có time-exit | chưa nối `position_manager` |
| Hòa vốn / trailing / tín hiệu ngược | `position_manager.py`, **tắt mặc định, chưa nối** | nối vào paper trước, chủ dự án bật từng cái |
| Kill switch | DÙNG ĐƯỢC (CLI); trạng thái trên `/` | hiện trên `/trade` |
| Giới hạn lỗ ngày / sàn FTMO | bot: guard FTMO + tự flatten đã nối (chỉ chạy khi bot chạy); `governor` chưa nối | hiện ở `/trade` |
| Paper trading | có broker giả lập + `POST /paper/orders` (nhận `at`, không nhận tham số lệnh); trang chủ chỉ hiện số dư; **không có nút**; chỉ nhận Signal BUY/SELL của luồng legacy (không bao giờ có) | nút PAPER BUY/SELL từ quyết định Trading Core (adapter đã có) + lưu bền |
| Lệnh DEMO thật | `Mt5DemoExecutor` đủ, **chưa từng gửi lệnh**. Chặn bởi: (1) terminal đăng nhập bằng investor password -> `TRADING_NOT_ALLOWED`, chưa có `MT5_TRADE_PASSWORD`; (2) `ENABLE_DEMO_TRADING=false`, `DEMO_DRY_RUN=true`; (3) bắt buộc `DEMO_ALLOWED_ACCOUNTS`, `DEMO_MAGIC`, `DEMO_INITIAL_CAPITAL`; (4) cổng bằng chứng: chỉ qua override D2 cho đúng một chiến lược, nhãn UNVALIDATED; (5) tin tức không rõ | **hành động của chủ dự án** (xem mục 11) |
| Cảnh báo | Telegram + dự phòng file đã code, có chống trùng/giới hạn; chưa có bằng chứng đã cấu hình; chỉ thấy cảnh báo `NEWS_UNKNOWN` trong file | thêm sự kiện "setup sẵn sàng / vô hiệu / SL-TP chạm / spread cao" (rẻ khi đã có quyết định) |

## 9. NĂM tính năng nên xây tiếp (chỉ năm)

Chọn theo giá trị cho chủ dự án, khả năng tái dùng mã có sẵn, và rủi ro nghiên cứu thấp. Không có hạ tầng mới.

| # | Tính năng | Tái dùng | Công sức | Phụ thuộc | Rủi ro nghiên cứu | Giá trị |
|---|---|---|---|---|---|---|
| 1 | **Quyết định sống**: endpoint `GET /trade/decision` nạp ledger -> `build_market_state` -> `decide`, trả `TradingSignal` + trạng thái đa khung + trạng thái volume; chính sách tin tức rõ ràng | `trading/*`, `market_data/ledger.py`, `news/*` | trung bình-thấp | quyết định tin tức (mục 12) | thấp (không đổi quy tắc) | CAO |
| 2 | **Màn hình `/trade`** (một màn hình: quyết định, lý do, đa khung, volume, cấu trúc, bằng chứng) | `/market` (biểu đồ, viên trạng thái), schema có sẵn | trung bình | #1 | thấp | CAO |
| 3 | **Kế hoạch giao dịch + máy tính rủi ro**: Entry/SL/TP/RR/risk %/lot hiển thị và máy tính nhập equity | `levels.py`, `sizing.py` | thấp | #1 | thấp | CAO |
| 4 | **Hành động PAPER BUY/SELL** từ quyết định + theo dõi thoát lệnh (SL/TP/hết hạn, hòa vốn/trailing tùy chọn) + nhật ký | `execution/paper.py`, `trader.py`, `trading/adapter.py`, `position_manager.py` | trung bình | #1-#3 | thấp | CAO |
| 5 | **Cảnh báo setup + nhật ký ngày** (Telegram hoặc file): setup sẵn sàng, vô hiệu, SL/TP chạm, spread cao | `ops/notifier.py`, `execution/journal.py` | thấp | #1 | thấp | TRUNG BÌNH-CAO |

Lý do KHÔNG đưa vào năm cái đầu: đặt lệnh DEMO thật (chặn bởi quyền/cờ của chủ dự án, nên đứng sau paper), thêm chiến lược/ML (cấm trong giai đoạn này),
thêm dashboard nghiên cứu, thay thế kho thô cũ (CONSOLIDATE sau khi `/trade` chạy, vì tách riêng nó không giúp quyết định nào).

**Thứ tự thực hiện:** #1 -> #2 -> #3 -> #4 -> #5 (mỗi cái dùng được ngay khi xong: sau #2 bạn đã có màn hình; sau #3 đã có kế hoạch lệnh; sau #4 đã thử lệnh).

## 10. Quy trình thủ công trước (có giá trị thật dù chưa tự động)

Hệ thống đưa ra: **BUY/SELL/WAIT, Entry, SL, TP, lot, lý do, hết hạn**. Chủ dự án đọc, tự quyết, vào lệnh tay trên terminal (hoặc bấm PAPER). Khi sản phẩm cho
thêm: nhật ký (đã đề xuất #5) để xem lại. Mọi hành động có giá trị thật nằm ở chủ dự án cho đến khi có bằng chứng.

## 11. Điều kiện để bật lệnh DEMO (tách biệt với độ đúng của chiến lược)

Chỉ làm sau khi paper chạy ổn. Hành động tối thiểu của chủ dự án: (1) cung cấp `MT5_TRADE_PASSWORD` trong `.env` (không bao giờ dán vào chat); (2)
đặt `XAU_EDGE_DEMO_ALLOWED_ACCOUNTS`, `XAU_EDGE_DEMO_MAGIC`, `XAU_EDGE_DEMO_INITIAL_CAPITAL`; (3) chủ động `XAU_EDGE_ENABLE_DEMO_TRADING=true`,
`XAU_EDGE_DEMO_DRY_RUN=false`; (4) chấp nhận override D2 cho đúng `xau_mtf_baseline` (nhãn UNVALIDATED, rủi ro trần 0,25%/lệnh). Chạy `smoke_demo_order.py` một lần để xác nhận
chuỗi hoạt động.

## 12. Quyết định cần chủ dự án

1. **Chính sách tin tức:** (a) cung cấp file lịch kinh tế (`scripts/news_update.py`), hoặc (b) cho phép `allow_unknown_news` với biểu ngữ "TIN TỨC CHƯA KIỂM TRA, tự xem lịch".
   Khuyến nghị (b) cho sprint đầu, (a) sau đó. Không bao giờ bỏ qua âm thầm. **Hiện tại đây là chốt chặn số một đối với mọi BUY/SELL.**
2. **Tần suất mong muốn:** 3 BUY / 2.702 mốc là quá thưa cho một bàn giao dịch. Bạn muốn khoảng bao nhiêu setup/ngày? (Ghi trước, chưa chỉnh gì.)
3. **Duyệt năm tính năng ở mục 9** và thứ tự.
4. **Đóng băng chính thức** các mục FREEZE ở mục 4 (không phát triển, vẫn chạy test).
5. **Paper trước demo**, hay muốn chuẩn bị song song quyền giao dịch demo?

## 13. Tiêu chí chấp nhận cho sprint tới

* `GET /trade/decision` dùng dữ liệu sống: `data_as_of` cách hiện tại < 2 phút khi thị trường mở; không đọc `data/raw`.
* Nhấn làm mới 20 lần liên tiếp: cùng dữ liệu đóng -> cùng quyết định và cùng `inputs_hash` (tất định).
* WAIT luôn có ít nhất một `refusal_reason` hiển thị bằng chữ thường; BUY/SELL luôn có Entry, SL, TP, RR >= cấu hình, lot > 0, hết hạn.
* Nhãn `UNVALIDATED_BASELINE` và "Edge đã kiểm định: KHÔNG" luôn nhìn thấy cạnh quyết định; không có câu nào hàm ý lợi nhuận kỳ vọng.
* Máy tính rủi ro: kiểm chứng với ví dụ tay (equity 10.000, 0,25%, SL cách 5,00 -> rủi ro 25 USD -> đúng lot theo tick value của broker), từ chối khi dưới lot tối thiểu.
* Paper: bấm PAPER BUY ra một vị thế trong sổ paper có SL/TP/hết hạn; đóng đúng khi SL/TP chạm trên dữ liệu thật; nhật ký ghi đủ; khởi động lại API không mất vị thế.
* Không có endpoint nhận hướng/lot/SL/TP tùy ý từ client (giữ test hiện có).
* Toàn bộ cổng chất lượng xanh (ruff, mypy, pytest, playwright, CI).
