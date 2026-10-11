# ADR-0030 (NHÁP): Chốt trần K trước mọi giả thuyết mới; luật nhận họ giả thuyết V3; luật chi tiêu Test-H/Holdout

Status: **draft** (2026-10-11), cần chủ dự án ký (append-only vào `docs/research/edge-program-v2/ledger.md`). Nguồn: báo cáo consolidation §6, quyết định (e).

## Bối cảnh (đã kiểm)
- Mâu thuẫn trần K: `docs/research/edge-program-v2/ledger.md:7` ghi "trần K cap = 24"; `STATE.json:3` ghi `"k_cap": 48`, và Research Console hiển thị 20/48. Văn bản D-1 (2026-10-09) ghi "≤ 48 variants". `STATE.json` tự nói ledger là nguồn sự thật.
- K_V2 = 20 đã dùng (Batch A, H07–H10, 0/20 qua Stage 1). Ngân sách giả thuyết V2: 8, đã dùng 4. Stage 2/Test-H dùng K_tổng = K_V2 + 21 (ledger, quy tắc bảo thủ).
- Chẩn đoán Dev 2026-10-11 (Class D, không tính K): Baseline A gross −0,054R [−0,28; +0,18], frictionless −0,078R. Exit give-back khớp random walk. Không họ nào trong entry geometry / session-cost / exit efficiency đủ bằng chứng (2 reviewer mù đồng thuận).
- Test-H (2022-01..2025-04) chỉ đủ H1; M15 từ 2022-07; không có M5 trước 2025-05. Holdout 2026-05-01..2026-10-07 chưa chạm.

## Quyết định
1. **Trước mọi đăng ký mới**, chủ dự án ghi một dòng append-only, có ngày và chữ ký, vào `ledger.md` chốt trần K của V2. Cho tới lúc đó áp **giá trị bảo thủ hơn (24)**. `STATE.json` và console phải đọc trần từ ledger (một nguồn) và báo lỗi nếu lệch.
2. **Không giữ họ giả thuyết nào** từ chẩn đoán Dev (entry geometry, session-cost, exit efficiency).
3. **Luật nhận họ giả thuyết V3:** chỉ nhận khi đủ cả năm điều kiện:
   - (a) có cơ chế kinh tế nằm ngoài 10 họ đã thử (V1 sáu họ + V2 H07–H10);
   - (b) được viết và review độc lập **trước** khi xem bất kỳ kết quả nào, và khai báo mọi kết quả đã từng thấy;
   - (c) diễn đạt được trên dữ liệu Test-H thực có (H1; M15 từ 2022-07);
   - (d) có kiểm tra power: không underpowered-by-design tại K khai báo;
   - (e) có reviewer có tên (agent `mle-reviewer` + một người/agent thứ hai).
4. **Luật chi tiêu:**
   - Test-H có tổng số lần nhìn khai báo trước.
   - Holdout chỉ được dùng **một lần** để xác nhận cuối cho đúng một ứng viên đã qua Test-H.
   - Đổi phân vùng dữ liệu phải là quyết định có phiên bản, ra **trước** khi chạy.
5. **Forward PAPER** được đăng ký là `PROSPECTIVE`, có horizon và quy tắc dừng khai báo trước. Độ phủ ≥ 95% chỉ chứng minh hệ thống chạy đúng, **không phải** bằng chứng edge.
6. Nguồn cơ chế gợi ý (chưa phải giả thuyết): phản ứng sau sự kiện/tin vĩ mô, liên thị trường (lợi suất thực, DXY), cấu trúc theo lịch (rollover, fix). Mỗi cơ chế phải qua luật ở mục 3.

## Acceptance criteria
- AC-E1 **Must:** test so sánh trần K giữa `ledger.md` và `STATE.json`/console, FAIL khi lệch.
- AC-E2 **Must:** template preregistration V3 có đủ năm trường (a)–(e) và ô "kết quả đã thấy".
- AC-E3 **Must not:** chạy bất kỳ biến thể nào trên Test-H/Holdout khi chưa có dòng ledger ở mục 1.
- AC-E4 **Must not:** đề xuất ngưỡng từ dữ liệu Dev đã burned.
