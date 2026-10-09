# Đặc tả màn hình giao dịch `/trade`

Ngày: 2026-10-09. Trạng thái: ĐẶC TẢ, chưa xây (chờ chủ dự án duyệt `docs/PRACTICAL_TRADING_MVP.md` mục 9). Mọi trường dưới đây đã tồn tại trong
mã (cột "Nguồn") trừ những dòng ghi **[MỚI]**. Màn hình trả lời bốn câu hỏi: ĐANG XẢY RA GÌ? NÊN LÀM GÌ? VÌ SAO? RỦI RO CỦA TÔI LÀ GÌ?

## 1. Nguyên tắc

* Một màn hình chính, không điều hướng sang Research/Operations/Lineage/Datasets để ra quyết định cơ bản.
* Khai báo dần: màn hình chính chỉ chứa dữ liệu hành động được; chi tiết kỹ thuật nằm trong khung gấp "Chi tiết kỹ thuật" và các trang System/Research.
* Chỉ dùng nến ĐÃ ĐÓNG cho quyết định; nến đang hình thành chỉ để xem và luôn đánh dấu. Không bao giờ hiển thị một quyết định trên dữ liệu cũ mà không báo.
* Không có ô nhập hướng/lot/SL/TP tùy ý gửi tới broker. Máy tính rủi ro chỉ tính, không gửi.
* Luôn có nhãn: `UNVALIDATED_BASELINE` và "Edge đã kiểm định: KHÔNG".

## 2. Bố cục (desktop 1280 px; điện thoại xếp dọc theo cùng thứ tự)

```
+--------------------------------------------------------------------------------------------+
| XAUUSD   Bid 4183.27  Ask 4183.68  Spread 41 điểm (GOOD)   Thị trường: MỞ   [Giờ: UTC v]   |
| Dữ liệu: M5 đóng 12:35 (cách 2 phút)  | MT5 ✓  Collector ✓  API ✓  | Làm mới tự động 5 s   |
+--------------------------------------------------------------------------------------------+
| QUYẾT ĐỊNH                                          | KẾ HOẠCH LỆNH                         |
|  ┌───────────┐  BUY / SELL / WAIT                   |  Vào lệnh   MARKET  4183.68           |
|  │   WAIT    │  "Chưa có setup"                     |  Cắt lỗ     4177.40  (6.28 = 1.7 ATR) |
|  └───────────┘  hiệu lực đến 12:50                  |  Chốt lời   4196.24  (TP1, 2.0 R)     |
|  Nhãn: UNVALIDATED_BASELINE | Edge kiểm định: KHÔNG  |  R/R ròng   2.0  (tối thiểu 1.5)      |
+-----------------------------------------------------+  Rủi ro     0.25%  = 24.00 USD        |
| VÌ SAO                                              |  Cỡ lot đề xuất  0.38                 |
|  ✓ H1 xu hướng tăng                                 |  [Sao chép kế hoạch] [PAPER BUY]      |
|  ✓ M15 pullback hoàn tất                            +----------------------------------------+
|  ✗ M5 chưa có nến xác nhận                          | MÁY TÍNH RỦI RO                        |
|  ✓ Spread bình thường (41 điểm)                     |  Equity [10 000.00]  Rủi ro % [0.25]    |
|  ✗ Biến động thấp (ATR dưới percentile 20)          |  Vào [ ]  SL [ ]  -> lot, rủi ro USD   |
+-----------------------------------------------------+----------------------------------------+
| ĐA KHUNG THỜI GIAN                                                                          |
|  H4  RANGE      (chế độ; chỉ chặn)        | H1  BULLISH   (HƯỚNG chính)                     |
|  M30 RANGE      (cấu trúc, tham khảo)     | M15 RANGE / NONE  (setup)                       |
|  M5  FLAT       (trigger)                 | M1  QUIET        (thời điểm vào, chỉ chặn)      |
+---------------------------------------------------+-----------------------------------------+
| HOẠT ĐỘNG / VOLUME (tick volume)                  | CẤU TRÚC                                |
|  M1 z-score -1.2  (LOW)  percentile 18            |  Xu hướng H1: tăng  | Swing gần: 4170.1 |
|  M5 tỷ lệ 0.7x   M15 tỷ lệ 0.8x                   |  Hỗ trợ 4170.1 (13.4 = 1.9 ATR)         |
|  gia tốc -0.3     (không phải volume sàn)         |  Kháng cự 4201.5 (18.2 = 2.6 ATR)       |
|                                                   |  Phá vỡ/từ chối gần nhất: -             |
+---------------------------------------------------+-----------------------------------------+
| [Biểu đồ M5/M15 nến + tick volume + mức Vào/SL/TP]                         [Chi tiết kỹ thuật v] |
+--------------------------------------------------------------------------------------------+
| BẰNG CHỨNG:  Baseline vận hành: UNVALIDATED_BASELINE  | Nghiên cứu: không có edge được kiểm định |
|              (Edge Program V1 = (B); V2 Batch A 0/20)   | Tin tức: CHƯA KIỂM TRA / Rõ / Cửa sổ tin |
+--------------------------------------------------------------------------------------------+
```

## 3. Các phần, trường, nguồn

| Phần | Trường | Nguồn dữ liệu |
|---|---|---|
| Đầu trang | bid, ask, spread (điểm), tuổi tick, trạng thái thị trường, múi giờ | `GET /md/XAUUSD/quote`, `/md/status` (có sẵn) |
| Đầu trang | thời điểm quyết định, tuổi dữ liệu, 3 viên MT5/Collector/API | `TradingSignal.timestamp`; `/md/status.components` (có sẵn) |
| Quyết định | `decision` BUY/SELL/WAIT, hiệu lực đến `signal_expiry`, `evidence_status` | `GET /trade/decision` **[MỚI]** (bao quanh `trading.baseline.decide`) |
| Kế hoạch lệnh | `entry_type`, `entry_price`, `stop_loss` (+ `stop_model`, khoảng cách theo ATR), `take_profit`, `take_profit_2`, `risk_reward`, `required_win_rate`, `risk_pct`, `position_size` | `TradingSignal` (có sẵn) |
| Vì sao | danh sách bước chuỗi (đạt/không) + `reasons` + `refusal_reasons` đổi sang câu thường | `TradingSignal.reasons/refusal_reasons` + bảng mẫu câu ở mục 6 |
| Máy tính rủi ro | equity, risk %, entry, SL -> rủi ro USD, khoảng cách SL, lot | `trading/sizing.py::size_for_risk` qua `GET /trade/risk` **[MỚI]**; equity gợi ý từ `/bot/account` hoặc nhập tay |
| Đa khung | trạng thái H4, H1, M30, M15 (setup/pullback), M5 (momentum), M1 (vi mô) | `MarketState` (có sẵn) |
| Volume | z-score M1 + nhãn, percentile, tỷ lệ M5/M15, gia tốc | `trading/activity.py` -> trường `volume_*` trong `MarketState` (một số trường cần xuất ra) |
| Cấu trúc | xu hướng H1, hỗ trợ/kháng cự gần nhất + khoảng cách theo ATR, BOS/CHoCH gần nhất | `MarketState` (`dist_*`, swing) |
| Bằng chứng | nhãn baseline, trạng thái nghiên cứu, tin tức | `evidence_status`; `docs/research/edge-program/final-verdict.md`; `news_state` |
| Biểu đồ | nến M5/M15 + tick volume + đường Vào/SL/TP | thành phần `MarketChart` (có sẵn) + 3 đường mức giá **[MỚI]** |

Hợp đồng API đề xuất `GET /trade/decision` (chỉ GET, không nhận tham số lệnh): `{ data_as_of, age_seconds, market_status, news_state, signal: TradingSignal,
state: { h4, h1, m30, m15, m5, m1, spread_state, volume: {...}, structure: {...} }, evidence: { operational, research }, warnings: [...] }`.
Tính theo nến đã đóng; kết quả tất định theo `inputs_hash`; không đọc `data/raw`.

## 4. Nút và hành động

| Nút | Hiện khi | Làm gì | Ràng buộc |
|---|---|---|---|
| Làm mới | luôn | gọi lại `/trade/decision` | còn tự làm mới 5 s |
| Sao chép kế hoạch | BUY/SELL | sao chép văn bản Vào/SL/TP/lot/lý do | không gửi gì ra ngoài |
| PAPER BUY / PAPER SELL | quyết định BUY/SELL, chưa hết hạn, kill switch không đặt | gửi quyết định (`at` = mốc quyết định) tới paper trader | qua `POST /paper/orders` (không nhận tham số lệnh); xác nhận hai bước; ghi nhật ký |
| Chọn múi giờ | luôn | UTC / Broker / Máy tôi | chỉ đổi hiển thị |
| Chi tiết kỹ thuật | luôn | mở khung: `inputs_hash`, `strategy_version`, ngưỡng cấu hình, tuổi từng khung | chỉ đọc |

KHÔNG có nút "gửi lệnh demo" trên màn hình này ở giai đoạn đầu. Lệnh demo đi qua bot/`/control` sau khi paper ổn (MVP mục 11).

## 5. Các trạng thái

| Trạng thái | Hiển thị |
|---|---|
| **BUY** | thẻ xanh "BUY", đầy đủ kế hoạch lệnh, lý do dạng ✓, hiệu lực đếm ngược, nút PAPER BUY bật |
| **SELL** | tương tự, màu đỏ, nút PAPER SELL |
| **WAIT** | thẻ xám "WAIT" + một câu nêu lý do chính; kế hoạch lệnh ẩn (hoặc "Nếu có setup: ..." chỉ khi có lean); danh sách ✗ cho từng từ chối; nút PAPER ẩn |
| **WAIT do tin tức chưa kiểm tra** | WAIT + biểu ngữ vàng "TIN TỨC CHƯA KIỂM TRA: cần lịch kinh tế" (nếu chủ dự án chọn cho phép tin chưa rõ thì BUY/SELL vẫn hiện kèm biểu ngữ đó) |
| **Dữ liệu cũ** (khung đã đóng trễ quá ngưỡng) | toàn bộ thẻ quyết định mờ, nhãn "KHÔNG DÙNG: dữ liệu cũ N phút", không có nút PAPER |
| **Thị trường đóng / rollover** | quyết định WAIT, nhãn "Thị trường đóng (cuối tuần)" hoặc "Nghỉ giữa ngày"; không báo là lỗi |
| **Collector dừng / MT5 mất kết nối** | biểu ngữ đỏ + lệnh khắc phục (tái dùng `recovery_action` của `/md/status`) |
| **API không phản hồi** | "Không đọc được API" + `scripts/start_market_stack.ps1` |
| **Kill switch đặt** | biểu ngữ đỏ "KILL SWITCH ĐANG BẬT: ..."; nút PAPER ẩn |
| **Quyết định hết hạn** | thẻ xám "HẾT HẠN", nút ẩn |
| **Đang tải** | khung xám "Đang tải..."; không hiện BUY/SELL tạm |

## 6. Lời giải thích (không bao giờ chỉ in "BUY")

BUY ví dụ: "BUY vì: H1 xu hướng tăng; M15 pullback đã hoàn tất; M5 có nến xác nhận; M1 hoạt động tăng và tick volume cao hơn bình thường (z = 1,4);
spread bình thường (41 điểm); R/R ròng 2,1; không có kháng cự lớn trong 1 ATR trước TP1."
WAIT ví dụ: "WAIT vì: H4 đang đi ngang nhưng H1 tăng; M15 chưa có pullback; biến động thấp (ATR dưới percentile 20); tin tức chưa kiểm tra."

Bảng chuyển `Refusal` -> câu (đủ 17 mã trong `trading/schema.py`): `NO_DIRECTIONAL_EDGE` "H1 không có hướng rõ"; `TIMEFRAME_CONFLICT` "các khung xung đột (H4 chặn H1)";
`NO_SETUP` "chưa có setup/pullback ở M15"; `NO_ENTRY_TRIGGER` "M5 chưa xác nhận"; `SPREAD_TOO_WIDE` "spread quá rộng"; `VOLATILITY_TOO_HIGH/LOW`
"biến động quá cao/thấp"; `TOO_CLOSE_TO_RESISTANCE/SUPPORT` "quá gần kháng cự/hỗ trợ"; `RR_TOO_LOW` "R/R không đạt tối thiểu"; `RISK_LIMIT` "vượt giới hạn rủi ro hoặc SL không hợp lệ";
`DAILY_LIMIT` "đã chạm giới hạn ngày"; `COOLDOWN` "đang nghỉ sau lệnh trước"; `NEWS_WINDOW` "quanh tin tức hoặc chưa kiểm tra tin"; `STALE_DATA` "dữ liệu cũ";
`BROKER_DISCONNECTED` "mất kết nối broker"; `UNKNOWN_STATE` "thiếu dữ liệu khung".

## 6b. Hiển thị rủi ro

* Luôn hiển thị: rủi ro % và USD, khoảng cách SL (điểm, USD, bội ATR), R/R ròng sau chi phí, `required_win_rate`, lot (đã làm tròn theo bước lot của broker).
* Cảnh báo: lot < tối thiểu (từ chối, không làm tròn lên); SL dưới `stops_level` của broker; vượt ngưỡng rủi ro ngày/prop; spread > ngưỡng.
* Không bao giờ ngụ ý lợi nhuận: nhãn tiếng Việt cố định "Đây là tín hiệu vận hành chưa được kiểm định, không phải dự báo lợi nhuận."

## 7. Điều hướng đơn giản (ngoài màn hình này)

Đề xuất 5 mục cấp một, thay cho 4 điểm vào rời nhau hiện nay: **Giao dịch** (`/trade`, mặc định), **Thị trường** (`/market`), **Nhật ký** (paper/demo/bot: giao dịch,
quyết định gần đây, đối soát), **Nghiên cứu** (toàn bộ `/research`, ẩn dưới một mục), **Hệ thống** (collector, bot, `/control`, sức khỏe dữ liệu).
Trang chủ `/` chuyển hướng tới `/trade`. Không xóa trang nào; chỉ gộp lối vào.

## 8. Kiểm thử chấp nhận cho màn hình

* Playwright (API giả): BUY, SELL, WAIT (mỗi mã từ chối), dữ liệu cũ, thị trường đóng, collector dừng, API chết, kill switch, hết hạn; không có cuộn ngang ở 390 px; chế độ tối.
* Một bài kiểm tra chứng minh trang không có phần tử gửi hướng/lot/SL/TP tùy ý; chỉ gọi GET và `POST /paper/orders` với `{at}`.
* Chạy thật (thủ công, ghi ảnh): quyết định hiện đúng như script kiểm toán tạm khi cùng dữ liệu đóng.
