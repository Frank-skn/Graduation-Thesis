import { useState } from 'react'
import { Card, Table, Tag, Button, Alert, Spin } from 'antd'
import {
  ApartmentOutlined, ThunderboltOutlined, RiseOutlined, FallOutlined, CheckCircleOutlined,
} from '@ant-design/icons'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { useApi } from '../hooks/useApi'
import scenarioService from '../services/scenarioService'
import optimizationService from '../services/optimizationService'

const DecisionImpactScenarios = () => {
  const [baseRunId, setBaseRunId] = useState(null)
  const [compareRunId, setCompareRunId] = useState(null)

  const { data: runsData, loading: loadingRuns } = useApi(() => optimizationService.listRuns())
  const { data: comparison, loading: comparing, execute: runCompare } = useApi(
    () => baseRunId && compareRunId ? scenarioService.compareWhatIf(baseRunId, compareRunId) : Promise.resolve(null),
    [baseRunId, compareRunId],
    { immediate: false }
  )

  const runs = (runsData?.runs || runsData || [])
  const deltas = comparison?.deltas || []

  const impactData = deltas.map(d => ({
    kpi: d.kpi_name,
    impact: Number(d.absolute_change) || 0,
    pctChange: Number(d.percent_change) || 0,
  }))

  const runColumns = [
    { title: 'Run ID', dataIndex: 'run_id', key: 'run_id', width: 80, render: (v) => <span className="font-mono font-bold text-blue-600">{v}</span> },
    { title: 'Optimization Result', dataIndex: 'objective_value', key: 'objective_value', render: (v) => Number(v).toLocaleString('en-US') },
    { title: 'Status', dataIndex: 'solver_status', key: 'solver_status', render: (s) => <Tag color="green" icon={<CheckCircleOutlined />}>{s}</Tag> },
    { title: 'Run Time', dataIndex: 'run_time', key: 'run_time', render: (t) => t ? new Date(t).toLocaleString('en-US') : 'N/A' },
    {
      title: 'Select As',
      key: 'action',
      render: (_, record) => (
        <div className="flex gap-2">
          <Button
            size="small"
            type={baseRunId === record.run_id ? 'primary' : 'default'}
            onClick={() => setBaseRunId(record.run_id)}
          >
            Baseline
          </Button>
          <Button
            size="small"
            type={compareRunId === record.run_id ? 'primary' : 'default'}
            danger={compareRunId === record.run_id}
            onClick={() => setCompareRunId(record.run_id)}
          >
            Compare
          </Button>
        </div>
      ),
    },
  ]

  const impactColumns = [
    { title: 'KPI', dataIndex: 'kpi_name', key: 'kpi_name', render: (t) => <span className="font-semibold">{t}</span> },
    { title: 'Baseline', dataIndex: 'base_value', key: 'base_value', render: (v) => Number(v).toLocaleString('en-US') },
    { title: 'Scenario', dataIndex: 'whatif_value', key: 'whatif_value', render: (v) => Number(v).toLocaleString('en-US') },
    {
      title: 'Impact', dataIndex: 'percent_change', key: 'percent_change',
      render: (v) => {
        const n = Number(v)
        const icon = n > 0 ? <RiseOutlined /> : <FallOutlined />
        return <Tag color={n > 0 ? 'red' : 'green'} icon={icon}>{n > 0 ? '+' : ''}{n.toFixed(1)}%</Tag>
      },
    },
  ]

  const runLabel = (id) => {
    const r = runs.find(r => r.run_id === id)
    return r ? `Run #${r.run_id} (${Number(r.objective_value).toLocaleString('en-US')})` : `Run #${id}`
  }

  return (
    <Spin spinning={loadingRuns || comparing}>
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-primary-700 mb-2"><ApartmentOutlined className="mr-3" />D1. Allocation Decision Impact</h1>
        <p className="text-gray-600">Analyze the impact of decisions on performance metrics</p>
      </div>

      <Card
        title="Optimization Runs"
        extra={<span className="text-sm text-gray-400">Select two runs to compare using the buttons below</span>}
      >
        <Table
          columns={runColumns}
          dataSource={runs}
          pagination={{ pageSize: 5 }}
          size="small"
          rowKey="run_id"
          rowClassName={(record) => {
            if (record.run_id === baseRunId) return 'bg-blue-50'
            if (record.run_id === compareRunId) return 'bg-red-50'
            return ''
          }}
        />
      </Card>

      <Card title="Comparison">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-gray-500">Baseline:</span>
            {baseRunId
              ? <Tag color="blue">{runLabel(baseRunId)}</Tag>
              : <span className="text-gray-400 italic">Not selected</span>
            }
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-500">Compare:</span>
            {compareRunId
              ? <Tag color="red">{runLabel(compareRunId)}</Tag>
              : <span className="text-gray-400 italic">Not selected</span>
            }
          </div>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={runCompare}
            disabled={!baseRunId || !compareRunId || baseRunId === compareRunId}
          >
            Analyze Impact
          </Button>
          {baseRunId === compareRunId && baseRunId && (
            <span className="text-orange-500 text-sm">Please select two different runs</span>
          )}
        </div>
      </Card>

      {comparison && (
        <>
          <Card title="KPI Impact Chart">
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

          <Card title="Impact Details">
            <Table columns={impactColumns} dataSource={deltas} pagination={false} size="middle" rowKey="kpi_name" />
          </Card>
        </>
      )}

      {!comparison && !comparing && (
        <Alert
          message="Usage Guide"
          description="Select the baseline run and the comparison run from the table above by clicking the 'Baseline' and 'Compare' buttons, then click 'Analyze Impact' to view the results."
          type="info"
          showIcon
        />
      )}
    </div>
    </Spin>
  )
}

export default DecisionImpactScenarios
