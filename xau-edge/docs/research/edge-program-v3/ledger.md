# Sổ thí nghiệm Edge Program V3 (chỉ thêm vào cuối, không sửa, không xóa)

Ngày mở: 2026-10-11. K của V3 nằm **trong trần của sổ V2** (`docs/research/edge-program-v2/ledger.md`, trần 24, đã dùng 20) theo ADR-0030. `STATE.json` không ghi đè sổ này.

* Biến thể đã khai báo (đăng ký trước, CHƯA CHẠY): F1 1 + F3 1 + F2 1 = **K_V3 = 3**. Còn lại trong trần V2: 24 − 20 − 3 = **1** (không được dùng nếu chủ dự án chưa ký bằng văn bản).
* Không tự mở rộng K. Không thêm biến thể sau một lần fail. Một họ fail Stage 1 hoặc Val thì **đóng hẳn**.
* Stage 1 (Development-2, 2011-01-01..2018-12-31): Bonferroni một phía α = 0.10 / 3 = 0.0333 cho từng họ (chặn trên của bước đầu Holm, vì các họ chạy tuần tự).
* Validation-2 (2019-01-01..2021-12-31): α = 0.05 / 3 = 0.0167.
* Test-H (2022-01-01..2025-04-30) và Holdout (2026-05-01..2026-10-07): **không bị chạm**. Khi tới lượt: α = 0.05 / K_tổng, K_tổng = 21 (Programme 1) + 20 (V2) + 3 (V3) = **44**; một lần mỗi ứng viên, chỉ sau review độc lập.
* Thứ tự chạy: **F1 → F3 → F2**. F2 bị hoãn (xem `F2_us_macro_reaction.md`): khe K của F2 vẫn được tính vào K_tổng (bảo thủ) dù chưa chạy.
* Mô hình chi phí: `foundation/cost_model_v2.json` (đo 2026-10-11). Dữ liệu chéo: `foundation/cross_asset_manifest.json` (SHA-256 từng file).

## Bảng đăng ký

| # | Ngày | Họ / biến thể | Trạng thái | File đăng ký |
|---|---|---|---|---|
| 1 | 2026-10-11 | F1-USDRES-z2.0 | ĐĂNG KÝ, CHƯA CHẠY | `F1_gold_usd_residual.md` |
| 2 | 2026-10-11 | F3-USMOM-0930-1400-1500-1645 | ĐĂNG KÝ, CHƯA CHẠY | `F3_us_session_momentum.md` |
| 3 | 2026-10-11 | F2-MACRO-SETB-15-120 | ĐĂNG KÝ, HOÃN (ECONOMICALLY IMPRACTICAL theo quy tắc tần suất; chặn dữ liệu lịch tin) | `F2_us_macro_reaction.md` |

## Bảng chạy

| # | Thời gian | Biến thể | Giai đoạn | Kết quả | Registry id |
|---|---|---|---|---|---|
| 1 | 2026-10-11T06:26Z | F1-USDRES-z2.0 | Stage 1 (Development-2) | **FAIL** — n=1601 (200/năm), mean base −0.283R (CI95 −0.346..−0.220), mean pess −0.354R, gross −0.144R, p=1.0, 0/8 năm dương, placebo percentile 0. **Họ F1 ĐÓNG.** Không F1b, không đảo chiều. | `results/F1_stage1.json` sha256 563D79B83A556A81…, code `d949b20`, prereg `4a03273` |
| — | 2026-10-11 | F3-USMOM-0930-1400-1500-1645 | Sửa đổi 1 (v1.1) trước khi chạy: mặt nạ đồng hồ cho năm chưa chứng nhận + cố định cách đọc. Không thêm biến thể, K_V3 = 3. | chưa chạy | `F3_amendment_1.md` |
| 2 | 2026-10-11 | F3-USMOM-0930-1400-1500-1645 | Stage 1 (Development-2) | **FAIL** — n=1735 (217/năm; loại: mặt nạ đồng hồ 135, lễ/đóng sớm 86, thiếu nến mốc 126, độ phủ thấp 3, s=0 1), gross −0.010R, mean base −0.214R (CI95 −0.240..−0.188), mean pess −0.327R, p=1.0, 0/8 năm dương, placebo percentile 16.3. Chi phí (spread + trượt giá ≈ −0.20R) lớn hơn mọi tín hiệu; hướng buổi sáng không mang thông tin. **Họ F3 ĐÓNG.** | `results/F3_stage1.json` sha256 1FE606351FA80DF6…, code `0651972`, prereg `4a03273` + sửa đổi `6ca3342` |
