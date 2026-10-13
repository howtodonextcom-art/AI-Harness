# Giá trị của mã nguồn cũ và thiết kế lại thành MỘT trang

Ngày: 2026-10-12 · Căn cứ: đọc lại `apps/dashboard` (components, lib, app, e2e), đối chiếu kiểm toán trước (`XAU_EDGE_KIEM_TOAN_VA_HUONG_XAY_DUNG_2026-10-12.md`) và UI thật đã chụp.

## 1. Nhận định

Bạn đúng: **nhiều trang không hiệu quả với sản phẩm này.** Bằng chứng trong chính repo cũ:
- Audit nội bộ của repo (`INDEPENDENT_EDGE_FAILURE_AUDIT.md` §3): *"Trang giúp ra quyết định ngay: chỉ `/trade`."* `/market` là giám sát (trùng lặp với `/trade`), `/research` là nghiên cứu, `/control` là vận hành (đang tắt), `/legacy` là di sản.
- `/journal` thực tế **rỗng** (0 lệnh đóng); `/research` chỉ nói "NO EDGE", 9 trang con (≈ 3.600 dòng) để hiển thị một kết luận.
- Nav 5 mục chiếm chỗ và chia nhỏ sự chú ý của một người chỉ cần biết "bây giờ làm gì".

[Ý KIẾN CỦA TÔI] Một người giao dịch cần **một màn hình**: giá, quyết định, vì sao, điều kiện tiếp theo, rủi ro. Phần còn lại (nhật ký, bằng chứng, sức khỏe dữ liệu) là **ngăn kéo phụ** trên cùng màn hình, không phải trang riêng.

## 2. Giá trị từng phần của UI cũ (đã đo số dòng)

Tổng `components/` 9.929 dòng + `lib/` 3.274 dòng + e2e 5.070 dòng.

| Phần | Dòng | Giá trị | Quyết định |
|---|---|---|---|
| `lib/action.ts`, `honesty.ts`, `lifecycle.ts`, `humanState.ts`, `vi.ts` | ~600 | **Cao.** Đây là "hợp đồng quyết định" bằng chữ: tách THIÊN HƯỚNG (mô tả) khỏi HÀNH ĐỘNG (được phép làm gì), thang mức bằng chứng 7 bậc, vòng đời Thiên hướng → Setup → Trigger → Sẵn sàng → Mở → Giữ → Thoát, câu "vì sao CHỜ" cho mọi mã từ chối. Trình duyệt **không quyết định chiến lược**, chỉ định dạng trường của server | **GIỮ** (đọc lại và chép có chọn lọc) |
| `components/terminal/` (HeroCard, DecisionPanel, WaitBriefing, MtfStrip, MarketBar, SystemCards, HealthCards, News) | ~2.400 | **Cao.** Là toàn bộ màn hình quyết định đã qua nhiều vòng QA bằng trình duyệt | **GIỮ** làm lõi của trang duy nhất, gọn lại |
| `TerminalChart.tsx` (1.019 dòng) + `chartMath/chartScale/sessions/time.ts` | ~1.300 | **Trung bình–cao.** Biểu đồ lightweight-charts với marker tín hiệu/lệnh, vùng phiên, lớp phủ kế hoạch, xử lý múi giờ và DST (một lỗi khó đã được xử lý). Quá lớn so với nhu cầu | **GIỮ lõi, cắt nhỏ** (nến, khối lượng, SL/TP/entry, marker, phiên); bỏ công cụ vẽ |
| `DrawingLayer`, `DrawingMenu`, `drawings.ts`, `ChartToolbar` (6 công cụ vẽ, Fibonacci, RR tool) | ~760 | **Thấp.** Báo cáo kiểm chứng cho thấy Fibonacci không có lợi thế; công cụ vẽ không phục vụ quyết định theo quy tắc | **BỎ** (có thể thêm lại sau nếu thật sự dùng) |
| `components/trade/JournalView` + `lib/trade.ts` | ~930 | **Trung bình.** Nhật ký R/MFE/MAE đúng hướng nhưng đang rỗng; kiểu dữ liệu `trade.ts` là hợp đồng API đáng giữ | **GIỮ ý tưởng**, đưa vào ngăn kéo dưới |
| `components/research/*` + `lib/research.ts` (9 trang) | ~3.640 | **Thấp.** Console chỉ đọc nói lại kết luận đã ghi trong file Markdown | **BỎ**; thay bằng 1 thẻ "Bằng chứng" (mức bằng chứng, K đã dùng/trần, kết luận, đường dẫn tới báo cáo) |
| `components/market/*` | ~485 | **Thấp.** Trùng với `/trade` | **BỎ**; gộp vào thanh "Sức khỏe dữ liệu" |
| `ControlPanel`, `BotPanel`, `Dashboard`, `AnalogueChart`, `lib/control.ts`, `app/legacy`, `app/api/control` | ~1.330 | **Không.** Bot demo khóa, trang cũ lệch 98 giờ, sinh 3 lỗi 503 | **BỎ** |
| `MainNav`, 17 file `page.tsx` | ~200 | Điều hướng nhiều trang | **BỎ**, còn 1 route |
| e2e: `states`, `decision_contract`, `human_state`, `honesty`, `lifecycle`, `terminal`, `layout_stability`, `a11y`, `desktop_contract` | ~1.860 | **Cao.** Là hợp đồng hành vi (trạng thái, trung thực, vòng đời, ổn định bố cục, a11y) | **GIỮ** làm bộ test chấp nhận, chỉnh theo trang mới |

Tóm tắt: trong ~13.200 dòng UI nguồn, **khoảng 5.000–5.500 dòng có giá trị** (logic quyết định, màn hình quyết định, biểu đồ lõi, hợp đồng test); **~5.500–6.000 dòng nên bỏ** (research, market, control, legacy, vẽ).

## 3. Giá trị backend (để dùng cho trang này)

Đã nêu ở báo cáo kiểm toán; ở đây chỉ xếp theo mức tái dùng:

| Mức | Module | Lý do |
|---|---|---|
| **Giữ gần nguyên** | `trading/{market_state,baseline,baseline_v12,levels,sizing,risk_calc,governor,setup_machine,paper_desk,position_manager,schema,funnel,decision_core}`, `structure/`, `features/`, `domain/` | Lõi đã kiểm thử, không rò rỉ, sizing đúng, vòng đời setup xác định |
| **Giữ, cắt gọn** | `market_data/` (collector, ledger, validators, broker_clock, calendars), `news/`, `risk/` | Cần cho dữ liệu; nhiều phần phụ trợ có thể bỏ |
| **Giữ cho nghiên cứu nhỏ** | `evaluation/{edge,bootstrap,periods,protocol,prop_mc}`, `backtest/{costs,metrics,engine}`, `outcomes/`, `models/` (benchmark) | Khung thống kê nghiêm; đây là phần giá trị về phương pháp |
| **Không chép** | `signals/` cũ, `control/`, `funded/`, `brokers/`, `execution/`, `video_intel/`, `forensics/`, `decision_research/`, `research_v2/v3` | Hai bộ não, khóa, hoặc nghiên cứu phụ |

## 4. Thiết kế MỘT trang (đề xuất)

Một route `/`. Không điều hướng. Ngăn kéo chuyển bằng tab trong cùng trang (hash `#journal`, `#evidence`, `#data` để chia sẻ link).

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ XAUUSD  4168.79 ▼  Ask 4169.20  Spread 41    [LIVE][PAPER][UNVALIDATED]  [Giờ VN ▾]│  thanh trạng thái
├───────────────────────────────────────────────────────┬──────────────────────────┤
│                                                       │  HÀNH ĐỘNG: CHỜ          │
│                BIỂU ĐỒ (M5/M15/H1, nến + khối lượng)   │  vì sao: H1 chưa có hướng │
│        entry / SL / TP / marker tín hiệu / phiên       │  cần xảy ra: …            │
│                                                       │ ───────────────────────── │
│                                                       │  CHECKLIST TRƯỚC LỆNH     │
│                                                       │  ☐ Xu hướng  ☐ Vùng       │
│                                                       │  ☐ Xác nhận  ☐ R:R ≥ 1,5  │
│                                                       │  ☐ Lot theo SL  ☐ Không tin│
│                                                       │ ───────────────────────── │
│                                                       │  RỦI RO: 0,25% · lot · swap│
├───────────────────────────────────────────────────────┴──────────────────────────┤
│ MTF strip: H4 · H1 · M30 · M15 · M5 · M1                                           │
├───────────────────────────────────────────────────────────────────────────────────┤
│ [Nhật ký] [Bằng chứng] [Sức khỏe dữ liệu]   ← ngăn kéo thu gọn (mặc định đóng)     │
└───────────────────────────────────────────────────────────────────────────────────┘
```

Nguyên tắc: (1) vừa một màn hình 1440×900 không cần cuộn để thấy hành động, lý do, rủi ro (repo cũ phải cuộn: khung Execution bị cắt); (2) mức bằng chứng luôn trên thanh trạng thái; (3) mọi con số hiệu suất có benchmark; (4) không có trang mồ côi, không có 503 khi tính năng tắt.

## 5. Đề xuất bước tiếp

1. Bạn xác nhận hướng **một trang** (và duyệt/bỏ thêm công cụ vẽ).
2. Tôi cập nhật Prompt xây dựng: thay Y8 ("UI 4 trang") bằng **"một route `/` + ngăn kéo"**, thêm bước G0 đọc `reference-v1/` làm đầu vào, và quy tắc "không import từ `reference-v1`, chỉ chép có chọn lọc rồi viết test".
3. Chạy G0 (thiết kế), dừng để bạn duyệt trước khi viết mã.

## 6. Giới hạn

Số dòng và phân loại giá trị dựa trên đọc nhanh các file chính (`action.ts`, `honesty.ts`, `lifecycle.ts`, đầu `TerminalChart.tsx`) và đếm theo thư mục; tôi chưa đọc hết 9.929 dòng component. "Giá trị cao/trung bình/thấp" là nhận định của tôi, dựa trên vai trò trong luồng quyết định và kết quả kiểm toán. Chưa chạy lại bộ e2e cũ trên bản sao.
