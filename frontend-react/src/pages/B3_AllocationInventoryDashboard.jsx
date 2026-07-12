import React, { useState, useEffect } from 'react'
import {
  Card, Row, Col, Table, Tag, Select, Tabs, Empty,
  Spin, Alert, Statistic, Button, Typography,
} from 'antd'
import {
  SwapOutlined,
  LineChartOutlined,
  AppstoreOutlined,
  NodeIndexOutlined,
  ReloadOutlined,
  FilterOutlined,
} from '@ant-design/icons'
import {
  ResponsiveContainer,
  BarChart, Bar,
  LineChart, Line,
  ComposedChart,
  XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ReferenceLine,
} from 'recharts'
import { useAppContext } from '../context/AppContext'
import { useApi } from '../hooks/useApi'
import optimizationService from '../services/optimizationService'
import dataService from '../services/dataService'
import PageHeader from '../components/PageHeader'
import { CATEGORICAL, SEMANTIC, NEUTRAL, CHART_GRID, BRAND } from '../theme/tokens'

const { Option } = Select
const { Text } = Typography

// ─── Màu sắc kho (bảng phân loại hài hòa) ───────────────────────────────────
const WH_COLORS = CATEGORICAL
const whColor = (idx) => WH_COLORS[idx % WH_COLORS.length]

// ════════════════════════════════════════════════════════════════════════════
//  TAB 1 — PLT Chuyển Hàng Ngang
// ════════════════════════════════════════════════════════════════════════════
const PLTTab = ({ runId, products, warehouses }) => {
  const [pltProduct, setPltProduct] = useState(undefined)
  const [pltFromWh, setPltFromWh] = useState(undefined)
  const [pltToWh, setPltToWh] = useState(undefined)

  const { data: pltData, loading, error } = useApi(
    () => runId
      ? optimizationService.getPLTTransfers(runId, {
          product_id: pltProduct,
          from_warehouse_id: pltFromWh,
          to_warehouse_id: pltToWh,
        })
      : Promise.resolve(null),
    [runId, pltProduct, pltFromWh, pltToWh],
  )

  const { has_plt, transfers = [], summary = [] } = pltData || {}

  // Ma trận kho
  const whs = [...new Set([
    ...summary.map((s) => s.from_warehouse_id),
    ...summary.map((s) => s.to_warehouse_id),
  ])].sort()

  const matrixData = whs.map((from) => {
    const row = { from_wh: from }
    whs.forEach((to) => {
      if (from === to) { row[to] = null; return }
      const entry = summary.find(
        (s) => s.from_warehouse_id === from && s.to_warehouse_id === to,
      )
      row[to] = entry ? entry.total_qty : 0
    })
    return row
  })

  const matrixColumns = [
    {
      title: 'Từ \\ Đến',
      dataIndex: 'from_wh',
      key: 'from_wh',
      fixed: 'left',
      width: 100,
      render: (v) => <span className="font-medium" style={{ color: NEUTRAL[700] }}>{v}</span>,
    },
    ...whs.map((to) => ({
      title: <span className="font-medium" style={{ color: NEUTRAL[600] }}>{to}</span>,
      dataIndex: to,
      key: to,
      align: 'right',
      width: 100,
      render: (v, row) => {
        if (row.from_wh === to) return <span style={{ color: NEUTRAL[300] }}>—</span>
        if (!v) return <span style={{ color: NEUTRAL[300] }}>0</span>
        return <span className="tabular-nums font-medium" style={{ color: BRAND[600] }}>{Number(v).toLocaleString()}</span>
      },
    })),
  ]

  // Biểu đồ theo kỳ — gom theo KHO NGUỒN (from_wh) để giữ ≤ 6 màu (không cầu vồng 22 cặp).
  // Mỗi cột kỳ = tổng lượng chuyển ĐI từ mỗi kho nguồn trong kỳ đó.
  const periods = [...new Set(transfers.map((t) => t.time_period))].sort((a, b) => a - b)
  const barData = periods.map((t) => {
    const row = { period: `Kỳ ${t}` }
    transfers.filter((r) => r.time_period === t).forEach((r) => {
      const k = r.from_warehouse_id
      row[k] = (row[k] || 0) + r.qty
    })
    return row
  })
  const barKeys = [...new Set(transfers.map((t) => t.from_warehouse_id))].sort()

  if (loading) return <div className="flex justify-center py-16"><Spin size="large" /></div>
  if (error) return <Alert type="error" message="Lỗi tải dữ liệu PLT" description={String(error)} />

  return (
    <div className="space-y-4">
      {/* Bộ lọc */}
      <Card size="small">
        <Row gutter={12} align="middle">
          <Col flex="none"><FilterOutlined /> <strong>Lọc:</strong></Col>
          <Col flex="200px">
            <Select allowClear value={pltProduct} onChange={setPltProduct}
              style={{ width: '100%' }} placeholder="Sản phẩm" showSearch optionFilterProp="children">
              {products.map((p) => <Option key={p} value={p}>{p}</Option>)}
            </Select>
          </Col>
          <Col flex="130px">
            <Select allowClear value={pltFromWh} onChange={setPltFromWh}
              style={{ width: '100%' }} placeholder="Từ kho">
              {warehouses.map((w) => <Option key={w} value={w}>{w}</Option>)}
            </Select>
          </Col>
          <Col flex="130px">
            <Select allowClear value={pltToWh} onChange={setPltToWh}
              style={{ width: '100%' }} placeholder="Đến kho">
              {warehouses.map((w) => <Option key={w} value={w}>{w}</Option>)}
            </Select>
          </Col>
        </Row>
      </Card>

      {!has_plt || transfers.length === 0 ? (
        <Empty description="Không có giao dịch PLT nào trong lần chạy này" style={{ marginTop: 48 }} />
      ) : (
        <>
          {/* Thẻ tổng quan */}
          <Row gutter={16}>
            <Col span={6}>
              <Card size="small">
                <Statistic title="Tổng lượng chuyển" prefix={<SwapOutlined />}
                  value={transfers.reduce((s, r) => s + r.qty, 0).toLocaleString()} suffix="đơn vị" />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic title="Số cặp kho" prefix={<NodeIndexOutlined />}
                  value={summary.length} suffix="cặp" />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic title="Số giao dịch" value={transfers.length} suffix="lần" />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic title="Số kỳ có PLT"
                  value={[...new Set(transfers.map((t) => t.time_period))].length} suffix="kỳ" />
              </Card>
            </Col>
          </Row>

          {/* Ma trận */}
          <Card title="Ma trận PLT — tổng lượng chuyển theo cặp kho" size="small">
            <Text type="secondary" style={{ fontSize: 12 }} className="block mb-2">
              Đơn vị: sản phẩm. Số có phần thập phân vì đây là tổng cộng dồn nhiều giao dịch — một số giao dịch có phần dư lẻ (không tròn theo thùng đóng gói)
            </Text>
            <Table dataSource={matrixData} columns={matrixColumns} rowKey="from_wh"
              pagination={false} size="small" scroll={{ x: 'max-content' }} />
          </Card>

          {/* Biểu đồ theo kỳ */}
          {barData.length > 0 && (
            <Card title="Lượng PLT theo kỳ (theo kho nguồn)" size="small">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={barData} margin={{ top: 8, right: 24, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis dataKey="period" />
                  <YAxis />
                  <Tooltip formatter={(v, name) => [Number(v).toLocaleString('vi-VN'), `Từ ${name}`]} />
                  <Legend formatter={(v) => `Từ ${v}`} />
                  {barKeys.map((k, i) => (
                    <Bar key={k} dataKey={k} name={k} stackId="a" fill={WH_COLORS[i % WH_COLORS.length]} radius={i === barKeys.length - 1 ? [4, 4, 0, 0] : 0} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* Bảng chi tiết */}
          <Card title="Chi tiết giao dịch PLT" size="small">
            <Table dataSource={transfers} rowKey="plt_id" size="small"
              pagination={{ pageSize: 20, showSizeChanger: true }}
              columns={[
                { title: 'Sản phẩm', dataIndex: 'product_id', key: 'pid', width: 130 },
                { title: 'Từ kho', dataIndex: 'from_warehouse_id', key: 'from',
                  render: (v) => <span className="font-medium" style={{ color: NEUTRAL[700] }}>{v}</span> },
                { title: 'Đến kho', dataIndex: 'to_warehouse_id', key: 'to',
                  render: (v) => <span className="font-medium" style={{ color: NEUTRAL[700] }}>{v}</span> },
                { title: 'Kỳ', dataIndex: 'time_period', key: 't',
                  sorter: (a, b) => a.time_period - b.time_period },
                { title: 'Số lượng', dataIndex: 'qty', key: 'qty', align: 'right',
                  render: (v) => <strong>{Number(v).toLocaleString()}</strong>,
                  sorter: (a, b) => a.qty - b.qty },
              ]}
            />
          </Card>
        </>
      )}
    </div>
  )
}

// ════════════════════════════════════════════════════════════════════════════
//  TAB 2 — Quỹ Đạo Tồn Kho Theo Kho
// ════════════════════════════════════════════════════════════════════════════
const METRIC_OPTIONS = [
  { value: 'total_net_inventory', label: 'Tồn kho (net)' },
  { value: 'total_backorder',     label: 'Backorder' },
  { value: 'total_overstock',     label: 'Overstock' },
  { value: 'total_shortage',      label: 'Shortage' },
]

const InventoryTrajectoryTab = ({ runId }) => {
  const [metric, setMetric] = useState('total_net_inventory')

  const { data: invData, loading, error } = useApi(
    () => runId ? optimizationService.getInventoryByWarehouse(runId) : Promise.resolve(null),
    [runId],
  )

  const warehouses = invData?.warehouses || []

  if (loading) return <div className="flex justify-center py-16"><Spin size="large" /></div>
  if (error) return <Alert type="error" message="Lỗi tải dữ liệu tồn kho" description={String(error)} />
  if (!warehouses.length) return <Empty description="Không có dữ liệu tồn kho" style={{ marginTop: 48 }} />

  const allPeriods = [
    ...new Set(warehouses.flatMap((w) => (w.periods || []).map((p) => p.time_period))),
  ].sort((a, b) => a - b)

  const chartData = allPeriods.map((t) => {
    const row = { period: `Kỳ ${t}` }
    warehouses.forEach((w) => {
      const pt = (w.periods || []).find((p) => p.time_period === t)
      row[w.warehouse_id] = pt ? pt[metric] : 0
    })
    return row
  })

  const metricLabel = METRIC_OPTIONS.find((o) => o.value === metric)?.label

  return (
    <div className="space-y-4">
      {/* Thẻ tổng quan theo kho */}
      <Row gutter={12}>
        {warehouses.map((w, i) => (
          <Col key={w.warehouse_id} span={4}>
            <Card size="small" style={{ borderTop: `3px solid ${whColor(i)}` }}>
              <div className="text-center">
                <div className="flex items-center justify-center mb-1 font-medium" style={{ color: NEUTRAL[700] }}>
                  <span className="inline-block w-2 h-2 rounded-full mr-1.5" style={{ background: whColor(i) }} />
                  {w.warehouse_id}
                </div>
                <div style={{ fontSize: 12, color: NEUTRAL[400] }}>Backorder</div>
                <div className="tabular-nums" style={{ fontWeight: 'bold', color: w.total_backorder > 0 ? SEMANTIC.badText : SEMANTIC.goodText }}>
                  {Number(w.total_backorder).toLocaleString()}
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      {/* Chọn metric */}
      <Card size="small">
        <Row align="middle" gutter={12}>
          <Col flex="none"><strong>Chỉ tiêu:</strong></Col>
          <Col flex="220px">
            <Select value={metric} onChange={setMetric} style={{ width: '100%' }}>
              {METRIC_OPTIONS.map((o) => (
                <Option key={o.value} value={o.value}>{o.label}</Option>
              ))}
            </Select>
          </Col>
        </Row>
      </Card>

      {/* Biểu đồ đường */}
      <Card title={`Quỹ đạo ${metricLabel} theo kho qua các kỳ`} size="small">
        <ResponsiveContainer width="100%" height={340}>
          <LineChart data={chartData} margin={{ top: 8, right: 24, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
            <XAxis dataKey="period" />
            <YAxis tickFormatter={(v) => Number(v).toLocaleString()} />
            <Tooltip formatter={(v) => Number(v).toLocaleString()} />
            <Legend />
            <ReferenceLine y={0} stroke={NEUTRAL[400]} strokeDasharray="3 3" />
            {warehouses.map((w, i) => (
              <Line key={w.warehouse_id} type="monotone" dataKey={w.warehouse_id}
                stroke={whColor(i)} strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </Card>

      {/* Bảng tổng hợp */}
      <Card title="Tổng hợp theo kho" size="small">
        <Table dataSource={warehouses} rowKey="warehouse_id" size="small" pagination={false}
          columns={[
            { title: 'Kho', dataIndex: 'warehouse_id',
              render: (v, _, i) => (
                <span className="flex items-center font-medium" style={{ color: NEUTRAL[700] }}>
                  <span className="inline-block w-2 h-2 rounded-full mr-1.5" style={{ background: whColor(i) }} />{v}
                </span>
              ) },
            { title: 'Tổng backorder', dataIndex: 'total_backorder', align: 'right',
              render: (v) => <span className="tabular-nums" style={{ color: v > 0 ? SEMANTIC.badText : NEUTRAL[600] }}>{Number(v).toLocaleString()}</span>,
              sorter: (a, b) => a.total_backorder - b.total_backorder },
            { title: 'Tổng overstock', dataIndex: 'total_overstock', align: 'right',
              render: (v) => <span style={{ color: v > 0 ? SEMANTIC.warn : undefined }}>{Number(v).toLocaleString()}</span> },
            { title: 'Tổng shortage', dataIndex: 'total_shortage', align: 'right',
              render: (v) => <span style={{ color: v > 0 ? SEMANTIC.warn : undefined }}>{Number(v).toLocaleString()}</span> },
          ]}
        />
      </Card>
    </div>
  )
}

// ════════════════════════════════════════════════════════════════════════════
//  TAB 3 — Phân Bổ Theo Sản Phẩm
// ════════════════════════════════════════════════════════════════════════════
const AllocationTab = ({ runId, products, warehouses }) => {
  const [filterProduct, setFilterProduct] = useState(undefined)
  const [filterWarehouse, setFilterWarehouse] = useState(undefined)

  const { data: allocationData, loading: allocLoading, error: allocError } = useApi(
    () => filterProduct && runId
      ? optimizationService.getAllocation(runId, { product_id: filterProduct, warehouse_id: filterWarehouse, page_size: 500 })
      : Promise.resolve(null),
    [runId, filterProduct, filterWarehouse],
  )

  const { data: inventoryData, loading: invLoading, error: invError } = useApi(
    () => filterProduct && runId
      ? optimizationService.getInventoryDynamics(runId, { product_id: filterProduct, warehouse_id: filterWarehouse })
      : Promise.resolve(null),
    [runId, filterProduct, filterWarehouse],
  )

  const loading = allocLoading || invLoading
  const error = allocError || invError
  const allocations = allocationData?.allocations || []

  // Flatten inventory dynamics thành chartData
  const chartData = []
  ;(inventoryData?.dynamics || []).forEach((d) => {
    ;(d.warehouses || []).forEach((wh) => {
      ;(wh.data_points || []).forEach((p) => {
        chartData.push({
          key: `${d.product_id}-${wh.warehouse_id}-${p.time_period}`,
          warehouse_id: wh.warehouse_id,
          time_period: p.time_period,
          net_inventory: Number(p.net_inventory || 0),
          backorder_qty: Number(p.backorder_qty || 0),
          overstock_qty: Number(p.overstock_qty || 0),
          shortage_qty: Number(p.shortage_qty || 0),
        })
      })
    })
  })

  // Biểu đồ tồn kho theo kỳ (gom theo warehouse)
  const whList = [...new Set(chartData.map((r) => r.warehouse_id))].sort()
  const periodList = [...new Set(chartData.map((r) => r.time_period))].sort((a, b) => a - b)
  const lineData = periodList.map((t) => {
    const row = { period: `Kỳ ${t}` }
    whList.forEach((wh) => {
      const pt = chartData.find((r) => r.warehouse_id === wh && r.time_period === t)
      row[wh] = pt ? pt.net_inventory : 0
    })
    return row
  })

  return (
    <div className="space-y-4">
      {/* Bộ lọc — bắt buộc chọn sản phẩm */}
      <Card size="small">
        <Row gutter={12} align="middle">
          <Col flex="none"><FilterOutlined /> <strong>Bộ lọc:</strong></Col>
          <Col flex="200px">
            <Select value={filterProduct} onChange={setFilterProduct} allowClear
              style={{ width: '100%' }} placeholder="Chọn sản phẩm (bắt buộc)"
              showSearch optionFilterProp="children">
              {products.map((p) => <Option key={p} value={p}>{p}</Option>)}
            </Select>
          </Col>
          <Col flex="140px">
            <Select value={filterWarehouse} onChange={setFilterWarehouse} allowClear
              style={{ width: '100%' }} placeholder="Kho (tuỳ chọn)">
              {warehouses.map((w) => <Option key={w} value={w}>{w}</Option>)}
            </Select>
          </Col>
        </Row>
      </Card>

      {!filterProduct ? (
        <Alert type="info" message="Vui lòng chọn sản phẩm để xem chi tiết phân bổ" />
      ) : loading ? (
        <div className="flex justify-center py-16"><Spin size="large" /></div>
      ) : error ? (
        <Alert type="error" message="Lỗi tải dữ liệu" description={String(error)} />
      ) : (
        <>
          {/* Thẻ tổng quan */}
          <Row gutter={16}>
            <Col span={6}>
              <Card size="small">
                <Statistic title="Tổng kiện hàng"
                  value={allocations.reduce((s, a) => s + (a.q_case_pack || 0), 0).toLocaleString()} />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic title="Tổng đơn vị lẻ"
                  value={allocations.reduce((s, a) => s + (a.r_residual_units || 0), 0).toLocaleString()} />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic title="Tổng backorder"
                  valueStyle={{ color: allocations.reduce((s, a) => s + Number(a.backorder_qty || 0), 0) > 0 ? SEMANTIC.bad : undefined }}
                  value={allocations.reduce((s, a) => s + Number(a.backorder_qty || 0), 0).toLocaleString()} />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small">
                <Statistic title="Vi phạm quy cách đóng gói"
                  valueStyle={{ color: allocations.filter((a) => a.penalty_flag).length > 0 ? SEMANTIC.warn : undefined }}
                  value={allocations.filter((a) => a.penalty_flag).length} suffix="dòng" />
              </Card>
            </Col>
          </Row>

          {/* Biểu đồ tồn kho theo kho × kỳ */}
          {lineData.length > 0 && (
            <Card title={`Quỹ đạo tồn kho — ${filterProduct}`} size="small">
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={lineData} margin={{ top: 8, right: 24, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis dataKey="period" />
                  <YAxis tickFormatter={(v) => Number(v).toLocaleString()} />
                  <Tooltip formatter={(v) => Number(v).toLocaleString()} />
                  <Legend />
                  <ReferenceLine y={0} stroke={NEUTRAL[400]} strokeDasharray="3 3" />
                  {whList.map((wh, i) => (
                    <Line key={wh} type="monotone" dataKey={wh} stroke={whColor(i)}
                      strokeWidth={2} dot={{ r: 3 }} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* Bảng chi tiết */}
          <Card title={`Chi tiết phân bổ — ${filterProduct}`} size="small">
            <Table dataSource={allocations} rowKey={(r) => `${r.product_id}-${r.warehouse_id}-${r.time_period}`}
              size="small" pagination={{ pageSize: 20, showSizeChanger: true }}
              columns={[
                { title: 'Kho', dataIndex: 'warehouse_id', key: 'wh',
                  render: (v) => <span className="font-medium" style={{ color: NEUTRAL[700] }}>{v}</span> },
                { title: 'Kỳ', dataIndex: 'time_period', key: 't',
                  sorter: (a, b) => a.time_period - b.time_period },
                { title: 'Kiện hàng (Q)', dataIndex: 'q_case_pack', key: 'q', align: 'right',
                  render: (v) => Number(v).toLocaleString(),
                  sorter: (a, b) => a.q_case_pack - b.q_case_pack },
                { title: 'Đơn vị lẻ (r)', dataIndex: 'r_residual_units', key: 'r', align: 'right',
                  render: (v) => Number(v).toLocaleString() },
                { title: 'Tồn kho (I)', dataIndex: 'net_inventory', key: 'inv', align: 'right',
                  render: (v) => (
                    <span className="tabular-nums" style={{ color: Number(v) < 0 ? SEMANTIC.badText : NEUTRAL[600] }}>
                      {Number(v).toLocaleString()}
                    </span>
                  ),
                  sorter: (a, b) => a.net_inventory - b.net_inventory },
                { title: 'Backorder', dataIndex: 'backorder_qty', key: 'bo', align: 'right',
                  render: (v) => (
                    <span className="tabular-nums" style={{ color: Number(v) > 0 ? SEMANTIC.badText : NEUTRAL[600] }}>
                      {Number(v).toLocaleString()}
                    </span>
                  ) },
                { title: 'Overstock', dataIndex: 'overstock_qty', key: 'ov', align: 'right',
                  render: (v) => (
                    <span className="tabular-nums" style={{ color: Number(v) > 0 ? SEMANTIC.warnText : NEUTRAL[600] }}>
                      {Number(v).toLocaleString()}
                    </span>
                  ) },
                { title: 'Shortage', dataIndex: 'shortage_qty', key: 'sh', align: 'right',
                  render: (v) => (
                    <span className="tabular-nums" style={{ color: Number(v) > 0 ? SEMANTIC.warnText : NEUTRAL[600] }}>
                      {Number(v).toLocaleString()}
                    </span>
                  ) },
                { title: 'Vi phạm', dataIndex: 'penalty_flag', key: 'pen',
                  render: (v) => v ? <Tag color="orange">Có</Tag> : <Tag color="default">Không</Tag> },
              ]}
            />
          </Card>
        </>
      )}
    </div>
  )
}

// ════════════════════════════════════════════════════════════════════════════
//  MAIN PAGE
// ════════════════════════════════════════════════════════════════════════════
const AllocationInventoryDashboard = () => {
  const { activeRunId, setActiveRunId } = useAppContext()
  const [runs, setRuns] = useState([])
  const [runsLoading, setRunsLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('plt')

  const fetchRuns = () => {
    setRunsLoading(true)
    optimizationService.listRuns()
      .then((res) => {
        const list = Array.isArray(res) ? res : (res?.runs ?? [])
        setRuns(list)
        if (!activeRunId && list.length > 0) setActiveRunId(list[0].run_id)
      })
      .catch(() => setRuns([]))
      .finally(() => setRunsLoading(false))
  }

  useEffect(() => { fetchRuns() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const { data: overview } = useApi(() => dataService.getOverview())
  const products = overview?.products || []
  const warehouses = overview?.warehouses || []

  const tabItems = [
    {
      key: 'plt',
      label: <span><SwapOutlined /> Điều chuyển ngang (PLT)</span>,
      children: <PLTTab runId={activeRunId} products={products} warehouses={warehouses} />,
    },
    {
      key: 'trajectory',
      label: <span><LineChartOutlined /> Quỹ đạo tồn kho theo kho</span>,
      children: <InventoryTrajectoryTab runId={activeRunId} />,
    },
    {
      key: 'allocation',
      label: <span><AppstoreOutlined /> Phân bổ theo sản phẩm</span>,
      children: <AllocationTab runId={activeRunId} products={products} warehouses={warehouses} />,
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        icon={<AppstoreOutlined />}
        title="B3. Phân bổ & Động thái tồn kho"
        subtitle="Điều chuyển ngang giữa kho · Quỹ đạo tồn kho theo kho · Chi tiết phân bổ theo sản phẩm"
      />

      {/* Chọn run */}
      <Card size="small">
        <Row gutter={12} align="middle">
          <Col flex="none"><strong>Lần chạy:</strong></Col>
          <Col flex="360px">
            <Select loading={runsLoading} value={activeRunId} onChange={setActiveRunId}
              style={{ width: '100%' }} placeholder="Chọn lần chạy tối ưu"
              options={runs.map((r) => ({
                value: r.run_id,
                label: `Lần #${r.run_id} — ${r.solver_status} (mục tiêu: ${Number(r.objective_value ?? 0).toLocaleString('vi-VN')})`,
              }))}
            />
          </Col>
          <Col flex="none">
            <Button icon={<ReloadOutlined />} onClick={fetchRuns} title="Làm mới" />
          </Col>
        </Row>
      </Card>

      {!activeRunId ? (
        <Alert type="info" message="Chọn lần chạy tối ưu để xem kết quả" />
      ) : (
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} type="card" />
      )}
    </div>
  )
}

export default AllocationInventoryDashboard
