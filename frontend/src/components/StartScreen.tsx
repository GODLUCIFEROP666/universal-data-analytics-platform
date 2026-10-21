import { useEffect, useState, useRef, type DragEvent, type ChangeEvent } from 'react'
import {
  AlertTriangle,
  BarChart2,
  Database,
  FileSpreadsheet,
  FileText,
  Info,
  Loader2,
  Lock,
  Play,
  ShieldCheck,
  Users,
} from 'lucide-react'
import { getVisitorCount } from '../lib/api'

interface StartScreenProps {
  onStart: () => Promise<void>
  onFileUpload: (file: File) => Promise<void>
  onAdminClick: () => void
}

const SAMPLE_CSV = `Order_ID,Order_Date,Region,Customer_Segment,Product_Category,Sales_Amount,Quantity,Discount_Percent,Profit
ORD-1001,2025-01-05,North,Corporate,Electronics,1250.50,5,10%,250.10
ORD-1002,2025-01-06,South,Consumer,Furniture,450.00,2,0%,90.00
ORD-1003,2025-01-08,East,Home Office,Technology,3400.00,10,15%,680.00
ORD-1004,2025-01-10,West,Consumer,Office Supplies,85.20,4,5%,17.04
ORD-1005,2025-01-12,North,Corporate,Furniture,890.00,3,10%,178.00
ORD-1006,2025-01-15,Central,Consumer,Electronics,2100.00,8,12%,420.00
ORD-1007,2025-01-18,East,Corporate,Technology,1800.00,4,8%,360.00
ORD-1008,2025-01-20,West,Home Office,Office Supplies,120.50,6,0%,30.12
ORD-1009,2025-01-22,South,Consumer,Electronics,1550.00,5,10%,310.00
ORD-1010,2025-01-25,North,Corporate,Technology,4200.00,12,20%,840.00`

// Mini SVG chart illustrations for the preview card
function MiniBarChart() {
  return (
    <svg viewBox="0 0 80 52" fill="none" xmlns="http://www.w3.org/2000/svg" className="mini-chart-svg">
      <rect x="4" y="28" width="10" height="20" rx="2" fill="#60a5fa" opacity="0.8"/>
      <rect x="18" y="16" width="10" height="32" rx="2" fill="#3b82f6"/>
      <rect x="32" y="8" width="10" height="40" rx="2" fill="#2563eb"/>
      <rect x="46" y="20" width="10" height="28" rx="2" fill="#60a5fa" opacity="0.8"/>
      <rect x="60" y="12" width="10" height="36" rx="2" fill="#3b82f6"/>
    </svg>
  )
}

function MiniPieChart() {
  return (
    <svg viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg" className="mini-chart-svg">
      <circle cx="26" cy="26" r="22" fill="#e0f2fe"/>
      <path d="M26 26 L26 4 A22 22 0 0 1 48 26 Z" fill="#2563eb"/>
      <path d="M26 26 L48 26 A22 22 0 0 1 13 44 Z" fill="#0d9488"/>
      <path d="M26 26 L13 44 A22 22 0 0 1 26 4 Z" fill="#60a5fa"/>
    </svg>
  )
}

function MiniLineChart() {
  return (
    <svg viewBox="0 0 80 52" fill="none" xmlns="http://www.w3.org/2000/svg" className="mini-chart-svg">
      <polyline points="4,40 18,28 32,32 46,16 60,20 74,8" stroke="#2563eb" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx="4" cy="40" r="3" fill="#2563eb"/>
      <circle cx="18" cy="28" r="3" fill="#2563eb"/>
      <circle cx="32" cy="32" r="3" fill="#2563eb"/>
      <circle cx="46" cy="16" r="3" fill="#2563eb"/>
      <circle cx="60" cy="20" r="3" fill="#2563eb"/>
      <circle cx="74" cy="8" r="3" fill="#2563eb"/>
    </svg>
  )
}

function MiniScatterChart() {
  return (
    <svg viewBox="0 0 80 52" fill="none" xmlns="http://www.w3.org/2000/svg" className="mini-chart-svg">
      <circle cx="12" cy="40" r="4" fill="#60a5fa" opacity="0.7"/>
      <circle cx="24" cy="32" r="3" fill="#3b82f6" opacity="0.8"/>
      <circle cx="38" cy="20" r="5" fill="#2563eb"/>
      <circle cx="52" cy="28" r="3" fill="#60a5fa" opacity="0.7"/>
      <circle cx="64" cy="12" r="4" fill="#3b82f6" opacity="0.8"/>
      <circle cx="20" cy="44" r="2.5" fill="#0d9488" opacity="0.7"/>
      <circle cx="70" cy="36" r="3" fill="#0d9488" opacity="0.6"/>
    </svg>
  )
}

function MiniHeatmap() {
  const colors = [
    ['#bfdbfe','#93c5fd','#60a5fa','#3b82f6'],
    ['#93c5fd','#60a5fa','#3b82f6','#2563eb'],
    ['#60a5fa','#3b82f6','#2563eb','#1d4ed8'],
  ]
  return (
    <svg viewBox="0 0 80 52" fill="none" xmlns="http://www.w3.org/2000/svg" className="mini-chart-svg">
      {colors.map((row, ri) =>
        row.map((color, ci) => (
          <rect
            key={`${ri}-${ci}`}
            x={ci * 20 + 2}
            y={ri * 16 + 2}
            width="17"
            height="13"
            rx="2"
            fill={color}
          />
        ))
      )}
    </svg>
  )
}

// CSV file icon
function CsvIcon() {
  return (
    <div className="file-icon csv-icon">
      <div className="file-icon-fold" />
      <div className="file-icon-label">CSV</div>
    </div>
  )
}

// Excel file icon
function XlsxIcon() {
  return (
    <div className="file-icon xlsx-icon">
      <div className="file-icon-fold" />
      <div className="file-icon-label">X</div>
    </div>
  )
}

export function StartScreen({ onStart, onFileUpload, onAdminClick }: StartScreenProps) {
  const [visitorCount, setVisitorCount] = useState<number | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<boolean>(false)
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)
  const [startError, setStartError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState<boolean>(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let isMounted = true
    getVisitorCount()
      .then((data) => {
        if (isMounted) {
          setVisitorCount(data.visitor_count)
          setError(false)
          setLoading(false)
        }
      })
      .catch(() => {
        if (isMounted) {
          setError(true)
          setLoading(false)
        }
      })
    return () => { isMounted = false }
  }, [])

  const processFile = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!ext || !['csv', 'xls', 'xlsx'].includes(ext)) {
      setStartError('Invalid file format. Please upload a CSV, XLS, or XLSX file.')
      return
    }
    if (isSubmitting) return
    setIsSubmitting(true)
    setStartError(null)
    try {
      if (visitorCount !== null) setVisitorCount((prev) => (prev !== null ? prev + 1 : 1))
      await onFileUpload(file)
    } catch {
      setStartError('Failed to process file. Please ensure the backend is active and try again.')
      setIsSubmitting(false)
    }
  }

  const handleStartClick = async () => {
    if (isSubmitting) return
    setIsSubmitting(true)
    setStartError(null)
    try {
      if (visitorCount !== null) setVisitorCount((prev) => (prev !== null ? prev + 1 : 1))
      await onStart()
    } catch {
      setStartError('The analytics engine could not be started. Please try again.')
      setIsSubmitting(false)
    }
  }

  const handleSampleClick = async () => {
    const sampleFile = new File([SAMPLE_CSV], 'sales_data_sample.csv', { type: 'text/csv' })
    await processFile(sampleFile)
  }

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => { e.preventDefault(); e.stopPropagation(); setIsDragging(true) }
  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => { e.preventDefault(); e.stopPropagation(); setIsDragging(false) }
  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation(); setIsDragging(false)
    const files = e.dataTransfer.files
    if (files && files.length > 0) void processFile(files[0])
  }
  const handleFileInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) void processFile(files[0])
  }

  return (
    <div className="ls-page animate-fade-in">
      {/* Animated background blobs */}
      <div className="ls-blob ls-blob-tl" />
      <div className="ls-blob ls-blob-tr" />
      <div className="ls-blob ls-blob-bl" />
      <div className="ls-wave-svg">
        <svg viewBox="0 0 1440 220" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M0,120 C240,180 480,60 720,120 C960,180 1200,60 1440,120 L1440,220 L0,220 Z" fill="rgba(255,255,255,0.45)"/>
          <path d="M0,160 C360,100 720,200 1080,140 C1260,110 1380,170 1440,160 L1440,220 L0,220 Z" fill="rgba(255,255,255,0.65)"/>
        </svg>
      </div>

      {/* ── TOP NAV ── */}
      <nav className="ls-nav">
        <div className="ls-brand">
          <div className="ls-brand-icon">
            <BarChart2 size={16} />
          </div>
          <span className="ls-brand-name">Universal Data Analytics</span>
        </div>
        <button className="ls-admin-btn" type="button" onClick={onAdminClick}>
          <Users size={15} />
          <span>Admin Login</span>
        </button>
      </nav>

      {/* ── HERO SECTION ── */}
      <div
        className={`ls-hero ${isDragging ? 'ls-hero--dragging' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* Left: file icons */}
        <div className="ls-file-icons" aria-hidden="true">
          <div className="ls-file-stack">
            <XlsxIcon />
            <CsvIcon />
          </div>
          <div className="ls-arrow-track">
            <svg viewBox="0 0 100 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M0 12 Q50 4 88 12"
                stroke="#2563eb"
                strokeWidth="2"
                strokeDasharray="6 4"
                fill="none"
              />
              <polygon points="88,6 100,12 88,18" fill="#2563eb" opacity="0.85"/>
            </svg>
          </div>
        </div>

        {/* Center: text + CTA */}
        <div className="ls-hero-center">
          <p className="ls-eyebrow">Enterprise-Grade In-Memory Analytics</p>
          <h1 className="ls-headline">
            Analyze Messy Data<br />
            <span className="ls-gradient-text">Instantly &amp; Privately</span>
          </h1>
          <p className="ls-subtext">
            Upload a CSV or Excel file. Get clean data, clear insights, and<br className="ls-br-hide" />
            interactive charts — privately.
          </p>

          <div className="ls-cta-group">
            <label className="ls-tap-btn" id="ls-tap-btn-label">
              {isSubmitting ? (
                <><Loader2 size={20} className="spin" /><span>Analyzing...</span></>
              ) : isDragging ? (
                <><FileSpreadsheet size={20} /><span>Drop to Analyze!</span></>
              ) : (
                <><Play size={18} fill="currentColor" /><span>Tap to Begin</span></>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={handleFileInputChange}
                disabled={isSubmitting}
                style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer' }}
              />
            </label>

            <p className="ls-cta-note">
              Ready when you are &nbsp;•&nbsp; No account required
            </p>

            <div className="ls-secondary-actions">
              <button
                className="ls-sample-btn"
                type="button"
                onClick={() => void handleSampleClick()}
                disabled={isSubmitting}
              >
                <FileText size={15} />
                <span>Try Sample Dataset</span>
              </button>
              <button
                className="ls-open-btn"
                type="button"
                onClick={() => void handleStartClick()}
                disabled={isSubmitting}
              >
                <Database size={15} />
                <span>Open Empty Workspace</span>
              </button>
            </div>
          </div>

          {startError && (
            <div className="ls-error animate-fade-in">
              <AlertTriangle size={16} />
              <span>{startError}</span>
            </div>
          )}

          {/* Visitor counter */}
          {!error && (
            <div className="ls-visitor-row">
              <div className="ls-visitor-dot" />
              <span>
                {loading ? '...' : (visitorCount ?? 0).toLocaleString()} analytics sessions completed
              </span>
            </div>
          )}

          <div className="ls-cold-notice">
            <Info size={13} />
            <span>First launch may take ~30 s while the backend wakes up.</span>
          </div>
        </div>

        {/* Right: chart preview card */}
        <div className="ls-chart-card" aria-hidden="true">
          <div className="ls-chart-card-inner">
            <div className="ls-mini-chart-row">
              <div className="ls-mini-chart-box">
                <MiniBarChart />
              </div>
              <div className="ls-mini-chart-box">
                <MiniPieChart />
              </div>
            </div>
            <div className="ls-mini-chart-row">
              <div className="ls-mini-chart-box ls-mini-chart-box--wide">
                <MiniLineChart />
              </div>
            </div>
            <div className="ls-mini-chart-row">
              <div className="ls-mini-chart-box">
                <MiniScatterChart />
              </div>
              <div className="ls-mini-chart-box">
                <MiniHeatmap />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── BOTTOM FEATURE CARDS ── */}
      <div className="ls-features">
        <div className="ls-feature-card">
          <div className="ls-feature-icon ls-fi-blue">
            <Database size={20} />
          </div>
          <div className="ls-feature-text">
            <h3>Smart Data Cleaning</h3>
            <p>Detect headers, tidy messy rows, and prepare your data automatically.</p>
          </div>
        </div>
        <div className="ls-feature-card">
          <div className="ls-feature-icon ls-fi-blue">
            <BarChart2 size={20} />
          </div>
          <div className="ls-feature-text">
            <h3>10 Interactive Charts</h3>
            <p>Bar, line, area, pie, histogram, boxplot, scatter, and correlation heatmaps.</p>
          </div>
        </div>
        <div className="ls-feature-card">
          <div className="ls-feature-icon ls-fi-blue">
            <ShieldCheck size={20} />
          </div>
          <div className="ls-feature-text">
            <h3>Private by Design</h3>
            <p>Rule-based analytics with no cloud AI services.</p>
          </div>
        </div>
      </div>

      {/* Drag overlay message */}
      {isDragging && (
        <div className="ls-drag-overlay">
          <FileSpreadsheet size={48} />
          <h2>Drop your file to analyze</h2>
        </div>
      )}
    </div>
  )
}
