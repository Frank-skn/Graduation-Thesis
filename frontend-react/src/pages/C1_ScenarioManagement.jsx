/**
 * C1 – What-If Analysis
 *
 * 6 scenario groups consolidated from 11 backend ScenarioTypes:
 *   1. demand       → demand_surge (pct>0), demand_drop (pct<0)
 *   2. capacity     → capacity_expansion (pct>0), capacity_disruption (pct<0)
 *   3. cost         → cost_increase (pct>0), cost_decrease (pct<0)
 *   4. inventory    → safety_stock_loosen (pct>0), safety_stock_tighten (pct<0)
 *   5. structural   → sub-type: new_product | warehouse_closure
 *   6. custom       → custom
 */
import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Row, Col, Table, Tag, Button, Form, Input, InputNumber,
  Select, Slider, Alert, Spin, message, Modal, Divider, Space, Tooltip,
  Badge, Statistic,
} from 'antd'
import {
  ExperimentOutlined, PlayCircleOutlined, ThunderboltOutlined, PlusOutlined,
  ReloadOutlined, BarChartOutlined, DollarOutlined, SafetyOutlined,
  ApartmentOutlined, ToolOutlined, RocketOutlined, InfoCircleOutlined,
  CheckCircleOutlined, WarningOutlined,
} from '@ant-design/icons'
import { useAppContext } from '../context/AppContext'
import { useApi, useMutation } from '../hooks/useApi'
import scenarioService from '../services/scenarioService'
import optimizationService from '../services/optimizationService'
import PageHeader from '../components/PageHeader'
import { CATEGORICAL, NEUTRAL } from '../theme/tokens'

const { Option } = Select
const { TextArea } = Input

// ────────────────────────────────────────────────────────────────────
// 6 SCENARIO GROUPS (defined on the frontend, independent of the API)
// ────────────────────────────────────────────────────────────────────
const SCENARIO_GROUPS = [
  {
    key: 'demand',
    icon: <BarChartOutlined style={{ fontSize: 28, color: CATEGORICAL[0] }} />,
    label: 'Demand adjustment (DI)',
    description: 'Increase or decrease demand by % ± x. Positive = demand increases, negative = demand decreases.',
    paramTag: ['DI'],
    color: CATEGORICAL[0],
    hasSlider: true,
    defaultPct: 20,
  },
  {
    key: 'capacity',
    icon: <RocketOutlined style={{ fontSize: 28, color: CATEGORICAL[1] }} />,
    label: 'Capacity adjustment (CAP)',
    description: 'Increase or decrease supplier capacity by %. Negative = supply disruption.',
    paramTag: ['CAP'],
    color: CATEGORICAL[1],
    hasSlider: true,
    defaultPct: 30,
  },
  {
    key: 'cost',
    icon: <DollarOutlined style={{ fontSize: 28, color: CATEGORICAL[2] }} />,
    label: 'Cost adjustment (Cb, Co, Cs, Cp)',
    description: 'Adjust all cost components simultaneously (backorder, overstock, shortage, penalty).',
    paramTag: ['Cb', 'Co', 'Cs', 'Cp'],
    color: CATEGORICAL[2],
    hasSlider: true,
    defaultPct: 20,
  },
  {
    key: 'inventory',
    icon: <SafetyOutlined style={{ fontSize: 28, color: CATEGORICAL[3] }} />,
    label: 'Inventory policy adjustment (U/L)',
    description: 'Widen or narrow the range between the upper threshold (U) and lower threshold (L).',
    paramTag: ['U', 'L'],
    color: CATEGORICAL[3],
    hasSlider: true,
    defaultPct: 30,
  },
  {
    key: 'structural',
    icon: <ApartmentOutlined style={{ fontSize: 28, color: CATEGORICAL[4] }} />,
    label: 'Structural change',
    description: 'Add a new product or close a warehouse — changes the structure of the model.',
    paramTag: ['I/J'],
    color: CATEGORICAL[4],
    hasSlider: false,
  },
  {
    key: 'custom',
    icon: <ToolOutlined style={{ fontSize: 28, color: CATEGORICAL[5] }} />,
    label: 'Advanced customization (Custom)',
    description: 'Override arbitrary parameters. Used for special cases not covered by the groups above.',
    paramTag: ['*'],
    color: CATEGORICAL[5],
    hasSlider: false,
  },
]

// Convert (groupKey, pct) → scenarioType + factor
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

// English labels for scenario_type
const TYPE_LABEL = {
  demand_surge: 'Demand increase',
  demand_drop: 'Demand decrease',
  capacity_expansion: 'Capacity expansion',
  capacity_disruption: 'Capacity disruption',
  cost_increase: 'Cost increase',
  cost_decrease: 'Cost decrease',
  safety_stock_loosen: 'Inventory threshold loosened',
  safety_stock_tighten: 'Inventory threshold tightened',
  new_product_introduction: 'New product',
  warehouse_closure: 'Warehouse closure',
  custom: 'Custom',
}

const fmt = (v, d = 0) =>
  typeof v === 'number' ? v.toLocaleString('vi-VN', { maximumFractionDigits: d }) : '—'

const sliderMarks = { '-50': '-50%', '-20': '-20%', 0: '0', 20: '+20%', 50: '+50%', 100: '+100%' }

// ────────────────────────────────────────────────────────────────────
const ScenarioManagement = () => {
  const navigate = useNavigate()
  const { setActiveScenarioId, setActiveRunId, activeScenarioId } = useAppContext()

  // ── State ──────────────────────────────────────────────────────────
  const [selectedGroup, setSelectedGroup] = useState(null)
  const [adjustPct, setAdjustPct]         = useState(20)
  const [structSubType, setStructSubType] = useState('warehouse_closure')
  const [warehouseIds, setWarehouseIds]   = useState('')
  const [showModal, setShowModal]         = useState(false)
  const [modalForm]                       = Form.useForm()

  // ── API ────────────────────────────────────────────────────────────
  const { data: historyData, error: scenariosError, execute: refreshScenarios } = useApi(() => scenarioService.getWhatIfHistory())
  const { mutate: createWhatIf, loading: creating } = useMutation((data) => scenarioService.createWhatIf(data))
  // History from /whatif/history endpoint
  const scenarios = historyData?.scenarios || []

  // Auto-poll history while a job is still running (what-if runs in the background)
  const hasRunningWhatIf = scenarios.some((s) => (s.status || '') === 'running')
  useEffect(() => {
    if (!hasRunningWhatIf) return
    const id = setInterval(() => { refreshScenarios() }, 5000)
    return () => clearInterval(id)
  }, [hasRunningWhatIf, refreshScenarios])

  // Run list for the base scenario selector
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

  // When runs finish loading and the modal is open → auto-fill the first run if none is set
  useEffect(() => {
    if (!showModal || runs.length === 0) return
    const cur = modalForm.getFieldValue('base_run_id')
    if (cur != null) return
    const preselect = activeScenarioId
      ? runs.find((r) => r.scenario_id === Number(activeScenarioId))?.run_id
      : undefined
    modalForm.setFieldsValue({ base_run_id: preselect ?? runs[0]?.run_id })
  }, [runs, showModal]) // eslint-disable-line

  // ── Open modal with the selected group ─────────────────────────────────────
  const openModal = (group) => {
    setSelectedGroup(group)
    setAdjustPct(group.defaultPct ?? 20)
    modalForm.resetFields()
    // Reload runs every time the modal opens to stay in sync
    loadRuns()
    // Priority: activeRunId from context → first run in the list
    const preselect = activeScenarioId
      ? runs.find((r) => r.scenario_id === activeScenarioId)?.run_id
      : undefined
    modalForm.setFieldsValue({
      base_run_id: preselect ?? runs[0]?.run_id ?? undefined,
      label: '',
      time_limit: 10,
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
          message.error('Invalid custom JSON')
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
        solver: 'ma',
        time_limit: values.time_limit || 10,
        mip_gap: 0.01,
      })

      message.success('The What-If scenario has been launched. Results will update in the history once complete.')
      setShowModal(false)
      refreshScenarios()
    } catch (err) {
      if (err?.errorFields) return
      const msg = err?.response?.data?.detail || err?.message || 'Unknown error'
      message.error(`Failed to run scenario: ${msg}`)
    }
  }

  // ── Scenario history table columns (What-If runs) ────────────────────
  const scenarioColumns = [
    { title: 'ID', dataIndex: 'whatif_id', key: 'id', width: 60,
      render: (v) => <Tag color="blue">#{v}</Tag> },
    { title: 'Name / Label', dataIndex: 'label', key: 'label',
      render: (v, r) => <span className="font-medium">{v || r.whatif_type || '—'}</span> },
    { title: 'Type', dataIndex: 'whatif_type', key: 'type',
      render: (v) => <Tag color="blue">{TYPE_LABEL[v] ?? v ?? 'Custom'}</Tag> },
    { title: 'Status', dataIndex: 'status', key: 'status',
      render: (v) => {
        const color = v === 'completed' ? 'green' : v === 'running' ? 'processing' : v === 'failed' ? 'red' : 'default'
        return <Tag color={color}>{v ?? '—'}</Tag>
      }},
    { title: 'Optimal Cost', dataIndex: 'objective_value', key: 'obj', align: 'right',
      render: (v) => v != null ? <span className="font-semibold tabular-nums" style={{ color: NEUTRAL[700] }}>{fmt(v, 0)}</span> : '—' },
    { title: 'Solver', dataIndex: 'solver_status', key: 'solver',
      render: (v) => v ? <Tag color={/^optimal$/i.test(v) ? 'green' : /^feasible$/i.test(v) ? 'orange' : 'red'}>{v}</Tag> : '—' },
    { title: 'Created At', dataIndex: 'created_at', key: 'at',
      render: (v) => v ? new Date(v).toLocaleString('en-US') : '—' },
    { title: 'Action', key: 'action', width: 100,
      render: (_, r) => r.run_id ? (
        <Button size="small" type="link" onClick={() => {
          setActiveRunId(r.run_id)
          message.success(`Run #${r.run_id} selected`)
          navigate('/b2-executive-summary')
        }}>View Results</Button>
      ) : null,
    },
  ]

  // Slider pct → display label
  const pctLabel = adjustPct === 0
    ? 'No change'
    : adjustPct > 0
      ? `Increase +${adjustPct}%`
      : `Decrease ${adjustPct}%`

  // ────────────────────────────────────────────────────────────────────
  // Render
  // ────────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      <PageHeader
        icon={<ExperimentOutlined />}
        title="C1. What-If Analysis"
        subtitle="Select a scenario group, adjust parameters, then run to compare with the base run"
      />

      {/* 6 scenario groups */}
      <Card title={<span className="font-bold">Select Scenario Group</span>}>
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

      {/* Scenario history */}
      <Card
        title={
          <span className="font-bold">
            <BarChartOutlined className="mr-2" />Scenario History
            {scenarios.length > 0 && <Badge count={scenarios.length} style={{ marginLeft: 8 }} />}
          </span>
        }
        extra={
          <Button icon={<ReloadOutlined />} onClick={() => refreshScenarios()} size="small">
            Refresh
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
            ? `Unable to load scenarios: ${scenariosError}`
            : 'No scenarios yet. Select a group above to get started.'
          }}
        />
      </Card>

      {/* ════ Create Scenario MODAL ════ */}
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
        okText="Run Scenario"
        cancelText="Cancel"
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

            {/* Select base run */}
            <Form.Item
              name="base_run_id"
              label="Base Run (Run ID)"
              rules={[{ required: true, message: 'Select a base run' }]}
            >
              <Select placeholder="Select a base run to adjust">
                {runs.map((r) => (
                  <Option key={r.run_id} value={r.run_id}>
                    Run #{r.run_id} · {r.solver_status} · Optimal Cost: {fmt(r.objective_value)}
                  </Option>
                ))}
              </Select>
            </Form.Item>

            {/* ± % slider for the 4 factor-based groups */}
            {selectedGroup.hasSlider && (
              <Form.Item
                label={
                  <span>
                    Adjustment level &nbsp;
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
                    ? `→ Scenario type: ${resolveScenarioType(selectedGroup.key, adjustPct).scenario_type}, factor = ${resolveScenarioType(selectedGroup.key, adjustPct).factor.toFixed(2)}`
                    : '⚠ A 0% level causes no change — please adjust the slider'}
                </div>
              </Form.Item>
            )}

            {/* Structural change configuration */}
            {selectedGroup.key === 'structural' && (
              <>
                <Form.Item label="Structural Change Type">
                  <Select value={structSubType} onChange={setStructSubType}>
                    <Option value="warehouse_closure">Warehouse Closure</Option>
                    <Option value="new_product_introduction">New Product Introduction</Option>
                  </Select>
                </Form.Item>
                {structSubType === 'warehouse_closure' && (
                  <Form.Item
                    label="Warehouse codes to close (comma-separated)"
                    extra="Example: WH01, WH02"
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
                    message="Adding a new product requires detailed configuration via the API. Not yet supported through the UI."
                  />
                )}
              </>
            )}

            {/* Advanced JSON */}
            {selectedGroup.key === 'custom' && (
              <Form.Item
                name="custom_json"
                label={
                  <span>
                    Override Parameters (JSON)&nbsp;
                    <Tooltip title='Example: {"parameter_overrides": {"DI": {}}}'>
                      <InfoCircleOutlined />
                    </Tooltip>
                  </span>
                }
                initialValue="{}"
              >
                <TextArea rows={5} placeholder='{"parameter_overrides": {}}' />
              </Form.Item>
            )}

            {/* Scenario label */}
            <Form.Item name="label" label="Scenario Label">
              <Input placeholder={
                selectedGroup.hasSlider
                  ? `${selectedGroup.label} ${adjustPct > 0 ? '+' : ''}${adjustPct}%`
                  : selectedGroup.label
              } />
            </Form.Item>

            {/* Time limit per product */}
            <Form.Item
              name="time_limit"
              label="Time Limit per Product (seconds)"
              initialValue={10}
              extra="Maximum time the MA runs per product. Increase for a better solution, decrease for a faster run."
            >
              <InputNumber min={1} max={60} step={1} style={{ width: '100%' }} />
            </Form.Item>
          </Form>
        )}
      </Modal>
    </div>
  )
}

export default ScenarioManagement