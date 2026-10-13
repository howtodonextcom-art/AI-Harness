# reference-v1: bản sao THAM CHIẾU (chỉ đọc) từ repo cũ

- Nguồn: `Z:\Coding\Projects\AI-Harness\xau-edge`, HEAD `daf22f6`, ngày sao chép 2026-10-12.
- Bản sao phản ánh **working tree** lúc đó, gồm 3 file có thay đổi chưa commit của repo cũ
  (`apps/dashboard/lib/action.ts`, `apps/dashboard/e2e/bias_vs_action.spec.ts`,
  `tests/unit/trading/test_decision_levels_sizing.py`).
- Repo cũ **không bị sửa**. Thư mục này chỉ là nguyên liệu để đọc/lấy ý tưởng; **không import từ đây**
  vào app mới và không chỉnh sửa tại chỗ. Mọi mã dùng lại phải được chép sang app mới, đọc lại, và có test.
- Chỉ chép các phần có giá trị (xem `reports/GIA_TRI_MA_CU_VA_THIET_KE_MOT_TRANG_2026-10-12.md`);
  KHÔNG chép: các trang research/control/legacy/market, engine `signals/` cũ, `control/`, `funded/`,
  `brokers/`, `execution/`, `video_intel/`, `forensics/`, dữ liệu (`data/`), `node_modules`, `.next`.
- Quy mô: 325 file, ~2,1 MB.
