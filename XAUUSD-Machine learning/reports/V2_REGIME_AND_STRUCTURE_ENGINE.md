# V2 · Động cơ chế độ và cấu trúc (định nghĩa, nhân quả, đo hành vi nhãn)

Ngày: 2026-10-13 · Dữ liệu: DEV' 2016-01..2018-12, kho sạch (chỉ tháng PASS, hash kiểm), H1 (17.623 nến) và M15 (70.466 nến). **Không outcome, không P&L.** Nguồn: `docs/research/intel_descriptive_dev.json` (seed 20261013, manifest `997d73f8…`), script `scripts/research/intel_descriptive.py`.

## 1. Định nghĩa
| Khái niệm | Định nghĩa | Nhân quả |
|---|---|---|
| Swing high/low | `high[i]` > `left=3` nến trước và ≥ `right=3` nến sau | biết tại đóng nến `i+3`, đo độ trễ = **3** (mọi swing) |
| Provisional swing | ứng viên trong 3 nến cuối | gắn `confirmed=false`; có thể mất |
| BOS / CHoCH | **đóng** vượt swing chưa phá; BOS theo xu hướng trước, CHoCH ngược | biết tại đóng nến đó |
| Phá vỡ thất bại | BOS/CHoCH rồi đóng lại dưới/trên mức đã phá trong ≤3 nến | biết tại đóng nến mất mức |
| Chế độ (V1) | SHOCK > HIGH_VOL > TREND (ADX≥25) > LOW_VOL > RANGE | từ chỉ báo nhân quả (test repaint indicators) |
| Pha biến động (mới) | ATR/trung vị 100 ATR trước; trung bình range 6 nến; hộp 12 nến | nến đóng cuối |

## 2. Đo hành vi nhãn (DEV', không outcome)
| Số đo | H1 | M15 |
|---|---|---|
| Sai lệch repaint trong 25 điểm cắt ngẫu nhiên × 2 bộ phát hiện | **0** | **0** |
| Độ trễ xác nhận swing | 3 nến | 3 nến |
| BOS/CHoCH rồi **mất mức ≤3 nến** | **48,0%** | **48,0%** |
| Chế độ RANGE / TREND_UP / TREND_DOWN | 45,6% / 23,5% / 24,5% | 48,3% / 18,0% / 20,4% |
| HIGH_VOL / LOW_VOL / SHOCK | 3,8% / 0,8% / 1,7% | 9,2% / 2,6% / 1,5% |
| Độ bền chế độ: trung vị / trung bình nến liên tiếp | 5 / 11,5 | 5 / 11,4 |
| Số lần đổi chế độ mỗi 1000 nến | 87,3 | 87,6 |
| Pha biến động (mẫu mỗi 40 nến): NORMAL / EXPANSION / COMPRESSION | 81% / 17% / 2% | 67% / 28% / 5% |
| Phá hộp nén (mẫu): lên / xuống | 6 / 5 | 24 / 22 |

## 3. Đọc kết quả (trung thực)
1. **Không repaint**: các bộ phát hiện nhất quán khi cắt lịch sử (kể cả trên 70k nến thật).
2. **Nhãn cấu trúc nhiễu**: gần một nửa BOS/CHoCH không trụ nổi 3 nến. Dùng "BOS" làm trigger đơn độc sẽ nhập cuộc vào nhiều phá vỡ thất bại. Đây là tính chất của *nhãn*, không phải tuyên bố về lợi nhuận.
3. **Nhãn chế độ không bền**: trung vị 5 nến. Một luận điểm "đang RANGE" cần nhãn kéo dài đủ lâu để có ý nghĩa; phân phối độ dài riêng cho RANGE chưa đo (chỉ có thống kê chung cho mọi chế độ). Bất kỳ bộ lọc bền nào (vd. 20 nến) là biến thể mới và tăng K.
4. **EXPANSION 28% (M15)** nghĩa là ngưỡng tiên nghiệm `ATR ratio ≥ 1,3 hoặc range ≥ 1,5 ATR` quá dễ thỏa; nhãn này hiện ít thông tin. **Không chỉnh sau khi nhìn kết quả**: ghi vào ledger để tiền đăng ký lại.
5. Phá hộp hiếm (M15 ~46 mẫu/1.755): họ B có ít cơ hội khi dùng định nghĩa chặt, đồng thời `median_risk_atr ≈ 2,8` (xem protocol).

## 4. Giới hạn
Mẫu 3 năm cuối DEV', không quét toàn DEV'; H4/M5/M1 chưa đo; thống kê nhãn không nói gì về giá trị giao dịch; thiếu đo "thông tin gia tăng" so với nhãn V1 (cần outcome, bị khóa).
