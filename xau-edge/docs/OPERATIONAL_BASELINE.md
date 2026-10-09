# Baseline vận hành (UNVALIDATED_OPERATIONAL_BASELINE)

## Nó là gì, không là gì

Một bộ quy tắc minh bạch (`xau_mtf_baseline`, phiên bản `1.1.0`) để **vận hành** toàn bộ đường ống quyết định → kế hoạch lệnh → rủi ro → paper → journal → cảnh báo trên dữ liệu thật, thu tín hiệu forward và đo thực thi. Nó **không** phải edge đã kiểm chứng.

Bằng chứng nghiên cứu hiện có (không đổi bởi sprint này): Edge Program V1 = NO EDGE WITHIN BUDGET; V2 Batch A 0/20 qua Stage 1; Test-H và Holdout chưa mở. Nhãn `UNVALIDATED_BASELINE` hiển thị trên quyết định, trang `/trade`, journal và mọi cảnh báo. Giao diện không có phần trăm "độ tin cậy".

## Quy tắc (cấu hình trong `BaselineConfig`, đóng băng theo `STRATEGY_VERSION`)

1. **Thị trường/dữ liệu**: thị trường mở, mọi khung cần thiết tươi, quote tươi (≤30 s), collector sống (≤60 s), `symbol_spec` của broker có thật. Thiếu ⇒ WAIT (`STALE_DATA`, `MARKET_CLOSED`, `UNKNOWN_STATE`).
2. **H4 REGIME**: chặn khi ngược xu hướng H4 mạnh hoặc chế độ `SHOCK`/`HIGH_VOLATILITY`.
3. **H1 DIRECTION**: BULLISH ⇒ chỉ BUY, BEARISH ⇒ chỉ SELL; RANGE ⇒ `NO_DIRECTION`. M15 ngược H1 ⇒ `TIMEFRAME_CONFLICT`.
4. **M15 SETUP**: pullback trong xu hướng (`NO_SETUP` nếu không).
5. **M5 TRIGGER**: động lượng/phá cấu trúc theo hướng H1 (`NO_TRIGGER`).
6. **M1 EXECUTION**: spread rộng so với biến động, tick volume QUIET (`VOLUME_TOO_LOW`), biến động bất thường ⇒ chặn. M1 không bao giờ đảo hướng H1.
7. **Cấu trúc**: cách kháng cự/hỗ trợ đối diện ≥ 1 ATR(M15) (`TOO_CLOSE_TO_RESISTANCE/SUPPORT`).
8. **Kế hoạch**: SL hybrid (cấu trúc/ATR, ≤3 ATR), TP 2R bị chặn bởi cấu trúc, **R/R ròng sau spread ≥ 1.5** (`RR_TOO_LOW`), SL ≥ `stops_level` của broker (`INVALID_STOP_DISTANCE`).
9. **Rủi ro**: lot từ rủi ro % (0.10/0.25/0.50), làm tròn xuống; không đủ `volume_min` ⇒ `RISK_LIMIT`.
10. **Tin tức**: không có lịch kinh tế ⇒ `NEWS_UNKNOWN`. Cho phép PAPER với cảnh báo hiển thị **NEWS NOT VERIFIED** (không được ngầm coi là an toàn); tự động DEMO phải giữ `allow_unknown_news=False`.

## Tick volume

Chỉ số hoạt động của giá (số lần đổi giá), chuẩn hóa theo từng khung (z-score, percentile, tỉ lệ so với trung bình, gia tốc). Volume cao một mình không tạo BUY/SELL; QUIET chặn, HIGH chỉ cải thiện `entry_quality`. Không bao giờ trình bày như volume sàn.

## Quản lý vị thế

Governor: tối đa 1 lệnh mở, ≤2 lệnh/giờ, ≤3/phiên, ≤6/ngày, cooldown 30 phút sau lệnh thua (240 phút sau chuỗi 3 thua), dừng lệnh mới khi lỗ ngày ≥2%. Break-even/trailing/đóng khi vô hiệu: mặc định TẮT. Thoát theo SL/TP/thời gian (120 phút)/thủ công.

## Quy tắc cấm sửa

* Không nới ngưỡng vì "ít BUY/SELL". WAIT chiếm đa số là hành vi dự kiến (xem `docs/reports/TRADING_CORE_ACCEPTANCE.md` cho tần suất đo được).
* Mọi thay đổi tham số = tăng `STRATEGY_VERSION` + replay lại trên dữ liệu đã đốt + ghi nhận; dữ liệu Test-H/Holdout không được dùng để chỉnh.
* Không tối ưu tham số trên kết quả paper (mẫu nhỏ, nhiễu).

## Điều kiện để nâng nhãn

Chỉ khi có đánh giá tiền đăng ký đủ công suất thống kê trên dữ liệu chưa chạm, theo giao thức của `docs/PROFITABILITY_ROADMAP.md`. Kết quả paper hằng ngày **không** đủ.
