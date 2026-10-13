# ADR-V2-019 rev.2 (PROPOSED, chờ chủ dự án): phân loại tháng hiện đại bằng hai nguồn

Trạng thái: **PROPOSED, chưa áp dụng**. Quarantine 2021-02..2021-09 **được giữ nguyên**; không sửa RAW; không đổi cửa sổ khóa; manifest `997d73f8…` không đổi.

## 1. Quy tắc đề xuất
Một tháng hiện đại (sau 2021-01-21, khi lịch sử FTMO và MetaQuotes tách nguồn) chỉ được xếp PASS khi **cả hai** nguồn đồng ý: (a) kiểm tra bằng tick của chính nhà cung cấp (khớp M1 ≥ 97%); (b) kiểm tra chéo nhà cung cấp (MetaQuotes-Demo) trên H1 với **đối sánh offset giờ** (DST Mỹ/Âu). Khi hai nguồn bất đồng, xem nguồn thứ ba trước khi gán SUSPECT (bài học 2022-Q1: tick lỗi chứ không phải nến).

## 2. Bằng chứng hiện có cho các tháng quarantine (`provider_crosscheck.json`, H1, USD)
| Tháng | bars | trung vị | p95 | p99 | max | trong 1 USD |
|---|---|---|---|---|---|---|
| 2021-02 | 370 | 0,06 | 0,46 | 1,66 | 4,6 | 97,6% |
| **2021-03** | 496 | **0,16** | **2,81** | 4,40 | 6,0 | **74,2%** |
| 2021-04 | 458 | 0,05 | 0,28 | 1,31 | 2,45 | 98,0% |
| 2021-05 | 444 | 0,06 | 0,26 | 1,87 | 3,76 | 97,8% |
| 2021-06 | 457 | 0,06 | 0,65 | 2,52 | 4,77 | 96,7% |
| 2021-07 | 479 | 0,05 | 0,16 | 0,62 | 1,66 | 99,2% |
| 2021-08 | 499 | 0,05 | 0,16 | 0,26 | 2,91 | 99,4% |
| 2021-09 | 498 | 0,06 | 0,18 | 0,85 | 4,13 | 99,0% |
Tham chiếu (tháng đã PASS bằng tick): 2021-10 0,06/0,16/99,4%; 2021-11 0,07/0,22/99,0%; 2021-12 0,08/0,21/99,8%; 2022-01 0,07/0,21/99,8%; trước 2021-01-21 hai nguồn **trùng tuyệt đối** (trung vị 0).

## 2.1 Đọc kết quả
- Bảy tháng (02, 04–09) có độ chênh cùng bậc với các tháng đã PASS sau khi hai nguồn tách (trung vị 0,05–0,06; p95 chủ yếu ≤0,65).
- **2021-03 là ngoại lệ rõ** (74,2% trong 1 USD, p95 2,81). Giả thuyết **chưa kiểm**: tuần lệch DST Mỹ/Âu (13–28/03/2021) chưa được đối sánh offset như đã làm cho 2022-03. Cần chạy lại kiểm tra với đối sánh offset trước khi kết luận.
- Chưa có kiểm tra tick cho các tháng này (kho tick tồn tại, cần phân tích riêng như `tick_check`).

## 3. Đề xuất (không tự thực hiện)
1. Chủ dự án duyệt quy tắc hai nguồn (mục 1).
2. Chạy `tick_check` cho 2021-02..09 và kiểm tra chéo có đối sánh offset; xuất bằng chứng vào `docs/research/`.
3. Nếu cả hai nguồn đạt ngưỡng (khớp M1 ≥ 97% với tick; H1 ≥ 99,9% sau offset... như các tháng PASS), đề nghị mở khóa từng tháng bằng một phiên bản manifest mới (manifest cũ không sửa tại chỗ); 2021-03 chỉ khi đối sánh offset giải thích được ngoại lệ.
4. Các tháng được mở khóa vẫn thuộc **RESERVED** cho đến khi chủ dự án giao vào cửa sổ nào; không vào DEV'/VALIDATION' tự động.

## 4. Không làm
Không mở khóa, không đổi nhãn tháng nào, không chạm RAW. Tài liệu chỉ tổng hợp bằng chứng đã có.
