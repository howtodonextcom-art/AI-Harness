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

## Bảng chạy

| # | Thời gian | Giả thuyết/biến thể | Giai đoạn | Kịch bản | Ghi chú | Registry id |
|---|---|---|---|---|---|---|
