# Evaluation criteria, fixed BEFORE any outcome or backtest is looked at

Written 2026-10-08 (ECC `eval-harness`: define the evals first). Nothing in this file may be changed
after results exist without recording the change, the reason and the number of variants already
tried. The aim is to keep "we found an edge" honest.

## Data splits (chronological, never shuffled)

Data: FTMO demo XAUUSD, 2025-05-01 to 2026-10-07, M5/M15/H1/H4.

| Period | Dates | Use |
|---|---|---|
| Development | 2025-05-01 .. 2025-12-31 | design, debugging, sanity checks, choosing among variants |
| Validation | 2026-01-01 .. 2026-04-30 | compare the finalists chosen on development |
| Test | 2026-05-01 .. 2026-10-07 | touched once per finished candidate; reported whatever it shows |

Warm-up bars before a period may come from earlier periods (indicators need them); decisions and
outcomes must lie inside the period. Pattern search history may use any data strictly before the
query minus the leakage margin (ADR-0013). Walk-forward (Sprint 9) uses anchored expanding training
windows with contiguous monthly test folds inside Validation and Test.

## Pre-specified analogue study (Sprint 7)

One configuration, chosen a priori: M15, window 30, horizon guard 60, `k = 20`, Euclidean distance,
outcome horizon 20 bars, neutral band 0.5 ATR, queries every 4th bar. Question: do the 20 analogues'
outcomes predict the query's own outcome better than the base rate?

* Statistics (both reported, day-block bootstrap 95% intervals, 2,000 resamples, seed 7):
  - total: mean of `sign(analogue mean forward ATR move) * realised forward ATR move`;
  - timing: mean of `(sign_i - mean(sign)) * realised_i`, the part not explained by always leaning
    the same way (gold drifts, so a constant bias would otherwise look like skill).
* Pass: the lower bound of BOTH intervals > 0 on Development AND Validation (amended on 2026-10-08
  before any result existed: the timing statistic was added to the pass rule). Test only after both
  periods pass.
* Alternatives (other windows, methods, k) are exploratory; each is counted in the registry and the
  required interval widens accordingly (see multiple testing).

## Edge criteria for a strategy (Sprint 9 checkpoint)

A strategy "shows an edge" only if ALL hold on Validation and then on Test, net of costs (measured
M5 spread, commission and slippage assumptions from the broker profile):

1. At least 100 trades in the period.
2. Mean net R per trade > 0 with a day-block bootstrap interval whose lower bound > 0 at the level
   `1 - 0.05 / K`, where `K` is the number of strategy variants evaluated so far (from the registry).
3. Net profit factor >= 1.2.
4. Maximum drawdown <= 15 R.
5. Positive mean net R in at least 3 of 4 contiguous walk-forward folds of the period.
6. Removing the best 5% of trades leaves mean net R > 0.
7. No single regime or session supplies more than 60% of net profit.

Failing any criterion is a failure; there is no partial credit and no re-running with new parameters
on the same period. A failed Test period ends that candidate.

## Model criteria (Sprint 10)

A model replaces nothing unless, out of sample on Validation and Test, it (a) beats the best baseline
on the criteria above and (b) has better Brier score and log loss than the base rate and than the
analogue estimate, with calibration error reported. Simpler wins ties.

## Checkpoint rule (after Sprint 9)

* At least one baseline meets all edge criteria: proceed to ML and signal engine on that evidence.
* None does: record "no statistically justified trade found with these baselines" as the result.
  Later components are still built (signal engine, API, dashboard, paper trading) because their
  correct output in that situation is WAIT with the reasons; no component may present a probability
  as an edge it has not demonstrated.

## Reporting rules

Every report states: data period, number of variants tried (registry count), costs assumed, trade
count, intervals, and every criterion with pass/fail. Negative results are published like positive
ones.

## Phụ lục 2026-10-08: dữ liệu lịch sử mới và các split MỚI (Edge Program, Gate 1 đã duyệt)

Phụ lục này chỉ BỔ SUNG split cho dữ liệu mới; 7 tiêu chí ở trên giữ NGUYÊN. Được commit TRƯỚC khi
xem bất kỳ kết quả (lợi nhuận, R, hướng giá) nào trên dữ liệu mới. Chỉ có số hàng, ngày đầu/cuối,
phân bố spread theo năm và số lỗi validator được xem để chọn cửa sổ dữ liệu (không phải kết quả).

### Dữ liệu mới (đọc MT5 chỉ-đọc, DEMO, `scripts/fetch_history.py`)

Lưu ở kho thô bất biến riêng `data/research_history` (không đụng catalog của bot). Bar còn đang
hình thành không bao giờ được lưu. Manifest + hash: `docs/research/edge-program/data-manifest.json`.

| TF | Hàng | Từ (UTC) | Đến (UTC) | dataset_id |
|---|---:|---|---|---|
| M5 | 0 | không có lịch sử trước 2025-05-01 | | |
| M15 | 66,720 | 2022-07-04 | 2025-04-30 | `f1480a7251ffce51` |
| H1 | 91,655 | 2010-01-24 | 2025-04-30 | `8e64dd6561015b72` |
| H4 | 31,995 | 2004-06-11 | 2025-04-30 | `b438f1794bd11402` |

* Daily (D1) KHÔNG phải member của `Timeframe`. Chỉ là dataset nghiên cứu dẫn xuất bằng resample H1
  theo ngày server broker (NY+7, rollover 17:00 New York), bỏ ngày < 12 bar H1, không điền.
* Chuỗi có thể thực thi (execution) cho lịch sử mới là H1 (không có M5 trước 2025-05). Lệnh vào ở
  open của bar H1 kế tiếp quyết định; chạm cả stop và target trong một bar H1 thì tính stop (bảo thủ).
* M15 chỉ phủ 2022-07..2025-04 (quá ngắn để chia Dev/Val/Test mới) nên KHÔNG dùng cho split mới.
* Trường `spread` của bar lịch sử KHÔNG đáng tin (trung vị theo năm: 2022-23 = 7 pts, 2024 = 15,
  2025 = 23 so với 27-31 pts đo được trên dữ liệu hiện tại; 2010 và 2021 hầu hết bằng 0). Quy tắc
  chi phí cho lịch sử mới, cố định trước: `spread_dùng = max(spread_ghi_nhận, 30)` points.
  Slippage 3 points/lần khớp, commission 0 (chưa xác minh), swap theo `CostModel` hiện hành (bảo
  thủ cho vị thế qua đêm). Kịch bản bi quan: slippage x2 (6 points), mọi thứ khác giữ nguyên.

### Split mới (theo thời gian, không xáo trộn; cuối mở)

| Giai đoạn | Ngày | Dùng cho |
|---|---|---|
| Development-H | 2011-01-01 .. 2018-12-31 | thiết kế, debug, kiểm tra tính hợp lệ code |
| Validation-H | 2019-01-01 .. 2021-12-31 | đánh giá các ứng viên đã đăng ký trước |
| Test-H | 2022-01-01 .. 2025-04-30 | đúng MỘT lần cho mỗi ứng viên PASS cả Dev-H và Val-H |
| Holdout (khóa) | 2026-05-01 .. 2026-10-07 (Test cũ) | KHÔNG chạm trong chương trình này; chỉ mở sau review độc lập, một lần, cho ứng viên đã PASS Test-H |

Dữ liệu 2025-05-01 .. 2026-04-30 (Dev/Val cũ) không dùng trong chương trình này. Warm-up trước một
giai đoạn được lấy từ giai đoạn trước. 4 fold của tiêu chí 5 chia đều thời lượng giai đoạn.

### Quy tắc thống kê cho split mới

* `K` = số biến thể đã đăng ký trong registry baseline (3) + toàn bộ lưới biến thể đã khai báo của
  Edge Program (đếm TOÀN BỘ lưới ngay từ đầu, dù có chạy hết hay không). alpha = 0.05 / K, cố định
  cho mọi đánh giá của chương trình. Số K và trần ghi trong `docs/research/edge-program/ledger.md`.
* Bootstrap khối theo ngày dùng 20,000 resample (seed 7) thay vì 2,000 vì alpha/K rất nhỏ; đây chỉ
  tăng độ phân giải của đuôi, không đổi tiêu chí.
* PASS = 7 tiêu chí đều đạt VÀ kịch bản bi quan (slippage x2) có mean net R > 0 trên cùng giai đoạn.
  Điều kiện bi quan là điều kiện cần bổ sung, không thay thế tiêu chí nào.
