import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from 'antd'
import { AppProvider } from './context/AppContext'
import DashboardLayout from './components/layout/DashboardLayout'

// Group A: Data Foundation
import A1_DataOverview from './pages/A1_DataOverview'
import A2_ParameterManagement from './pages/A2_ParameterManagement'

// Group B: Results & Performance
import B1_ExecutiveSummary from './pages/B1_ExecutiveSummary'
import B2_AllocationInventoryDashboard from './pages/B2_AllocationInventoryDashboard'

// Group C: Scenario Analysis
import C1_ScenarioManagement from './pages/C1_ScenarioManagement'
import C3_ScenarioComparison from './pages/C3_ScenarioComparison'

// Group D: Advanced Analysis
import D1_DecisionImpactScenarios from './pages/D1_DecisionImpactScenarios'
import D2_SensitivityAnalysis from './pages/D2_SensitivityAnalysis'
import D3_ParameterStability from './pages/D3_ParameterStability'

// Group E: Insights
import E1_DecisionInsights from './pages/E1_DecisionInsights'

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
          <Route path="/b1-executive-summary" element={<B1_ExecutiveSummary />} />
          <Route path="/b2-allocation-inventory-dashboard" element={<B2_AllocationInventoryDashboard />} />
          
          {/* Group C: Scenario Analysis */}
          <Route path="/c1-scenario-management" element={<C1_ScenarioManagement />} />
          <Route path="/c3-scenario-comparison" element={<C3_ScenarioComparison />} />
          
          {/* Group D: Advanced Analysis */}
          <Route path="/d1-decision-impact-scenarios" element={<D1_DecisionImpactScenarios />} />
          <Route path="/d2-sensitivity-analysis" element={<D2_SensitivityAnalysis />} />
          <Route path="/d3-parameter-stability" element={<D3_ParameterStability />} />
          
          {/* Group E: Insights */}
          <Route path="/e1-decision-insights" element={<E1_DecisionInsights />} />
        </Routes>
      </DashboardLayout>
    </Router>
    </AppProvider>
  )
}

export default App
