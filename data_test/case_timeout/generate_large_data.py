"""
Generate large test data to force MILP solver timeout.

Scenario: 50 products × 6 warehouses × 8 periods = 2,400 cells
With time_limit=1 second, CBC should not reach Optimal.
"""
import csv
import os
import random

random.seed(42)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

N_PRODUCTS = 50
N_WAREHOUSES = 6
N_PERIODS = 8

products = [f"P{i:04d}" for i in range(1, N_PRODUCTS + 1)]
warehouses = [f"WH{j:02d}" for j in range(1, N_WAREHOUSES + 1)]
periods = list(range(1, N_PERIODS + 1))

# ── product.csv
with open(os.path.join(OUT_DIR, "product.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["product_id", "item_class", "product_series", "product_style",
                "product_size", "created_at", "updated_at", "product_name"])
    for p in products:
        w.writerow([p, "CLS-A", "SER-001", "STY-001", "SZ-001",
                    "2024-01-01 00:00:00", "2024-01-01 00:00:00", f"Product-{p}"])

# ── warehouse.csv
with open(os.path.join(OUT_DIR, "warehouse.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["warehouse_id", "market_code", "warehouse_name", "country_code",
                "created_at", "updated_at"])
    for wh in warehouses:
        w.writerow([wh, f"REG-{wh[-1]}", f"Distribution Center {wh}", "XX",
                    "2024-01-01 00:00:00", "2024-01-01 00:00:00"])

# ── time_period.csv
with open(os.path.join(OUT_DIR, "time_period.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["time_period", "start_date", "end_date", "week", "month", "year", "created_at"])
    for t in periods:
        w.writerow([t, f"2024-01-{(t-1)*7+1:02d}", f"2024-01-{t*7:02d}",
                    t, 1, 2024, "2024-01-01 00:00:00"])

# ── inventory_begin.csv
with open(os.path.join(OUT_DIR, "inventory_begin.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["product_id", "warehouse_id", "beginning_inventory", "effective_date", "created_at"])
    for p in products:
        for wh in warehouses:
            bi = random.randint(0, 15)
            w.writerow([p, wh, bi, "2024-01-01", "2024-01-01 00:00:00"])

# ── inventory_flow.csv
with open(os.path.join(OUT_DIR, "inventory_flow.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["product_id", "warehouse_id", "time_period",
                "inventory_fluctuation", "inventory_ceiling", "inventory_floor", "created_at"])
    for p in products:
        for wh in warehouses:
            for t in periods:
                di = -random.randint(3, 25)
                ceiling = random.randint(40, 80)
                floor = random.randint(10, 30)
                w.writerow([p, wh, t, di, ceiling, floor, "2024-01-01 00:00:00"])

# ── unit_cost.csv (varied costs to make optimization non-trivial)
with open(os.path.join(OUT_DIR, "unit_cost.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["product_id", "warehouse_id", "time_period",
                "overstock_cost", "shortage_cost", "backlog_cost", "penalty_cost", "created_at"])
    for p in products:
        for wh in warehouses:
            for t in periods:
                oc = round(random.uniform(0.5, 5.0), 2)
                sc = round(random.uniform(5.0, 50.0), 2)
                bc = random.randint(500, 5000)
                pc = random.randint(100, 2000)
                w.writerow([p, wh, t, oc, sc, bc, pc, "2024-01-01 00:00:00"])

# ── vendor_capacity.csv
with open(os.path.join(OUT_DIR, "vendor_capacity.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["product_id", "time_period", "capacity", "created_at"])
    for p in products:
        for t in periods:
            cap = random.randint(20, 60)
            w.writerow([p, t, cap, "2024-01-01 00:00:00"])

# ── packing_details.csv (1 row per product)
with open(os.path.join(OUT_DIR, "packing_details.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["product_id", "box_id", "pack_multiple", "created_at"])
    for i, p in enumerate(products, 1):
        cp = random.choice([2, 4, 6, 8])
        w.writerow([p, "BOX-01", cp, "2024-01-01 00:00:00"])

# ── box_shipment.csv (all products active in all warehouses)
with open(os.path.join(OUT_DIR, "box_shipment.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["packing_details_id", "warehouse_id", "is_active", "created_at", "updated_at"])
    for i, p in enumerate(products, 1):
        for wh in warehouses:
            w.writerow([i, wh, "True", "2024-01-01 00:00:00", "2024-01-01 00:00:00"])

# ── box.csv
with open(os.path.join(OUT_DIR, "box.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["box_id", "box_name", "length", "width", "height", "weight", "created_at", "updated_at"])
    w.writerow(["BOX-01", "BOX-01", "40.00", "30.00", "25.00", "6.00",
                "2024-01-01 00:00:00", "2024-01-01 00:00:00"])

print(f"Generated {N_PRODUCTS} products × {N_WAREHOUSES} warehouses × {N_PERIODS} periods")
print(f"Total cells: {N_PRODUCTS * N_WAREHOUSES * N_PERIODS}")
print(f"Files written to: {OUT_DIR}")
