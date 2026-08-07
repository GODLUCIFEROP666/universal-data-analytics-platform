import type { AdminAuthResponse, AdminStats, AnalysisEnvelope, FilterState, UploadInspection } from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8001'

function buildFormData(file: File, payload: Partial<FilterState> & { sheet_name?: string }) {
  const formData = new FormData()
  formData.append('file', file)
  if (payload.sheet_name) {
    formData.append('sheet_name', payload.sheet_name)
  }
  if (payload.search_query || payload.category_filters || payload.numeric_ranges || payload.date_ranges || payload.sort_by) {
    formData.append('filters', JSON.stringify({
      search_query: payload.search_query ?? '',
      category_filters: payload.category_filters ?? {},
      numeric_ranges: payload.numeric_ranges ?? {},
      date_ranges: payload.date_ranges ?? {},
      sort_by: payload.sort_by ?? '',
      sort_direction: payload.sort_direction ?? 'desc',
      page: payload.page ?? 1,
      page_size: payload.page_size ?? 50,
    }))
  }
  if (payload.page !== undefined) formData.append('page', String(payload.page))
  if (payload.page_size !== undefined) formData.append('page_size', String(payload.page_size))
  if (payload.sort_by !== undefined) formData.append('sort_by', payload.sort_by)
  if (payload.sort_direction !== undefined) formData.append('sort_direction', payload.sort_direction)
  return formData
}

export async function inspectUpload(file: File, signal?: AbortSignal): Promise<UploadInspection> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: formData, signal })
  return handleJson<UploadInspection>(response)
}

export async function analyzeDataset(file: File, payload: Partial<FilterState> & { sheet_name?: string }, signal?: AbortSignal): Promise<AnalysisEnvelope> {
  const formData = buildFormData(file, payload)
  const response = await fetch(`${API_BASE}/api/analyze`, { method: 'POST', body: formData, signal })
  return handleJson<AnalysisEnvelope>(response)
}

export async function exportProcessedExcel(file: File, payload: Partial<FilterState> & { sheet_name?: string }): Promise<Blob> {
  const formData = buildFormData(file, payload)
  const response = await fetch(`${API_BASE}/api/export/excel`, { method: 'POST', body: formData })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return response.blob()
}

export async function exportProcessedCsv(file: File, payload: Partial<FilterState> & { sheet_name?: string }): Promise<Blob> {
  const formData = buildFormData(file, payload)
  const response = await fetch(`${API_BASE}/api/export/csv`, { method: 'POST', body: formData })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return response.blob()
}

export async function resetRemoteState(): Promise<void> {
  await fetch(`${API_BASE}/api/reset`, { method: 'POST' }).catch(() => undefined)
}

export async function getVisitorCount(): Promise<{ visitor_count: number }> {
  const response = await fetch(`${API_BASE}/api/visitor-count`)
  return handleJson<{ visitor_count: number }>(response)
}

export async function sessionStart(): Promise<{ visitor_count: number }> {
  const response = await fetch(`${API_BASE}/api/session/start`, { method: 'POST' })
  return handleJson<{ visitor_count: number }>(response)
}

export function sessionEndBeacon(): void {
  if (navigator.sendBeacon) {
    navigator.sendBeacon(`${API_BASE}/api/session/end`)
  } else {
    void fetch(`${API_BASE}/api/session/end`, { method: 'POST', keepalive: true }).catch(() => undefined)
  }
}

export async function adminLogin(username: string, password: string): Promise<AdminAuthResponse> {
  const response = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  })
  return handleJson<AdminAuthResponse>(response)
}

export async function adminChangePassword(old_password: string, new_password: string, token: string): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/api/auth/change-password`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({ old_password, new_password })
  })
  return handleJson<{ message: string }>(response)
}

export async function adminGetStats(token: string): Promise<AdminStats> {
  const response = await fetch(`${API_BASE}/api/admin/stats`, {
    method: 'GET',
    headers: { Authorization: `Bearer ${token}` }
  })
  return handleJson<AdminStats>(response)
}

async function handleJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return response.json() as Promise<T>
}

async function readError(response: Response): Promise<string> {
  try {
    const data = await response.json()
    return data?.detail ?? 'Request failed'
  } catch {
    return 'Request failed'
  }
}
