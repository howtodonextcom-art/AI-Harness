# Prompt — Đánh giá mức hoàn thành XAU EDGE và lộ trình tiếp theo (làm / hoãn / bỏ) khai thác ECC

## ROLE
Bạn là **Principal Product & Trading-Systems Reviewer kiêm ECC Delivery Architect**. Bạn đánh giá dự án theo **mục tiêu kiếm tiền thật một cách an toàn**, không theo số tính năng; bạn dám nói "dừng làm X" khi X không đổi được kết quả; bạn biến lộ trình thành quy trình ECC chạy được ngay.

## NORTH STAR (thước đo duy nhất)
XAU EDGE là Desktop Decision Terminal XAUUSD dùng dữ liệu thật giúp human trader biết khi nào đứng ngoài / chuẩn bị / BUY-SELL thật, Entry-SL-TP, HOLD/EXIT và vì sao — và **tín hiệu đó phải có edge dương được chứng minh** trước khi dùng tiền thật (paper → demo → funded FTMO).

## CONTEXT ĐÃ BIẾT (xác minh lại, không tin mù)
- HEAD: `b57e07d` (báo cáo, CI xanh) → `3ee3990` (chỉ ghi dòng CI vào mục 26, chưa có CI riêng).
- `docs/reports/WORKSTATION_COMPLETION_FINAL.md`: verdict **FUNCTIONALLY COMPLETE — FORWARD LIVE SIGNAL OBSERVATION PENDING**; mobile **SHOULD WAIT**; ma trận 17 hàng; nhãn ĐÃ KIỂM / CHƯA KIỂM / CHƯA LÀM. CHƯA LÀM: canonical brain, adapters, indicators, BOS/CHoCH, 2-chart. Telemetry = PARTIAL.
- Cổng: ruff/format/mypy sạch; pytest not-mt5 2601 passed/1 skipped; eslint/tsc/next build sạch; Playwright mock 291, real-backend 31; `audit_bar_parity.py` 14 ngày 0 chênh lệch. `pytest -m mt5` không chạy (nối terminal thật).
- LIVE: **decision coverage 48,64% (232/477)**, news CLEAR (nguồn Forex Factory, không SLA), forward F0, chưa quan sát được tín hiệu LIVE actionable.
- Edge: strategy A −0.135R Dev (135 lệnh), −0.099R Val (63) (`docs/research/.../checkpoint-1.md`, `final-verdict.md`). Không được chỉnh v1.1/v1.2/v1.3/Test-H/holdout nếu chưa preregister.
- Tồn đọng đã biết từ các audit trước: `governor.flatten_required` không có caller; `daily_loss_guard` không bao giờ set; legacy `demo_trader.py` đọc `data/raw` (stale) → SignalBridge → executor; 2 store song song; chart chỉ 400 bar, không lazy-load, không D1/W1; ổ C: ~13 GB.
- Owner phải quyết: (Q1) nguồn tin có SLA hay giữ Forex Factory; (Q2) có bật quản lý vị thế tự động (break-even/trailing/partial) — là thay đổi ALPHA.
- ECC: upstream `affaan-m/ECC` @ `4eb71d92` (2.2.3); danh mục 590 mục ở `docs/reports/ECC_CATALOG.md` (50 Cao, 98 Trung bình); xau-edge cài profile minimal, no hooks; vòng bắt buộc `AGENTS.md:93-114`.

## OBJECTIVE
1. Chấm **mức hoàn thành thật** của dự án theo từng trụ cột, có bằng chứng.
2. Đưa ra **lộ trình** đã thống nhất trong phiên: việc **LÀM NGAY / LÀM SAU / HOÃN / BỎ**, theo thứ tự phụ thuộc, dẫn tới cổng Demo.
3. Gắn mỗi việc với **quy trình ECC cụ thể** (skill/agent/command, input → output, Gate).

## METHOD
1. **Xác minh hiện trạng**: `git log`/`gh run list` cho `3ee3990`; đọc báo cáo final, ma trận, `funded-readiness.md`, `canonical-brain.md`, `POSITION_MANAGEMENT_AUDIT.md`, `final-verdict.md`. Đo lại read-only: coverage hiện tại (API/System), news state, collector health, disk. Không tin số trong prompt nếu đo được khác.
2. **Chẩn đoán coverage 48,64%** (đọc code + dữ liệu telemetry, không sửa): phân biệt engine không step / M1 không đóng / collector lag / restart / writer conflict / kỳ vọng lịch sai / ghi file lỗi. Đây là blocker của forward evidence → phải có nguyên nhân gốc hoặc giả thuyết xếp hạng + cách xác minh.
3. **Scorecard 6 trụ cột** (0–100% + nhãn + bằng chứng): (a) Dữ liệu & feed, (b) Quyết định/Signal UI, (c) Rủi ro & guard FTMO, (d) Thực thi & kiến trúc (canonical brain), (e) Bằng chứng (telemetry, forward, edge), (f) Vận hành (news, supervisor, cảnh báo, disk, CI). Nêu rõ trụ cột nào **chặn tiền thật**.
4. **Phân loại backlog** — mọi hạng mục còn mở (từ báo cáo final, audit 20%, audit dữ liệu, ECC mapping) vào 4 rổ với tiêu chí công khai: tác động lên North Star, rủi ro mất tiền, chi phí, phụ thuộc, có phải thay đổi alpha không. Mặc định áp quan điểm đã thảo luận: **dừng mở rộng chart/drawing/indicator** (trùng MT5/TradingView), **ưu tiên coverage → forward evidence → edge program → canonical brain → guard FTMO/flatten → demo gate**.
5. **Lộ trình theo pha** (mỗi pha: mục tiêu, Definition of Done đo được, thời lượng ước tính, cổng ra), tối đa 5 pha tới **Demo Preparation Gate** (không vượt cổng).
6. **ECC playbook cho từng pha**: chọn ≤3 thành phần/việc từ `ECC_CATALOG.md` (ưu tiên đã cài), ghi cách gọi (`/plan`, `/orch-fix-defect`, `eval-harness`, `santa-method`, `council`, `intent-driven-development`, `silent-failure-hunter`, `pr-test-analyzer`, `latency-critical-systems`, `docs-governance`, `prediction-market-risk-review`, `architecture-decision-records`...), input → output, Gate A/B. Nêu rõ cái gì ECC **không** làm được ở pha đó.
7. **Khuyến nghị cho Q1/Q2** kèm lựa chọn, trade-off, và mặc định an toàn nếu owner chưa quyết.

## OUTPUT (tiếng Việt, thuật ngữ kỹ thuật giữ tiếng Anh)
Tạo **`docs/reports/PROJECT_COMPLETION_AND_ROADMAP.md`** (được phép tạo file này, không sửa file nào khác) và tóm tắt trong chat:
1. **TL;DR** (≤6 câu): % hoàn thành tổng, cái chặn tiền thật, việc số 1 tuần này.
2. **Scorecard 6 trụ cột** (bảng: trụ cột | % | nhãn | bằng chứng | chặn tiền thật?).
3. **Chẩn đoán coverage 48,64%**.
4. **Backlog 4 rổ**: LÀM NGAY / LÀM SAU / HOÃN / BỎ (mỗi mục 1 dòng lý do).
5. **Lộ trình pha** tới Demo Gate (DoD, ước tính, cổng ra).
6. **ECC playbook** theo pha (bảng: việc | ECC | cách gọi | input→output | Gate).
7. **Quyết định cần owner** (Q1, Q2 + bất kỳ quyết định mới), mỗi cái có khuyến nghị.
8. **Những điều không được làm** trong lộ trình (governance, execution flags, alpha).

## CONSTRAINTS
- Chỉ đọc. Không sửa code/tài liệu khác, không commit/push, không stash, không đụng thay đổi chưa commit của người khác.
- Không chạy collector/supervisor/bot, không gửi lệnh, không kết nối MT5, không restart stack live, không build vào `apps/dashboard/.next`, không đọc/in `.env`, số tài khoản tối đa 3 số cuối.
- Không đề xuất chỉnh threshold/alpha ngoài quy trình preregister; thay đổi guard/scope ghi "cần ADR".
- Mỗi khẳng định có file:line, số đo hôm nay, hoặc trích báo cáo (ghi ngày); điều chưa xác minh ghi "Giả thuyết – chưa xác minh".
