/**
 * RequireRun – Bảo vệ trang B1/B2/B3
 * Nếu chưa có kết quả tối ưu (activeRunId == null), hiển thị thông báo
 * và nút dẫn về B0 thay vì render nội dung trang.
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
        title="Chưa có kết quả tối ưu hoá"
        subTitle={
          <span>
            Bạn cần chạy tối ưu hoá trước khi xem trang này.<br />
            Hãy đến <strong>B0. Chạy Tối Ưu Hoá</strong> để bắt đầu.
          </span>
        }
        extra={
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            size="large"
            onClick={() => navigate('/b0-run-optimization')}
          >
            Đến B0. Chạy Tối Ưu Hoá
          </Button>
        }
      />
    )
  }

  return children
}
