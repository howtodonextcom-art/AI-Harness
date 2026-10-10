# Hướng dẫn dùng terminal PAPER hằng ngày (không cần Python hay log)

Terminal chỉ là **PAPER** (giả lập). Nó không gửi lệnh nào tới MT5, DEMO luôn KHÓA, và nó **không chứng minh có lợi thế**. Mọi con số là mô phỏng để theo dõi quy trình.

Mở trình duyệt: `http://127.0.0.1:3000/trade`. Nếu trang không mở được, khởi động stack bằng `scripts\start_market_stack.ps1 -Dashboard` (xem `docs/OPERATIONAL_BASELINE.md`).

## Cách đọc màn hình

1. **Thanh thị trường (trên cùng)**: XAUUSD, nhãn `LIVE` (hoặc `REPLAY · NOT LIVE`), thị trường MỞ/ĐÓNG, giá **Bid** thật lớn, Ask và spread; thay đổi trong ngày (so với đóng cửa hôm trước), cao/thấp/biên ngày; phiên hiện tại (Á/Âu/Mỹ/chồng phiên, tự đúng giờ mùa hè), **đồng hồ giờ Việt Nam**, và **đếm ngược nến** của khung đang xem (theo giờ máy chủ, không lệch theo đồng hồ máy bạn). Chọn múi giờ khác ở ô bên cạnh đồng hồ.
2. **Biểu đồ (giữa trái)**: nến, tick volume, đường Entry/SL/TP, mũi tên MUA/BÁN, dấu thoát lệnh, lệnh paper đang mở. Phía trên: các khung M1–H4, `⤢` vừa khung, `⇥` về nến mới nhất, **Theo nến** BẬT/TẮT, `⛶` toàn màn hình, **Đo**, **Đường ngang**, **Cảnh báo giá**, **Lớp phủ**, `⌨` phím tắt. Rê chuột để xem O/H/L/C, thay đổi, biên và volume của nến đó; bấm vào nến có mũi tên để xem chi tiết tín hiệu. Khi bạn kéo biểu đồ về quá khứ, nó **không tự nhảy về** khi có nến mới; bấm "Về hiện tại" để quay lại.
3. **Dải đa khung (dưới biểu đồ)**: H4 · H1 · M30 · M15 · M5 · M1 với trạng thái ngắn; bấm một ô để đổi khung biểu đồ.
4. **Quyết định (cột phải)**: trạng thái lớn do **máy chủ** tính, luôn có biểu tượng + chữ (không chỉ màu).

| Trạng thái | Ý nghĩa | Làm gì |
|---|---|---|
| `CHỜ` | Bộ máy đã đánh giá và chưa có lệnh | Đọc tiến trình các bước, "Đang chờ" và "Đang bị chặn bởi". Mô tả trạng thái, không phải dự báo |
| `SETUP ĐANG HÌNH THÀNH` | Có setup đang tạo, chưa kích hoạt | Chờ |
| `SẴN SÀNG MUA` / `SẴN SÀNG BÁN` | Kế hoạch đầy đủ, còn hiệu lực (đếm ngược) | Xem vé lệnh; có thể mở lệnh paper |
| `ĐANG CÓ VỊ THẾ PAPER` | Đang có lệnh paper | Theo dõi bảng vị thế |
| `VỪA THOÁT LỆNH` | Vừa thoát lệnh paper | Xem tab Hoạt động / Journal |
| `HẾT HẠN` | Kế hoạch hết hạn | Không mở được; chờ setup mới |
| `DỮ LIỆU CŨ` | Dữ liệu không tin được | Không có kế hoạch; kiểm tra stack. **Không phải CHỜ** |
| `KHÔNG THỂ TÍNH` | Bộ máy không tính được (thiếu spec, mất collector, hai tiến trình ghi, bàn paper lỗi...) | Đọc câu giải thích đỏ. **Không phải CHỜ** |
| `THỊ TRƯỜNG ĐÓNG CỬA` | Thị trường nghỉ | Không có quyết định; giá hiển thị là giá đóng cửa gần nhất |

Nếu cả trang báo **Không kết nối được API** thì mọi thứ hiển thị có thể đã cũ và không được vào lệnh.

## Các tình huống

**A. Thấy CHỜ.** Không cần làm gì. Bấm một bước trong tiến trình (Thị trường & dữ liệu → Spread & chế độ H4 → Hướng H1 → H4/M15 → Setup M15 → Kích hoạt M5 → Thực thi M1 → Kế hoạch) để biểu đồ chuyển sang khung của bước đó. Setup của baseline rất hiếm (khoảng 0,1–0,25 setup/ngày), nên CHỜ cả ngày là bình thường. Không có setup vẫn có **Máy tính lệnh** (nhập entry, SL, rủi ro để biết lot): ghi rõ "CHỈ LÀ MÁY TÍNH — KHÔNG PHẢI TÍN HIỆU".

**B. Thấy SẴN SÀNG MUA.** Vé lệnh hiện Entry (thị trường), SL, TP, TP2, R/R sau spread (kèm thước R/R), rủi ro % và tiền, lot, lãi nếu chạm TP, điều kiện vô hiệu. Chọn rủi ro 0,10 / 0,25 (mặc định) / 0,50 %. Đồng hồ "còn hiệu lực" cho biết còn bao lâu. Một cảnh báo "setup" được gửi **một lần** cho mỗi setup (Telegram nếu cấu hình, nếu không ghi file).

**C. Thấy SẴN SÀNG BÁN.** Giống B, hướng ngược lại (▼, màu đỏ).

**D. Mở lệnh PAPER.** Bấm "Mở lệnh PAPER MUA/BÁN" → hộp xác nhận hiện đủ hướng, entry, SL, TP, R/R, rủi ro, lot → "XÁC NHẬN MỞ LỆNH PAPER". Hộp xác nhận gắn với đúng setup, SL, TP và mức rủi ro bạn đã xem; nếu kế hoạch đổi hoặc hết hạn trong lúc hộp mở, nó báo "Kế hoạch đã thay đổi" và không cho xác nhận. Máy chủ còn tự kiểm lại mọi điều kiện. Nút bị khóa/ẩn khi: kế hoạch chưa đủ, hết hạn, dữ liệu cũ, đang có lệnh, nghỉ sau lệnh trước, giới hạn ngày, gần giờ thị trường đóng cửa (`CLOSURE_NEAR`), bàn paper lỗi (`PAPER_STATE_ERROR`), hoặc có tiến trình khác đang giữ quyền ghi.

**E. Theo dõi.** Cột phải chuyển sang **bảng vị thế**: lãi/lỗ tạm tính (lớn), R hiện tại, giá vào (khớp) và giá kế hoạch, giá hiện tại, SL/TP, lot, thời gian giữ, MFE/MAE. Biểu đồ vẽ PAPER ENTRY/SL/TP và NOW.

**F. Thoát lệnh.** Tự động khi chạm SL, TP hoặc hết thời gian giữ (TIME_EXIT); hoặc bấm "Đóng lệnh paper…" → hộp xác nhận cho thấy giá thực thi mới nhất, lãi/lỗ và R ước tính, mã lệnh → "XÁC NHẬN ĐÓNG" (máy chủ đọc lại giá lúc đóng và chỉ đóng một lần).

**G. Xem lại.** Tab **Hoạt động** gộp tín hiệu, lệnh paper và cảnh báo theo thời gian (bấm một dòng để biểu đồ nhảy tới đó). Tab **Vị thế** liệt kê lệnh đã đóng. Trang **Journal** liệt kê từng lệnh (setup, hướng, giờ mở, vào/thoát, SL/TP, lot, lý do thoát, R, P&L, MFE/MAE, phút, phiên bản chiến lược, `code_version`), có "xem trên biểu đồ" mở đúng lệnh trên biểu đồ, và "nguồn gốc" cho ảnh chụp quyết định lúc vào lệnh.

## Công cụ của bạn (chỉ để ghi chú, không ảnh hưởng quyết định)

* **Đường ngang**: bấm nút → bấm lên biểu đồ → đường được vẽ và nhớ lại lần sau; xóa ở tab Tổng quan.
* **Đo**: bấm hai điểm để biết chênh lệch giá, số điểm, phần trăm, số nến và số phút.
* **Cảnh báo giá**: nhập giá, trang báo khi bid chạm giá đó (chỉ hoạt động khi trang đang mở; chỉ thông báo, không giao dịch).
* **Lớp phủ**: bật/tắt tín hiệu, kế hoạch, lệnh paper, hỗ trợ/kháng cự + PDH/PDL, tick volume, nền màu phiên Á/Âu/Mỹ, lịch sử lệnh paper.
* Tùy chọn của bạn (khung, lớp phủ, theo nến, múi giờ, tab, mức rủi ro) được nhớ trong trình duyệt; không có gì liên quan tới quyền giao dịch, chiến lược hay thông tin đăng nhập được lưu.

## Phím tắt (không phím nào mở hay đóng lệnh)

`1` M1 · `5` M5 · `2` M15 · `3` M30 · `H` H1 · `4` H4 · `F` vừa khung · `L` về nến mới nhất · `W` theo nến · `X` toàn màn hình · `M` đo · `T` đường ngang · `?` bảng phím tắt · `Esc` thoát công cụ/toàn màn hình/hộp thoại.

## Tab dưới biểu đồ

**Tổng quan** (hoạt động thị trường, mức giá, công cụ của bạn) · **Lý do** (từng tầng điều kiện + chi tiết kỹ thuật) · **Vị thế** · **Hoạt động** · **Hệ thống** (trạng thái dữ liệu, lõi, chiến lược đang chạy và các phiên bản chỉ cài đặt, forward acceptance, phễu, cảnh báo, tài khoản PAPER, khóa DEMO). Các thông tin kỹ thuật nằm ở đây để không cạnh tranh với giá.

## Phiên bản chiến lược đang chạy

Thẻ "Chiến lược" (tab Hệ thống) luôn ghi **Đang chạy** (mặc định v1.1.0). v1.2.0 và v1.2.1 chỉ được cài đặt, ghi `ĐÃ CÀI · KHÔNG CHẠY`, không chạy.

## Những gì CHƯA được kiểm chứng (đừng hiểu nhầm)

* Không có edge được chứng minh; baseline chỉ là quy trình vận hành minh bạch.
* **Tin tức: chưa xác minh** (chưa có lịch kinh tế). Tự kiểm tra tin trước khi tin vào một setup.
* Volume là **tick volume**, không phải volume sàn.
* Mức "Forward acceptance" ở F0 cho đến khi có một setup LIVE thật; replay không nâng được mức này.
* Chưa có thực thi DEMO; không có lệnh nào đi tới MT5.

## Khi có lỗi

| Thấy | Nghĩa | Việc cần làm |
|---|---|---|
| `PAPER_STATE_ERROR` | File trạng thái paper không khớp journal | Dừng mở lệnh mới; chạy khôi phục (xem `docs/trading/PAPER_RECOVERY.md`) |
| `WRITER_LOCK` | Một tiến trình API khác đang giữ bàn paper | Tắt tiến trình thừa (chỉ một API được chạy) |
| `DATA_STALE` / collector dừng | Dữ liệu không tươi | `scripts\status_market_stack.ps1` |
| `SPEC_MISSING` | Thiếu đặc tả hợp đồng broker | Kiểm tra collector/MT5 |
| `API_UNAVAILABLE` | Trang không nói chuyện được với API | Kiểm tra stack; không vào lệnh |
