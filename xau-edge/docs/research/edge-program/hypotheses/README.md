# Edge Program: 6 giả thuyết đăng ký trước (pre-registered)

Đăng ký ngày 2026-10-08 (T1.3), TRƯỚC khi chạy bất kỳ backtest nào trên dữ liệu mới. Không file nào
trong thư mục này được sửa sau khi có kết quả; một thay đổi = một giả thuyết mới, tính vào K (và
chương trình chỉ có N = 6 giả thuyết). Split, chi phí và quy tắc PASS: phụ lục cuối
`docs/evals/edge-criteria.md` (7 tiêu chí NGUYÊN VẸN).

## Quy ước chung (áp dụng cho cả 6)

* Dữ liệu: H1 (và H4 cho H06) của `data/research_history`, dataset_id `8e64dd6561015b72` (H1),
  `b438f1794bd11402` (H4). Daily dẫn xuất từ H1 (H04). Thực thi trên bar H1.
* Tín hiệu chỉ dùng bar ĐÃ ĐÓNG; quyết định tại thời điểm đóng bar; vào lệnh ở open của bar H1 kế
  tiếp; mỗi lần chỉ một vị thế (engine bỏ qua tín hiệu khi đang có vị thế).
* ATR = ATR(14) Wilder của timeframe tín hiệu tại bar quyết định (cột `atr_14` của feature set).
* Thoát: stop = `stop_atr` x ATR, target = `target_atr` x ATR tính từ giá khớp, hết `hold` bar thì
  đóng theo thị trường. Chạm cả stop và target trong cùng một bar: tính stop.
* Nơi `hold` đếm theo bar của timeframe tín hiệu, nó được đổi sang bar H1 (thực thi) khi ghi tín hiệu.
* Chi phí: spread = max(ghi nhận, 30 pts), slippage 3 pts mỗi lần khớp, commission 0, swap hiện
  hành; kịch bản bi quan: slippage 6 pts. Sizing/rủi ro: RiskEngine mặc định như các baseline
  (0.5% rủi ro/lệnh trên 100,000 USD), regime SHOCK bị chặn, không có lịch tin tức (nghiên cứu).
* Hướng giao dịch được cố định trong giả thuyết (momentum hay fade). Kết quả theo hướng NGƯỢC LẠI
  không được báo cáo như một phát hiện (nó sẽ là một giả thuyết khác, tính vào K).
* Lưới tham số: 1 tham số x 3 giá trị cho mỗi giả thuyết, tức mỗi giả thuyết đóng góp 3 biến thể,
  tổng 18; K = 3 (baseline) + 18 = 21 (xem `ledger.md`).
* Mọi biến thể đều là "finalist" (không chọn lọc trên Dev); chạy cả Dev-H và Val-H cho tất cả.

## Mục lục

| ID | Tên | Cơ sở kinh tế (00-diagnosis mục 4) |
|---|---|---|
| H01 | Động lượng ở giờ mở phiên (Tokyo/London/New York) | thanh khoản và dòng lệnh vĩ mô dồn vào giờ mở phiên |
| H02 | Phá vỡ biên độ Asia khi London/NY mở | thanh khoản mỏng ở Asia, định giá lại khi châu Âu/Mỹ vào |
| H03 | Nén biến động rồi mở rộng (Donchian trong chế độ nén) | volatility clustering |
| H04 | Xu hướng ngày + hồi về EMA H1 | momentum ngày (time-series momentum) |
| H05 | Đảo chiều sau bar xung lực quá mức (fade) | price impact tạm thời, thanh khoản cạn |
| H06 | Xu hướng H4 Donchian | persistence của dòng vốn vĩ mô (CTA-style trend) |

Ghi chú về tiêu chí 7 (không đổi): các giả thuyết ở đây được thiết kế để thời điểm vào lệnh phân
tán trên nhiều phiên/chế độ; nếu một biến thể vẫn tập trung > 60% lợi nhuận vào một phiên hoặc
chế độ thì nó FAIL tiêu chí 7, đúng như quy tắc.

Ghi chú về London fix và cửa sổ tin tức: không được đăng ký vì (a) một giả thuyết vào lệnh ở giờ cố
định luôn dồn 100% lợi nhuận vào một phiên và FAIL tiêu chí 7 theo cấu trúc, (b) chưa có lịch tin
tức có `available_at`.
