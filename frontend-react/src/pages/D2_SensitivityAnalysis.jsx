import React, { useState, useEffect, useRef } from 'react'
import { Card, Row, Col, Table, Tag, Button, Select, InputNumber, Alert, message, Radio, Switch, Tooltip, Popconfirm } from 'antd'
import {
  LineChartOutlined, BarChartOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Legend, ReferenceLine } from 'recharts'
import { useAppContext } from '../context/AppContext'
import sensitivityService from '../services/sensitivityService'
import PageHeader from '../components/PageHeader'
import { BRAND, SEMANTIC } from '../theme/tokens'

const { Option } = Select

// Tham số có thể phân tích độ nhạy (CP case-pack bị loại vì không co giãn được).
const PARAMETERS = [
  { code: 'DI',  label: 'DI · Biến động cầu' },
  { code: 'CAP', label: 'CAP · Năng lực cung ứng' },
  { code: 'Cb',  label: 'Cb · Chi phí nợ đơn' },
  { code: 'Co',  label: 'Co · Chi phí tồn kho vượt mức' },
  { code: 'Cs',  label: 'Cs · Chi phí thiếu hụt' },
  { code: 'Cp',  label: 'Cp · Chi phí phạt đóng gói' },
  { code: 'U',   label: 'U · Mức trần tồn kho' },
  { code: 'L',   label: 'L · Mức sàn tồn kho' },
  { code: 'BI',  label: 'BI · Tồn kho ban đầu' },
]
const PARAM_CODES = PARAMETERS.map(p => p.code)
const paramLabel = (code) => (PARAMETERS.find(p => p.code === code)?.label) || code

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

  // localStorage lưu {id, ts} để resume + đếm elapsed từ timestamp thật.
  const startPolling = (id) => {
    const ts = Date.now()
    startTsRef.current = ts
    if (persistKey) localStorage.setItem(persistKey, JSON.stringify({ id, ts }))
    setJobId(id)
    setPolling(true)
    setElapsed(0)
  }

  // Resume an unfinished job recorded in localStorage on mount.
  useEffect(() => {
    if (!persistKey) return
    const saved = localStorage.getItem(persistKey)
    if (saved) {
      try {
        const { id, ts } = JSON.parse(saved)
        startTsRef.current = ts || Date.now()
        setJobId(Number(id))
        setPolling(true)
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
      clearInterval(intervalRef.current)
      clearInterval(timerRef.current)
      setPolling(false)
      setCancelling(false)
      if (persistKey) localStorage.removeItem(persistKey)
    }
    // elapsed tính từ timestamp thật → không reset khi quay lại trang
    const tick = () => setElapsed(Math.floor((Date.now() - (startTsRef.current || Date.now())) / 1000))
    tick()
    timerRef.current = setInterval(tick, 1000)
    intervalRef.current = setInterval(async () => {
      try {
        const res = await sensitivityService.pollJob(jobId)
        if (res.status === 'completed') {
          stop()
          onCompleteRef.current(res.result)
        } else if (res.status === 'cancelled') {
          stop()
          message.warning('Phân tích đã được dừng.')
        } else if (res.status === 'failed') {
          stop()
          message.error('Phân tích thất bại: ' + (res.error || 'Unknown error'))
        } else if (res.status === 'cancelling') {
          setCancelling(true)
        }
      } catch (e) {
        stop()
      }
    }, 4000)
    return () => {
      clearInterval(intervalRef.current)
      clearInterval(timerRef.current)
    }
  }, [polling, jobId, persistKey])

  return { polling, elapsed, startPolling, cancelJob, cancelling }
}

const SensitivityAnalysis = () => {
  const { activeScenarioId } = useAppContext()
  const [scenarioId, setScenarioId] = useState(activeScenarioId || 1)
  const [selectedParam, setSelectedParam] = useState('DI')
  const [analysisType, setAnalysisType] = useState('oat')
  const [variationPct, setVariationPct] = useState(10)

  const [oatResult, setOatResult] = useState(null)
  const [tornadoResult, setTornadoResult] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [fullDataset, setFullDataset] = useState(false)

  const [history, setHistory] = useState([])

  const loadHistory = async () => {
    try {
      const res = await sensitivityService.getHistory({ limit: 20 })
      setHistory(res?.jobs || [])
    } catch (e) { /* ignore */ }
  }
  useEffect(() => { loadHistory() }, [])

  const { polling: pollingOAT, elapsed: elapsedOAT, startPolling: startOAT, cancelJob: cancelOAT, cancelling: cancellingOAT } = usePollJob((result) => {
    // OAT result stored as array of points in DB
    setOatResult(Array.isArray(result) ? { points: result, parameter_name: selectedParam, baseline_objective: result[0]?.baseline_objective || 0, elasticity: null } : result)
    message.success('Phân tích OAT hoàn thành!')
    loadHistory()
  }, 'smi_d2_oat_job')

  const { polling: pollingTornado, elapsed: elapsedTornado, startPolling: startTornado, cancelJob: cancelTornado, cancelling: cancellingTornado } = usePollJob((result) => {
    // Tornado result stored as {baseline_objective, variation_pct, bars}
    setTornadoResult(result)
    message.success('Phân tích Tornado hoàn thành!')
    loadHistory()
  }, 'smi_d2_tornado_job')

  // View a completed job from history
  const viewHistoryJob = async (job) => {
    try {
      const res = await sensitivityService.getResults(job.job_id)
      const result = res?.result
      if (!result) { message.warning('Job chưa có kết quả'); return }
      if (job.analysis_type === 'tornado') {
        setAnalysisType('tornado')
        setTornadoResult(result)
      } else {
        setAnalysisType('oat')
        setOatResult(Array.isArray(result)
          ? { points: result, parameter_name: job.parameter_name, baseline_objective: result[0]?.baseline_objective || 0, elasticity: null }
          : result)
      }
    } catch (e) {
      message.error('Không tải được kết quả job')
    }
  }

  const loading = submitting || pollingOAT || pollingTornado

  const handleRunOAT = async () => {
    setSubmitting(true)
    try {
      const res = await sensitivityService.runSensitivity({
        scenario_id: scenarioId,
        parameter_name: selectedParam,
        variation_percentages: [-20, -10, 10, 20],
        sample_size: fullDataset ? null : 50,
        time_limit: 5,
      })
      startOAT(res.job_id)
    } catch (e) {
      message.error('Không thể khởi động phân tích')
    } finally {
      setSubmitting(false)
    }
  }

  const handleRunTornado = async () => {
    setSubmitting(true)
    try {
      const res = await sensitivityService.runTornado({
        scenario_id: scenarioId,
        parameters: PARAM_CODES.slice(0, 6),
        variation_pct: variationPct,
        sample_size: fullDataset ? null : 50,
        time_limit: 5,
      })
      startTornado(res.job_id)
    } catch (e) {
      message.error('Không thể khởi động phân tích')
    } finally {
      setSubmitting(false)
    }
  }

  // OAT chart data
  const oatChartData = oatResult?.points?.map(p => ({
    variation: `${p.variation_pct > 0 ? '+' : ''}${p.variation_pct}%`,
    objective: Number(p.objective_value) || 0,
    status: p.solver_status,
  })) || []

  // Tornado chart data
  const tornadoBars = tornadoResult?.bars?.sort((a, b) => b.spread - a.spread) || []
  const tornadoChartData = tornadoBars.map(b => ({
    parameter: b.parameter_name,
    low: Number(b.low_pct_change) || 0,
    high: Number(b.high_pct_change) || 0,
    spread: Number(b.spread) || 0,
  }))

  return (
    <div className="space-y-6">
      <PageHeader
        icon={<LineChartOutlined />}
        title="D1. Phân tích độ nhạy tham số"
        subtitle="Đánh giá mức độ tác động của từng tham số đến chi phí (phân tích OAT và biểu đồ tornado)"
      />

      <Card>
        <div className="flex items-center gap-4 flex-wrap">
          <div><span className="mr-2">ID kịch bản:</span><InputNumber min={1} value={scenarioId} onChange={setScenarioId} /></div>
          <Radio.Group value={analysisType} onChange={(e) => setAnalysisType(e.target.value)} buttonStyle="solid">
            <Radio.Button value="oat">Từng tham số</Radio.Button>
            <Radio.Button value="tornado">Tornado</Radio.Button>
          </Radio.Group>
          {analysisType === 'oat' && (
            <>
              <Select value={selectedParam} onChange={setSelectedParam} style={{ width: 280 }}>
                {PARAMETERS.map(p => <Option key={p.code} value={p.code}>{p.label}</Option>)}
              </Select>
              <Button type="primary" icon={<ThunderboltOutlined />} onClick={handleRunOAT} loading={pollingOAT || submitting} disabled={loading}>Chạy OAT</Button>
            </>
          )}
          {analysisType === 'tornado' && (
            <>
              <div><span className="mr-2">Biến thiên %:</span><InputNumber min={1} max={50} value={variationPct} onChange={setVariationPct} /></div>
              <Button type="primary" icon={<BarChartOutlined />} onClick={handleRunTornado} loading={pollingTornado || submitting} disabled={loading}>Chạy Tornado</Button>
            </>
          )}
          <Tooltip title={fullDataset ? 'Chạy toàn bộ 943 SP — RẤT LÂU (mỗi mức biến thiên là một lần chạy MA đầy đủ)' : 'Chạy 50 mẫu đại diện — OAT ~22 phút, Tornado ~57 phút'}>
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
            description={
              analysisType === 'oat'
                ? 'OAT chạy 4 mức biến thiên trên toàn bộ 943 SP → mỗi mức là một lần chạy MA đầy đủ, tổng có thể mất NHIỀU GIỜ. Khuyến nghị dùng chế độ 50 mẫu (~22 phút).'
                : 'Tornado chạy ±biến thiên cho 6 tham số = 12 lần chạy MA trên toàn bộ 943 SP → có thể mất RẤT NHIỀU GIỜ. Khuyến nghị dùng chế độ 50 mẫu (~57 phút).'
            }
          />
        )}
      </Card>

      {(pollingOAT || pollingTornado) && (
        <Alert
          type="info"
          showIcon
          message={
            <span>
              Đang phân tích {pollingOAT ? `OAT (${selectedParam})` : 'Tornado'}
              {' '}trên <b>{fullDataset ? '943 SP' : '50 mẫu đại diện'}</b>...
              <span className="ml-2 font-mono text-blue-600">{pollingOAT ? elapsedOAT : elapsedTornado}s</span>
              <span className="ml-2 text-gray-400">({fullDataset ? 'toàn bộ 943 SP — có thể mất nhiều giờ' : 'mẫu 50 SP'})</span>
            </span>
          }
          description={
            (pollingOAT ? cancellingOAT : cancellingTornado)
              ? 'Đang dừng… job sẽ kết thúc sau khi hoàn tất bước tính hiện tại (có thể mất tới vài phút).'
              : 'Job chạy nền — bạn có thể rời trang và quay lại, kết quả vẫn được theo dõi và lưu trong Lịch sử bên dưới.'
          }
          action={
            <Popconfirm
              title="Dừng phân tích?"
              description="Job sẽ dừng sau khi hoàn tất bước tính hiện tại. Kết quả dở dang sẽ không được lưu."
              okText="Dừng" cancelText="Tiếp tục"
              onConfirm={pollingOAT ? cancelOAT : cancelTornado}
            >
              <Button danger size="small" loading={pollingOAT ? cancellingOAT : cancellingTornado}>
                {(pollingOAT ? cancellingOAT : cancellingTornado) ? 'Đang dừng…' : 'Dừng'}
              </Button>
            </Popconfirm>
          }
        />
      )}

      {analysisType === 'oat' && oatResult && (
        <>
          <Row gutter={16}>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Tham số</p><Tag color="blue">{paramLabel(oatResult.parameter_name)}</Tag></div></Card></Col>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Mục tiêu cơ sở</p><p className="text-xl font-bold">{Number(oatResult.baseline_objective || 0).toLocaleString('vi-VN')}</p></div></Card></Col>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Độ co giãn</p><p className="text-xl font-bold">{Number(oatResult.elasticity || 0).toFixed(3)}</p></div></Card></Col>
          </Row>
          <Card title={`Độ nhạy: ${paramLabel(oatResult.parameter_name)}`}>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={oatChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="variation" />
                <YAxis />
                <RechartsTooltip formatter={(v) => [`${Number(v).toLocaleString('vi-VN')}`]} />
                <ReferenceLine
                  y={Number(oatResult.baseline_objective)}
                  stroke={SEMANTIC.bad}
                  strokeDasharray="3 3"
                  label={{ value: 'Cơ sở', position: 'insideBottomLeft', fill: SEMANTIC.bad, fontSize: 11, dy: -6 }}
                />
                <Line type="monotone" dataKey="objective" stroke={BRAND[500]} strokeWidth={2} name="Giá trị mục tiêu" />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </>
      )}

      {analysisType === 'tornado' && tornadoResult && (
        <>
          <Row gutter={16}>
            <Col span={12}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Cơ sở</p><p className="text-xl font-bold">{Number(tornadoResult.baseline_objective || 0).toLocaleString('vi-VN')}</p></div></Card></Col>
            <Col span={12}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Biến thiên</p><p className="text-xl font-bold">+/- {tornadoResult.variation_pct}%</p></div></Card></Col>
          </Row>
          <Card title="Biểu đồ Tornado">
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={tornadoChartData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis type="category" dataKey="parameter" width={60} />
                <RechartsTooltip />
                <Legend />
                <ReferenceLine x={0} stroke="#000" />
                <Bar dataKey="low" fill={SEMANTIC.good} name="Thấp (-)" />
                <Bar dataKey="high" fill={SEMANTIC.bad} name="Cao (+)" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card title="Xếp hạng độ nhạy tham số">
            <Table
              columns={[
                { title: 'Tham số', dataIndex: 'parameter_name', key: 'parameter_name', render: (t) => <Tag color="blue">{paramLabel(t)}</Tag> },
                { title: 'Giá trị thấp', dataIndex: 'low_value', key: 'low_value', render: (v) => Number(v).toLocaleString('vi-VN') },
                { title: 'Giá trị cao', dataIndex: 'high_value', key: 'high_value', render: (v) => Number(v).toLocaleString('vi-VN') },
                { title: 'Khoảng biến thiên', dataIndex: 'spread', key: 'spread', render: (v) => <span className="font-bold">{Number(v).toLocaleString('vi-VN')}</span> },
              ]}
              dataSource={tornadoBars}
              pagination={false}
              size="middle"
              rowKey="parameter_name"
            />
          </Card>
        </>
      )}

      {!oatResult && !tornadoResult && !loading && (
        <Alert message="Chọn tham số và chạy phân tích để xem kết quả" type="info" showIcon />
      )}

      <Card title="Lịch sử phân tích" extra={<Button size="small" onClick={loadHistory}>Làm mới</Button>}>
        <Table
          columns={[
            { title: 'ID', dataIndex: 'job_id', key: 'job_id', width: 60 },
            { title: 'Loại', dataIndex: 'analysis_type', key: 'analysis_type', width: 90,
              render: (t) => <Tag color={t === 'tornado' ? 'purple' : 'blue'}>{t === 'tornado' ? 'Tornado' : 'OAT'}</Tag> },
            { title: 'Tham số', dataIndex: 'parameter_name', key: 'parameter_name' },
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
          locale={{ emptyText: 'Chưa có lịch sử phân tích' }}
        />
      </Card>
    </div>
  )
}

export default SensitivityAnalysis
