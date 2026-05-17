import os
import csv
from collections import defaultdict

def load_csv(filepath):
    lines = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            lines.append(row)
    return lines

def parse_all_data(data_dir):
    # 1. Load all CSVs
    products = load_csv(os.path.join(data_dir, 'product.csv'))
    fgps = load_csv(os.path.join(data_dir, 'FGPs.csv'))
    inv_begin = load_csv(os.path.join(data_dir, 'inventory_begin.csv'))
    inv_flow = load_csv(os.path.join(data_dir, 'inventory_flow.csv'))
    vendor_cap = load_csv(os.path.join(data_dir, 'vendor_capacity.csv'))
    plt_lead = load_csv(os.path.join(data_dir, 'plt_lead_time.csv'))
    unit_cost = load_csv(os.path.join(data_dir, 'unit_cost.csv'))
    fgps_dist = load_csv(os.path.join(data_dir, 'FGPs_distance.csv'))

    # Warehouses
    wh_map = {}
    for row in fgps:
        wid = row['warehouse_id']
        name = row['warehouse_name']
        wh_code = name.split()[-1] if 'WH' in name else f"WH{wid.zfill(2)}"
        wh_code = wh_code.strip()
        wh_map[wid] = wh_code
    warehouses = sorted(list(wh_map.values()))

    # T (max time period)
    T = max(int(row['time_period']) for row in vendor_cap)
    
    # Distance
    distance = {}
    states = [k for k in fgps_dist[0].keys() if k != 'State']
    for i, row in enumerate(fgps_dist):
        s1 = row['State']
        for j, s2 in enumerate(states):
            if i == j: continue
            dist = int(row[s2])
            w1 = wh_map.get(str(i+1), f"WH{str(i+1).zfill(2)}")
            w2 = wh_map.get(str(j+1), f"WH{str(j+1).zfill(2)}")
            distance[f"{w1}_{w2}"] = dist

    # PLT lead time
    PLT_lead = {}
    for row in plt_lead:
        w1 = wh_map.get(row['from_warehouse_id'], f"WH{row['from_warehouse_id'].zfill(2)}")
        w2 = wh_map.get(row['to_warehouse_id'], f"WH{row['to_warehouse_id'].zfill(2)}")
        PLT_lead[f"{w1}_{w2}"] = int(row['lead_time_weeks'])

    # Group by product
    prod_data = defaultdict(lambda: {
        "BI": {}, "delta_I": {}, "U": {}, "L": {}, "CAP": {}, "cost": defaultdict(dict)
    })
    
    for row in inv_begin:
        wh = row['warehouse_id']
        prod_data[row['product_id']]['BI'][wh] = int(float(row['beginning_inventory']))

    for row in inv_flow:
        wh = row['warehouse_id']
        t = row['time_period']
        key = f"{wh}_{t}"
        pid = row['product_id']
        prod_data[pid]['delta_I'][key] = int(float(row['inventory_fluctuation']))
        prod_data[pid]['U'][key] = int(float(row['inventory_ceiling']))
        prod_data[pid]['L'][key] = int(float(row['inventory_floor']))

    for row in vendor_cap:
        t = row['time_period']
        prod_data[row['product_id']]['CAP'][t] = int(float(row['capacity']))
        
    for row in unit_cost:
        wh = row['warehouse_id']
        t = row['time_period']
        pid = row['product_id']
        prod_data[pid]['cost'][wh][t] = {
            "overstock": float(row['overstock_cost']),
            "shortage": float(row['shortage_cost']),
            "backorder": float(row['backlog_cost']),
            "penalty": float(row['penalty_cost'])
        }

    cases = []
    for prod in products:
        pid = prod['product_id']
        data = prod_data[pid]
        
        # fix cost dict format
        cost_dict = {}
        for wh in warehouses:
            if wh in data['cost']:
                cost_dict[wh] = data['cost'][wh]
            else:
                # default cost if missing
                cost_dict[wh] = {str(t): {"overstock":1, "shortage":3, "backorder":5, "penalty":2} for t in range(1, T+1)}
                
        # ensure BI has all WHs
        BI = {wh: data['BI'].get(wh, 0) for wh in warehouses}
        
        params = {
            "meta": {
                "product": pid,
                "warehouses": warehouses,
                "T": T
            },
            "BI": BI,
            "delta_I": data['delta_I'],
            "U": data['U'],
            "L": data['L'],
            "CAP": data['CAP'],
            "distance": distance,
            "PLT_lead": PLT_lead,
            "CP": 12,
            "TC": 0.05,
            "M": 1000,
            "cost": cost_dict
        }
        cases.append((pid, params))
        
    return cases
