import React, { useState } from 'react'
import { Card, Row, Col, Table, Tag, Button, Alert, Spin, Select, InputNumber } from 'antd'
import {
  ApartmentOutlined, ThunderboltOutlined, RiseOutlined, FallOutlined,
} from '@ant-design/icons'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ScatterChart, Scatter, ZAxis } from 'recharts'
import { useApi } from '../hooks/useApi'
import scenarioService from '../services/scenarioService'

const DecisionImpactScenarios = () => {
  const [baseRunId, setBaseRunId] = useState(null)
  const [compareRunId, setCompareRunId] = useState(null)

  const { data: scenariosData, loading: loadingScenarios } = useApi(() => scenarioService.getScenarios())
  const { data: comparison, loading: comparing, execute: runCompare } = useApi(
    () => baseRunId && compareRunId ? scenarioService.compareWhatIf(baseRunId, compareRunId) : Promise.resolve(null),
    [baseRunId, compareRunId],
    { immediate: false }
  )

  const scenarios = scenariosData?.scenarios || []
  const deltas = comparison?.deltas || []

  const impactData = deltas.map(d => ({
    kpi: d.kpi_name,
    impact: Number(d.absolute_change) || 0,
    pctChange: Number(d.percent_change) || 0,
  }))

  const scenarioColumns = [
    { title: 'ID', dataIndex: 'scenario_id', key: 'scenario_id', width: 60 },
    { title: 'Name', dataIndex: 'scenario_name', key: 'scenario_name', render: (t) => <span className="font-semibold">{t}</span> },
    { title: 'Baseline', dataIndex: 'is_baseline', key: 'is_baseline', render: (v) => v ? <Tag color="green">Yes</Tag> : <Tag>No</Tag> },
    { title: 'Created', dataIndex: 'created_at', key: 'created_at', render: (t) => t ? new Date(t).toLocaleDateString() : 'N/A' },
  ]

  const impactColumns = [
    { title: 'KPI', dataIndex: 'kpi_name', key: 'kpi_name', render: (t) => <span className="font-semibold">{t}</span> },
    { title: 'Base', dataIndex: 'base_value', key: 'base_value', render: (v) => Number(v).toLocaleString() },
    { title: 'Scenario', dataIndex: 'whatif_value', key: 'whatif_value', render: (v) => Number(v).toLocaleString() },
    {
      title: 'Impact', dataIndex: 'percent_change', key: 'percent_change',
      render: (v) => {
        const n = Number(v)
        const icon = n > 0 ? <RiseOutlined /> : <FallOutlined />
        return <Tag color={n > 0 ? 'red' : 'green'} icon={icon}>{n > 0 ? '+' : ''}{n.toFixed(1)}%</Tag>
      },
    },
  ]

  return (
    <Spin spinning={loadingScenarios || comparing}>
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-primary-700 mb-2"><ApartmentOutlined className="mr-3" />D1. Decision Impact Scenarios</h1>
        <p className="text-gray-600">Analyze how decisions impact key performance indicators</p>
      </div>

      <Card title="Available Scenarios">
        <Table columns={scenarioColumns} dataSource={scenarios} pagination={{ pageSize: 5 }} size="small" rowKey="scenario_id" />
      </Card>

      <Card title="Compare Runs">
        <div className="flex items-center gap-4 flex-wrap">
          <div><span className="mr-2">Base Run:</span><InputNumber min={1} value={baseRunId} onChange={setBaseRunId} /></div>
          <div><span className="mr-2">Compare Run:</span><InputNumber min={1} value={compareRunId} onChange={setCompareRunId} /></div>
          <Button type="primary" icon={<ThunderboltOutlined />} onClick={runCompare} disabled={!baseRunId || !compareRunId}>Analyze Impact</Button>
        </div>
      </Card>

      {comparison && (
        <>
          <Card title="Impact Analysis">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={impactData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="kpi" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="impact" fill="#1890ff" name="Absolute Impact" />
                <Bar dataKey="pctChange" fill="#f5222d" name="% Change" />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card title="Detailed Impact">
            <Table columns={impactColumns} dataSource={deltas} pagination={false} size="middle" rowKey="kpi_name" />
          </Card>
        </>
      )}

      {!comparison && !comparing && (
        <Alert message="Select two run IDs above and click Analyze Impact to see decision impact analysis" type="info" showIcon />
      )}
    </div>
    </Spin>
  )
}

export default DecisionImpactScenarios
