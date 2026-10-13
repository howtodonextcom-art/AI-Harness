# V2 G3: kết nối dữ liệu chỉ-đọc và parity với V1

Ngày: 2026-10-12 · V2 commit `ce09a17` (repo `xau-edge-v2`, nhánh `main`, local, chưa push) · V1 HEAD `daf22f6` (**không bị sửa**).

> **TRẠNG THÁI:** mã, test, parity nhanh và **parity đầy đủ (202.542 phép kiểm, 0 sai lệch)** đã xong; độ trễ endpoint lịch sử đã đo (mục 5).

Quyết định của bạn đã áp dụng: G2 PASS · **G3 được duyệt** · `git init` trước G3 (**đã làm**) · O2 tiếp tục có điều kiện · dùng chung `data/market` **chỉ đọc nghiêm ngặt** · **K = 44 không kế thừa** · **ML V0 đóng băng (biên độ)** · **H-V2-01 chỉ nghiên cứu, không Test-H** · V1 chỉ đọc.

## 1. Việc đã làm trước G3

| Việc | Kết quả |
|---|---|
| `git init` cho `xau-edge-v2` | Xong. Nhánh `main`, commit local (chưa có remote, chưa push). **Lưu ý:** thư mục nằm trong repo cha `Z:\Coding\Projects\AI-Harness`, nên đây là **repo lồng**; repo cha sẽ coi `xau-edge-v2` là thư mục chưa theo dõi/nhúng. `.gitattributes` chuẩn hóa EOL (LF), `.gitignore` loại `logs/`, `node_modules`, `dist`, `.venv` |
| Sửa một lỗi của chính tôi | Commit đầu lỡ chứa tệp log (`logs/*.jsonl`) vì lệnh dọn dẹp lỗi mà bước commit vẫn chạy; đã `--amend` trước khi có bất kỳ push nào (không có remote) |
| Đóng băng ML V0 | `docs/ml/ml_v0_spec.json` (spec `ml-v0-rng24` v1.0.0, vai trò A: **không thẩm quyền**, nhãn `rng24.v1`, 13 đặc trưng đủ hợp đồng, ridge/HAR mặc định, tiêu chí thăng cấp, Test-H và Holdout **LOCKED, mỗi cái đúng một lần**), `ML_V0_FREEZE.md`, băm bảo vệ `ml_v0_spec.sha256` và 4 test chặn sửa tại chỗ. Muốn đổi phải tạo phiên bản mới |
| H-V2-01 | `docs/research/H-V2-01_RESEARCH_ONLY.md`: **RESEARCH_ONLY**, chưa đăng ký, không tiêu K, không dùng Test-H/Holdout, nêu rõ vì sao chưa phải bằng chứng và con đường tới bằng chứng sạch |
| Chính sách K | Giữ nguyên **mở** (ADR-V2-007): V2 không đăng ký giả thuyết nào |

## 2. G3 đã xây

**Miền thuần (không I/O), viết lại, không import V1:** `domain/market.py`: đồng hồ broker `NY+N`/IANA (chuyển hai chiều, từ chối giờ server mơ hồ/không tồn tại do DST), lịch thị trường (mẫu tuần, nghỉ giữa ngày, cửa sổ ngày lễ/đóng sớm gộp, `status`, `next_open`, `open_seconds_between`).

**Đọc dữ liệu chỉ-đọc:**
- `data/bar_store.py`: nến đã đóng theo khoảng, ngữ nghĩa như V1 (duy nhất theo thời điểm mở, bản đầu tiên thắng, sắp tăng); `tail(limit, before)`, `window(start, end, limit)`, `coverage`.
- `data/tick_store.py`: tick theo `[start, end)`.
- `data/live_feed.py`: quote, nến đang hình thành và **thông số hợp đồng của broker** từ tệp live của collector (`tick_size`, `tick_value`, bước lot…), ngưỡng cũ 30 giây như V1; tệp thiếu/hỏng ⇒ "UNAVAILABLE", không lỗi.
- `data/store_status.py`: **độ mới theo lịch thị trường**: một khung chỉ "CŨ" khi số giây thị trường *mở* kể từ lần đóng cuối vượt `2 × khung + 60 giây`; cuối tuần/nghỉ giữa ngày/ngày lễ hiển thị `MARKET_CLOSED`; kho dừng giữa tuần vẫn bị coi là CŨ kể cả khi đang đóng cửa.
- `data/broker_profile.py` + `configs/*.json`: hồ sơ FTMO demo và 1.307 cửa sổ đóng cửa **sao chép một lần** từ V1 kèm nguồn, SHA-256, thời điểm (`scripts/import_v1_config.py`); V2 không đọc cấu hình V1 lúc chạy.

**API (đều chỉ đọc, lỗi luôn có dạng `{error_code, message}`):**

| Endpoint | Ghi chú |
|---|---|
| `GET /api/v2/market/bars?timeframe&limit&before` hoặc `&from&to` | tối đa 5.000 nến/yêu cầu; trả `oldest_available`, `newest_available`, `has_more_before/after`, `data_version`; tham số xung đột, thiếu múi giờ, khoảng sai ⇒ 422 có mã lỗi; kho không có ⇒ 404 (không 503) |
| `GET /api/v2/market/quote` | FRESH / STALE / MARKET_CLOSED / UNAVAILABLE |
| `GET /api/v2/market/symbol` | thông số hợp đồng broker |
| `GET /api/v2/health` | nay có độ mới theo lịch, quote live; `GET /api/v2/state` vẫn `UNAVAILABLE` (chưa có engine) |

**Giao diện:** thanh trạng thái và dải MTF dùng độ mới theo lịch ("Thị trường ĐÓNG · nến M1 cuối cách 3 giờ" thay vì báo cũ giả).

## 3. Parity với V1

Công cụ: `scripts/parity/parity.py` (chạy bằng interpreter của V1; import V1 **chỉ để so sánh đầu ra**; không ghi vào kho). Seed cố định 20261012.

### 3.1. Bản nhanh (đã chạy, đạt)

Chạy khi V1 (`:8000`) và V2 (`:8200`) cùng chạy: **29.438 phép kiểm, 0 sai lệch**, 60 giây.

| Nhóm | Phép kiểm | Sai lệch | Nội dung |
|---|---|---|---|
| Nến: nội dung từng tệp tháng (mẫu 12 tháng/khung) | 72 | 0 | băm SHA-256 toàn bộ cột; 257.797 M1, 67.463 M5, 22.461 M15, 11.472 M30, 6.103 H1, 1.523 H4 |
| Nến: `tail(limit, before)` ngẫu nhiên | 48 | 0 | giới hạn 1…5.000 |
| Nến: cửa sổ `[start, end)` ngẫu nhiên | 48 | 0 | |
| Nến qua HTTP: V2 `/api/v2/market/bars` so với V1 `/md/XAUUSD/bars` | 24 | 0 | 6 khung × 4 cửa sổ sâu ngẫu nhiên |
| Tick: V2 `TickStore` so với V1 `TickLedger` | 21 | 0 | 1.565 ngày tick (2021-10-01…2026-10-12), 13.825 tick, so `timestamp_msc`, bid, ask |
| **Lịch thị trường** (OPEN/CLOSED/ROLLOVER) | **9.716** | 0 | thời điểm ngẫu nhiên 2004–2026 **cộng 6.716 điểm quanh mọi chuyển DST của Mỹ và EU** |
| Đồng hồ broker NY+7: UTC → giờ server | 9.716 | 0 | |
| Đồng hồ broker: giờ server → UTC (`strict=False`) | 9.716 | 0 | 36 khoảng trống/gập DST cho kết quả null giống hệt nhau |
| Thông số hợp đồng: V2 `symbol_info` so với V1 `spec_from_broker` | 10 | 0 | 10 trường |
| Cấu hình: bản sao JSON so với YAML của V1 | 7 | 0 | tham số tuần, đồng hồ, **1.307 cửa sổ đóng cửa** |
| Quote: V2 so với V1 (cùng tệp live) | 60 | 0 | bid, ask, spread (điểm), trạng thái |

### 3.2. Bản đầy đủ (đã chạy, đạt): 202.542 phép kiểm, 0 sai lệch, 335,6 s

| Nhóm | Phép kiểm | Sai lệch |
|---|---|---|
| Nến: **mọi** tệp tháng, băm toàn bộ nội dung (M1 7.065.794; M5 1.500.300; M15 515.725; M30 260.771; H1 132.255; H4 34.239 dòng) | 1.614 | 0 |
| Nến: `tail(limit, before)` ngẫu nhiên | 240 | 0 |
| Nến: cửa sổ `[start,end)` ngẫu nhiên | 240 | 0 |
| Nến qua HTTP (V2 so với V1) | 72 | 0 |
| Tick (1.565 ngày, 172.830 tick so sánh) | 151 | 0 |
| Lịch thị trường (66.716 thời điểm, gồm 6.716 quanh mọi chuyển DST) | 66.716 | 0 |
| Đồng hồ NY+7: UTC → giờ server | 66.716 | 0 |
| Đồng hồ: giờ server → UTC (42 khoảng trống/gập cho null giống hệt nhau) | 66.716 | 0 |
| Thông số hợp đồng / cấu hình / quote | 10 / 7 / 60 | 0 |

Bằng chứng: `reports/evidence/g3/parity_output.txt`, `parity_results.json`.

### 3.3. Đọc kết quả cho đúng

1. **Parity chứng minh V2 đọc và diễn giải dữ liệu giống V1; không chứng minh V1 đúng so với broker.** Mối liên hệ với sự thật broker là kiểm toán riêng của V1: `data/market/parity-audit.json` (so terminal MT5 với kho trong 14 ngày: M1 13.650/13.650 giống hệt, M5 2.730/2.730, M15 920/920, … không sai lệch) và `ledger-verification.json` (`ok: true`). Tôi **dẫn chiếu** các tệp đó, **không** tự tái kiểm với MT5 (V2 không kết nối MT5).
2. Phần **nến/tick** dùng chung tệp Parquet với V1 nên "giống hệt" là kỳ vọng; giá trị kiểm nằm ở ngữ nghĩa đọc (khoảng, phân trang, loại trùng, thứ tự) và ở việc đã viết lại độc lập.
3. Phần **lịch và đồng hồ** là logic **độc lập** (V2: Python thuần; V1: polars): 9.716 thời điểm khớp 100% kể cả mọi chuyển DST là bằng chứng mạnh nhất của G3.
4. **Tick parity chỉ ở mức đọc kho.** V2 chưa có endpoint tick (sẽ cần ở G4 cho mô hình chi phí).

## 4. Kiểm tra chất lượng

| Kiểm tra | Kết quả |
|---|---|
| `ruff` + `ruff format` | sạch |
| `mypy --strict` | không lỗi (19 file nguồn) |
| `pytest` | **84 đạt** (tăng từ 36): thời gian thị trường 17 (đồng hồ, DST gập/gập, lịch, ngày lễ, thuộc tính Hypothesis), kho nến 10 (phân trang không trùng/không hở, nửa mở, bản đầu thắng, cache, chỉ-đọc), live/tick/độ mới 8, API thị trường 10, đóng băng ML 4, cô lập V1 + không có đường gửi lệnh, hợp đồng OpenAPI đồng bộ mã và độc lập với việc đã build web |
| Playwright + axe | **17 đạt** (không đổi), console sạch |
| Chrome DevTools MCP | console không thông báo; ảnh chụp màn hình trang mới |

## 5. Độ trễ endpoint lịch sử và việc còn lại

Đo cùng phiên, cùng máy, 40 yêu cầu/trường hợp (`evidence/g3/latency_bars_g3_output.txt`). Đơn vị ms (p50 / p95):

| Trường hợp | V2 | V1 |
|---|---|---|
| M1 mới nhất, 400 nến | 8,0 / 25,1 | 11,1 / 31,7 |
| M1 mới nhất, 5.000 nến | 36,2 / 61,0 | 36,5 / 53,6 |
| H1 mới nhất, 5.000 nến | 59,7 / 84,3 | 51,7 / 91,7 |
| H4 mới nhất, 5.000 nến | 90,4 / 108,0 | 90,2 / 111,5 |
| Trang sâu 1.000 nến (năm ngẫu nhiên), M1 / H1 / H4 | 15,2 / 14,9 / 23,3 (p50) | 18,4 / 29,9 / 32,4 (p50) |
| quote | 1,4 / 17,7 | 8,6 / 32,3 |

Kết luận trung thực: **ngang V1** (khác biệt nằm trong nhiễu; một số ca 5.000 nến chậm hơn 5–15 ms ở p50, trang nhỏ/trang sâu nhanh hơn). Payload nhỏ hơn ~0,7%. Không tuyên bố nhanh hơn. Một lần chạy, 40 mẫu: ước lượng thô.

Còn lại (không thuộc G3):
- Gộp lịch sử với nến live, backfill khi kéo trái, biểu đồ, nến forming và quote qua WebSocket: **G5**.
- Mô hình chi phí (spread, trượt giá, hoa hồng, swap) và cỡ lệnh: **G4**.
- Lịch dùng cấu hình V1 (xác minh từ 2025 trở đi); giai đoạn cũ hơn là giới hạn kế thừa.
- V2 chưa có endpoint tick (chỉ parity ở mức kho).

## 6. Bước tiếp theo đề xuất

**G4: lõi quyết định** (`market_state`, cấu trúc không repaint, vòng đời 0–6, chi phí theo kỷ nguyên, hàm cỡ lệnh duy nhất, governor, Decision Governor) với **test replay xác định và so khớp golden với V1**. Cần bạn duyệt vào G4; cần bạn xác nhận phạm vi G4 gồm thêm endpoint tick nhỏ cho mô hình chi phí hay để G4 sau.
