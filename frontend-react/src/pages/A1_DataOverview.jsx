import React, { useState } from 'react'
import { Card, Row, Col, Table, Tag, Progress, Button, Radio, Select, Tooltip, Spin, Alert } from 'antd'
import {
  DatabaseOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  CalendarOutlined,
  BarChartOutlined,
  HeatMapOutlined,
  SyncOutlined,
} from '@ant-design/icons'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts'
import { useApi } from '../hooks/useApi'
import dataService from '../services/dataService'

const { Option } = Select

const DataOverview = () => {
  const [timeView, setTimeView] = useState('daily')
  const [selectedRegion, setSelectedRegion] = useState('all')
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

  // Map parameters to Data Freshness format
  const dataFreshness = parameters.map((p) => {
    const completeness = totalCombinations > 0 ? Math.round((p.num_entries / totalCombinations) * 100) : 0
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

  // Quality metrics derived from parameters
  const qualityMetrics = [
    { metric: 'Completeness', value: parameters.length > 0 ? Math.round(parameters.reduce((s, p) => s + (totalCombinations > 0 ? p.num_entries / totalCombinations : 0), 0) / parameters.length * 100) : 0, target: 95 },
    { metric: 'Zero-free Rate', value: parameters.length > 0 ? Math.round(parameters.reduce((s, p) => s + (p.num_entries > 0 ? (1 - p.zero_count / p.num_entries) : 0), 0) / parameters.length * 100) : 0, target: 90 },
    { metric: 'Coverage', value: totalCombinations > 0 ? Math.round((numProducts * numWarehouses * numPeriods) / totalCombinations * 100) : 0, target: 90 },
    { metric: 'Parameters', value: parameters.length > 0 ? 100 : 0, target: 85 },
  ]

  // Coverage heatmap from products x warehouses
  const coverageData = products.flatMap(prod =>
    warehouses.map(wh => ({
      region: wh,
      product: prod,
      coverage: totalCombinations > 0 ? Math.round((parameters.filter(p => p.num_entries > 0).length / parameters.length) * 100) : 0,
      demand: totalCombinations,
    }))
  )

  // Static trend data (no historical endpoint)
  const trendData = [
    { period: 'T1', freshness: 95, quality: 92, coverage: 88 },
    { period: 'T2', freshness: 92, quality: 94, coverage: 90 },
    { period: 'T3', freshness: 89, quality: 96, coverage: 92 },
    { period: 'T4', freshness: 87, quality: 95, coverage: 89 },
    { period: 'T5', freshness: 85, quality: 93, coverage: 91 },
    { period: 'T6', freshness: 88, quality: 94, coverage: 93 },
  ]

  const freshSources = dataFreshness.filter(d => d.status === 'Fresh' || d.status === 'Good').length
  const avgQuality = qualityMetrics.length > 0 ? Math.round(qualityMetrics.reduce((s, m) => s + m.value, 0) / qualityMetrics.length) : 0

  const freshnessColumns = [
    {
      title: 'Data Source',
      dataIndex: 'source',
      key: 'source',
      render: (text) => (
        <span className="flex items-center">
          <DatabaseOutlined className="mr-2 text-blue-500" />
          {text}
        </span>
      ),
    },
    { title: 'Entries', dataIndex: 'lastUpdated', key: 'lastUpdated' },
    {
      title: 'Staleness',
      dataIndex: 'staleness',
      key: 'staleness',
      render: (value) => {
        let color = 'red'
        if (value >= 85) color = 'green'
        else if (value >= 70) color = 'orange'

        return (
          <div className="flex items-center space-x-2 w-32">
            <Progress percent={value} size="small" status={color === 'red' ? 'exception' : 'normal'} strokeColor={color} />
            <span className="text-xs">{value}%</span>
          </div>
        )
      },
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status) => {
        const configs = {
          Fresh: { color: 'green', icon: CheckCircleOutlined },
          Good: { color: 'blue', icon: CheckCircleOutlined },
          Moderate: { color: 'orange', icon: ClockCircleOutlined },
          Stale: { color: 'red', icon: ExclamationCircleOutlined },
          Critical: { color: 'red', icon: ExclamationCircleOutlined },
        }
        const config = configs[status] || configs.Critical
        const Icon = config.icon
        return (
          <Tag color={config.color} icon={<Icon />}>
            {status}
          </Tag>
        )
      },
    },
  ]

  const getCoverageColor = (coverage) => {
    if (coverage >= 95) return '#52c41a'
    if (coverage >= 90) return '#1890ff'
    if (coverage >= 85) return '#fa8c16'
    return '#f5222d'
  }

  return (
    <Spin spinning={loading}>
    <div className="space-y-6">
      {error && <Alert message="Error loading data" description={error} type="error" showIcon closable />}
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-primary-700 mb-2">
          <BarChartOutlined className="mr-3" />
          A1. Data Overview
        </h1>
        <p className="text-gray-600">
          Monitor data freshness, quality metrics, and coverage across all sources
        </p>
      </div>

      {/* Summary Cards */}
      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">Products</p>
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
                <p className="text-sm text-gray-500 mb-1">Warehouses</p>
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
                <p className="text-sm text-gray-500 mb-1">Time Periods</p>
                <p className="text-2xl font-bold text-purple-600">{numPeriods}</p>
              </div>
              <HeatMapOutlined className="text-3xl text-purple-500" />
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500 mb-1">Combinations</p>
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
            Data Freshness & Completeness
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

      {/* Quality Metrics & Trends */}
      <Row gutter={16}>
        <Col span={12}>
          <Card
            title={
              <span className="text-lg font-semibold">
                Quality Metrics vs Targets
              </span>
            }
          >
            <div className="space-y-4">
              {qualityMetrics.map((metric) => (
                <div key={metric.metric}>
                  <div className="flex justify-between mb-1">
                    <span className="text-sm font-medium">{metric.metric}</span>
                    <span className="text-sm">{metric.value}% / {metric.target}%</span>
                  </div>
                  <Progress
                    percent={metric.value}
                    strokeColor={metric.value >= metric.target ? '#52c41a' : '#fa8c16'}
                    size="small"
                  />
                </div>
              ))}
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card
            title={<span className="text-lg font-semibold">Data Trends</span>}
            extra={
              <Radio.Group
                value={timeView}
                onChange={(e) => setTimeView(e.target.value)}
                size="small"
                buttonStyle="solid"
              >
                <Radio.Button value="hourly">Hourly</Radio.Button>
                <Radio.Button value="daily">Daily</Radio.Button>
              </Radio.Group>
            }
          >
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="period" />
                <YAxis domain={[75, 100]} />
                <RechartsTooltip />
                <Line type="monotone" dataKey="freshness" stroke="#f5222d" name="Freshness" />
                <Line type="monotone" dataKey="quality" stroke="#1890ff" name="Quality" />
                <Line type="monotone" dataKey="coverage" stroke="#52c41a" name="Coverage" />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      {/* Coverage Heatmap */}
      <Card
        title={
          <span className="text-lg font-semibold flex items-center">
            <HeatMapOutlined className="mr-2" />
            Product-Warehouse Coverage
          </span>
        }
        extra={
          <Select
            value={selectedRegion}
            onChange={setSelectedRegion}
            style={{ width: 120 }}
          >
            <Option value="all">All</Option>
            {warehouses.map(w => <Option key={w} value={w}>{w}</Option>)}
          </Select>
        }
      >
        <div className="grid grid-cols-3 gap-4">
          {warehouses.map(wh => (
            <div key={wh} className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-semibold text-center mb-3">{wh}</h4>
              <div className="space-y-2">
                {coverageData
                  .filter(d => d.region === wh)
                  .map(item => (
                    <Tooltip
                      key={`${item.region}-${item.product}`}
                      title={`${item.product}: ${item.coverage}% coverage`}
                    >
                      <div className="flex items-center justify-between p-2 rounded" style={{ backgroundColor: getCoverageColor(item.coverage), opacity: 0.8 }}>
                        <span className="text-white font-medium text-sm">{item.product}</span>
                        <span className="text-white font-bold text-sm">{item.coverage}%</span>
                      </div>
                    </Tooltip>
                  ))
                }
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
    </Spin>
  )
}

export default DataOverview
