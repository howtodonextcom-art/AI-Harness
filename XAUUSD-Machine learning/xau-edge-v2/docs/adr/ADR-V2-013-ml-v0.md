# ADR-V2-013: ML V0 (dự báo biên độ), khóa cửa sổ, sổ cái K và registry

Trạng thái: **ĐÃ DUYỆT** (G6, 2026-10-13) · Liên quan: ADR-V2-007 (K khóa theo họ), `docs/ml/ML_V0_FREEZE.md`.

## Quyết định

1. **Vai trò A, không thẩm quyền.** ML V0 chỉ là thông tin biên độ; không có đường nào để nó tạo/hủy/sửa BUY/SELL/WAIT, và **dự báo không hiển thị ở đâu** khi mô hình dưới SHADOW. `authority` luôn `NONE` trong registry; không bước thăng cấp nào đổi điều đó.
2. **Đặc tả đóng băng, sửa bằng phiên bản.** `ml_v0_spec.json` 1.1.0 chỉ khác 1.0.0 ở `k_accounting` (họ `K_V2_VOL_V0`, K = 2, ứng viên `har_ridge` + `lightgbm_regressor`; Ridge/HAR là một ứng viên; baseline không tiêu K). Bản 1.0.0 và băm được giữ nguyên; test chứng minh mọi khóa khác giống hệt.
3. **Mã chặn dữ liệu bị khóa.** Mã phát triển/kiểm định chỉ thấy nến có nhãn hoàn tất trước 2022-01-01. Test-H và Holdout mở **đúng một lần mỗi cái**, cần tệp duyệt của chủ dự án (`docs/ml/approvals/<window>_approval.json`) khớp băm đặc tả và họ K, và sổ cái K không có lần nhìn trước; lần nhìn được ghi **trước** khi đọc dữ liệu. Sổ cái chỉ thêm (không sửa/xóa).
4. **K theo họ.** Kiểm định 2019–2021 là Class D (đã đốt) và không tiêu K; Test-H là bước confirmatory duy nhất tiêu K = 2 với CI hiệu chỉnh Bonferroni mức 97,5% (alpha 0,05 / K). Thêm ứng viên, biến thể siêu tham số chọn theo kết quả, tác vụ hoặc khung mới ⇒ cần ADR + họ mới trước khi thấy kết quả confirmatory.
5. **Registry thăng từng bước có bằng chứng:** VALIDATED_OFFLINE cần một lần chạy Test-H có trong sổ cái và mọi tiêu chí đăng ký trước đạt; các bước sau cần bản ghi duyệt của chủ dự án. Không kích hoạt bằng cách thay tệp.
6. **Kết quả lần chạy chính thức (Phát triển + Kiểm định):** ridge/HAR cải thiện MSE 9,6% so với ATR14 ở Kiểm định (CI 95% và 97,5% > 0, độ phủ dải 76,9%) nhưng **tiêu chí "dương ≥ 75% số năm" không đạt (2/3)**; LightGBM không hơn ridge. Mô hình ở **RESEARCH**. Không đổi tiêu chí trong ADR này; mọi sửa tiêu chí là một `spec_version` mới có lý do được duyệt và được ghi nhận là sửa sau khi đã thấy kết quả.

## Hệ quả

- `GET /api/v2/model` (chỉ đọc) trả trạng thái, khóa, tiêu chí đạt/không đạt; hợp đồng `2.0.0-g6`.
- Chưa có dịch vụ suy luận, giám sát vận hành và fail-closed (điều kiện của SHADOW, ngoài G6).

## Quyết định sau Kiểm định (2026-10-13)

ML V0 bị **loại tại Kiểm định** theo tiêu chí đăng ký trước (không đổi tiêu chí, không mở Test-H). Họ K đóng, registry RETIRED. Tạm dừng ứng viên ML này; hướng tiếp theo là G8 (độ tin cậy và forward evidence). Mọi ML mới = ADR + họ K mới + đặc tả mới trước khi thấy kết quả confirmatory.
