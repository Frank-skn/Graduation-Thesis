import React from 'react'

/**
 * Tiêu đề trang dùng chung cho toàn bộ DSS.
 * Đảm bảo mọi trang có cùng cỡ chữ, khoảng cách và vị trí tiêu đề,
 * tránh hiện tượng "nhảy" khi chuyển tab.
 *
 * Props:
 *   icon:    React node (icon Ant Design), tùy chọn
 *   title:   string — tiêu đề chính (vd "A1. Tổng quan dữ liệu đầu vào")
 *   subtitle:string — mô tả ngắn dưới tiêu đề, tùy chọn
 *   extra:   React node — nút/điều khiển bên phải, tùy chọn
 */
const PageHeader = ({ icon, title, subtitle, extra }) => {
  return (
    <div className="page-header flex items-start justify-between mb-6">
      <div className="min-w-0">
        <h1 className="flex items-center gap-3 text-2xl font-bold text-primary-700 m-0 leading-tight">
          {icon && <span className="text-primary-600 shrink-0">{icon}</span>}
          <span className="truncate">{title}</span>
        </h1>
        {subtitle && (
          <p className="text-gray-500 text-sm mt-1 mb-0">{subtitle}</p>
        )}
      </div>
      {extra && <div className="shrink-0 ml-4">{extra}</div>}
    </div>
  )
}

export default PageHeader
