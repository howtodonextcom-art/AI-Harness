# POSITION-01: kiểm toán quản lý vị thế (bàn PAPER)

> Ngày: 2026-10-11. Chỉ ĐỌC mã nguồn và tài liệu hoá; không đổi hành vi. PAPER ONLY, không lệnh thật.
> Nguồn sự thật: `src/xau_edge/trading/paper_desk.py`, `position_manager.py`, `governor.py`, `engine.py`.

## 1. Đã triển khai (mặc định đang chạy)

| Chức năng | Trạng thái | Bằng chứng |
|---|---|---|
| Mở lệnh PAPER từ setup đã kiểm tra (mỗi `setup_id` một lệnh, trùng bị từ chối) | CÓ | `paper_desk.py` `open_*`, idempotence |
| Stop loss cố định theo kế hoạch (`SL` của setup), chạm trong nến thì thoát `STOP_LOSS` | CÓ | `position_manager.evaluate`; cùng nến chạm cả SL và TP thì coi SL trước (bi quan) |
| Take profit 1 theo kế hoạch (`TP1`); `TP2` chỉ hiển thị trong plan, không có chốt từng phần | CÓ (chỉ TP1 thoát) | `levels.py`, `paper_desk` |
| Thoát theo thời gian: giữ tối đa 120 phút (`max_hold_minutes`) | CÓ | `DeskConfig.max_hold_minutes`, `DeskExit.TIME_EXIT` |
| Chính sách đóng cửa thị trường (mặc định chặn lệnh mới nếu thời gian giữ tối đa chạm vào giờ đóng cửa) | CÓ | `ClosurePolicy.BLOCK_NEW_NEAR_CLOSE` (+ `CLOSE_BEFORE_CLOSURE`, `HOLD_ACROSS_CLOSE` cấu hình được) |
| Đóng tay lệnh PAPER (`MANUAL_CLOSE`) với xác nhận, không nhận giá/lot/hướng từ trình duyệt | CÓ | route đóng lệnh của `/trade`, tuân AGENTS.md |
| Giới hạn quản trị rủi ro: lỗ ngày tối đa, số lệnh/ngày (hiện 6), rủi ro/lệnh chọn trong 0.10/0.25/0.50% | CÓ | `governor.py`, `risk_calc.RISK_CHOICES` |
| Sổ nhật ký: R, MFE, MAE, thời lượng, phí, lý do thoát, phiên bản chiến lược, SHA mã | CÓ | `paper_desk` journal |
| Phục hồi sau khởi động lại; trạng thái hỏng thì dừng và nói rõ (`UNAVAILABLE`), không đoán | CÓ | `paper_recovery.py` |
| Hiển thị vị thế: R hiện tại, P&L, khoảng cách tới SL/TP, thời gian còn lại tới hạn giữ, lý do thoát cuối | CÓ | `DecisionPanel` `PositionPanel`, `desk.last_exit` |

## 2. Có mã nhưng TẮT mặc định (không được bật trong sprint này)

| Chức năng | Mã | Trạng thái |
|---|---|---|
| Dời SL về hoà vốn (`break_even_enabled`, ở 1.0R, đệm 0.05R) | `position_manager.py` | `False` |
| Trailing stop (ATR / SWING / CHANDELIER) | `position_manager.py` | `TrailModel.NONE` |
| Đóng khi setup vô hiệu (`close_on_invalidation`) | `paper_desk.DeskConfig.manager` | `False` |
| Chốt từng phần | KHÔNG CÓ mã | chưa tồn tại |

Đây là mã được kiểm thử (đơn vị) nhưng chưa có bằng chứng forward, nên bàn giữ chúng TẮT: đúng thiết kế
("bật bằng cấu hình tường minh, sau khi có bằng chứng, không bao giờ tự động").

## 3. Chưa có / khoảng trống sản phẩm

* Không có nút PROTECT hay gợi ý "dời SL về hoà vốn" trên màn hình (người dùng chỉ thấy khoảng cách tới SL/TP).
* Không có chốt từng phần (partial TP) và không có TP2 dạng thoát.
* Không có cảnh báo "sắp hết thời gian giữ" ngoài đồng hồ đếm lùi trong khung vị thế.
* Không có ghi chú/nhãn của người dùng gắn vào lệnh paper (nhật ký chỉ có dữ liệu của máy).

## 4. Phân loại cho việc làm sau (QUAN TRỌNG: ranh giới sản phẩm và alpha)

| Việc | Loại | Vì sao | Điều kiện để làm |
|---|---|---|---|
| Hiển thị thêm: R nếu chạm TP/SL, khoảng cách tới hoà vốn, MFE/MAE đang chạy | **Sản phẩm/UX** | chỉ đọc số liệu có sẵn, không đổi kết quả lệnh | được làm ngay, có test hiển thị |
| Cảnh báo giao diện "còn N phút tới hạn giữ" | **Sản phẩm/UX** | thuần hiển thị | được làm |
| Tự động dời SL hoà vốn / trailing / chốt từng phần trên bàn PAPER | **THAY ĐỔI ALPHA** | đổi phân phối R thực hiện của chiến lược; bằng chứng forward hiện có sẽ không còn so sánh được | phải có phiên bản chiến lược mới, A/B có quản trị, không đụng v1.1.0, không đụng holdout/Test-H |
| Nút "dời SL về hoà vốn" do người dùng bấm | **Chưa quyết (nghiêng alpha)** | biến bàn PAPER thành giao dịch tuỳ ý: nhật ký không còn là bằng chứng của chiến lược; AGENTS.md cấm endpoint nhận SL/TP tuỳ ý (nút không tham số vẫn đổi kết quả) | chỉ làm nếu sổ nhật ký ghi rõ cờ "QUẢN LÝ TAY" và bị loại khỏi bằng chứng forward |
| Đổi `max_hold_minutes`, `closure_policy` mặc định | **THAY ĐỔI ALPHA/VẬN HÀNH** | đổi thời điểm thoát | quản trị như trên |

## 5. Kết luận

Quản lý vị thế hiện tại ĐÚNG VỚI THIẾT KẾ của baseline: SL/TP/hạn giữ cố định, có đóng tay, có giới hạn rủi ro,
nhật ký đầy đủ. Không có tính năng "bảo vệ lãi" nào đang chạy; mã cho hoà vốn và trailing tồn tại nhưng TẮT
và chưa có bằng chứng. Bất kỳ việc bật chúng là quyết định chiến lược (alpha), không phải việc UX.
