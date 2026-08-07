export type Severity = 'info' | 'success' | 'warning' | 'error'

export interface InsightItem {
  type: string
  title: string
  description: string
  severity: Severity
}

export interface ColumnStats {
  name: string
  detected_type: string
  is_numeric: boolean
  is_date: boolean
  is_categorical: boolean
  is_id: boolean
  exclude_from_charts: boolean
  null_count: number
  null_percentage: number
  unique_count: number
  stats?: {
    min?: number
    max?: number
    mean?: number
    median?: number
    mode?: number
    variance?: number
    std_dev?: number
    q1?: number
    q3?: number
    iqr?: number
    outliers_count?: number
    skewness?: number
    kurtosis?: number
    most_frequent_values?: Array<{ value: string; count: number; percentage: number }>
    least_frequent_values?: Array<{ value: string; count: number; percentage: number }>
    distribution?: { type: string; buckets: Array<{ label: string; count: number }> }
  }
  top_values?: Array<{ value: string; count: number; percentage: number }>
  bottom_values?: Array<{ value: string; count: number; percentage: number }>
  date_range?: { min_date: string; max_date: string }
}

export interface SummaryStats {
  total_rows: number
  total_columns: number
  missing_values: number
  missing_percentage: number
  duplicate_rows: number
  memory_usage_mb: number
  numeric_columns_count: number
  categorical_columns_count: number
  date_columns_count: number
  boolean_columns_count?: number
  analysis_time_ms: number
}

export interface AnalysisResponse {
  summary: SummaryStats
  columns: Record<string, ColumnStats>
  correlations: { columns: string[]; values: number[][] } | Record<string, never>
  insights: InsightItem[]
}

export interface ChartSeriesItem {
  name: string
  data: Array<number | number[] | [number, number] | { name: string; value: number }>
}

export interface ChartDefinition {
  id: string
  title: string
  type: 'bar' | 'horizontal_bar' | 'pie' | 'donut' | 'line' | 'area' | 'histogram' | 'scatter' | 'stacked_bar' | 'heatmap' | 'boxplot'
  category: string
  x_axis?: string[]
  y_axis?: string[]
  x_label?: string | null
  y_label?: string | null
  series: ChartSeriesItem[]
  description: string
}

export interface TablePage {
  rows: Record<string, unknown>[]
  page: number
  page_size: number
  total_rows: number
  total_pages: number
}

export interface AnalysisEnvelope {
  filename: string
  sheet_name: string | null
  analysis: AnalysisResponse
  charts: ChartDefinition[]
  table: TablePage
  available_columns: string[]
}

export interface UploadInspection {
  filename: string
  format: string
  sheets: string[]
  selected_sheet: string
  size_bytes: number
}

export interface FilterState {
  search_query: string
  category_filters: Record<string, string[]>
  numeric_ranges: Record<string, { min?: number; max?: number }>
  date_ranges: Record<string, { start?: string; end?: string }>
  sort_by: string
  sort_direction: 'asc' | 'desc'
  page: number
  page_size: number
}

export interface DashboardState {
  started: boolean
  file: File | null
  inspection: UploadInspection | null
  analysis: AnalysisEnvelope | null
  loading: boolean
  loadingMessage: string
  filters: FilterState
  sheetName: string
  error: string | null
  darkMode: boolean
}

export interface AdminAuthResponse {
  token: string
  username: string
}

export interface AdminStats {
  total_visitors: number
  total_uploads: number
  total_analyses: number
  active_users: number
}
