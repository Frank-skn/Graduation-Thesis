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
      message.info('Stop request sent. The job will stop after completing the current computation step.')
    } catch (e) {
      message.error('Failed to send stop request')
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
          stop(); message.warning('Analysis has been stopped.')
        } else if (res.status === 'failed') {
          stop(); message.error('Analysis failed: ' + (res.error || 'Unknown'))
        } else if (res.status === 'cancelling') {
          setCancelling(true)
        }
      } catch { stop() }
    }, 4000)
    return () => { clearInterval(intervalRef.current); clearInterval(timerRef.current) }
  }, [polling, jobId, persistKey])

  return { polling, elapsed, startPolling, cancelJob, cancelling }
}

// English labels for parameter codes
const PARAM_LABELS = {
  DI: 'DI · Demand fluctuation',
  CAP: 'CAP · Supply Capacity',
  Cb: 'Cb · Backorder cost',
  Co: 'Co · Overstock cost',
  Cs: 'Cs · Shortage cost',
  Cp: 'Cp · Packing penalty cost',
  U: 'U · Ceiling level',
  L: 'L · Floor level',
  BI: 'BI · Beginning inventory',
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
    message.success('Stability check complete!')
    loadHistory()
  }, 'smi_d3_stability_job')

  const viewHistoryJob = async (job) => {
    try {
      const res = await sensitivityService.getResults(job.job_id)
      if (!res?.result) { message.warning('Job has no results yet'); return }
      setResults(res.result)
    } catch (e) {
      message.error('Failed to load job results')
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
    } catch { message.error('Unable to start the analysis') }
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
    { title: 'Parameter', dataIndex: 'parameter_name', key: 'parameter_name', render: (t) => <Tag color="blue">{paramLabel(t)}</Tag> },
    { title: `Value at -${variationLevel}%`, dataIndex: 'low_value', key: 'low_value', render: (v) => `${Number(v).toLocaleString('vi-VN')}` },
    { title: `Value at +${variationLevel}%`, dataIndex: 'high_value', key: 'high_value', render: (v) => `${Number(v).toLocaleString('vi-VN')}` },
    { title: 'Variation range', dataIndex: 'spread', key: 'spread', align: 'right', render: (v) => <span className="font-semibold tabular-nums" style={{ color: NEUTRAL[700] }}>{Number(v).toLocaleString('vi-VN')}</span> },
    {
      title: 'Stability index', key: 'stability',
      render: (_, record) => {
        const volatility = Math.abs(Number(record.spread || 0)) / Math.max(1, Number(results?.baseline_objective || 1)) * 100
        const stability = Math.max(0, 100 - volatility)
        return <Progress percent={Math.round(stability)} size="small" status={stability > 80 ? 'success' : stability > 60 ? 'normal' : 'exception'} />
      },
    },
    {
      title: 'Rating', key: 'rating',
      render: (_, record) => {
        const volatility = Math.abs(Number(record.spread || 0)) / Math.max(1, Number(results?.baseline_objective || 1)) * 100
        if (volatility < 5)  return <Tag color="green">Very stable</Tag>
        if (volatility < 15) return <Tag color="blue">Stable</Tag>
        if (volatility < 25) return <Tag color="orange">Moderate</Tag>
        return <Tag color="red">Volatile</Tag>
      },
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        icon={<BarChartOutlined />}
        title="D2. Optimal Solution Stability"
        subtitle="Analyze the stability of the optimal solution as parameters change"
      />

      <Card>
        <div className="flex items-center gap-4 flex-wrap">
          <div><span className="mr-2">Scenario ID:</span><InputNumber min={1} value={scenarioId} onChange={setScenarioId} /></div>
          <div style={{ width: 200 }}>
            <span className="mr-2">Variation level: {variationLevel}%</span>
            <Slider min={5} max={30} value={variationLevel} onChange={setVariationLevel} />
          </div>
          <Button type="primary" icon={<ExperimentOutlined />} onClick={handleRunStability} loading={loading} disabled={loading}>Run stability check</Button>
          <Tooltip title={fullDataset ? 'Run on all 943 products — VERY SLOW (12 full MA runs)' : 'Run on 50 representative samples (selected by warehouse-count group, prioritizing high-cost products) — much faster'}>
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
            description="The stability check runs ±variation for 6 parameters = 12 full MA runs → can take many hours. Recommended: use the 50-sample mode for a quick survey."
          />
        )}
      </Card>

      {polling && (
        <Alert
          type="info"
          showIcon
          message={
            <span>
              Running stability check on <b>{fullDataset ? '943 products' : '50 representative samples'}</b>...
              <span className="ml-2 font-mono" style={{ color: BRAND[600] }}>{elapsed}s</span>
              <span className="ml-2 text-gray-400">({fullDataset ? 'all 943 products — may take several hours' : '50-product sample'})</span>
            </span>
          }
          description={
            cancelling
              ? 'Stopping… the job will end after completing the current computation step (may take up to a few minutes).'
              : 'Job runs in the background — you can leave the page and come back; the result is still tracked and saved in the History section below.'
          }
          action={
            <Popconfirm
              title="Stop the analysis?"
              description="The job will stop after completing the current computation step. Partial results will not be saved."
              okText="Stop" cancelText="Continue"
              onConfirm={cancelJob}
            >
              <Button danger size="small" loading={cancelling}>
                {cancelling ? 'Stopping…' : 'Stop'}
              </Button>
            </Popconfirm>
          }
        />
      )}

      {results && (
        <>
          <Row gutter={16}>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Baseline objective</p><p className="text-xl font-bold">{Number(results.baseline_objective || 0).toLocaleString('vi-VN')}</p></div></Card></Col>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Variation level</p><p className="text-xl font-bold">+/- {results.variation_pct}%</p></div></Card></Col>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Parameters analyzed</p><p className="text-xl font-bold">{bars.length}</p></div></Card></Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Card title="Radar Chart - Parameter Stability">
                <ResponsiveContainer width="100%" height={300}>
                  <RadarChart data={radarData}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="parameter" />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} />
                    <Radar name="Volatility" dataKey="volatility" stroke={SEMANTIC.warn} fill={SEMANTIC.warn} fillOpacity={0.3} />
                    <Radar name="Stability" dataKey="stability" stroke={SEMANTIC.good} fill={SEMANTIC.good} fillOpacity={0.3} />
                    <Legend />
                  </RadarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
            <Col span={12}>
              <Card title="Parameter Variation Impact">
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={bars.map(b => ({ param: b.parameter_name, variationRange: Number(b.spread) }))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="param" />
                    <YAxis />
                    <RechartsTooltip formatter={(v) => `${Number(v).toLocaleString('vi-VN')}`} />
                    <Bar dataKey="variationRange" fill={BRAND[500]} name="Variation range" />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
          </Row>

          <Card title="Parameter Stability Assessment" className="mb-6">
            <Table columns={stabilityColumns} dataSource={bars} pagination={false} size="middle" rowKey="parameter_name" />
          </Card>

          {/* Summary and Insights */}
          <Card title="Stability Insights">
            <Row gutter={16}>
              <Col span={12}>
                <div className="mb-4">
                  <h4 className="font-semibold mb-2">Most stable parameters:</h4>
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
                  <h4 className="font-semibold mb-2">Most volatile parameters:</h4>
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
              message="Recommendation on parameter stability"
              description="Parameters with high volatility should be closely monitored and may require more conservative settings or additional constraints to improve solution stability."
              type="info"
              showIcon
            />
          </Card>
        </>
      )}

      {!results && !loading && (
        <Alert
          message="Configure the stability check parameters and click Run stability check"
          description="This analysis helps identify the parameters with the greatest impact on solution stability and supports decision-making under uncertainty."
          type="info"
          showIcon
        />
      )}

      <Card title="Stability Check History" extra={<Button size="small" onClick={loadHistory}>Refresh</Button>}>
        <Table
          columns={[
            { title: 'ID', dataIndex: 'job_id', key: 'job_id', width: 60 },
            { title: 'Parameter', dataIndex: 'parameter_name', key: 'parameter_name',
              render: (t) => <span className="text-xs">{t}</span> },
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
          locale={{ emptyText: 'No stability check history yet' }}
        />
      </Card>
    </div>
  )
}

export default ParameterStability