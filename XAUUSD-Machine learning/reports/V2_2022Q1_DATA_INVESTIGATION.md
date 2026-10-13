# V2 · Điều tra chất lượng dữ liệu 2022-Q1 (chỉ giá và tick)

Ngày: 2026-10-13 · Phạm vi theo quyết định Gate B2: **chỉ giá/tick và nguồn**. Không đọc tín hiệu, PnL hay outcome của Test-H. Mã: `scripts/research/investigate_2022q1.py`, `scripts/research/provider_crosscheck.py`. Dữ liệu: `docs/research/investigation_2022q1.json`, `provider_crosscheck.json`, `tick_defect_2022q1.json`.

## Kết luận
Bất thường 2022-Q1 **nằm ở kho TICK, không phải ở nến**. Nến M1/H1 của FTMO khớp nhà cung cấp độc lập (MetaQuotes-Demo); tick FTMO của giai đoạn **2022-01-04 → 2022-03-21** lệch khỏi cả hai tới $12. Nhãn SUSPECT ở báo cáo Gate B xuất phát từ việc dùng chính kho tick lỗi làm nguồn kiểm chứng.

## Bằng chứng
1. **Ticks ↔ nến M1 (cùng giá bid), theo ngày.** Kiểm soát: 2021-11 và 2021-12 khớp 100% (≤ 10 cent); 2022-04 và 2022-05 khớp 99,3% và 98,9%. Giai đoạn lỗi: 2022-01 trung bình 56% (15/26 ngày dưới 90%), 2022-02 53% (24/24 ngày), 2022-03 58% (18/27 ngày). Ngày đầu 2022-01-04, ngày cuối 2022-03-21; không ngày lỗi nào ngoài khoảng đó.
2. **Không phải lệch giờ, giá mid hay ask.** Dịch ±2 phút không cải thiện; mid/ask còn kém hơn bid; không có quote bắt chéo, không trùng timestamp; có ngày khớp 99,7% (2022-01-20, 01-25) xen giữa các ngày lệch, nên không phải đổi quy ước giá cố định.
3. **Ba nguồn so với nhau (H1, trung vị | lớn nhất của max|ΔOHLC|, USD):**
| Ngày | nến FTMO ↔ tick FTMO | MetaQuotes ↔ tick FTMO | **MetaQuotes ↔ nến FTMO** |
|---|---|---|---|
| 2022-01-06 | 2,19 / 10,74 | 2,28 / 10,72 | **0,09 / 1,92** |
| 2022-01-11 | 1,93 / 4,91 | 1,97 / 4,86 | **0,06 / 0,89** |
| 2022-02-24 | 0,20 / 1,68 | 0,28 / 1,75 | **0,13 / 0,28** |
| 2022-03-10 | 0,14 / 3,65 | 0,26 / 3,71 | **0,10 / 0,57** |
| 2022-01-25 (ngày tốt) | 0,00 / 0,00 | 0,08 / 0,23 | 0,08 / 0,23 |
| 2022-04-06 (kiểm soát) | 0,00 / 0,00 | 0,11 / 0,50 | 0,11 / 0,50 |
Trên các ngày lỗi, **nến FTMO và MetaQuotes đồng thuận, tick FTMO không đồng thuận với cả hai.** (Ghi chú: MetaQuotes theo giờ DST châu Âu, FTMO theo DST Mỹ; từ 13 đến 27/03/2022 hai máy chủ lệch một giờ, đã xử lý bằng cách khớp mỗi bar ở offset 2 hoặc 3.)
4. **Chéo nhà cung cấp theo tháng, H1 (trung vị | p95 | share trong 1 USD):** 2022-01 0,07 | 0,21 | 99,8%; 2022-02 0,07 | 0,28 | 98,9%; 2022-03 0,12 | 0,46 | 97,6%; so với 2022-05 0,09 | 0,33 | 100%. Cùng mức nhiễu giữa hai nhà cung cấp như các tháng sạch.

## Hệ quả
- **Nến 2022-01..03 không bị nghi ngờ.** Test-H không bị chặn vì lý do này; nó vẫn khóa.
- **Tick 2022-01-04..03-21 không được dùng** cho mô hình chi phí/spread hay mọi kiểm tra dựa trên tick (đã ghi vào manifest `known_source_defects` và `docs/research/tick_defect_2022q1.json`).
- Phân loại tháng cần **hai nguồn** cho giai đoạn hiện đại (tick và nhà cung cấp khác), và khi hai nguồn bất đồng thì phải xem nguồn thứ ba trước khi gán SUSPECT. Cập nhật vào ADR-V2-019 khi chủ dự án duyệt.

## Giới hạn
Không xác định được **vì sao** tick lỗi (lỗi thu thập, nguồn tick của broker, hay thay đổi bộ lọc tick): cần nhật ký collector ngày 2022 hoặc broker. Mẫu: mọi ngày của 7 tháng (không phải mẫu 3 ngày). Không có nguồn tick thứ hai.
