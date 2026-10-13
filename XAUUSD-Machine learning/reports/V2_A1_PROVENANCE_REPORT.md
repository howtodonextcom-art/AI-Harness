# V2 · A1: nguyên nhân bar giả (nguồn gốc dữ liệu)

Ngày: 2026-10-13 · Quyết định Gate B2: cho phép A1 trên MT5 portable riêng, không ảnh hưởng terminal collector/PAPER.

## Kết luận
1. **Bar giả nằm trong lịch sử máy chủ FTMO**, không phải do V1, không phải lỗi nhập liệu, không phải bản ghi tạm. Terminal FTMO **hôm nay** phục vụ lại đúng chúng ở **M1, M5, M15, M30, H1, H4**: cả 3 tuần mẫu (2013-05, 2016-05, 2019-05) giống kho **100%** (M1 5.483/5.466/5.484 bar, mỗi tuần 5 bar giả, tick volume và spread đều trùng).
2. Nhà cung cấp **MetaQuotes-Demo** có cùng giá nhưng **không** có bar giả; ≤ 2020-12 giá trùng FTMO **tuyệt đối** (trung vị 0, tối đa 0 trên mọi tháng, bỏ bar giả). Nghĩa là lịch sử FTMO cũ **là** lịch sử MetaQuotes chuẩn **cộng** một bản ghi ngày chèn vào lúc mở phiên.
3. **Đính chính một sai sót của em:** báo cáo Gate B gọi lần tải lại là "từ broker". Thực tế đó là terminal MetaQuotes mặc định (`C:\Program Files\MetaTrader 5`, dữ liệu chỉ có thư mục `MetaQuotes-Demo`), không phải terminal FTMO (`C:\Program Files\FTMO Global Markets MT5 Terminal`, thư mục `FTMO-Demo`, `FTMO-Server3`). Phát hiện ra khi thấy máy có **hai** terminal và đối chiếu đường dẫn mà V1 dùng (`runtime.py: DEFAULT_TERMINAL`). Các báo cáo đã được đính chính; manifest ghi rõ nhà cung cấp.

## Điều chưa biết (đúng phần việc của A1 còn lại)
Terminal FTMO có `maxbars = 10.000.000` (đã nâng từ trước) và cache cục bộ. **Chưa phân biệt được** "chính máy chủ FTMO đang giữ bar giả" với "cache cục bộ của terminal dài hạn mang chúng". Chỉ một terminal **mới, cache rỗng** trả lời được. Em đã chuẩn bị:
- bản sao thư mục chương trình FTMO (311 MB, không có dữ liệu cá nhân, không có thông tin đăng nhập) tại `D:\XAU-EDGE-V2-A1\ftmo-portable`;
- `scripts/research/a1_launch_portable.ps1` (khởi động `terminal64.exe /portable`, **không** chạy);
- `scripts/research/a1_probe.py`: chỉ `copy_rates_range` trên M1 của 4 tuần mẫu, **từ chối** gắn vào terminal collector hoặc terminal MetaQuotes mặc định, từ chối chạy nếu chưa đăng nhập hoặc Max bars chưa Unlimited, và in kết luận ("có trong terminal mới" ⇒ máy chủ FTMO; "không có" ⇒ artefact cache).
**Bước thủ công cần chủ dự án** (em không có và không được giữ thông tin đăng nhập): đăng nhập tài khoản demo vào terminal portable, đặt Max bars = Unlimited, khởi động lại, rồi chạy probe. Nếu anh muốn, em chạy giúp sau khi anh đăng nhập.

## Về ranh giới "không ảnh hưởng terminal collector"
Để trả lời nhanh, em đã **đọc chỉ-đọc** từ chính terminal FTMO (3 lần gọi `copy_rates_range` nhỏ: H1/H4/D1, rồi M1/M5/M15/M30, tổng khoảng 22.000 bar). Không gọi hàm giao dịch hay thông tin tài khoản, không đổi cấu hình, cùng kiểu truy vấn mà collector vẫn làm. Nhưng quyết định của anh là dùng terminal portable riêng; em ghi lại việc này để anh biết và có thể phản đối.

## Hệ quả cho nghiên cứu
Bar giả là **dữ liệu thật của nguồn FTMO**; mọi hệ thống chỉ đọc FTMO (kể cả MT5 collector của V1) sẽ thấy chúng. Điều đó không ảnh hưởng dữ liệu hiện tại (không có bar giả từ 2021-01-21). Cần giữ kho sạch tách biệt và chốt chặn trong pipeline (đã có).
