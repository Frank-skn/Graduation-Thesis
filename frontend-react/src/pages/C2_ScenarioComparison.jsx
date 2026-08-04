import React, { useState, useEffect, useCallback } from 'react'
import { Card, Row, Col, Table, Tag, Button, Alert, Spin, Select } from 'antd'
import { SwapOutlined, BarChartOutlined, ReloadOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import scenarioService from '../services/scenarioService'
import optimizationService from '../services/optimizationService'
import PageHeader from '../components/PageHeader'
import { BRAND, NEUTRAL, SEMANTIC } from '../theme/tokens'

const { Option } = Select
const fmt = (v, d = 0) =>
  typeof v === 'number' ? v.toLocaleString('vi-VN', { maximumFractionDigits: d }) : '—'

// English labels for KPI names (matches the 7 KPIs returned by the backend)
const KPI_LABEL = {
  total_cost: 'Total Cost',
  total_backorder: 'Total Backorder',
  total_overstock: 'Total Overstock',
  total_shortage: 'Total Shortage',
  total_penalty: 'Total Packaging Penalty',
  service_level: 'Service Level',
  capacity_utilization: 'Capacity Utilization',
}
const kpiLabel = (name) => KPI_LABEL[name] || name

// KPIs where an increase = good (opposite of most other KPIs, which are costs/issues where an increase = bad)
const HIGHER_IS_BETTER = new Set(['service_level'])
// true if this change is GOOD for the system
const isGoodChange = (kpiName, pct) =>
  HIGHER_IS_BETTER.has(kpiName) ? pct > 0 : pct < 0

// English labels for scenario type (matches the 11 backend ScenarioTypes — see C1)
const TYPE_LABEL = {
  demand_surge: 'Demand increase',
  demand_drop: 'Demand decrease',
  capacity_expansion: 'Capacity expansion',
  capacity_disruption: 'Capacity disruption',
  cost_increase: 'Cost increase',
  cost_decrease: 'Cost decrease',
  safety_stock_loosen: 'Inventory threshold loosened',
  safety_stock_tighten: 'Inventory threshold tightened',
  new_product_introduction: 'New product',
  warehouse_closure: 'Warehouse closure',
  custom: 'Custom / Direct comparison',
}
const typeLabel = (t) => TYPE_LABEL[t] || t

const ScenarioComparison = () => {
  const [runs, setRuns]               = useState([])
  const [runsLoading, setRunsLoading] = useState(true)
  const [baseRunId, setBaseRunId]     = useState(null)
  const [compareRunId, setCompareRunId] = useState(null)
  const [data, setData]               = useState(null)
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState(null)

  const loadRuns = useCallback(() => {
    setRunsLoading(true)
    optimizationService.listRuns()
      .then((res) => {
        const list = Array.isArray(res) ? res : (res?.runs ?? [])
        setRuns(list)
      })
      .catch(() => setRuns([]))
      .finally(() => setRunsLoading(false))
  }, [])

  useEffect(() => { loadRuns() }, [loadRuns])

  const handleCompare = async () => {
    if (!baseRunId || !compareRunId) return
    setLoading(true)
    setError(null)
    try {
      const res = await scenarioService.compareWhatIf(baseRunId, compareRunId)
      setData(res?.data ?? res)
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const deltas = data?.deltas || []

  const chartData = deltas
    .filter((d) => Math.abs(Number(d.percent_change) || 0) >= 0.1)
    .map((d) => ({
      kpi: kpiLabel(d.kpi_name),
      'Base': Number(d.base_value) || 0,
      'Scenario': Number(d.whatif_value) || 0,
    }))

  // Summary: only list KPIs with a significant change (|%| >= 0.1)
  const summaryItems = deltas
    .filter((d) => Math.abs(Number(d.percent_change) || 0) >= 0.1)
    .map((d) => {
      const pct = Number(d.percent_change) || 0
      return {
        name: kpiLabel(d.kpi_name),
        pct,
        up: pct > 0,
        good: isGoodChange(d.kpi_name, pct),
        text: `${pct > 0 ? 'increased' : 'decreased'} ${Math.abs(pct).toFixed(1)}%`,
      }
    })

  const deltaColumns = [
    { title: 'KPI', dataIndex: 'kpi_name', key: 'kpi_name',
      render: (t) => <span className="font-semibold">{kpiLabel(t)}</span> },
    { title: 'Base', dataIndex: 'base_value', key: 'base_value', align: 'right',
      render: (v) => fmt(Number(v), 2) },
    { title: 'Scenario', dataIndex: 'whatif_value', key: 'whatif_value', align: 'right',
      render: (v) => fmt(Number(v), 2) },
    { title: 'Absolute Change', dataIndex: 'absolute_change', key: 'absolute_change', align: 'right',
      render: (v, record) => {
        const n = Number(v)
        const good = isGoodChange(record.kpi_name, n)
        return <span className="font-medium tabular-nums" style={{ color: n === 0 ? undefined : good ? SEMANTIC.goodText : SEMANTIC.badText }}>
          {n > 0 ? '+' : ''}{fmt(n, 2)}
        </span>
      }},
    { title: '% Change', dataIndex: 'percent_change', key: 'percent_change', align: 'right',
      render: (v, record) => {
        if (v == null) return <Tag color="default">N/A</Tag>
        const n = Number(v)
        const good = isGoodChange(record.kpi_name, n)
        const color = Math.abs(n) < 5 ? 'blue' : (good ? 'green' : 'red')
        const icon = n > 0 ? <ArrowUpOutlined /> : n < 0 ? <ArrowDownOutlined /> : null
        return <Tag color={color} icon={icon}>{n > 0 ? '+' : ''}{n.toFixed(1)}%</Tag>
      }},
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        icon={<SwapOutlined />}
        title="C2. Scenario Comparison"
        subtitle="Compare key performance indicators (KPIs) between two optimization runs"
      />

      {error && <Alert message="Error" description={error} type="error" showIcon closable onClose={() => setError(null)} />}

      <Card>
        <div className="flex items-end gap-4 flex-wrap">
          <div>
            <span className="text-gray-500 text-xs block mb-1">Base Run:</span>
            <Select
              style={{ width: 280 }}
              placeholder="Select base run"
              value={baseRunId}
              onChange={setBaseRunId}
              loading={runsLoading}
              showSearch
              filterOption={(input, opt) => String(opt.children).toLowerCase().includes(input.toLowerCase())}
            >
              {runs.map((r) => (
                <Option key={r.run_id} value={r.run_id}>
                  Run #{r.run_id} — {r.solver_status} ({fmt(r.objective_value)})
                </Option>
              ))}
            </Select>
          </div>
          <div>
            <span className="text-gray-500 text-xs block mb-1">Comparison Run (What-If):</span>
            <Select
              style={{ width: 280 }}
              placeholder="Select comparison run"
              value={compareRunId}
              onChange={setCompareRunId}
              loading={runsLoading}
              showSearch
              filterOption={(input, opt) => String(opt.children).toLowerCase().includes(input.toLowerCase())}
            >
              {runs.map((r) => (
                <Option key={r.run_id} value={r.run_id}>
                  Run #{r.run_id} — {r.solver_status} ({fmt(r.objective_value)})
                </Option>
              ))}
            </Select>
          </div>
          <Button
            type="primary"
            icon={<BarChartOutlined />}
            onClick={handleCompare}
            disabled={!baseRunId || !compareRunId}
            loading={loading}
          >
            Compare KPIs
          </Button>
          <Button icon={<ReloadOutlined />} onClick={loadRuns} title="Refresh list" />
        </div>
      </Card>

      <Spin spinning={loading}>
        {data && (
          <>
            <Row gutter={16}>
              <Col span={8}>
                <Card size="small">
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Scenario Type</p>
                    <Tag color="blue">{data.scenario_type ? typeLabel(data.scenario_type) : 'Unknown'}</Tag>
                  </div>
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small">
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Comparison Run</p>
                    <p className="font-semibold">#{baseRunId} → #{compareRunId}</p>
                  </div>
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small">
                  <div className="text-center">
                    <p className="text-sm text-gray-500">KPIs Compared</p>
                    <p className="text-xl font-bold">{deltas.length}</p>
                  </div>
                </Card>
              </Col>
            </Row>

            {summaryItems.length > 0 ? (
              <Card
                size="small"
                title={<span className="font-semibold" style={{ color: BRAND[700] }}>Summary of Changes vs. Base Run</span>}
                styles={{ header: { background: BRAND[50], borderBottom: `1px solid ${BRAND[100]}` } }}
              >
                <ul className="space-y-2 my-1">
                  {summaryItems.map((it) => (
                    <li key={it.name} className="flex items-center gap-2">
                      {it.up
                        ? <ArrowUpOutlined style={{ color: it.good ? SEMANTIC.good : SEMANTIC.bad }} />
                        : <ArrowDownOutlined style={{ color: it.good ? SEMANTIC.good : SEMANTIC.bad }} />}
                      <span className="font-medium">{it.name}</span>
                      <span className="text-gray-500">{it.up ? 'increased' : 'decreased'}</span>
                      <Tag color={it.good ? 'green' : 'red'} className="ml-auto">
                        {it.up ? '+' : '−'}{Math.abs(it.pct).toFixed(1)}%
                      </Tag>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : (
              <Alert
                message="No KPI changed significantly between the two runs."
                type="success"
                showIcon
              />
            )}

            {chartData.length > 0 && (
              <Card title={
                <span className="font-bold">
                  <BarChartOutlined className="mr-2" />KPI Comparison Chart
                  <span className="ml-2 font-normal text-xs text-gray-400">
                    (showing {chartData.length}/{deltas.length} KPIs with change ≥ 0.1%)
                  </span>
                </span>
              }>
                <ResponsiveContainer width="100%" height={340}>
                  <BarChart data={chartData} margin={{ bottom: 90 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="kpi" angle={-25} textAnchor="end" interval={0} height={80} tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={(v) => v.toLocaleString('vi-VN')} width={90} tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(v) => fmt(v, 2)} />
                    <Legend verticalAlign="bottom" wrapperStyle={{ paddingTop: 24 }} />
                    <Bar dataKey="Base"     fill={NEUTRAL[400]} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Scenario" fill={BRAND[500]} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            )}

            <Card title={<span className="font-bold">KPI Comparison Details</span>}>
              <Table
                columns={deltaColumns}
                dataSource={deltas}
                pagination={false}
                size="middle"
                rowKey="kpi_name"
              />
            </Card>
          </>
        )}

        {!data && !loading && (
          <Alert
            message="Select two runs and click Compare KPIs to see the results"
            type="info"
            showIcon
          />
        )}
      </Spin>
    </div>
  )
}

export default ScenarioComparison
