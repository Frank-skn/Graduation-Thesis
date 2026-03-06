# User Guide

## Getting Started

### Prerequisites
- Docker and Docker Compose installed
- 8GB RAM minimum
- 10GB free disk space

### Initial Setup

1. **Clone/Extract Project**
```bash
cd ss-mb-smi-dss
```

2. **Configure Environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

3. **Start Services**
```bash
docker-compose up -d
```

Wait for all services to be healthy:
```bash
docker-compose ps
```

4. **Initialize Database**
```bash
# Connect to SQL Server and run:
# 1. database/nds/01_create_nds_schema.sql
# 2. database/dds/01_create_dds_schema.sql
# 3. database/dds/02_etl_procedures.sql

# Or use the init script:
docker-compose exec backend python scripts/init_db.py
```

5. **Load Sample Data**
```bash
docker-compose exec backend python scripts/load_sample_data.py
```

6. **Access Application**
- Frontend: http://localhost:8501
- API Docs: http://localhost:8000/docs

## Using the DSS

### 1. Dashboard

The dashboard shows:
- Total scenarios
- Recent optimization runs
- System status
- Activity log

### 2. Creating Scenarios

**What-If Scenarios** allow you to test different business conditions.

1. Navigate to **Scenarios** page
2. Click **Create Scenario** tab
3. Fill in:
   - **Scenario Name**: Descriptive name (e.g., "Q1 2024 High Demand")
   - **Description**: What makes this scenario different
   - **Created By**: Your name/email
4. Click **Create Scenario**

### 3. Running Optimization

1. Navigate to **Run Optimization** page
2. Select a scenario from dropdown
3. Configure solver settings:
   - **Solver**: CBC (free, fast) or GLPK (alternative)
   - **Time Limit**: Maximum solve time (300s recommended)
   - **MIP Gap**: Optimality tolerance (0.01 = 1%)
4. Click **Run Optimization**
5. Wait for results (watch progress in terminal if running locally)

### 4. Viewing Results

1. Navigate to **View Results** page
2. Enter the **Run ID** (from optimization output)
3. Click **Load Results**

#### Result Components

**KPI Summary**
- Total Cost
- Service Level
- Capacity Utilization
- Total Backorder

**Charts**
- **Inventory Time Series**: How inventory changes over time
- **Cost Breakdown**: Pie chart of cost components
- **Warehouse Comparison**: Performance by warehouse
- **Decision Variables**: q (case packs) and r (residuals) over time
- **Product Heatmap**: Inventory distribution

**Raw Data**
Expand "View Raw Data" to see detailed results table.

### 5. Scenario Comparison

Compare multiple scenarios:

1. Run optimization for multiple scenarios
2. Note their Run IDs
3. Use the comparison charts to see differences

### 6. Data Explorer

Browse input data:
- **Products**: All product IDs
- **Warehouses**: All warehouse IDs
- **Time Periods**: Planning horizon

## Understanding Results

### Decision Variables

**q (Case Packs)**: Number of full boxes to ship
**r (Residual Units)**: Loose units to fill capacity exactly

### Performance Metrics

**Backorder**: Demand not met (negative inventory) - HIGH COST
**Overstock**: Inventory above ceiling - MODERATE COST
**Shortage**: Inventory below floor - MODERATE COST
**Penalty**: Used residual units (inefficient) - HIGH COST

### Optimal Solution

- Minimize total cost
- Meet capacity constraints exactly
- Balance inventory within bounds
- Prefer full case packs over residuals

## Best Practices

### Creating Scenarios

1. **Baseline First**: Create baseline with current data
2. **One Change**: Vary one parameter per scenario
3. **Descriptive Names**: "Baseline vs +20% Demand"
4. **Document**: Use description field thoroughly

### Running Optimization

1. **Start Small**: Test with short time horizons
2. **Increase Time Limit**: If solution not optimal, increase time
3. **Check Status**: "optimal" is best, "feasible" is acceptable
4. **Save Run IDs**: Keep track of important runs

### Analyzing Results

1. **Compare to Baseline**: Always compare to baseline scenario
2. **Look for Patterns**: Seasonal trends, warehouse bottlenecks
3. **Check Service Level**: High is good (fewer backorders)
4. **Review Penalty Flags**: High penalties mean inefficient packing

## Troubleshooting

### Optimization Fails

**"Infeasible" Status**
- Capacity too low for demand
- Check CAP values in DDS
- Review constraint formulation

**Slow Solve Time**
- Reduce time horizon
- Increase time limit
- Try different solver

### No Results Displayed

- Verify Run ID is correct
- Check API is running: http://localhost:8000/health
- Review browser console for errors

### Database Connection Issues

```bash
# Check SQL Server is running
docker-compose ps sqlserver

# Restart services
docker-compose restart backend
```

### Frontend Not Loading

```bash
# Check logs
docker-compose logs frontend

# Restart
docker-compose restart frontend
```

## Advanced Usage

### Custom Solvers

To use Gurobi (commercial, requires license):

1. Install Gurobi in backend container
2. Add license file
3. Select "gurobi" in solver dropdown

### ETL Customization

Modify `database/dds/02_etl_procedures.sql` to change data transformation logic.

### API Integration

Access the DSS programmatically:

```python
import requests

# Create scenario
response = requests.post("http://localhost:8000/api/v1/scenarios/", json={
    "scenario_name": "API Test",
    "description": "Created via API",
    "created_by": "script@example.com"
})
scenario_id = response.json()["scenario_id"]

# Run optimization
response = requests.post("http://localhost:8000/api/v1/optimize/run", json={
    "scenario_id": scenario_id,
    "solver": "cbc",
    "time_limit": 300,
    "mip_gap": 0.01
})
run_id = response.json()["run_id"]

# Get results
results = requests.get(f"http://localhost:8000/api/v1/optimize/results/{run_id}")
print(results.json())
```

### Exporting Data

Results can be exported:

1. View results in browser
2. Expand "View Raw Data"
3. Copy to clipboard or export to CSV via browser

Alternatively, query database directly:

```sql
-- Get results from NDS
SELECT * FROM SMI_NDS.dbo.OPTIMIZATION_RESULT
WHERE run_id = 1;

-- Get KPIs
SELECT * FROM SMI_NDS.dbo.DSS_KPI
WHERE run_id = 1;
```

## Support

For issues:
1. Check logs: `docker-compose logs`
2. Review API docs: http://localhost:8000/docs
3. Verify database schema matches documentation

## Next Steps

After basic usage:
1. Load real operational data into NDS
2. Run ETL to populate DDS
3. Create multiple scenarios
4. Perform sensitivity analysis
5. Generate executive reports from results
