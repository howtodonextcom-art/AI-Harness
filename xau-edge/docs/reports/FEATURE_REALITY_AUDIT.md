# Kiểm toán thực tế tính năng XAU EDGE

Ngày: 2026-10-09. HEAD: `195c04b610654871d93b254cb7464d9cb7c6394c`. Chế độ: KIỂM TOÁN, không xây thêm gì.
Mọi nhận định bên dưới dựa trên mã nguồn hiện tại, các lần chạy thật ghi trong tài liệu, và ba phép thử chỉ-đọc của kiểm toán này
(gọi `/signals`, đọc trang chủ bằng trình duyệt, chạy Trading Core trên dữ liệu sống bằng script tạm).

## 0. Trả lời thẳng

**Mở XAU EDGE ngay bây giờ, bạn làm được gì như một trader?** Bạn **nhìn** được thị trường (giá sống, nến 6 khung từ 2004, tick volume,
spread) và biết dữ liệu có đáng tin không (`/market`). Bạn **không** nhận được quyết định mua/bán dùng được: trang chủ hiện WAIT dựa trên dữ liệu
cũ 23 giờ, và Trading Core (bộ quyết định mới, minh bạch) chạy được nhưng chưa nối vào đâu. Không có Entry/SL/TP dùng được, không có máy tính
rủi ro, không bấm được paper trade, và chưa từng có lệnh demo nào được gửi.

**Năm mảnh nhỏ nhất còn thiếu để dùng được hằng ngày:** (1) nối Trading Core vào dữ liệu sống qua một endpoint, (2) một màn hình `/trade`,
(3) trade plan + máy tính rủi ro, (4) nút PAPER BUY/SELL kèm theo dõi thoát lệnh, (5) cảnh báo "setup sẵn sàng". Chi tiết ở `docs/PRACTICAL_TRADING_MVP.md`.

## 1. Số liệu tổng

| Chỉ số | Số lượng | Tỷ lệ |
|---|---|---|
| Tổng số tính năng có ý nghĩa | 61 | 100% |
| Chủ dự án dùng được HÔM NAY (USABLE_NOW + USABLE_BUT_TECHNICAL) | 8 | 13% |
| ...trong đó dùng ngay không cần kỹ thuật (USABLE_NOW) | 4 | 7% |
| Chỉ là hạ tầng (INFRASTRUCTURE_ONLY) | 10 | 16% |
| Chỉ phục vụ nghiên cứu (RESEARCH_ONLY) | 9 | 15% |
| Chưa hoàn chỉnh (PARTIALLY_WIRED + BACKEND_ONLY + BLOCKED + FRONTEND_ONLY) | 29 | 48% |
| Trùng lặp (DUPLICATED) | 4 | 7% |
| Không có giá trị người dùng rõ ràng hiện tại | 17 | 28% |

Cách đếm: chỉ tính tính năng có ý nghĩa (không tính hàm phụ). Hạ tầng không được tính là tính năng người dùng. "Chưa hoàn chỉnh" gồm backend chưa có
đường tới người dùng.

**Phân bố trạng thái**

| Trạng thái | Số | Tỷ lệ |
|---|---|---|
| USABLE_NOW | 4 | 7% |
| USABLE_BUT_TECHNICAL | 4 | 7% |
| BACKEND_ONLY | 16 | 26% |
| RESEARCH_ONLY | 9 | 15% |
| INFRASTRUCTURE_ONLY | 10 | 16% |
| PARTIALLY_WIRED | 10 | 16% |
| BLOCKED | 3 | 5% |
| DUPLICATED | 4 | 7% |
| NOT_USEFUL_CURRENTLY | 1 | 2% |

**Phân bố theo giá trị người dùng**

| Lớp | Số tính năng | Tỷ lệ | Dùng được hôm nay |
|---|---|---|---|
| A Quan sát thị trường | 12 | 20% | 3 |
| B Quyết định giao dịch | 7 | 11% | 1 |
| C Quản lý rủi ro | 9 | 15% | 1 |
| D Thực thi | 8 | 13% | 1 |
| E Nghiên cứu / kiểm định | 12 | 20% | 1 |
| F Vận hành / hạ tầng | 11 | 18% | 1 |
| G Sản phẩm / UX | 2 | 3% | 0 |

## 2. Công sức đã đổ vào đâu (đo bằng dòng mã, không phải ý kiến)

Mã nguồn Python: **32,970 dòng** ở 218 file, 141 file test. Dashboard TypeScript: **6,152 dòng**.

| Nhóm | Dòng | Tỷ lệ |
|---|---|---|
| Nghiên cứu / kiểm định (E) | 10,980 | 33.3% |
| Vận hành / hạ tầng (F): dữ liệu, giám sát, miền chung | 7,009 | 21.3% |
| Thực thi (D): bot, điều khiển web, broker, funded | 8,033 | 24.4% |
| Quyết định + quan sát + rủi ro (A/B/C): signals, features, structure, trading, risk, news | 5,115 | 15.5% |
| API | 1,501 | 4.6% |
| Khác (config, observability) | 332 | 1.0% |

Dashboard: nghiên cứu 3,726 dòng (61%), điều khiển/bot 1,043 (17%),
thị trường (`/market`) 677 (11%), trang chủ legacy 706 (11%).
**Không có dòng nào cho màn hình giao dịch.**

Chẩn đoán: hạ tầng + nghiên cứu chiếm khoảng 55% mã Python; phần quan sát + quyết định + rủi ro (A/B/C) chỉ khoảng 16%, và gần như toàn bộ
phần đó (Trading Core, 2.228 dòng) KHÔNG đến được người dùng. Phía giao diện, 61% là trang nghiên cứu và 0% là màn hình giao dịch.

## 3. Bảng "DÙNG ĐƯỢC NGAY HÔM NAY?" (bản đầy đủ nhất)

| Tính năng | Dùng ngay? | Ở đâu | Làm được gì | Giới hạn |
|---|---|---|---|---|
| Giá XAUUSD sống (bid/ask/spread/tuổi tick) | CÓ | /market | Số liệu thật từ terminal FTMO, làm mới 1 s | Chỉ xem; không có quyết định |
| Biểu đồ nến M1/M5/M15/M30/H1/H4 + tick volume + spread | CÓ | /market | Nến thật 2004→nay, nến đang hình thành được đánh dấu | Không có chỉ báo, không vẽ mức giá |
| Tick volume | CÓ (dạng thô) | /market (panel dưới biểu đồ) | Số lần giá đổi mỗi nến | KHÔNG chuẩn hóa (tỷ lệ/percentile chưa hiện); không phải volume sàn |
| Độ tươi dữ liệu + trạng thái MT5/collector/API | CÓ | /market (6 viên), status_market_stack.ps1 | Nói rõ vì sao UI cũ và cách khắc phục | Chỉ là sức khỏe hệ thống |
| Quyết định BUY/SELL/WAIT (legacy) | KHÔNG HỮU ÍCH | / | Trang chủ hiện WAIT + lý do | Luôn WAIT (cổng bằng chứng đóng, tin tức không rõ) và đọc dữ liệu CŨ 23 giờ (data/raw), không phải feed sống |
| Quyết định BUY/SELL/WAIT (Trading Core) | KHÔNG | chưa có | Chạy được qua script tạm trên dữ liệu sống | Không có endpoint, không có màn hình |
| Entry/SL/TP/RR | KHÔNG | chỉ khi legacy có 'lean' (hiện SELL, EV 0,26R, dữ liệu cũ) | Có mức giá nhưng WAIT | Không dùng được để vào lệnh |
| Máy tính rủi ro / cỡ lot | KHÔNG | chưa có | Backend có sẵn (trading/sizing.py) | Không có API, không có UI |
| Paper trading | KHÔNG BẤM ĐƯỢC | / (chỉ hiện số dư paper) | API POST /paper/orders tồn tại | Cần tín hiệu BUY/SELL (không bao giờ xảy ra) và không có nút |
| Bot demo DRY-RUN | CÓ (kỹ thuật) | python scripts/demo_trader.py; xem trên / | Chạy cả đường quyết định, không gửi lệnh | Chỉ ra WAIT; heartbeat hiện cũ 22 giờ (chưa chạy lại) |
| Gửi lệnh DEMO thật | KHÔNG (bị chặn) | /control (cần WEB_CONTROL=true) | Chưa từng gửi lệnh nào | Cần MT5_TRADE_PASSWORD + cờ + whitelist; đăng nhập hiện là investor password |
| Kill switch | CÓ (dòng lệnh) | scripts/kill_switch.py; trạng thái trên / | Dừng mọi giao dịch | Trạng thái 'unknown' vì bot chưa tạo state |
| Research Console (9 trang) | CÓ (nâng cao) | /research | Sổ giả thuyết, bằng chứng, K, lineage | Cho thấy 'không có edge'; không giúp quyết định mua/bán |
| Cảnh báo Telegram | CHƯA RÕ | docs/operations/telegram-alerts.md | Đã cài code; cảnh báo chỉ ghi file | Chưa có bằng chứng đã cấu hình token; không có cảnh báo 'setup sẵn sàng' |
| Khởi động/dừng hệ thống dữ liệu | CÓ | start/stop/status_market_stack.ps1 | Một lệnh dựng MT5+collector+API+dashboard | Chưa thử đăng nhập thật |

## 4. Hai thế giới dữ liệu không nối nhau (phát hiện quan trọng nhất)

* **Thế giới mới (đúng, sống):** terminal FTMO -> collector -> `data/market` (nến 6 khung từ 2004 + 205 triệu tick) -> `/md/*` -> `/market`.
* **Thế giới cũ (chết):** `scripts/fetch_history.py`/`refresh` -> `data/raw` (làm mới lần cuối 2026-10-08 20:15) -> `/signals`, `/features`, `/regime`,
  `/patterns`, trang chủ, bot demo, nghiên cứu.
* **Trading Core** (2.228 dòng, TC-01..07) đọc `MultiTfBars` và chưa được import ở đâu ngoài một script replay. Nó chạy tốt trên dữ liệu sống
  (đã thử), nhưng không có đường nào từ nó tới người dùng, API hay bot.

Hệ quả: mọi đầu tư vào dữ liệu MT5 sống (hạ tầng F) chưa làm cho quyết định (B) tốt hơn. Đây là khoảng trống lớn nhất của sản phẩm.

## 5. Các chốt chặn đang ép mọi quyết định thành WAIT

1. **Cổng bằng chứng** (`signals/evidence.py`): không chiến lược nào VALIDATED -> bản legacy luôn WAIT. Đúng và nên giữ; Trading Core dùng nhãn
   `UNVALIDATED_BASELINE` riêng để vẫn cho ra tín hiệu vận hành.
2. **Tin tức không rõ:** chưa có file lịch (`XAU_EDGE_NEWS_CALENDAR_PATH` trống) -> cả hai đường đều từ chối (`NEWS_UNKNOWN` / `NEWS_WINDOW`).
   Đã thấy cả trên dữ liệu sống hôm nay. Đây là chốt chặn rẻ nhất để gỡ nhưng cần chủ dự án quyết định.
3. **Baseline quá chọn lọc:** replay 2 tuần (burned dev, 2025-09-01..15): 2.702 mốc quyết định -> **3 BUY, 0 SELL, 2.699 WAIT** (0,1%); hai lệnh
   ra đều dính SL. Từ chối nhiều nhất: biến động quá thấp (636), quá cao (629), không có setup (611), xung đột khung (391), spread rộng (389).
   Đây là kiểm tra Class D (không phải bằng chứng edge, không được dùng để chỉnh tham số), nhưng nó cho biết sản phẩm sẽ gần như luôn WAIT.
4. **Terminal đăng nhập bằng investor password:** mọi lệnh bị `TRADING_NOT_ALLOWED`. Chưa có `MT5_TRADE_PASSWORD`.
5. **Cờ demo:** `ENABLE_DEMO_TRADING=false`, `DEMO_DRY_RUN=true`, `WEB_CONTROL=false` theo mặc định.

## 6. Chi tiết từng tính năng

### F01 - Báo giá sống bid/ask/spread/tuổi tick

* **Lớp:** A Quan sát thị trường  |  **Trạng thái:** `USABLE_NOW`  |  **Dùng được hôm nay:** CÓ
* **Mục đích / vấn đề giải quyết:** Thấy giá XAUUSD hiện tại và tick còn tươi không
* **Backend:** src/xau_edge/market_data/mt5/feed.py, api/market_data.py  |  **Frontend:** apps/dashboard/components/market/MarketView.tsx
* **API:** GET /md/XAUUSD/quote  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** terminal FTMO (collector -> live.json)
* **Bằng chứng test:** tests/unit/market_data, tests/unit/api/test_api_market_status.py
* **Bằng chứng chạy thật:** chạy thật 2026-10-09 (tuổi tick < 2 s)
* **Cách dùng hôm nay:** Mở http://127.0.0.1:3000/market
* **Giá trị cho quyết định giao dịch:** HIGH  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F02 - Biểu đồ nến 6 khung + tick volume + spread (nến đang hình thành được đánh dấu, chọn múi giờ)

* **Lớp:** A Quan sát thị trường  |  **Trạng thái:** `USABLE_NOW`  |  **Dùng được hôm nay:** CÓ
* **Mục đích / vấn đề giải quyết:** Nhìn thị trường theo M1..H4 với dữ liệu FTMO thật
* **Backend:** api/market_data.py, market_data/ledger.py  |  **Frontend:** components/market/MarketChart.tsx
* **API:** GET /md/XAUUSD/bars  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** bar ledger (data/market)
* **Bằng chứng test:** apps/dashboard/e2e/market.spec.ts, tests/unit/api
* **Bằng chứng chạy thật:** chạy thật; 312 nến khớp terminal
* **Cách dùng hôm nay:** Trang /market, nút M1..H4
* **Giá trị cho quyết định giao dịch:** HIGH  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F03 - Viên trạng thái thành phần + độ mới từng khung + chỉ dẫn khắc phục

* **Lớp:** A Quan sát thị trường  |  **Trạng thái:** `USABLE_NOW`  |  **Dùng được hôm nay:** CÓ
* **Mục đích / vấn đề giải quyết:** Biết dữ liệu có đáng tin không và vì sao cũ
* **Backend:** api/market_data.py, market_data/freshness.py  |  **Frontend:** components/market/MarketView.tsx
* **API:** GET /md/status, /md/XAUUSD/matrix  |  **CLI/script:** scripts/status_market_stack.ps1
* **Dữ liệu phụ thuộc:** collector_status.json, ledger
* **Bằng chứng test:** tests/unit/market_data/test_freshness_disk_verify.py
* **Bằng chứng chạy thật:** chạy thật
* **Cách dùng hôm nay:** Trang /market (6 viên) hoặc status_market_stack.ps1
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F04 - API tick lịch sử có giới hạn (60 phút, 5.000 hàng)

* **Lớp:** A Quan sát thị trường  |  **Trạng thái:** `BACKEND_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Truy vấn tick đã lưu để đo thực thi
* **Backend:** api/market_data.py, market_data/tick_ledger.py  |  **Frontend:** -
* **API:** GET /md/XAUUSD/ticks/history  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** tick ledger (205 triệu tick)
* **Bằng chứng test:** tests/unit/api/test_api_market_status.py
* **Bằng chứng chạy thật:** chạy qua test, chưa có UI
* **Cách dùng hôm nay:** Gọi bằng curl
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **DEFER**

### F05 - Phân loại chế độ thị trường (regime) - bản legacy M15 và bản Trading Core H4

* **Lớp:** A Quan sát thị trường  |  **Trạng thái:** `PARTIALLY_WIRED`  |  **Dùng được hôm nay:** MỘT PHẦN
* **Mục đích / vấn đề giải quyết:** Biết đang trend/range/biến động
* **Backend:** structure/regime.py; trading/market_state.py  |  **Frontend:** Dashboard.tsx (chỉ bản legacy)
* **API:** GET /regime/XAUUSD  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** data/raw (legacy, cũ 23 h); ledger (Trading Core)
* **Bằng chứng test:** tests/unit/structure, tests/unit/trading
* **Bằng chứng chạy thật:** legacy: dữ liệu cũ; Trading Core: chạy thật qua script tạm 2026-10-09
* **Cách dùng hôm nay:** Trang chủ / (dữ liệu cũ)
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **CONSOLIDATE**

### F06 - Cấu trúc thị trường không repaint (swing, BOS, CHoCH, hỗ trợ/kháng cự)

* **Lớp:** A Quan sát thị trường  |  **Trạng thái:** `BACKEND_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Xác định cấu trúc để đặt SL/TP và né kháng cự
* **Backend:** structure/swings.py  |  **Frontend:** chỉ gián tiếp (mức hỗ trợ/kháng cự trên trang chủ)
* **API:** GET /regime  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** bars
* **Bằng chứng test:** tests/unit/structure
* **Bằng chứng chạy thật:** chạy trong cả hai đường quyết định
* **Cách dùng hôm nay:** Không có màn hình riêng
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **KEEP**

### F07 - Thư viện chỉ báo (SMA, EMA, RSI, ATR, ADX, MACD, Stochastic, Bollinger)

* **Lớp:** A Quan sát thị trường  |  **Trạng thái:** `BACKEND_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Tính chỉ báo chuẩn
* **Backend:** features/indicators.py  |  **Frontend:** -
* **API:** GET /features/XAUUSD  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** bars
* **Bằng chứng test:** tests/unit/features (so khớp golden)
* **Bằng chứng chạy thật:** chỉ ATR/EMA đi vào quyết định; còn lại không dùng
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **FREEZE**

### F08 - Nhận diện mẫu giá khách quan (thân nến mạnh, pin bar, engulfing, inside/outside, mở rộng biên độ, nén, breakout, breakout thất bại)

* **Lớp:** A Quan sát thị trường  |  **Trạng thái:** `BACKEND_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Cho ra các sự kiện giá có định nghĩa chính xác
* **Backend:** trading/patterns.py (+ features/candles.py)  |  **Frontend:** -
* **API:** -  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** bars
* **Bằng chứng test:** tests/unit/trading/test_activity_patterns_frames.py
* **Bằng chứng chạy thật:** chạy trong replay; không có UI
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **KEEP**

### F09 - Hoạt động tick volume chuẩn hóa theo từng khung (tỷ lệ, percentile, z-score, gia tốc)

* **Lớp:** A Quan sát thị trường  |  **Trạng thái:** `BACKEND_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Biết thị trường đang sôi động hay im ắng so với chính nó
* **Backend:** trading/activity.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** tick_volume trong bars
* **Bằng chứng test:** tests/unit/trading
* **Bằng chứng chạy thật:** chạy trong trạng thái M1/M5; không có UI
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **KEEP**

### F10 - Đặc trưng tick volume bản cũ (z-score, thay đổi)

* **Lớp:** A Quan sát thị trường  |  **Trạng thái:** `DUPLICATED`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Trùng với F09
* **Backend:** features/volume.py  |  **Frontend:** -
* **API:** GET /features  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** bars
* **Bằng chứng test:** tests/unit/features
* **Bằng chứng chạy thật:** dùng trong dataset mô hình
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **CONSOLIDATE**

### F11 - Nhãn phiên (Á/Âu/Mỹ) và đặc trưng thời gian

* **Lớp:** A Quan sát thị trường  |  **Trạng thái:** `BACKEND_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Biết đang ở phiên nào
* **Backend:** features/sessions.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** timestamps
* **Bằng chứng test:** tests/unit/features
* **Bằng chứng chạy thật:** dùng trong nghiên cứu
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **KEEP**

### F12 - Trạng thái đa khung thời gian có thứ bậc (H4 chế độ -> H1 hướng -> M30 cấu trúc -> M15 setup -> M5 kích hoạt -> M1 vi mô + spread + volume)

* **Lớp:** A Quan sát thị trường  |  **Trạng thái:** `BACKEND_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Một bức tranh thống nhất của thị trường
* **Backend:** trading/market_state.py, trading/frames.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** ledger 6 khung
* **Bằng chứng test:** tests/unit/trading
* **Bằng chứng chạy thật:** CHẠY THẬT trên dữ liệu sống 2026-10-09 (script tạm): H4 RANGE, H1 BULLISH, M30 RANGE, M5 FLAT, M1 QUIET, volume LOW
* **Cách dùng hôm nay:** Chưa có cách dùng: không có endpoint/UI
* **Giá trị cho quyết định giao dịch:** HIGH  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **KEEP**

### F13 - Lịch tin kinh tế + chặn tin (news guard)

* **Lớp:** C Quản lý rủi ro  |  **Trạng thái:** `BLOCKED`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Không giao dịch quanh tin mạnh
* **Backend:** news/calendar.py, news/pit.py, news/update.py  |  **Frontend:** chỉ hiển thị 'News unknown'
* **API:** (trong /signals)  |  **CLI/script:** scripts/news_update.py
* **Dữ liệu phụ thuộc:** data/news/calendar.csv (CHƯA CÓ)
* **Bằng chứng test:** tests/unit/news
* **Bằng chứng chạy thật:** chạy thật: mọi quyết định bị chặn NEWS_UNKNOWN / NEWS_WINDOW
* **Cách dùng hôm nay:** Cần cung cấp file lịch (chủ dự án)
* **Giá trị cho quyết định giao dịch:** HIGH  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F20 - Quyết định legacy BUY/SELL/WAIT từ analogue lịch sử (M15) + trang chủ

* **Lớp:** B Quyết định giao dịch  |  **Trạng thái:** `PARTIALLY_WIRED`  |  **Dùng được hôm nay:** MỘT PHẦN
* **Mục đích / vấn đề giải quyết:** Cho một quyết định kèm lý do
* **Backend:** signals/engine.py, signals/decision.py, signals/explain.py  |  **Frontend:** components/Dashboard.tsx
* **API:** GET /signals/XAUUSD  |  **CLI/script:** scripts/current_signal.py
* **Dữ liệu phụ thuộc:** data/raw (làm mới lần cuối 2026-10-08 20:15, KHÔNG nối với ledger MT5 mới)
* **Bằng chứng test:** tests/unit/signals
* **Bằng chứng chạy thật:** chạy thật: WAIT (NO_VALIDATED_EDGE, HTF_BIAS_CONFLICT, NEWS_UNKNOWN), dữ liệu cũ 23 h
* **Cách dùng hôm nay:** Trang chủ / - nhưng luôn WAIT và dữ liệu cũ
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **CONSOLIDATE**

### F21 - Xác suất từ analogue (tìm mẫu tương tự + thống kê kết cục)

* **Lớp:** B Quyết định giao dịch  |  **Trạng thái:** `PARTIALLY_WIRED`  |  **Dùng được hôm nay:** MỘT PHẦN
* **Mục đích / vấn đề giải quyết:** Ước lượng tần suất kết cục lịch sử
* **Backend:** patterns/*, outcomes/*  |  **Frontend:** Dashboard.tsx
* **API:** GET /patterns/XAUUSD  |  **CLI/script:** scripts/run_analogue_study.py
* **Dữ liệu phụ thuộc:** data/raw
* **Bằng chứng test:** tests/unit/patterns, tests/statistical
* **Bằng chứng chạy thật:** chạy thật nhưng 'chưa hiệu chuẩn'
* **Cách dùng hôm nay:** Trang chủ
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **FREEZE**

### F22 - Cổng bằng chứng + sổ chiến lược (VALIDATED / NONE)

* **Lớp:** B Quyết định giao dịch  |  **Trạng thái:** `USABLE_NOW`  |  **Dùng được hôm nay:** CÓ
* **Mục đích / vấn đề giải quyết:** Không bao giờ hiện một quy tắc chưa kiểm định như có edge
* **Backend:** signals/evidence.py, signals/strategy_registry.py  |  **Frontend:** Dashboard.tsx (nhãn Evidence: NONE)
* **API:** trong /signals  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** experiments/runs
* **Bằng chứng test:** tests/unit/signals
* **Bằng chứng chạy thật:** chạy thật: NONE
* **Cách dùng hôm nay:** Xem nhãn Evidence
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** HIGH  |  **Khuyến nghị:** **KEEP**

### F23 - Baseline vận hành Trading Core: chuỗi REGIME->HƯỚNG->SETUP->ENTRY->PAYOFF->RỦI RO, lý do + từ chối

* **Lớp:** B Quyết định giao dịch  |  **Trạng thái:** `BACKEND_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Cho BUY/SELL/WAIT minh bạch, nhãn UNVALIDATED_BASELINE
* **Backend:** trading/baseline.py, trading/schema.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** scripts/trading_baseline_sanity.py (replay)
* **Dữ liệu phụ thuộc:** ledger / data/raw
* **Bằng chứng test:** tests/unit/trading
* **Bằng chứng chạy thật:** CHẠY THẬT: WAIT [NEWS_WINDOW, VOLATILITY_TOO_LOW]; replay 2 tuần: 3 BUY / 2.699 WAIT trên 2.702 mốc
* **Cách dùng hôm nay:** Chưa dùng được: không có endpoint/UI
* **Giá trị cho quyết định giao dịch:** HIGH  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **KEEP**

### F24 - Động cơ SL/TP (SL lai cấu trúc + ATR, TP theo net-RR, tối thiểu 1,5R)

* **Lớp:** B Quyết định giao dịch  |  **Trạng thái:** `BACKEND_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Cho Entry/SL/TP/RR có lý do
* **Backend:** trading/levels.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** bars
* **Bằng chứng test:** tests/unit/trading/test_decision_levels_sizing.py
* **Bằng chứng chạy thật:** chạy trong replay
* **Cách dùng hôm nay:** Không có UI
* **Giá trị cho quyết định giao dịch:** HIGH  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **KEEP**

### F25 - Vùng vào lệnh/SL ATR/TP/EV sau chi phí bản legacy

* **Lớp:** B Quyết định giao dịch  |  **Trạng thái:** `PARTIALLY_WIRED`  |  **Dùng được hôm nay:** MỘT PHẦN
* **Mục đích / vấn đề giải quyết:** Mức giá cho quyết định legacy
* **Backend:** signals/decision.py, signals/expected_value.py  |  **Frontend:** Dashboard.tsx
* **API:** trong /signals  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** data/raw
* **Bằng chứng test:** tests/unit/signals
* **Bằng chứng chạy thật:** hiển thị khi có 'lean' (hiện: SELL, EV 0,26R), dữ liệu cũ
* **Cách dùng hôm nay:** Trang chủ
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **CONSOLIDATE**

### F26 - Bộ chuyển Trading Core -> Signal legacy (để bot dùng)

* **Lớp:** B Quyết định giao dịch  |  **Trạng thái:** `BACKEND_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Cho phép bot tiêu thụ quyết định mới
* **Backend:** trading/adapter.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** -
* **Bằng chứng test:** tests/unit/trading
* **Bằng chứng chạy thật:** chỉ test
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F27 - Chiến lược baseline A/B/C và giả thuyết H01-H10

* **Lớp:** E Nghiên cứu / kiểm định  |  **Trạng thái:** `RESEARCH_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Thử có edge hay không
* **Backend:** strategies/*, research_v2/events.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** scripts/run_edge_program.py, run_batch_a.py
* **Dữ liệu phụ thuộc:** data/raw
* **Bằng chứng test:** tests/unit/strategies, tests/unit/research_v2
* **Bằng chứng chạy thật:** kết luận: không có edge (V1 = B; V2 Batch A 0/20)
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** HIGH  |  **Khuyến nghị:** **FREEZE**

### F28 - Benchmark mô hình ML (logistic, forest, xgboost, lightgbm; walk-forward; hiệu chuẩn)

* **Lớp:** E Nghiên cứu / kiểm định  |  **Trạng thái:** `RESEARCH_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Kiểm tra ML có hơn baseline không
* **Backend:** models/*, evaluation/model_runner.py  |  **Frontend:** -
* **API:** GET /models  |  **CLI/script:** scripts/run_models.py
* **Dữ liệu phụ thuộc:** data/raw
* **Bằng chứng test:** tests/unit/models
* **Bằng chứng chạy thật:** không mô hình nào được kiểm định
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **FREEZE**

### F30 - Risk engine (giới hạn, chặn theo regime/spread/kill switch, định cỡ)

* **Lớp:** C Quản lý rủi ro  |  **Trạng thái:** `PARTIALLY_WIRED`  |  **Dùng được hôm nay:** MỘT PHẦN
* **Mục đích / vấn đề giải quyết:** Quyết định một lệnh có được phép và cỡ bao nhiêu
* **Backend:** risk/engine.py, risk/prop_rules.py  |  **Frontend:** Dashboard.tsx (bảng giới hạn)
* **API:** GET /risk/status  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** configs/prop/*.yaml
* **Bằng chứng test:** tests/unit/risk
* **Bằng chứng chạy thật:** chạy thật (hiển thị giới hạn); dùng bởi bot và paper
* **Cách dùng hôm nay:** Trang chủ (chỉ đọc)
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F31 - Định cỡ lệnh theo % rủi ro và đặc tả hợp đồng của broker

* **Lớp:** C Quản lý rủi ro  |  **Trạng thái:** `BACKEND_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Ra số lot từ equity, risk %, entry, SL
* **Backend:** trading/sizing.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** symbol spec của broker
* **Bằng chứng test:** tests/unit/trading/test_decision_levels_sizing.py
* **Bằng chứng chạy thật:** chạy trong baseline
* **Cách dùng hôm nay:** KHÔNG có máy tính nào cho chủ dự án
* **Giá trị cho quyết định giao dịch:** HIGH  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F32 - Định cỡ lệnh bản cũ (risk/sizing.py)

* **Lớp:** C Quản lý rủi ro  |  **Trạng thái:** `DUPLICATED`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Trùng F31
* **Backend:** risk/sizing.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** -
* **Bằng chứng test:** tests/unit/risk
* **Bằng chứng chạy thật:** dùng trong risk engine
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **CONSOLIDATE**

### F33 - Kill switch bền vững (đặt/xem/reset bằng dòng lệnh)

* **Lớp:** C Quản lý rủi ro  |  **Trạng thái:** `USABLE_BUT_TECHNICAL`  |  **Dùng được hôm nay:** CÓ
* **Mục đích / vấn đề giải quyết:** Dừng mọi giao dịch ngay khi cần
* **Backend:** risk/kill_switch.py, execution/cli.py  |  **Frontend:** Dashboard.tsx (hiển thị)
* **API:** GET /risk/status  |  **CLI/script:** scripts/kill_switch.py
* **Dữ liệu phụ thuộc:** data/execution/state.sqlite
* **Bằng chứng test:** tests/unit/execution, tests/unit/risk
* **Bằng chứng chạy thật:** trạng thái 'unknown' (bot chưa tạo state)
* **Cách dùng hôm nay:** python scripts/kill_switch.py
* **Giá trị cho quyết định giao dịch:** HIGH  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F34 - Chốt chặn quy tắc FTMO (khoảng cách sàn lỗ, ngân sách request, rollover, tự flatten)

* **Lớp:** C Quản lý rủi ro  |  **Trạng thái:** `PARTIALLY_WIRED`  |  **Dùng được hôm nay:** MỘT PHẦN
* **Mục đích / vấn đề giải quyết:** Không vi phạm luật prop firm
* **Backend:** execution/guards.py, risk/prop_rules.py  |  **Frontend:** BotPanel (bảng PROP ACCOUNT, đang '-')
* **API:** GET /bot/status  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** configs/prop
* **Bằng chứng test:** tests/unit/execution
* **Bằng chứng chạy thật:** chỉ chạy khi bot chạy (dry-run 10-08)
* **Cách dùng hôm nay:** Qua bot
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F35 - Trade governor (phơi nhiễm, tần suất, cooldown, lỗ ngày)

* **Lớp:** C Quản lý rủi ro  |  **Trạng thái:** `BACKEND_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Giới hạn số lệnh và lỗ
* **Backend:** trading/governor.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** -
* **Bằng chứng test:** tests/unit/trading
* **Bằng chứng chạy thật:** chỉ test
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F36 - Quản lý lệnh đang mở (hòa vốn, trailing, thoát theo thời gian, tín hiệu ngược, vô hiệu hóa)

* **Lớp:** C Quản lý rủi ro  |  **Trạng thái:** `BACKEND_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Đóng lệnh có kỷ luật
* **Backend:** trading/position_manager.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** -
* **Bằng chứng test:** tests/unit/trading/test_manager_governor_arming.py
* **Bằng chứng chạy thật:** chỉ test; mặc định TẮT; bot demo hiện chỉ gắn SL/TP của broker
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** HIGH  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F37 - Rollout tài khoản funded theo bậc + định danh tài khoản

* **Lớp:** C Quản lý rủi ro  |  **Trạng thái:** `BLOCKED`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Chặn giao dịch funded trừ khi đủ điều kiện
* **Backend:** funded/*  |  **Frontend:** -
* **API:** -  |  **CLI/script:** scripts/rollout.py
* **Dữ liệu phụ thuộc:** configs/execution/rollout.yaml
* **Bằng chứng test:** tests/unit/funded
* **Bằng chứng chạy thật:** funded bị tắt theo thiết kế
* **Cách dùng hôm nay:** Không dùng
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **FREEZE**

### F38 - Monte Carlo khả thi prop firm

* **Lớp:** E Nghiên cứu / kiểm định  |  **Trạng thái:** `RESEARCH_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Rủi ro/lệnh nào còn sống sót qua giới hạn
* **Backend:** evaluation/prop_mc.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** -
* **Bằng chứng test:** tests/unit/evaluation
* **Bằng chứng chạy thật:** chỉ nghiên cứu
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **FREEZE**

### F40 - Paper trading (broker giả lập + POST /paper/orders + bảng tài khoản)

* **Lớp:** D Thực thi  |  **Trạng thái:** `PARTIALLY_WIRED`  |  **Dùng được hôm nay:** MỘT PHẦN
* **Mục đích / vấn đề giải quyết:** Thử lệnh mà không mất tiền
* **Backend:** execution/paper.py, execution/trader.py  |  **Frontend:** Dashboard.tsx (chỉ hiện số dư)
* **API:** POST /paper/orders, GET /paper/account|positions  |  **CLI/script:** scripts/forward_test.py
* **Dữ liệu phụ thuộc:** Signal BUY/SELL (không bao giờ xảy ra: cổng bằng chứng đóng)
* **Bằng chứng test:** tests/unit/execution, tests/unit/api/test_api_paper.py
* **Bằng chứng chạy thật:** tài khoản paper tồn tại; KHÔNG có nút; không có tín hiệu để mua
* **Cách dùng hôm nay:** Không bấm được từ giao diện
* **Giá trị cho quyết định giao dịch:** HIGH  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F41 - Bot demo chế độ DRY-RUN (mỗi nến M15: dữ liệu -> tín hiệu -> cầu nối -> nhật ký -> trạng thái)

* **Lớp:** D Thực thi  |  **Trạng thái:** `USABLE_BUT_TECHNICAL`  |  **Dùng được hôm nay:** CÓ
* **Mục đích / vấn đề giải quyết:** Chạy toàn bộ đường quyết định trên tài khoản demo mà không gửi lệnh
* **Backend:** execution/app.py, execution/runner.py  |  **Frontend:** components/BotPanel.tsx
* **API:** GET /bot/*  |  **CLI/script:** scripts/demo_trader.py
* **Dữ liệu phụ thuộc:** terminal + data/raw
* **Bằng chứng test:** tests/unit/execution (15 file)
* **Bằng chứng chạy thật:** chạy thật 2026-10-08 (9 chu kỳ, toàn WAIT); nhịp tim cũ 22 h
* **Cách dùng hôm nay:** python scripts/demo_trader.py (dry-run)
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F42 - Gửi lệnh DEMO thật (Mt5DemoExecutor) và lệnh smoke 0,01 lot

* **Lớp:** D Thực thi  |  **Trạng thái:** `BLOCKED`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Đưa quyết định thành lệnh trên tài khoản demo
* **Backend:** brokers/mt5_demo/executor.py, scripts/smoke_demo_order.py  |  **Frontend:** ControlPanel (nút smoke)
* **API:** POST /control/smoke  |  **CLI/script:** scripts/smoke_demo_order.py
* **Dữ liệu phụ thuộc:** MT5_TRADE_PASSWORD (chưa có), whitelist tài khoản
* **Bằng chứng test:** tests/unit/brokers (terminal giả)
* **Bằng chứng chạy thật:** CHƯA TỪNG gửi lệnh nào; thử bật smoke bị chặn TRADING_NOT_ALLOWED (đăng nhập bằng investor password)
* **Cách dùng hôm nay:** Chủ dự án phải đặt mật khẩu giao dịch + cờ (xem MVP)
* **Giá trị cho quyết định giao dịch:** HIGH  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F43 - Cầu nối tín hiệu->lệnh (idempotent, bảo vệ, override D2)

* **Lớp:** D Thực thi  |  **Trạng thái:** `BACKEND_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Cổng duy nhất từ tín hiệu tới lệnh
* **Backend:** execution/bridge.py, execution/order_intent.py, execution/override.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** -
* **Bằng chứng test:** tests/unit/execution
* **Bằng chứng chạy thật:** chạy dry-run
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F44 - Đối soát broker vs bot

* **Lớp:** D Thực thi  |  **Trạng thái:** `BACKEND_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Phát hiện lệch trạng thái lệnh
* **Backend:** execution/reconcile.py  |  **Frontend:** BotPanel (Reconciliation: clean)
* **API:** GET /bot/reconciliation  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** -
* **Bằng chứng test:** tests/unit/execution
* **Bằng chứng chạy thật:** chạy thật: clean
* **Cách dùng hôm nay:** Xem trên trang chủ
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F45 - Mặt phẳng điều khiển web (/control: bật/tắt bot, DRY-RUN/DEMO, smoke, flatten)

* **Lớp:** D Thực thi  |  **Trạng thái:** `PARTIALLY_WIRED`  |  **Dùng được hôm nay:** MỘT PHẦN
* **Mục đích / vấn đề giải quyết:** Điều khiển bot không cần dòng lệnh
* **Backend:** control/*, api/control.py  |  **Frontend:** components/ControlPanel.tsx, app/control/page.tsx
* **API:** /control/*  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** cần XAU_EDGE_WEB_CONTROL=true (mặc định false)
* **Bằng chứng test:** tests/unit/control, apps/dashboard/e2e/control.spec.ts
* **Bằng chứng chạy thật:** e2e có mock; chưa bật thật
* **Cách dùng hôm nay:** Đặt XAU_EDGE_WEB_CONTROL=true rồi mở /control
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F46 - Cảnh báo (Telegram + file dự phòng)

* **Lớp:** D Thực thi  |  **Trạng thái:** `PARTIALLY_WIRED`  |  **Dùng được hôm nay:** MỘT PHẦN
* **Mục đích / vấn đề giải quyết:** Báo khi có tín hiệu/lỗi
* **Backend:** ops/notifier.py, ops/settings.py  |  **Frontend:** -
* **API:** GET /bot/alerts  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** token Telegram (chưa thấy cấu hình)
* **Bằng chứng test:** tests/unit/ops
* **Bằng chứng chạy thật:** chỉ thấy cảnh báo NEWS_UNKNOWN ghi ra file alerts.jsonl; chưa có bằng chứng gửi Telegram
* **Cách dùng hôm nay:** Theo docs/operations/telegram-alerts.md (chủ dự án đặt token)
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F47 - Tự động hóa có chủ đích: arming thủ công trước khi bot tự giao dịch demo

* **Lớp:** D Thực thi  |  **Trạng thái:** `BACKEND_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Bắt buộc chủ dự án bật tay
* **Backend:** trading/arming.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** -
* **Bằng chứng test:** tests/unit/trading
* **Bằng chứng chạy thật:** chỉ test
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **DEFER**

### F48 - Replay/forward-test của paper trader

* **Lớp:** E Nghiên cứu / kiểm định  |  **Trạng thái:** `RESEARCH_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Xem lại hành vi trên dữ liệu gần đây
* **Backend:** execution/forward.py, trading/replay.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** scripts/forward_test.py, trading_baseline_sanity.py
* **Dữ liệu phụ thuộc:** data/raw
* **Bằng chứng test:** tests/unit/execution, tests/unit/trading
* **Bằng chứng chạy thật:** replay baseline 2 tuần chạy được (2,6 phút)
* **Cách dùng hôm nay:** dòng lệnh
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **FREEZE**

### F50 - Backtest event-driven (spread, slippage, commission, swap)

* **Lớp:** E Nghiên cứu / kiểm định  |  **Trạng thái:** `RESEARCH_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Đo kết quả chiến lược trên quá khứ
* **Backend:** backtest/*  |  **Frontend:** -
* **API:** GET /backtests  |  **CLI/script:** scripts/run_backtest.py
* **Dữ liệu phụ thuộc:** data/raw
* **Bằng chứng test:** tests/unit/backtest
* **Bằng chứng chạy thật:** chạy trong chương trình edge
* **Cách dùng hôm nay:** dòng lệnh
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** HIGH  |  **Khuyến nghị:** **FREEZE**

### F51 - Tiêu chí edge + phán quyết + bootstrap + khóa holdout

* **Lớp:** E Nghiên cứu / kiểm định  |  **Trạng thái:** `RESEARCH_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Chống tự lừa dối về edge
* **Backend:** evaluation/*  |  **Frontend:** -
* **API:** -  |  **CLI/script:** scripts/edge_program_report.py
* **Dữ liệu phụ thuộc:** data/raw
* **Bằng chứng test:** tests/unit/evaluation
* **Bằng chứng chạy thật:** đã dùng để kết luận V1 = (B)
* **Cách dùng hôm nay:** dòng lệnh
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** HIGH  |  **Khuyến nghị:** **KEEP**

### F52 - Edge Program V1 (H01-H06) + V2 Batch A (H07-H10) và kết quả

* **Lớp:** E Nghiên cứu / kiểm định  |  **Trạng thái:** `RESEARCH_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Tìm edge có thể kiểm định
* **Backend:** evaluation/edge_program.py, research_v2/*  |  **Frontend:** -
* **API:** -  |  **CLI/script:** scripts/run_edge_program.py, run_batch_a.py
* **Dữ liệu phụ thuộc:** data/raw
* **Bằng chứng test:** tests/unit/evaluation, research_v2
* **Bằng chứng chạy thật:** kết luận: NO EDGE WITHIN BUDGET; Batch A 0/20 qua Stage 1
* **Cách dùng hôm nay:** dòng lệnh
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** HIGH  |  **Khuyến nghị:** **FREEZE**

### F53 - Research Console (9 trang: tổng quan, sổ K, giả thuyết, bằng chứng, ứng viên, dữ liệu, lineage, forward, vận hành)

* **Lớp:** E Nghiên cứu / kiểm định  |  **Trạng thái:** `USABLE_BUT_TECHNICAL`  |  **Dùng được hôm nay:** CÓ
* **Mục đích / vấn đề giải quyết:** Xem toàn bộ sổ nghiên cứu
* **Backend:** research/*, api/research.py  |  **Frontend:** app/research/**, components/research/*
* **API:** GET /research/*, /lifecycle/*  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** docs/research/*, experiments/runs
* **Bằng chứng test:** tests/unit/research, e2e/research.spec.ts (64 test tổng e2e)
* **Bằng chứng chạy thật:** chạy thật
* **Cách dùng hôm nay:** Trang /research
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** HIGH  |  **Khuyến nghị:** **FREEZE**

### F54 - Lớp toàn vẹn nghiên cứu (placebo, power, DoF, lineage, prospective, gates, identity, freeze guard, ...)

* **Lớp:** E Nghiên cứu / kiểm định  |  **Trạng thái:** `INFRASTRUCTURE_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Bảo vệ tính trung thực của nghiên cứu
* **Backend:** integrity/* (18 file, 2.393 dòng)  |  **Frontend:** (một phần qua Research Console)
* **API:** GET /research/*  |  **CLI/script:** scripts/check_freeze.py, build_lineage.py
* **Dữ liệu phụ thuộc:** -
* **Bằng chứng test:** tests/unit/integrity
* **Bằng chứng chạy thật:** chạy thật
* **Cách dùng hôm nay:** Không cần dùng hằng ngày
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** HIGH  |  **Khuyến nghị:** **FREEZE**

### F55 - Vòng đời chiến lược + suy giảm edge

* **Lớp:** E Nghiên cứu / kiểm định  |  **Trạng thái:** `RESEARCH_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Hạ bậc chiến lược khi forward xấu
* **Backend:** research/lifecycle.py, research/decay.py  |  **Frontend:** ForwardView.tsx
* **API:** GET /lifecycle/*  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** -
* **Bằng chứng test:** tests/unit/research
* **Bằng chứng chạy thật:** chưa có chiến lược nào để theo dõi
* **Cách dùng hôm nay:** Trang /research/forward
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **FREEZE**

### F56 - Sổ thí nghiệm (experiment registry)

* **Lớp:** E Nghiên cứu / kiểm định  |  **Trạng thái:** `INFRASTRUCTURE_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Ghi mọi lần chạy để cổng bằng chứng tra cứu
* **Backend:** experiments/registry.py  |  **Frontend:** -
* **API:** GET /backtests  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** experiments/runs
* **Bằng chứng test:** tests/unit/experiments
* **Bằng chứng chạy thật:** dùng bởi F22
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **KEEP**

### F57 - Điều tra đồng hồ và chất lượng dữ liệu theo năm

* **Lớp:** E Nghiên cứu / kiểm định  |  **Trạng thái:** `RESEARCH_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Chứng minh đồng hồ broker NY+7
* **Backend:** forensics/clock.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** scripts/forensics_p0.py
* **Dữ liệu phụ thuộc:** data/raw
* **Bằng chứng test:** tests/unit/forensics
* **Bằng chứng chạy thật:** đã chạy (chứng chỉ clock)
* **Cách dùng hôm nay:** dòng lệnh
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **FREEZE**

### F60 - Feed MT5 chỉ-đọc (báo giá, tick, nến, symbol, đồng hồ broker) + guard DEMO

* **Lớp:** F Vận hành / hạ tầng  |  **Trạng thái:** `INFRASTRUCTURE_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Nguồn dữ liệu thật
* **Backend:** market_data/mt5/*  |  **Frontend:** -
* **API:** (qua /md/*)  |  **CLI/script:** scripts/mt5_connection_probe.py
* **Dữ liệu phụ thuộc:** terminal FTMO
* **Bằng chứng test:** tests/unit/market_data, tests/integration/test_mt5_live_data.py
* **Bằng chứng chạy thật:** chạy thật
* **Cách dùng hôm nay:** Nền cho F01-F03
* **Giá trị cho quyết định giao dịch:** HIGH  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F61 - Kho nến đã đóng (ledger) + sửa có kiểm toán

* **Lớp:** F Vận hành / hạ tầng  |  **Trạng thái:** `INFRASTRUCTURE_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Lưu nến bất biến 6 khung từ 2004 (7 triệu M1)
* **Backend:** market_data/ledger.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** scripts/backfill_mt5.py, repair_changed_bars.py
* **Dữ liệu phụ thuộc:** terminal
* **Bằng chứng test:** tests/unit/market_data
* **Bằng chứng chạy thật:** chạy thật; 0 vấn đề
* **Cách dùng hôm nay:** Nền
* **Giá trị cho quyết định giao dịch:** HIGH  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F62 - Kho tick + backfill + retention

* **Lớp:** F Vận hành / hạ tầng  |  **Trạng thái:** `INFRASTRUCTURE_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Lưu 205 triệu tick (1,46 GB) để đo thực thi
* **Backend:** market_data/tick_ledger.py  |  **Frontend:** -
* **API:** GET /md/*/ticks*  |  **CLI/script:** scripts/backfill_mt5_ticks.py, archive_ticks.py
* **Dữ liệu phụ thuộc:** terminal
* **Bằng chứng test:** tests/unit/market_data
* **Bằng chứng chạy thật:** chạy thật
* **Cách dùng hôm nay:** Chưa có tính năng giao dịch nào dùng tick
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **KEEP**

### F63 - Collector chạy mãi + tự nối lại + health/disk/freshness

* **Lớp:** F Vận hành / hạ tầng  |  **Trạng thái:** `INFRASTRUCTURE_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Giữ dữ liệu luôn tươi
* **Backend:** market_data/collector.py, collector_runner.py, freshness.py, disk.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** scripts/run_market_collector.py
* **Dữ liệu phụ thuộc:** terminal
* **Bằng chứng test:** tests/unit/market_data
* **Bằng chứng chạy thật:** chạy thật
* **Cách dùng hôm nay:** Nền
* **Giá trị cho quyết định giao dịch:** HIGH  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F64 - Lịch phiên FTMO (nghỉ ngày 16:50-18:05 NY, ngày lễ suy ra từ dữ liệu)

* **Lớp:** F Vận hành / hạ tầng  |  **Trạng thái:** `INFRASTRUCTURE_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Phân biệt đóng cửa thật với thiếu dữ liệu
* **Backend:** market_data/calendars.py, session_exceptions.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** scripts/infer_session_exceptions.py
* **Dữ liệu phụ thuộc:** configs/brokers/*.yaml
* **Bằng chứng test:** tests/unit/market_data/test_session_calendar.py
* **Bằng chứng chạy thật:** chạy thật
* **Cách dùng hôm nay:** Nền
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F65 - Giám sát tiến trình + start/stop/status + Task Scheduler

* **Lớp:** F Vận hành / hạ tầng  |  **Trạng thái:** `USABLE_BUT_TECHNICAL`  |  **Dùng được hôm nay:** CÓ
* **Mục đích / vấn đề giải quyết:** Khởi động/dừng cả hệ thống bằng một lệnh
* **Backend:** ops/supervisor.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** scripts/start_market_stack.ps1, stop_market_stack.ps1, status_market_stack.ps1, install_market_autostart.ps1
* **Dữ liệu phụ thuộc:** -
* **Bằng chứng test:** tests/unit/ops/test_supervisor.py
* **Bằng chứng chạy thật:** chạy thật; đăng nhập thật chưa thử
* **Cách dùng hôm nay:** PowerShell
* **Giá trị cho quyết định giao dịch:** HIGH  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F66 - Kiểm tra toàn vẹn, parity, visual parity, snapshot, benchmark

* **Lớp:** F Vận hành / hạ tầng  |  **Trạng thái:** `INFRASTRUCTURE_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Chứng minh dữ liệu đúng
* **Backend:** market_data/verification.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** scripts/verify_*.py, market_data_parity.py, snapshot_market.py, bench_market_data.py
* **Dữ liệu phụ thuộc:** ledger
* **Bằng chứng test:** tests/unit/market_data
* **Bằng chứng chạy thật:** chạy thật: 312/312 khớp
* **Cách dùng hôm nay:** Dòng lệnh
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F67 - Kho bar thô cũ (data/raw): catalog, refresh, compact, validator

* **Lớp:** F Vận hành / hạ tầng  |  **Trạng thái:** `DUPLICATED`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Kho bar thứ hai nuôi tín hiệu legacy và nghiên cứu; KHÔNG nối với ledger MT5 mới
* **Backend:** market_data/store.py, catalog.py, refresh.py, compact.py, validators/*  |  **Frontend:** -
* **API:** (nuôi /signals, /features)  |  **CLI/script:** scripts/fetch_history.py, compact_raw.py
* **Dữ liệu phụ thuộc:** data/raw (cũ 23 h)
* **Bằng chứng test:** tests/unit/market_data
* **Bằng chứng chạy thật:** tín hiệu đang đọc kho này nên cũ
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **CONSOLIDATE**

### F68 - Đồng hồ NTP, log JSON che bí mật, health check cho watcher ngoài

* **Lớp:** F Vận hành / hạ tầng  |  **Trạng thái:** `INFRASTRUCTURE_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Vận hành an toàn
* **Backend:** ops/clock_check.py, ops/logging_setup.py, observability.py  |  **Frontend:** -
* **API:** -  |  **CLI/script:** scripts/check_health.py
* **Dữ liệu phụ thuộc:** -
* **Bằng chứng test:** tests/unit/ops, tests/test_observability*.py
* **Bằng chứng chạy thật:** đã dùng
* **Cách dùng hôm nay:** Nền
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F69 - Trình cài dịch vụ NSSM (bot, API)

* **Lớp:** F Vận hành / hạ tầng  |  **Trạng thái:** `NOT_USEFUL_CURRENTLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Chạy bot/API như service Windows
* **Backend:** scripts/install_services.ps1  |  **Frontend:** -
* **API:** -  |  **CLI/script:** scripts/install_services.ps1
* **Dữ liệu phụ thuộc:** NSSM (chưa cài)
* **Bằng chứng test:** (không có test tự động)
* **Bằng chứng chạy thật:** chưa chạy
* **Cách dùng hôm nay:** Không
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **DEFER**

### F70 - CI 7 job (Windows+Ubuntu x Python 3.12-3.14 + dashboard)

* **Lớp:** F Vận hành / hạ tầng  |  **Trạng thái:** `INFRASTRUCTURE_ONLY`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Chặn hồi quy
* **Backend:** .github/workflows/xau-edge-ci.yml  |  **Frontend:** -
* **API:** -  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** -
* **Bằng chứng test:** chính nó
* **Bằng chứng chạy thật:** xanh trên HEAD 195c04b
* **Cách dùng hôm nay:** Nền
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **KEEP**

### F80 - Điều hướng dashboard (3 điểm vào rời nhau + 9 trang nghiên cứu, KHÔNG có màn hình giao dịch)

* **Lớp:** G Sản phẩm / UX  |  **Trạng thái:** `PARTIALLY_WIRED`  |  **Dùng được hôm nay:** MỘT PHẦN
* **Mục đích / vấn đề giải quyết:** Đi tới các màn hình
* **Backend:** app/page.tsx, app/market, app/research, app/control  |  **Frontend:** Dashboard.tsx (3 nút), ResearchNav.tsx
* **API:** -  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** -
* **Bằng chứng test:** e2e
* **Bằng chứng chạy thật:** chạy thật
* **Cách dùng hôm nay:** /, /market, /research, /control
* **Giá trị cho quyết định giao dịch:** MEDIUM  |  **Giá trị nghiên cứu:** LOW  |  **Khuyến nghị:** **CONSOLIDATE**

### F81 - Bộ tài liệu (100 file md: 25 ADR, báo cáo sprint, 4 lộ trình chồng nhau)

* **Lớp:** G Sản phẩm / UX  |  **Trạng thái:** `DUPLICATED`  |  **Dùng được hôm nay:** KHÔNG
* **Mục đích / vấn đề giải quyết:** Ghi nhớ quyết định
* **Backend:** docs/*  |  **Frontend:** -
* **API:** -  |  **CLI/script:** -
* **Dữ liệu phụ thuộc:** -
* **Bằng chứng test:** -
* **Bằng chứng chạy thật:** -
* **Cách dùng hôm nay:** Đọc docs/MT5_DATA_PLATFORM.md và docs/PRACTICAL_TRADING_MVP.md
* **Giá trị cho quyết định giao dịch:** LOW  |  **Giá trị nghiên cứu:** MEDIUM  |  **Khuyến nghị:** **CONSOLIDATE**


## 7. Ma trận "việc của trader" (XAU EDGE làm được gì hôm nay)

| Việc | Hôm nay làm được | Chưa làm được | Module chịu trách nhiệm |
|---|---|---|---|
| NHÌN thị trường | Giá sống, nến 6 khung từ 2004, tick volume, spread, độ tươi | Không có mức giá/chỉ báo/cấu trúc vẽ trên biểu đồ | `market_data/*`, `api/market_data.py`, `/market` |
| HIỂU thị trường | Backend tính được trạng thái H4->M1, volume chuẩn hóa, mẫu giá, cấu trúc (đã thử trên dữ liệu sống) | Không có màn hình hay API hiển thị; trang chủ hiện bản legacy trên dữ liệu cũ | `trading/market_state.py`, `trading/activity.py`, `trading/patterns.py`, `structure/*` |
| QUYẾT ĐỊNH | Trading Core cho BUY/SELL/WAIT + lý do (qua script) | Không có endpoint/UI; bị chặn bởi tin tức chưa rõ; rất thưa (0,1%) | `trading/baseline.py` |
| LẬP KẾ HOẠCH LỆNH | Entry/SL/TP/RR có trong `TradingSignal` khi có BUY/SELL | Không hiển thị; legacy chỉ ra mức khi WAIT có 'lean' trên dữ liệu cũ | `trading/levels.py` |
| ĐỊNH CỠ RỦI RO | Hàm tính lot theo thông số broker | Không có máy tính cho chủ dự án | `trading/sizing.py` |
| THỰC THI | Bot DRY-RUN; paper broker (API) | Không bấm paper được; chưa từng gửi lệnh demo; thiếu mật khẩu giao dịch và cờ | `execution/*`, `brokers/mt5_demo/*` |
| THEO DÕI LỆNH | Đối soát broker; trạng thái bot; nhật ký | Không theo dõi SL/TP/thời gian của lệnh paper; quản lý lệnh chưa nối | `execution/reconcile.py`, `trading/position_manager.py` |
| THOÁT LỆNH | SL/TP gắn kèm lệnh; kill switch (CLI); flatten FTMO; hết hạn tín hiệu | Hòa vốn/trailing/thoát theo thời gian/tín hiệu ngược chưa nối (mặc định tắt) | `trading/position_manager.py` |
| XEM LẠI | Sổ nhật ký thực thi; Research Console | Không có sổ giao dịch paper/thủ công, không có thống kê theo ngày | `execution/journal.py`, `research/*` |

## 8. Bảng "thiếu để dùng được" (ước lượng của người kiểm toán, dựa trên mã đã đọc)

| Năng lực mong muốn | Backend có sẵn | Frontend có sẵn | Phần thiếu | Độ phức tạp | Phụ thuộc | Ưu tiên |
|---|---|---|---|---|---|---|
| BUY/SELL/WAIT trên dữ liệu sống | ~85% | ~10% | endpoint `/trade/decision`, chính sách tin tức, đọc ledger thay `data/raw` | trung bình-thấp | quyết định tin tức | **1** |
| Màn hình `/trade` (đa khung, lý do, volume, cấu trúc, bằng chứng) | ~90% (dữ liệu) | ~20% (biểu đồ, viên trạng thái) | trang mới tái dùng thành phần | trung bình | #1 | **2** |
| Kế hoạch Entry/SL/TP/RR + lot | ~85% | ~15% | hiển thị + máy tính rủi ro | thấp | #1 | **3** |
| Máy tính rủi ro | ~80% | 0% | endpoint `/trade/risk` + ô nhập | thấp | thông số broker, equity | **3** |
| PAPER BUY/SELL + theo dõi thoát | ~65% | ~10% | nút, nối `position_manager` vào paper, lưu bền | trung bình | #1-#3 | **4** |
| Cảnh báo "setup sẵn sàng/vô hiệu/SL-TP chạm" | ~70% (notifier) | n/a | thêm sự kiện + cấu hình token (chủ dự án) | thấp | #1; token Telegram | **5** |
| Nhật ký/ôn tập giao dịch | ~40% | ~20% | sổ giao dịch paper + tóm tắt ngày | trung bình | #4 | 6 (sau 5 cái đầu) |
| Lệnh DEMO thật | ~85% | ~40% (`/control`) | hành động chủ dự án (mật khẩu giao dịch, cờ, whitelist, override) | thấp (kỹ thuật) / chủ dự án | sau paper | 7 |
| Thiết bị đo thực thi bằng tick | ~60% (kho tick) | 0% | thước đo trượt giá/spread theo giờ | trung bình | dữ liệu thực thi thật | hoãn |

## 9. Xếp hạng giá trị chủ dự án và giá trị nghiên cứu (tách bạch)

| Nhóm | Giá trị hằng ngày cho chủ dự án | Giá trị nghiên cứu | Ghi chú |
|---|---|---|---|
| BUY/SELL/WAIT có giải thích | CAO | TRUNG BÌNH | tạo dữ liệu forward để sau này kiểm định |
| Kế hoạch lệnh + rủi ro | CAO | THẤP | |
| Nến/volume/spread sống | CAO | THẤP | đã có |
| Paper + nhật ký | CAO | CAO | nguồn bằng chứng forward duy nhất không chạm holdout |
| Lineage, manifest, K, freeze guard, placebo, power | THẤP | CAO | hạ tầng nền, không để lấn át giao diện hằng ngày |
| Research Console (9 trang) | THẤP | CAO | đóng băng, ẩn dưới "Nghiên cứu" |
| ML/chiến lược mới | KHÔNG | KHÔNG (giai đoạn này) | không làm |

## 10. Phát hiện bổ sung của kiểm toán

* **Quyết định bị chặn từ nhiều phía cùng lúc** (mục 5): ngay cả khi sửa một chốt chặn, vẫn còn các chốt khác. Bắt đầu bằng tin tức, vì đây là chốt rẻ nhất.
* **Heartbeat bot cũ 22 giờ**: bot demo DRY-RUN chỉ chạy ngày 2026-10-08; không có bằng chứng nó chạy lại. Nếu muốn bot chạy, cần đặt nó vào cùng supervisor với collector.
* **Mỗi hệ thống có trạng thái riêng**: `status.json` (bot), `collector_status.json`, `supervisor.json`, Research Console; chưa có một nơi tóm tắt cho `/trade`.
* **Thông tin tài khoản demo** đã hiển thị trên trang chủ từ `status.json`; đây là số dư demo, nhưng nhớ rằng bất cứ ảnh chụp màn hình nào chia sẻ ra ngoài cũng lộ nó.
* **Không có kết quả nào chứng minh Trading Core có lãi.** Replay 2 tuần chỉ là kiểm tra Class D (2 lệnh, cả hai dính SL).
