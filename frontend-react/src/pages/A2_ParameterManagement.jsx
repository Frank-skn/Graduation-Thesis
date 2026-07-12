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
      message.success('Đã lưu tham số thành công')
      setEditMode(false)
      setEditedParams({})
      refreshParams()
    } else {
      message.error('Không lưu được một số tham số')
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
        message.success('Đã tạo phiên bản dữ liệu thành công')
        setShowCreateModal(false)
        form.resetFields()
        refreshDatasets()
      }
    } catch (err) {
      if (err.errorFields) return
      message.error('Không tạo được phiên bản dữ liệu')
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

  // Cột bảng tham số giải thuật (read-only)
  const ALGO_GROUP_LABEL = { GA: 'Tìm kiếm chính', ALNS: 'Tinh chỉnh cục bộ', 'Dừng': 'Điều kiện dừng' }
  const algoColumns = [
    {
      title: 'Tham Số', dataIndex: 'name', key: 'name',
      render: (text) => <span className="font-semibold text-gray-800">{text}</span>,
    },
    {
      title: 'Ký Hiệu', dataIndex: 'symbol', key: 'symbol', width: 140,
      render: (t) => <code className="text-primary-700 bg-gray-100 px-1.5 py-0.5 rounded text-xs">{t}</code>,
    },
    {
      title: 'Giá Trị', dataIndex: 'value', key: 'value', width: 100, align: 'right',
      render: (v) => <span className="font-semibold">{Number(v).toLocaleString('vi-VN', { maximumFractionDigits: 3 })}</span>,
    },
    {
      title: 'Nhóm', dataIndex: 'group', key: 'group', width: 130,
      render: (g) => {
        const color = g === 'GA' ? 'blue' : g === 'ALNS' ? 'purple' : g === 'Dừng' ? 'red' : 'default'
        return <Tag color={color}>{ALGO_GROUP_LABEL[g] || g}</Tag>
      },
    },
    { title: 'Diễn Giải', dataIndex: 'description', key: 'description',
      render: (t) => <span className="text-gray-600 text-sm">{t}</span> },
  ]

  // Cột bảng tham số chi phí/vận hành (read-only)
  const costColumns = [
    { title: 'Tham Số', dataIndex: 'name', key: 'name',
      render: (t) => <span className="font-semibold text-gray-800">{t}</span> },
    { title: 'Ký Hiệu', dataIndex: 'symbol', key: 'symbol', width: 110,
      render: (t) => <code className="text-primary-700 bg-gray-100 px-1.5 py-0.5 rounded text-xs">{t}</code> },
    { title: 'Giá Trị', dataIndex: 'value', key: 'value', width: 90, align: 'right',
      render: (v) => <span className="font-semibold">{v}</span> },
    { title: 'Đơn Vị', dataIndex: 'unit', key: 'unit', width: 100,
      render: (t) => <span className="text-gray-500 text-sm">{t}</span> },
    { title: 'Nhóm', dataIndex: 'group', key: 'group', width: 110,
      render: (g) => <Tag color={g === 'Chi phí' ? 'volcano' : 'cyan'}>{g}</Tag> },
    { title: 'Diễn Giải', dataIndex: 'description', key: 'description',
      render: (t) => <span className="text-gray-600 text-sm">{t}</span> },
  ]

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
    <div className="space-y-6">
      <PageHeader
        icon={<SettingOutlined />}
        title="A2. Tham số mô hình"
        subtitle="Quản lý tham số mô hình và phiên bản dữ liệu"
      />

      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        <TabPane tab={<><SettingOutlined />Tham Số</>} key="parameters">
          {/* Parameters Content */}
          <div className="space-y-6">
            {/* Edit Mode Alert */}
            {editMode && (
              <Alert
                message="Chế Độ Chỉnh Sửa Đang Hoạt Động"
                description="Bạn đang chỉnh sửa tham số. Hãy lưu hoặc các thay đổi sẽ bị mất."
                type="warning"
                showIcon
              />
            )}

            {/* Tham số giải thuật tối ưu (đọc từ config, đã hiệu chỉnh qua thực nghiệm) */}
            <Card
              title={
                <span className="text-lg font-semibold flex items-center">
                  <SyncOutlined className="mr-2" />
                  Tham Số Giải Thuật Tối Ưu
                </span>
              }
              extra={<Tag color="blue">Cấu hình đã hiệu chỉnh</Tag>}
            >
              <Alert
                type="info"
                showIcon
                className="mb-4"
                message="Bộ tham số vận hành tối ưu"
                description="Các tham số điều khiển cách hệ thống tìm kiếm phương án phân bổ tốt nhất. Bộ giá trị hiện tại đã được thử nghiệm và hiệu chỉnh để cân bằng giữa chất lượng kết quả và thời gian chạy. Giá trị chi tiết hiển thị trong bảng dưới."
              />
              <Table
                columns={algoColumns}
                dataSource={algoParams}
                pagination={false}
                size="middle"
                rowKey="symbol"
              />
            </Card>

            {/* Tham số chi phí & vận hành (Bảng 3.3 — read-only) */}
            <Card
              title={
                <span className="text-lg font-semibold flex items-center">
                  <DollarOutlined className="mr-2" />
                  Tham Số Chi Phí & Vận Hành
                </span>
              }
            >
              <Alert
                type="warning"
                showIcon
                className="mb-4"
                message="Giá trị nền của dữ liệu vận hành (chỉ hiển thị)"
                description="Đây là các tham số chi phí và vận chuyển thực của doanh nghiệp. Để thay đổi và đánh giá tác động của chúng đến chi phí tối ưu, hãy dùng chức năng Phân tích kịch bản (C1. What-If) hoặc Phân tích độ nhạy (D1)."
              />
              <Table
                columns={costColumns}
                dataSource={costParams}
                pagination={false}
                size="middle"
                rowKey="symbol"
              />
            </Card>

            {/* Tham số mô hình (hằng số kỹ thuật lưu trong DB) */}
            <Card
              title={
                <span className="text-lg font-semibold flex items-center">
                  <DollarOutlined className="mr-2" />
                  Tham Số Mô Hình
                </span>
              }
              extra={
                !editMode ? (
                  <Button type="primary" icon={<EditOutlined />} onClick={() => setEditMode(true)}>
                    Chỉnh Sửa
                  </Button>
                ) : (
                  <div className="flex gap-2">
                    <Button icon={<ReloadOutlined />} onClick={handleCancel}>Hủy</Button>
                    <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}
                      disabled={Object.keys(editedParams).length === 0}>Lưu Thay Đổi</Button>
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
                locale={{ emptyText: 'Chưa có tham số mô hình tùy chỉnh' }}
              />
            </Card>
          </div>
        </TabPane>

        <TabPane tab={<><BranchesOutlined />Quản Lý Phiên Bản</>} key="versions">
          {/* Version Control Content */}
          <div className="space-y-6">
            <Alert
              type="info"
              showIcon
              message="Phiên bản dữ liệu dùng để làm gì?"
              description="Mỗi lần chạy tối ưu được gắn với một phiên bản dữ liệu (ảnh chụp bộ dữ liệu đầu vào tại thời điểm chạy, kèm mã kiểm tra checksum). Nhờ đó có thể truy vết lần chạy nào dùng bộ dữ liệu nào — hỗ trợ cơ chế rolling horizon khi dữ liệu cập nhật theo từng kỳ. Nhấn vào dấu ▸ ở mỗi phiên bản để xem các lần chạy đã dùng nó."
            />
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
                expandable={{
                  onExpand: (expanded, record) => {
                    if (expanded && !versionRuns[record.version_id]) loadVersionRuns(record.version_id)
                  },
                  expandedRowRender: (record) => {
                    const runs = versionRuns[record.version_id]
                    if (!runs) return <span className="text-gray-400">Đang tải...</span>
                    if (runs.length === 0) return <span className="text-gray-400">Chưa có lần chạy nào dùng phiên bản này.</span>
                    return (
                      <Table
                        size="small"
                        pagination={false}
                        rowKey="run_id"
                        dataSource={runs}
                        columns={[
                          { title: 'Lần chạy', dataIndex: 'run_id', render: (v) => <strong>#{v}</strong> },
                          { title: 'Thời gian', dataIndex: 'run_time', render: (v) => v ? String(v).slice(0, 16) : '—' },
                          { title: 'Trạng thái', dataIndex: 'solver_status', render: (v) => <Tag color={/optimal/i.test(v) ? 'green' : /error/i.test(v) ? 'red' : 'orange'}>{v}</Tag> },
                          { title: 'Chi phí tối ưu', dataIndex: 'objective_value', align: 'right', render: (v) => Number(v).toLocaleString('vi-VN') },
                        ]}
                      />
                    )
                  },
                }}
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
