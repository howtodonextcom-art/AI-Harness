# ADR-V2-007: sổ cái K theo họ (ĐÃ KHÓA theo quyết định của chủ dự án)

Trạng thái: **KHÓA (LOCKED), 2026-10-13.** Thay thế bản "MỞ" ngày 2026-10-12.

## Quyết định của chủ dự án

1. **K = 44 của V1 KHÔNG được kế thừa** (giữ nguyên quyết định 2026-10-12). K được tính **theo họ đa kiểm định (family)**, không dùng một con số chung.
2. **Họ `K_V2_VOL_V0`** (dự báo biên độ `rng24.v1`, task vai trò A của ML V0): **K = 2**, với điều kiện chỉ **Ridge/HAR** và **LightGBM** cùng tham gia *selection* trên *confirmatory evaluation*. Baseline (naive, EWMA, HAR đơn giản) là mốc so sánh, **không** tiêu K.
3. **Khóa:** mọi thay đổi làm tăng số ứng viên tham gia selection (thêm mô hình, thêm biến thể siêu tham số được chọn theo kết quả confirmatory, thêm task, thêm khung dữ liệu) **không được tự động dùng K = 2**: phải mở họ mới hoặc nâng K qua một ADR mới, trước khi nhìn kết quả confirmatory.
4. **Test-H và Holdout vẫn khóa** cho tới khi đủ điều kiện ở mục 5; mỗi cửa sổ dùng **đúng một lần** cho họ của nó.
5. **Điều kiện trước khi dùng K = 2:** (a) đặc tả ML V0 đã đóng băng và băm bảo vệ (đã có, `docs/ml/ml_v0_spec.json`); (b) danh sách ứng viên selection được ghi trong đặc tả trước khi chạy confirmatory; (c) ghi nhận mọi lần nhìn vào cửa sổ confirmatory vào sổ cái.
6. **ML chưa có thẩm quyền**; không có đường nào để một dự báo ML đổi hành động BUY/SELL/WAIT trong V0.

## Phạm vi và những gì chưa quyết

- K ở đây chỉ nói về **họ biên độ V0**. Họ giả thuyết giao dịch (kể cả H-V2-01, đang RESEARCH_ONLY) **chưa có K**; V2 vẫn **không đăng ký giả thuyết giao dịch nào**.
- Các phép đo Class D đã làm trên lịch sử đầy đủ (V1 và các phép thử kiểm chứng ảnh) vẫn là mô tả, không phải bằng chứng; chúng không giảm K nhưng làm cửa sổ liên quan **không còn sạch** cho họ giao dịch.
- Việc quan sát tín hiệu live **tự nhiên** (forward evidence) là một yêu cầu riêng, không thuộc sổ cái K.

## Hệ quả

- G6 (ML V0) được phép bắt đầu khi chủ dự án duyệt; K của nó là 2 (có điều kiện mục 2).
- Sổ cái triển khai `M-14`: **RESOLVED** (chính sách), còn triển khai cơ chế ghi sổ ở G6.

## Làm rõ 2026-10-13 (chủ dự án): một phía hay hai phía

- Với họ α = 0,05 (Bonferroni) và K = 2, mức mỗi phép so sánh là α/K = **0,025**.
- Phát biểu cần chứng minh là **"cải thiện > 0"** (một chiều). Diễn đạt thống kê sạch nhất là **cận dưới MỘT PHÍA 97,5%** (= bách phân vị thứ 2,5 của bootstrap), **không** phải khoảng hai phía 97,5% (bách phân vị 1,25 và 98,75; chặt hơn mức cần).
- Bản đặc tả 1.1.0 ghi "two-sided 97.5%" (chặt hơn cần thiết): được **thay thế cho các họ sau**; không kết quả nào phụ thuộc vào câu chữ đó (cận dưới một phía 97,5% trên Kiểm định là 0,0082 > 0 và V0 bị loại vì một tiêu chí khác). Ghi nhận bằng sự kiện `POLICY_CLARIFICATION` trong sổ cái K.
- Mã: `metrics.block_ci` trả `lower97.5_one_sided`; tiêu chí và ngăn Mô hình dùng đúng khóa này.

## Kết cục họ `K_V2_VOL_V0` (2026-10-13)

Chủ dự án **không mở Test-H**, **giữ nguyên tiêu chí đăng ký trước** và **loại V0 tại Kiểm định** (tiêu chí "dương ≥ 75% số năm" đạt 2/3). Họ được **ĐÓNG** (`FAMILY_CLOSED`, 0 lần nhìn confirmatory): K **không bị tiêu**; không cửa sổ confirmatory nào có thể mở cho họ này. Hai bản ghi registry (`har_ridge`, `lightgbm_regressor`) ở **RETIRED**, authority NONE. Một mô hình/ứng viên mới cần ADR và họ K mới.
