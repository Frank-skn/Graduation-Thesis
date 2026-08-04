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
    if (secs < 90) return `~${Math.max(5, Math.round(secs))} sec`
    if (secs < 3600) return `~${Math.round(secs / 60)} min`
    return `~${(secs / 3600).toFixed(1)} hr`
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
  // Number of products and start timestamp of the current run (used to estimate progress)
  const [runProductCount, setRunProductCount] = useState(943)
  const startTsRef = useRef(null)
  const pollRef = useRef(null)
  const timerRef = useRef(null)

  // localStorage key used to persist "running" state when leaving and returning to the page
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
    // elapsed is computed from a real timestamp → resumes correctly when returning to the page
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
          if (ok) message.success(`Optimization completed! Run #${runId} - ${status.solver_status}`)
          else message.error(`Run #${runId} ended with status: ${status.solver_status}`)
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

  // Resume "running" state if the user leaves the page and comes back
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
    message.success('Optimization results confirmed and saved successfully!')
    navigate('/b2-executive-summary')
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
        setErrorMsg('Unable to create or find the base scenario. Check the backend connection.')
        setSubmitting(false)
        return
      }

      if (!scenarioId) {
        setErrorMsg('Could not retrieve the scenario ID. Please try again.')
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
        setErrorMsg(`Unable to submit the optimization job: ${detail}`)
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
      // Persist state so it can be resumed after leaving and returning to the page
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
  // Estimated total time = number of products × ~10s/product (based on empirical measurement).
  // Progress is based on elapsed time vs. the estimated total, capped at 97% until the
  // backend reports completion (avoids showing 100% before it's actually done).
  const estTotalSec = Math.max(10, runProductCount * 10)
  const progressPct = Math.min(97, Math.floor((elapsedSec / estTotalSec) * 100))
  const itemsDone = Math.min(runProductCount, Math.floor((progressPct / 100) * runProductCount))

  const MILESTONES = [
    { pct: 15, label: 'Loading data' },
    { pct: 40, label: 'Building model' },
    { pct: 70, label: 'Solving with MA (GA-ALNS)' },
    { pct: 92, label: 'Validating solution' },
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
      message.success(`Run #${runId} deleted`)
      if (selectedHistId === runId) {
        setSelectedHistId(null)
        setHistSummary(null)
      }
      loadHistory()
    } catch (err) {
      message.error(`Delete failed: ${err?.message || 'Unknown error'}`)
    }
  }

  const histColumns = [
    { title: 'Run', dataIndex: 'run_id', key: 'run_id', width: 90,
      render: (v) => <strong>#{v}</strong> },
    { title: 'Data Version', dataIndex: 'version_id', key: 'version_id', width: 110,
      render: (v) => v ? <Tag color="blue">V #{v}</Tag> : <span className="text-gray-400">—</span> },
    { title: 'Run Time', dataIndex: 'run_time', key: 'run_time', width: 160,
      render: (v) => v ? String(v).slice(0, 16) : '—' },
    { title: 'Status', dataIndex: 'solver_status', key: 'status', width: 110,
      render: (v) => {
        const s = (v || '').toLowerCase()
        const color = s === 'optimal' ? 'success' : s === 'running' ? 'processing' : s.includes('error') ? 'error' : 'warning'
        return <Tag color={color}>{v}</Tag>
      }},
    { title: 'Optimal Cost', dataIndex: 'objective_value', key: 'objective_value', width: 130,
      render: (v) => fmt(v) },
    { title: 'Solve Time', dataIndex: 'solve_time_seconds', key: 'solve_time', width: 110,
      render: (v) => v ? `${Number(v).toFixed(1)}s` : '—' },
    { title: 'Actions', key: 'action', width: 220,
      render: (_, row) => {
        const rid = row.run_id ?? row.id
        return (
          <div className="flex gap-1 flex-wrap">
            <Button size="small" icon={<EyeOutlined />}
              type={selectedHistId === rid ? 'primary' : 'default'}
              onClick={() => handleViewHistRun(rid)}>
              Details
            </Button>
            <AntTooltip title="View B2 · Summary & Variable Details">
              <Button size="small" icon={<DashboardOutlined />}
                onClick={() => { setActiveRunId(rid); navigate('/b2-executive-summary') }}>
                B2
              </Button>
            </AntTooltip>
            <Popconfirm
              title="Delete this run?"
              description={`Run #${rid} and all related results will be permanently deleted.`}
              onConfirm={() => handleDeleteRun(rid)}
              okText="Delete"
              cancelText="Cancel"
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
        title="B1. Run Optimization"
        subtitle="Run the SS-MB-SMI optimization model before viewing results or analyzing scenarios"
      />

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'run',
            label: <span><ThunderboltOutlined /> New Run</span>,
            children: (
              <div className="space-y-4">

      {/* Workflow steps */}
      <Card>
        <Steps
          size="small"
          current={step}
          items={[
            { title: 'Configure', description: 'Choose solver and parameters', icon: <DatabaseOutlined /> },
            {
              title: 'Running',
              description: `Solving with MA (GA-ALNS)${step === 1 ? ` (${elapsedSec}s)` : ''}`,
              icon: step === 1 ? <LoadingOutlined /> : <PlayCircleOutlined />,
            },
            { title: 'Completed', description: 'View results', icon: <CheckCircleOutlined /> },
          ]}
        />
      </Card>

      {/* Done state */}
      {step === 2 && pollResult && (
        <Card>
          <div className="text-center space-y-4">
            <CheckCircleOutlined style={{ fontSize: 48, color: SEMANTIC.good }} />
            <h2 className="text-xl font-semibold">Optimization completed!</h2>

            {/* Core KPI row */}
            <Row gutter={24} justify="center">
              <Col><Statistic title="Run ID" value={pollingRunId} prefix="#" /></Col>
              <Col>
                <Statistic
                  title="Solver Status"
                  value={pollResult.solver_status}
                  valueStyle={{ color: statusColor(pollResult.solver_status) }}
                />
              </Col>
              <Col>
                <Statistic title="Optimal Cost" value={fmt(pollResult.objective_value)} />
              </Col>
              <Col>
                <Statistic title="Actual Time" value={elapsedSec} suffix="s" prefix={<ClockCircleOutlined />} />
              </Col>
            </Row>

            {/* Baseline / Savings summary */}
            {runSummary && (
              <>
                <Divider orientation="left" orientationMargin={0}>
                  <BarChartOutlined className="mr-1" />Cost & Savings Summary
                </Divider>
                <Row gutter={[16, 16]} justify="center">
                  <Col xs={24} sm={8}>
                    <Card size="small" style={{ background: NEUTRAL[100], textAlign: 'center' }}>
                      <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>Baseline Cost</div>
                      <div style={{ fontSize: 22, fontWeight: 700, color: '#333' }}>{fmt(runSummary.baseline_cost)}</div>
                    </Card>
                  </Col>
                  <Col xs={24} sm={8}>
                    <Card size="small" style={{ background: BRAND[50], textAlign: 'center' }}>
                      <div style={{ color: BRAND[500], fontSize: 12, marginBottom: 4 }}>Optimal Cost</div>
                      <div style={{ fontSize: 22, fontWeight: 700, color: BRAND[600] }}>{fmt(runSummary.opt_cost)}</div>
                    </Card>
                  </Col>
                  <Col xs={24} sm={8}>
                    <Card size="small" style={{ background: SEMANTIC.goodBg, textAlign: 'center' }}>
                      <div style={{ color: SEMANTIC.good, fontSize: 12, marginBottom: 4 }}>
                        <FallOutlined className="mr-1" />Savings
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
                    <Statistic title="Allocation Changes" value={runSummary.n_changes} suffix="items" />
                  </Col>
                  <Col xs={12} sm={6}>
                    <Statistic title="Average SI" value={(runSummary.si_mean ?? 0).toFixed(2)} />
                  </Col>
                  <Col xs={12} sm={6}>
                    <Statistic title="Safety Stock Violations" value={runSummary.ss_below_count} suffix="items" />
                  </Col>
                </Row>
              </>
            )}

            <Divider orientation="left" orientationMargin={0}>Choose Next Step</Divider>
            <Row gutter={[16, 16]}>
              <Col xs={24} md={12}>
                <Card hoverable style={{ border: `2px solid ${BRAND[500]}`, height: '100%' }}
                  title={<span style={{ color: BRAND[500] }}><ExperimentOutlined className="mr-2" />Option 1: Analyze &amp; adjust further</span>}>
                  <p className="text-gray-500 text-sm mb-3">
                    View the full results, run scenario analysis, then come back and re-run the optimization if needed.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Button type="primary" icon={<DashboardOutlined />}
                      onClick={() => navigate('/b2-executive-summary')}>
                      B2 · View Results
                    </Button>
                    <Button icon={<ExperimentOutlined />}
                      onClick={() => navigate('/c1-scenario-management')}>
                      C1 · What-If
                    </Button>
                    <Button icon={<SlidersOutlined />}
                      onClick={() => navigate('/c2-scenario-comparison')}>
                      C2 · Compare
                    </Button>
                    <Button icon={<ReloadOutlined />} onClick={handleReset}>
                      Re-run B1
                    </Button>
                  </div>
                </Card>
              </Col>
              <Col xs={24} md={12}>
                <Card hoverable style={{ border: `2px solid ${SEMANTIC.good}`, height: '100%' }}
                  title={<span style={{ color: SEMANTIC.good }}><CheckCircleOutlined className="mr-2" />Option 2: Confirm optimization results</span>}>
                  <p className="text-gray-500 text-sm mb-3">
                    Confirm and save this optimization result as the official result.
                  </p>
                  <Button
                    type="primary"
                    style={{ background: SEMANTIC.good, borderColor: SEMANTIC.good }}
                    icon={<CheckCircleOutlined />}
                    size="large"
                    block
                    onClick={handleConfirmOptimization}>
                    Confirm &amp; Save Results
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
            <h2 className="text-xl font-semibold">Solving with MA (Hybrid GA-ALNS)...</h2>

            {/* Time + item counter */}
            <div className="flex justify-center gap-8">
              <div>
                <div className="text-3xl font-bold tabular-nums" style={{ color: BRAND[600] }}>{elapsedSec}s</div>
                <div className="text-gray-400 text-xs mt-1">Elapsed Time</div>
              </div>
              {runProductCount > 0 && (
                <div>
                  <div className="text-3xl font-bold tabular-nums" style={{ color: BRAND[600] }}>
                    {itemsDone.toLocaleString('en-US')}
                    <span className="text-lg font-normal text-gray-400"> / {runProductCount.toLocaleString('en-US')}</span>
                  </div>
                  <div className="text-gray-400 text-xs mt-1">Products Solved (estimated)</div>
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
              Run #{pollingRunId} &middot; This page updates automatically when finished.
            </p>
          </div>
        </Card>
      )}

      {/* Configure state */}
      {step === 0 && (
        <Row gutter={16}>
          <Col xs={24} md={10}>
            <Card title={<><DatabaseOutlined className="mr-2" />Optimization Data</>} loading={loadingOverview}>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-500">Products (I)</span>
                  <strong>{counts.num_products ?? '--'}</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Warehouses (J)</span>
                  <strong>{counts.num_warehouses ?? '--'}</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Periods (T)</span>
                  <strong>{counts.num_periods ?? '--'}</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Combinations (IxJxT)</span>
                  <strong>{counts.total_combinations ?? '--'}</strong>
                </div>
                <Divider className="my-2" />
                <div className="text-xs text-gray-400">Model: SS-MB-SMI &middot; Solver: Hybrid GA-ALNS (MA)</div>
              </div>
            </Card>
          </Col>

          <Col xs={24} md={14}>
            <Card title={<><PlayCircleOutlined className="mr-2" />Optimization Settings</>}>
              {errorMsg && (
                <Alert type="error" message={errorMsg} showIcon closable className="mb-4" onClose={() => setErrorMsg(null)} />
              )}
              <Form form={form} layout="vertical" initialValues={{ solver: 'ma', time_limit: 10, mip_gap: 0.01, product_limit: 20 }}>
                <Form.Item label="Solver">
                  <div className="flex items-center gap-2">
                    <Tag color="blue" className="text-sm py-1 px-3">MA · Memetic (Hybrid GA-ALNS)</Tag>
                  </div>
                  <div className="text-gray-500 text-xs mt-1">
                    A Memetic Algorithm combining a genetic algorithm with adaptive large neighborhood search — the primary solver of the SS-MB-SMI system.
                  </div>
                </Form.Item>
                <Form.Item
                  label="Number of Products to Run" name="product_limit"
                  extra="Leave EMPTY (clear the number) to run all 943 products (~2.5 hours). Enter a small number (e.g. 20) to quickly test the full pipeline (~a few minutes)."
                >
                  <InputNumber min={1} max={943} step={1} style={{ width: '100%' }} placeholder="Empty = all 943 products" />
                </Form.Item>
                <Form.Item
                  label="Time Limit per Product (seconds)" name="time_limit"
                  rules={[{ required: true, type: 'number', min: 1, max: 3600 }]}
                  extra="Maximum time MA runs for each product. Increase for better convergence, decrease for faster test runs."
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
                        ? <>Running <b>all 943 products</b> — estimated time <b>{estimateText}</b>. Best run when you don't need the machine.</>
                        : <>Test mode: <b>{watchedLimit} products</b> — estimated time <b>{estimateText}</b>.</>}
                    </span>
                  }
                />
                <Form.Item className="mb-0">
                  <Button
                    type="primary" icon={<ThunderboltOutlined />} size="large" block
                    onClick={handleRun} loading={submitting} disabled={submitting}
                  >
                    {submitting ? 'Submitting...' : 'Run Optimization'}
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
                <HistoryOutlined /> History
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
                    Total of <strong>{histRuns.length}</strong> runs. Click <strong>Details</strong> for a summary, or <strong>View B2</strong> for full analysis.
                  </span>
                  <Button size="small" icon={<ReloadOutlined />} onClick={loadHistory} loading={histLoading}>
                    Refresh
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
                  locale={{ emptyText: 'No runs yet. Please run an optimization first.' }}
                />

                {/* Details of the selected run */}
                {selectedHistId && (
                  <Card
                    title={<><EyeOutlined className="mr-2" />Run #{selectedHistId} Details</>}
                    loading={histSummaryLoading}
                    extra={
                      <div className="flex gap-2">
                        <Button type="primary" size="small" icon={<DashboardOutlined />}
                          onClick={() => { setActiveRunId(selectedHistId); navigate('/b2-executive-summary') }}>
                          B2 · Summary &amp; Details
                        </Button>
                        <Button size="small" icon={<BarChartOutlined />}
                          onClick={() => { setActiveRunId(selectedHistId); navigate('/b3-allocation-inventory-dashboard') }}>
                          B3 · Allocation
                        </Button>
                      </div>
                    }
                  >
                    {histSummary ? (
                      <>
                        <Row gutter={[16, 16]}>
                          <Col xs={24} sm={8}>
                            <Card size="small" style={{ background: NEUTRAL[100], textAlign: 'center' }}>
                              <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>Baseline Cost</div>
                              <div style={{ fontSize: 20, fontWeight: 700, color: '#333' }}>{fmt(histSummary.baseline_cost)}</div>
                            </Card>
                          </Col>
                          <Col xs={24} sm={8}>
                            <Card size="small" style={{ background: BRAND[50], textAlign: 'center' }}>
                              <div style={{ color: BRAND[500], fontSize: 12, marginBottom: 4 }}>Optimal Cost</div>
                              <div style={{ fontSize: 20, fontWeight: 700, color: BRAND[600] }}>{fmt(histSummary.opt_cost)}</div>
                            </Card>
                          </Col>
                          <Col xs={24} sm={8}>
                            <Card size="small" style={{ background: SEMANTIC.goodBg, textAlign: 'center' }}>
                              <div style={{ color: SEMANTIC.good, fontSize: 12, marginBottom: 4 }}>
                                <FallOutlined className="mr-1" />Savings
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
                            <Statistic title="Allocation Changes" value={histSummary.n_changes} suffix="items" />
                          </Col>
                          <Col xs={12} sm={6}>
                            <Statistic title="Average SI" value={(histSummary.si_mean ?? 0).toFixed(2)} />
                          </Col>
                          <Col xs={12} sm={6}>
                            <Statistic title="Safety Stock Violations" value={histSummary.ss_below_count} suffix="items" />
                          </Col>
                        </Row>
                      </>
                    ) : (
                      !histSummaryLoading && (
                        <Alert type="warning" showIcon
                          message="No summary data available for this run (it may be an older run without a saved baseline)." />
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