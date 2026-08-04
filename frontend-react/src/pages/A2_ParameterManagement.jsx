import React, { useState } from 'react'
import { Card, Row, Col, Table, Tag, Button, InputNumber, Alert, Spin, message, Tabs, Modal, Form, Input, Timeline } from 'antd'
import {
  SettingOutlined,
  DollarOutlined,
  EditOutlined,
  SaveOutlined,
  ReloadOutlined,
  BranchesOutlined,
  PlusOutlined,
  CheckCircleOutlined,
  HistoryOutlined,
  TagOutlined,
  SyncOutlined,
} from '@ant-design/icons'
import { useApi, useMutation } from '../hooks/useApi'
import dataService from '../services/dataService'
import PageHeader from '../components/PageHeader'

const { TabPane } = Tabs

const ParameterManagement = () => {
  const [editMode, setEditMode] = useState(false)
  const [editedParams, setEditedParams] = useState({})
  const [activeTab, setActiveTab] = useState('parameters')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [versionRuns, setVersionRuns] = useState({})  // {version_id: [runs]}
  const [form] = Form.useForm()

  const loadVersionRuns = async (versionId) => {
    try {
      const res = await dataService.getRunsForVersion(versionId)
      setVersionRuns((prev) => ({ ...prev, [versionId]: res?.runs || [] }))
    } catch (e) { /* ignore */ }
  }

  const { data: overview, loading: loadingOverview } = useApi(() => dataService.getOverview(), [], { cacheKey: 'data-overview' })
  const { data: paramsData, loading: loadingParams, execute: refreshParams } = useApi(() => dataService.getParameters(), [], { cacheKey: 'model-parameters' })
  const { data: datasetsData, loading: loadingDatasets, execute: refreshDatasets } = useApi(() => dataService.getDatasets(), [], { cacheKey: 'datasets' })
  const { data: algoData, loading: loadingAlgo } = useApi(() => dataService.getAlgorithmParameters(), [], { cacheKey: 'algorithm-parameters' })
  const { data: costData, loading: loadingCost } = useApi(() => dataService.getCostParameters(), [], { cacheKey: 'cost-parameters' })
  const { mutate: saveParam, loading: saving } = useMutation((name, value) => dataService.updateParameter(name, value))
  const { mutate: createDataset, loading: creating } = useMutation((data) => dataService.createDataset(data))

  // Ensure parameters is always a valid array
  const parameters = Array.isArray(paramsData?.parameters) ? paramsData.parameters : []
  const algoParams = Array.isArray(algoData?.parameters) ? algoData.parameters : []
  const costParams = Array.isArray(costData?.parameters) ? costData.parameters : []

  const datasets = datasetsData?.datasets || []
  const loading = loadingOverview || loadingParams || loadingDatasets || loadingAlgo || loadingCost

  const handleEditChange = (paramName, value) => {
    setEditedParams(prev => ({ ...prev, [paramName]: value }))
  }

  const handleSave = async () => {
    const entries = Object.entries(editedParams)
    let success = true
    for (const [name, value] of entries) {
      const result = await saveParam(name, value)
      if (!result) { success = false; break }
    }
    if (success) {
      message.success('Parameters saved successfully')
      setEditMode(false)
      setEditedParams({})
      refreshParams()
    } else {
      message.error('Failed to save some parameters')
    }
  }

  const handleCancel = () => {
    setEditMode(false)
    setEditedParams({})
  }

  const handleCreateDataset = async () => {
    try {
      const values = await form.validateFields()
      const result = await createDataset(values)
      if (result) {
        message.success('Data version created successfully')
        setShowCreateModal(false)
        form.resetFields()
        refreshDatasets()
      }
    } catch (err) {
      if (err.errorFields) return
      message.error('Failed to create data version')
    }
  }

  const paramColumns = [
    {
      title: 'Parameter',
      dataIndex: 'param_name',
      key: 'param_name',
      render: (text) => <span className="font-semibold text-gray-800">{text}</span>,
    },
    {
      title: 'Current Value',
      dataIndex: 'param_value',
      key: 'param_value',
      render: (value, record) => editMode
        ? (
          <InputNumber
            value={editedParams[record.param_name] !== undefined ? editedParams[record.param_name] : value}
            step={0.01}
            onChange={(val) => handleEditChange(record.param_name, val)}
          />
        )
        : Number(value).toLocaleString(),
    },
    {
      title: 'Description',
      dataIndex: 'param_description',
      key: 'param_description',
      render: (text) => <span className="text-gray-600 text-sm">{text}</span>,
    },
    {
      title: 'Status',
      key: 'status',
      render: (_, record) => {
        return editedParams[record.param_name] !== undefined
          ? <Tag color="orange">Edited</Tag>
          : <Tag color="green">Saved</Tag>
      },
    },
  ]

  // Algorithm parameter table columns (read-only)
  const ALGO_GROUP_LABEL = { GA: 'Main Search', ALNS: 'Local Refinement', 'Stopping': 'Stopping Condition' }
  const algoColumns = [
    {
      title: 'Parameter', dataIndex: 'name', key: 'name',
      render: (text) => <span className="font-semibold text-gray-800">{text}</span>,
    },
    {
      title: 'Symbol', dataIndex: 'symbol', key: 'symbol', width: 140,
      render: (t) => <code className="text-primary-700 bg-gray-100 px-1.5 py-0.5 rounded text-xs">{t}</code>,
    },
    {
      title: 'Value', dataIndex: 'value', key: 'value', width: 100, align: 'right',
      render: (v) => <span className="font-semibold">{Number(v).toLocaleString('en-US', { maximumFractionDigits: 3 })}</span>,
    },
    {
      title: 'Group', dataIndex: 'group', key: 'group', width: 130,
      render: (g) => {
        const color = g === 'GA' ? 'blue' : g === 'ALNS' ? 'purple' : g === 'Stopping' ? 'red' : 'default'
        return <Tag color={color}>{ALGO_GROUP_LABEL[g] || g}</Tag>
      },
    },
    { title: 'Description', dataIndex: 'description', key: 'description',
      render: (t) => <span className="text-gray-600 text-sm">{t}</span> },
  ]

  // Cost/operational parameter table columns (read-only)
  const costColumns = [
    { title: 'Parameter', dataIndex: 'name', key: 'name',
      render: (t) => <span className="font-semibold text-gray-800">{t}</span> },
    { title: 'Symbol', dataIndex: 'symbol', key: 'symbol', width: 110,
      render: (t) => <code className="text-primary-700 bg-gray-100 px-1.5 py-0.5 rounded text-xs">{t}</code> },
    { title: 'Value', dataIndex: 'value', key: 'value', width: 90, align: 'right',
      render: (v) => <span className="font-semibold">{v}</span> },
    { title: 'Unit', dataIndex: 'unit', key: 'unit', width: 100,
      render: (t) => <span className="text-gray-500 text-sm">{t}</span> },
    { title: 'Group', dataIndex: 'group', key: 'group', width: 110,
      render: (g) => <Tag color={g === 'Cost' ? 'volcano' : 'cyan'}>{g}</Tag> },
    { title: 'Description', dataIndex: 'description', key: 'description',
      render: (t) => <span className="text-gray-600 text-sm">{t}</span> },
  ]

  // Dataset version columns
  const datasetColumns = [
              { title: 'ID', dataIndex: 'version_id', key: 'version_id', width: 60 },
    {
      title: 'Version Name',
      dataIndex: 'version_name',
      key: 'version_name',
      render: (text) => <span className="font-semibold">{text}</span>,
    },
    { title: 'Description', dataIndex: 'description', key: 'description' },
    {
      title: 'Created By',
      dataIndex: 'created_by',
      key: 'created_by',
      render: (text) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: 'Created At',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date) => new Date(date).toLocaleString(),
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active) => active ? <Tag color="green">Active</Tag> : <Tag color="default">Inactive</Tag>,
    },
  ]

  return (
    <Spin spinning={loading || saving || creating}>
    <div className="space-y-6">
      <PageHeader
        icon={<SettingOutlined />}
        title="A2. Model Parameters"
        subtitle="Manage model parameters and data versions"
      />

      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        <TabPane tab={<><SettingOutlined />Parameters</>} key="parameters">
          {/* Parameters Content */}
          <div className="space-y-6">
            {/* Edit Mode Alert */}
            {editMode && (
              <Alert
                message="Edit Mode Active"
                description="You are editing parameters. Save your changes, or they will be lost."
                type="warning"
                showIcon
              />
            )}

            {/* Optimization algorithm parameters (read from config, calibrated through experiments) */}
            <Card
              title={
                <span className="text-lg font-semibold flex items-center">
                  <SyncOutlined className="mr-2" />
                  Optimization Algorithm Parameters
                </span>
              }
              extra={<Tag color="blue">Calibrated configuration</Tag>}
            >
              <Alert
                type="info"
                showIcon
                className="mb-4"
                message="Optimal Operating Parameter Set"
                description="These parameters control how the system searches for the best allocation solution. The current value set has been tested and calibrated to balance solution quality against runtime. Detailed values are shown in the table below."
              />
              <Table
                columns={algoColumns}
                dataSource={algoParams}
                pagination={false}
                size="middle"
                rowKey="symbol"
              />
            </Card>

            {/* Cost & operational parameters (Table 3.3 — read-only) */}
            <Card
              title={
                <span className="text-lg font-semibold flex items-center">
                  <DollarOutlined className="mr-2" />
                  Cost & Operational Parameters
                </span>
              }
            >
              <Alert
                type="warning"
                showIcon
                className="mb-4"
                message="Baseline Operational Data Values (display only)"
                description="These are the company's actual cost and transportation parameters. To change them and evaluate their impact on optimization cost, use the Scenario Analysis (C1. What-If) or Sensitivity Analysis (D1) features."
              />
              <Table
                columns={costColumns}
                dataSource={costParams}
                pagination={false}
                size="middle"
                rowKey="symbol"
              />
            </Card>

            {/* Model parameters (technical constants stored in DB) */}
            <Card
              title={
                <span className="text-lg font-semibold flex items-center">
                  <DollarOutlined className="mr-2" />
                  Model Parameters
                </span>
              }
              extra={
                !editMode ? (
                  <Button type="primary" icon={<EditOutlined />} onClick={() => setEditMode(true)}>
                    Edit
                  </Button>
                ) : (
                  <div className="flex gap-2">
                    <Button icon={<ReloadOutlined />} onClick={handleCancel}>Cancel</Button>
                    <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}
                      disabled={Object.keys(editedParams).length === 0}>Save Changes</Button>
                  </div>
                )
              }
            >
              <Table
                columns={paramColumns}
                dataSource={parameters}
                pagination={false}
                size="middle"
                rowKey="param_name"
                locale={{ emptyText: 'No custom model parameters yet' }}
              />
            </Card>
          </div>
        </TabPane>

        <TabPane tab={<><BranchesOutlined />Version Management</>} key="versions">
          {/* Version Control Content */}
          <div className="space-y-6">
            <Alert
              type="info"
              showIcon
              message="What are data versions used for?"
              description="Each optimization run is tied to a data version (a snapshot of the input dataset at run time, with a checksum). This makes it possible to trace which run used which dataset — supporting the rolling horizon mechanism as data is updated period by period. Click the ▸ marker on a version to see the runs that used it."
            />
            <Card
              title={<><BranchesOutlined /> Data Version Management</>}
              extra={
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => setShowCreateModal(true)}
                >
                  Create Version
                </Button>
              }
            >
              <Table
                columns={datasetColumns}
                dataSource={datasets}
                rowKey="version_id"
                pagination={{ pageSize: 10 }}
                expandable={{
                  onExpand: (expanded, record) => {
                    if (expanded && !versionRuns[record.version_id]) loadVersionRuns(record.version_id)
                  },
                  expandedRowRender: (record) => {
                    const runs = versionRuns[record.version_id]
                    if (!runs) return <span className="text-gray-400">Loading...</span>
                    if (runs.length === 0) return <span className="text-gray-400">No runs have used this version yet.</span>
                    return (
                      <Table
                        size="small"
                        pagination={false}
                        rowKey="run_id"
                        dataSource={runs}
                        columns={[
                          { title: 'Run', dataIndex: 'run_id', render: (v) => <strong>#{v}</strong> },
                          { title: 'Time', dataIndex: 'run_time', render: (v) => v ? String(v).slice(0, 16) : '—' },
                          { title: 'Status', dataIndex: 'solver_status', render: (v) => <Tag color={/optimal/i.test(v) ? 'green' : /error/i.test(v) ? 'red' : 'orange'}>{v}</Tag> },
                          { title: 'Optimal Cost', dataIndex: 'objective_value', align: 'right', render: (v) => Number(v).toLocaleString('en-US') },
                        ]}
                      />
                    )
                  },
                }}
              />
            </Card>

            {/* Version History Timeline */}
            <Card title={<><HistoryOutlined /> Version History</>}>
              <Timeline>
                {datasets.slice(0, 5).map(dataset => (
                  <Timeline.Item
                    key={dataset.version_id}
                    color={dataset.is_active ? 'green' : 'gray'}
                    dot={dataset.is_active ? <CheckCircleOutlined /> : <TagOutlined />}
                  >
                    <div>
                      <div className="font-semibold">{dataset.version_name}</div>
                      <div className="text-gray-500 text-sm">{dataset.description}</div>
                      <div className="text-gray-400 text-xs">
                        {new Date(dataset.created_at).toLocaleString()} by {dataset.created_by}
                      </div>
                    </div>
                  </Timeline.Item>
                ))}
              </Timeline>
            </Card>
          </div>
        </TabPane>
      </Tabs>

      {/* Create Dataset Modal */}
      <Modal
        title="Create Data Version"
        open={showCreateModal}
        onOk={handleCreateDataset}
        onCancel={() => {
          setShowCreateModal(false)
          form.resetFields()
        }}
        confirmLoading={creating}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="version_name"
            label="Version Name"
            rules={[{ required: true, message: 'Please enter a version name' }]}
          >
            <Input placeholder="e.g.: v1.0.0, baseline, scenario-A" />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea
              placeholder="Describe the changes in this version"
              rows={3}
            />
          </Form.Item>
          <Form.Item name="created_by" label="Created By" initialValue="user">
            <Input placeholder="Your name" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
    </Spin>
  )
}

export default ParameterManagement
