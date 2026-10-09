# Báo cáo nghiệm thu Trading Desk MVP (TRADE-01/02)

Câu hỏi nghiệm thu: *chủ sở hữu có mở một trang và đưa ra quyết định PAPER có kỷ luật, minh bạch, rủi ro xác định trên dữ liệu FTMO sống không?* — **Có**: `/trade` hiển thị đủ (xem mục 2). Giới hạn trung thực: baseline đóng băng hiện **rất hiếm khi** ra BUY/SELL (mục 4).

## 1. Cổng chất lượng

| Cổng | Kết quả |
|---|---|
| ruff format / ruff check / mypy --strict (409 file) | xanh |
| pytest không-MT5 | 2421 passed, 1 skipped (symlink Windows), 3 deselected |
| MT5 read-only (`-m mt5`) | 3 passed (chỉ GET, không `order_send`) |
| Dashboard eslint / tsc / build | xanh |
| Playwright | 75 passed (11 test mới cho /trade, /journal; 60+ cũ) |
| CI từ xa trên HEAD cuối | xem mục 8 |

## 2. Màn hình /trade (đã kiểm bằng trình duyệt thật trên dữ liệu sống)

LIVE XAUUSD bid/ask/spread; BUY/SELL/WAIT; lý do (WAIT nêu chính xác mắt xích chặn); 6 khung với vai trò; tick volume (nhãn "not exchange volume"); Entry/SL/TP/R:R/lot theo 0.10/0.25/0.50%; nút paper 2 bước; vị thế paper mở với P&L/R; vốn paper giả lập; bằng chứng `CHƯA KIỂM CHỨNG`; `NEWS NOT VERIFIED`; khóa DEMO kèm lý do. Journal tại `/journal`. Điều hướng: Trade, Market, Journal, Research, System; `/` → `/trade`; trang cũ ở `/legacy` có banner deprecated.

## 3. Replay smoke (dữ liệu ĐÃ ĐỐT 2025-11-03 → 2025-12-01; không đụng Test-H/Holdout)

`scripts/trade_replay_smoke.py` từ chối cửa sổ ngoài 2025-05-01..2026-04-30.

| Chỉ số | Giá trị |
|---|---|
| Quyết định (mỗi lần đóng M5) | 5406 |
| BUY / SELL / WAIT | 0 / 0 / 5406 |
| Vi phạm bất biến kế hoạch (SL/TP sai phía, lot dưới min/sai bước, rủi ro > 0.5%) | 0 (không có kế hoạch nào được tạo; bất biến được kiểm thêm bằng unit test) |
| **Parity: toàn lịch sử vs đuôi cắt như live** | **0 khác biệt / 5406** |
| Thời gian | ~166 ms/quyết định (2 lần tính), ~86 ms (1 lần) |

Phễu chặn đầu tiên (mỗi quyết định đúng một lý do): VOLATILITY_TOO_LOW 1465, NO_SETUP 1311, VOLATILITY_TOO_HIGH 1015, NO_DIRECTION 423, TIMEFRAME_CONFLICT 277, NO_TRIGGER 245, SPREAD_TOO_WIDE 243, RR_TOO_LOW 9, TOO_CLOSE_TO_RESISTANCE 5, TOO_CLOSE_TO_SUPPORT 4. H1 có hướng ở 4056/5406 quyết định.

**Hạn chế**: vòng đời paper (mở→theo dõi→thoát) không được kích hoạt trong replay vì không có setup; nó được kiểm bằng 17 test `test_paper_desk.py` + test end-to-end engine (`paper_open` → `paper_close`, đóng lần hai bị từ chối) với giá tổng hợp. Chưa có lệnh paper nào chạy trên thị trường sống.

## 4. Phát hiện quan trọng: tần suất tín hiệu

Baseline v1.1.0 không ra setup nào trong 4 tuần dữ liệu đã đốt (và 0 trong 40 phút soak sống). Hai cổng biến động (thấp/cao theo phân vị ATR) chặn ~46% thời gian; NO_SETUP thêm 24%. **Không có tham số nào bị nới** (đúng ràng buộc). Hệ quả cho owner: bàn paper hoạt động đúng nhưng có thể nhiều ngày chỉ WAIT. Mọi thay đổi (ví dụ cổng biến động) phải là phiên bản cấu hình mới, replay trên dữ liệu đã đốt, và được ghi nhận — đó là quyết định của owner, không phải việc tinh chỉnh ngầm.

## 5. Soak dry-run sống (40 phút, 2026-10-09 12:57–13:37 UTC)

477 lần poll `GET /trade/decision`: 0 lỗi, 0 flicker (quyết định không đổi khi không có nến M1 mới), 0 vi phạm (không có kế hoạch actionable khi hết hạn/dữ liệu cũ/quote cũ; không có WAIT thiếu lý do; khóa DEMO luôn nói bàn paper không gửi lệnh). Độ trễ: median 27.5 ms, p95 159 ms, max 728 ms (lần tính lại). Telemetry ghi mỗi nến M1 đóng vào `data/trade/decisions-YYYYMMDD.jsonl`.

## 6. Hiệu năng (`scripts/trade_perf.py`, dữ liệu sống)

| Giai đoạn | median | p95 |
|---|---|---|
| Nạp thị trường (ledger tails + live.json) | 31 ms | 37 ms |
| Tính trạng thái thị trường (đặc trưng 6 khung) | 88 ms | 105 ms |
| Quyết định + kế hoạch lệnh + lot | <0.1 ms | <0.1 ms |
| Dựng JSON view | 3.9 ms | 6.9 ms |
| Bước không đổi (cache) | 6.8 ms | 8.9 ms |

Tính lại ~120 ms mỗi nến M1 đóng; đủ nhanh cho giao dịch thủ công, không cần tối ưu thêm.

## 7. Red team (15 tấn công)

| # | Tấn công | Kết quả / bằng chứng |
|---|---|---|
| 1 | Dữ liệu cũ tạo tín hiệu | Chỉ WAIT (`STALE_DATA`/`MARKET_CLOSED`), không actionable — `test_stale_data_can_only_produce_a_wait…` |
| 2 | Nến đang hình thành dùng như đã đóng | Không: `available_at <= now`, forming không nằm trong khung — `test_a_forming_bar_never_reaches…`, `test_market_state_ignores_bars_that_have_not_closed` |
| 3 | M1 ghi đè hướng H1 | M1 chỉ chặn — `test_m1_may_block_but_never_reverses_the_h1_direction` |
| 4 | Sai ngữ nghĩa volume | Luôn `TICK_VOLUME` + chú thích UI — `test_volume_is_always_labelled_tick_volume`, e2e |
| 5 | Sai lot | Từ tick_value broker, làm tròn xuống, không vượt rủi ro — `test_lots_come_from_tick_value_and_round_down`, `test_risk_calculator_*` |
| 6 | SL sai phía | Bất biến + sizing/levels tests; kiểm lại trong replay (`_plan_problems`) |
| 7 | TP sai phía | như trên |
| 8 | Tính sai RR | R/R ròng sau spread — `test_targets_are_r_multiples_capped_by_structure_and_judged_net_of_spread` |
| 9 | Thiếu spread/quote | Luôn WAIT có lý do — `test_a_missing_spread_or_quote_can_never_produce_a_trade` |
| 10 | Lệnh paper trùng | Một lệnh/setup, một vị thế — `test_one_order_per_setup_and_one_position_at_a_time`, sống qua restart |
| 11 | Đóng đôi | `NOT_OPEN` — `test_manual_close_requires_an_open_trade_and_cannot_repeat`, test end-to-end engine |
| 12 | Sai hết hạn | Neo vào nến M5 trigger; hết hạn ⇒ không actionable, desk từ chối `EXPIRED` — `test_an_expired_setup_is_not_actionable…` |
| 13 | Lệch múi giờ | Mọi mốc thời gian API là UTC có offset; hết hạn trùng biên M5 — `test_every_timestamp_the_api_serves_is_timezone_aware_utc`; broker clock ở lớp nạp |
| 14 | Journal thiếu provenance | `code_version`, ảnh quyết định, trạng thái thị trường, `setup_id` — `test_open_fills_at_the_ask…journals` |
| 15 | UI hiện BUY actionable khi dữ liệu cũ | **Tìm thấy và sửa**: UI từng chỉ dựa vào `actionable` của API; nay còn chặn khi tuổi dữ liệu >180 s hoặc quote cũ, nhãn "(dữ liệu cũ)" — e2e `a BUY on stale data…` |

Phát hiện khác trong quá trình: mũi tên "hướng" lệch nhãn trạng thái (H1 BULLISH hiện •) và percentile hiển thị sai thang — đã sửa (mức thấp). Không còn HIGH/CRITICAL mở. Lưu ý: đánh giá do chính tác nhân thực hiện (không dùng subagent vì không được yêu cầu), nên độc lập hạn chế.

## 8. `data/raw`

Luồng quyết định production không import/đọc `data/raw` (test cô lập). Phân loại phần còn lại:

| Nhóm | Ví dụ | Ghi chú |
|---|---|---|
| Nghiên cứu/backtest (giữ) | `run_backtest.py`, `run_models.py`, `run_analogue_study.py`, `benchmark_similarity.py`, `bench_cycle.py`, `trading_baseline_sanity.py`, `fetch_history.py`, `compact_raw.py` | lịch sử, không ra quyết định live |
| **Bot DEMO cũ (đóng băng)** | `scripts/demo_trader.py`, `forward_test.py`, `current_signal.py` | còn đọc `data/raw`; bot bị KHÓA (không mật khẩu trade/dry-run). Phải chuyển sang `data/market` trong sprint thực thi DEMO trước khi bật |
| API cũ | `/signals`, trang `/legacy`, `/patterns`, `/market/{symbol}` (research frames) | `/signals` đánh dấu deprecated (header `Deprecation`, trường `deprecated`, `successor`), tự ép WAIT + `stale` nếu dữ liệu cũ hơn 45 phút; `/legacy` có banner |

Kết luận: không còn phụ thuộc production của quyết định `/trade` vào `data/raw`; bot DEMO cũ vẫn phụ thuộc (đã khóa) và là blocker của sprint thực thi.

## 9. Tỉ lệ hoàn thành (không thổi phồng)

| Hạng mục | % |
|---|---|
| Trading Core engineering | 85 |
| Live-data wiring | 95 |
| Trade Plan | 90 |
| Risk calculator | 95 |
| Paper execution | 85 (chưa có lệnh paper sống thật nào) |
| Position management | 70 (BE/trailing có nhưng TẮT, chưa kiểm sống) |
| Alerting | 80 (Telegram chưa cấu hình ⇒ file) |
| Trader UI | 85 |
| **Edge validation** | **0** |

## 10. Còn lại cho owner

Cấu hình Telegram (tùy chọn); lịch tin tức/quy tắc tránh tin; quyết định về tần suất tín hiệu (mục 4); mật khẩu trade MT5 cho sprint thực thi DEMO.
