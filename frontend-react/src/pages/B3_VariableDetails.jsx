/**
 * B3 – Decision Variable Detail & SI/SS Indicators
 *
 * Visualization dashboard:
 *  Row 0 – Run selector
 *  Row 1 – KPI cards: baseline cost, optimal cost, savings, mean SI
 *  Row 2 – "Decision Variables" tab (select product → ComposedChart q/r/I/bo/o/s + bounds)
 *  Row 3 – "SI/SS Indicators" tab (BarChart SI distribution, PieChart safety ratio)
 *  Row 4 – Changes table (p=1 or r>0)
 */
import React, { useEffect, useState, useCallback } from 'react'
import {
  Card, Col, Row, Select, Statistic, Tabs, Table, Tag, Spin, Empty,
  Typography, Space, Alert, Badge,
} from 'antd'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, BarChart, PieChart, Pie, Cell,
  Scatter, ScatterChart, ZAxis,
} from 'recharts'
import {
  DollarOutlined, RiseOutlined, SafetyOutlined, WarningOutlined,
  BarChartOutlined, TableOutlined,
} from '@ant-design/icons'
import optimizationService from '../services/optimizationService'
import { useAppContext } from '../context/AppContext'
import { SEMANTIC, NEUTRAL } from '../theme/tokens'

const { Title, Text } = Typography
const { Option } = Select
const { TabPane } = Tabs

// ─────────────────────────────────────────────
// Colors
// ─────────────────────────────────────────────
const COLORS = {
  q:    '#2196F3',
  r:    '#03A9F4',
  inv:  '#4CAF50',
  bo:   '#F44336',
  o:    '#FF9800',
  s:    '#9C27B0',
  p:    '#607D8B',
  safe: '#52c41a',
  risk: '#ff4d4f',
  warn: '#faad14',
}

const PIE_COLORS = [COLORS.safe, COLORS.warn, COLORS.risk]

// ─────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────
const fmt = (v, d = 0) =>
  typeof v === 'number' ? v.toLocaleString('en-US', { maximumFractionDigits: d }) : '—'

const pct = (v) => `${Number(v).toFixed(1)}%`

// ─────────────────────────────────────────────
// Custom tooltip for ComposedChart
// ─────────────────────────────────────────────
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

// ─────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────
export default function B3_VariableDetails() {
  // ── State ────────────────────────────────
  const { activeRunId } = useAppContext()
  const [runs, setRuns] = useState([])
  const [runId, setRunId] = useState(null)
  const [summary, setSummary] = useState(null)
  const [variables, setVariables] = useState([])
  const [siSs, setSiSs] = useState([])
  const [changes, setChanges] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Variable filters
  const [products, setProducts] = useState([])
  const [selectedProduct, setSelectedProduct] = useState(null)
  const [warehouses, setWarehouses] = useState([])
  const [selectedWarehouse, setSelectedWarehouse] = useState(null)

  // ── Load run list ────────────────
  useEffect(() => {
    optimizationService.listRuns()
      .then((res) => {
        const list = res.data?.runs ?? res.data ?? []
        setRuns(list)
        // Prefer activeRunId from context, otherwise fall back to the first run
        const defaultId = activeRunId ?? (list.length > 0 ? (list[0].run_id ?? list[0].id) : null)
        setRunId(defaultId)
      })
      .catch(() => {})
  }, [activeRunId])

  // ── Load data when runId changes ───────
  const loadData = useCallback(async () => {
    if (!runId) return
    setLoading(true)
    setError(null)
    try {
      const [sumRes, varRes, siRes, chgRes] = await Promise.all([
        optimizationService.getSummaryExtended(runId),
        optimizationService.getVariables(runId),
        optimizationService.getSiSs(runId),
        optimizationService.getChangesDetail(runId),
      ])
      setSummary(sumRes.data)
      const vars = varRes.data?.variables ?? []
      setVariables(vars)
      // Get unique product & warehouse lists
      const prods = [...new Set(vars.map((v) => v.product_id))].sort()
      const whs   = [...new Set(vars.map((v) => v.warehouse_id))].sort()
      setProducts(prods)
      setWarehouses(whs)
      if (!selectedProduct || !prods.includes(selectedProduct)) setSelectedProduct(prods[0] ?? null)
      if (!selectedWarehouse || !whs.includes(selectedWarehouse)) setSelectedWarehouse(null)
      setSiSs(siRes.data?.records ?? [])
      setChanges(chgRes.data?.changes ?? [])
    } catch (e) {
      setError('Unable to load data. Make sure an optimization run has completed.')
    } finally {
      setLoading(false)
    }
  }, [runId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { loadData() }, [loadData])

  // ── Filter variables by selected product + warehouse ─
  const filteredVars = variables.filter(
    (v) =>
      (!selectedProduct  || v.product_id  === selectedProduct) &&
      (!selectedWarehouse || v.warehouse_id === selectedWarehouse),
  )

  // Prepare chart data: group by time_period (combining warehouses if needed)
  const varChartData = React.useMemo(() => {
    const byPeriod = {}
    filteredVars.forEach((v) => {
      const key = v.time_period
      if (!byPeriod[key]) byPeriod[key] = { period: key, q: 0, r: 0, inv: 0, bo: 0, o: 0, s: 0, p: 0 }
      byPeriod[key].q   += v.q
      byPeriod[key].r   += v.r
      byPeriod[key].inv += v.inv
      byPeriod[key].bo  += v.bo
      byPeriod[key].o   += v.o
      byPeriod[key].s   += v.s
      byPeriod[key].p   += v.p
    })
    return Object.values(byPeriod).sort((a, b) => a.period - b.period)
  }, [filteredVars])

  // ── SI histogram (bins 0..2) ───────────────
  const siHistData = React.useMemo(() => {
    const bins = {}
    ;(siSs).forEach(({ si }) => {
      const bin = Math.floor(si * 5) / 5  // 0.0, 0.2, 0.4 …
      const label = bin.toFixed(1)
      bins[label] = (bins[label] ?? 0) + 1
    })
    return Object.entries(bins)
      .sort(([a], [b]) => parseFloat(a) - parseFloat(b))
      .map(([si, count]) => ({ si, count }))
  }, [siSs])

  const pieSafeData = React.useMemo(() => {
    let safe = 0, warn = 0, risk = 0
    siSs.forEach(({ si }) => {
      if (si >= 1) safe++
      else if (si >= 0.8) warn++
      else risk++
    })
    return [
      { name: 'Safe (SI≥1)',            value: safe },
      { name: 'Warning (0.8≤SI<1)',    value: warn },
      { name: 'At risk (SI<0.8)',       value: risk },
    ].filter((d) => d.value > 0)
  }, [siSs])

  // ── Changes table ─────────────────────────
  const changeColumns = [
    { title: 'Product', dataIndex: 'product_id', key: 'product_id', width: 110,
      sorter: (a, b) => a.product_id.localeCompare(b.product_id) },
    { title: 'Warehouse', dataIndex: 'warehouse_id', key: 'warehouse_id', width: 80 },
    { title: 'Period', dataIndex: 'time_period', key: 'time_period', width: 60,
      sorter: (a, b) => a.time_period - b.time_period },
    { title: 'q (case-pack)', dataIndex: 'q', key: 'q', width: 90,
      align: 'right', render: (v) => <span className="tabular-nums">{v}</span> },
    { title: 'r (residual units)', dataIndex: 'r', key: 'r', width: 110,
      align: 'right', render: (v) => <span className="tabular-nums">{v}</span> },
    { title: 'Net inventory', dataIndex: 'inv', key: 'inv', width: 110,
      align: 'right', render: (v) => <span className="tabular-nums">{fmt(v, 1)}</span> },
    { title: 'Shortage', dataIndex: 'shortage_qty', key: 'shortage_qty', width: 100,
      align: 'right',
      render: (v) => v > 0
        ? <span className="tabular-nums font-medium" style={{ color: SEMANTIC.badText }}>{fmt(v, 1)}</span>
        : <span className="tabular-nums" style={{ color: NEUTRAL[400] }}>0</span> },
  ]

  // ─────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────
  return (
    <div className="space-y-4">
      <Title level={4} style={{ margin: 0 }}>
        B3 – Decision Variable Detail &amp; Safety Indicators (SI/SS)
      </Title>

      {/* ── Run selector ── */}
      <Card size="small">
        <Space>
          <Text strong>Optimization Run:</Text>
          <Select
            style={{ width: 220 }}
            placeholder="Select a run"
            value={runId}
            onChange={(v) => setRunId(v)}
            loading={runs.length === 0}
          >
            {runs.map((r) => (
              <Option key={r.run_id ?? r.id} value={r.run_id ?? r.id}>
                Run #{r.run_id ?? r.id}{r.run_time ? ` — ${r.run_time.slice(0, 16)}` : ''}
              </Option>
            ))}
          </Select>
        </Space>
      </Card>

      {error && <Alert type="error" message={error} showIcon />}

      <Spin spinning={loading}>
        {/* ── Row 1: KPI cards ── */}
        {summary && (
          <Row gutter={16} className="mb-4">
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title="Baseline cost"
                  value={summary.baseline_cost}
                  precision={0}
                  prefix={<DollarOutlined />}
                  valueStyle={{ color: '#666' }}
                  formatter={(v) => fmt(v)}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title="Optimal cost"
                  value={summary.opt_cost}
                  precision={0}
                  prefix={<DollarOutlined />}
                  valueStyle={{ color: COLORS.safe }}
                  formatter={(v) => fmt(v)}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title="Savings"
                  value={summary.savings_pct}
                  precision={1}
                  suffix="%"
                  prefix={<RiseOutlined />}
                  valueStyle={{ color: summary.savings_pct > 0 ? COLORS.safe : COLORS.risk }}
                />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {fmt(summary.savings)} cost units
                </Text>
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title="Mean SI"
                  value={summary.si_mean}
                  precision={3}
                  prefix={<SafetyOutlined />}
                  valueStyle={{ color: summary.si_mean >= 1 ? COLORS.safe : COLORS.risk }}
                />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {summary.ss_below_count} cells below SS threshold
                  &nbsp;|&nbsp; {summary.n_changes} residual changes
                </Text>
              </Card>
            </Col>
          </Row>
        )}

        {/* ── Row 2-3: Tabs ── */}
        <Card>
          <Tabs defaultActiveKey="vars">
            {/* ─── Tab 1: Decision Variables ─── */}
            <TabPane
              tab={<span><BarChartOutlined /> Decision Variables</span>}
              key="vars"
            >
              {/* Filters */}
              <Space wrap className="mb-3">
                <Text strong>Product:</Text>
                <Select
                  style={{ width: 160 }}
                  value={selectedProduct}
                  onChange={setSelectedProduct}
                  showSearch
                  filterOption={(input, opt) =>
                    opt.children.toLowerCase().includes(input.toLowerCase())
                  }
                >
                  {products.map((p) => <Option key={p} value={p}>{p}</Option>)}
                </Select>
                <Text strong>Warehouse:</Text>
                <Select
                  style={{ width: 110 }}
                  value={selectedWarehouse}
                  onChange={setSelectedWarehouse}
                  allowClear
                  placeholder="All"
                >
                  {warehouses.map((w) => <Option key={w} value={w}>{w}</Option>)}
                </Select>
              </Space>

              {varChartData.length === 0
                ? <Empty description="No data for this selection" />
                : (
                  <Row gutter={16}>
                    {/* q & r chart (allocation by period) */}
                    <Col xs={24} xl={12}>
                      <Text strong className="block mb-2">
                        q (case-pack) and r (residual) allocation by period
                      </Text>
                      <ResponsiveContainer width="100%" height={260}>
                        <BarChart data={varChartData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="period" label={{ value: 'Period', position: 'insideBottom', offset: -2 }} />
                          <YAxis />
                          <Tooltip content={<VarTooltip />} />
                          <Legend />
                          <Bar dataKey="q" name="q (case-pack)" fill={COLORS.q} stackId="a" />
                          <Bar dataKey="r" name="r (residual)" fill={COLORS.r} stackId="a" />
                        </BarChart>
                      </ResponsiveContainer>
                    </Col>

                    {/* Inventory & deviation chart */}
                    <Col xs={24} xl={12}>
                      <Text strong className="block mb-2">
                        Inventory (I), overstock/backorder (o/bo) and shortage (s)
                      </Text>
                      <ResponsiveContainer width="100%" height={260}>
                        <ComposedChart data={varChartData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="period" />
                          <YAxis />
                          <Tooltip content={<VarTooltip />} />
                          <Legend />
                          <Bar dataKey="bo"  name="Backorder (bo)" fill={COLORS.bo} />
                          <Bar dataKey="o"   name="Overstock (o)"   fill={COLORS.o}  />
                          <Bar dataKey="s"   name="Shortage (s)"  fill={COLORS.s}  />
                          <Line type="monotone" dataKey="inv" name="Net inventory (I)"
                                stroke={COLORS.inv} strokeWidth={2} dot={false} />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </Col>
                  </Row>
                )
              }
            </TabPane>

            {/* ─── Tab 2: SI / SS ─── */}
            <TabPane
              tab={<span><SafetyOutlined /> SI / SS Indicators</span>}
              key="siss"
            >
              {siSs.length === 0
                ? <Empty description="No SI/SS data available" />
                : (
                  <Row gutter={16}>
                    {/* SI distribution */}
                    <Col xs={24} lg={14}>
                      <Text strong className="block mb-2">
                        Safety Index distribution (SI = inventory / lower threshold)
                      </Text>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={siHistData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="si"
                            label={{ value: 'SI', position: 'insideBottom', offset: -2 }} />
                          <YAxis label={{ value: 'Cells', angle: -90, position: 'insideLeft' }} />
                          <Tooltip formatter={(v) => [v, 'Cells']} />
                          <ReferenceLine x="1.0" stroke="#ff4d4f" strokeDasharray="4 4"
                            label={{ value: 'SI=1', fill: '#ff4d4f', fontSize: 11 }} />
                          <Bar dataKey="count" name="Cells"
                            fill={COLORS.warn}
                            isAnimationActive={false}>
                            {siHistData.map((entry) => (
                              <Cell
                                key={entry.si}
                                fill={parseFloat(entry.si) >= 1 ? COLORS.safe
                                  : parseFloat(entry.si) >= 0.8 ? COLORS.warn : COLORS.risk}
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </Col>

                    {/* Safety ratio */}
                    <Col xs={24} lg={10}>
                      <Text strong className="block mb-2">Safety Level Ratio</Text>
                      <ResponsiveContainer width="100%" height={280}>
                        <PieChart>
                          <Pie
                            data={pieSafeData}
                            cx="50%" cy="50%"
                            outerRadius={90}
                            dataKey="value"
                            label={({ name, percent }) =>
                              `${name}\n${(percent * 100).toFixed(1)}%`}
                            labelLine={false}
                          >
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
            </TabPane>

            {/* ─── Tab 3: Changes Table ─── */}
            <TabPane
              tab={
                <span>
                  <TableOutlined /> Residual Changes
                  {changes.length > 0 && (
                    <Badge count={changes.length} style={{ marginLeft: 6 }} />
                  )}
                </span>
              }
              key="changes"
            >
              <Table
                dataSource={changes}
                columns={changeColumns}
                rowKey={(r) => `${r.product_id}-${r.warehouse_id}-${r.time_period}`}
                size="small"
                pagination={{ pageSize: 20 }}
                scroll={{ x: 700 }}
                locale={{ emptyText: 'No residual changes (r=0 and p=0)' }}
              />
            </TabPane>
          </Tabs>
        </Card>
      </Spin>
    </div>
  )
}
