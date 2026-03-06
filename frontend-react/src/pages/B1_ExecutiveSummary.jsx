import React, { useState } from 'react'
import { Card, Row, Col, Statistic, Tag, Alert, Spin, Select, InputNumber, Button, Progress } from 'antd'
import {
  DashboardOutlined,
  DollarOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  RiseOutlined,
  FallOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import { useApi } from '../hooks/useApi'
import { useAppContext } from '../context/AppContext'
import optimizationService from '../services/optimizationService'

const COLORS = ['#f5222d', '#fa8c16', '#faad14', '#1890ff']

const ExecutiveSummary = () => {
  const { activeRunId, setActiveRunId } = useAppContext()
  const [runIdInput, setRunIdInput] = useState(activeRunId || 1)

  const { data, loading, error, execute: refresh } = useApi(
    () => activeRunId ? optimizationService.getExecutiveSummary(activeRunId) : Promise.resolve(null),
    [activeRunId]
  )

  const handleLoadRun = () => {
    setActiveRunId(runIdInput)
  }

  if (!activeRunId) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-primary-700 mb-2">
          <DashboardOutlined className="mr-3" />
          B1. Executive Summary
        </h1>
        <Alert
          message="No Optimization Run Selected"
          description="Enter a run ID to view the executive summary."
          type="info"
          showIcon
        />
        <Card>
          <div className="flex items-center gap-4">
            <span>Run ID:</span>
            <InputNumber min={1} value={runIdInput} onChange={setRunIdInput} />
            <Button type="primary" onClick={handleLoadRun}>Load Results</Button>
          </div>
        </Card>
      </div>
    )
  }

  const summary = data || {}
  const run = summary.run || {}
  const kpis = summary.kpis || {}

  const costBreakdown = [
    { name: 'Backorder', value: Number(kpis.total_backorder) || 0 },
    { name: 'Overstock', value: Number(kpis.total_overstock) || 0 },
    { name: 'Shortage', value: Number(kpis.total_shortage) || 0 },
    { name: 'Penalty', value: Number(kpis.total_penalty) || 0 },
  ]

  const statusColor = run.solver_status === 'Optimal' ? 'green' : run.solver_status === 'Feasible' ? 'orange' : 'red'

  return (
    <Spin spinning={loading}>
    <div className="space-y-6">
      {error && <Alert message="Error loading summary" description={error} type="error" showIcon closable />}

      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-primary-700 mb-2">
            <DashboardOutlined className="mr-3" />
            B1. Executive Summary
          </h1>
          <p className="text-gray-600">
            Run #{run.run_id} | Scenario: {run.scenario_name || run.scenario_id}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <InputNumber min={1} value={runIdInput} onChange={setRunIdInput} size="small" />
          <Button onClick={() => { setActiveRunId(runIdInput) }} size="small">Load</Button>
          <Tag color={statusColor}>{run.solver_status || 'N/A'}</Tag>
        </div>
      </div>

      {/* Key Performance Indicators */}
      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic
              title="Total Cost"
              value={Number(kpis.total_cost) || 0}
              precision={2}
              prefix={<DollarOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Service Level"
              value={Number(kpis.service_level) || 0}
              precision={1}
              suffix="%"
              valueStyle={{ color: '#3f8600' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Capacity Utilization"
              value={Number(kpis.capacity_utilization) || 0}
              precision={1}
              suffix="%"
              prefix={<ThunderboltOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Solve Time"
              value={Number(run.solve_time_seconds) || 0}
              precision={2}
              suffix="s"
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* Cost Breakdown & Run Details */}
      <Row gutter={16}>
        <Col span={12}>
          <Card title="Cost Breakdown">
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={costBreakdown}
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  dataKey="value"
                  label={({ name, value }) => `${name}: $${value.toLocaleString()}`}
                >
                  {costBreakdown.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => `$${Number(value).toLocaleString()}`} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Run Details">
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-500">Objective Value:</span>
                <span className="font-bold">${Number(run.objective_value || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">MIP Gap:</span>
                <span>{Number(run.mip_gap || 0).toFixed(4)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Products:</span>
                <span>{summary.product_count || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Warehouses:</span>
                <span>{summary.warehouse_count || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Periods:</span>
                <span>{summary.period_count || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Total Results:</span>
                <span>{summary.result_count || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Total Backorder:</span>
                <span className="text-red-600">{Number(kpis.total_backorder || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Total Overstock:</span>
                <span className="text-orange-600">{Number(kpis.total_overstock || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Total Shortage:</span>
                <span className="text-yellow-600">{Number(kpis.total_shortage || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Total Penalty:</span>
                <span className="text-blue-600">{Number(kpis.total_penalty || 0).toLocaleString()}</span>
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
    </Spin>
  )
}

export default ExecutiveSummary
