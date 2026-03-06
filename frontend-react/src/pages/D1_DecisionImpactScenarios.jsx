import React, { useState } from 'react'
import { Card, Row, Col, Table, Tag, Button, Alert, Spin, Select, InputNumber } from 'antd'
import {
  ApartmentOutlined, ThunderboltOutlined, RiseOutlined, FallOutlined,
} from '@ant-design/icons'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ScatterChart, Scatter, ZAxis } from 'recharts'
import { useApi } from '../hooks/useApi'
import scenarioService from '../services/scenarioService'

const DecisionImpactScenarios = () => {
  const [baseRunId, setBaseRunId] = useState(null)
  const [compareRunId, setCompareRunId] = useState(null)

  const { data: scenariosData, loading: loadingScenarios } = useApi(() => scenarioService.getScenarios())
  const { data: comparison, loading: comparing, execute: runCompare } = useApi(
    () => baseRunId && compareRunId ? scenarioService.compareWhatIf(baseRunId, compareRunId) : Promise.resolve(null),
    [baseRunId, compareRunId],
    { immediate: false }
  )

  const scenarios = scenariosData?.scenarios || []
  const deltas = comparison?.deltas || []

  const impactData = deltas.map(d => ({
    kpi: d.kpi_name,
    impact: Number(d.absolute_change) || 0,
    pctChange: Number(d.percent_change) || 0,
  }))

  const scenarioColumns = [
    { title: 'ID',    dataIndex: 'scenario_id',   key: 'scenario_id',   width: 60 },
    { title: 'Tên',  dataIndex: 'scenario_name', key: 'scenario_name', render: (t) => <span className="font-semibold">{t}</span> },
    { title: 'Cơ sở', dataIndex: 'is_baseline',   key: 'is_baseline',   render: (v) => v ? <Tag color="green">Âng</Tag> : <Tag>Không</Tag> },
    { title: 'Ngày tạo', dataIndex: 'created_at', key: 'created_at', render: (t) => t ? new Date(t).toLocaleDateString('vi-VN') : 'N/A' },
  ]

  const impactColumns = [
    { title: 'KPI', dataIndex: 'kpi_name', key: 'kpi_name', render: (t) => <span className="font-semibold">{t}</span> },
    { title: 'Cơ sở', dataIndex: 'base_value', key: 'base_value', render: (v) => Number(v).toLocaleString('vi-VN') },
    { title: 'Kịch bản', dataIndex: 'whatif_value', key: 'whatif_value', render: (v) => Number(v).toLocaleString('vi-VN') },
    {
      title: 'Tác động', dataIndex: 'percent_change', key: 'percent_change',
      render: (v) => {
        const n = Number(v)
        const icon = n > 0 ? <RiseOutlined /> : <FallOutlined />
        return <Tag color={n > 0 ? 'red' : 'green'} icon={icon}>{n > 0 ? '+' : ''}{n.toFixed(1)}%</Tag>
      },
    },
  ]

  return (
    <Spin spinning={loadingScenarios || comparing}>
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-primary-700 mb-2"><ApartmentOutlined className="mr-3" />D1. Tác động quyết định</h1>
        <p className="text-gray-600">Phân tích tác động của các quyết định đến các chỉ số hiệu suất</p>
      </div>

      <Card title="Kịch bản hiện có">
        <Table columns={scenarioColumns} dataSource={scenarios} pagination={{ pageSize: 5 }} size="small" rowKey="scenario_id" />
      </Card>

      <Card title="So sánh lần chạy">
        <div className="flex items-center gap-4 flex-wrap">
          <div><span className="mr-2">Lần chạy cơ sở:</span><InputNumber min={1} value={baseRunId} onChange={setBaseRunId} /></div>
          <div><span className="mr-2">Lần chạy so sánh:</span><InputNumber min={1} value={compareRunId} onChange={setCompareRunId} /></div>
          <Button type="primary" icon={<ThunderboltOutlined />} onClick={runCompare} disabled={!baseRunId || !compareRunId}>Phân tích tác động</Button>
        </div>
      </Card>

      {comparison && (
        <>
          <Card title="Phân tích tác động">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={impactData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="kpi" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="impact" fill="#1890ff" name="Tác động tuyệt đối" />
                <Bar dataKey="pctChange" fill="#f5222d" name="% Thay đổi" />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card title="Chi tiết tác động">
            <Table columns={impactColumns} dataSource={deltas} pagination={false} size="middle" rowKey="kpi_name" />
          </Card>
        </>
      )}

      {!comparison && !comparing && (
        <Alert message="Chọn hai mã lần chạy và nhấn Phân tích tác động để hiển thị kết quả" type="info" showIcon />
      )}
    </div>
    </Spin>
  )
}

export default DecisionImpactScenarios
