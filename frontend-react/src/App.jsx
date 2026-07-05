import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Layout, ConfigProvider } from 'antd'
import viVN from 'antd/locale/vi_VN'
import { AppProvider } from './context/AppContext'
import DashboardLayout from './components/layout/DashboardLayout'
import { BRAND, NEUTRAL, SEMANTIC } from './theme/tokens'

// Group A: Data Foundation
import A1_DataOverview from './pages/A1_DataOverview'
import A2_ParameterManagement from './pages/A2_ParameterManagement'

// Group B: Results & Performance
import B0_RunOptimization from './pages/B0_RunOptimization'
import B1_ExecutiveSummary from './pages/B1_ExecutiveSummary'
import B2_AllocationInventoryDashboard from './pages/B2_AllocationInventoryDashboard'

// Group C: Scenario Analysis
import C1_ScenarioManagement from './pages/C1_ScenarioManagement'
import C3_ScenarioComparison from './pages/C3_ScenarioComparison'

// Group D: Advanced Analysis
import D2_SensitivityAnalysis from './pages/D2_SensitivityAnalysis'
import D3_ParameterStability from './pages/D3_ParameterStability'

// Guard component
import RequireRun from './components/RequireRun'

const { Content } = Layout

const themeConfig = {
  token: {
    colorPrimary: BRAND[600],
    colorInfo: BRAND[600],
    colorSuccess: SEMANTIC.good,
    colorWarning: SEMANTIC.warn,
    colorError: SEMANTIC.bad,
    colorText: NEUTRAL[900],
    colorTextSecondary: NEUTRAL[600],
    colorBorder: NEUTRAL[200],
    colorBorderSecondary: NEUTRAL[100],
    colorBgLayout: NEUTRAL[50],
    borderRadius: 10,
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
    fontSize: 14,
    controlHeight: 36,
  },
  components: {
    Card: { borderRadiusLG: 12, headerFontSize: 15, paddingLG: 20 },
    Table: { headerBg: NEUTRAL[50], headerColor: NEUTRAL[600], borderColor: NEUTRAL[200], rowHoverBg: BRAND[50] },
    Statistic: { titleFontSize: 13 },
    Tag: { defaultBg: NEUTRAL[100], defaultColor: NEUTRAL[600], borderRadiusSM: 6 },
    Button: { primaryShadow: 'none', fontWeight: 500 },
    Menu: { itemSelectedBg: BRAND[50], itemSelectedColor: BRAND[600] },
  },
}

function App() {
  return (
    <ConfigProvider locale={viVN} theme={themeConfig}>
    <AppProvider>
    <Router>
      <DashboardLayout>
        <Routes>
          <Route path="/" element={<Navigate to="/a1-data-overview" replace />} />
          
          {/* Group A: Data Foundation */}
          <Route path="/a1-data-overview" element={<A1_DataOverview />} />
          <Route path="/a2-parameter-management" element={<A2_ParameterManagement />} />
          
          {/* Group B: Results & Performance */}
          <Route path="/b0-run-optimization" element={<B0_RunOptimization />} />
          <Route path="/b1-executive-summary" element={<RequireRun><B1_ExecutiveSummary /></RequireRun>} />
          <Route path="/b2-allocation-inventory-dashboard" element={<RequireRun><B2_AllocationInventoryDashboard /></RequireRun>} />
          {/* Legacy routes kept as redirects for old bookmarks */}
          <Route path="/b3-variable-details" element={<Navigate to="/b1-executive-summary" replace />} />
          
          {/* Group C: Scenario Analysis */}
          <Route path="/c1-scenario-management" element={<C1_ScenarioManagement />} />
          <Route path="/c3-scenario-comparison" element={<C3_ScenarioComparison />} />
          
          {/* Group D: Advanced Analysis */}
          {/* D1 (Decision Impact) removed — duplicated C2 Scenario Comparison */}
          <Route path="/d1-decision-impact-scenarios" element={<Navigate to="/c3-scenario-comparison" replace />} />
          <Route path="/d2-sensitivity-analysis" element={<D2_SensitivityAnalysis />} />
          <Route path="/d3-parameter-stability" element={<D3_ParameterStability />} />
          

        </Routes>
      </DashboardLayout>
    </Router>
    </AppProvider>
    </ConfigProvider>
  )
}

export default App
