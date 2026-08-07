import { useEffect, useState } from 'react'
import { BarChart3, Database, ShieldCheck, Users, Zap } from 'lucide-react'
import { getVisitorCount } from '../lib/api'

interface StartScreenProps {
  onStart: () => Promise<void> | void
  onAdminClick: () => void
}

export function StartScreen({ onStart, onAdminClick }: StartScreenProps) {
  const [visitorCount, setVisitorCount] = useState<number | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<boolean>(false)
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)

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

    return () => {
      isMounted = false
    }
  }, [])

  const handleStartClick = async () => {
    if (isSubmitting) return
    setIsSubmitting(true)
    try {
      if (visitorCount !== null) {
        setVisitorCount((prev) => (prev !== null ? prev + 1 : 1))
      }
      await onStart()
    } catch {
      // Ignore network failure when offline
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="start-screen animate-fade-in">
      <div className="start-topbar">
        <div className="brand-badge">
          <Database size={16} />
          <span>Universal Data Analytics</span>
        </div>
        <button className="ghost small" type="button" onClick={onAdminClick}>
          Admin Login
        </button>
      </div>

      <div className="start-hero">
        <span className="eyebrow">Enterprise-Grade In-Memory Analytics</span>
        <h1 className="start-title">
          Analyze Messy Data <br />
          <span className="gradient-text">Instantly & Privately</span>
        </h1>
        <p className="start-subtitle">
          Upload any raw CSV or Excel file. Automatic cleaning, header detection, multi-type chart recommendations, rule-based insights, and multi-format exports — 100% free & offline safe.
        </p>

        <div className="visitor-count-card">
          <div className="visitor-count-header">
            <Users size={18} className="visitor-icon" />
            <span>Total Visitors</span>
          </div>
          <div className="visitor-count-number">
            {loading ? (
              <span className="visitor-skeleton">...</span>
            ) : error ? (
              <span className="visitor-fallback">Unavailable</span>
            ) : (
              (visitorCount ?? 0).toLocaleString()
            )}
          </div>
          <div className="visitor-count-footer">
            Visited this Analytics Platform
          </div>
        </div>

        <div className="start-cta-group">
          <button
            className="start-btn primary-lg"
            type="button"
            onClick={() => void handleStartClick()}
            disabled={isSubmitting}
          >
            <Zap size={20} />
            <span>{isSubmitting ? 'Starting...' : 'Start Analytics Engine'}</span>
          </button>
        </div>

        <div className="feature-grid">
          <div className="feature-card">
            <div className="feature-icon"><Database size={20} /></div>
            <h3>Raw File Cleaning</h3>
            <p>Smart header row detection, ignores merged title banners and total/subtotal summary footers.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon"><BarChart3 size={20} /></div>
            <h3>10 Visualizations</h3>
            <p>Automated line, area, bar, pie, donut, histogram, boxplot, scatter, and correlation heatmaps.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon"><ShieldCheck size={20} /></div>
            <h3>Zero Cloud AI</h3>
            <p>100% offline-capable, open-source, private, commercial-use safe, and free forever.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

