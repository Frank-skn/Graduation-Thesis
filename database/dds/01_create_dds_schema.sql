-- =============================================
-- DDS (Dimensional Data Store) Schema - PostgreSQL
-- Star schema optimized for OLAP and optimization
-- =============================================

SET search_path TO dds, public;

-- =============================================
-- DIMENSION TABLES
-- =============================================

-- Product Dimension
CREATE TABLE IF NOT EXISTS dds.dim_product (
    product_sk INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL,
    item_class VARCHAR(50),
    product_series VARCHAR(50),
    product_style VARCHAR(50),
    product_size VARCHAR(50),
    pack_kind VARCHAR(50),
    effective_date DATE NOT NULL,
    expiry_date DATE,
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dim_product_id ON dds.dim_product(product_id);
CREATE INDEX IF NOT EXISTS idx_dim_product_current ON dds.dim_product(is_current);

-- Warehouse Dimension
CREATE TABLE IF NOT EXISTS dds.dim_warehouse (
    warehouse_sk INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    warehouse_id VARCHAR(50) NOT NULL,
    market_code VARCHAR(50),
    effective_date DATE NOT NULL,
    expiry_date DATE,
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dim_warehouse_id ON dds.dim_warehouse(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_dim_warehouse_current ON dds.dim_warehouse(is_current);

-- Time Dimension
CREATE TABLE IF NOT EXISTS dds.dim_time (
    time_period_sk INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    time_period INT NOT NULL UNIQUE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    week INT,
    month INT,
    year INT,
    quarter INT,
    is_current BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dim_time_period ON dds.dim_time(time_period);
CREATE INDEX IF NOT EXISTS idx_dim_time_date ON dds.dim_time(start_date, end_date);

-- =============================================
-- FACT TABLE
-- =============================================

-- Main Inventory Fact Table
CREATE TABLE IF NOT EXISTS dds.fact_inventory_smi (
    fact_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Foreign Keys (Surrogate)
    product_sk INT NOT NULL,
    warehouse_sk INT NOT NULL,
    time_period_sk INT NOT NULL,

    -- Inventory Measures
    beginning_inventory_qty INT NOT NULL,           -- BI(i,j)
    delta_inventory_qty INT NOT NULL,               -- delta_I(i,j,t)
    net_inventory_qty DECIMAL(18,2),                -- I(i,j,t) - calculated

    -- Capacity & Packing
    firm_capacity_qty INT NOT NULL,                 -- CAP(i,t)
    q_case_pack INT DEFAULT 0,                      -- q(i,j,t) - decision variable
    r_residual_units INT DEFAULT 0,                 -- r(i,j,t) - decision variable

    -- Deviation Measures
    backorder_qty DECIMAL(18,2) DEFAULT 0,          -- bo(i,j,t)
    overstock_qty DECIMAL(18,2) DEFAULT 0,          -- o(i,j,t)
    shortage_qty DECIMAL(18,2) DEFAULT 0,           -- s(i,j,t)

    -- Policy Flags
    penalty_flag BOOLEAN DEFAULT FALSE,             -- p(i,j,t)

    -- Packing Info
    applied_box_code INT,
    applied_pack_multiple INT,                      -- CP value used

    -- Bounds
    inventory_ceiling INT NOT NULL,                 -- U(i,j,t)
    inventory_floor INT NOT NULL,                   -- L(i,j,t)

    -- Costs
    cost_backorder DECIMAL(10,2),                   -- Cb(i,j,t)
    cost_overstock DECIMAL(10,2),                   -- Co(i,j,t)
    cost_shortage DECIMAL(10,2),                    -- Cs(i,j,t)
    cost_penalty DECIMAL(10,2),                     -- Cp(i,j,t)

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign Key Constraints
    CONSTRAINT fk_fact_product FOREIGN KEY (product_sk) REFERENCES dds.dim_product(product_sk),
    CONSTRAINT fk_fact_warehouse FOREIGN KEY (warehouse_sk) REFERENCES dds.dim_warehouse(warehouse_sk),
    CONSTRAINT fk_fact_time FOREIGN KEY (time_period_sk) REFERENCES dds.dim_time(time_period_sk)
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_fact_product ON dds.fact_inventory_smi(product_sk);
CREATE INDEX IF NOT EXISTS idx_fact_warehouse ON dds.fact_inventory_smi(warehouse_sk);
CREATE INDEX IF NOT EXISTS idx_fact_time ON dds.fact_inventory_smi(time_period_sk);
CREATE INDEX IF NOT EXISTS idx_fact_composite ON dds.fact_inventory_smi(product_sk, warehouse_sk, time_period_sk);
CREATE INDEX IF NOT EXISTS idx_fact_created ON dds.fact_inventory_smi(created_at);

-- =============================================
-- SUPPORTING TABLES
-- =============================================

-- Packing Configuration (denormalized for performance)
CREATE TABLE IF NOT EXISTS dds.dds_packing_config (
    config_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_sk INT NOT NULL,
    warehouse_sk INT NOT NULL,
    box_id INT NOT NULL,
    pack_multiple INT NOT NULL,     -- CP(i,j)
    box_volume DECIMAL(10,2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_packing_product_sk FOREIGN KEY (product_sk) REFERENCES dds.dim_product(product_sk),
    CONSTRAINT fk_packing_warehouse_sk FOREIGN KEY (warehouse_sk) REFERENCES dds.dim_warehouse(warehouse_sk)
);

CREATE INDEX IF NOT EXISTS idx_packing_lookup ON dds.dds_packing_config(product_sk, warehouse_sk);

-- Model Parameters (for easy reference)
CREATE TABLE IF NOT EXISTS dds.dds_model_parameters (
    param_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    param_name VARCHAR(50) NOT NULL UNIQUE,
    param_value DECIMAL(18,6),
    param_description VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- High Value constant (HV in the model)
INSERT INTO dds.dds_model_parameters (param_name, param_value, param_description)
VALUES ('HV', 9999, 'High value constant for linearization constraints')
ON CONFLICT (param_name) DO NOTHING;

-- =============================================
-- VIEWS FOR OPTIMIZATION INPUT
-- =============================================

-- View: Get all products for optimization (I set)
CREATE OR REPLACE VIEW dds.vw_opt_products AS
SELECT DISTINCT
    p.product_sk,
    p.product_id,
    p.item_class,
    p.product_series
FROM dds.dim_product p
WHERE p.is_current = TRUE;

-- View: Get all warehouses for optimization (J set)
CREATE OR REPLACE VIEW dds.vw_opt_warehouses AS
SELECT DISTINCT
    w.warehouse_sk,
    w.warehouse_id,
    w.market_code
FROM dds.dim_warehouse w
WHERE w.is_current = TRUE;

-- View: Get all time periods for optimization (T set)
CREATE OR REPLACE VIEW dds.vw_opt_time_periods AS
SELECT
    t.time_period_sk,
    t.time_period,
    t.start_date,
    t.end_date
FROM dds.dim_time t;

-- View: Complete fact data with dimension details
CREATE OR REPLACE VIEW dds.vw_fact_complete AS
SELECT
    f.fact_id,
    p.product_id,
    p.product_sk,
    w.warehouse_id,
    w.warehouse_sk,
    t.time_period,
    t.time_period_sk,
    f.beginning_inventory_qty,
    f.delta_inventory_qty,
    f.net_inventory_qty,
    f.firm_capacity_qty,
    f.q_case_pack,
    f.r_residual_units,
    f.backorder_qty,
    f.overstock_qty,
    f.shortage_qty,
    f.penalty_flag,
    f.inventory_ceiling,
    f.inventory_floor,
    f.cost_backorder,
    f.cost_overstock,
    f.cost_shortage,
    f.cost_penalty
FROM dds.fact_inventory_smi f
INNER JOIN dds.dim_product p ON f.product_sk = p.product_sk
INNER JOIN dds.dim_warehouse w ON f.warehouse_sk = w.warehouse_sk
INNER JOIN dds.dim_time t ON f.time_period_sk = t.time_period_sk;

-- =============================================
-- DATA QUALITY CONSTRAINTS
-- =============================================

-- Ensure no duplicate fact records
CREATE UNIQUE INDEX IF NOT EXISTS idx_fact_unique
ON dds.fact_inventory_smi(product_sk, warehouse_sk, time_period_sk);

-- Check constraints
ALTER TABLE dds.fact_inventory_smi
ADD CONSTRAINT chk_fact_capacity CHECK (firm_capacity_qty >= 0);

ALTER TABLE dds.fact_inventory_smi
ADD CONSTRAINT chk_fact_ceiling CHECK (inventory_ceiling >= inventory_floor);
