# V2 · Ma trận ảnh hưởng của lỗi dữ liệu lên nghiên cứu cũ

Ngày: 2026-10-13 · Căn cứ: `V2_DATA_PROVENANCE_FORENSIC_REPORT.md` và `reports/evidence/data_forensics/months.csv`
Phạm vi lỗi **đã xác định chính xác**: bar giả hằng ngày (pseudo-bar, nhìn trước tới 24 giờ) **2012-06-26 → 2021-01-20**, trong M1/M5/M15/M30/H1, và gộp vào H4. Mọi thứ ngoài khoảng đó **không** bị lỗi này (có thể có vấn đề khác: xem cột Ghi chú).
Không bác bỏ toàn bộ nghiên cứu cũ: mỗi dòng dưới đây chỉ ra dữ liệu nào, tháng nào, và hướng lệch nếu biết.

Nhãn trạng thái: **KHÔNG ẢNH HƯỞNG** · **VÔ HIỆU** (kết quả dựa trên dữ liệu nhìn trước) · **KHÔNG TIN CẬY, CHƯA RÕ HƯỚNG** · **MỘT PHẦN HỢP LỆ** · **CẦN KIỂM TRA**.

| # | CLAIM | DATA SOURCE (cửa sổ, số tháng bị lỗi) | TÁC ĐỘNG | TRẠNG THÁI |
|---|---|---|---|---|
| 1 | Parity lõi V1 ↔ V2 (G4, golden): hai cài đặt cho cùng số học | tháng mẫu 2008–2021 + 2025-05..2026-04 (có tháng lỗi) | Parity so hai cài đặt **trên cùng dữ liệu**; lỗi dữ liệu ảnh hưởng cả hai như nhau | **KHÔNG ẢNH HƯỞNG** |
| 2 | Khóa chiến lược v1.1.0 (hằng số, sha256) | không dùng dữ liệu | — | **KHÔNG ẢNH HƯỞNG** |
| 3 | V1 baseline A/B/C và dự đoán ML V1 (lightgbm, logistic, RF, xgboost) | dev 2025-05→2025-12, val 2026-01→2026-04 (`xau-edge/data/backtests`): **0 tháng lỗi pseudo-bar** | Cửa sổ hiện đại; 11/12 tháng VERIFIED, 2025-10 SUSPECT (khớp tick 97,0%, sát ngưỡng) | **KHÔNG ẢNH HƯỞNG** (ghi chú: 2025-10) |
| 4 | V1 Edge Program H01–H06 và Batch A H07–H10: "NO EDGE WITHIN BUDGET, 0/20 qua Stage 1" | dev 2011-01..2018-12 (79/96 tháng lỗi), val 2019-01..2021-12 (26/36 lỗi) | Rò rỉ nhìn trước thiên về **tạo edge giả**; nhiễu mean-reversion thiên về pullback. Kết luận âm tính **không** được củng cố vì hướng lệch tùy giả thuyết. Cần chạy lại trên dữ liệu đã làm sạch | **KHÔNG TIN CẬY, CHƯA RÕ HƯỚNG** |
| 5 | Funnel Gate A, cửa sổ hiện đại 2025-05..2026-04: ≈17 episode/năm của V1 control; nguyên nhân chính là cổng biến động percentile + độ sâu chuỗi; BUY 16 / SELL 9 | 12 tháng đủ, 0 pseudo-bar; 11 VERIFIED, 2025-10 SUSPECT | Không bị lỗi nhìn trước. Ghi chú về 2025-10 | **KHÔNG ẢNH HƯỞNG** (có điều kiện) |
| 6 | Funnel Gate A, Dev 2011–2018 (25 tháng mẫu): "cổng spread chặn 92,7%", "67 episode", "67% tín hiệu ở phiên Á" | 4 tháng sạch (2011-02/06/10, 2012-02) + **21 tháng có pseudo-bar** | Số đếm quanh 22:00–04:00 UTC (đúng khung Á) bị đổi: 82–87% trạng thái đổi nhãn khi bỏ pseudo-bar ⇒ tỷ trọng phiên Á và số episode không đáng tin. Phần spread ở 2011 là thật (spread 60–70 điểm) | **MỘT PHẦN HỢP LỆ** (chỉ 2011-02..2012-05) |
| 7 | Funnel Gate A, Validation 2019–2021 (9 tháng mẫu): 36 episode, 71/35 BUY/SELL chuỗi | 6 tháng lỗi (2019-02/06/10, 2020-02/06/10), 2021-02 và 2021-06 INSUFFICIENT, 2021-10 VERIFIED | như dòng 6 | **KHÔNG TIN CẬY** (trừ 2021-10) |
| 8 | Phân tích "tính đối xứng BUY/SELL không phải lỗi mã" | Dev + modern | Kết luận dựa chủ yếu trên tỷ lệ qua cổng; đúng ở cửa sổ hiện đại | **MỘT PHẦN HỢP LỆ** |
| 9 | Candidate Stage A (tín hiệu) | Dev 96 tháng: 17 tháng sạch (2011-01..2012-05), 1 SUSPECT, **78 tháng có pseudo-bar** | Tín hiệu sinh ra từ trạng thái bị nhiễm | **VÔ HIỆU** (trừ 17 tháng sạch, chưa tách riêng) |
| 10 | Candidate Stage B: CORE +0,68R, 57% thắng, dương mọi năm; mọi biến thể INCONCLUSIVE | như dòng 9 | Edge là **artefact**: tháng sạch N=28, E=+0,12R, 39%; tháng lỗi N=201, E=+0,76R, 60%. Đường thoát cũng bị nhiễm: vị thế mở lúc 21:00 UTC chạm SL/TP bởi biên độ phiên kế tiếp của pseudo-bar | **VÔ HIỆU** |
| 11 | Quy tắc chọn đã preregister cho "cả bốn thay đổi đều vào, candidate = CORE" | như dòng 9–10 | Không được dùng. Chưa đóng băng candidate | **VÔ HIỆU** |
| 12 | ML V0 (volatility/range) rejected tại Validation; skill vs ATR14 9,6% (val), 8,6% (dev) | train 2004-06→2021-12; Validation 2019–2021 (26/36 tháng lỗi); đặc trưng `lATR14/50/200, lR24, lR5` từ H1 **chứa pseudo-bar** (≈1.748 bar H1) | Đặc trưng tại thời điểm t sau pseudo-bar chứa biên độ phiên kế tiếp, tức là chứa nhãn `rng24` (24 giờ tới). Rò rỉ thổi phồng skill nhưng cũng thổi phồng baseline ATR14. Hướng lệch của *skill tương đối* không xác định; rất có thể skill thật thấp hơn | **KHÔNG TIN CẬY, CHƯA RÕ HƯỚNG**. Quyết định "retired" vẫn là sự kiện quản trị; không mở lại |
| 13 | Cửa sổ Validation 2019–2021 như "cửa sổ chưa xem outcome" | 26/36 tháng lỗi | Không dùng được làm cửa sổ xác nhận mù cho đến khi làm sạch; 2021-02..09 INSUFFICIENT | **CẦN KIỂM TRA** |
| 14 | Test-H 2022-01..2025-04 chưa mở | tháng: 2022-01..03 SUSPECT (khớp tick 54–86%, chênh tới $7,8), 2023-10, 2024-01 SUSPECT (96–97%), phần còn lại VERIFIED | Không có pseudo-bar. Bất thường 2022-Q1 phải được điều tra **trước khi** có ai xin mở Test-H | **CẦN KIỂM TRA** (không mở, không outcome) |
| 15 | Holdout 2026-05..2026-10-07 chưa mở | 2026-05..10 VERIFIED | Sạch | **KHÔNG ẢNH HƯỞNG** |
| 16 | Forward evidence và PAPER desk (G7, G8) | từ 2026-10-09 | Sạch | **KHÔNG ẢNH HƯỞNG** |
| 17 | G9/G10 (lớp con người, M1 execution), UI, API | kiểm thử tổng hợp, dữ liệu sống | Không dùng lịch sử bị lỗi | **KHÔNG ẢNH HƯỞNG** |
| 18 | Công suất thống kê (295/663/1.178/2.649) | không dùng dữ liệu | — | **KHÔNG ẢNH HƯỞNG** |

## Các số bị ảnh hưởng, theo giai đoạn dữ liệu
| Giai đoạn | Tình trạng |
|---|---|
| 2004-06 → 2005-05 | SUSPECT (mean reversion trong phiên, spread không ghi); chưa xác định nguyên nhân |
| 2005-06 → 2012-05 | VERIFIED_VALID (H4/H1 giống tải lại broker) |
| 2012-06 → 2021-01 | **Có pseudo-bar** (INVALID; recoverable bằng cách bỏ bar giả) |
| 2021-02 → 2021-09 | INSUFFICIENT_EVIDENCE |
| 2021-10 → 2026-10 | VERIFIED_VALID 53 tháng, SUSPECT 8 tháng (2022-01..03, 2023-10, 2024-01, 2024-07, 2024-08, 2025-10) |

## Việc cần làm theo ma trận
1. Chạy lại funnel (không outcome) trên dữ liệu đã làm sạch để thay các dòng 6–7 (chờ phê duyệt, xem `V2_DATA_RECOVERY_OPTIONS.md`).
2. Đánh dấu kết quả Edge Program của V1 (dòng 4) là "chưa tin cậy" trong Research Console của V1; không rerun nếu chưa được phê duyệt.
3. Điều tra 2022-Q1 trước khi bàn Test-H (dòng 14).
