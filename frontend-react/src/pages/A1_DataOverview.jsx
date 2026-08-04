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

// English labels for model parameter symbols (Table 3.3 in the thesis)
const PARAM_LABEL = {
  BI: 'Beginning Inventory (BI)',
  CP: 'Packing Configuration (CP)',
  U: 'Ceiling Level (U)',
  L: 'Floor Level (L)',
  DI: 'Exogenous Inventory Variation (ΔI)',
  CAP: 'Supply Capacity (CAP)',
  Cb: 'Backorder Cost (Cb)',
  Co: 'Overstock Cost (Co)',
  Cs: 'Shortage Cost (Cs)',
  Cp: 'Packing Penalty Cost (Cp)',
  LT_OA: 'Lead Time from Central Warehouse (LT_OA)',
  LT_PLT: 'Lateral Transshipment Lead Time (LT_PLT)',
  d: 'Distance Between Warehouses (d)',
}
const paramLabel = (symbol) => PARAM_LABEL[symbol] || symbol

const DataOverview = () => {
  const { data, loading, error, execute: refresh } = useApi(() => dataService.getOverview(), [], { cacheKey: 'data-overview' })

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
      lastUpdated: `${Number(p.num_entries).toLocaleString('en-US')} records`,
      status,
      staleness: completeness,
    }
  })

  // Quality metrics — derived from real parameter data
  //   Completeness : avg(num_entries / max_entries) per param
  //   Parameters   : 100% if all 13 params present
  // (Removed "Zero-free Rate": with real operational data, a value of 0 is
  //  normal — e.g. no penalty cost incurred — so the non-zero ratio does not
  //  reflect data quality.)
  const avgCompleteness = parameters.length > 0
    ? Math.round(parameters.reduce((s, p) => s + (p.max_entries > 0 ? p.num_entries / p.max_entries : 0), 0) / parameters.length * 100)
    : 0

  const qualityMetrics = [
    { metric: 'Completeness', value: avgCompleteness, target: 95 },
    { metric: 'Parameters', value: parameters.length >= 13 ? 100 : Math.round(parameters.length / 13 * 100), target: 85 },
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
      title: 'Data Source',
      dataIndex: 'source',
      key: 'source',
      render: (text) => (
        <span className="flex items-center">
          <DatabaseOutlined className="mr-2" style={{ color: BRAND[400] }} />
          {paramLabel(text)}
        </span>
      ),
    },
    { title: 'Records', dataIndex: 'lastUpdated', key: 'lastUpdated' },
    {
      title: 'Completeness (%)',
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
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status) => {
        const statusMap = {
          Fresh: { label: 'Fresh', color: 'green', icon: CheckCircleOutlined },
          Good: { label: 'Good', color: 'blue', icon: CheckCircleOutlined },
          Moderate: { label: 'Moderate', color: 'orange', icon: ClockCircleOutlined },
          Stale: { label: 'Stale', color: 'red', icon: ExclamationCircleOutlined },
          Critical: { label: 'Critical', color: 'red', icon: ExclamationCircleOutlined },
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
      <PageHeader
        icon={<BarChartOutlined />}
        title="A1. Input Data Overview"
        subtitle="Monitor the completeness, quality, and readiness of all data sources"
      />

      {/* Summary Cards — consistent brand tone, bold ink numbers, light brand icons */}
      <Row gutter={16}>
        {[
          { label: 'Products',              value: numProducts,       Icon: CheckCircleOutlined },
          { label: 'Warehouses',            value: numWarehouses,     Icon: DatabaseOutlined },
          { label: 'Time Periods',          value: numPeriods,        Icon: CalendarOutlined },
          { label: 'Combinations (Prod-WH)', value: totalCombinations, Icon: SyncOutlined },
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
            Data Completeness by Parameter
          </span>
        }
        extra={
          <Button icon={<SyncOutlined />} type="primary" onClick={refresh}>
            Refresh
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
          <Card title={<span className="text-lg font-semibold">Quality Metrics vs. Target</span>}>
            <div className="space-y-4">
              {qualityMetrics.map((metric) => {
                const metricNames = {
                  'Completeness': 'Data Completeness',
                  'Parameters': 'Parameter Coverage',
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
          <Card title={<span className="text-lg font-semibold">Completeness by Parameter (%)</span>}>
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={paramBarData} margin={{ top: 28, right: 24, left: 8, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tickFormatter={paramLabel} angle={-25} textAnchor="end" interval={0} height={70} tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tickFormatter={v => `${v}%`} />
                <RechartsTooltip
                  labelFormatter={paramLabel}
                  formatter={(v, name) => [`${v}%`, name === 'completeness' ? 'Completeness' : 'Valid']}
                />
                <Bar dataKey="completeness" name="Completeness" radius={[4,4,0,0]}>
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
