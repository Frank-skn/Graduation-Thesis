import { useState } from 'react'
import { Card, Table, Tag, Button, Alert, Spin } from 'antd'
import {
  ApartmentOutlined, ThunderboltOutlined, RiseOutlined, FallOutlined, CheckCircleOutlined,
} from '@ant-design/icons'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { useApi } from '../hooks/useApi'
import scenarioService from '../services/scenarioService'
import optimizationService from '../services/optimizationService'

const DecisionImpactScenarios = () => {
  const [baseRunId, setBaseRunId] = useState(null)
  const [compareRunId, setCompareRunId] = useState(null)

  const { data: runsData, loading: loadingRuns } = useApi(() => optimizationService.listRuns())
  const { data: comparison, loading: comparing, execute: runCompare } = useApi(
    () => baseRunId && compareRunId ? scenarioService.compareWhatIf(baseRunId, compareRunId) : Promise.resolve(null),
    [baseRunId, compareRunId],
    { immediate: false }
  )

  const runs = (runsData?.runs || runsData || [])
  const deltas = comparison?.deltas || []

  const impactData = deltas.map(d => ({
    kpi: d.kpi_name,
    impact: Number(d.absolute_change) || 0,
    pctChange: Number(d.percent_change) || 0,
  }))

  const runColumns = [
    { title: 'Run ID', dataIndex: 'run_id', key: 'run_id', width: 80, render: (v) => <span className="font-mono font-bold text-blue-600">{v}</span> },
    { title: 'Kết quả tối ưu', dataIndex: 'objective_value', key: 'objective_value', render: (v) => Number(v).toLocaleString('vi-VN') },
    { title: 'Trạng thái', dataIndex: 'solver_status', key: 'solver_status', render: (s) => <Tag color="green" icon={<CheckCircleOutlined />}>{s}</Tag> },
    { title: 'Thời gian chạy', dataIndex: 'run_time', key: 'run_time', render: (t) => t ? new Date(t).toLocaleString('vi-VN') : 'N/A' },
    {
      title: 'Chọn làm',
      key: 'action',
      render: (_, record) => (
        <div className="flex gap-2">
          <Button
            size="small"
            type={baseRunId === record.run_id ? 'primary' : 'default'}
            onClick={() => setBaseRunId(record.run_id)}
          >
            Cơ sở
          </Button>
          <Button
            size="small"
            type={compareRunId === record.run_id ? 'primary' : 'default'}
            danger={compareRunId === record.run_id}
            onClick={() => setCompareRunId(record.run_id)}
          >
            So sánh
          </Button>
        </div>
      ),
    },
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

  const runLabel = (id) => {
    const r = runs.find(r => r.run_id === id)
    return r ? `Run #${r.run_id} (${Number(r.objective_value).toLocaleString('vi-VN')})` : `Run #${id}`
  }

  return (
    <Spin spinning={loadingRuns || comparing}>
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-primary-700 mb-2"><ApartmentOutlined className="mr-3" />D1. Tác Động Quyết Định Phân Bổ</h1>
        <p className="text-gray-600">Phân tích tác động của các quyết định đến các chỉ số hiệu suất</p>
      </div>

      <Card
        title="Các lần chạy tối ưu"
        extra={<span className="text-sm text-gray-400">Chọn hai lần chạy để so sánh bằng cách nhấn nút bên dưới</span>}
      >
        <Table
          columns={runColumns}
          dataSource={runs}
          pagination={{ pageSize: 5 }}
          size="small"
          rowKey="run_id"
          rowClassName={(record) => {
            if (record.run_id === baseRunId) return 'bg-blue-50'
            if (record.run_id === compareRunId) return 'bg-red-50'
            return ''
          }}
        />
      </Card>

      <Card title="So sánh">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-gray-500">Cơ sở:</span>
            {baseRunId
              ? <Tag color="blue">{runLabel(baseRunId)}</Tag>
              : <span className="text-gray-400 italic">Chưa chọn</span>
            }
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-500">So sánh:</span>
            {compareRunId
              ? <Tag color="red">{runLabel(compareRunId)}</Tag>
              : <span className="text-gray-400 italic">Chưa chọn</span>
            }
          </div>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={runCompare}
            disabled={!baseRunId || !compareRunId || baseRunId === compareRunId}
          >
            Phân tích tác động
          </Button>
          {baseRunId === compareRunId && baseRunId && (
            <span className="text-orange-500 text-sm">Vui lòng chọn hai lần chạy khác nhau</span>
          )}
        </div>
      </Card>

      {comparison && (
        <>
          <Card title="Biểu đồ tác động KPI">
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
        <Alert
          message="Hướng dẫn sử dụng"
          description="Chọn lần chạy cơ sở và lần chạy so sánh từ bảng bên trên bằng cách nhấn nút 'Cơ sở' và 'So sánh', sau đó nhấn 'Phân tích tác động' để xem kết quả."
          type="info"
          showIcon
        />
      )}
    </div>
    </Spin>
  )
}

export default DecisionImpactScenarios
