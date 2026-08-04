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

// Parameters available for sensitivity analysis (CP case-pack excluded, not elastic).
const PARAMETERS = [
  { code: 'DI',  label: 'DI · Demand fluctuation' },
  { code: 'CAP', label: 'CAP · Supply Capacity' },
  { code: 'Cb',  label: 'Cb · Backorder cost' },
  { code: 'Co',  label: 'Co · Overstock cost' },
  { code: 'Cs',  label: 'Cs · Shortage cost' },
  { code: 'Cp',  label: 'Cp · Packing penalty cost' },
  { code: 'U',   label: 'U · Ceiling level' },
  { code: 'L',   label: 'L · Floor level' },
  { code: 'BI',  label: 'BI · Beginning inventory' },
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

  // localStorage stores {id, ts} to resume + count elapsed from the real timestamp.
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
      message.info('Stop request sent. The job will stop after completing the current computation step.')
    } catch (e) {
      message.error('Failed to send stop request')
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
    // elapsed is computed from the real timestamp → does not reset when returning to the page
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
          message.warning('Analysis has been stopped.')
        } else if (res.status === 'failed') {
          stop()
          message.error('Analysis failed: ' + (res.error || 'Unknown error'))
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
    message.success('OAT analysis complete!')
    loadHistory()
  }, 'smi_d2_oat_job')

  const { polling: pollingTornado, elapsed: elapsedTornado, startPolling: startTornado, cancelJob: cancelTornado, cancelling: cancellingTornado } = usePollJob((result) => {
    // Tornado result stored as {baseline_objective, variation_pct, bars}
    setTornadoResult(result)
    message.success('Tornado analysis complete!')
    loadHistory()
  }, 'smi_d2_tornado_job')

  // View a completed job from history
  const viewHistoryJob = async (job) => {
    try {
      const res = await sensitivityService.getResults(job.job_id)
      const result = res?.result
      if (!result) { message.warning('Job has no results yet'); return }
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
      message.error('Failed to load job results')
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
      message.error('Unable to start the analysis')
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
      message.error('Unable to start the analysis')
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
        title="D1. Parameter Sensitivity Analysis"
        subtitle="Assess how much each parameter impacts cost (OAT analysis and tornado chart)"
      />

      <Card>
        <div className="flex items-center gap-4 flex-wrap">
          <div><span className="mr-2">Scenario ID:</span><InputNumber min={1} value={scenarioId} onChange={setScenarioId} /></div>
          <Radio.Group value={analysisType} onChange={(e) => setAnalysisType(e.target.value)} buttonStyle="solid">
            <Radio.Button value="oat">Single parameter</Radio.Button>
            <Radio.Button value="tornado">Tornado</Radio.Button>
          </Radio.Group>
          {analysisType === 'oat' && (
            <>
              <Select value={selectedParam} onChange={setSelectedParam} style={{ width: 280 }}>
                {PARAMETERS.map(p => <Option key={p.code} value={p.code}>{p.label}</Option>)}
              </Select>
              <Button type="primary" icon={<ThunderboltOutlined />} onClick={handleRunOAT} loading={pollingOAT || submitting} disabled={loading}>Run OAT</Button>
            </>
          )}
          {analysisType === 'tornado' && (
            <>
              <div><span className="mr-2">Variation %:</span><InputNumber min={1} max={50} value={variationPct} onChange={setVariationPct} /></div>
              <Button type="primary" icon={<BarChartOutlined />} onClick={handleRunTornado} loading={pollingTornado || submitting} disabled={loading}>Run Tornado</Button>
            </>
          )}
          <Tooltip title={fullDataset ? 'Run on all 943 products — VERY SLOW (each variation level is a full MA run)' : 'Run on 50 representative samples (selected by warehouse-count group, prioritizing high-cost products) — OAT ~22 min, Tornado ~57 min'}>
            <div className="flex items-center gap-2 ml-2">
              <span className="text-xs text-gray-500">{fullDataset ? '943 products' : '50 samples'}</span>
              <Switch size="small" checked={fullDataset} onChange={setFullDataset} />
              <span className="text-xs text-gray-500">Full dataset</span>
            </div>
          </Tooltip>
        </div>
        {fullDataset && (
          <Alert
            className="mt-3"
            type="warning"
            showIcon
            message="Warning: running on all 943 products"
            description={
              analysisType === 'oat'
                ? 'OAT runs 4 variation levels on all 943 products → each level is a full MA run, which can take MANY HOURS in total. Recommended: use the 50-sample mode (~22 min).'
                : 'Tornado runs ±variation for 6 parameters = 12 full MA runs on all 943 products → can take MANY HOURS. Recommended: use the 50-sample mode (~57 min).'
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
              Running {pollingOAT ? `OAT (${selectedParam})` : 'Tornado'} analysis
              {' '}on <b>{fullDataset ? '943 products' : '50 representative samples'}</b>...
              <span className="ml-2 font-mono" style={{ color: BRAND[600] }}>{pollingOAT ? elapsedOAT : elapsedTornado}s</span>
              <span className="ml-2 text-gray-400">({fullDataset ? 'all 943 products — may take several hours' : '50-product sample'})</span>
            </span>
          }
          description={
            (pollingOAT ? cancellingOAT : cancellingTornado)
              ? 'Stopping… the job will end after completing the current computation step (may take up to a few minutes).'
              : 'Job runs in the background — you can leave the page and come back; the result is still tracked and saved in the History section below.'
          }
          action={
            <Popconfirm
              title="Stop the analysis?"
              description="The job will stop after completing the current computation step. Partial results will not be saved."
              okText="Stop" cancelText="Continue"
              onConfirm={pollingOAT ? cancelOAT : cancelTornado}
            >
              <Button danger size="small" loading={pollingOAT ? cancellingOAT : cancellingTornado}>
                {(pollingOAT ? cancellingOAT : cancellingTornado) ? 'Stopping…' : 'Stop'}
              </Button>
            </Popconfirm>
          }
        />
      )}

      {analysisType === 'oat' && oatResult && (
        <>
          <Row gutter={16}>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Parameter</p><Tag color="blue">{paramLabel(oatResult.parameter_name)}</Tag></div></Card></Col>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Baseline objective</p><p className="text-xl font-bold">{Number(oatResult.baseline_objective || 0).toLocaleString('vi-VN')}</p></div></Card></Col>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Elasticity</p><p className="text-xl font-bold">{Number(oatResult.elasticity || 0).toFixed(3)}</p></div></Card></Col>
          </Row>
          <Card title={`Sensitivity: ${paramLabel(oatResult.parameter_name)}`}>
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
                  label={{ value: 'Baseline', position: 'insideBottomLeft', fill: SEMANTIC.bad, fontSize: 11, dy: -6 }}
                />
                <Line type="monotone" dataKey="objective" stroke={BRAND[500]} strokeWidth={2} name="Objective value" />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </>
      )}

      {analysisType === 'tornado' && tornadoResult && (
        <>
          <Row gutter={16}>
            <Col span={12}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Baseline</p><p className="text-xl font-bold">{Number(tornadoResult.baseline_objective || 0).toLocaleString('vi-VN')}</p></div></Card></Col>
            <Col span={12}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Variation</p><p className="text-xl font-bold">+/- {tornadoResult.variation_pct}%</p></div></Card></Col>
          </Row>
          <Card title="Tornado Chart">
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={tornadoChartData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis type="category" dataKey="parameter" width={60} />
                <RechartsTooltip />
                <Legend />
                <ReferenceLine x={0} stroke="#000" />
                <Bar dataKey="low" fill={SEMANTIC.good} name="Low (-)" />
                <Bar dataKey="high" fill={SEMANTIC.bad} name="High (+)" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card title="Parameter Sensitivity Ranking">
            <Table
              columns={[
                { title: 'Parameter', dataIndex: 'parameter_name', key: 'parameter_name', render: (t) => <Tag color="blue">{paramLabel(t)}</Tag> },
                { title: 'Low value', dataIndex: 'low_value', key: 'low_value', render: (v) => Number(v).toLocaleString('vi-VN') },
                { title: 'High value', dataIndex: 'high_value', key: 'high_value', render: (v) => Number(v).toLocaleString('vi-VN') },
                { title: 'Variation range', dataIndex: 'spread', key: 'spread', render: (v) => <span className="font-bold">{Number(v).toLocaleString('vi-VN')}</span> },
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
        <Alert message="Select a parameter and run the analysis to see results" type="info" showIcon />
      )}

      <Card title="Analysis History" extra={<Button size="small" onClick={loadHistory}>Refresh</Button>}>
        <Table
          columns={[
            { title: 'ID', dataIndex: 'job_id', key: 'job_id', width: 60 },
            { title: 'Type', dataIndex: 'analysis_type', key: 'analysis_type', width: 90,
              render: (t) => <Tag color={t === 'tornado' ? 'purple' : 'blue'}>{t === 'tornado' ? 'Tornado' : 'OAT'}</Tag> },
            { title: 'Parameter', dataIndex: 'parameter_name', key: 'parameter_name' },
            { title: 'Status', dataIndex: 'status', key: 'status', width: 110,
              render: (s) => {
                const color = s === 'completed' ? 'green' : s === 'running' ? 'processing' : s === 'failed' ? 'red' : 'default'
                return <Tag color={color}>{s}</Tag>
              } },
            { title: 'Time', dataIndex: 'created_at', key: 'created_at',
              render: (v) => v ? new Date(v).toLocaleString('vi-VN') : '—' },
            { title: '', key: 'action', width: 90,
              render: (_, r) => r.status === 'completed'
                ? <Button size="small" type="link" onClick={() => viewHistoryJob(r)}>View</Button>
                : null },
          ]}
          dataSource={history}
          pagination={{ pageSize: 5 }}
          size="small"
          rowKey="job_id"
          locale={{ emptyText: 'No analysis history yet' }}
        />
      </Card>
    </div>
  )
}

export default SensitivityAnalysis
