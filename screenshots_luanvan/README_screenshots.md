# Ảnh chụp màn hình DSS cho luận văn

Chụp trên hệ thống thật (localhost:3000), tài khoản admin. **B2/B3/C2 dùng Run #30** — chạy sau khi fix bug công thức SI, nên số SI trung bình trong ảnh là đúng (≈1.127, không còn bị lỗi 21,879 như run cũ). Objective 114.359.643,94 và tiết kiệm 52,92% — sai lệch chỉ 0,03% so với Run #28 (114.390.681,6 / 52,91%), nằm trong biên độ dao động tự nhiên của giải thuật MA (giống 10 lần chạy độc lập ở Bảng 7.1 luận văn), nên hoàn toàn dùng được làm số liệu chính thức. A1/A2/B1/C1 không phụ thuộc run cụ thể.

---

## fig:ui_dashboard → `screenshot_dashboard.png`
**Trang A1 — Tổng quan dữ liệu đầu vào.** Trang đầu tiên sau khi đăng nhập, đóng vai trò cổng kiểm tra chất lượng dữ liệu trước khi chạy tối ưu. Hiển thị 4 chỉ số quy mô bài toán (943 sản phẩm, 6 kho, 10 kỳ, 56.580 tổ hợp), bảng mức độ hoàn chỉnh của 13 tham số đầu vào (Bảng 3.3 luận văn: BI, CP, U, L, ΔI, CAP, 4 loại chi phí, LT_OA, LT_PLT, khoảng cách), cùng 2 biểu đồ trực quan hoá chỉ số chất lượng và độ hoàn chỉnh từng tham số.

## fig:ui_data_management → `screenshot_data_management(1)` và `screenshot_data_management(2).png`
**Trang A2 — Tham số mô hình (tab "Tham Số").** Trung tâm cấu hình hệ thống, gồm 3 bảng: (1) Tham số giải thuật tối ưu — 13 tham số điều khiển giải thuật Memetic (GA-ALNS), diễn giải bằng ngôn ngữ nghiệp vụ dễ hiểu; (2) Tham số chi phí & vận hành — 7 giá trị nền thực tế doanh nghiệp (Co, Cs, Cb, Cp, TC, LT_OA, LT_PLT), chỉ hiển thị tham khảo; (3) Tham số mô hình — hằng số kỹ thuật có thể chỉnh sửa trực tiếp.

## fig:ui_optimization_run → `screenshot_optimization_run.png`
**Trang B1 — Thực thi tối ưu hoá (tab "Lịch Sử").** Bảng danh sách 26 lần chạy tối ưu đã thực hiện, mỗi dòng gồm mã lần chạy, phiên bản dữ liệu, thời gian chạy, trạng thái solver (optimal), chi phí tối ưu đạt được, thời gian giải, và nút thao tác xem chi tiết/điều hướng sang B2.

## fig:ui_cost_analysis → `screenshot_cost_analysis.png`  *(Run #30)*
**Trang B2 — Kết quả & Chi phí (tab "Phân tích chi phí").** Trang kết quả trung tâm của hệ thống. 5 thẻ KPI đầu trang: chi phí cơ sở hiện trạng (242.914.822), tổng chi phí tối ưu (114.359.644), mức độ phục vụ (89,7%), **tiết kiệm so với hiện trạng 52,92%**, thời gian giải (9.627s). Bên dưới là bảng + biểu đồ cột 5 thành phần chi phí (nợ đơn 108.250.511 chiếm 94,66% — chi phối), khối so sánh Hiện trạng vs MA Tối ưu, và bảng chi tiết lần chạy.

## fig:ui_allocation_transshipment → `screenshot_allocation_transshipment.png`  *(Run #30)*
**Trang B3 — Phân bổ & Động thái tồn kho (tab "Điều chuyển ngang PLT").** Ma trận 6×6 kho thể hiện tổng lượng hàng điều chuyển ngang giữa các cặp kho, biểu đồ cột chồng lượng PLT theo kỳ (theo kho nguồn), và bảng chi tiết từng giao dịch PLT. Bằng chứng trực quan cho cơ chế "điều chuyển ngang chủ động" — đóng góp cốt lõi của mô hình SS-MB-SMI.
→ *Ảnh phụ* `screenshot_allocation_transshipment_products.png` *(Run #30)*: tab "Phân bổ theo sản phẩm" — chọn sản phẩm P0001, hiển thị đầy đủ kế hoạch phân bổ OA (kiện hàng Q, đơn vị lẻ r, tồn kho I, backorder, overstock, shortage) theo từng kho × từng kỳ.

## fig:ui_inventory_tracking → `screenshot_inventory_tracking.png`  *(Run #30)*
**Trang B3 — tab "Quỹ đạo tồn kho theo kho".** 6 thẻ tổng quan backorder mỗi kho, biểu đồ đường đa kho thể hiện quỹ đạo tồn kho ròng qua 10 kỳ, và bảng tổng hợp backorder/overstock/shortage theo từng kho suốt kỳ hoạch định.
→ *Ảnh phụ* `screenshot_inventory_tracking_b2_variant.png` *(Run #30)*: trang B2 tab "Biến quyết định & SI/SS" — biểu đồ q/r phân bổ theo kỳ và biểu đồ "Tồn kho (I), vượt ngưỡng và thiếu hụt" cho 1 sản phẩm cụ thể. **Thẻ "SI trung bình" = 1.127** — đã đúng (trước đây bug cho ra 21,879, đã fix và chạy lại MA để cập nhật số này).

## fig:ui_scenario_comparison → `screenshot_scenario_comparison.png`  *(Run #30 vs #29)*
**Trang C2 — So sánh kịch bản, sau khi bấm "So sánh KPI" giữa Run #30 và Run #29** (kịch bản what-if "Nới ngưỡng tồn kho ±25%"). Hiển thị đầy đủ: 3 thẻ tổng quan, khối tóm tắt thay đổi bằng ngôn ngữ tự nhiên (Tổng chi phí giảm 26,3%, Mức độ phục vụ tăng 2,1%...), biểu đồ cột song song, và bảng chi tiết 7 KPI với % thay đổi (màu theo hướng tốt/xấu đúng logic — Mức độ phục vụ tăng được tô xanh).
→ *Ảnh phụ* `screenshot_scenario_comparison_c1_variant.png`: trang C1 "Phân tích What-If" — 6 nhóm kịch bản dạng thẻ bấm chọn và bảng lịch sử 17 kịch bản đã chạy.

---

## Lưu ý khi đưa vào luận văn
- Toàn bộ ảnh chụp full-page, độ phân giải gốc 1600px chiều rộng.
- Số liệu chính thức để trích dẫn: **114.359.644** (chi phí tối ưu), **52,92%** (tiết kiệm) — từ Run #30. Nếu muốn khớp tuyệt đối 100% với số đã in trong Chương 7 (114.390.682 / 52,91%), dùng Run #28 thay thế (chênh lệch không đáng kể, 0,03%).
- Phía "kịch bản so sánh" ở C2 (Run #29) chỉ minh hoạ tính năng so sánh, không phải số liệu cần trích dẫn riêng.
