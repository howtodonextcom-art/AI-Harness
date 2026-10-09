# Nền tảng dữ liệu thị trường MT5 (FTMO DEMO)

**Trạng thái: PARTIALLY READY** — mọi thành phần chạy và đã kiểm chứng trên terminal thật; còn đúng 1 việc của
chủ dự án (nâng "Max bars in chart"), vì nó chặn chiều sâu lịch sử của M1/M5/M15/M30/H1. Bảng điểm và cổng
ở cuối tài liệu.

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
Kết quả: tỷ lệ bucket bị loại M1→H4 từ **33,6% xuống 0,45%** (chỉ còn 2 bucket biên dữ liệu); xem
`docs/reports/mt5-data-parity.md`. Giới hạn: mẫu tuần đã kiểm chứng từ 2025; kỷ nguyên cũ (chủ yếu 2010–2020) có lịch
khác, chưa mô hình hóa, nên các bucket H1→H4 lịch sử đó ghi `UNKNOWN`.

## 4. Chiều sâu lịch sử (đo 2026-10-09)

Backfill v2 (`scripts/backfill_mt5.py`): nến mới nhất rồi lùi theo khối bằng `copy_rates_from`, có xác thực từng
khối, hash SHA-256 vào sự kiện, chạy lại/tiếp tục được, chống vòng lặp, và gán trạng thái trung thực
(`COMPLETE_AVAILABLE_HISTORY`, `BROKER_LIMITED`, `TERMINAL_LIMITED`, `INCOMPLETE`, `UNKNOWN`).

| Khung | Local sớm nhất | Trạng thái |
|---|---|---|
| M1 | 2026-06-29 | TERMINAL_LIMITED |
| M5 | 2025-05-08 | TERMINAL_LIMITED |
| M15 | 2022-07-18 | TERMINAL_LIMITED |
| M30 | 2018-05-11 | TERMINAL_LIMITED |
| H1 | 2010-02-05 | TERMINAL_LIMITED |
| H4 | 2004-06-11 | BROKER_LIMITED (đủ: không còn gì cũ hơn) |
| Tick | 2021-10-01 11:32 UTC | server giữ từ đó; đã lưu đủ 205.083.656 tick |

Nguyên nhân là `[Charts] MaxBars=100000` của terminal: `copy_rates_from_pos` 100.000 → "Invalid params"; truy vấn theo
ngày chỉ thêm ~900 nến rồi `Terminal: Call failed`. Không bịa nến thấp từ khung cao; không suy tick từ nến.
Báo cáo: `docs/reports/mt5-backfill-final.md`.

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

* Chiều sâu M1–H1 chờ chủ dự án nâng Max bars (mục 4); sau đó chạy lại backfill.
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
| B Lịch sử | CHƯA: 5/6 khung TERMINAL_LIMITED (H4 đủ) — cần hành động của chủ dự án |
| C MaxBars | CHƯA: vẫn 100.000 |
| D Tick | ĐẠT (kho + retention + backfill 2021-10 → nay + API có giới hạn) |
| E Lịch | ĐẠT trong kỷ nguyên đã kiểm chứng (bỏ 0 bucket tránh được từ 2025) |
| F Collector | ĐẠT (giám sát, tự nối lại; MT5 thật đóng/mở: danh sách kiểm tay) |
| G Khởi động | MỘT PHẦN (đã cấu hình + chạy thử; chưa xác minh đăng nhập thật) |
| H Sức khỏe | ĐẠT |
| I API | ĐẠT (tươi, có giới hạn) |
| J UI | ĐẠT (6 khung, tick volume, spread, trạng thái, chất lượng) |
| K Parity | ĐẠT (8/8 cặp EXACT) |
| L Visual | ĐẠT (240/240 nến khớp terminal) |
| M Lưu trữ | ĐẠT (bar + tick sạch) |
| N Phục hồi | ĐẠT (xem `mt5-chaos-tests.md`) |

Quyết định giao dịch tự động (BUY/SELL, SL/TP, thực thi) vẫn TẠM DỪNG cho đến khi cổng B, C (và G đã xác
minh) qua.
