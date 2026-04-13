import React, { useState } from 'react'
import { Card, Row, Col, Table, Tag, Button, InputNumber, Switch, Alert, Spin, message, Tabs, Modal, Form, Input, Timeline } from 'antd'
import {
  SettingOutlined,
  DollarOutlined,
  EditOutlined,
  SaveOutlined,
  ReloadOutlined,
  LockOutlined,
  BranchesOutlined,
  PlusOutlined,
  CheckCircleOutlined,
  HistoryOutlined,
  TagOutlined,
  SyncOutlined,
} from '@ant-design/icons'
import { useApi, useMutation } from '../hooks/useApi'
import dataService from '../services/dataService'

const { TabPane } = Tabs

const ParameterManagement = () => {
  const [editMode, setEditMode] = useState(false)
  const [hasPermission, setHasPermission] = useState(true)
  const [editedParams, setEditedParams] = useState({})
  const [activeTab, setActiveTab] = useState('parameters')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [form] = Form.useForm()

  const { data: overview, loading: loadingOverview } = useApi(() => dataService.getOverview())
  const { data: paramsData, loading: loadingParams, execute: refreshParams } = useApi(() => dataService.getParameters())
  const { data: datasetsData, loading: loadingDatasets, execute: refreshDatasets } = useApi(() => dataService.getDatasets())
  const { mutate: saveParam, loading: saving } = useMutation((name, value) => dataService.updateParameter(name, value))
  const { mutate: createDataset, loading: creating } = useMutation((data) => dataService.createDataset(data))

  // Ensure parameters is always a valid array
  const parameters = Array.isArray(paramsData?.parameters) ? paramsData.parameters : []
  const datasets = datasetsData?.datasets || []
  const loading = loadingOverview || loadingParams || loadingDatasets

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
        message.success('Dataset version created successfully')
        setShowCreateModal(false)
        form.resetFields()
        refreshDatasets()
      }
    } catch (err) {
      if (err.errorFields) return
      message.error('Failed to create dataset version')
    }
  }

  const paramColumns = [
    {
      title: 'Parameter',
      dataIndex: 'param_name',
      key: 'param_name',
      render: (text) => <span className="font-semibold">{text}</span>,
    },
    {
      title: 'Current Value',
      dataIndex: 'param_value',
      key: 'param_value',
      render: (value, record) => editMode ? (
        <InputNumber
          value={editedParams[record.param_name] !== undefined ? editedParams[record.param_name] : value}
          step={0.01}
          onChange={(val) => handleEditChange(record.param_name, val)}
        />
      ) : (value !== null ? Number(value).toLocaleString() : 'N/A'),
    },
    { title: 'Description', dataIndex: 'param_description', key: 'param_description' },
    {
      title: 'Status',
      key: 'status',
      render: (_, record) => editedParams[record.param_name] !== undefined
        ? <Tag color="orange">Modified</Tag>
        : <Tag color="green">Saved</Tag>,
    },
  ]

  // Overview summary
  const numProducts = overview?.num_products || 0
  const numWarehouses = overview?.num_warehouses || 0
  const numPeriods = overview?.num_periods || 0

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
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold mb-2">
          <SettingOutlined className="mr-3" />
          A2. Tham Số Mô Hình
        </h1>
        <p className="text-gray-600">Configure model parameters and manage dataset versions</p>
      </div>

      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        <TabPane tab={<><SettingOutlined />Parameters</>} key="parameters">
          {/* Parameters Content */}
          <div className="space-y-6">
            {/* Header Controls */}
            <div className="flex justify-between items-start">
              <div className="flex gap-2">
                {hasPermission ? (
                  <>
                    {!editMode ? (
                      <Button
                        type="primary"
                        icon={<EditOutlined />}
                        onClick={() => setEditMode(true)}
                      >
                        Edit Parameters
                      </Button>
                    ) : (
                      <>
                        <Button
                          icon={<ReloadOutlined />}
                          onClick={handleCancel}
                        >
                          Cancel
                        </Button>
                        <Button
                          type="primary" 
                          icon={<SaveOutlined />}
                          onClick={handleSave}
                          disabled={Object.keys(editedParams).length === 0}
                        >
                          Save Changes
                        </Button>
                      </>
                    )}
                  </>
                ) : (
                  <Button disabled icon={<LockOutlined />}>
                    View Only
                  </Button>
                )}
              </div>
            </div>

            {/* Edit Mode Alert */}
            {editMode && (
              <Alert
                message="Edit Mode Active"
                description="You are currently editing parameters. Save changes or they will be lost."
                type="warning"
                showIcon
              />
            )}

            {/* Role Control */}
            <Card size="small" style={{ borderLeft: '4px solid #c5a572' }}>
              <Row gutter={16}>
                <Col span={12}>
                  <span className="text-sm font-medium">Role:</span>
                  <Tag color="blue" className="ml-2">Administrator</Tag>
                </Col>
                <Col span={12}>
                  <span className="text-sm font-medium">Edit Permission:</span>
                  <Switch
                    checked={hasPermission}
                    onChange={setHasPermission}
                    className="ml-2"
                    size="small"
                  />
                </Col>
              </Row>
            </Card>

            {/* Model Parameters */}
            <Card
              title={
                <span className="text-lg font-semibold flex items-center">
                  <DollarOutlined className="mr-2" />
                  Model Parameters
                </span>
              }
            >
              <Table
                columns={paramColumns}
                dataSource={parameters}
                pagination={false}
                size="middle"
                rowKey="param_name"
              />
            </Card>

            {/* Quick Summary */}
            <Row gutter={16}>
              <Col span={8}>
                <Card size="small">
                  <div className="text-center">
                    <h3 className="text-lg font-semibold text-primary-700">Products</h3>
                    <p className="text-2xl font-bold text-green-600">{numProducts}</p>
                  </div>
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small">
                  <div className="text-center">
                    <h3 className="text-lg font-semibold text-primary-700">Warehouses</h3>
                    <p className="text-2xl font-bold text-blue-600">{numWarehouses}</p>
                  </div>
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small">
                  <div className="text-center">
                    <h3 className="text-lg font-semibold text-primary-700">Time Periods</h3>
                    <p className="text-2xl font-bold text-purple-600">{numPeriods}</p>
                  </div>
                </Card>
              </Col>
            </Row>
          </div>
        </TabPane>

        <TabPane tab={<><BranchesOutlined />Version Control</>} key="versions">
          {/* Version Control Content */}
          <div className="space-y-6">
            <Card
              title={<><BranchesOutlined /> Dataset Version Control</>}
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
        title="Create Dataset Version"
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
            rules={[{ required: true, message: 'Please enter version name' }]}
          >
            <Input placeholder="e.g., v1.0.0, baseline, scenario-A" />
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
