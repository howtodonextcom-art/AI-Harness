# CAND_V2_CORE_1.1.0: hợp đồng tín hiệu (đã đóng băng)

Nguồn chính thức: `docs/research/cand_v2_spec.json` (FROZEN 2026-10-13, hash `cand_v2_spec.sha256`; 1.0.0 lưu ở `cand_v2_spec_1.0.0.json`). Tài liệu này chỉ tóm tắt hợp đồng để đối chiếu; nếu khác với JSON thì JSON thắng. **Độc lập với `multifamily_0.1.0.spec.json`** (hai nhánh không bao giờ gộp thành một chiến lược).

| Mục hợp đồng | Quy định |
|---|---|
| Bản chất | lớp mỏng quanh `decide()` của CONTROL V1 v1.1.0: nhãn chuỗi, stop, target, net R:R và sizing là mã của CONTROL, không đổi. Mọi cờ tắt ⇒ giống CONTROL (parity test) |
| Thay đổi (CORE) | **C1** vòng đời có nhớ: setup được giữ 6 nến M5, `planned_stop` cố định tại lúc hình thành, trigger có thể đến sau; **C2** cổng chi phí/rủi ro `cost_R ≤ 0,15` thay cổng spread theo percentile; **C3a** bỏ cổng percentile biến động THẤP; **C3b** thay cổng biến động CAO và H4 HIGH_VOL bằng bảo vệ SHOCK |
| Exploratory | C7 (đối kháng từ khung lớn) chỉ nghiên cứu dev, không vào ứng viên; C4–C6 chưa cài |
| Biến thể | danh sách **đóng** 14 biến thể (CTRL, A_C1, A_C2, A_C3a, A_C3b, B_C1C2, B_C2C3a, CORE, LOO_no*, X_C7, X_CORE_C7); không thêm sau khi thấy dữ liệu |
| Entry quote | BUY ở ask (bid + spread của nến M1 đóng), SELL ở bid; giá trong biểu đồ BID của broker |
| Stop | hybrid của CONTROL: `max(cấu trúc + 0,1 ATR, 1,25 ATR)`, từ chối nếu > 3 ATR; với C1 dùng `planned_stop` cố định lúc hình thành |
| Target | 2R, giới hạn bởi cản đối diện; TP2 3R khi không bị giới hạn |
| Net R:R | `(reward − spread) / (risk + spread) ≥ 1,5` (cổng lập kế hoạch, KHÔNG phải khoản trừ) |
| Cost | C2 `cost_R = (spread + 2×slippage 3 điểm) / risk`, quote thực thi; là bộ lọc, không trừ vào kết quả (spread và trượt giá chỉ tính một lần ở PnL thực) |
| Expiry | tín hiệu hết hạn sau 3 nến M5 kể từ nến trigger (CONTROL `expiry_bars_m5 = 3`) |
| Overlapping position | một lệnh PAPER mỗi lúc (governor: 1 vị thế mở); một episode ⇒ một lệnh tại nến tín hiệu đầu tiên, episode = chuỗi tín hiệu cùng phía cách nhau ≤ 60 phút |
| Ablation | các biến thể ở trên: A (một thay đổi), B (hai), CORE (bốn), LOO (bỏ một khỏi CORE); báo từng bước cái gì mất, không chọn theo kết quả |
| Cửa sổ | DEV' 2005-11..2018-12 (tín hiệu, KHÔNG outcome); VALIDATION' một lần sau khi chủ dự án duyệt; Confirm-C một lần; Test-H và Holdout KHÓA |
| Kiểm chứng | K_V2_CAND_DET = 1 (hai cửa sổ, cần cả hai); K_V2_CAND_ML = 2 (quyền NONE) |
| Quyền hạn | PAPER; con người là quyền quyết định cuối; ứng viên không hoạt động trong live |

Stage A (đợt này) chỉ chạy `cand_replay.py` (một tiến trình liên tục, restore bằng từng bit, không outcome) và báo cáo `reports/V2_STAGE_A_SIGNAL_ONLY_REPORT.md`.
