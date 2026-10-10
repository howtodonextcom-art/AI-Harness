# Independent audit + news wiring + docs rewrite (2026-10-10 18:11)

Trạng thái: đã duyệt (OK) 2026-10-10.

```text
# VAI TRÒ
Bạn là Independent Technical Auditor kiêm Senior Python Engineer và QA kiểu "human tester".
Nguyên tắc: CODE VÀ QUAN SÁT TRỰC TIẾP LÀ NGUỒN SỰ THẬT; markdown, tên commit và báo cáo tự viết
chỉ là đầu mối cần kiểm chứng.

# BỐI CẢNH
- Repo: `z:\Coding\Projects\AI-Harness\xau-edge` (Windows, PowerShell, Python/uv, FastAPI, Next.js).
- Stack LIVE đang chạy dưới supervisor (Task Scheduler "XAU-EDGE Market Stack"): collector MT5
  FTMO DEMO (chỉ đọc), API 127.0.0.1:8000 (có TradeEngine chạy trong tiến trình), dashboard
  127.0.0.1:3000 (`next start` từ `apps/dashboard/.next`).
- Kiểm toán ngày 2026-10-10 (HEAD `e7aeddb`) đã phát hiện:
  - TradeEngine KHÔNG nhận lịch tin: `news_calendar_path` không được truyền vào
    (`src/xau_edge/trading/engine.py:77, 232`; `src/xau_edge/api/trade.py:90-103` không truyền;
    không chỗ nào đọc `Settings.news_calendar_path` cho TradeEngine), nên `/trade` luôn báo
    tin tức UNKNOWN dù đã cấu hình `XAU_EDGE_NEWS_CALENDAR_PATH`.
  - Có hai engine quyết định (TradeEngine trên `data/market` và `signals.engine` legacy trên
    `data/raw`); đường demo execution chỉ nối với engine cũ.
  - `CLAUDE.md` và `docs/diagrams/end-to-end-flow.md` mô tả hệ thống ngày 08/10, đã lỗi thời.
  - Working tree có thay đổi TRADE-08 CHƯA COMMIT trong `apps/dashboard/**`, một số
    `docs/reports/**` và `prompts/26-10-08-22-13-web-control-plane.md`: KHÔNG được sửa, stage
    hay commit các file đó.
- MCP trình duyệt có sẵn: `cursor-ide-browser` và `user-playwright` (đọc schema bằng
  GetDynamicTools trước khi dùng). Không cần cài thêm. Nếu cả hai không dùng được thì báo blocker,
  KHÔNG tự cài phần mềm hệ thống.

# PHẦN A: KIỂM CHỨNG TỪ CODE (chỉ đọc)
Lập "fact sheet" nội bộ, mỗi dòng có file:dòng, cho các câu hỏi:
1. Các process đang chạy và entry point (`scripts/run_market_stack.py`, `ops/supervisor.py`,
   `scripts/serve_api.py`, collector, dashboard).
2. Luồng dữ liệu MT5 → ledger → TradeEngine → PaperDesk → API → UI; luồng legacy
   `data/raw` → `signals.engine` → `demo_trader.py` → executor; luồng `/control`, funded.
3. Baseline nào đang chạy và vì sao (`trading/baseline.py`, `api/trade.py`, env
   `XAU_EDGE_BASELINE_VERSION`); trạng thái evidence (`validated_edge`).
4. Các route API thật sự tồn tại (quét route table bằng code, không đọc từ docs), route nào ghi.
5. Các cổng fail-closed còn hiệu lực và chỗ nào đi vòng (ví dụ `allow_unknown_news=True`,
   `market_open` coi UNKNOWN là mở).
6. Module mồ côi, trùng lặp, file lớn (dùng grep import và đếm dòng).
Với mỗi tuyên bố lớn trong `README.md`, `AGENTS.md`, `CLAUDE.md`, `docs/architecture/*`,
`docs/reports/TRADING_DESK_FINAL_COMPLETION.md`: đánh dấu ĐÚNG / SAI / LỖI THỜI / KHÔNG KIỂM ĐƯỢC.

# PHẦN B: SỬA LỖI LỊCH TIN TRONG TRADEENGINE (TDD)
1. Viết test FAIL trước, chứng minh:
   - Khi `Settings.news_calendar_path` trỏ tới một lịch hợp lệ có sự kiện mạnh đang trong
     cửa sổ chặn, quyết định của TradeEngine phản ánh lịch đó (không còn UNKNOWN).
   - Khi lịch hết coverage hoặc không đọc được thì vẫn fail-closed hoặc cảnh báo đúng như chính
     sách hiện hành (đọc kỹ `allow_unknown_news` và `news/*`, KHÔNG đổi chính sách).
   - Khi không cấu hình lịch, hành vi giữ nguyên như hiện tại (không regression).
2. Sửa tối thiểu: truyền `news_calendar_path` từ `Settings` qua `build_trade_engine`
   (`api/trade.py`) vào `TradeEngine`, tôn trọng định dạng point-in-time (`available_at`) có sẵn.
3. Kiểm tra cả các entry point khác dựng TradeEngine (acceptance replay, scripts) để hành vi
   nhất quán; replay không được đọc lịch tương lai (không look-ahead).
4. Không nới bất kỳ gate nào. Nếu phát hiện chính sách tin tức cần thay đổi, CHỈ đề xuất.
5. Cập nhật tài liệu vận hành nói về `XAU_EDGE_NEWS_CALENDAR_PATH` cho đúng.
6. Xác minh end-to-end KHÔNG đụng stack live: chạy một API phụ ở cổng khác (ví dụ 8010) với một
   lịch tin giả trong thư mục tạm và namespace dữ liệu trade tạm, gọi `GET /trade/decision`.
7. KHÔNG khởi động lại supervisor/stack live. Ghi lệnh để chủ dự án tự restart API.

# PHẦN C: ĐÁNH GIÁ ĐỘC LẬP BẰNG TRÌNH DUYỆT (như người dùng thật)
1. Mở `http://127.0.0.1:3000` bằng MCP trình duyệt; click, cuộn, hover, phím tắt, popover/modal,
   timeframe, "Go to latest", fullscreen, sáng/tối.
2. Viewport 1920x1080, 1440x900, 390x844, 844x390 và zoom 200%.
3. Mọi trang: `/trade`, `/journal`, `/market`, `/research`, `/legacy`, `/control`.
4. Đối chiếu UI với API (`/trade/decision`, `/md/status`, `/md/quote/XAUUSD`).
5. Kiểm tra trung thực: UI có ngụ ý edge/lợi nhuận không; trạng thái lỗi hiển thị thế nào.
6. Console và network.
7. Ảnh bằng chứng: `docs/reports/img/audit-2026-10-10/`.

LUẬT AN TOÀN TRÌNH DUYỆT: CẤM bấm mở/đóng/xác nhận lệnh paper, mọi POST `/trade/paper/*`,
`/paper/orders`, mọi nút trong `/control`. Modal xác nhận chỉ mở rồi Hủy/Esc. Không nhập mật khẩu.

# PHẦN D: VIẾT LẠI TÀI LIỆU THEO BẢN CHẤT MÃ NGUỒN
1. `CLAUDE.md`: viết lại hoàn toàn, mỗi khẳng định có đường dẫn file.
2. `docs/diagrams/end-to-end-flow.md`: 3 sơ đồ Mermaid + bảng trạng thái file:dòng.
3. Liệt kê tài liệu khác còn lỗi thời trong báo cáo.

# RÀNG BUỘC CHUNG
- Không gửi lệnh, không kết nối MT5 (pytest `-m "not mt5"`), không bật cờ demo/funded, không đọc `.env`.
- Không restart stack live, không build lại `apps/dashboard/.next` tại chỗ.
- Không sửa/stage/commit file TRADE-08 chưa commit.
- Gate: ruff check, ruff format --check, mypy, pytest -m "not mt5".
- Commit nhỏ với danh tính howtodonext.com <howtodonext.com@gmail.com> qua biến môi trường;
  không trailer Co-authored-by; KHÔNG push.

# BÁO CÁO CUỐI (tiếng Việt)
Tóm tắt; Phần B; Phần C (bảng phát hiện + ảnh); Phần A (bảng tuyên bố docs); gate + commit; đề xuất.
```
