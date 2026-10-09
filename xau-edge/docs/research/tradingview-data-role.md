# Vai trò của dữ liệu TradingView trong xau-edge

Ngày: 2026-10-09. Chỉ dựa trên các trang chính thức của TradingView và FTMO đã fetch (xem "Nguồn"). Chỗ không xác minh được ghi "chưa xác minh bằng trang hiện tại".

## 1. Quyết định mặc định

**TradingView is NOT the execution source of truth.** Nguồn sự thật cho giá, spread, tick và thực thi là MT5 FTMO (xem mt5-data-integration-options.md). TradingView chỉ là công cụ tham khảo/so sánh trực quan.

## 2. Các lựa chọn chính thức của TradingView

| Lựa chọn | Giấy phép | Dữ liệu | Ghi chú |
|---|---|---|---|
| Lightweight Charts | Apache 2.0 (mã nguồn mở), dùng cá nhân và thương mại | Tự cấp dữ liệu qua API của mình ("bring your own data"); hỗ trợ cập nhật streaming cho dữ liệu tùy biến | Phù hợp nhất để nhúng biểu đồ vẽ từ dữ liệu MT5 của chính ta; yêu cầu attribution chưa xác minh bằng trang hiện tại (trang chỉ trỏ tới GitHub và giấy phép Apache 2.0) |
| Advanced Charts (Charting Library) | Proprietary; miễn phí kèm logo TradingView; không cấp cho mục đích cá nhân, sở thích, học tập hay thử nghiệm, chỉ cho công ty dùng trong dự án/ứng dụng web công khai | Thư viện "không cung cấp bất kỳ dữ liệu thị trường nào"; ta tự nối nguồn qua Datafeed API hoặc UDF adapter (HTTP tới backend; backend có thể viết bằng Python) | Truy cập repo bị hạn chế, cần được duyệt; FAQ nói chỉ dùng trên website công khai theo license. Dự án xau-edge nội bộ/cá nhân có thể không đủ điều kiện (chưa xác minh bằng trang hiện tại về từng trường hợp) |
| Trading Platform | Proprietary, tương tự Advanced Charts | Phải nối trực tiếp backend broker cho cả data stream và order routing | Không phù hợp: ta không phải broker |
| Widgets | Miễn phí, nhúng sẵn, có branding TradingView; theo Terms of Use và House Rules | Dữ liệu do TradingView hiển thị; trang widget ghi "We don't have an API that gives access to data"; REST API chỉ dành cho broker | Chỉ để xem, không lấy được dữ liệu ra backend |
| Datafeed API | Thành phần của Advanced Charts/Trading Platform | Ta viết JS object trả symbol, lịch sử OHLC, quote realtime (hỗ trợ WebSocket) | Nếu dùng, đây là hướng "đẩy dữ liệu MT5 của ta vào chart TradingView", không phải ngược lại |

Kết luận: TradingView không cung cấp API dữ liệu thị trường chính thức để ta kéo dữ liệu chart về backend riêng. Các trang đã fetch chỉ cho phép: hiển thị (widget), hoặc dùng thư viện biểu đồ với dữ liệu do ta cấp.

## 3. Licensing dữ liệu

- Điều khoản dịch vụ (policies) nói nội dung và dữ liệu thị trường được cấp phép "display-only", giới hạn cho mục đích cá nhân hoặc nội bộ.
- Cấm các hình thức không phải hiển thị cho người đọc: automated trading, automated order generation, price referencing, order verification, algorithmic decision-making, smart order routing, dùng trong chương trình risk management/operations control.
- Cấm sublicense, chuyển nhượng, phân phối lại nội dung và dữ liệu thị trường (do hợp đồng với Data Providers).
- Cấm công cụ thu thập dữ liệu tự động (scripts, APIs, screen scraping, data mining, robots) bất kể mục đích (theo kết quả tìm kiếm trong trang policies; đoạn nguyên văn này chưa được trang fetch xác nhận lại đầy đủ, nên cần đọc trực tiếp trang policies trước khi dựa vào).
- Hệ quả: dữ liệu hiển thị của TradingView không được dùng làm đầu vào cho engine quyết định, replay hay risk management của xau-edge.

## 4. Vì sao dữ liệu TradingView có thể khác MT5 FTMO

Những điểm đã có căn cứ chính thức:

1. Nguồn dữ liệu và feed khác nhau: TradingView lấy dữ liệu từ các nhà cung cấp/sàn (trang widget nêu ICE Data Services, FactSet là ví dụ); FTMO MT5 dùng feed của server FTMO. Trang hỗ trợ TradingView nói dữ liệu intraday có thể khác nguồn khác do cách lọc của data provider (ví dụ lọc odd lots, late prints; ví dụ này nêu cho cổ phiếu Mỹ, không phải XAUUSD).
2. Feed chart và feed broker tách nhau: khi nối broker thật, order panel dùng dữ liệu của broker chứ không phải của TradingView, nên giá thấy trên chart và giá khớp có thể khác nhau, đặc biệt khi biến động nhanh (trang hỗ trợ TradingView).
3. Múi giờ/phiên: FTMO ghi server time MT4/MT5 là GMT+2 +DST, còn cTrader và TradingView của FTMO là "customised (as per trader's settings)". Nên cùng một bar D1 hoặc H4 có thể mở ở thời điểm khác nhau, dẫn tới OHLC khác nhau.
4. Chưa xác minh bằng trang hiện tại, cần đo thực nghiệm: mức chênh spread (chart TradingView thường vẽ theo một loại giá, thường là last/bid tùy nguồn, còn MT5 cho bid/ask riêng và spread biến thiên), nguồn cụ thể của symbol XAUUSD trên TradingView, và khác biệt cách dựng nến giữa hai bên.
5. Lưu ý: FTMO cũng cung cấp TradingView như một nền tảng trade (trong danh sách MT4, MT5, cTrader, TradingView). Nếu chạy trên TradingView của FTMO, đó là một nền tảng thực thi khác với MT5 và không nằm trong phạm vi bot hiện tại.

## 5. TradingView được phép dùng cho việc gì

- So sánh trực quan thủ công: người dùng tự mở chart để đối chiếu hình dạng nến, vùng giá, sự kiện với dữ liệu MT5. Không tự động hóa việc đọc.
- Nguồn cảm hứng UX: bố cục chart, công cụ vẽ, đa khung thời gian, cách hiển thị lệnh/mức SL/TP.
- Nhúng biểu đồ chỉ-đọc nếu license cho phép: ưu tiên Lightweight Charts (Apache 2.0) vẽ dữ liệu MT5 của ta; Advanced Charts chỉ khi đủ điều kiện license (công ty, website công khai) và được cấp quyền truy cập. Widget TradingView chỉ để xem, không nối với logic quyết định.

## 6. Cấm tuyệt đối

- Không dùng, không khuyến nghị scraping không chính thức TradingView, gồm WebSocket không chính thức, screen scraping, bot trình duyệt, hay thư viện không chính thức lấy dữ liệu chart. Điều khoản của TradingView cấm thu thập dữ liệu tự động và có thể dẫn tới khóa tài khoản.
- Không đưa dữ liệu TradingView vào pipeline quyết định, replay, hay kiểm định của xau-edge.
- Không phân phối lại dữ liệu TradingView.

## Nguồn

- https://www.tradingview.com/free-charting-libraries/
- https://www.tradingview.com/lightweight-charts/
- https://www.tradingview.com/charting-library-docs/latest/getting_started/Frequently-Asked-Questions/
- https://www.tradingview.com/charting-library-docs/latest/connecting_data/
- https://www.tradingview.com/widget/
- https://www.tradingview.com/policies/
- https://www.tradingview.com/support/solutions/43000710585-why-do-the-values-on-the-tradingview-intraday-charts-differ-from-other-sources/
- https://www.tradingview.com/support/solutions/43000739323-how-does-the-source-of-real-time-data-affect-the-trading-experience/
- https://www.tradingview.com/support/solutions/43000690949-the-price-on-my-chart-differs-from-the-price-in-the-watchlist/
- https://ftmo.com/en/faq/what-are-the-account-specifications/
- https://ftmo.com/en/faq/which-platforms-can-i-use-for-trading/
- https://ftmo.com/en/trading-platforms/
