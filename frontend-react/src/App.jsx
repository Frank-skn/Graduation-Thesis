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
import B1_RunOptimization from './pages/B1_RunOptimization'
import B2_ExecutiveSummary from './pages/B2_ExecutiveSummary'
import B3_AllocationInventoryDashboard from './pages/B3_AllocationInventoryDashboard'

// Group C: Scenario Analysis
import C1_ScenarioManagement from './pages/C1_ScenarioManagement'
import C2_ScenarioComparison from './pages/C2_ScenarioComparison'

// Group D: Advanced Analysis
import D1_SensitivityAnalysis from './pages/D1_SensitivityAnalysis'
import D2_ParameterStability from './pages/D2_ParameterStability'

// Guard components
import RequireRun from './components/RequireRun'
import RequireAuth from './components/RequireAuth'
import Login from './pages/Login'

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
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route path="/*" element={
            <RequireAuth>
              <DashboardLayout>
                <Routes>
                  <Route path="/" element={<Navigate to="/a1-data-overview" replace />} />

                  {/* Group A: Data Foundation */}
                  <Route path="/a1-data-overview" element={<A1_DataOverview />} />
                  <Route path="/a2-parameter-management" element={<A2_ParameterManagement />} />

                  {/* Group B: Results & Performance */}
                  <Route path="/b1-run-optimization" element={<B1_RunOptimization />} />
                  <Route path="/b2-executive-summary" element={<RequireRun><B2_ExecutiveSummary /></RequireRun>} />
                  <Route path="/b3-allocation-inventory-dashboard" element={<RequireRun><B3_AllocationInventoryDashboard /></RequireRun>} />
                  {/* Legacy routes kept as redirects for old bookmarks (old numbering before menu renumbering) */}
                  <Route path="/b0-run-optimization" element={<Navigate to="/b1-run-optimization" replace />} />
                  <Route path="/b1-executive-summary" element={<Navigate to="/b2-executive-summary" replace />} />
                  <Route path="/b2-allocation-inventory-dashboard" element={<Navigate to="/b3-allocation-inventory-dashboard" replace />} />
                  <Route path="/b3-variable-details" element={<Navigate to="/b2-executive-summary" replace />} />

                  {/* Group C: Scenario Analysis */}
                  <Route path="/c1-scenario-management" element={<C1_ScenarioManagement />} />
                  <Route path="/c2-scenario-comparison" element={<C2_ScenarioComparison />} />
                  {/* Legacy route kept as redirect for old bookmarks (old numbering before menu renumbering) */}
                  <Route path="/c3-scenario-comparison" element={<Navigate to="/c2-scenario-comparison" replace />} />

                  {/* Group D: Advanced Analysis */}
                  <Route path="/d1-sensitivity-analysis" element={<D1_SensitivityAnalysis />} />
                  <Route path="/d2-parameter-stability" element={<D2_ParameterStability />} />
                  {/* Legacy routes kept as redirects for old bookmarks (old numbering before menu renumbering) */}
                  <Route path="/d2-sensitivity-analysis" element={<Navigate to="/d1-sensitivity-analysis" replace />} />
                  <Route path="/d3-parameter-stability" element={<Navigate to="/d2-parameter-stability" replace />} />
                  {/* Decision Impact Scenarios (old D1) removed — duplicated C2 Scenario Comparison */}
                  <Route path="/d1-decision-impact-scenarios" element={<Navigate to="/c2-scenario-comparison" replace />} />
                </Routes>
              </DashboardLayout>
            </RequireAuth>
          } />
        </Routes>
    </Router>
    </AppProvider>
    </ConfigProvider>
  )
}

export default App
