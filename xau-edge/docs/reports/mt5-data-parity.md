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
| M1->M5 | 1499954 | 1321952 | 1321952 | 12.07% | 11.867% | 2 | 35 | 177915 | EXACT |
| M1->M15 | 515608 | 426964 | 426964 | 19.17% | 17.192% | 2 | 24 | 88535 | EXACT |
| M1->M30 | 260712 | 208841 | 208841 | 23.63% | 19.897% | 2 | 20 | 51755 | EXACT |
| M1->H1 | 132225 | 102390 | 102390 | 29.64% | 22.565% | 2 | 18 | 29718 | EXACT |
| M1->H4 | 34231 | 23735 | 23735 | 50.62% | 30.666% | 2 | 16 | 10360 | EXACT |
| M5->H1 | 132225 | 119329 | 119329 | 17.96% | 9.754% | 2 | 4 | 12831 | EXACT |
| M5->H4 | 34231 | 28313 | 28313 | 42.34% | 17.293% | 2 | 4 | 5826 | EXACT |
| H1->H4 | 34231 | 33441 | 33441 | 12.80% | 2.314% | 2 | 0 | 789 | EXACT |

* **Mọi cặp EXACT**: resample của dự án tái tạo đúng cách broker dựng nến.
* Lịch phiên FTMO (xem `docs/MT5_DATA_PLATFORM.md` §Lịch phiên): nghỉ hằng ngày 16:50-18:05 giờ New York,
  cuối tuần, cộng các cửa sổ ngày lễ/đóng cửa sớm suy ra từ chính nến thiếu của broker (chỉ chấp nhận khi
  trùng ngày lễ theo luật ngày; khoảng thiếu không giải thích được KHÔNG bị coi là ngày lễ).
* Lý do bucket còn bị loại: `BOUNDARY` (nến đầu/cuối của dữ liệu, không phải lỗi); `DATA_GAP` (nến thật sự thiếu trong
  kỷ nguyên đã kiểm chứng từ 2025, được báo cáo chứ không điền: ví dụ 14 bucket M5 ngày 2025-11-28 và vài phút đầu sau mỗi
  lần mở cửa Chủ nhật); `UNKNOWN` (trước 2025: lịch broker khác, và nến M1/M5 của thời kỳ đầu 2004–2012 rất thưa vì
  broker chỉ có nến khi có tick, nên bucket dẫn xuất thiếu nến nguồn; không thể dựng lại và không bị bịa).
* Tỷ lệ "Bỏ sau" cao ở các cặp lấy M1/M5 làm nguồn phản ánh độ thưa của M1/M5 thời kỳ đầu, không phản ánh chất lượng dữ
  liệu hiện tại; từ 2025 chỉ còn bucket biên và `DATA_GAP` thật. Mỗi khung vẫn giữ lịch sử native đầy đủ của nó.
* Không nến lịch sử thấp nào bị bịa từ khung cao hơn; mỗi khung giữ lịch sử native của nó.

## 2. Visual parity: XAU EDGE so với terminal FTMO

Trang `/market` vẽ đúng các nến mà `/md/XAUUSD/bars` trả về. Với 312 nến đã đóng lấy mẫu (52 mỗi khung:
40 nến gần đây gồm 3 nến mới nhất + các nến cách đều trong 5.000 nến gần nhất, và 12 nến ở lịch sử sâu năm 2005, 2012, 2019), script lấy cùng nến từ terminal qua một
đường độc lập (`copy_rates_range` thô, giờ broker tính bằng `zoneinfo` New York+7, KHÔNG dùng BrokerClock
của dự án) rồi so thời điểm, open, high, low, close và tick volume.

**Kết quả: 312 nến so sánh, 0 sai lệch.** Biểu đồ của terminal vẽ từ cùng dữ liệu terminal này, nên
đây là phép so sánh số tương đương với đặt hai biểu đồ cạnh nhau, từng nến một. Cửa sổ terminal cố ý
không chụp màn hình vì có thể lộ thông tin tài khoản; ảnh trang XAU EDGE thật ở
`docs/reports/screenshots/market-v2-desktop.png` và `market-v2-mobile.png`.

Mẫu (giờ broker = UTC+3 vào tháng 10 vì New York đang ở giờ mùa hè):

| Khung | UTC | Giờ broker | OHLC terminal | OHLC XAU EDGE | Vol terminal | Vol XAU EDGE | Kết quả |
|---|---|---|---|---|---|---|---|
| M1 | 2026-10-09T10:59 | 2026-10-09T13:59 | 4181.34/4181.67/4179.16/4179.18 | 4181.34/4181.67/4179.16/4179.18 | 207 | 207 | MATCH |
| M1 | 2026-10-08T02:12 | 2026-10-08T05:12 | 4137.70/4138.48/4137.30/4138.48 | 4137.70/4138.48/4137.30/4138.48 | 124 | 124 | MATCH |
| M1 | 2019-06-14T20:54 | 2019-06-14T23:54 | 1341.10/1341.10/1340.82/1340.82 | 1341.10/1341.10/1340.82/1340.82 | 34 | 34 | MATCH |
| M5 | 2026-10-09T10:45 | 2026-10-09T13:45 | 4180.79/4180.79/4179.62/4180.26 | 4180.79/4180.79/4179.62/4180.26 | 574 | 574 | MATCH |
| M5 | 2026-09-30T12:20 | 2026-09-30T15:20 | 4189.17/4191.20/4182.69/4190.28 | 4189.17/4191.20/4182.69/4190.28 | 1281 | 1281 | MATCH |
| M5 | 2019-06-14T20:50 | 2019-06-14T23:50 | 1341.13/1341.21/1340.82/1340.82 | 1341.13/1341.21/1340.82/1340.82 | 100 | 100 | MATCH |
| M15 | 2026-10-09T10:15 | 2026-10-09T13:15 | 4185.19/4185.95/4183.61/4183.88 | 4185.19/4185.95/4183.61/4183.88 | 1436 | 1436 | MATCH |
| M15 | 2026-09-10T20:15 | 2026-09-10T23:15 | 4322.86/4322.90/4316.20/4318.43 | 4322.86/4322.90/4316.20/4318.43 | 1686 | 1686 | MATCH |
| M15 | 2019-06-14T20:45 | 2019-06-14T23:45 | 1341.18/1341.32/1340.82/1340.82 | 1341.18/1341.32/1340.82/1340.82 | 168 | 168 | MATCH |
| M30 | 2026-10-09T09:30 | 2026-10-09T12:30 | 4186.70/4187.68/4182.69/4185.88 | 4186.70/4187.68/4182.69/4185.88 | 3333 | 3333 | MATCH |
| M30 | 2026-08-13T04:00 | 2026-08-13T07:00 | 4400.04/4400.26/4391.49/4398.05 | 4400.04/4400.26/4391.49/4398.05 | 4926 | 4926 | MATCH |
| M30 | 2019-06-14T20:30 | 2019-06-14T23:30 | 1341.67/1341.71/1340.82/1340.82 | 1341.67/1341.71/1340.82/1340.82 | 320 | 320 | MATCH |
| H1 | 2026-10-09T08:00 | 2026-10-09T11:00 | 4194.84/4201.59/4187.12/4187.68 | 4194.84/4201.59/4187.12/4187.68 | 9818 | 9818 | MATCH |
| H1 | 2026-06-16T15:00 | 2026-06-16T18:00 | 4324.33/4343.27/4320.96/4335.13 | 4324.33/4343.27/4320.96/4335.13 | 14584 | 14584 | MATCH |
| H1 | 2019-06-14T20:00 | 2019-06-14T23:00 | 1340.99/1341.71/1340.78/1340.82 | 1340.99/1341.71/1340.78/1340.82 | 587 | 587 | MATCH |
| H4 | 2026-10-08T21:00 | 2026-10-09T00:00 | 4132.09/4150.35/4131.73/4143.16 | 4132.09/4150.35/4131.73/4143.16 | 17103 | 17103 | MATCH |
| H4 | 2025-07-21T05:00 | 2025-07-21T08:00 | 3357.72/3370.70/3357.58/3365.93 | 3357.72/3370.70/3357.58/3365.93 | 13981 | 13981 | MATCH |
| H4 | 2019-06-14T17:00 | 2019-06-14T20:00 | 1347.04/1347.14/1337.73/1340.82 | 1347.04/1347.14/1337.73/1340.82 | 9147 | 9147 | MATCH |

Phát hiện phụ có giá trị: `copy_rates_range` coi `datetime` KHÔNG múi giờ là giờ cục bộ của máy (máy này
UTC+7), nên truyền `12:17` trần trả nến lúc 05:17 UTC. Mọi mã của dự án luôn truyền datetime có múi giờ
(giờ server gắn nhãn UTC); script kiểm tra đã bắt đúng lỗi này khi viết.

Giới hạn: đây là so sánh dữ liệu, không phải so sánh điểm ảnh; hình dạng nến phụ thuộc tỷ lệ trục của
từng ứng dụng.
