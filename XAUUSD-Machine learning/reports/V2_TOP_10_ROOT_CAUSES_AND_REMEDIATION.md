# V2 · Top 10 nguyên nhân gốc và phương án khắc phục (đề xuất, chưa thực thi)

Ngày: 2026-10-13 · Ưu tiên P0 (làm trước) → P3. Không đề xuất nới an toàn/rủi ro.

| # | P | Module | Bằng chứng | Nguyên nhân gốc | Hệ quả cho trader | Giải pháp | Độ phức tạp | Cải thiện đo được | Rủi ro | Kiểm chứng |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | P0 | UI `SystemPanel.tsx` | grep: không render `next_condition` | API có dữ liệu, UI bỏ | không biết cần gì để BUY/SELL | render + thang chuỗi | S | % trạng thái WAIT có "điều kiện tiếp theo" hiển thị: 0 → 100% | gây nhiễu nếu quá dài | test UI + ảnh 720 px |
| 2 | P0 | `decision_log` | thiếu lệnh AUTO 07:43 | chỉ ghi tại M5 close | mất dữ liệu phân tích | ghi theo sự kiện đổi trạng thái + khi vào lệnh | S | độ phủ log của mọi lệnh = 100% | phình DB | test: mọi lệnh có dòng log |
| 3 | P0 | `decision.py` hiển thị | SPREAD_TOO_WIDE khi H1 NEUTRAL | hard gate che chuỗi | tưởng chỉ do spread | xuất cả cổng + trạng thái chuỗi (không đổi quyết định) | S–M | 100% WAIT có cả hai tầng | đổi hợp đồng API | parity test: quyết định không đổi |
| 4 | P1 | governor | ~24% bar RISK_LIMIT/COOLDOWN | trộn trạng thái hệ thống vào lý do | không tách WAIT thị trường/hệ thống | tách trường `system_hold` vs `market_blocker` | S | nhãn tách 100% | | test |
| 5 | P1 | quote | p95 3,4–3,8 s, p99 10,9 s, 47% quote không hiện | poll 1 Hz + đuôi collector | giá hiển thị cũ khi bấm | điều tra đuôi collector; cảnh báo tuổi >5 s | M | p99 10,9 → ≤6 s | chạm collector (cần cẩn trọng) | đo lại 30 phút |
| 6 | P1 | Candidate | 0 ref live | chưa có kết quả nghiên cứu | không cải thiện não | chốt spec 1.1.0 → Stage A DEV' | M (compute 4–8 h/lõi) | có tín hiệu để đánh giá | tiêu tốn CPU | replay hash |
| 7 | P1 | Dữ liệu tick | tick 2022-Q1 lỗi | chỉ ghi nhãn, không chặn | rủi ro mô hình chi phí sai | cổng kỹ thuật chặn khoảng lỗi | S | 0 truy cập không có cờ | | test |
| 8 | P2 | Thư viện mẫu nến | V1 có, V2 live không | không mang sang/không thiết kế | thiếu ngữ cảnh nến | nghiên cứu mô tả (không đổi quyết định) trước | M–L | | tuning trên cửa sổ khóa | preregistration |
| 9 | P2 | UI 720 px | key panel phải cuộn | bố cục | mất thông tin | đưa panel quyết định lên đầu | S | không cuộn ở ≤720 | | ảnh/ test vị trí |
| 10 | P3 | Hiệu năng | 92% đọc Parquet lặp | tail mỗi giây | lãng phí nhẹ | cache theo bar đóng | S | CPU V2 3,6% → thấp hơn | cache cũ | đo CPU, parity |

Ghi chú: #5, #6 phải theo giới hạn máy (≤4 worker ưu tiên thấp, CPU <60%), không chạm collector đang chạy khi chưa có cửa sổ bảo trì.
