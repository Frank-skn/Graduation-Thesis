import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Card, Row, Col, Statistic, Tag, Alert, Spin, Select, Button, Table, Divider,
  Tabs, Space, Badge, Empty, Typography,
} from 'antd'
import {
  DashboardOutlined, DollarOutlined, CheckCircleOutlined, ClockCircleOutlined,
  ReloadOutlined, RiseOutlined, FallOutlined, SafetyOutlined, BarChartOutlined,
  WarningOutlined, TableOutlined,
} from '@ant-design/icons'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell,
  ComposedChart, Line, ReferenceLine, PieChart, Pie,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import { useAppContext } from '../context/AppContext'
import optimizationService from '../services/optimizationService'

const { Text } = Typography
const { Option } = Select

// ── Màu sắc ───────────────────────────────────────────
const BAR_COLORS = ['#f5222d', '#fa8c16', '#faad14', '#1890ff', '#52c41a']
const COLORS = {
  q: '#2196F3', r: '#03A9F4', inv: '#4CAF50',
  bo: '#F44336', o: '#FF9800', s: '#9C27B0',
  safe: '#52c41a', risk: '#ff4d4f', warn: '#faad14',
}
const PIE_COLORS = [COLORS.safe, COLORS.warn, COLORS.risk]
const fmt = (v, d = 0) =>
  typeof v === 'number' ? v.toLocaleString('vi-VN', { maximumFractionDigits: d }) : '—'

// Custom tooltip cho biểu đồ biến quyết định
const VarTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-200 rounded p-3 shadow-lg text-xs">
      <p className="font-semibold mb-1">Kỳ {label}</p>
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
    label: `Lần #${r.run_id} — ${r.solver_status} (mục tiêu: ${Number(r.objective_value ?? 0).toLocaleString('vi-VN')})`,
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
  const propCost        = Number(ext.prop_cost) || 0
  const savingsVsProp   = Number(ext.savings_vs_prop) || 0
  const savingsPctProp  = Number(ext.savings_pct_prop) || 0

  // ── Bảng phân tích chi phí ────────────────────────────
  const costRows = [
    { key: 'backorder', name: 'Chi phí tồn thiếu (Backlog)',   value: Number(kpis.cost_backorder) || 0 },
    { key: 'overstock', name: 'Chi phí tồn thừa (Overstock)',  value: Number(kpis.cost_overstock) || 0 },
    { key: 'shortage',  name: 'Chi phí thiếu hụt (Shortage)',  value: Number(kpis.cost_shortage)  || 0 },
    { key: 'penalty',   name: 'Chi phí vi phạm (Penalty)',     value: Number(kpis.cost_penalty)   || 0 },
  ].map((r) => ({ ...r, pct: totalCost > 0 ? (r.value / totalCost * 100) : 0 }))

  const costColumns = [
    {
      title: 'Thành phần chi phí', dataIndex: 'name', key: 'name',
      render: (t) => <span className="font-medium">{t}</span>,
    },
    {
      title: 'Chi phí tối ưu', dataIndex: 'value', key: 'value', align: 'right',
      render: (v) => <span className="font-semibold">{fmt(v, 2)}</span>,
      sorter: (a, b) => a.value - b.value,
    },
    {
      title: '% Tổng', dataIndex: 'pct', key: 'pct', align: 'right',
      render: (v) => <Tag color={v > 50 ? 'red' : v > 20 ? 'orange' : 'blue'}>{v.toFixed(2)}%</Tag>,
      sorter: (a, b) => a.pct - b.pct,
    },
  ]

  const costBarData = costRows.map((r) => ({
    name: r.name.split('(')[0].replace('Chi phí ', '').trim(),
    'Chi phí': r.value,
  }))

  const compareBarData = baselineCost > 0
    ? [{ name: 'So sánh', 'Do-nothing': baselineCost, 'Proportional': propCost || undefined, 'MILP Tối ưu': optCost }]
    : []

  // ── B3: State & logic cho chi tiết biến & SI/SS ───────
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
      setVarError('Không thể tải dữ liệu biến. Hãy đảm bảo đã chạy tối ưu hoá.')
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
      { name: 'An toàn (SI≥1)',        value: safe },
      { name: 'Cảnh báo (0.8≤SI<1)',  value: warn },
      { name: 'Rủi ro (SI<0.8)',       value: risk },
    ].filter((d) => d.value > 0)
  }, [siSs])

  const changeColumns = [
    { title: 'Sản phẩm',      dataIndex: 'product_id',   key: 'product_id',   width: 110,
      sorter: (a, b) => a.product_id.localeCompare(b.product_id) },
    { title: 'Kho',            dataIndex: 'warehouse_id', key: 'warehouse_id', width: 80 },
    { title: 'Kỳ',             dataIndex: 'time_period',  key: 'time_period',  width: 60,
      sorter: (a, b) => a.time_period - b.time_period },
    { title: 'q (kiện)',       dataIndex: 'q',             key: 'q',            width: 90,
      render: (v) => <Tag color="blue">{v}</Tag> },
    { title: 'r (đơn vị lẻ)', dataIndex: 'r',             key: 'r',            width: 110,
      render: (v) => <Tag color="cyan">{v}</Tag> },
    { title: 'Tồn kho net',   dataIndex: 'inv',            key: 'inv',          width: 110,
      render: (v) => fmt(v, 1) },
    { title: 'Thiếu hụt',     dataIndex: 'shortage_qty',  key: 'shortage_qty', width: 100,
      render: (v) => v > 0 ? <Tag color="red">{fmt(v, 1)}</Tag> : <Tag color="green">0</Tag> },
  ]

  return (
    <Spin spinning={loading || extLoading || runsLoading}>
      <div className="space-y-6">
        {error && (
          <Alert message="Lỗi tải dữ liệu" description={String(error)} type="error" showIcon closable />
        )}

        {/* ── Tiêu đề & chọn lần chạy ── */}
        <div className="flex justify-between items-start flex-wrap gap-3">
          <div>
            <h1 className="text-3xl font-bold text-primary-700 mb-1">
              <DashboardOutlined className="mr-3" />B2. Tóm Tắt &amp; Chi Tiết
            </h1>
            <p className="text-gray-500">
              Kịch bản: <strong>{run.scenario_name || run.scenario_id || '—'}</strong>
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Select
              style={{ minWidth: 340 }}
              options={runOptions}
              value={activeRunId}
              onChange={(val) => setActiveRunId(val)}
              placeholder="Chọn lần chạy"
              loading={runsLoading}
            />
            <Button icon={<ReloadOutlined />} onClick={fetchRuns} title="Làm mới" />
            <Tag color={
              run.solver_status === 'Optimal' ? 'green'
              : run.solver_status === 'Feasible' ? 'orange' : 'red'
            }>
              {run.solver_status || '—'}
            </Tag>
          </div>
        </div>

        {/* ── KPI Cards ── */}
        <Row gutter={16}>
          <Col span={5}>
            <Card>
              <Statistic
                title="Tổng chi phí tối ưu"
                value={totalCost}
                formatter={(v) => fmt(v, 0)}
                prefix={<DollarOutlined />}
                valueStyle={{ color: '#cf1322' }}
              />
            </Card>
          </Col>
          <Col span={4}>
            <Card>
              <Statistic
                title="Mức độ phục vụ"
                value={Number(kpis.service_level) || 0}
                precision={1}
                suffix="%"
                valueStyle={{ color: '#3f8600' }}
                prefix={<CheckCircleOutlined />}
              />
            </Card>
          </Col>
          <Col span={5}>
            <Card>
              <Statistic
                title="Tiết kiệm vs Do-nothing"
                value={savingsPct}
                precision={2}
                suffix="%"
                prefix={savingsPct >= 0 ? <RiseOutlined /> : <FallOutlined />}
                valueStyle={{ color: savingsPct >= 0 ? '#3f8600' : '#cf1322' }}
              />
              <div className="text-xs text-gray-400 mt-1">
                Tiết kiệm: {fmt(savingsAmt, 0)}
              </div>
            </Card>
          </Col>
          <Col span={6}>
            <Card style={{ borderColor: propCost > 0 ? '#1890ff' : undefined }}>
              <Statistic
                title="Tiết kiệm vs Proportional"
                value={savingsPctProp}
                precision={2}
                suffix="%"
                prefix={<BarChartOutlined />}
                valueStyle={{ color: savingsPctProp >= 0 ? '#1890ff' : '#cf1322' }}
              />
              <div className="text-xs text-gray-400 mt-1">
                Tiết kiệm: {fmt(savingsVsProp, 0)} &nbsp;|&nbsp; Prop: {fmt(propCost, 0)}
              </div>
            </Card>
          </Col>
          <Col span={4}>
            <Card>
              <Statistic
                title="Thời gian giải"
                value={Number(run.solve_time_seconds) || 0}
                precision={2}
                suffix="s"
                prefix={<ClockCircleOutlined />}
              />
              <div className="text-xs text-gray-400 mt-1">
                MIP Gap: {Number(run.mip_gap || 0).toFixed(4)}
              </div>
            </Card>
          </Col>
        </Row>

        {/* ── TABS chính ── */}
        <Tabs
          defaultActiveKey="cost"
          items={[
            {
              key: 'cost',
              label: <span><BarChartOutlined /> Phân tích chi phí</span>,
              children: (
                <div className="space-y-4">
                  <Card title={<span className="text-lg font-bold"><BarChartOutlined className="mr-2" />PHÂN TÍCH CHI PHÍ</span>}>
                    <Row gutter={24}>
                      <Col xs={24} lg={12}>
                        <Table
                          columns={[
                            { title: 'Thành phần chi phí', dataIndex: 'name', key: 'name',
                              render: (t) => <span className="font-medium">{t}</span> },
                            { title: 'Chi phí tối ưu', dataIndex: 'value', key: 'value', align: 'right',
                              render: (v) => <span className="font-semibold">{fmt(v, 2)}</span>,
                              sorter: (a, b) => a.value - b.value },
                            { title: '% Tổng', dataIndex: 'pct', key: 'pct', align: 'right',
                              render: (v) => <Tag color={v > 50 ? 'red' : v > 20 ? 'orange' : 'blue'}>{v.toFixed(2)}%</Tag>,
                              sorter: (a, b) => a.pct - b.pct },
                          ]}
                          dataSource={costRows}
                          rowKey="key"
                          pagination={false}
                          size="middle"
                          className="mb-4"
                          summary={() => (
                            <Table.Summary.Row style={{ fontWeight: 'bold', background: '#fafafa' }}>
                              <Table.Summary.Cell index={0}><strong>TỔNG</strong></Table.Summary.Cell>
                              <Table.Summary.Cell index={1} align="right"><strong>{fmt(totalCost, 2)}</strong></Table.Summary.Cell>
                              <Table.Summary.Cell index={2} align="right"><Tag color="purple"><strong>100%</strong></Tag></Table.Summary.Cell>
                            </Table.Summary.Row>
                          )}
                        />
                        {baselineCost > 0 && (
                          <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                            <h4 className="font-bold text-green-700 mb-3">
                              <RiseOutlined className="mr-1" />So sánh với chi phí cơ sở (Do-nothing)
                            </h4>
                            <div className="space-y-2 text-sm">
                              <div className="flex justify-between">
                                <span className="text-gray-600">Chi phí cơ sở (Baseline):</span>
                                <span className="font-semibold text-gray-700">{fmt(baselineCost, 2)}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-600">Chi phí tối ưu:</span>
                                <span className="font-semibold text-green-700">{fmt(optCost, 2)}</span>
                              </div>
                              <Divider className="my-2" />
                              <div className="flex justify-between text-base">
                                <span className="font-bold text-green-700">Tiết kiệm:</span>
                                <span className="font-bold text-green-700">
                                  {fmt(savingsAmt, 2)} ({savingsPct.toFixed(2)}%)
                                </span>
                              </div>
                            </div>
                          </div>
                        )}
                        {propCost > 0 && (
                          <div className="p-4 bg-blue-50 rounded-lg border border-blue-200 mt-3">
                            <h4 className="font-bold text-blue-700 mb-3">
                              <BarChartOutlined className="mr-1" />So sánh với Proportional Allocation
                            </h4>
                            <div className="space-y-2 text-sm">
                              <div className="flex justify-between">
                                <span className="text-gray-600">Chi phí Proportional (heuristic):</span>
                                <span className="font-semibold text-gray-700">{fmt(propCost, 2)}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-600">Chi phí tối ưu (MILP):</span>
                                <span className="font-semibold text-blue-700">{fmt(optCost, 2)}</span>
                              </div>
                              <Divider className="my-2" />
                              <div className="flex justify-between text-base">
                                <span className="font-bold text-blue-700">MILP tốt hơn:</span>
                                <span className="font-bold text-blue-700">
                                  {fmt(savingsVsProp, 2)} ({savingsPctProp.toFixed(2)}%)
                                </span>
                              </div>
                            </div>
                          </div>
                        )}
                      </Col>
                      <Col xs={24} lg={12}>
                        <p className="text-sm font-semibold text-gray-600 mb-2">Biểu đồ thành phần chi phí tối ưu</p>
                        <ResponsiveContainer width="100%" height={210}>
                          <BarChart data={costBarData} margin={{ top: 5, right: 10, bottom: 50, left: 10 }}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="name" angle={-28} textAnchor="end" interval={0} tick={{ fontSize: 11 }} />
                            <YAxis tickFormatter={(v) => v.toLocaleString('vi-VN')} width={80} tick={{ fontSize: 10 }} />
                            <Tooltip formatter={(v) => [fmt(v, 2), 'Chi phí']} />
                            <Bar dataKey="Chi phí" radius={[4, 4, 0, 0]}>
                              {costBarData.map((_, i) => <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />)}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                        {compareBarData.length > 0 && (
                          <>
                            <p className="text-sm font-semibold text-gray-600 mt-4 mb-2">So sánh tổng: Do-nothing vs Proportional vs MILP</p>
                            <ResponsiveContainer width="100%" height={160}>
                              <BarChart data={compareBarData} layout="vertical" margin={{ left: 10, right: 80 }}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis type="number" tickFormatter={(v) => v.toLocaleString('vi-VN')} tick={{ fontSize: 10 }} />
                                <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={70} />
                                <Tooltip formatter={(v) => [fmt(v, 2)]} />
                                <Legend />
                                <Bar dataKey="Do-nothing"   fill="#d9d9d9" radius={[0, 4, 4, 0]} />
                                <Bar dataKey="Proportional" fill="#1890ff" radius={[0, 4, 4, 0]} />
                                <Bar dataKey="MILP Tối ưu"  fill="#52c41a" radius={[0, 4, 4, 0]} />
                              </BarChart>
                            </ResponsiveContainer>
                          </>
                        )}
                      </Col>
                    </Row>
                  </Card>

                  <Card title={<><SafetyOutlined className="mr-2" />Chi tiết lần chạy</>}>
                    <Row gutter={24}>
                      <Col span={12}>
                        <div className="space-y-0 text-sm">
                          {[
                            ['Giá trị mục tiêu', fmt(Number(run.objective_value || 0))],
                            ['Sai số MIP',       Number(run.mip_gap || 0).toFixed(4)],
                            ['Số sản phẩm',      summary.product_count || 0],
                            ['Số kho',           summary.warehouse_count || 0],
                            ['Số chu kỳ',        summary.period_count || 0],
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
                            ['Tổng kết quả lưu',    summary.result_count || 0,   ''],
                            ['Tồn thiếu (Backlog)',  Number(kpis.cost_backorder || 0).toLocaleString('vi-VN'), 'text-red-600'],
                            ['Tồn thừa (Overstock)', Number(kpis.cost_overstock || 0).toLocaleString('vi-VN'), 'text-orange-600'],
                            ['Thiếu hụt (Shortage)', Number(kpis.cost_shortage  || 0).toLocaleString('vi-VN'), 'text-yellow-600'],
                            ['Vi phạm (Penalty)',    Number(kpis.cost_penalty   || 0).toLocaleString('vi-VN'), 'text-blue-600'],
                          ].map(([label, val, cls]) => (
                            <div key={label} className="flex justify-between py-2 border-b last:border-0">
                              <span className="text-gray-500">{label}:</span>
                              <span className={`font-medium ${cls}`}>{val}</span>
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
                  <BarChartOutlined /> Biến quyết định &amp; SI/SS
                  {changes.length > 0 && <Badge count={changes.length} size="small" style={{ marginLeft: 6 }} />}
                </span>
              ),
              children: (
                <Spin spinning={varLoading}>
                  {varError && <Alert type="error" message={varError} showIcon className="mb-4" />}

                  {/* Mini KPI row từ extended summary */}
                  {ext && (ext.baseline_cost || ext.si_mean) && (
                    <Row gutter={16} className="mb-4">
                      <Col xs={24} sm={12} md={6}>
                        <Card size="small">
                          <Statistic title="Chi phí cơ sở" value={ext.baseline_cost} precision={0}
                            prefix={<DollarOutlined />} valueStyle={{ color: '#666' }} formatter={(v) => fmt(v)} />
                        </Card>
                      </Col>
                      <Col xs={24} sm={12} md={6}>
                        <Card size="small">
                          <Statistic title="Chi phí tối ưu" value={ext.opt_cost} precision={0}
                            prefix={<DollarOutlined />} valueStyle={{ color: COLORS.safe }} formatter={(v) => fmt(v)} />
                        </Card>
                      </Col>
                      <Col xs={24} sm={12} md={6}>
                        <Card size="small">
                          <Statistic title="Tiết kiệm" value={ext.savings_pct} precision={1} suffix="%"
                            prefix={<RiseOutlined />}
                            valueStyle={{ color: (ext.savings_pct ?? 0) > 0 ? COLORS.safe : COLORS.risk }} />
                          <Text type="secondary" style={{ fontSize: 12 }}>{fmt(ext.savings)} đơn vị tiền</Text>
                        </Card>
                      </Col>
                      <Col xs={24} sm={12} md={6}>
                        <Card size="small">
                          <Statistic title="SI trung bình" value={ext.si_mean} precision={3}
                            prefix={<SafetyOutlined />}
                            valueStyle={{ color: (ext.si_mean ?? 0) >= 1 ? COLORS.safe : COLORS.risk }} />
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {ext.ss_below_count} ô dưới ngưỡng SS &nbsp;|&nbsp; {ext.n_changes} thay đổi lẻ
                          </Text>
                        </Card>
                      </Col>
                    </Row>
                  )}

                  <Card>
                    <Tabs defaultActiveKey="decision">
                      <Tabs.TabPane tab={<span><BarChartOutlined /> Biến quyết định</span>} key="decision">
                        <Space wrap className="mb-3">
                          <Text strong>Sản phẩm:</Text>
                          <Select style={{ width: 160 }} value={selectedProduct} onChange={setSelectedProduct}
                            showSearch filterOption={(input, opt) =>
                              String(opt.children).toLowerCase().includes(input.toLowerCase())}>
                            {products.map((p) => <Option key={p} value={p}>{p}</Option>)}
                          </Select>
                          <Text strong>Kho:</Text>
                          <Select style={{ width: 110 }} value={selectedWarehouse} onChange={setSelectedWarehouse}
                            allowClear placeholder="Tất cả">
                            {warehouses.map((w) => <Option key={w} value={w}>{w}</Option>)}
                          </Select>
                        </Space>
                        {varChartData.length === 0
                          ? <Empty description="Không có dữ liệu cho lựa chọn này" />
                          : (
                            <Row gutter={16}>
                              <Col xs={24} xl={12}>
                                <Text strong className="block mb-2">Phân bổ q (kiện) và r (lẻ) theo kỳ</Text>
                                <ResponsiveContainer width="100%" height={260}>
                                  <BarChart data={varChartData}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="period" label={{ value: 'Kỳ', position: 'insideBottom', offset: -2 }} />
                                    <YAxis />
                                    <Tooltip content={<VarTooltip />} />
                                    <Legend />
                                    <Bar dataKey="q" name="q (kiện)" fill={COLORS.q} stackId="a" />
                                    <Bar dataKey="r" name="r (lẻ)"   fill={COLORS.r} stackId="a" />
                                  </BarChart>
                                </ResponsiveContainer>
                              </Col>
                              <Col xs={24} xl={12}>
                                <Text strong className="block mb-2">Tồn kho (I), vượt ngưỡng và thiếu hụt</Text>
                                <ResponsiveContainer width="100%" height={260}>
                                  <ComposedChart data={varChartData}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="period" />
                                    <YAxis />
                                    <Tooltip content={<VarTooltip />} />
                                    <Legend />
                                    <Bar  dataKey="bo"  name="Tồn thiếu (bo)"  fill={COLORS.bo} />
                                    <Bar  dataKey="o"   name="Tồn thừa (o)"    fill={COLORS.o}  />
                                    <Bar  dataKey="s"   name="Thiếu hụt (s)"   fill={COLORS.s}  />
                                    <Line type="monotone" dataKey="inv" name="Tồn kho net (I)"
                                          stroke={COLORS.inv} strokeWidth={2} dot={false} />
                                  </ComposedChart>
                                </ResponsiveContainer>
                              </Col>
                            </Row>
                          )
                        }
                      </Tabs.TabPane>

                      <Tabs.TabPane tab={<span><SafetyOutlined /> Chỉ số SI / SS</span>} key="siss">
                        {siSs.length === 0
                          ? <Empty description="Không có dữ liệu SI/SS" />
                          : (
                            <Row gutter={16}>
                              <Col xs={24} lg={14}>
                                <Text strong className="block mb-2">
                                  Phân phối Safety Index (SI = tồn kho / ngưỡng dưới)
                                </Text>
                                <ResponsiveContainer width="100%" height={280}>
                                  <BarChart data={siHistData}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="si" label={{ value: 'SI', position: 'insideBottom', offset: -2 }} />
                                    <YAxis label={{ value: 'Số ô', angle: -90, position: 'insideLeft' }} />
                                    <Tooltip formatter={(v) => [v, 'Số ô']} />
                                    <ReferenceLine x="1.0" stroke="#ff4d4f" strokeDasharray="4 4"
                                      label={{ value: 'SI=1', fill: '#ff4d4f', fontSize: 11 }} />
                                    <Bar dataKey="count" name="Số ô" fill={COLORS.warn} isAnimationActive={false}>
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
                                <Text strong className="block mb-2">Tỉ lệ mức an toàn</Text>
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
                            <TableOutlined /> Thay đổi lẻ
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
                          locale={{ emptyText: 'Không có thay đổi lẻ (r=0 và p=0)' }}
                        />
                      </Tabs.TabPane>
                    </Tabs>
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
