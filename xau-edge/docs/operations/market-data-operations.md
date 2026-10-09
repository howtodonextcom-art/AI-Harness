# Vận hành nền tảng dữ liệu thị trường MT5

Một việc duy nhất cần nhớ: **`scripts\start_market_stack.ps1`**. Mọi thứ khác bên dưới là để hiểu và khắc phục.

## 1. Kiến trúc vận hành (một người giám sát)

```
Đăng nhập Windows ──(Task Scheduler "XAU-EDGE Market Stack", trễ 45 s, chạy bằng tài khoản của bạn)
   └─ start_market_stack.ps1
        1. mở terminal FTMO MT5 nếu chưa chạy (ứng dụng desktop: KHÔNG chạy như service Session 0)
        2. khởi chạy MỘT supervisor Python (scripts/run_market_stack.py), không bao giờ chạy trùng
              ├─ collector   (quote ~1 s, nến ~5 s, tick, reconcile, tự kết nối lại khi mất terminal)
              ├─ api         (127.0.0.1:8000, chỉ GET)
              └─ dashboard   (127.0.0.1:3000, nếu dùng -Dashboard)
        3. chờ nhịp tim collector mới rồi chạy cổng sức khỏe
```

Vì sao không NSSM: MT5 là ứng dụng GUI; còn các tiến trình Python đã có supervisor riêng (khởi động lại có
backoff 2→60 s, PID/nhịp tim ở `data/run/`, log xoay vòng 10 MB × 5 ở `data/logs/`). Hai bộ giám sát cùng
quản một tiến trình sẽ tranh nhau và che lỗi nên chỉ có một. NSSM/`install_services.ps1` vẫn dành cho bot
giao dịch và không bị đụng tới.

## 2. Lệnh hằng ngày

| Việc | Lệnh |
|---|---|
| Bật toàn bộ | `.\scripts\start_market_stack.ps1 -Dashboard -Open` |
| Xem một cái nhìn: vì sao UI cũ? | `.\scripts\status_market_stack.ps1` |
| Tắt (giữ dữ liệu, KHÔNG tắt MT5) | `.\scripts\stop_market_stack.ps1` |
| Cổng sức khỏe (exit 0 chỉ khi GOOD) | `uv run python scripts/check_market_data_health.py` |
| Cài tự khởi động khi đăng nhập | `.\scripts\install_market_autostart.ps1 -Dashboard` (gỡ: `-Uninstall`) |

`status_market_stack.ps1` in từng thành phần (MT5, supervisor, collector, API, dashboard), tuổi nhịp tim,
báo giá, nến M1 gần nhất, độ mới từng khung, kho tick, đĩa, rồi liệt kê "WHY THE UI MAY BE STALE".

## 3. Trang `/market` đọc thế nào

Sáu viên trạng thái độc lập: **MT5** (terminal), **Collector**, **API**, **Thị trường** (MỞ / ĐÓNG cuối tuần /
NGHỈ GIỮA NGÀY), **Báo giá**, **Nến**. Khi thị trường đóng, tick/nến cũ là bình thường (viên "THỊ TRƯỜNG ĐÓNG"),
nhưng viên Collector vẫn cho biết tiến trình có sống không. Nếu có việc cần làm, dòng "Cách khắc phục" nói
chính xác lệnh. Độ mới tính theo lịch: khung chỉ "CŨ" khi bỏ lỡ nến trong lúc thị trường mở (M1 trễ > 2 nến,
khung khác trễ > 1 nến). Nến H4 đóng cách đây 1 giờ KHÔNG bị coi là cũ. Khung "Chất lượng dữ liệu" mở rộng
cho độ sâu lịch sử, kho tick, đĩa, toàn vẹn kho nến và sự kiện thay đổi/khoảng trống gần đây.

## 4. "Max bars in chart" (đã làm 2026-10-09; ghi lại để lặp lại được)

Terminal từng có `MaxBars=100000` nên M1/M5/M15/M30/H1 không lùi tới hết lịch sử. Đã nâng lên 10.000.000. Nếu phải làm lại
(cài lại terminal, đổi máy):

1. **Tắt stack trước**: `.\scripts\stop_market_stack.ps1`. Nếu không, collector sẽ TỰ MỞ LẠI MT5 mỗi khi bạn thoát nó
   (`initialize` khởi động terminal), và bạn không bao giờ đóng được terminal.
2. Đóng hẳn terminal FTMO MT5 (File → Exit). Kiểm tra `Get-Process terminal64` không in gì.
3. `uv run python scripts/mt5_set_max_bars.py` (xem trước), rồi `... --value 10000000 --apply` (tự sao lưu, chỉ sửa dòng
   `MaxBars`, từ chối nếu terminal còn chạy, không in thông tin tài khoản).
4. Mở lại terminal DESKTOP (không phải WebTerminal trên trình duyệt), đợi đăng nhập/đồng bộ.
5. `uv run --extra mt5 python scripts/mt5_set_max_bars.py --verify`: hỏi chính terminal giá trị MaxBars đang hiệu lực
   (không tin vào file) và số M1 phục vụ.
6. `uv run --extra mt5 python scripts/backfill_mt5.py --write-report`, rồi `scripts/verify_market_ledger.py --save-manifest`,
   `scripts/market_data_parity.py --write`, `scripts/verify_visual_parity.py --write`, và bật lại stack.

Trạng thái mỗi khung sau backfill: `COMPLETE_AVAILABLE_HISTORY` / `BROKER_LIMITED` (đủ), `TERMINAL_LIMITED` (còn bị cap),
`INCOMPLETE` (chạy lại), `UNKNOWN`. Báo cáo: `docs/reports/mt5-backfill-final.{json,md}`.

## 5. Tick, retention, đĩa

* Collector ghi tick mỗi ~5 s vào `data/market/XAUUSD/ticks/` (tối đa 24 giờ vá lại sau khi tắt; xa hơn dùng
  `scripts/backfill_mt5_ticks.py --from YYYY-MM-DD`, chạy lại được, chia cửa sổ 6 giờ).
* Mặc định giữ mọi tick (≈ 0,3 GB/năm). Chuyển tick cũ sang ổ khác: `scripts/archive_ticks.py` (dry-run mặc định).
* Đĩa: `status_market_stack.ps1` và khung Chất lượng dữ liệu cho `disk.level`; CRITICAL kéo health xuống DEGRADED.
* Chi tiết: `docs/reports/mt5-tick-storage.md`.

## 6. Kiểm tra tự khởi động THẬT (danh sách kiểm tay)

Cấu hình ≠ đã xác minh. Task đã đăng ký và đã chạy thử bằng `Start-ScheduledTask` (dựng được cả stack), nhưng
chuỗi đăng nhập thật chưa chạy tự động. Để đóng mục này:

1. Đảm bảo `Get-ScheduledTask 'XAU-EDGE Market Stack'` ở trạng thái Ready.
2. Đăng xuất Windows (hoặc khởi động lại) rồi đăng nhập lại; ĐỪNG chạy gì.
3. Sau ~2 phút: `.\scripts\status_market_stack.ps1` phải in `OK` (MT5, supervisor, collector, API, dashboard đều chạy);
   mở `http://127.0.0.1:3000/market` thấy sáu viên màu xanh.
4. Ghi ngày giờ + kết quả vào cuối `docs/reports/mt5-chaos-tests.md`.

## 7. Khắc phục sự cố

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Collector "ĐÃ DỪNG/CŨ" | supervisor không chạy | `start_market_stack.ps1`; xem `data\logs\collector.log` |
| MT5 "MẤT KẾT NỐI" | terminal đóng/chưa đăng nhập/broker ngắt | mở terminal, đăng nhập; collector tự nối lại ≤ 5 s |
| Báo giá "CŨ" khi thị trường mở | collector chết hoặc broker không có tick | `status_market_stack.ps1`; nếu collector sống, xem log |
| Nến một khung "CŨ" | collector bị chặn hoặc terminal chậm | xem sự kiện GAP trong khung Chất lượng dữ liệu |
| `BAR_CHANGED` / DEGRADED | broker sửa nến lịch sử | kho giữ bản cũ và ghi sự kiện; xem `events.jsonl`, quyết định thủ công |
| Cổng 3000/8000 bị chiếm | tiến trình mồ côi cũ | `stop_market_stack.ps1`; nếu vẫn chiếm, `Get-NetTCPConnection -LocalPort 3000` |
| Đĩa CRITICAL | đĩa đầy | giải phóng chỗ hoặc `archive_ticks.py` |

## 8. Bảo mật

Không file nào ở đây chứa mật khẩu, login hay số dư; collector dùng phiên đã đăng nhập của terminal và từ chối
tài khoản không phải DEMO. Client dữ liệu không có hàm giao dịch. Mọi API `/md/*` chỉ GET và chỉ lắng nghe 127.0.0.1.
