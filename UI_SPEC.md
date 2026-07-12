# Đặc tả giao diện DSS — SS-MB-SMI

> Tài liệu mô tả chi tiết chức năng, vai trò và nội dung hiển thị của từng trang trong hệ thống, dùng để đối chiếu khi chụp màn hình và viết mô tả trong luận văn.
> Số liệu minh hoạ lấy từ dữ liệu thực đang chạy (943 sản phẩm, 6 kho khai báo / 4 kho có mặt trong dữ liệu vận hành, 10 kỳ thời gian).

---

## Nhóm A — Dữ liệu & Cấu hình

### A1. Tổng quan dữ liệu đầu vào

**File:** `frontend-react/src/pages/A1_DataOverview.jsx`
**Route:** `/a1-data-overview`
**API:** `GET /api/v1/data-overview/`

#### Vai trò
Trang đầu tiên người dùng gặp sau khi đăng nhập — đóng vai trò **cổng kiểm tra chất lượng dữ liệu** trước khi chạy tối ưu. Trả lời câu hỏi: "Dữ liệu đầu vào đã đủ, đúng, sẵn sàng để đưa vào mô hình MILP/MA chưa?" Đây là bước bắt buộc về mặt quy trình (không kỹ thuật) trước khi sang nhóm B.

#### Chức năng chính
1. **Thẻ tổng quan quy mô bài toán** (4 thẻ số liệu lớn ở đầu trang)
2. **Bảng mức độ hoàn chỉnh dữ liệu theo tham số** — kiểm tra từng tham số mô hình có đủ bản ghi hay không
3. **Biểu đồ chất lượng dữ liệu tổng hợp** (progress bar) so với ngưỡng mục tiêu
4. **Biểu đồ cột độ hoàn chỉnh từng tham số** (%) — trực quan hoá bảng ở mục 2
5. Nút **"Làm Mới"** — gọi lại API để refresh dữ liệu (không sửa/ghi gì)

#### Nội dung & chỉ số hiển thị

**Hàng thẻ số liệu (Summary Cards):**
| Thẻ | Ý nghĩa | Giá trị mẫu |
|---|---|---|
| Sản Phẩm | Tổng số mã sản phẩm (SKU) trong bộ dữ liệu | 943 |
| Kho Hàng | Tổng số kho/nhà máy nhận hàng (FGP) khai báo | 6 |
| Kỳ Thời Gian | Số kỳ (tuần) trong khung hoạch định | 10 |
| Tổ Hợp (SP-Kho) | Số cặp (sản phẩm, kho) thực sự có phát sinh dữ liệu | tính từ `total_combinations` |

**Bảng "Mức Độ Hoàn Chỉnh Dữ Liệu Theo Tham Số":** liệt kê **13 tham số** mô hình học thuật, khớp đầy đủ Bảng 3.3 luận văn (đã rà soát và bổ sung — xem ghi chú bên dưới), mỗi dòng gồm:
- **Nguồn dữ liệu** — tên tham số diễn giải tiếng Việt (vd. "Tồn kho đầu kỳ (BI)", "Ngưỡng tồn kho trên (U)", "Biến động tồn kho ngoại sinh (ΔI)"...)
- **Bản ghi** — số dòng dữ liệu thực có, định dạng có phân cách nghìn
- **Mức độ đầy đủ (%)** — thanh Progress, tỉ lệ `num_entries / max_entries` (mẫu số đúng theo miền chỉ số toán học của từng tham số: (i,j), (i,j,t), (i,t), (j), hoặc (j,j))
- **Trạng thái** — nhãn màu theo ngưỡng: Cập nhật (≥95%, xanh lá) / Tốt (≥85%, xanh dương) / Trung bình (≥70%, cam) / Lỗi thời hoặc Nghiêm trọng (<70%, đỏ)

13 tham số theo dõi (khớp Bảng 3.3): `BI` (tồn kho đầu kỳ), `CP` (cấu hình đóng gói), `U`/`L` (ngưỡng tồn kho trên/dưới), `DI` (biến động tồn kho ngoại sinh — xem lưu ý bên dưới), `CAP` (công suất cung ứng), `Cb`/`Co`/`Cs`/`Cp` (4 loại chi phí: nợ đơn, tồn vượt, thiếu hụt, phạt đóng gói), `LT_OA` (thời gian giao từ kho trung tâm, theo kho), `LT_PLT` (thời gian điều chuyển ngang, theo cặp kho), `d` (khoảng cách giữa nhà máy, theo cặp kho).

> **Ghi chú rà soát (đối chiếu Bảng 3.3):**
> 1. **Đã sửa nhãn sai**: mã `DI` trong code (biến `opt_input.DI`, cột nguồn `inventory_fluctuation`) thực chất là **ΔI — biến động tồn kho ngoại sinh** trong luận văn, KHÔNG phải "Nhu cầu/Demand" như nhãn cũ. Chỉ sửa nhãn hiển thị, không đổi giá trị/logic tính toán.
> 2. **Đã bổ sung 3 tham số bị thiếu**: `LT_OA`, `LT_PLT`, `d` (khoảng cách) — dữ liệu vốn có sẵn trong hệ thống (dùng thực trong MA solver) nhưng trước đó chưa được đưa vào bảng giám sát A1. Nay cả 3 đạt 100% đầy đủ (LT_OA 6/6 kho, LT_PLT 30/30 cặp kho, d 30/30 cặp kho).
> 3. **`Cp` gộp chung OA+PLT**: luận văn tách `Cp,OA` (phạt phần dư phân bổ từ kho trung tâm) và `Cp,PLT` (phạt phần dư điều chuyển ngang) thành 2 tham số lý thuyết, nhưng dữ liệu nguồn (`unit_cost.csv`, cột `penalty_cost`) chỉ có **1 giá trị nền duy nhất** dùng chung cho cả hai — đây là giới hạn của dữ liệu thực tế, không phải thiếu sót của bảng.

**Cột trái — "Chỉ Số Chất Lượng So Với Mục Tiêu":** 2 progress bar so sánh giá trị đo được với ngưỡng mục tiêu:
- **Tính Đầy Đủ Dữ Liệu** — trung bình tỉ lệ đầy đủ trên toàn bộ 13 tham số / mục tiêu 95%
- **Độ Bao Phủ Tham Số** — có đủ 13/13 tham số bắt buộc hay không / mục tiêu 85%

> Đã bỏ chỉ số "Tỉ Lệ Dữ Liệu Hợp Lệ" (Zero-free Rate — % bản ghi khác 0): với dữ liệu vận hành thực, giá trị 0 là bình thường (vd. không phát sinh chi phí phạt ở kỳ đó), nên tỉ lệ khác-0 không phản ánh đúng chất lượng dữ liệu và dễ gây hiểu nhầm.

Màu thanh progress đổi theo kết quả: đạt mục tiêu → xanh lá; ≥70% nhưng chưa đạt → cam; <70% → đỏ.

**Cột phải — Biểu đồ cột "Độ Hoàn Chỉnh Từng Tham Số (%)":** trực quan hoá lại 10 tham số ở dạng bar chart, trục X là tên tham số, trục Y là % hoàn chỉnh (0–100%), mỗi cột tô màu theo ngưỡng giống bảng, có nhãn số % trên đầu cột.

#### Giá trị mang lại cho người dùng
- Phát hiện sớm dữ liệu thiếu/lỗi **trước khi** tốn thời gian chạy MA (tránh lãng phí 2.5h giải toàn bộ 943 SP trên dữ liệu sai)
- Cho người đánh giá (giảng viên, hội đồng) thấy được **độ tin cậy của input** — một phần quan trọng của lập luận "kết quả tối ưu đáng tin vì dữ liệu đầu vào đã được kiểm định"
- Không có chức năng chỉnh sửa dữ liệu tại đây — chỉ giám sát (read-only), đúng vai trò "bảng điều khiển chất lượng"

---

### A2. Tham số mô hình

**File:** `frontend-react/src/pages/A2_ParameterManagement.jsx`
**Route:** `/a2-parameter-management`
**API:** `GET /api/v1/data-overview/parameters`, `/algorithm-parameters`, `/cost-parameters`, `/datasets`; `PUT` để lưu tham số; `POST` để tạo phiên bản dữ liệu

#### Vai trò
Trung tâm cấu hình và **truy vết phiên bản dữ liệu** của hệ thống. Gồm 2 tab: "Tham Số" (xem/sửa các nhóm tham số) và "Quản Lý Phiên Bản" (versioning cho tái lập kết quả — reproducibility). Đây là bằng chứng cho tính **khoa học và có thể kiểm chứng** của quy trình thực nghiệm trong luận văn.

#### Chức năng chính — Tab "Tham Số"
1. **Bảng tham số giải thuật Memetic (GA-ALNS)** — read-only, hiển thị cấu hình đã tinh chỉnh bằng Taguchi
2. **Bảng tham số chi phí & vận hành** — read-only, giá trị nền thực tế doanh nghiệp
3. **Bảng tham số mô hình** — có thể **chỉnh sửa** (hằng số kỹ thuật, vd. hằng số Big-M)

#### Chức năng chính — Tab "Quản Lý Phiên Bản"
1. **Bảng danh sách phiên bản dữ liệu** (dataset version) — mỗi phiên bản là một "ảnh chụp" bộ dữ liệu đầu vào tại một thời điểm
2. **Mở rộng dòng (expandable row)** — xem các lần chạy tối ưu (run) nào đã dùng phiên bản đó
3. **Dòng thời gian (Timeline)** lịch sử 5 phiên bản gần nhất
4. Nút **"Tạo Phiên Bản"** — mở modal tạo snapshot mới (tên, mô tả, người tạo)

#### Nội dung & chỉ số hiển thị

**1. Bảng "Tham Số Giải Thuật Memetic (GA-ALNS)"** — 13 tham số đọc từ `backend/ma/config.json`, gồm 5 cột: Tham Số / Ký Hiệu / Giá Trị / Nhóm / Diễn Giải. 5 tham số được gắn nhãn **"Taguchi"** (màu vàng gold) vì là kết quả hiệu chỉnh bằng quy hoạch thực nghiệm Taguchi (Chương 6 luận văn):

| Ký hiệu | Tên | Giá trị | Nhóm |
|---|---|---|---|
| n_pop | Kích thước quần thể | 38 | GA (Taguchi — ảnh hưởng lớn nhất 45.81%) |
| G_max | Số thế hệ tối đa | 500 | GA (Taguchi) |
| p_crossover | Xác suất lai chéo | 0.75 | GA (Taguchi) |
| p_mutation | Xác suất đột biến | 0.25 | GA (Taguchi) |
| n_iterations | Số vòng lặp ALNS | 45 | ALNS (Taguchi) |
| G_stag | Số thế hệ dừng sớm | 140 | GA |
| k_tournament | Kích thước tournament | 3 | GA |
| milp_seed_fraction | Tỷ lệ seed từ MILP | 0.35 | GA |
| heuristic_fraction | Tỷ lệ nghiệm heuristic | 0.45 | GA |
| q_min_ratio / q_max_ratio | Tỷ lệ phá huỷ tối thiểu/tối đa | 0.08 / 0.25 | ALNS |
| lambda_rho | Hệ số cập nhật trọng số | 0.15 | ALNS |
| time_limit_seconds | Giới hạn thời gian/SP | 3600s (mặc định config; UI runtime override 10s/SP) | Dừng |

Có banner (Alert) giải thích: "Bộ tham số vận hành tối ưu — đã tinh chỉnh bằng Taguchi nhằm cân bằng chất lượng lời giải và tốc độ hội tụ."

**2. Bảng "Tham Số Chi Phí & Vận Hành"** — 7 tham số read-only (Bảng 3.3 luận văn), giá trị nền thực tế doanh nghiệp:

| Ký hiệu | Tên | Giá trị | Đơn vị |
|---|---|---|---|
| Co | Chi phí tồn kho vượt mức | 0.1 | USD/đơn vị |
| Cs | Chi phí thiếu hụt | 0.5 | USD/đơn vị |
| Cb | Chi phí nợ đơn (thành phần chi phối) | 1500 | USD/đơn vị |
| Cp | Chi phí phạt đóng gói | 500 | USD/lần |
| TC | Chi phí vận chuyển ngang (container 40ft) | 1.2 | USD/km |
| LT_OA | Thời gian giao hàng từ nguồn | 8 | tuần |
| LT_PLT | Thời gian điều chuyển ngang | 2–3 | tuần |

Có banner cảnh báo (màu cam): đây là giá trị chỉ để tham khảo — muốn đánh giá tác động khi thay đổi phải dùng **C1 (What-If)** hoặc **D1 (Phân tích độ nhạy)**, không sửa trực tiếp ở đây. Đây là điểm thiết kế quan trọng: tách bạch "xem dữ liệu nền" và "thử nghiệm kịch bản" để tránh người dùng vô tình làm sai lệch số liệu gốc.

**3. Bảng "Tham Số Mô Hình"** — duy nhất bảng **cho phép sửa trực tiếp** (nút "Chỉnh Sửa" → nhập số mới → "Lưu Thay Đổi"/"Hủy"), có cột Trạng Thái đổi tag "Đã Sửa" (cam) khi có thay đổi chưa lưu, "Đã Lưu" (xanh) khi ổn định. Ví dụ tham số: hằng số HV (Big-M dùng trong ràng buộc tuyến tính hoá nhị phân).

**4. Bảng "Quản Lý Phiên Bản Dữ Liệu"** — cột: ID / Tên Phiên Bản / Mô Tả / Tạo Bởi (tag xanh) / Ngày Tạo / Trạng Thái (Hoạt Động / Bất Hoạt Động). Mỗi dòng mở rộng được để xem danh sách các lần chạy tối ưu (run) đã sử dụng phiên bản dữ liệu đó — gồm mã run, thời gian, trạng thái solver, chi phí tối ưu đạt được.

**5. Timeline lịch sử phiên bản** — hiển thị 5 phiên bản gần nhất dạng dòng thời gian dọc, chấm xanh + icon check cho phiên bản đang hoạt động, chấm xám + icon tag cho phiên bản cũ.

#### Giá trị mang lại cho người dùng
- **Minh bạch giải thuật**: người đọc luận văn thấy rõ bộ tham số GA-ALNS nào đang chạy thực tế, không phải chỉ mô tả suông trong văn bản
- **Tách bạch vai trò**: dữ liệu nền (cost/algo params) vs. tham số kỹ thuật có thể chỉnh — tránh sửa nhầm số liệu gốc ảnh hưởng đến toàn bộ kết quả nghiên cứu
- **Truy vết & tái lập (reproducibility)**: mỗi kết quả tối ưu (run) đều gắn với đúng một phiên bản dữ liệu cụ thể — trả lời được câu hỏi phản biện "kết quả này chạy trên bộ dữ liệu nào, có lặp lại được không?"
- Hỗ trợ kịch bản **rolling horizon**: khi dữ liệu cập nhật theo từng kỳ, tạo phiên bản mới mà không mất lịch sử các phiên bản trước

---

## Nhóm B — Tối ưu hoá & Kết quả (chương chính)

> Đây là nhóm trang lõi của hệ thống — nơi chạy giải thuật Memetic và trình bày kết quả tối ưu. Nên đầu tư mô tả kỹ nhất trong luận văn vì đây là bằng chứng trực tiếp cho đóng góp của đề tài.
>
> Tên file, route URL và tiêu đề trên trang đã được đồng bộ khớp menu sidebar (B1 = chạy tối ưu, B2 = kết quả tổng hợp, B3 = chi tiết phân bổ).

### B1. Thực thi tối ưu hoá

**File:** `frontend-react/src/pages/B1_RunOptimization.jsx`
**Route:** `/b1-run-optimization`
**API:** `POST /api/v1/optimize/run`, `GET /api/v1/optimize/runs/{id}/status`, `GET /api/v1/optimize/runs`

#### Vai trò
Trang **khởi chạy giải thuật Memetic** — nơi người dùng thiết lập phạm vi chạy (toàn bộ hay giới hạn số sản phẩm để test nhanh), theo dõi tiến độ giải theo thời gian thực, và xem lại lịch sử các lần chạy trước. Là điểm chuyển giao giữa "chuẩn bị dữ liệu" (nhóm A) và "xem kết quả" (B2/B3).

#### Chức năng chính
1. **Form cấu hình lần chạy**: chọn giới hạn số sản phẩm (để trống = chạy toàn bộ 943 SP), giới hạn thời gian tối đa mỗi sản phẩm
2. **Ước tính thời gian chạy trực tiếp** (~10 giây/sản phẩm, cập nhật ngay khi đổi số lượng)
3. **Thanh tiến trình thời gian thực**: polling trạng thái mỗi 4 giây, hiển thị số sản phẩm đã giải / tổng số, thời gian đã trôi qua
4. **Giữ trạng thái "đang chạy" qua localStorage**: rời trang rồi quay lại vẫn thấy tiến độ, không bị mất theo dõi
5. **Tab "Lịch sử lần chạy"**: liệt kê toàn bộ các lần chạy trước, xem lại tóm tắt kết quả, xoá lần chạy không cần

#### Nội dung & chỉ số hiển thị
- **Bước 1 — Cấu hình**: Steps (Ant Design) 3 bước Cấu hình → Đang chạy → Hoàn tất
  - Trường "Giới hạn số sản phẩm": để trống chạy full 943 SP; nhập số để test nhanh (vd. 5, 50 SP)
  - Trường "Giới hạn thời gian mỗi sản phẩm": mặc định phù hợp với chế độ demo, kiểm soát trần thời gian giải mỗi bài toán con
  - Dòng ước tính: "~X phút/giờ" tính theo công thức số SP × 10 giây
- **Bước 2 — Đang chạy**: 
  - Progress bar phần trăm hoàn thành
  - Đồng hồ đếm thời gian đã trôi qua
  - Trạng thái solver theo thời gian thực (đang giải, đã xong)
- **Bước 3 — Hoàn tất**: tóm tắt kết quả lần chạy vừa xong (giá trị mục tiêu, thời gian giải, trạng thái optimal/feasible), nút chuyển sang B2 xem chi tiết
- **Tab Lịch sử**: bảng các lần chạy — mã lần chạy, thời gian, trạng thái, giá trị mục tiêu; chọn 1 dòng để xem lại tóm tắt nhanh mà không cần sang B2

#### Giá trị mang lại cho người dùng
- Cho phép **thử nghiệm nhanh** trên tập con sản phẩm trước khi cam kết chạy toàn bộ (tránh chờ ~2.5 giờ nếu chỉ muốn kiểm tra cấu hình)
- **Minh bạch tiến độ**: người dùng doanh nghiệp không phải đoán hệ thống có đang treo hay không — luôn thấy % hoàn thành
- **Truy vết lịch sử**: so sánh nhanh nhiều lần chạy (vd. thử các tham số khác nhau) mà không mất dữ liệu lần trước

#### Câu hỏi phản biện có thể gặp
- *"Vì sao chạy 943 sản phẩm cần ~2.5 giờ? Có tối ưu được thời gian không?"* → Trả lời: mỗi sản phẩm là một bài toán con độc lập (do ràng buộc tách rời theo sản phẩm), thời gian giải mỗi SP giới hạn ~10s theo Taguchi; tổng thời gian tuyến tính theo số SP. Có thể tăng tốc bằng chạy song song (không nằm trong phạm vi hiện tại).
- *"Nếu dừng giữa chừng thì kết quả có bị mất không?"* → Cần làm rõ: hệ thống lưu kết quả sau khi giải xong toàn bộ, không có cơ chế lưu tạm giữa chừng — đây là điểm có thể cải tiến.
- *"Giới hạn thời gian mỗi sản phẩm có ảnh hưởng đến chất lượng lời giải không?"* → Có: nếu giới hạn quá thấp, giải thuật có thể dừng trước khi hội tụ, cho lời giải chưa tối ưu (feasible nhưng không optimal).

---

### B2. Kết quả & Chi phí

**File:** `frontend-react/src/pages/B2_ExecutiveSummary.jsx`
**Route:** `/b2-executive-summary`
**API:** `GET /api/v1/results/{run_id}/executive-summary`, `GET /api/v1/optimize/kpis/{run_id}`, `GET /api/v1/results/{run_id}/summary-extended`, `GET /api/v1/results/{run_id}/cost-by-warehouse`, `GET /api/v1/results/{run_id}/variables`, `GET /api/v1/results/{run_id}/si-ss`, `GET /api/v1/results/{run_id}/changes-detail`

#### Vai trò
**Trang kết quả trung tâm** của toàn hệ thống — nơi trả lời câu hỏi cốt lõi của luận văn: "Tối ưu hoá tiết kiệm được bao nhiêu so với hiện trạng, và chi phí đó đến từ đâu?" Đây là trang có khả năng cao nhất được dùng để trình bày trước hội đồng, vì gói gọn toàn bộ câu chuyện savings 52.91% (baseline 242.9M → MA 114.4M) trong một màn hình.

#### Chức năng chính
1. **Bộ chọn lần chạy** (dropdown) — xem lại bất kỳ lần chạy nào trong lịch sử
2. **5 thẻ KPI đầu trang** — con số quan trọng nhất, nhìn thấy ngay khi vào trang
3. **Tab "Phân tích chi phí"** — bảng + biểu đồ 5 thành phần chi phí, so sánh baseline vs tối ưu
4. **Tab "Biến quyết định & SI/SS"** — đi sâu vào biến số kỹ thuật (lượng phân bổ, tồn kho, chỉ số an toàn) theo từng sản phẩm/kho/kỳ
5. **Tab "Chi phí theo kho"** — phân rã chi phí theo từng nhà máy nhận hàng (FGP)

#### Nội dung & chỉ số hiển thị

**5 thẻ KPI (đầu trang):**
| Thẻ | Ý nghĩa | Công thức / nguồn |
|---|---|---|
| Chi phí cơ sở (hiện trạng) | Chi phí nếu vận hành theo cách doanh nghiệp đang làm — không áp dụng tối ưu | `baseline_cost` — mô phỏng phân bổ theo heuristic vận hành thực tế (OA + PLT thông minh theo mức thiếu hụt), KHÔNG phải kịch bản "không làm gì" |
| Tổng chi phí tối ưu | Giá trị hàm mục tiêu sau khi giải bằng Memetic | Tổng của 5 thành phần chi phí bên dưới |
| Mức độ phục vụ | % số dòng (sản phẩm, kho, kỳ) đáp ứng đủ nhu cầu, không phát sinh nợ đơn | `service_level = (số dòng có backorder=0) / tổng số dòng × 100%` |
| Tiết kiệm vs hiện trạng | % chi phí giảm được so với chi phí cơ sở | `(baseline − tối ưu) / baseline × 100%` |
| Thời gian giải | Thời gian thực tế giải thuật chạy | Đo trực tiếp khi solver chạy, đơn vị giây |

**Tab 1 — "Phân tích chi phí":**
- **Bảng 5 thành phần chi phí** (có dòng TỔNG ở cuối), mỗi dòng gồm tên, giá trị (VNĐ/USD), % trên tổng:
  1. Chi phí nợ đơn (backorder) — thường chiếm tỉ trọng lớn nhất (theo luận văn ~94%)
  2. Chi phí tồn kho vượt mức (overstock)
  3. Chi phí thiếu hụt (shortage)
  4. Chi phí phạt đóng gói (penalty)
  5. Chi phí điều chuyển ngang (transport/PLT)
- **Biểu đồ cột** trực quan hoá 5 thành phần trên
- **Khối "So sánh với chi phí cơ sở"**: 3 dòng số (chi phí cơ sở, chi phí tối ưu, tiết kiệm) + biểu đồ cột ngang so sánh 2 cột Baseline vs MA Tối ưu
- **Card "Chi tiết lần chạy"**: giá trị mục tiêu chính xác, tên giải thuật, số sản phẩm/kho/chu kỳ đã xử lý, tổng bản ghi kết quả, nhắc lại breakdown 5 thành phần chi phí kèm chấm màu

**Tab 2 — "Biến quyết định & SI/SS":**
- **Thẻ "SI trung bình"**: chỉ số an toàn tồn kho trung bình toàn hệ thống (SI = tồn kho thực tế / ngưỡng tồn kho tối thiểu). SI ≥ 1 = an toàn, SI < 1 = dưới ngưỡng. Kèm số ô dưới ngưỡng an toàn và số thay đổi lẻ (đơn vị không tròn kiện)
- **Sub-tab "Biến quyết định"**: chọn 1 sản phẩm + kho (tuỳ chọn) → 2 biểu đồ:
  - Phân bổ theo kiện hàng (q) và đơn vị lẻ (r) qua từng kỳ
  - Tồn kho ròng (đường), tồn thiếu/tồn thừa/thiếu hụt (cột) qua từng kỳ
- **Sub-tab "Chỉ số SI/SS"**: 
  - Biểu đồ phân phối SI (histogram) — có đường tham chiếu tại SI=1
  - Biểu đồ tròn tỉ lệ 3 mức an toàn: An toàn (SI≥1) / Cảnh báo (0.8≤SI<1) / Rủi ro (SI<0.8)
- **Sub-tab "Thay đổi lẻ"**: bảng chi tiết các dòng có phần dư sau khi chia theo quy cách đóng gói (không tròn kiện) — sản phẩm, kho, kỳ, số kiện, số lẻ, tồn kho, thiếu hụt

**Tab 3 — "Chi phí theo kho":**
- Bộ lọc chọn kho cụ thể (đa lựa chọn)
- **Bảng theo từng kho**: 4 thành phần chi phí (nợ đơn, tồn thừa, thiếu hụt, phạt đóng gói) + tổng + % trên tổng toàn hệ thống, có dòng TỔNG
- **Biểu đồ cột chồng** theo kho — trực quan hoá cơ cấu chi phí mỗi kho

#### Giá trị mang lại cho người dùng
- **Trả lời trực tiếp câu hỏi ROI**: "đầu tư hệ thống DSS này tiết kiệm được bao nhiêu tiền" — con số cụ thể, có breakdown minh bạch
- **Truy vết nguyên nhân chi phí**: biết chi phí đến từ đâu (nợ đơn hay tồn kho dư hay vận chuyển) để ra quyết định vận hành đúng chỗ
- **Phân tích SI/SS hỗ trợ ra quyết định rủi ro**: cảnh báo sớm những sản phẩm/kho có nguy cơ thiếu hàng dù tổng thể đã tối ưu
- **So sánh đa lần chạy**: đổi kịch bản tham số rồi so kết quả ngay trên cùng giao diện

#### Câu hỏi phản biện có thể gặp
- *"Chi phí cơ sở (baseline) được tính như thế nào, có công bằng khi so sánh không?"* → Cần trả lời rõ: baseline là mô phỏng cách vận hành THỰC TẾ của doanh nghiệp (có OA + điều chuyển ngang theo kinh nghiệm), KHÔNG phải kịch bản "không làm gì" — nên savings 52.91% phản ánh đúng giá trị gia tăng của việc áp dụng tối ưu hoá so với cách làm hiện tại, không phải so với kịch bản cực đoan.
- *"Vì sao chi phí nợ đơn chiếm tỉ trọng áp đảo trong cả baseline và tối ưu?"* → Vì chi phí nợ đơn (Cb=1500 USD/đơn vị) cao hơn nhiều lần so với các chi phí khác (Co=0.1, Cs=0.5, Cp=500) — đây là do đặc thù ngành ô tô, thiếu hàng gây gián đoạn dây chuyền sản xuất của khách hàng nên bị phạt rất nặng.
- *"SI < 1 có nghĩa là giải pháp sai không?"* → Không nhất thiết — SI<1 nghĩa là tồn kho dưới ngưỡng khuyến nghị ở một số ô cụ thể, nhưng hàm mục tiêu đã cân bằng giữa chi phí giữ tồn kho cao và rủi ro thiếu hàng; một số điểm SI thấp có thể là lựa chọn tối ưu toàn cục dù cục bộ có rủi ro.
- *"Vì sao chọn thước đo Mức độ phục vụ = tỉ lệ dòng không backorder, thay vì đo theo % nhu cầu được đáp ứng?"* → Đây là điểm có thể bị hỏi sâu — cách đo hiện tại đơn giản (nhị phân: có/không nợ đơn) chứ chưa đo tỉ lệ % số lượng được đáp ứng trên tổng nhu cầu; có thể là hướng cải tiến.

---

### B3. Phân bổ & Động thái tồn kho

**File:** `frontend-react/src/pages/B3_AllocationInventoryDashboard.jsx`
**Route:** `/b3-allocation-inventory-dashboard`
**API:** `GET /api/v1/results/{run_id}/plt-transfers`, `GET /api/v1/results/{run_id}/inventory-by-warehouse`, `GET /api/v1/results/{run_id}/allocation`, `GET /api/v1/results/{run_id}/inventory-dynamics`

#### Vai trò
Trang **đào sâu vận hành** — nếu B2 trả lời "tiết kiệm bao nhiêu", thì B3 trả lời "cụ thể hàng hoá di chuyển thế nào, tồn kho biến động ra sao". Phục vụ người dùng cần vận hành thực tế (nhân viên logistics/kế hoạch) muốn biết chi tiết đến từng lô hàng, từng kho, từng kỳ — không chỉ số tổng hợp.

#### Chức năng chính — 3 tab độc lập
1. **Tab "Điều chuyển ngang (PLT)"** — toàn bộ giao dịch chuyển hàng giữa các kho
2. **Tab "Quỹ đạo tồn kho theo kho"** — theo dõi diễn biến tồn kho của từng kho qua thời gian
3. **Tab "Phân bổ theo sản phẩm"** — tra cứu chi tiết một sản phẩm cụ thể

#### Nội dung & chỉ số hiển thị

**Tab 1 — "Điều chuyển ngang (PLT)":**
- Bộ lọc: sản phẩm, kho nguồn, kho đích
- **4 thẻ tổng quan**: Tổng lượng chuyển (đơn vị), Số cặp kho có giao dịch, Số giao dịch, Số kỳ có PLT
- **Ma trận PLT**: bảng vuông kho×kho, mỗi ô là tổng lượng đã chuyển từ kho hàng-dọc sang kho hàng-ngang — trực quan hoá "dòng chảy hàng hoá" giữa các nhà máy
- **Biểu đồ cột chồng theo kỳ**: lượng PLT mỗi kỳ, chia theo kho nguồn (màu khác nhau) — thấy được kho nào đang "cho mượn" hàng nhiều nhất theo thời gian
- **Bảng chi tiết giao dịch**: từng dòng PLT — sản phẩm, kho đi, kho đến, kỳ, số lượng

**Tab 2 — "Quỹ đạo tồn kho theo kho":**
- **Thẻ tổng quan mỗi kho**: tổng backorder của kho đó (màu đỏ nếu >0, xanh nếu =0) — nhận diện nhanh kho nào đang có vấn đề
- **Bộ chọn chỉ tiêu**: Tồn kho (net) / Backorder / Overstock / Shortage — đổi được biểu đồ đường bên dưới xem theo chỉ tiêu nào
- **Biểu đồ đường đa kho**: mỗi kho một đường màu riêng, trục X là kỳ thời gian, trục Y là giá trị chỉ tiêu đã chọn — thấy được xu hướng tăng/giảm và biến động theo thời gian, có đường tham chiếu y=0
- **Bảng tổng hợp theo kho**: tổng backorder / overstock / shortage của từng kho suốt kỳ hoạch định

**Tab 3 — "Phân bổ theo sản phẩm":**
- Bộ lọc bắt buộc chọn 1 sản phẩm (tuỳ chọn thêm kho)
- **4 thẻ tổng quan** (theo sản phẩm đã chọn): Tổng kiện hàng, Tổng đơn vị lẻ, Tổng backorder, Vi phạm quy cách đóng gói (số dòng)
- **Biểu đồ đường quỹ đạo tồn kho**: tồn kho ròng của sản phẩm đó tại từng kho qua các kỳ
- **Bảng chi tiết phân bổ**: từng dòng (kho, kỳ) — kiện hàng (Q), đơn vị lẻ (r), tồn kho (I), backorder, overstock, shortage, có vi phạm quy cách đóng gói hay không

#### Giá trị mang lại cho người dùng
- **Vận hành thực tế**: nhân viên kho có thể tra đúng "kỳ tới cần chuyển bao nhiêu hàng từ kho A sang kho B" — biến kết quả tối ưu trừu tượng thành hành động cụ thể
- **Giám sát sức khoẻ từng kho**: phát hiện kho nào liên tục thiếu hụt/dư thừa để điều chỉnh chính sách tồn kho riêng cho kho đó
- **Truy vết một sản phẩm xuyên suốt chuỗi cung ứng**: hữu ích khi có sự cố với 1 SKU cụ thể (vd. sản phẩm bị recall, nhu cầu đột biến)
- **Ma trận PLT** là bằng chứng trực quan cho luận điểm "điều chuyển ngang chủ động" — một trong những đóng góp cốt lõi của mô hình SS-MB-SMI so với vận hành truyền thống (chỉ phân bổ 1 chiều từ kho trung tâm)

#### Câu hỏi phản biện có thể gặp
- *"Vì sao cần điều chuyển ngang (PLT) giữa các kho thay vì chỉ phân bổ từ kho trung tâm?"* → Vì thời gian giao hàng từ kho trung tâm (LT_OA ≈ 8 tuần) dài hơn nhiều so với điều chuyển ngang giữa các nhà máy Mỹ (LT_PLT ≈ 2–3 tuần) — khi một kho thiếu hụt đột xuất, điều chuyển ngang phản ứng nhanh hơn chờ chuyến hàng mới từ Việt Nam.
- *"Ma trận PLT có đối xứng không, tức là các kho có 'trao đổi qua lại' hay chỉ chảy một chiều?"* → Cần xem dữ liệu thực tế; về lý thuyết mô hình cho phép cả 2 chiều (i→j và j→i) miễn thoả ràng buộc thời gian `T^PLT_i,j`, nhưng thực tế có thể lệch nếu một số kho luôn dư thừa còn số khác luôn thiếu hụt theo đặc điểm nhu cầu vùng miền.
- *"'Vi phạm quy cách đóng gói' có phải là lỗi hệ thống không?"* → Không — đây là chỉ báo khi lượng phân bổ/điều chuyển không chia hết cho quy cách đóng gói (CP), phát sinh phần dư lẻ bị phạt chi phí Cp. Là đánh đổi có chủ đích của mô hình (chấp nhận phạt nhỏ để tối ưu tổng thể) chứ không phải lỗi tính toán.
- *"Dữ liệu ở B3 có nhất quán với tổng chi phí ở B2 không?"* → Có — cả hai cùng đọc từ bảng kết quả (`OptimizationResult`) của cùng một lần chạy (`run_id`); B2 là tổng hợp, B3 là chi tiết của đúng dữ liệu đó, không tính lại bằng logic khác.

---

## Nhóm C — Phân tích kịch bản

> Trả lời câu hỏi "nếu điều kiện thay đổi thì sao?" — công cụ thử nghiệm giả định (what-if) mà không cần đụng vào dữ liệu gốc. Đây là minh chứng cho tính "hỗ trợ ra quyết định" (decision support) của hệ thống, không chỉ dừng ở tối ưu 1 lần.

### C1. Phân tích What-If

**File:** `frontend-react/src/pages/C1_ScenarioManagement.jsx`
**Route:** `/c1-scenario-management`
**API:** `POST /api/v1/whatif/`, `GET /api/v1/whatif/history`, `GET /api/v1/optimize/runs`

#### Vai trò
Cho phép người dùng **thử nghiệm giả định** ("điều gì xảy ra nếu nhu cầu tăng 20%?", "nếu đóng cửa kho X thì sao?") bằng cách chạy lại MA với tham số bị điều chỉnh (override) trên một lần chạy cơ sở có sẵn, **không sửa dữ liệu gốc**. Là công cụ mô phỏng rủi ro/kịch bản kinh doanh trước khi ra quyết định thật.

#### Chức năng chính
1. **6 nhóm kịch bản dạng thẻ bấm chọn** — gộp lại từ 11 loại kịch bản chi tiết ở backend
2. **Modal cấu hình kịch bản**: chọn lần chạy cơ sở, slider mức điều chỉnh %, giới hạn thời gian giải
3. **Chạy nền (background job)**: kịch bản chạy MA thực sự, không chặn giao diện, tự động polling cập nhật trạng thái mỗi 5 giây
4. **Bảng lịch sử kịch bản**: toàn bộ kịch bản đã chạy, trạng thái, kết quả, link nhanh sang B2 xem chi tiết

#### Nội dung & chỉ số hiển thị

**6 nhóm kịch bản** (mỗi thẻ gồm icon, mô tả, tham số ảnh hưởng):
| Nhóm | Tham số | Ý nghĩa |
|---|---|---|
| Điều chỉnh nhu cầu | DI | Mô phỏng nhu cầu thị trường tăng/giảm đột biến |
| Điều chỉnh công suất | CAP | Mô phỏng nhà cung cấp mở rộng hoặc gián đoạn sản xuất |
| Điều chỉnh chi phí | Cb, Co, Cs, Cp | Mô phỏng biến động giá vận hành (nhiên liệu, nhân công...) |
| Điều chỉnh chính sách tồn kho | U, L | Nới/thu hẹp khoảng an toàn tồn kho theo chính sách mới |
| Thay đổi cấu trúc | I/J | Đóng cửa kho hoặc thêm sản phẩm mới — thay đổi quy mô bài toán |
| Tùy chỉnh nâng cao | * | Ghi đè tham số bất kỳ qua JSON, cho trường hợp đặc biệt |

4 nhóm đầu có **thanh trượt (slider)** từ -60% đến +100%, mỗi 6 nhóm ánh xạ ra 1 trong **11 loại kịch bản kỹ thuật** ở backend theo dấu của mức điều chỉnh (vd. slider dương ở nhóm "Điều chỉnh nhu cầu" → `demand_surge`; slider âm → `demand_drop`).

**Modal cấu hình kịch bản:**
- **Lần chạy cơ sở**: bắt buộc chọn 1 run có sẵn để làm nền so sánh
- **Thanh trượt mức điều chỉnh**: kéo để chọn %, có nhãn trực quan "Tăng +20%"/"Giảm -30%", hiển thị ngay tên loại kịch bản kỹ thuật tương ứng
- Với nhóm "Thay đổi cấu trúc": chọn đóng kho (nhập mã kho) hoặc thêm sản phẩm mới (hiện chưa hỗ trợ qua giao diện, chỉ qua API)
- Với nhóm "Tùy chỉnh nâng cao": ô nhập JSON tự do cho override tham số
- **Giới hạn thời gian mỗi sản phẩm**: mặc định 10 giây, kiểm soát tốc độ chạy MA cho kịch bản

**Bảng "Lịch sử kịch bản":** mã kịch bản, tên/nhãn, loại (tag màu), trạng thái (đang chạy/hoàn tất/lỗi), chi phí tối ưu đạt được, trạng thái solver, ngày tạo, nút "Xem kết quả" dẫn thẳng sang B2 với đúng run đó được chọn sẵn.

#### Giá trị mang lại cho người dùng
- **Đánh giá rủi ro trước khi xảy ra thật**: doanh nghiệp có thể trả lời "nếu nhu cầu quý tới tăng 20% thì chi phí tăng bao nhiêu, có cần tăng công suất không" mà không cần đợi tình huống thực tế
- **Không phá vỡ dữ liệu gốc**: mọi kịch bản là bản sao có override, chạy độc lập, dữ liệu CSV gốc và các run trước không bị ảnh hưởng
- **Đơn giản hoá 11 loại kỹ thuật thành 6 nhóm dễ hiểu**: người dùng không cần biết tên kỹ thuật `demand_surge`/`demand_drop`, chỉ cần kéo thanh trượt

#### Câu hỏi phản biện có thể gặp
- *"Kịch bản what-if có chạy lại toàn bộ 943 sản phẩm không, mất bao lâu?"* → Có, chạy lại MA thật trên tập sản phẩm của lần chạy cơ sở (thường giới hạn thời gian ngắn hơn, mặc định 10s/SP thay vì đầy đủ) để có kết quả nhanh hơn, đánh đổi độ chính xác lấy tốc độ phản hồi.
- *"Vì sao chỉ có 4/6 nhóm dùng thanh trượt %, còn 'Thay đổi cấu trúc' và 'Tùy chỉnh' thì không?"* → Vì đóng kho/thêm sản phẩm là thay đổi **rời rạc** (có hoặc không, không có "50% đóng cửa"), không thể biểu diễn bằng % liên tục như nhu cầu/chi phí — nên dùng hình thức nhập khác (chọn kho, JSON).
- *"Kết quả what-if có đáng tin bằng kết quả chạy chính thức không?"* → Về thuật toán là cùng 1 MA solver, chỉ khác input (tham số bị override) và thường giới hạn thời gian ngắn hơn để phản hồi nhanh — nên chất lượng lời giải có thể thấp hơn 1 chút so với chạy đầy đủ, nhưng đủ tin cậy để so sánh xu hướng.

---

### C2. So sánh kịch bản

**File:** `frontend-react/src/pages/C2_ScenarioComparison.jsx`
**Route:** `/c2-scenario-comparison`
**API:** `GET /api/v1/whatif/compare?base_run_id=...&compare_run_id=...`

#### Vai trò
Công cụ **đối chiếu song song 2 lần chạy bất kỳ** (không nhất thiết phải là run gốc vs. what-if — có thể so sánh 2 run tối ưu thường, hoặc 2 kịch bản what-if với nhau) trên cùng bộ 7 chỉ số KPI, giúp trả lời nhanh "kịch bản này tốt hơn hay xấu hơn kịch bản kia, và ở khía cạnh nào".

#### Chức năng chính
1. **2 bộ chọn lần chạy** (cơ sở và so sánh) — chọn tự do từ toàn bộ lịch sử run
2. **Nút "So sánh KPI"** — gọi API tính chênh lệch (delta) từng chỉ số
3. **Tóm tắt thay đổi bằng ngôn ngữ tự nhiên** — liệt kê nhanh các KPI thay đổi đáng kể
4. **Biểu đồ cột song song** — trực quan hoá 2 giá trị cạnh nhau cho từng KPI
5. **Bảng chi tiết đầy đủ 7 KPI** — số tuyệt đối, chênh lệch, % thay đổi

#### Nội dung & chỉ số hiển thị

**7 KPI được so sánh** (đọc từ bảng `DssKPI` đã lưu sẵn của mỗi run — không tính lại):
1. Tổng chi phí
2. Tổng nợ đơn
3. Tổng tồn kho vượt mức
4. Tổng thiếu hụt
5. Tổng vi phạm đóng gói
6. Mức độ phục vụ
7. Mức sử dụng công suất

**3 thẻ tổng quan**: loại kịch bản, nhãn, số KPI có trong bảng so sánh.

**Khối "Tóm tắt thay đổi so với lần chạy cơ sở"**: chỉ liệt kê các KPI có thay đổi đáng kể (≥0.1%), viết dạng câu tự nhiên "Tổng chi phí giảm 12.3%" kèm icon mũi tên lên/xuống và màu (đỏ = tăng, xanh = giảm) — do phần lớn KPI càng thấp càng tốt (chi phí, nợ đơn...) nên quy ước màu theo hướng "tăng = xấu, giảm = tốt" (riêng Mức độ phục vụ thì ngược lại về mặt ý nghĩa, cần lưu ý khi đọc).

**Biểu đồ cột song song**: mỗi KPI có thay đổi ≥0.1% được vẽ 2 cột cạnh nhau (Cơ sở vs Kịch bản) để so trực quan độ lớn.

**Bảng chi tiết**: đầy đủ 7 KPI, mỗi dòng có giá trị cơ sở, giá trị kịch bản, thay đổi tuyệt đối (màu đỏ nếu tăng, xanh nếu giảm), % thay đổi (tag màu theo ngưỡng ±5%).

#### Giá trị mang lại cho người dùng
- **Ra quyết định nhanh giữa nhiều phương án**: so hết các kịch bản đã chạy để chọn ra phương án tốt nhất trước khi áp dụng thực tế
- **Không giới hạn chỉ so run gốc vs what-if**: có thể so 2 kịch bản what-if với nhau (vd. "tăng nhu cầu 20%" vs "tăng nhu cầu 30%") để thấy độ nhạy
- **Tóm tắt ngôn ngữ tự nhiên** giảm gánh nặng đọc số cho người dùng không chuyên kỹ thuật — quan trọng với đối tượng doanh nghiệp

#### Câu hỏi phản biện có thể gặp
- *"'Nhãn' và 'Loại kịch bản' hiển thị giống hệt nhau, có dư thừa không?"* → Đã xử lý: bảng dữ liệu (`WhatIfScenario`) không lưu nhãn tuỳ chỉnh riêng của người dùng khi tạo kịch bản ở C1 — chỉ lưu `whatif_type` (mã kỹ thuật). Ô "Nhãn" trước đây chỉ lặp lại đúng nội dung "Loại kịch bản" (cả hai đều là bản dịch của cùng 1 giá trị) nên đã thay bằng "Lần chạy so sánh" (hiển thị mã 2 run đang đối chiếu) để không trùng lặp thông tin vô nghĩa.
- *"So sánh 2 run có cùng bộ dữ liệu/tham số cố định không, có công bằng không?"* → Cần lưu ý: nếu 2 run dùng phiên bản dữ liệu khác nhau (xem A2 — quản lý phiên bản), kết quả so sánh phản ánh cả tác động của thay đổi dữ liệu lẫn thay đổi kịch bản, không tách bạch được — nên ưu tiên so sánh các run cùng version_id để kết luận chính xác về tác động của riêng kịch bản.
- *"'Mức độ phục vụ' tăng có phải luôn là tin tốt không, sao lại tô cùng quy tắc màu với chi phí?"* → Đây là điểm UI chưa tinh chỉnh: quy ước "tăng=đỏ, giảm=xanh" áp dụng đồng loạt cho cả 7 KPI, nhưng Mức độ phục vụ tăng thực ra là điều TỐT (nên đáng ra phải tô xanh khi tăng) — hướng cải tiến hợp lý nếu bị hỏi sâu.

---

## Nhóm D — Phân tích độ nhạy & Rủi ro

> Trả lời câu hỏi "tham số nào quan trọng nhất, và lời giải có đáng tin cậy khi dữ liệu đầu vào không hoàn toàn chính xác?" — đây là lớp phân tích học thuật sâu nhất trong hệ thống, thể hiện tính nghiêm túc khoa học của luận văn (không chỉ đưa ra 1 con số tối ưu mà còn đánh giá độ tin cậy của nó).
>
> Tên file, route URL và tiêu đề trên trang đã được đồng bộ khớp menu sidebar (D1 = độ nhạy, D2 = độ bền vững).

### D1. Phân tích độ nhạy tham số

**File:** `frontend-react/src/pages/D1_SensitivityAnalysis.jsx`
**Route:** `/d1-sensitivity-analysis`
**API:** `POST /api/v1/sensitivity/run` (OAT), `POST /api/v1/sensitivity/tornado`, `GET /api/v1/sensitivity/jobs/{id}`, `GET /api/v1/sensitivity/history`

#### Vai trò
Trả lời câu hỏi **"tham số nào ảnh hưởng nhiều nhất đến chi phí tối ưu?"** — phân tích độ nhạy (sensitivity analysis) kinh điển trong nghiên cứu vận trù học. Giúp người ra quyết định biết nên **kiểm soát chặt tham số nào** (ảnh hưởng lớn, cần dữ liệu chính xác) và tham số nào có thể ước lượng lỏng hơn (ảnh hưởng nhỏ).

#### Chức năng chính
1. **2 chế độ phân tích**: OAT (từng tham số riêng lẻ, chi tiết) và Tornado (nhiều tham số cùng lúc, so sánh xếp hạng)
2. **Chọn mẫu 50 SP (nhanh) hoặc toàn bộ 943 SP (đầy đủ, rất lâu)** — đánh đổi tốc độ vs độ chính xác
3. **Chạy nền + polling**, có thể huỷ giữa chừng, lưu lịch sử để xem lại
4. **Biểu đồ đường (OAT)** hoặc **biểu đồ tornado + bảng xếp hạng (Tornado)**

#### Nội dung & chỉ số hiển thị

**9 tham số có thể phân tích:** DI (biến động cầu), CAP (năng lực cung ứng), Cb/Co/Cs/Cp (4 loại chi phí), U/L (ngưỡng tồn kho trên/dưới), BI (tồn kho ban đầu). Riêng CP (quy cách đóng gói) bị loại vì là số nguyên rời rạc, không co giãn được theo %.

**Chế độ "Từng tham số" (OAT — One-At-a-Time):**
- Chọn **1 tham số**, hệ thống tự chạy lại MA ở **4 mức biến thiên cố định: -20%, -10%, +10%, +20%**
- **3 thẻ tổng quan**: tham số đang phân tích, giá trị mục tiêu cơ sở (0% biến thiên), **độ co giãn (elasticity)** — tỉ lệ %thay đổi chi phí / %thay đổi tham số, đo bằng mức biến thiên nhỏ nhất hợp lệ
- **Biểu đồ đường**: trục X là % biến thiên, trục Y là giá trị mục tiêu, có đường tham chiếu ngang tại mức cơ sở (0%) — độ dốc của đường càng lớn thì tham số càng "nhạy"

**Chế độ "Tornado":**
- Chạy đồng thời **6 tham số cố định** (DI, CAP, Cb, Co, Cs, Cp) ở cùng 1 mức biến thiên % (người dùng chọn qua thanh trượt 1-50%), mỗi tham số có 2 lần chạy (thấp/cao)
- **Biểu đồ tornado** (thanh ngang): mỗi tham số 1 dòng, thanh trải dài từ giá trị chi phí khi giảm tới khi tăng — tham số nào thanh dài nhất thì ảnh hưởng lớn nhất, xếp từ trên xuống theo độ lớn giảm dần (tạo hình phễu — nguồn gốc tên "tornado chart")
- **Bảng xếp hạng độ nhạy tham số**: giá trị thấp/cao, khoảng biến thiên (spread — thước đo chính để so sánh)

**Cảnh báo thời gian chạy:** vì mỗi mức biến thiên = 1 lần chạy MA đầy đủ, hệ thống hiển thị rõ ước tính thời gian: chế độ mẫu 50 SP mất ~22 phút (OAT) hoặc ~57 phút (Tornado, 12 lần chạy); chế độ đầy đủ 943 SP có thể mất **nhiều giờ** — có banner cảnh báo rõ trước khi chạy.

#### Giá trị mang lại cho người dùng
- **Ưu tiên hoá nỗ lực thu thập dữ liệu**: nếu Cb có elasticity cao nhất, doanh nghiệp nên đầu tư đo đạc chính xác chi phí nợ đơn hơn là các tham số ít ảnh hưởng
- **Cơ sở khoa học cho khuyến nghị chính sách**: biết chính xác đòn bẩy nào (tăng CAP? giảm Cb?) tác động mạnh nhất đến chi phí tổng, hỗ trợ đàm phán với nhà cung cấp/khách hàng
- **Minh bạch hoá "hộp đen" tối ưu hoá**: thay vì chỉ đưa 1 con số kết quả, cho thấy kết quả đó nhạy cảm ra sao với sai số đầu vào — tăng độ tin cậy khoa học

#### Câu hỏi phản biện có thể gặp
- *"Độ co giãn (elasticity) tính như thế nào, ý nghĩa con số đó là gì?"* → Công thức: `elasticity = %thay_đổi_chi_phí / %thay_đổi_tham_số`, tính tại mức biến thiên nhỏ nhất hợp lệ (thường ±10%). Elasticity = 2 nghĩa là tham số tăng 1% thì chi phí tăng ~2% — tham số có elasticity càng lớn (trị tuyệt đối) thì càng "nhạy".
- *"Vì sao OAT chỉ đổi 1 tham số một lần mà không đổi nhiều tham số cùng lúc để xem tương tác giữa chúng?"* → Đây là giới hạn phương pháp luận cố hữu của OAT — được thiết kế để cô lập ảnh hưởng riêng của từng biến, dễ diễn giải nhưng **bỏ sót hiệu ứng tương tác** (interaction effect) giữa các tham số. Đây là điểm luận văn có thể tự nhận là hạn chế, hướng phát triển là thiết kế thực nghiệm đa yếu tố (factorial design) như đã áp dụng cho hiệu chỉnh giải thuật ở Chương 6 (Taguchi).
- *"Chạy trên mẫu 50 SP có đại diện được cho toàn bộ 943 SP không?"* → Đây là đánh đổi tốc độ thực nghiệm — 50 SP là mẫu ngẫu nhiên, đủ lớn để ước lượng xu hướng nhưng không đảm bảo chính xác tuyệt đối bằng chạy đầy đủ; nên xem chế độ 50 mẫu là công cụ khảo sát nhanh, chế độ 943 SP đầy đủ dùng khi cần kết luận chính thức.

---

### D2. Độ bền vững nghiệm tối ưu

**File:** `frontend-react/src/pages/D2_ParameterStability.jsx`
**Route:** `/d2-parameter-stability`
**API:** `POST /api/v1/sensitivity/tornado` (dùng chung với D1), `GET /api/v1/sensitivity/jobs/{id}`, `GET /api/v1/sensitivity/history`

#### Vai trò
Trả lời câu hỏi **"lời giải tối ưu có đáng tin cậy không, hay chỉ cần dữ liệu sai lệch nhẹ là kết quả đã đổi hẳn?"** — đánh giá tính **ổn định/bền vững (robustness)** của nghiệm trước sự bất định của dữ liệu đầu vào. Đây là góc nhìn bổ sung cho D1: D1 hỏi "cái gì ảnh hưởng nhiều nhất", D2 hỏi "nghiệm có đủ chắc chắn để tin dùng không".

#### Chức năng chính
1. **Chạy kiểm tra ổn định**: về mặt kỹ thuật gọi cùng API Tornado như D1 (6 tham số cố định DI/CAP/Cb/Co/Cs/Cp), nhưng kết quả được diễn giải theo góc độ "ổn định" thay vì "độ nhạy"
2. **Biểu đồ radar (nhện)** hai lớp: vùng "Biến động" và vùng "Ổn định" cho từng tham số
3. **Bảng đánh giá định tính**: xếp loại mỗi tham số theo 4 mức (Rất ổn định / Ổn định / Trung bình / Biến động)
4. **Khối nhận xét tự động**: liệt kê 2 tham số ổn định nhất và 2 tham số biến động nhất

#### Nội dung & chỉ số hiển thị

**3 thẻ tổng quan**: giá trị mục tiêu cơ sở, mức biến thiên đã chọn (±%, điều chỉnh qua thanh trượt 5–30%), số tham số được phân tích (cố định 6).

**Biểu đồ radar "Ổn định tham số":** mỗi trục là 1 tham số, 2 lớp phủ:
- **Vùng "Biến động"** (màu cam) = mức % biến thiên chi phí quy đổi trên thang 0–100
- **Vùng "Ổn định"** (màu xanh) = phần bù của biến động (100 − biến động)
- Tham số nào vùng cam càng phình to thì càng kém ổn định — trực quan hoá nhanh tham số "yếu điểm" của mô hình

**Bảng "Đánh giá ổn định tham số"**: mỗi tham số có giá trị tại mức thấp/cao, khoảng biến thiên tuyệt đối, **thanh Chỉ số ổn định** (Progress bar, %, màu xanh/vàng/đỏ theo ngưỡng 80%/60%), và nhãn phân loại:
| Mức biến động (so với cơ sở) | Đánh giá |
|---|---|
| < 5% | Rất ổn định (xanh lá) |
| 5–15% | Ổn định (xanh dương) |
| 15–25% | Trung bình (cam) |
| ≥ 25% | Biến động (đỏ) |

**Khối "Nhận xét về ổn định"**: tự động liệt kê 2 tham số có khoảng biến thiên nhỏ nhất ("ổn định nhất") và 2 tham số có khoảng biến thiên lớn nhất ("biến động nhất"), kèm khuyến nghị chung: tham số biến động cao cần giám sát chặt hoặc bổ sung ràng buộc.

#### Giá trị mang lại cho người dùng
- **Đánh giá rủi ro mô hình trước khi triển khai thực tế**: nếu tham số quan trọng (vd. CAP) lại biến động cao, doanh nghiệp biết cần có kế hoạch dự phòng (buffer) thay vì tin tuyệt đối vào 1 con số tối ưu
- **Bổ sung góc nhìn định tính dễ hiểu**: nhãn "Rất ổn định/Biến động" và biểu đồ radar trực quan hơn số liệu thô, phù hợp trình bày cho người ra quyết định không chuyên kỹ thuật
- **Tái sử dụng hạ tầng tính toán**: không cần chạy thêm lần nào mới — dùng lại chính xác kết quả Tornado từ D1 nếu đã chạy cùng tham số/mức biến thiên, tiết kiệm thời gian tính toán

#### Câu hỏi phản biện có thể gặp
- *"D1 (Tornado) và D2 có phải là cùng một phép tính, chỉ khác cách hiển thị không?"* → Đúng — về mặt kỹ thuật, D2 gọi lại chính xác API `runTornado` giống chế độ Tornado ở D1 (cùng 6 tham số cố định DI/CAP/Cb/Co/Cs/Cp). D2 diễn giải lại cùng một bộ số liệu (spread/khoảng biến thiên) theo góc độ "độ ổn định của nghiệm" thay vì "mức độ ảnh hưởng của tham số" — hai câu hỏi nghiên cứu khác nhau nhưng dùng chung dữ liệu thực nghiệm là hợp lý về phương pháp luận, không phải trùng lặp thừa.
- *"Ngưỡng phân loại 5%/15%/25% có căn cứ khoa học nào không, hay chỉ là quy ước?"* → Đây là điểm cần lưu ý: các ngưỡng này là quy ước thiết kế của hệ thống (rule-of-thumb), chưa thấy trích dẫn từ tài liệu tham khảo cụ thể trong luận văn — nếu bị hỏi sâu, nên trình bày như một **ngưỡng vận hành hợp lý cho ngữ cảnh bài toán** chứ không phải kết quả suy ra từ lý thuyết thống kê chính thức.
- *"Tham số 'ổn định nhất' có phải là tham số ít quan trọng nhất không?"* → Không nhất thiết — 2 khái niệm khác nhau: độ nhạy (D1) đo mức ảnh hưởng đến chi phí, độ ổn định (D2) đo mức dao động của chính tham số đó gây ra biến động chi phí. Một tham số có thể ảnh hưởng lớn (nhạy cao) NHƯNG nếu giá trị của nó trong thực tế ít biến động (dữ liệu đáng tin cậy) thì vẫn được coi là rủi ro thấp trong vận hành thực tế — đây là lý do D1 và D2 bổ sung cho nhau chứ không thay thế nhau.

---

*(Hoàn tất — đã phân tích đầy đủ Nhóm A, B, C, D.)*
