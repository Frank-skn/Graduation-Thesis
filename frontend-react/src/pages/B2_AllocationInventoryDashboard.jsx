import React, { useState } from 'react'
import { Card, Row, Col, Table, Tag, Select, Alert, Spin, InputNumber, Button, Radio, Tabs, Progress } from 'antd'
import {
  AppstoreOutlined,
  LineChartOutlined,
  FilterOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ComposedChart, Line, ReferenceLine } from 'recharts'
import { useApi } from '../hooks/useApi'
import { useAppContext } from '../context/AppContext'
import optimizationService from '../services/optimizationService'
import dataService from '../services/dataService'

const { Option } = Select
const { TabPane } = Tabs

const AllocationInventoryDashboard = () => {
  const { activeRunId, setActiveRunId } = useAppContext()
  const [runIdInput, setRunIdInput] = useState(activeRunId || 1)
  const [filterProduct, setFilterProduct] = useState(undefined)
  const [filterWarehouse, setFilterWarehouse] = useState(undefined)
  const [viewMode, setViewMode] = useState('chart')
  const [activeTab, setActiveTab] = useState('allocation')

  const { data: overview } = useApi(() => dataService.getOverview())
  
  // Allocation data
  const { data: allocationData, loading: allocationLoading, error: allocationError } = useApi(
    () => activeRunId ? optimizationService.getAllocation(activeRunId, { product_id: filterProduct, warehouse_id: filterWarehouse }) : Promise.resolve(null),
    [activeRunId, filterProduct, filterWarehouse]
  )

  // Inventory dynamics data
  const { data: inventoryData, loading: inventoryLoading, error: inventoryError } = useApi(
    () => activeRunId ? optimizationService.getInventoryDynamics(activeRunId, { product_id: filterProduct, warehouse_id: filterWarehouse }) : Promise.resolve(null),
    [activeRunId, filterProduct, filterWarehouse]
  )

  const products = overview?.products || []
  const warehouses = overview?.warehouses || []
  const allocations = allocationData?.allocations || []
  const dynamics = inventoryData?.dynamics || []

  const loading = allocationLoading || inventoryLoading
  const error = allocationError || inventoryError

  const handleRunLoad = () => {
    if (runIdInput) {
      setActiveRunId(runIdInput)
    }
  }

  // Allocation data processing
  const warehouseStats = warehouses.map(wh => {
    const whAllocs = allocations.filter(a => a.warehouse_id === wh)
    return {
      warehouse: wh,
      totalCasePack: whAllocs.reduce((s, a) => s + (a.q_case_pack || 0), 0),
      totalResidual: whAllocs.reduce((s, a) => s + (a.r_residual_units || 0), 0),
      avgInventory: whAllocs.length > 0 ? Math.round(whAllocs.reduce((s, a) => s + Number(a.net_inventory || 0), 0) / whAllocs.length) : 0,
      backorders: whAllocs.reduce((s, a) => s + Number(a.backorder_qty || 0), 0),
      penalties: whAllocs.filter(a => a.penalty_flag).length,
    }
  })

  // Inventory dynamics data processing
  const chartData = []
  dynamics.forEach(d => {
    (d.periods || []).forEach(p => {
      chartData.push({
        key: `${d.product_id}-${d.warehouse_id}-${p.time_period}`,
        product_id: d.product_id,
        warehouse_id: d.warehouse_id,
        time_period: p.time_period,
        net_inventory: Number(p.net_inventory || 0),
        backorder_qty: Number(p.backorder_qty || 0),
        overstock_qty: Number(p.overstock_qty || 0),
        shortage_qty: Number(p.shortage_qty || 0),
        q_case_pack: p.q_case_pack || 0,
        r_residual_units: p.r_residual_units || 0,
        penalty_flag: p.penalty_flag,
      })
    })
  })

  const allocationColumns = [
    {
      title: 'Product',
      dataIndex: 'product_id',
      key: 'product_id',
      render: (t) => <Tag color="blue">{t}</Tag>,
    },
    {
      title: 'Warehouse',
      dataIndex: 'warehouse_id',
      key: 'warehouse_id',
      render: (t) => <Tag color="green">{t}</Tag>,
    },
    {
      title: 'Case Packs',
      dataIndex: 'q_case_pack',
      key: 'q_case_pack',
      sorter: true,
      render: (val) => val?.toLocaleString() || 0,
    },
    {
      title: 'Residual',
      dataIndex: 'r_residual_units',
      key: 'r_residual_units',
      sorter: true,
      render: (val) => val?.toLocaleString() || 0,
    },
    {
      title: 'Net Inventory',
      dataIndex: 'net_inventory',
      key: 'net_inventory',
      sorter: true,
      render: (val) => (
        <span className={Number(val) < 0 ? 'text-red-500' : ''}>
          {Number(val)?.toLocaleString() || 0}
        </span>
      ),
    },
    {
      title: 'Backorder',
      dataIndex: 'backorder_qty',
      key: 'backorder_qty',
      render: (val) => (
        <span className={Number(val) > 0 ? 'text-red-500' : ''}>
          {Number(val)?.toLocaleString() || 0}
        </span>
      ),
    },
    {
      title: 'Penalty',
      dataIndex: 'penalty_flag',
      key: 'penalty_flag',
      render: (flag) => flag ? <Tag color="orange">Yes</Tag> : <Tag color="default">No</Tag>,
    },
  ]

  const inventoryColumns = [
    {
      title: 'Product',
      dataIndex: 'product_id',
      key: 'product_id',
      render: (t) => <Tag color="blue">{t}</Tag>,
    },
    {
      title: 'Warehouse',
      dataIndex: 'warehouse_id',
      key: 'warehouse_id',
      render: (t) => <Tag color="green">{t}</Tag>,
    },
    {
      title: 'Period',
      dataIndex: 'time_period',
      key: 'time_period',
      sorter: true,
    },
    {
      title: 'Net Inventory',
      dataIndex: 'net_inventory',
      key: 'net_inventory',
      sorter: true,
      render: (val) => (
        <span className={val < 0 ? 'text-red-500' : ''}>
          {val?.toLocaleString() || 0}
        </span>
      ),
    },
    {
      title: 'Backorder',
      dataIndex: 'backorder_qty',
      key: 'backorder_qty',
      render: (val) => (
        <span className={val > 0 ? 'text-red-500' : ''}>
          {val?.toLocaleString() || 0}
        </span>
      ),
    },
    {
      title: 'Overstock',
      dataIndex: 'overstock_qty',
      key: 'overstock_qty',
      render: (val) => (
        <span className={val > 0 ? 'text-orange-500' : ''}>
          {val?.toLocaleString() || 0}
        </span>
      ),
    },
    {
      title: 'Shortage',
      dataIndex: 'shortage_qty',
      key: 'shortage_qty',
      render: (val) => (
        <span className={val > 0 ? 'text-yellow-500' : ''}>
          {val?.toLocaleString() || 0}
        </span>
      ),
    },
  ]

  const renderAllocationView = () => (
    <div>
      {/* Allocation Summary Cards */}
      <Row gutter={16} className="mb-6">
        <Col span={6}>
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {allocations.length}
              </div>
              <div className="text-gray-500">Total Allocations</div>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {allocations.reduce((s, a) => s + (a.q_case_pack || 0), 0).toLocaleString()}
              </div>
              <div className="text-gray-500">Total Case Packs</div>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600">
                {allocations.reduce((s, a) => s + Number(a.backorder_qty || 0), 0).toLocaleString()}
              </div>
              <div className="text-gray-500">Total Backorders</div>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">
                {allocations.filter(a => a.penalty_flag).length}
              </div>
              <div className="text-gray-500">Penalty Cases</div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* Allocation Chart */}
      <Card title={<><AppstoreOutlined /> Allocation by Warehouse</>} className="mb-6">
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={warehouseStats}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="warehouse" />
            <YAxis yAxisId="left" />
            <YAxis yAxisId="right" orientation="right" />
            <Tooltip />
            <Legend />
            <Bar yAxisId="left" dataKey="totalCasePack" fill="#1890ff" name="Case Packs" />
            <Bar yAxisId="left" dataKey="totalResidual" fill="#52c41a" name="Residual Units" />
            <Line yAxisId="right" type="monotone" dataKey="avgInventory" stroke="#ff7300" name="Avg Inventory" />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>

      {/* Allocation Table */}
      <Card title={<><AppstoreOutlined /> Allocation Details</>}>
        <Table
          columns={allocationColumns}
          dataSource={allocations}
          rowKey="allocation_id"
          scroll={{ x: 800 }}
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </div>
  )

  const renderInventoryView = () => (
    <div>
      {/* Inventory Summary Cards */}
      <Row gutter={16} className="mb-6">
        <Col span={8}>
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {chartData.reduce((s, d) => s + d.net_inventory, 0).toLocaleString()}
              </div>
              <div className="text-gray-500">Total Net Inventory</div>
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">
                {chartData.reduce((s, d) => s + d.backorder_qty, 0).toLocaleString()}
              </div>
              <div className="text-gray-500">Total Backorders</div>
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600">
                {chartData.reduce((s, d) => s + d.overstock_qty, 0).toLocaleString()}
              </div>
              <div className="text-gray-500">Total Overstock</div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* Inventory Chart */}
      <Card title={<><LineChartOutlined /> Inventory Dynamics Over Time</>} className="mb-6">
        <Radio.Group
          value={viewMode}
          onChange={(e) => setViewMode(e.target.value)}
          className="mb-4"
        >
          <Radio.Button value="chart">Chart View</Radio.Button>
          <Radio.Button value="table">Table View</Radio.Button>
        </Radio.Group>

        {viewMode === 'chart' ? (
          <ResponsiveContainer width="100%" height={400}>
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time_period" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="net_inventory" fill="#1890ff" name="Net Inventory" />
              <Line type="monotone" dataKey="backorder_qty" stroke="#ff4d4f" name="Backorders" />
              <Line type="monotone" dataKey="overstock_qty" stroke="#faad14" name="Overstock" />
              <ReferenceLine y={0} stroke="#000" strokeDasharray="2 2" />
            </ComposedChart>
          </ResponsiveContainer>
        ) : (
          <Table
            columns={inventoryColumns}
            dataSource={chartData}
            rowKey="key"
            scroll={{ x: 800 }}
            pagination={{ pageSize: 20 }}
          />
        )}
      </Card>
    </div>
  )

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Allocation & Inventory Dashboard</h1>
        <p className="text-gray-600">Comprehensive view of optimization results and inventory dynamics</p>
      </div>

      {/* Run Selection */}
      <Card size="small" className="mb-6">
        <Row gutter={16} align="middle">
          <Col>
            <span className="font-medium">Run ID:</span>
          </Col>
          <Col>
            <InputNumber
              value={runIdInput}
              onChange={setRunIdInput}
              min={1}
              style={{ width: 120 }}
            />
          </Col>
          <Col>
            <Button type="primary" onClick={handleRunLoad}>Load Run</Button>
          </Col>
        </Row>
      </Card>

      {/* Filters */}
      <Card size="small" className="mb-6">
        <Row gutter={16} align="middle">
          <Col>
            <FilterOutlined /> <strong>Filters:</strong>
          </Col>
          <Col>
            <Select
              placeholder="Product"
              value={filterProduct}
              onChange={setFilterProduct}
              allowClear
              style={{ width: 150 }}
            >
              {products.map(p => (
                <Option key={p} value={p}>{p}</Option>
              ))}
            </Select>
          </Col>
          <Col>
            <Select
              placeholder="Warehouse"
              value={filterWarehouse}
              onChange={setFilterWarehouse}
              allowClear
              style={{ width: 150 }}
            >
              {warehouses.map(w => (
                <Option key={w} value={w}>{w}</Option>
              ))}
            </Select>
          </Col>
        </Row>
      </Card>

      {/* Main Content */}
      {loading && (
        <Card>
          <div className="text-center py-20">
            <Spin size="large" />
            <div className="mt-4">Loading optimization results...</div>
          </div>
        </Card>
      )}

      {error && (
        <Alert
          message="Error Loading Data"
          description={error.message}
          type="error"
          showIcon
          className="mb-6"
        />
      )}

      {!loading && !error && activeRunId && (
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          <TabPane 
            tab={<><AppstoreOutlined />Allocation Results</>} 
            key="allocation"
          >
            {renderAllocationView()}
          </TabPane>
          <TabPane 
            tab={<><LineChartOutlined />Inventory Dynamics</>} 
            key="inventory"
          >
            {renderInventoryView()}
          </TabPane>
        </Tabs>
      )}

      {!loading && !activeRunId && (
        <Card>
          <div className="text-center py-20">
            <WarningOutlined className="text-4xl text-gray-400 mb-4" />
            <div className="text-gray-500">Please select a run ID to view results</div>
          </div>
        </Card>
      )}
    </div>
  )
}

export default AllocationInventoryDashboard