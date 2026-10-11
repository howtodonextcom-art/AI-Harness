# V3 — giao thức chung (đóng băng 2026-10-11, trước mọi kết quả)

Áp dụng cho F1, F3, F2. Một mục ở đây chỉ được đổi bằng một bản đăng ký mới, có phiên bản, **trước** khi chạy, và tính lại K.

## Dữ liệu

* Broker/terminal: FTMO-Demo (MT5), cùng một đồng hồ UTC cho mọi symbol (kiểm 2026-10-11: tuần mở Chủ nhật 21/22:00 UTC, đóng thứ Sáu ~20:00 UTC, giống nhau ở XAUUSD/EURUSD/USDJPY/XAGUSD — `foundation/cross_asset_qa.json`).
* XAUUSD M1/H1 bid: `data/market/XAUUSD` (ledger có sẵn). EURUSD/USDJPY/XAGUSD M1/H1: tải read-only 2026-10-11 bằng `scripts/backfill_mt5.py`, băm trong `foundation/cross_asset_manifest.json`.
* Không nội suy nến thiếu. Một sự kiện cần một nến không tồn tại thì bị loại và được đếm (`dropped_missing_bar`).

## Phân vùng

| Vùng | Khoảng | Vai trò |
|---|---|---|
| Development-2 | 2011-01-01 .. 2018-12-31 | Stage 1 (screening) |
| Validation-2 | 2019-01-01 .. 2021-12-31 | Stage 2, chỉ cho survivor Stage 1 |
| Test-H | 2022-01-01 .. 2025-04-30 | **khóa**; một lần, sau Dev PASS + Val PASS + review độc lập |
| Burned recent | 2025-05-01 .. 2026-04-30 | chỉ mô tả, không là bằng chứng |
| Holdout | 2026-05-01 .. 2026-10-07 | **khóa**; một lần, cuối cùng |

## Chi phí (cost model v2, từ `foundation/cost_model_v2.json`)

* Spread mỗi lần khớp (vào và ra): từ 2021-10-01 dùng **trung vị spread tick của đúng phút đó**; trước đó dùng `spread` của nến M1 × hệ số kỷ nguyên.
  * Hệ số base / bi quan: **1.6 / 2.4** cho 2011–2023 (tỉ lệ tick/nến cùng phút đo 2021–2023: trung vị 1.43–1.63, p90 1.86–2.43; trước 2021 không có tick nên giả định như 2021–2023); **1.1 / 1.7** cho 2024+ (đo: trung vị 1.03–1.10, p90 1.15–1.70).
  * Bi quan khi có tick: 1.5 × spread tick của phút.
* Slippage: 3 điểm mỗi lần khớp (base), 6 điểm (bi quan). **Giả định, chưa đo** (0 lệnh khớp thật).
* Commission: 0 (base, **CHƯA XÁC MINH**). Báo cáo kèm commission hòa vốn (USD/lot/side làm mean net R = 0).
* Swap: theo `CostModel` hiện hành nếu giữ qua rollover 21:00 UTC (chỉ F1 có thể giữ qua đêm). Swap đọc lại trước khi chạy (đã thấy thay đổi: long −76.05 → −69.25 điểm, 2026-10-08 → 2026-10-11).
* Không dùng mô hình chi phí này để chạy lại hay "cứu" bất kỳ giả thuyết V1/V2 nào.

## Thống kê và cổng

* Đơn vị: R (định nghĩa riêng từng họ). Số liệu chính: **mean net R (base)**; kèm net bi quan, gross (không chi phí), PF, MDD theo R, tỉ lệ thắng, số sự kiện, phân bố theo năm.
* Kiểm định: bootstrap khối theo ngày (khối 5 ngày giao dịch, 10,000 lần, seed 20261011), một phía H0: mean net R (base) ≤ 0.
* Placebo: cùng thời điểm vào, hướng ngẫu nhiên (1,000 lần, seed 20261011); báo cáo percentile (không phải cổng riêng, nhưng xem "artefact").
* **Stage 1 PASS** chỉ khi đồng thời: (1) n ≥ mẫu tối thiểu của họ; (2) p < 0.0333; (3) mean net R base ≥ **+0.10R** (sàn kinh tế; mục tiêu nghiên cứu +0.15R); (4) mean net R bi quan > 0; (5) không có artefact rõ: dấu dương ở ≥ 5/8 năm Dev, bỏ 1% lệnh tốt nhất vẫn > 0, placebo percentile ≥ 95.
* **Val PASS**: n ≥ mẫu tối thiểu Val; p < 0.0167; mean net R base ≥ +0.10R; bi quan > 0.
* **Test-H / Holdout**: p < 0.05/44; bi quan > 0; mean net R base ≥ +0.10R; một lần.
* Fail ở bất kỳ cổng nào: họ **đóng**. Không chỉnh ngưỡng, cửa sổ, tập sự kiện hay chi phí sau khi đã thấy kết quả.

## Quản lý vị thế

* Một vị thế tại một thời điểm trong mỗi họ (sự kiện độc lập). Không BE, không trailing, không chốt một phần (chỉ nghiên cứu sau khi một entry qua Validation).
* Khi SL và TP cùng chạm trong một nến M1: tính SL trước (bi quan).

## Tần suất và kinh tế

* Yêu cầu ≥ 150 sự kiện độc lập/năm, hoặc power cho thấy kiểm chứng forward ≤ 12 tháng; nếu không: **ECONOMICALLY IMPRACTICAL**.
* Báo cáo kèm: rủi ro 0.25% mỗi lệnh × tần suất × mean net R = đóng góp kỳ vọng/năm, và MDD theo R.
