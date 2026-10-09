# Nền tảng dữ liệu thị trường MT5 (FTMO DEMO)

**Trạng thái: PARTIALLY READY** — mọi thành phần chạy và đã kiểm chứng trên terminal thật; "Max bars in chart" đã
nâng lên 10.000.000 và lịch sử sáu khung đã backfill đủ (từ 2004-06-11). Còn đúng 1 việc: một lần đăng xuất/đăng nhập
thật để xác minh tự khởi động (§7, §8). Bảng cổng ở cuối tài liệu.

Quyết định kiến trúc: `docs/adr/ADR-MT5-MARKET-DATA-PLATFORM.md`. Vận hành: `docs/operations/market-data-operations.md`.
Nghiên cứu: `docs/research/mt5-data-integration-options.md`, `tradingview-data-role.md`,
`unverified-claims-audit.md`. Báo cáo: `docs/reports/mt5-data-parity.md`, `mt5-spread-semantics.md`,
`mt5-tick-storage.md`, `mt5-backfill-final.md`, `mt5-chaos-tests.md`, `mt5-performance.json`.

## 1. Luồng dữ liệu

```
FTMO MT5 terminal (đã đăng nhập, DEMO)
 └─ ReadOnlyMt5Client (allowlist: chỉ hàm dữ liệu; guard DEMO có cache 30 s, lỗi không bao giờ cache)
     └─ Mt5Feed: quote, tick, nến, symbol, đồng hồ broker (NY+7)          market_data/mt5/feed.py
         └─ MarketCollector (supervisor chạy mãi, tự nối lại)             market_data/collector.py
             ├─ BarLedger   nến ĐÃ ĐÓNG, parquet theo tháng, khóa ghi      market_data/ledger.py
             ├─ TickLedger  tick thô, parquet theo ngày UTC + coverage     market_data/tick_ledger.py
             ├─ live.json (quote, nến đang hình thành, 200 tick gần nhất), collector_status.json
             └─ sự kiện BAR_CHANGED / GAP / RECONCILED / TICKS_CHANGED (events.jsonl, phân đoạn không xóa)
 API /md/* (chỉ GET, KHÔNG mở kết nối MT5, tự tính độ mới)              api/market_data.py
 └─ Web /market (nến + tick volume + spread + 6 viên trạng thái + chất lượng dữ liệu + múi giờ)
```

Dữ liệu ở `data/market/` (không vào git). Research/backtest/signal/paper/demo đọc cùng lớp nến chuẩn
(`domain/market.py`), mặc định chỉ nến đã đóng.

## 2. Quy tắc bất biến

* Chỉ nến đã đóng vào kho; nến đang hình thành ở `live.json`/UI, luôn `is_closed=false`.
* Nến vừa đóng chờ **20 giây** ổn định trước khi lưu (tick đến muộn vẫn có thể bổ sung). Một nến lưu quá sớm bị phát hiện
  bằng `BAR_CHANGED` (mỗi nến báo một lần) và chỉ được sửa bằng `scripts/repair_changed_bars.py --apply` (ghi `BAR_REPAIRED`
  với giá trị cũ/mới; nến đã sửa không còn tính là vấn đề).
* Không ghi đè nến/tick đã lưu; khác biệt → sự kiện (`BAR_CHANGED`, `TICKS_CHANGED`). Ghi nguyên tử dưới khóa
  liên tiến trình; chạy lại idempotent.
* Khối lượng là **tick volume**. `real_volume` là `UNVERIFIED_LEGACY_REAL_VOLUME` (chỉ khác 0 ở H1/H4 2012-03-28..
  2018-02-09): không hiển thị, không dùng. `last`/`volume` của tick luôn 0 với CFD vàng.
* Client dữ liệu không có `order_send`, `order_check`, `positions_get`, `orders_get`, `history_deals_get`,
  `history_orders_get`; test cấm tên hàm giao dịch. Tài khoản không DEMO → từ chối. Không mật khẩu/login/số dư.
* Thị trường đóng không phải lỗi dữ liệu; mở mà không có tick/nến mới → CŨ, không bao giờ im lặng là tốt.
* TradingView không phải nguồn dữ liệu; MT5 FTMO là nguồn thật duy nhất.

## 3. Lịch phiên FTMO

Đo thực tế (M1 từ 2026-06-30): đóng 16:50 và mở lại 18:05 giờ New York mỗi ngày (thứ Sáu 16:50 → Chủ nhật
18:05), theo giờ mùa hè/đông của Mỹ (broker = New York + 7 h cố định). Nằm trong `configs/brokers/ftmo_demo.yaml`.
Ngày lễ/đóng cửa sớm (ví dụ 2026-07-03 13:00 NY, 2026-09-07 14:30 NY) KHÔNG nằm trong mẫu tuần: chúng được suy ra
từ nến thiếu của chính broker (`scripts/infer_session_exceptions.py` → `configs/brokers/ftmo_session_exceptions.yaml`)
nhưng CHỈ chấp nhận khi khớp luật ngày lễ (Mỹ + Thứ Sáu Tốt lành, Giáng sinh, Năm mới; luật theo tháng/thứ, không
phải danh sách năm cố định). Khoảng thiếu không giải thích được vẫn là khoảng trống dữ liệu (`DATA_GAP`/`UNKNOWN`).
Quy tắc chặt: chỉ khoảng thiếu **liên tục ≥ 60 phút và ≤ 5 ngày** chạm ngày lễ mới thành cửa sổ đóng cửa; vài phút thiếu
của thị trường mỏng và lỗ hổng nhiều tuần không bao giờ bị coi là ngày lễ. Với lịch sử đầy đủ 2004→nay có 1.307 cửa sổ
(≈ 61 ngày lễ + 179 đóng cửa sớm theo M1). Kết quả: trong kỷ nguyên đã kiểm chứng (từ 2025) mọi bucket bị loại đều có lý
do (`HOLIDAY`, `EARLY_CLOSE`, `DATA_GAP` thật như sự cố CME 2025-11-28, hoặc biên dữ liệu); trước 2025 chúng ghi
`UNKNOWN` vì lịch broker cũ khác và nến M1/M5 thời kỳ đầu thưa (không thể dựng lại, không bịa). Xem
`docs/reports/mt5-data-parity.md`.

## 4. Chiều sâu lịch sử (đo 2026-10-09, sau khi nâng Max bars)

`[Charts] MaxBars` đã đổi 100000 → 10000000 và `scripts/mt5_set_max_bars.py --verify` xác nhận chính terminal báo
giá trị mới (không tin vào file). Backfill v2 (`scripts/backfill_mt5.py`): nến mới nhất rồi lùi theo khối bằng
`copy_rates_from`, xác thực từng khối, hash SHA-256 vào sự kiện, chạy lại/tiếp tục được, chống vòng lặp, trạng thái
trung thực. Kết quả: **cả sáu khung đều `BROKER_LIMITED`**, nghĩa là cap không còn chặn và broker không có gì cũ hơn.

| Khung | Local sớm nhất | Số nến | Trạng thái |
|---|---|---|---|
| M1 | 2004-06-11 04:18 UTC | 7.064.072 | BROKER_LIMITED (đủ) |
| M5 | 2004-06-11 04:15 | 1.499.955 | BROKER_LIMITED (đủ) |
| M15 | 2004-06-11 04:15 | 515.609 | BROKER_LIMITED (đủ) |
| M30 | 2004-06-11 04:00 | 260.713 | BROKER_LIMITED (đủ) |
| H1 | 2004-06-11 04:00 | 132.226 | BROKER_LIMITED (đủ) |
| H4 | 2004-06-11 01:00 | 34.232 | BROKER_LIMITED (đủ) |
| Tick | 2021-10-01 11:32 UTC | 205.083.656 | server giữ từ đó; đã lưu đủ |

Trước khi nâng: M1 chỉ tới 2026-06-29, M5 2025-05, M15 2022-07, M30 2018-05, H1 2010-02. Lưu ý: M1 thời kỳ đầu
(2004-2012) rất thưa (broker chỉ có nến M1 khi có tick), nên độ phủ theo lịch của M1 là ≈ 90%; điều này là đặc
tính dữ liệu của broker, không phải thiếu sót của backfill, và không có nến nào bị bịa. Báo cáo chi tiết kèm các
khoảng trống lớn nhất (đều là cuối tuần lễ): `docs/reports/mt5-backfill-final.md`.

## 5. Vận hành và giám sát

Một supervisor (`scripts/run_market_stack.py`) giữ collector + API + dashboard; Task Scheduler khi đăng nhập
chạy `start_market_stack.ps1` (mở terminal trước). Collector tự kết nối lại khi terminal vắng/khởi động muộn/mất
kết nối và reconcile 200 nến mỗi khung ở mỗi phiên mới. Sức khỏe: GOOD / DEGRADED / STALE / DISCONNECTED /
UNKNOWN; độ mới tính theo lịch (số nến mở cửa bị bỏ lỡ), đĩa và độ trễ ghi tick được báo trước khi hỏng.
Đo thật: collector ≈ 3,3% một lõi, ≈ 11 lệnh gọi MT5/giây; API: báo giá 4 ms, trạng thái 18 ms, 500 nến M1 8 ms,
5.000 nến H4 57 ms (`mt5-performance.json`).

## 6. Kiểm tra toàn vẹn

`scripts/verify_market_ledger.py` (đọc được, lược đồ, thứ tự, trùng, OHLC hợp lý, bất biến so với manifest, độ phủ
theo lịch) và `scripts/verify_tick_ledger.py` (hash, thứ tự, trùng, ask < bid, tick ngoài ngày). Hiện cả hai sạch.
`scripts/snapshot_market.py` ghi snapshot bất biến kèm provenance (nguồn, build terminal, server, symbol, thời điểm UTC,
hash đầu kho, nến mới nhất mỗi khung, tick mới nhất).

## 7. Giới hạn đã biết

* Khi mở terminal, KHÔNG để collector chạy lúc cần đóng/sửa terminal: collector tự mở lại MT5 mỗi khi nó thoát
  (`initialize` khởi động terminal). Tắt stack bằng `stop_market_stack.ps1` trước (xem tài liệu vận hành).
* Tự khởi động mới ở mức **đã cấu hình và đã chạy thử qua Task Scheduler**, chưa **đã xác minh bằng đăng nhập thật**
  (danh sách kiểm tay ở `docs/operations/market-data-operations.md` §6).
* Chưa thử đóng terminal MT5 thật khi collector chạy (quy tắc: không tự tắt MT5); kịch bản được kiểm bằng test
  mô phỏng và nằm trong danh sách kiểm tay.
* Kỷ nguyên lịch cũ trước 2021 chưa mô hình hóa (bucket `UNKNOWN`, không ảnh hưởng nến native).
* Dùng phiên đăng nhập của terminal; không dùng mật khẩu investor.

## 8. Cổng

| Cổng | Trạng thái |
|---|---|
| A Terminal | ĐẠT (DEMO, nối được, quote tuổi ≈ 0 s) |
| B Lịch sử | ĐẠT: 6/6 khung BROKER_LIMITED từ 2004-06-11 (đủ những gì broker phục vụ) |
| C MaxBars | ĐẠT: terminal báo 10.000.000 (đã xác minh bằng chính terminal, không chỉ file) |
| D Tick | ĐẠT (kho + retention + backfill 2021-10 → nay + API có giới hạn) |
| E Lịch | ĐẠT trong kỷ nguyên đã kiểm chứng (mọi bucket bỏ từ 2025 đều có lý do; cổng ≥ 60 phút) |
| F Collector | ĐẠT (giám sát, tự nối lại; MT5 thật đóng/mở: danh sách kiểm tay) |
| G Khởi động | MỘT PHẦN (đã cấu hình + chạy thử; chưa xác minh đăng nhập thật) |
| H Sức khỏe | ĐẠT |
| I API | ĐẠT (tươi, có giới hạn) |
| J UI | ĐẠT (6 khung, tick volume, spread, trạng thái, chất lượng) |
| K Parity | ĐẠT (8/8 cặp EXACT, kể cả toàn bộ lịch sử 2004→nay) |
| L Visual | ĐẠT (312/312 nến khớp terminal, gồm 2005/2012/2019) |
| M Lưu trữ | ĐẠT (bar + tick sạch) |
| N Phục hồi | ĐẠT (xem `mt5-chaos-tests.md`) |

Quyết định giao dịch tự động (BUY/SELL, SL/TP, thực thi) vẫn TẠM DỪNG cho đến khi cổng G (tự khởi động) được
xác minh bằng một lần đăng nhập thật.
