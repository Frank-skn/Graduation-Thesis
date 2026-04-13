import React, { useState, useEffect, useRef } from 'react'
import { Card, Row, Col, Table, Tag, Button, InputNumber, Alert, Slider, message, Progress, Switch, Tooltip } from 'antd'
import {
  BarChartOutlined, ExperimentOutlined,
} from '@ant-design/icons'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend } from 'recharts'
import { useAppContext } from '../context/AppContext'
import sensitivityService from '../services/sensitivityService'

const usePollJob = (onComplete) => {
  const [jobId, setJobId] = useState(null)
  const [polling, setPolling] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const intervalRef = useRef(null)
  const timerRef = useRef(null)

  const startPolling = (id) => { setJobId(id); setPolling(true); setElapsed(0) }

  useEffect(() => {
    if (!polling || !jobId) return
    timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000)
    intervalRef.current = setInterval(async () => {
      try {
        const res = await sensitivityService.pollJob(jobId)
        if (res.status === 'completed') {
          clearInterval(intervalRef.current); clearInterval(timerRef.current)
          setPolling(false); onComplete(res.result)
        } else if (res.status === 'failed') {
          clearInterval(intervalRef.current); clearInterval(timerRef.current)
          setPolling(false); message.error('Phân tích thất bại: ' + (res.error || 'Unknown'))
        }
      } catch { clearInterval(intervalRef.current); clearInterval(timerRef.current); setPolling(false) }
    }, 4000)
    return () => { clearInterval(intervalRef.current); clearInterval(timerRef.current) }
  }, [polling, jobId])

  return { polling, elapsed, startPolling }
}

const ParameterStability = () => {
  const { activeScenarioId } = useAppContext()
  const [scenarioId, setScenarioId] = useState(activeScenarioId || 1)
  const [variationLevel, setVariationLevel] = useState(15)
  const [results, setResults] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [fullDataset, setFullDataset] = useState(false)

  const { polling, elapsed, startPolling } = usePollJob((result) => {
    setResults(result)
    message.success('Kiểm tra ổn định hoàn thành!')
  })

  const loading = submitting || polling

  const handleRunStability = async () => {
    setSubmitting(true)
    try {
      const res = await sensitivityService.runTornado({
        scenario_id: scenarioId,
        parameters: ['DI', 'CAP', 'Cb', 'Co', 'Cs', 'Cp'],
        variation_pct: variationLevel,
        sample_size: fullDataset ? null : 50,
      })
      startPolling(res.job_id)
    } catch { message.error('Không thể khởi động phân tích') }
    finally { setSubmitting(false) }
  }

  const bars = results?.bars || []

  // Radar data for stability dimensions
  const radarData = bars.map(b => ({
    parameter: b.parameter_name,
    volatility: Math.min(100, Math.abs(Number(b.spread || 0)) / Math.max(1, Number(results?.baseline_objective || 1)) * 100),
    stability: Math.max(0, 100 - Math.abs(Number(b.spread || 0)) / Math.max(1, Number(results?.baseline_objective || 1)) * 100),
  }))

  // Parameter stability table
  const stabilityColumns = [
    { title: 'Tham số', dataIndex: 'parameter_name', key: 'parameter_name', render: (t) => <Tag color="blue">{t}</Tag> },
    { title: `Giá trị tại -${variationLevel}%`, dataIndex: 'low_value', key: 'low_value', render: (v) => `${Number(v).toLocaleString('vi-VN')}` },
    { title: `Giá trị tại +${variationLevel}%`, dataIndex: 'high_value', key: 'high_value', render: (v) => `${Number(v).toLocaleString('vi-VN')}` },
    { title: 'Khoảng biến thiên', dataIndex: 'spread', key: 'spread', render: (v) => <span className="font-bold text-orange-600">{Number(v).toLocaleString('vi-VN')}</span> },
    {
      title: 'Chỉ số ổn định', key: 'stability',
      render: (_, record) => {
        const volatility = Math.abs(Number(record.spread || 0)) / Math.max(1, Number(results?.baseline_objective || 1)) * 100
        const stability = Math.max(0, 100 - volatility)
        return <Progress percent={Math.round(stability)} size="small" status={stability > 80 ? 'success' : stability > 60 ? 'normal' : 'exception'} />
      },
    },
    {
      title: 'Đánh giá', key: 'rating',
      render: (_, record) => {
        const volatility = Math.abs(Number(record.spread || 0)) / Math.max(1, Number(results?.baseline_objective || 1)) * 100
        if (volatility < 5)  return <Tag color="green">Rất ổn định</Tag>
        if (volatility < 15) return <Tag color="cyan">Ổn định</Tag>
        if (volatility < 25) return <Tag color="orange">Trung bình</Tag>
        return <Tag color="red">Biến động</Tag>
      },
    },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-primary-700 mb-2"><BarChartOutlined className="mr-3" />D3. Độ Bền Vững Nghiệm Tối Ưu</h1>
        <p className="text-gray-600">Phân tích độ ổn định của nghiệm tối ưu khi các tham số thay đổi</p>
      </div>

      <Card>
        <div className="flex items-center gap-4 flex-wrap">
          <div><span className="mr-2">ID kịch bản:</span><InputNumber min={1} value={scenarioId} onChange={setScenarioId} /></div>
          <div style={{ width: 200 }}>
            <span className="mr-2">Mức biến thiên: {variationLevel}%</span>
            <Slider min={5} max={30} value={variationLevel} onChange={setVariationLevel} />
          </div>
          <Button type="primary" icon={<ExperimentOutlined />} onClick={handleRunStability} loading={loading} disabled={loading}>Chạy kiểm tra ổn định</Button>
          <Tooltip title={fullDataset ? 'Chạy toàn bộ 943 SP (~14 phút)' : 'Chạy 50 mẫu đại diện (~1 phút)'}>
            <div className="flex items-center gap-2 ml-2">
              <span className="text-xs text-gray-500">{fullDataset ? '943 SP' : '50 mẫu'}</span>
              <Switch size="small" checked={fullDataset} onChange={setFullDataset} />
              <span className="text-xs text-gray-500">Đầy đủ</span>
            </div>
          </Tooltip>
        </div>
      </Card>

      {polling && (
        <Alert
          type="info"
          showIcon
          message={
            <span>
              Đang kiểm tra độ bền vững trên <b>{fullDataset ? '943 SP' : '50 mẫu đại diện'}</b>...
              <span className="ml-2 font-mono text-blue-600">{elapsed}s</span>
              <span className="ml-2 text-gray-400">(ước tính {fullDataset ? '~14 phút' : '~1 phút'})</span>
            </span>
          }
          description="Kết quả sẽ tự động hiển thị khi hoàn thành. Vui lòng không đóng trang."
        />
      )}

      {results && (
        <>
          <Row gutter={16}>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Mục tiêu cơ sở</p><p className="text-xl font-bold">{Number(results.baseline_objective || 0).toLocaleString('vi-VN')}</p></div></Card></Col>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Mức biến thiên</p><p className="text-xl font-bold">+/- {results.variation_pct}%</p></div></Card></Col>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Số tham số phân tích</p><p className="text-xl font-bold">{bars.length}</p></div></Card></Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Card title="Biểu đồ nhện ướt - Ổn định tham số">
                <ResponsiveContainer width="100%" height={300}>
                  <RadarChart data={radarData}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="parameter" />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} />
                    <Radar name="Biến động" dataKey="volatility" stroke="#fa8c16" fill="#fa8c16" fillOpacity={0.3} />
                    <Radar name="Ổn định" dataKey="stability" stroke="#52c41a" fill="#52c41a" fillOpacity={0.3} />
                    <Legend />
                  </RadarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
            <Col span={12}>
              <Card title="Tác động biến thiên tham số">
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={bars.map(b => ({ param: b.parameter_name, variationRange: Number(b.spread) }))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="param" />
                    <YAxis />
                    <RechartsTooltip formatter={(v) => `${Number(v).toLocaleString('vi-VN')}`} />
                    <Bar dataKey="variationRange" fill="#1890ff" name="Khoảng biến thiên" />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
          </Row>

          <Card title="Đánh giá ổn định tham số" className="mb-6">
            <Table columns={stabilityColumns} dataSource={bars} pagination={false} size="middle" rowKey="parameter_name" />
          </Card>

          {/* Summary and Insights */}
          <Card title="Nhận xét về ổn định">
            <Row gutter={16}>
              <Col span={12}>
                <div className="mb-4">
                  <h4 className="font-semibold mb-2">Tham số ổn định nhất:</h4>
                  {bars
                    .sort((a, b) => Number(a.spread) - Number(b.spread))
                    .slice(0, 2)
                    .map(param => (
                      <Tag key={param.parameter_name} color="green" className="mb-1">
                        {param.parameter_name}
                      </Tag>
                    ))}
                </div>
              </Col>
              <Col span={12}>
                <div className="mb-4">
                  <h4 className="font-semibold mb-2">Tham số biến động nhất:</h4>
                  {bars
                    .sort((a, b) => Number(b.spread) - Number(a.spread))
                    .slice(0, 2)
                    .map(param => (
                      <Tag key={param.parameter_name} color="orange" className="mb-1">
                        {param.parameter_name}
                      </Tag>
                    ))}
                </div>
              </Col>
            </Row>
            <Alert 
              message="Khúyến nghị về ổn định tham số" 
              description="Các tham số có độ biến động cao cần được theo dõi chặt chẽ và có thể cần cài đặt bảo thủ hơn hoặc bổ sung ràng buộc để cải thiện độ ổn định nghiệm."
              type="info" 
              showIcon 
            />
          </Card>
        </>
      )}

      {!results && !loading && (
        <Alert
          message="Cấu hình tham số kiểm tra ổn định và nhấn Chạy kiểm tra"
          description="Phân tích này giúp xác định các tham số có tác động lớn nhất đến độ ổn định nghiệm và hỗ trợ ra quyết định trong điều kiện không chắc chắn."
          type="info"
          showIcon
        />
      )}
    </div>
  )
}

export default ParameterStability