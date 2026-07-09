import React, { useState, useEffect, useRef } from 'react'
import { Card, Row, Col, Table, Tag, Button, InputNumber, Alert, Slider, message, Progress, Switch, Tooltip, Popconfirm } from 'antd'
import {
  BarChartOutlined, ExperimentOutlined,
} from '@ant-design/icons'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend } from 'recharts'
import { useAppContext } from '../context/AppContext'
import sensitivityService from '../services/sensitivityService'
import PageHeader from '../components/PageHeader'
import { BRAND, SEMANTIC, NEUTRAL } from '../theme/tokens'

// Polling hook with localStorage persistence so an in-flight job keeps
// being tracked even after the user navigates away and comes back.
const usePollJob = (onComplete, persistKey) => {
  const [jobId, setJobId] = useState(null)
  const [polling, setPolling] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const intervalRef = useRef(null)
  const timerRef = useRef(null)
  const startTsRef = useRef(null)
  const onCompleteRef = useRef(onComplete)
  onCompleteRef.current = onComplete

  const startPolling = (id) => {
    const ts = Date.now()
    startTsRef.current = ts
    if (persistKey) localStorage.setItem(persistKey, JSON.stringify({ id, ts }))
    setJobId(id); setPolling(true); setElapsed(0)
  }

  useEffect(() => {
    if (!persistKey) return
    const saved = localStorage.getItem(persistKey)
    if (saved) {
      try {
        const { id, ts } = JSON.parse(saved)
        startTsRef.current = ts || Date.now()
        setJobId(Number(id)); setPolling(true)
        setElapsed(Math.floor((Date.now() - startTsRef.current) / 1000))
      } catch { localStorage.removeItem(persistKey) }
    }
  }, [persistKey])

  const [cancelling, setCancelling] = useState(false)

  const cancelJob = async () => {
    if (!jobId) return
    try {
      await sensitivityService.cancelJob(jobId)
      setCancelling(true)
      message.info('Đã gửi yêu cầu dừng. Job sẽ dừng sau khi hoàn tất bước tính hiện tại.')
    } catch (e) {
      message.error('Không gửi được yêu cầu dừng')
    }
  }

  useEffect(() => {
    if (!polling || !jobId) return
    const stop = () => {
      clearInterval(intervalRef.current); clearInterval(timerRef.current)
      setPolling(false); setCancelling(false)
      if (persistKey) localStorage.removeItem(persistKey)
    }
    const tick = () => setElapsed(Math.floor((Date.now() - (startTsRef.current || Date.now())) / 1000))
    tick()
    timerRef.current = setInterval(tick, 1000)
    intervalRef.current = setInterval(async () => {
      try {
        const res = await sensitivityService.pollJob(jobId)
        if (res.status === 'completed') {
          stop(); onCompleteRef.current(res.result)
        } else if (res.status === 'cancelled') {
          stop(); message.warning('Phân tích đã được dừng.')
        } else if (res.status === 'failed') {
          stop(); message.error('Phân tích thất bại: ' + (res.error || 'Unknown'))
        } else if (res.status === 'cancelling') {
          setCancelling(true)
        }
      } catch { stop() }
    }, 4000)
    return () => { clearInterval(intervalRef.current); clearInterval(timerRef.current) }
  }, [polling, jobId, persistKey])

  return { polling, elapsed, startPolling, cancelJob, cancelling }
}

// Nhãn tiếng Việt cho mã tham số
const PARAM_LABELS = {
  DI: 'DI · Biến động cầu',
  CAP: 'CAP · Năng lực cung ứng',
  Cb: 'Cb · Chi phí nợ đơn',
  Co: 'Co · Chi phí tồn kho vượt mức',
  Cs: 'Cs · Chi phí thiếu hụt',
  Cp: 'Cp · Chi phí phạt đóng gói',
  U: 'U · Mức trần tồn kho',
  L: 'L · Mức sàn tồn kho',
  BI: 'BI · Tồn kho ban đầu',
}
const paramLabel = (code) => PARAM_LABELS[code] || code

const ParameterStability = () => {
  const { activeScenarioId } = useAppContext()
  const [scenarioId, setScenarioId] = useState(activeScenarioId || 1)
  const [variationLevel, setVariationLevel] = useState(15)
  const [results, setResults] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [fullDataset, setFullDataset] = useState(false)

  const [history, setHistory] = useState([])

  const loadHistory = async () => {
    try {
      const res = await sensitivityService.getHistory({ limit: 20, analysis_type: 'tornado' })
      setHistory(res?.jobs || [])
    } catch (e) { /* ignore */ }
  }
  useEffect(() => { loadHistory() }, [])

  const { polling, elapsed, startPolling, cancelJob, cancelling } = usePollJob((result) => {
    setResults(result)
    message.success('Kiểm tra ổn định hoàn thành!')
    loadHistory()
  }, 'smi_d3_stability_job')

  const viewHistoryJob = async (job) => {
    try {
      const res = await sensitivityService.getResults(job.job_id)
      if (!res?.result) { message.warning('Job chưa có kết quả'); return }
      setResults(res.result)
    } catch (e) {
      message.error('Không tải được kết quả job')
    }
  }

  const loading = submitting || polling

  const handleRunStability = async () => {
    setSubmitting(true)
    try {
      const res = await sensitivityService.runTornado({
        scenario_id: scenarioId,
        parameters: ['DI', 'CAP', 'Cb', 'Co', 'Cs', 'Cp'],
        variation_pct: variationLevel,
        sample_size: fullDataset ? null : 50,
        time_limit: 5,
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
    { title: 'Tham số', dataIndex: 'parameter_name', key: 'parameter_name', render: (t) => <Tag color="blue">{paramLabel(t)}</Tag> },
    { title: `Giá trị tại -${variationLevel}%`, dataIndex: 'low_value', key: 'low_value', render: (v) => `${Number(v).toLocaleString('vi-VN')}` },
    { title: `Giá trị tại +${variationLevel}%`, dataIndex: 'high_value', key: 'high_value', render: (v) => `${Number(v).toLocaleString('vi-VN')}` },
    { title: 'Khoảng biến thiên', dataIndex: 'spread', key: 'spread', align: 'right', render: (v) => <span className="font-semibold tabular-nums" style={{ color: NEUTRAL[700] }}>{Number(v).toLocaleString('vi-VN')}</span> },
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
        if (volatility < 15) return <Tag color="blue">Ổn định</Tag>
        if (volatility < 25) return <Tag color="orange">Trung bình</Tag>
        return <Tag color="red">Biến động</Tag>
      },
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        icon={<BarChartOutlined />}
        title="D2. Độ bền vững nghiệm tối ưu"
        subtitle="Phân tích độ ổn định của nghiệm tối ưu khi các tham số thay đổi"
      />

      <Card>
        <div className="flex items-center gap-4 flex-wrap">
          <div><span className="mr-2">ID kịch bản:</span><InputNumber min={1} value={scenarioId} onChange={setScenarioId} /></div>
          <div style={{ width: 200 }}>
            <span className="mr-2">Mức biến thiên: {variationLevel}%</span>
            <Slider min={5} max={30} value={variationLevel} onChange={setVariationLevel} />
          </div>
          <Button type="primary" icon={<ExperimentOutlined />} onClick={handleRunStability} loading={loading} disabled={loading}>Chạy kiểm tra ổn định</Button>
          <Tooltip title={fullDataset ? 'Chạy toàn bộ 943 SP — RẤT LÂU (12 lần chạy MA đầy đủ)' : 'Chạy 50 mẫu đại diện (nhanh)'}>
            <div className="flex items-center gap-2 ml-2">
              <span className="text-xs text-gray-500">{fullDataset ? '943 SP' : '50 mẫu'}</span>
              <Switch size="small" checked={fullDataset} onChange={setFullDataset} />
              <span className="text-xs text-gray-500">Đầy đủ</span>
            </div>
          </Tooltip>
        </div>
        {fullDataset && (
          <Alert
            className="mt-3"
            type="warning"
            showIcon
            message="Cảnh báo: chạy trên toàn bộ 943 sản phẩm"
            description="Kiểm tra ổn định chạy ±biến thiên cho 6 tham số = 12 lần chạy MA đầy đủ → có thể mất rất nhiều giờ. Khuyến nghị dùng chế độ 50 mẫu để khảo sát nhanh."
          />
        )}
      </Card>

      {polling && (
        <Alert
          type="info"
          showIcon
          message={
            <span>
              Đang kiểm tra độ bền vững trên <b>{fullDataset ? '943 SP' : '50 mẫu đại diện'}</b>...
              <span className="ml-2 font-mono" style={{ color: BRAND[600] }}>{elapsed}s</span>
              <span className="ml-2 text-gray-400">({fullDataset ? 'toàn bộ 943 SP — có thể mất nhiều giờ' : 'mẫu 50 SP'})</span>
            </span>
          }
          description={
            cancelling
              ? 'Đang dừng… job sẽ kết thúc sau khi hoàn tất bước tính hiện tại (có thể mất tới vài phút).'
              : 'Job chạy nền — bạn có thể rời trang và quay lại, kết quả vẫn được theo dõi và lưu trong Lịch sử bên dưới.'
          }
          action={
            <Popconfirm
              title="Dừng phân tích?"
              description="Job sẽ dừng sau khi hoàn tất bước tính hiện tại. Kết quả dở dang sẽ không được lưu."
              okText="Dừng" cancelText="Tiếp tục"
              onConfirm={cancelJob}
            >
              <Button danger size="small" loading={cancelling}>
                {cancelling ? 'Đang dừng…' : 'Dừng'}
              </Button>
            </Popconfirm>
          }
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
                    <Radar name="Biến động" dataKey="volatility" stroke={SEMANTIC.warn} fill={SEMANTIC.warn} fillOpacity={0.3} />
                    <Radar name="Ổn định" dataKey="stability" stroke={SEMANTIC.good} fill={SEMANTIC.good} fillOpacity={0.3} />
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
                    <Bar dataKey="variationRange" fill={BRAND[500]} name="Khoảng biến thiên" />
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

      <Card title="Lịch sử kiểm tra ổn định" extra={<Button size="small" onClick={loadHistory}>Làm mới</Button>}>
        <Table
          columns={[
            { title: 'ID', dataIndex: 'job_id', key: 'job_id', width: 60 },
            { title: 'Tham số', dataIndex: 'parameter_name', key: 'parameter_name',
              render: (t) => <span className="text-xs">{t}</span> },
            { title: 'Trạng thái', dataIndex: 'status', key: 'status', width: 110,
              render: (s) => {
                const color = s === 'completed' ? 'green' : s === 'running' ? 'processing' : s === 'failed' ? 'red' : 'default'
                return <Tag color={color}>{s}</Tag>
              } },
            { title: 'Thời gian', dataIndex: 'created_at', key: 'created_at',
              render: (v) => v ? new Date(v).toLocaleString('vi-VN') : '—' },
            { title: '', key: 'action', width: 90,
              render: (_, r) => r.status === 'completed'
                ? <Button size="small" type="link" onClick={() => viewHistoryJob(r)}>Xem</Button>
                : null },
          ]}
          dataSource={history}
          pagination={{ pageSize: 5 }}
          size="small"
          rowKey="job_id"
          locale={{ emptyText: 'Chưa có lịch sử kiểm tra' }}
        />
      </Card>
    </div>
  )
}

export default ParameterStability