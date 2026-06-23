import React, { useState, useEffect, useRef } from 'react'
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

  const noRun = !activeRunId
  const noRunTitle = 'Chạy B1 trước để mở khoá trang này'

  const menuItems = [
    {
      key: 'group-a',
      icon: <DatabaseOutlined />,
      label: 'A. Dữ liệu & Cấu hình',
      children: [
        {
          key: '/a1-data-overview',
          icon: <TableOutlined />,
          label: 'A1. Tổng quan dữ liệu đầu vào',
        },
        {
          key: '/a2-parameter-management',
          icon: <SettingOutlined />,
          label: 'A2. Tham số mô hình',
        },
      ],
    },
    {
      key: 'group-b',
      icon: <BarChartOutlined />,
      label: 'B. Tối ưu hoá phân bổ',
      children: [
        {
          key: '/b0-run-optimization',
          icon: <ThunderboltOutlined />,
          label: 'B1. Thực thi tối ưu hoá',
        },
        {
          key: '/b1-executive-summary',
          icon: <DashboardOutlined />,
          label: noRun ? <Tooltip title={noRunTitle}>B2. Kết quả &amp; Chi phí</Tooltip> : 'B2. Kết quả & Chi phí',
          disabled: noRun,
        },
        {
          key: '/b2-allocation-inventory-dashboard',
          icon: <FunnelPlotOutlined />,
          label: noRun ? <Tooltip title={noRunTitle}>B3. Phân bổ &amp; Động thái tồn kho</Tooltip> : 'B3. Phân bổ & Động thái tồn kho',
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
      label: 'D. Phân tích độ nhạy & Rủi ro',
      children: [
        {
          key: '/d1-decision-impact-scenarios',
          icon: <AimOutlined />,
          label: 'D1. Tác động quyết định phân bổ',
        },
        {
          key: '/d2-sensitivity-analysis',
          icon: <RadarChartOutlined />,
          label: 'D2. Phân tích độ nhạy tham số',
        },
        {
          key: '/d3-parameter-stability',
          icon: <BarChartOutlined />,
          label: 'D3. Độ bền vững nghiệm tối ưu',
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
        className="shadow-xl relative"
        style={{
          background: '#1a3a52',
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
        {/* Drag handle */}
        <div
          onMouseDown={handleDragStart}
          style={{
            position: 'absolute',
            right: 0,
            top: 0,
            bottom: 0,
            width: '4px',
            cursor: 'col-resize',
            background: isDragging ? '#1890ff' : 'transparent',
            transition: isDragging ? 'none' : 'background 0.3s',
            zIndex: 1000,
          }}
          title="Kéo để điều chỉnh độ rộng menu"
        />
        
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
      <Layout style={{ marginLeft: sidebarWidth }}>
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
