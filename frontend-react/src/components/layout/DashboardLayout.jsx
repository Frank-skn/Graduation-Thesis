import React, { useState } from 'react'
import { Layout, Menu } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  DatabaseOutlined,
  BarChartOutlined,
  ExperimentOutlined,
  SwapOutlined,
  LineChartOutlined,
  BulbOutlined,
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
  TrophyOutlined,
} from '@ant-design/icons'

const { Header, Sider, Content } = Layout

const DashboardLayout = ({ children }) => {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  const menuItems = [
    {
      key: 'group-a',
      icon: <DatabaseOutlined />,
      label: 'A. Data Foundation',
      children: [
        {
          key: '/a1-data-overview',
          icon: <TableOutlined />,
          label: 'A1. Data Overview',
        },
        {
          key: '/a2-parameter-management',
          icon: <SettingOutlined />,
          label: 'A2. Parameter Management',
        },
      ],
    },
    {
      key: 'group-b',
      icon: <BarChartOutlined />,
      label: 'B. Results & Performance',
      children: [
        {
          key: '/b1-executive-summary',
          icon: <DashboardOutlined />,
          label: 'B1. Executive Summary',
        },
        {
          key: '/b2-allocation-inventory-dashboard',
          icon: <FunnelPlotOutlined />,
          label: 'B2. Allocation & Inventory Dashboard',
        },
      ],
    },
    {
      key: 'group-c',
      icon: <ExperimentOutlined />,
      label: 'C. Scenario Analysis',
      children: [
        {
          key: '/c1-scenario-management',
          icon: <ToolOutlined />,
          label: 'C1. Scenario Management',
        },
        {
          key: '/c3-scenario-comparison',
          icon: <SlidersOutlined />,
          label: 'C3. Scenario Comparison',
        },
      ],
    },
    {
      key: 'group-d',
      icon: <SwapOutlined />,
      label: 'D. Advanced Analysis',
      children: [
        {
          key: '/d1-decision-impact-scenarios',
          icon: <AimOutlined />,
          label: 'D1. Decision Impact Analysis',
        },
        {
          key: '/d2-sensitivity-analysis',
          icon: <RadarChartOutlined />,
          label: 'D2. Sensitivity Analysis',
        },
        {
          key: '/d3-parameter-stability',
          icon: <BarChartOutlined />,
          label: 'D3. Parameter Stability',
        },
      ],
    },
    {
      key: 'group-e',
      icon: <BulbOutlined />,
      label: 'E. Insights',
      children: [
        {
          key: '/e1-decision-insights',
          icon: <TrophyOutlined />,
          label: 'E1. Decision Insights',
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
