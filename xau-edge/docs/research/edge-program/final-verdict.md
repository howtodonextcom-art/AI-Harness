# Edge Program: kết luận cuối (T1.6)

Ngày: 2026-10-08. Trạng thái: **(B) NO EDGE WITHIN BUDGET**.

> Không có edge được kiểm định; bot funded chỉ chạy ở chế độ UNVALIDATED theo override D2, rủi ro
> trần 0,25%/lệnh, tối đa bậc 2.

## Phạm vi đã chạy

* Dữ liệu: lịch sử MT5 FTMO DEMO đọc chỉ-đọc (H1 `8e64dd6561015b72`, H4 `b438f1794bd11402`), split
  mới Dev-H 2011–2018, Val-H 2019–2021 (phụ lục `docs/evals/edge-criteria.md`, commit `a840fe7`, trước
  mọi kết quả). 7 tiêu chí giữ nguyên.
* 6 giả thuyết đăng ký trước (`hypotheses/H01..H06.md`, commit `a840fe7`), 18 biến thể, K = 21,
  alpha = 0.05/21. Lựa chọn triển khai ghi vào ledger trước lần chạy đầu (commit `d28a3d0`).
* 36 lần chạy (18 × Dev-H, 18 × Val-H), mỗi lần gồm kịch bản cơ sở và bi quan (slippage × 2). Bảng
  đầy đủ: `ledger.md`; file kết quả: `experiments/edge_program/*.json`.
* **Test-H không chạy** (không biến thể nào PASS cả Dev-H và Val-H). **Holdout 2026-05..2026-10 không
  bị chạm.** Không có vi phạm quy tắc chống overfitting.

## Kết quả

| Giả thuyết | Biến thể tốt nhất theo mean net R bi quan (min Dev-H, Val-H) | Nhận xét |
|---|---|---|
| H01 động lượng giờ mở phiên | theta0.3: -0.093 | âm ở mọi biến thể, mọi giai đoạn |
| H02 phá vỡ biên độ Asia | b0.0: -0.074 | âm ở mọi biến thể |
| H03 nén rồi mở rộng | c1.0: -0.066 (≥ 100 lệnh) | c0.9 dương ở Val-H (+0.012) nhưng chỉ 83 lệnh và âm ở Dev-H |
| H04 xu hướng ngày + hồi EMA | L40: -0.144 | âm rõ nhất |
| H05 fade bar xung lực | s1.5: -0.142 | s2.5 chỉ 22 / 6 lệnh |
| H06 Donchian H4 | N40: -0.428 | ít lệnh, âm mạnh ở Val-H |

Chỉ 3/36 lần chạy có mean net R cơ sở > 0 (H03-c0.9 Val-H +0.021 với 83 lệnh, H03-c1.0 Dev-H +0.0001,
H05-s2.5 Val-H +0.667 với 6 lệnh); cả ba đều âm hoặc không đủ lệnh ở giai đoạn còn lại. Profit factor
cơ sở cao nhất là 1,023 (H03-c0.9 Val-H), dưới ngưỡng 1,2 của tiêu chí 3; mọi lần chạy khác có PF < 1
(trừ H05-s2.5 Val-H không có lệnh lỗ nào trong 6 lệnh, vẫn FAIL tiêu chí 1 về số lệnh).

## Chiến lược cho override D2 (quy tắc 6 của ledger, ghi trước kết quả)

* 11 biến thể có ≥ 100 lệnh ở cả Dev-H và Val-H. Điểm = min(mean net R bi quan Dev-H, Val-H).
* Cao nhất: **H03-c1.0**, điểm **-0.0663 R/lệnh** (Dev-H -0.0143, Val-H -0.0663).
* Điểm ≤ 0, nên theo quy tắc: **không có biến thể nào dương cả hai giai đoạn sau chi phí bi quan**.
  H03-c1.0 được nêu tên như giá trị tham khảo, không phải phát hiện. Kỳ vọng của nó sau chi phí bi quan
  là **âm**: chạy nó trên funded là chấp nhận một chiến lược có kỳ vọng âm theo dữ liệu lịch sử, đổi
  lấy kinh nghiệm vận hành, với rủi ro bị giới hạn.
* T1.5 prop filter (Monte Carlo bootstrap khối theo ngày Prague, lệnh bi quan Dev-H + Val-H, 312 ngày
  có lệnh, 10.000 đường, seed 7):

| Rủi ro/lệnh | P(vi phạm) 30 ngày | 60 ngày | 90 ngày |
|---:|---:|---:|---:|
| 0,10% | 0,0000 | 0,0000 | 0,0000 |
| 0,25% | 0,0000 | 0,0002 | 0,0028 |
| 0,35% | 0,0000 | 0,0085 | 0,0420 |
| 0,50% | 0,0065 | 0,0786 | 0,1721 |
| 1,00% | 0,1927 | 0,3974 | 0,5132 |

  Mức lớn nhất giữ P(vi phạm 90 ngày) ≤ 5%: 0,35%/lệnh. **Rủi ro override = min(0,35; 0,25) =
  0,25%/lệnh.** Monte Carlo không mô phỏng lỗ thả nổi trong lệnh vượt quá R đã chốt.

## Việc còn lại trước khi override D2 dùng được trên funded

1. H03-c1.0 hiện **chưa có bản live** trong strategy registry (`signals/strategy_registry.py` chỉ có
   Baseline C). Cần: thêm `StrategySpec` cho H03-c1.0 sinh tín hiệu từ bar H1 đã đóng (đúng quy tắc
   H03), ADR ủy quyền chạy UNVALIDATED, và parity test giữa `strategies/edge_program.py` và signal
   engine trên cùng bar. Khi chưa có, bot chạy tín hiệu `baseline_c`, nên
   `XAU_EDGE_FUNDED_STRATEGY_ID=H03-c1.0` không khớp `strategy_id` của tín hiệu, override không mở và
   evidence gate tiếp tục chặn (fail-closed, không lệnh nào được gửi).
2. Chủ dự án ký chấp nhận override D2 trong `docs/operations/go-live-checklist.md`, biết rằng chiến lược
   có kỳ vọng âm trong lịch sử.

## Giới hạn

* Một broker, một symbol; thực thi H1, không có M5 trước 2025-05; spread lịch sử không đáng tin nên
  dùng sàn 30 points; commission 0 chưa xác minh; không có lịch tin trong nghiên cứu.
* Kết luận (B) chỉ nói: trong ngân sách N = 6 giả thuyết đã đăng ký, không tìm thấy edge vượt chi phí.
  Không nói vàng không có edge nào.
