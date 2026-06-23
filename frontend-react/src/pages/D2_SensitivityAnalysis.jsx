import React, { useState, useEffect, useRef } from 'react'
import { Card, Row, Col, Table, Tag, Button, Select, InputNumber, Alert, message, Radio, Switch, Tooltip } from 'antd'
import {
  LineChartOutlined, BarChartOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Legend, ReferenceLine } from 'recharts'
import { useAppContext } from '../context/AppContext'
import sensitivityService from '../services/sensitivityService'

const { Option } = Select

const PARAMETERS = ['DI', 'CAP', 'Cb', 'Co', 'Cs', 'Cp', 'U', 'L', 'BI', 'CP']

const usePollJob = (onComplete) => {
  const [jobId, setJobId] = useState(null)
  const [polling, setPolling] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const intervalRef = useRef(null)
  const timerRef = useRef(null)

  const startPolling = (id) => {
    setJobId(id)
    setPolling(true)
    setElapsed(0)
  }

  useEffect(() => {
    if (!polling || !jobId) return
    timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000)
    intervalRef.current = setInterval(async () => {
      try {
        const res = await sensitivityService.pollJob(jobId)
        if (res.status === 'completed') {
          clearInterval(intervalRef.current)
          clearInterval(timerRef.current)
          setPolling(false)
          onComplete(res.result)
        } else if (res.status === 'failed') {
          clearInterval(intervalRef.current)
          clearInterval(timerRef.current)
          setPolling(false)
          message.error('Phân tích thất bại: ' + (res.error || 'Unknown error'))
        }
      } catch (e) {
        clearInterval(intervalRef.current)
        clearInterval(timerRef.current)
        setPolling(false)
      }
    }, 4000)
    return () => {
      clearInterval(intervalRef.current)
      clearInterval(timerRef.current)
    }
  }, [polling, jobId])

  return { polling, elapsed, startPolling }
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

  const { polling: pollingOAT, elapsed: elapsedOAT, startPolling: startOAT } = usePollJob((result) => {
    // OAT result stored as array of points in DB
    setOatResult(Array.isArray(result) ? { points: result, parameter_name: selectedParam, baseline_objective: result[0]?.baseline_objective || 0, elasticity: null } : result)
    message.success('Phân tích OAT hoàn thành!')
  })

  const { polling: pollingTornado, elapsed: elapsedTornado, startPolling: startTornado } = usePollJob((result) => {
    // Tornado result stored as {baseline_objective, variation_pct, bars}
    setTornadoResult(result)
    message.success('Phân tích Tornado hoàn thành!')
  })

  const loading = submitting || pollingOAT || pollingTornado

  const handleRunOAT = async () => {
    setSubmitting(true)
    try {
      const res = await sensitivityService.runSensitivity({
        scenario_id: scenarioId,
        parameter_name: selectedParam,
        variation_percentages: [-20, -10, -5, 5, 10, 20],
        sample_size: fullDataset ? null : 50,
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
        parameters: PARAMETERS.slice(0, 6),
        variation_pct: variationPct,
        sample_size: fullDataset ? null : 50,
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
      <div>
        <h1 className="text-3xl font-bold text-primary-700 mb-2"><LineChartOutlined className="mr-3" />D2. Phân Tích Độ Nhạy Tham Số</h1>
        <p className="text-gray-600">Phân tích độ nhạy của tham số và biểu đồ tornado</p>
      </div>

      <Card>
        <div className="flex items-center gap-4 flex-wrap">
          <div><span className="mr-2">ID kịch bản:</span><InputNumber min={1} value={scenarioId} onChange={setScenarioId} /></div>
          <Radio.Group value={analysisType} onChange={(e) => setAnalysisType(e.target.value)} buttonStyle="solid">
            <Radio.Button value="oat">Từng tham số</Radio.Button>
            <Radio.Button value="tornado">Tornado</Radio.Button>
          </Radio.Group>
          {analysisType === 'oat' && (
            <>
              <Select value={selectedParam} onChange={setSelectedParam} style={{ width: 120 }}>
                {PARAMETERS.map(p => <Option key={p} value={p}>{p}</Option>)}
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
          <Tooltip title={fullDataset ? 'Chạy toàn bộ 943 SP (~14 phút)' : 'Chạy 50 mẫu đại diện (~1 phút)'}>
            <div className="flex items-center gap-2 ml-2">
              <span className="text-xs text-gray-500">{fullDataset ? '943 SP' : '50 mẫu'}</span>
              <Switch size="small" checked={fullDataset} onChange={setFullDataset} />
              <span className="text-xs text-gray-500">Đầy đủ</span>
            </div>
          </Tooltip>
        </div>
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
              <span className="ml-2 text-gray-400">(ước tính {fullDataset ? '~14 phút' : '~1 phút'})</span>
            </span>
          }
          description="Kết quả sẽ tự động hiển thị khi hoàn thành. Vui lòng không đóng trang."
        />
      )}

      {analysisType === 'oat' && oatResult && (
        <>
          <Row gutter={16}>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Tham số</p><Tag color="blue">{oatResult.parameter_name}</Tag></div></Card></Col>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Mục tiêu cơ sở</p><p className="text-xl font-bold">{Number(oatResult.baseline_objective || 0).toLocaleString('vi-VN')}</p></div></Card></Col>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Độ co giãn</p><p className="text-xl font-bold">{Number(oatResult.elasticity || 0).toFixed(3)}</p></div></Card></Col>
          </Row>
          <Card title={`Độ nhạy: ${oatResult.parameter_name}`}>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={oatChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="variation" />
                <YAxis />
                <RechartsTooltip formatter={(v) => [`${Number(v).toLocaleString('vi-VN')}`]} />
                <ReferenceLine y={Number(oatResult.baseline_objective)} stroke="#f5222d" strokeDasharray="3 3" label="Cơ sở" />
                <Line type="monotone" dataKey="objective" stroke="#1890ff" strokeWidth={2} name="Giá trị mục tiêu" />
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
                <Bar dataKey="low" fill="#52c41a" name="Thấp (-)" />
                <Bar dataKey="high" fill="#f5222d" name="Cao (+)" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card title="Xếp hạng độ nhạy tham số">
            <Table
              columns={[
                { title: 'Tham số', dataIndex: 'parameter_name', key: 'parameter_name', render: (t) => <Tag color="blue">{t}</Tag> },
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
    </div>
  )
}

export default SensitivityAnalysis
