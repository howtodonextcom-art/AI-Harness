# ADR-0027 (NHÁP): Một kho live duy nhất `data/market`; `data/raw` đóng băng thành kho nghiên cứu chỉ đọc

Status: **SUPERSEDED** as the working copy — accepted text is `docs/decisions/0027-single-live-store.md` (2026-10-11). Draft kept for the closed-loop rationale.

## Bối cảnh (đã kiểm 2026-10-11)
- `data/market` (ledger của collector, ~1,5 GB, trong đó tick ~1,4 GB) là nguồn của Trading Core (`trading/live_source.py:157,195`) và `/md/*`.
- `data/raw` (~8,4 MB, file mới nhất 2026-10-08 13:15 UTC) vẫn được API live đọc qua `DatasetCatalog` (`scripts/serve_api.py:43,50-58`) cho các route legacy `/market/{symbol}`, `/signals`, `/paper/*`, `/features`, `/regime`, `/patterns`. Các route này chỉ trang `/legacy` (ẩn khỏi menu) dùng (`components/Dashboard.tsx:71-80`). Script còn ghi vào đó: `compact_raw.py` (chuyển file sang `_archive`), `verify_mt5.py:118`, `demo_trader.py:369`.
- **Kho thứ ba đã tồn tại:** `data/research_history` (3 file parquet + 3 meta, ~3,5 MB, ghi 2026-10-08). Đây là nguồn thật của Edge V1/V2: `scripts/run_edge_program.py:56`, `run_batch_a.py:43`, `fetch_history.py:7,44` (gọi đây là "SEPARATE immutable store"). ADR-0021 `dataset_hash` băm `{timeframe: dataset_id}`, **không** băm nội dung file — không chứng minh byte không đổi.
- `serve_api.py:63-65` dựng thêm một `PaperTrader` legacy với journal riêng: thực chất là "bộ não thứ ba" chạy trên `data/raw`.

## Phương án đã xét (closed-loop, chấm mù theo rubric (b))
| Phương án | Reviewer kiến trúc | Reviewer rủi ro | Kết quả |
|---|---|---|---|
| Gộp `data/raw` vào ledger rồi xoá | 3,10 FAIL (B2 = 2: mất khả năng tái lập V1/V2) | xem báo cáo | Loại |
| **Đóng băng `data/raw` + một kho live** | **4,35 PASS** | xem báo cáo | **Chọn** |
| Giữ nguyên | 3,40 FAIL | xem báo cáo | Loại |

## Quyết định
1. `data/market` là kho **duy nhất** cho vận hành, Trading Core, dashboard và **mọi nghiên cứu mới**. Không tạo kho **thứ tư**. `data/research_history` đã là kho thứ ba — đóng băng, không xoá.
2. `data/raw` **và** `data/research_history` thành **kho nghiên cứu lịch sử chỉ đọc**:
   - mỗi kho có `MANIFEST.json` gồm đường dẫn, kích thước và sha256 của mọi file;
   - loader nghiên cứu kiểm manifest **mỗi lần tải**, lệch là từ chối chạy;
   - mọi writer (`fetch_history.py`, `compact_raw.py`, `verify_mt5.py`, `demo_trader.py`) từ chối ghi vào kho đã đóng băng (cần cờ tường minh + ADR mới để mở).
3. Nghiên cứu mới đọc `data/market` qua một loader point-in-time. Cutoff theo **thời điểm đóng nến** (`open + duration ≤ as_of`), không theo `timestamp` mở (`ledger.py:283-285` hiện lọc theo open — đó là look-ahead trên H1/H4). Mỗi lần chạy nghiên cứu ghim `ledger.file_hashes` + danh sách sự kiện `BAR_REPAIRED`.
4. Các route legacy đọc `data/raw` và `PaperTrader` legacy trong `serve_api.py` bị **retire cùng `/legacy`**, chỉ sau khi đủ điều kiện xoá legacy (ADR-0026).
5. Tuỳ chọn: import một chiều, chỉ đọc, kho lưu trữ sang định dạng ledger với nhãn nguồn riêng. **Không xoá, không back-fill nến từ `data/raw` vào ledger.**
6. Chạy lại V1/V2 từ archive (hash khớp) phải tái lập kết quả đã ghi — đó mới là bằng chứng khả năng tái lập. Hash ADR-0021 không đủ.

## Acceptance criteria
- AC-B1 **Must:** loader nghiên cứu từ chối chạy khi một file trong `data/raw` lệch hash manifest (test FAIL trước).
- AC-B2 **Must:** `fetch_history.py` / `compact_raw.py` thoát lỗi khi đích là kho đóng băng.
- AC-B3 **Must:** loader `data/market` với `as_of=T` không trả nến có `open + duration > T` (test look-ahead trên M1/M15/H1/H4).
- AC-B4 **Must:** archive cả `data/raw` và `data/research_history`; chạy lại V1/V2 từ archive tái lập kết quả đã ghi.
- AC-B5 **Must not:** xoá hoặc ghi đè file trong hai kho lưu trữ; không back-fill nến từ archive vào ledger.
- AC-B6 **Must not:** Trading Core, `/trade/*`, hoặc nghiên cứu mới đọc archive.

## Hệ quả
- Kết quả V1/V2 vẫn tái lập được. Nghiên cứu mới chỉ có lịch sử `data/market` (độ sâu theo collector/backfill). Test-H chỉ đủ H1, M15 từ 2022-07 (`docs/evals/edge-criteria.md`, phụ lục V2).
- Không đổi guard, không đổi hành vi `/trade`.
