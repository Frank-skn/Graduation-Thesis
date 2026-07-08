"""
Data overview endpoints.
Provides dataset exploration, model-parameter management,
and dataset version tracking.
"""
import json
import hashlib
import statistics
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.database import get_db_nds, get_csv_data
from backend.data_access.csv_repository import CsvOptimizationDataRepository
from backend.data_access.models_nds import ModelParameter, DatasetVersion
from backend.schemas.data_overview import (
    DataOverview,
    ParameterSummary,
    DatasetVersionInfo,
    DatasetVersionList,
)

router = APIRouter()


# ------------------------------------------------------------------ #
#  1. GET / -- Dataset overview                                       #
# ------------------------------------------------------------------ #

@router.get("/", response_model=DataOverview)
def get_data_overview(csv_repo: CsvOptimizationDataRepository = Depends(get_csv_data)):
    """
    Get high-level overview of the loaded optimization dataset.

    Returns product / warehouse / period counts and per-parameter
    summary statistics (min, max, mean, std, zero-count).
    """
    opt_input = csv_repo.get_optimization_input()

    # Actual distinct combination counts from the CSV files.
    # These reflect the real operational domain, not the theoretical Cartesian product:
    #   BI[(i,j)]  → denominator = distinct (i,j) in inventory_flow
    #   CP[(i,j)]  → denominator = |I|×|J| theoretical (packing coverage)
    #   U/L/DI/cost[(i,j,t)] → denominator = distinct (i,j,t) in inventory_flow
    #   CAP[(i,t)] → denominator = |I|×|T|
    cc = csv_repo.get_actual_combination_counts()

    param_meta = {
        "BI":  (opt_input.BI,  "ij",  cc["ij_flow"]),   # vs actual (i,j) in flow
        "CP":  (opt_input.CP,  "ij",  cc["ij_theor"]),  # vs |I|×|J| theoretical
        "U":   (opt_input.U,   "ijt", cc["ijt_flow"]),  # vs actual (i,j,t) in flow
        "L":   (opt_input.L,   "ijt", cc["ijt_flow"]),
        "DI":  (opt_input.DI,  "ijt", cc["ijt_flow"]),
        "CAP": (opt_input.CAP, "it",  cc["it"]),        # vs |I|×|T|
        "Cb":  (opt_input.Cb,  "ijt", cc["ijt_flow"]),
        "Co":  (opt_input.Co,  "ijt", cc["ijt_flow"]),
        "Cs":  (opt_input.Cs,  "ijt", cc["ijt_flow"]),
        "Cp":  (opt_input.Cp,  "ijt", cc["ijt_flow"]),
    }

    summaries: List[ParameterSummary] = []
    for name, (d, idx_type, max_ent) in param_meta.items():
        if not d:
            continue
        float_values = [float(v) for v in d.values()]
        summaries.append(
            ParameterSummary(
                name=name,
                index_type=idx_type,
                max_entries=max_ent,
                num_entries=len(float_values),
                min_value=min(float_values),
                max_value=max(float_values),
                mean_value=statistics.mean(float_values),
                std_value=(
                    statistics.stdev(float_values)
                    if len(float_values) > 1
                    else 0.0
                ),
                zero_count=sum(1 for v in float_values if v == 0),
                sample_keys=[str(k) for k in list(d.keys())[:5]],
            )
        )

    return DataOverview(
        num_products=len(opt_input.I),
        num_warehouses=len(opt_input.J),
        num_periods=len(opt_input.T),
        products=opt_input.I,
        warehouses=opt_input.J,
        periods=opt_input.T,
        parameters=summaries,
        total_combinations=(
            len(opt_input.I) * len(opt_input.J) * len(opt_input.T)
        ),
    )


# ------------------------------------------------------------------ #
#  2. GET /parameters -- List model parameters                        #
# ------------------------------------------------------------------ #

class ModelParameterResponse(BaseModel):
    """Single model parameter."""
    param_id: int
    param_name: str
    param_value: float
    param_description: Optional[str] = None


class ModelParameterList(BaseModel):
    """Collection of model parameters."""
    parameters: List[ModelParameterResponse]
    total: int


@router.get("/parameters", response_model=ModelParameterList)
def get_model_parameters(db: Session = Depends(get_db_nds)):
    """
    Get all model parameters from SQLite model_parameter table.
    """
    params = db.query(ModelParameter).order_by(
        ModelParameter.param_name
    ).all()

    return ModelParameterList(
        parameters=[
            ModelParameterResponse(
                param_id=p.param_id,
                param_name=p.param_name,
                param_value=float(p.param_value or 0),
                param_description=p.param_description,
            )
            for p in params
        ],
        total=len(params),
    )


# ------------------------------------------------------------------ #
#  3. PUT /parameters/{param_name} -- Update a model parameter        #
# ------------------------------------------------------------------ #

class ModelParameterUpdate(BaseModel):
    """Payload to update a model parameter value."""
    param_value: float = Field(..., description="New parameter value")


@router.put("/parameters/{param_name}", response_model=ModelParameterResponse)
def update_model_parameter(
    param_name: str,
    update: ModelParameterUpdate,
    db: Session = Depends(get_db_nds),
):
    """
    Update a model parameter value by name.
    """
    param = db.query(ModelParameter).filter(
        ModelParameter.param_name == param_name
    ).first()

    if not param:
        raise HTTPException(
            status_code=404,
            detail=f"Parameter '{param_name}' not found",
        )

    param.param_value = update.param_value
    db.commit()
    db.refresh(param)

    return ModelParameterResponse(
        param_id=param.param_id,
        param_name=param.param_name,
        param_value=float(param.param_value or 0),
        param_description=param.param_description,
    )


# ------------------------------------------------------------------ #
#  4. GET /datasets -- List dataset versions                          #
# ------------------------------------------------------------------ #

@router.get("/datasets", response_model=DatasetVersionList)
def list_dataset_versions(
    limit: int = 50,
    db: Session = Depends(get_db_nds),
):
    """
    List all active dataset version snapshots, newest first.
    """
    versions = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.is_active == True)
        .order_by(DatasetVersion.created_at.desc())
        .limit(limit)
        .all()
    )

    items: List[DatasetVersionInfo] = []
    for v in versions:
        snapshot = {}
        if v.snapshot_data:
            try:
                snapshot = json.loads(v.snapshot_data)
            except (json.JSONDecodeError, TypeError):
                pass

        items.append(
            DatasetVersionInfo(
                version_id=v.version_id,
                scenario_id=snapshot.get("scenario_id", 0),
                label=v.version_name,
                created_at=v.created_at or datetime.utcnow(),
                created_by=v.created_by or "system",
                num_products=snapshot.get("num_products", 0),
                num_warehouses=snapshot.get("num_warehouses", 0),
                num_periods=snapshot.get("num_periods", 0),
                checksum=snapshot.get("checksum"),
                notes=v.description,
            )
        )

    return DatasetVersionList(versions=items, total=len(items))


# ------------------------------------------------------------------ #
#  5. POST /datasets -- Create a dataset version snapshot              #
# ------------------------------------------------------------------ #

class DatasetVersionCreate(BaseModel):
    """Payload to create a new dataset version snapshot."""
    version_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    created_by: str = Field(default="system", max_length=100)


@router.post("/datasets", response_model=DatasetVersionInfo, status_code=201)
def create_dataset_version(
    request: DatasetVersionCreate,
    db_nds: Session = Depends(get_db_nds),
    csv_repo: CsvOptimizationDataRepository = Depends(get_csv_data),
):
    """
    Create a dataset version snapshot from the current CSV data.

    Captures the current set of products, warehouses, and periods,
    computes a SHA-256 checksum, and stores the metadata in
    dataset_version (SQLite).
    """
    products = csv_repo.get_products()
    warehouses = csv_repo.get_warehouses()
    periods = csv_repo.get_time_periods()

    # Build snapshot metadata
    snapshot_meta = {
        "scenario_id": 0,
        "num_products": len(products),
        "num_warehouses": len(warehouses),
        "num_periods": len(periods),
        "products": products,
        "warehouses": warehouses,
        "periods": periods,
        "checksum": hashlib.sha256(
            json.dumps(
                {"I": products, "J": warehouses, "T": periods},
                sort_keys=True,
            ).encode()
        ).hexdigest(),
    }

    version = DatasetVersion(
        version_name=request.version_name,
        description=request.description,
        snapshot_data=json.dumps(snapshot_meta),
        created_by=request.created_by,
        is_active=True,
    )

    db_nds.add(version)
    db_nds.commit()
    db_nds.refresh(version)

    return DatasetVersionInfo(
        version_id=version.version_id,
        scenario_id=0,
        label=version.version_name,
        created_at=version.created_at or datetime.utcnow(),
        created_by=version.created_by or "system",
        num_products=snapshot_meta["num_products"],
        num_warehouses=snapshot_meta["num_warehouses"],
        num_periods=snapshot_meta["num_periods"],
        checksum=snapshot_meta["checksum"],
        notes=version.description,
    )


# ------------------------------------------------------------------ #
#  6. GET /algorithm-parameters -- Tham số giải thuật Memetic          #
# ------------------------------------------------------------------ #

class AlgoParam(BaseModel):
    """Một tham số giải thuật (đọc từ config.json)."""
    name: str
    symbol: str
    value: float
    group: str            # "GA" | "ALNS" | "Dừng" | "Chung"
    description: str
    taguchi: bool = False  # True nếu là 1 trong 5 tham số hiệu chỉnh Taguchi


class AlgoParamList(BaseModel):
    parameters: List[AlgoParam]
    total: int
    source: str
    tuned_by: str


@router.get("/algorithm-parameters", response_model=AlgoParamList)
def get_algorithm_parameters():
    """
    Trả về tham số của giải thuật Memetic (Hybrid GA-ALNS) từ config.json.

    5 tham số Taguchi (n_pop, G_max, p_crossover, p_mutation, n_iterations)
    được đánh dấu taguchi=True — đây là cấu hình tối ưu từ thực nghiệm Taguchi
    (Chương 6 luận văn: n_pop=38, G_max=500, ...).
    """
    from pathlib import Path
    # data_overview.py ở backend/api/v1/endpoints → parents[3] = backend/
    cfg_path = Path(__file__).resolve().parents[3] / "ma" / "config.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        cfg = {}

    ga = cfg.get("ga", {})
    alns = cfg.get("alns", {})
    stopping = cfg.get("stopping", {})

    params: List[AlgoParam] = [
        # ── 5 tham số Taguchi ─────────────────────────────────────
        AlgoParam(name="Kích thước quần thể", symbol="n_pop", value=ga.get("n_pop", 0),
                  group="GA", taguchi=True,
                  description="Số cá thể trong quần thể GA (Taguchi: ảnh hưởng lớn nhất – 45.81%)"),
        AlgoParam(name="Số thế hệ tối đa", symbol="G_max", value=ga.get("G_max", 0),
                  group="GA", taguchi=True,
                  description="Số thế hệ tối đa của GA trước khi dừng"),
        AlgoParam(name="Xác suất lai chéo", symbol="p_crossover", value=ga.get("p_crossover", 0),
                  group="GA", taguchi=True,
                  description="Xác suất thực hiện lai chéo giữa hai cá thể cha mẹ"),
        AlgoParam(name="Xác suất đột biến", symbol="p_mutation", value=ga.get("p_mutation", 0),
                  group="GA", taguchi=True,
                  description="Xác suất đột biến tạo đa dạng nghiệm"),
        AlgoParam(name="Số vòng lặp ALNS", symbol="n_iterations", value=alns.get("n_iterations", 0),
                  group="ALNS", taguchi=True,
                  description="Số vòng lặp tìm kiếm lân cận lớn thích nghi để cải thiện cục bộ"),
        # ── Tham số GA cố định ────────────────────────────────────
        AlgoParam(name="Số thế hệ dừng sớm", symbol="G_stag", value=ga.get("G_stag", 0),
                  group="GA", description="Dừng nếu không cải thiện trong G_stag thế hệ liên tiếp"),
        AlgoParam(name="Kích thước tournament", symbol="k_tournament", value=ga.get("k_tournament", 0),
                  group="GA", description="Số cá thể tham gia mỗi lần chọn lọc tournament"),
        AlgoParam(name="Tỷ lệ seed từ MILP", symbol="milp_seed_fraction", value=ga.get("milp_seed_fraction", 0),
                  group="GA", description="Tỷ lệ quần thể khởi tạo từ nghiệm MILP warm-start"),
        AlgoParam(name="Tỷ lệ nghiệm heuristic", symbol="heuristic_fraction", value=ga.get("heuristic_fraction", 0),
                  group="GA", description="Tỷ lệ quần thể khởi tạo bằng heuristic theo mức thiếu hụt"),
        # ── Tham số ALNS cố định ──────────────────────────────────
        AlgoParam(name="Tỷ lệ phá hủy tối thiểu", symbol="q_min_ratio", value=alns.get("q_min_ratio", 0),
                  group="ALNS", description="Tỷ lệ nhỏ nhất của nghiệm bị phá hủy mỗi vòng ALNS"),
        AlgoParam(name="Tỷ lệ phá hủy tối đa", symbol="q_max_ratio", value=alns.get("q_max_ratio", 0),
                  group="ALNS", description="Tỷ lệ lớn nhất của nghiệm bị phá hủy mỗi vòng ALNS"),
        AlgoParam(name="Hệ số cập nhật trọng số", symbol="lambda_rho", value=alns.get("lambda_rho", 0),
                  group="ALNS", description="Hệ số λρ cập nhật trọng số thích nghi của toán tử"),
        # ── Dừng ──────────────────────────────────────────────────
        AlgoParam(name="Giới hạn thời gian (giây/SP)", symbol="time_limit_seconds",
                  value=stopping.get("time_limit_seconds", 0),
                  group="Dừng", description="Trần thời gian tối đa cho mỗi sản phẩm"),
    ]

    return AlgoParamList(
        parameters=params,
        total=len(params),
        source="backend/ma/config.json",
        tuned_by=cfg.get("_comment", "Hiệu chỉnh bằng phương pháp Taguchi (Chương 6)"),
    )


# ------------------------------------------------------------------ #
#  7. GET /cost-parameters -- Tham số chi phí & vận hành (read-only)   #
# ------------------------------------------------------------------ #

class CostParam(BaseModel):
    """Một tham số chi phí/vận hành (giá trị nền, chỉ đọc)."""
    name: str
    symbol: str
    value: str            # chuỗi để hiển thị (có đơn vị/khoảng)
    unit: str
    group: str            # "Chi phí" | "Vận chuyển"
    description: str


class CostParamList(BaseModel):
    parameters: List[CostParam]
    total: int
    note: str


@router.get("/cost-parameters", response_model=CostParamList)
def get_cost_parameters(
    csv_repo: CsvOptimizationDataRepository = Depends(get_csv_data),
):
    """
    Trả về các tham số chi phí và vận hành của mô hình (Bảng 3.3 luận văn).

    Đây là DỮ LIỆU NỀN (giá trị vận hành thực của doanh nghiệp), chỉ hiển thị
    để tham khảo. Muốn thay đổi để đánh giá tác động → dùng Phân tích kịch bản
    (What-if / Độ nhạy), không sửa trực tiếp tại đây.
    """
    inp = csv_repo.get_optimization_input()

    def _mode(d):
        """Giá trị xuất hiện nhiều nhất (đại diện) trong dict."""
        if not d:
            return None
        from collections import Counter
        c = Counter(round(float(v), 4) for v in d.values())
        return c.most_common(1)[0][0]

    co = _mode(inp.Co)
    cs = _mode(inp.Cs)
    cb = _mode(inp.Cb)
    cp = _mode(inp.Cp)

    params = [
        CostParam(name="Chi phí tồn kho vượt mức", symbol="Co", value=str(co), unit="USD/đơn vị",
                  group="Chi phí", description="Chi phí phát sinh khi tồn kho vượt mức trần U"),
        CostParam(name="Chi phí thiếu hụt", symbol="Cs", value=str(cs), unit="USD/đơn vị",
                  group="Chi phí", description="Chi phí phát sinh khi tồn kho thấp hơn mức sàn L"),
        CostParam(name="Chi phí nợ đơn", symbol="Cb", value=str(cb), unit="USD/đơn vị",
                  group="Chi phí", description="Chi phí phát sinh khi tồn kho âm / không đáp ứng đủ nhu cầu (thành phần chi phối)"),
        CostParam(name="Chi phí phạt đóng gói", symbol="Cp", value=str(cp), unit="USD/lần",
                  group="Chi phí", description="Chi phí phạt khi lượng phân bổ/điều chuyển không đủ một case-pack"),
        CostParam(name="Chi phí vận chuyển ngang", symbol="TC", value=str(round(csv_repo.get_transport_cost(), 4)) if hasattr(csv_repo, "get_transport_cost") else "1.2", unit="USD/km",
                  group="Vận chuyển", description="Chi phí trên một đơn vị khoảng cách cho mỗi tuyến điều chuyển ngang (container 40ft Dry)"),
        CostParam(name="Thời gian giao hàng từ nguồn (OA)", symbol="LT_OA", value="8", unit="tuần",
                  group="Vận chuyển", description="Thời gian vận chuyển từ kho trung tâm (Việt Nam) đến nhà máy nhận (Hoa Kỳ)"),
        CostParam(name="Thời gian điều chuyển ngang (PLT)", symbol="LT_PLT", value="2–3", unit="tuần",
                  group="Vận chuyển", description="Thời gian vận chuyển hàng giữa các nhà máy nhận"),
    ]

    return CostParamList(
        parameters=params,
        total=len(params),
        note="Giá trị nền từ dữ liệu vận hành doanh nghiệp. Để phân tích tác động khi thay đổi, dùng chức năng Phân tích kịch bản (What-if / Độ nhạy).",
    )


# ------------------------------------------------------------------ #
#  8. GET /datasets/{version_id}/runs -- Các lần chạy dùng phiên bản   #
# ------------------------------------------------------------------ #

@router.get("/datasets/{version_id}/runs")
def get_runs_for_version(version_id: int, db: Session = Depends(get_db_nds)):
    """
    Liệt kê các lần chạy tối ưu đã sử dụng phiên bản dữ liệu này.
    Phục vụ truy vết: 'phiên bản X được dùng bởi những run nào'.
    """
    from backend.data_access.models_nds import OptimizationRun
    runs = (
        db.query(OptimizationRun)
        .filter(OptimizationRun.version_id == version_id)
        .order_by(OptimizationRun.run_id.desc())
        .all()
    )
    return {
        "version_id": version_id,
        "runs": [
            {
                "run_id": r.run_id,
                "run_time": r.run_time.isoformat() if r.run_time else None,
                "solver_status": r.solver_status,
                "objective_value": float(r.objective_value or 0),
            }
            for r in runs
        ],
        "total": len(runs),
    }
