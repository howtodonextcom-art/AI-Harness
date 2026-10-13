# V2 · GATE B3: nộp báo cáo để duyệt (dữ liệu sạch và replay tất định)

Ngày: 2026-10-13 · **Dừng tại Cổng B3.** Không chạy lại outcome backtest, không chọn/đóng băng Candidate, không mở Validation/Confirm-C/Test-H/Holdout, không đổi V1 control, ngưỡng hay rủi ro, không giao dịch thật, không tuyên bố edge.

## 1. Sáu quyết định của Gate B2 và kết quả
| # | Quyết định | Kết quả | Báo cáo |
|---|---|---|---|
| 1 | ADR-V2-019 có điều kiện: giữ RAW, kho sạch riêng, loại bar giả, khôi phục H4, manifest + SHA256, đồng bộ M1/H1/H4, chặn dữ liệu lỗi | **XONG.** 190 tháng PASS, 9 quarantine; 2.216 bar giả M1 bị loại; 2.182 bar H4 khôi phục; đồng bộ 100% ở mọi tháng PASS; xây hai lần giống từng bit; RAW không đổi (băm trước/sau); `CleanBarStore` kiểm hash từng tệp và không bỏ qua im lặng tháng quarantine | `V2_CLEAN_DATA_PIPELINE_REPORT.md` |
| 2 | Sửa F6: giữ `planned_stop`, checkpoint bền, replay liên tục qua tháng, restart bằng chạy liên tục, không khôi phục được ⇒ WAIT | **XONG.** Restore từ checkpoint = chạy liên tục từng bit (mô phỏng 21 điểm dừng + 2 tháng dữ liệu thật); cold start ⇒ WAIT tới khi chứng minh được trạng thái | `V2_F6_DETERMINISTIC_REPLAY_REPORT.md`, ADR-V2-020 |
| 3 | Cửa sổ DEV' 2005-06..2018-12, VALIDATION' 2019-01..2021-01 (chỉ tháng đã kiểm sau làm sạch), quarantine 2021-02..09, giữ riêng 2021-10..12; chưa chốt spec 1.1.0 | **XONG, spec 1.1.0 chỉ ở dạng ĐỀ XUẤT** (`cand_v2_spec_1.1.0.PROPOSED.json`, không băm, evaluation gate không nhận). DEV' 163/163 PASS; VALIDATION' 24/25 (2021-01 loại); RESERVED 3/3. Confirm-C, Test-H, Holdout không được xây | báo cáo kho sạch |
| 4 | A1 trên MT5 portable riêng | **MỘT PHẦN, đã trả lời câu hỏi chính.** Terminal FTMO hôm nay vẫn phục vụ bar giả ở M1/M5/M15/M30/H1/H4 (giống kho 100%). **Đính chính lớn:** lần "tải lại broker" trước đó đến từ terminal **MetaQuotes-Demo**, một nhà cung cấp khác. Bản portable FTMO đã sao chép, công cụ probe đã viết, **chờ anh đăng nhập** | `V2_A1_PROVENANCE_REPORT.md` |
| 5 | V1 Edge Program H01–H10 = UNRELIABLE; ML V0 = CONTAMINATED; không xóa, không chạy lại | **XONG:** `docs/research/research_status_register.json` + ghi chú `xau-edge/docs/research/DATA_DEFECT_NOTICE.md` | sổ đăng ký |
| 6 | Điều tra 2022-Q1 (chỉ giá/tick) | **XONG.** Lỗi ở **kho tick** 2022-01-04 → 2022-03-21 (57 ngày), **nến không lỗi** (khớp MetaQuotes-Demo). Nhãn SUSPECT cũ là do dùng tick lỗi làm nguồn kiểm | `V2_2022Q1_DATA_INVESTIGATION.md` |

## 2. Hai phát hiện mới đáng chú ý
1. **Terminal em dùng để "tải lại broker" không phải FTMO** (máy có hai terminal). Đã đính chính các báo cáo Gate B và ghi nhà cung cấp vào manifest. Điều này làm bằng chứng **mạnh hơn** (nhà cung cấp khác) nhưng sai nhãn cũ; đáng ghi nhận vì em suýt kết luận "terminal hôm nay không còn phục vụ bar giả" cho FTMO.
2. **Bar giả là dữ liệu của máy chủ FTMO**, không phải lỗi V1: ≤ 2020-12 lịch sử FTMO **bằng** lịch sử MetaQuotes **cộng** bản ghi ngày chèn vào lúc mở phiên.

## 3. Kiểm thử và chất lượng
`pytest` **1.925 passed** (trước Gate B3: 1.891; thêm 34 test: kho sạch, manifest, replay), `ruff` sạch, `mypy --strict` 60 tệp sạch, test khóa chiến lược V1 xanh, spec 1.0.0 giữ nguyên hash. Bảng test mới:
- `test_clean_store.py` (15): làm sạch, RAW không đổi, tái lập từng bit, tháng không có gì để làm sạch ra giống hệt, bucket trộn dựng lại từ M1, bar giả đứng một mình trong H4 bị loại, 4 lý do quarantine, đọc có kiểm hash, sửa tệp/manifest bị từ chối, tháng quarantine giữa khoảng không bị bỏ qua.
- `test_clean_store_manifest.py` (9): hash manifest, phạm vi không chạm cửa sổ khóa, mỗi tháng PASS đủ 6 khung + hash thô + đồng bộ ≥ 99,5%, quyết định của chủ dự án nằm trong manifest, danh sách bar loại khớp hash, nhà cung cấp đối chiếu được ghi, spec đề xuất không phải spec đã đóng băng, `cand_signals.py` từ chối chạy chia tháng.
- `test_replay.py` (10) và các test candidate: F6.
Không có test đơn vị cho: thăm dò terminal sống, mã A1 probe, điều tra 2022-Q1 (chạy trên kho thật, kết quả trong `docs/research/`).

## 4. Việc đã làm với terminal đang chạy
Thăm dò **chỉ-đọc** terminal FTMO (`copy_rates_range`, khoảng 22.000 bar, 3 lần gọi); không gọi hàm giao dịch, không đọc tài khoản, không đổi cài đặt. Anh đã giao A1 cho terminal portable riêng; em ghi nhận để anh quyết định có chấp nhận hay không.

## 5. Điều chưa xong (blockers cho bước sau)
| # | Việc | Cần |
|---|---|---|
| 1 | Duyệt **spec 1.1.0** (đang là đề xuất) rồi băm và đóng băng | chủ dự án |
| 2 | A1 hoàn tất: đăng nhập terminal portable (Max bars Unlimited), chạy `a1_probe.py` | chủ dự án đăng nhập; em chạy |
| 3 | 2021-02..09: có bằng chứng chéo nhà cung cấp tương đương các tháng đã kiểm; có mở khóa không? | chủ dự án |
| 4 | Phân loại tháng hiện đại cần **hai nguồn** (tick + nhà cung cấp khác); cập nhật ADR-V2-019 | chủ dự án duyệt |
| 5 | Chạy Stage A trên DEV' bằng `cand_replay.py` (≈ 4–8 giờ một lõi, 1 tiến trình, ưu tiên thấp) **chỉ tạo tín hiệu, chưa outcome** | chủ dự án cho phép sau khi chốt spec |
| 6 | Tích hợp candidate vào engine sống (nếu có) cần thiết kế restart/cold start sống | sau khi có kết quả nghiên cứu |
| 7 | Nếu muốn nguồn bên thứ ba có giấy phép để "VERIFIED_VALID" thật sự độc lập | chủ dự án |

## 6. Điểm trung thực
Vẫn chưa có outcome hợp lệ nào cho Candidate. Công suất thống kê không đổi (≈ 663 lệnh cho 0,20R). Chiến lược vẫn UNVALIDATED; không có tuyên bố edge. Bộ não V2 vẫn là gating + vòng đời trên nhãn của V1; cần nghiên cứu C4–C7 (đã nằm trong nhóm thăm dò) nếu muốn logic thực sự khác. Dữ liệu và tái lập đã đủ chặt để bắt đầu nghiên cứu đó **sau khi anh duyệt**.
