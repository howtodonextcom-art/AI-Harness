# Ngữ nghĩa spread của MT5 (FTMO XAUUSD)

Nguồn đo: `scripts/market_data_parity.py` (20.000 nến cuối mỗi khung) và quote trực tiếp.

* **Quote**: `spread_price = ask - bid` (đơn vị giá), `spread_points = spread_price / point` với
  `point = 0.01` cho XAUUSD tại FTMO. Ví dụ đo sống: bid 4201.34, ask 4201.78 → 0.44 giá = 44 điểm.
* **Trường `spread` của nến** là số **điểm** (points), một giá trị **do broker ghi cho nến** (giá trị
  spread tại thời điểm nến, không phải trung bình/tối đa trong nến). Không bao giờ coi nó là spread
  trung bình của nến hay của đoạn khớp lệnh thật.
* Resample dùng chính sách `last` theo mặc định (spread của nến mịn cuối cùng trong bucket); khi cần
  một thước đo phân phối, dùng `spread_summary` trên tick thay vì suy ra từ nến.
* Spread biến thiên theo thời điểm: nới ở rollover, tin tức, thanh khoản thấp. Không được lấy một con
  số cố định cho chi phí.

| Khung | Số nến | Min | Trung vị | P95 | Max | Tỷ lệ 0 |
|---|---|---|---|---|---|---|
| M1 | 20000 | 35 | 40.0 | 49.0 | 120 | 0.00000 |
| M15 | 20000 | 0 | 40.0 | 58.0 | 196 | 0.00015 |
| H1 | 20000 | 0 | 21.0 | 45.0 | 193 | 0.00045 |

Ghi chú: nến M15/H1 có vài nến `spread = 0` (tỷ lệ < 0,05%) — là giá trị broker ghi (thường nến nhập
cũ/không có tick), không phải spread thật bằng 0; bộ validator coi là điểm cần xem xét, không sửa.
Điểm vs giá: 1 điểm = 0.01 USD/oz; 44 điểm = 0.44 USD.
