"""
Dataset versioning helper (B1 — lightweight).

Mỗi lần chạy tối ưu sẽ được gắn với một "phiên bản dữ liệu" — ảnh snapshot
metadata của bộ dữ liệu đầu vào (số sản phẩm/kho/kỳ + checksum SHA-256).

Nếu dữ liệu KHÔNG đổi giữa các lần chạy (cùng checksum) thì các run dùng
CHUNG một phiên bản → tránh tạo trùng. Khi dữ liệu đổi (checksum khác) thì
tự tạo phiên bản mới → truy vết được run nào chạy trên data nào (rolling horizon).

An toàn tuyệt đối: chỉ ĐỌC CSV để tính checksum + đếm, KHÔNG ghi/sửa CSV,
KHÔNG đụng thuật toán MA.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy.orm import Session

from backend.data_access.models_nds import DatasetVersion


def _compute_checksum(products, warehouses, periods) -> str:
    return hashlib.sha256(
        json.dumps({"I": sorted(products), "J": sorted(warehouses), "T": sorted(periods)},
                   sort_keys=True).encode()
    ).hexdigest()


def get_or_create_current_version(db: Session, csv_repo, created_by: str = "system") -> int:
    """
    Trả về version_id của phiên bản ứng với dữ liệu HIỆN TẠI.

    - Tính checksum của (I, J, T) hiện tại.
    - Nếu đã tồn tại version active có cùng checksum → tái sử dụng.
    - Nếu chưa → tạo version mới (đánh số tự động theo thời gian).
    """
    products = csv_repo.get_products()
    warehouses = csv_repo.get_warehouses()
    periods = csv_repo.get_time_periods()
    checksum = _compute_checksum(products, warehouses, periods)

    # Tìm version active đã có cùng checksum
    for v in (db.query(DatasetVersion)
              .filter(DatasetVersion.is_active == True)
              .order_by(DatasetVersion.version_id.desc())
              .all()):
        try:
            snap = json.loads(v.snapshot_data) if v.snapshot_data else {}
        except (json.JSONDecodeError, TypeError):
            snap = {}
        if snap.get("checksum") == checksum:
            return v.version_id

    # Chưa có → tạo mới
    snapshot_meta = {
        "num_products": len(products),
        "num_warehouses": len(warehouses),
        "num_periods": len(periods),
        "products": products,
        "warehouses": warehouses,
        "periods": periods,
        "checksum": checksum,
    }
    seq = db.query(DatasetVersion).count() + 1
    version = DatasetVersion(
        version_name=f"Data Version #{seq}",
        description=f"Auto-created on optimization run — {len(products)} products, "
                    f"{len(warehouses)} warehouses, {len(periods)} periods.",
        snapshot_data=json.dumps(snapshot_meta),
        created_by=created_by,
        is_active=True,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version.version_id
