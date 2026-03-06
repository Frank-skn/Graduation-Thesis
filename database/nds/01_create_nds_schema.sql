-- =============================================
-- NDS (Normalized Data Store) Schema - PostgreSQL
-- Stores operational data with full history
-- =============================================

SET search_path TO nds, public;

-- =============================================
-- CORE MASTER DATA
-- =============================================

-- Product Master
CREATE TABLE IF NOT EXISTS nds.product (
    product_id VARCHAR(50) PRIMARY KEY,
    item_class VARCHAR(50),
    product_series VARCHAR(50),
    product_style VARCHAR(50),
    product_size VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_product_class ON nds.product(item_class);
CREATE INDEX IF NOT EXISTS idx_product_series ON nds.product(product_series);

-- Warehouse Master
CREATE TABLE IF NOT EXISTS nds.warehouse (
    warehouse_id VARCHAR(50) PRIMARY KEY,
    market_code VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_warehouse_market ON nds.warehouse(market_code);

-- Time Period Master
CREATE TABLE IF NOT EXISTS nds.time_period (
    time_period INT PRIMARY KEY,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    week INT,
    month INT,
    year INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_time_period_date ON nds.time_period(start_date, end_date);

-- Box Master (for packaging)
CREATE TABLE IF NOT EXISTS nds.box (
    box_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    length DECIMAL(10,2),
    width DECIMAL(10,2),
    height DECIMAL(10,2),
    weight DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- LOGISTICS
-- =============================================

-- Packing Details (Product-Box relationship)
CREATE TABLE IF NOT EXISTS nds.packing_details (
    packing_details_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL,
    box_id INT NOT NULL,
    pack_multiple INT NOT NULL, -- CP in the model
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_packing_product FOREIGN KEY (product_id) REFERENCES nds.product(product_id),
    CONSTRAINT fk_packing_box FOREIGN KEY (box_id) REFERENCES nds.box(box_id),
    CONSTRAINT uq_product_box UNIQUE (product_id, box_id)
);

CREATE INDEX IF NOT EXISTS idx_packing_product ON nds.packing_details(product_id);

-- Box Shipment (Which boxes go to which warehouses)
CREATE TABLE IF NOT EXISTS nds.box_shipment (
    shipment_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    packing_details_id INT NOT NULL,
    warehouse_id VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_shipment_packing FOREIGN KEY (packing_details_id) REFERENCES nds.packing_details(packing_details_id),
    CONSTRAINT fk_shipment_warehouse FOREIGN KEY (warehouse_id) REFERENCES nds.warehouse(warehouse_id)
);

CREATE INDEX IF NOT EXISTS idx_shipment_warehouse ON nds.box_shipment(warehouse_id);

-- =============================================
-- INVENTORY
-- =============================================

-- Beginning Inventory (BI in the model)
CREATE TABLE IF NOT EXISTS nds.inventory_begin (
    inventory_begin_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL,
    warehouse_id VARCHAR(50) NOT NULL,
    beginning_inventory INT NOT NULL,
    effective_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_inv_begin_product FOREIGN KEY (product_id) REFERENCES nds.product(product_id),
    CONSTRAINT fk_inv_begin_warehouse FOREIGN KEY (warehouse_id) REFERENCES nds.warehouse(warehouse_id),
    CONSTRAINT uq_inv_begin UNIQUE (product_id, warehouse_id, effective_date)
);

CREATE INDEX IF NOT EXISTS idx_inv_begin_lookup ON nds.inventory_begin(product_id, warehouse_id);

-- Inventory Flow (delta_I, U, L in the model)
CREATE TABLE IF NOT EXISTS nds.inventory_flow (
    inventory_flow_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL,
    warehouse_id VARCHAR(50) NOT NULL,
    time_period INT NOT NULL,
    inventory_fluctuation INT NOT NULL, -- delta_I (delta inventory)
    inventory_ceiling INT NOT NULL,     -- U (upper bound)
    inventory_floor INT NOT NULL,       -- L (lower bound)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_inv_flow_product FOREIGN KEY (product_id) REFERENCES nds.product(product_id),
    CONSTRAINT fk_inv_flow_warehouse FOREIGN KEY (warehouse_id) REFERENCES nds.warehouse(warehouse_id),
    CONSTRAINT fk_inv_flow_time FOREIGN KEY (time_period) REFERENCES nds.time_period(time_period),
    CONSTRAINT uq_inv_flow UNIQUE (product_id, warehouse_id, time_period)
);

CREATE INDEX IF NOT EXISTS idx_inv_flow_lookup ON nds.inventory_flow(product_id, warehouse_id, time_period);

-- =============================================
-- COST & CAPACITY
-- =============================================

-- Unit Costs (Cb, Co, Cs, Cp in the model)
CREATE TABLE IF NOT EXISTS nds.unit_cost (
    cost_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL,
    warehouse_id VARCHAR(50) NOT NULL,
    time_period INT NOT NULL,
    overstock_cost DECIMAL(10,2) NOT NULL,  -- Co
    shortage_cost DECIMAL(10,2) NOT NULL,   -- Cs
    backlog_cost DECIMAL(10,2) NOT NULL,    -- Cb
    penalty_cost DECIMAL(10,2) NOT NULL,    -- Cp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cost_product FOREIGN KEY (product_id) REFERENCES nds.product(product_id),
    CONSTRAINT fk_cost_warehouse FOREIGN KEY (warehouse_id) REFERENCES nds.warehouse(warehouse_id),
    CONSTRAINT fk_cost_time FOREIGN KEY (time_period) REFERENCES nds.time_period(time_period),
    CONSTRAINT uq_cost UNIQUE (product_id, warehouse_id, time_period)
);

CREATE INDEX IF NOT EXISTS idx_cost_lookup ON nds.unit_cost(product_id, warehouse_id, time_period);

-- Vendor Capacity (CAP in the model)
CREATE TABLE IF NOT EXISTS nds.vendor_capacity (
    capacity_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL,
    time_period INT NOT NULL,
    capacity INT NOT NULL, -- CAP(i,t)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_capacity_product FOREIGN KEY (product_id) REFERENCES nds.product(product_id),
    CONSTRAINT fk_capacity_time FOREIGN KEY (time_period) REFERENCES nds.time_period(time_period),
    CONSTRAINT uq_capacity UNIQUE (product_id, time_period)
);

CREATE INDEX IF NOT EXISTS idx_capacity_lookup ON nds.vendor_capacity(product_id, time_period);

-- =============================================
-- DSS CORE
-- =============================================

-- Scenario Management
CREATE TABLE IF NOT EXISTS nds.scenario (
    scenario_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scenario_name VARCHAR(200) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    is_baseline BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_scenario_name ON nds.scenario(scenario_name);

-- Optimization Run History
CREATE TABLE IF NOT EXISTS nds.optimization_run (
    run_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scenario_id INT NOT NULL,
    run_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    solver_status VARCHAR(50),
    solve_time_seconds DECIMAL(10,2),
    objective_value DECIMAL(18,2),
    mip_gap DECIMAL(10,6),
    CONSTRAINT fk_run_scenario FOREIGN KEY (scenario_id) REFERENCES nds.scenario(scenario_id)
);

CREATE INDEX IF NOT EXISTS idx_run_scenario ON nds.optimization_run(scenario_id);

-- Optimization Results
CREATE TABLE IF NOT EXISTS nds.optimization_result (
    result_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id INT NOT NULL,
    product_id VARCHAR(50) NOT NULL,
    warehouse_id VARCHAR(50) NOT NULL,
    box_id INT NOT NULL,
    time_period INT NOT NULL,
    q_case_pack INT NOT NULL,           -- Decision variable q
    r_residual_units INT NOT NULL,      -- Decision variable r
    net_inventory DECIMAL(18,2),        -- I_inv
    backorder_qty DECIMAL(18,2),        -- bo
    overstock_qty DECIMAL(18,2),        -- o
    shortage_qty DECIMAL(18,2),         -- s
    penalty_flag BOOLEAN,               -- p
    CONSTRAINT fk_result_run FOREIGN KEY (run_id) REFERENCES nds.optimization_run(run_id),
    CONSTRAINT fk_result_product FOREIGN KEY (product_id) REFERENCES nds.product(product_id),
    CONSTRAINT fk_result_warehouse FOREIGN KEY (warehouse_id) REFERENCES nds.warehouse(warehouse_id),
    CONSTRAINT fk_result_box FOREIGN KEY (box_id) REFERENCES nds.box(box_id),
    CONSTRAINT fk_result_time FOREIGN KEY (time_period) REFERENCES nds.time_period(time_period)
);

CREATE INDEX IF NOT EXISTS idx_result_run ON nds.optimization_result(run_id);
CREATE INDEX IF NOT EXISTS idx_result_lookup ON nds.optimization_result(product_id, warehouse_id, time_period);

-- KPIs Summary
CREATE TABLE IF NOT EXISTS nds.dss_kpi (
    kpi_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id INT NOT NULL UNIQUE,
    total_cost DECIMAL(18,2),
    total_backorder DECIMAL(18,2),
    total_overstock DECIMAL(18,2),
    total_shortage DECIMAL(18,2),
    total_penalty DECIMAL(18,2),
    service_level DECIMAL(5,2),          -- Percentage
    capacity_utilization DECIMAL(5,2),   -- Percentage
    CONSTRAINT fk_kpi_run FOREIGN KEY (run_id) REFERENCES nds.optimization_run(run_id)
);

-- =============================================
-- DSS EXTENDED (What-If, Sensitivity, Dataset)
-- =============================================

-- What-If Scenario
CREATE TABLE IF NOT EXISTS nds.what_if_scenario (
    whatif_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scenario_id INT NOT NULL,
    whatif_type VARCHAR(50) NOT NULL,     -- demand_surge, capacity_disruption, etc.
    parameter_overrides TEXT,             -- JSON of parameter changes
    status VARCHAR(20) DEFAULT 'pending', -- pending, running, completed, failed
    run_id INT,                          -- link to optimization_run after execution
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_whatif_scenario FOREIGN KEY (scenario_id) REFERENCES nds.scenario(scenario_id),
    CONSTRAINT fk_whatif_run FOREIGN KEY (run_id) REFERENCES nds.optimization_run(run_id)
);

CREATE INDEX IF NOT EXISTS idx_whatif_scenario ON nds.what_if_scenario(scenario_id);
CREATE INDEX IF NOT EXISTS idx_whatif_type ON nds.what_if_scenario(whatif_type);

-- Sensitivity Run
CREATE TABLE IF NOT EXISTS nds.sensitivity_run (
    sensitivity_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    base_run_id INT NOT NULL,
    parameter_name VARCHAR(50) NOT NULL,  -- CAP, DI, Cb, Co, Cs, Cp, U_L
    variation_points TEXT,                -- JSON array of % variations
    results TEXT,                         -- JSON of results per variation point
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sensitivity_run FOREIGN KEY (base_run_id) REFERENCES nds.optimization_run(run_id)
);

CREATE INDEX IF NOT EXISTS idx_sensitivity_base ON nds.sensitivity_run(base_run_id);

-- Dataset Version
CREATE TABLE IF NOT EXISTS nds.dataset_version (
    version_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    version_name VARCHAR(200) NOT NULL,
    description TEXT,
    snapshot_data TEXT,                   -- JSON snapshot of parameters
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- =============================================
-- AUDIT TRAIL
-- =============================================

CREATE TABLE IF NOT EXISTS nds.audit_log (
    log_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_name VARCHAR(100),
    operation VARCHAR(20),
    record_id VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_table ON nds.audit_log(table_name, changed_at);
