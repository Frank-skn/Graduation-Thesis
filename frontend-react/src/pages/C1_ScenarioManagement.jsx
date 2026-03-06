/**
 * C1 – Phân tích What-If
 *
 * 6 nhóm kịch bản gộp lại từ 11 ScenarioType backend:
 *   1. demand       → demand_surge (pct>0), demand_drop (pct<0)
 *   2. capacity     → capacity_expansion (pct>0), capacity_disruption (pct<0)
 *   3. cost         → cost_increase (pct>0), cost_decrease (pct<0)
 *   4. inventory    → safety_stock_loosen (pct>0), safety_stock_tighten (pct<0)
 *   5. structural   → sub-type: new_product | warehouse_closure
 *   6. custom       → custom
 */
import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Row, Col, Table, Tag, Button, Form, Input, InputNumber,
  Select, Slider, Alert, Spin, message, Modal, Divider, Space, Tooltip,
  Badge, Statistic,
} from 'antd'
import {
  ExperimentOutlined, PlayCircleOutlined, ThunderboltOutlined, PlusOutlined,
  ReloadOutlined, BarChartOutlined, DollarOutlined, SafetyOutlined,
  ApartmentOutlined, ToolOutlined, RocketOutlined, InfoCircleOutlined,
  CheckCircleOutlined, WarningOutlined, ArrowUpOutlined, ArrowDownOutlined,
} from '@ant-design/icons'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RChartTooltip, ResponsiveContainer, Legend, ReferenceLine } from 'recharts'
import { useAppContext } from '../context/AppContext'
import { useApi, useMutation } from '../hooks/useApi'
import scenarioService from '../services/scenarioService'
import optimizationService from '../services/optimizationService'

const { Option } = Select
const { TextArea } = Input

// ────────────────────────────────────────────────────────────────────
// 6 NHÓM KỊCH BẢN (định nghĩa phía frontend, không phụ thuộc API)
// ────────────────────────────────────────────────────────────────────
const SCENARIO_GROUPS = [
  {
    key: 'demand',
    icon: <BarChartOutlined style={{ fontSize: 28, color: '#1890ff' }} />,
    label: '1️⃣ Điều chỉnh nhu cầu (DI)',
    description: 'Tăng hoặc giảm nhu cầu theo % ± x. Dương = nhu cầu tăng, âm = nhu cầu giảm.',
    paramTag: ['DI'],
    color: '#1890ff',
    hasSlider: true,
    defaultPct: 20,
  },
  {
    key: 'capacity',
    icon: <RocketOutlined style={{ fontSize: 28, color: '#722ed1' }} />,
    label: '2️⃣ Điều chỉnh công suất (CAP)',
    description: 'Tăng hoặc giảm công suất nhà cung cấp theo %. Âm = gián đoạn cung ứng.',
    paramTag: ['CAP'],
    color: '#722ed1',
    hasSlider: true,
    defaultPct: 30,
  },
  {
    key: 'cost',
    icon: <DollarOutlined style={{ fontSize: 28, color: '#cf1322' }} />,
    label: '3️⃣ Điều chỉnh chi phí (Cb, Co, Cs, Cp)',
    description: 'Điều chỉnh đồng thời tất cả thành phần chi phí (tồn thiếu, tồn thừa, thiếu hụt, vi phạm).',
    paramTag: ['Cb', 'Co', 'Cs', 'Cp'],
    color: '#cf1322',
    hasSlider: true,
    defaultPct: 20,
  },
  {
    key: 'inventory',
    icon: <SafetyOutlined style={{ fontSize: 28, color: '#52c41a' }} />,
    label: '4️⃣ Điều chỉnh chính sách tồn kho (U/L)',
    description: 'Nới rộng hoặc thu hẹp khoảng giữa ngưỡng trên (U) và ngưỡng dưới (L).',
    paramTag: ['U', 'L'],
    color: '#52c41a',
    hasSlider: true,
    defaultPct: 30,
  },
  {
    key: 'structural',
    icon: <ApartmentOutlined style={{ fontSize: 28, color: '#fa8c16' }} />,
    label: '5️⃣ Thay đổi cấu trúc',
    description: 'Thêm sản phẩm mới hoặc đóng cửa kho hàng — thay đổi cơ cấu mô hình.',
    paramTag: ['I/J'],
    color: '#fa8c16',
    hasSlider: false,
  },
  {
    key: 'custom',
    icon: <ToolOutlined style={{ fontSize: 28, color: '#595959' }} />,
    label: '6️⃣ Tùy chỉnh nâng cao (Custom)',
    description: 'Ghi đè tham số tùy ý. Dùng cho trường hợp đặc biệt không thuộc các nhóm trên.',
    paramTag: ['*'],
    color: '#595959',
    hasSlider: false,
  },
]

// Chuyển (groupKey, pct) → scenarioType + factor
function resolveScenarioType(groupKey, pct, structuralSubType) {
  switch (groupKey) {
    case 'demand':
      return { scenario_type: pct >= 0 ? 'demand_surge' : 'demand_drop', factor: 1 + Math.abs(pct) / 100 }
    case 'capacity':
      return { scenario_type: pct >= 0 ? 'capacity_expansion' : 'capacity_disruption', factor: 1 + Math.abs(pct) / 100 }
    case 'cost':
      return { scenario_type: pct >= 0 ? 'cost_increase' : 'cost_decrease', factor: 1 + Math.abs(pct) / 100 }
    case 'inventory':
      return { scenario_type: pct >= 0 ? 'safety_stock_loosen' : 'safety_stock_tighten', factor: 1 + Math.abs(pct) / 100 }
    case 'structural':
      return { scenario_type: structuralSubType || 'warehouse_closure', factor: 1 }
    case 'custom':
      return { scenario_type: 'custom', factor: 1 }
    default:
      return { scenario_type: 'custom', factor: 1 }
  }
}

// Nhãn tiếng Việt cho scenario_type
const TYPE_LABEL = {
  demand_surge: 'Nhu cầu tăng',
  demand_drop: 'Nhu cầu giảm',
  capacity_expansion: 'Mở rộng công suất',
  capacity_disruption: 'Gián đoạn công suất',
  cost_increase: 'Chi phí tăng',
  cost_decrease: 'Chi phí giảm',
  safety_stock_loosen: 'Nới ngưỡng tồn kho',
  safety_stock_tighten: 'Thu hẹp ngưỡng tồn kho',
  new_product_introduction: 'Sản phẩm mới',
  warehouse_closure: 'Đóng cửa kho',
  custom: 'Tùy chỉnh',
}

const fmt = (v, d = 0) =>
  typeof v === 'number' ? v.toLocaleString('vi-VN', { maximumFractionDigits: d }) : '—'

const sliderMarks = { '-50': '-50%', '-20': '-20%', 0: '0', 20: '+20%', 50: '+50%', 100: '+100%' }

// ────────────────────────────────────────────────────────────────────
const ScenarioManagement = () => {
  const { setActiveScenarioId, setActiveRunId, activeScenarioId } = useAppContext()

  // ── State ──────────────────────────────────────────────────────────
  const [selectedGroup, setSelectedGroup] = useState(null)
  const [adjustPct, setAdjustPct]         = useState(20)
  const [structSubType, setStructSubType] = useState('warehouse_closure')
  const [warehouseIds, setWarehouseIds]   = useState('')
  const [showModal, setShowModal]         = useState(false)
  const [modalForm]                       = Form.useForm()

  // Comparison state
  const [compareBase, setCompareBase]     = useState(null)
  const [compareWhatIf, setCompareWhatIf] = useState(null)
  const [comparing, setComparing]         = useState(false)
  const [compResult, setCompResult]       = useState(null)

  // ── API ────────────────────────────────────────────────────────────
  const { data: historyData, error: scenariosError, execute: refreshScenarios } = useApi(() => scenarioService.getWhatIfHistory())
  const { mutate: createWhatIf, loading: creating } = useMutation((data) => scenarioService.createWhatIf(data))
  // History from /whatif/history endpoint
  const scenarios = historyData?.scenarios || []

  // Run list cho base scenario selector
  const [runs, setRuns] = useState([])
  const loadRuns = useCallback(() => {
    optimizationService.listRuns()
      .then((res) => {
        // API interceptor already unwraps body: res = array directly
        const list = Array.isArray(res) ? res : (res?.runs ?? [])
        setRuns(list)
      })
      .catch(() => {})
  }, [])
  useEffect(() => { loadRuns() }, [loadRuns])

  // Khi runs load xong và modal đang mở → tự điền run đầu tiên nếu chưa có
  useEffect(() => {
    if (!showModal || runs.length === 0) return
    const cur = modalForm.getFieldValue('base_run_id')
    if (cur != null) return
    const preselect = activeScenarioId
      ? runs.find((r) => r.scenario_id === Number(activeScenarioId))?.run_id
      : undefined
    modalForm.setFieldsValue({ base_run_id: preselect ?? runs[0]?.run_id })
  }, [runs, showModal]) // eslint-disable-line

  // ── Mở modal với group đã chọn ─────────────────────────────────────
  const openModal = (group) => {
    setSelectedGroup(group)
    setAdjustPct(group.defaultPct ?? 20)
    modalForm.resetFields()
    // Reload runs mỗi lần mở modal để luôn đồng bộ
    loadRuns()
    // Ưu tiên: activeRunId từ context → run đầu tiên trong danh sách
    const preselect = activeScenarioId
      ? runs.find((r) => r.scenario_id === activeScenarioId)?.run_id
      : undefined
    modalForm.setFieldsValue({
      base_run_id: preselect ?? runs[0]?.run_id ?? undefined,
      label: '',
      time_limit: 300,
    })
    setShowModal(true)
  }

  // ── Submit What-If ─────────────────────────────────────────────────
  const handleSubmit = async () => {
    try {
      const values = await modalForm.validateFields()
      const { scenario_type, factor } = resolveScenarioType(
        selectedGroup.key,
        adjustPct,
        structSubType,
      )

      let overrides = { factor }
      if (selectedGroup.key === 'structural' && structSubType === 'warehouse_closure') {
        overrides = {
          warehouses: warehouseIds.split(',').map((s) => s.trim()).filter(Boolean),
          redistribute: true,
        }
      }
      if (selectedGroup.key === 'custom') {
        try {
          overrides = JSON.parse(values.custom_json || '{}')
        } catch {
          message.error('JSON tùy chỉnh không hợp lệ')
          return
        }
      }

      const selectedRun = runs.find((r) => r.run_id === values.base_run_id)
      const baseScenarioId = selectedRun?.scenario_id || activeScenarioId || 1

      await createWhatIf({
        base_scenario_id: baseScenarioId,
        scenario_type,
        label: values.label || `${TYPE_LABEL[scenario_type]} ±${Math.abs(adjustPct)}%`,
        overrides,
        solver: 'glpk',
        time_limit: values.time_limit || 300,
        mip_gap: 0.01,
      })

      message.success('Kịch bản What-If đã chạy thành công!')
      setShowModal(false)
      refreshScenarios()
    } catch (err) {
      if (err?.errorFields) return
      const msg = err?.response?.data?.detail || err?.message || 'Lỗi không xác định'
      message.error(`Chạy kịch bản thất bại: ${msg}`)
    }
  }

  // ── So sánh 2 lần chạy ─────────────────────────────────────────────
  const handleCompare = async () => {
    if (!compareBase || !compareWhatIf) {
      message.warning('Vui lòng chọn 2 lần chạy để so sánh')
      return
    }
    setComparing(true)
    try {
      const res = await scenarioService.compareWhatIf(compareBase, compareWhatIf)
      setCompResult(res.data ?? res)
    } catch (err) {
      message.error('Không thể so sánh: ' + (err?.message || ''))
    } finally {
      setComparing(false)
    }
  }

  // ── Cột bảng lịch sử kịch bản (What-If runs) ────────────────────
  const scenarioColumns = [
    { title: 'ID', dataIndex: 'whatif_id', key: 'id', width: 60,
      render: (v) => <Tag color="blue">#{v}</Tag> },
    { title: 'Tên / Nhãn', dataIndex: 'label', key: 'label',
      render: (v, r) => <span className="font-medium">{v || r.whatif_type || '—'}</span> },
    { title: 'Loại', dataIndex: 'whatif_type', key: 'type',
      render: (v) => <Tag color="geekblue">{TYPE_LABEL[v] ?? v ?? 'Tùy chỉnh'}</Tag> },
    { title: 'Trạng thái', dataIndex: 'status', key: 'status',
      render: (v) => {
        const color = v === 'completed' ? 'green' : v === 'running' ? 'processing' : v === 'failed' ? 'red' : 'default'
        return <Tag color={color}>{v ?? '—'}</Tag>
      }},
    { title: 'Chi phí tối ưu', dataIndex: 'objective_value', key: 'obj', align: 'right',
      render: (v) => v != null ? <span className="font-semibold text-red-600">{fmt(v, 0)}</span> : '—' },
    { title: 'Solver', dataIndex: 'solver_status', key: 'solver',
      render: (v) => v ? <Tag color={v === 'Optimal' ? 'green' : v === 'Feasible' ? 'orange' : 'red'}>{v}</Tag> : '—' },
    { title: 'Ngày tạo', dataIndex: 'created_at', key: 'at',
      render: (v) => v ? new Date(v).toLocaleString('vi-VN') : '—' },
    { title: 'Hành động', key: 'action', width: 100,
      render: (_, r) => r.run_id ? (
        <Button size="small" type="link" onClick={() => {
          setActiveRunId(r.run_id)
          message.success(`Đã chọn lần chạy #${r.run_id} — điều hướng đến B2 để xem kết quả`)
        }}>Xem kết quả</Button>
      ) : null,
    },
  ]

  // Slider pct → hiển thị label
  const pctLabel = adjustPct === 0
    ? 'Không thay đổi'
    : adjustPct > 0
      ? `Tăng +${adjustPct}%`
      : `Giảm ${adjustPct}%`

  // Biểu đồ so sánh KPI
  const compChartData = compResult?.deltas
    ? compResult.deltas
        .filter((d) => Math.abs(d.percent_change ?? 0) >= 0.1)
        .map((d) => ({
          name: d.kpi_name,
          'Cơ sở': Number(d.base_value) || 0,
          'Kịch bản': Number(d.whatif_value) || 0,
          pct: Number(d.percent_change) || 0,
        }))
    : []

  // ────────────────────────────────────────────────────────────────────
  // Render
  // ────────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      {/* Tiêu đề */}
      <div>
        <h1 className="text-3xl font-bold text-primary-700 mb-1">
          <ExperimentOutlined className="mr-3" />C1. Phân tích What-If
        </h1>
        <p className="text-gray-500">
          Chọn một nhóm kịch bản, điều chỉnh tham số, rồi chạy để xem kết quả so với lần chạy cơ sở.
        </p>
      </div>

      {/* 6 nhóm kịch bản */}
      <Card title={<span className="font-bold">Chọn nhóm kịch bản</span>}>
        <Row gutter={[16, 16]}>
          {SCENARIO_GROUPS.map((g) => (
            <Col xs={24} sm={12} lg={8} key={g.key}>
              <Card
                hoverable
                onClick={() => openModal(g)}
                style={{ borderColor: g.color, borderWidth: 1.5, height: '100%', cursor: 'pointer' }}
                bodyStyle={{ padding: '16px' }}
              >
                <div className="flex gap-3">
                  <div>{g.icon}</div>
                  <div>
                    <div className="font-semibold text-sm" style={{ color: g.color }}>{g.label}</div>
                    <div className="text-gray-500 text-xs mt-1">{g.description}</div>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {g.paramTag.map((p) => (
                        <Tag key={p} color="default" style={{ fontSize: 11 }}>{p}</Tag>
                      ))}
                    </div>
                  </div>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      </Card>

      {/* Lịch sử kịch bản */}
      <Card
        title={
          <span className="font-bold">
            <BarChartOutlined className="mr-2" />Lịch sử kịch bản
            {scenarios.length > 0 && <Badge count={scenarios.length} style={{ marginLeft: 8 }} />}
          </span>
        }
        extra={
          <Button icon={<ReloadOutlined />} onClick={() => refreshScenarios()} size="small">
            Làm mới
          </Button>
        }
      >
        <Table
          dataSource={scenarios}
          columns={scenarioColumns}
          rowKey="whatif_id"
          size="small"
          pagination={{ pageSize: 8, showSizeChanger: false }}
          locale={{ emptyText: scenariosError
            ? `Không thể tải kịch bản: ${scenariosError}`
            : 'Chưa có kịch bản nào. Chọn nhóm bên trên để bắt đầu.'
          }}
        />
      </Card>

      {/* So sánh 2 lần chạy */}
      <Card title={<span className="font-bold"><BarChartOutlined className="mr-2" />So sánh lần chạy</span>}>
        <div className="flex items-center gap-4 flex-wrap mb-4">
          <div>
            <span className="text-gray-500 text-xs block mb-1">Lần chạy cơ sở:</span>
            <Select
              style={{ width: 260 }}
              placeholder="Chọn lần chạy cơ sở"
              value={compareBase}
              onChange={setCompareBase}
            >
              {runs.map((r) => (
                <Option key={r.run_id} value={r.run_id}>
                  Run #{r.run_id} — {r.solver_status} ({fmt(r.objective_value)})
                </Option>
              ))}
            </Select>
          </div>
          <div>
            <span className="text-gray-500 text-xs block mb-1">Lần chạy so sánh:</span>
            <Select
              style={{ width: 260 }}
              placeholder="Chọn lần chạy so sánh"
              value={compareWhatIf}
              onChange={setCompareWhatIf}
            >
              {runs.map((r) => (
                <Option key={r.run_id} value={r.run_id}>
                  Run #{r.run_id} — {r.solver_status} ({fmt(r.objective_value)})
                </Option>
              ))}
            </Select>
          </div>
          <div style={{ marginTop: 20 }}>
            <Button
              type="primary"
              icon={<BarChartOutlined />}
              onClick={handleCompare}
              loading={comparing}
              disabled={!compareBase || !compareWhatIf}
            >
              So sánh KPI
            </Button>
          </div>
        </div>

        {compResult && compChartData.length > 0 && (
          <>
            <Alert
              type="info"
              showIcon
              message={compResult.summary || 'So sánh hoàn tất'}
              className="mb-4"
            />
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={compChartData} margin={{ bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" angle={-30} textAnchor="end" interval={0} tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => v.toLocaleString('vi-VN')} width={90} tick={{ fontSize: 10 }} />
                <RChartTooltip formatter={(v) => fmt(v, 2)} />
                <Legend />
                <Bar dataKey="Cơ sở"    fill="#d9d9d9" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Kịch bản" fill="#1890ff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <Table
              size="small"
              pagination={false}
              className="mt-4"
              dataSource={compResult.deltas ?? []}
              rowKey="kpi_name"
              columns={[
                { title: 'KPI', dataIndex: 'kpi_name', key: 'kpi_name',
                  render: (v) => <span className="font-medium">{v}</span> },
                { title: 'Cơ sở', dataIndex: 'base_value', key: 'base',
                  align: 'right', render: (v) => fmt(Number(v), 2) },
                { title: 'Kịch bản', dataIndex: 'whatif_value', key: 'wi',
                  align: 'right', render: (v) => fmt(Number(v), 2) },
                { title: 'Thay đổi', dataIndex: 'percent_change', key: 'pct',
                  align: 'right',
                  render: (v) => {
                    const n = Number(v)
                    if (!v && v !== 0) return '—'
                    const color = n > 0 ? 'red' : n < 0 ? 'green' : 'default'
                    const icon = n > 0 ? <ArrowUpOutlined /> : n < 0 ? <ArrowDownOutlined /> : null
                    return <Tag color={color} icon={icon}>{n > 0 ? '+' : ''}{n.toFixed(1)}%</Tag>
                  }},
              ]}
            />
          </>
        )}
        {compResult && compChartData.length === 0 && (
          <Alert type="success" showIcon message="Không có thay đổi KPI đáng kể giữa hai lần chạy." />
        )}
      </Card>

      {/* ════ MODAL tạo kịch bản ════ */}
      <Modal
        title={
          selectedGroup && (
            <div className="flex items-center gap-2">
              {selectedGroup.icon}
              <span>{selectedGroup.label}</span>
            </div>
          )
        }
        open={showModal}
        onCancel={() => { setShowModal(false); modalForm.resetFields() }}
        onOk={handleSubmit}
        confirmLoading={creating}
        okText="Chạy kịch bản"
        cancelText="Huỷ"
        width={560}
      >
        {selectedGroup && (
          <Form form={modalForm} layout="vertical" className="pt-2">
            <Alert
              type="info"
              showIcon
              message={selectedGroup.description}
              className="mb-4"
            />

            {/* Chọn lần chạy cơ sở */}
            <Form.Item
              name="base_run_id"
              label="Lần chạy cơ sở (Run ID)"
              rules={[{ required: true, message: 'Chọn lần chạy cơ sở' }]}
            >
              <Select placeholder="Chọn lần chạy cơ sở để điều chỉnh">
                {runs.map((r) => (
                  <Option key={r.run_id} value={r.run_id}>
                    Run #{r.run_id} · {r.solver_status} · CP tối ưu: {fmt(r.objective_value)}
                  </Option>
                ))}
              </Select>
            </Form.Item>

            {/* Slider ± % cho 4 nhóm factor-based */}
            {selectedGroup.hasSlider && (
              <Form.Item
                label={
                  <span>
                    Mức điều chỉnh &nbsp;
                    <Tag color={adjustPct > 0 ? 'blue' : adjustPct < 0 ? 'orange' : 'default'}>
                      {pctLabel}
                    </Tag>
                  </span>
                }
              >
                <Slider
                  min={-60}
                  max={100}
                  step={5}
                  value={adjustPct}
                  onChange={setAdjustPct}
                  marks={sliderMarks}
                  tooltip={{ formatter: (v) => `${v > 0 ? '+' : ''}${v}%` }}
                />
                <div className="text-center text-gray-400 text-xs mt-1">
                  {adjustPct !== 0
                    ? `→ Loại kịch bản: ${resolveScenarioType(selectedGroup.key, adjustPct).scenario_type}, factor = ${resolveScenarioType(selectedGroup.key, adjustPct).factor.toFixed(2)}`
                    : '⚠ Mức 0% không gây thay đổi — hãy điều chỉnh slider'}
                </div>
              </Form.Item>
            )}

            {/* Cấu hình thay đổi cấu trúc */}
            {selectedGroup.key === 'structural' && (
              <>
                <Form.Item label="Loại thay đổi cấu trúc">
                  <Select value={structSubType} onChange={setStructSubType}>
                    <Option value="warehouse_closure">Đóng cửa kho hàng (Warehouse Closure)</Option>
                    <Option value="new_product_introduction">Thêm sản phẩm mới (New Product)</Option>
                  </Select>
                </Form.Item>
                {structSubType === 'warehouse_closure' && (
                  <Form.Item
                    label="Mã kho cần đóng (cách nhau bởi dấu phẩy)"
                    extra="Ví dụ: WH01, WH02"
                  >
                    <Input
                      placeholder="WH01, WH02"
                      value={warehouseIds}
                      onChange={(e) => setWarehouseIds(e.target.value)}
                    />
                  </Form.Item>
                )}
                {structSubType === 'new_product_introduction' && (
                  <Alert
                    type="warning"
                    showIcon
                    message="Thêm sản phẩm mới yêu cầu cấu hình chi tiết qua API. Hiện chưa hỗ trợ qua giao diện."
                  />
                )}
              </>
            )}

            {/* JSON nâng cao */}
            {selectedGroup.key === 'custom' && (
              <Form.Item
                name="custom_json"
                label={
                  <span>
                    Tham số overrides (JSON)&nbsp;
                    <Tooltip title='Ví dụ: {"parameter_overrides": {"DI": {}}}'>
                      <InfoCircleOutlined />
                    </Tooltip>
                  </span>
                }
                initialValue="{}"
              >
                <TextArea rows={5} placeholder='{"parameter_overrides": {}}' />
              </Form.Item>
            )}

            {/* Nhãn kịch bản */}
            <Form.Item name="label" label="Nhãn kịch bản">
              <Input placeholder={
                selectedGroup.hasSlider
                  ? `${selectedGroup.label} ${adjustPct > 0 ? '+' : ''}${adjustPct}%`
                  : selectedGroup.label
              } />
            </Form.Item>

            {/* Giới hạn thời gian */}
            <Form.Item name="time_limit" label="Giới hạn thời gian giải (giây)" initialValue={300}>
              <InputNumber min={30} max={3600} step={30} style={{ width: '100%' }} />
            </Form.Item>
          </Form>
        )}
      </Modal>
    </div>
  )
}

export default ScenarioManagement