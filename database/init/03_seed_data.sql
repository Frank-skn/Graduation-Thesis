-- =============================================
-- Seed Data for SS-MB-SMI DSS Testing
-- Run after schema creation, inside database SMI_DSS
-- =============================================

SET search_path TO nds, public;

-- =============================================
-- CORE MASTER DATA
-- =============================================

-- 5 Products (Items)
INSERT INTO nds.product (product_id, item_class, product_series, product_style, product_size) VALUES
('ITEM001', 'CLASS_A', 'SERIES_1', 'STYLE_X', 'SMALL'),
('ITEM002', 'CLASS_A', 'SERIES_1', 'STYLE_Y', 'MEDIUM'),
('ITEM003', 'CLASS_B', 'SERIES_2', 'STYLE_X', 'LARGE'),
('ITEM004', 'CLASS_B', 'SERIES_2', 'STYLE_Z', 'SMALL'),
('ITEM005', 'CLASS_C', 'SERIES_3', 'STYLE_Y', 'MEDIUM')
ON CONFLICT (product_id) DO NOTHING;

-- 3 Warehouses (Finished-Goods Plants / FGPs)
INSERT INTO nds.warehouse (warehouse_id, market_code) VALUES
('FGP01', 'NORTH'),
('FGP02', 'SOUTH'),
('FGP03', 'CENTRAL')
ON CONFLICT (warehouse_id) DO NOTHING;

-- 6 Time Periods (weekly)
INSERT INTO nds.time_period (time_period, start_date, end_date, week, month, year) VALUES
(1, '2026-01-05', '2026-01-11', 1, 1, 2026),
(2, '2026-01-12', '2026-01-18', 2, 1, 2026),
(3, '2026-01-19', '2026-01-25', 3, 1, 2026),
(4, '2026-01-26', '2026-02-01', 4, 1, 2026),
(5, '2026-02-02', '2026-02-08', 5, 2, 2026),
(6, '2026-02-09', '2026-02-15', 6, 2, 2026)
ON CONFLICT (time_period) DO NOTHING;

-- 3 Box definitions
INSERT INTO nds.box (length, width, height, weight) VALUES
(40.0, 30.0, 25.0, 2.5),
(50.0, 35.0, 30.0, 3.0),
(60.0, 40.0, 35.0, 4.0);

-- =============================================
-- LOGISTICS (Packing Details & Box Shipments)
-- =============================================

-- Packing details: which product goes in which box, case-pack multiple = CP(i,j)
INSERT INTO nds.packing_details (product_id, box_id, pack_multiple) VALUES
('ITEM001', 1, 20),
('ITEM002', 1, 25),
('ITEM003', 2, 15),
('ITEM004', 2, 30),
('ITEM005', 3, 10);

-- Box shipments: which packing goes to which FGP
-- packing_details_id 1 = ITEM001/Box1, 2 = ITEM002/Box1, etc.
INSERT INTO nds.box_shipment (packing_details_id, warehouse_id, is_active) VALUES
(1, 'FGP01', TRUE), (1, 'FGP02', TRUE), (1, 'FGP03', TRUE),
(2, 'FGP01', TRUE), (2, 'FGP02', TRUE), (2, 'FGP03', TRUE),
(3, 'FGP01', TRUE), (3, 'FGP02', TRUE), (3, 'FGP03', TRUE),
(4, 'FGP01', TRUE), (4, 'FGP02', TRUE), (4, 'FGP03', TRUE),
(5, 'FGP01', TRUE), (5, 'FGP02', TRUE), (5, 'FGP03', TRUE);

-- =============================================
-- INVENTORY DATA
-- =============================================

-- Beginning Inventory: BI(i,j) for each product at each FGP
INSERT INTO nds.inventory_begin (product_id, warehouse_id, beginning_inventory, effective_date) VALUES
('ITEM001', 'FGP01', 100, '2026-01-05'),
('ITEM001', 'FGP02', 80,  '2026-01-05'),
('ITEM001', 'FGP03', 90,  '2026-01-05'),
('ITEM002', 'FGP01', 120, '2026-01-05'),
('ITEM002', 'FGP02', 110, '2026-01-05'),
('ITEM002', 'FGP03', 95,  '2026-01-05'),
('ITEM003', 'FGP01', 70,  '2026-01-05'),
('ITEM003', 'FGP02', 85,  '2026-01-05'),
('ITEM003', 'FGP03', 60,  '2026-01-05'),
('ITEM004', 'FGP01', 150, '2026-01-05'),
('ITEM004', 'FGP02', 130, '2026-01-05'),
('ITEM004', 'FGP03', 140, '2026-01-05'),
('ITEM005', 'FGP01', 50,  '2026-01-05'),
('ITEM005', 'FGP02', 45,  '2026-01-05'),
('ITEM005', 'FGP03', 55,  '2026-01-05')
ON CONFLICT DO NOTHING;

-- Inventory Flow: delta_I(i,j,t), U(i,j,t), L(i,j,t)
-- delta_I represents demand fluctuation (negative = consumption)
INSERT INTO nds.inventory_flow (product_id, warehouse_id, time_period, inventory_fluctuation, inventory_ceiling, inventory_floor) VALUES
-- ITEM001
('ITEM001', 'FGP01', 1, -35, 300, 50), ('ITEM001', 'FGP01', 2, -30, 300, 50),
('ITEM001', 'FGP01', 3, -40, 300, 50), ('ITEM001', 'FGP01', 4, -25, 300, 50),
('ITEM001', 'FGP01', 5, -45, 300, 50), ('ITEM001', 'FGP01', 6, -30, 300, 50),
('ITEM001', 'FGP02', 1, -25, 250, 40), ('ITEM001', 'FGP02', 2, -20, 250, 40),
('ITEM001', 'FGP02', 3, -30, 250, 40), ('ITEM001', 'FGP02', 4, -28, 250, 40),
('ITEM001', 'FGP02', 5, -35, 250, 40), ('ITEM001', 'FGP02', 6, -22, 250, 40),
('ITEM001', 'FGP03', 1, -20, 280, 45), ('ITEM001', 'FGP03', 2, -25, 280, 45),
('ITEM001', 'FGP03', 3, -28, 280, 45), ('ITEM001', 'FGP03', 4, -22, 280, 45),
('ITEM001', 'FGP03', 5, -30, 280, 45), ('ITEM001', 'FGP03', 6, -18, 280, 45),
-- ITEM002
('ITEM002', 'FGP01', 1, -40, 350, 60), ('ITEM002', 'FGP01', 2, -35, 350, 60),
('ITEM002', 'FGP01', 3, -45, 350, 60), ('ITEM002', 'FGP01', 4, -38, 350, 60),
('ITEM002', 'FGP01', 5, -50, 350, 60), ('ITEM002', 'FGP01', 6, -42, 350, 60),
('ITEM002', 'FGP02', 1, -30, 300, 50), ('ITEM002', 'FGP02', 2, -28, 300, 50),
('ITEM002', 'FGP02', 3, -35, 300, 50), ('ITEM002', 'FGP02', 4, -32, 300, 50),
('ITEM002', 'FGP02', 5, -40, 300, 50), ('ITEM002', 'FGP02', 6, -30, 300, 50),
('ITEM002', 'FGP03', 1, -25, 270, 45), ('ITEM002', 'FGP03', 2, -22, 270, 45),
('ITEM002', 'FGP03', 3, -30, 270, 45), ('ITEM002', 'FGP03', 4, -28, 270, 45),
('ITEM002', 'FGP03', 5, -35, 270, 45), ('ITEM002', 'FGP03', 6, -25, 270, 45),
-- ITEM003
('ITEM003', 'FGP01', 1, -20, 200, 30), ('ITEM003', 'FGP01', 2, -18, 200, 30),
('ITEM003', 'FGP01', 3, -25, 200, 30), ('ITEM003', 'FGP01', 4, -22, 200, 30),
('ITEM003', 'FGP01', 5, -28, 200, 30), ('ITEM003', 'FGP01', 6, -20, 200, 30),
('ITEM003', 'FGP02', 1, -25, 220, 35), ('ITEM003', 'FGP02', 2, -22, 220, 35),
('ITEM003', 'FGP02', 3, -28, 220, 35), ('ITEM003', 'FGP02', 4, -20, 220, 35),
('ITEM003', 'FGP02', 5, -30, 220, 35), ('ITEM003', 'FGP02', 6, -25, 220, 35),
('ITEM003', 'FGP03', 1, -15, 180, 25), ('ITEM003', 'FGP03', 2, -18, 180, 25),
('ITEM003', 'FGP03', 3, -20, 180, 25), ('ITEM003', 'FGP03', 4, -16, 180, 25),
('ITEM003', 'FGP03', 5, -22, 180, 25), ('ITEM003', 'FGP03', 6, -18, 180, 25),
-- ITEM004
('ITEM004', 'FGP01', 1, -50, 400, 70), ('ITEM004', 'FGP01', 2, -45, 400, 70),
('ITEM004', 'FGP01', 3, -55, 400, 70), ('ITEM004', 'FGP01', 4, -48, 400, 70),
('ITEM004', 'FGP01', 5, -60, 400, 70), ('ITEM004', 'FGP01', 6, -50, 400, 70),
('ITEM004', 'FGP02', 1, -40, 350, 60), ('ITEM004', 'FGP02', 2, -38, 350, 60),
('ITEM004', 'FGP02', 3, -45, 350, 60), ('ITEM004', 'FGP02', 4, -42, 350, 60),
('ITEM004', 'FGP02', 5, -50, 350, 60), ('ITEM004', 'FGP02', 6, -40, 350, 60),
('ITEM004', 'FGP03', 1, -45, 380, 65), ('ITEM004', 'FGP03', 2, -40, 380, 65),
('ITEM004', 'FGP03', 3, -50, 380, 65), ('ITEM004', 'FGP03', 4, -43, 380, 65),
('ITEM004', 'FGP03', 5, -55, 380, 65), ('ITEM004', 'FGP03', 6, -45, 380, 65),
-- ITEM005
('ITEM005', 'FGP01', 1, -15, 150, 20), ('ITEM005', 'FGP01', 2, -12, 150, 20),
('ITEM005', 'FGP01', 3, -18, 150, 20), ('ITEM005', 'FGP01', 4, -14, 150, 20),
('ITEM005', 'FGP01', 5, -20, 150, 20), ('ITEM005', 'FGP01', 6, -15, 150, 20),
('ITEM005', 'FGP02', 1, -12, 130, 18), ('ITEM005', 'FGP02', 2, -10, 130, 18),
('ITEM005', 'FGP02', 3, -15, 130, 18), ('ITEM005', 'FGP02', 4, -13, 130, 18),
('ITEM005', 'FGP02', 5, -18, 130, 18), ('ITEM005', 'FGP02', 6, -12, 130, 18),
('ITEM005', 'FGP03', 1, -10, 140, 20), ('ITEM005', 'FGP03', 2, -12, 140, 20),
('ITEM005', 'FGP03', 3, -14, 140, 20), ('ITEM005', 'FGP03', 4, -11, 140, 20),
('ITEM005', 'FGP03', 5, -16, 140, 20), ('ITEM005', 'FGP03', 6, -10, 140, 20)
ON CONFLICT DO NOTHING;

-- =============================================
-- COST DATA
-- =============================================

-- Unit costs: Co (overstock), Cs (shortage), Cb (backlog), Cp (penalty)
INSERT INTO nds.unit_cost (product_id, warehouse_id, time_period, overstock_cost, shortage_cost, backlog_cost, penalty_cost) VALUES
-- ITEM001
('ITEM001', 'FGP01', 1, 2.0, 5.0, 8.0, 15.0), ('ITEM001', 'FGP01', 2, 2.0, 5.0, 8.0, 15.0),
('ITEM001', 'FGP01', 3, 2.0, 5.0, 8.0, 15.0), ('ITEM001', 'FGP01', 4, 2.0, 5.0, 8.0, 15.0),
('ITEM001', 'FGP01', 5, 2.0, 5.0, 8.0, 15.0), ('ITEM001', 'FGP01', 6, 2.0, 5.0, 8.0, 15.0),
('ITEM001', 'FGP02', 1, 2.5, 5.5, 9.0, 15.0), ('ITEM001', 'FGP02', 2, 2.5, 5.5, 9.0, 15.0),
('ITEM001', 'FGP02', 3, 2.5, 5.5, 9.0, 15.0), ('ITEM001', 'FGP02', 4, 2.5, 5.5, 9.0, 15.0),
('ITEM001', 'FGP02', 5, 2.5, 5.5, 9.0, 15.0), ('ITEM001', 'FGP02', 6, 2.5, 5.5, 9.0, 15.0),
('ITEM001', 'FGP03', 1, 2.0, 5.0, 8.5, 15.0), ('ITEM001', 'FGP03', 2, 2.0, 5.0, 8.5, 15.0),
('ITEM001', 'FGP03', 3, 2.0, 5.0, 8.5, 15.0), ('ITEM001', 'FGP03', 4, 2.0, 5.0, 8.5, 15.0),
('ITEM001', 'FGP03', 5, 2.0, 5.0, 8.5, 15.0), ('ITEM001', 'FGP03', 6, 2.0, 5.0, 8.5, 15.0),
-- ITEM002
('ITEM002', 'FGP01', 1, 3.0, 6.0, 10.0, 20.0), ('ITEM002', 'FGP01', 2, 3.0, 6.0, 10.0, 20.0),
('ITEM002', 'FGP01', 3, 3.0, 6.0, 10.0, 20.0), ('ITEM002', 'FGP01', 4, 3.0, 6.0, 10.0, 20.0),
('ITEM002', 'FGP01', 5, 3.0, 6.0, 10.0, 20.0), ('ITEM002', 'FGP01', 6, 3.0, 6.0, 10.0, 20.0),
('ITEM002', 'FGP02', 1, 3.0, 6.0, 10.0, 20.0), ('ITEM002', 'FGP02', 2, 3.0, 6.0, 10.0, 20.0),
('ITEM002', 'FGP02', 3, 3.0, 6.0, 10.0, 20.0), ('ITEM002', 'FGP02', 4, 3.0, 6.0, 10.0, 20.0),
('ITEM002', 'FGP02', 5, 3.0, 6.0, 10.0, 20.0), ('ITEM002', 'FGP02', 6, 3.0, 6.0, 10.0, 20.0),
('ITEM002', 'FGP03', 1, 2.5, 5.5, 9.0, 18.0), ('ITEM002', 'FGP03', 2, 2.5, 5.5, 9.0, 18.0),
('ITEM002', 'FGP03', 3, 2.5, 5.5, 9.0, 18.0), ('ITEM002', 'FGP03', 4, 2.5, 5.5, 9.0, 18.0),
('ITEM002', 'FGP03', 5, 2.5, 5.5, 9.0, 18.0), ('ITEM002', 'FGP03', 6, 2.5, 5.5, 9.0, 18.0),
-- ITEM003
('ITEM003', 'FGP01', 1, 2.0, 4.0, 7.0, 12.0), ('ITEM003', 'FGP01', 2, 2.0, 4.0, 7.0, 12.0),
('ITEM003', 'FGP01', 3, 2.0, 4.0, 7.0, 12.0), ('ITEM003', 'FGP01', 4, 2.0, 4.0, 7.0, 12.0),
('ITEM003', 'FGP01', 5, 2.0, 4.0, 7.0, 12.0), ('ITEM003', 'FGP01', 6, 2.0, 4.0, 7.0, 12.0),
('ITEM003', 'FGP02', 1, 2.0, 4.5, 7.5, 12.0), ('ITEM003', 'FGP02', 2, 2.0, 4.5, 7.5, 12.0),
('ITEM003', 'FGP02', 3, 2.0, 4.5, 7.5, 12.0), ('ITEM003', 'FGP02', 4, 2.0, 4.5, 7.5, 12.0),
('ITEM003', 'FGP02', 5, 2.0, 4.5, 7.5, 12.0), ('ITEM003', 'FGP02', 6, 2.0, 4.5, 7.5, 12.0),
('ITEM003', 'FGP03', 1, 1.5, 4.0, 7.0, 10.0), ('ITEM003', 'FGP03', 2, 1.5, 4.0, 7.0, 10.0),
('ITEM003', 'FGP03', 3, 1.5, 4.0, 7.0, 10.0), ('ITEM003', 'FGP03', 4, 1.5, 4.0, 7.0, 10.0),
('ITEM003', 'FGP03', 5, 1.5, 4.0, 7.0, 10.0), ('ITEM003', 'FGP03', 6, 1.5, 4.0, 7.0, 10.0),
-- ITEM004
('ITEM004', 'FGP01', 1, 2.5, 5.0, 9.0, 18.0), ('ITEM004', 'FGP01', 2, 2.5, 5.0, 9.0, 18.0),
('ITEM004', 'FGP01', 3, 2.5, 5.0, 9.0, 18.0), ('ITEM004', 'FGP01', 4, 2.5, 5.0, 9.0, 18.0),
('ITEM004', 'FGP01', 5, 2.5, 5.0, 9.0, 18.0), ('ITEM004', 'FGP01', 6, 2.5, 5.0, 9.0, 18.0),
('ITEM004', 'FGP02', 1, 2.5, 5.5, 9.5, 18.0), ('ITEM004', 'FGP02', 2, 2.5, 5.5, 9.5, 18.0),
('ITEM004', 'FGP02', 3, 2.5, 5.5, 9.5, 18.0), ('ITEM004', 'FGP02', 4, 2.5, 5.5, 9.5, 18.0),
('ITEM004', 'FGP02', 5, 2.5, 5.5, 9.5, 18.0), ('ITEM004', 'FGP02', 6, 2.5, 5.5, 9.5, 18.0),
('ITEM004', 'FGP03', 1, 2.0, 5.0, 8.0, 16.0), ('ITEM004', 'FGP03', 2, 2.0, 5.0, 8.0, 16.0),
('ITEM004', 'FGP03', 3, 2.0, 5.0, 8.0, 16.0), ('ITEM004', 'FGP03', 4, 2.0, 5.0, 8.0, 16.0),
('ITEM004', 'FGP03', 5, 2.0, 5.0, 8.0, 16.0), ('ITEM004', 'FGP03', 6, 2.0, 5.0, 8.0, 16.0),
-- ITEM005
('ITEM005', 'FGP01', 1, 1.5, 3.5, 6.0, 10.0), ('ITEM005', 'FGP01', 2, 1.5, 3.5, 6.0, 10.0),
('ITEM005', 'FGP01', 3, 1.5, 3.5, 6.0, 10.0), ('ITEM005', 'FGP01', 4, 1.5, 3.5, 6.0, 10.0),
('ITEM005', 'FGP01', 5, 1.5, 3.5, 6.0, 10.0), ('ITEM005', 'FGP01', 6, 1.5, 3.5, 6.0, 10.0),
('ITEM005', 'FGP02', 1, 1.5, 3.5, 6.0, 10.0), ('ITEM005', 'FGP02', 2, 1.5, 3.5, 6.0, 10.0),
('ITEM005', 'FGP02', 3, 1.5, 3.5, 6.0, 10.0), ('ITEM005', 'FGP02', 4, 1.5, 3.5, 6.0, 10.0),
('ITEM005', 'FGP02', 5, 1.5, 3.5, 6.0, 10.0), ('ITEM005', 'FGP02', 6, 1.5, 3.5, 6.0, 10.0),
('ITEM005', 'FGP03', 1, 1.5, 3.0, 5.5, 10.0), ('ITEM005', 'FGP03', 2, 1.5, 3.0, 5.5, 10.0),
('ITEM005', 'FGP03', 3, 1.5, 3.0, 5.5, 10.0), ('ITEM005', 'FGP03', 4, 1.5, 3.0, 5.5, 10.0),
('ITEM005', 'FGP03', 5, 1.5, 3.0, 5.5, 10.0), ('ITEM005', 'FGP03', 6, 1.5, 3.0, 5.5, 10.0)
ON CONFLICT DO NOTHING;

-- =============================================
-- CAPACITY DATA
-- =============================================

-- Vendor Capacity: CAP(i,t) production capacity per item per period
INSERT INTO nds.vendor_capacity (product_id, time_period, capacity) VALUES
('ITEM001', 1, 200), ('ITEM001', 2, 200), ('ITEM001', 3, 220),
('ITEM001', 4, 200), ('ITEM001', 5, 210), ('ITEM001', 6, 200),
('ITEM002', 1, 250), ('ITEM002', 2, 250), ('ITEM002', 3, 270),
('ITEM002', 4, 260), ('ITEM002', 5, 280), ('ITEM002', 6, 250),
('ITEM003', 1, 150), ('ITEM003', 2, 150), ('ITEM003', 3, 160),
('ITEM003', 4, 150), ('ITEM003', 5, 165), ('ITEM003', 6, 155),
('ITEM004', 1, 350), ('ITEM004', 2, 350), ('ITEM004', 3, 380),
('ITEM004', 4, 360), ('ITEM004', 5, 400), ('ITEM004', 6, 350),
('ITEM005', 1, 100), ('ITEM005', 2, 100), ('ITEM005', 3, 110),
('ITEM005', 4, 105), ('ITEM005', 5, 115), ('ITEM005', 6, 100)
ON CONFLICT DO NOTHING;

-- =============================================
-- DSS SCENARIO (Baseline)
-- =============================================

INSERT INTO nds.scenario (scenario_name, description, created_by, is_baseline) VALUES
('Baseline Scenario', 'Initial baseline with default parameters for all items and FGPs', 'system', TRUE);
