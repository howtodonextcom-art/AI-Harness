# V2 · Các phương án khôi phục dữ liệu lịch sử XAUUSD

Ngày: 2026-10-13 · Không phương án nào được thực hiện. Raw store, `research_history`, `raw` **không bị sửa hay xóa**. Mọi bản dữ liệu sạch sẽ là **bản dẫn xuất ở thư mục riêng** có băm và nhật ký.

## Dữ kiện nền
- Lỗi: một pseudo-bar mỗi ngày, 2012-06-26 → 2021-01-20, nhìn trước tới 24 giờ (báo cáo pháp y).
- Tải lại hôm nay từ terminal (H1 từ 2009-09, H4 từ 2004-06, D1): **không có pseudo-bar**, và phần còn lại **giống hệt** kho. Terminal đang `maxbars = 100000`, nên M1/M5/M15/M30 cũ không tải lại được (M1 từ 2026-06, M5 từ 2025-05, M15 từ 2022-07, M30 từ 2018-05).
- Pseudo-bar có mặt khi terminal ở chế độ "Max bars = Unlimited" ngày 2026-10-08/09. Chưa rõ nó gắn với chế độ đó, với server, hay với thời điểm.

## Phương án A. Sửa/khôi phục tại nguồn
- **A1 (thí nghiệm, cần chủ dự án):** trên một thư mục dữ liệu terminal **riêng** (bản portable) hoặc sau khi nâng Max bars, tải M1 của vài ngày mẫu (2013-05-14, 2016-05-12, 2019-05-14, 2020-12-15), kiểm pseudo-bar. Nếu **không** có ⇒ nguồn sạch, tải toàn bộ vào kho cách ly `data/market_v2_candidate/` (V2 vẫn chỉ đọc), kiểm toàn vẹn rồi đối chiếu. Nếu **có** ⇒ lỗi gắn với nguồn/chế độ; chuyển B.
- **A2:** H1/H4/D1 sạch có thể thay thế ngay (tải lại hôm nay, đã so khớp). M1/M5/M15/M30 chỉ khôi phục được từ A1.
- Rủi ro: A1 đụng vào cấu hình terminal đang dùng cho collector (nếu làm trên terminal chính). **Khuyến nghị bản portable riêng.** Có khả năng pseudo-bar tái xuất hiện (chính nó là điều thí nghiệm kiểm).

## Phương án B. Loại dữ liệu lỗi theo quy tắc kiểm chứng độc lập
Tạo **bản dẫn xuất sạch** từ kho: (1) bỏ pseudo-bar khỏi M1/M5/M15/M30/H1 bằng `research/clean_view.py` (định nghĩa xác định, có test, 0 dương tính giả trong 269 tháng); (2) **thay H4 bằng H4 tải lại từ terminal** (đã giống kho trừ bar 21:00 UTC bị gộp); (3) ghi băm và danh sách bar bị loại.
- **Kiểm chứng độc lập đã làm:** sau khi bỏ pseudo-bar, tập H1 kho **trùng đúng** tập H1 tải lại (2009-09 → 2020-12), M1 tổng hợp lên H1 khớp ≈ 100% (độc lập: terminal không có M1 cũ), tự tương quan toàn chuỗi về −0,03…+0,02, đỉnh/đáy lịch sử khớp các mốc công khai.
- **Chưa kiểm chứng được:** M5/M15 cũ so với nguồn ngoài (M30 chỉ từ 2018-05, M15 từ 2022-07); các bar M1 không có pseudo-bar nhưng có thể còn lỗi ẩn khác mà H1 không lộ.
- Rủi ro chọn lọc: quy tắc được xác định **sau** khi thấy kết quả Dev bị nhiễm (đã ghi sổ); nhưng quy tắc dựa hoàn toàn trên chữ ký dữ liệu (rollover, spread 0, volume cỡ ngày), khớp nguồn tải lại, không dựa vào kết quả chiến lược.

## Phương án C. Chỉ dùng giai đoạn hiện đại đã kiểm nguồn
2021-10 → 2026-10: 53 tháng VERIFIED, 8 SUSPECT. Nhưng: **Test-H (2022-01..2025-04) và Holdout (2026-05..10) bị khóa**, 2022-01..03 còn bất thường. Phần **mở** và đã kiểm chỉ gồm 2021-10..2021-12 (3 tháng) và Confirm-C 2025-05..2026-04 (12 tháng, một lần). **Không có cửa sổ thiết kế nào còn lại** ⇒ C không đủ để làm Dev.

## So sánh
| Tiêu chí | A (nguồn) | B (loại + thay H4) | C (hiện đại) |
|---|---|---|---|
| Độ phủ thời gian cho thiết kế | 2004 → 2021 nếu A1 thành công (≈ 16 năm) | 2005-06 → 2021-01 (≈ 15,6 năm, tháng recoverable) | **≈ 3 tháng mở** (2021-10..12) |
| Cửa sổ xác nhận | thêm 2019-01..2021-01 | thêm 2019-01..2021-01 và 2021-10..12 | Confirm-C (một lần) |
| Số lệnh kỳ vọng (V1 ≈17 episode/năm hiện đại; thang tương đối) | cao nhất (≈ 16 năm) | ≈ 15 năm | rất ít |
| Công suất (cần ≈ 663 lệnh cho 0,20R) | vẫn chưa đủ nhưng tốt nhất | gần như A | **không thể** |
| Nguy cơ chọn lọc | thấp nhất (sửa tại nguồn, không có luật tự đặt) | trung bình (luật tự đặt, đã kiểm) | thấp, nhưng không có dữ liệu |
| Khả năng tái lập | cần nguồn terminal ổn định (bản ghi băm) | **cao** (quy tắc + băm + mã) | cao |
| Hành động cần | chủ dự án chạy thí nghiệm terminal | chỉ phê duyệt | không |
| Rủi ro | pseudo-bar có thể tái xuất hiện; đụng terminal | bỏ sót lỗi khác ở M1/M5 cũ | không đủ dữ liệu |

## Khuyến nghị
**B làm chính, A1 làm đối chứng song song.** Lý do: B có thể làm ngay, tái lập, có kiểm chứng tải lại ở H1/H4 và không đụng terminal. A1 xác nhận nguồn gốc và có thể thay thế B bằng dữ liệu sạch từ gốc. C chỉ là bước kiểm xác nhận.
Điều kiện trước khi chạy lại bất kỳ outcome nào: (1) chủ dự án duyệt ADR-V2-019 (quy tắc hợp lệ + dẫn xuất sạch); (2) chốt thiết kế sửa lỗi mở F6; (3) điều tra 2022-Q1; (4) cửa sổ mới cho spec 1.1.0 (xem blockers). Không dùng Validation/Confirm-C/Test-H/Holdout để chọn quy tắc.
