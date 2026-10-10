# TRADE-08 — rubric cố định (viết TRƯỚC khi chụp/chấm bất kỳ biến thể nào)

## Biến thể "thiên hướng ≠ hành động" (WATCH không được giống lệnh)

- A: dải **Thiên hướng ↑ MUA** mỏng phía trên thẻ hành động trung tính.
- B: chữ **CHỜ** lớn + biểu ngữ viền đứt "ĐANG HÌNH THÀNH SETUP MUA · KHÔNG VÀO LỆNH".
- C: hai ô **BIAS | HÀNH ĐỘNG** cạnh nhau (BIAS ↑ MUA nhỏ, HÀNH ĐỘNG CHỜ lớn) + dòng SETUP.

## Cổng cứng (một vi phạm = biến thể bị loại)

Người chấm mù, nhìn ảnh 5 giây, **không được** coi một trạng thái WATCH/ARMED là cho phép giao dịch. Chỉ cần 1 người chấm trả lời "được phép mua/bán" cho một ảnh WATCH là loại biến thể.

## Tiêu chí điểm (0–2 mỗi mục, chỉ xét biến thể qua cổng)

1. Hiểu hành động trong 5 giây (CHỜ).
2. Phân biệt rõ "thiên hướng" với "được phép": người chấm tự diễn đạt đúng.
3. Đọc được hướng đang được ưu tiên (MUA/BÁN).
4. Đọc được điều kiện còn thiếu (một điều cụ thể).
5. Không nhầm với trạng thái MUA PAPER/BÁN PAPER đứng cạnh (ảnh đối chứng).
6. Gọn trên điện thoại 390 px.
7. Độ tương phản/accessibility (axe sáng + tối).
8. Độ phức tạp và khả năng bảo trì.

Thắng = qua cổng cứng, tổng điểm cao nhất; hòa thì chọn phương án đơn giản hơn. Cổng riêng cho bố cục phone nằm ở mục Mobile bên dưới.

---

## Mobile (390×844 và 844×390) — định nghĩa trước khi dựng

Chiều cao biểu đồ **tối thiểu dùng được** = 280 px nến thật (không tính thanh công cụ), đo trong màn hình đầu tiên, không cuộn.

Cổng cứng ở 390×844, không cuộn: thấy **giá**, **hành động**, **một câu "khi nào / thiếu gì"** (≥ 1 dòng đầy đủ) và biểu đồ ≥ 280 px; thanh hành động dính (nếu có) không che nến/giá mới nhất; không cuộn ngang.
Ở 844×390: nút Xác nhận/Hủy luôn nằm trong màn hình; biểu đồ ≥ 160 px sau tối đa 1 lần cuộn.

Phương án:
- A: header quyết định gọn (giá + hành động trên một dải) → biểu đồ → thanh hành động dính.
- B: biểu đồ trước, quyết định là bottom sheet kéo lên.
- C: quyết định thu gọn được (mặc định gọn: hành động + 1 dòng), biểu đồ chiếm phần lớn.

Tiêu chí: cổng cứng; hiểu hành động trong 5 giây; kiểm soát vô tình (chạm nhầm); độ phức tạp.

---

# Kết quả (ghi SAU khi chấm; rubric ở trên không bị sửa)

## 1. "Thiên hướng ≠ hành động" — bốn người chấm mù, 20 ảnh từ backend replay thật

Vòng 1 (A, B, C; 15 ảnh xáo trộn × 2 người chấm, tên trung tính): **cả ba biến thể qua cổng cứng** (mọi ảnh WATCH/ARMED trả lời "KHÔNG được phép giao dịch"). Phát hiện:

| Biến thể | Điểm yếu do người chấm nêu |
|---|---|
| A (dải thiên hướng phía trên) | đọc "MUA/BÁN" trước "CHỜ"; ghi chú "không phải lệnh" quá nhỏ |
| B (biểu ngữ viền đứt hổ phách) | màu hổ phách đọc như cảnh báo; "KHÔNG VÀO LỆNH" nằm cuối câu; dài, xuống dòng xấu |
| C (hai ô BIAS \| HÀNH ĐỘNG cạnh nhau) | **rủi ro nhất**: "↑ MUA" lớn đứng cạnh CHỜ đọc thành "mua, chờ" |

Biến thể D (mới, rút từ phát hiện trên): hành động CHỜ lớn + nhãn "KHÔNG VÀO LỆNH" ngay cạnh; **thiên hướng nhỏ, có nhãn, nằm DƯỚI hành động**, kèm "chỉ là hướng thị trường nghiêng về, không phải lệnh"; dòng "Chỉ MUA/BÁN khi: …" cụ thể.

Vòng 2 (D, 5 ảnh × 2 người chấm mới): **qua cổng cứng, 10/10 ảnh**: thiên hướng được đọc là "LEAN", chưa lần nào là "PERMISSION", độ tự tin 4–5. Góp ý áp dụng: nhãn "KHÔNG VÀO LỆNH" có ở **mọi** trạng thái CHỜ; ghi chú đậm hơn; "Chỉ MUA khi:" (thêm "Chỉ"); "nến" rõ nghĩa; "Điều kiện vào lệnh: đạt n/8 — cần đủ tất cả".

**Thắng: D** (qua cổng, điểm cao nhất theo tiêu chí 2–5, đơn giản ngang A).

## 2. Bố cục điện thoại 390×844 (cổng định trước: biểu đồ ≥ 280 px, thấy giá + hành động + câu "khi nào", không cuộn)

Đo trên replay thật (px nến nhìn thấy; WAIT/BUY/ARMED):

| | A | B | C |
|---|---|---|---|
| biểu đồ nhìn thấy | 313 / 328 / 288 | 448 (mọi trạng thái) | 313 / 352 / 332 |
| hành động trong màn hình đầu | có | **KHÔNG (y≈902)** | có |

B loại ở cổng cứng. Người chấm mù (6 ảnh): C xếp trên A (dòng phụ lặp huy hiệu, tốn ~20 px biểu đồ); B xếp cuối (không có quyết định ở màn hình đầu). **Thắng: C** (bỏ dòng phụ chỉ khi nó lặp huy hiệu; mọi trạng thái khác giữ dòng phụ).

Trước đó (TRADE-07): 87–93 px. Sau: 288–411 px. Ngang (844×390) và zoom 200% (720×450) cũng có biểu đồ nhờ bố cục hai cột "short" (cổng ≥ 160 px, có test).
