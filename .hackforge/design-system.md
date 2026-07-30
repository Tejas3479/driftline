<!-- Source: hackforge-design | Confidence: [STRONG] | Version: v1 | Checkpoint: design-complete | Dependencies: blueprint.md -->
# Design System: Driftline

## Visual Aesthetics & Philosophy
Driftline targets enterprise financial operations, data engineers, and executives. The UI design emphasizes precision, high data density, glassmorphism cards, vibrant status accents, dynamic Plotly visual interactions, and dark mode native aesthetics.

## Color Tokens & Palette
```css
:root {
  --bg-primary: #0F172A;        /* Slate 900 */
  --bg-secondary: #1E293B;      /* Slate 800 */
  --bg-card: rgba(30, 41, 59, 0.7); /* Slate 800 with glass opacity */
  --border-card: #334155;      /* Slate 700 */
  
  --text-primary: #F8FAFC;      /* Slate 50 */
  --text-secondary: #94A3B8;    /* Slate 400 */
  --text-muted: #64748B;        /* Slate 500 */
  
  /* Brand Accent Colors */
  --accent-purple: #8B5CF6;     /* Purple 500 - Forecasting Bands */
  --accent-blue: #3B82F6;       /* Blue 500 - Trend Lines */
  --accent-cyan: #06B6D4;       /* Cyan 500 - Interactive Highlights */
  
  /* Severity / Anomaly Status Badges */
  --status-critical: #EF4444;   /* Red 500 (Severity >= 80) */
  --status-warning: #F59E0B;    /* Amber 500 (Severity 50..79) */
  --status-info: #3B82F6;       /* Blue 500 (Severity < 50) */
  --status-good: #10B981;       /* Emerald 500 (Normal / Improvement) */
}
```

## Typography Scale
- `font-sans`: Inter / System UI, `-apple-system`, BlinkMacSystemFont, "Segoe UI", Roboto.
- `font-mono`: JetBrains Mono / Fira Code (Used for numerical deltas, z-scores, MAPE percentages, and matrix indices).
- `h1`: `text-2xl font-bold tracking-tight text-slate-50`
- `h2`: `text-xl font-semibold text-slate-100`
- `h3`: `text-lg font-medium text-slate-200`
- `body`: `text-sm text-slate-300`
- `caption`: `text-xs font-mono text-slate-400`

## Core Component Specifications

### 1. Metric Overview Cards (`OverviewCard.tsx`)
- **Structure**: Glassmorphic container with 1px border (`border-slate-800`), metric name, unit, latest 30-day value, inline SVG sparkline, and anomaly alert counter badge.
- **States**: Loading skeleton (`animate-pulse`), zero metrics state with CTA button.

### 2. Time-Series Plotly Chart (`MetricChart.tsx`)
- **Main Trace**: Dark mode styled plot with `#3B82F6` actual value line, `#64748B` trend line, and shaded confidence bounds (`trend ± MAD`).
- **Anomaly Markers**: Marker shapes differentiated by anomaly type:
  - Spike / Dip: Filled colored circles with severity tooltips.
  - Level Shift: Vertical threshold reference lines.
  - Volatility: Shaded region highlight.
- **Forecast Projections**: Purple dashed median line (`#8B5CF6`) with shaded `$p_{10}\dots p_{90}$` band extending into future dates.

### 3. Anomaly Detail Waterfall & Segment Bar (`SegmentBarChart.tsx`)
- **Layout**: Ranked horizontal bar chart displaying dimensional segment deltas ($\Delta_s$).
- **Color Logic**: Direction-aware coloring (Green for favorable shifts, Red for unfavorable shifts according to `metric.direction_good`).

### 4. Segment Comparison Small-Multiples (`SegmentComparisonChart.tsx`)
- **Engine**: Client-side `vega-embed` mounting Altair-generated Vega-Lite JSON specification.
- **Faceting**: Multi-column grid with aligned, locked y-axis scale bounds.

## Interactive Micro-Animations & Accessibility
- **Hover Effects**: Subtitle cards shift slightly upward (`hover:-translate-y-0.5 transition-all duration-200`).
- **Focus Rings**: All interactive controls carry high-contrast focus rings (`focus:ring-2 focus:ring-purple-500 focus:outline-none`).
- **Screen Reader Support**: ARIA tags on anomaly tables and form controls (`aria-label`, `role="status"`).
