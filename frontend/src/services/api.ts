import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

const baseURL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001/api'
export const api = axios.create({ baseURL, timeout: 20000 })
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('access')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
let refreshTask: Promise<string | null> | null = null
api.interceptors.response.use(response => response, async (error: AxiosError) => {
  const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
  if (error.response?.status === 401 && original && !original._retried && !original.url?.includes('/auth/')) {
    original._retried = true
    if (!refreshTask) {
      const refresh = localStorage.getItem('refresh')
      refreshTask = refresh ? axios.post(`${baseURL}/auth/refresh/`, { refresh }).then(({ data }) => {
        localStorage.setItem('access', data.access)
        if (data.refresh) localStorage.setItem('refresh', data.refresh)
        return data.access as string
      }).catch(() => null).finally(() => { refreshTask = null }) : Promise.resolve(null)
    }
    const token = await refreshTask
    if (token) { original.headers.Authorization = `Bearer ${token}`; return api(original) }
    localStorage.removeItem('access'); localStorage.removeItem('refresh'); localStorage.removeItem('user')
  }
  return Promise.reject(error)
})

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Record<string, unknown> | undefined
    if (typeof data?.detail === 'string') return data.detail
    if (data) return Object.entries(data).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : String(value)}`).join(' · ')
  }
  return 'Something went wrong. Please try again.'
}
