# V2 · Kiểm toán dữ liệu thời gian thực và độ trễ

Ngày: 2026-10-13 · Công cụ: `xau-edge-v2/scripts/audit/p0_measure.py`, `mt5_tick_sampler.py` (chỉ đọc `symbol_info_tick` ở 10 Hz). Bằng chứng: `reports/evidence/audit_p0/p0_latency.json`, `p0_propagation.json`, `mt5_ticks.json`.

## 1. Đường ống
MT5 tick → collector V1 → `live.json` (~1/s) + Parquet → V2 `live_feed` (cache 0,25 s, STALE=30 s) → `live_analysis` (cache 1 s) → FastAPI → WS `/ws` (poll: live 1,0 s, state 3,0 s, heartbeat 5,0 s, paper 3,0 s) → React → chart.
Cơ chế: **polling snapshot**, không phải stream tick. Mỗi giây V2 đọc trạng thái mới nhất.

## 2. Số đo (VERIFIED IN RUNTIME)
| Đoạn | Chỉ số | Kết quả |
|---|---|---|
| Tuổi quote tại V2 | p50 / p95 / max | 0,86 s / 2,67 s / 4,45 s (lần 1); 0,95 / 3,38 / 4,92 (lần 2) |
| Tuổi collector | p50 / p95 | 0,64–0,70 s / 1,19–1,36 s |
| MT5→hiển thị V2 (khớp cùng bid/ask) | p50 / p95 / p99 / max | **0,47 s / 3,78 s / 10,9 s / 10,9 s**, n=40 khớp |
| Quote khác nhau của MT5 chưa từng thấy ở V2 | | **35/75 (~47%)** |
| REST `/state` | p50/p95/p99 | 8,8 / 63,5 / 90,1 ms (n=150) |
| REST `/market/quote` | | 8,0 / 32,0 / 34,6 ms |
| REST `/market/forming` | | 10,5 / 32,0 / 37,9 ms |
| REST `/health` | | 21,4 / 46,1 / 66,7 ms |
| REST `/market/bars` M5×500 (71 KB) | | 21,7 / 42,2 / 48,6 ms |
| REST `/paper/summary` | | 10,5 / 32,1 / 42,1 ms |
| WS | seq gap | **0** trong 53 sự kiện |
| WS | live giữa hai sự kiện | median 1,031 s; heartbeat 5,217 s |
| WS | trễ giao | p50 0,45 ms, p95 0,54 ms |
| `compute_analysis` | median | ~17 ms, ~92% là đọc Parquet |
| CPU/RAM | V2 3,6% 1 lõi / 112 MB; collector 9,4% / 393 MB; API V1 1,5% / 194 MB |

## 3. Diễn giải
- Phần lớn trễ nằm ở **bước lấy mẫu 1 Hz** (collector + poll), không ở FastAPI/WS (trễ <1 ms).
- Đuôi p99 ~11 s: nghi do đồng bộ ghi `live.json` của collector hoặc nghẽn tạm; **nguyên nhân chưa xác định** (NOT MEASURED ở cấp collector).
- Hệ quả giao dịch: với quyết định M5 và PAPER, trễ <5 s chấp nhận được; với "giá hiển thị để người bấm vào lệnh" nên hiển thị tuổi quote (đã có `age_seconds` trong API; UI cần nổi bật).
- Mẫu nhỏ: n=40 khớp, một lần chạy ~4 phút. Chưa có p99 ổn định, chưa đo qua phiên Á/Âu/Mỹ.

## 4. Ngân sách độ trễ đề xuất (không áp dụng)
| Đoạn | Mục tiêu p95 |
|---|---|
| MT5→collector | ≤ 1 s |
| collector→V2 | ≤ 1,5 s |
| V2→trình duyệt | ≤ 100 ms |
| Tổng tuổi quote hiển thị | ≤ 3 s p95, ≤ 6 s p99 |
Hiện p95 3,4–3,8 s: sát biên; p99 10,9 s: vượt.

## 5. Tính lại theo từng tick?
Không cần. Quyết định dựa trên bar M5 đã đóng + spread live; 1 Hz đủ. Mỗi giây tính ~17 ms (rẻ) nhưng 92% là đọc Parquet lặp (có thể cache theo bar đóng — tối ưu hóa nhỏ, không phải thắt cổ chai).

## 6. NOT MEASURED
Trễ render chart trong trình duyệt; WS với nhiều client; hành vi khi collector chết (cơ chế STALE_QUOTE 30 s chỉ đọc từ mã); độ trễ tick-to-bar đóng; đuôi p99.9.
