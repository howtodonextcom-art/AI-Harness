# Edge Program Ledger (T1.4)

Sổ cái này do Track 1 sở hữu: K, mọi lần chạy (kể cả hỏng/bỏ dở), và các quy tắc cố định TRƯỚC
khi có kết quả. Commit đầu tiên của file này nằm TRƯỚC mọi file kết quả. Không sửa các mục
"Quy tắc cố định"; chỉ được THÊM dòng vào bảng chạy ở cuối.

## K và trần

* Biến thể đã khai báo: 6 giả thuyết x 3 giá trị = **18** (xem `hypotheses/`).
* Baseline đã đăng ký trước đó (registry `backtest`): **3**.
* **K = 3 + 18 = 21; trần K cap = 21.** alpha = 0.05 / 21 = 0.002381, dùng cho MỌI đánh giá của
  chương trình (toàn bộ lưới được đếm ngay từ đầu).
* Quy tắc dừng: dừng khi cả 6 giả thuyết đã dùng hết HOẶC K chạm trần 21, cái nào đến trước. Chạy
  lại hoặc thêm bất kỳ biến thể nào ngoài lưới là vượt trần, tức là dừng chương trình. Mỗi lần chạy,
  kể cả lỗi code/bỏ dở, được ghi vào bảng chạy bên dưới; lần chạy lỗi code phải sửa code mà KHÔNG đổi
  quy tắc giả thuyết, và chạy lại không tính biến thể mới (cùng tham số) nhưng được ghi.

## Quy tắc cố định (viết trước kết quả)

1. Mọi 18 biến thể chạy trên Dev-H rồi Val-H (đều là finalist; không chọn lọc trên Dev).
2. Biến thể "PASS giai đoạn" = 7 tiêu chí đạt với `variants = 21`, 20,000 resample, seed 7, VÀ
   mean net R > 0 trong kịch bản bi quan (slippage 6 pts).
3. Test-H: chạy đúng MỘT lần cho mỗi biến thể PASS cả Dev-H và Val-H. Không chạy lại.
4. Holdout (Test cũ 2026-05..2026-10) không được chạm trong chương trình này.
5. Mỗi biến thể PASS Test-H sinh `review-request.md` và chương trình dừng ở biến thể đó chờ review
   độc lập; kết luận (A) chỉ sau review.
6. **Quy tắc chọn "tốt nhất" cho trường hợp (B)** (cố định trước): trong các biến thể có >= 100 lệnh
   ở CẢ Dev-H và Val-H, điểm = min(mean net R bi quan ở Dev-H, mean net R bi quan ở Val-H) (maximin,
   đo bằng R/lệnh sau chi phí bi quan). Biến thể có điểm cao nhất là "tốt nhất sau chi phí bi quan".
   Nếu điểm cao nhất <= 0 thì báo cáo rõ "không có biến thể nào dương cả hai giai đoạn sau chi phí
   bi quan" và vẫn nêu tên biến thể có điểm cao nhất như giá trị tham khảo, không như phát hiện.
7. Kết quả được báo cáo theo hướng đã đăng ký; hướng ngược lại không được chọn sau khi xem kết quả.

## Nhật ký toàn vẹn

* 2026-10-08 21:11-21:14 (UTC+7): đọc lịch sử MT5 DEMO chỉ-đọc (`scripts/fetch_history.py`) vào
  `data/research_history`. Trước khi viết split chỉ xem: số hàng, ngày đầu/cuối, số lỗi validator và
  trung vị spread theo năm (để đặt sàn chi phí 30 pts). KHÔNG xem lợi nhuận, R hay hướng giá.
* 2026-10-08 21:18-21:20: viết phụ lục split (`edge-criteria.md`), 6 giả thuyết và ledger này.
  Không có file nào trong `data/backtests` được tạo sau 20:30; registry không có lần chạy nào trên
  dữ liệu mới. 7 tiêu chí gốc không bị sửa (diff chỉ THÊM phụ lục).
* Lượt trước dừng giữa chừng (hết quota) khi các file trên mới được stage; lượt tiếp theo kiểm tra
  lại các điểm trên và commit chúng thành một commit riêng TRƯỚC mọi code thực nghiệm và kết quả.

## Lựa chọn triển khai (ghi TRƯỚC lần chạy đầu tiên, commit `eaffe46` là code)

Code: `src/xau_edge/strategies/edge_program.py`, `src/xau_edge/evaluation/edge_program.py`,
`scripts/run_edge_program.py`. Chỗ giả thuyết chưa nói rõ được đọc theo nghĩa đen, quyết định ở đây
trước khi có kết quả, không đổi sau:

1. Cooldown đếm bar (timeframe tín hiệu) từ tín hiệu phát ra trước đó, kể cả khi engine bỏ qua tín
   hiệu đó vì đang có vị thế (giống `signals_from_direction` của baseline).
2. H01: ATR14 tại chính bar mở phiên; bar mở phiên chỉ khi giờ mở địa phương đúng 09:00 Tokyo /
   08:00 London / 08:00 New York.
3. H02: ngày UTC; đủ 7 bar Asia; ATR tại bar phá vỡ; không cooldown, tối đa 1 tín hiệu/ngày.
4. H03: cần đủ 120 giá trị ATR trước đó; kênh 24 bar trước tính theo hàng (vượt qua gap); ATR trung
   bình = 0 thì không có tín hiệu.
5. H04: `available_at` = giờ mở bar H1 cuối + 1h, áp dụng nguyên văn cả ở ngày đóng cửa sớm (hơi lạc
   quan ở những ngày đó, ghi nhận); L đếm bar daily được giữ (>= 12 bar H1); `t-1` là hàng H1 trước;
   SHORT: `close[t-1] >= ema[t-1]` và `close[t] < ema[t]`; EMA20 khởi tạo từ đầu lịch sử nạp.
6. H05: ngưỡng dùng ATR tại t-1; stop/target dùng ATR tại t.
7. H06: dùng dataset H4 của broker (không resample từ H1); regime cho chặn SHOCK và tiêu chí 7 là
   regime của bar H4; vào lệnh ở bar H1 đầu tiên mở tại/sau lúc đóng bar H4.
8. Regime null trong warm-up bị bỏ qua (`REGIME_UNKNOWN`, mặc định risk engine); trần spread 120 pts
   của engine giữ nguyên (bar vượt bị bỏ qua `SPREAD`); tín hiệu mà bar H1 kế tiếp cách > 30 phút bị
   bỏ qua `ENTRY_GAP` và được đếm. Dữ liệu không được sửa/điền; lỗi validator ghi trong mỗi kết quả.
9. Biên giai đoạn: end-exclusive; lệnh còn mở ở cuối giai đoạn đóng ở bar cuối (`DATA_END`).
10. 7 tiêu chí chấm trên kịch bản cơ sở; kịch bản bi quan chỉ dùng điều kiện mean net R > 0.
11. Test-H: ghi marker "started" trước khi chạy, nên kể cả lỗi code cũng tiêu hết lượt duy nhất (chặt
    hơn quy tắc ledger, được chấp nhận). Dev/Val chạy lại sau lỗi code được phép và được ghi; bản ghi
    hoàn tất gần nhất quyết định.
12. K = 21 là hằng số trong code (không đọc từ registry).
13. Monte Carlo T1.5: mặc định chỉ resample các ngày có lệnh (bảo thủ); rủi ro theo % vốn ban đầu,
    không lãi kép; ngưỡng vi phạm bao gồm dấu bằng; không mô phỏng lỗ thả nổi trong lệnh vượt R đã
    chốt; mức rủi ro chọn theo chân trời 90 ngày.
14. Bootstrap của tiêu chí 2 dùng khối theo ngày UTC vào lệnh (như `evaluate_edge` hiện có); chỉ Monte
    Carlo dùng ngày Prague.

## Bảng chạy

| # | Thời gian | Giả thuyết/biến thể | Giai đoạn | Kịch bản | Ghi chú | Registry id |
|---|---|---|---|---|---|---|
| 1 | 2026-10-08 14:50:34 UTC | H01-theta0.3 | dev-H | base + bi quan | 2727 lệnh, mean net R -0.0812 / bi quan -0.0933; FAIL | `1eb8c293cfe9074f` |
| 2 | 2026-10-08 14:50:38 UTC | H01-theta0.6 | dev-H | base + bi quan | 1461 lệnh, mean net R -0.0854 / bi quan -0.0974; FAIL | `a4d067e77ca95fb4` |
| 3 | 2026-10-08 14:50:41 UTC | H01-theta0.9 | dev-H | base + bi quan | 729 lệnh, mean net R -0.0995 / bi quan -0.1154; FAIL | `4cfc35a9ad84f5d1` |
| 4 | 2026-10-08 14:50:46 UTC | H02-b0.0 | dev-H | base + bi quan | 1714 lệnh, mean net R -0.0595 / bi quan -0.0736; FAIL | `0c53b7e69ff4fce1` |
| 5 | 2026-10-08 14:50:51 UTC | H02-b0.25 | dev-H | base + bi quan | 1549 lệnh, mean net R -0.0766 / bi quan -0.0909; FAIL | `39e953fbcb9e8d76` |
| 6 | 2026-10-08 14:50:55 UTC | H02-b0.5 | dev-H | base + bi quan | 1320 lệnh, mean net R -0.0844 / bi quan -0.0968; FAIL | `b3f2005b1a136b2e` |
| 7 | 2026-10-08 14:50:56 UTC | H03-c0.8 | dev-H | base + bi quan | 83 lệnh, mean net R -0.0132 / bi quan -0.0179; FAIL | `5afa890118e851be` |
| 8 | 2026-10-08 14:50:57 UTC | H03-c0.9 | dev-H | base + bi quan | 152 lệnh, mean net R -0.0700 / bi quan -0.0888; FAIL | `b2e8f4a24fd5008a` |
| 9 | 2026-10-08 14:50:58 UTC | H03-c1.0 | dev-H | base + bi quan | 211 lệnh, mean net R +0.0001 / bi quan -0.0143; FAIL | `24553565875442ae` |
| 10 | 2026-10-08 14:51:03 UTC | H04-L10 | dev-H | base + bi quan | 1851 lệnh, mean net R -0.1545 / bi quan -0.1607; FAIL | `989b03af33b1b63f` |
| 11 | 2026-10-08 14:51:08 UTC | H04-L20 | dev-H | base + bi quan | 1861 lệnh, mean net R -0.1884 / bi quan -0.1953; FAIL | `e296e799945758cc` |
| 12 | 2026-10-08 14:51:13 UTC | H04-L40 | dev-H | base + bi quan | 1810 lệnh, mean net R -0.1358 / bi quan -0.1440; FAIL | `313f13c64d579a85` |
| 13 | 2026-10-08 14:51:15 UTC | H05-s1.5 | dev-H | base + bi quan | 815 lệnh, mean net R -0.1331 / bi quan -0.1422; FAIL | `ef64a0f3ea2b6dbb` |
| 14 | 2026-10-08 14:51:16 UTC | H05-s2.0 | dev-H | base + bi quan | 183 lệnh, mean net R -0.1176 / bi quan -0.1271; FAIL | `2f03f792061a4f00` |
| 15 | 2026-10-08 14:51:16 UTC | H05-s2.5 | dev-H | base + bi quan | 22 lệnh, mean net R -0.3469 / bi quan -0.3510; FAIL | `c4ca56c25293fce9` |
| 16 | 2026-10-08 14:51:17 UTC | H06-N20 | dev-H | base + bi quan | 142 lệnh, mean net R -0.0993 / bi quan -0.1011; FAIL | `fd50e5852a1dcedd` |
| 17 | 2026-10-08 14:51:18 UTC | H06-N40 | dev-H | base + bi quan | 101 lệnh, mean net R -0.0415 / bi quan -0.0433; FAIL | `eb3949ac74445693` |
| 18 | 2026-10-08 14:51:18 UTC | H06-N80 | dev-H | base + bi quan | 78 lệnh, mean net R -0.1808 / bi quan -0.1825; FAIL | `03e93934a18e6b36` |
| 19 | 2026-10-08 14:51:32 UTC | H01-theta0.3 | val-H | base + bi quan | 1091 lệnh, mean net R -0.0827 / bi quan -0.0908; FAIL | `b2ec554d467c0d66` |
| 20 | 2026-10-08 14:51:33 UTC | H01-theta0.6 | val-H | base + bi quan | 600 lệnh, mean net R -0.1097 / bi quan -0.1163; FAIL | `855a09953e7a618c` |
| 21 | 2026-10-08 14:51:34 UTC | H01-theta0.9 | val-H | base + bi quan | 291 lệnh, mean net R -0.0441 / bi quan -0.0507; FAIL | `83e5f557b1f9d640` |
| 22 | 2026-10-08 14:51:37 UTC | H02-b0.0 | val-H | base + bi quan | 640 lệnh, mean net R -0.0326 / bi quan -0.0386; FAIL | `9b548405883ba019` |
| 23 | 2026-10-08 14:51:39 UTC | H02-b0.25 | val-H | base + bi quan | 562 lệnh, mean net R -0.0463 / bi quan -0.0524; FAIL | `c1f60507d76a1e53` |
| 24 | 2026-10-08 14:51:40 UTC | H02-b0.5 | val-H | base + bi quan | 487 lệnh, mean net R -0.0943 / bi quan -0.1043; FAIL | `e048e97b0e21285f` |
| 25 | 2026-10-08 14:51:41 UTC | H03-c0.8 | val-H | base + bi quan | 35 lệnh, mean net R -0.0588 / bi quan -0.0738; FAIL | `62096c9bfb932ec3` |
| 26 | 2026-10-08 14:51:41 UTC | H03-c0.9 | val-H | base + bi quan | 83 lệnh, mean net R +0.0208 / bi quan +0.0123; FAIL | `f5b34041d4fba9bd` |
| 27 | 2026-10-08 14:51:42 UTC | H03-c1.0 | val-H | base + bi quan | 119 lệnh, mean net R -0.0569 / bi quan -0.0663; FAIL | `aa83ed1b697ea855` |
| 28 | 2026-10-08 14:51:44 UTC | H04-L10 | val-H | base + bi quan | 687 lệnh, mean net R -0.1666 / bi quan -0.1747; FAIL | `e727d1e8f5198dda` |
| 29 | 2026-10-08 14:51:46 UTC | H04-L20 | val-H | base + bi quan | 701 lệnh, mean net R -0.1436 / bi quan -0.1482; FAIL | `927967dc43f70410` |
| 30 | 2026-10-08 14:51:48 UTC | H04-L40 | val-H | base + bi quan | 703 lệnh, mean net R -0.1207 / bi quan -0.1332; FAIL | `fd5e5e7a0716c01d` |
| 31 | 2026-10-08 14:51:49 UTC | H05-s1.5 | val-H | base + bi quan | 305 lệnh, mean net R -0.0930 / bi quan -0.1005; FAIL | `c75fa0df111e754d` |
| 32 | 2026-10-08 14:51:50 UTC | H05-s2.0 | val-H | base + bi quan | 80 lệnh, mean net R -0.0426 / bi quan -0.0461; FAIL | `43f8a9c86daec1e5` |
| 33 | 2026-10-08 14:51:50 UTC | H05-s2.5 | val-H | base + bi quan | 6 lệnh, mean net R +0.6667 / bi quan +0.6667; FAIL | `3202b3d4d182d190` |
| 34 | 2026-10-08 14:51:50 UTC | H06-N20 | val-H | base + bi quan | 71 lệnh, mean net R -0.3755 / bi quan -0.3773; FAIL | `7eb9c5d6aadb5c2f` |
| 35 | 2026-10-08 14:51:51 UTC | H06-N40 | val-H | base + bi quan | 54 lệnh, mean net R -0.4262 / bi quan -0.4280; FAIL | `972a934966701c2b` |
| 36 | 2026-10-08 14:51:51 UTC | H06-N80 | val-H | base + bi quan | 34 lệnh, mean net R -0.2670 / bi quan -0.2685; FAIL | `3470093233226e1d` |

Tổng: 36 lần chạy = 18 biến thể x {Dev-H, Val-H}, mỗi lần gồm kịch bản cơ sở và bi quan. Không có lần
chạy lỗi hay bỏ dở. Không lần nào trên Test-H (không biến thể nào PASS Dev-H và Val-H) và holdout
không bị chạm. K đã dùng nằm trong lưới đã đăng ký (K = 21, alpha = 0.002381); không thêm biến thể.
Code: commit `d28a3d0`. Cờ `code_dirty=true` ở các bản ghi sau bản đầu tiên chỉ do chính thư mục kết
quả `experiments/edge_program/` chưa được track lúc chạy; không file code nào thay đổi giữa các lần.

## Kết luận chương trình (2026-10-08)

* Điều kiện dừng đạt: cả 6 giả thuyết đã dùng hết (18/18 biến thể đã đánh giá), K không vượt trần.
* Kết luận: **(B) NO EDGE WITHIN BUDGET**. Chi tiết: `final-verdict.md`.
* Quy tắc 6 (chọn cho override D2): 11 biến thể đủ >= 100 lệnh ở cả Dev-H và Val-H; điểm cao nhất là
  **H03-c1.0** với min(mean net R bi quan Dev-H, Val-H) = min(-0.0143, -0.0663) = **-0.0663 R/lệnh**.
  Điểm <= 0: **không có biến thể nào dương cả hai giai đoạn sau chi phí bi quan**; H03-c1.0 chỉ là
  giá trị tham khảo, không phải phát hiện.
* T1.5 prop filter trên H03-c1.0 (lệnh bi quan Dev-H + Val-H, 312 ngày có lệnh, 10.000 đường, seed
  7): mức rủi ro lớn nhất giữ P(vi phạm trong 90 ngày) <= 5% là 0,35%/lệnh; override =
  min(0,35; 0,25) = **0,25%/lệnh**. Kết quả: `experiments/edge_program/verdict.json`.
* Quy tắc 5 (review độc lập) chỉ áp dụng cho ứng viên PASS; không có ứng viên nào nên không kích hoạt.
