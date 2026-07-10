import React, { useState, useEffect, useRef } from 'react'
import {
  Card, Row, Col, Form, Select, InputNumber, Button, Alert,
  Statistic, Steps, Divider, message, Progress, Tag, Tabs, Table, Badge, Tooltip as AntTooltip,
  Popconfirm,
} from 'antd'
import {
  ThunderboltOutlined, CheckCircleOutlined, LoadingOutlined,
  DatabaseOutlined, PlayCircleOutlined, ClockCircleOutlined, ReloadOutlined,
  RiseOutlined, FallOutlined, BarChartOutlined, HistoryOutlined, EyeOutlined,
  ExperimentOutlined, SlidersOutlined, DashboardOutlined, SaveOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { useAppContext } from '../context/AppContext'
import optimizationService from '../services/optimizationService'
import scenarioService from '../services/scenarioService'
import dataService from '../services/dataService'
import PageHeader from '../components/PageHeader'
import { BRAND, NEUTRAL, SEMANTIC } from '../theme/tokens'

const { Option } = Select

const POLL_INTERVAL_MS = 4000

const RunOptimization = () => {
  const [form] = Form.useForm()
  const navigate = useNavigate()
  const { setActiveRunId, setActiveScenarioId } = useAppContext()

  // Watch product_limit to show a live runtime estimate
  const watchedLimit = Form.useWatch('product_limit', form)
  const estimateText = (() => {
    const n = (watchedLimit == null || watchedLimit === '') ? 943 : Number(watchedLimit)
    // ~10s/product average (from thesis: 943 SP ≈ 154 min)
    const secs = n * 10
    if (secs < 90) return `~${Math.max(5, Math.round(secs))} giây`
    if (secs < 3600) return `~${Math.round(secs / 60)} phút`
    return `~${(secs / 3600).toFixed(1)} giờ`
  })()
  const isFullRun = watchedLimit == null || watchedLimit === ''

  // 0 = configure, 1 = running (polling), 2 = done
  const [step, setStep] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [pollingRunId, setPollingRunId] = useState(null)
  const [pollResult, setPollResult] = useState(null)
  const [elapsedSec, setElapsedSec] = useState(0)
  const [errorMsg, setErrorMsg] = useState(null)
  const [timeLimit, setTimeLimit] = useState(300)
  const [runSummary, setRunSummary] = useState(null)
  // Số sản phẩm và thời điểm bắt đầu của lần chạy hiện tại (để ước tính tiến độ)
  const [runProductCount, setRunProductCount] = useState(943)
  const startTsRef = useRef(null)
  const pollRef = useRef(null)
  const timerRef = useRef(null)

  // Khóa localStorage để giữ trạng thái "đang chạy" khi rời trang rồi quay lại
  const LS_RUNNING = 'smi_b0_running'

  // ── History tab state ──
  const [activeTab, setActiveTab] = useState('run')
  const [histRuns, setHistRuns] = useState([])
  const [histLoading, setHistLoading] = useState(false)
  const [selectedHistId, setSelectedHistId] = useState(null)
  const [histSummary, setHistSummary] = useState(null)
  const [histSummaryLoading, setHistSummaryLoading] = useState(false)

  const { data: overviewData, loading: loadingOverview } = useApi(() => dataService.getOverview())
  const counts = overviewData || {}

  // -- Polling logic --
  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
  }

  const startPolling = (runId, startTs, prodCount) => {
    startTsRef.current = startTs || Date.now()
    // elapsed tính từ timestamp thật → resume đúng khi quay lại trang
    const tick = () => setElapsedSec(Math.floor((Date.now() - startTsRef.current) / 1000))
    tick()
    timerRef.current = setInterval(tick, 1000)

    pollRef.current = setInterval(async () => {
      try {
        const status = await optimizationService.getRunStatus(runId)
        if (status.is_done) {
          stopPolling()
          localStorage.removeItem(LS_RUNNING)
          setActiveRunId(runId)
          setPollResult(status)
          setStep(2)
          const ok = /optimal|feasible/i.test(status.solver_status)
          if (ok) message.success(`Tối ưu hoá hoàn thành! Lần chạy #${runId} - ${status.solver_status}`)
          else message.error(`Lần chạy #${runId} kết thúc với trạng thái: ${status.solver_status}`)
          try {
            const ext = await optimizationService.getSummaryExtended(runId)
            setRunSummary(ext)
          } catch { /* non-blocking */ }
        }
      } catch {
        // keep polling on transient errors
      }
    }, POLL_INTERVAL_MS)
  }

  // Resume trạng thái "đang chạy" nếu người dùng rời trang rồi quay lại
  useEffect(() => {
    const saved = localStorage.getItem(LS_RUNNING)
    if (saved) {
      try {
        const { runId, startTs, prodCount, tl } = JSON.parse(saved)
        if (runId) {
          setStep(1)
          setPollingRunId(runId)
          setTimeLimit(tl || 300)
          setRunProductCount(prodCount || 943)
          startPolling(runId, startTs, prodCount)
        }
      } catch { localStorage.removeItem(LS_RUNNING) }
    }
    return () => stopPolling()
  }, [])

  // ── Load history ──
  const handleConfirmOptimization = () => {
    message.success('Kết quả tối ưu đã được xác nhận và lưu thành công!')
    navigate('/b1-executive-summary')
  }

  const loadHistory = async () => {
    setHistLoading(true)
    try {
      const res = await optimizationService.listRuns()
      // API interceptor already returns body directly — res is the array itself
      const list = Array.isArray(res) ? res : (res?.runs ?? [])
      setHistRuns(list)
    } catch { /* ignore */ } finally {
      setHistLoading(false)
    }
  }

  useEffect(() => { loadHistory() }, [])

  // Reload history after a new run finishes (step goes to 2)
  useEffect(() => { if (step === 2) loadHistory() }, [step])

  const handleViewHistRun = async (runId) => {
    setSelectedHistId(runId)
    setHistSummary(null)
    setHistSummaryLoading(true)
    try {
      const ext = await optimizationService.getSummaryExtended(runId)
      const extData = ext?.data ?? ext
      setHistSummary(extData)
    } catch {
      setHistSummary(null)
    } finally {
      setHistSummaryLoading(false)
    }
  }

  // -- Submit handler --
  const handleRun = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)
      setErrorMsg(null)
      setTimeLimit(values.time_limit)

      // Ensure base scenario exists
      let scenarioId
      try {
        const allScenarios = await scenarioService.getScenarios()
        const existing = (allScenarios?.scenarios || []).find(
          (s) => s.scenario_name === 'Base Optimization'
        )
        if (existing) {
          scenarioId = existing.scenario_id
        } else {
          const created = await scenarioService.createScenario({
            scenario_name: 'Base Optimization',
            description: 'Auto-created base scenario for the SS-MB-SMI model',
            created_by: 'system',
          })
          scenarioId = created?.scenario_id
        }
      } catch {
        setErrorMsg('Không thể tạo hoặc tìm kịch bản cơ sở. Kiểm tra kết nối backend.')
        setSubmitting(false)
        return
      }

      if (!scenarioId) {
        setErrorMsg('Không lấy được ID kịch bản. Vui lòng thử lại.')
        setSubmitting(false)
        return
      }

      setActiveScenarioId(scenarioId)

      // Submit job - returns immediately with run_id
      let runId
      try {
        const res = await optimizationService.runOptimization({
          scenario_id: scenarioId,
          solver: values.solver,
          time_limit: values.time_limit,
          mip_gap: values.mip_gap,
          product_limit: values.product_limit ?? null,
        })
        runId = res?.run_id
      } catch (err) {
        const detail = err?.message || 'Unknown error'
        setErrorMsg(`Không thể gửi bài toán tối ưu: ${detail}`)
        setSubmitting(false)
        return
      }

      const prodCount = values.product_limit
        ? Number(values.product_limit)
        : (counts.num_products || 943)
      const startTs = Date.now()

      setPollingRunId(runId)
      setRunProductCount(prodCount)
      setStep(1)
      setSubmitting(false)
      // Lưu trạng thái để resume khi rời trang rồi quay lại
      localStorage.setItem(LS_RUNNING, JSON.stringify({
        runId, startTs, prodCount, tl: values.time_limit,
      }))
      startPolling(runId, startTs, prodCount)
    } catch {
      // form validation failed
      setSubmitting(false)
    }
  }

  const handleReset = () => {
    stopPolling()
    localStorage.removeItem(LS_RUNNING)
    setStep(0)
    setPollResult(null)
    setPollingRunId(null)
    setErrorMsg(null)
    setElapsedSec(0)
    setRunSummary(null)
  }

  // -- Progress calculation for running state --
  // Ước tính tổng thời gian = số SP × ~10s/SP (theo đo thực nghiệm).
  // Tiến độ dựa trên elapsed so với tổng ước tính, chặn ở 97% tới khi
  // backend báo hoàn thành (tránh hiện 100% khi chưa xong).
  const estTotalSec = Math.max(10, runProductCount * 10)
  const progressPct = Math.min(97, Math.floor((elapsedSec / estTotalSec) * 100))
  const itemsDone = Math.min(runProductCount, Math.floor((progressPct / 100) * runProductCount))

  const MILESTONES = [
    { pct: 15, label: 'Nạp dữ liệu' },
    { pct: 40, label: 'Xây dựng mô hình' },
    { pct: 70, label: 'Đang giải MA (GA-ALNS)' },
    { pct: 92, label: 'Kiểm tra nghiệm' },
  ]

  const fmt = (v, d = 0) =>
    Number(v ?? 0).toLocaleString('vi-VN', { maximumFractionDigits: d })

  const statusColor = (status) => {
    const s = (status || '').toLowerCase()
    if (s === 'optimal') return SEMANTIC.good
    if (s === 'feasible') return SEMANTIC.warn
    return SEMANTIC.bad
  }

  // ── History table columns ──
  const handleDeleteRun = async (runId) => {
    try {
      await optimizationService.deleteRun(runId)
      message.success(`Đã xoá lần chạy #${runId}`)
      if (selectedHistId === runId) {
        setSelectedHistId(null)
        setHistSummary(null)
      }
      loadHistory()
    } catch (err) {
      message.error(`Xoá thất bại: ${err?.message || 'Lỗi không xác định'}`)
    }
  }

  const histColumns = [
    { title: 'Lần chạy', dataIndex: 'run_id', key: 'run_id', width: 90,
      render: (v) => <strong>#{v}</strong> },
    { title: 'Phiên bản DL', dataIndex: 'version_id', key: 'version_id', width: 110,
      render: (v) => v ? <Tag color="blue">PB #{v}</Tag> : <span className="text-gray-400">—</span> },
    { title: 'Thời gian chạy', dataIndex: 'run_time', key: 'run_time', width: 160,
      render: (v) => v ? String(v).slice(0, 16) : '—' },
    { title: 'Trạng thái', dataIndex: 'solver_status', key: 'status', width: 110,
      render: (v) => {
        const s = (v || '').toLowerCase()
        const color = s === 'optimal' ? 'success' : s === 'running' ? 'processing' : s.includes('error') ? 'error' : 'warning'
        return <Tag color={color}>{v}</Tag>
      }},
    { title: 'Chi phí tối ưu', dataIndex: 'objective_value', key: 'objective_value', width: 130,
      render: (v) => fmt(v) },
    { title: 'Thời gian giải', dataIndex: 'solve_time_seconds', key: 'solve_time', width: 110,
      render: (v) => v ? `${Number(v).toFixed(1)}s` : '—' },
    { title: 'Thao tác', key: 'action', width: 220,
      render: (_, row) => {
        const rid = row.run_id ?? row.id
        return (
          <div className="flex gap-1 flex-wrap">
            <Button size="small" icon={<EyeOutlined />}
              type={selectedHistId === rid ? 'primary' : 'default'}
              onClick={() => handleViewHistRun(rid)}>
              Chi tiết
            </Button>
            <AntTooltip title="Xem B2 · Tóm tắt & Chi tiết biến">
              <Button size="small" icon={<DashboardOutlined />}
                onClick={() => { setActiveRunId(rid); navigate('/b1-executive-summary') }}>
                B2
              </Button>
            </AntTooltip>
            <Popconfirm
              title="Xoá lần chạy này?"
              description={`Lần chạy #${rid} và toàn bộ kết quả liên quan sẽ bị xoá vĩnh viễn.`}
              onConfirm={() => handleDeleteRun(rid)}
              okText="Xoá"
              cancelText="Huỷ"
              okButtonProps={{ danger: true }}
            >
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </div>
        )
      }},
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        icon={<ThunderboltOutlined />}
        title="B1. Thực thi tối ưu hoá"
        subtitle="Chạy mô hình tối ưu hoá SS-MB-SMI trước khi xem kết quả hoặc phân tích kịch bản"
      />

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'run',
            label: <span><ThunderboltOutlined /> Chạy Mới</span>,
            children: (
              <div className="space-y-4">

      {/* Workflow steps */}
      <Card>
        <Steps
          size="small"
          current={step}
          items={[
            { title: 'Cấu hình', description: 'Chọn bộ giải và tham số', icon: <DatabaseOutlined /> },
            {
              title: 'Đang chạy',
              description: `Giải MA (GA-ALNS)${step === 1 ? ` (${elapsedSec}s)` : ''}`,
              icon: step === 1 ? <LoadingOutlined /> : <PlayCircleOutlined />,
            },
            { title: 'Hoàn thành', description: 'Xem kết quả', icon: <CheckCircleOutlined /> },
          ]}
        />
      </Card>

      {/* Done state */}
      {step === 2 && pollResult && (
        <Card>
          <div className="text-center space-y-4">
            <CheckCircleOutlined style={{ fontSize: 48, color: SEMANTIC.good }} />
            <h2 className="text-xl font-semibold">Tối ưu hoá hoàn thành!</h2>

            {/* Core KPI row */}
            <Row gutter={24} justify="center">
              <Col><Statistic title="Mã lần chạy" value={pollingRunId} prefix="#" /></Col>
              <Col>
                <Statistic
                  title="Trạng thái bộ giải"
                  value={pollResult.solver_status}
                  valueStyle={{ color: statusColor(pollResult.solver_status) }}
                />
              </Col>
              <Col>
                <Statistic title="Chi phí tối ưu" value={fmt(pollResult.objective_value)} />
              </Col>
              <Col>
                <Statistic title="Thời gian thực tế" value={elapsedSec} suffix="s" prefix={<ClockCircleOutlined />} />
              </Col>
            </Row>

            {/* Baseline / Savings summary */}
            {runSummary && (
              <>
                <Divider orientation="left" orientationMargin={0}>
                  <BarChartOutlined className="mr-1" />Tóm tắt Chi phí & Tiết kiệm
                </Divider>
                <Row gutter={[16, 16]} justify="center">
                  <Col xs={24} sm={8}>
                    <Card size="small" style={{ background: NEUTRAL[100], textAlign: 'center' }}>
                      <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>Chi phí cơ sở (Baseline)</div>
                      <div style={{ fontSize: 22, fontWeight: 700, color: '#333' }}>{fmt(runSummary.baseline_cost)}</div>
                    </Card>
                  </Col>
                  <Col xs={24} sm={8}>
                    <Card size="small" style={{ background: BRAND[50], textAlign: 'center' }}>
                      <div style={{ color: BRAND[500], fontSize: 12, marginBottom: 4 }}>Chi phí tối ưu</div>
                      <div style={{ fontSize: 22, fontWeight: 700, color: BRAND[600] }}>{fmt(runSummary.opt_cost)}</div>
                    </Card>
                  </Col>
                  <Col xs={24} sm={8}>
                    <Card size="small" style={{ background: SEMANTIC.goodBg, textAlign: 'center' }}>
                      <div style={{ color: SEMANTIC.good, fontSize: 12, marginBottom: 4 }}>
                        <FallOutlined className="mr-1" />Tiết kiệm được
                      </div>
                      <div style={{ fontSize: 22, fontWeight: 700, color: SEMANTIC.good }}>
                        {fmt(runSummary.savings)}
                        <span style={{ fontSize: 14, fontWeight: 400, marginLeft: 6, color: SEMANTIC.good }}>
                          ({(runSummary.savings_pct ?? 0).toFixed(1)}%)
                        </span>
                      </div>
                    </Card>
                  </Col>
                </Row>
                <Row gutter={[16, 8]} justify="center" style={{ marginTop: 8 }}>
                  <Col xs={12} sm={6}>
                    <Statistic title="Số thay đổi phân bổ" value={runSummary.n_changes} suffix="mục" />
                  </Col>
                  <Col xs={12} sm={6}>
                    <Statistic title="Chỉ số SI trung bình" value={(runSummary.si_mean ?? 0).toFixed(2)} />
                  </Col>
                  <Col xs={12} sm={6}>
                    <Statistic title="Vi phạm an toàn tồn kho" value={runSummary.ss_below_count} suffix="mục" />
                  </Col>
                </Row>
              </>
            )}

            <Divider orientation="left" orientationMargin={0}>Chọn bước tiếp theo</Divider>
            <Row gutter={[16, 16]}>
              <Col xs={24} md={12}>
                <Card hoverable style={{ border: `2px solid ${BRAND[500]}`, height: '100%' }}
                  title={<span style={{ color: BRAND[500] }}><ExperimentOutlined className="mr-2" />Lựa chọn 1: Phân tích &amp; điều chỉnh thêm</span>}>
                  <p className="text-gray-500 text-sm mb-3">
                    Xem kết quả đầy đủ, chạy phân tích kịch bản, rồi quay lại chạy tối ưu lại nếu chưa hài lòng.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Button type="primary" icon={<DashboardOutlined />}
                      onClick={() => navigate('/b1-executive-summary')}>
                      B2 · Xem kết quả
                    </Button>
                    <Button icon={<ExperimentOutlined />}
                      onClick={() => navigate('/c1-scenario-management')}>
                      C1 · What-If
                    </Button>
                    <Button icon={<SlidersOutlined />}
                      onClick={() => navigate('/c3-scenario-comparison')}>
                      C2 · So sánh
                    </Button>
                    <Button icon={<ReloadOutlined />} onClick={handleReset}>
                      Chạy lại B1
                    </Button>
                  </div>
                </Card>
              </Col>
              <Col xs={24} md={12}>
                <Card hoverable style={{ border: `2px solid ${SEMANTIC.good}`, height: '100%' }}
                  title={<span style={{ color: SEMANTIC.good }}><CheckCircleOutlined className="mr-2" />Lựa chọn 2: Xác nhận kết quả tối ưu</span>}>
                  <p className="text-gray-500 text-sm mb-3">
                    Xác nhận và lưu kết quả tối ưu hoá này làm kết quả chính thức.
                  </p>
                  <Button
                    type="primary"
                    style={{ background: SEMANTIC.good, borderColor: SEMANTIC.good }}
                    icon={<CheckCircleOutlined />}
                    size="large"
                    block
                    onClick={handleConfirmOptimization}>
                    Xác nhận &amp; Lưu kết quả
                  </Button>
                </Card>
              </Col>
            </Row>
          </div>
        </Card>
      )}

      {/* Running state */}
      {step === 1 && (
        <Card>
          <div className="text-center space-y-5 py-4">
            <LoadingOutlined style={{ fontSize: 48, color: BRAND[500] }} />
            <h2 className="text-xl font-semibold">Đang giải bài toán MA (Hybrid GA-ALNS)...</h2>

            {/* Time + item counter */}
            <div className="flex justify-center gap-8">
              <div>
                <div className="text-3xl font-bold tabular-nums" style={{ color: BRAND[600] }}>{elapsedSec}s</div>
                <div className="text-gray-400 text-xs mt-1">Thời gian đã chạy</div>
              </div>
              {runProductCount > 0 && (
                <div>
                  <div className="text-3xl font-bold tabular-nums" style={{ color: BRAND[600] }}>
                    {itemsDone.toLocaleString('vi-VN')}
                    <span className="text-lg font-normal text-gray-400"> / {runProductCount.toLocaleString('vi-VN')}</span>
                  </div>
                  <div className="text-gray-400 text-xs mt-1">Sản phẩm đã giải (ước tính)</div>
                </div>
              )}
            </div>

            {/* Progress bar */}
            <div className="max-w-lg mx-auto px-4">
              <Progress
                percent={progressPct}
                status="active"
                strokeColor={{ '0%': BRAND[400], '100%': SEMANTIC.good }}
              />
            </div>

            {/* Milestone tags */}
            <div className="flex justify-center flex-wrap gap-2">
              {MILESTONES.map(({ pct, label }) => (
                <Tag
                  key={pct}
                  color={progressPct >= pct ? 'green' : 'default'}
                  icon={progressPct >= pct ? <CheckCircleOutlined /> : <LoadingOutlined />}
                >
                  {label}
                </Tag>
              ))}
            </div>

            <p className="text-gray-400 text-sm">
              Lần chạy #{pollingRunId} &middot; Trang tự động cập nhật khi hoàn thành.
            </p>
          </div>
        </Card>
      )}

      {/* Configure state */}
      {step === 0 && (
        <Row gutter={16}>
          <Col xs={24} md={10}>
            <Card title={<><DatabaseOutlined className="mr-2" />Dữ liệu tối ưu hoá</>} loading={loadingOverview}>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-500">Sản phẩm (I)</span>
                  <strong>{counts.num_products ?? '--'}</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Kho hàng (J)</span>
                  <strong>{counts.num_warehouses ?? '--'}</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Chu kỳ (T)</span>
                  <strong>{counts.num_periods ?? '--'}</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Tổ hợp (IxJxT)</span>
                  <strong>{counts.total_combinations ?? '--'}</strong>
                </div>
                <Divider className="my-2" />
                <div className="text-xs text-gray-400">Mô hình: SS-MB-SMI &middot; Bộ giải: Hybrid GA-ALNS (MA)</div>
              </div>
            </Card>
          </Col>

          <Col xs={24} md={14}>
            <Card title={<><PlayCircleOutlined className="mr-2" />Cài đặt tối ưu hoá</>}>
              {errorMsg && (
                <Alert type="error" message={errorMsg} showIcon closable className="mb-4" onClose={() => setErrorMsg(null)} />
              )}
              <Form form={form} layout="vertical" initialValues={{ solver: 'ma', time_limit: 10, mip_gap: 0.01, product_limit: 20 }}>
                <Form.Item label="Bộ giải (Solver)">
                  <div className="flex items-center gap-2">
                    <Tag color="blue" className="text-sm py-1 px-3">MA · Memetic (Hybrid GA-ALNS)</Tag>
                  </div>
                  <div className="text-gray-500 text-xs mt-1">
                    Giải thuật Memetic kết hợp thuật toán di truyền và tìm kiếm lân cận lớn thích nghi — bộ giải chính của hệ thống SS-MB-SMI.
                  </div>
                </Form.Item>
                <Form.Item
                  label="Số sản phẩm chạy" name="product_limit"
                  extra="Để TRỐNG (xóa số) = chạy toàn bộ 943 sản phẩm (~2.5 giờ). Nhập số nhỏ (vd 20) để test nhanh toàn bộ luồng (~vài phút)."
                >
                  <InputNumber min={1} max={943} step={1} style={{ width: '100%' }} placeholder="Trống = toàn bộ 943 SP" />
                </Form.Item>
                <Form.Item
                  label="Giới hạn thời gian mỗi sản phẩm (giây)" name="time_limit"
                  rules={[{ required: true, type: 'number', min: 1, max: 3600 }]}
                  extra="Thời gian tối đa MA chạy cho mỗi sản phẩm. Tăng để nghiệm hội tụ tốt hơn, giảm để chạy nhanh hơn khi test."
                >
                  <InputNumber min={1} max={3600} step={1} style={{ width: '100%' }} />
                </Form.Item>
                <Alert
                  className="mb-4"
                  type={isFullRun ? 'warning' : 'info'}
                  showIcon
                  message={
                    <span>
                      {isFullRun
                        ? <>Chạy <b>toàn bộ 943 sản phẩm</b> — thời gian ước tính <b>{estimateText}</b>. Nên chạy khi không cần dùng máy.</>
                        : <>Chế độ test: <b>{watchedLimit} sản phẩm</b> — thời gian ước tính <b>{estimateText}</b>.</>}
                    </span>
                  }
                />
                <Form.Item className="mb-0">
                  <Button
                    type="primary" icon={<ThunderboltOutlined />} size="large" block
                    onClick={handleRun} loading={submitting} disabled={submitting}
                  >
                    {submitting ? 'Đang gửi...' : 'Chạy Tối Ưu Hoá'}
                  </Button>
                </Form.Item>
              </Form>
            </Card>
          </Col>
        </Row>
      )}
              </div>
            ),
          },
          {
            key: 'history',
            label: (
              <span>
                <HistoryOutlined /> Lịch Sử
                {histRuns.length > 0 && (
                  <Badge count={histRuns.length} size="small"
                    style={{ marginLeft: 6, backgroundColor: BRAND[500] }} />
                )}
              </span>
            ),
            children: (
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 text-sm">
                    Tổng cộng <strong>{histRuns.length}</strong> lần chạy. Nhấn <strong>Chi tiết</strong> để xem tóm tắt, hoặc <strong>Xem B1</strong> để phân tích toàn bộ.
                  </span>
                  <Button size="small" icon={<ReloadOutlined />} onClick={loadHistory} loading={histLoading}>
                    Làm mới
                  </Button>
                </div>

                <Table
                  dataSource={histRuns}
                  columns={histColumns}
                  rowKey={(r) => r.run_id ?? r.id ?? Math.random()}
                  size="small"
                  loading={histLoading}
                  pagination={{ pageSize: 10, showSizeChanger: false }}
                  rowClassName={(r) => r.run_id === selectedHistId ? 'ant-table-row-selected' : ''}
                  locale={{ emptyText: 'Chưa có lần chạy nào. Hãy chạy tối ưu hoá trước.' }}
                />

                {/* Chi tiết lần chạy đã chọn */}
                {selectedHistId && (
                  <Card
                    title={<><EyeOutlined className="mr-2" />Chi tiết lần chạy #{selectedHistId}</>}
                    loading={histSummaryLoading}
                    extra={
                      <div className="flex gap-2">
                        <Button type="primary" size="small" icon={<DashboardOutlined />}
                          onClick={() => { setActiveRunId(selectedHistId); navigate('/b1-executive-summary') }}>
                          B2 · Tóm tắt &amp; Chi tiết
                        </Button>
                        <Button size="small" icon={<BarChartOutlined />}
                          onClick={() => { setActiveRunId(selectedHistId); navigate('/b2-allocation-inventory-dashboard') }}>
                          B3 · Phân bổ
                        </Button>
                      </div>
                    }
                  >
                    {histSummary ? (
                      <>
                        <Row gutter={[16, 16]}>
                          <Col xs={24} sm={8}>
                            <Card size="small" style={{ background: NEUTRAL[100], textAlign: 'center' }}>
                              <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>Chi phí cơ sở (Baseline)</div>
                              <div style={{ fontSize: 20, fontWeight: 700, color: '#333' }}>{fmt(histSummary.baseline_cost)}</div>
                            </Card>
                          </Col>
                          <Col xs={24} sm={8}>
                            <Card size="small" style={{ background: BRAND[50], textAlign: 'center' }}>
                              <div style={{ color: BRAND[500], fontSize: 12, marginBottom: 4 }}>Chi phí tối ưu</div>
                              <div style={{ fontSize: 20, fontWeight: 700, color: BRAND[600] }}>{fmt(histSummary.opt_cost)}</div>
                            </Card>
                          </Col>
                          <Col xs={24} sm={8}>
                            <Card size="small" style={{ background: SEMANTIC.goodBg, textAlign: 'center' }}>
                              <div style={{ color: SEMANTIC.good, fontSize: 12, marginBottom: 4 }}>
                                <FallOutlined className="mr-1" />Tiết kiệm được
                              </div>
                              <div style={{ fontSize: 20, fontWeight: 700, color: SEMANTIC.good }}>
                                {fmt(histSummary.savings)}
                                <span style={{ fontSize: 13, fontWeight: 400, marginLeft: 6, color: SEMANTIC.good }}>
                                  ({(histSummary.savings_pct ?? 0).toFixed(1)}%)
                                </span>
                              </div>
                            </Card>
                          </Col>
                        </Row>
                        <Row gutter={[16, 8]} style={{ marginTop: 12 }}>
                          <Col xs={12} sm={6}>
                            <Statistic title="Số thay đổi phân bổ" value={histSummary.n_changes} suffix="mục" />
                          </Col>
                          <Col xs={12} sm={6}>
                            <Statistic title="Chỉ số SI trung bình" value={(histSummary.si_mean ?? 0).toFixed(2)} />
                          </Col>
                          <Col xs={12} sm={6}>
                            <Statistic title="Vi phạm an toàn tồn kho" value={histSummary.ss_below_count} suffix="mục" />
                          </Col>
                        </Row>
                      </>
                    ) : (
                      !histSummaryLoading && (
                        <Alert type="warning" showIcon
                          message="Không có dữ liệu tóm tắt cho lần chạy này (có thể là lần chạy cũ chưa lưu baseline)." />
                      )
                    )}
                  </Card>
                )}
              </div>
            ),
          },
        ]}
      />
    </div>
  )
}

export default RunOptimization