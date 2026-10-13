# V2 G2: bộ khung tối thiểu (báo cáo)

Ngày: 2026-10-12 · Thư mục: `XAUUSD-Machine learning\xau-edge-v2\` · V1 HEAD tham chiếu `daf22f6` (không bị sửa).

Quyết định của bạn đã áp dụng: **O2 có điều kiện** (cổng G2 bên dưới) · thư mục V2 · dùng chung `data/market` **chỉ đọc** · **K = 44 KHÔNG kế thừa máy móc** · được cài Vite/React/TypeScript/Playwright.

## 1. Đã xây (và chưa xây)

**Đã có (G2):** hợp đồng dữ liệu thuần (không I/O) · API REST chỉ-đọc (`/api/v2/health`, `/api/v2/state`) · WebSocket có `seq` · kho đọc **chỉ đọc** (dò độ mới 6 khung trên dữ liệu thật) · nhật ký JSON có xoay vòng · phục vụ trang tĩnh cùng gốc · một trang `/` với ngăn kéo `#journal #evidence #data #model` · kiểu TypeScript sinh từ hợp đồng · script khởi động và kiểm tra.

**Chưa có (cố ý):** bộ máy quyết định (G4) · endpoint lịch sử nến và biểu đồ (G3/G5) · ML (G6–G7) · journal thật · mọi thứ chạm đến chiến lược. Màn hình nói thẳng "KHÔNG KHẢ DỤNG, ENGINE_NOT_IMPLEMENTED"; **không có tín hiệu giả**. Ngăn kéo chưa triển khai ghi rõ "chưa triển khai".

**Quyết định K (ADR-V2-007):** V2 không đăng ký giả thuyết nào và không chạy Test-H/holdout cho đến khi bạn duyệt chính sách K. Ô ledger M-14 chuyển **BLOCKED (chờ chủ dự án)**.

## 2. Kết quả kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| `ruff check` / `ruff format` | sạch |
| `mypy --strict` | không lỗi (12 file nguồn) |
| `pytest` | **36 đạt** (unit 19 gồm 2 thuộc tính Hypothesis, API 12, hợp đồng 5) |
| Hợp đồng OpenAPI đồng bộ mã và kiểu TS | đạt (`--check`) |
| Build web (`tsc --noEmit` + Vite) | đạt |
| Playwright + axe (Chromium) | **17 đạt**: hợp đồng 5 giây, một route, placeholder trung thực, bố cục ở 6 khung (1920×1080, 1440×900, 1152×864, 960×720, 200% zoom, 390×844), lấp đầy màn hình (không vùng trống), a11y WCAG 2 A/AA (trang và ngăn kéo mở), ngăn kéo theo hash, WebSocket ngắt và kết nối lại, phát hiện lỗ hổng `seq`, lỗi API hiển thị |
| Chrome DevTools MCP | **dùng được**: console không có thông báo nào, 7 request đều 200, ảnh chụp màn hình |
| Isolation | test tự động: không import V1/reference, không có `order_send`/MetaTrader5 trong mã V2 |
| Kho dữ liệu chỉ đọc | test: đọc 3 lần, thư mục và mtime không đổi; chạy được trên kho đặt quyền chỉ đọc |

**Lỗi thật mà kiểm tra bắt được và đã sửa trong lúc làm** (để tránh tin vào kết quả quá đẹp):
1. Trang thiếu favicon ⇒ 404 trong console (test "console sạch" bắt).
2. Phục vụ tĩnh trên Windows nhận đường dẫn có `\` nên `Cache-Control` và SPA fallback sai (test bắt).
3. Hàng lưới `1fr` rơi nhầm vào dải MTF khi không có banner lỗi ⇒ vùng trống lớn ở màn hình lớn. **Test ban đầu không bắt được**; tôi thấy khi chụp bằng Chrome DevTools MCP rồi thêm test "lấp đầy màn hình".
4. Hợp đồng OpenAPI thay đổi tùy việc đã build web hay chưa (route dự phòng lọt vào hợp đồng) ⇒ `--check` bắt, đã loại khỏi schema và thêm test.
5. `uv sync` đầu tiên chạy khi chưa có mã nên cài gói rỗng; sửa bằng cài lại. TypeScript 7 làm hỏng `openapi-typescript` (không còn API compiler) ⇒ ghim TypeScript 5.9.

## 3. Cổng G2 (đã đặt trước ở `V2_ARCHITECTURE_DECISION.md`): *không tệ hơn V1*

Cùng máy, cùng phương pháp đo (Chromium headless, 1440×900, một lần tải, cache nóng, 30 giây rảnh); V1 từ `V2_PERFORMANCE_BASELINE.md`, riêng độ trễ API API đo lại cùng phiên với V2.

| Cổng | V1 | V2 (bộ khung) | Đạt? |
|---|---|---|---|
| JS truyền (nén) | 291.221 B, 13 file | **71.867 B, 1 file** | đạt |
| CSS truyền | 11.303 B | 1.397 B | đạt |
| Tổng tài nguyên tải | 38 | 6 | đạt |
| Request khi rảnh (30 s) | 40 | **4** HTTP + 6 khung WebSocket | đạt |
| Byte khi rảnh (30 s) | ~0,73 MB (ước từ payload đo riêng) | **~5,0 KB** (4.356 HTTP + 696 WS) | đạt |
| Tiến trình khi chạy | 5 Python + 1 Node | **1 Python** (+ launcher của `uv`) | đạt |
| RAM | API 188 MB + Node 29 MB | Python **86 MB** (+5 MB launcher) | đạt |
| Load / FCP / LCP | 333 / 324 / 776 ms | **56–60 / 120 / 120 ms** | đạt (ngưỡng ≤ 1,5 s) |
| Quyết định p95 (cùng phiên) | `/trade/decision` 64,8 ms | `/api/v2/state` 27,2 ms; `/health` 28,2 ms | đạt (ngưỡng ≤ 100 ms) |
| Khởi động đến phản hồi khỏe | không đo (cần khởi động lại stack sống) | ≈ **1,1 s** (5 lần: 1.075–1.123 ms, gồm `uv run`) | — |
| Console / network | — | 0 thông báo; 7/7 request 200; không 503 | đạt |
| Long task / FPS rảnh / heap / DOM | 2 (≤97 ms) / 60 / 8,9 MB / 956 | 0 / 60 / 2,8 MB / 203 | đạt |

### Đọc kết quả cho đúng (quan trọng)

1. **Cổng đạt nhưng chưa có ý nghĩa mạnh.** Bộ khung hầu như không có chức năng: `/state` trả hằng, chưa có biểu đồ, chưa có engine, chưa có ML. Mọi con số "nhẹ hơn" là **hệ quả của việc chưa làm gì**, **không phải bằng chứng V2 nhanh hơn/ổn định hơn** (mục 100 của đặc tả). Ví dụ, 5 KB khi rảnh sẽ tăng khi có nến live và quyết định thật.
2. **Điều có giá trị thực:** nền kiến trúc chạy được: **một tiến trình, một cổng, WebSocket có `seq`, không Node khi chạy, bundle 72 KB nén**; và ngân sách để giữ: V2 không được vượt V1 ở bundle (291.221 B), byte khi rảnh, số tiến trình, RAM, độ trễ khi thêm tính năng.
3. **Điều kiện của ADR-V2-002 được xác nhận tạm thời cho bộ khung.** **Phải đo lại ở G5 (UI đầy đủ) và G8 (soak)** với cùng workload; thua cổng nào thì quay lại O1.
4. Số khởi động của V1 không đo; không so sánh.

## 4. Kích thước mã V2 (theo dõi, mục 57)

| Loại | Dòng |
|---|---|
| Python runtime (`src`) | 673 |
| Python test | 402 |
| Web (ts/tsx/css, không gồm file sinh) | 565 |
| File sinh tự động (`schema.d.ts`) | 339 |
| Web e2e | 175 |

(V1 để so: runtime ~21,8k Python + ~13,5k TS. Chưa có ý nghĩa vì V2 chưa có chức năng.)

## 5. Giới hạn và điều tôi không chắc

- Một lần đo cho UI, cache nóng, Chromium headless trên cùng máy chạy MT5/collector/V1; chưa đo FPS khi kéo (chưa có biểu đồ), soak, MT5 rớt, khôi phục dữ liệu cũ (G8).
- Độ mới dữ liệu **chưa tính lịch nghỉ thị trường** (`calendar_aware: false`): cuối tuần sẽ hiện "cũ"; G3 sẽ dùng lịch (đã ghi trong hợp đồng và UI).
- Cổng WebSocket chỉ kiểm tra `Origin` nội bộ; chưa có xác thực (chỉ lắng nghe `127.0.0.1`).
- Playwright MCP vẫn lỗi trình duyệt ở phiên này; tôi dùng Playwright của dự án V2 (test) và Chrome DevTools MCP (kiểm tra thủ công).
- Test e2e chạy trên kho dữ liệu thật (chỉ đọc); khẳng định về dữ liệu chỉ ở mức chung ("Nến M1 …"), không phụ thuộc giá trị cụ thể.
- Tôi chưa commit/push; V2 chưa là git repo riêng (chưa hỏi).

## 6. Bước tiếp theo đề xuất (chờ bạn duyệt)

**G3: dữ liệu.** Endpoint `/api/v2/market/bars` theo khoảng/`before` (đọc kho chỉ đọc), kiểm tra parity với V1 (nến, spread, thông số hợp đồng, đồng hồ broker NY+7), lịch thị trường cho độ mới. Cần quyết định: (a) bạn đồng ý G3 bắt đầu ngay; (b) chính sách K (ADR-V2-007) chưa cần cho G3–G5, chỉ cần trước G6; (c) có muốn khởi tạo `git init` cho `xau-edge-v2`?
