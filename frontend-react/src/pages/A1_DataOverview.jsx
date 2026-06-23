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
      lastUpdated: `${p.num_entries} entries`,
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
  const PARAM_COLORS = ['#1890ff','#52c41a','#fa8c16','#f5222d','#722ed1','#13c2c2','#eb2f96','#a0d911','#faad14','#2f54eb']

  const freshSources = dataFreshness.filter(d => d.status === 'Fresh' || d.status === 'Good').length

  const freshnessColumns = [
    {
      title: 'Nguồn Dữ Liệu',
      dataIndex: 'source',
      key: 'source',
      render: (text) => (
        <span className="flex items-center">
          <DatabaseOutlined className="mr-2 text-blue-500" />
          {text}
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
      {error && <Alert message="Error loading data" description={error} type="error" showIcon closable />}
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-primary-700 mb-2">
          <BarChartOutlined className="mr-3" />
          A1. Tổng Quan Dữ Liệu Đầu Vào
        </h1>
        <p className="text-gray-600">
          Giám sát mức độ đầy đủ dữ liệu, chất lượng và bảo đảm toàn bộ nguồn dữ liệu
        </p>
      </div>

      {/* Summary Cards */}
      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">Sản Phẩm</p>
                <p className="text-2xl font-bold text-green-600">{numProducts}</p>
              </div>
              <CheckCircleOutlined className="text-3xl text-green-500" />
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">Kho Hàng</p>
                <p className="text-2xl font-bold text-blue-600">{numWarehouses}</p>
              </div>
              <DatabaseOutlined className="text-3xl text-blue-500" />
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">Kỳ Thời Gian</p>
                <p className="text-2xl font-bold text-purple-600">{numPeriods}</p>
              </div>
              <CalendarOutlined className="text-3xl text-purple-500" />
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">Tổ Hợp (SP-Kho)</p>
                <p className="text-2xl font-bold text-orange-600">{totalCombinations}</p>
              </div>
              <SyncOutlined className="text-3xl text-orange-500" />
            </div>
          </Card>
        </Col>
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
                    strokeColor={metric.value >= metric.target ? '#52c41a' : metric.value >= 70 ? '#fa8c16' : '#f5222d'}
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
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={paramBarData} margin={{ top: 28, right: 24, left: 8, bottom: 16 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis domain={[0, 100]} tickFormatter={v => `${v}%`} />
                <RechartsTooltip formatter={(v, name) => [`${v}%`, name === 'completeness' ? 'Tính Đầy Đủ' : 'Hợp Lệ']} />
                <Bar dataKey="completeness" name="Tính Đầy Đủ" radius={[4,4,0,0]}>
                  {paramBarData.map((entry, idx) => (
                    <Cell key={entry.name} fill={entry.completeness >= 95 ? '#52c41a' : entry.completeness >= 70 ? '#fa8c16' : '#f5222d'} />
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
