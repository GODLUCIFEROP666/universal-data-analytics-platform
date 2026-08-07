import ReactECharts from 'echarts-for-react'
import { Calendar, Hash, Tag, X } from 'lucide-react'
import type { ColumnStats } from '../types'
import { buildChartOption } from '../App'

interface ColumnDetailModalProps {
  isOpen: boolean
  columnName: string | null
  stats: ColumnStats | null
  darkMode: boolean
  onClose: () => void
}

export function ColumnDetailModal({ isOpen, columnName, stats, darkMode, onClose }: ColumnDetailModalProps) {
  if (!isOpen || !columnName || !stats) return null

  const isNumeric = stats.is_numeric
  const isDate = stats.is_date
  const isCategorical = stats.is_categorical || stats.detected_type === 'Category' || stats.detected_type === 'Boolean'

  // Build mini distribution chart if distribution data exists
  const distributionChart = stats.stats?.distribution ? {
    id: `col_dist_${columnName}`,
    title: `Distribution of ${columnName}`,
    type: 'histogram' as const,
    category: 'column_detail',
    x_axis: stats.stats.distribution.buckets.map((b) => b.label),
    series: [{ name: 'Frequency', data: stats.stats.distribution.buckets.map((b) => b.count) }],
    description: `Frequency distribution across ${stats.stats.distribution.buckets.length} buckets`
  } : null

  // Top values chart for categorical/text
  const topValues = stats.top_values ?? stats.stats?.most_frequent_values ?? []
  const topValuesChart = isCategorical && topValues.length > 0 ? {
    id: `col_top_${columnName}`,
    title: `Top Frequencies for ${columnName}`,
    type: 'horizontal_bar' as const,
    category: 'column_detail',
    x_axis: topValues.slice(0, 10).map((v) => v.value),
    series: [{ name: 'Count', data: topValues.slice(0, 10).map((v) => v.count) }],
    description: 'Most frequent category occurrences'
  } : null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box column-modal-box animate-fade-in" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div className="flex-row gap-8">
            <div className="col-type-pill">
              {isNumeric ? <Hash size={16} /> : isDate ? <Calendar size={16} /> : <Tag size={16} />}
              <span>{stats.detected_type}</span>
            </div>
            <h3>Column: {columnName}</h3>
          </div>
          <button className="ghost small icon-only" type="button" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body column-modal-body">
          {/* TOP METRICS SUMMARY */}
          <div className="meta-grid col-summary-grid">
            <div className="meta-item">
              <span>Unique Count</span>
              <strong>{stats.unique_count.toLocaleString()}</strong>
            </div>
            <div className="meta-item">
              <span>Null / Missing Count</span>
              <strong>{stats.null_count.toLocaleString()} ({stats.null_percentage}%)</strong>
            </div>
            {stats.date_range && (
              <>
                <div className="meta-item">
                  <span>Earliest Date</span>
                  <strong>{stats.date_range.min_date}</strong>
                </div>
                <div className="meta-item">
                  <span>Latest Date</span>
                  <strong>{stats.date_range.max_date}</strong>
                </div>
              </>
            )}
          </div>

          {/* NUMERIC DETAILED STATS */}
          {isNumeric && stats.stats && (
            <div className="num-stats-panel">
              <h5>Numerical Descriptives</h5>
              <div className="num-stats-grid">
                <div className="stat-pill"><span>Min</span><strong>{stats.stats.min ?? 'N/A'}</strong></div>
                <div className="stat-pill"><span>Max</span><strong>{stats.stats.max ?? 'N/A'}</strong></div>
                <div className="stat-pill"><span>Mean</span><strong>{stats.stats.mean ?? 'N/A'}</strong></div>
                <div className="stat-pill"><span>Median</span><strong>{stats.stats.median ?? 'N/A'}</strong></div>
                <div className="stat-pill"><span>Std Dev</span><strong>{stats.stats.std_dev ?? 'N/A'}</strong></div>
                <div className="stat-pill"><span>Variance</span><strong>{stats.stats.variance ?? 'N/A'}</strong></div>
                <div className="stat-pill"><span>Q1 (25%)</span><strong>{stats.stats.q1 ?? 'N/A'}</strong></div>
                <div className="stat-pill"><span>Q3 (75%)</span><strong>{stats.stats.q3 ?? 'N/A'}</strong></div>
                <div className="stat-pill"><span>IQR</span><strong>{stats.stats.iqr ?? 'N/A'}</strong></div>
                <div className="stat-pill"><span>Skewness</span><strong>{stats.stats.skewness ?? 'N/A'}</strong></div>
                <div className="stat-pill"><span>Kurtosis</span><strong>{stats.stats.kurtosis ?? 'N/A'}</strong></div>
                <div className="stat-pill"><span>Outliers</span><strong>{stats.stats.outliers_count ?? 0}</strong></div>
              </div>
            </div>
          )}

          {/* DISTRIBUTION OR TOP VALUES CHART */}
          {distributionChart && (
            <div className="col-chart-box">
              <ReactECharts
                option={buildChartOption(distributionChart, darkMode)}
                style={{ height: 260, width: '100%' }}
                notMerge
                lazyUpdate
              />
            </div>
          )}

          {topValuesChart && (
            <div className="col-chart-box">
              <ReactECharts
                option={buildChartOption(topValuesChart, darkMode)}
                style={{ height: 260, width: '100%' }}
                notMerge
                lazyUpdate
              />
            </div>
          )}

          {/* TOP VALUES FREQUENCY LIST */}
          {topValues.length > 0 && (
            <div className="frequent-values-panel">
              <h5>Most Frequent Values</h5>
              <div className="mini-list">
                {topValues.slice(0, 8).map((v, i) => (
                  <div key={i} className="mini-row">
                    <span className="truncate">{v.value || '(Empty / Null)'}</span>
                    <strong>{v.count.toLocaleString()} ({v.percentage}%)</strong>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
