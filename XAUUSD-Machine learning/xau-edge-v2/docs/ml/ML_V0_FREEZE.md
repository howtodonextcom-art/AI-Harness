# ML V0: đóng băng đặc tả (trước G6)

Ngày: 2026-10-12 · Trạng thái: **FROZEN** · Duyệt: chủ dự án ("ML V0: freeze volatility/range task trước G6").

Đặc tả máy đọc được: [`ml_v0_spec.json`](ml_v0_spec.json) (spec_id `ml-v0-rng24`, phiên bản `1.0.0`). Chữ ký băm: `ml_v0_spec.sha256`; một test thất bại nếu đặc tả bị sửa tại chỗ.

## Điều đã đóng băng

- **Vai trò A:** ML chỉ cung cấp thông tin biên độ/rủi ro. **Không thẩm quyền**: không được tạo, hủy hay sửa quyết định MUA/BÁN/CHỜ. Không dự đoán hướng.
- **Nhãn:** `y[t] = ln((max High[t+1..t+24] − min Low[t+1..t+24]) / Close[t])`, khung H1, nhãn `rng24.v1`; embargo 25 nến.
- **13 đặc trưng** (mỗi đặc trưng có đủ trường hợp đồng: tên, phiên bản, đơn vị, khung nguồn, lookback, `available_at`, quy tắc thiếu, chuẩn hóa, khả dụng live, lý do). ATR dùng **SMA của true range** (khác ATR Wilder của V1, có chủ ý và ghi rõ).
- **Mô hình:** mặc định ridge/HAR (α = 10, chuẩn hóa); thách đấu LightGBM (tham số cố định). LightGBM chỉ được thăng nếu CI 95% của (MSE ridge − MSE LightGBM) > 0 trên **cả** Validation và Test-H.
- **Baseline bắt buộc:** trung bình mở rộng; ATR14 một đặc trưng; bảng theo phân vị ATR.
- **Chia dữ liệu:** theo thời gian, mở rộng, bước theo năm; Validation 2019–2021; **Test-H 2022-01-01..2025-04-30 và Holdout 2026-05-01..2026-10-07 KHÓA, mỗi cái đúng một lần chạy**; không tinh chỉnh trên Validation/Test-H.
- **Tiêu chí thăng `RESEARCH → VALIDATED_OFFLINE`:** cải thiện MSE ≥ 5% so với ATR14 với cận dưới CI > 0 trên Validation và Test-H; độ phủ dải 80% trong 75–85%; dương ≥ 75% số năm; parity replay/live.
- **Hiển thị:** biên độ kỳ vọng 24 giờ (USD) + dải 80%, chỉ khi mô hình ≥ SHADOW và khỏe; **không bao giờ** hiển thị "AI confidence", xác suất thắng hay hướng.
- **K:** V0 **không tiêu K** (đánh giá dự báo, không tuyên bố giao dịch). Chính sách K vẫn mở (ADR-V2-007).

## Điều KHÔNG được làm cho đến khi sửa đặc tả bằng phiên bản mới

Sửa nhãn, đặc trưng, ngưỡng; chạy Test-H hoặc Holdout; chọn mô hình theo lợi nhuận giao dịch; học trực tuyến; xáo trộn ngẫu nhiên train/test.

## Căn cứ chọn (tóm tắt)

Lát cắt G0 (dữ liệu ≤ 2021, Class D): ridge/HAR cải thiện MSE ≈ 10% so với ATR14 một đặc trưng ở cả Dev 2015–2018 và Val 2019–2021 (CI loại trừ 0); LightGBM ≈ ridge. Chi tiết và giới hạn: `reports/V2_ML_RESEARCH_PROTOCOL.md`. **Đó là kết quả mô tả, không phải bằng chứng**; lần chạy chính thức ở G6 sẽ thực hiện đúng đặc tả này.

## Sửa đổi

Không sửa tại chỗ. Sửa = phiên bản mới (`spec_version`), lý do được chủ dự án duyệt, đổi băm trong cùng commit.

## Sửa đổi 2026-10-13: spec 1.1.0 (chỉ `k_accounting`)

Chủ dự án duyệt ADR-V2-007 (K khóa theo họ): `K_V2_VOL_V0 = 2`, ứng viên `har_ridge` + `lightgbm_regressor`, CI hiệu chỉnh 97,5% ở Test-H. Đặc tả 1.0.0 và băm được giữ (`ml_v0_spec_v1.0.0.json/.sha256`); mọi khóa khác giữ nguyên (có test). Dòng "K: V0 không tiêu K" ở trên áp dụng cho bản 1.0.0; từ 1.1.0, **Test-H là bước confirmatory tiêu K = 2**, Kiểm định không tiêu K.
