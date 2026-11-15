/**
 * RequireRun – Protects the B1/B2/B3 pages.
 * If there is no optimization result yet (activeRunId == null), shows a
 * notice and a button linking back to B1 instead of rendering the page.
 */
import React from 'react'
import { Result, Button } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useAppContext } from '../context/AppContext'

export default function RequireRun({ children }) {
  const { activeRunId } = useAppContext()
  const navigate = useNavigate()

  if (!activeRunId) {
    return (
      <Result
        status="warning"
        icon={<ThunderboltOutlined style={{ color: '#faad14' }} />}
        title="No optimization result yet"
        subTitle={
          <span>
            You need to run the optimization before viewing this page.<br />
            Go to <strong>B1. Run Optimization</strong> to get started.
          </span>
        }
        extra={
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            size="large"
            onClick={() => navigate('/b1-run-optimization')}
          >
            Go to B1. Run Optimization
          </Button>
        }
      />
    )
  }

  return children
}
