import React, { useState } from 'react'
import { Card, Row, Col, Table, Button, Tag, Select, Progress, Alert, Switch, Timeline, Statistic, Spin, InputNumber, message } from 'antd'
import {
  BulbOutlined, TrophyOutlined, CheckCircleOutlined, ExclamationCircleOutlined,
  RightCircleOutlined, ClockCircleOutlined, DollarOutlined, EyeOutlined, StarFilled,
} from '@ant-design/icons'
import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Legend } from 'recharts'
import { useApi } from '../hooks/useApi'
import { useAppContext } from '../context/AppContext'
import insightsService from '../services/insightsService'
import optimizationService from '../services/optimizationService'

const { Option } = Select

const DecisionInsights = () => {
  const { activeRunId, setActiveRunId } = useAppContext()
  const [runIdInput, setRunIdInput] = useState(activeRunId || 1)
  const [priorityFilter, setPriorityFilter] = useState('all')
  const [showImplementationPlan, setShowImplementationPlan] = useState(true)

  const { data: insightsData, loading: loadingInsights, error } = useApi(
    () => activeRunId ? insightsService.getInsights(activeRunId) : Promise.resolve(null),
    [activeRunId]
  )

  const { data: summaryData, loading: loadingSummary } = useApi(
    () => activeRunId ? optimizationService.getExecutiveSummary(activeRunId) : Promise.resolve(null),
    [activeRunId]
  )

  const loading = loadingInsights || loadingSummary
  const insights = insightsData?.insights || []
  const kpis = summaryData?.kpis || {}
  const run = summaryData?.run || {}

  const filteredInsights = insights.filter(ins => {
    if (priorityFilter === 'all') return true
    if (priorityFilter === 'critical') return ins.severity === 'CRITICAL'
    if (priorityFilter === 'warning') return ins.severity === 'CRITICAL' || ins.severity === 'WARNING'
    return true
  })

  const severityColors = { CRITICAL: 'red', WARNING: 'orange', INFO: 'blue', OPPORTUNITY: 'green' }

  const insightColumns = [
    {
      title: 'Insight', key: 'insight', width: 250,
      render: (_, record) => (
        <div>
          <div className="font-medium text-gray-900">{record.title}</div>
          <div className="text-sm text-gray-600">{record.category}</div>
        </div>
      ),
    },
    {
      title: 'Severity', dataIndex: 'severity', key: 'severity', width: 100,
      render: (s) => <Tag color={severityColors[s] || 'blue'}>{s}</Tag>,
    },
    {
      title: 'Description', dataIndex: 'description', key: 'description', width: 300,
      render: (text) => <span className="text-sm">{text}</span>,
    },
    {
      title: 'Affected', key: 'affected', width: 150,
      render: (_, record) => (
        <div className="text-xs">
          {(record.affected_products || []).length > 0 && <div>Products: {record.affected_products.join(', ')}</div>}
          {(record.affected_warehouses || []).length > 0 && <div>Warehouses: {record.affected_warehouses.join(', ')}</div>}
        </div>
      ),
    },
    {
      title: 'Metric', key: 'metric', width: 120,
      render: (_, record) => record.metric_name ? (
        <div className="text-sm"><span className="text-gray-500">{record.metric_name}:</span> <span className="font-bold">{Number(record.metric_value || 0).toFixed(2)}</span></div>
      ) : 'N/A',
    },
  ]

  if (!activeRunId) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-primary-700 mb-2"><BulbOutlined className="mr-3" />F1. Decision Insights</h1>
        <Alert message="No Optimization Run Selected" description="Enter a run ID to generate decision insights." type="info" showIcon />
        <Card><div className="flex items-center gap-4"><span>Run ID:</span><InputNumber min={1} value={runIdInput} onChange={setRunIdInput} /><Button type="primary" onClick={() => setActiveRunId(runIdInput)}>Load Insights</Button></div></Card>
      </div>
    )
  }

  return (
    <Spin spinning={loading}>
    <div className="space-y-6">
      {error && <Alert message="Error loading insights" description={error} type="error" showIcon closable />}

      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-primary-700 mb-2"><BulbOutlined className="mr-3" />F1. Decision Insights</h1>
          <p className="text-gray-600">Run #{activeRunId} | {insightsData?.total_insights || 0} insights generated</p>
        </div>
        <div className="flex items-center gap-2">
          <InputNumber min={1} value={runIdInput} onChange={setRunIdInput} size="small" />
          <Button onClick={() => setActiveRunId(runIdInput)} size="small">Load</Button>
        </div>
      </div>

      <Card title={<span className="text-lg font-semibold flex items-center"><TrophyOutlined className="mr-2" />Executive Summary</span>}>
        <Row gutter={[16, 16]}>
          <Col span={4}><Statistic title="Total Cost" value={Number(kpis.total_cost || 0)} precision={2} prefix="$" valueStyle={{ color: '#fa541c' }} /></Col>
          <Col span={4}><Statistic title="Service Level" value={Number(kpis.service_level || 0)} precision={1} suffix="%" valueStyle={{ color: '#52c41a' }} /></Col>
          <Col span={4}><Statistic title="Capacity Util." value={Number(kpis.capacity_utilization || 0)} precision={1} suffix="%" valueStyle={{ color: '#1890ff' }} /></Col>
          <Col span={4}><Statistic title="Critical Issues" value={insightsData?.critical_count || 0} valueStyle={{ color: '#ff4d4f' }} prefix={<ExclamationCircleOutlined />} /></Col>
          <Col span={4}><Statistic title="Warnings" value={insightsData?.warning_count || 0} valueStyle={{ color: '#fa8c16' }} /></Col>
          <Col span={4}><Statistic title="Opportunities" value={insightsData?.opportunity_count || 0} valueStyle={{ color: '#52c41a' }} prefix={<CheckCircleOutlined />} /></Col>
        </Row>

        {(insightsData?.critical_count || 0) > 0 && (
          <Alert className="mt-4" message="Action Required" description={`${insightsData.critical_count} critical issue(s) detected. Review insights below for recommendations.`} type="error" showIcon icon={<ExclamationCircleOutlined />} />
        )}
        {(insightsData?.critical_count || 0) === 0 && (insightsData?.opportunity_count || 0) > 0 && (
          <Alert className="mt-4" message="Opportunities Available" description={`${insightsData.opportunity_count} optimization opportunity(ies) identified.`} type="success" showIcon icon={<BulbOutlined />} />
        )}
      </Card>

      <Card title={<span className="text-lg font-semibold">Insights & Recommendations</span>}>
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div>
              <label className="block text-sm font-medium mb-1">Filter</label>
              <Select value={priorityFilter} onChange={setPriorityFilter} style={{ width: 150 }}>
                <Option value="all">All ({insights.length})</Option>
                <Option value="critical">Critical Only ({insights.filter(i => i.severity === 'CRITICAL').length})</Option>
                <Option value="warning">Critical + Warning ({insights.filter(i => ['CRITICAL', 'WARNING'].includes(i.severity)).length})</Option>
              </Select>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-sm">Expand Details:</span>
            <Switch checked={showImplementationPlan} onChange={setShowImplementationPlan} checkedChildren="ON" unCheckedChildren="OFF" />
          </div>
        </div>

        <Table
          columns={insightColumns}
          dataSource={filteredInsights}
          rowKey="insight_id"
          pagination={{ pageSize: 10 }}
          scroll={{ x: 1000 }}
          expandable={showImplementationPlan ? {
            expandedRowRender: (record) => (
              <div className="bg-gray-50 p-4 rounded">
                <Row gutter={16}>
                  <Col span={16}>
                    <h4 className="font-semibold text-gray-700 mb-3">Recommendation</h4>
                    <p className="text-sm text-gray-600">{record.recommendation}</p>
                    {record.affected_products?.length > 0 && (
                      <div className="mt-2"><span className="text-sm font-medium">Products:</span> {record.affected_products.map(p => <Tag key={p} color="blue" className="ml-1">{p}</Tag>)}</div>
                    )}
                    {record.affected_warehouses?.length > 0 && (
                      <div className="mt-1"><span className="text-sm font-medium">Warehouses:</span> {record.affected_warehouses.map(w => <Tag key={w} color="green" className="ml-1">{w}</Tag>)}</div>
                    )}
                  </Col>
                  <Col span={8}>
                    <h4 className="font-semibold text-gray-700 mb-3">Metrics</h4>
                    {record.metric_name && (
                      <div className="border rounded p-2 bg-white">
                        <div className="text-sm font-medium">{record.metric_name}</div>
                        <div className="text-lg font-bold">{Number(record.metric_value || 0).toFixed(2)}</div>
                        {record.threshold && <div className="text-xs text-gray-500">Threshold: {record.threshold}</div>}
                      </div>
                    )}
                  </Col>
                </Row>
              </div>
            ),
          } : undefined}
        />
      </Card>

      <Card title="Next Steps">
        <Row gutter={16}>
          <Col span={8}><div className="bg-green-50 p-4 rounded border border-green-200"><div className="flex items-center mb-3"><CheckCircleOutlined className="text-green-500 mr-2 text-lg" /><span className="font-semibold text-green-700">Immediate Actions</span></div><div className="text-sm text-green-600 space-y-2">{insights.filter(i => i.severity === 'CRITICAL').slice(0, 3).map((ins, idx) => <div key={idx}>- {ins.title}</div>)}{insights.filter(i => i.severity === 'CRITICAL').length === 0 && <div>- No critical actions needed</div>}</div></div></Col>
          <Col span={8}><div className="bg-blue-50 p-4 rounded border border-blue-200"><div className="flex items-center mb-3"><ClockCircleOutlined className="text-blue-500 mr-2 text-lg" /><span className="font-semibold text-blue-700">Warnings to Address</span></div><div className="text-sm text-blue-600 space-y-2">{insights.filter(i => i.severity === 'WARNING').slice(0, 3).map((ins, idx) => <div key={idx}>- {ins.title}</div>)}{insights.filter(i => i.severity === 'WARNING').length === 0 && <div>- No warnings at this time</div>}</div></div></Col>
          <Col span={8}><div className="bg-purple-50 p-4 rounded border border-purple-200"><div className="flex items-center mb-3"><TrophyOutlined className="text-purple-500 mr-2 text-lg" /><span className="font-semibold text-purple-700">Opportunities</span></div><div className="text-sm text-purple-600 space-y-2">{insights.filter(i => i.severity === 'OPPORTUNITY').slice(0, 3).map((ins, idx) => <div key={idx}>- {ins.title}</div>)}{insights.filter(i => i.severity === 'OPPORTUNITY').length === 0 && <div>- No opportunities identified yet</div>}</div></div></Col>
        </Row>
      </Card>
    </div>
    </Spin>
  )
}

export default DecisionInsights
