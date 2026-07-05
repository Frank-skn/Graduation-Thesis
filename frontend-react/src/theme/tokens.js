/**
 * Design tokens — hệ màu thống nhất cho toàn bộ DSS.
 *
 * Tone chủ đạo: ROYAL BLUE (#2563EB) — sáng, tươi, hiện đại, chuyên nghiệp.
 * Phong cách: sáng-sạch, nhiều khoảng trắng (SaaS hiện đại kiểu Stripe/Vercel).
 *
 * Nguyên tắc: "Trung tính chủ đạo, màu có kỷ luật."
 * - Brand blue cho nhấn mạnh chính (nút, link, tiêu đề, selection).
 * - Neutral xám mát cho phần lớn nền/chữ/viền và biểu đồ trung tính.
 * - Màu ngữ nghĩa (good/warn/bad) CHỈ khi mang ý nghĩa trạng thái.
 * - Data-viz ưu tiên thang xanh đơn sắc; semantic khi so sánh trạng thái.
 *
 * Mọi component NÊN import từ đây thay vì hardcode mã màu.
 */

// ── Thương hiệu (Royal Blue scale) ───────────────────────────
export const BRAND = {
  900: '#1E3A8A',
  800: '#1E40AF',
  700: '#1D4ED8',
  600: '#2563EB',   // chủ đạo — nút, nhấn mạnh
  500: '#3B82F6',   // hover / sáng hơn
  400: '#60A5FA',
  300: '#93C5FD',
  200: '#BFDBFE',
  100: '#DBEAFE',
  50:  '#EFF6FF',   // nền nhấn rất nhạt
}

// ── Trung tính (xám mát hơi ngả xanh — sáng, sạch) ───────────
export const NEUTRAL = {
  900: '#0F172A',   // tiêu đề đậm (slate-900)
  800: '#1E293B',
  700: '#334155',   // chữ chính
  600: '#475569',   // chữ phụ
  500: '#64748B',
  400: '#94A3B8',
  300: '#CBD5E1',   // viền
  200: '#E2E8F0',
  100: '#F1F5F9',
  50:  '#F8FAFC',   // nền trang
  white: '#ffffff',
}

// ── Ngữ nghĩa (tươi vừa phải, hợp nền sáng) ──────────────────
export const SEMANTIC = {
  good:   '#16A34A',   // xanh lá — an toàn / tiết kiệm
  goodBg: '#F0FDF4',
  warn:   '#D97706',   // hổ phách — cảnh báo
  warnBg: '#FFFBEB',
  bad:    '#DC2626',   // đỏ — rủi ro / nợ đơn
  badBg:  '#FEF2F2',
  info:   '#2563EB',   // xanh brand — thông tin
  infoBg: '#EFF6FF',
}

// ── Thang đơn sắc cho biểu đồ (chuỗi cùng loại) ──────────────
export const SEQUENTIAL = [
  '#1D4ED8', '#2563EB', '#3B82F6', '#60A5FA', '#93C5FD', '#BFDBFE',
]

// ── Bảng màu phân loại (hài hòa, cùng độ tươi, hợp nền sáng) ──
export const CATEGORICAL = [
  '#2563EB', // blue
  '#0D9488', // teal
  '#7C3AED', // violet
  '#EA580C', // orange
  '#0891B2', // cyan
  '#DB2777', // pink
]

// ── Ánh xạ ngữ nghĩa cho các thành phần chi phí ──────────────
// Nợ đơn = thành phần chi phối/rủi ro → đỏ nổi bật.
// Còn lại dùng sắc độ blue/neutral để không loạn màu.
export const COST_COLORS = {
  backorder: SEMANTIC.bad,      // nợ đơn (chi phối)
  shortage:  SEMANTIC.warn,     // thiếu hụt
  overstock: BRAND[500],        // tồn kho vượt mức
  penalty:   NEUTRAL[400],      // phạt đóng gói
  transship: BRAND[300],        // điều chuyển ngang
}

// ── Ngưỡng an toàn SI/SS ─────────────────────────────────────
export const SI_COLORS = {
  safe: SEMANTIC.good,   // SI >= 1
  warn: SEMANTIC.warn,   // 0.8 <= SI < 1
  risk: SEMANTIC.bad,    // SI < 0.8
}

// Màu lưới/trục biểu đồ
export const CHART_GRID = NEUTRAL[200]
export const CHART_AXIS = NEUTRAL[500]

// ── Sidebar (nền sáng, không còn navy tối) ───────────────────
export const SIDEBAR = {
  bg:          '#FFFFFF',   // nền trắng sạch
  border:      '#E8EDF4',
  itemText:    '#475569',
  itemHover:   '#F1F5F9',
  itemActive:  '#EFF6FF',   // nền xanh rất nhạt khi chọn
  itemActiveText: '#2563EB',
  groupText:   '#0F172A',
  brandText:   '#2563EB',
}

export default {
  BRAND, NEUTRAL, SEMANTIC, SEQUENTIAL, CATEGORICAL,
  COST_COLORS, SI_COLORS, CHART_GRID, CHART_AXIS, SIDEBAR,
}
