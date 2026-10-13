# V2 PERFORMANCE BASELINE (đo V1 trước khi đặt mục tiêu V2)

Ngày: 2026-10-12 · V1 HEAD `daf22f6` · Quy tắc (mục 55–56, 67, 100): **đo V1 trước; V2 chỉ được gọi "nhanh hơn" nếu có số đo; không bịa phần trăm cải thiện trước khi đo.**

## 1. Điều kiện đo (đọc trước khi dùng số)

- Máy: Windows 11, cùng máy chạy MT5 + collector + API + dashboard (đang vận hành bình thường, thị trường MỞ, phiên London+New York).
- API: Python (FastAPI) `127.0.0.1:8000`; dashboard Next.js `:3000`; gọi từ Python `urllib` (không qua trình duyệt), **40 lần mỗi endpoint**, tuần tự.
- UI: Chromium headless 1248 (Playwright), viewport 1440×900, `/trade`, **một lần tải** (không xóa cache), 30 giây rảnh, 25 lần kéo biểu đồ.
- **Chưa đo:** cold start, soak, FPS khi kéo (chỉ nhịp khung rảnh), WebSocket reconnect (V1 không có WebSocket), disk writes, CPU theo thời gian thực. Những mục này thuộc G8 và phải được đo trên cả V1 và V2 cùng workload.
- Một lần đo, không lặp theo ngày giờ; **độ lệch chuẩn giữa các lần chạy chưa biết.**

## 2. Độ trễ API của V1 (40 mẫu mỗi endpoint)

| Endpoint | p50 (ms) | p95 (ms) | max (ms) | Payload (byte) |
|---|---|---|---|---|
| `/trade/decision` | 39,5 | **63,5** | 66,1 | 14.003 |
| `/md/status` | 33,6 | 47,4 | 52,0 | 2.289 |
| `/md/XAUUSD/quote` | 7,2 | 23,5 | 31,1 | 451 |
| `/md/XAUUSD/bars` M5 limit 400 | 10,2 | 23,3 | 32,9 | 58.010 |
| `/md/XAUUSD/bars` M15 limit 400 | 9,0 | 30,4 | 34,6 | 58.294 |
| `/md/XAUUSD/bars` H1 limit 500 | 12,3 | 37,4 | 37,8 | 73.072 |
| `/md/XAUUSD/bars` M1 limit 400 | 11,6 | 36,0 | 115,9 | 57.868 |
| `/md/XAUUSD/bars` M1 limit 5000 | 45,2 | 64,9 | 73,8 | 717.629 |
| `/md/XAUUSD/bars` H1 limit 5000 | 60,1 | 71,7 | 83,8 | 725.998 |
| `/md/XAUUSD/bars` H4 limit 5000 | 92,4 | 104,0 | 126,4 | 726.483 |
| `/trade/journal` | 2,3 | 19,0 | 34,6 | 446 |
| `/research/overview` | 67,8 | 95,5 | 494,8 | 2.456 |

## 3. UI của V1 (`/trade`, 1440×900, một lần tải)

| Chỉ số | Giá trị |
|---|---|
| `load` event | 332,7 ms (đo ngoài: 340 ms) |
| DOMContentLoaded | 96,7 ms |
| First Contentful Paint | 324 ms |
| Largest Contentful Paint | 776 ms |
| Canvas biểu đồ xuất hiện | 725 ms |
| JavaScript truyền | **291.221 byte nén** (943.680 byte giải nén), **13 file** |
| CSS truyền | 11.303 byte (1 file) |
| Tổng tài nguyên | 38 |
| Long task (≥ 50 ms) | 2, lớn nhất 97 ms |
| JS heap | 8,9 MB |
| DOM nodes / event listeners | 956 / 566 |
| Nhịp khung khi rảnh (400 khung) | p50 16,7 ms · p95 17,2 ms · max 18,2 ms (≈ 60 FPS) |

### Tải mạng khi rảnh (30 giây)

40 request / 30 s ≈ **80 request/phút**: `/trade/decision` 10, `/md/XAUUSD/bars` 10, `/trade/markers` 5, `/trade/signals` 5, `/trade/journal` 5, `/trade/setups` 5. Riêng `/bars` tải lại cả 400 nến (~58 KB) mỗi 3 giây ≈ **1,16 MB/phút** chỉ để biết vài nến cuối thay đổi; cộng `/trade/decision` (14 KB × 20) ≈ 0,28 MB/phút.

## 4. Tiến trình và bộ nhớ của V1 (Working Set)

| Tiến trình | RAM | CPU tích lũy |
|---|---|---|
| Collector (`run_market_collector.py`) | **397 MB** | 3.619 s |
| API (`serve_api.py`, gồm engine PAPER) | **188 MB** | 617 s |
| Dashboard (Next.js `node`) | 29 MB | 3 s |
| Tiến trình khởi chạy (launcher/`run_market_stack`, news refresher) | ~1–5 MB mỗi cái | ~30 s |
| **Tổng ước tính** | **≈ 620 MB** | |

(5 tiến trình Python + 1 Node đang chạy; vài tiến trình xuất hiện hai lần vì launcher của venv.)

## 5. Mục tiêu hiệu năng của đặc tả (mục 55) so với V1

| Mục tiêu | Ngưỡng | V1 đo được | V1 đã đạt? |
|---|---|---|---|
| API khởi tạo, p95 sau warm-up | < 150 ms | 23–37 ms (bars), 63,5 ms (decision) | **Đạt** |
| Endpoint quyết định p95 (không gồm MT5) | < 100 ms | 63,5 ms | **Đạt** |
| Render đầu tiên có nghĩa (local) | < 1,5 s | FCP 324 ms, LCP 776 ms | **Đạt** |
| Cập nhật trạng thái sau phản hồi API | < 100 ms | **chưa đo** | — |
| Tương tác biểu đồ ≥ 55 FPS | ≥ 55 | rảnh ≈ 60 FPS; **kéo chưa đo** | một phần |
| Không long task > 200 ms | 0 | lớn nhất 97 ms | **Đạt** |

## 6. Hàm ý cho V2 (quan trọng, trung thực)

1. **V1 đã đạt các ngưỡng của mục 55.** Vì vậy "V2 nhanh hơn V1" **không phải điểm khác biệt có thật** trên trải nghiệm tải trang và độ trễ API cục bộ; mục tiêu V2 hợp lý là *không chậm hơn* (đặt ngưỡng sau khi đo V2 ở G2).
2. **Cơ hội thật nằm ở tải mạng và cấu trúc:** (a) đưa 80 request/phút và 1,4 MB/phút xuống còn một kênh sự kiện + delta; (b) loại 13 chunk JS (291 KB nén) nếu SPA tĩnh nhỏ hơn: **chỉ khẳng định sau khi đo bundle V2**; (c) giảm số tiến trình (hiện 5 Python + 1 Node) và RAM (collector 397 MB là điểm đáng xem xét: lý do chưa điều tra).
3. **Không bịa:** mọi phần trăm cải thiện của V2 sẽ được báo cáo từ số đo cùng workload ở G2 (khởi động, bundle), G5 (UI), G8 (soak).

## 7. Cách tái lập

`reports/evidence/g0/api_latency_and_depth.py.txt` (đổi đuôi `.py`, chạy khi API đang chạy), `ui_perf_and_chart_history_probe.cjs.txt` (cần `node` và `@playwright/test` của `apps/dashboard`, trình duyệt Chromium); kết quả thô: `ui_perf.json`.
