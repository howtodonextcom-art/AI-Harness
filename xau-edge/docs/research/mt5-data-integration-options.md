# Các phương án tích hợp dữ liệu MT5 (FTMO) cho xau-edge

Ngày: 2026-10-09. Phạm vi: chọn đường lấy dữ liệu XAUUSD (bar, tick, bid/ask, volume) từ MetaTrader 5 kết nối FTMO. Tài liệu chỉ dựa trên các trang chính thức đã fetch (xem mục "Nguồn"). Chỗ nào không tìm thấy trong nguồn chính thức được ghi rõ là "chưa xác minh bằng trang hiện tại".

## 1. Tóm tắt các sự thật đã xác minh

- Gói Python `MetaTrader5` do MetaQuotes phát hành (MIT), bản mới nhất trên PyPI là 5.0.6231 (27/09/2026), hỗ trợ Python 3.6 đến 3.14, wheel chỉ cho Windows x86-64 (PyPI). Trang docs mql5 nói gói lấy dữ liệu "via interprocess communication" từ terminal MT5 và cần terminal đang chạy; trang docs không nêu rõ danh sách hệ điều hành của gói Python (chưa xác minh bằng trang docs; PyPI là nguồn duy nhất cho "Windows-only").
- `initialize()` có thể tự khởi chạy terminal; tham số `path`, `login`, `password`, `server`, `timeout` (mặc định 60000 ms), `portable` (mặc định False).
- FTMO cho phép chọn MT4, MT5, cTrader, TradingView; tài khoản FTMO (kể cả Free Trial) là demo với vốn giả lập; Free Trial có trên MT5; server time MT4/MT5 là GMT+2 +DST (FTMO FAQ account specifications).
- FTMO cho phép algorithmic trading/EA (blog FTMO), trader vẫn chịu trách nhiệm về Trading Objectives; blog không nói gì về API/Python cho MT5.
- FTMO có nhắc Open API (C#, Python) cho cTrader; không tìm thấy API gốc cho MT5 (chưa xác minh bằng trang hiện tại rằng FTMO không có API cho MT5, chỉ là không thấy trong các trang đã fetch).

## 2. Bảng so sánh phương án A-H

| Method | Official status | Requirements | History support | Tick support | Bid/ask support | Volume support | Windows dependency | Terminal dependency | Security model | Advantages | Limitations | Decision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A. FTMO MT5 desktop + package `MetaTrader5` chính thức | Chính thức (MetaQuotes; docs mql5, PyPI) | Terminal MT5 FTMO cài và đăng nhập; Python trong dải 3.6-3.14; `pip install MetaTrader5` | `copy_rates_from/from_pos/range`, các `TIMEFRAME_*` (M1..MN1); giới hạn bởi "Max. bars in chart" | `copy_ticks_from/range` với `COPY_TICKS_ALL/INFO/TRADE`; `symbol_info_tick` cho tick cuối | Có: cột `bid`, `ask` trong tick; `spread` trong rates (đơn vị point) | `tick_volume`, `real_volume` (rates); `volume`, `volume_real` (tick). Ý nghĩa của `real_volume` cho CFD vàng FTMO: chưa xác minh bằng trang hiện tại | Có (wheel chỉ Windows x86-64 trên PyPI) | Có: terminal phải chạy, giao tiếp IPC cục bộ | Cục bộ, không mở cổng mạng; thông tin đăng nhập nằm trong terminal hoặc truyền vào `initialize()`; nên dùng read-only password nếu chỉ lấy dữ liệu (xem mục 4) | Chính thức, ổn định, trả numpy array, có sẵn `symbol_info` (digits, volume_min/step, contract size) cho sizing; không cần viết MQL5 | Phụ thuộc terminal sống và đồng bộ lịch sử; giới hạn Max bars; chỉ Windows; một process Python gắn với một terminal | CHỌN làm mặc định |
| B. MT5 desktop chuẩn kết nối FTMO (cài đặt mặc định, dữ liệu ở AppData) | Chính thức (FTMO cung cấp link tải trong Client Area) | Tải terminal từ Credentials, chọn đúng server FTMO | Giống A (là nền của A) | Giống A | Giống A | Giống A | Có | Có | Như A | Cách cài tiêu chuẩn, FTMO hướng dẫn trực tiếp | Dữ liệu và config nằm ở thư mục người dùng; dễ lẫn nếu có nhiều terminal | Là cấu hình nền của A |
| C. MT5 portable (`/portable`) | Chính thức (help MT5, launch key `/portable`; `initialize(portable=True)`) | Quyền ghi vào thư mục cài; nếu ở Program Files cần admin và tắt UAC (theo help) | Như A, lịch sử tách riêng theo thư mục | Như A | Như A | Như A | Có | Có | Cô lập dữ liệu/profile theo thư mục, dễ tách môi trường bot khỏi terminal trade tay | Tái lập được, nhiều instance song song, dọn dẹp dễ | Phải quản lý cập nhật từng bản; vẫn cần đăng nhập mỗi bản | Khuyến nghị dùng cho môi trường data/bot riêng (biến thể của A) |
| D. EA/script MQL5 làm cầu | Chính thức (MQL5 là ngôn ngữ gốc); FTMO cho phép EA | Viết, biên dịch, gắn EA vào chart; bật Algo Trading | Có qua `CopyRates` (cùng giới hạn TERMINAL_MAXBARS) | Có qua `CopyTicks*` | Có | Có | Có | Có (EA chạy trong terminal) | EA chạy trong sandbox MQL5; rủi ro lỗi code chạy cạnh tài khoản; FTMO nói trader chịu trách nhiệm | Truy cập dữ liệu và sự kiện theo thời gian thực nội bộ terminal | Tăng bề mặt rủi ro, phải bảo trì mã MQL5; không cho thêm dữ liệu so với A | Không dùng trừ khi A chứng minh không đủ |
| E. Cầu socket/TCP/ZeroMQ trong MQL5 | `SocketCreate/SocketConnect` là hàm chính thức; ZeroMQ là thư viện bên thứ ba (không chính thức, chưa xác minh bằng trang hiện tại) | EA hoặc script (không dùng được trong indicator, lỗi 4014); địa chỉ phải nằm trong danh sách cho phép của terminal; tối đa 128 socket mỗi chương trình | Qua CopyRates | Qua CopyTicks | Có | Có | Có | Có | Mở kênh mạng ra ngoài terminal; cần whitelist địa chỉ, tự lo xác thực và mã hóa | Streaming tick gần realtime tới tiến trình ngoài | Phức tạp, thêm điểm lỗi, thêm bề mặt tấn công; trùng lặp chức năng với A | Không dùng trừ khi A không đủ về độ trễ |
| F. Cầu file CSV/JSON qua MQL5 | Chính thức (`FileOpen`, sandbox `MQL5\Files`, cờ `FILE_COMMON`) | EA/script ghi file; bên ngoài đọc file | Qua CopyRates | Qua CopyTicks | Có | Có | Có | Có | File bị giới hạn trong sandbox; truy cập đồng thời cần `FILE_SHARE_*`; không có xác thực, bảo vệ bằng quyền file hệ điều hành | Đơn giản, dễ debug | Độ trễ cao, race condition, dễ file dở dang, không chuẩn hóa schema | Không dùng; chỉ cân nhắc làm bản dự phòng offline |
| G. API gốc của broker (nếu FTMO có) | FTMO nhắc Open API cho cTrader (C#, Python). Với MT5 không tìm thấy API gốc | Với cTrader: nền tảng khác, không phải MT5 | Với MT5: chưa xác minh bằng trang hiện tại | Chưa xác minh bằng trang hiện tại | Chưa xác minh bằng trang hiện tại | Chưa xác minh bằng trang hiện tại | Không áp dụng | Không áp dụng | Chưa xác minh bằng trang hiện tại | Nếu có sẽ không cần terminal | Không có tài liệu cho MT5; chuyển sang cTrader làm đổi cả nền tảng thực thi và feed | Loại cho MT5; chỉ xem lại nếu đổi sang cTrader |
| H. MT5 WebTerminal | Chính thức (metatrader5.com), mỗi broker tự host trên domain riêng; FTMO có link web trong Credentials | Chỉ cần trình duyệt | Chỉ xem trên giao diện; không có API lập trình được nêu trong các trang đã fetch | Chưa xác minh bằng trang hiện tại | Chỉ hiển thị | Chỉ hiển thị | Không (chạy trong trình duyệt) | Không cần terminal desktop, nhưng không có kênh dữ liệu cho backend | Phiên trình duyệt; automation giao diện là lách luật, không nên | Tiện để xem/trade tay mọi nơi | Không cung cấp đường lấy dữ liệu cho backend; trang how-to-connect không nói về EA (chưa xác minh) | Loại cho mục đích dữ liệu |

## 3. Giới hạn đã biết của copy_rates/copy_ticks

Theo tài liệu chính thức:

1. Phạm vi lịch sử: "MetaTrader 5 terminal provides bars only within a history available to a user on charts. The number of bars available to users is set in the 'Max. bars in chart' parameter." (ghi trong `copy_rates_from`, `copy_rates_from_pos`, `copy_rates_range`). Help của MT5 nói giá trị tối thiểu là 5000 và phải khởi động lại nền tảng để thay đổi có hiệu lực. Docs MQL5 nói giới hạn này không cứng tuyệt đối, số bar thực tế có thể vượt nhẹ giá trị cấu hình. `terminal_info().maxbars` cho biết giá trị hiện hành. Hệ quả: backtest/replay dài trên M1 phải kiểm tra `maxbars` trước, và không được giả định lịch sử vô hạn.
2. Đồng bộ lịch sử: terminal xin dữ liệu từ server theo từng khối "packed blocks of minute bars" và dựng các timeframe khác từ đó; docs nhấn mạnh độ trễ đồng bộ khó dự đoán. Với MQL5 `CopyRates`: gọi khi timeseries chưa dựng sẽ khởi động tải nền; trong EA/script, hàm trả dữ liệu đang có khi hết timeout, trong khi tải nền vẫn tiếp tục; trả -1 nếu khoảng yêu cầu vượt dữ liệu server hoặc vượt TERMINAL_MAXBARS. Các trang Python không nêu hành vi đồng bộ này riêng; ta chỉ biết `None` được trả khi lỗi, dùng `last_error()`. Nên coi lần gọi đầu có thể thiếu dữ liệu, và gọi lại/kiểm tra số lượng và độ liên tục (chưa xác minh hành vi chính xác của wrapper Python bằng trang hiện tại).
3. `symbol_select()`: ký hiệu cần ở Market Watch để lấy dữ liệu ổn định (docs `symbol_info_tick` khuyên chọn symbol trước); không thể bỏ chọn nếu còn chart mở hoặc vị thế mở.
4. Thứ tự trả về: docs Python không nêu thứ tự cho `copy_rates_*`/`copy_ticks_*` (chưa xác minh bằng trang Python). Với MQL5 `CopyRates`, phần tử cũ nhất nằm ở đầu bộ nhớ mảng. `copy_rates_from_pos`: start_pos đánh số từ hiện tại về quá khứ (0 là bar hiện tại, có thể chưa đóng). `copy_rates_from`: chỉ trả bar có open time nhỏ hơn hoặc bằng ngày chỉ định. `copy_rates_range`: bar có open time trong [date_from, date_to]. Bar cuối có thể là bar đang hình thành, nên loại trước khi dùng cho quyết định (closed-bar frames của TC-01).
5. Múi giờ: docs ghi "MetaTrader 5 stores tick and bar open time in UTC time zone (without the shift)", `datetime` đưa vào phải tạo ở UTC (Python dùng múi giờ cục bộ), và dữ liệu nhận về "have UTC time"; in ra bằng Python có thể bị áp lại offset cục bộ. Tuy nhiên FTMO ghi server time MT5 là GMT+2 +DST. Hai nguồn này không tự giải thích sự khác biệt giữa "UTC" của docs và "server time" của FTMO; việc timestamp trả về thực tế là UTC thật hay là giờ server dạng epoch chưa xác minh bằng trang hiện tại. Phải kiểm chứng thực nghiệm (so `symbol_info_tick().time` với đồng hồ UTC lúc thị trường mở; so open bar D1 với giờ mở phiên) trước khi tin vào bất kỳ quy đổi nào, và ghi kết quả vào hợp đồng dữ liệu.
6. Tick: `COPY_TICKS_INFO` (đổi Bid/Ask), `COPY_TICKS_TRADE` (đổi Last/Volume), `COPY_TICKS_ALL` (tất cả). Cột: time, bid, ask, last, volume, time_msc, flags, volume_real. Flags: TICK_FLAG_BID, ASK, LAST, VOLUME, BUY, SELL. Docs không nêu giới hạn số tick, thứ tự, hay cách xử lý lịch sử tick thiếu/tải từ server (đã kiểm tra trang `copy_ticks_range`: không có phát biểu nào). Với CFD vàng, trường `last`/`volume` có thể rỗng; chưa xác minh bằng trang hiện tại.
7. Lỗi: hầu hết hàm trả `None`; gọi `last_error()`.

## 4. Investor password

- FTMO FAQ "How do I log in to MT5?" xác nhận có hai loại mật khẩu: master password (để trade) và read-only password (chỉ xem); "Trading-related actions require the master password"; cả hai hiển thị trong Credentials của Account MetriX trong Client Area; server phải trùng đúng với mục Credentials.
- FTMO dùng cụm "read-only password"; việc nó chính là "investor password" của MT5 chuẩn về mặt kỹ thuật không được FTMO nói rõ trong trang đã fetch (chưa xác minh bằng trang hiện tại).
- Chưa xác minh bằng trang hiện tại: `initialize(login, password, server)` có đăng nhập và lấy được dữ liệu thị trường bằng read-only password hay không, và FTMO có hạn chế đăng nhập đồng thời nhiều phiên hay không. Cần thử trên tài khoản demo/Free Trial.
- Free Trial: trang FTMO nói "Traders can use our Free Trial demo account for 14 days. After this period, they can create a new one" (trang ftmo-free-trial); FAQ khác ghi "No time limit" nhưng "limited to one phase". Hai trang mâu thuẫn, chưa xác minh bằng trang hiện tại thời hạn chính xác.
- Khuyến nghị an toàn: tiến trình lấy dữ liệu chỉ nên dùng read-only password; không lưu master password trong repo.

## 5. Khuyến nghị

1. Mặc định: phương án A (package `MetaTrader5` chính thức), chạy trên một terminal MT5 FTMO ở chế độ portable (C) dành riêng cho bot dữ liệu, tách khỏi terminal trade tay.
2. Không xây bridge tùy chỉnh (D, E, F). Chỉ xem xét lại khi có bằng chứng đo được rằng A không đủ: ví dụ độ trễ tick không đáp ứng, hoặc thiếu lịch sử do Max bars.
3. Không dùng H để lấy dữ liệu. G không áp dụng cho MT5.
4. Việc cần làm trước khi dùng dữ liệu cho quyết định: (a) đo `terminal_info().maxbars` và độ sâu M1/M30 thực tế cho XAUUSD; (b) xác minh múi giờ timestamp (mục 3.5); (c) kiểm tra liên tục lịch sử, bar cuối chưa đóng; (d) kiểm tra read-only password trên demo; (e) xác nhận ý nghĩa `real_volume`/`last` của XAUUSD ở FTMO; (f) ghi version/build từ `version()` và `terminal_info()` vào mỗi lần thu để tái lập.
5. Dữ liệu nền tảng thực thi là nguồn sự thật là MT5 FTMO, không phải TradingView (xem tradingview-data-role.md).

## Nguồn

- https://www.mql5.com/en/docs/python_metatrader5
- https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrompos_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrom_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksrange_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksfrom_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5terminalinfo_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5version_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5accountinfo_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5symbolsget_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5symbolselect_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5symbolinfo_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5symbolinfotick_py
- https://www.mql5.com/en/docs/series/copyrates
- https://www.mql5.com/en/docs/series/timeseries_access
- https://www.mql5.com/en/docs/network/socketcreate
- https://www.mql5.com/en/docs/files/fileopen
- https://pypi.org/project/MetaTrader5/
- https://www.metatrader5.com/en/terminal/help/startworking/settings
- https://www.metatrader5.com/en/terminal/help/start_advanced/start
- https://www.metatrader5.com/en/trading-platform/web-trading/how-to-connect
- https://ftmo.com/en/faq/how-do-i-log-in-to-mt5/
- https://ftmo.com/en/faq/how-about-a-free-trial/
- https://ftmo.com/en/ftmo-free-trial/
- https://ftmo.com/en/faq/which-platforms-can-i-use-for-trading/
- https://ftmo.com/en/faq/what-are-the-account-specifications/
- https://ftmo.com/en/blog/what-is-algorithmic-trading-and-how-to-use-it-for-the-ftmo-challenge/
- https://ftmo.com/en/trading-platforms/
