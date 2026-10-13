# V2 · Kiểm toán cơ sở dữ liệu và đường ống dữ liệu

Ngày: 2026-10-13 · Không sửa RAW, không chạm cửa sổ khóa. Chi tiết nền: `V2_CLEAN_DATA_PIPELINE_REPORT.md`, `V2_F6_DETERMINISTIC_REPLAY_REPORT.md`, `V2_A1_PROVENANCE_REPORT.md`, `V2_2022Q1_DATA_INVESTIGATION.md`.

## 1. Kho dữ liệu
| Kho | Kích thước (đo) | Vai trò | Ghi chú |
|---|---|---|---|
| V1 market RAW | 1,8 GB (ticks 1.395 MB, M1 92, M5 22, M15 9, M30 5, H1 3, H4 2) | nguồn thô, collector ghi | **có bar giả FTMO ≤ 2021-01-20** |
| V2 `data/clean_store` | 95 MB, 1.140 tệp | dẫn xuất sạch, hash, read-only | 190 tháng PASS, 9 quarantine |
| V2 `data/research` | 29 MB | checkpoint, tín hiệu | |
| `paper.sqlite3` (WAL) | nhỏ | positions, journal, decision_log, human_decisions, account | |
| logs | 5,8 MB | | |
| V1 video_work | 305 MB | không thuộc V2 | |

## 2. Các câu hỏi bắt buộc
| Hạng mục | Kết luận | Nhãn |
|---|---|---|
| Provenance, hash | manifest tự băm (997d73f8…), sha256 từng tệp kiểm trước khi đọc | TESTED + VERIFIED |
| Dedup / thứ tự | 0 vi phạm trùng/ngược thứ tự ở tháng PASS | VERIFIED |
| Thời gian / DST | FTMO theo DST Mỹ; MetaQuotes theo DST Âu; 2022-03 lệch 1 giờ đã xử lý | VERIFIED (nghiên cứu) |
| Nhất quán đa khung | M1→M5→M15/M30/H1→H4 đồng bộ 100% ở 190 tháng PASS | VERIFIED |
| Cổng chất lượng | tháng không chứng minh được ⇒ không có tệp, chỉ lý do | TESTED |
| Hiệu năng | tail 450 bar/khung, `compute_analysis` ~17 ms | VERIFIED |
| Nhất quán khi crash | ghi tạm → fsync → thay thế + `.prev` (checkpoint); SQLite WAL | TESTED (checkpoint); SQLite crash trực tiếp NOT MEASURED |
| Replay tất định | restore = chạy liên tục từng bit (21 điểm dừng + 2 tháng thật) | TESTED + VERIFIED |
| Backup / recovery | có thư mục backup (liệt kê khi kiểm kho); **chưa thử khôi phục** từ backup trong P0 | NOT MEASURED |
| Tăng trưởng / retention | ticks 1,4 GB chiếm 77% kho; chưa có chính sách retention được tài liệu hóa | UNVERIFIED |

## 3. Có thể dữ liệu nhiễm lọt vào nghiên cứu outcome không?
Chặn đã xác minh: `CleanBarStore` chỉ phục vụ tháng PASS, kiểm hash từng tệp, từ chối quarantine/khoảng ngoài; pipeline `require_clean`; `cand_signals.py` từ chối chạy chia tháng; `cand_replay.py` chỉ nhận DEV'/VALIDATION'/RESERVED. Kết luận: **trong đường V2, không thể lọt âm thầm** (TESTED).
**Rủi ro còn lại (ngoài hàng rào):**
1. Mã nghiên cứu V1 (Edge Program H01–H10, ML V0) vẫn có thể đọc RAW; chỉ được **gắn nhãn** UNRELIABLE/CONTAMINATED trong register và `DATA_DEFECT_NOTICE.md`, không bị chặn kỹ thuật.
2. Kho tick 2022-01-04..03-21 lỗi (57 ngày): chỉ ghi nhận trong manifest `known_source_defects`; mã mô hình chi phí/spread dựa tick **không tự động bị chặn** (cần cổng).
3. Nguồn đối chiếu (MetaQuotes-Demo) chưa độc lập tuyệt đối về nguồn gốc lịch sử.

## 4. Mâu thuẫn trung thực cần nhớ
Báo cáo Gate B từng gọi lần tải lại là "từ broker"; thực tế là terminal MetaQuotes-Demo; đã đính chính. A1 chưa xong nên chưa biết bar giả do **máy chủ FTMO** hay **cache cục bộ**.

## 5. Khuyến nghị (chưa làm)
(a) Cổng kỹ thuật chặn mọi truy cập tick trong 2022-01-04..03-21 qua một API đọc duy nhất; (b) kiểm khôi phục backup định kỳ có biên bản; (c) chính sách retention ticks; (d) cập nhật ADR-V2-019 sang phân loại hai nguồn.

## 6. Giới hạn
Không đo tốc độ truy vấn clean store theo nhiều cửa sổ; không crash-test SQLite; không kiểm backup có khôi phục được.
