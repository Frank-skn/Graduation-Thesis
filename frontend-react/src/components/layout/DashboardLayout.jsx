import React, { useState } from 'react'
import { Layout, Menu, Tooltip } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAppContext } from '../../context/AppContext'
import {
  DatabaseOutlined,
  BarChartOutlined,
  ExperimentOutlined,
  SwapOutlined,
  LineChartOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SettingOutlined,
  TableOutlined,
  HistoryOutlined,
  DashboardOutlined,
  FunnelPlotOutlined,
  StockOutlined,
  ToolOutlined,
  ThunderboltOutlined,
  SlidersOutlined,
  RadarChartOutlined,
  AimOutlined,
  WarningOutlined,
  SafetyOutlined,
} from '@ant-design/icons'

const { Header, Sider, Content } = Layout

const DashboardLayout = ({ children }) => {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { activeRunId } = useAppContext()

  const noRun = !activeRunId
  const noRunTitle = 'Chạy B1 trước để mở khoá trang này'

  const menuItems = [
    {
      key: 'group-a',
      icon: <DatabaseOutlined />,
      label: 'A. Dữ liệu nền',
      children: [
        {
          key: '/a1-data-overview',
          icon: <TableOutlined />,
          label: 'A1. Tổng quan dữ liệu',
        },
        {
          key: '/a2-parameter-management',
          icon: <SettingOutlined />,
          label: 'A2. Quản lý tham số',
        },
      ],
    },
    {
      key: 'group-b',
      icon: <BarChartOutlined />,
      label: 'B. Tối ưu & Kết quả',
      children: [
        {
          key: '/b0-run-optimization',
          icon: <ThunderboltOutlined />,
          label: 'B1. Chạy tối ưu hoá',
        },
        {
          key: '/b1-executive-summary',
          icon: <DashboardOutlined />,
          label: noRun ? <Tooltip title={noRunTitle}>B2. Tóm tắt &amp; Chi tiết</Tooltip> : 'B2. Tóm tắt & Chi tiết',
          disabled: noRun,
        },
        {
          key: '/b2-allocation-inventory-dashboard',
          icon: <FunnelPlotOutlined />,
          label: noRun ? <Tooltip title={noRunTitle}>B3. Phân bổ &amp; Tồn kho</Tooltip> : 'B3. Phân bổ & Tồn kho',
          disabled: noRun,
        },
      ],
    },
    {
      key: 'group-c',
      icon: <ExperimentOutlined />,
      label: 'C. Phân tích kịch bản',
      children: [
        {
          key: '/c1-scenario-management',
          icon: <ToolOutlined />,
          label: 'C1. Phân tích What-If',
        },
        {
          key: '/c3-scenario-comparison',
          icon: <SlidersOutlined />,
          label: 'C2. So sánh kịch bản',
        },
      ],
    },
    {
      key: 'group-d',
      icon: <SwapOutlined />,
      label: 'D. Phân tích nâng cao',
      children: [
        {
          key: '/d1-decision-impact-scenarios',
          icon: <AimOutlined />,
          label: 'D1. Tác động quyết định',
        },
        {
          key: '/d2-sensitivity-analysis',
          icon: <RadarChartOutlined />,
          label: 'D2. Phân tích độ nhạy',
        },
        {
          key: '/d3-parameter-stability',
          icon: <BarChartOutlined />,
          label: 'D3. Ổn định tham số',
        },
      ],
    },
  ]

  const handleMenuClick = ({ key }) => {
    // Only navigate if it's a leaf item (starts with '/')
    if (key.startsWith('/')) {
      navigate(key)
    }
  }

  return (
    <Layout className="min-h-screen">
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        className="shadow-xl"
        style={{
          background: '#1a3a52',
        }}
        width={280}
      >
        <div className="p-4 text-center">
          <h1 className={`text-white font-bold transition-all ${collapsed ? 'text-lg' : 'text-xl'}`}>
            {collapsed ? 'SMI' : 'SMI DSS'}
          </h1>
          {!collapsed && (
            <p className="text-accent-300 text-xs mt-1">Decision Support System</p>
          )}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{
            background: 'transparent',
            border: 'none',
            fontSize: collapsed ? '12px' : '13px',
          }}
          className="custom-menu"
        />
      </Sider>
      <Layout>
        <Header
          className="bg-white shadow-sm px-6 flex items-center justify-between"
          style={{ padding: '0 24px' }}
        >
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="text-2xl text-primary-500 hover:text-primary-700 transition-colors"
          >
            {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </button>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-sm font-semibold text-primary-700">Single-Supplier Multi-Buyer</p>
              <p className="text-xs text-gray-500">Supplier-Managed Inventory Optimization</p>
            </div>
          </div>
        </Header>
        <Content className="p-6 bg-gray-50">
          <div className="bg-white rounded-lg shadow-sm p-6 min-h-[calc(100vh-120px)]">
            {children}
          </div>
        </Content>
      </Layout>
    </Layout>
  )
}

export default DashboardLayout
