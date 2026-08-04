import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Card, Row, Col, Statistic, Tag, Alert, Spin, Select, Button, Table, Divider,
  Tabs, Space, Badge, Empty, Typography,
} from 'antd'
import {
  DashboardOutlined, DollarOutlined, CheckCircleOutlined, ClockCircleOutlined,
  ReloadOutlined, RiseOutlined, FallOutlined, SafetyOutlined, BarChartOutlined,
  WarningOutlined, TableOutlined, ShopOutlined,
} from '@ant-design/icons'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell,
  ComposedChart, Line, ReferenceLine, PieChart, Pie,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import { useAppContext } from '../context/AppContext'
import optimizationService from '../services/optimizationService'
import PageHeader from '../components/PageHeader'
import { BRAND, NEUTRAL, SEMANTIC, SI_COLORS, COST_COLORS, CHART_GRID } from '../theme/tokens'

const { Text } = Typography
const { Option } = Select

// ── Colors (unified from design tokens) ─────────────
const COLORS = {
  q: BRAND[500], r: BRAND[300], inv: NEUTRAL[700],
  bo: SEMANTIC.bad, o: BRAND[400], s: SEMANTIC.warn,
  safe: SI_COLORS.safe, risk: SI_COLORS.risk, warn: SI_COLORS.warn,
}
const PIE_COLORS = [SI_COLORS.safe, SI_COLORS.warn, SI_COLORS.risk]
// Order matches costRows: backorder, overstock, shortage, packing penalty, lateral transshipment
const COST_BAR_COLORS = [COST_COLORS.backorder, COST_COLORS.overstock, COST_COLORS.shortage, COST_COLORS.penalty, COST_COLORS.transship]
const fmt = (v, d = 0) =>
  typeof v === 'number' ? v.toLocaleString('en-US', { maximumFractionDigits: d }) : '—'

// Custom tooltip for the decision variables chart
const VarTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-200 rounded p-3 shadow-lg text-xs">
      <p className="font-semibold mb-1">Period {label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {p.name}: <strong>{fmt(p.value, 1)}</strong>
        </p>
      ))}
    </div>
  )
}

const ExecutiveSummary = () => {
  const { activeRunId, setActiveRunId } = useAppContext()
  const [runs, setRuns] = useState([])
  const [runsLoading, setRunsLoading] = useState(true)

  const fetchRuns = () => {
    setRunsLoading(true)
    optimizationService.listRuns()
      .then((res) => {
        // API interceptor already unwraps body: res IS the array directly
        const list = Array.isArray(res) ? res : (res?.runs ?? [])
        setRuns(list)
        if (!activeRunId && list.length > 0) setActiveRunId(list[0].run_id)
      })
      .catch(() => setRuns([]))
      .finally(() => setRunsLoading(false))
  }

  useEffect(() => { fetchRuns() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const { data, loading, error } = useApi(
    () => activeRunId ? optimizationService.getExecutiveSummary(activeRunId) : Promise.resolve(null),
    [activeRunId]
  )

  const { data: extData, loading: extLoading } = useApi(
    () => activeRunId ? optimizationService.getSummaryExtended(activeRunId) : Promise.resolve(null),
    [activeRunId]
  )

  const runOptions = runs.map((r) => ({
    value: r.run_id,
    label: `Run #${r.run_id} — ${r.solver_status} (objective: ${Number(r.objective_value ?? 0).toLocaleString('en-US')})`,
  }))

  const summary = data || {}
  const run     = summary.run  || {}
  const kpis    = summary.kpis || {}
  const ext     = extData      || {}

  const totalCost  = Number(kpis.total_cost) || 0
  const baselineCost = Number(ext.baseline_cost) || 0
  const optCost    = Number(ext.opt_cost) || totalCost
  const savingsAmt = Number(ext.savings)  || (baselineCost - optCost)
  const savingsPct = ext.savings_pct
    ? Number(ext.savings_pct)
    : (baselineCost > 0 ? (savingsAmt / baselineCost * 100) : 0)
  // ── Cost analysis table ────────────────────────────
  const costRows = [
    { key: 'backorder', name: 'Backorder Cost',            value: Number(kpis.cost_backorder) || 0 },
    { key: 'overstock', name: 'Overstock Cost',             value: Number(kpis.cost_overstock) || 0 },
    { key: 'shortage',  name: 'Shortage Cost',              value: Number(kpis.cost_shortage)  || 0 },
    { key: 'penalty',   name: 'Packing Penalty Cost',       value: Number(kpis.cost_penalty)   || 0 },
    { key: 'transport', name: 'Lateral Transshipment Cost', value: Number(kpis.cost_transport) || 0 },
  ].map((r) => ({ ...r, pct: totalCost > 0 ? (r.value / totalCost * 100) : 0 }))

  const costColumns = [
    {
      title: 'Cost Component', dataIndex: 'name', key: 'name',
      render: (t) => <span className="font-medium">{t}</span>,
    },
    {
      title: 'Optimal Cost', dataIndex: 'value', key: 'value', align: 'right',
      render: (v) => <span className="font-semibold">{fmt(v, 2)}</span>,
      sorter: (a, b) => a.value - b.value,
    },
    {
      title: '% of Total', dataIndex: 'pct', key: 'pct', align: 'right',
      render: (v) => <Tag color={v > 50 ? 'red' : v > 20 ? 'orange' : 'blue'}>{v.toFixed(2)}%</Tag>,
      sorter: (a, b) => a.pct - b.pct,
    },
  ]

  const costBarData = costRows.map((r) => ({
    name: r.name.replace(' Cost', '').trim(),
    'Cost': r.value,
  }))

  const compareBarData = baselineCost > 0
    ? [{ name: 'Comparison', 'Baseline': baselineCost, 'MA Optimal': optCost }]
    : []

  // ── Warehouse cost breakdown ──────────────────────────
  const [whCostData, setWhCostData]   = useState([])
  const [whCostLoading, setWhCostLoading] = useState(false)
  const [whFilter, setWhFilter]       = useState([])  // [] = all

  useEffect(() => {
    if (!activeRunId) return
    setWhCostLoading(true)
    optimizationService.getCostByWarehouse(activeRunId)
      .then((res) => setWhCostData(res?.warehouses ?? []))
      .catch(() => setWhCostData([]))
      .finally(() => setWhCostLoading(false))
  }, [activeRunId])

  const filteredWhCost = whFilter.length > 0
    ? whCostData.filter((w) => whFilter.includes(w.warehouse_id))
    : whCostData

  const whCostChartData = filteredWhCost.map((w) => ({
    name: w.warehouse_id,
    'Backorder': w.cost_backorder,
    'Overstock': w.cost_overstock,
    'Shortage': w.cost_shortage,
    'Packing Violation': w.cost_penalty,
  }))

  // ── B3: State & logic for variable & SI/SS details ───────
  const [varLoading, setVarLoading] = useState(false)
  const [varError, setVarError]     = useState(null)
  const [variables, setVariables]   = useState([])
  const [siSs, setSiSs]             = useState([])
  const [changes, setChanges]       = useState([])
  const [products, setProducts]     = useState([])
  const [selectedProduct, setSelectedProduct]     = useState(null)
  const [warehouses, setWarehouses]               = useState([])
  const [selectedWarehouse, setSelectedWarehouse] = useState(null)

  const loadVarData = useCallback(async () => {
    if (!activeRunId) return
    setVarLoading(true)
    setVarError(null)
    try {
      const [varRes, siRes, chgRes] = await Promise.all([
        optimizationService.getVariables(activeRunId),
        optimizationService.getSiSs(activeRunId),
        optimizationService.getChangesDetail(activeRunId),
      ])
      // API interceptor already unwraps body: varRes IS {run_id, variables, total}
      const vars = varRes?.variables ?? varRes?.data?.variables ?? []
      setVariables(vars)
      const prods = [...new Set(vars.map((v) => v.product_id))].sort()
      const whs   = [...new Set(vars.map((v) => v.warehouse_id))].sort()
      setProducts(prods)
      setWarehouses(whs)
      setSelectedProduct((prev) => prods.includes(prev) ? prev : (prods[0] ?? null))
      setSiSs(siRes?.records ?? siRes?.data?.records ?? [])
      setChanges(chgRes?.changes ?? chgRes?.data?.changes ?? [])
    } catch {
      setVarError('Unable to load variable data. Please make sure an optimization run has completed.')
    } finally {
      setVarLoading(false)
    }
  }, [activeRunId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { loadVarData() }, [loadVarData])

  const filteredVars = useMemo(
    () => variables.filter(
      (v) =>
        (!selectedProduct   || v.product_id   === selectedProduct) &&
        (!selectedWarehouse  || v.warehouse_id  === selectedWarehouse),
    ),
    [variables, selectedProduct, selectedWarehouse],
  )

  const varChartData = useMemo(() => {
    const byPeriod = {}
    filteredVars.forEach((v) => {
      const key = v.time_period
      if (!byPeriod[key]) byPeriod[key] = { period: key, q: 0, r: 0, inv: 0, bo: 0, o: 0, s: 0 }
      byPeriod[key].q   += v.q
      byPeriod[key].r   += v.r
      byPeriod[key].inv += v.inv
      byPeriod[key].bo  += v.bo
      byPeriod[key].o   += v.o
      byPeriod[key].s   += v.s
    })
    return Object.values(byPeriod).sort((a, b) => a.period - b.period)
  }, [filteredVars])

  const siHistData = useMemo(() => {
    const bins = {}
    siSs.forEach(({ si }) => {
      const bin   = Math.floor(si * 5) / 5
      const label = bin.toFixed(1)
      bins[label] = (bins[label] ?? 0) + 1
    })
    return Object.entries(bins)
      .sort(([a], [b]) => parseFloat(a) - parseFloat(b))
      .map(([si, count]) => ({ si, count }))
  }, [siSs])

  const pieSafeData = useMemo(() => {
    let safe = 0, warn = 0, risk = 0
    siSs.forEach(({ si }) => {
      if (si >= 1) safe++
      else if (si >= 0.8) warn++
      else risk++
    })
    return [
      { name: 'Safe (SI≥1)',           value: safe },
      { name: 'Warning (0.8≤SI<1)',   value: warn },
      { name: 'At Risk (SI<0.8)',      value: risk },
    ].filter((d) => d.value > 0)
  }, [siSs])

  const changeColumns = [
    { title: 'Product',       dataIndex: 'product_id',   key: 'product_id',   width: 110,
      sorter: (a, b) => a.product_id.localeCompare(b.product_id) },
    { title: 'Warehouse',      dataIndex: 'warehouse_id', key: 'warehouse_id', width: 80 },
    { title: 'Period',         dataIndex: 'time_period',  key: 'time_period',  width: 60,
      sorter: (a, b) => a.time_period - b.time_period },
    { title: 'q (cases)',      dataIndex: 'q',             key: 'q',            width: 90,
      align: 'right', render: (v) => <span className="tabular-nums">{v}</span> },
    { title: 'r (units)',      dataIndex: 'r',             key: 'r',            width: 110,
      align: 'right', render: (v) => <span className="tabular-nums">{v}</span> },
    { title: 'Net Inventory', dataIndex: 'inv',            key: 'inv',          width: 110,
      align: 'right', render: (v) => <span className="tabular-nums">{fmt(v, 1)}</span> },
    { title: 'Shortage',      dataIndex: 'shortage_qty',  key: 'shortage_qty', width: 100,
      align: 'right',
      render: (v) => v > 0
        ? <span className="tabular-nums font-medium" style={{ color: SEMANTIC.badText }}>{fmt(v, 1)}</span>
        : <span className="tabular-nums" style={{ color: NEUTRAL[400] }}>0</span> },
  ]

  return (
    <Spin spinning={loading || extLoading || runsLoading}>
      <div className="space-y-6">
        {error && (
          <Alert message="Error loading data" description={String(error)} type="error" showIcon closable />
        )}

        {/* ── Title & run selector ── */}
        <PageHeader
          icon={<DashboardOutlined />}
          title="B2. Results & Cost"
          subtitle={<>Scenario: <strong>{run.scenario_name || run.scenario_id || '—'}</strong></>}
          extra={
            <div className="flex items-center gap-2 flex-wrap">
              <Select
                style={{ minWidth: 340 }}
                options={runOptions}
                value={activeRunId}
                onChange={(val) => setActiveRunId(val)}
                placeholder="Select a run"
                loading={runsLoading}
              />
              <Button icon={<ReloadOutlined />} onClick={fetchRuns} title="Refresh" />
              <Tag color={
                /^optimal$/i.test(run.solver_status) ? 'green'
                : /^feasible$/i.test(run.solver_status) ? 'orange' : 'red'
              }>
                {run.solver_status || '—'}
              </Tag>
            </div>
          }
        />

        {/* ── KPI Cards (5 evenly split cards) ── */}
        <Row gutter={16} align="stretch">
          <Col flex="1">
            <Card className="h-full">
              <Statistic
                title="Baseline Cost (current state)"
                value={baselineCost}
                formatter={(v) => fmt(v, 0)}
                prefix={<DollarOutlined />}
                valueStyle={{ color: NEUTRAL[600] }}
              />
              <div className="text-xs text-gray-400 mt-1">
                Cost without optimization
              </div>
            </Card>
          </Col>
          <Col flex="1">
            <Card className="h-full">
              <Statistic
                title="Total Optimal Cost"
                value={totalCost}
                formatter={(v) => fmt(v, 0)}
                prefix={<DollarOutlined />}
                valueStyle={{ color: BRAND[600] }}
              />
              <div className="text-xs text-gray-400 mt-1">
                MA objective function value
              </div>
            </Card>
          </Col>
          <Col flex="1">
            <Card className="h-full">
              <Statistic
                title="Service Level"
                value={Number(kpis.service_level) || 0}
                precision={1}
                suffix="%"
                valueStyle={{ color: SEMANTIC.good }}
                prefix={<CheckCircleOutlined />}
              />
              <div className="text-xs text-gray-400 mt-1">
                Demand fulfillment rate
              </div>
            </Card>
          </Col>
          <Col flex="1">
            <Card className="h-full">
              <Statistic
                title="Savings vs Baseline"
                value={savingsPct}
                precision={2}
                suffix="%"
                prefix={savingsPct >= 0 ? <RiseOutlined /> : <FallOutlined />}
                valueStyle={{ color: savingsPct >= 0 ? SEMANTIC.good : SEMANTIC.bad }}
              />
              <div className="text-xs text-gray-400 mt-1">
                Savings: {fmt(savingsAmt, 0)}
              </div>
            </Card>
          </Col>
          <Col flex="1">
            <Card className="h-full">
              <Statistic
                title="Solve Time"
                value={Number(run.solve_time_seconds) || 0}
                precision={2}
                suffix="s"
                prefix={<ClockCircleOutlined />}
              />
              <div className="text-xs text-gray-400 mt-1">
                Algorithm: Memetic (GA-ALNS)
              </div>
            </Card>
          </Col>
        </Row>

        {/* ── Main tabs ── */}
        <Tabs
          defaultActiveKey="cost"
          items={[
            {
              key: 'cost',
              label: <span><BarChartOutlined /> Cost Analysis</span>,
              children: (
                <div className="space-y-4">
                  <Card title={<span className="text-lg font-bold"><BarChartOutlined className="mr-2" />COST ANALYSIS</span>}>
                    <Row gutter={24}>
                      <Col xs={24} lg={12}>
                        <Table
                          columns={[
                            { title: 'Cost Component', dataIndex: 'name', key: 'name',
                              render: (t) => <span className="font-medium">{t}</span> },
                            { title: 'Optimal Cost', dataIndex: 'value', key: 'value', align: 'right',
                              render: (v) => <span className="font-semibold">{fmt(v, 2)}</span>,
                              sorter: (a, b) => a.value - b.value },
                            { title: '% of Total', dataIndex: 'pct', key: 'pct', align: 'right',
                              render: (v) => <Tag color={v > 50 ? 'red' : v > 20 ? 'orange' : 'blue'}>{v.toFixed(2)}%</Tag>,
                              sorter: (a, b) => a.pct - b.pct },
                          ]}
                          dataSource={costRows}
                          rowKey="key"
                          pagination={false}
                          size="middle"
                          className="mb-4"
                          summary={() => (
                            <Table.Summary.Row style={{ fontWeight: 'bold', background: NEUTRAL[50] }}>
                              <Table.Summary.Cell index={0}><strong>TOTAL</strong></Table.Summary.Cell>
                              <Table.Summary.Cell index={1} align="right"><strong>{fmt(totalCost, 2)}</strong></Table.Summary.Cell>
                              <Table.Summary.Cell index={2} align="right"><strong>100%</strong></Table.Summary.Cell>
                            </Table.Summary.Row>
                          )}
                        />
                        {baselineCost > 0 && (
                          <div className="p-4 rounded-lg" style={{ background: NEUTRAL[50], border: `1px solid ${NEUTRAL[200]}` }}>
                            <h4 className="font-semibold mb-3" style={{ color: NEUTRAL[700] }}>
                              <RiseOutlined className="mr-1" style={{ color: SEMANTIC.good }} />Comparison with Baseline Cost (current state)
                            </h4>
                            <div className="space-y-2 text-sm">
                              <div className="flex justify-between">
                                <span style={{ color: NEUTRAL[500] }}>Baseline Cost (current state):</span>
                                <span className="font-semibold tabular-nums" style={{ color: NEUTRAL[700] }}>{fmt(baselineCost, 2)}</span>
                              </div>
                              <div className="flex justify-between">
                                <span style={{ color: NEUTRAL[500] }}>Optimal Cost:</span>
                                <span className="font-semibold tabular-nums" style={{ color: NEUTRAL[700] }}>{fmt(optCost, 2)}</span>
                              </div>
                              <Divider className="my-2" />
                              <div className="flex justify-between text-base">
                                <span className="font-bold" style={{ color: SEMANTIC.goodText }}>Savings:</span>
                                <span className="font-bold tabular-nums" style={{ color: SEMANTIC.goodText }}>
                                  {fmt(savingsAmt, 2)} ({savingsPct.toFixed(2)}%)
                                </span>
                              </div>
                            </div>
                          </div>
                        )}
                      </Col>
                      <Col xs={24} lg={12}>
                        <p className="text-sm font-semibold text-gray-600 mb-2">Optimal Cost Component Chart</p>
                        <ResponsiveContainer width="100%" height={210}>
                          <BarChart data={costBarData} margin={{ top: 5, right: 10, bottom: 50, left: 10 }}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="name" angle={-28} textAnchor="end" interval={0} tick={{ fontSize: 11 }} />
                            <YAxis tickFormatter={(v) => v.toLocaleString('en-US')} width={80} tick={{ fontSize: 10 }} />
                            <Tooltip formatter={(v) => [fmt(v, 2), 'Cost']} />
                            <Bar dataKey="Cost" radius={[4, 4, 0, 0]}>
                              {costBarData.map((_, i) => <Cell key={i} fill={COST_BAR_COLORS[i % COST_BAR_COLORS.length]} />)}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                        {compareBarData.length > 0 && (
                          <>
                            <p className="text-sm font-semibold text-gray-600 mt-4 mb-2">Total Comparison: Baseline vs MA Optimal</p>
                            <ResponsiveContainer width="100%" height={160}>
                              <BarChart data={compareBarData} layout="vertical" margin={{ left: 10, right: 80 }}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis type="number" tickFormatter={(v) => v.toLocaleString('en-US')} tick={{ fontSize: 10 }} />
                                <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={70} />
                                <Tooltip formatter={(v) => [fmt(v, 2)]} />
                                <Legend />
                                <Bar dataKey="Baseline" fill={NEUTRAL[400]} radius={[0, 4, 4, 0]} />
                                <Bar dataKey="MA Optimal"  fill={BRAND[500]} radius={[0, 4, 4, 0]} />
                              </BarChart>
                            </ResponsiveContainer>
                          </>
                        )}
                      </Col>
                    </Row>
                  </Card>

                  <Card title={<><SafetyOutlined className="mr-2" />Run Details</>}>
                    <Row gutter={24}>
                      <Col span={12}>
                        <div className="space-y-0 text-sm">
                          {[
                            ['Objective Value',  fmt(Number(run.objective_value || 0))],
                            ['Algorithm',        'Memetic (GA-ALNS)'],
                            ['Number of Products', summary.product_count || 0],
                            ['Number of Warehouses', summary.warehouse_count || 0],
                            ['Number of Periods', summary.period_count || 0],
                          ].map(([label, val]) => (
                            <div key={label} className="flex justify-between py-2 border-b last:border-0">
                              <span className="text-gray-500">{label}:</span>
                              <span className="font-medium">{val}</span>
                            </div>
                          ))}
                        </div>
                      </Col>
                      <Col span={12}>
                        <div className="space-y-0 text-sm">
                          {[
                            ['Total Result Records', summary.result_count || 0,   null],
                            ['Backorder Cost',              Number(kpis.cost_backorder || 0).toLocaleString('en-US'), COST_COLORS.backorder],
                            ['Overstock Cost',              Number(kpis.cost_overstock || 0).toLocaleString('en-US'), COST_COLORS.overstock],
                            ['Shortage Cost',               Number(kpis.cost_shortage  || 0).toLocaleString('en-US'), COST_COLORS.shortage],
                            ['Packing Penalty Cost',        Number(kpis.cost_penalty   || 0).toLocaleString('en-US'), COST_COLORS.penalty],
                            ['Lateral Transshipment Cost',  Number(kpis.cost_transport || 0).toLocaleString('en-US'), COST_COLORS.transship],
                          ].map(([label, val, dot]) => (
                            <div key={label} className="flex justify-between items-center py-2 border-b last:border-0">
                              <span className="flex items-center" style={{ color: NEUTRAL[500] }}>
                                {dot && <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: dot }} />}
                                {label}:
                              </span>
                              <span className="font-medium tabular-nums" style={{ color: NEUTRAL[700] }}>{val}</span>
                            </div>
                          ))}
                        </div>
                      </Col>
                    </Row>
                  </Card>
                </div>
              ),
            },
            {
              key: 'vars',
              label: (
                <span>
                  <BarChartOutlined /> Decision Variables &amp; SI/SS
                  {changes.length > 0 && <Badge count={changes.length} size="small" style={{ marginLeft: 6 }} />}
                </span>
              ),
              children: (
                <Spin spinning={varLoading}>
                  {varError && <Alert type="error" message={varError} showIcon className="mb-4" />}

                  {/* Average SI from extended summary */}
                  {ext && ext.si_mean != null && (
                    <Row gutter={16} className="mb-4" align="stretch">
                      <Col xs={24} sm={12} md={8}>
                        <Card size="small" className="h-full">
                          <Statistic title="Average SI" value={ext.si_mean} precision={3}
                            prefix={<SafetyOutlined />}
                            valueStyle={{ color: (ext.si_mean ?? 0) >= 1 ? COLORS.safe : COLORS.risk }} />
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {ext.ss_below_count} cells below SS threshold &nbsp;|&nbsp; {ext.n_changes} unit changes
                          </Text>
                        </Card>
                      </Col>
                      <Col xs={24} sm={12} md={16}>
                        <Card size="small" className="h-full" style={{ background: NEUTRAL[50] }}>
                          <Text style={{ fontSize: 12.5, color: NEUTRAL[600], lineHeight: 1.6 }}>
                            <strong>SI (Safety Index)</strong> = Actual Inventory ÷ Minimum Inventory Threshold (floor level).
                            SI ≥ 1: inventory meets or exceeds the safe level. SI &lt; 1: inventory is below the recommended threshold, with a risk of shortage.
                            The closer the average SI is to or above 1, the safer the system.
                          </Text>
                        </Card>
                      </Col>
                    </Row>
                  )}

                  <Card>
                    <Tabs defaultActiveKey="decision">
                      <Tabs.TabPane tab={<span><BarChartOutlined /> Decision Variables</span>} key="decision">
                        <Space wrap className="mb-3">
                          <Text strong>Product:</Text>
                          <Select style={{ width: 160 }} value={selectedProduct} onChange={setSelectedProduct}
                            showSearch filterOption={(input, opt) =>
                              String(opt.children).toLowerCase().includes(input.toLowerCase())}>
                            {products.map((p) => <Option key={p} value={p}>{p}</Option>)}
                          </Select>
                          <Text strong>Warehouse:</Text>
                          <Select style={{ width: 110 }} value={selectedWarehouse} onChange={setSelectedWarehouse}
                            allowClear placeholder="All">
                            {warehouses.map((w) => <Option key={w} value={w}>{w}</Option>)}
                          </Select>
                        </Space>
                        {varChartData.length === 0
                          ? <Empty description="No data for this selection" />
                          : (
                            <Row gutter={16}>
                              <Col xs={24} xl={12}>
                                <Text strong className="block mb-1">q (cases) and r (units) allocation by period</Text>
                                <Text type="secondary" style={{ fontSize: 12 }} className="block mb-2">
                                  Includes only allocation from the central warehouse (OA) — excludes lateral transshipment (PLT) between warehouses
                                </Text>
                                <ResponsiveContainer width="100%" height={280}>
                                  <BarChart data={varChartData} margin={{ bottom: 20 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="period" label={{ value: 'Period', position: 'insideBottom', offset: -14 }} />
                                    <YAxis />
                                    <Tooltip content={<VarTooltip />} />
                                    <Legend wrapperStyle={{ paddingTop: 8 }} />
                                    <Bar dataKey="q" name="q (cases)" fill={COLORS.q} stackId="a" />
                                    <Bar dataKey="r" name="r (units)"   fill={COLORS.r} stackId="a" />
                                  </BarChart>
                                </ResponsiveContainer>
                              </Col>
                              <Col xs={24} xl={12}>
                                <Text strong className="block mb-1">Inventory (I), overstock and shortage</Text>
                                <Text type="secondary" style={{ fontSize: 12 }} className="block mb-2">
                                  {selectedWarehouse
                                    ? `Shown for warehouse ${selectedWarehouse} only`
                                    : 'Aggregated across all warehouses — select a specific warehouse in the filter above to view it separately'}
                                </Text>
                                <ResponsiveContainer width="100%" height={280}>
                                  <ComposedChart data={varChartData} margin={{ bottom: 20 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="period" label={{ value: 'Period', position: 'insideBottom', offset: -14 }} />
                                    <YAxis />
                                    <Tooltip content={<VarTooltip />} />
                                    <Legend wrapperStyle={{ paddingTop: 8 }} />
                                    <Bar  dataKey="bo"  name="Backorder (bo)"  fill={COLORS.bo} />
                                    <Bar  dataKey="o"   name="Overstock (o)"    fill={COLORS.o}  />
                                    <Bar  dataKey="s"   name="Shortage (s)"   fill={COLORS.s}  />
                                    <Line type="monotone" dataKey="inv" name="Net Inventory (I)"
                                          stroke={COLORS.inv} strokeWidth={2} dot={false} />
                                  </ComposedChart>
                                </ResponsiveContainer>
                              </Col>
                            </Row>
                          )
                        }
                      </Tabs.TabPane>

                      <Tabs.TabPane tab={<span><SafetyOutlined /> SI / SS Index</span>} key="siss">
                        {siSs.length === 0
                          ? <Empty description="No SI/SS data available" />
                          : (
                            <Row gutter={16}>
                              <Col xs={24} lg={14}>
                                <Text strong className="block mb-2">
                                  Safety Index Distribution (SI = inventory / floor level)
                                </Text>
                                <ResponsiveContainer width="100%" height={280}>
                                  <BarChart data={siHistData}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="si" label={{ value: 'SI', position: 'insideBottom', offset: -2 }} />
                                    <YAxis label={{ value: 'Cell Count', angle: -90, position: 'insideLeft' }} />
                                    <Tooltip formatter={(v) => [v, 'Cell Count']} />
                                    <ReferenceLine x="1.0" stroke={SI_COLORS.risk} strokeDasharray="4 4"
                                      label={{ value: 'SI=1', fill: SI_COLORS.risk, fontSize: 11 }} />
                                    <Bar dataKey="count" name="Cell Count" fill={COLORS.warn} isAnimationActive={false}>
                                      {siHistData.map((entry) => (
                                        <Cell key={entry.si}
                                          fill={parseFloat(entry.si) >= 1 ? COLORS.safe
                                            : parseFloat(entry.si) >= 0.8 ? COLORS.warn : COLORS.risk} />
                                      ))}
                                    </Bar>
                                  </BarChart>
                                </ResponsiveContainer>
                              </Col>
                              <Col xs={24} lg={10}>
                                <Text strong className="block mb-2">Safety Level Proportions</Text>
                                <ResponsiveContainer width="100%" height={280}>
                                  <PieChart>
                                    <Pie data={pieSafeData} cx="50%" cy="50%" outerRadius={90} dataKey="value"
                                      label={({ name, percent }) => `${(percent * 100).toFixed(1)}%`}
                                      labelLine={false}>
                                      {pieSafeData.map((_, idx) => (
                                        <Cell key={idx} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                                      ))}
                                    </Pie>
                                    <Tooltip formatter={(v, n) => [v, n]} />
                                    <Legend />
                                  </PieChart>
                                </ResponsiveContainer>
                              </Col>
                            </Row>
                          )
                        }
                      </Tabs.TabPane>

                      <Tabs.TabPane
                        tab={(
                          <span>
                            <TableOutlined /> Unit Changes
                            {changes.length > 0 && <Badge count={changes.length} style={{ marginLeft: 6 }} />}
                          </span>
                        )}
                        key="changes"
                      >
                        <Table
                          dataSource={changes}
                          columns={changeColumns}
                          rowKey={(r) => `${r.product_id}-${r.warehouse_id}-${r.time_period}`}
                          size="small"
                          pagination={{ pageSize: 20 }}
                          scroll={{ x: 700 }}
                          locale={{ emptyText: 'No unit changes (r=0 and p=0)' }}
                        />
                      </Tabs.TabPane>
                    </Tabs>
                  </Card>
                </Spin>
              ),
            },
            {
              key: 'whcost',
              label: <span><ShopOutlined /> Cost by Warehouse</span>,
              children: (
                <Spin spinning={whCostLoading}>
                  <Card title={<span className="text-lg font-bold"><ShopOutlined className="mr-2" />COST BY WAREHOUSE</span>}
                    extra={
                      <Space>
                        <Select mode="multiple" style={{ minWidth: 200 }} value={whFilter} onChange={setWhFilter}
                          allowClear placeholder="All warehouses" maxTagCount={2}>
                          {whCostData.map((w) => (
                            <Option key={w.warehouse_id} value={w.warehouse_id}>{w.warehouse_id}</Option>
                          ))}
                        </Select>
                        <Button size="small" onClick={() => setWhFilter([])}>All</Button>
                      </Space>
                    }>
                    <Row gutter={24}>
                      <Col xs={24} lg={14}>
                        <Table
                          dataSource={filteredWhCost}
                          rowKey="warehouse_id"
                          size="middle"
                          pagination={false}
                          columns={[
                            { title: 'Warehouse', dataIndex: 'warehouse_id', key: 'warehouse_id',
                              render: (v) => <span className="font-medium" style={{ color: NEUTRAL[700] }}>{v}</span> },
                            { title: 'Backorder', dataIndex: 'cost_backorder', key: 'cost_backorder',
                              align: 'right', render: (v) => fmt(v, 2),
                              sorter: (a, b) => a.cost_backorder - b.cost_backorder },
                            { title: 'Overstock', dataIndex: 'cost_overstock', key: 'cost_overstock',
                              align: 'right', render: (v) => fmt(v, 2) },
                            { title: 'Shortage', dataIndex: 'cost_shortage', key: 'cost_shortage',
                              align: 'right', render: (v) => fmt(v, 2) },
                            { title: 'Packing Penalty', dataIndex: 'cost_penalty', key: 'cost_penalty',
                              align: 'right', render: (v) => fmt(v, 2) },
                            { title: 'Total', dataIndex: 'total_cost', key: 'total_cost',
                              align: 'right', sorter: (a, b) => a.total_cost - b.total_cost,
                              render: (v) => <span className="font-bold">{fmt(v, 2)}</span> },
                            { title: '% of Total', dataIndex: 'pct_of_total', key: 'pct_of_total',
                              align: 'right',
                              render: (v) => <Tag color={v > 40 ? 'red' : v > 20 ? 'orange' : 'green'}>{v.toFixed(2)}%</Tag> },
                          ]}
                          summary={() => {
                            const totals = filteredWhCost.reduce((acc, w) => ({
                              bo: acc.bo + w.cost_backorder,
                              o: acc.o + w.cost_overstock,
                              s: acc.s + w.cost_shortage,
                              p: acc.p + w.cost_penalty,
                              t: acc.t + w.total_cost,
                            }), { bo: 0, o: 0, s: 0, p: 0, t: 0 })
                            return (
                              <Table.Summary.Row style={{ fontWeight: 'bold', background: NEUTRAL[50] }}>
                                <Table.Summary.Cell index={0}><strong>TOTAL</strong></Table.Summary.Cell>
                                <Table.Summary.Cell index={1} align="right">{fmt(totals.bo, 2)}</Table.Summary.Cell>
                                <Table.Summary.Cell index={2} align="right">{fmt(totals.o, 2)}</Table.Summary.Cell>
                                <Table.Summary.Cell index={3} align="right">{fmt(totals.s, 2)}</Table.Summary.Cell>
                                <Table.Summary.Cell index={4} align="right">{fmt(totals.p, 2)}</Table.Summary.Cell>
                                <Table.Summary.Cell index={5} align="right"><strong>{fmt(totals.t, 2)}</strong></Table.Summary.Cell>
                                <Table.Summary.Cell index={6} align="right"><strong>100%</strong></Table.Summary.Cell>
                              </Table.Summary.Row>
                            )
                          }}
                        />
                      </Col>
                      <Col xs={24} lg={10}>
                        <Text strong className="block mb-2">Cost Breakdown by Warehouse</Text>
                        {whCostChartData.length === 0
                          ? <Empty description="No data available" />
                          : (
                            <ResponsiveContainer width="100%" height={300}>
                              <BarChart data={whCostChartData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="name" />
                                <YAxis tickFormatter={(v) => v.toLocaleString('en-US')} width={80} tick={{ fontSize: 10 }} />
                                <Tooltip formatter={(v) => [fmt(v, 2), '']} />
                                <Legend />
                                <Bar dataKey="Backorder" fill={COST_COLORS.backorder} stackId="a" />
                                <Bar dataKey="Overstock" fill={COST_COLORS.overstock} stackId="a" />
                                <Bar dataKey="Shortage"  fill={COST_COLORS.shortage} stackId="a" />
                                <Bar dataKey="Packing Violation"   fill={COST_COLORS.penalty} stackId="a" />
                              </BarChart>
                            </ResponsiveContainer>
                          )
                        }
                      </Col>
                    </Row>
                  </Card>
                </Spin>
              ),
            },
          ]}
        />
      </div>
    </Spin>
  )
}

export default ExecutiveSummary
