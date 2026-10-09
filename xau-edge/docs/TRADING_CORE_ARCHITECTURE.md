# Kiến trúc Trading Core và Trading Desk (paper)

Trạng thái: TRADE-01. Mục tiêu: một trang `/trade` cho quyết định PAPER có kỷ luật, minh bạch, có rủi ro xác định, trên dữ liệu FTMO DEMO sống. Không gửi lệnh thật, không gọi `order_send`.

## 1. Luồng dữ liệu duy nhất

```
FTMO MT5 (terminal)
  └─ collector (supervisor sở hữu, chỉ ĐỌC MT5)
       ├─ data/market  (ledger nến ĐÃ ĐÓNG, 6 khung, từ 2004)
       ├─ live.json     (quote, nến đang hình thành, tick, symbol_spec của broker)
       └─ collector_status.json
            │
            ▼
LiveTradingMarketSource  (trading/live_source.py)  ← adapter production DUY NHẤT
            │  chỉ nến đã đóng + quote + spec; đo độ tươi từng khung
            ▼
decision_core.evaluate   (hàm THUẦN: không I/O, không đồng hồ)
   build_market_state → baseline.decide → TradingSignal (= TradingDecision)
            │
            ▼
TradeEngine (trading/engine.py)  ── cache quyết định, telemetry, cảnh báo
   ├─ PaperDesk (trading/paper_desk.py) ← bọc PaperExecutionBroker có sẵn
   ├─ SetupAlerts (AlertDispatcher có sẵn: Telegram hoặc file)
   └─ DecisionTelemetry (data/trade/decisions-YYYYMMDD.jsonl)
            │
            ▼
API  GET /trade/decision, /trade/risk, /trade/paper, /trade/journal, /trade/telemetry
     POST /trade/paper/open, /trade/paper/close   (chỉ PAPER, có guard)
            │
            ▼
Dashboard  /trade  /journal  (+ /market, /research, /control)
```

`data/raw` (kho nghiên cứu cũ) **không** nằm trong luồng quyết định. Test `test_live_path_isolation.py` fail nếu `trading/*` hoặc `api/trade.py` import `DatasetCatalog`, `raw_store`, `signals.engine/evidence` hay API lệnh MT5.

## 2. Phân cấp khung thời gian (đơn giản hóa)

| Khung | Vai trò | Quyền |
|---|---|---|
| H4 | REGIME / BLOCKER | chỉ chặn lệnh ngược xu hướng H4 mạnh; không tạo lệnh |
| H1 | DIRECTION | nguồn DUY NHẤT của BUY/SELL |
| M30 | CONTEXT | chỉ hiển thị; không veto, không tạo lệnh |
| M15 | SETUP | pullback trong xu hướng H1, cấu trúc không ngược |
| M5 | TRIGGER | động lượng / phá cấu trúc theo hướng H1 |
| M1 | EXECUTION TIMING | spread, tick volume, biến động ngắn; chỉ được CHẶN, không đảo hướng |

Chuỗi: REGIME → DIRECTION → SETUP → TRIGGER → EXECUTION → PLAN → RISK. WAIT là câu trả lời bình thường; mỗi WAIT có ít nhất một lý do (schema bắt buộc).

## 3. Nguyên tắc nến đã đóng

Mỗi khung dùng `available_at = open + độ dài khung`; `closed_as_of(df, now)` chỉ giữ nến có `available_at <= now`. Nến đang hình thành (`live.json: forming`) **không bao giờ** vào quyết định (test đỏ-đội `test_a_forming_bar_never_reaches_the_decision`). Tick volume luôn gắn nhãn `TICK_VOLUME`, không bao giờ là volume sàn.

## 4. Trade plan

* Entry: MARKET tại giá thực thi (BUY = ask, SELL = bid).
* SL: mô hình HYBRID = max(cấu trúc + đệm, 1.25 ATR); từ chối nếu rộng hơn 3 ATR hoặc gần hơn `stops_level` của broker (`INVALID_STOP_DISTANCE`).
* TP: bội số R (2R, TP2 3R) bị chặn bởi cấu trúc đối diện; phải đạt `min_net_rr = 1.5` SAU spread.
* Lot: rủi ro % (0.10 / 0.25 / 0.50, mặc định 0.25, tối đa 0.50) × vốn paper giả lập / (khoảng SL × tick_value broker), LÀM TRÒN XUỐNG theo `volume_step`; nhỏ hơn `volume_min` thì từ chối (`RISK_LIMIT`), không bao giờ vượt rủi ro.
* Hết hạn: neo vào thời điểm đóng của nến M5 trigger (3 nến M5), không phải "bây giờ".
* `setup_id` ổn định theo nến M5 trigger (cảnh báo và lệnh paper khóa theo nó); `decision_id` đổi theo mỗi lần tính.

## 5. Paper desk

`PaperDesk` bọc `PaperExecutionBroker`: trạng thái PENDING → OPEN → CLOSED/CANCELLED; mỗi setup chỉ vào một lần (idempotent), tối đa 1 lệnh mở, governor (cooldown, giới hạn ngày/phiên). Thoát tự động: STOP_LOSS, TAKE_PROFIT, TIME_EXIT (120 phút), MANUAL_CLOSE (và INVALIDATED nếu bật); nến vào lệnh không bao giờ dùng để thoát; nến chạm cả SL và TP → tính SL. BE/trailing/đóng khi vô hiệu: mặc định TẮT. Lưu `paper_desk.json` (sống qua restart), `paper_journal.jsonl` (sự kiện + provenance: code_version, quyết định, thị trường), `paper_broker.jsonl`.

## 6. Khóa thực thi DEMO

`demo_lock_status()` trả về `LOCKED` kèm từng lý do (chỉ boolean): `TRADING_NOT_ALLOWED` (mật khẩu investor), `MT5_TRADE_PASSWORD_MISSING`, `DEMO_TRADING_DISABLED`, `DEMO_DRY_RUN`, `DEMO_ALLOWED_ACCOUNTS_EMPTY`. Không bao giờ in giá trị bí mật. Bàn paper **không** gửi lệnh dù khóa mở (`paper_desk_sends_orders: false`).

## 7. Bảo mật API ghi

Hai POST paper: Host phải là `127.0.0.1:8000`/`localhost:8000`, `Origin` thuộc danh sách dashboard, `Content-Type: application/json`, header `X-Paper-Desk: 1`, body chỉ `setup_id`/`trade_id` (+ `risk_pct`), không giá/hướng/lot do client chọn, `extra=forbid`. Máy chủ kiểm lại `setup_id` còn là setup hiện tại, dữ liệu đủ tươi, chưa hết hạn. Trình duyệt đi qua proxy `app/api/trade/[...path]` của dashboard (chỉ 2 đường dẫn). Test duyệt bảng route: ngoài 2 POST paper không có route ghi nào.

## 8. Song song (parity)

Live, replay và paper cùng gọi `decision_core.evaluate`. `comparable()` gom các trường phải GIỐNG HỆT. Replay chạy hai lần: toàn bộ lịch sử vs đuôi cắt như live (`TAILS`); khác biệt = blocker.
