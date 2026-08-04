/**
 * Design tokens — unified color system for the entire DSS.
 *
 * Primary tone: ROYAL BLUE (#2563EB) — bright, fresh, modern, professional.
 * Style: light-and-clean, generous whitespace (modern SaaS look, Stripe/Vercel-style).
 *
 * Principle: "Neutral by default, color with discipline."
 * - Brand blue for primary emphasis (buttons, links, titles, selection).
 * - Cool neutral gray for most backgrounds/text/borders and neutral charts.
 * - Semantic colors (good/warn/bad) ONLY when they carry status meaning.
 * - Data-viz prefers a monochrome blue scale; semantic colors for state comparisons.
 *
 * All components SHOULD import from here instead of hardcoding color codes.
 */

// ── Brand (Royal Blue scale) ───────────────────────────
export const BRAND = {
  900: '#1E3A8A',
  800: '#1E40AF',
  700: '#1D4ED8',
  600: '#2563EB',   // primary — buttons, emphasis
  500: '#3B82F6',   // hover / brighter
  400: '#60A5FA',
  300: '#93C5FD',
  200: '#BFDBFE',
  100: '#DBEAFE',
  50:  '#EFF6FF',   // very light accent background
}

// ── Neutral (cool gray with a slight blue tint — light, clean) ───────────
export const NEUTRAL = {
  900: '#0F172A',   // dark heading (slate-900)
  800: '#1E293B',
  700: '#334155',   // primary text
  600: '#475569',   // secondary text
  500: '#64748B',
  400: '#94A3B8',
  300: '#CBD5E1',   // border
  200: '#E2E8F0',
  100: '#F1F5F9',
  50:  '#F8FAFC',   // page background
  white: '#ffffff',
}

// ── Semantic (bright and legible, still enough contrast) ─────────
// Rule: the plain `*` variant is for MARKS/accent backgrounds (brighter); `*Text`
// is used for TEXT on a white background (darker, for >= 4.5:1 legibility). `*Bg` is a light secondary background.
export const SEMANTIC = {
  good:     '#1BAE4B',   // bright green — safe / savings (mark/background)
  goodText: '#15803D',   // dark green — for small text (>=4.5:1)
  goodBg:   '#F0FDF4',
  warn:     '#F59E0B',   // bright amber — warning (mark/background)
  warnText: '#B45309',   // dark amber — for small text
  warnBg:   '#FFFBEB',
  bad:      '#EF4444',   // bright red — risk / backorder (mark/background)
  badText:  '#DC2626',   // dark red — for small text
  badBg:    '#FEF2F2',
  info:     '#3B82F6',   // bright brand blue — informational
  infoText: '#1D4ED8',
  infoBg:   '#EFF6FF',
}

// ── Monochrome scale for charts (single-series) ──────────────
export const SEQUENTIAL = [
  '#1D4ED8', '#2563EB', '#3B82F6', '#60A5FA', '#93C5FD', '#BFDBFE',
]

// ── Categorical palette (harmonious, consistent brightness, fits light background) ──
export const CATEGORICAL = [
  '#2563EB', // blue
  '#0D9488', // teal
  '#7C3AED', // violet
  '#EA580C', // orange
  '#0891B2', // cyan
  '#EF4444', // bright red (matches semantic bad — used for the 6th category)
]

// ── Semantic mapping for cost components ──────────────
// Backorder = the dominant/risk-driving component → highlighted in red.
// The rest use blue/neutral shades to avoid visual clutter.
export const COST_COLORS = {
  backorder: SEMANTIC.bad,      // backorder (dominant)
  shortage:  SEMANTIC.warn,     // shortage
  overstock: BRAND[500],        // overstock
  penalty:   NEUTRAL[400],      // packing penalty
  transship: BRAND[300],        // lateral transshipment
}

// ── SI/SS safety thresholds ─────────────────────────────────
export const SI_COLORS = {
  safe: SEMANTIC.good,   // SI >= 1
  warn: SEMANTIC.warn,   // 0.8 <= SI < 1
  risk: SEMANTIC.bad,    // SI < 0.8
}

// Chart grid/axis colors
export const CHART_GRID = NEUTRAL[200]
export const CHART_AXIS = NEUTRAL[500]

// ── Sidebar (light background, no longer dark navy) ───────────────────
export const SIDEBAR = {
  bg:          '#FFFFFF',   // clean white background
  border:      '#E8EDF4',
  itemText:    '#475569',
  itemHover:   '#F1F5F9',
  itemActive:  '#EFF6FF',   // very light blue background when selected
  itemActiveText: '#2563EB',
  groupText:   '#0F172A',
  brandText:   '#2563EB',
}

export default {
  BRAND, NEUTRAL, SEMANTIC, SEQUENTIAL, CATEGORICAL,
  COST_COLORS, SI_COLORS, CHART_GRID, CHART_AXIS, SIDEBAR,
}
