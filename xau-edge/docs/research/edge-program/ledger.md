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
