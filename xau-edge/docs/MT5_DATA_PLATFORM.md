# Nền tảng dữ liệu thị trường MT5 (FTMO DEMO)

Trạng thái: **PARTIALLY READY** — hạ tầng chạy và đã kiểm chứng trên terminal thật; còn 1 hành động
của chủ dự án (nâng "Max bars in chart") để có đủ chiều sâu lịch sử cho M1/M5/M15/M30/H1.

Quyết định kiến trúc: xem `docs/adr/ADR-MT5-MARKET-DATA-PLATFORM.md`. Nghiên cứu phương án:
`docs/research/mt5-data-integration-options.md`, vai trò TradingView: `docs/research/tradingview-data-role.md`.

## 1. Luồng dữ liệu

```
FTMO MT5 terminal (đã đăng nhập, DEMO)
   └─ ReadOnlyMt5Client (allowlist: chỉ hàm dữ liệu)         src/xau_edge/market_data/mt5/source.py
       └─ Mt5Feed (quote, tick, bar, symbol, đồng hồ broker)  .../mt5/feed.py
           └─ MarketCollector (vòng quote ~1s + vòng bar ~5s)  src/xau_edge/market_data/collector.py
               ├─ BarLedger: nến ĐÃ ĐÓNG, parquet theo tháng  src/xau_edge/market_data/ledger.py
               ├─ live.json: quote, nến đang hình thành, tick gần đây
               └─ collector_status.json: sức khỏe (GOOD/DEGRADED/STALE/DISCONNECTED/UNKNOWN)
                   └─ API /md/*  (chỉ GET, không mở kết nối MT5)  src/xau_edge/api/market_data.py
                       └─ Web /market (nến + tick volume + spread)  apps/dashboard/app/market
```

Thư mục dữ liệu: `data/market/` (không vào git). Research/backtest/signal/paper/demo đều đọc cùng
một lớp bar chuẩn (`domain/market.py`, `CANONICAL_BAR_COLUMNS`), mặc định **chỉ nến đã đóng**.

## 2. Quy tắc bất biến

* Chỉ nến đã đóng vào kho; nến đang hình thành chỉ ở `live.json`/UI và luôn gắn `is_closed=false`.
* Kho không bao giờ ghi đè nến đã lưu. Nến cùng thời điểm mở nhưng khác giá = sự kiện `BAR_CHANGED`
  (giữ nguyên bản đã lưu, ghi vào `events.jsonl`). Ghi file nguyên tử (tạm + đổi tên), chạy lại là idempotent.
* Khối lượng là **tick volume**. `real_volume` chỉ khác 0 trong H1/H4 2012-03-28..2018-02-09 (dữ liệu
  nhập cũ, ngữ nghĩa chưa xác minh) → không dùng. Không bao giờ gắn nhãn tick volume là real volume.
* Client dữ liệu không có `order_send`, `order_check`, `positions_get`, `orders_get`,
  `history_deals_get`, `history_orders_get`; test fail nếu mã nguồn chạm tên ngoài allowlist.
  Tài khoản không phải DEMO → từ chối (fail closed). Không truyền/in/ghi mật khẩu, login, số dư.
* Thị trường đóng (cuối tuần, rollover) không phải lỗi dữ liệu; nhưng khi lịch báo "mở" mà không có
  tick/nến mới → `STALE`, không bao giờ im lặng coi là tốt (ngày lễ calendar chưa biết cũng rơi vào đây).

## 3. Vận hành

```
uv run --extra mt5 python scripts/diagnose_mt5_environment.py     # terminal, package (không kết nối)
uv run --extra mt5 python scripts/mt5_connection_probe.py --write # kết nối, symbol, độ sâu, tick
uv run --extra mt5 python scripts/probe_mt5_history_depth.py --write
uv run --extra mt5 python scripts/backfill_mt5.py --write-report  # nạp lịch sử (idempotent)
uv run --extra mt5 python scripts/run_market_collector.py         # chạy liên tục (Ctrl+C để dừng)
uv run python scripts/check_market_data_health.py                 # exit 0 chỉ khi GOOD
uv run python scripts/snapshot_market.py                          # snapshot bất biến có hash
uv run python scripts/market_data_parity.py --write               # parity native vs resample
uv run python scripts/serve_api.py                                # API + /md/*
```

Collector tự `reconcile` 200 nến cuối của mọi khung khi khởi động và mỗi 10 phút; mất kết nối →
trạng thái `DISCONNECTED`, tự kết nối lại sau 5 s. Sau khi khởi động lại máy: mở terminal FTMO
(đăng nhập sẵn), rồi chạy lại collector (có thể đặt vào Task Scheduler "At log on" — chưa cài, cần
quyết định của chủ dự án).

## 4. API (chỉ GET)

| Endpoint | Nội dung |
|---|---|
| `/md/status` | sức khỏe collector, trạng thái phiên, nhãn nguồn |
| `/md/{symbol}/quote` | bid/ask/mid/spread, tuổi tick, `stale` |
| `/md/{symbol}/bars?timeframe&limit&before&include_forming` | nến đã đóng (+ nến đang hình thành khi yêu cầu, `is_closed=false`) |
| `/md/{symbol}/ticks?limit` | ≤500 tick gần nhất (bộ đệm của collector) |
| `/md/{symbol}/matrix` | nến đóng gần nhất và độ mới của 6 khung |

Giao thức: polling (UI ~1 s quote, ~3 s nến). Không dùng SSE/WebSocket: đơn giản, chịu được restart.

## 5. Chiều sâu lịch sử (đo thực tế, 2026-10-09)

| Khung | Sớm nhất lưu được | Ghi chú |
|---|---|---|
| M1 | 2026-06-30 | bị cắt bởi Max bars |
| M5 | 2025-05-14 | bị cắt |
| M15 | 2022-08-02 | bị cắt |
| M30 | 2018-06-12 | bị cắt |
| H1 | 2010-04-09 | bị cắt |
| H4 | 2004-06-11 | đầy đủ |
| Tick | ≈ 2021-10-01 | server giữ; chưa lưu (xem giới hạn) |

Nguyên nhân: `[Charts] MaxBars=100000` trong `common.ini` của terminal (không phải server thiếu dữ liệu).
`copy_rates_from_pos` với count 100000 trả "Invalid params"; 99000 chạy được.

## 6. Hành động của chủ dự án

Nâng "Max bars in chart" (Tools → Options → Charts) lên Unlimited hoặc ≥ 10.000.000, **đóng hẳn rồi mở
lại** terminal, sau đó chạy lại `scripts/backfill_mt5.py`. (Hoặc dùng `scripts/mt5_set_max_bars.py
--apply` khi terminal đã đóng; script chỉ sửa dòng `MaxBars`, có backup.) Trong lúc chờ, collector tích
lũy M1 từ nay về sau nên không mất dữ liệu mới.

## 7. Giới hạn đã biết

* Chưa lưu tick lịch sử vào kho (chỉ bộ đệm 500 tick gần nhất ở `live.json`); cần quyết định lưu trữ.
* `MarketCalendar` mặc định không mô hình hóa giờ nghỉ hằng ngày của FTMO và ngày lễ → ~2% bucket
  khi resample bị loại là "không đủ nến" (được báo cáo, không điền giả). Không ảnh hưởng parity.
* `last` thường rỗng với CFD vàng (chỉ có bid/ask). Spread theo nến là điểm (points), xem
  `docs/reports/mt5-spread-semantics.md`.
* Kết nối chạy bằng phiên đăng nhập sẵn của terminal; chưa dùng mật khẩu investor (không cần với cách này).
* So khớp hình ảnh với biểu đồ FTMO bằng mắt chưa thực hiện tự động; parity số liệu OHLC/tick volume giữa
  nguồn native và nguồn dẫn xuất khớp 100% (`docs/reports/mt5-data-parity.md`).
* 13 khẳng định trong tài liệu nghiên cứu nhúng ở `docs/research/*` chưa được xác minh từ nguồn chính
  thức; chỉ các kết luận đo thực tế ở đây được coi là sự thật của dự án.

## 8. Cổng chặn (trước khi mở lại việc ra quyết định giao dịch)

Quyết định BUY/SELL tự động, nghiên cứu chiến lược mới, tự động SL/TP và mọi thực thi vẫn **tạm dừng**
(commit `618e0d8`, `af4cd53` giữ baseline UNVALIDATED). Chỉ mở lại sau khi chủ dự án nâng Max bars và
backfill đủ sâu được xác nhận.
