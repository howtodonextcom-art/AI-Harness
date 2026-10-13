# Bóc tách, kiểm chứng và phản biện 123 file ảnh (104 gốc + bổ sung ở `Image/` và `Image/1/`; xem mục G–J), 107 mã băm độc nhất

Ngày: 2026-10-12 · Dữ liệu kiểm chứng: XAUUSD H1 của dự án (MT5), 132.253 nến, 2004-06-11 → 2026-10-12 13:00 UTC · Phạm vi: phân tích tri thức, không phải tín hiệu mua/bán.

## A. Tóm tắt điều hành

- **104 ảnh, 15 cặp trùng tuyệt đối (so mã băm MD5): ảnh #036–#050 lặp lại ở #051–#065.** Còn 89 file độc nhất. Do nhiều ảnh là khung hình của cùng một video (ví dụ #091–#094, #102–#104, #080–#087), nội dung thực chỉ khoảng 48 bài/video của khoảng 30 tài khoản.
- Toàn bộ là ảnh chụp màn hình Facebook Reels/bài đăng. **Không ảnh nào có dữ liệu thống kê** (không có số lệnh, không có điều kiện, không có chi phí). Phần lớn là infographic vẽ tay hoặc do AI tạo, với ví dụ chọn sau khi biết kết quả.
- Khoảng 35/104 ảnh (≈ 1/3, tính cả bản sao) có yếu tố bán hàng (e-book, sách, Telegram, chỉ báo "độc quyền", quảng cáo sàn). Danh sách ở mục B.
- **Tôi đã kiểm chứng bằng dữ liệu thật** các khẳng định có thể lượng hóa. Kết quả:

| Khẳng định trong ảnh | Kết quả kiểm chứng trên XAUUSD H1 |
|---|---|
| Fibonacci 78,6–88,6% là vùng "xác suất rất tốt"; 38,2% "xác suất thấp"; 61,8% "bị thao túng" (#001, #068) | **Không được ủng hộ.** Không mức nào vượt random-walk. Mức 38,2–61,8% còn thấp hơn kỳ vọng ngẫu nhiên (z từ −2,9 đến −4,9). Mức 88,6% có kết quả tốt ở giai đoạn dev nhưng không lặp lại ở val. |
| Mẫu hình nến (engulfing, sao mai/hôm, hammer, harami, …) cho tín hiệu mua/bán (#002, #046, #078–#079, #100–#101, …) | **Không được ủng hộ.** Không mẫu hình nào có lợi thế theo hướng nhà đăng khẳng định. Sao mai và sao hôm có kết quả *ngược* hướng sau 1 nến, nhưng độ lớn rất nhỏ (xem mục C3). |
| EMA 200 trên/dưới = tăng/giảm; EMA cắt nhau, pullback EMA50 (#036, #067) | **Không được ủng hộ như tín hiệu vào lệnh.** Giá nằm dưới EMA200 vẫn có lợi suất dương trung bình vì vàng tăng mạnh trong giai đoạn này. |
| Double Top/Bottom bán/mua khi phá neckline (#088, #095, #045, #044) | **Không có lợi thế** (N = 607 lệnh, thắng 58,0% so với 60,0% kỳ vọng; E[R] = −0,04 trước phí). |
| "Tỷ lệ thắng 80–83%" trong ảnh quảng cáo chỉ báo vàng (#070) | **Không kiểm chứng được và không hợp lý nếu là tỷ lệ thắng thật** với TP1 = 1R: vào lệnh ngẫu nhiên có xác suất ≈ 50%. |
| Quy tắc rủi ro 1–2%/lệnh, luôn có SL, R:R ≥ 1:2, công thức position size (#003–#005, #038, #041–#042) | **Đúng về mặt toán học và đáng giữ**, nhưng đây là bảo toàn vốn, không phải lợi thế giao dịch. "Backtest 50–100 lệnh" là quá ít (mục C6). |
| Bảng lot theo vốn cho XAUUSD (#076) | **Nguy hiểm.** Bảng ngụ ý đòn bẩy ≈ 41,7 lần; SL 34,54 USD sẽ mất ≈ 34,5% vốn (mục C7). |

- Các khái niệm ICT/SMC (liquidity sweep, FVG, order block, BOS/CHoCH, premium/discount; #047, #080–#087, #097–#099) **chưa kiểm chứng được** ở dạng ảnh vì định nghĩa mang tính chủ quan. Cần được hình thức hóa thành quy tắc có thể mã hóa trước khi test (mục E).

## B. Kiểm kê ảnh

Chỉ số #NNN là thứ tự tăng dần theo tên file; "ID" là 13 chữ số đầu của tên file (ví dụ `1791813618468_…`). ⚑ = có yếu tố bán hàng/quảng cáo.

| # (ID đầu) | Chủ đề | Nguồn hiển thị | Cờ / ghi chú |
|---|---|---|---|
| 001 (…618468) | "Fibonacci Secrets": 38,2% thấp, 61,8% tốt/"manipulated", 78,6–88,6% rất tốt (vùng bán) | Nitin Sharma | Không có số liệu |
| 002 (…618491) | Lưới 16 mẫu: nến + S/R → MUA/BÁN | Tradewiser Academy | Không có thống kê |
| 003–005 (…618507, …521, …533) | Lộ trình Price Action 10 bước; "dấu hiệu rủi ro quá mức"; lộ trình giao dịch 9 bước (rủi ro ≤1%, backtest 50–100+ lệnh) | Servesh Dubey | Quy tắc chung đúng hướng |
| 006–011 (…618544 … …585) | "New Trader vs Pro Trader": Pro dùng kênh xu hướng + vùng thanh khoản | Tristan Ford | 6 khung hình cùng video |
| 012–022 (…618593 … …663) | Cùng video: người mới dùng H&S/cờ/kênh rồi bị quét SL | Tristan Ford | 11 khung hình; một ví dụ chọn lọc |
| 023 (…618669) | Kế hoạch tuần XAUUSD 12–16/10: bán ~4210, SL ~4230,5, TP 4190/4170/4150 | Apex Gold FX | Có thể đối chiếu dữ liệu (mục C8) |
| 024 (…618677) | 12 khái niệm price action ("master these = 100% clear") | A Ashu | Hứa hẹn quá mức |
| 025 (…618684) | 7 điều trước khi giao dịch (R:R 1:3, backtest 100–200 lệnh) | Trading Vlogs | |
| 026 (…618691) | Sách "Black Book of Forex Trading" ("có lãi trong 4 tháng") | Online Bookshop | ⚑ |
| 027–035 (…618698 … …752) | 10 cuốn sách forex hay nhất (chỉ bìa sách) | Online Bookshop | ⚑ không có nội dung kiểm chứng |
| 036 (…618759) | Chiến lược EMA cross (50, 5-8-13, 200, 20, 8-14, 50-200) + "comment CALCULATOR" | A Ashu | ⚑ Có ghi "không phải lời khuyên đầu tư" |
| 037 (…618767) | 9 sai lầm tâm lý và cách tránh | Servesh Dubey | Trùng #052 |
| 038 (…618774) | Công thức position size | Servesh Dubey | Ví dụ bằng INR cổ phiếu |
| 039 (…618781) | Khung thời gian: Monthly → 1m ("1m chỉ cho người có kinh nghiệm") | Shubham Mali | |
| 040–041 (…618789, …796) | Lộ trình đa khung thời gian 1D→4H→15M; 9 quy tắc vàng quản lý rủi ro | Servesh Dubey | |
| 042 (…618803) | "One note every trader should save" + checklist | Trading Monastery | |
| 043–044 (…618811, …817) | Sơ đồ S/R–breakdown–retest; ví dụ consolidation/fakeout | (không rõ) / Lagomtrader | ⚑ "buy trading e-book link in bio" |
| 045 (…618824) | Vai đầu vai / hai đỉnh / S&R = điểm SELL | ATFX Vietnam | ⚑ Được tài trợ (quảng cáo sàn/chỉ báo) |
| 046 (…618831) | 11 mẫu nến đơn (bảng Hindi + English) | Trading with gs | |
| 047 (…618838) | Bảng thuật ngữ SMC/ICT | Chart Lab | Lỗi chính tả: "Fair Valve Gap", "Mane Threshold" |
| 048 (…618845) | Phân tích đa khung 4H→1H→15M→5M | MrTrader NK | Ví dụ chỉ có chiều mua |
| 049–050 (…618852, …858) | Hoạt ảnh Evening Star | Trade4Wealth_India | #049 mũi tên chấm chấm chỉ lên, trái với tên mẫu |
| 051–065 | **Bản sao tuyệt đối của #036–#050** | — | MD5 trùng |
| 066 (…664440) | Biến thể Evening Star (bấc trắng) | Trade4Wealth_India | |
| 067 (…664446) | "Top 7 indicators": BB, MACD, RSI, EMA 200/50/9/21 | Trade4Wealth_India | ⚑ Có số liên hệ trong ảnh. "50 EMA = Stop Loss point" là khẳng định đáng ngờ |
| 068 (…664453) | 4 chiến lược mua: structure retest 0,618; Fib 0,5/0,618; demand; break block | Mananjay Capital | Bình luận cố định có cảnh báo "Don't invest your hard earned money…" |
| 069 (…664460) | "SMC trade setup" 7/10 trên SENSEX (5 phút) | Bharat Sky | Không phải XAUUSD; vẽ sau khi biết kết quả |
| 070 (…664467) | Màn hình XAUUSD: lệnh SELL 4159,86; SL 4194,4; TP1/2/3 4125,32/4090,79/4056,25; bảng "348 lệnh, mục tiêu 80–83%" | Vip Gold Trading | ⚑ Được tài trợ; "chỉ báo độc quyền" |
| 071 (…664473) | "Backtesting trades – updated SL/TP and alerts" (màn hình mờ) | Forex Gold Algorithm | Không đọc được số liệu |
| 072 (…664480) | Tín hiệu mua "Alpha/Beta", mẫu hình Hai Đỉnh, @1,15350 T/P 1,15750 S/L 1,15250 | TOPONE Markets | ⚑ Được tài trợ (sàn/AI) |
| 073–075 (…664487, …493, …499) | Triple Bottom: quy tắc + ví dụ + hai kịch bản vào lệnh | Traders Notes | ⚑ "Trading book link in bio" |
| 076 (…664506) | Bảng XAUUSD (tiếng Tây Ban Nha): vốn → lot → lãi khi chạy 10 pip | Alvaro Alfonso | ⚑ Telegram; nhãn "nội dung do AI tạo" |
| 077 (…664512) | 3 kiểu vào lệnh: limit, nến xác nhận, pullback structure | Rahul Singh | |
| 078 (…664519) | 6 cặp mẫu nến bullish/bearish | Mrr Daady (@trade_notebook) | **Lỗi**: Inverted Hammer xếp bên bearish (xem C3) |
| 079 (…664525) | 30 mẫu nến quan trọng (sổ viết tay) | Crezystocks | |
| 080–087 (…679331 … …424) | Loạt 8 slide ICT/SMC tiếng Việt: công thức 7 bước, TP, chọn FVG/OB, BOS/CHoCH, displacement, thanh khoản, swing, quy trình | #ongdotradingpro | Đồ họa kiểu AI; không dữ liệu |
| 088 (…707737) | Double Top (SNR, trendline, wick rejection, risk/reward) | School of Trade | ⚑ Được tài trợ (phần 1/2) |
| 089 (…707766) | XAUUSD H4 trên MT5: SELL 0,03 lot, "TP 100 pips", Stoch(8,3,3) | trading Gold | Không có kết quả |
| 090 (…707782) | "Learn it. Don't guess": bearish order block + FVG + BOS + SSL | School of Trades | ⚑ Được tài trợ |
| 091–094 (…707795, …808, …819, …829) | Mẫu ABC trong kênh giá (bán tại C, mua tại C) | Стратегии форекс | ⚑ Telegram; biểu đồ năm 2015 và 2023 |
| 095 (…707838) | Double Top (cùng nội dung #088) | Academy School of Trades | ⚑ Được tài trợ |
| 096–097 (…707846, …853) | Liquidity Sweep; "5 khái niệm SMC … không gì ngăn bạn có lãi" | Dheeraj.trades | Hứa hẹn quá mức |
| 098–101 (…707860 … …881) | Time-frame analysis; trading patterns; top 16 mẫu nến; candlestick explained | Mananjay Capital | #101 liệt kê "Bullish Doji" hai lần |
| 102–104 (…707888, …895, …902) | Chiến lược đường xu hướng 3 điểm chạm (mua/bán), "2 Profits Taken" | Стратегии форекс | ⚑ Ví dụ chọn lọc |

**Mâu thuẫn giữa các ảnh:**
1. Inverted Hammer là tín hiệu **mua** (#046, #079, #100) nhưng là tín hiệu **bán** ở #078 (mẫu giảm giá cùng hình dạng đúng ra là Shooting Star).
2. #001 xem 38,2% là "xác suất thấp"; #068 coi vùng 0,5/0,618 là vùng mua ưu tiên; #047/#080 dùng premium/discount 50%. Ba cách tiếp cận khác nhau về vùng tốt.
3. #006 xem kênh xu hướng là cách "chuyên nghiệp"; #044, #045, #088, #095 dạy chính các mẫu cổ điển (đỉnh đôi, vai đầu vai) mà #012–#022 bảo là "không còn hiệu quả".
4. Doji là mẫu trung tính ở #046 ("Indecision"), nhưng #101 gán nhãn "Bullish Doji"/"Bearish Doji" và còn lặp "Bullish Doji" hai lần.

## C. Kiểm chứng và phản biện theo chủ đề

### C0. Phương pháp (chung cho mọi phép thử)

- Dữ liệu: XAUUSD H1, 132.253 nến, tách **dev (trước 2019)** và **val (từ 2019)**. Mọi kết quả đều báo cả hai.
- Baseline luôn là baseline cùng bối cảnh: random-walk (xác suất chạm mục tiêu trước SL = khoảng cách tới SL ÷ tổng khoảng cách) hoặc nền cùng bối cảnh cho lợi suất tiến.
- Lợi suất được chuẩn hóa theo ATR(14) của H1 tại thời điểm tín hiệu, để so sánh được giữa năm 2005 (vàng ~$500) và 2026 (vàng ~$4.100).
- Nhiều phép thử → **hiệu chỉnh Bonferroni**: 14 mẫu hình × 3 độ dài = 42 phép thử → ngưỡng |t| ≈ 3,24. Lợi suất chồng lấn nên t của h = 4 và 12 được chia thêm √h.
- Không có look-ahead: pivot cần 5 nến để xác nhận; chỉ vào lệnh sau xác nhận; mức bị phá trong thời gian chờ xác nhận bị loại.
- Chi phí chưa trừ trong E[R]. Spread trung vị từ 2025 là 24 điểm (≈ 0,24 USD), nhỏ so với SL kiểu 34,54 USD nhưng không nhỏ so với hiệu ứng 0,1 ATR (mục C3).
- Mã nguồn và kết quả thô: `docs/reports/image_claims_verification/`.

**Lỗi thiết kế tôi đã gặp và sửa trong lúc làm.** Bản đầu của phép thử Fibonacci cho kết quả thấp hơn kỳ vọng ở mọi mức (z ≈ −47). Nguyên nhân là tôi giả định vào lệnh đúng tại mức, trong khi pivot cần 5 nến để xác nhận nên nhiều mức đã bị phá trước đó, và nến chạm mức thường đóng dưới mức. Phiên bản cuối vào lệnh tại giá đóng cửa nến chạm mức, loại mức đã bị phá trong thời gian chờ, và so với kỳ vọng random-walk tính từ chính giá vào đó. Nếu bạn thấy phương pháp nào vẫn còn thiên lệch, xin nói để tôi sửa tiếp.

### C1. Fibonacci (#001, #068, #047, #080)

**Khẳng định:** vùng 78,6–88,6% là "very good probability", 61,8% "bị thao túng", 38,2% "low probability" (#001). #068: hồi về 0,5/0,618 rồi "rejection and continuation".

**Phép thử:** với mỗi chân sóng (pivot đáy → pivot đỉnh, biên độ ≥ 2 ATR; và đối xứng cho chân giảm), khi giá hồi về mức r lần đầu sau khi pivot được xác nhận: vào lệnh tại giá đóng của nến chạm mức, SL tại đầu kia của chân sóng, mục tiêu là đỉnh cũ. Kỳ vọng random-walk: P = (giá vào − SL) ÷ biên độ. Nhóm "rejection" là các nến chạm mức nhưng đóng cửa phía trên mức (đúng nghĩa "phản ứng tại mức").

| Mức | N (chạm) | P thực | P null | z | E[R] | z dev / val | N (rejection) | P thực | P null | z | E[R] |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 38.2% | 1251 | 53.7% | 60.3% | -4.88 | -0.109 | -4.61 / -1.96 | 605 | 61.5% | 68.1% | -3.52 | -0.098 |
| 50.0% | 1877 | 44.7% | 49.3% | -4.14 | -0.079 | -3.52 / -2.20 | 930 | 50.6% | 57.7% | -4.40 | -0.128 |
| 61.8% | 2355 | 36.4% | 39.1% | -2.86 | -0.052 | -2.09 / -1.98 | 1258 | 43.5% | 47.7% | -3.05 | -0.092 |
| 78.6% | 2424 | 25.6% | 26.3% | -0.81 | +0.040 | +0.59 / -2.10 | 1504 | 30.6% | 32.8% | -1.85 | -0.044 |
| 88.6% | 1867 | 20.8% | 19.8% | +1.13 | +0.213 | +2.49 / -1.37 | 1406 | 23.8% | 23.6% | +0.09 | +0.008 |

*(P = tỷ lệ chạm lại đỉnh cũ trước khi phá đáy; z so với P null; E[R] chưa tính phí; các chân sóng của các mức khác nhau không độc lập.)*

**Kết luận:** khẳng định **không được ủng hộ**. Không mức nào có P vượt kỳ vọng ngẫu nhiên một cách bền vững. Các mức 38,2%, 50% và 61,8% có P *thấp hơn* ngẫu nhiên (z từ −2,9 đến −4,9), nghĩa là sau khi chạm các mức nông, chân sóng có xu hướng hỏng nhiều hơn mức ngẫu nhiên. Mức 88,6% ở giai đoạn dev có z = +2,49 (E[R] = +0,41) nhưng val là −1,37 (E[R] = −0,11): kết quả không lặp lại. Nhóm "rejection" cũng không khá hơn.

**Phản biện:**
- Điểm hợp lý: "mức sâu hơn có R:R lớn hơn" là đúng về hình học, nhưng điều đó đã được bù trừ bằng xác suất thấp hơn (P null) nên kỳ vọng vẫn ≈ 0. "Xác suất" trong ảnh có thể đang bị hiểu nhầm giữa "xác suất giá phản ứng" và "kỳ vọng lợi nhuận".
- Ví dụ trong #001 là một chân giảm vẽ sau khi biết kết quả (vùng bán đúng đỉnh hồi). Đó là thiên kiến chọn mẫu.
- Hạn chế của phép thử của tôi: một định nghĩa pivot (k = 5 nến H1), một ngưỡng biên độ (2 ATR), một khung thời gian. Khung H4/D1 hoặc định nghĩa swing khác chưa thử. Kết luận đúng là **"không thấy bằng chứng trong định nghĩa này"**, chưa phải "Fibonacci vô dụng trong mọi định nghĩa".
- Độ tin cậy kết luận: **trung bình–cao** (N = 1.251–2.424 mỗi mức ở nhóm chạm mức, cùng chiều ở cả dev và val cho các mức nông).

### C2. Đa khung thời gian "top-down" (#003, #040, #048, #098, #039)

**Khẳng định:** xác định xu hướng ở khung lớn (D/4H), tìm vùng ở khung trung, vào lệnh theo hướng khung lớn ở khung nhỏ.

**Kiểm chứng:** phần "đi theo xu hướng lớn" được thử gián tiếp qua bộ lọc EMA200 (mục C4): giá trên EMA200 có lợi suất tiến cao hơn dưới EMA200, nhưng độ chênh nhỏ và không vượt ngưỡng Bonferroni (t hiệu chỉnh = +2,2 ở 12 nến). Phần SMC của #048 (sweep → CHoCH → FVG → entry) chưa kiểm chứng được vì chưa có định nghĩa máy đọc được.

**Phản biện:** ý tưởng chia vai trò theo khung thời gian là hợp lý về mặt quy trình, nhưng các ví dụ đều là minh họa chiều mua, chọn sau khi biết kết quả. Không có số liệu so sánh "có lọc HTF" với "không lọc". Độ tin cậy: **thấp (chưa kiểm chứng)**.

### C3. Mẫu hình nến (#002, #046, #078, #079, #100, #101, #049–#050, #066)

**Khẳng định:** mỗi mẫu hình là tín hiệu mua/bán, hoặc đảo chiều/tiếp diễn.

**Phép thử:** 14 mẫu hình (bullish/bearish engulfing, hammer, hanging man, inverted hammer, shooting star, morning/evening star, three white soldiers/black crows, piercing line, dark cloud cover, harami, tweezer top/bottom). Mỗi mẫu hình đòi hỏi bối cảnh xu hướng 5 nến trước (≥ 0,5 ATR) trừ ba lính/ba quạ. Lợi suất tiến 1/4/12 nến nhân với hướng tín hiệu, so với nền *cùng bối cảnh* nhưng không có mẫu hình (loại trừ hiệu ứng của chính bối cảnh).

| Mẫu hình (hướng tín hiệu) | N | h=1: Δ ATR (t) | h=4: Δ ATR (t) | h=12: Δ ATR (t) | h=1 dev / val (t) |
|---|---|---|---|---|---|
| bearish_engulfing(-1) | 3656 | -0.017 (-1.05) | +0.015 (+0.25) | +0.060 (+0.38) | -2.07 / 0.94 |
| bearish_harami(-1) | 2074 | -0.012 (-0.56) | +0.000 (+0.00) | +0.039 (+0.19) | -0.28 / -0.6 |
| bullish_engulfing(+1) | 3555 | -0.052 (-3.08) | -0.093 (-1.50) | -0.017 (-0.10) | -3.29 / -0.71 |
| bullish_harami(+1) | 1936 | -0.008 (-0.38) | -0.002 (-0.03) | -0.007 (-0.03) | -0.25 / -0.35 |
| dark_cloud_cover(-1) | 69 | -0.085 (-0.81) | -0.018 (-0.05) | +0.063 (+0.04) | -1.65 / 0.7 |
| evening_star(-1) ** | 1076 | -0.102 (-3.93) | -0.120 (-1.19) | -0.255 (-0.96) | -4.23 / -0.84 |
| hammer(+1) | 2897 | +0.005 (+0.30) | -0.001 (-0.02) | +0.015 (+0.08) | 0.49 / -0.23 |
| hanging_man(-1) | 2570 | +0.037 (+1.81) | +0.019 (+0.26) | -0.032 (-0.16) | 1.82 / 0.49 |
| inverted_hammer(+1) | 2311 | -0.003 (-0.15) | -0.006 (-0.08) | +0.071 (+0.33) | 0.3 / -0.75 |
| morning_star(+1) ** | 1126 | -0.100 (-3.76) | -0.138 (-1.33) | -0.404 (-1.58) | -3.08 / -2.17 |
| piercing_line(+1) | 82 | +0.181 (+1.05) | +0.220 (+0.55) | +0.034 (+0.02) | 0.68 / 1.49 |
| shooting_star(-1) | 2615 | -0.013 (-0.76) | -0.034 (-0.47) | -0.046 (-0.24) | -0.48 / -0.6 |
| three_black_crows(-1, claimed continuation) | 1840 | -0.057 (-2.31) | -0.030 (-0.34) | +0.033 (+0.14) | -1.84 / -1.48 |
| three_white_soldiers(+1, claimed continuation) | 1933 | -0.043 (-2.27) | -0.074 (-1.00) | -0.004 (-0.02) | -2.26 / -0.69 |
| tweezer_bottom(+1) | 2488 | -0.044 (-2.14) | -0.022 (-0.34) | +0.003 (+0.01) | -1.53 / -1.57 |
| tweezer_top(-1) | 3056 | +0.013 (+0.70) | +0.047 (+0.80) | +0.150 (+0.86) | 0.69 / 0.22 |

*(Δ ATR = lợi suất trung bình theo hướng tín hiệu của mẫu hình trừ nền cùng bối cảnh; dương = đúng hướng ảnh khẳng định; ** = có |t| ≥ 3,24, vượt Bonferroni.)*

**Kết luận:** **không mẫu hình nào có lợi thế theo hướng khẳng định**. Hai mẫu vượt ngưỡng Bonferroni nhưng theo hướng *ngược lại*: sao hôm (Δ = −0,10 ATR, t = −3,93) và sao mai (Δ = −0,10 ATR, t = −3,76) sau 1 nến, nghĩa là giá có xu hướng đi ngược tín hiệu ở nến kế tiếp. Bullish engulfing cũng nghiêng ngược nhưng chỉ cận ngưỡng (t = −3,08). Ở giai đoạn val, hiệu ứng sao hôm không còn ý nghĩa (t = −0,84); sao mai vẫn âm (t = −2,17).

**Phản biện:**
- Hiệu ứng ngược ≈ 0,1 ATR ≈ 0,4 USD (ATR H1 trung vị cả giai đoạn ≈ 3,8 USD) đến 2,2 USD (ATR H1 trung bình 250 ngày gần nhất ≈ 21,7 USD), so với spread trung vị ≈ 0,24 USD từ 2025. Nghĩa là không đủ để khai thác và không nên suy diễn "ngược" thành chiến lược. Chỉ nên đọc là "không có lợi thế theo hướng khẳng định".
- Định nghĩa mẫu hình của tôi là một cách hiện thực hóa cụ thể; các sách có biến thể khác (ngưỡng bấc, thân nến). Số mẫu hình hiếm (piercing line N = 82, dark cloud N = 69) quá nhỏ để kết luận.
- Hầu hết sách giáo khoa đều dặn dùng mẫu hình nến *cùng* S/R và xác nhận (#002, #078 có ghi "Always use with Support, Resistance & Risk Management"). Phép thử này kiểm tra mẫu hình một mình trong bối cảnh xu hướng 5 nến, **chưa** kiểm tra kết hợp với S/R.
- Lỗi trong chính ảnh: Inverted Hammer ở #078 bị xếp bên bearish; "Bullish Doji" lặp hai lần ở #101; doji được dán nhãn bullish/bearish trong khi là mẫu trung tính (#046 đúng, #101 sai).
- Độ tin cậy kết luận: **cao** với các mẫu hình phổ biến (N > 1.000), **thấp** với piercing và dark cloud.

### C4. EMA (#036, #067, #003)

**Khẳng định (#036):** EMA 200: giá trên = tăng, dưới = giảm; pullback về EMA50 trong xu hướng tăng = mua; EMA 5-8-13, 8-14, 20 cho tín hiệu vào lệnh; golden cross 50/200 = đảo chiều dài hạn. #067: EMA50 làm "điểm dừng lỗ"; EMA 21 "điểm vào/ra chính xác".

**Phép thử:** lợi suất tiến (ATR) theo hướng tín hiệu so với nền.

| Thử nghiệm | h=12 | h=24 | h=120 |
|---|---|---|---|
| Close>EMA200: ret TB (ATR) | +0.167 | +0.319 | +1.426 |
| Close<EMA200: ret TB (ATR) | +0.054 | +0.076 | +0.499 |
| Chênh lệch trên-dưới (t hiệu chỉnh) | +0.113 (+2.20) | +0.243 (+2.39) | +0.927 (+1.72) |
| Pullback EMA50 mua (so với nền xu hướng tăng) — N=6428; Δ ATR (t) | -0.204 (-1.57) | -0.105 (-0.40) | +0.026 (+0.02) |
| Pullback EMA50 bán (so với nền xu hướng giảm) — N=5294; Δ ATR (t) | -0.116 (-0.87) | +0.106 (+0.38) | +0.133 (+0.09) |
| Cắt lên 8/14 — N=4018; Δ ATR (t) | -0.203 (-1.34) | -0.146 (-0.48) | -0.122 (-0.07) |
| Cắt xuống 8/14 (tín hiệu bán) — N=4018; Δ ATR (t) | -0.107 (-0.68) | +0.015 (+0.05) | -0.030 (-0.02) |
| Cắt lên 9/21 — N=3029; Δ ATR (t) | -0.163 (-0.93) | -0.113 (-0.33) | -0.144 (-0.08) |
| Cắt xuống 9/21 (bán) — N=3029; Δ ATR (t) | -0.174 (-0.98) | -0.036 (-0.10) | -0.019 (-0.01) |
| Cắt lên 20/50 — N=1286; Δ ATR (t) | -0.191 (-0.76) | -0.199 (-0.39) | +0.167 (+0.06) |
| Cắt xuống 20/50 (bán) — N=1286; Δ ATR (t) | -0.086 (-0.34) | +0.027 (+0.05) | -0.024 (-0.01) |
| Golden cross 50/200 — N=378; Δ ATR (t) | -0.057 (-0.14) | -0.068 (-0.08) | -0.023 (-0.00) |
| Death cross 50/200 (bán) — N=379; Δ ATR (t) | +0.142 (+0.31) | +0.228 (+0.26) | +0.818 (+0.15) |

*(Δ = trung bình theo hướng tín hiệu trừ nền; với EMA200 là chênh lệch trên − dưới; t hiệu chỉnh √h.)*

**Kết luận:** **không có lợi thế vào lệnh** từ các tín hiệu cắt EMA hay pullback EMA50 (mọi |t| < 1,6). Với EMA200: trong dữ liệu này giá nằm *dưới* EMA200 vẫn có lợi suất tiến dương (+0,05 đến +0,5 ATR) vì vàng ở trong xu hướng tăng dài hạn (2004–2026). Câu "dưới EMA200 = bearish" không đúng theo nghĩa lợi suất kỳ vọng âm.

**Phản biện:** lợi suất của gần mọi tín hiệu *mua* bị nâng bởi xu hướng tăng của vàng nên bắt buộc phải so với nền (tôi đã làm vậy). Ảnh #067 dùng EMA50 làm "SL" mà không nói về khoảng cách: SL đặt trên đường động có thể quá gần (bị quét) hoặc quá xa (R:R xấu). Độ tin cậy: **trung bình–cao**.

### C5. Double Top/Bottom và các mẫu hình giá (#088, #095, #045, #044, #073–#075, #091–#094, #102–#104)

**Khẳng định:** hai đỉnh cùng mức rồi phá neckline là tín hiệu bán, mục tiêu bằng chiều cao mẫu hình; tương tự cho Triple Bottom.

**Phép thử (Double Top/Bottom):** hai pivot (k = 5) lệch ≤ 0,5 ATR, cách nhau 8–60 nến, chiều sâu tới neckline ≥ 1,5 ATR; vào lệnh khi nến đóng phá neckline (trong 40 nến, trước khi giá vượt đỉnh); SL tại đỉnh; TP = neckline − chiều cao mẫu hình. Kỳ vọng random-walk tính theo từng lệnh từ khoảng cách SL/TP thực tế.

| Giai đoạn | N | Thắng thực | Thắng kỳ vọng (random-walk) | z | E[R] (chưa phí) |
|---|---|---|---|---|---|
| all | 607 | 58.0% | 60.0% | -1.05 | -0.042 |
| dev | 375 | 59.7% | 60.1% | -0.16 | -0.015 |
| val | 232 | 55.2% | 59.9% | -1.49 | -0.087 |

**Kết luận:** **không có lợi thế**. Tỷ lệ thắng thực (58,0%) hơi thấp hơn kỳ vọng ngẫu nhiên (60,0%). E[R] ≈ −0,04 trước phí; ở val là −0,09. Median R:R ≈ 0,77 nên tỷ lệ thắng cần ≈ 56% mới hòa vốn trước phí.

**Phản biện:** đây chỉ là một cách tự động hóa; nhà giao dịch thật dùng thêm S/R, thanh khoản, khung lớn. Triple Bottom, ABC, đường xu hướng 3 điểm chạm, vai đầu vai **chưa kiểm chứng** vì cần vẽ đường chủ quan. Các ví dụ trong ảnh có vẻ chọn lọc: #091–#094 là hai ví dụ năm 2015 và 2023, #102–#104 là hai ví dụ có lãi ("2 Profits Taken"), không có ví dụ thua. Độ tin cậy: **trung bình** (đúng cho Double Top/Bottom, chưa kiểm chứng cho mẫu còn lại).

### C6. Quản lý rủi ro và quy mô mẫu backtest (#003–#005, #025, #038, #041–#042, #004)

**Khẳng định:** rủi ro 1–2%/lệnh, luôn đặt SL, R:R ≥ 1:2, công thức `Position size = Rủi ro tài khoản ÷ |Entry − SL|`, backtest "50–100+ lệnh" (#005), "100–200 lệnh" (#025).

**Kiểm chứng (toán học):**
- Công thức position size **đúng**. Với XAUUSD cần nhân hệ số hợp đồng (1 lot = 100 oz): rủi ro 100 USD, SL 34,54 USD → 0,029 lot.
- R:R ≥ 1:2 cần tỷ lệ thắng hòa vốn ≥ 33,3% (trước phí). Đúng, nhưng R:R lớn không tạo lợi thế nếu xác suất đạt mục tiêu giảm tương ứng (kết quả mục C1, C8: random-walk có E[R] = 0 ở mọi R:R).
- Chuỗi thua: 10 lệnh thua liên tiếp ở rủi ro 1% mất 9,6% vốn; ở rủi ro 10% mất 65,1% (#004 nói đúng rằng 10% là quá mức).
- **Quy mô mẫu:** với 50 lệnh, khoảng tin cậy 95% của tỷ lệ thắng rộng ±13,9 điểm %; 100 lệnh ±9,8 điểm %; 200 lệnh ±6,9 điểm %. Để phân biệt tỷ lệ thắng 55% với 50% (α = 0,05, power 0,8) cần ≈ 783 lệnh.

**Phản biện:** các quy tắc này là bảo toàn vốn và kỷ luật, đáng giữ, nhưng chúng **không tạo ra lợi thế**. Việc "backtest 50–100 lệnh" nghe an toàn nhưng không đủ để phát hiện lợi thế vừa phải; kết quả tốt trên mẫu nhỏ chủ yếu là may. Các phép thử ở báo cáo này dùng hàng trăm đến hàng nghìn sự kiện mỗi phép thử. Độ tin cậy: **cao**.

### C7. Bảng lot XAUUSD (#076)

**Khẳng định:** vốn $100 → 0,01 lot; $1.000 → 0,10 lot; $10.000 → 1,00 lot; $100.000 → 10 lot; "10 pip = $1 trên 0,01 lot"; "Más capital ≠ más riesgo".

**Kiểm chứng:**
- Giá trị pip đúng (1 pip = 0,10 USD, 0,01 lot = 1 oz → 10 pip = 1 USD).
- Bảng tương đương **1 lot cho mỗi $10.000**, tức mỗi 1 USD giá chạy = **1% vốn**. Với giá 4.171,53 (nến H1 cuối của dữ liệu), 1 lot = 100 oz ≈ 417.153 USD, đòn bẩy ≈ **41,7 lần**.
- Biên độ ngày của vàng 250 ngày gần nhất: trung bình ≈ 106 USD, trung vị ≈ 88 USD (p10 ≈ 28, p90 ≈ 185). Với bảng này, một ngày giá chạy trung vị tương đương **≈ 88% vốn**.
- Theo quy tắc 1% rủi ro với SL 34,54 USD (như ảnh #070), cỡ lệnh đúng là **≈ 0,029 lot cho $10.000**, tức bảng lớn hơn ≈ 34 lần.

| SL (USD) | Mất khi dùng 1 lot/$10k | Lot cho rủi ro 1% trên $10k |
|---|---|---|
| 5 | 5,0% | 0,200 |
| 10 | 10,0% | 0,100 |
| 20 | 20,0% | 0,050 |
| 34,54 | 34,5% | 0,029 |
| 60 | 60,0% | 0,017 |

**Phản biện:** tiêu đề ảnh hỏi "Tôi có đang rủi ro quá nhiều?" nhưng chính bảng trả lời ngược lại: nó cho cỡ lệnh rất lớn mà không nói SL. Câu "vốn lớn hơn ≠ rủi ro lớn hơn" chỉ đúng nếu lot được tính từ SL, điều mà bảng không làm. Ảnh có nhãn "nội dung do AI tạo" và kèm Telegram bán hàng. Ngoài ra biên độ giá thay đổi mạnh: trung bình biên độ ngày là ≈ 20 USD năm 2015, ≈ 19 USD năm 2019, ≈ 28 USD năm 2024, nhưng ≈ 106 USD trong 250 ngày gần nhất, nên mọi con số "pip" trong ảnh cũ cần chuyển sang đơn vị ATR. Độ tin cậy: **cao** (số học và dữ liệu).

### C8. Lệnh/kế hoạch cụ thể và tỷ lệ thắng quảng cáo (#023, #070, #089, #072, #069)

**#070 (Vip Gold Trading, được tài trợ):** SELL 4159,86; SL 4194,4 (34,54); TP1/2/3 = 4125,32 / 4090,79 / 4056,25, tương ứng đúng 1R/2R/3R. Bảng ghi "tổng lệnh 348, đang chạy 2, mục tiêu 80–83%". Nhãn "mục tiêu" có thể là mục tiêu chứ không phải tỷ lệ thắng thực đạt được; đọc theo cách nào cũng không có bằng chứng.

**Phép thử:** vào lệnh ngẫu nhiên tại mỗi nến H1 từ 2025, SL 34,54 USD, TP bằng 1R/2R/3R, cả mua và bán.

| Mục tiêu (SL = 34,54 điểm) | Mua, vào ngẫu nhiên | Bán, vào ngẫu nhiên | Trung bình mua/bán | Kỳ vọng random-walk |
|---|---|---|---|---|
| TP=1R | 55.5% | 44.1% | 49.8% | 50.0% |
| TP=2R | 42.1% | 27.5% | 34.8% | 33.3% |
| TP=3R | 36.0% | 18.6% | 27.3% | 25.0% |

*(10.512 điểm vào, mỗi nến cho cả mua và bán; hòa trong cùng nến tính là thua.)*

**Kết luận:** vào lệnh ngẫu nhiên có xác suất đạt TP1 ≈ 50% (trung bình mua/bán 49,8%), TP2 ≈ 34,8%, TP3 ≈ 27,3%, rất sát kỳ vọng random-walk. Hướng cũng đáng lưu ý: từ 2025 vàng tăng mạnh nên mua đạt 55,5% và bán chỉ 44,1% ở TP1. Một hệ thống thật sự đạt 80% với TP1 = 1R sẽ cách xa baseline này (z ≈ 11 trên 348 lệnh). Điều đó chỉ khả thi nếu có lợi thế rất lớn, hoặc (thực tế phổ biến hơn) nếu "thắng" được định nghĩa khác: TP1 gần hơn 1R, dời SL về hòa vốn, chốt từng phần, trung bình giá, hoặc chọn lọc kết quả. **Cần số liệu từng lệnh với giờ vào, giờ ra, và cách tính trước khi coi 80–83% là tin được.**

**#023 (Apex Gold FX, kế hoạch 12–16/10):** đối chiếu với dữ liệu của dự án (đến 13:00 UTC ngày 12/10/2026):
- Entry ~4210: giá chạm trong nến 00:00 UTC ngày 12/10 (đỉnh nến 4210,43; đỉnh cao nhất sau đó 4217,03 ở nến 01:00).
- SL ~4230,5: **chưa bị chạm** (đỉnh cao nhất 4217,03).
- TP1 ~4190,3: **đã đạt** (nến 05:00, đáy 4179,14).
- TP2 ~4170,7: **đã đạt** (nến 09:00, đáy 4168,67).
- TP3 ~4150,4: **chưa đạt** (đáy 4154,51, còn thiếu ~4 USD).

Đây là **một** kết quả (n = 1) và đang mở, nên không đủ để đánh giá phương pháp. Cũng cần lưu ý: không biết thời điểm đăng chính xác so với lúc giá chạm entry, và ảnh chụp có thanh crosshair "Tue 13 Oct '26 14:00" nên nó được chụp vào ngày 12/10 hoặc sau. Cần có bản ghi thời điểm đăng để coi là bằng chứng trước-sau.

**#089, #072, #069:** không kết quả (không có đóng lệnh), hoặc không phải XAUUSD (#069 là SENSEX, #072 là cặp ngoại tệ, giá 1,15350). Tôi chỉ xác nhận giá XAUUSD trong #089 (4197,08) là hợp lý với dữ liệu ngày 9/10 (đóng cửa 4195,09, đỉnh 4207,40). Độ tin cậy: **cao** cho phần tỷ lệ thắng ngẫu nhiên; **không kiểm chứng được** cho tuyên bố 80–83%.

### C9. ICT/SMC, thanh khoản, order block, FVG (#047, #080–#087, #090, #097–#099, #069, #077, #048)

**Khẳng định:** thứ tự "bias HTF → cấu trúc → quét thanh khoản → displacement → BOS/CHoCH → FVG/OB ở vùng discount/premium → TP ở vùng thanh khoản". #097: hiểu 5 khái niệm "thì không gì có thể ngăn bạn có lãi".

**Đánh giá:** chưa kiểm chứng được. Các định nghĩa (khi nào là "quét thanh khoản", "displacement", "order block hợp lệ") chủ quan, mỗi tác giả vẽ khác nhau, và mọi ví dụ đều được chọn sau khi biết kết quả. Các điểm đáng ghi nhận:
- Mô tả nhất quán giữa các nguồn, và loạt #080–#087 có những câu cảnh báo đúng chuẩn thực hành: "FVG chạm giá chỉ là một xác nhận" (#085), "đợi xác nhận, tránh FOMO" (#084), "không vào khi các yếu tố chưa hoàn chỉnh" (#080).
- Nhưng chính điều đó làm cho hệ thống khó phản biện: có quá nhiều điều kiện tùy ý, và mọi thất bại đều có thể giải thích là "chưa đủ xác nhận".
- Khẳng định "không gì ngăn bạn có lãi" (#097) là hứa hẹn quá mức, không có bằng chứng.
- #047 có lỗi chính tả ("Fair Valve Gap", "Mane Threshold" thay vì "Mean Threshold", "Reejction").

**Độ tin cậy:** không áp dụng (chưa kiểm chứng); nên xếp **ưu tiên nghiên cứu** nếu bạn muốn, nhưng chỉ sau khi hình thức hóa.

### C10. Ảnh tâm lý, sách và lộ trình học (#006–#022, #024–#035, #037, #039)

- Tâm lý (#037/#052): 9 sai lầm (overtrading, sợ hãi, trả thù, FOMO, giữ lệnh thua, chốt sớm, thiếu kế hoạch, tự tin quá mức, so sánh với người khác) là các lời khuyên chung hợp lý, không có dữ liệu.
- Lộ trình học (#003, #005, #024): hợp lý về quy trình nhưng "master these = 100% clear" (#024) và "profitable in 4 months" (#026) là hứa hẹn quá mức.
- Sách (#027–#035): chỉ có bìa sách, không có nội dung để kiểm chứng. Bìa "Candlestick Trading Bible" khẳng định Homma là "nhà giao dịch thành công nhất lịch sử", chưa có nguồn.
- Tristan Ford (#006–#022): lập luận "mẫu hình cổ điển không còn hiệu quả, thay bằng kênh + thanh khoản" dựa trên **một** ví dụ người mới thua và một ví dụ "chuyên nghiệp" đúng. Không có thống kê; thiên kiến chọn lọc rõ.

## D. Bảng tổng hợp khẳng định

| # | Khẳng định | Ảnh | Trạng thái | Độ tin cậy | Hành động đề xuất |
|---|---|---|---|---|---|
| 1 | Fib 78,6–88,6% xác suất rất tốt; 38,2% thấp; 61,8% bị thao túng | 001, 068 | Kiểm chứng: không ủng hộ | Trung bình–cao | Bỏ khỏi backlog; chỉ thử lại với định nghĩa swing/khung khác |
| 2 | Mẫu hình nến cho tín hiệu mua/bán | 002, 046, 078–079, 100–101 | Kiểm chứng: không ủng hộ | Cao | Bỏ; chỉ dùng như mô tả bối cảnh |
| 3 | EMA200 phân chia xu hướng; EMA cross/pullback cho tín hiệu | 036, 067 | Kiểm chứng: không ủng hộ | Trung bình–cao | Có thể giữ EMA200 làm bộ lọc bối cảnh yếu; không dùng làm tín hiệu |
| 4 | Double Top/Bottom phá neckline | 044–045, 088, 095 | Kiểm chứng: không lợi thế | Trung bình | Bỏ; các mẫu giá khác chưa thử |
| 5 | Top-down đa khung (D/4H → 1H → 15m → 5m) | 003, 040, 048, 098 | Một phần (gián tiếp, yếu) | Thấp | Thử "có/không có lọc HTF" trên hệ thống hiện có |
| 6 | Rủi ro 1–2%, SL, R:R ≥ 1:2, position size | 003–005, 038, 041–042 | Toán học đúng | Cao | Giữ làm nguyên tắc; hệ thống paper của bạn đã áp dụng |
| 7 | Backtest 50–100 lệnh là đủ | 005, 025 | Không đủ về thống kê | Cao | Dùng ≥ vài trăm lệnh và tách dev/val như đã làm |
| 8 | Bảng lot XAUUSD theo vốn | 076 | Nguy hiểm (đòn bẩy ≈ 41,7×) | Cao | Không dùng; tính lot từ SL |
| 9 | Chỉ báo/tín hiệu đạt 80–83% thắng | 070 | Không kiểm chứng được; không hợp lý nếu TP1 = 1R | Cao (phần ngẫu nhiên), không áp dụng (phần tuyên bố) | Yêu cầu nhật ký từng lệnh; không dùng làm cơ sở |
| 10 | Kế hoạch tuần Apex Gold (bán 4210) | 023 | n = 1; entry, TP1, TP2 đạt, TP3 chưa, SL chưa | Không đủ | Theo dõi đến hết tuần; không suy ra phương pháp |
| 11 | ICT/SMC (sweep, FVG, OB, BOS/CHoCH) | 047, 080–087, 090, 097–099 | Chưa kiểm chứng | Không áp dụng | Hình thức hóa rồi thử (mục E) |
| 12 | "Mẫu hình cổ điển không còn hiệu quả" | 012–022 | Chưa kiểm chứng; nguồn là một ví dụ | Thấp | Bỏ qua |
| 13 | Hứa hẹn "không gì ngăn bạn có lãi", "100% rõ ràng", "có lãi trong 4 tháng" | 024, 026, 097 | Không có bằng chứng; ngược với kết quả mục C | Cao | Coi là marketing |

## E. Hạn chế, rủi ro và câu hỏi còn mở

**Hạn chế của chính phân tích này**
1. Một cặp (XAUUSD), một khung (H1), một định nghĩa cho mỗi mẫu hình/pivot. Kết luận chỉ áp dụng cho các định nghĩa này.
2. Lợi suất tiến chồng lấn: tôi đã chia t cho √h nhưng đó là hiệu chỉnh thô, không phải sai số chuẩn bền vững (HAC).
3. Chưa trừ chi phí/spread trong E[R]; ảnh hưởng nhỏ với SL lớn, đáng kể với SL nhỏ (ví dụ SL 5 USD: spread 0,24 USD ≈ 4,8% R).
4. Dữ liệu 2004–2026 chứa một xu hướng tăng mạnh của vàng; mọi chỉ số "mua" có nền dương. Tôi đã so với nền cùng bối cảnh, nhưng không loại bỏ hết ảnh hưởng chế độ thị trường (biên độ ngày trung bình tăng ≈ 3,8 lần từ năm 2024 đến 250 ngày gần nhất).
5. Xử lý nhiều phép thử bằng Bonferroni làm tăng nguy cơ bỏ sót lợi thế nhỏ thật.
6. Phần đọc ảnh: các lô ảnh #001–#035 ban đầu được trả về với lỗi tải nội dung và được đính kèm lại ở lượt sau. Tôi đã đọc lại và đối chiếu 10 ảnh đại diện (#001, #002, #005, #006, #017, #023, #027, #052, #079, #088); mọi ghi chú khớp. Các ảnh còn lại trong nhóm đó giữ theo ghi chú, chưa đối chiếu từng ảnh.
7. Không thể tự xác minh danh tính hay uy tín của các tài khoản; "nguồn" chỉ là tên hiển thị trên ảnh.

**Câu hỏi còn mở**
- Nếu muốn kiểm chứng ICT/SMC: cần một định nghĩa máy đọc được cho từng khái niệm (ví dụ "FVG hợp lệ" = ba nến với khoảng trống ≥ x ATR; "quét thanh khoản" = phá đỉnh/đáy phiên trước rồi đóng cửa lại trong biên). Bạn có muốn tôi viết đặc tả rồi chạy cùng bộ phương pháp này không?
- Các phép thử trên dùng H1. Có nên lặp lại trên M15/H4 (dữ liệu của dự án có sẵn)?
- Có nên đưa "lọc xu hướng EMA200 + Fib/Double Top" như một điều kiện *kết hợp* vào bộ quy tắc hiện có để thử (thay vì thử từng cái riêng lẻ)?

## G. Bổ sung: 2 ảnh mới (#105–#106, Bài 74 và Bài 75, nguồn "Ci" / #HocCungCiNhe)

Thư mục giờ có 106 ảnh (bạn nhắc 3 ảnh nhưng chỉ có 2 file mới: `…814969813_…29a48e…` và `…814969817_…5e86a3…`). Cả hai là infographic tiếng Việt do AI vẽ, theo chuỗi bài học.

**#105 (Bài 75, Trend Following):** xu hướng = HH/HL hoặc LH/LL, giá trên/dưới EMA50/200; vào lệnh khi giá hồi về hỗ trợ/EMA kèm nến xác nhận (pin bar, engulfing); SL dưới hỗ trợ, TP tại kháng cự hoặc R:R 1:2; tránh giao dịch khi đi ngang. Có mục "Ưu điểm/Hạn chế" cân bằng (thừa nhận bỏ lỡ đoạn đầu, dễ bị quét SL, kém hiệu quả khi đi ngang).
**#106 (Bài 74, một setup XAU/USD hoàn chỉnh):** 8 bước: xu hướng → pullback → xác nhận → Entry/SL/TP → tính lot theo rủi ro → điều kiện bỏ setup → quy trình → kết luận ("không có setup nào đảm bảo thắng").

**Điểm cộng:** đây là hai ảnh trung thực nhất trong cả bộ về mặt thông điệp: có ghi "ví dụ minh họa, không phải thị trường hiện tại", "không có setup nào đảm bảo thắng", "thông số hợp đồng khác nhau tùy broker", và có điều kiện hủy setup.

**Lỗi tính toán trong #106 (mục 5):** ảnh ghi "SL 10 USD → rủi ro 100 USD/lot → lot cần thiết ≈ 0,01 để rủi ro ~10 USD". Hai vế mâu thuẫn nhau. Với 1 lot = 100 oz, giá chạy 10 USD = **1.000 USD/lot** (không phải 100). Kết quả cuối 0,01 lot là đúng (10 ÷ 1.000), nhưng bước trung gian sai, và nếu làm theo "100 USD/lot" thì ra 0,1 lot, gấp 10 lần mức rủi ro dự định. Các giá trong ví dụ (Entry 2.435, SL 2.425, TP 2.455) là mặt bằng giá vàng của năm 2024 (lần cuối vàng ở vùng 2.435 là 15/08/2024), không phải hiện tại; ảnh có ghi chú "không phải giá thị trường hiện tại" nên đây chỉ là lưu ý.

**Kiểm chứng trên XAUUSD H1 (cùng phương pháp mục C0, so với nền cùng bối cảnh, có tách dev/val):**

| Khẳng định | Phép thử | Kết quả |
|---|---|---|
| "Giá trên EMA50 và EMA hướng lên → ưu tiên mua" | Lợi suất tiến 12/24/120 nến theo ATR, so với mọi nến còn lại | Mua: Δ = +0,08 ATR sau 12 nến (t = +1,50), cùng chiều ở dev (+0,94) và val (+1,23). Bán (giá dưới EMA50, EMA xuống): Δ = +0,06 (t = +1,23). **Dấu đúng hướng ở cả hai phía nhưng không đạt ý nghĩa thống kê**, và bị nâng bởi xu hướng tăng dài hạn của vàng. |
| Setup Bài 74: xu hướng + pullback chạm EMA50 + pin bar/engulfing xác nhận | Lợi suất tiến so với nền "cùng xu hướng, không có tín hiệu" | Mua (N = 2.816): Δ = −0,21 ATR sau 12 nến (t = −1,17), −0,01 sau 24 nến. Bán (N = 2.608): Δ = −0,06 (t = −0,32), +0,13 sau 24 nến. **Thêm xác nhận nến vào pullback không cải thiện kết quả so với chỉ đi theo xu hướng.** |
| Cùng setup với SL dưới/trên nến tín hiệu, TP = 2R, như ảnh | Tỷ lệ thắng so với random-walk (1/3) | Mua: thắng 33,1%, kỳ vọng 33,3% (z = −0,28, E[R] = −0,008, N = 2.781). Bán: thắng 33,3%, kỳ vọng 33,3% (z = −0,06, E[R] = −0,002, N = 2.557). **Trùng hoàn toàn với ngẫu nhiên, ở cả dev và val.** |

**Kết luận và phản biện:**
- Bộ lọc xu hướng EMA50 chỉ nghiêng nhẹ đúng hướng. Giá trị chính của nó là giảm giao dịch ngược xu hướng, chứ chưa chứng minh được là tạo ra lợi thế.
- Quy trình "chờ pullback + xác nhận" trong cả hai ảnh **không có lợi thế đo được** với định nghĩa tôi dùng (chạm EMA50 ±0,3 ATR + pin bar/engulfing, vùng hỗ trợ/kháng cự **không** được thử vì cần vẽ chủ quan). Vì vậy kết luận chính xác là "EMA50 + nến xác nhận không đủ", chưa phải "hỗ trợ/kháng cự vô dụng".
- Cấu trúc 8 bước và kỷ luật rủi ro vẫn đáng giữ như một quy trình quản trị; đó là giá trị thật của hai bài này (khớp với mục C6), không phải lợi thế dự báo.
- Độ tin cậy: **trung bình–cao** cho phần đã thử (N > 2.500, cùng chiều dev/val); **không kiểm chứng được** phần hỗ trợ/kháng cự.

Cập nhật mục D: dòng 3 (EMA) và dòng 5 (top-down) nay có thêm bằng chứng từ #105–#106 theo hướng "không có lợi thế vào lệnh từ pullback EMA50 + nến xác nhận". Dòng 6 được củng cố, nhưng lỗi 100 USD/lot ở #106 cần lưu ý. Tái lập: `image_claims_verification/verify_trend_following.py.txt` và `results_v2_trend_following.json`.

## H. Bổ sung: ảnh thứ 3 (#107, Bài 73 "Không có setup thì không giao dịch", nguồn "Ci")

Thư mục giờ có 107 ảnh. Bài 73 cùng chuỗi với #105–#106: định nghĩa setup (xu hướng H1 trên/dưới EMA50 + pullback về hỗ trợ/kháng cự + nến xác nhận + R:R + SL/TP/lot), 4 trường hợp "không có setup" (thị trường đi ngang, giá giữa vùng, tín hiệu nhiễu, sát tin tức lớn), checklist 8 mục, 7 lỗi thường gặp, ví dụ rủi ro 1% trên tài khoản 1.000 USD (SL 20 USD).

**Khẳng định cần kiểm chứng:** (1) "Có setup → tỷ lệ thắng cao hơn" (mục 5); (2) tránh giao dịch khi đi ngang, khi giá ở giữa vùng, khi tín hiệu nhiễu và quanh tin tức sẽ cải thiện kết quả; (3) "ít lệnh nhưng đúng có giá trị hơn nhiều lệnh nhưng sai".

**Phép thử:** dùng đúng setup của Bài 73/74 (xu hướng EMA50 + pullback chạm EMA50 + pin bar/engulfing, SL ở nến tín hiệu, TP = 2R, so với kỳ vọng random-walk 1/3), rồi chia theo các điều kiện ảnh bảo nên tránh. Thị trường đi ngang đo bằng Efficiency Ratio 20 nến (tercile); "giá giữa vùng" = 35–65% biên 50 nến; biến động theo ATR/giá (tercile). N = 5.338 setup, trung bình ≈ 232 setup mỗi năm.

| Nhóm | N | Tỷ lệ thắng (kỳ vọng 33,3%) | z | E[R] | z dev / val |
|---|---|---|---|---|---|
| Tất cả setup | 5.338 | 33,2% | −0,24 | −0,005 | −0,27 / −0,05 |
| Thị trường đi ngang (ER thấp) | 2.577 | 33,3% | −0,04 | −0,001 | +0,62 / −0,91 |
| Xu hướng rõ (ER cao) | 750 | 32,3% | −0,62 | −0,032 | −0,34 / −0,56 |
| Giá giữa vùng | 2.834 | 34,2% | +0,97 | +0,026 | +0,98 / +0,31 |
| Giá gần biên vùng | 2.504 | 32,0% | −1,38 | −0,039 | −1,47 / −0,38 |
| Biến động thấp | 2.161 | 32,3% | −1,02 | −0,031 | −1,14 / −0,22 |
| Biến động cao | 1.433 | 36,1% | +2,20 | +0,082 | +2,13 / +0,84 |

**Kết luận:**
- **(1) Không được ủng hộ.** Setup đầy đủ có tỷ lệ thắng 33,2%, trùng với ngẫu nhiên (33,3%) ở cả dev và val.
- **(2) Không được ủng hộ cho các bộ lọc đo được.** Tránh thị trường đi ngang không giúp gì: nhóm đi ngang có kết quả bằng nhóm xu hướng rõ (33,3% so với 32,3%, chênh lệch không có ý nghĩa). Tránh "giá giữa vùng" còn ngược chiều mong đợi: giá giữa vùng nhỉnh hơn giá sát biên (34,2% so với 32,0%), nhưng cả hai đều không khác ngẫu nhiên. Phần "tin tức lớn" chưa kiểm chứng được vì dự án chưa gắn lịch tin vào phép thử này, "tín hiệu nhiễu" chưa có định nghĩa đo được.
- **Một tín hiệu đáng ghi nhận nhưng chưa tin được:** nhóm biến động cao có z = +2,20 (E[R] = +0,08), nhưng đây là 1 trong 7 nhóm đã so sánh nên không vượt hiệu chỉnh Bonferroni (ngưỡng ≈ 2,7), và val chỉ +0,84. Nên coi là giả thuyết để thử lại độc lập, không phải kết quả.
- **(3) Giá trị của "đứng ngoài":** kỷ luật bỏ qua cơ hội kém là lời khuyên hợp lý về tâm lý và giảm chi phí giao dịch, nhưng ở đây việc bỏ qua các nhóm "xấu" không nâng được kỳ vọng. "Ít lệnh nhưng đúng" chỉ đúng nếu có tiêu chí chọn lệnh thực sự tốt hơn ngẫu nhiên, và các tiêu chí trong ảnh không chứng minh được điều đó.

**Phản biện:** thông điệp và checklist của Bài 73 là phần mềm quy trình hữu ích (khớp mục C6), cùng điểm mạnh như #105–#106 (có ghi "không có setup nào đảm bảo thắng"). Điểm yếu là mục 5 hứa "tỷ lệ thắng cao hơn" mà không có số liệu, và tập "ví dụ hoàn chỉnh" chỉ có hai minh họa chọn lọc. Hạn chế của phép thử: vùng hỗ trợ/kháng cự thật (vẽ tay) không được thử, nên kết luận chỉ áp dụng cho cách hiện thực hóa bằng EMA50 + nến.

Độ tin cậy: **trung bình–cao** cho phần (1) và (2) đo được (N > 2.000 mỗi nhóm lớn, cùng chiều dev/val); **không kiểm chứng được** cho tin tức và tín hiệu nhiễu. Tái lập: `image_claims_verification/verify_setup_filters.py.txt`.

## I. Bổ sung: thư mục `Image/1/` (Bài 72 và Bài 71, nguồn "Ci")

Thư mục con `Image/1/` có 6 file, nhưng 3 file trùng nội dung với Bài 75, 74, 73 đã xử lý (MD5 trùng với ảnh trong `Image/`). Chỉ có **2 ảnh mới**: **#108 Bài 72 "Điều kiện xác nhận là gì?"** và **#109 Bài 71 "Entry – khi nào thực sự nên vào lệnh?"**. Tổng cộng nay có 113 file ảnh, trong đó 94 file độc nhất (kiểm bằng MD5 trên toàn bộ cây thư mục). Ngoài ra thư mục `docs/` cạnh `Image/` có `72.md`–`75.md`, là bản chữ của các bài này; tôi không phân tích riêng vì cùng nội dung ảnh.

**Nội dung:** Bài 72: xác nhận bằng nến (pin bar, engulfing), cấu trúc (HL, phá đỉnh gần nhất), breakout, indicator; "xác nhận không phải càng nhiều càng tốt" (quá nhiều xác nhận → vào muộn, SL rộng, R:R giảm). Bài 71: vào lệnh phải nằm trong một setup (xu hướng H1/H4 → hỗ trợ/kháng cự → price action → xác nhận → R:R → lot), tránh vào sớm (chưa xác nhận, dễ false breakout) và vào muộn (giá đã chạy xa, SL rộng, R:R xấu), ví dụ rủi ro 1% trên 1.000 USD với SL 20 USD.

**Khẳng định cần kiểm chứng:** (1) vào khi có xác nhận tốt hơn vào sớm; (2) thêm quá nhiều xác nhận làm vào muộn, SL rộng, R:R giảm; (3) vào muộn thì R:R xấu.

**Phép thử** (cùng khung H1, TP = 2R, SL dưới/trên đáy/đỉnh 5 nến gần nhất, so với kỳ vọng ngẫu nhiên 1/3 **và** so với nền "mọi nến trong cùng xu hướng, cùng quy tắc SL"). Bốn mức: A = xu hướng + chạm EMA50 (vào sớm, chưa xác nhận); B = A + pin bar/engulfing; D = A + phá đỉnh/đáy 3 nến; C = A + nến + phá đỉnh/đáy (xác nhận kép).

| Nhóm | Mua: thắng (N) | Bán: thắng (N) | R trung vị | Ghi chú |
|---|---|---|---|---|
| Nền: mọi nến trong xu hướng | 35,4% (60.785) | 33,3% (50.230) | — | baseline |
| A: chạm EMA50 (chưa xác nhận) | 35,1% (12.488) | 35,4% (11.973) | 1,07 ATR | |
| B: + nến xác nhận | 35,6% (4.116) | 33,5% (3.771) | 1,51 ATR | |
| D: + phá đỉnh/đáy | 38,0% (4.709) | 34,0% (4.327) | 2,37 ATR | |
| C: + nến + phá đỉnh/đáy | 38,6% (1.546) | 33,1% (1.418) | 2,27 ATR | |

**Cảnh báo về chính phép thử:** lần chạy đầu của tôi chỉ so với 1/3 và cho z = +6,3 cho nhóm A (N = 24.461) trông như có lợi thế. Đó là **sai lệch giả**: các lệnh ở nến liên tiếp có cùng kết quả (chồng lấn), và nền xu hướng tăng của vàng nâng tỷ lệ thắng bên mua lên 35,4% sẵn ngay cả khi vào ngẫu nhiên. Sau khi (a) so với nền cùng chế độ và (b) giãn mẫu còn 1 lệnh mỗi 24 nến, z của A chỉ còn +1,49 và của C +1,50 (nền: +0,06).

**Kết luận:**
- **(1) Chỉ được ủng hộ yếu và chỉ bên mua.** Xác nhận bằng phá đỉnh (D) nâng tỷ lệ thắng bên mua từ 35,4% lên 38,0% (C: 38,6%, cùng chiều ở dev 38,1% và val 39,4%), nhưng bên bán không có cải thiện (33,1–34,0% so với nền 33,3%). Xác nhận bằng nến một mình (B) gần như không khác nền. Vì chỉ bên mua có hiệu ứng và vàng đang trong xu hướng tăng dài hạn, đây là **giả thuyết phụ thuộc chế độ**, chưa phải lợi thế.
- **(2) Được ủng hộ về mặt đo đạc.** Thêm xác nhận làm rủi ro (khoảng cách SL) tăng từ 1,07 ATR (A) lên 1,51 (B) và 2,3–2,4 ATR (C, D), và số tín hiệu giảm 4–16 lần. Đúng với lời ảnh: "SL phải rộng, R:R giảm", xác nhận kép cho ít lệnh hơn nhưng với rủi ro mỗi lệnh gấp đôi. Nếu cố định mục tiêu 2R thì tỷ lệ thắng không tăng bù lại ở bên bán.
- **(3) Một phần đúng:** vào muộn đúng là làm SL xa hơn (đo ở trên), nhưng "R:R xấu" chỉ đúng khi cố định SL theo cấu trúc; nếu giữ rủi ro 1% và co lot lại thì kỳ vọng mỗi R không đổi.

**Phản biện:** hai bài này trình bày quy trình hợp lý, có điều kiện hủy và cảnh báo "xác nhận không đảm bảo thắng". Lỗi/điểm yếu: không số liệu; "xác nhận giúp tránh false breakout" chưa được chứng minh bằng thống kê (kết quả bên bán không cho thấy điều đó); ví dụ chọn sau khi biết kết quả. Giới hạn của phép thử: một cách hiện thực hóa "xác nhận", không có vùng hỗ trợ/kháng cự vẽ tay, không chi phí. Độ tin cậy: **trung bình** cho phần đã đo (N = 1.400–12.500 mỗi nhóm), nhưng **thấp** cho khẳng định "xác nhận tăng tỷ lệ thắng" (chỉ một bên, sau khi giãn mẫu không vượt ngưỡng ý nghĩa).

**Bản sao mới:** `Image/1/` chứa 3 file trùng MD5 với `Image/` (…501445 = …814969813 [Bài 75], …501470 = …814969817 [Bài 74], …501499 = …815154653 [Bài 73]); file …501486 trùng …501445. Tái lập: `image_claims_verification/verify_confirmation.py.txt`.

## J. Bổ sung: loạt bài chỉ báo và price action của "Ci" (13 ảnh mới trong `Image/1/`: Bài 57–60, 62–70)

`Image/1/` nay có 20 file; 6 file là bản trùng Bài 71–75 đã xử lý, 1 file (…685381) là Bài 74 nén lại (mã băm khác, nội dung trùng), còn **13 ảnh mới**: Bài 57 Pullback, 58 Liquidity, 59 Price Action, 60 Indicator, 62 EMA 20/50/100/200, 63 RSI, 64 RSI 70, 65 MACD, 66 ATR, 67 Bollinger Bands, 68 Dùng nhiều indicator, 69 Một hệ thống indicator đơn giản, 70 Một chiến lược Forex. **Không có Bài 61** trong thư mục. Tổng cả cây thư mục: 123 file ảnh, 107 mã băm độc nhất.

**Tính chất chung:** cùng phong cách infographic AI, thông điệp nhất quán và thận trọng ("indicator không dự đoán", "RSI > 70 không phải lệnh Sell", "xác nhận trước khi vào lệnh"). Không có số liệu thống kê; ví dụ giá XAU/USD 2.300–2.500 là mặt bằng năm 2024. Điểm tốt hơn mặt bằng chung của bộ ảnh: gần như mọi khẳng định mang tính định tính và có kèm cảnh báo. Điểm cần kiểm tra là các câu ngầm định hướng giá ở Bài 62–65 và 67: cực trị chỉ báo hoặc cắt nhau "có thể" báo hiệu.

**Phương pháp (cùng mục C0, bổ sung):** lợi suất tiến 12 và 24 nến theo ATR, trừ nền cùng bối cảnh; sự kiện được giãn cách ≥ h nến để tránh chồng lấn; báo cáo tất cả/dev (<2019)/val (≥2019); ngưỡng Bonferroni cho khoảng 35 phép thử là |z| ≈ 3,2. Với các kết quả có vẻ mạnh tôi chạy thêm phép thử thực tế: giữ lệnh 12 nến, trừ spread thật của dữ liệu.

| Khẳng định | Ảnh | Kết quả trên XAUUSD H1 |
|---|---|---|
| "RSI > 70 không có nghĩa phải Sell; RSI < 30 không có nghĩa phải Buy" | 063, 064 | **Đúng một phần, nhưng ở 12 nến có xu hướng đảo chiều.** Sau RSI cắt lên 70, giá yếu hơn nền 0,43 ATR (z = +6,3); sau RSI cắt xuống 30, mạnh hơn nền 0,56 ATR (z = +7,4). Hiệu ứng mạnh ở dev (+0,58, +0,78) và **suy yếu mạnh ở val** (+0,17, z = 1,5; +0,11, z = 0,8), biến mất ở 24 nến. Giữ 12 nến trừ spread: bán RSI>70 dev +2,45 USD (z = 8,2) nhưng val −0,88 USD và **từ 2025 −7,47 USD** (n = 145, z = −2,0); mua RSI<30 dev +3,43, val +1,78 (z = 1,1), từ 2025 −3,39 (n = 95). **Hiệu ứng có thật trong giai đoạn cũ nhưng không còn đáng tin trong dữ liệu gần đây.** |
| "RSI về vùng 40–50 trong uptrend rồi mua" | 063 | **Không được ủng hộ, kết quả ngược:** n = 232, sau 24 nến thấp hơn nền 0,87 ATR (z = −3,5); val −0,61 (z = −1,3). Mẫu nhỏ. |
| MACD cắt lên/xuống là tín hiệu; MACD trên 0 → ưu tiên tăng | 065 | **Không được ủng hộ.** MACD cắt lên → mua: −0,17 ATR (z = −4,2); cắt xuống → bán: −0,19 (z = −4,7); cả hai cho thấy giá đảo chiều sau tín hiệu ở 12 nến (dev rõ, val yếu: −0,11 và −0,10). Trạng thái MACD > 0 hoặc < 0 không có thông tin hướng (Δ ≈ 0,00, z ≈ 0). Ảnh đã tự cảnh báo "coi cắt là tín hiệu chắc chắn là sai lầm", khớp với kết quả. |
| "Giá chạm dải Bollinger không có nghĩa phải đảo chiều; trong xu hướng giá đi dọc theo dải" | 067 | **So với nền, đảo chiều khả dĩ hơn tiếp diễn ở 12 nến.** Đóng cửa trên dải trên → bán: +0,27 ATR (z = +5,6; val +0,22, z = 2,8); đóng cửa dưới dải dưới → mua: +0,41 (z = +8,3; val +0,18, z = 2,0). Trừ spread, giữ 12 nến: **mua dưới dải dưới có lãi ở cả dev (+2,02 USD, z = 9,4) và val (+2,06 USD, z = 2,5)**, nhưng từ 2025 chỉ +1,68 USD với z = 0,5 (n = 208); bán trên dải trên: dev +1,13, val −0,03, từ 2025 −4,14. Lưu ý: vàng tăng dài hạn nên bên mua được nâng bởi drift; tôi so tuyệt đối trừ spread nhưng chưa tách drift. |
| "Bollinger co lại (squeeze) → sau đó biến động mạnh" | 067 | **Không được ủng hộ khi đo đúng.** Chuẩn hóa theo ATR cho 7,30 so với 5,93 nền, nhưng đó là hiệu ứng giả: ATR lúc co lại nhỏ nên mẫu số nhỏ. Tính biên độ thô 24 nến sau theo % giá: squeeze 1,718% so với nền 1,746% và dải rộng 1,929%. Squeeze không báo trước biến động lớn hơn trong dữ liệu này. |
| "ATR cao = biến động lớn; ATR không cho biết hướng" | 066 | **Đúng.** Nhóm ATR cao nhất (20% trên) có biên độ 24 nến sau lớn hơn 1,28 lần nhóm thấp nhất (0,966% so với 0,753%). ATR tăng ≥ 20% không phân biệt hướng ở val (Δ = +0,013, z = 0,2); dev có +0,136 (z = 3,0) nhưng không lặp lại. |
| "SL = 2 ATR, TP = 3 ATR" | 066 | Vào ngẫu nhiên: thắng 39,6% (N = 12.000) so với kỳ vọng ngẫu nhiên 40,0%, E[R] ≈ −0,01. ATR giúp đặt SL hợp lý như ảnh nói, nhưng không tạo lợi thế. |
| Quét thanh khoản rồi đảo chiều ("fake breakout"); phá vỡ thật thì tiếp diễn | 058 | **Không có lợi thế ổn định.** Quét đỉnh 20 nến rồi đóng lại trong vùng → bán: +0,10 ATR sau 12 nến (z = 2,2) nhưng val −0,02; quét đáy → mua: −0,02 (z = −0,3). Thêm điều kiện bấc dài không cải thiện (bên mua còn ngược: −0,24, z = −2,8). Phá vỡ thật lên: 12 nến đầu thấp hơn nền (−0,24, z = −4,3) rồi 24 nến cao hơn nền (+0,25, z = +2,9; val +0,23, z = 1,6): có kéo ngược ngắn hạn rồi tiếp diễn nhẹ, nhưng không vượt ngưỡng ở val. |
| Xếp chồng EMA 20/50/100/200 là xu hướng rõ; giao cắt khi đi ngang cho nhiều tín hiệu nhiễu | 062 | **Không có lợi thế.** Xếp chồng tăng đầy đủ → mua: Δ +0,02 (12 nến), +0,09 (24 nến, z = 1,1); xếp chồng giảm → bán: −0,01 và +0,16 (z = 1,6). EMA20/50 cắt lên trong xu hướng rõ còn kém nền (−0,36, z = −2,9), không tốt hơn khi đi ngang (−0,06): khẳng định "giao cắt hiệu quả hơn khi có xu hướng" không được ủng hộ. |
| Pullback là cơ hội vào lệnh theo xu hướng (Bài 57); Price Action đọc cấu trúc/vùng/nến (Bài 59) | 057, 059 | Đã kiểm chứng ở mục C1, C3, I: pullback về EMA50 hoặc Fibonacci và nến xác nhận không cho lợi thế vượt ngẫu nhiên; cấu trúc HH/HL và vùng hỗ trợ/kháng cự vẽ tay chưa kiểm chứng được. |
| Dùng nhiều indicator làm chiến lược tốt hơn (Bài 68); hệ thống EMA50 + RSI + ATR (Bài 69, 70) | 068, 069, 070 | "Nhiều indicator không tốt hơn; nguy cơ overfitting khi backtest" **đúng về nguyên lý**: trong chính đợt kiểm tra này, khoảng 35 phép thử × 3 giai đoạn cho một số z lớn ở dev biến mất ở val, đúng minh họa cảnh báo. Hệ thống Bài 69/70 (EMA50 + pullback + Price Action + RSI + ATR) là bản mở rộng của setup Bài 73–74 đã đo ở mục H–I: không có lợi thế vượt ngẫu nhiên. Quy trình backtest/forward test ở Bài 69–70 (ghi lệnh, winrate, expectancy, profit factor, demo trước live) là chuẩn thực hành tốt. |

**Kết luận chính của đợt này:**
1. **Không chỉ báo nào cho tín hiệu hướng giá đáng tin ở H1 theo cách ảnh dạy** (MACD cắt, xếp chồng EMA, RSI 40–50 pullback, quét thanh khoản, squeeze Bollinger). Lời cảnh báo trong ảnh ("không dự đoán, đừng dùng một mình") phù hợp với dữ liệu hơn là các ví dụ minh họa.
2. **Có một hiện tượng đáng ghi nhận nhưng không nên coi là lợi thế:** ở cực trị RSI và dải Bollinger, 12 nến sau có xu hướng đảo chiều so với nền; mạnh ở 2004–2018, yếu ở 2019+, và gần như biến mất trong dữ liệu 2025+ (n nhỏ, hai chiều bán đều âm). Bên mua dưới dải dưới Bollinger bền nhất qua cả dev và val nhưng bị trộn với drift tăng dài hạn của vàng, và chưa mô phỏng thực tế (SL, trượt giá, nhiều lệnh đồng thời). Đây là **giả thuyết đáng thử lại** (ví dụ trên M15/H4 và dữ liệu mới), chưa phải kết luận.
3. **Sai lầm đáng nhớ trong đợt này:** kết quả squeeze ban đầu trông ủng hộ ảnh nhưng là hiệu ứng chuẩn hóa. Mọi kết quả "biến động" nên kiểm tra bằng biên độ thô, không chỉ đơn vị ATR.
4. Các bài quản trị rủi ro ($1.000, rủi ro 1% = $10/lệnh) lặp lại cùng công thức; số 0,01 lot cho SL 10 USD đúng (lỗi 100 USD/lot đã nêu ở mục G).

**Hạn chế:** một khung (H1), tham số mặc định (RSI 14, MACD 12/26/9, BB 20/2); đã chia dev/val nhưng chưa tách theo chế độ biến động; chưa mô phỏng quản lý lệnh đầy đủ cho hiệu ứng đảo chiều; xu hướng tăng dài hạn của vàng nâng các kết quả bên mua. Độ tin cậy: **cao** cho kết luận "MACD/EMA stack/quét thanh khoản/squeeze không có lợi thế" và "ATR đo biến động, không đo hướng"; **trung bình–thấp** cho hiệu ứng đảo chiều ở cực trị (phụ thuộc giai đoạn). Tái lập: `image_claims_verification/verify_indicators.py.txt` và `verify_indicators_net_of_spread.py.txt`.

## K. Dọn thư mục ảnh (2026-10-12)

Sau khi đọc toàn bộ ảnh, tôi đã xóa **52 file** khỏi `Image/`: 15 bản sao chính xác của bộ #036–#050 (MD5 trùng) và 1 bản Bài 75 lặp, 22 ảnh trùng nội dung (khung lặp của cùng video, bản nén lại), 6 ảnh giá trị thấp (quảng cáo sàn, không phải XAUUSD, mờ) và 10 ảnh bìa sách (không có nội dung kiểm chứng). Danh sách sách đã ghi ở mục B (#026–#035), nên không mất thông tin.

- Trước khi xóa, mọi file được sao lưu và kiểm lại mã băm vào `Image_trash_2026-10-12/` (cạnh `Image/`, ngoài thư mục ảnh). Manifest: `image_claims_verification/CLEANUP_MANIFEST_2026-10-12.txt`.
- Còn lại: **71 file ảnh, 71 mã băm độc nhất** (không còn trùng chính xác).
- 22 ảnh xếp nhóm "xem xét" (chung chung hoặc có quảng cáo nhưng còn thông tin) được **giữ nguyên**, chờ quyết định riêng.
- Kế hoạch từng file: `image_claims_verification/IMAGE_CLEANUP_PLAN.md`. Lưu ý các số đếm ở đầu báo cáo và mục B/G–J phản ánh thời điểm trước khi dọn; các ID ảnh đã xóa vẫn có trong bảng kiểm kê để truy vết.

## F. Tái lập kết quả

Thư mục `docs/reports/image_claims_verification/` chứa:
- `verify_image_claims.py.txt`: mã nguồn (lưu đuôi `.txt` để không bị công cụ mypy/pre-commit của repo quét; đổi lại thành `.py` để chạy).
- `results.json`: toàn bộ số liệu thô của các phép thử.

Chạy bằng môi trường `.venv` của `xau-edge` (polars, numpy): `.venv/Scripts/python.exe -X utf8 verify_image_claims.py <đường dẫn results.json>`.
