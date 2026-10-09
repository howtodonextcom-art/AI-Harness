# Parity dữ liệu MT5

Lớp D (chất lượng dữ liệu; không phân tích kết quả thị trường). Hai kiểm tra độc lập: (1) nến native của
broker so với nến dẫn xuất bằng resample tất định; (2) cái XAU EDGE vẽ so với chính terminal FTMO.
Số liệu thô: `mt5-data-parity.json`, `mt5-visual-parity.json`. Sinh bởi `scripts/market_data_parity.py` và
`scripts/verify_visual_parity.py`.

## 1. Native so với dẫn xuất (đồng hồ broker `NY+7`, lịch phiên FTMO)

Mỗi nến so sánh được đều phải khớp tuyệt đối OHLC và tick volume. Cột "Bỏ trước/sau" là tỷ lệ bucket bị
loại vì thiếu nến nguồn khi dùng lịch mặc định (trước) và lịch phiên FTMO có ngày lễ (sau).

| Cặp | Native | Dẫn xuất | So sánh | Bỏ trước | Bỏ sau | BOUNDARY | DATA_GAP | UNKNOWN | Kết luận |
|---|---|---|---|---|---|---|---|---|---|
| M1->M5 | 20064 | 20064 | 20064 | 0.01% | 0.010% | 2 | 0 | 0 | EXACT |
| M1->M15 | 6760 | 6760 | 6760 | 2.19% | 0.030% | 2 | 0 | 0 | EXACT |
| M1->M30 | 3379 | 3379 | 3379 | 4.38% | 0.059% | 2 | 0 | 0 | EXACT |
| M1->H1 | 1689 | 1689 | 1689 | 8.81% | 0.118% | 2 | 0 | 0 | EXACT |
| M1->H4 | 441 | 441 | 441 | 33.63% | 0.451% | 2 | 0 | 0 | EXACT |
| M5->H1 | 8431 | 8430 | 8430 | 8.73% | 0.036% | 2 | 1 | 0 | EXACT |
| M5->H4 | 2205 | 2204 | 2204 | 33.35% | 0.136% | 2 | 1 | 0 | EXACT |
| H1->H4 | 25713 | 25234 | 25234 | 10.25% | 1.867% | 1 | 0 | 479 | EXACT |

* **Mọi cặp EXACT**: resample của dự án tái tạo đúng cách broker dựng nến.
* Lịch phiên FTMO (xem `docs/MT5_DATA_PLATFORM.md` §Lịch phiên): nghỉ hằng ngày 16:50-18:05 giờ New York,
  cuối tuần, cộng các cửa sổ ngày lễ/đóng cửa sớm suy ra từ chính nến thiếu của broker (chỉ chấp nhận khi
  trùng ngày lễ theo luật ngày; khoảng thiếu không giải thích được KHÔNG bị coi là ngày lễ).
* Lý do bucket còn bị loại: `BOUNDARY` (nến đầu/cuối của dữ liệu, không phải lỗi), `DATA_GAP` (nến thật sự
  thiếu trong kỷ nguyên đã kiểm chứng từ 2025: 1 bucket M5 ngày 2025-12-07, được báo cáo chứ không điền),
  `UNKNOWN` (kỷ nguyên cũ, chủ yếu 2010–2020 và 2 bucket 2022: lịch broker khác, chưa mô hình hóa; chỉ có ở H1→H4 lịch sử).
* Không nến lịch sử thấp nào bị bịa từ khung cao hơn; mỗi khung giữ lịch sử native của nó.

## 2. Visual parity: XAU EDGE so với terminal FTMO

Trang `/market` vẽ đúng các nến mà `/md/XAUUSD/bars` trả về. Với 240 nến đã đóng lấy mẫu (40 mỗi khung:
3 nến mới nhất + các nến cách đều trong 5.000 nến gần nhất), script lấy cùng nến từ terminal qua một
đường độc lập (`copy_rates_range` thô, giờ broker tính bằng `zoneinfo` New York+7, KHÔNG dùng BrokerClock
của dự án) rồi so thời điểm, open, high, low, close và tick volume.

**Kết quả: 240 nến so sánh, 0 sai lệch.** Biểu đồ của terminal vẽ từ cùng dữ liệu terminal này, nên
đây là phép so sánh số tương đương với đặt hai biểu đồ cạnh nhau, từng nến một. Cửa sổ terminal cố ý
không chụp màn hình vì có thể lộ thông tin tài khoản; ảnh trang XAU EDGE thật ở
`docs/reports/screenshots/market-v2-desktop.png` và `market-v2-mobile.png`.

Mẫu (giờ broker = UTC+3 vào tháng 10 vì New York đang ở giờ mùa hè):

| Khung | UTC | Giờ broker | OHLC terminal | OHLC XAU EDGE | Vol terminal | Vol XAU EDGE | Kết quả |
|---|---|---|---|---|---|---|---|
| M1 | 2026-10-09T09:43 | 2026-10-09T12:43 | 4184.99/4185.20/4184.55/4184.70 | 4184.99/4185.20/4184.55/4184.70 | 113 | 113 | MATCH |
| M1 | 2026-10-07T10:11 | 2026-10-07T13:11 | 4116.78/4118.04/4116.55/4117.87 | 4116.78/4118.04/4116.55/4117.87 | 140 | 140 | MATCH |
| M1 | 2026-10-09T07:26 | 2026-10-09T10:26 | 4190.99/4192.78/4190.58/4192.37 | 4190.99/4192.78/4190.58/4192.37 | 166 | 166 | MATCH |
| M5 | 2026-10-09T09:30 | 2026-10-09T12:30 | 4186.70/4187.68/4184.45/4184.45 | 4186.70/4187.68/4184.45/4184.45 | 631 | 631 | MATCH |
| M5 | 2026-09-25T11:50 | 2026-09-25T14:50 | 4302.55/4304.61/4302.41/4303.45 | 4302.55/4304.61/4302.41/4303.45 | 949 | 949 | MATCH |
| M5 | 2026-10-08T22:05 | 2026-10-09T01:05 | 4132.09/4134.99/4131.73/4134.52 | 4132.09/4134.99/4131.73/4134.52 | 369 | 369 | MATCH |
| M15 | 2026-10-09T09:00 | 2026-10-09T12:00 | 4187.67/4187.98/4185.14/4185.54 | 4187.67/4187.98/4185.14/4185.54 | 2009 | 2009 | MATCH |
| M15 | 2026-08-30T22:00 | 2026-08-31T01:00 | 4446.03/4459.45/4445.89/4458.94 | 4446.03/4459.45/4445.89/4458.94 | 1834 | 1834 | MATCH |
| M15 | 2026-10-07T20:45 | 2026-10-07T23:45 | 4108.80/4109.32/4108.36/4109.15 | 4108.80/4109.32/4108.36/4109.15 | 208 | 208 | MATCH |
| M30 | 2026-10-09T08:00 | 2026-10-09T11:00 | 4194.84/4201.59/4193.51/4198.35 | 4194.84/4201.59/4193.51/4198.35 | 5140 | 5140 | MATCH |
| M30 | 2026-07-20T11:30 | 2026-07-20T14:30 | 4022.07/4040.57/4021.40/4025.20 | 4022.07/4040.57/4021.40/4025.20 | 7596 | 7596 | MATCH |
| M30 | 2026-10-06T08:30 | 2026-10-06T11:30 | 4146.00/4155.47/4145.08/4155.39 | 4146.00/4155.47/4145.08/4155.39 | 5640 | 5640 | MATCH |
| H1 | 2026-10-09T06:00 | 2026-10-09T09:00 | 4193.06/4198.72/4189.20/4196.08 | 4193.06/4198.72/4189.20/4196.08 | 10089 | 10089 | MATCH |
| H1 | 2026-04-28T06:00 | 2026-04-28T09:00 | 4631.91/4642.68/4623.19/4628.89 | 4631.91/4642.68/4623.19/4628.89 | 14744 | 14744 | MATCH |
| H1 | 2026-10-01T07:00 | 2026-10-01T10:00 | 4181.52/4183.33/4154.32/4163.52 | 4181.52/4183.33/4154.32/4163.52 | 15259 | 15259 | MATCH |
| H4 | 2026-10-08T21:00 | 2026-10-09T00:00 | 4132.09/4150.35/4131.73/4143.16 | 4132.09/4150.35/4131.73/4143.16 | 17103 | 17103 | MATCH |
| H4 | 2025-01-10T02:00 | 2025-01-10T04:00 | 2670.92/2675.78/2670.45/2674.90 | 2670.92/2675.78/2670.45/2674.90 | 12898 | 12898 | MATCH |
| H4 | 2026-09-08T01:00 | 2026-09-08T04:00 | 4426.16/4442.81/4417.01/4435.94 | 4426.16/4442.81/4417.01/4435.94 | 42789 | 42789 | MATCH |

Phát hiện phụ có giá trị: `copy_rates_range` coi `datetime` KHÔNG múi giờ là giờ cục bộ của máy (máy này
UTC+7), nên truyền `12:17` trần trả nến lúc 05:17 UTC. Mọi mã của dự án luôn truyền datetime có múi giờ
(giờ server gắn nhãn UTC); script kiểm tra đã bắt đúng lỗi này khi viết.

Giới hạn: đây là so sánh dữ liệu, không phải so sánh điểm ảnh; hình dạng nến phụ thuộc tỷ lệ trục của
từng ứng dụng.
