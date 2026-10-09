# P0 forensics: kết quả (Class D, không tạo bằng chứng edge)

Ngày: 2026-10-09. Mọi mục dưới đây là **Class D**: mô tả, không tính vào K, không thể dùng để mở lại một
giả thuyết đã thất bại và không phải căn cứ chọn giả thuyết mới. Mã: `src/xau_edge/forensics/`,
`scripts/forensics_p0.py`, `scripts/probe_mt5_depth.py`, `scripts/p0_cost_attribution.py`.

## 1. Chứng nhận đồng hồ broker theo năm (chỉ dùng timestamp, không đọc giá)

Phương pháp: phút New York của bar cuối cùng trước mỗi cuối tuần thật (Thứ Sáu NY sang Chủ Nhật NY) qua các
tuần Mỹ và EU lệch giờ mùa hè (DST). Đồng hồ neo New York giữ 17:00 NY trong tuần lệch; đồng hồ theo DST
châu Âu thì trượt 60 phút. File: `clock-certificate.json`.

| Năm | Tuần cuối tuần | Mở cửa NY | Tuần lệch DST | Giữ 17:00 NY trong tuần lệch | Chứng nhận |
|---|---|---|---|---|---|
| 2010-2020 | 46-51 | 17:00 (2010: 18:00) | 2-4 | **0%** | **KHÔNG** |
| 2021 | 49 | 18:00 | 3 | 100% | có |
| 2022 | 49 | 18:00 | 3 | 100% | có |
| 2023 | 49 | 18:00 | 3 | 100% | có |
| 2024 | 51 | 18:00 | 3 | 100% | có |
| 2025 (Jan-Apr) | 16 | không đủ tuần | 0 | không kiểm được | không |

**Phát hiện.** Trước 2021 bộ dữ liệu theo đồng hồ châu Âu có DST (đóng cửa tuần dịch sang 16:00 NY đúng vào
các tuần lệch DST Mỹ/EU, ví dụ 2015-03-13/20/27 và 2015-10-30), từ 2021 theo đồng hồ neo New York. Mỗi năm
trước 2021 khoảng 3-4 tuần (6-8%) có timestamp UTC lệch một giờ. Lịch phiên cũng đổi: giờ mở lại sau break là
17:00 NY trước 2021 và 18:00 NY từ 2021; số bar nằm trong cửa sổ đóng cửa của lịch hiện tại là khoảng 514
mỗi năm trước 2021 so với khoảng 258 từ 2021.

**Hệ quả.** Giả thuyết theo giờ phiên (H09, mức Asia của H07/H08, H01/H02 của Programme 1) bị ảnh hưởng ở
các ngày lệch DST trước 2021. Batch A xử lý bằng *loại bỏ có khai báo* (không sửa, không dịch giờ): ngày giao
dịch rơi vào khoảng lệch của năm chưa chứng nhận bị loại và được đếm (H07-PD 148, H07-ASIA 216, H09 148,
H10 47-88 sự kiện). Lý do loại thay vì sửa: ADR-0005 (báo cáo, không sửa) và vì ngoài khoảng lệch hai đồng
hồ trùng nhau nên các ngày còn lại đúng.

## 2. Chất lượng dữ liệu theo năm (`data-quality-by-year.json`)

Tỷ lệ bar thiếu so với lịch (H1) khoảng 1.6-2.7% mỗi năm từ 2011 (2010: 11.9% do bắt đầu giữa năm), 1.1-1.5%
từ 2022. Khoảng trống dài hơn 28 giờ: 49-53 mỗi năm (cuối tuần và lễ). Không khôi phục hay lấp bar nào.

## 3. Quy mô chi phí (đối chiếu chi phí với kết quả Batch A)

Chi phí trung bình mỗi giao dịch khoảng **0.10-0.12R** ở thang ATR H1 (spread tối thiểu 30 points + slippage 3
points mỗi lần khớp). Swap theo giá terminal hiện tại chỉ thêm 0.01-0.03R. Bảng trong
`cost-attribution-dev2.json` (mean R trên Development-2):

* Mọi biến thể đều **âm** kể cả với spread ghi nhận (không sàn 30 points) và swap 0 (tối đa -0.027R ở
  H09-ASIA_LONDON-t0.2).
* Gross-mid dương nhưng nhỏ chỉ ở H09 (+0.03 đến +0.07R) và H10 L50/L100 (+0.01 đến +0.03R): chi phí nuốt hết.
* PD/ASIA đảo chiều (H07) có gross-mid âm: chi phí không phải nguyên nhân.

**Kết luận về nghi vấn "chi phí giết edge":** với barrier ATR H1, chi phí cỡ 0.1R/lệnh nghĩa là một edge H1
chỉ có ý nghĩa khi gross-mid vượt rõ 0.10R. Không giả thuyết nào của Batch A có gross đó.

## 4. Độ sâu dữ liệu MT5 (probe chỉ đọc, tài khoản DEMO, `mt5-probe.json`)

* **Tick**: có từ ít nhất 2022-03 (574-851 tick trong 5 phút mẫu); **không có** ở các mẫu 2021-09 trở về
  trước. Vì vậy tick không thể kiểm chứng mức Asia hay xác nhận trong-bar cho giai đoạn Development-2.
* **M1**: **INCONCLUSIVE**. Terminal trả tối đa 1 bar cho truy vấn M1 theo khoảng ở 4 năm mẫu (2025, 2022,
  2018, 2012), và "Call failed" với truy vấn theo vị trí. Cần tải lịch sử M1 thủ công từ terminal.
* **Cùng broker**: có XAUUSD, XAGUSD, XAUEUR, XAUAUD, EURUSD, GBPUSD, USDJPY, AUDUSD, USDCHF, BTCUSD. **Không
  có** DXY/USDX, chỉ số (US500, US100, US30, GER40), dầu (USOIL, UKOIL), VIX. Hệ quả: H14 (xác nhận chéo tài sản)
  chỉ làm được với FX/bạc cùng broker; chỉ số, dầu, DXY cần nguồn khác (OWNER_ACTION_REQUIRED nếu cần).

## 5. Đối soát K giữa các chương trình

Từ sổ đăng ký thí nghiệm cục bộ (`experiments/runs`): `edge-program` 36 lần chạy (18 biến thể x Dev-H/Val-H)
khớp ledger V1 (K = 3 baseline + 18 = 21); `backtest` 15 lần chạy / 6 tên; `model` 16 lần chạy / 8 tên;
`analogue-study` 4 lần chạy / 2 tên. **Không có bản ghi nào có `period = test`** trong bất kỳ họ nào: Test-H và
holdout nguyên vẹn theo sổ đăng ký (cộng với ledger V1 và các file kết quả, xem `locks()`).
V2 mở sổ mới: K = 20 (`ledger.md`), không cộng dồn với K cũ nhưng dữ liệu 2011-2021 đã bị Programme 1 dùng.

## 6. ENTRY_GAP và cuối tuần

Trong Batch A, sự kiện có bar vào lệnh cách bar quyết định hơn 90 phút bị loại và đếm
(`dropped_without_outcome`: 0-7 mỗi biến thể trên Development-2): tác động của ENTRY_GAP là không đáng kể
với các sự kiện của Batch A. Bar cuối tuần không bị sửa; chúng nằm trong số "bar trong cửa sổ đóng cửa".

## 7. Kết luận P0

* Đồng hồ: **đã chứng nhận từ 2021; không chứng nhận 2010-2020** (đồng hồ EU DST). Các giả thuyết theo giờ phiên
  phải dùng quy tắc loại ngày lệch DST (đã làm) hoặc dữ liệu đã được xác minh lại.
* Chi phí: không phải nguyên nhân duy nhất; thang chi phí 0.1R/lệnh đặt ngưỡng cho mọi edge H1.
* Dữ liệu sâu hơn (tick, M1) bị chặn: tick chỉ từ 2022; M1 cần thao tác của chủ dự án.
* Không thay đổi `edge-criteria.md`.
