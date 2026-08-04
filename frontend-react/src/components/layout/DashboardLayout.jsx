import React, { useState, useEffect, useRef } from 'react'
import { Layout, Menu, Tooltip, Avatar, Dropdown } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAppContext } from '../../context/AppContext'
import authService from '../../services/authService'
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
  WarningOutlined,
  SafetyOutlined,
  UserOutlined,
  LogoutOutlined,
} from '@ant-design/icons'

const { Header, Sider, Content } = Layout

const DashboardLayout = ({ children }) => {
  const [collapsed, setCollapsed] = useState(false)
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem('sidebarWidth')
    return saved ? parseInt(saved) : 300
  })
  const [isDragging, setIsDragging] = useState(false)
  const siderRef = useRef(null)
  const navigate = useNavigate()
  const location = useLocation()
  const { activeRunId } = useAppContext()

  // Save sidebar width to localStorage
  useEffect(() => {
    localStorage.setItem('sidebarWidth', sidebarWidth.toString())
  }, [sidebarWidth])

  // Handle drag resize
  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging) return
      
      const newWidth = e.clientX
      // Min 180px, Max 400px
      if (newWidth >= 180 && newWidth <= 400) {
        setSidebarWidth(newWidth)
      }
    }

    const handleMouseUp = () => {
      setIsDragging(false)
      document.body.style.cursor = 'default'
    }

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = 'col-resize'
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging])

  const handleDragStart = () => {
    setIsDragging(true)
  }

  const username = authService.getUsername() || 'admin'

  const handleLogout = () => {
    authService.logout()
    navigate('/login', { replace: true })
  }

  const userMenuItems = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Log out',
      danger: true,
      onClick: handleLogout,
    },
  ]

  const noRun = !activeRunId
  const noRunTitle = 'Run optimization (B1) first to unlock this page'

  const menuItems = [
    {
      key: 'group-a',
      icon: <DatabaseOutlined />,
      label: 'A. Data & Configuration',
      children: [
        {
          key: '/a1-data-overview',
          icon: <TableOutlined />,
          label: 'A1. Input Data Overview',
        },
        {
          key: '/a2-parameter-management',
          icon: <SettingOutlined />,
          label: 'A2. Model Parameters',
        },
      ],
    },
    {
      key: 'group-b',
      icon: <BarChartOutlined />,
      label: 'B. Allocation Optimization',
      children: [
        {
          key: '/b1-run-optimization',
          icon: <ThunderboltOutlined />,
          label: 'B1. Run Optimization',
        },
        {
          key: '/b2-executive-summary',
          icon: <DashboardOutlined />,
          label: noRun ? <Tooltip title={noRunTitle}>B2. Results &amp; Cost</Tooltip> : 'B2. Results & Cost',
          disabled: noRun,
        },
        {
          key: '/b3-allocation-inventory-dashboard',
          icon: <FunnelPlotOutlined />,
          label: noRun ? <Tooltip title={noRunTitle}>B3. Allocation &amp; Inventory Dynamics</Tooltip> : 'B3. Allocation & Inventory Dynamics',
          disabled: noRun,
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
          label: 'C1. What-If Analysis',
        },
        {
          key: '/c2-scenario-comparison',
          icon: <SlidersOutlined />,
          label: 'C2. Scenario Comparison',
        },
      ],
    },
    {
      key: 'group-d',
      icon: <SwapOutlined />,
      label: 'D. Sensitivity & Risk Analysis',
      children: [
        {
          key: '/d1-sensitivity-analysis',
          icon: <RadarChartOutlined />,
          label: 'D1. Parameter Sensitivity Analysis',
        },
        {
          key: '/d2-parameter-stability',
          icon: <BarChartOutlined />,
          label: 'D2. Solution Stability',
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
        collapsedWidth={80}
        className="relative"
        style={{
          background: '#FFFFFF',
          borderRight: '1px solid #E8EDF4',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          height: '100vh',
          overflowY: 'auto',
          zIndex: 999,
        }}
        width={sidebarWidth}
        ref={siderRef}
      >
        {/* Drag handle — only shown when sidebar is expanded */}
        {!collapsed && (
          <div
            onMouseDown={handleDragStart}
            style={{
              position: 'absolute',
              right: 0,
              top: 0,
              bottom: 0,
              width: '4px',
              cursor: 'col-resize',
              background: isDragging ? '#2563EB' : 'transparent',
              transition: isDragging ? 'none' : 'background 0.3s',
              zIndex: 1000,
            }}
            title="Drag to resize menu width"
          />
        )}

        <div className="px-4 py-5 flex items-center gap-2.5" style={{ borderBottom: '1px solid #F1F5F9' }}>
          <div style={{
            width: 34, height: 34, borderRadius: 9,
            background: 'linear-gradient(135deg, #2563EB, #3B82F6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontWeight: 700, fontSize: 13, letterSpacing: '-0.3px', flexShrink: 0,
            boxShadow: '0 2px 6px rgba(37,99,235,0.28)',
          }}>SMI</div>
          {!collapsed && (
            <div className="leading-tight">
              <div style={{ fontWeight: 700, fontSize: 16, color: '#0F172A' }}>SMI DSS</div>
              <div style={{ fontSize: 11, color: '#94A3B8' }}>Decision Support System</div>
            </div>
          )}
        </div>
        <Menu
          theme="light"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{
            background: 'transparent',
            border: 'none',
            fontSize: collapsed ? '12px' : '13px',
            marginTop: 8,
          }}
          className="custom-menu"
        />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 80 : sidebarWidth, transition: 'margin-left 0.2s', background: '#F8FAFC' }}>
        <Header
          className="flex items-center justify-between"
          style={{ padding: '0 24px', background: '#FFFFFF', borderBottom: '1px solid #E8EDF4', boxShadow: 'none' }}
        >
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="text-xl transition-colors"
            style={{ color: '#64748B' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#2563EB')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#64748B')}
          >
            {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </button>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-sm font-semibold" style={{ color: '#1E293B' }}>Single-Supplier Multi-Buyer</p>
              <p className="text-xs" style={{ color: '#94A3B8' }}>Supplier-Managed Inventory Optimization</p>
            </div>
            <div style={{ width: 1, height: 28, background: '#E2E8F0' }} />
            <Dropdown menu={{ items: userMenuItems }} trigger={['click']} placement="bottomRight">
              <div className="flex items-center gap-2" style={{ cursor: 'pointer' }}>
                <Avatar
                  size={32}
                  icon={<UserOutlined />}
                  style={{ background: 'linear-gradient(135deg, #2563EB, #3B82F6)' }}
                />
                <span className="text-sm font-medium" style={{ color: '#334155' }}>{username}</span>
              </div>
            </Dropdown>
          </div>
        </Header>
        <Content className="p-6" style={{ background: '#F8FAFC' }}>
          <div style={{ background: '#FFFFFF', borderRadius: 14, border: '1px solid #E8EDF4', padding: 24, minHeight: 'calc(100vh - 120px)' }}>
            {children}
          </div>
        </Content>
      </Layout>
    </Layout>
  )
}

export default DashboardLayout
