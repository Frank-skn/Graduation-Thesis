#!/usr/bin/env python3
"""
anonymize.py
============
Anonymize all sensitive business data in:
  - DATN/Change_Dest/data/         (production CSVs)
  - DATN/Change_Dest/data_test/    (test-case CSVs, WH IDs only)

Mappings applied
----------------
  warehouse_id  : 1→WH01, 12→WH02, 15→WH03, 17→WH04, 28→WH05, ECR→WH06
  product_id    : sorted list → P0001, P0002, …  (zero-padded to 4 digits)
  box_id        : 1→BOX-01, …, 17→BOX-17
  warehouse_name: → "Distribution Center WH01", …
  market_code   : → REG-A, REG-B, …
  country_code  : → XX
  item_class    : all → CLS-A
  product_series: unique values → SER-001, SER-002, …
  product_style : unique values → STY-001, STY-002, …
  product_size  : unique values → keep as-is (just a number)
  product_name  : → Product-P0001, …
  box_name      : → BOX-01, …
  dates/timestamps: shift reference 2025-09-30 → 2024-01-01

Outputs
-------
  - Overwrites CSVs in data/ in-place (originals backed up to data_original/)
  - Saves mapping_reference.json alongside this script
"""

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ─────────────────────────── paths ────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
DATA_BAK = SCRIPT_DIR / "data_original"
DATA_TEST_DIR = SCRIPT_DIR / "data_test"
MAP_FILE = SCRIPT_DIR / "mapping_reference.json"

# ─────────────────────────── warehouse mapping ────────────────────────────────
WH_ID_MAP = {
    "1":   "WH01",
    "12":  "WH02",
    "15":  "WH03",
    "17":  "WH04",
    "28":  "WH05",
    "ECR": "WH06",
}
WH_MARKET_MAP = {
    "1":   "REG-A",
    "12":  "REG-B",
    "15":  "REG-C",
    "17":  "REG-D",
    "28":  "REG-E",
    "ECR": "REG-F",
}
WH_NAME_MAP = {
    "1":   "Distribution Center WH01",
    "12":  "Distribution Center WH02",
    "15":  "Distribution Center WH03",
    "17":  "Distribution Center WH04",
    "28":  "Distribution Center WH05",
    "ECR": "Distribution Center WH06",
}

# ─────────────────────────── box mapping ──────────────────────────────────────
BOX_ID_MAP = {str(i): f"BOX-{i:02d}" for i in range(1, 18)}

# ─────────────────────────── date shift ───────────────────────────────────────
ORIG_DATE = datetime(2025, 9, 30)
NEW_DATE  = datetime(2024, 1,  1)
DATE_DELTA = ORIG_DATE - NEW_DATE               # 638 days forward to orig
ORIG_DATE_STR = "2025-09-30"
NEW_DATE_STR  = "2024-01-01"
ORIG_TS_STR   = "2025-09-30 00:00:00"
NEW_TS_STR    = "2024-01-01 00:00:00"


def _shift_date(s: str) -> str:
    """Shift a date string YYYY-MM-DD by -DATE_DELTA (back toward NEW_DATE)."""
    try:
        d = datetime.strptime(s.strip(), "%Y-%m-%d")
        return (d - DATE_DELTA).strftime("%Y-%m-%d")
    except Exception:
        return s


def _shift_ts(s: str) -> str:
    """Shift a timestamp string YYYY-MM-DD HH:MM:SS by -DATE_DELTA."""
    try:
        d = datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S")
        return (d - DATE_DELTA).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return s


# ─────────────────────────── helpers ──────────────────────────────────────────
def _map_col(df: pd.DataFrame, col: str, mapping: dict) -> pd.DataFrame:
    """Apply a string→string mapping to a column (in-place, unknown keys kept)."""
    if col in df.columns:
        df[col] = df[col].astype(str).map(lambda v: mapping.get(v, v))
    return df


def _shift_date_col(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col in df.columns:
        df[col] = df[col].astype(str).map(_shift_date)
    return df


def _shift_ts_col(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col in df.columns:
        df[col] = df[col].astype(str).map(_shift_ts)
    return df


# ─────────────────────────── build product map ────────────────────────────────
def build_product_map() -> dict:
    p_csv = DATA_DIR / "product.csv"
    df = pd.read_csv(p_csv, dtype=str)
    ids = sorted(df["product_id"].dropna().unique().tolist())
    width = max(4, len(str(len(ids))))   # at least 4 digits
    fmt = f"P{{:0{width}d}}"
    return {orig: fmt.format(idx) for idx, orig in enumerate(ids, 1)}


# ─────────────────────────── per-file anonymisers ─────────────────────────────
def anon_warehouse(df: pd.DataFrame) -> pd.DataFrame:
    # warehouse_name  (do before id rename so we can use original id as key)
    if "warehouse_name" in df.columns:
        df["warehouse_name"] = df["warehouse_id"].astype(str).map(
            lambda v: WH_NAME_MAP.get(v, f"Distribution Center {WH_ID_MAP.get(v, v)}")
        )
    if "market_code" in df.columns:
        df["market_code"] = df["warehouse_id"].astype(str).map(
            lambda v: WH_MARKET_MAP.get(v, "REG-X")
        )
    if "country_code" in df.columns:
        df["country_code"] = "XX"
    _map_col(df, "warehouse_id", WH_ID_MAP)
    _shift_ts_col(df, "created_at")
    _shift_ts_col(df, "updated_at")
    return df


def anon_product(df: pd.DataFrame, prod_map: dict) -> pd.DataFrame:
    if "product_name" in df.columns:
        df["product_name"] = df["product_id"].astype(str).map(
            lambda v: f"Product-{prod_map.get(v, v)}"
        )
    # Build series/style/size maps (preserve relative groupings → no, just generic)
    if "item_class" in df.columns:
        df["item_class"] = "CLS-A"

    # Encode series, style, size with sorted-unique mapping
    for col, prefix in [("product_series", "SER"), ("product_style", "STY"), ("product_size", "SZ")]:
        if col in df.columns:
            uniq = sorted(df[col].dropna().unique().tolist())
            w = max(3, len(str(len(uniq))))
            local_map = {v: f"{prefix}-{{:0{w}d}}".format(i) for i, v in enumerate(uniq, 1)}
            df[col] = df[col].astype(str).map(lambda v, m=local_map: m.get(v, v))

    _map_col(df, "product_id", prod_map)
    _shift_ts_col(df, "created_at")
    _shift_ts_col(df, "updated_at")
    return df


def anon_box(df: pd.DataFrame) -> pd.DataFrame:
    # box_name → BOX-01 based on box_id before replacing id
    if "box_name" in df.columns:
        df["box_name"] = df["box_id"].astype(str).map(
            lambda v: BOX_ID_MAP.get(v, f"BOX-{v.zfill(2)}")
        )
    _map_col(df, "box_id", BOX_ID_MAP)
    # dimensions: keep as-is (just numbers, not company-identifiable)
    _shift_ts_col(df, "created_at")
    _shift_ts_col(df, "updated_at")
    return df


def anon_packing_details(df: pd.DataFrame, prod_map: dict) -> pd.DataFrame:
    _map_col(df, "product_id", prod_map)
    _map_col(df, "box_id", BOX_ID_MAP)
    _shift_ts_col(df, "created_at")
    return df


def anon_box_shipment(df: pd.DataFrame) -> pd.DataFrame:
    _map_col(df, "warehouse_id", WH_ID_MAP)
    _shift_ts_col(df, "created_at")
    _shift_ts_col(df, "updated_at")
    return df


def anon_inventory_begin(df: pd.DataFrame, prod_map: dict) -> pd.DataFrame:
    _map_col(df, "product_id", prod_map)
    _map_col(df, "warehouse_id", WH_ID_MAP)
    _shift_date_col(df, "effective_date")
    _shift_ts_col(df, "created_at")
    return df


def anon_inventory_flow(df: pd.DataFrame, prod_map: dict) -> pd.DataFrame:
    _map_col(df, "product_id", prod_map)
    _map_col(df, "warehouse_id", WH_ID_MAP)
    _shift_ts_col(df, "created_at")
    return df


def anon_unit_cost(df: pd.DataFrame, prod_map: dict) -> pd.DataFrame:
    _map_col(df, "product_id", prod_map)
    _map_col(df, "warehouse_id", WH_ID_MAP)
    _shift_ts_col(df, "created_at")
    return df


def anon_vendor_capacity(df: pd.DataFrame, prod_map: dict) -> pd.DataFrame:
    _map_col(df, "product_id", prod_map)
    _shift_ts_col(df, "created_at")
    return df


def anon_time_period(df: pd.DataFrame) -> pd.DataFrame:
    _shift_date_col(df, "start_date")
    _shift_date_col(df, "end_date")
    _shift_ts_col(df, "created_at")
    # month/year: recompute from new start_date
    if "start_date" in df.columns and "month" in df.columns:
        df["month"] = df["start_date"].map(
            lambda s: str(datetime.strptime(s, "%Y-%m-%d").month) if s else s
        )
    if "start_date" in df.columns and "year" in df.columns:
        df["year"] = df["start_date"].map(
            lambda s: str(datetime.strptime(s, "%Y-%m-%d").year) if s else s
        )
    return df


# ─────────────────────────── data_test helper ─────────────────────────────────
def anon_test_csv(path: Path, prod_map: dict | None = None) -> None:
    """Apply WH + optional product mapping to any test CSV."""
    df = pd.read_csv(path, dtype=str)
    changed = False

    if "warehouse_id" in df.columns:
        df["warehouse_id"] = df["warehouse_id"].astype(str).map(
            lambda v: WH_ID_MAP.get(v, v)
        )
        changed = True

    if prod_map and "product_id" in df.columns:
        df["product_id"] = df["product_id"].astype(str).map(
            lambda v: prod_map.get(v, v)
        )
        changed = True

    if "box_id" in df.columns:
        df["box_id"] = df["box_id"].astype(str).map(lambda v: BOX_ID_MAP.get(v, v))
        changed = True

    if changed:
        df.to_csv(path, index=False)


# ─────────────────────────── main ─────────────────────────────────────────────
def main():
    print("=" * 60)
    print("Anonymizing data…")
    print("=" * 60)

    # 1. Backup originals
    if DATA_BAK.exists():
        print(f"Backup already exists at {DATA_BAK} — skipping backup.")
    else:
        shutil.copytree(DATA_DIR, DATA_BAK)
        print(f"Backed up data/ → data_original/ ({len(list(DATA_BAK.glob('*.csv')))} files)")

    # 2. Build product map
    prod_map = build_product_map()
    print(f"Product map built: {len(prod_map)} products → P0001…P{len(prod_map):04d}")

    # 3. Dispatch per-file
    FILE_HANDLERS = {
        "warehouse.csv":       lambda df: anon_warehouse(df),
        "product.csv":         lambda df: anon_product(df, prod_map),
        "box.csv":             lambda df: anon_box(df),
        "packing_details.csv": lambda df: anon_packing_details(df, prod_map),
        "box_shipment.csv":    lambda df: anon_box_shipment(df),
        "inventory_begin.csv": lambda df: anon_inventory_begin(df, prod_map),
        "inventory_flow.csv":  lambda df: anon_inventory_flow(df, prod_map),
        "unit_cost.csv":       lambda df: anon_unit_cost(df, prod_map),
        "vendor_capacity.csv": lambda df: anon_vendor_capacity(df, prod_map),
        "time_period.csv":     lambda df: anon_time_period(df),
    }

    for fname, handler in FILE_HANDLERS.items():
        fpath = DATA_DIR / fname
        if not fpath.exists():
            print(f"  [SKIP] {fname} not found")
            continue
        df = pd.read_csv(fpath, dtype=str)
        df = handler(df)
        df.to_csv(fpath, index=False)
        print(f"  [OK]   {fname}  ({len(df)} rows)")

    # 4. Anonymize data_test CSVs
    if DATA_TEST_DIR.exists():
        test_csvs = sorted(DATA_TEST_DIR.rglob("*.csv"))
        print(f"\nAnonymizing data_test/ ({len(test_csvs)} CSV files)…")
        for tc in test_csvs:
            anon_test_csv(tc, prod_map)
            print(f"  [OK]   {tc.relative_to(SCRIPT_DIR)}")
    else:
        print("\n[INFO] data_test/ not found — skipping test anonymization.")

    # 5. Save mapping reference
    mapping = {
        "warehouse_id":   WH_ID_MAP,
        "warehouse_market": WH_MARKET_MAP,
        "warehouse_name": WH_NAME_MAP,
        "box_id":         BOX_ID_MAP,
        "product_id":     prod_map,
        "date_shift_days": DATE_DELTA.days,
        "date_from": ORIG_DATE_STR,
        "date_to":   NEW_DATE_STR,
    }
    MAP_FILE.write_text(json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nMapping reference saved → {MAP_FILE.name}")
    print("\nDone.")


if __name__ == "__main__":
    main()
