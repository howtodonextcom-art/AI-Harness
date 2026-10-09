# Parity dữ liệu MT5: nến native so với nến dẫn xuất

Lớp D (chất lượng dữ liệu; không phân tích kết quả thị trường). Sinh bởi `scripts/market_data_parity.py`
(số liệu thô: `mt5-data-parity.json`), trên nến đã đóng trong `data/market` (FTMO DEMO, 2026-10-09).

Phương pháp: nến native của broker so với nến resample từ khung mịn hơn (`resample_bars`, bucket theo
đồng hồ broker `NY+7`, bucket thiếu nến nguồn bị loại chứ không điền giả), so từng nến trên phần giao nhau.

| Cặp | Native | Dẫn xuất | So sánh | Bucket bị loại | Sai OHLC | Sai tick volume | Kết luận |
|---|---|---|---|---|---|---|---|
| M1->M5 | 19800 | 19800 | 19800 | 2 | 0 | 0 | EXACT |
| M1->M15 | 6671 | 6527 | 6527 | 146 | 0 | 0 | EXACT |
| M1->M30 | 3335 | 3191 | 3191 | 146 | 0 | 0 | EXACT |
| M1->H1 | 1667 | 1522 | 1522 | 147 | 0 | 0 | EXACT |
| M1->H4 | 435 | 290 | 290 | 147 | 0 | 0 | EXACT |
| M5->H1 | 8342 | 7616 | 7616 | 728 | 0 | 0 | EXACT |
| M5->H4 | 2181 | 1455 | 1455 | 728 | 0 | 0 | EXACT |
| H1->H4 | 25439 | 22893 | 22893 | 2547 | 0 | 0 | EXACT |

**Kết luận**: mọi nến so sánh được đều khớp tuyệt đối (OHLC và tick volume), cho cả 8 cặp. Vậy resample
tất định của dự án tái tạo đúng cách broker dựng nến, và đồng hồ `NY+7` đúng.

Bucket bị loại (~2%) là do `MarketCalendar` mặc định không biết giờ nghỉ hằng ngày/ngày lễ nên coi các
nến nguồn thiếu là bất thường; chúng được báo cáo, không bị điền. "Native không có bản dẫn xuất" ≈ số
bucket bị loại (+ biên). Chưa so sánh bằng mắt với biểu đồ FTMO; xem `docs/MT5_DATA_PLATFORM.md` mục 7.
