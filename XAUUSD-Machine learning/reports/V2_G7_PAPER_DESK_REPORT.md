# V2 G7: Paper Desk (trước G6 ML)

Ngày: 2026-10-13 · repo `xau-edge-v2` (local, chưa push) · V1 **không bị sửa**.

Quyết định đã áp dụng: G5 PASS · **không chờ BUY/SELL tự nhiên mới pass** · quan sát tín hiệu live tự nhiên là yêu cầu forward-evidence riêng · **K policy KHÓA theo họ** (`K_V2_VOL_V0 = 2` nếu chỉ Ridge/HAR + LightGBM tham gia selection trên confirmatory; không kế thừa 44; ADR-V2-007 viết lại) · bước tiếp theo G7 trước G6 · ML chưa có thẩm quyền · cấm tuning chiến lược · Demo/MT5 order chưa mở.

## 1. Đã xây

| Hạng mục | Nội dung |
|---|---|
| `core/paper.py` (thuần) | giá khớp vào (ask/bid + 3 điểm bất lợi), đánh giá nến M1 (SL/TP, SL trước khi chạm cả hai, BÁN thoát theo ask = giá + spread của nến), PnL theo `tick_size/tick_value`, swap theo số lần qua 17:00 New York ngày thường, bộ kiểm soát V1 (ngưỡng giữ nguyên) |
| `paper/store.py` | SQLite riêng (WAL, giao dịch `BEGIN IMMEDIATE`), nhật ký chỉ thêm, `setup_id` UNIQUE, equity khởi đầu ghi một lần |
| `paper/desk.py` | mở lệnh từ quyết định (tính lại rủi ro từ giá khớp), quản lý bằng nến M1 đóng sau phút vào lệnh, MAE/MFE, cắt khi lỗ ngày ≥ 3,5%, đóng tay, sổ cái (equity, lãi/lỗ nổi, hôm nay, R), bộ kiểm soát trạng thái |
| API | `GET /api/v2/paper/{summary,positions,journal}`; `POST /api/v2/paper/open-current`, `POST /api/v2/paper/positions/{id}/close` (từ chối Origin lạ, mã lỗi có tên, server tính mọi thứ); engine nền tự quản lý + tự mở (mặc định BẬT); sự kiện socket `paper`; mục `paper` trong `/health` |
| Quyết định | equity cỡ lệnh = equity của sổ; cờ cooldown/daily/risk từ bộ kiểm soát đi vào chuỗi quyết định; khi đang giữ lệnh `state = HOLD` kèm kế hoạch của lệnh và PnL nổi; bộ đệm quyết định 1 giây dùng chung |
| UI | ngăn Nhật ký: tổng hợp sổ + bộ kiểm soát + bảng lệnh (R, MAE/MFE, nguồn, nến mơ hồ) + nhật ký chỉ-thêm + nút "Mở lệnh PAPER theo kế hoạch hiện tại" (chỉ bật khi BUY/SELL) và "Đóng ngay"; chip sổ PAPER ở thanh trên; đánh dấu vào/ra và đường Entry/SL/TP của lệnh trên biểu đồ |
| ADR | ADR-V2-007 (K khóa theo họ), ADR-V2-012 (paper desk) |

## 2. Kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| `ruff`, `ruff format`, `mypy --strict` (33 file) | sạch |
| `pytest` | **1.676 đạt** (+45 test paper: 20 quy tắc, 15 desk với SQLite thật, 10 API/engine/socket) |
| Test TS đơn vị | 9 đạt (thêm đánh dấu vào/ra theo khung) |
| Playwright + axe | **29 đạt** (24 + 5 paper: sổ rỗng không mở được, bảng lệnh/R/MAE/nến mơ hồ/bộ kiểm soát + axe sạch, mở lệnh **không gửi body**, lỗi ghi hiện mã của server, server thật: paper rỗng + 403 Origin lạ) |
| Hợp đồng OpenAPI | đồng bộ; **hai** đường POST duy nhất, không PUT/PATCH/DELETE |

Test hành vi chính (đều bằng SQLite thật hoặc khởi động lại giả lập bằng cách mở lại cùng tệp): nến của chính phút vào lệnh **không bao giờ được dùng**; SL đóng kèm trượt giá và ra số PnL đúng theo `tick_size/tick_value`; TP khớp đúng mức; nến chạm cả hai → SL + cờ `ambiguous`; MAE/MFE; swap một đêm = -76,05 điểm × lô; cooldown sau lệnh thua và hết sau 40 phút; chuỗi 3 thua → nghỉ 240 phút; lỗ ngày ≥ 2% chặn lệnh mới và ≥ 3,5% cắt lệnh; một setup không mở hai lần kể cả sau khởi động lại; đổi `PAPER_EQUITY` không ghi đè equity khởi đầu; giao dịch lỗi không để lại dòng nhật ký mồ côi; `PaperDesk` không có hàm đặt lệnh.

## 3. Nghiệm thu live

Dịch vụ thật :8200 chạy bản G7 (tự động BẬT, tệp `data/paper.sqlite3` mới). `/health`: `paper: OK, tự động BẬT, 0 lệnh đang mở, engine chạy`. Phiên 90 giây (`reports/evidence/g7/`): 108 sự kiện socket (live 84, state 6, heartbeat 17), **0 khoảng hở `seq`**, 39 quote khác nhau, 6 khung đều nạp được, 0 lỗi console/HTTP, không tràn trang, hiển thị lần đầu 278 ms.

## 4. Giới hạn (nói thẳng)

- **Chưa có lệnh PAPER nào từ tín hiệu tự nhiên.** Đường mở/quản lý/đóng được kiểm bằng quyết định ép sẵn và nến tổng hợp, không bằng một BUY/SELL tự nhiên; sổ live đang rỗng. Engine đang chạy, nên khi baseline ra BUY/SELL hợp lệ (hiếm) lệnh sẽ được ghi tự động. Đây là yêu cầu forward-evidence riêng như bạn chốt.
- Khởi động lại được kiểm bằng mở lại cùng tệp SQLite, **chưa** kiểm bằng việc giết tiến trình giữa chừng một giao dịch (SQLite WAL bảo đảm nguyên tử, nhưng tôi chưa tự chứng minh).
- Mô phỏng khớp đơn giản: nến M1 (không tick), SL/TP cố định, một lệnh một lúc, TP2 chỉ hiển thị, swap/hoa hồng/trượt giá là giả định, equity 10.000 là giả định.
- Chưa có: so với mua-và-giữ, "vi phạm kỷ luật", bất đồng quy tắc-ML (ML chưa có), đọc lại swap từ terminal, báo cáo R/MAE/MFE theo thời gian.
- Số liệu sổ **không phải bằng chứng**: mẫu nhỏ, baseline là UNVALIDATED (UI nói rõ).
- `data/paper.sqlite3` nằm ngoài git (không sao lưu); mất tệp là mất sổ.

## 5. Còn nợ trước G6

1. Cơ chế sổ cái K trong mã (chính sách đã khóa, ADR-V2-007; việc ghi sổ mỗi lần nhìn confirmatory là việc của G6).
2. Danh sách ứng viên selection của `K_V2_VOL_V0` phải được ghi vào đặc tả ML V0 **trước** khi chạy confirmatory (ADR-V2-007 mục 5b); đặc tả hiện đã đóng băng, nên cần quy trình tạo phiên bản mới có băm.
3. Quan sát tín hiệu tự nhiên (song song, không chặn).

## 6. Bước tiếp theo đề xuất

Cần bạn: (a) duyệt G7 (kèm chấp nhận giới hạn "chưa có lệnh tự nhiên"); (b) xác nhận **tự động mở mặc định BẬT** (nếu muốn mặc định TẮT: đặt `XAU_V2_AUTO_PAPER=false`); (c) bước kế tiếp: **G6 ML V0** (K đã khóa) hoặc làm tiếp phần forward-evidence/báo cáo sổ trước.
