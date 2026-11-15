# SMI Decision Support System - React Dashboard

Modern React-based dashboard for Single-Supplier Multi-Buyer Supplier-Managed Inventory (SS-MB-SMI) optimization.

## Features

### 📊 Interactive Dashboard
- Real-time KPI monitoring
- Cost trend analysis
- Demand distribution visualization
- Quick action cards for key workflows

### 🧪 What-If Scenario Analysis (Table 1)
Complete implementation of scenario modeling:

#### Demand-Related Scenarios
- **Demand Surge**: Sudden increase at FGPs (ΔI↑)
- **Demand Imbalance**: Uneven distribution across plants
- **Demand Drop**: System-wide demand decrease (ΔI↓)

#### Capacity-Related Scenarios
- **Capacity Disruption**: Production reduction (CAP↓)
- **Capacity Expansion**: Investment analysis (CAP↑)

#### Inventory Policy Scenarios
- **Tight Safety Stock**: Stricter bounds (U/L narrowed)
- **Loose Safety Stock**: Flexible policy (U/L widened)

#### Packaging & Cost Scenarios
- **Case-pack Tightening/Relaxation**
- **Backorder/Overstock Penalty Adjustments**

### 📈 Sensitivity Analysis (Table 2)
Continuous parameter sensitivity with:

- **Capacity (CAP)**: ±10% to ±30%
- **Demand Volatility (ΔI)**: ±10% to ±25%
- **Cost Parameters**: Backorder (C^b), Overstock (C^o), Shortage (C^s), Penalty (C^p)
- **Inventory Bounds**: Safety stock sensitivity
- **Tornado Diagrams**: Multi-parameter comparison
- **Threshold Identification**: Breaking point analysis

### 🔍 Additional Pages
- **Data Overview**: FGP details and system state
- **Optimization Results**: Allocation decisions and performance
- **Scenario Comparison**: Side-by-side analysis with radar charts

## Technology Stack

- **React 18** - Modern React with Hooks
- **Vite** - Fast build tool and dev server
- **Ant Design** - Enterprise UI components
- **Recharts** - Responsive charting library
- **TailwindCSS** - Utility-first CSS framework
- **React Router** - Client-side routing
- **Axios** - HTTP client for API calls

## Design System

### Typography
- **Font Family**: Inter (sans-serif)
- **Modern, clean, highly readable**

### Color Palette
- **Primary**: #1a3a52 (Navy Blue)
- **Secondary**: #2c5f7f (Ocean Blue)
- **Accent**: #c5a572 (Gold)
- **Success**: #16a34a (Green)
- **Error**: #ef4444 (Red)

## Quick Start

### Development
```bash
npm install
npm run dev
```

### Production Build
```bash
npm run build
npm run preview
```

### Docker
```bash
docker-compose up -d
```

Access at: **http://localhost:3000**

## API Integration

Backend API URL: `http://backend:8000`

All API calls are proxied through Nginx configuration:
- `/api/*` → `http://backend:8000/*`

## Project Structure

```
frontend-react/
├── public/          # Static assets
├── src/
│   ├── components/  # Reusable components
│   │   └── layout/  # Layout components
│   ├── pages/       # Page components
│   │   ├── Dashboard.jsx
│   │   ├── DataOverview.jsx
│   │   ├── WhatIfScenarios.jsx
│   │   ├── SensitivityAnalysis.jsx
│   │   ├── OptimizationResults.jsx
│   │   └── ScenarioComparison.jsx
│   ├── App.jsx      # Main app component
│   ├── main.jsx     # Entry point
│   └── index.css    # Global styles
├── Dockerfile       # Multi-stage Docker build
├── nginx.conf       # Nginx configuration
└── package.json     # Dependencies
```

## Key Components

### DashboardLayout
- Responsive sidebar navigation
- Collapsible menu
- Header with system info

### Pages
1. **Dashboard** - Overview with KPIs and quick actions
2. **Data Overview** - FGP data and system state
3. **What-If Scenarios** - Interactive scenario modeling (5 groups, 11 scenarios)
4. **Sensitivity Analysis** - Parameter sensitivity with charts and tornado diagrams
5. **Optimization Results** - Allocation and performance metrics
6. **Scenario Comparison** - Multi-scenario radar chart comparison

## Features Implementation

### What-If Scenarios
- Interactive parameter sliders
- Real-time impact calculation
- Scenario configuration cards
- Impact comparison charts
- Save/run functionality

### Sensitivity Analysis
- Single parameter continuous analysis
- Multi-parameter tornado diagrams
- Threshold identification
- Key insights and recommendations
- Customizable analysis ranges

## Browser Support

- Chrome (recommended)
- Firefox
- Safari
- Edge

## Performance

- Lazy loading for routes
- Code splitting
- Optimized bundle size
- Nginx caching for static assets
- Gzip compression

## Contributing

See main project README for contribution guidelines.

## License

See main project LICENSE file.
