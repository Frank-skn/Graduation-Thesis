# Decision Support System for Single-Supplier, Multi-Buyer SMI

Hệ thống hỗ trợ ra quyết định (DSS) cho bài toán quản lý tồn kho do nhà cung cấp
quản lý (Supplier-Managed Inventory) trong bối cảnh một nhà cung cấp – nhiều người
mua (Single-Supplier, Multi-Buyer). Hệ thống tối ưu hóa phân bổ và điều chuyển tồn
kho bằng giải thuật Memetic (Hybrid GA-ALNS).

## Tổng quan kiến trúc

```
Dữ liệu (CSV) → Backend (FastAPI) → Giải thuật MA (GA-ALNS) → SQLite (NDS/DDS) → Frontend (React)
```

### Công nghệ sử dụng

- **Backend**: FastAPI + SQLAlchemy + Pydantic
- **Giải thuật tối ưu**: Memetic Algorithm (Hybrid GA-ALNS), tinh chỉnh bằng Taguchi
- **Cơ sở dữ liệu**: SQLite (NDS `nds.db` + DDS `dds.db` với star schema)
- **Dữ liệu đầu vào**: Tệp CSV trong thư mục `data/`
- **Frontend**: React 18 + Vite + Ant Design + Recharts + Tailwind CSS
- **Triển khai**: Docker + Docker Compose

## Cấu trúc dự án

```
Graduation-Thesis/
├── backend/                # Ứng dụng FastAPI
│   ├── api/                # REST endpoints
│   ├── core/               # Cấu hình & kết nối cơ sở dữ liệu
│   ├── data_access/        # Repository truy cập dữ liệu (CSV/NDS/DDS)
│   ├── domain/             # Nghiệp vụ (dịch vụ tối ưu, what-if, sensitivity)
│   ├── ma/                 # Giải thuật Memetic (GA + ALNS + core)
│   └── schemas/            # Pydantic models
├── frontend-react/         # Giao diện React (Vite + Ant Design)
│   └── src/
│       ├── pages/          # Các trang A/B/C/D
│       ├── components/     # Thành phần UI dùng chung
│       ├── services/       # Gọi API
│       └── theme/          # Design tokens (bảng màu thống nhất)
├── data/                   # Dữ liệu đầu vào (CSV) + SQLite (nds.db, dds.db)
├── docker/                 # Cấu hình Docker (backend)
├── tests/                  # Kiểm thử API
├── docker-compose.yml
└── requirements.txt
```

## Tính năng chính

1. **A1/A2 – Dữ liệu & tham số**: Xem tổng quan dữ liệu đầu vào, tham số mô hình
   và tham số giải thuật (Taguchi), quản lý phiên bản dữ liệu.
2. **B0/B1/B2 – Tối ưu hóa**: Chạy giải thuật MA, xem kết quả & phân tích chi phí,
   phân bổ và động thái tồn kho (điều chuyển ngang PLT).
3. **C1/C2 – Phân tích kịch bản**: Phân tích What-If và so sánh KPI giữa các lần chạy.
4. **D1/D2 – Phân tích độ nhạy & rủi ro**: Phân tích OAT/Tornado, đánh giá độ bền
   vững của nghiệm tối ưu.

## Khởi chạy nhanh

### Yêu cầu
- Docker và Docker Compose

### Các bước

1. Cấu hình môi trường:
```bash
cp .env.example .env
```

2. Khởi động dịch vụ:
```bash
docker compose up -d
```

3. Truy cập ứng dụng:
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs

## Luồng làm việc

1. **Xem dữ liệu**: Kiểm tra tính đầy đủ, chất lượng dữ liệu đầu vào (A1).
2. **Chạy tối ưu**: Chọn bộ giải MA và cấu hình, chạy tối ưu hóa (B0).
3. **Phân tích**: Xem kết quả, chi phí, phân bổ và điều chuyển tồn kho (B1/B2).
4. **Kịch bản**: Tạo What-If và so sánh với lần chạy cơ sở (C1/C2).
5. **Độ nhạy**: Đánh giá tác động thay đổi tham số và độ bền nghiệm (D1/D2).

## Kiểm thử

```bash
docker compose exec backend pytest tests/
```
