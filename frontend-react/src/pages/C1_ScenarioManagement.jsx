import React, { useState } from 'react'
import { Card, Row, Col, Table, Tag, Button, Steps, Form, Input, InputNumber, Select, Slider, Alert, Spin, message, Modal, Tabs } from 'antd'
import {
  ExperimentOutlined, PlayCircleOutlined, SettingOutlined,
  CheckCircleOutlined, RocketOutlined, ThunderboltOutlined, PlusOutlined,
  ExclamationCircleOutlined, SyncOutlined,
} from '@ant-design/icons'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { useApi, useMutation } from '../hooks/useApi'
import { useAppContext } from '../context/AppContext'
import scenarioService from '../services/scenarioService'
import optimizationService from '../services/optimizationService'

const { Option } = Select
const { TabPane } = Tabs

const ScenarioManagement = () => {
  const [activeTab, setActiveTab] = useState('builder')
  const { setActiveScenarioId, setActiveRunId, activeScenarioId } = useAppContext()

  // Scenario Builder States
  const [currentStep, setCurrentStep] = useState(0)
  const [builderForm] = Form.useForm()

  // What-If Scenarios States
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [whatIfForm] = Form.useForm()

  // API Calls
  const { data: templates, loading: loadingTemplates } = useApi(() => scenarioService.getWhatIfTemplates())
  const { data: scenariosData, loading: loadingScenarios, execute: refreshScenarios } = useApi(() => scenarioService.getScenarios())
  const { mutate: createScenario, loading: creatingScenario } = useMutation((data) => scenarioService.createScenario(data))
  const { mutate: runOptimization, loading: running } = useMutation((data) => optimizationService.runOptimization(data))
  const { mutate: createWhatIf, loading: creating } = useMutation((data) => scenarioService.createWhatIf(data))

  const templateList = templates || []
  const scenarios = scenariosData?.scenarios || []
  const loading = loadingTemplates || creatingScenario || running || loadingScenarios

  // Scenario Builder Logic
  const steps = [
    { title: 'Select Template', description: 'Choose scenario type' },
    { title: 'Configure', description: 'Set parameters' },
    { title: 'Review', description: 'Verify settings' },
    { title: 'Execute', description: 'Run optimization' },
  ]

  const handleCreateAndRun = async () => {
    try {
      const values = await builderForm.validateFields()
      const scenario = await createScenario({
        scenario_name: values.scenario_name,
        description: values.description || '',
        created_by: values.created_by || 'user',
      })
      if (!scenario) { 
        message.error('Failed to create scenario')
        return 
      }

      setActiveScenarioId(scenario.scenario_id)
      message.success(`Scenario #${scenario.scenario_id} created`)

      const result = await runOptimization({
        scenario_id: scenario.scenario_id,
        solver: values.solver || 'cbc',
        time_limit: values.time_limit || 300,
        mip_gap: values.mip_gap || 0.01,
      })

      if (result) {
        setActiveRunId(result.run_id)
        message.success(`Optimization completed! Status: ${result.solver_status}`)
        setCurrentStep(0)
        builderForm.resetFields()
        refreshScenarios()
      }
    } catch (err) {
      if (err.errorFields) return
      message.error('Failed to create and run scenario')
    }
  }

  // What-If Scenarios Logic
  const handleCreateWhatIf = async () => {
    try {
      const values = await whatIfForm.validateFields()
      const result = await createWhatIf({
        base_scenario_id: values.base_scenario_id || activeScenarioId || 1,
        scenario_type: values.scenario_type,
        label: values.label,
        overrides: { factor: values.factor || 1.0 },
        solver: 'cbc',
        time_limit: 300,
        mip_gap: 0.01,
      })
      if (result) {
        message.success(`What-If scenario created: ${result.solver_status || 'completed'}`)
        setShowCreateModal(false)
        whatIfForm.resetFields()
        refreshScenarios()
      }
    } catch (err) {
      if (err.errorFields) return
      message.error('Failed to create what-if scenario')
    }
  }

  const scenarioColumns = [
    {
      title: 'ID',
      dataIndex: 'scenario_id',
      key: 'scenario_id',
      render: (id) => <Tag color="blue">#{id}</Tag>,
    },
    {
      title: 'Name',
      dataIndex: 'scenario_name',
      key: 'scenario_name',
    },
    {
      title: 'Type',
      dataIndex: 'scenario_type',
      key: 'scenario_type',
      render: (type) => <Tag color="green">{type || 'Base'}</Tag>,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status) => {
        const color = status === 'completed' ? 'green' : status === 'running' ? 'blue' : 'default'
        return <Tag color={color}>{status}</Tag>
      },
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date) => new Date(date).toLocaleString(),
    },
  ]

  const renderScenarioBuilder = () => (
    <div>
      <Card className="mb-6">
        <Steps current={currentStep} className="mb-6">
          {steps.map((step, index) => (
            <Steps.Step
              key={index}
              title={step.title}
              description={step.description}
              icon={
                index === 0 ? <SettingOutlined /> :
                index === 1 ? <ExperimentOutlined /> :
                index === 2 ? <CheckCircleOutlined /> :
                <RocketOutlined />
              }
            />
          ))}
        </Steps>

        <Form form={builderForm} layout="vertical">
          {currentStep === 0 && (
            <div>
              <h3>Select Scenario Template</h3>
              <Row gutter={16}>
                {templateList.map(template => (
                  <Col span={8} key={template.template_id}>
                    <Card
                      hoverable
                      onClick={() => {
                        builderForm.setFieldsValue({ template_id: template.template_id })
                        setCurrentStep(1)
                      }}
                      className="mb-4"
                    >
                      <div className="text-center">
                        <ExperimentOutlined className="text-2xl text-blue-500 mb-2" />
                        <h4>{template.template_name}</h4>
                        <p className="text-gray-500">{template.description}</p>
                      </div>
                    </Card>
                  </Col>
                ))}
              </Row>
            </div>
          )}

          {currentStep === 1 && (
            <div>
              <h3>Configure Scenario</h3>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="scenario_name"
                    label="Scenario Name"
                    rules={[{ required: true, message: 'Please enter scenario name' }]}
                  >
                    <Input placeholder="Enter scenario name" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="created_by" label="Created By">
                    <Input placeholder="Your name" defaultValue="user" />
                  </Form.Item>
                </Col>
                <Col span={24}>
                  <Form.Item name="description" label="Description">
                    <Input.TextArea placeholder="Scenario description" rows={3} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="solver" label="Solver" initialValue="cbc">
                    <Select>
                      <Option value="cbc">CBC</Option>
                      <Option value="cplex">CPLEX</Option>
                      <Option value="gurobi">Gurobi</Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="time_limit" label="Time Limit (sec)" initialValue={300}>
                    <InputNumber min={10} max={3600} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="mip_gap" label="MIP Gap" initialValue={0.01}>
                    <InputNumber min={0.001} max={0.1} step={0.001} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
            </div>
          )}

          {currentStep === 2 && (
            <div>
              <h3>Review Configuration</h3>
              <Alert
                message="Ready to Execute"
                description="Please review your configuration before running the optimization."
                type="info"
                showIcon
                className="mb-4"
              />
              {/* Display form values for review */}
            </div>
          )}

          {currentStep === 3 && (
            <div>
              <h3>Execute Optimization</h3>
              <div className="text-center py-8">
                <Button
                  type="primary"
                  size="large"
                  icon={<PlayCircleOutlined />}
                  onClick={handleCreateAndRun}
                  loading={loading}
                >
                  Create & Run Scenario
                </Button>
              </div>
            </div>
          )}
        </Form>

        <div className="mt-6 text-center">
          {currentStep > 0 && (
            <Button onClick={() => setCurrentStep(currentStep - 1)} className="mr-4">
              Previous
            </Button>
          )}
          {currentStep < steps.length - 1 && (
            <Button type="primary" onClick={() => setCurrentStep(currentStep + 1)}>
              Next
            </Button>
          )}
        </div>
      </Card>
    </div>
  )

  const renderWhatIfScenarios = () => (
    <div>
      <Card
        title={<><ThunderboltOutlined /> What-If Scenarios</>}
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setShowCreateModal(true)}
          >
            Create What-If
          </Button>
        }
        className="mb-6"
      >
        <Table
          columns={scenarioColumns}
          dataSource={scenarios}
          rowKey="scenario_id"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      </Card>

      <Modal
        title="Create What-If Scenario"
        open={showCreateModal}
        onOk={handleCreateWhatIf}
        onCancel={() => {
          setShowCreateModal(false)
          whatIfForm.resetFields()
        }}
        confirmLoading={creating}
      >
        <Form form={whatIfForm} layout="vertical">
          <Form.Item name="base_scenario_id" label="Base Scenario ID" initialValue={activeScenarioId || 1}>
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            name="scenario_type"
            label="Scenario Type"
            rules={[{ required: true, message: 'Please select scenario type' }]}
          >
            <Select placeholder="Select scenario type">
              {templateList.map(template => (
                <Option key={template.template_id} value={template.template_name}>
                  {template.template_name}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="label"
            label="Label"
            rules={[{ required: true, message: 'Please enter label' }]}
          >
            <Input placeholder="What-if scenario label" />
          </Form.Item>
          <Form.Item name="factor" label="Adjustment Factor" initialValue={1.0}>
            <Slider
              min={0.1}
              max={2.0}
              step={0.1}
              marks={{
                0.5: '0.5x',
                1.0: '1.0x',
                1.5: '1.5x',
                2.0: '2.0x'
              }}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Scenario Management</h1>
        <p className="text-gray-600">Build scenarios and explore what-if alternatives</p>
      </div>

      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        <TabPane 
          tab={<><ExperimentOutlined />Scenario Builder</>} 
          key="builder"
        >
          {renderScenarioBuilder()}
        </TabPane>
        <TabPane 
          tab={<><ThunderboltOutlined />What-If Scenarios</>} 
          key="whatif"
        >
          {renderWhatIfScenarios()}
        </TabPane>
      </Tabs>
    </div>
  )
}

export default ScenarioManagement