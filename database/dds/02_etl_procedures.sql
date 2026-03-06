-- =============================================
-- ETL Process: NDS to DDS - PostgreSQL
-- Transforms normalized operational data to star schema
-- Uses schemas within single database SMI_DSS
-- =============================================

SET search_path TO dds, nds, public;

-- =============================================
-- HELPER: Load Dimension Tables
-- =============================================

-- Load Product Dimension
CREATE OR REPLACE FUNCTION dds.sp_load_dim_product()
RETURNS VOID AS $$
BEGIN
    INSERT INTO dds.dim_product (product_id, item_class, product_series, product_style, product_size, pack_kind, effective_date, is_current)
    SELECT DISTINCT
        p.product_id,
        p.item_class,
        p.product_series,
        p.product_style,
        p.product_size,
        'STANDARD',
        CURRENT_DATE,
        TRUE
    FROM nds.product p
    ON CONFLICT DO NOTHING;

    -- Update existing records
    UPDATE dds.dim_product dp
    SET
        item_class = p.item_class,
        product_series = p.product_series,
        product_style = p.product_style,
        product_size = p.product_size
    FROM nds.product p
    WHERE dp.product_id = p.product_id
      AND dp.is_current = TRUE;

    RAISE NOTICE 'Product dimension loaded';
END;
$$ LANGUAGE plpgsql;

-- Load Warehouse Dimension
CREATE OR REPLACE FUNCTION dds.sp_load_dim_warehouse()
RETURNS VOID AS $$
BEGIN
    INSERT INTO dds.dim_warehouse (warehouse_id, market_code, effective_date, is_current)
    SELECT DISTINCT
        w.warehouse_id,
        w.market_code,
        CURRENT_DATE,
        TRUE
    FROM nds.warehouse w
    ON CONFLICT DO NOTHING;

    UPDATE dds.dim_warehouse dw
    SET market_code = w.market_code
    FROM nds.warehouse w
    WHERE dw.warehouse_id = w.warehouse_id
      AND dw.is_current = TRUE;

    RAISE NOTICE 'Warehouse dimension loaded';
END;
$$ LANGUAGE plpgsql;

-- Load Time Dimension
CREATE OR REPLACE FUNCTION dds.sp_load_dim_time()
RETURNS VOID AS $$
BEGIN
    INSERT INTO dds.dim_time (time_period, start_date, end_date, week, month, year, quarter)
    SELECT DISTINCT
        t.time_period,
        t.start_date,
        t.end_date,
        t.week,
        t.month,
        t.year,
        CEIL(t.month / 3.0)::INT
    FROM nds.time_period t
    ON CONFLICT (time_period) DO UPDATE SET
        start_date = EXCLUDED.start_date,
        end_date = EXCLUDED.end_date,
        week = EXCLUDED.week,
        month = EXCLUDED.month,
        year = EXCLUDED.year,
        quarter = EXCLUDED.quarter;

    RAISE NOTICE 'Time dimension loaded';
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- MAIN ETL: Load Fact Table
-- =============================================

CREATE OR REPLACE FUNCTION dds.sp_load_fact_inventory_smi()
RETURNS VOID AS $$
DECLARE
    row_count INT;
BEGIN
    -- Clear existing fact data (full refresh strategy)
    TRUNCATE TABLE dds.fact_inventory_smi CASCADE;

    -- Insert fact records
    INSERT INTO dds.fact_inventory_smi (
        product_sk,
        warehouse_sk,
        time_period_sk,
        beginning_inventory_qty,
        delta_inventory_qty,
        firm_capacity_qty,
        inventory_ceiling,
        inventory_floor,
        cost_backorder,
        cost_overstock,
        cost_shortage,
        cost_penalty,
        net_inventory_qty
    )
    SELECT
        dp.product_sk,
        dw.warehouse_sk,
        dt.time_period_sk,

        -- Beginning Inventory (BI)
        COALESCE(ib.beginning_inventory, 0),

        -- Delta Inventory
        COALESCE(inf.inventory_fluctuation, 0),

        -- Capacity (CAP) - per product per time
        COALESCE(vc.capacity, 0),

        -- Bounds (U, L)
        COALESCE(inf.inventory_ceiling, 0),
        COALESCE(inf.inventory_floor, 0),

        -- Costs (Cb, Co, Cs, Cp)
        COALESCE(uc.backlog_cost, 0),
        COALESCE(uc.overstock_cost, 0),
        COALESCE(uc.shortage_cost, 0),
        COALESCE(uc.penalty_cost, 0),

        -- Initialize net inventory with BI + delta_I
        COALESCE(ib.beginning_inventory, 0) + COALESCE(inf.inventory_fluctuation, 0)

    FROM nds.product p
    CROSS JOIN nds.warehouse w
    CROSS JOIN nds.time_period t

    -- Join to dimensions
    INNER JOIN dds.dim_product dp ON p.product_id = dp.product_id AND dp.is_current = TRUE
    INNER JOIN dds.dim_warehouse dw ON w.warehouse_id = dw.warehouse_id AND dw.is_current = TRUE
    INNER JOIN dds.dim_time dt ON t.time_period = dt.time_period

    -- Join to fact sources
    LEFT JOIN nds.inventory_begin ib
        ON p.product_id = ib.product_id
        AND w.warehouse_id = ib.warehouse_id
        AND ib.effective_date = (
            SELECT MAX(effective_date)
            FROM nds.inventory_begin
            WHERE product_id = p.product_id
            AND warehouse_id = w.warehouse_id
        )

    LEFT JOIN nds.inventory_flow inf
        ON p.product_id = inf.product_id
        AND w.warehouse_id = inf.warehouse_id
        AND t.time_period = inf.time_period

    LEFT JOIN nds.unit_cost uc
        ON p.product_id = uc.product_id
        AND w.warehouse_id = uc.warehouse_id
        AND t.time_period = uc.time_period

    LEFT JOIN nds.vendor_capacity vc
        ON p.product_id = vc.product_id
        AND t.time_period = vc.time_period;

    GET DIAGNOSTICS row_count = ROW_COUNT;
    RAISE NOTICE 'Fact table loaded: % records', row_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- Load Packing Configuration
-- =============================================

CREATE OR REPLACE FUNCTION dds.sp_load_packing_config()
RETURNS VOID AS $$
DECLARE
    row_count INT;
BEGIN
    TRUNCATE TABLE dds.dds_packing_config CASCADE;

    INSERT INTO dds.dds_packing_config (
        product_sk,
        warehouse_sk,
        box_id,
        pack_multiple,
        box_volume,
        is_active
    )
    SELECT
        dp.product_sk,
        dw.warehouse_sk,
        pd.box_id,
        pd.pack_multiple,
        (b.length * b.width * b.height),
        bs.is_active
    FROM nds.packing_details pd
    INNER JOIN nds.box_shipment bs ON pd.packing_details_id = bs.packing_details_id
    INNER JOIN nds.box b ON pd.box_id = b.box_id
    INNER JOIN dds.dim_product dp ON pd.product_id = dp.product_id AND dp.is_current = TRUE
    INNER JOIN dds.dim_warehouse dw ON bs.warehouse_id = dw.warehouse_id AND dw.is_current = TRUE
    WHERE bs.is_active = TRUE;

    GET DIAGNOSTICS row_count = ROW_COUNT;
    RAISE NOTICE 'Packing config loaded: % records', row_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- MASTER ETL ORCHESTRATOR
-- =============================================

CREATE OR REPLACE FUNCTION dds.sp_run_full_etl()
RETURNS VOID AS $$
BEGIN
    RAISE NOTICE 'Starting ETL process...';
    RAISE NOTICE '=============================================';

    -- Step 1: Load Dimensions
    RAISE NOTICE 'Step 1: Loading Product Dimension...';
    PERFORM dds.sp_load_dim_product();

    RAISE NOTICE 'Step 2: Loading Warehouse Dimension...';
    PERFORM dds.sp_load_dim_warehouse();

    RAISE NOTICE 'Step 3: Loading Time Dimension...';
    PERFORM dds.sp_load_dim_time();

    -- Step 2: Load Facts
    RAISE NOTICE 'Step 4: Loading Fact Table...';
    PERFORM dds.sp_load_fact_inventory_smi();

    -- Step 3: Load Supporting Tables
    RAISE NOTICE 'Step 5: Loading Packing Configuration...';
    PERFORM dds.sp_load_packing_config();

    RAISE NOTICE '=============================================';
    RAISE NOTICE 'ETL process completed successfully.';

EXCEPTION WHEN OTHERS THEN
    RAISE EXCEPTION 'ETL FAILED: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- USAGE
-- =============================================
-- Execute full ETL:
-- SELECT dds.sp_run_full_etl();
