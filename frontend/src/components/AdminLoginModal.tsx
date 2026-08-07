import { useState, type FormEvent } from 'react'
import { KeyRound, User, X } from 'lucide-react'
import { adminLogin } from '../lib/api'

interface AdminLoginModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (token: string, username: string) => void
}

export function AdminLoginModal({ isOpen, onClose, onSuccess }: AdminLoginModalProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!username || !password) {
      setError('Please enter both username and password.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await adminLogin(username, password)
      onSuccess(res.token, res.username)
      setUsername('')
      setPassword('')
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box animate-fade-in" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>Admin Login</h3>
          <button className="ghost small icon-only" type="button" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          {error && <div className="error-banner">{error}</div>}

          <label className="field">
            <span>Username</span>
            <div className="input-with-icon">
              <User size={16} />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter admin username"
                autoFocus
              />
            </div>
          </label>

          <label className="field">
            <span>Password</span>
            <div className="input-with-icon">
              <KeyRound size={16} />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter admin password"
              />
            </div>
          </label>

          <div className="modal-actions">
            <button className="secondary" type="button" onClick={onClose}>
              Cancel
            </button>
            <button className="primary" type="submit" disabled={loading}>
              {loading ? 'Authenticating...' : 'Sign In'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
