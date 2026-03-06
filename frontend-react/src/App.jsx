import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from 'antd'
import { AppProvider } from './context/AppContext'
import DashboardLayout from './components/layout/DashboardLayout'

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
import D1_DecisionImpactScenarios from './pages/D1_DecisionImpactScenarios'
import D2_SensitivityAnalysis from './pages/D2_SensitivityAnalysis'
import D3_ParameterStability from './pages/D3_ParameterStability'

// Guard component
import RequireRun from './components/RequireRun'

const { Content } = Layout

function App() {
  return (
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
          {/* B3 đã được gộp vào B1 (B2) — redirect để hỗ trợ liên kết cũ */}
          <Route path="/b3-variable-details" element={<Navigate to="/b1-executive-summary" replace />} />
          
          {/* Group C: Scenario Analysis */}
          <Route path="/c1-scenario-management" element={<C1_ScenarioManagement />} />
          <Route path="/c3-scenario-comparison" element={<C3_ScenarioComparison />} />
          
          {/* Group D: Advanced Analysis */}
          <Route path="/d1-decision-impact-scenarios" element={<D1_DecisionImpactScenarios />} />
          <Route path="/d2-sensitivity-analysis" element={<D2_SensitivityAnalysis />} />
          <Route path="/d3-parameter-stability" element={<D3_ParameterStability />} />
          

        </Routes>
      </DashboardLayout>
    </Router>
    </AppProvider>
  )
}

export default App
