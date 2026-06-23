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
      title: 'Tham Số',
      dataIndex: 'param_name',
      key: 'param_name',
      render: (text) => <span className="font-semibold text-gray-800">{text}</span>,
    },
    {
      title: 'Giá Trị Hiện Tại',
      dataIndex: 'param_value',
      key: 'param_value',
      render: (value) => editMode 
        ? <InputNumber value={value} step={0.01} onChange={(val) => {}} />
        : Number(value).toLocaleString(),
    },
    {
      title: 'Mô Tả',
      dataIndex: 'param_description',
      key: 'param_description',
      render: (text) => <span className="text-gray-600 text-sm">{text}</span>,
    },
    {
      title: 'Trạng Thái',
      key: 'status',
      render: (_, record) => {
        return editedParams[record.param_name] !== undefined
          ? <Tag color="orange">Đã Sửa</Tag>
          : <Tag color="green">Đã Lưu</Tag>
      },
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
      title: 'Tên Phiên Bản',
      dataIndex: 'version_name',
      key: 'version_name',
      render: (text) => <span className="font-semibold">{text}</span>,
    },
    { title: 'Mô Tả', dataIndex: 'description', key: 'description' },
    {
      title: 'Tạo Bởi',
      dataIndex: 'created_by',
      key: 'created_by',
      render: (text) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: 'Ngày Tạo',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date) => new Date(date).toLocaleString(),
    },
    {
      title: 'Trạng Thái',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active) => active ? <Tag color="green">Hoạt Động</Tag> : <Tag color="default">Bất Hoạt Động</Tag>,
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
        <p className="text-gray-600">Quản lý tham số mô hình và phiên bản dữ liệu</p>
      </div>

      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        <TabPane tab={<><SettingOutlined />Tham Số</>} key="parameters">
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
                        Chỉnh Sửa Tham Số
                      </Button>
                    ) : (
                      <>
                        <Button
                          icon={<ReloadOutlined />}
                          onClick={handleCancel}
                        >
                          Hủy Bỏ
                        </Button>
                        <Button
                          type="primary" 
                          icon={<SaveOutlined />}
                          onClick={handleSave}
                          disabled={Object.keys(editedParams).length === 0}
                        >
                          Lưu Thay Đổi
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
                message="Chế Độ Chỉnh Sửa Đang Hoạt Động"
                description="Bạn đang chỉnh sửa tham số. Hãy lưu hoặc các thay đổi sẽ bị mất."
                type="warning"
                showIcon
              />
            )}

            {/* Role Control */}
            <Card size="small" style={{ borderLeft: '4px solid #c5a572' }}>
              <Row gutter={16}>
                <Col span={12}>
                  <span className="text-sm font-medium">Vai trò: </span>
                  <Tag color="blue" className="ml-2">Quản Trị Viên</Tag>
                </Col>
                <Col span={12}>
                  <span className="text-sm font-medium">Quyền Chỉnh Sửa:</span>
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
                  Tham Số Mô Hình
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
                    <h3 className="text-lg font-semibold text-primary-700">Sản Phẩm</h3>
                    <p className="text-2xl font-bold text-green-600">{numProducts}</p>
                  </div>
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small">
                  <div className="text-center">
                    <h3 className="text-lg font-semibold text-primary-700">Kho Hàng</h3>
                    <p className="text-2xl font-bold text-blue-600">{numWarehouses}</p>
                  </div>
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small">
                  <div className="text-center">
                    <h3 className="text-lg font-semibold text-primary-700">Kỳ Thời Gian</h3>
                    <p className="text-2xl font-bold text-purple-600">{numPeriods}</p>
                  </div>
                </Card>
              </Col>
            </Row>
          </div>
        </TabPane>

        <TabPane tab={<><BranchesOutlined />Quản Lý Phiên Bản</>} key="versions">
          {/* Version Control Content */}
          <div className="space-y-6">
            <Card
              title={<><BranchesOutlined /> Quản Lý Phiên Bản Dữ Liệu</>}
              extra={
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => setShowCreateModal(true)}
                >
                  Tạo Phiên Bản
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
            <Card title={<><HistoryOutlined /> Lịch Sử Phiên Bản</>}>
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
        title="Tạo Phiên Bản Dữ Liệu"
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
            label="Tên Phiên Bản"
            rules={[{ required: true, message: 'Vui lòng nhập tên phiên bản' }]}
          >
            <Input placeholder="ví dụ: v1.0.0, cơ bản, kịch bản-A" />
          </Form.Item>
          <Form.Item name="description" label="Mô Tả">
            <Input.TextArea 
              placeholder="Mô tả những thay đổi trong phiên bản này"
              rows={3}
            />
          </Form.Item>
          <Form.Item name="created_by" label="Tạo Bởi" initialValue="user">
            <Input placeholder="Tên của bạn" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
    </Spin>
  )
}

export default ParameterManagement
