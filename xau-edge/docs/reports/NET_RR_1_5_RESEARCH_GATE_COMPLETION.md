# NET R:R 1.50 Research Gate Completion

Ngày: 2026-10-11  
Phạm vi: `structure/` và `decision_research/`; baseline/live engine không đổi.  
Phân loại dữ liệu: Development-2 H1, BURNED; chỉ mô tả hình học/tần suất, không đọc outcome.

## 1. Executive Verdict

**PASS cho research gate và bộ bảo vệ; FAIL cho điều kiện cấp entry-eligible từ dữ liệu hiện có.** Ngưỡng code mặc định hiện là 1.50 net R:R và không thể hạ thấp. Không setup nào được cấp candidate nếu chi phí chưa verified, room thiếu, geometry sai, entry chưa causal, stop/target chưa hợp lệ hoặc risk guard chưa đạt. Không setup nào trong phép đo Development-2 đủ dữ liệu để được authorize: giá khớp kế tiếp và mô hình all-in costs đã xác minh chưa có.

R:R 1.50 chỉ là sàn hình học payoff cần thiết. Nó không chứng minh edge, xác suất thắng, EV hay khả năng sinh lời. Break-even là phép tính lý thuyết; sau chi phí tỷ lệ cần cao hơn và không phải predicted win probability.

## 2. Code Reality

- `trading/levels.py`: stop mặc định HYBRID = max(structure distance + 0.10 ATR buffer, 1.25 ATR); từ chối nếu stop > 3.0 ATR. TP1 mặc định 2.0R, bị chặn tại structure đối diện sau buffer 0.10 ATR; net floor 1.50 chỉ tính spread. TP2 3.0R, chỉ có khi TP1 không bị structure cap.
- Baseline BUY/SELL vào ask/bid nếu có; nếu không, ước tính từ close và nửa spread. Baseline target formula chỉ đưa spread vào chi phí, không gồm slippage, commission hoặc swap. Không sửa baseline trong sprint này.
- `decision_research/authorization.py` trước sprint mặc định 2.0. Đây là sai lệch với chính sách được giao; nay mặc định/minimum là 1.50.
- Reversal detector giữ trigger close lịch sử nhưng trước đây dùng nó như entry reference khi trigger xảy ra trước lúc pattern được xác nhận. Nay entry reference là actionable close; đây vẫn chỉ là reference, không phải giá fill.
- Wolfe dùng close lúc P5 được xác nhận (hoặc close tại LINE13_RECLAIM), P5 làm stop, EPA làm target. Mặc định detector lọc gross RR dưới 1.0, không phải net 1.50.
- Tài liệu V4 đang dùng được cập nhật sang 1.50. Báo cáo lịch sử giữ nguyên ngưỡng 2.0 như một nhận định tại thời điểm viết; không sửa research history. Một biến thể 2.0 chỉ được thử trong charter preregister riêng nếu owner cho phép.

## 3. Current RR Implementation

Canonical utility là `decision_research/rr.py`: `NET_RR = max(0, reward - total_costs) / (risk + total_costs)`, với total costs = spread + slippage + commission + swap, cùng đơn vị giá. Công thức tính một round-trip cost bảo thủ ở cả nhánh thắng và thua. CostModel nay bắt buộc đủ bốn giá trị, source và `verified`; unverified chặn authorization. Các giá phải được làm tròn bất lợi theo tick trước khi RR tính lại: BUY entry lên, stop xuống, target xuống; SELL làm ngược lại.

Room được làm tròn xuống và phải còn ít nhất một tick phía sau target. Geometry sai phía trả về invalid; unknown room không được coi là room miễn phí. Không có công thức RR thứ hai trong authorization.

## 4. Detector Geometry Audit

Đã chạy defaults cố định trên 48,470 bar H1 Development-2, từ loader `load_dev2_h1` có filter tại scan; thời gian chỉ trong 2011-01-01 đến trước 2019-01-01. Entry tham chiếu là actionable close, giá được tick-round bất lợi. Các số dưới đây là gross geometry, không phải fill hay NET R:R.

| Detector | N | Entry distance median (max) | Stop distance median | Target distance median | Gross R:R median | Gross >=1.5 |
|---|---:|---:|---:|---:|---:|---:|
| Double Top | 143 | 0 (15.20) | 15.99 | 10.29 | 0.74 | 2 |
| Double Bottom | 144 | 0 (14.55) | 15.03 | 9.35 | 0.77 | 4 |
| Head & Shoulders | 3 | 2.74 (3.62) | 14.65 | 28.08 | 1.94 | 3 |
| Inverse H&S | 4 | 0 (2.03) | 18.97 | 22.45 | 1.23 | 1 |
| Wolfe | 71 | 0 (0) | 5.74 | 20.85 | 3.64 | 64 |

Các giá trị trên dùng close và textbook invalidation/target tại detection. Số gross cho thấy target measured-move của top/bottom thường không bù được stop ở đỉnh/đáy invalidation. Wolfe gross cao bị cấu trúc đối diện chặn ở 70/71 trường hợp. H&S có mẫu chỉ 7 setup tổng, không đủ để kết luận tần suất bền vững.

## 5. Failure Reasons

Phân loại có thể chồng lấp; không cộng các cột để suy ra tổng reject.

| Reason | Count | Diễn giải |
|---|---:|---|
| STOP_TOO_WIDE | 217 reversal geometry hợp lệ | Stop distance > 3 ATR, dùng mức 3 ATR baseline làm diagnostic cố định; Wolfe thiếu ATR reference nên không xếp loại này. Không bóp stop. |
| TARGET_TOO_CLOSE | 271 geometry hợp lệ | Gross R:R đã <1.50 trước chi phí. Sau chi phí không thể cải thiện. |
| INSUFFICIENT_ROOM | 344/365 | nearest opposing pivot đã confirmed tại detection nằm trước target hoặc không đủ một tick buffer. |
| COST_UNVERIFIED | 365/365 | H1 extract không có spread/next-open fill tương ứng; commission 0 được tài liệu dự án đánh dấu CHƯA XÁC MINH; swap cũng chưa có chuyển đổi price-unit đã xác minh. |
| ENTRY_TOO_LATE | 41/365 có trigger delay >0 | Trigger event có trước confirmation. Geometry nay dùng actionable close thay cho trigger close quá khứ. Actual next-open fill vẫn không có trong detector output. |
| INVALID_GEOMETRY | 20/365 | Sai thứ tự entry/stop/target sau tick rounding; không tính RR. |

NET R:R distribution không được bịa từ chi phí giả định. Cost uncertainty chặn toàn bộ authorization cho phép đo này; 0 setup entry-eligible.

## 6. Predefined Options

Các tiêu chí được chốt trước phép đo: causality; ít tham số; stop hợp lệ theo invalidation; target thực tế; room; robustness với chi phí; giữ tần suất; testability; độ phức tạp triển khai.

## 7. Selection Criteria

- Causality: chỉ dùng thông tin có tại actionable close; fill tiếp theo cần xác minh riêng.
- Stop validity: điểm invalidation theo detector, không thay đổi khoảng stop để đạt tỷ lệ.
- Target realism/room: target gốc phải ở trước structure đối diện với tối thiểu một tick buffer.
- Costs: tất cả bốn khoản có nguồn, verified; không có nghĩa là một khoản bằng 0 nếu chưa xác minh.
- Frequency retention: báo cả N gốc và N sau từng gate; không coi ít setup là lỗi.
- Testability/complexity: utility RR duy nhất, deterministic tick rounding, test property và mutation.

## 8. Chosen Approach

Chọn **A: giữ target logic hiện có, reject mọi setup dưới 1.50 net hoặc thiếu bất kỳ gate nào**. Không sửa target để tăng RR. Không siết stop.

B bị loại: Wolfe LINE13_RECLAIM là chờ thêm sau P5, không phải entry sớm hơn. Trên 930 geometry synthetic walk có ở P5, 652 cũng xuất hiện trong reclaim mode; số bar chờ median 0, còn tỷ lệ stop-distance reclaim/P5 median 1.0, p75 1.0, max 38.81. Không có bằng chứng geometry đủ để đổi default.

C bị loại: target thay thế không có quy tắc cấu trúc đã preregister chứng minh room. Đẩy target qua resistance/support là không hợp lệ. Kết quả ít setup hoặc không có setup là kết quả chấp nhận được.

## 9. Implementation

- Default `Thresholds.min_net_rr` thành 1.50; validation không cho cấu hình thấp hơn.
- Bổ sung tick size vào research Proposal; làm tròn bất lợi trước canonical NET_RR.
- Proposal phải khai báo entry causal, stop/target structural validity và `risk_ok`; mặc định thiếu thông tin là WAIT.
- Chi phí cần spread/slippage/commission/swap/source/verified; `verified=False` trả `COST_MODEL_UNVERIFIED`.
- Room thiếu, bằng đúng target boundary hoặc không chừa một tick buffer đều trả `NO_ROOM_TO_TARGET`.
- Reversal detector lưu `entry_reference` tại detection close, giữ `trigger_close` làm event context. Thống kê ưu tiên entry reference.
- Không phát TradingSignal; không nối research authorization với TradeEngine/PaperDesk.

## 10. Net-Cost Handling

Formula bắt buộc nhận cost bằng đơn vị giá, không âm, hữu hạn. Cost stress unit tests dùng spread 0.01 / 0.10 / 0.25 cùng explicit zero cho các thành phần còn lại; setup test chỉ pass ở spread thấp, fail ở mức thường/cao. Đây là contract test tổng hợp, không phải spread đo từ Development-2.

Tài liệu broker hiện có nói commission 0 chưa xác minh; lịch sử H1 không chứa fill kế tiếp và spread đúng tại thời điểm lệnh. Vì thế net distribution, net pass count và lowest authorized NET_RR của market data là **N/A**. Không thay bằng 0 hoặc con số tự chọn.

## 11. Structure-Room Handling

Nearest opposing confirmed pivot chỉ được dùng nếu `confirmed_at <= actionable_at`; target phải dừng trước pivot tối thiểu một tick. 344/365 không đủ room. Test riêng cho mathematical target 1.5R nhưng resistance/support nằm trước target trả `NO_ROOM_TO_TARGET`. Unknown room cũng reject.

## 12. Tests

- Property test Hypothesis: không có `BUY_CANDIDATE` nào có net RR <1.50 trên nhiều cost/target combinations.
- Cost-drop: gross 1.60, all-in costs làm net <1.50, kết quả `NET_RR_BELOW_MIN`.
- Structure-room: target vượt/đụng barrier bị reject.
- Wrong side BUY/SELL, tick rounding, unverified/omitted costs, spread thấp/thường/cao, stop/target/entry/risk flags đều có test.
- Prefix invariance dùng harness `causality_violations` và các kiểm tra prefix đã có cho reversal/Wolfe; late-entry regression khóa entry reference tại actionable time.
- Không có future return, TP/SL hit, PnL, win rate, expectancy hoặc profit factor trong phép đo.
- `ruff check`: PASS; `ruff format --check`: PASS (777 Python files); `mypy`: PASS (488 files); `pytest -m "not mt5"`: 2801 passed, 1 skipped (Windows symlink privilege), 3 deselected (MT5); targeted research/structure: 141 passed.

## 13. Mutation Tests

Deliberately mutated floor minimum, cost aggregation, room comparison, structural-stop guard, and BUY/SELL sign. Mỗi mutation bị test liên quan bắt (test chuyển RED); các thay đổi probe đã được gỡ. Mẫu: floor mutant bị `test_policy_floor_cannot_be_lowered_below_one_point_five` bắt; bỏ cost bị cost-drop test bắt; bỏ room bị room test bắt; bỏ structural stop bị gate test bắt; đảo SELL sign bị symmetry test bắt.

## 14. Descriptive Frequency Result

| Detector | Setup count | Gross >=1.5 | Reject gross <1.5 hoặc geometry invalid |
|---|---:|---:|---:|
| Double Top | 143 | 2 | 141 |
| Double Bottom | 144 | 4 | 140 |
| H&S | 3 | 3 | 0 |
| Inverse H&S | 4 | 1 | 3 |
| Wolfe | 71 | 64 | 7 |
| **Tổng** | **365** | **74** | **291** |

Trong 291 trường hợp cuối, 271 có geometry hợp lệ nhưng gross <1.5; 20 geometry invalid. Sau khi xét các gate khác, 0 eligible. Trong 74 gross pass, net pass không thể xác định vì `REJECT_COST`.

## 15. Random / Block-Shuffle Control

Chỉ so sánh tần suất detector, không so PnL.

| Detector | Dev-2 thật / 10k H1 | Block shuffle mean (range), 20 lần | Gaussian random walk mean / 10k, 20 x 10k |
|---|---:|---:|---:|
| Wolfe | 14.65 | 15.84 (14.44–18.57) | 46.50 |
| Double Top/Bottom | 59.21 | 55.75 (53.64–58.59) | 58.50 |
| H&S family | 1.44 | 2.70 (1.24–3.92) | 4.25 |

Geometry frequency không chứng minh edge; các tần suất gần control không được diễn giải thành xác suất thắng.

## 16. Red-Team Findings

- Far TP: detector target gốc bị room gate; không kéo qua structure.
- Tight stop: stop giữ nguyên invalidation; 217 reversal geometry hợp lệ vượt diagnostic 3 ATR, không sửa stop để cứu RR.
- Omit spread/slippage/commission/swap: constructor bắt đủ trường; unverified hard-block.
- Tick rounding: adverse rounding trước authorization; test tạo pre-round pass nhưng rounded fail.
- Future structure/pivot: chỉ pivot đã confirmed tại actionable time được dùng.
- Wrong SELL side: sign-symmetry test bắt lỗi.
- Thin liquidity/volatile spread: không có fill/spread H1 đáng tin; không tạo market eligibility. Synthetic variable-spread tests chỉ xác nhận gate phản ứng theo cost.
- Reused future pivot / prefix: detector harness kiểm tra prefix; no future outcomes loaded.

## 17. Frequency Cost

Before geometry/cost/room gates: **365**. Gross floor giữ lại **74/365 = 20.3%** trước room/cost. Gross dưới sàn: **271/365 = 74.2%**; invalid geometry: **20/365 = 5.5%**. Room gate loại **344/365 = 94.2%** (overlaps other reasons). Cost verification loại **365/365 = 100%** khỏi authorization. Cuối cùng **0/365 entry-eligible**. Các reject reason chồng lấp, ngoại trừ partition gross pass/fail + invalid.

## 18. Remaining Risks

- Net R:R và realistic frequency retention chưa định lượng được trên H1 lịch sử do thiếu next-open executable fill và verified all-in cost model.
- Commission 0 chưa xác minh; swap cần chuyển đổi theo holding time, side, lot và broker terms.
- Nearest confirmed pivot là diagnostic room proxy; chưa phải room service đa timeframe được production validate.
- H&S 7 trường hợp và Wolfe target convention có ít dữ liệu; mọi detector vẫn geometry-only.
- Break-even rate là lý thuyết; xác suất thắng/edge cần charter outcome riêng và dữ liệu sạch.

## 19. Baseline Live-Engine Impact

**Không thay đổi** `trading/levels.py`, `trading/baseline.py`, `baseline_v12.py`, execution, PaperDesk, API hay dashboard. Baseline hiện net gate chỉ trừ spread; thêm cost hay thay hành vi cần bug finding + ADR riêng và xác nhận scope. Partial TP vẫn DISABLED; break-even move/trailing vẫn UNVALIDATED / DISABLED.

## 20. Final Verdict

Research gate hiện chặn mọi trường hợp thiếu chi phí verified, fill causal, geometry đúng phía, stop/target structural, room và risk guard; không có setup nào được phát thành lệnh production. Bộ 1.50 là sàn hình học cần thiết, không đủ để kết luận edge hay xác suất thắng. Phép đo mô tả không dùng bất kỳ outcome metric nào và không mở Test-H, Holdout hoặc Validation-2.

SCOPE:
RESEARCH DETECTORS

MINIMUM NET R:R:
1.50

LIVE ENGINE MODIFIED:
NO

TOTAL SETUPS:
365

ENTRY-ELIGIBLE AFTER 1.5 FILTER:
0

REJECTED BELOW 1.5:
271 / 365 (74.2% known gross-under-floor; additional cost drops unknown)

REJECTED FOR STRUCTURE ROOM:
344 / 365 (94.2%, overlapping reasons)

REJECTED FOR COST:
365 / 365 (100%, cost/fill model unverified)

REJECTED FOR INVALID GEOMETRY:
20 / 365 (5.5%)

LOWEST AUTHORIZED NET R:R:
N/A (no authorized setup)

PROPERTY TEST:
PASS

COST-DROP TEST:
PASS

STRUCTURE-ROOM TEST:
PASS

PREFIX-INVARIANCE:
PASS

MUTATION TESTS:
PASS

OUTCOME METRICS USED:
NO

WIN PROBABILITY CLAIMED:
NO

EDGE CLAIMED:
NO

PARTIAL TP:
DISABLED

BREAK-EVEN / TRAILING:
DISABLED

TEST-H TOUCHED:
NO

HOLDOUT TOUCHED:
NO

COMMIT:
ed293d1

PUSHED:
NO

OVERALL VERDICT:
The 1.50 net-R:R research floor and its hard safeguards are implemented and tested. No setup is entry-eligible from this dataset because complete verified costs and executable next-open fills are unavailable; every candidate remains WAIT/REJECT. No live engine code or protected evaluation data was touched.
