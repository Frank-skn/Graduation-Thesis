import React from 'react'
import { Card, Row, Col, Table, Tag, Progress, Button, Tooltip, Spin, Alert } from 'antd'
import {
  DatabaseOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  CalendarOutlined,
  BarChartOutlined,
  SyncOutlined,
} from '@ant-design/icons'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Cell, LabelList } from 'recharts'
import { useApi } from '../hooks/useApi'
import dataService from '../services/dataService'
import PageHeader from '../components/PageHeader'
import { SEMANTIC, BRAND, NEUTRAL } from '../theme/tokens'

// Diễn giải tiếng Việt cho ký hiệu tham số mô hình (Bảng 3.3 luận văn)
const PARAM_LABEL = {
  BI: 'Tồn kho đầu kỳ (BI)',
  CP: 'Cấu hình đóng gói (CP)',
  U: 'Ngưỡng tồn kho trên (U)',
  L: 'Ngưỡng tồn kho dưới (L)',
  DI: 'Nhu cầu (DI)',
  CAP: 'Công suất cung ứng (CAP)',
  Cb: 'Chi phí nợ đơn (Cb)',
  Co: 'Chi phí tồn kho vượt mức (Co)',
  Cs: 'Chi phí thiếu hụt (Cs)',
  Cp: 'Chi phí phạt đóng gói (Cp)',
}
const paramLabel = (symbol) => PARAM_LABEL[symbol] || symbol

const DataOverview = () => {
  const { data, loading, error, execute: refresh } = useApi(() => dataService.getOverview())

  // Derive display data from API response
  const overview = data || {}
  const numProducts = overview.num_products || 0
  const numWarehouses = overview.num_warehouses || 0
  const numPeriods = overview.num_periods || 0
  const totalCombinations = overview.total_combinations || 0
  const parameters = overview.parameters || []
  const products = overview.products || []
  const warehouses = overview.warehouses || []

  // Map parameters to Data Freshness format.
  // Each parameter has its own index set per the mathematical model:
  //   BI, CP  → (i,j)   → denominator = |I|×|J|
  //   U,L,DI,Cb,Co,Cs,Cp → (i,j,t) → denominator = |I|×|J|×|T|
  //   CAP     → (i,t)   → denominator = |I|×|T|
  // The backend now provides max_entries (correct denominator) per parameter.
  const dataFreshness = parameters.map((p) => {
    const denom = p.max_entries > 0 ? p.max_entries : 1
    const completeness = Math.round((p.num_entries / denom) * 100)
    let status = 'Critical'
    if (completeness >= 95) status = 'Fresh'
    else if (completeness >= 85) status = 'Good'
    else if (completeness >= 70) status = 'Moderate'
    else if (completeness >= 40) status = 'Stale'
    return {
      source: p.name,
      lastUpdated: `${Number(p.num_entries).toLocaleString('vi-VN')} bản ghi`,
      status,
      staleness: completeness,
    }
  })

  // Quality metrics — derived from real parameter data
  //   Completeness : avg(num_entries / max_entries) per param
  //   Zero-free    : avg(1 - zero_count / num_entries) per param
  //   Parameters   : 100% if all 10 params present
  const avgCompleteness = parameters.length > 0
    ? Math.round(parameters.reduce((s, p) => s + (p.max_entries > 0 ? p.num_entries / p.max_entries : 0), 0) / parameters.length * 100)
    : 0
  const avgZeroFree = parameters.length > 0
    ? Math.round(parameters.reduce((s, p) => s + (p.num_entries > 0 ? (1 - p.zero_count / p.num_entries) : 0), 0) / parameters.length * 100)
    : 0

  const qualityMetrics = [
    { metric: 'Completeness', value: avgCompleteness, target: 95 },
    { metric: 'Zero-free Rate', value: avgZeroFree, target: 90 },
    { metric: 'Parameters', value: parameters.length >= 10 ? 100 : Math.round(parameters.length / 10 * 100), target: 85 },
  ]

  // Per-parameter bar chart data (replaces static trendData)
  const paramBarData = parameters.map(p => ({
    name: p.name,
    completeness: p.max_entries > 0 ? Math.round(p.num_entries / p.max_entries * 100) : 0,
    zeroFree: p.num_entries > 0 ? Math.round((1 - p.zero_count / p.num_entries) * 100) : 0,
    entries: p.num_entries,
  }))

  const freshSources = dataFreshness.filter(d => d.status === 'Fresh' || d.status === 'Good').length

  const freshnessColumns = [
    {
      title: 'Nguồn Dữ Liệu',
      dataIndex: 'source',
      key: 'source',
      render: (text) => (
        <span className="flex items-center">
          <DatabaseOutlined className="mr-2" style={{ color: BRAND[400] }} />
          {paramLabel(text)}
        </span>
      ),
    },
    { title: 'Bản Ghi', dataIndex: 'lastUpdated', key: 'lastUpdated' },
    {
      title: 'Mức Độ Đầy Đủ (%)',
      dataIndex: 'staleness',
      key: 'staleness',
      render: (value) => {
        let color = 'red'
        if (value >= 95) color = 'green'
        else if (value >= 70) color = 'orange'

        return (
          <div style={{ minWidth: 160 }}>
            <Progress
              percent={value}
              size="small"
              status={color === 'red' ? 'exception' : 'normal'}
              strokeColor={color}
              format={(pct) => `${pct}%`}
            />
          </div>
        )
      },
    },
    {
      title: 'Trạng Thái',
      dataIndex: 'status',
      key: 'status',
      render: (status) => {
        const statusMap = {
          Fresh: { label: 'Cập nhật', color: 'green', icon: CheckCircleOutlined },
          Good: { label: 'Tốt', color: 'blue', icon: CheckCircleOutlined },
          Moderate: { label: 'Trung bình', color: 'orange', icon: ClockCircleOutlined },
          Stale: { label: 'Lỗi thời', color: 'red', icon: ExclamationCircleOutlined },
          Critical: { label: 'Nghiêm trọng', color: 'red', icon: ExclamationCircleOutlined },
        }
        const config = statusMap[status] || statusMap.Critical
        const Icon = config.icon
        return (
          <Tag color={config.color} icon={<Icon />}>
            {config.label}
          </Tag>
        )
      },
    },
  ]

  return (
    <Spin spinning={loading}>
    <div className="space-y-6">
      {error && <Alert message="Lỗi khi tải dữ liệu" description={error} type="error" showIcon closable />}
      <PageHeader
        icon={<BarChartOutlined />}
        title="A1. Tổng quan dữ liệu đầu vào"
        subtitle="Giám sát mức độ đầy đủ, chất lượng và tính sẵn sàng của toàn bộ nguồn dữ liệu"
      />

      {/* Summary Cards — đồng nhất tone brand, số ink đậm, icon brand nhạt */}
      <Row gutter={16}>
        {[
          { label: 'Sản Phẩm',        value: numProducts,       Icon: CheckCircleOutlined },
          { label: 'Kho Hàng',        value: numWarehouses,     Icon: DatabaseOutlined },
          { label: 'Kỳ Thời Gian',    value: numPeriods,        Icon: CalendarOutlined },
          { label: 'Tổ Hợp (SP-Kho)', value: totalCombinations, Icon: SyncOutlined },
        ].map(({ label, value, Icon }) => (
          <Col span={6} key={label}>
            <Card>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm mb-1" style={{ color: NEUTRAL[500] }}>{label}</p>
                  <p className="text-2xl font-bold tabular-nums" style={{ color: NEUTRAL[800] }}>{value}</p>
                </div>
                <Icon className="text-3xl" style={{ color: BRAND[400] }} />
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      {/* Data Freshness Table */}
      <Card
        title={
          <span className="text-lg font-semibold flex items-center">
            <CalendarOutlined className="mr-2" />
            Mức Độ Hoàn Chỉnh Dữ Liệu Theo Tham Số
          </span>
        }
        extra={
          <Button icon={<SyncOutlined />} type="primary" onClick={refresh}>
            Làm Mới
          </Button>
        }
      >
        <Table
          columns={freshnessColumns}
          dataSource={dataFreshness}
          pagination={false}
          size="middle"
          rowKey="source"
        />
      </Card>

      {/* Quality Metrics & Parameter Coverage */}
      <Row gutter={16}>
        <Col span={10}>
          <Card title={<span className="text-lg font-semibold">Chỉ Số Chất Lượng So Với Mục Tiêu</span>}>
            <div className="space-y-4">
              {qualityMetrics.map((metric) => {
                const metricNames = {
                  'Completeness': 'Tính Đầy Đủ',
                  'Zero-free Rate': 'Tỉ Lệ Dữ Liệu Hợp Lệ',
                  'Parameters': 'Số Tham Số',
                }
                return (
                <div key={metric.metric}>
                  <div className="flex justify-between mb-1">
                    <span className="text-sm font-medium">{metricNames[metric.metric] || metric.metric}</span>
                    <span className="text-sm text-gray-500">{metric.value}% / {metric.target}%</span>
                  </div>
                  <Progress
                    percent={metric.value}
                    strokeColor={metric.value >= metric.target ? SEMANTIC.good : metric.value >= 70 ? SEMANTIC.warn : SEMANTIC.bad}
                    size="small"
                    format={(pct) => `${pct}%`}
                  />
                </div>
              )})}
            </div>
          </Card>
        </Col>
        <Col span={14}>
          <Card title={<span className="text-lg font-semibold">Độ Hoàn Chỉnh Từng Tham Số (%)</span>}>
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={paramBarData} margin={{ top: 28, right: 24, left: 8, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tickFormatter={paramLabel} angle={-25} textAnchor="end" interval={0} height={70} tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tickFormatter={v => `${v}%`} />
                <RechartsTooltip
                  labelFormatter={paramLabel}
                  formatter={(v, name) => [`${v}%`, name === 'completeness' ? 'Tính Đầy Đủ' : 'Hợp Lệ']}
                />
                <Bar dataKey="completeness" name="Tính Đầy Đủ" radius={[4,4,0,0]}>
                  {paramBarData.map((entry, idx) => (
                    <Cell key={entry.name} fill={entry.completeness >= 95 ? SEMANTIC.good : entry.completeness >= 70 ? SEMANTIC.warn : SEMANTIC.bad} />
                  ))}
                  <LabelList dataKey="completeness" position="top" formatter={v => `${v}%`} style={{ fontSize: 11 }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

    </div>
    </Spin>
  )
}

export default DataOverview
