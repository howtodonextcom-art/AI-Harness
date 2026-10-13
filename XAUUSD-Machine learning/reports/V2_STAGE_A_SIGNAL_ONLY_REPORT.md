# V2 · Stage A signal-only: CAND_V2_CORE_1.1.0 và MULTIFAMILY_RESEARCH_0.1.0 (DEV')

Viết cho: chủ dự án. **Không có outcome, không PnL, không mở Validation/Confirm-C/Test-H/Holdout, không chỉnh ngưỡng.** Số liệu được kết xuất tự động từ `docs/research/multifamily_stage_a_dev.json` và `docs/research/core_stage_a_dev.json`.

Dữ liệu: kho sạch (manifest `997d73f8025c…`), tháng PASS của DEV' 2005-11..2018-12; M15: 300,922 nến (~12.01 năm giao dịch).

## 1. MULTIFAMILY_RESEARCH_0.1.0 (spec đóng băng `multifamily_0.1.0.spec.json`, hash `multifamily_0.1.0.sha256`)

### 1.1 Phễu (mỗi episode bị chặn ở cổng ĐẦU TIÊN nó vi phạm)
| Họ | Raw | Episode | Sau CLEARANCE | Sau STOP | Sau TARGET | Sau COST (= chấp nhận) | Không chồng (96 nến) |
|---|---|---|---|---|---|---|---|
| B | 7211 | 5763 | 3648 | 1800 | 583 | 519 | 434 |
| C | 4465 | 4438 | 2507 | 1204 | 293 | 272 | 234 |
| D | 4760 | 4047 | 4017 | 4016 | 2305 | 1626 | 849 |

Cổng đầu tiên chặn episode:

| Họ | CLEARANCE | STOP | TARGET | COST | ACCEPTED |
|---|---|---|---|---|---|
| B | 2115 (36.7%) | 1848 (32.1%) | 1217 (21.1%) | 64 (1.1%) | 519 (9.0%) |
| C | 1931 (43.5%) | 1303 (29.4%) | 911 (20.5%) | 21 (0.5%) | 272 (6.1%) |
| D | 30 (0.7%) | 1 (0.0%) | 1711 (42.3%) | 679 (16.8%) | 1626 (40.2%) |

### 1.2 Cân bằng hướng (mua / bán)

| Họ | Raw | Episode | Chấp nhận |
|---|---|---|---|
| B | 3808/3403 | 3029/2734 | 275/244 |
| C | 2245/2220 | 2226/2212 | 146/126 |
| D | 2396/2364 | 2017/2030 | 758/868 |

### 1.3 Chế độ và phiên (của tín hiệu chấp nhận)

- **B** chế độ M15: `{"RANGE": 192, "TREND_DOWN": 119, "TREND_UP": 126, "SHOCK": 9, "LOW_VOLATILITY": 40, "HIGH_VOLATILITY": 33}`; phiên: `{"LONDON": 27, "ASIA": 266, "NEW_YORK": 86, "OFF_HOURS": 138, "LONDON_NY_OVERLAP": 2}`
- **C** chế độ M15: `{"SHOCK": 31, "TREND_DOWN": 47, "RANGE": 89, "TREND_UP": 64, "LOW_VOLATILITY": 10, "HIGH_VOLATILITY": 31}`; phiên: `{"OFF_HOURS": 29, "ASIA": 113, "NEW_YORK": 29, "LONDON_NY_OVERLAP": 55, "LONDON": 46}`
- **D** chế độ M15: `{"RANGE": 1626}`; phiên: `{"ASIA": 542, "LONDON_NY_OVERLAP": 340, "LONDON": 465, "OFF_HOURS": 102, "NEW_YORK": 177}`

### 1.4 Khả thi hình học

| Họ | Episode có stop hợp lệ (≤3 ATR) | Rủi ro ATR p10/50/90 | Có target hợp lệ (trong số có stop) | Target bị cản chặn | Net R:R p10/50/90 | cost_R p10/50/90 |
|---|---|---|---|---|---|---|
| B | 31.2% | 1.984 / 2.512 / 2.911 (n=1800) | 32.4% | 16.1% | 1.612 / 1.858 / 2.0 (n=583) | 0.016 / 0.048 / 0.154 (n=583) |
| C | 27.1% | 1.835 / 2.461 / 2.895 (n=1204) | 24.3% | 20.1% | 1.615 / 1.829 / 2.0 (n=293) | 0.013 / 0.06 / 0.14 (n=293) |
| D | 99.2% | 1.25 / 1.25 / 1.619 (n=4016) | 57.4% | 12.9% | 1.551 / 1.807 / 2.0 (n=2305) | 0.025 / 0.085 / 0.206 (n=2305) |

### 1.5 Chồng lấn giữa các họ (tín hiệu chấp nhận, ±6 nến M15)

| Cặp | Số tín hiệu của họ đầu | Cùng phía | Ngược phía |
|---|---|---|---|
| BxC | 519 | 67 | 7 |
| BxD | 519 | 8 | 30 |
| CxD | 272 | 8 | 11 |

Core giao họ mới (CORE episode, ±1 giờ):

| Họ | Core episodes | Cùng phía | Ngược phía |
|---|---|---|---|
| B | 65 | 4 | 0 |
| C | 65 | 3 | 0 |
| D | 65 | 1 | 3 |

### 1.6 Ước lượng công suất nghiên cứu (không phải kết quả)

| Họ | Tín hiệu không chồng trong DEV' | n cần (0,20R) | n cần (0,30R) | Năm để đủ n (0,20R) | Năm để đủ n (0,30R) |
|---|---|---|---|---|---|
| B | 434 | 663 | 295 | 18.4 | 8.2 |
| C | 234 | 663 | 295 | 34.0 | 15.1 |
| D | 849 | 663 | 295 | 9.4 | 4.2 |

## 2. CAND_V2_CORE_1.1.0 (spec đóng băng `cand_v2_spec.json`, hash `cand_v2_spec.sha256`)

Tháng đã xử lý: **36** (2005-11 → 2016-03); hoàn tất toàn DEV': **False**. Nến M5 đánh giá: 188,892; bị bỏ qua vì thiếu trạng thái (H1 UNKNOWN hoặc thiếu M1): 39,149 (20.7%); nến mà chuỗi CONTROL đủ điều kiện khi TẮT cổng (raw eligibility giả định): 67.

Tín hiệu sau cổng chi phí/cấu trúc (mọi biến thể, episode = chuỗi cùng phía cách nhau ≤60 phút):

| Biến thể | Tín hiệu | Episode | Hướng | Episode/năm | Năm để đủ n (0,20R) |
|---|---|---|---|---|---|
| A_C1 | 47 | 33 | {"SELL": 16, "BUY": 17} | 13.13 | 50.5 |
| A_C2 | 29 | 22 | {"SELL": 11, "BUY": 11} | 8.75 | 75.8 |
| A_C3a | 35 | 27 | {"BUY": 14, "SELL": 13} | 10.74 | 61.7 |
| A_C3b | 45 | 31 | {"SELL": 18, "BUY": 13} | 12.33 | 53.8 |
| B_C1C2 | 51 | 36 | {"SELL": 17, "BUY": 19} | 14.32 | 46.3 |
| B_C2C3a | 35 | 27 | {"BUY": 14, "SELL": 13} | 10.74 | 61.7 |
| CORE | 103 | 65 | {"BUY": 37, "SELL": 28} | 25.86 | 25.6 |
| CTRL | 28 | 21 | {"SELL": 11, "BUY": 10} | 8.35 | 79.4 |
| LOO_noC1 | 56 | 41 | {"SELL": 20, "BUY": 21} | 16.31 | 40.7 |
| LOO_noC2 | 92 | 59 | {"BUY": 32, "SELL": 27} | 23.47 | 28.3 |
| LOO_noC3a | 86 | 54 | {"BUY": 29, "SELL": 25} | 21.48 | 30.9 |
| LOO_noC3b | 67 | 46 | {"BUY": 26, "SELL": 20} | 18.3 | 36.2 |
| X_C7 | 97 | 73 | {"SELL": 33, "BUY": 40} | 29.04 | 22.8 |
| X_CORE_C7 | 410 | 246 | {"SELL": 94, "BUY": 152} | 97.85 | 6.8 |

CORE: chế độ H4 `{'HIGH_VOLATILITY': 8, 'RANGE': 23, 'TREND_UP': 20, 'TREND_DOWN': 13, 'LOW_VOLATILITY': 1}`; chế độ M15 `{'RANGE': 32, 'TREND_DOWN': 15, 'HIGH_VOLATILITY': 9, 'TREND_UP': 6, 'LOW_VOLATILITY': 3}`; phiên `{'ASIA': 22, 'LONDON_NY_OVERLAP': 13, 'NEW_YORK': 10, 'LONDON': 13, 'OFF_HOURS': 7}`; hình học rủi ro ATR 1.25 / 1.327 / 2.602 (n=65); net R:R 1.637 / 1.985 / 2.0 (n=65).

Giới hạn: số liệu Core phụ thuộc vào việc replay đã chạy hết DEV' chưa (`complete`).
