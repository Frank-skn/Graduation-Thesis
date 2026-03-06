/**
 * B3 – Chi tiết biến quyết định & Chỉ số SI/SS
 *
 * Dashboard trực quan hóa:
 *  Row 0 – Chọn lần chạy (run selector)
 *  Row 1 – KPI cards: chi phí cơ sở, chi phí tối ưu, tiết kiệm, SI trung bình
 *  Row 2 – Tab "Biến quyết định" (chọn sản phẩm → ComposedChart q/r/I/bo/o/s + bounds)
 *  Row 3 – Tab "Chỉ số SI/SS" (BarChart phân phối SI, PieChart tỉ lệ an toàn)
 *  Row 4 – Bảng thay đổi (p=1 hoặc r>0)
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

const { Title, Text } = Typography
const { Option } = Select
const { TabPane } = Tabs

// ─────────────────────────────────────────────
// Màu sắc
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
// Tiện ích
// ─────────────────────────────────────────────
const fmt = (v, d = 0) =>
  typeof v === 'number' ? v.toLocaleString('vi-VN', { maximumFractionDigits: d }) : '—'

const pct = (v) => `${Number(v).toFixed(1)}%`

// ─────────────────────────────────────────────
// Custom tooltip cho ComposedChart
// ─────────────────────────────────────────────
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

// ─────────────────────────────────────────────
// Component chính
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

  // Bộ lọc biến
  const [products, setProducts] = useState([])
  const [selectedProduct, setSelectedProduct] = useState(null)
  const [warehouses, setWarehouses] = useState([])
  const [selectedWarehouse, setSelectedWarehouse] = useState(null)

  // ── Tải danh sách lần chạy ────────────────
  useEffect(() => {
    optimizationService.listRuns()
      .then((res) => {
        const list = res.data?.runs ?? res.data ?? []
        setRuns(list)
        // Ưu tiên dùng activeRunId từ context, nếu không có thì lấy lần đầu tiên
        const defaultId = activeRunId ?? (list.length > 0 ? (list[0].run_id ?? list[0].id) : null)
        setRunId(defaultId)
      })
      .catch(() => {})
  }, [activeRunId])

  // ── Tải dữ liệu khi runId thay đổi ───────
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
      // Lấy danh sách sản phẩm & kho duy nhất
      const prods = [...new Set(vars.map((v) => v.product_id))].sort()
      const whs   = [...new Set(vars.map((v) => v.warehouse_id))].sort()
      setProducts(prods)
      setWarehouses(whs)
      if (!selectedProduct || !prods.includes(selectedProduct)) setSelectedProduct(prods[0] ?? null)
      if (!selectedWarehouse || !whs.includes(selectedWarehouse)) setSelectedWarehouse(null)
      setSiSs(siRes.data?.records ?? [])
      setChanges(chgRes.data?.changes ?? [])
    } catch (e) {
      setError('Không thể tải dữ liệu. Hãy đảm bảo đã chạy tối ưu hoá.')
    } finally {
      setLoading(false)
    }
  }, [runId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { loadData() }, [loadData])

  // ── Lọc biến theo sản phẩm + kho đã chọn ─
  const filteredVars = variables.filter(
    (v) =>
      (!selectedProduct  || v.product_id  === selectedProduct) &&
      (!selectedWarehouse || v.warehouse_id === selectedWarehouse),
  )

  // Chuẩn bị dữ liệu chart: nhóm theo time_period (gộp nhiều kho nếu cần)
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
      { name: 'An toàn (SI≥1)',         value: safe },
      { name: 'Cảnh báo (0.8≤SI<1)',   value: warn },
      { name: 'Rủi ro (SI<0.8)',        value: risk },
    ].filter((d) => d.value > 0)
  }, [siSs])

  // ── Bảng thay đổi ─────────────────────────
  const changeColumns = [
    { title: 'Sản phẩm', dataIndex: 'product_id', key: 'product_id', width: 110,
      sorter: (a, b) => a.product_id.localeCompare(b.product_id) },
    { title: 'Kho', dataIndex: 'warehouse_id', key: 'warehouse_id', width: 80 },
    { title: 'Kỳ', dataIndex: 'time_period', key: 'time_period', width: 60,
      sorter: (a, b) => a.time_period - b.time_period },
    { title: 'q (kiện)', dataIndex: 'q', key: 'q', width: 90,
      render: (v) => <Tag color="blue">{v}</Tag> },
    { title: 'r (đơn vị lẻ)', dataIndex: 'r', key: 'r', width: 110,
      render: (v) => <Tag color="cyan">{v}</Tag> },
    { title: 'Tồn kho net', dataIndex: 'inv', key: 'inv', width: 110,
      render: (v) => fmt(v, 1) },
    { title: 'Thiếu hụt', dataIndex: 'shortage_qty', key: 'shortage_qty', width: 100,
      render: (v) => v > 0 ? <Tag color="red">{fmt(v, 1)}</Tag> : <Tag color="green">0</Tag> },
  ]

  // ─────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────
  return (
    <div className="space-y-4">
      <Title level={4} style={{ margin: 0 }}>
        B3 – Chi tiết biến quyết định &amp; Chỉ số an toàn (SI/SS)
      </Title>

      {/* ── Chọn lần chạy ── */}
      <Card size="small">
        <Space>
          <Text strong>Lần chạy:</Text>
          <Select
            style={{ width: 220 }}
            placeholder="Chọn lần chạy"
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
                  title="Chi phí cơ sở"
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
                  title="Chi phí tối ưu"
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
                  title="Tiết kiệm"
                  value={summary.savings_pct}
                  precision={1}
                  suffix="%"
                  prefix={<RiseOutlined />}
                  valueStyle={{ color: summary.savings_pct > 0 ? COLORS.safe : COLORS.risk }}
                />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {fmt(summary.savings)} đơn vị tiền
                </Text>
              </Card>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title="SI trung bình"
                  value={summary.si_mean}
                  precision={3}
                  prefix={<SafetyOutlined />}
                  valueStyle={{ color: summary.si_mean >= 1 ? COLORS.safe : COLORS.risk }}
                />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {summary.ss_below_count} ô dưới ngưỡng SS
                  &nbsp;|&nbsp; {summary.n_changes} thay đổi lẻ
                </Text>
              </Card>
            </Col>
          </Row>
        )}

        {/* ── Row 2-3: Tabs ── */}
        <Card>
          <Tabs defaultActiveKey="vars">
            {/* ─── Tab 1: Biến quyết định ─── */}
            <TabPane
              tab={<span><BarChartOutlined /> Biến quyết định</span>}
              key="vars"
            >
              {/* Bộ lọc */}
              <Space wrap className="mb-3">
                <Text strong>Sản phẩm:</Text>
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
                <Text strong>Kho:</Text>
                <Select
                  style={{ width: 110 }}
                  value={selectedWarehouse}
                  onChange={setSelectedWarehouse}
                  allowClear
                  placeholder="Tất cả"
                >
                  {warehouses.map((w) => <Option key={w} value={w}>{w}</Option>)}
                </Select>
              </Space>

              {varChartData.length === 0
                ? <Empty description="Không có dữ liệu cho lựa chọn này" />
                : (
                  <Row gutter={16}>
                    {/* Biểu đồ q & r (phân bổ theo kỳ) */}
                    <Col xs={24} xl={12}>
                      <Text strong className="block mb-2">
                        Phân bổ q (kiện) và r (lẻ) theo kỳ
                      </Text>
                      <ResponsiveContainer width="100%" height={260}>
                        <BarChart data={varChartData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="period" label={{ value: 'Kỳ', position: 'insideBottom', offset: -2 }} />
                          <YAxis />
                          <Tooltip content={<VarTooltip />} />
                          <Legend />
                          <Bar dataKey="q" name="q (kiện)" fill={COLORS.q} stackId="a" />
                          <Bar dataKey="r" name="r (lẻ)" fill={COLORS.r} stackId="a" />
                        </BarChart>
                      </ResponsiveContainer>
                    </Col>

                    {/* Biểu đồ tồn kho & sai lệch */}
                    <Col xs={24} xl={12}>
                      <Text strong className="block mb-2">
                        Tồn kho (I), vượt ngưỡng (o/bo) và thiếu hụt (s)
                      </Text>
                      <ResponsiveContainer width="100%" height={260}>
                        <ComposedChart data={varChartData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="period" />
                          <YAxis />
                          <Tooltip content={<VarTooltip />} />
                          <Legend />
                          <Bar dataKey="bo"  name="Tồn thiếu (bo)" fill={COLORS.bo} />
                          <Bar dataKey="o"   name="Tồn thừa (o)"   fill={COLORS.o}  />
                          <Bar dataKey="s"   name="Thiếu hụt (s)"  fill={COLORS.s}  />
                          <Line type="monotone" dataKey="inv" name="Tồn kho net (I)"
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
              tab={<span><SafetyOutlined /> Chỉ số SI / SS</span>}
              key="siss"
            >
              {siSs.length === 0
                ? <Empty description="Không có dữ liệu SI/SS" />
                : (
                  <Row gutter={16}>
                    {/* Phân phối SI */}
                    <Col xs={24} lg={14}>
                      <Text strong className="block mb-2">
                        Phân phối Safety Index (SI = tồn kho / ngưỡng dưới)
                      </Text>
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={siHistData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="si"
                            label={{ value: 'SI', position: 'insideBottom', offset: -2 }} />
                          <YAxis label={{ value: 'Số ô', angle: -90, position: 'insideLeft' }} />
                          <Tooltip formatter={(v) => [v, 'Số ô']} />
                          <ReferenceLine x="1.0" stroke="#ff4d4f" strokeDasharray="4 4"
                            label={{ value: 'SI=1', fill: '#ff4d4f', fontSize: 11 }} />
                          <Bar dataKey="count" name="Số ô"
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

                    {/* Tỉ lệ an toàn */}
                    <Col xs={24} lg={10}>
                      <Text strong className="block mb-2">Tỉ lệ mức an toàn</Text>
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

            {/* ─── Tab 3: Bảng thay đổi ─── */}
            <TabPane
              tab={
                <span>
                  <TableOutlined /> Thay đổi lẻ
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
                locale={{ emptyText: 'Không có thay đổi lẻ (r=0 và p=0)' }}
              />
            </TabPane>
          </Tabs>
        </Card>
      </Spin>
    </div>
  )
}
