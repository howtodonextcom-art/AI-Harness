# Benchmark tính năng trading bot / nền tảng algo-trading cho XAU EDGE

Ngày kiểm tra: 2026-10-09. Phạm vi: rút ý tưởng KIẾN TRÚC và TÍNH NĂNG, không sao chép chiến lược. XAU EDGE là nền tảng research-first, fail-closed, hỗ trợ quyết định XAUUSD, có lớp thực thi MT5 DEMO có bảo vệ, không dùng tiền thật.

Quy ước: chỉ ghi điều đọc được từ trang đã tải. Mô tả được rút gọn từ nội dung WebFetch (bản tóm tắt tự động), nên chi tiết tham số cần đối chiếu lại tài liệu gốc trước khi code. Ô ghi "chưa xác minh bằng trang hiện tại" nghĩa là trang tải lỗi (404) hoặc không nêu rõ.

Trang tải lỗi / không có nội dung hữu ích trong lần kiểm tra này: MQL5 `symbolproperties`, `accountinformation` (đường dẫn tradingconstants), `marginmode`; QuantConnect `order-types/key-concepts` và `consolidating-data` (404); Jesse `docs.jesse.trade/docs/` (404) và trang Strategy API không mô tả `should_long/go_long/stop_loss`.

## 1. Bảng benchmark

| Feature | Platform | How it works | Useful for XAU EDGE? | Adopt / Adapt / Reject | Reason |
|---|---|---|---|---|---|
| Multi-timeframe / informative data, merge HTF không look-ahead | Freqtrade | `@informative()` hoặc `merge_informative_pair()` đổi tên cột (vd `rsi_1h`) và forward-fill sang timeframe nhỏ; docs cảnh báo không dùng `shift(-1)`/giá trị âm | Có | Adapt | Lấy nguyên tắc: HTF chỉ khả dụng sau khi nến đóng; ta cần as-of join theo thời điểm đóng nến, không theo thời điểm mở |
| Multi-timeframe | Backtrader | Thêm data từ timeframe nhỏ đến lớn, `resampledata()`; `next` chỉ gọi khi mọi indicator có giá trị; docs nêu cần căn chỉnh datetime | Một phần | Reject (cơ chế), Adopt (cảnh báo warm-up) | Cơ chế resample lồng trong engine không đảm bảo no-lookahead tường minh; warm-up theo indicator chậm nhất là bài học hợp lệ |
| Multi-timeframe | Jesse | `get_candles()` truy cập timeframe khác route chính | Một phần | Adapt | Chỉ xác minh có API này; cách xử lý look-ahead: chưa xác minh bằng trang hiện tại |
| Multi-timeframe / consolidators | QuantConnect LEAN | chưa xác minh bằng trang hiện tại (trang consolidating-data 404) | Không rõ | Chưa quyết | Không đưa vào quyết định |
| Multi-timeframe | Qlib | Data layer với Point-in-Time database | Có (ý tưởng) | Adapt | Khái niệm point-in-time: mọi feature phải tái dựng được "tại thời điểm T" |
| Signal generation interface | Freqtrade | `populate_indicators` / `populate_entry_trend` / `populate_exit_trend`, cột `enter_long`, `exit_long`... vector hóa | Có | Adapt | Tách rõ indicator -> signal -> exit; nhưng ta cần tín hiệu có trạng thái (lý do, evidence), không chỉ cột boolean |
| Signal generation interface | QuantConnect LEAN | Algorithm Framework 5 module: Universe, Alpha (Insight), Portfolio Construction (PortfolioTarget), Risk Management, Execution; "separation of concerns" | Có | Adopt (cấu trúc) | Pipeline Alpha -> Target -> Risk -> Execution khớp với decision pipeline fail-closed của ta; Risk đứng giữa Alpha và Execution |
| Signal generation interface | NautilusTrader | Strategy -> ExecutionEngine -> RiskEngine -> ExecutionClient; RiskEngine kiểm tra trước khi gửi | Có | Adopt | Risk gate bắt buộc trước submit, không thể bỏ qua |
| Signal generation interface | Backtrader | `Strategy.next()` + `notify_order()` | Thấp | Reject | Kiểu event-per-bar cũ, repo lớn nhưng README không nêu trạng thái bảo trì; không dùng làm nền |
| Signal generation interface | Qlib | Workflow `qrun`, model zoo (LightGBM, LSTM...), RD-Agent | Một phần | Adapt | Chỉ lấy ý tưởng workflow nghiên cứu tái lập (config -> dataset -> model -> backtest -> report); không nhúng ML vào đường quyết định |
| Order lifecycle states | NautilusTrader | Local: Initialized/Emulated/Released; in-flight: Submitted/PendingUpdate/PendingCancel; open: Accepted/Triggered/PartiallyFilled; terminal: Denied/Rejected/Canceled/Expired/Filled/Voided | Có | Adopt | State machine tường minh với terminal states; dùng làm mẫu cho order ledger |
| Order lifecycle states | Backtrader | Created, Submitted, Accepted, Partial, Complete, Rejected, Margin, Cancelled, Expired | Có | Adapt | Tập tối thiểu tham khảo; thêm "Denied by our risk gate" như Nautilus |
| Order lifecycle states | MT5 (MQL5) | Order states STARTED, PLACED, PARTIAL, FILLED, REJECTED, EXPIRED, REQUEST_ADD/MODIFY/CANCEL; `OnTradeTransaction` có thể bắn nhiều lần, thứ tự không đảm bảo | Có (bắt buộc) | Adopt | Phải tự dựng state machine từ request/result/deal/position, không tin một lần gọi |
| Order lifecycle states | QuantConnect LEAN | chưa xác minh bằng trang hiện tại (404) | Không rõ | Chưa quyết | |
| Stop loss: static, trailing, on-exchange vs in-bot | Freqtrade | 5 kiểu: static, trailing, trailing có positive offset, trailing kích hoạt theo offset, custom function; `stoploss_on_exchange` kiểm tra mỗi 60s; `emergency_exit` khi tạo stoploss sàn thất bại | Có | Adopt | SL phải nằm trên server (gắn vào position MT5), không chỉ trong bot; có đường emergency khi sửa SL lỗi |
| Stop loss | MT5 | SL/TP gắn vào position, sửa bằng `TRADE_ACTION_SLTP` (cần action, symbol, sl, tp, position) | Có (bắt buộc) | Adopt | Server-side SL là mặc định; hedging cần position ticket |
| Stop loss | Jesse | `stop_loss`/`take_profit` là hook chiến lược (tên có trong tài liệu khác) | Không rõ | Chưa quyết | chưa xác minh bằng trang hiện tại |
| Stop loss | QuantConnect LEAN | Risk model có TrailingStop | Một phần | Adapt | Đặt trailing như một risk module độc lập, không lẫn trong alpha |
| Take profit / ROI table | Freqtrade | `minimal_roi` theo thời gian giữ; `custom_roi()`; khi cả hai bật, ngưỡng thấp hơn kích hoạt | Một phần | Adapt | Không dùng ROI cố định %, dùng TP theo R-multiple/ATR; ý "ngưỡng giảm dần theo thời gian giữ" dùng cho time-stop |
| Trailing stop | Freqtrade | Trailing %, offset kích hoạt | Có | Adapt | Dùng ATR/structure-based trailing, kích hoạt sau ngưỡng R |
| Trailing stop | NautilusTrader | Trailing-Stop order variants điều chỉnh trigger theo offset, có trigger type (last, bid-ask, mid, mark) | Có | Adapt | Với MT5 phải tự trailing bằng SLTP modify (có stops/freeze level), không có lệnh trailing gốc đã xác minh |
| Break-even | Freqtrade | Làm bằng `custom_stoploss` / trailing có offset (docs mô tả kiểu "lock in gains"); không có tính năng break-even riêng được xác minh | Có | Adapt | Break-even là một stage của SL engine, kèm buffer cho spread |
| Break-even / partial / trailing | MQL5-Trading-Bot (GitHub) | Đóng 50% ở +50 pips, trailing chỉ bật sau +50 pips, 30 pips trail | Một phần | Adapt (ý tưởng) | Chỉ lấy cấu trúc "partial rồi trailing"; tham số của họ viết cho EURUSD, không dùng cho XAU |
| Risk-based position sizing | Freqtrade | `custom_stake_amount()` | Một phần | Adapt | Ta cần sizing theo rủi ro tiền / khoảng SL, không theo stake |
| Risk-based position sizing | MQL5-Trading-Bot | Lot = RiskAmount / (SL distance x TickValue), làm tròn min/max/step | Có | Adopt | Đúng công thức nền; phải lấy tick value/size từ `symbol_info`, và kiểm lại rủi ro thực sau khi làm tròn lot |
| Risk-based position sizing | mt5-trading-system (GitHub) | Post-mortem: lot step 0.01 khiến 55.3% lệnh vượt trần rủi ro 1%, đỉnh 2.56% equity khi tài khoản nhỏ lại | Có | Adopt (bài học) | Sau khi làm tròn lot phải tính lại risk thực và từ chối nếu vượt trần (fail-closed), không làm tròn lên |
| Risk-based position sizing | Backtrader / Nautilus | Backtrader có sizers; Nautilus RiskEngine kiểm quantity bounds, notional limits, account balance impact | Một phần | Adapt | Lấy ý niệm kiểm tra notional/balance impact trước submit |
| Cooldown / protections | Freqtrade | Protections: StoplossGuard (số stoploss trong lookback -> khóa `stop_duration`), MaxDrawdown (ratio hoặc equity curve), CooldownPeriod (khóa sau khi thoát), LowProfitPairs (lợi nhuận tích lũy dưới `required_profit`); làm tròn tới nến kế | Có | Adopt | Mô hình khóa có thời hạn, có lý do, ghi vào journal; LowProfitPairs ở mức mã chỉ tương ứng "khóa theo setup/regime" |
| Daily loss guard | mt5-trading-system (GitHub) | Post-mortem: cap ngày bắn 58 lần mà không dừng; 373/696 lệnh xảy ra sau lần bắn đầu | Có | Adopt (bài học) | Circuit breaker phải là trạng thái chốt (latched) chặn mọi submit mới, có test chứng minh |
| Daily loss guard | Feihassan/trading-bot, MQL5-Trading-Bot, Quantum XAUUSD EA (MQL5) | Giới hạn loss ngày/tuần, max drawdown halt, max open trades, trades-per-day, daily drawdown mặc định 5% | Có | Adopt | Đồng thuận phổ biến; ta thêm ngưỡng theo equity và reset theo ngày broker server |
| Kill switch / emergency exit | NautilusTrader | Trading state ACTIVE / REDUCING (chỉ reduce-only) / HALTED (chỉ cancel và query) | Có | Adopt | Ba trạng thái này mô tả rất gọn kill switch của ta |
| Kill switch / emergency exit | Freqtrade | `/forceexit` thủ công; emergency exit khi stoploss sàn lỗi hoặc timeout exit vượt `exit_timeout_count`, mặc định market order; điều khiển qua Telegram/WebUI | Có | Adapt | Có force-exit thủ công và emergency path, nhưng ta chỉ hành động trên DEMO và ghi rõ lý do |
| Kill switch | Feihassan/trading-bot | Risk manager "không thể bypass", LLM chỉ được hạ xuống WAIT, không được tạo hay nâng lệnh | Có | Adopt | Quy tắc "lớp AI/LLM chỉ được làm chặt thêm, không nới" phù hợp fail-closed |
| Position reconciliation khi restart | NautilusTrader | Reconciliation liên tục khi startup; ExecutionEngine dựng lại positions, phát hiện overfill/duplicate fill | Có | Adopt | Khi khởi động phải đọc positions/orders từ MT5 làm nguồn sự thật, so với ledger nội bộ, lệch thì HALT |
| Position reconciliation khi restart | Freqtrade | Kiểm tra order tồn tại khi startup (`skip_open_order_update` mặc định false); dry-run giữ open orders qua restart | Có | Adapt | Cùng ý tưởng, ta thêm kiểm tra magic/comment để nhận diện lệnh của ta |
| Position reconciliation | MT5 | `POSITION_IDENTIFIER` giữ nguyên suốt vòng đời; ở netting khi đảo chiều ticket đổi nhưng identifier không đổi | Có | Adopt | Key theo identifier, không theo ticket |
| Partial close / scale-out | Freqtrade | `adjust_trade_position()`: giá trị dương tăng, âm giảm vị thế (DCA, partial exit) | Một phần | Adapt (chỉ nửa giảm) | Chỉ dùng scale-out; nửa "tăng" là DCA, bị cấm mặc định (xem mục 3) |
| Partial close / scale-out | MQL5-Trading-Bot | Đóng 50% ở ngưỡng cố định, rồi trailing phần còn lại | Một phần | Adapt | Phần còn lại phải kế thừa SL không xấu hơn break-even |
| Partial close | Nautilus | Reduce-only orders | Có | Adopt | Lệnh đóng một phần luôn đánh dấu reduce-only trong logic nội bộ |
| Session filters | Feihassan/trading-bot | Session windows, cửa sổ giao dịch theo phiên | Có | Adopt | Lọc phiên cho XAU (London/NY, rollover) |
| Session filters | MQL5-Trading-Bot | Kill zone London 8-10 GMT, New York 13-15 GMT | Có | Adapt | Tham số phải rút ra từ dữ liệu XAU của ta, không lấy của họ |
| Session filters | Freqtrade / Nautilus / LEAN / Jesse / Backtrader | chưa xác minh bằng trang hiện tại (không thấy tính năng session filter trong các trang đã đọc) | Không rõ | Chưa quyết | |
| Spread filters | Freqtrade | Pairlist `SpreadFilter`: loại cặp có spread vượt `max_spread_ratio` (mặc định 0.005) | Có | Adapt | Ngưỡng tương đối so với ATR/SL, không dùng tỉ lệ cố định |
| Spread filters | Feihassan/trading-bot | Phát hiện spread bất thường so với median, không dùng ngưỡng cố định; stale-data guard | Có | Adopt | Median-relative + stale tick guard rất hợp XAU |
| Spread filters | MQL5-Trading-Bot | Spread tối đa 30 points | Một phần | Reject (giá trị) | Hằng số cố định, không tổng quát hóa |
| Spread filters | mt5-trading-system (GitHub) | Spread chiếm 6.96% đến 24.87% của ngân sách 1R (median), chiếm 302.31 USD trên khoản lỗ ròng 454.56 USD | Có | Adopt (bài học) | Guard theo "spread / khoảng SL" và từ chối khi vượt ngưỡng |
| Slippage / fill models | Backtrader | `set_slippage_perc`, `set_slippage_fixed`, các cờ `slip_open`, `slip_match`, `slip_limit`, `slip_out`; ví dụ số lệnh khớp giảm từ 35 xuống 13 khi tắt `slip_match` | Có | Adapt | Mô hình slippage tham số hóa; cho phép "không khớp" khi vượt giới hạn |
| Slippage / fill models | QuantConnect LEAN | SetSlippageModel; mô hình fill, fee, buying power riêng; brokerage mặc định dùng NullSlippageModel (zero slippage) | Có | Adopt (cảnh báo) | Mặc định zero slippage là bẫy; ta bắt buộc slippage > 0 và ghi rõ trong report |
| Slippage / fill models | NautilusTrader | Fill model cấu hình được (slippage, khớp xác suất), matching tất định, bar execution (OHLC sequencing) | Có | Adapt | Ý tưởng khớp xác suất và OHLC sequencing có ích cho paper loop |
| Slippage / fill | Freqtrade dry-run | Market order khớp theo orderbook, slippage tối đa 5%; limit order khớp khi giá chạm hoặc hết `unfilledtimeout` | Một phần | Adapt | Giả lập fill dùng bid/ask thật, không dùng giá mid |
| Slippage / fill | MT5 | `deviation` (points) trong request; retcode REQUOTE / REJECT / INVALID_FILL | Có (bắt buộc) | Adopt | Dùng deviation làm trần slippage, ghi slippage thực đo được từ deal |
| News / event guards | tất cả nền tảng đã đọc | chưa xác minh bằng trang hiện tại (không thấy tính năng news guard trong các trang tài liệu nền tảng đã đọc); Quantum XAUUSD EA ghi rõ không có spread/session/news filter | Có (cần) | Adopt (tự xây) | Calendar-based blackout và spread/volatility spike guard ta phải tự dựng; đừng giả định nền tảng nào có sẵn |
| Trade journal / persistence | Freqtrade | `db_url` SQLite (`tradesv3.sqlite`, dry-run riêng) | Có | Adapt | Có DB trade; ta cần thêm decision log |
| Trade journal | Feihassan/trading-bot | JSONL append-only: lý do vào lệnh, stop, kết quả | Có | Adopt | Append-only, một dòng mỗi sự kiện, có reason code |
| Trade journal | mt5-trading-system (GitHub) | SQLite ledger đầy đủ cho phép dựng lại mọi lỗi; backtest harness có bootstrap CI và null-control | Có | Adopt | Journal đủ để post-mortem; null-control là ý tưởng test tốt |
| Backtest-live parity, lookahead/recursive analysis | Freqtrade | `lookahead-analysis`: chạy backtest cơ sở và theo từng cặp, so sánh indicator/tín hiệu, khác biệt chỉ ra look-ahead; `recursive-analysis`: tính lại indicator với số nến startup khác nhau, so sánh giá trị cuối | Có | Adopt | Dựng test tương đương: tái tính feature với cắt dữ liệu tại T và so sánh với tính trên toàn chuỗi |
| Backtest-live parity | NautilusTrader | Dùng cùng thành phần lõi (engines, Cache, MessageBus, Portfolio, Strategies...) cho backtest và live | Có | Adopt | Một đường code cho research, paper và demo; khác nhau chỉ ở adapter |
| Backtest-live parity | QuantConnect LEAN | README nêu chuyển từ `lean backtest` sang `lean live` | Có | Adopt (nguyên tắc) | Cùng nguyên tắc; chi tiết chưa xác minh sâu |
| Backtest-live parity | vectorbt | Vector hóa, kiểm hàng nghìn cấu hình nhanh; bản open-source docs không nêu stop orders; PRO có limit orders, leverage | Một phần | Reject (làm engine kiểm chứng), Adapt (làm công cụ quét sơ bộ) | Vector hóa nhanh nhưng không mô hình vòng đời lệnh; chỉ dùng khám phá, kết quả phải xác nhận lại bằng engine event-driven |
| Backtest-live parity | Qlib | Backtest với metric (Sharpe, IC, max drawdown), nested decision execution, online serving | Một phần | Adapt | Ý tưởng evaluate theo IC và báo cáo; không đưa vào đường quyết định |
| Dry-run / paper mode | Freqtrade | Dry-run với ví giả `dry_run_wallet` (mặc định 1000) | Có | Adopt | Paper loop chạy cùng pipeline, chỉ khác adapter |
| Dry-run / paper mode | Feihassan/trading-bot | 3 chế độ: DRY_RUN (chỉ log tín hiệu), DEMO, LIVE (cần xác nhận kép) | Có | Adopt (DRY_RUN, DEMO), Reject (LIVE) | Ta chỉ có hai chế độ đầu; LIVE không tồn tại trong code |
| Idempotent order submission | NautilusTrader | `client_order_id` hợp lệ bắt buộc, `trade_id` ổn định để khử trùng lặp giữa kênh realtime và reconciliation; ID sai bị DENIED | Có | Adopt | Mỗi quyết định có `decision_id` duy nhất, lưu vào comment/magic của lệnh MT5 và khóa chống gửi lại |
| Idempotent order submission | MT5 | `OrderSend` trả `true` chỉ là kiểm cấu trúc, phải xem `retcode`; xử lý bất đồng bộ có thể sau khi hàm trả về; `OrderSendAsync` tồn tại | Có (bắt buộc) | Adopt | Sau mỗi send, truy vấn positions/orders theo `decision_id` trước khi coi là thất bại hoặc thử lại |
| Idempotent submission | Freqtrade | chưa xác minh bằng trang hiện tại | Không rõ | Chưa quyết | |

## 2. MT5 specifics to respect

Tất cả mục dưới đây đã đọc từ docs MQL5/Python MT5 hiện tại, trừ khi nêu khác.

- Tick value / contract size / volume: lấy từ `symbol_info`/`SymbolInfoDouble` (`SYMBOL_TRADE_TICK_SIZE`, `SYMBOL_TRADE_TICK_VALUE`, `SYMBOL_TRADE_CONTRACT_SIZE`, `SYMBOL_VOLUME_MIN`, `SYMBOL_VOLUME_STEP`). Không hard-code giá trị cho XAUUSD; kiểm tra lại mỗi phiên vì broker khác nhau. Docs mô tả `SYMBOL_TRADE_TICK_VALUE` chỉ là "Value of SYMBOL_TRADE_TICK_VALUE_PROFIT"; tick value cho lỗ (loss) là thuộc tính riêng, cần xác minh khi code.
- Stops level: `SYMBOL_TRADE_STOPS_LEVEL` = khoảng cách tối thiểu (points) từ giá hiện tại để đặt lệnh stop. SL/TP phải cách giá đủ xa; SL sai phía/khoảng cách gây `TRADE_RETCODE_INVALID_STOPS` (10016).
- Freeze level: `SYMBOL_TRADE_FREEZE_LEVEL` = khoảng cách mà tại đó thao tác giao dịch bị đóng băng; `TRADE_RETCODE_FROZEN` (10029). Chưa tìm được trang mô tả chi tiết cách áp dụng cho SL/TP modify; cần đọc thêm trước khi code vòng sửa SL (chưa xác minh bằng trang hiện tại).
- Filling mode: đọc `SYMBOL_FILLING_MODE` (cờ FOK/IOC/BOC/Return) trước khi chọn `type_filling`; `ORDER_FILLING_RETURN` bị vô hiệu ở Market Execution; chọn sai gây `TRADE_RETCODE_INVALID_FILL` (10030).
- `order_check` trước `order_send`: kiểm tiền ký quỹ và tính hợp lệ tham số, trả `MqlTradeCheckResult` (retcode, balance, equity, margin, margin_free, margin_level, comment). Docs nhấn mạnh kết quả OK không đảm bảo khớp lệnh. Do đó: order_check -> order_send -> đọc retcode -> đối chiếu position.
- Retcodes cần xử lý: REQUOTE 10004, REJECT 10006, PLACED 10008, DONE 10009, DONE_PARTIAL 10010, INVALID_STOPS 10016, MARKET_CLOSED 10018, NO_MONEY 10019, FROZEN 10029, INVALID_FILL 10030. Mọi retcode lạ = coi là thất bại và fail-closed (không tự thử lại mù).
- Netting vs hedging: `ACCOUNT_MARGIN_MODE`: netting (một position mỗi symbol), hedging (nhiều position mỗi symbol), exchange. Phải đọc mode lúc khởi động và từ chối chạy nếu không đúng giả định. Hedging cần position ticket khi sửa/đóng; netting khi đảo chiều đổi ticket nhưng giữ `POSITION_IDENTIFIER`.
- Sửa SL/TP: `TRADE_ACTION_SLTP` cần action, symbol, sl, tp, position. Trước khi sửa phải kiểm stops level, freeze level và rằng SL mới không xấu hơn SL hiện tại (trừ khi là quyết định thoát có ghi lý do).
- Sự kiện giao dịch: `OnTradeTransaction` có thể sinh nhiều giao dịch cho một request và thứ tự không đảm bảo; nếu dùng Python polling thì phải đọc lại trạng thái, không suy luận từ thứ tự.
- Kiểm tra `ACCOUNT_TRADE_MODE_DEMO` trước khi cho phép bất kỳ order_send nào (fail-closed nếu không phải demo).

## 3. Cái gì KHÔNG nên làm

| Điều cấm | Lý do |
|---|---|
| Martingale (nhân lot sau lỗ) | Rủi ro tăng theo cấp số khi thua; XAU có gap/biến động lớn; phá trần rủi ro mỗi lệnh. Quantum XAUUSD EA và MQL5-Trading-Bot đều ghi rõ không dùng; ta giữ cùng lập trường |
| Grid (đặt lưới lệnh ngược xu hướng) | Gom vị thế âm không giới hạn, lỗ lớn đến một đợt trend; không có SL tổng rõ ràng |
| Averaging down / DCA vào vị thế đang lỗ | `adjust_trade_position` của Freqtrade cho phép tăng vị thế; ta chỉ dùng nửa giảm. Tăng rủi ro đúng lúc luận điểm đang sai |
| Pyramiding không giới hạn | Chỉ cho thêm lệnh khi có luật cứng: tối đa N lần, SL tổng không xấu hơn trần rủi ro ban đầu; mặc định tắt |
| News scalping (vào lệnh ngay lúc ra tin) | Spread giãn, slippage, requote, `INVALID_STOPS`/`FROZEN`; backtest dữ liệu bar không tái tạo được. Thay vào đó: blackout quanh tin |
| Indicator vote counting (đếm số indicator đồng ý) | Các indicator tương quan nên "phiếu" không độc lập; không có calibrated probability; khó giải thích và kiểm chứng. Quantum XAUUSD EA dùng weighted decision nhưng ta không lấy cách này. Dùng feature có kiểm chứng riêng và tổng hợp có hiệu chuẩn |
| Stop quá chật so với nhiễu và spread | Post-mortem mt5-trading-system: stop 0.06% giá, spread chiếm đa số khoản lỗ, mất 82% demo trong 21 giờ; mở rộng stop lên 0.3-0.5% cho kết quả tốt hơn trong harness của họ (đây là kết quả của họ, không phải bằng chứng cho XAU của ta) |
| Circuit breaker mang tính trang trí | Cap bắn nhưng vẫn cho gửi lệnh (58 lần trong post-mortem trên); cap phải latched |
| Nới guard bằng LLM/ML | Feihassan/trading-bot cho LLM chỉ hạ xuống WAIT; ta giữ nguyên tắc đó |
| Tin kết quả nền tảng có slippage mặc định bằng 0 | LEAN mặc định NullSlippageModel |

## 4. Hệ quả thiết kế cho XAU EDGE

1. Market-state engine: tính feature theo nguyên tắc as-of (HTF chỉ khả dụng sau khi nến đóng), kèm warm-up bắt buộc theo indicator chậm nhất; lưu "phiên bản dữ liệu tại T" kiểu point-in-time (Freqtrade informative, Backtrader warm-up, Qlib PIT).
2. Decision pipeline: tách Signal -> Target -> Risk -> Execution như LEAN Framework; Risk là cổng bắt buộc cuối (NautilusTrader RiskEngine); mọi lớp ML/LLM chỉ được làm chặt thêm (Feihassan).
3. Order state machine: mượn tập trạng thái của Nautilus (Initialized/Submitted/Accepted/PartiallyFilled/Filled và terminal Denied/Rejected/Canceled/Expired) cộng trạng thái nội bộ "Denied by risk"; trạng thái chỉ đổi dựa trên dữ liệu MT5 đọc lại.
4. SL engine: SL luôn gắn vào position phía server MT5; các giai đoạn static -> break-even (có buffer spread) -> trailing (ATR/structure, bật sau ngưỡng R); mỗi lần sửa kiểm stops/freeze level và "không nới SL".
5. TP engine: TP theo R-multiple/cấu trúc; thêm time-stop theo ý tưởng ROI giảm dần theo thời gian giữ; không dùng bảng ROI % cố định.
6. Position sizing: Lot = RiskAmount / (SL distance x tick value) với tick value/size từ `symbol_info`; sau khi làm tròn theo volume step tính lại risk thực, từ chối nếu vượt trần (bài học lot granularity).
7. Position manager + reconciliation: khi khởi động đọc positions/orders MT5 (key theo `POSITION_IDENTIFIER`, nhận diện bằng magic/comment), so với ledger; lệch thì HALT; scale-out chỉ giảm, mặc định không có tăng vị thế.
8. Guards: spread guard tương đối (median-relative và spread/khoảng SL), stale tick guard, volume/liquidity guard, session filter rút từ dữ liệu XAU, news blackout tự xây; protections kiểu Freqtrade (StoplossGuard, MaxDrawdown, Cooldown) có thời hạn và lý do.
9. Kill switch ba trạng thái ACTIVE / REDUCING / HALTED (Nautilus), latched, có test chứng minh không còn submit sau khi HALTED; daily loss tính theo equity và ngày server broker.
10. Paper loop và demo loop dùng chung một đường code với backtest, chỉ khác adapter (Nautilus parity); paper fill dùng bid/ask thật, slippage > 0 bắt buộc, có khả năng "không khớp" khi vượt `deviation`.
11. Journal: append-only JSONL cho decision log (mỗi quyết định kể cả NO-TRADE có reason code) cộng SQLite ledger cho lệnh/deal; đủ để dựng lại post-mortem như mt5-trading-system; `decision_id` duy nhất đưa vào comment lệnh để idempotent, trước khi retry phải truy vấn theo `decision_id`.
12. Parity tests: test kiểu lookahead-analysis (tính feature trên cắt tại T so với trên toàn chuỗi) và recursive-analysis (đổi số nến startup, so sánh giá trị cuối), chạy trong CI; thêm null-control và bootstrap CI cho kết quả research.
13. Preflight MT5: kiểm tra `ACCOUNT_TRADE_MODE_DEMO`, margin mode, `SYMBOL_FILLING_MODE`, stops/freeze level, `order_check` trước mọi `order_send`; retcode lạ -> fail-closed.

## 5. Ghi chú về các bot GitHub/MQL5 đã đọc (chỉ lấy kiến trúc)

- Feihassan/trading-bot: DRY_RUN/DEMO/LIVE, risk manager không thể bypass, spread median-relative, JSONL journal; khẳng định không martingale/grid. Chỉ đọc README, chưa kiểm mã nguồn.
- JoshRiang/mt5-trading-system: harness nghiên cứu và post-mortem mất 82% tài khoản demo (nêu 5 nguyên nhân ở trên). Bot có chiến lược `gamble_multi_v3` (tên chiến lược, chưa xác minh nội dung); dùng Kelly sizing, đây là điểm cần thận trọng với ta. Số liệu là tự công bố của repo.
- carlosrod723/MQL5-Trading-Bot: EA OnTick, new-bar detection, lot theo tick value, partial exit, trailing, spread filter, kill zone; tự nhận không martingale/grid. Số liệu hiệu suất (29.8% năm, 5.2% DD, EURUSD 2024) do tác giả tự công bố, chưa kiểm chứng, không dùng làm bằng chứng.
- Quantum XAUUSD Silver Trader (mql5.com/en/code/73622): ATR SL/TP, ATR trailing, giới hạn daily/total drawdown, trần cỡ vị thế; ra quyết định kiểu trọng số nhiều indicator và trọng số thích nghi theo kết quả gần đây (rủi ro overfit, không lấy); không có spread/session/news filter.
- Không bot nào trong số trên được chạy hoặc kiểm tra mã; chỉ dựa trên README/trang mô tả.

## Nguồn (đã tải trong lần kiểm tra này)

- https://www.freqtrade.io/en/stable/strategy-customization/
- https://www.freqtrade.io/en/stable/strategy-callbacks/
- https://www.freqtrade.io/en/stable/plugins/
- https://www.freqtrade.io/en/stable/stoploss/
- https://www.freqtrade.io/en/stable/lookahead-analysis/
- https://www.freqtrade.io/en/stable/recursive-analysis/
- https://www.freqtrade.io/en/stable/configuration/
- https://github.com/freqtrade/freqtrade
- https://nautilustrader.io/docs/latest/concepts/orders/
- https://nautilustrader.io/docs/latest/concepts/execution/
- https://nautilustrader.io/docs/latest/concepts/backtesting/
- https://github.com/quantconnect/lean
- https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/slippage/key-concepts
- https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/overview
- https://www.backtrader.com/docu/order/
- https://www.backtrader.com/docu/slippage/slippage/
- https://www.backtrader.com/docu/data-multitimeframe/data-multitimeframe/
- https://github.com/mementum/backtrader
- https://docs.jesse.trade/docs/strategies/api.html
- https://vectorbt.dev/
- https://github.com/microsoft/qlib
- https://www.mql5.com/en/docs/constants/tradingconstants/enum_trade_request_actions
- https://www.mql5.com/en/docs/trading/ordercheck
- https://www.mql5.com/en/docs/trading/ordersend
- https://www.mql5.com/en/docs/constants/tradingconstants/orderproperties
- https://www.mql5.com/en/docs/constants/structures/mqltraderequest
- https://www.mql5.com/en/docs/constants/errorswarnings/enum_trade_return_codes
- https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants
- https://www.mql5.com/en/docs/constants/environment_state/accountinformation
- https://www.mql5.com/en/docs/constants/tradingconstants/positionproperties
- https://www.mql5.com/en/docs/python_metatrader5/mt5ordercheck_py
- https://www.mql5.com/en/docs/basis/function/events
- https://www.mql5.com/en/code/73622
- https://github.com/Feihassan/trading-bot
- https://github.com/JoshRiang/mt5-trading-system
- https://github.com/carlosrod723/MQL5-Trading-Bot
