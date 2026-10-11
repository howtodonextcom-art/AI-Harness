# Prompt — NSSM trong phạm vi an toàn + đóng Gate A + hoàn tất bàn quyết định (không hỏi human)

## ROLE
Bạn là **Principal Architect + Windows Ops Lead + Trading Product Lead**, thực thi theo vòng ECC. Mọi việc chỉ có một câu hỏi: *human có quyết định MUA / BÁN / CHỜ / GIỮ / CHỐT / CẮT trung thực hơn sau khi xong không?*

Bạn **không dừng để hỏi**. Mọi phân nhánh đã được chốt trong mục QUYẾT ĐỊNH ĐÃ KÝ. Nếu thiếu thông tin: chọn phương án an toàn hơn, ghi giả định, làm tiếp. Không hỏi mật khẩu, không mở hộp thoại chờ người.

## NORTH STAR
XAU EDGE là Desktop XAUUSD Decision Terminal. Human trên `/trade` (5 giây, 1440×900, không cuộn) phải thấy: hành động, vì sao, Entry/SL/TP, vị thế, điều kiện tiếp, **và** mức bằng chứng (UNVALIDATED + độ phủ forward so với cổng 95% đã có). Không có edge được kiểm định thì phải nói rõ, không che.

## QUYẾT ĐỊNH ĐÃ KÝ (không hỏi lại)
1. **Q3 — sống sót tiến trình:** Task Scheduler giữ **market stack** (đã đăng ký `XAU-EDGE Market Stack`). NSSM **không** thay Task Scheduler cho collector/API/dashboard. Lý do kỹ thuật đã kiểm: MT5 là GUI, Session 0 không ổn; `install_services.ps1` dựng `xau-edge-api` trên cổng 8000 — **trùng** API live của supervisor; hai giám sát tranh nhau (`docs/operations/market-data-operations.md:18-21`).
2. **NSSM được phép cài** với phạm vi hẹp dưới đây (mục NSSM). Không `-ConfirmMode DEMO` / `FUNDED`. Không `-StartNow` cho bot. Không đọc `.env`.
3. **Gate A được duyệt** cho đúng một việc agent: **thẻ B honesty** trên sandbox `:8100/:3200`. Không contract v2, không UNKNOWN=đóng, không alert 2 phút, không giả thuyết edge mới, không nối `flatten_required`.
4. **Trần K:** giữ giá trị bảo thủ trong `ledger.md` (24). Không sửa số trên ledger (append-only, chủ mới được ký). Code/console đọc một nguồn: parser ledger. `STATE.json` / `service.py` mặc định 48 phải **theo ledger**, không ngược lại.
5. **Không gửi lệnh. Không bật DEMO/FUNDED. Không `smoke_demo_order.py`.** Bot legacy vẫn khoá.
6. Thị trường mở lại **2026-10-12 05:05 GMT+7**. Trước mốc đó được restart sandbox. **Không** restart / rebuild `.next` của stack LIVE (`:8000/:3000`) trừ khi task Task Scheduler đã chết và `status_market_stack.ps1` xác nhận — khi đó chỉ `start_market_stack.ps1`, không kill MT5.

## NSSM — phạm vi bắt buộc (toàn quyền trong khung này)
Mục tiêu thật: **không để bàn quyết định tắt vì đóng console**, không phải “có icon NSSM”.

**Làm**
1. Cài `nssm.exe` local (portable, ví dụ `xau-edge/tools/nssm/` hoặc `%LOCALAPPDATA%\xau-edge\nssm\`), không bắt buộc installer system-wide nếu portable đủ. Không ghi mật khẩu. Không `git add` binary nếu repo đã ignore; nếu chưa ignore thì thêm `tools/nssm/` vào ignore.
2. `.\scripts\install_services.ps1 -WhatIf` trước, lưu output vào `%TEMP%\xau_nssm\whatif.txt`.
3. Chỉ đăng ký dịch vụ nếu WhatIf sạch **và** không đụng cổng 8000:
   - **`-SkipApi`** bắt buộc (API live đã do supervisor + Task Scheduler).
   - **`-SkipBot`** bắt buộc ở sprint này (không có edge; Demo 7 cổng chưa đạt; `ConfirmMode` để trống vẫn là process `demo_trader.py`).
4. Nếu cả hai skip: NSSM = binary có mặt + WhatIf đã chạy + ADR-0029 bổ sung một đoạn “NSSM sẵn sàng, chưa bind API/bot”. Đó là **xong NSSM** cho sprint này.
5. Củng cố đường sống sót đang dùng: xác nhận task `XAU-EDGE Market Stack` Enabled; không mở `run_market_stack.py` từ console; nếu status stack xấu — chỉ `start_market_stack.ps1`. Không cài task thứ hai, không NSSM ôm `run_market_stack.py` (hai supervisor).

**Cấm**
- `install_services.ps1` không `-SkipApi` (giết hoặc tranh `:8000`).
- `-StartNow`, `-ConfirmMode DEMO|FUNDED`.
- Service account mới, hỏi password, LocalSystem ôm MT5.
- Gỡ Task Scheduler hiện có.
- Đọc/in `.env`, token, số tài khoản đủ.

**Nếu admin Windows chặn:** ghi BLOCKED + lệnh sẵn (không password), chuyển việc thẻ B. Không lặp, không hỏi.

## PHẠM VI CÒN LẠI CỦA PROMPT 09-15 (làm hết, theo thứ tự)
A. **Santa đóng:** chấm lại `docs/reports/CONSOLIDATION_AUDIT_AND_EDGE_PATH.md` bằng 2 reviewer độc lập (cùng rubric S1–S5). Sửa đến cả hai PASS hoặc 3 vòng thì ghi BLOCKED còn gì. Không tự duyệt.
B. **Thẻ B (một commit):** UNVALIDATED + độ phủ (so với 95% đã có) cạnh hành động; Entry/SL/TP/R:R trên fold kể cả "—"; badge `DỮ LIỆU LIVE` thay `LIVE` dễ hiểu nhầm tiền thật; pill hành động trên header khi đóng cửa. Sửa mâu thuẫn M15 vs "chưa có setup" hoặc chú thích một nguồn sự thật. **Không** redesign, không chỉ báo mới.
   - TDD: test FAIL trước. E2e Playwright trên sandbox 1440×900 + 1920×1080.
   - Không merge/build vào process LIVE.
C. **Một nguồn `k_cap` (một commit, S):** test FAIL khi `STATE.json` / console lệch ledger. Sửa reader. Không đổi số trên `ledger.md`.
D. **Cập nhật ADR-0029 + báo cáo:** Q3 = Task Scheduler (đã có) + NSSM portable sẵn, chưa bind. Không tạo ADR mới nếu 0029 đủ.
E. **Không làm:** contract v2, intent Demo, UNKNOWN=đóng, họ giả thuyết A/B/C, xoá `data/raw`, NSSM API/bot start, Telegram, nguồn tin SLA.

## CLOSED-LOOP (tương xứng)
- **S** (k_cap, docs, nssm portable): bước 7, 9–12, 1 reviewer.
- **M** (thẻ B): 2 phương án đã có (B thắng); bước 7–14 gọn; 1 reviewer mù trên ảnh sandbox; red team gọn (không execution).
- **L:** không mở trong sprint này.
- Tối đa 3 lần fix / bug. Quá → BLOCKED, việc tiếp.
- PASS thẻ B chỉ khi: bài 5 giây 12 P0 + honesty trên fold sandbox; e2e xanh; `dev.ps1 check` hoặc `pytest -m "not mt5"` + lint dashboard liên quan xanh; 1 reviewer PASS; không CRITICAL.

## CONSTRAINTS (không thương lượng, không hỏi)
- Author commit `howtodonext.com <howtodonext.com@gmail.com>` qua env, không `git config --global`. Không trailer Co-authored-by. Không push trừ khi prompt sau yêu cầu.
- Không stash. Không đụng WIP người khác.
- `pytest -m "not mt5"`. Không kết nối MT5 mới, không `verify_mt5` nếu không cần.
- Không nới evidence/risk/news/kill-switch/FTMO. Đổi guard = dừng, ghi "cần ADR", không làm.
- Mỗi khẳng định: file:line / số đo / trích báo cáo ngày. Chưa chắc: "Giả thuyết – chưa xác minh".

## OUTPUT
1. Chat: NSSM (WhatIf path, SkipApi/SkipBot, binary ở đâu, task Scheduler còn Enabled không).
2. Cập nhật §13b santa PASS/FAIL; Gate A = đã duyệt hẹp (thẻ B + k_cap).
3. Commit riêng: (i) thẻ B, (ii) k_cap reader nếu có diff.
4. Ảnh sandbox 1440 + 1920 bài 5 giây sau thẻ B.
5. Không tuyên "dự án hoàn thành / sẵn sàng tiền thật". Tuyên đúng: bàn quyết định trung thực hơn; edge vẫn UNVALIDATED.

## ĐỊNH NGHĨA XONG
Sprint xong khi: santa báo cáo PASS hoặc BLOCKED sau 3 vòng; NSSM trong phạm vi trên đã xử lý; thẻ B PASS trên sandbox; k_cap một nguồn hoặc BLOCKED có test; LIVE `:3000` không bị rebuild; 0 lệnh; 0 dịch vụ bot/API NSSM đang chạy.
