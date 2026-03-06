import React, { useState } from 'react'
import { Card, Row, Col, Table, Tag, InputNumber, Button, Alert, Spin, Select } from 'antd'
import {
  SwapOutlined, BarChartOutlined,
} from '@ant-design/icons'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine } from 'recharts'
import { useApi } from '../hooks/useApi'
import scenarioService from '../services/scenarioService'

const ScenarioComparison = () => {
  const [baseRunId, setBaseRunId] = useState(null)
  const [compareRunId, setCompareRunId] = useState(null)

  const { data, loading, error, execute: compare } = useApi(
    () => baseRunId && compareRunId ? scenarioService.compareWhatIf(baseRunId, compareRunId) : Promise.resolve(null),
    [baseRunId, compareRunId],
    { immediate: false }
  )

  const deltas = data?.deltas || []

  const chartData = deltas.map(d => ({
    kpi: d.kpi_name,
    base: Number(d.base_value) || 0,
    whatif: Number(d.whatif_value) || 0,
    change: Number(d.percent_change) || 0,
  }))

  const deltaColumns = [
    { title: 'KPI', dataIndex: 'kpi_name', key: 'kpi_name', render: (t) => <span className="font-semibold">{t}</span> },
    { title: 'Base Value', dataIndex: 'base_value', key: 'base_value', render: (v) => Number(v).toLocaleString() },
    { title: 'What-If Value', dataIndex: 'whatif_value', key: 'whatif_value', render: (v) => Number(v).toLocaleString() },
    { title: 'Abs Change', dataIndex: 'absolute_change', key: 'absolute_change', render: (v) => { const n = Number(v); return <span className={n > 0 ? 'text-red-600' : 'text-green-600'}>{n > 0 ? '+' : ''}{n.toLocaleString()}</span> } },
    {
      title: '% Change', dataIndex: 'percent_change', key: 'percent_change',
      render: (v) => {
        const n = Number(v)
        return <Tag color={n > 5 ? 'red' : n < -5 ? 'green' : 'blue'}>{n > 0 ? '+' : ''}{n.toFixed(1)}%</Tag>
      },
    },
  ]

  return (
    <div className="space-y-6">
      {error && <Alert message="Error" description={error} type="error" showIcon closable />}
      <div>
        <h1 className="text-3xl font-bold text-primary-700 mb-2"><SwapOutlined className="mr-3" />C3. Scenario Comparison</h1>
        <p className="text-gray-600">Compare KPIs between two optimization runs</p>
      </div>

      <Card>
        <div className="flex items-center gap-4 flex-wrap">
          <div><span className="mr-2">Base Run ID:</span><InputNumber min={1} value={baseRunId} onChange={setBaseRunId} /></div>
          <div><span className="mr-2">Compare Run ID:</span><InputNumber min={1} value={compareRunId} onChange={setCompareRunId} /></div>
          <Button type="primary" icon={<BarChartOutlined />} onClick={compare} disabled={!baseRunId || !compareRunId} loading={loading}>Compare</Button>
        </div>
      </Card>

      {data && (
        <>
          <Row gutter={16}>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Scenario Type</p><Tag color="blue">{data.scenario_type || 'N/A'}</Tag></div></Card></Col>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Label</p><p className="font-semibold">{data.label || 'N/A'}</p></div></Card></Col>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">KPIs Compared</p><p className="text-xl font-bold">{deltas.length}</p></div></Card></Col>
          </Row>

          <Card title="KPI Comparison Chart">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="kpi" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="base" fill="#1890ff" name="Base" />
                <Bar dataKey="whatif" fill="#52c41a" name="What-If" />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card title="Detailed Comparison">
            <Table columns={deltaColumns} dataSource={deltas} pagination={false} size="middle" rowKey="kpi_name" />
          </Card>

          {data.summary && (
            <Alert message="Summary" description={data.summary} type="info" showIcon />
          )}
        </>
      )}

      {!data && !loading && (
        <Alert message="Select two run IDs and click Compare to see results" type="info" showIcon />
      )}
    </div>
  )
}

export default ScenarioComparison
