import React, { useState, useEffect, useCallback } from 'react'
import { Card, Row, Col, Table, Tag, Button, Alert, Spin, Select } from 'antd'
import { SwapOutlined, BarChartOutlined, ReloadOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import scenarioService from '../services/scenarioService'
import optimizationService from '../services/optimizationService'
import PageHeader from '../components/PageHeader'
import { BRAND, NEUTRAL } from '../theme/tokens'

const { Option } = Select
const fmt = (v, d = 0) =>
  typeof v === 'number' ? v.toLocaleString('vi-VN', { maximumFractionDigits: d }) : '—'

const ScenarioComparison = () => {
  const [runs, setRuns]               = useState([])
  const [runsLoading, setRunsLoading] = useState(true)
  const [baseRunId, setBaseRunId]     = useState(null)
  const [compareRunId, setCompareRunId] = useState(null)
  const [data, setData]               = useState(null)
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState(null)

  const loadRuns = useCallback(() => {
    setRunsLoading(true)
    optimizationService.listRuns()
      .then((res) => {
        const list = Array.isArray(res) ? res : (res?.runs ?? [])
        setRuns(list)
      })
      .catch(() => setRuns([]))
      .finally(() => setRunsLoading(false))
  }, [])

  useEffect(() => { loadRuns() }, [loadRuns])

  const handleCompare = async () => {
    if (!baseRunId || !compareRunId) return
    setLoading(true)
    setError(null)
    try {
      const res = await scenarioService.compareWhatIf(baseRunId, compareRunId)
      setData(res?.data ?? res)
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Lỗi không xác định')
    } finally {
      setLoading(false)
    }
  }

  const deltas = data?.deltas || []

  const chartData = deltas
    .filter((d) => Math.abs(Number(d.percent_change) || 0) >= 0.1)
    .map((d) => ({
      kpi: d.kpi_name,
      'Cơ sở': Number(d.base_value) || 0,
      'Kịch bản': Number(d.whatif_value) || 0,
    }))

  const deltaColumns = [
    { title: 'KPI', dataIndex: 'kpi_name', key: 'kpi_name',
      render: (t) => <span className="font-semibold">{t}</span> },
    { title: 'Cơ sở', dataIndex: 'base_value', key: 'base_value', align: 'right',
      render: (v) => fmt(Number(v), 2) },
    { title: 'Kịch bản', dataIndex: 'whatif_value', key: 'whatif_value', align: 'right',
      render: (v) => fmt(Number(v), 2) },
    { title: 'Thay đổi tuyệt đối', dataIndex: 'absolute_change', key: 'absolute_change', align: 'right',
      render: (v) => {
        const n = Number(v)
        return <span className={n > 0 ? 'text-red-600 font-medium' : 'text-green-600 font-medium'}>
          {n > 0 ? '+' : ''}{fmt(n, 2)}
        </span>
      }},
    { title: '% Thay đổi', dataIndex: 'percent_change', key: 'percent_change', align: 'right',
      render: (v) => {
        if (v == null) return <Tag color="default">N/A</Tag>
        const n = Number(v)
        const color = n > 5 ? 'red' : n < -5 ? 'green' : 'blue'
        const icon = n > 0 ? <ArrowUpOutlined /> : n < 0 ? <ArrowDownOutlined /> : null
        return <Tag color={color} icon={icon}>{n > 0 ? '+' : ''}{n.toFixed(1)}%</Tag>
      }},
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        icon={<SwapOutlined />}
        title="C2. So sánh kịch bản"
        subtitle="So sánh các chỉ số hiệu quả (KPI) giữa hai lần chạy tối ưu"
      />

      {error && <Alert message="Lỗi" description={error} type="error" showIcon closable onClose={() => setError(null)} />}

      <Card>
        <div className="flex items-end gap-4 flex-wrap">
          <div>
            <span className="text-gray-500 text-xs block mb-1">Lần chạy cơ sở:</span>
            <Select
              style={{ width: 280 }}
              placeholder="Chọn lần chạy cơ sở"
              value={baseRunId}
              onChange={setBaseRunId}
              loading={runsLoading}
              showSearch
              filterOption={(input, opt) => String(opt.children).toLowerCase().includes(input.toLowerCase())}
            >
              {runs.map((r) => (
                <Option key={r.run_id} value={r.run_id}>
                  Run #{r.run_id} — {r.solver_status} ({fmt(r.objective_value)})
                </Option>
              ))}
            </Select>
          </div>
          <div>
            <span className="text-gray-500 text-xs block mb-1">Lần chạy so sánh (What-If):</span>
            <Select
              style={{ width: 280 }}
              placeholder="Chọn lần chạy so sánh"
              value={compareRunId}
              onChange={setCompareRunId}
              loading={runsLoading}
              showSearch
              filterOption={(input, opt) => String(opt.children).toLowerCase().includes(input.toLowerCase())}
            >
              {runs.map((r) => (
                <Option key={r.run_id} value={r.run_id}>
                  Run #{r.run_id} — {r.solver_status} ({fmt(r.objective_value)})
                </Option>
              ))}
            </Select>
          </div>
          <Button
            type="primary"
            icon={<BarChartOutlined />}
            onClick={handleCompare}
            disabled={!baseRunId || !compareRunId}
            loading={loading}
          >
            So sánh KPI
          </Button>
          <Button icon={<ReloadOutlined />} onClick={loadRuns} title="Làm mới danh sách" />
        </div>
      </Card>

      <Spin spinning={loading}>
        {data && (
          <>
            <Row gutter={16}>
              <Col span={8}>
                <Card size="small">
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Loại kịch bản</p>
                    <Tag color="blue">{data.scenario_type || 'N/A'}</Tag>
                  </div>
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small">
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Nhãn</p>
                    <p className="font-semibold">{data.label || '—'}</p>
                  </div>
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small">
                  <div className="text-center">
                    <p className="text-sm text-gray-500">Số KPI so sánh</p>
                    <p className="text-xl font-bold">{deltas.length}</p>
                  </div>
                </Card>
              </Col>
            </Row>

            {data.summary && (
              <Alert message="Tóm tắt" description={data.summary} type="info" showIcon />
            )}

            {chartData.length > 0 && (
              <Card title={<span className="font-bold"><BarChartOutlined className="mr-2" />Biểu đồ so sánh KPI</span>}>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={chartData} margin={{ bottom: 60 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="kpi" angle={-30} textAnchor="end" interval={0} tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={(v) => v.toLocaleString('vi-VN')} width={90} tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(v) => fmt(v, 2)} />
                    <Legend />
                    <Bar dataKey="Cơ sở"    fill={NEUTRAL[400]} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Kịch bản" fill={BRAND[500]} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            )}

            <Card title={<span className="font-bold">Chi tiết so sánh KPI</span>}>
              <Table
                columns={deltaColumns}
                dataSource={deltas}
                pagination={false}
                size="middle"
                rowKey="kpi_name"
              />
            </Card>
          </>
        )}

        {!data && !loading && (
          <Alert
            message="Chọn hai lần chạy và nhấn So sánh KPI để xem kết quả"
            type="info"
            showIcon
          />
        )}
      </Spin>
    </div>
  )
}

export default ScenarioComparison
