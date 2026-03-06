import React, { useState } from 'react'
import { Card, Row, Col, Table, Tag, Button, Select, InputNumber, Alert, Spin, Slider, message, Progress } from 'antd'
import {
  BarChartOutlined, ThunderboltOutlined, ExperimentOutlined,
} from '@ant-design/icons'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, LineChart, Line } from 'recharts'
import { useMutation } from '../hooks/useApi'
import { useAppContext } from '../context/AppContext'
import sensitivityService from '../services/sensitivityService'

const { Option } = Select

const ParameterStability = () => {
  const { activeScenarioId } = useAppContext()
  const [scenarioId, setScenarioId] = useState(activeScenarioId || 1)
  const [variationLevel, setVariationLevel] = useState(15)
  const [results, setResults] = useState(null)

  const { mutate: runStabilityTest, loading } = useMutation(async (data) => {
    const result = await sensitivityService.runTornado(data)
    setResults(result)
    return result
  })

  const handleRunStability = () => {
    runStabilityTest({
      scenario_id: scenarioId,
      parameters: ['DI', 'CAP', 'Cb', 'Co', 'Cs', 'Cp'],
      variation_pct: variationLevel,
    })
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
    { title: 'Parameter', dataIndex: 'parameter_name', key: 'parameter_name', render: (t) => <Tag color="blue">{t}</Tag> },
    { title: `Value at -${variationLevel}%`, dataIndex: 'low_value', key: 'low_value', render: (v) => `$${Number(v).toLocaleString()}` },
    { title: `Value at +${variationLevel}%`, dataIndex: 'high_value', key: 'high_value', render: (v) => `$${Number(v).toLocaleString()}` },
    { title: 'Variation Range', dataIndex: 'spread', key: 'spread', render: (v) => <span className="font-bold text-orange-600">${Number(v).toLocaleString()}</span> },
    {
      title: 'Stability Index', key: 'stability',
      render: (_, record) => {
        const volatility = Math.abs(Number(record.spread || 0)) / Math.max(1, Number(results?.baseline_objective || 1)) * 100
        const stability = Math.max(0, 100 - volatility)
        return <Progress percent={Math.round(stability)} size="small" status={stability > 80 ? 'success' : stability > 60 ? 'normal' : 'exception'} />
      },
    },
    {
      title: 'Stability Rating', key: 'rating',
      render: (_, record) => {
        const volatility = Math.abs(Number(record.spread || 0)) / Math.max(1, Number(results?.baseline_objective || 1)) * 100
        if (volatility < 5) return <Tag color="green">Very Stable</Tag>
        if (volatility < 15) return <Tag color="cyan">Stable</Tag>
        if (volatility < 25) return <Tag color="orange">Moderate</Tag>
        return <Tag color="red">Volatile</Tag>
      },
    },
  ]

  return (
    <Spin spinning={loading}>
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-primary-700 mb-2"><BarChartOutlined className="mr-3" />D3. Parameter Stability Analysis</h1>
        <p className="text-gray-600">Analyze the stability of optimization solutions under parameter variations</p>
      </div>

      <Card>
        <div className="flex items-center gap-4 flex-wrap">
          <div><span className="mr-2">Scenario ID:</span><InputNumber min={1} value={scenarioId} onChange={setScenarioId} /></div>
          <div style={{ width: 200 }}>
            <span className="mr-2">Variation Level: {variationLevel}%</span>
            <Slider min={5} max={30} value={variationLevel} onChange={setVariationLevel} />
          </div>
          <Button type="primary" icon={<ExperimentOutlined />} onClick={handleRunStability} loading={loading}>Run Stability Test</Button>
        </div>
      </Card>

      {results && (
        <>
          <Row gutter={16}>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Baseline Objective</p><p className="text-xl font-bold">${Number(results.baseline_objective || 0).toLocaleString()}</p></div></Card></Col>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Variation Level</p><p className="text-xl font-bold">+/- {results.variation_pct}%</p></div></Card></Col>
            <Col span={8}><Card size="small"><div className="text-center"><p className="text-sm text-gray-500">Parameters Analyzed</p><p className="text-xl font-bold">{bars.length}</p></div></Card></Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Card title="Parameter Stability Radar">
                <ResponsiveContainer width="100%" height={300}>
                  <RadarChart data={radarData}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="parameter" />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} />
                    <Radar name="Volatility" dataKey="volatility" stroke="#fa8c16" fill="#fa8c16" fillOpacity={0.3} />
                    <Radar name="Stability" dataKey="stability" stroke="#52c41a" fill="#52c41a" fillOpacity={0.3} />
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
                    <Tooltip formatter={(v) => `$${Number(v).toLocaleString()}`} />
                    <Bar dataKey="variationRange" fill="#1890ff" name="Variation Range" />
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
                  <h4 className="font-semibold mb-2">Most Stable Parameters:</h4>
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
                  <h4 className="font-semibold mb-2">Most Volatile Parameters:</h4>
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
              message="Parameter Stability Recommendation" 
              description="Parameters with high volatility require careful monitoring and may benefit from more conservative settings or additional constraints to improve solution stability."
              type="info" 
              showIcon 
            />
          </Card>
        </>
      )}

      {!results && !loading && (
        <Alert 
          message="Configure stability test parameters above and click Run to analyze parameter stability" 
          description="This analysis helps identify which parameters have the most significant impact on solution stability and guides decision-making under uncertainty."
          type="info" 
          showIcon 
        />
      )}
    </div>
    </Spin>
  )
}

export default ParameterStability