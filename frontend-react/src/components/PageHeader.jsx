import React from 'react'

/**
 * Shared page header used across the entire DSS.
 * Ensures every page has the same title font size, spacing and position,
 * avoiding a "jump" when switching tabs.
 *
 * Props:
 *   icon:    React node (Ant Design icon), optional
 *   title:   string — main title (e.g. "A1. Input Data Overview")
 *   subtitle:string — short description below the title, optional
 *   extra:   React node — buttons/controls on the right, optional
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
