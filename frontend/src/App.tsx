import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode, type DragEvent } from 'react'
import html2canvas from 'html2canvas'
import jsPDF from 'jspdf'
import ReactECharts from 'echarts-for-react'
import {
  AlertTriangle,
  BarChart3,
  Calendar,
  CheckSquare,
  CircleGauge,
  Columns,
  Copy,
  Download,
  EyeOff,
  FileImage,
  FileSpreadsheet,
  FileText,
  Filter,
  HardDrive,
  Hash,
  Maximize2,
  Minimize2,
  MoonStar,
  Percent,
  RefreshCw,
  Rows,
  Search,
  SunMedium,
  Tags,
  Upload,
  UserCheck,
  X
} from 'lucide-react'

import { analyzeDataset, exportProcessedCsv, exportProcessedExcel, inspectUpload, resetRemoteState, sessionStart, sessionEndBeacon } from './lib/api'
import type { ChartDefinition, DashboardState, FilterState, InsightItem } from './types'
import { StartScreen } from './components/StartScreen'
import { AdminLoginModal } from './components/AdminLoginModal'
import { AdminDashboard } from './components/AdminDashboard'
import { ChartSelector, ChartVisibilitySelector } from './components/ChartSelector'
import { ColumnDetailModal } from './components/ColumnDetailModal'
import './App.css'

const EMPTY_FILTERS: FilterState = {
  search_query: '',
  category_filters: {},
  numeric_ranges: {},
  date_ranges: {},
  sort_by: '',
  sort_direction: 'desc',
  page: 1,
  page_size: 25
}

const STEPS = [
  'Reading File...',
  'Detecting Column Types...',
  'Computing Summary Statistics...',
  'Recommending Visualizations...',
  'Preparing Interactive Dashboard...'
]

const INITIAL: DashboardState = {
  started: false,
  file: null,
  inspection: null,
  analysis: null,
  loading: false,
  loadingMessage: '',
  filters: EMPTY_FILTERS,
  sheetName: '',
  error: null,
  darkMode: false
}

function App() {
  const dashboardRef = useRef<HTMLDivElement | null>(null)
  const chartRefs = useRef<Record<string, ReactECharts | null>>({})
  const abortControllerRef = useRef<AbortController | null>(null)

  const [state, setState] = useState<DashboardState>(INITIAL)
  const [isDragging, setIsDragging] = useState(false)
  const [visibleCols, setVisibleCols] = useState<Record<string, boolean>>({})

  // Admin & Custom Chart state
  const [adminLoginOpen, setAdminLoginOpen] = useState(false)
  const [adminDashOpen, setAdminDashOpen] = useState(false)
  const [adminToken, setAdminToken] = useState<string | null>(null)
  const [adminUsername, setAdminUsername] = useState('')

  const [customCharts, setCustomCharts] = useState<ChartDefinition[]>([])
  const [hiddenChartIds, setHiddenChartIds] = useState<Set<string>>(new Set())
  const [selectedColDetail, setSelectedColDetail] = useState<string | null>(null)

  // Session unload listener
  useEffect(() => {
    const handleUnload = () => {
      sessionEndBeacon()
    }
    window.addEventListener('beforeunload', handleUnload)
    return () => window.removeEventListener('beforeunload', handleUnload)
  }, [])

  const handleStart = async () => {
    await sessionStart()
    setState((p) => ({ ...p, started: true }))
  }

  // Apply Dark Mode class to <html>
  useEffect(() => {
    document.documentElement.classList.toggle('dark', state.darkMode)
  }, [state.darkMode])

  // Initialize visible columns when new analysis arrives
  useEffect(() => {
    const cols = state.analysis?.analysis.columns
    if (!cols) return
    setVisibleCols(Object.fromEntries(Object.keys(cols).map((c) => [c, true])))
  }, [state.analysis])

  const runAnalysisWithState = useCallback(async (currentFile: File, sheetName: string, filters: FilterState) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    const controller = new AbortController()
    abortControllerRef.current = controller

    setState((p) => ({ ...p, loading: true, loadingMessage: STEPS[0], error: null }))

    let stepIdx = 0
    const timerId = window.setInterval(() => {
      stepIdx = Math.min(stepIdx + 1, STEPS.length - 1)
      setState((p) => ({ ...p, loadingMessage: STEPS[stepIdx] }))
    }, 400)

    try {
      const analysisData = await analyzeDataset(
        currentFile,
        { ...filters, sheet_name: sheetName },
        controller.signal
      )
      setState((p) => ({ ...p, analysis: analysisData, loading: false, loadingMessage: '' }))
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return
      setState((p) => ({
        ...p,
        loading: false,
        loadingMessage: '',
        error: err instanceof Error ? err.message : 'Analysis request failed.'
      }))
    } finally {
      window.clearInterval(timerId)
    }
  }, [])

  const handleFileSelection = async (selectedFile: File) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    setState((p) => ({
      ...p,
      file: selectedFile,
      inspection: null,
      analysis: null,
      filters: EMPTY_FILTERS,
      sheetName: '',
      error: null,
      loading: true,
      loadingMessage: 'Inspect Uploaded File...'
    }))

    try {
      const inspection = await inspectUpload(selectedFile)
      const selectedSheet = inspection.selected_sheet || ''

      setState((p) => ({
        ...p,
        inspection,
        sheetName: selectedSheet,
        filters: { ...EMPTY_FILTERS, page_size: 25 }
      }))

      // Automatically run analysis after inspection
      void runAnalysisWithState(selectedFile, selectedSheet, EMPTY_FILTERS)
    } catch (err: unknown) {
      setState((p) => ({
        ...p,
        loading: false,
        loadingMessage: '',
        error: err instanceof Error ? err.message : 'Failed to inspect file.'
      }))
    }
  }

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const onDragLeave = () => {
    setIsDragging(false)
  }

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    const files = e.dataTransfer.files
    if (files && files.length > 0) {
      const file = files[0]
      const ext = file.name.split('.').pop()?.toLowerCase()
      if (ext && ['csv', 'xls', 'xlsx'].includes(ext)) {
        void handleFileSelection(file)
      } else {
        setState((p) => ({ ...p, error: 'Invalid file format. Please upload CSV, XLS, or XLSX.' }))
      }
    }
  }

  const patchFilters = (patch: Partial<FilterState>) => {
    setState((p) => {
      const updatedFilters = { ...p.filters, ...patch, page: patch.page ?? 1 }
      if (p.file) {
        void runAnalysisWithState(p.file, p.sheetName || p.inspection?.selected_sheet || '', updatedFilters)
      }
      return { ...p, filters: updatedFilters }
    })
  }

  const toggleCategory = (column: string, value: string, checked: boolean) => {
    setState((p) => {
      const currentSet = new Set(p.filters.category_filters[column] ?? [])
      if (checked) {
        currentSet.add(value)
      } else {
        currentSet.delete(value)
      }
      const updatedFilters: FilterState = {
        ...p.filters,
        category_filters: { ...p.filters.category_filters, [column]: [...currentSet] },
        page: 1
      }
      if (p.file) {
        void runAnalysisWithState(p.file, p.sheetName || p.inspection?.selected_sheet || '', updatedFilters)
      }
      return { ...p, filters: updatedFilters }
    })
  }

  const onSheetChange = (sheet: string) => {
    setState((p) => {
      const updatedState = { ...p, sheetName: sheet }
      if (p.file) {
        void runAnalysisWithState(p.file, sheet, p.filters)
      }
      return updatedState
    })
  }

  const analyzeClick = () => {
    if (state.file) {
      void runAnalysisWithState(state.file, state.sheetName || state.inspection?.selected_sheet || '', state.filters)
    }
  }

  const resetClick = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    setVisibleCols({})
    setState({ ...INITIAL, darkMode: state.darkMode })
    await resetRemoteState()
  }

  const toggleChartVisibility = (chartId: string) => {
    setHiddenChartIds((prev) => {
      const next = new Set(prev)
      if (next.has(chartId)) {
        next.delete(chartId)
      } else {
        next.add(chartId)
      }
      return next
    })
  }

  const toggleAllCharts = (showAll: boolean) => {
    if (showAll) {
      setHiddenChartIds(new Set())
    } else {
      const allIds = [...charts, ...customCharts].map((c) => c.id)
      setHiddenChartIds(new Set(allIds))
    }
  }

  const exportExcel = async () => {
    if (!state.file) return
    try {
      const blob = await exportProcessedExcel(state.file, {
        ...state.filters,
        sheet_name: state.sheetName || state.inspection?.selected_sheet || ''
      })
      downloadBlob(blob, `Analyzed_${state.file.name.replace(/\.[^.]+$/, '')}.xlsx`)
    } catch (err: unknown) {
      setState((p) => ({ ...p, error: err instanceof Error ? err.message : 'Export failed.' }))
    }
  }

  const exportCsv = async () => {
    if (!state.file) return
    try {
      const blob = await exportProcessedCsv(state.file, {
        ...state.filters,
        sheet_name: state.sheetName || state.inspection?.selected_sheet || ''
      })
      downloadBlob(blob, `Filtered_${state.file.name.replace(/\.[^.]+$/, '')}.csv`)
    } catch (err: unknown) {
      setState((p) => ({ ...p, error: err instanceof Error ? err.message : 'Export failed.' }))
    }
  }

  const [exporting, setExporting] = useState(false)
  const [exportStatus, setExportStatus] = useState('')

  const exportDashboard = async (format: 'png' | 'pdf') => {
    const dashboard = dashboardRef.current
    if (!dashboard) return

    setExporting(true)
    setExportStatus('Waiting for all charts to finish rendering...')

    try {
      // ── Step 1: Wait for all ECharts instances to finish rendering ──────────
      const echartsInstances = Object.values(chartRefs.current)
        .map((ref) => ref?.getEchartsInstance())
        .filter(Boolean)

      await Promise.all(
        echartsInstances.map(
          (instance) =>
            new Promise<void>((resolve) => {
              if (!instance || instance.isDisposed()) { resolve(); return }
              if ((instance as any).isFinished && (instance as any).isFinished()) { resolve(); return }
              const timeout = setTimeout(() => resolve(), 3000)
              instance.on('finished', function handler() {
                clearTimeout(timeout)
                instance.off('finished', handler)
                resolve()
              })
              instance.resize()
            })
        )
      )

      // Flush paints
      await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))

      const sanitizeClonedDom = (_clonedDoc: Document, clonedEl: HTMLElement) => {
        const allElements = clonedEl.querySelectorAll<HTMLElement>('*')
        allElements.forEach((el) => {
          if (!el.style) return
          if (el.style.backdropFilter) el.style.backdropFilter = 'none'
          const styleObj = el.style as unknown as Record<string, unknown>
          if (styleObj.webkitBackdropFilter) styleObj.webkitBackdropFilter = 'none'

          try {
            const computed = window.getComputedStyle(el)
            const propsToSanitize = ['backgroundColor', 'color', 'borderColor', 'background', 'border']
            propsToSanitize.forEach((prop) => {
              const val = computed.getPropertyValue(prop)
              if (val && (val.includes('color(') || val.includes('color-mix('))) {
                el.style.setProperty(prop, 'transparent', 'important')
              }
            })
          } catch {
            // Ignore errors reading computed styles on disconnected nodes
          }
        })
      }

      // ── PNG Export Branch ────────────────────────────────────────────────
      if (format === 'png') {
        setExportStatus('Capturing high-resolution dashboard canvas...')

        const fullWidth  = dashboard.scrollWidth
        const fullHeight = dashboard.scrollHeight
        const prevOverflow  = dashboard.style.overflow
        const prevHeight    = dashboard.style.height
        const prevMaxHeight = dashboard.style.maxHeight

        dashboard.style.overflow  = 'visible'
        dashboard.style.height    = `${fullHeight}px`
        dashboard.style.maxHeight = 'none'

        const canvas = await html2canvas(dashboard, {
          backgroundColor: state.darkMode ? '#07111f' : '#ffffff',
          scale: 2,
          useCORS: true,
          allowTaint: true,
          logging: false,
          scrollX: 0,
          scrollY: -window.scrollY,
          windowWidth:  fullWidth,
          windowHeight: fullHeight,
          width:  fullWidth,
          height: fullHeight,
          onclone: (_clonedDoc, clonedEl) => {
            ;(clonedEl as HTMLElement).style.overflow  = 'visible'
            ;(clonedEl as HTMLElement).style.height    = `${fullHeight}px`
            ;(clonedEl as HTMLElement).style.maxHeight = 'none'
            sanitizeClonedDom(_clonedDoc, clonedEl as HTMLElement)
          }
        })

        dashboard.style.overflow  = prevOverflow
        dashboard.style.height    = prevHeight
        dashboard.style.maxHeight = prevMaxHeight

        const blob = await canvasToBlob(canvas)
        return downloadBlob(blob, `dashboard_${Date.now()}.png`)
      }

      // ── PDF Export Branch ─────────────────────────────────────────────────
      // Strategy:
      //  1. Scroll to top, expand dashboard to full height
      //  2. Measure ALL block positions via getBoundingClientRect (now accurate
      //     because scroll=0 and layout is fully expanded)
      //  3. Capture full-dashboard canvas in the same DOM state
      //  4. Restore scroll + styles
      //  5. Slice the canvas at measured boundaries → assemble PDF
      //
      // Critical ordering: positions are measured in the SAME state as the
      // canvas capture, so pixel coordinates always match the canvas pixels.
      // ─────────────────────────────────────────────────────────────────────

      setExportStatus('Preparing PDF export...')
      const MARGIN_MM = 8
      const A4_W_MM   = 210
      const A4_H_MM   = 297
      const printW_MM = A4_W_MM - MARGIN_MM * 2   // 194 mm
      const printH_MM = A4_H_MM - MARGIN_MM * 2   // 281 mm
      const SCALE     = 2                          // html2canvas pixel scale
      const GAP_MM    = 4                          // vertical gap between blocks

      // ── Step A: scroll to top ────────────────────────────────────────────
      const savedScrollY = window.scrollY
      window.scrollTo({ top: 0, behavior: 'instant' })
      // Wait two frames for scroll + layout to settle
      await new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r())))

      // ── Step B: expand dashboard to its full scrollable height ────────────
      const fullWidth   = dashboard.scrollWidth
      const fullHeight  = dashboard.scrollHeight
      const prevOverflow  = dashboard.style.overflow
      const prevHeight    = dashboard.style.height
      const prevMaxHeight = dashboard.style.maxHeight
      dashboard.style.overflow  = 'visible'
      dashboard.style.height    = `${fullHeight}px`
      dashboard.style.maxHeight = 'none'
      // Give browser one frame to reflow at full height
      await new Promise<void>((r) => requestAnimationFrame(() => r()))

      // ── Step C: measure all block positions NOW ───────────────────────────
      // getBoundingClientRect is viewport-relative. Since scroll=0, viewport
      // top === document top, so these are correct document-relative coords.
      // We subtract dashboard's own top so all values are dashboard-relative.
      interface PdfBlock { topPx: number; bottomPx: number; label: string }
      const blocks: PdfBlock[] = []

      const dashTop = dashboard.getBoundingClientRect().top  // usually 0-ish

      const panels = Array.from(dashboard.querySelectorAll<HTMLElement>('section.panel'))

      for (const panel of panels) {
        const chartCards   = Array.from(panel.querySelectorAll<HTMLElement>('.chart-card'))
        const insightCards = Array.from(panel.querySelectorAll<HTMLElement>('.insight-card'))

        if (chartCards.length > 0) {
          // Section heading
          const heading = panel.querySelector<HTMLElement>('.section-heading')
          if (heading) {
            const r = heading.getBoundingClientRect()
            blocks.push({
              topPx:    Math.round((r.top    - dashTop) * SCALE),
              bottomPx: Math.round((r.bottom - dashTop) * SCALE),
              label: 'Section heading'
            })
          }

          // Group cards into rows by their top coordinate (8px tolerance)
          const rowMap = new Map<number, { top: number; bottom: number }[]>()
          for (const card of chartCards) {
            const r = card.getBoundingClientRect()
            const cTop = r.top - dashTop
            let key: number | undefined
            for (const k of rowMap.keys()) {
              if (Math.abs(k - cTop) <= 8) { key = k; break }
            }
            const entry = { top: cTop, bottom: r.bottom - dashTop }
            if (key !== undefined) {
              rowMap.get(key)!.push(entry)
            } else {
              rowMap.set(cTop, [entry])
            }
          }

          const sortedRowTops = Array.from(rowMap.keys()).sort((a, b) => a - b)
          for (const rowTop of sortedRowTops) {
            const entries = rowMap.get(rowTop)!
            const minTop = Math.min(...entries.map((e) => e.top))
            const maxBot = Math.max(...entries.map((e) => e.bottom))
            blocks.push({
              topPx:    Math.round(minTop * SCALE),
              bottomPx: Math.round(maxBot * SCALE),
              label: `Chart row (${entries.length} card${entries.length > 1 ? 's' : ''})`
            })
          }

        } else if (insightCards.length > 0) {
          const r = panel.getBoundingClientRect()
          blocks.push({
            topPx:    Math.round((r.top    - dashTop) * SCALE),
            bottomPx: Math.round((r.bottom - dashTop) * SCALE),
            label: 'Insights panel'
          })

        } else {
          const r = panel.getBoundingClientRect()
          blocks.push({
            topPx:    Math.round((r.top    - dashTop) * SCALE),
            bottomPx: Math.round((r.bottom - dashTop) * SCALE),
            label: 'Panel'
          })
        }
      }

      if (blocks.length === 0) {
        blocks.push({ topPx: 0, bottomPx: fullHeight * SCALE, label: 'Dashboard' })
      }

      // ── Step D: capture the full dashboard canvas ─────────────────────────
      setExportStatus('Rendering high-resolution dashboard snapshot...')
      const fullCanvas = await html2canvas(dashboard, {
        backgroundColor: state.darkMode ? '#07111f' : '#ffffff',
        scale: SCALE,
        useCORS: true,
        allowTaint: true,
        logging: false,
        scrollX: 0,
        scrollY: 0,
        windowWidth:  fullWidth,
        windowHeight: fullHeight,
        width:  fullWidth,
        height: fullHeight,
        onclone: (_clonedDoc, clonedEl) => {
          ;(clonedEl as HTMLElement).style.overflow  = 'visible'
          ;(clonedEl as HTMLElement).style.height    = `${fullHeight}px`
          ;(clonedEl as HTMLElement).style.maxHeight = 'none'
          sanitizeClonedDom(_clonedDoc, clonedEl as HTMLElement)
        }
      })

      // ── Step E: restore dashboard styles and scroll ───────────────────────
      dashboard.style.overflow  = prevOverflow
      dashboard.style.height    = prevHeight
      dashboard.style.maxHeight = prevMaxHeight
      window.scrollTo({ top: savedScrollY, behavior: 'instant' })

      // ── Step F: merge each heading with the first chart row below it ──────
      // (prevents orphaned section titles on their own page)
      const mergedBlocks: PdfBlock[] = []
      for (let i = 0; i < blocks.length; i++) {
        if (
          blocks[i].label === 'Section heading' &&
          i + 1 < blocks.length &&
          blocks[i + 1].label.startsWith('Chart row')
        ) {
          mergedBlocks.push({
            topPx:    blocks[i].topPx,
            bottomPx: blocks[i + 1].bottomPx,
            label:    'Heading + first chart row'
          })
          i++  // skip the row we absorbed
        } else {
          mergedBlocks.push(blocks[i])
        }
      }

      // ── Step G: assemble PDF ──────────────────────────────────────────────
      setExportStatus('Assembling PDF pages...')
      const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
      let curY = MARGIN_MM

      const extractStrip = (topPx: number, bottomPx: number): HTMLCanvasElement => {
        const t = Math.max(0, Math.floor(topPx))
        const b = Math.min(fullCanvas.height, Math.ceil(bottomPx))
        const h = Math.max(1, b - t)
        const c = document.createElement('canvas')
        c.width  = fullCanvas.width
        c.height = h
        c.getContext('2d')!.drawImage(fullCanvas, 0, t, fullCanvas.width, h, 0, 0, fullCanvas.width, h)
        return c
      }

      for (const block of mergedBlocks) {
        const strip     = extractStrip(block.topPx, block.bottomPx)
        const blockH_MM = (strip.height / strip.width) * printW_MM

        if (blockH_MM <= printH_MM) {
          // Whole block fits on one page — jump to next page if not enough room
          const remaining = A4_H_MM - MARGIN_MM - curY
          if (blockH_MM > remaining && curY > MARGIN_MM) {
            pdf.addPage()
            curY = MARGIN_MM
          }
          pdf.addImage(
            strip.toDataURL('image/png'), 'PNG',
            MARGIN_MM, curY, printW_MM, blockH_MM,
            undefined, 'FAST'
          )
          curY += blockH_MM + GAP_MM

        } else {
          // Block taller than one page (e.g. data table) — only acceptable slice
          let drawnPx = 0
          while (drawnPx < strip.height) {
            const avail_MM = A4_H_MM - MARGIN_MM - curY
            if (avail_MM < 15) { pdf.addPage(); curY = MARGIN_MM }
            const pageAvail_MM = A4_H_MM - MARGIN_MM - curY
            const slicePx   = Math.min(Math.ceil((pageAvail_MM / printW_MM) * strip.width), strip.height - drawnPx)
            const sliceH_MM = (slicePx / strip.width) * printW_MM

            const tmp = document.createElement('canvas')
            tmp.width  = strip.width
            tmp.height = slicePx
            tmp.getContext('2d')!.drawImage(strip, 0, drawnPx, strip.width, slicePx, 0, 0, strip.width, slicePx)

            pdf.addImage(tmp.toDataURL('image/png'), 'PNG', MARGIN_MM, curY, printW_MM, sliceH_MM, undefined, 'FAST')
            drawnPx += slicePx
            curY    += sliceH_MM + GAP_MM

            if (drawnPx < strip.height) { pdf.addPage(); curY = MARGIN_MM }
          }
        }
      }

      setExportStatus('Saving PDF...')
      pdf.save(`dashboard_${Date.now()}.pdf`)



    } catch (err: unknown) {
      setState((p) => ({ ...p, error: err instanceof Error ? err.message : 'Dashboard capture failed.' }))
    } finally {
      setExporting(false)
      setExportStatus('')
    }
  }

  const downloadChartImage = (chartId: string, title: string) => {
    const echartInstance = chartRefs.current[chartId]?.getEchartsInstance()
    if (!echartInstance) return
    const dataUrl = echartInstance.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: state.darkMode ? '#0d1729' : '#ffffff'
    })
    const a = document.createElement('a')
    a.href = dataUrl
    a.download = `${title.replace(/\s+/g, '_').toLowerCase()}_chart.png`
    a.click()
  }

  const summary = state.analysis?.analysis.summary
  const columns = state.analysis?.analysis.columns ?? {}
  const charts = state.analysis?.charts ?? []
  const table = state.analysis?.table
  const insights = state.analysis?.analysis.insights ?? []
  const availableColumns = state.analysis?.available_columns ?? []

  const categoryColumns = Object.values(columns).filter((c) => c.is_categorical && c.top_values?.length)
  const numericColumns = Object.values(columns).filter((c) => c.is_numeric && c.stats)
  const dateColumns = Object.values(columns).filter((c) => c.is_date && c.date_range)

  const visibleTableColumns = useMemo(() => {
    return availableColumns.filter((c) => visibleCols[c] !== false)
  }, [availableColumns, visibleCols])

  const visibleRows = useMemo(() => {
    if (!table?.rows) return []
    if (!Object.keys(visibleCols).length) return table.rows
    return table.rows.map((row) =>
      Object.fromEntries(Object.entries(row).filter(([key]) => visibleCols[key] !== false))
    )
  }, [table, visibleCols])

  if (!state.started) {
    return (
      <div className="app-shell">
        <div className="ambient ambient-a" />
        <div className="ambient ambient-b" />
        <StartScreen onStart={handleStart} onAdminClick={() => setAdminLoginOpen(true)} />
        <AdminLoginModal
          isOpen={adminLoginOpen}
          onClose={() => setAdminLoginOpen(false)}
          onSuccess={(token, username) => {
            setAdminToken(token)
            setAdminUsername(username)
            setAdminDashOpen(true)
          }}
        />
        <AdminDashboard
          isOpen={adminDashOpen}
          token={adminToken || ''}
          username={adminUsername}
          onClose={() => setAdminDashOpen(false)}
          onLogout={() => {
            setAdminToken(null)
            setAdminUsername('')
            setAdminDashOpen(false)
          }}
        />
      </div>
    )
  }

  const allVisibleCharts = [...charts, ...customCharts].filter((c) => !hiddenChartIds.has(c.id))

  return (
    <div className="app-shell">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />

      <header className="topbar">
        <div>
          <p className="eyebrow">Universal Data Analytics Platform</p>
          <h1>Automated Analytics Dashboard</h1>
          <p className="lede">
            Upload CSV, XLS, or XLSX files. Fast in-memory automated profiling, data exploration, recommendations, and exports — 100% free and offline safe.
          </p>
        </div>
        <div className="toolbar">
          {adminToken ? (
            <button className="secondary" type="button" onClick={() => setAdminDashOpen(true)}>
              <UserCheck size={16} /> Admin Dashboard ({adminUsername})
            </button>
          ) : (
            <button className="ghost" type="button" onClick={() => setAdminLoginOpen(true)}>
              Admin Login
            </button>
          )}
          <button
            className="ghost"
            type="button"
            onClick={() => setState((p) => ({ ...p, darkMode: !p.darkMode }))}
            aria-label="Toggle Theme"
          >
            {state.darkMode ? <SunMedium size={16} /> : <MoonStar size={16} />}
            {state.darkMode ? 'Light Mode' : 'Dark Mode'}
          </button>
          <button className="ghost" type="button" onClick={() => void resetClick()} aria-label="Reset State">
            <RefreshCw size={16} /> Reset
          </button>
        </div>
      </header>

      <AdminLoginModal
        isOpen={adminLoginOpen}
        onClose={() => setAdminLoginOpen(false)}
        onSuccess={(token, username) => {
          setAdminToken(token)
          setAdminUsername(username)
          setAdminDashOpen(true)
        }}
      />
      <AdminDashboard
        isOpen={adminDashOpen}
        token={adminToken || ''}
        username={adminUsername}
        onClose={() => setAdminDashOpen(false)}
        onLogout={() => {
          setAdminToken(null)
          setAdminUsername('')
          setAdminDashOpen(false)
        }}
      />

      {exporting ? (
        <div className="modal-overlay">
          <div className="modal-box animate-fade-in" style={{ padding: '36px 24px', textAlign: 'center' }}>
            <RefreshCw size={36} className="spin" style={{ color: 'var(--accent-2)', marginBottom: '16px' }} />
            <h4 style={{ margin: '0 0 8px', fontSize: '1.2rem' }}>Exporting Dashboard</h4>
            <p style={{ margin: 0, color: 'var(--muted)', fontSize: '0.92rem' }}>{exportStatus}</p>
          </div>
        </div>
      ) : null}

      <main className="dashboard" ref={dashboardRef}>
        {/* HERO / FILE UPLOAD SECTION */}
        <section className="panel hero-card">
          <div
            className={`upload-zone ${isDragging ? 'dragging' : ''}`}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
          >
            <div className="upload-copy">
              <span className="badge">100% In-memory processing</span>
              <h2>{state.file ? state.file.name : 'Drag & drop your file or click browse'}</h2>
              <p>
                {state.file
                  ? 'Inspect structure, select sheet, filter data, and export your dashboard anytime.'
                  : 'Supports CSV, XLS, and XLSX datasets up to 100,000+ rows. No database required.'}
              </p>
            </div>
            <label className="upload-button">
              <Upload size={16} /> Browse File
              <input
                type="file"
                accept=".csv,.xls,.xlsx"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) void handleFileSelection(f)
                }}
              />
            </label>
          </div>

          {/* ACTIONS TOOLBAR */}
          <div className="action-row">
            <button
              className="primary"
              type="button"
              onClick={analyzeClick}
              disabled={!state.file || state.loading}
            >
              <BarChart3 size={16} /> Analyze
            </button>
            <button
              className="secondary"
              type="button"
              onClick={analyzeClick}
              disabled={!state.file || state.loading}
              title="Re-run analysis on uploaded file"
            >
              <RefreshCw size={16} /> Refresh Dashboard
            </button>
            <button
              className="secondary"
              type="button"
              onClick={() => void exportExcel()}
              disabled={!state.analysis || !state.file || state.loading}
            >
              <Download size={16} /> Export Excel
            </button>
            <button
              className="secondary"
              type="button"
              onClick={() => void exportCsv()}
              disabled={!state.analysis || !state.file || state.loading}
            >
              <FileText size={16} /> Export CSV
            </button>
            <button
              className="secondary"
              type="button"
              onClick={() => void exportDashboard('png')}
              disabled={!state.analysis || state.loading}
            >
              <FileImage size={16} /> Export PNG
            </button>
            <button
              className="secondary"
              type="button"
              onClick={() => void exportDashboard('pdf')}
              disabled={!state.analysis || state.loading}
            >
              <FileSpreadsheet size={16} /> Export PDF
            </button>
          </div>

          {/* INSPECTION METRICS */}
          <div className="inspection-row">
            <Pill icon={<CircleGauge size={16} />} label="Total Rows" value={formatNumber(summary?.total_rows)} />
            <Pill icon={<CircleGauge size={16} />} label="Total Columns" value={formatNumber(summary?.total_columns)} />
            <Pill icon={<RefreshCw size={16} />} label="Analysis Time" value={summary ? `${summary.analysis_time_ms} ms` : '0 ms'} />
            <Pill
              icon={<Filter size={16} />}
              label="Active Filters"
              value={
                Object.keys(state.filters.category_filters).length +
                Object.keys(state.filters.numeric_ranges).length +
                Object.keys(state.filters.date_ranges).length +
                (state.filters.search_query ? 1 : 0)
              }
            />
          </div>

          {/* ERROR BANNER */}
          {state.error ? (
            <div className="error-banner">
              <span>{state.error}</span>
              <button type="button" onClick={() => setState((p) => ({ ...p, error: null }))} aria-label="Dismiss error">
                <X size={16} />
              </button>
            </div>
          ) : null}

          {/* LOADING SKELETON */}
          {state.loading ? (
            <div className="skeleton-container animate-fade-in">
              <div className="badge">{state.loadingMessage || 'Processing dataset...'}</div>
              <div className="skeleton-strip" />
              <div className="skeleton-strip" style={{ width: '80%' }} />
            </div>
          ) : null}
        </section>

        {/* METADATA & SHEET SELECTION */}
        {state.inspection ? (
          <section className="panel split-panel animate-fade-in">
            <div className="meta-grid">
              <Meta label="Filename" value={state.inspection.filename} />
              <Meta label="File Format" value={state.inspection.format.toUpperCase()} />
              <Meta label="Available Sheets" value={state.inspection.sheets.join(', ')} />
              <Meta label="Selected Sheet" value={state.sheetName || state.inspection.selected_sheet} />
            </div>
            {state.inspection.sheets.length > 1 ? (
              <label className="field">
                <span>Select Excel Sheet</span>
                <select
                  value={state.sheetName || state.inspection.selected_sheet}
                  onChange={(e) => onSheetChange(e.target.value)}
                >
                  {state.inspection.sheets.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
          </section>
        ) : null}

        {/* DASHBOARD ANALYTICS RESULTS */}
        {state.analysis ? (
          <>
            {/* KPI SUMMARY CARDS */}
            <section className="panel animate-fade-in">
              <SectionTitle title="Dataset Overview & Health" subtitle="Executive KPI metrics automatically profiled from RAM" />
              <div className="cards-grid">
                <StatCard label="Total Rows" value={formatNumber(summary?.total_rows)} icon={<Rows size={20} />} />
                <StatCard label="Total Columns" value={formatNumber(summary?.total_columns)} icon={<Columns size={20} />} />
                <StatCard label="Missing Values" value={formatNumber(summary?.missing_values)} icon={<AlertTriangle size={20} />} />
                <StatCard label="Missing %" value={summary ? `${summary.missing_percentage}%` : '0%'} icon={<Percent size={20} />} />
                <StatCard label="Duplicate Rows" value={formatNumber(summary?.duplicate_rows)} icon={<Copy size={20} />} />
                <StatCard label="Numeric Columns" value={formatNumber(summary?.numeric_columns_count)} icon={<Hash size={20} />} />
                <StatCard label="Categorical Columns" value={formatNumber(summary?.categorical_columns_count)} icon={<Tags size={20} />} />
                <StatCard label="Date Columns" value={formatNumber(summary?.date_columns_count)} icon={<Calendar size={20} />} />
                <StatCard label="Boolean Columns" value={formatNumber(summary?.boolean_columns_count)} icon={<CheckSquare size={20} />} />
                <StatCard label="Memory Usage" value={summary ? `${summary.memory_usage_mb.toFixed(2)} MB` : '0.00 MB'} icon={<HardDrive size={20} />} />
              </div>
            </section>

            {/* COLUMN DETAIL MODAL */}
            <ColumnDetailModal
              isOpen={Boolean(selectedColDetail)}
              columnName={selectedColDetail}
              stats={selectedColDetail ? columns[selectedColDetail] ?? null : null}
              darkMode={state.darkMode}
              onClose={() => setSelectedColDetail(null)}
            />

            {/* AUTOMATED INSIGHTS */}
            {insights.length > 0 ? (
              <section className="panel animate-fade-in">
                <SectionTitle title="Automated Rule-Based Insights" subtitle="Pattern recognition, outlier alerts, and correlation findings" />
                <div className="insights-grid">
                  {insights.map((insight, idx) => (
                    <InsightCard key={`${insight.type}-${idx}`} insight={insight} />
                  ))}
                </div>
              </section>
            ) : null}

            {/* CHOOSE CHARTS TO DISPLAY */}
            {[...charts, ...customCharts].length > 0 ? (
              <section className="panel animate-fade-in">
                <ChartVisibilitySelector
                  charts={[...charts, ...customCharts]}
                  hiddenChartIds={hiddenChartIds}
                  onToggleChart={toggleChartVisibility}
                  onToggleAll={toggleAllCharts}
                />
              </section>
            ) : null}

            {/* RECOMMENDED & CUSTOM CHARTS */}
            {allVisibleCharts.length > 0 ? (
              <section className="panel animate-fade-in">
                <SectionTitle title="Automated & Custom Visualizations" subtitle="Smart multi-type visualizations generated directly from data distributions" />
                <div className="charts-grid">
                  {allVisibleCharts.map((chart) => (
                    <ChartCard
                      key={chart.id}
                      chart={chart}
                      darkMode={state.darkMode}
                      onRef={(ref) => {
                        chartRefs.current[chart.id] = ref
                      }}
                      onDownload={() => downloadChartImage(chart.id, chart.title)}
                      onHide={() => setHiddenChartIds((prev) => new Set(prev).add(chart.id))}
                    />
                  ))}
                </div>
              </section>
            ) : null}

            {/* MANUAL CHART SELECTOR & PREVIEW */}
            <section className="panel animate-fade-in">
              <ChartSelector
                availableColumns={availableColumns}
                columnsStats={columns}
                rows={table?.rows ?? []}
                darkMode={state.darkMode}
                onAddChart={(newChart: ChartDefinition) => setCustomCharts((prev) => [...prev, newChart])}
              />
            </section>

            {/* INTERACTIVE DATA EXPLORER */}
            <section className="panel animate-fade-in">
              <SectionTitle title="Interactive Data Explorer" subtitle="Search, filter, sort, paginate, and customize column visibility" />

              {/* CONTROLS TOOLBAR */}
              <div className="explorer-toolbar">
                <label className="field">
                  <span>Search Data</span>
                  <div className="search-box">
                    <Search size={16} />
                    <input
                      value={state.filters.search_query}
                      onChange={(e) => patchFilters({ search_query: e.target.value })}
                      placeholder="Type keyword to filter..."
                    />
                  </div>
                </label>
                <label className="field">
                  <span>Sort By Column</span>
                  <select value={state.filters.sort_by} onChange={(e) => patchFilters({ sort_by: e.target.value })}>
                    <option value="">(Default order)</option>
                    {availableColumns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>Sort Order</span>
                  <select
                    value={state.filters.sort_direction}
                    onChange={(e) => patchFilters({ sort_direction: e.target.value as 'asc' | 'desc' })}
                  >
                    <option value="desc">Descending</option>
                    <option value="asc">Ascending</option>
                  </select>
                </label>
                <label className="field">
                  <span>Page Size</span>
                  <select
                    value={state.filters.page_size}
                    onChange={(e) => patchFilters({ page_size: Number(e.target.value), page: 1 })}
                  >
                    {[25, 50, 100, 250].map((n) => (
                      <option key={n} value={n}>
                        {n} rows
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {/* FILTERS SECTION */}
              <div className="filter-layout">
                {categoryColumns.length > 0 ? (
                  <FilterColumn title="Category Filters">
                    {categoryColumns.slice(0, 4).map((column) => (
                      <FilterBox key={column.name} title={column.name} subtitle={column.detected_type}>
                        <div className="chip-grid">
                          {(column.top_values ?? []).slice(0, 8).map((item) => {
                            const active = (state.filters.category_filters[column.name] ?? []).includes(item.value)
                            return (
                              <label key={item.value} className={`chip ${active ? 'chip-active' : ''}`}>
                                <input
                                  type="checkbox"
                                  checked={active}
                                  onChange={(e) => toggleCategory(column.name, item.value, e.target.checked)}
                                />
                                <span>{item.value}</span>
                              </label>
                            )
                          })}
                        </div>
                      </FilterBox>
                    ))}
                  </FilterColumn>
                ) : null}

                {numericColumns.length > 0 ? (
                  <FilterColumn title="Numeric Range Filters">
                    {numericColumns.slice(0, 4).map((column) => (
                      <FilterBox
                        key={column.name}
                        title={column.name}
                        subtitle={`Min: ${column.stats?.min ?? '-'} | Max: ${column.stats?.max ?? '-'}`}
                      >
                        <div className="range-grid">
                          <input
                            type="number"
                            placeholder="Min value"
                            defaultValue={state.filters.numeric_ranges[column.name]?.min ?? ''}
                            onBlur={(e) =>
                              patchFilters({
                                numeric_ranges: {
                                  ...state.filters.numeric_ranges,
                                  [column.name]: {
                                    ...state.filters.numeric_ranges[column.name],
                                    min: e.target.value === '' ? undefined : Number(e.target.value)
                                  }
                                }
                              })
                            }
                          />
                          <input
                            type="number"
                            placeholder="Max value"
                            defaultValue={state.filters.numeric_ranges[column.name]?.max ?? ''}
                            onBlur={(e) =>
                              patchFilters({
                                numeric_ranges: {
                                  ...state.filters.numeric_ranges,
                                  [column.name]: {
                                    ...state.filters.numeric_ranges[column.name],
                                    max: e.target.value === '' ? undefined : Number(e.target.value)
                                  }
                                }
                              })
                            }
                          />
                        </div>
                      </FilterBox>
                    ))}
                  </FilterColumn>
                ) : null}

                {dateColumns.length > 0 ? (
                  <FilterColumn title="Date Range Filters">
                    {dateColumns.slice(0, 3).map((column) => (
                      <FilterBox
                        key={column.name}
                        title={column.name}
                        subtitle={column.date_range ? `${column.date_range.min_date} to ${column.date_range.max_date}` : 'Date range'}
                      >
                        <div className="range-grid">
                          <input
                            type="date"
                            onBlur={(e) =>
                              patchFilters({
                                date_ranges: {
                                  ...state.filters.date_ranges,
                                  [column.name]: {
                                    ...state.filters.date_ranges[column.name],
                                    start: e.target.value || undefined
                                  }
                                }
                              })
                            }
                          />
                          <input
                            type="date"
                            onBlur={(e) =>
                              patchFilters({
                                date_ranges: {
                                  ...state.filters.date_ranges,
                                  [column.name]: {
                                    ...state.filters.date_ranges[column.name],
                                    end: e.target.value || undefined
                                  }
                                }
                              })
                            }
                          />
                        </div>
                      </FilterBox>
                    ))}
                  </FilterColumn>
                ) : null}
              </div>

              {/* COLUMN VISIBILITY & TABLE TOOLBAR */}
              <div className="table-toolbar">
                <p>
                  Showing {table?.rows.length ?? 0} of {table?.total_rows ?? 0} matching records
                </p>
                <div className="table-actions">
                  <button
                    className="ghost small"
                    type="button"
                    onClick={() => setVisibleCols(Object.fromEntries(Object.keys(columns).map((c) => [c, true])))}
                  >
                    Show All Columns
                  </button>
                  <button
                    className="ghost small"
                    type="button"
                    onClick={() => setVisibleCols(Object.fromEntries(Object.keys(columns).map((c) => [c, false])))}
                  >
                    Hide All Columns
                  </button>
                </div>
              </div>

              <div className="visibility-strip">
                {availableColumns.map((column) => (
                  <label key={column} className={`visibility-chip ${visibleCols[column] === false ? 'inactive' : ''}`}>
                    <input
                      type="checkbox"
                      checked={visibleCols[column] !== false}
                      onChange={(e) => setVisibleCols((p) => ({ ...p, [column]: e.target.checked }))}
                    />
                    {column}
                  </label>
                ))}
              </div>

              {/* DATA TABLE */}
              <div className="table-wrap">
                {visibleTableColumns.length === 0 ? (
                  <div className="empty-table-placeholder">All columns are currently hidden. Select columns above to display data.</div>
                ) : (
                  <table>
                    <thead>
                      <tr>
                        {visibleTableColumns.map((c) => (
                          <th key={c}>{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {visibleRows.length === 0 ? (
                        <tr>
                          <td colSpan={visibleTableColumns.length} style={{ textAlign: 'center', padding: '30px' }}>
                            No matching rows found for current filters.
                          </td>
                        </tr>
                      ) : (
                        visibleRows.map((row, idx) => (
                          <tr key={idx}>
                            {visibleTableColumns.map((c) => (
                              <td key={c}>{formatCell(row[c])}</td>
                            ))}
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                )}
              </div>

              {/* PAGINATION */}
              <div className="pager">
                <button
                  className="ghost small"
                  type="button"
                  onClick={() => patchFilters({ page: Math.max((table?.page ?? 1) - 1, 1) })}
                  disabled={(table?.page ?? 1) <= 1}
                >
                  Previous
                </button>
                <span>
                  Page {table?.page ?? 1} of {table?.total_pages ?? 1}
                </span>
                <button
                  className="ghost small"
                  type="button"
                  onClick={() => patchFilters({ page: Math.min((table?.page ?? 1) + 1, table?.total_pages ?? 1) })}
                  disabled={(table?.page ?? 1) >= (table?.total_pages ?? 1)}
                >
                  Next
                </button>
              </div>
            </section>

            {/* COLUMN DETAILS */}
            <section className="panel animate-fade-in">
              <SectionTitle title="Detailed Column Statistics" subtitle="Click any column card to inspect full descriptive statistics, distribution charts, and null rates" />
              <div className="column-list">
                {Object.values(columns).map((column) => (
                  <article
                    className="column-card"
                    key={column.name}
                    onClick={() => setSelectedColDetail(column.name)}
                    title="Click to inspect detailed metrics & distribution"
                  >
                    <div className="column-head">
                      <div>
                        <h4>{column.name}</h4>
                        <p>{column.detected_type}</p>
                      </div>
                      {column.is_id ? <span className="pill">ID / Key</span> : null}
                    </div>
                    <div className="column-metrics">
                      <Metric label="Null Count" value={formatNumber(column.null_count)} />
                      <Metric label="Null %" value={`${column.null_percentage}%`} />
                      <Metric label="Unique" value={formatNumber(column.unique_count)} />
                      <Metric label="Outliers" value={formatNumber(column.stats?.outliers_count ?? 0)} />
                    </div>
                    {column.top_values?.length ? (
                      <div className="mini-list">
                        {column.top_values.slice(0, 5).map((item) => (
                          <div key={item.value} className="mini-row">
                            <span>{item.value}</span>
                            <strong>
                              {item.count} ({item.percentage}%)
                            </strong>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            </section>
          </>
        ) : (
          !state.loading && (
            <section className="panel empty-state animate-fade-in">
              <CircleGauge size={44} />
              <h3>No Analysis Active</h3>
              <p>Upload a CSV, XLS, or XLSX file above to automatically analyze data and render an interactive dashboard.</p>
            </section>
          )
        )}
      </main>
    </div>
  )
}

function SectionTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="section-heading">
      <div>
        <h3>{title}</h3>
        <p>{subtitle}</p>
      </div>
    </div>
  )
}

function Pill({ icon, label, value }: { icon: ReactNode; label: string; value: string | number }) {
  return (
    <div className="inspection-pill">
      {icon}
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  )
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="meta-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function StatCard({ label, value, icon }: { label: string; value: string; icon?: ReactNode }) {
  return (
    <div className="summary-card">
      <div className="summary-card-inner">
        {icon ? <div className="summary-card-icon">{icon}</div> : null}
        <div className="summary-card-content">
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      </div>
    </div>
  )
}

function InsightCard({ insight }: { insight: InsightItem }) {
  return (
    <article className={`insight-card insight-${insight.severity}`}>
      <div className="insight-head">
        <span>{insight.type}</span>
        <strong>{insight.severity}</strong>
      </div>
      <h4>{insight.title}</h4>
      <p>{insight.description}</p>
    </article>
  )
}

function FilterColumn({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="filter-column">
      <h4>{title}</h4>
      {children}
    </div>
  )
}

function FilterBox({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <section className="filter-block">
      <div className="filter-head">
        <h5>{title}</h5>
        <p>{subtitle}</p>
      </div>
      {children}
    </section>
  )
}

function ChartCard({
  chart,
  darkMode,
  onRef,
  onDownload,
  onHide
}: {
  chart: ChartDefinition
  darkMode: boolean
  onRef: (ref: ReactECharts | null) => void
  onDownload: () => void
  onHide?: () => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const echartInstanceRef = useRef<ReactECharts | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)

  useEffect(() => {
    if (!containerRef.current) return
    const observer = new ResizeObserver(() => {
      const instance = echartInstanceRef.current?.getEchartsInstance()
      instance?.resize()
    })
    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  const setRef = (ref: ReactECharts | null) => {
    echartInstanceRef.current = ref
    onRef(ref)
  }

  const dataLen = chart.x_axis?.length ?? 0
  const isHorizontalBar = chart.type === 'horizontal_bar'
  const dynamicHeight = isHorizontalBar ? Math.max(340, Math.min(600, dataLen * 26 + 70)) : 340

  return (
    <article className={`chart-card ${isFullWidth ? 'chart-card-full' : ''}`} ref={containerRef}>
      <div className="chart-head">
        <div>
          <h4>{chart.title}</h4>
          <p>{chart.description}</p>
        </div>
        <div className="chart-actions">
          <button
            className="ghost small icon-only"
            type="button"
            onClick={() => {
              setIsFullWidth(!isFullWidth)
              setTimeout(() => echartInstanceRef.current?.getEchartsInstance()?.resize(), 50)
            }}
            title={isFullWidth ? 'Collapse Width' : 'Expand Width'}
          >
            {isFullWidth ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
          {onHide && (
            <button className="ghost small icon-only" type="button" onClick={onHide} title="Hide Chart">
              <EyeOff size={14} />
            </button>
          )}
          <button className="ghost small" type="button" onClick={onDownload} title="Download Chart PNG">
            <Download size={14} /> PNG
          </button>
        </div>
      </div>
      <ReactECharts
        ref={setRef}
        option={buildChartOption(chart, darkMode)}
        style={{ height: dynamicHeight, width: '100%' }}
        notMerge
        lazyUpdate
      />
    </article>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

export function buildChartOption(chart: ChartDefinition, darkMode: boolean) {
  const axisColor = darkMode ? '#a8b3c9' : '#475569'
  const gridColor = darkMode ? 'rgba(148,163,184,0.12)' : 'rgba(15,23,42,0.06)'
  const textColor = darkMode ? '#f1f5f9' : '#0f172a'

  if (chart.type === 'pie' || chart.type === 'donut') {
    return {
      backgroundColor: 'transparent',
      color: ['#38bdf8', '#2dd4bf', '#f59e0b', '#a78bfa', '#f97316', '#ef4444', '#ec4899', '#8b5cf6', '#10b981', '#64748b'],
      textStyle: { color: textColor },
      tooltip: {
        trigger: 'item',
        formatter: '{b}: <b>{c}</b> ({d}%)',
        confine: true
      },
      legend: {
        type: 'scroll',
        orient: 'horizontal',
        bottom: 0,
        left: 'center',
        textStyle: { color: axisColor, fontSize: 11 },
        pageIconColor: axisColor,
        pageTextStyle: { color: axisColor },
        formatter: (name: string) => (name.length > 18 ? name.slice(0, 15) + '...' : name)
      },
      series: [
        {
          type: 'pie',
          radius: chart.type === 'donut' ? ['38%', '65%'] : '65%',
          center: ['50%', '42%'],
          avoidLabelOverlap: true,
          label: {
            show: true,
            fontSize: 11,
            color: textColor,
            formatter: (params: any) => {
              const name = String(params.name)
              return name.length > 14 ? name.slice(0, 11) + '...' : name
            }
          },
          labelLine: { show: true, length: 8, length2: 10 },
          data: chart.series[0]?.data ?? []
        }
      ]
    }
  }

  if (chart.type === 'scatter') {
    return {
      backgroundColor: 'transparent',
      textStyle: { color: textColor },
      tooltip: { trigger: 'item', confine: true },
      grid: { top: 40, left: '3%', right: '4%', bottom: 35, containLabel: true },
      xAxis: {
        type: 'value',
        name: chart.x_label ?? undefined,
        axisLine: { lineStyle: { color: axisColor } },
        splitLine: { lineStyle: { color: gridColor } },
        axisLabel: { color: axisColor, fontSize: 11 }
      },
      yAxis: {
        type: 'value',
        name: chart.y_label ?? undefined,
        axisLine: { lineStyle: { color: axisColor } },
        splitLine: { lineStyle: { color: gridColor } },
        axisLabel: { color: axisColor, fontSize: 11 }
      },
      series: [{ type: 'scatter', data: chart.series[0]?.data ?? [], symbolSize: 8 }]
    }
  }

  if (chart.type === 'heatmap') {
    return {
      backgroundColor: 'transparent',
      textStyle: { color: textColor },
      tooltip: { position: 'top', confine: true },
      grid: { top: 40, left: '3%', right: '4%', bottom: 60, containLabel: true },
      xAxis: {
        type: 'category',
        data: chart.x_axis ?? [],
        splitArea: { show: true },
        axisLabel: {
          color: axisColor,
          fontSize: 11,
          rotate: 45,
          formatter: (val: string) => (val.length > 14 ? val.slice(0, 11) + '...' : val)
        }
      },
      yAxis: {
        type: 'category',
        data: chart.y_axis ?? [],
        splitArea: { show: true },
        axisLabel: {
          color: axisColor,
          fontSize: 11,
          formatter: (val: string) => (val.length > 14 ? val.slice(0, 11) + '...' : val)
        }
      },
      visualMap: { min: -1, max: 1, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, textStyle: { color: axisColor } },
      series: [{ type: 'heatmap', data: chart.series[0]?.data ?? [] }]
    }
  }

  if (chart.type === 'boxplot') {
    return {
      backgroundColor: 'transparent',
      textStyle: { color: textColor },
      tooltip: { trigger: 'item', confine: true },
      grid: { top: 45, left: '3%', right: '4%', bottom: 35, containLabel: true },
      xAxis: {
        type: 'category',
        data: chart.x_axis ?? [],
        axisLabel: { color: axisColor, fontSize: 11 },
        axisLine: { lineStyle: { color: axisColor } }
      },
      yAxis: {
        type: 'value',
        name: chart.y_label ?? undefined,
        axisLabel: { color: axisColor, fontSize: 11 },
        splitLine: { lineStyle: { color: gridColor } }
      },
      series: [
        {
          name: chart.series[0]?.name ?? 'Boxplot',
          type: 'boxplot',
          data: chart.series[0]?.data ?? [],
          itemStyle: { color: '#38bdf8', borderColor: '#0284c7' }
        }
      ]
    }
  }

  const horizontal = chart.type === 'horizontal_bar'
  const stacked = chart.type === 'stacked_bar'
  const isArea = chart.type === 'area'
  const dataLen = chart.x_axis?.length ?? 0
  const needsZoom = !horizontal && dataLen > 10

  return {
    backgroundColor: 'transparent',
    textStyle: { color: textColor },
    tooltip: {
      trigger: 'axis',
      confine: true,
      axisPointer: { type: 'shadow' }
    },
    legend: {
      type: 'scroll',
      top: 0,
      textStyle: { color: axisColor, fontSize: 11 },
      pageIconColor: axisColor,
      pageTextStyle: { color: axisColor }
    },
    grid: {
      top: 45,
      left: '3%',
      right: '4%',
      bottom: needsZoom ? 45 : 30,
      containLabel: true
    },
    dataZoom: needsZoom ? [
      {
        type: 'inside',
        start: 0,
        end: Math.min(100, Math.round((10 / dataLen) * 100))
      },
      {
        type: 'slider',
        show: true,
        bottom: 5,
        height: 16,
        borderColor: 'transparent',
        fillerColor: darkMode ? 'rgba(56, 189, 248, 0.25)' : 'rgba(56, 189, 248, 0.15)',
        handleSize: '100%',
        textStyle: { color: axisColor, fontSize: 10 }
      }
    ] : [],
    xAxis: horizontal
      ? {
          type: 'value',
          axisLine: { lineStyle: { color: axisColor } },
          splitLine: { lineStyle: { color: gridColor } },
          axisLabel: { color: axisColor, fontSize: 11 }
        }
      : {
          type: 'category',
          data: chart.x_axis ?? [],
          axisLine: { lineStyle: { color: axisColor } },
          axisLabel: {
            color: axisColor,
            fontSize: 11,
            rotate: dataLen > 6 ? (dataLen > 12 ? 45 : 35) : 0,
            interval: 0,
            formatter: (val: string) => {
              const s = String(val)
              return s.length > 14 ? s.slice(0, 11) + '...' : s
            }
          }
        },
    yAxis: horizontal
      ? {
          type: 'category',
          data: chart.x_axis ?? [],
          axisLine: { lineStyle: { color: axisColor } },
          axisLabel: {
            color: axisColor,
            fontSize: 11,
            interval: 0,
            formatter: (val: string) => {
              const s = String(val)
              return s.length > 14 ? s.slice(0, 11) + '...' : s
            }
          }
        }
      : {
          type: 'value',
          axisLine: { lineStyle: { color: axisColor } },
          splitLine: { lineStyle: { color: gridColor } },
          axisLabel: { color: axisColor, fontSize: 11 }
        },
    series: chart.series.map((series, idx) => ({
      name: series.name,
      type: isArea ? 'line' : chart.type === 'line' ? 'line' : 'bar',
      stack: stacked ? 'total' : undefined,
      smooth: isArea || chart.type === 'line',
      areaStyle: isArea ? {} : undefined,
      data: series.data,
      itemStyle: { color: palette(idx) }
    }))
  }
}

function formatNumber(value: number | undefined | null) {
  if (value === undefined || value === null) return '0'
  return Number(value).toLocaleString()
}

function formatCell(value: unknown) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'number') return value.toLocaleString()
  return String(value)
}

function palette(index: number) {
  return ['#38bdf8', '#2dd4bf', '#fbbf24', '#a78bfa', '#f97316', '#f43f5e', '#ec4899', '#8b5cf6', '#10b981', '#64748b'][index % 10]
}

async function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('Canvas image conversion failed.'))), 'image/png')
  })
}

function downloadBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

export default App
