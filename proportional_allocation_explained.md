# Proportional Allocation Heuristic — Giải thích chi tiết

## 1. Bối cảnh: Tại sao cần 3 phương pháp?

Trong hệ thống SS-MB-SMI (Single-Supplier Multi-Buyer Supplier-Managed Inventory), nhà cung cấp phải quyết định: **giao bao nhiêu hàng cho mỗi kho, mỗi tuần?**

Có 3 cách tiếp cận, từ đơn giản đến phức tạp:

| # | Phương pháp | Ý nghĩa | Vai trò trong bài |
|---|-------------|---------|-------------------|
| 1 | **Do-nothing** (Baseline) | Không giao hàng gì cả | Trường hợp tệ nhất, mốc tham chiếu |
| 2 | **Proportional Allocation** (Heuristic) | Chia hàng theo tỉ lệ thiếu hụt | Cách "thủ công thông minh", benchmark thực tế |
| 3 | **MILP** (Tối ưu) | Giải bài toán tối ưu toàn cục | Đề xuất của bài báo |

---

## 2. Ý tưởng cốt lõi của Proportional Allocation

> **"Ai thiếu nhiều hơn thì được nhận nhiều hơn"**

Đây là cách một người quản lý kho có kinh nghiệm sẽ ra quyết định:
- Nhìn tồn kho hiện tại của từng kho
- So sánh với mức tồn kho tối thiểu (safety stock floor)
- Kho nào thiếu nhiều → ưu tiên giao nhiều
- Số lượng giao phải là bội số của thùng đóng gói (case-pack)

**Điểm yếu quan trọng:** Phương pháp này chỉ nhìn **tuần hiện tại** — không biết tuần sau nhu cầu sẽ thay đổi thế nào. Trong lý thuyết tối ưu, đây gọi là **myopic** (cận thị).

---

## 3. Thuật toán từng bước

### Đầu vào

Với mỗi **sản phẩm i**, xét qua từng **tuần t**:

| Ký hiệu | Ý nghĩa | Ví dụ |
|----------|---------|-------|
| $I_{ij}^{before}$ | Tồn kho hiện tại của sản phẩm i tại kho j (sau khi trừ nhu cầu) | Kho A: 5, Kho B: 20 |
| $L_{ijt}$ | Mức tồn kho tối thiểu (safety stock floor) | Kho A: 40, Kho B: 60 |
| $U_{ijt}$ | Mức tồn kho tối đa (ceiling) | Kho A: 80, Kho B: 100 |
| $CAP_{it}$ | Năng lực giao hàng tối đa của nhà cung cấp cho SP i trong tuần t | 100 thùng |
| $CP_{ij}$ | Kích thước thùng đóng gói (case-pack) — phải giao theo bội số | 4 thùng/kiện |

### Bước 1 — Cập nhật tồn kho theo nhu cầu

Đầu mỗi tuần, tồn kho thay đổi theo biến động nhu cầu (DI):

$$I_{ij}^{before} = I_{ij}^{prev} + DI_{ijt}$$

> DI thường âm (bán ra → tồn kho giảm). Ví dụ: tồn kho 50, bán 45 → $I^{before}$ = 5.

### Bước 2 — Tính deficit (mức thiếu hụt)

$$d_{jt} = \max(0, \ L_{ijt} - I_{ij}^{before})$$

| Kho | Tồn kho hiện tại | Floor (L) | Deficit |
|-----|:-:|:-:|:-:|
| A | 5 | 40 | max(0, 40-5) = **35** |
| B | 20 | 60 | max(0, 60-20) = **40** |
| **Tổng** | | | **75** |

### Bước 3 — Phân bổ theo tỉ lệ deficit

Mỗi kho nhận lượng hàng tỉ lệ với mức thiếu của nó, **làm tròn xuống** bội số case-pack:

$$\tilde{q}_{ijt} = \left\lfloor \frac{CAP_{it} \times d_{jt}}{\sum_{j'} d_{j't}} \times \frac{1}{CP_{ij}} \right\rfloor \times CP_{ij}$$

**Ví dụ cụ thể** (CAP = 100, CP = 4 cho cả 2 kho):

| Kho | Tính toán | Kết quả |
|-----|-----------|:-------:|
| A | 100 × (35/75) = 46.67 → ⌊46.67/4⌋ × 4 = 11 × 4 | **44** |
| B | 100 × (40/75) = 53.33 → ⌊53.33/4⌋ × 4 = 13 × 4 | **52** |
| **Tổng đã phân bổ** | | **96** |
| **Phần dư** | 100 - 96 | **4** |

> **Trường hợp đặc biệt:** Nếu không kho nào thiếu (tổng deficit = 0), chia đều CAP cho tất cả kho, vẫn làm tròn theo CP.

### Bước 4 — Phân bổ phần dư

Phần dư (do làm tròn) = 4 thùng. Ưu tiên giao cho **kho thiếu nhiều nhất trước**:

| Kho | Deficit | Ưu tiên | Nhận thêm |
|-----|:-------:|:-------:|:---------:|
| B | 40 (lớn nhất) | 1 | +4 (1 kiện × CP=4) |
| A | 35 | 2 | +0 (hết dư) |

**Kết quả cuối:**
- Kho A nhận: **44 thùng**
- Kho B nhận: **52 + 4 = 56 thùng**
- Tổng: 44 + 56 = **100 = CAP** ✓

### Bước 5 — Cập nhật tồn kho & tính chi phí

$$I_{ijt} = I_{ij}^{before} + \tilde{q}_{ijt}$$

| Kho | Tồn trước | Nhận | Tồn sau | Floor (L) | Ceiling (U) | Trạng thái |
|-----|:---------:|:----:|:-------:|:---------:|:-----------:|:----------:|
| A | 5 | 44 | **49** | 40 | 80 | OK (40 ≤ 49 ≤ 80) |
| B | 20 | 56 | **76** | 60 | 100 | OK (60 ≤ 76 ≤ 100) |

Chi phí phát sinh khi tồn kho **ra ngoài ngưỡng**:

$$C^{prop} = \sum_{i,j,t} \Big[ \underbrace{C^o_{ijt} \cdot \max(0,\ I_{ijt} - U_{ijt})}_{\text{phí tồn thừa}} + \underbrace{C^s_{ijt} \cdot \max(0,\ L_{ijt} - I_{ijt})}_{\text{phí thiếu hụt}} + \underbrace{C^b_{ijt} \cdot \max(0,\ -I_{ijt})}_{\text{phí backlog}} \Big]$$

Trong ví dụ trên, cả 2 kho đều nằm trong ngưỡng → chi phí tuần này = 0.

---

## 4. Ví dụ hoàn chỉnh 2 tuần — Tại sao Proportional thua MILP?

Hãy xem xét 1 sản phẩm, 2 kho (A, B), 2 tuần. CAP = 100 mỗi tuần, CP = 4.

### Dữ liệu đầu vào

| | Kho A | Kho B |
|---|:-:|:-:|
| **Tồn kho ban đầu (BI)** | 50 | 50 |
| **Floor (L) cả 2 tuần** | 40 | 40 |
| **Ceiling (U) cả 2 tuần** | 80 | 80 |
| **DI tuần 1** (bán ra) | -10 | -10 |
| **DI tuần 2** (bán ra) | -80 | -20 |
| **Chi phí tồn thừa (Co)** | 1 | 1 |
| **Chi phí thiếu hụt (Cs)** | 10 | 10 |
| **Chi phí backlog (Cb)** | 100 | 100 |

> Lưu ý: Tuần 2 kho A bán rất mạnh (-80), kho B bán ít (-20). **Proportional không biết điều này khi quyết định tuần 1.**

---

### Proportional giải (tuần 1 rồi tuần 2, tuần nào biết tuần đó)

**Tuần 1:**

```
Tồn kho sau DI:   A = 50 + (-10) = 40    B = 50 + (-10) = 40
Floor:             A = 40                  B = 40
Deficit:           A = max(0, 40-40) = 0   B = max(0, 40-40) = 0
```

Không ai thiếu → **chia đều**: mỗi kho 100/2 = 50, làm tròn CP=4 → mỗi kho nhận **48**.

Tổng đã phân bổ = 48 + 48 = 96 → **dư 4 thùng**.

Phân bổ phần dư: deficit cả 2 kho đều = 0 (bằng nhau), nên kho đầu tiên trong danh sách (A) nhận thêm: ⌊4/4⌋ × 4 = **4 thùng**.

Kết quả: **A nhận 52**, **B nhận 48**.

```
Tồn sau giao:     A = 40 + 52 = 92        B = 40 + 48 = 88
Overstock:         A = max(0, 92-80) = 12  B = max(0, 88-80) = 8
Chi phí tuần 1:    12×1 + 8×1 = 20
```

**Tuần 2:**

```
Tồn kho sau DI:   A = 92 + (-80) = 12     B = 88 + (-20) = 68
Deficit:           A = max(0, 40-12) = 28  B = max(0, 40-68) = 0
```

Chỉ A thiếu → A nhận 100% CAP: ⌊100/4⌋×4 = **100**.

```
Tồn sau giao:     A = 12 + 100 = 112      B = 68 + 0 = 68
Overstock A:       max(0, 112-80) = 32     → chi phí: 32×1 = 32
Chi phí tuần 2:    32
```

**Tổng chi phí Proportional = 20 + 32 = 52**

---

### MILP giải (nhìn cả 2 tuần cùng lúc)

MILP **biết trước** tuần 2 kho A sẽ bán rất mạnh, nên tuần 1 ưu tiên giao cho A:

**Tuần 1:** A nhận **80**, B nhận **20**

```
Tồn sau giao:     A = 40 + 80 = 120       B = 40 + 20 = 60
Overstock A:       max(0, 120-80) = 40     → chi phí: 40×1 = 40
Shortage B:        max(0, 40-60) = 0       → OK
Chi phí tuần 1:    40
```

Trông tệ hơn Proportional ở tuần 1! Nhưng...

**Tuần 2:**

```
Tồn kho sau DI:   A = 120 + (-80) = 40    B = 60 + (-20) = 40
Deficit:           A = 0                    B = 0
```

Cả 2 kho đều vừa đúng floor! MILP phân bổ CAP tuần 2 vừa đủ:

A nhận **40**, B nhận **40**

```
Tồn sau giao:     A = 40 + 40 = 80        B = 40 + 40 = 80
Overstock:         0                        0
Chi phí tuần 2:    0
```

**Tổng chi phí MILP = 40 + 0 = 40**

---

### So sánh

| | Proportional | MILP | Lý do |
|---|:-:|:-:|---|
| **Tuần 1** | 20 | 40 | MILP chấp nhận overstock tạm thời |
| **Tuần 2** | 32 | 0 | Nhưng bù lại tuần sau hoàn hảo |
| **Tổng** | **52** | **40** | MILP tốt hơn **23.1%** |

> **Bài học:** MILP "chấp nhận đau ngắn hạn, để được lợi dài hạn" — đây là sức mạnh của tối ưu đa chu kỳ mà heuristic myopic không có.

---

## 5. Kết quả thực tế trên dữ liệu 943 sản phẩm

| Phương pháp | Tổng chi phí | So với MILP |
|---|--:|--:|
| **Do-nothing** (không giao gì) | 135,035,759 | +2,077% |
| **Proportional** (heuristic) | 8,145,479 | +31.3% |
| **MILP** (tối ưu) | 6,203,728 | — (baseline) |

- MILP tiết kiệm **95.41%** so với do-nothing
- MILP tiết kiệm **23.84%** so với proportional

> Con số 23.84% là đóng góp thực tế: nếu doanh nghiệp đang chia hàng thủ công theo tỉ lệ (như heuristic), hệ thống này giúp tiết kiệm thêm gần 1/4 chi phí.

