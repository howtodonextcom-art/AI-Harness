# Dữ liệu có chắp vá không? Đối chiếu biểu đồ XAU EDGE vs MT5 + ECC giúp được gì

# VAI TRÒ
Bạn là Market Data Engineer (MT5 / time-series) kiêm Trading Charting QA và ECC Workflow Architect.
Bạn hiểu MT5 (server time, bar ownership, tick volume, broker history limit), lightweight-charts, và bộ
Everything Claude Code (ECC) tại z:\Coding\Projects\AI-Harness\ECC (293 skills, 68 agents, 94 commands;
một phần đã cài vào xau-edge/.claude/ theo AGENTS.md:93-100).

# BỐI CẢNH
- Dự án: z:\Coding\Projects\AI-Harness\xau-edge. Dữ liệu: collector MT5 → data/market (bar ledger append-only M1..H4,
  tick ledger, live.json) → API /md/* → dashboard /trade và /market. Kho cũ data/raw (đọc bởi bot cũ) cũ từ 2026-10-08.
- Báo cáo đã có: docs/reports/mt5-backfill-final.md, mt5-data-parity.md, mt5-chaos-tests.md, MT5_DATA_PLATFORM.md;
  công cụ: scripts/audit_bar_parity.py, market_data_parity.py, trade_m1_parity.py, verify_market_ledger.py,
  verify_tick_ledger.py, verify_visual_parity.py, repair_changed_bars.py. DATA-01 (b90a7e7) thêm parity + deep reconcile.
- Quan sát của chủ dự án (4 ảnh, 2026-10-11 ~00:29 UTC+7, thị trường đóng cửa cuối tuần):
  (1) XAU EDGE /trade M1: 17:00-20:49 UTC, close 4195.09, ask 4195.52, spread 43.
  (2) FTMO MT5 web M1: 21:33-23:49 giờ server, bid/ask 4195.09/4195.52.
  (3) FTMO MT5 web MN: "Failed to load bars - bars max count: 9000", chỉ vẽ 2004-2017.
  (4) XAU EDGE /trade H4: dữ liệu chỉ bắt đầu từ ~đầu 08/2026, nửa trái trục trống.
  Ảnh: C:\Users\Kieu Oanh\.cursor\projects\z-Coding-Projects-AI-Harness\assets\ (4 file image-*.png mới nhất).
- Đã biết từ code: /trade tải 400 nến/timeframe (apps/dashboard/components/terminal/TerminalView.tsx:279), H1 500 (:179),
  /market 500 (MarketView.tsx:100); API cho tối đa 5000 (src/xau_edge/api/market_data.py:31); /trade không có D1/W1/MN.
- Cảm nhận của chủ dự án: "data có vẻ còn chắp vá và chưa thực sự đầy đủ".

# MỤC TIÊU
A. Xác định khách quan dữ liệu có thật sự chắp vá không, ở đâu, vì sao; tách 4 loại nguyên nhân:
   (1) giới hạn HIỂN THỊ (UI tải ít nến, thiếu timeframe, không lazy-load lịch sử);
   (2) thiếu dữ liệu LƯU TRỮ (gap trong ledger, coverage tick, timeframe chưa backfill);
   (3) giới hạn BROKER/MT5 (lịch sử FTMO, max bars, BROKER_LIMITED);
   (4) LỖI DỮ LIỆU thật (OHLC/volume/spread lệch so với MT5, timezone, bar trùng/thiếu, BAR_CHANGED, data/raw cũ).
B. So sánh dữ liệu trên biểu đồ XAU EDGE với MT5 (cùng timeframe, cùng thời điểm) ở mức từng nến.
C. ECC giúp được gì: chọn đúng skill/agent/command của ECC cho từng vấn đề tìm thấy, kèm cách dùng cụ thể trong dự án.

# PHƯƠNG PHÁP
Bước 1 - Kiểm kê coverage (chỉ đọc file): với mỗi timeframe M1, M5, M15, M30, H1, H4 trong data/market: ngày đầu, ngày cuối,
  số nến, số gap trong giờ giao dịch (dùng lịch phiên FTMO trong market_data/session*.py, calendars.py; gap cuối tuần/lễ không tính),
  gap lớn nhất, so với số nến kỳ vọng; tick coverage (coverage.json); trạng thái health/DEGRADED, số BAR_CHANGED/BAR_REPAIRED;
  so với data/raw (ngày cuối, timeframe có). Ưu tiên chạy các script verify_* có sẵn ở chế độ chỉ đọc nếu chúng không kết nối MT5.
Bước 2 - Đối chiếu XAU EDGE vs MT5:
  2a. Nguồn MT5 tham chiếu, theo thứ tự ưu tiên: (i) ảnh của chủ dự án; (ii) docs/reports/mt5-*parity* đã có;
      (iii) [CHỈ KHI CHỦ DỰ ÁN BẬT CỜ "MT5_READONLY_PROBE=yes" Ở CUỐI PROMPT] chạy scripts/audit_bar_parity.py hoặc
      market_data_parity.py ở chế độ đọc (copy_rates / symbol_info_tick, không order_check/order_send, không in số tài khoản).
  2b. Lấy nến từ API live: GET http://127.0.0.1:8000/md/XAUUSD/bars?timeframe=TF&limit=N cho các mốc trùng với ảnh
      (M1 20:30-20:49 UTC ngày 2026-10-09; H4 08-09/2026; giá cuối). So OHLC, tick volume, spread, timestamp; quy đổi rõ
      UTC ↔ giờ server (NY+7) ↔ GMT+7.
  2c. Mở dashboard bằng browser MCP (chỉ xem, không bấm mở/đóng lệnh, không bấm /control): chụp /trade và /market ở M1, M5, M15,
      H1, H4 (1440×900), thử cuộn ngược và nút "Về hiện tại", ghi số nến thực vẽ và ngày đầu tiên hiển thị.
  2d. Bảng chênh lệch: mỗi khác biệt gắn 1 trong 4 loại nguyên nhân ở Mục tiêu A.
Bước 3 - Đọc code nguyên nhân: đường tải nến của UI (lib/market.ts, TerminalView.tsx, TerminalChart.tsx), API /md (market_data.py),
  ledger tail/loader (ledger.py), backfill (history_backfill.py), collector reconcile (collector.py); ghi file:dòng.
Bước 4 - Ánh xạ ECC: đọc SKILL.md/agent .md thật (không đoán theo tên) của các ứng viên dưới đây, xác nhận cái nào đã cài trong
  xau-edge/.claude/ và cái nào chỉ có trong ECC/. Với mỗi vấn đề ở Bước 1-3, chọn tối đa 2 thành phần ECC phù hợp nhất và viết
  cách dùng cụ thể (lệnh/quy trình, input, output, cổng duyệt). Ứng viên:
  skills: eval-harness, verification-loop, python-testing, tdd-workflow, benchmark-methodology, data-throughput-accelerator,
  production-audit, browser-qa, e2e-testing, research-ops, deep-research, architecture-decision-records, delivery-gate,
  orch-fix-defect, orch-pipeline, plankton-code-quality, santa-method, council, llm-trading-agent-security, living-docs-governance;
  agents: python-reviewer, fastapi-reviewer, database-reviewer, mle-reviewer, performance-optimizer, typescript-reviewer,
  react-reviewer, architect, code-architect, pr-test-analyzer. Được phép đề xuất thành phần ECC khác nếu đọc thấy phù hợp hơn.
  Nói rõ cả những gì ECC KHÔNG giúp được (ví dụ: không tạo ra dữ liệu broker không có, không tạo edge).

# RÀNG BUỘC
- Không sửa code/tài liệu, không commit, không stash, không đụng thay đổi chưa commit của người khác.
- Không chạy collector/supervisor/bot, không gửi lệnh, không đọc/in .env, không in số tài khoản (tối đa 3 số cuối),
  không build vào apps/dashboard/.next, không restart stack live. Không kết nối MT5 trừ khi cờ MT5_READONLY_PROBE=yes.
- Script có thể ghi file: chỉ chạy nếu output trỏ được ra %TEMP%; nếu không, chỉ đọc mã và báo cáo đã có.
- Mọi khẳng định có file:dòng, số liệu đo được, hoặc ảnh; không có thì ghi "Giả thuyết – chưa xác minh".
- Phân biệt: "đo trực tiếp hôm nay" / "lấy từ báo cáo cũ (ghi ngày)" / "suy luận".
- Văn xuôi tiếng Việt, thuật ngữ kỹ thuật giữ tiếng Anh.

# ĐỊNH DẠNG ĐẦU RA
1. TL;DR 5 câu: dữ liệu có thật sự chắp vá không; nguyên nhân chính; ECC giúp được gì nhất.
2. Ma trận coverage theo timeframe (từ, đến, số nến, gap trong giờ giao dịch, gap lớn nhất, so broker limit, health) + tick coverage
   + data/raw so với data/market.
3. Bảng đối chiếu XAU EDGE vs MT5 (mốc thời gian, TF, OHLC/volume/spread hai bên, chênh lệch, loại nguyên nhân 1-4) + ảnh đặt cạnh nhau.
4. Chẩn đoán "chắp vá": danh sách vấn đề xếp theo mức ảnh hưởng tới quyết định trading, mỗi vấn đề: loại, bằng chứng, file:dòng.
5. Bảng ánh xạ ECC: vấn đề → thành phần ECC (đã cài / chỉ trong ECC/) → cách dùng cụ thể → kết quả mong đợi → cổng duyệt.
6. Những gì ECC không giải quyết được và cần làm thủ công/quyết định của chủ dự án.
7. Kế hoạch 2 tuần (tối đa 8 việc): việc, thành phần ECC dùng, file chính, cỡ S/M/L, tiêu chí nghiệm thu đo được.

# CỜ CỦA CHỦ DỰ ÁN
MT5_READONLY_PROBE=no
