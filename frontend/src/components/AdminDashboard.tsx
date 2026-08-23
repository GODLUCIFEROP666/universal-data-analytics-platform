import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Activity, BarChart2, Eye, KeyRound, LogOut, RefreshCw, UploadCloud, X } from 'lucide-react'
import { adminChangePassword, adminGetStats } from '../lib/api'
import type { AdminStats } from '../types'

interface AdminDashboardProps {
  isOpen: boolean
  token: string
  username: string
  onClose: () => void
  onLogout: () => void
}

export function AdminDashboard({ isOpen, token, username, onClose, onLogout }: AdminDashboardProps) {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passStatus, setPassStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [passLoading, setPassLoading] = useState(false)

  const fetchStats = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const data = await adminGetStats(token)
      setStats(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch admin statistics.')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    if (isOpen && token) {
      void fetchStats()
      const interval = setInterval(() => {
        void fetchStats()
      }, 30000)
      return () => clearInterval(interval)
    }
  }, [isOpen, token, fetchStats])

  if (!isOpen) return null

  const handlePasswordChange = async (e: FormEvent) => {
    e.preventDefault()
    setPassStatus(null)

    if (newPassword !== confirmPassword) {
      setPassStatus({ type: 'error', message: 'New passwords do not match.' })
      return
    }
    if (newPassword.length < 6) {
      setPassStatus({ type: 'error', message: 'Password must be at least 6 characters.' })
      return
    }

    setPassLoading(true)
    try {
      const res = await adminChangePassword(oldPassword, newPassword, token)
      setPassStatus({ type: 'success', message: res.message })
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err: unknown) {
      setPassStatus({ type: 'error', message: err instanceof Error ? err.message : 'Password update failed.' })
    } finally {
      setPassLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box admin-dashboard-box animate-fade-in" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <h3>Admin System Metrics & Security</h3>
            <p className="subtitle">Logged in as <strong>{username}</strong></p>
          </div>
          <div className="toolbar">
            <button className="ghost small" type="button" onClick={() => void fetchStats()} disabled={loading}>
              <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
            </button>
            <button className="ghost small" type="button" onClick={onLogout}>
              <LogOut size={14} /> Logout
            </button>
            <button className="ghost small icon-only" type="button" onClick={onClose}>
              <X size={18} />
            </button>
          </div>
        </div>

        <div className="modal-body admin-body">
          {error && <div className="error-banner">{error}</div>}

          {/* SYSTEM COUNTERS */}
          <div className="admin-stats-grid">
            <div className="admin-stat-card">
              <div className="stat-icon"><Eye size={20} /></div>
              <div>
                <span>Total Visitors</span>
                <strong>{stats ? stats.total_visitors.toLocaleString() : '...'}</strong>
              </div>
            </div>
            <div className="admin-stat-card">
              <div className="stat-icon"><UploadCloud size={20} /></div>
              <div>
                <span>Files Uploaded</span>
                <strong>{stats ? stats.total_uploads.toLocaleString() : '...'}</strong>
              </div>
            </div>
            <div className="admin-stat-card">
              <div className="stat-icon"><BarChart2 size={20} /></div>
              <div>
                <span>Analyses Completed</span>
                <strong>{stats ? stats.total_analyses.toLocaleString() : '...'}</strong>
              </div>
            </div>
            <div className="admin-stat-card">
              <div className="stat-icon"><Activity size={20} /></div>
              <div>
                <span>Current Active Users</span>
                <strong>{stats ? stats.active_users.toLocaleString() : '...'}</strong>
              </div>
            </div>
          </div>

          {/* PASSWORD CHANGE FORM */}
          <section className="password-section">
            <h4>Change Administrator Password</h4>
            {passStatus && (
              <div className={passStatus.type === 'success' ? 'success-banner' : 'error-banner'}>
                {passStatus.message}
              </div>
            )}
            <form onSubmit={handlePasswordChange} className="password-form">
              <label className="field">
                <span>Current Password</span>
                <input
                  type="password"
                  value={oldPassword}
                  onChange={(e) => setOldPassword(e.target.value)}
                  placeholder="Old password"
                />
              </label>

              <div className="range-grid">
                <label className="field">
                  <span>New Password</span>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="New password"
                  />
                </label>
                <label className="field">
                  <span>Confirm New Password</span>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Confirm new password"
                  />
                </label>
              </div>

              <button className="primary" type="submit" disabled={passLoading}>
                <KeyRound size={16} />
                {passLoading ? 'Updating Password...' : 'Update Password'}
              </button>
            </form>
          </section>
        </div>
      </div>
    </div>
  )
}
