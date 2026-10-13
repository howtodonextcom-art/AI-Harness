# V2 G4.1 và G5: mở rộng phủ nhánh quyết định, biểu đồ và giao diện quyết định

Ngày: 2026-10-13 · repo `xau-edge-v2` (local, chưa push) · V1 **không bị sửa**.

Quyết định đã áp dụng: G4 PASS · G5 duyệt · parity MUA/BÁN "đủ để đi tiếp" nhưng cần **G4.1** (đã làm) · collector offline không chặn việc viết mã, chỉ chặn nghiệm thu live cuối G5 · ML chưa bắt đầu · K phải khóa trước G6 · cấm đổi chiến lược · V1 chỉ đọc.

## 1. G4.1: phủ nhánh bằng trạng thái tổng hợp (`scripts/parity/golden_synthetic.py`)

Vấn đề: trên nến thật, MUA/BÁN rất hiếm nên đường kế hoạch (SL/TP/cỡ lệnh/chi phí) được kiểm mỏng. Cách làm: **sinh chính trạng thái thị trường** (hạt giống cố định, từng trường, phần lớn nhất quán với hướng đã chọn, kèm nhiễu có chủ đích để chạm mọi từ chối), đưa cùng giá trị vào `MarketState` của V1 và V2, so hai hàm `decide`. Không dùng nến, không cửa sổ dữ liệu, không đo hiệu suất.

| Kết quả (150.000 ca) | |
|---|---|
| Phép kiểm | **1.421.036, 0 sai lệch, chênh tuyệt đối lớn nhất 0,0** |
| Quyết định MUA / BÁN / CHỜ | **2.587 / 2.487 / 144.926** (so với 53 ở lần chạy nến thật) |
| Mức sẵn sàng 0..6 | 12.118 / 49.383 / 15.965 / 13.094 / 30.951 / 23.415 / 5.074 |
| Mã từ chối chạm tới | **tất cả 21** (mỗi mã từ 952 lần trở lên); script **thất bại** nếu một nhánh bắt buộc không tới được |
| Biến thể kế hoạch | STRONG và ACCEPTABLE; SL hybrid; TP bị cấu trúc chặn và không chặn; có và không có TP2; có lô (equity hợp lệ) và không equity |
| Bất biến mới | READY (6) khi và chỉ khi BUY/SELL; cổng cứng không bao giờ cho mức > 5: 150.000/150.000 |
| Tham số ngẫu nhiên | spec broker (tick size/value, bước lot, min/max, stops level), equity (gồm âm, NaN, quá nhỏ), quote có/không, cờ cổng, tin, `risk_pct`, `min_clear_atr`, chặn M1 vắng |

Đóng băng: `tests/golden/core_golden_synthetic.json` (976 ca, tối đa 40 ca cho mỗi nhánh). Tổng fixture golden: 1.493 ca (hơn 100 ca MUA/BÁN), pytest xác nhận cả **tập mã từ chối đầy đủ** có trong fixture. Bằng chứng: `reports/evidence/g41/`.

Giới hạn: đây là phủ **nhánh và số học**, không phủ phân phối thị trường thật; trạng thái sinh ra không thay thế kiểm chứng trên nến thật (lần chạy G4 vẫn là bằng chứng cho phần đó). Lõi `structure.py` được sửa một chi tiết (bỏ cảnh báo "All-NaN" bằng cách không đưa hàng rỗng vào `nanmedian`, thay vì tắt cảnh báo vốn không an toàn đa luồng); parity chạy lại sau sửa: 14.538 phép kiểm nhanh, 0 sai lệch, và toàn bộ test đạt.

## 2. G5: những gì đã xây

| Hạng mục | Nội dung |
|---|---|
| Biểu đồ | nến + khối lượng tick (Lightweight Charts 5.2.1, ghim phiên bản), 6 khung M1…H4, đường Entry/SL/TP1/TP2 khi có kế hoạch, dải thiên hướng + mức 0..6 + bid/ask trên đầu biểu đồ, giờ UTC, trạng thái/lỗi bằng chữ (`aria-live`) |
| Lịch sử | 500 nến đầu; kéo trái gọi `before=` + 1000 nến, tới **hết kho**; không còn trần 400 nến; hợp nhất không trùng; giữ vùng nhìn khi chèn nến cũ; phản hồi của khung đã rời đi bị loại |
| Nến live | từ `live.json` qua `GET /api/v2/market/forming` và sự kiện socket `live`; nến đã đóng luôn thắng nến forming (mối nối không trùng); khi có nến lưu mới (`data_version` đổi) chỉ hợp nhất 10 nến mới nhất |
| Socket | `hello`/`live`/`state`/`heartbeat`, `seq` tăng 1 cho mọi loại; `state` chỉ báo "quyết định đã đổi" (dấu vân tay bỏ `generated_at` và `decision_id`) |
| Quyết định | hàng Entry/SL/TP1/TP2 + R/R ròng, chi phí (USD/vòng + nhãn GIẢ ĐỊNH), cảnh báo, hạn hiệu lực, chuỗi lý do (gập), thang 0..6 gọn + nhãn mức hiện tại |
| Khung thời gian | 6 ô: vai trò + phán quyết từng khung (H4 chặn, H1 hướng duy nhất, M30 hiển thị, M15 setup, M5 trigger, M1 chặn) + độ mới |
| Bố cục | một màn hình từ 1152 px; thẻ quyết định cuộn bên trong thay vì đẩy trang; từ 860 px trở xuống thẻ quyết định lên trước biểu đồ |

ADR-V2-011; hợp đồng `2.0.0-g5`.

## 3. Kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| `ruff`, `ruff format`, `mypy --strict` (28 file) | sạch |
| `pytest` | **1.631 đạt** (G4: 650; thêm 976 ca synthetic + test forming/socket/tick/hợp đồng) |
| Hợp đồng OpenAPI + kiểu TS | đồng bộ (`export_openapi.py --check`) |
| Test đơn vị TS (`node --test`, `bars.test.ts`) | 7 đạt: hợp nhất không trùng/không hở, bản mới ghi đè, bất biến, `withForming`, ngưỡng nạp thêm |
| Playwright + axe | **24 đạt** (17 cũ + 7 biểu đồ: trang đầu 500 nến; kéo trái tới hết kho 2.300 nến mỗi nến đúng một lần và mỗi `before` đúng bằng nến cũ nhất đã có; đổi khung với phản hồi chậm không thắng; cả 6 khung; lỗi API hiện rõ; nến mới chỉ hợp nhất 10 nến; quote live lên đầu biểu đồ) |
| Chrome DevTools MCP | console sạch sau khi sửa một lỗi tôi gây ra: `series.update` với nến cũ hơn nến cuối (phát hiện khi xem thật, đã sửa) |

## 4. Nghiệm thu live (collector đã chạy lại)

`apps/web/scripts/live_acceptance.mjs` chạy trên dịch vụ thật :8200 trong 120 giây (bằng chứng `reports/evidence/g5/live_acceptance.json` và `.png`):

| Chỉ số | Kết quả |
|---|---|
| Hiển thị lần đầu có nến | 312 ms |
| Sự kiện socket | 134 (hello 1, **live 108**, heartbeat 23, state 2), **0 khoảng hở `seq`** |
| Quote khác nhau quan sát được trên biểu đồ | 46 |
| Bấm lần lượt 6 khung | mỗi khung 500 nến |
| Lỗi console / HTTP ≥ 400 / request hỏng | **0** |
| Tràn trang | 0 px |
| Gọi API trong 2 phút | state 12, health 12, forming 12, bars 9 |

Giới hạn của nghiệm thu: một phiên 2 phút, một trình duyệt (Chromium). Quyết định trong phiên chỉ là CHỜ nên **chưa thấy một MUA/BÁN thật với đường Entry/SL/TP trên biểu đồ**; phần đường giá mới được kiểm bằng kiểu và dựng thủ công, chưa bằng hình ảnh sống. Chưa kiểm cảnh nến đóng giữa phiên theo dõi dài (nối forming → đóng) ngoài test mô phỏng; chưa soak nhiều giờ; chưa đo bộ nhớ trình duyệt.

## 5. Còn lại / không làm trong G5

- Marker lệnh PAPER và vị thế đang mở: cần paper desk (G7).
- Tô vùng phiên (Á/Âu/Mỹ): chưa làm (hạng mục nhỏ).
- Bundle JS 126 KB gzip (G2: 73 KB); thư viện biểu đồ chiếm phần lớn.
- Chính sách K chưa khóa (ADR-V2-007), cần trước G6. ML chưa bắt đầu.

## 6. Bước tiếp theo đề xuất

Cần bạn: (a) duyệt G5 và cho biết có chờ quan sát một MUA/BÁN thật hay chấp nhận như hiện tại; (b) khóa chính sách K; (c) chọn sau G5: **G6 ML V0** (task biên độ đã đóng băng, cần K) hoặc **G7 paper desk** (vị thế, sổ lệnh, marker; không cần ML).
