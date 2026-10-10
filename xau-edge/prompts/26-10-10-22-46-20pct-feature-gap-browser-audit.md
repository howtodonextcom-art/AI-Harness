# 20% feature tốt nhất thị trường vs XAU EDGE - kiểm toán sâu + kiểm thử toàn bộ sản phẩm trên trình duyệt

# VAI TRÒ
Bạn là Principal Product Engineer kiêm Trading UX Reviewer, QA Lead (exploratory + scripted browser testing) và Quant Systems
Reviewer. Bạn đã dùng thực tế TradingView, cTrader, LuxAlgo, Prime Indicator, Flux Charts, NautilusTrader, LEAN, Freqtrade,
Hummingbot, Jesse, TraderSync, TradeZella, Tradervue, Edgewonk. Bạn đánh giá theo một câu hỏi: sản phẩm có giúp human trader
quyết định BUY / SELL / WAIT / HOLD / EXIT đúng hơn, nhanh hơn, ít sai hơn, và từ đó có khả năng kiếm tiền thật hay không.

# MỤC TIÊU SẢN PHẨM (thước đo cho mọi kết luận)
"XAU EDGE là Desktop Decision Terminal chuyên XAUUSD, sử dụng dữ liệu thị trường thực để giúp human trader biết khi nào nên
đứng ngoài, khi nào chuẩn bị BUY/SELL, khi nào BUY/SELL thực sự, vào ở đâu, SL/TP ở đâu, khi nào HOLD, khi nào EXIT/chốt lời,
và tại sao."

# BỐI CẢNH ĐÃ XÁC MINH (audit 2026-10-10, HEAD b90a7e7; kiểm lại nếu HEAD đã đổi)
- Stack live: collector MT5 → data/market → API :8000 (TradeEngine 5 s, baseline v1.1.0) → PaperDesk → dashboard :3000.
- Routes: /, /trade, /market, /journal, /control, /legacy, /research (+ operations, candidates, lineage, data, evidence,
  hypotheses, forward, ledger).
- Hành động server: WAIT/BUY/SELL/HOLD/EXIT/UNAVAILABLE + bias/missing/stage (TRADE-08).
- Live: 251/251 WAIT, F0, PaperDesk 0 lệnh. Không phiên bản nào đạt docs/evals/edge-criteria.md (V1: (B) NO EDGE).
- HOLD/EXIT chỉ cho vị thế paper; break-even/trailing/thoát khi vô hiệu tắt (paper_desk.py:139-143); tin chưa rõ chỉ cảnh báo
  (api/trade.py:106); data/news rỗng. Ba decision engine, ba đường paper. CI không chạy Playwright. /control trả 503 (flag tắt).
- Sandbox có sẵn: scripts/serve_acceptance.py (replay thật qua TradeEngine/PaperDesk, ghi vào temp dir, /acceptance/* điều khiển
  thời gian replay) + apps/dashboard/playwright.acceptance.config.ts (API :8100, dashboard `next start -p 3200`
  với XAU_EDGE_API_URL=http://127.0.0.1:8100).

# NHIỆM VỤ
1. Mỗi feature trong rubric: đang ở đâu so với mức hoàn thiện (chức năng, UI, UX, màu sắc/ngữ nghĩa thị giác, dữ liệu thật)?
2. Nhiều màn hình/bảng UI có giúp quyết định BUY / SELL / chốt lời đúng điểm hơn không, hay gây nhiễu?
3. Phần nào của codebase dư thừa (không phục vụ mục tiêu, trùng lặp, mồ côi, legacy)?
4. Điều gì THỰC SỰ cản công cụ giúp kiếm tiền thật, xếp theo mức chặn?
5. Công cụ phân tích (chart intelligence, research console, replay) phục vụ quyết định hay chỉ trình diễn?
6. Kiểm thử toàn bộ sản phẩm qua trình duyệt thật bằng MCP, thực hiện MỌI thao tác người dùng có thể làm, ghi bằng chứng.

# RUBRIC CỐ ĐỊNH (chấm TRƯỚC khi kết luận, không đổi sau)
- Chart intelligence: signal markers; entry/SL/TP trên chart; support/resistance; multi-timeframe context; relative volume.
- Decision: BUY/SELL/WAIT; reasons; refusal reasons; expiry.
- Risk: position sizing; RR; SL/TP; daily risk.
- Execution: paper first; demo later; active position; auto exit.
- Feedback: alerts; journal; signal history; replay.
Mỗi feature chấm 0-3 ở 7 cột (0 không có, 1 có code, 2 đã test fake/replay, 3 chạy với dữ liệu thật/live):
BACKEND | API | UI | UX (hiểu trong 5 giây) | DỮ LIỆU THẬT | BROWSER-VERIFIED (đã thao tác thật trong trình duyệt) |
ĐÓNG GÓP VÀO QUYẾT ĐỊNH. Kèm "Chuẩn tham chiếu thị trường" (đối thủ nào làm tốt nhất, họ có gì mà XAU EDGE chưa có;
không chắc thì ghi "Giả thuyết – chưa xác minh").

# PHƯƠNG PHÁP
Bước 1 - Kiểm kê bề mặt UI từ code: mọi route/tab/panel/modal/nút trong apps/dashboard (app/, components/, lib/): route,
  component, endpoint, câu hỏi trader được phục vụ.
Bước 2 - Truy vết feature: UI → hook/fetch → endpoint → hàm backend → nguồn dữ liệu, ghi file:dòng; phân loại
  Thật / Replay / Mock / Docs-only / Thiếu.

Bước 3 - KIỂM THỬ TOÀN BỘ SẢN PHẨM BẰNG BROWSER MCP (bắt buộc, không thay bằng đọc code)
  Công cụ: cursor-ide-browser (ưu tiên) hoặc user-playwright. Ảnh lưu vào C:\Users\Kieu Oanh\.playwright-mcp\audit-20pct\
  (nhúng đường dẫn tuyệt đối trong báo cáo; không chép vào repo ở lượt này).
  3a. Môi trường LIVE (http://127.0.0.1:3000, dữ liệu thật) - mọi thao tác KHÔNG làm đổi dữ liệu server:
      - Duyệt cả 15 route; mỗi route: snapshot accessibility + screenshot 1440×900, 1920×1080, 390×844, 844×390, 720×450 (~zoom 200%),
        sáng + tối nếu có.
      - /trade: đổi mọi timeframe; crosshair; zoom/pan bằng chuột và phím; fit (F), về hiện tại, follow, fullscreen; đổi múi giờ;
        hover/focus mọi tooltip; mở popover marker; mọi tab (Thị trường, Hệ thống, Journal, Công cụ của tôi...); vẽ/xóa đường ngang;
        tạo/xóa cảnh báo giá (chỉ localStorage); bàn phím Tab/Shift+Tab/Esc; đếm ngược và tuổi dữ liệu.
      - /market, /journal, /research/*, /legacy: mọi bộ lọc, sort, phân trang, link, mở/đóng chi tiết.
      - /control: chỉ mở trang, ghi trạng thái (503/flag tắt); KHÔNG bấm nút nào.
      - Mỗi trang: đọc console errors/warnings và network requests lỗi (4xx/5xx, chậm >2 s).
  3b. Môi trường SANDBOX (replay thật, ghi vào temp dir) - cho MỌI thao tác có ghi dữ liệu:
      - Khởi động: `uv run python scripts/serve_acceptance.py --port 8100` và trong apps/dashboard
        `npx next start -p 3200 -H 127.0.0.1` với XAU_EDGE_API_URL=http://127.0.0.1:8100 (dùng build .next hiện có, KHÔNG build lại).
        Nếu build hiện có không chạy được hoặc client vẫn gọi :8000 (NEXT_PUBLIC_API_URL đóng cứng lúc build), ghi rõ giới hạn và
        chỉ dùng các thao tác đi qua proxy /api/trade.
      - Dùng /acceptance/* để đưa replay tới từng trạng thái: WAIT, BIAS MUA/BÁN, BUY READY, SELL READY, HOLD, EXIT, EXPIRED,
        INVALIDATED, UNAVAILABLE.
      - Thao tác: mở PAPER BUY và SELL (xác nhận + hủy), double-click nút mở/đóng, đổi setup khi modal đang mở, đóng tay,
        để chạm SL/TP/TIME exit, xem journal và signal history sau mỗi lệnh, tắt API sandbox ~60 s rồi bật lại (mất kết nối/nối lại).
      - /control trong sandbox: chỉ thử nếu route có mount; nếu không, ghi "không kiểm được bằng trình duyệt" và dẫn chiếu
        e2e/control.spec.ts (mock).
      - Kết thúc: dừng đúng 2 tiến trình sandbox đã khởi động, xác nhận stack live (:3000/:8000) không bị ảnh hưởng.
  3c. Ma trận thao tác: bảng route × thao tác × môi trường (LIVE/SANDBOX) × kết quả mong đợi × kết quả thực × PASS/FAIL ×
      ảnh/log. Mọi lỗi tìm thấy ghi repro từng bước.
  3d. Đánh giá thị giác: phân cấp thông tin, mật độ, ngữ nghĩa màu (đỏ/xanh/hổ phách mang mấy nghĩa), tương phản, trạng thái
      rỗng/lỗi, số click để trả lời "làm gì bây giờ", so với TradingView/cTrader/LuxAlgo cùng tình huống.

Bước 4 - Bài kiểm tra quyết định: 5 kịch bản (WAIT có thiên hướng; BUY READY; HOLD đang lời; HOLD sắp chạm SL; EXIT vừa xảy ra),
  thực hiện trong SANDBOX: đếm panel phải nhìn, thông tin thừa, thông tin thiếu để vào/thoát đúng điểm; so với đối thủ.
Bước 5 - Dư thừa: module/trang/endpoint không phục vụ mục tiêu hoặc trùng lặp; bằng chứng (import graph, số caller, test,
  lưu lượng trong browser); khuyến nghị GIỮ / GỘP / ĐÓNG BĂNG / XÓA và rủi ro.
Bước 6 - Rào cản kiếm tiền, 3 lớp: (a) Edge; (b) Quyết định (tin tức, market status, độ trễ, expiry, độ tin cậy hiển thị);
  (c) Thực thi và quản lý vị thế (vị thế thật, auto exit, daily risk). Nêu rõ: sửa hết UI mà không có edge thì kết quả là gì.
Có thể dùng subagent song song (code: Bước 1-2, 5; browser LIVE: 3a; browser SANDBOX: 3b, 4), nhưng tự kiểm lại khẳng định chính.

# RÀNG BUỘC
- Không sửa code/tài liệu, không commit, không stash, không đụng thay đổi chưa commit của người khác.
- Không kết nối MT5, không chạy collector/supervisor/bot, không gửi lệnh, không đọc/in .env, không build vào apps/dashboard/.next,
  không restart stack live.
- Trên LIVE: KHÔNG bấm mở/đóng lệnh paper, KHÔNG bấm nút nào ở /control. Mọi thao tác ghi dữ liệu chỉ làm ở SANDBOX.
- Chỉ được khởi động/dừng 2 tiến trình sandbox (:8100, :3200); không dừng tiến trình nào khác.
- Mọi khẳng định có file:dòng hoặc ảnh/log trình duyệt; không có thì ghi "Giả thuyết – chưa xác minh".
- Phân biệt: "đã có code" / "đã test fake/replay" / "đã thao tác trong trình duyệt" / "đã chạy với dữ liệu live".
- Không khẳng định edge; không đề xuất nới guard (evidence/risk/news/kill-switch/FTMO); đổi guard phải ghi "cần ADR".
- Theo hướng dẫn MCP: không lặp một thao tác thất bại quá 4 lần không có bằng chứng mới; gặp chặn thì báo cáo.
- Văn xuôi tiếng Việt, thuật ngữ kỹ thuật giữ tiếng Anh.

# ĐỊNH DẠNG ĐẦU RA
1. TL;DR 5 câu: vị trí so với "20% tốt nhất" và rào cản số 1 để kiếm tiền thật.
2. Bảng rubric 22 feature × 7 cột + tổng theo nhóm + chuẩn tham chiếu thị trường.
3. Bản đồ bề mặt UI (route/panel → câu hỏi trader → dữ liệu → GIỮ/GỘP/BỎ) + Mermaid sơ đồ điều hướng.
4. Kết quả kiểm thử trình duyệt: số route/thao tác đã chạy, PASS/FAIL, ma trận rút gọn, danh sách lỗi (HIGH/MEDIUM/LOW) kèm repro
   và ảnh; console/network errors.
5. Audit UI/UX/màu sắc: 5-8 phát hiện quan trọng nhất kèm ảnh và đề xuất cụ thể.
6. Bài kiểm tra quyết định 5 kịch bản (panel phải xem, thông tin thừa, thiếu, so với đối thủ).
7. Codebase dư thừa: module → bằng chứng → khuyến nghị → rủi ro.
8. Rào cản kiếm tiền xếp hạng theo Edge / Quyết định / Thực thi, mỗi mục có bằng chứng và "nếu không gỡ thì sao".
9. Lộ trình "ranh giới hoàn thiện": tối đa 10 việc theo ưu tiên (feature được nâng điểm, file chính, S/M/L, việc nào chỉ có giá trị
   sau khi có edge) + danh sách những gì KHÔNG nên làm tiếp.
