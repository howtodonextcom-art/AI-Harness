# V2 · F6: replay tất định, checkpoint bền và khởi động lại (ADR-V2-020)

Ngày: 2026-10-13 · Mã: `src/xau_edge_v2/core/candidate.py` (Memory, RESTORE_PENDING), `src/xau_edge_v2/research/replay.py`, `scripts/research/cand_replay.py` · Kiểm thử: `tests/unit/test_replay.py` (10 test), `tests/unit/test_candidate.py` · Bằng chứng dữ liệu thật: `reports/evidence/replay_restart/`

## Quyết định của chủ dự án và cách thực hiện
| Quyết định (Gate B2) | Thực hiện |
|---|---|
| `planned_stop` giữ tại thời điểm setup hình thành, không trượt | không đổi trong mã; test `test_the_planned_stop_stays_where_the_setup_formed`: 150 bar armed, swing M5 dịch chuyển, **một** giá trị duy nhất |
| Checkpoint bền | `save_checkpoint`: ghi tạm → `fsync` → thay thế, giữ bản trước `.prev`; chứa hash spec, phiên bản mã, hash manifest kho dữ liệu, biến thể, chỉ số bar, bar cuối, **chuỗi hash mọi bar đã xử lý**, bộ nhớ từng biến thể, hash của chính nó |
| Replay liên tục qua ranh giới tháng | `cand_replay.py` chạy MỘT tiến trình, bộ nhớ vòng đời không bao giờ bị đặt lại ở đầu tháng; checkpoint cuối mỗi tháng. `cand_signals.py` (chia tháng) **từ chối chạy** nếu không có `--allow-chunked` |
| Restart phải giống chạy liên tục | khôi phục chỉ khi **mọi** trường và lịch sử bar khớp (spec, mã, kho dữ liệu, biến thể, vị trí bar, chuỗi hash) |
| Không khôi phục được ⇒ WAIT | khởi động **COLD**: quyết định C1 bị thay bằng WAIT (`RESTORE_PENDING`) cho tới khi điều kiện armed tắt liên tục `memory_bars + 1` = 7 bar; từ đó trạng thái bằng chạy liên tục. Biến thể không có C1 không bị ảnh hưởng. Control luôn bằng V1 |

## Bằng chứng
1. **Mô phỏng tổng hợp (3 hạt giống × 7 điểm dừng, gồm giữa lúc armed dài 120–160 bar, có bar thiếu dữ liệu, shock, đổi hướng H1):** quyết định và `StepInfo` của **cả 14 biến thể** sau khi restore từ checkpoint **bằng từng bit** với chạy liên tục.
2. **Cold:** các biến thể không C1 bằng chạy liên tục ở **mọi** bar; biến thể C1 chỉ khác trong lúc cold và khi đó luôn WAIT (bị chặn), tổng hơn 1.000 so sánh ngoài vùng cold bằng nhau.
3. **Từ chối an toàn:** 6 loại checkpoint không tin cậy (spec khác, kho dữ liệu khác, phiên bản mã khác, biến thể khác, bar không thuộc lịch sử, chuỗi hash khác), cộng hỏng hash, tệp rác, tệp không có ⇒ COLD với lý do. Một run có lịch sử dịch một bar bị từ chối.
4. **Ghi nguyên tử và giữ bản trước:** kiểm trực tiếp.
5. **Dữ liệu thật, kho sạch, 2011-03..2011-04 (14 biến thể, mọi quyết định băm):** chạy liên tục hai lần ⇒ cùng digest (`8fd7a48e5da87564…`, `aa45566287c82323…`); chạy dừng sau tháng 3, **restore** ("engine: RESTORED") rồi chạy tháng 4 ⇒ digest tháng 4 **giống hệt** (`aa45566287c82323bcf5d2d684cc97ab94cb809443b5edd9e8fbc98f8a2127e7`).
6. Chốt chặn dữ liệu: `cand_replay.py` chỉ chấp nhận tháng PASS của DEV'/VALIDATION'/RESERVED.

## Giới hạn
- Bằng chứng dữ liệu thật dùng 2 tháng (ít tín hiệu: 1 + 3); độ phủ vòng đời chủ yếu từ mô phỏng. Chưa chạy DEV' đầy đủ (≈ 4–8 giờ một lõi).
- Checkpoint hiện ở cuối mỗi tháng; restart giữa tháng phải phát lại từ checkpoint trước đó (kết quả vẫn giống). Có thể ghi dày hơn.
- Candidate **chưa** được tích hợp vào engine sống; đường restart "sống" chưa tồn tại. Khi tích hợp, cold start là mặc định an toàn.
- Chạy liên tục nghĩa là không song song hóa theo tháng; song song theo **biến thể** là khả thi nhưng không cần vì chi phí chủ yếu là dựng trạng thái thị trường.
