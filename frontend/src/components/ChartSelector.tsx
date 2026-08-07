import { useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { Plus, Eye } from 'lucide-react'
import type { ChartDefinition, ColumnStats } from '../types'
import { buildChartOption } from '../App'

interface ChartSelectorProps {
  availableColumns: string[]
  columnsStats: Record<string, ColumnStats>
  rows: Record<string, unknown>[]
  darkMode: boolean
  onAddChart: (chart: ChartDefinition) => void
}

const SUPPORTED_TYPES: Array<{ type: ChartDefinition['type']; label: string }> = [
  { type: 'bar', label: 'Bar Chart' },
  { type: 'horizontal_bar', label: 'Horizontal Bar Chart' },
  { type: 'line', label: 'Line Chart' },
  { type: 'area', label: 'Area Chart' },
  { type: 'pie', label: 'Pie Chart' },
  { type: 'donut', label: 'Donut Chart' },
  { type: 'histogram', label: 'Histogram' },
  { type: 'boxplot', label: 'Box Plot' },
  { type: 'scatter', label: 'Scatter Plot' },
  { type: 'heatmap', label: 'Correlation Heatmap' }
]

export function ChartVisibilitySelector({
  charts,
  hiddenChartIds,
  onToggleChart,
  onToggleAll
}: {
  charts: ChartDefinition[]
  hiddenChartIds: Set<string>
  onToggleChart: (chartId: string) => void
  onToggleAll: (showAll: boolean) => void
}) {
  const allShown = hiddenChartIds.size === 0

  const TYPE_LABELS: Record<string, string> = {
    bar: 'Bar Chart',
    horizontal_bar: 'Horizontal Bar',
    line: 'Line Chart',
    area: 'Area Chart',
    pie: 'Pie Chart',
    donut: 'Donut Chart',
    histogram: 'Histogram',
    boxplot: 'Box Plot',
    scatter: 'Scatter Plot',
    heatmap: 'Correlation Heatmap'
  }

  return (
    <div className="chart-visibility-selector animate-fade-in">
      <div className="section-heading">
        <div>
          <h3>Choose Charts to Display</h3>
          <p>Select which generated charts you would like to view.</p>
        </div>
      </div>

      <div className="show-all-bar">
        <label className={`chip show-all-chip ${allShown ? 'chip-active' : ''}`}>
          <input
            type="checkbox"
            checked={allShown}
            onChange={(e) => onToggleAll(e.target.checked)}
          />
          <strong>Show All Charts</strong>
        </label>
      </div>

      <div className="chart-checkbox-grid">
        {charts.map((chart) => {
          const isVisible = !hiddenChartIds.has(chart.id)
          return (
            <label
              key={chart.id}
              className={`chart-select-card ${isVisible ? 'selected' : ''}`}
            >
              <input
                type="checkbox"
                checked={isVisible}
                onChange={() => onToggleChart(chart.id)}
              />
              <span className="chart-select-title">{chart.title}</span>
              <span className="chart-select-type">
                ({TYPE_LABELS[chart.type] || chart.type})
              </span>
            </label>
          )
        })}
      </div>
    </div>
  )
}

export function ChartSelector({ availableColumns, columnsStats, rows, darkMode, onAddChart }: ChartSelectorProps) {
  const [xAxisCol, setXAxisCol] = useState(availableColumns[0] || '')
  const [yAxisCol, setYAxisCol] = useState(availableColumns[1] || availableColumns[0] || '')
  const [chartType, setChartType] = useState<ChartDefinition['type']>('bar')
  const [previewOpen, setPreviewOpen] = useState(false)

  // Compute preview chart definition client-side from available rows
  const previewChart = useMemo<ChartDefinition | null>(() => {
    if (!xAxisCol || !rows.length) return null

    const safeVal = (v: unknown): number => {
      const num = Number(v)
      return isNaN(num) ? 0 : num
    }

    if (chartType === 'pie' || chartType === 'donut') {
      const counts: Record<string, number> = {}
      rows.forEach((r) => {
        const k = String(r[xAxisCol] ?? 'Unknown')
        const val = yAxisCol && yAxisCol !== xAxisCol ? safeVal(r[yAxisCol]) : 1
        counts[k] = (counts[k] || 0) + val
      })
      const items = Object.entries(counts).slice(0, 10).map(([name, value]) => ({ name, value }))
      return {
        id: `custom_${Date.now()}`,
        title: `${yAxisCol || 'Count'} by ${xAxisCol}`,
        type: chartType,
        category: 'custom',
        series: [{ name: yAxisCol || 'Count', data: items }],
        description: `Custom ${chartType} chart preview.`
      }
    }

    if (chartType === 'scatter') {
      const scatterData = rows.slice(0, 300).map((r) => [safeVal(r[xAxisCol]), safeVal(r[yAxisCol])])
      return {
        id: `custom_${Date.now()}`,
        title: `${xAxisCol} vs ${yAxisCol}`,
        type: 'scatter',
        category: 'custom',
        x_label: xAxisCol,
        y_label: yAxisCol,
        series: [{ name: `${xAxisCol} vs ${yAxisCol}`, data: scatterData as [number, number][] }],
        description: `Custom scatter plot preview.`
      }
    }

    if (chartType === 'boxplot') {
      const nums = rows.map((r) => safeVal(r[yAxisCol || xAxisCol])).sort((a, b) => a - b)
      if (!nums.length) return null
      const qmin = nums[0]
      const q1 = nums[Math.floor(nums.length * 0.25)]
      const qmed = nums[Math.floor(nums.length * 0.5)]
      const q3 = nums[Math.floor(nums.length * 0.75)]
      const qmax = nums[nums.length - 1]
      return {
        id: `custom_${Date.now()}`,
        title: `Boxplot of ${yAxisCol || xAxisCol}`,
        type: 'boxplot',
        category: 'custom',
        x_axis: [yAxisCol || xAxisCol],
        y_label: yAxisCol || xAxisCol,
        series: [{ name: yAxisCol || xAxisCol, data: [[qmin, q1, qmed, q3, qmax]] }],
        description: `Custom boxplot preview.`
      }
    }

    // Default bar, line, area, horizontal_bar
    const grouped: Record<string, number> = {}
    rows.forEach((r) => {
      const k = String(r[xAxisCol] ?? '')
      if (!k) return
      const v = yAxisCol && yAxisCol !== xAxisCol ? safeVal(r[yAxisCol]) : 1
      grouped[k] = (grouped[k] || 0) + v
    })

    const x_axis = Object.keys(grouped).slice(0, 15)
    const data = x_axis.map((k) => Math.round(grouped[k] * 100) / 100)

    return {
      id: `custom_${Date.now()}`,
      title: `${yAxisCol || 'Count'} across ${xAxisCol}`,
      type: chartType,
      category: 'custom',
      x_axis,
      x_label: xAxisCol,
      y_label: yAxisCol,
      series: [{ name: yAxisCol || 'Count', data }],
      description: `Custom ${chartType} visualization.`
    }
  }, [xAxisCol, yAxisCol, chartType, rows])

  const handleAdd = () => {
    if (previewChart) {
      onAddChart(previewChart)
    }
  }

  return (
    <div className="chart-selector-panel animate-fade-in">
      <div className="filter-head">
        <h5>Manual Chart Generator & Preview</h5>
        <p>Choose X and Y axis columns to create and preview custom charts on demand</p>
      </div>

      <div className="explorer-toolbar">
        <label className="field">
          <span>X-Axis / Category Column</span>
          <select value={xAxisCol} onChange={(e) => setXAxisCol(e.target.value)}>
            {availableColumns.map((c) => (
              <option key={c} value={c}>
                {c} ({columnsStats[c]?.detected_type || 'Text'})
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Y-Axis / Metric Column</span>
          <select value={yAxisCol} onChange={(e) => setYAxisCol(e.target.value)}>
            {availableColumns.map((c) => (
              <option key={c} value={c}>
                {c} ({columnsStats[c]?.detected_type || 'Text'})
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Chart Type</span>
          <select value={chartType} onChange={(e) => setChartType(e.target.value as ChartDefinition['type'])}>
            {SUPPORTED_TYPES.map((t) => (
              <option key={t.type} value={t.type}>
                {t.label}
              </option>
            ))}
          </select>
        </label>

        <div className="action-row" style={{ paddingTop: '22px' }}>
          <button className="secondary" type="button" onClick={() => setPreviewOpen(!previewOpen)}>
            <Eye size={16} /> {previewOpen ? 'Hide Preview' : 'Preview Chart'}
          </button>
          <button className="primary" type="button" onClick={handleAdd} disabled={!previewChart}>
            <Plus size={16} /> Add to Dashboard
          </button>
        </div>
      </div>

      {previewOpen && previewChart && (
        <div className="chart-preview-box animate-fade-in">
          <h6>Chart Preview: {previewChart.title}</h6>
          <div className="preview-chart-wrap">
            <ReactECharts
              option={buildChartOption(previewChart, darkMode)}
              style={{ height: 320, width: '100%' }}
              notMerge
              lazyUpdate
            />
          </div>
        </div>
      )}
    </div>
  )
}
