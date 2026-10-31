import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { X } from 'lucide-react'
import { api, errorMessage } from '../services/api'
import { useAuth } from './AuthContext'
import Avatar from '../components/Avatar'
import { Notification, Page } from '../types'
import { timeAgo } from '../utils'
import './NotificationContext.css'

type NotificationContextValue = {
  notifications: Notification[]
  unread: number
  loading: boolean
  error: string
  refresh: () => Promise<void>
  markRead: (notification: Notification) => Promise<void>
  markAllRead: () => Promise<void>
  openNotification: (notification: Notification) => Promise<void>
}
const NotificationContext = createContext<NotificationContextValue | null>(null)

export function notificationLabel(kind: Notification['kind']) {
  return {
    like: 'liked your post', comment: 'commented on your post', follow: 'started following you',
    message: 'sent you a message', call: 'started a call with you', missed_call: 'missed your call',
    declined_call: 'declined your call', mention: 'mentioned you', story_reply: 'replied to your story',
    story_reaction: 'reacted to your story',
  }[kind]
}

function notificationPath(notification: Notification) {
  if (['message', 'call', 'missed_call', 'declined_call'].includes(notification.kind)) return '/messages'
  if (notification.story && notification.story_author_id) return `/?story=${notification.story_author_id}`
  if (notification.post) return `/?post=${notification.post}`
  return `/u/${notification.actor.username}`
}

function websocketUrl() {
  const configured = import.meta.env.VITE_NOTIFICATIONS_WS_URL as string | undefined
  if (configured) return configured
  if (import.meta.env.PROD) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}/ws/notifications/`
  }
  const backend = new URL(import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001/api', window.location.origin)
  return `${backend.protocol === 'https:' ? 'wss:' : 'ws:'}//${backend.host}/ws/notifications/`
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const userId = user?.id
  const navigate = useNavigate()
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unread, setUnread] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [toasts, setToasts] = useState<Notification[]>([])
  const notificationsRef = useRef<Notification[]>([])
  const toastIdsRef = useRef(new Set<number>())
  const toastTimersRef = useRef(new Map<number, number>())
  const bootstrappedRef = useRef(false)

  const pushToast = useCallback((notification: Notification) => {
    if (toastIdsRef.current.has(notification.id)) return
    toastIdsRef.current.add(notification.id)
    setToasts(current => [notification, ...current].slice(0, 4))
    const timer = window.setTimeout(() => {
      setToasts(current => current.filter(item => item.id !== notification.id))
      toastIdsRef.current.delete(notification.id)
      toastTimersRef.current.delete(notification.id)
    }, 8500)
    toastTimersRef.current.set(notification.id, timer)
  }, [])

  const upsert = useCallback((notification: Notification, showToast: boolean) => {
    const exists = notificationsRef.current.some(item => item.id === notification.id)
    const next = exists
      ? notificationsRef.current.map(item => item.id === notification.id ? notification : item)
      : [notification, ...notificationsRef.current].slice(0, 50)
    notificationsRef.current = next
    setNotifications(next)
    if (showToast && !exists && !notification.is_read) pushToast(notification)
  }, [pushToast])

  const refresh = useCallback(async () => {
    if (!userId) return
    try {
      const { data } = await api.get<Page<Notification> & { unread_count: number }>('/notifications/')
      const rows = data.results || []
      const known = new Set(notificationsRef.current.map(item => item.id))
      notificationsRef.current = rows
      setNotifications(rows)
      setUnread(data.unread_count || 0)
      if (!bootstrappedRef.current) {
        rows.filter(item => !item.is_read).slice(0, 3).forEach(pushToast)
        bootstrappedRef.current = true
      } else {
        rows.filter(item => !known.has(item.id) && !item.is_read).forEach(pushToast)
      }
      setError('')
    } catch (cause) {
      setError(errorMessage(cause))
    } finally {
      setLoading(false)
    }
  }, [pushToast, userId])

  const markRead = useCallback(async (notification: Notification) => {
    if (!notification.is_read) {
      try { await api.patch(`/notifications/${notification.id}/read/`) } catch { /* Keep the popup navigable during a temporary API outage. */ }
      const next = notificationsRef.current.map(item => item.id === notification.id ? { ...item, is_read: true } : item)
      notificationsRef.current = next
      setNotifications(next)
      setUnread(value => Math.max(0, value - 1))
    }
    setToasts(current => current.filter(item => item.id !== notification.id))
    const timer = toastTimersRef.current.get(notification.id)
    if (timer) window.clearTimeout(timer)
    toastTimersRef.current.delete(notification.id)
    toastIdsRef.current.delete(notification.id)
  }, [])

  const markAllRead = useCallback(async () => {
    try {
      await api.post('/notifications/read-all/')
      const next = notificationsRef.current.map(item => ({ ...item, is_read: true }))
      notificationsRef.current = next
      setNotifications(next)
      setUnread(0)
      setToasts([])
      toastTimersRef.current.forEach(timer => window.clearTimeout(timer))
      toastTimersRef.current.clear()
      toastIdsRef.current.clear()
    } catch (cause) { setError(errorMessage(cause)) }
  }, [])

  const openNotification = useCallback(async (notification: Notification) => {
    await markRead(notification)
    navigate(notificationPath(notification))
  }, [markRead, navigate])

  useEffect(() => {
    notificationsRef.current = []
    toastIdsRef.current.clear()
    bootstrappedRef.current = false
    setNotifications([]); setUnread(0); setToasts([]); setLoading(Boolean(userId)); setError('')
    toastTimersRef.current.forEach(timer => window.clearTimeout(timer))
    toastTimersRef.current.clear()
    if (!userId) return

    void refresh()
    let stopped = false
    let attempts = 0
    let reconnectTimer = 0
    let activeSocket: WebSocket | null = null
    const connect = () => {
      if (stopped) return
      const socket = new WebSocket(websocketUrl())
      activeSocket = socket
      socket.onopen = () => {
        attempts = 0
        const token = localStorage.getItem('access')
        if (!token) { socket.close(4401); return }
        socket.send(JSON.stringify({ type: 'authenticate', token }))
      }
      socket.onmessage = event => {
        let payload: { type?: string; unread_count?: number; notification?: Notification; notification_id?: number }
        try { payload = JSON.parse(event.data) } catch { return }
        if (typeof payload.unread_count === 'number') setUnread(payload.unread_count)
        if (payload.type === 'notification.created' && payload.notification) upsert(payload.notification, true)
        if (payload.type === 'notification.read' && payload.notification_id) {
          const next = notificationsRef.current.map(item => item.id === payload.notification_id ? { ...item, is_read: true } : item)
          notificationsRef.current = next; setNotifications(next)
          setToasts(current => current.filter(item => item.id !== payload.notification_id))
          const timer = toastTimersRef.current.get(payload.notification_id)
          if (timer) window.clearTimeout(timer)
          toastTimersRef.current.delete(payload.notification_id)
          toastIdsRef.current.delete(payload.notification_id)
        }
        if (payload.type === 'notifications.read_all') {
          const next = notificationsRef.current.map(item => ({ ...item, is_read: true }))
          notificationsRef.current = next; setNotifications(next); setToasts([])
          toastTimersRef.current.forEach(timer => window.clearTimeout(timer))
          toastTimersRef.current.clear(); toastIdsRef.current.clear()
        }
      }
      socket.onclose = event => {
        if (event.code === 4401) void api.get('/notifications/').catch(() => {})
        if (!stopped) {
          const delay = Math.min(30000, 1000 * (2 ** Math.min(attempts, 5)))
          attempts += 1
          reconnectTimer = window.setTimeout(connect, delay)
        }
      }
    }
    connect()
    const poll = window.setInterval(() => { if (document.visibilityState === 'visible') void refresh() }, 30000)
    return () => {
      stopped = true
      activeSocket?.close(1000, 'Notification client disconnected')
      window.clearInterval(poll)
      window.clearTimeout(reconnectTimer)
      toastTimersRef.current.forEach(timer => window.clearTimeout(timer))
      toastTimersRef.current.clear()
    }
  }, [refresh, upsert, userId])

  const value = useMemo(() => ({ notifications, unread, loading, error, refresh, markRead, markAllRead, openNotification }),
    [notifications, unread, loading, error, refresh, markRead, markAllRead, openNotification])

  return <NotificationContext.Provider value={value}>
    {children}
    <aside className="notification-toasts" aria-live="polite" aria-label="New notifications">
      {toasts.map(notification => <div className="notification-toast" key={notification.id}>
        <button className="notification-toast-open" onClick={() => void openNotification(notification)}>
          <span className="notification-toast-avatar"><Avatar user={notification.actor} size="sm"/><i/></span>
          <span className="notification-toast-copy"><span><strong>{notification.actor.full_name || notification.actor.username}</strong> {notificationLabel(notification.kind)}</span><time>{timeAgo(notification.created_at)}</time></span>
        </button>
        <button className="notification-toast-close" aria-label="Dismiss notification" onClick={() => {
          setToasts(current => current.filter(item => item.id !== notification.id))
          toastIdsRef.current.delete(notification.id)
          const timer = toastTimersRef.current.get(notification.id)
          if (timer) window.clearTimeout(timer)
          toastTimersRef.current.delete(notification.id)
        }}><X size={15}/></button>
      </div>)}
    </aside>
  </NotificationContext.Provider>
}

export function useNotifications() {
  const context = useContext(NotificationContext)
  if (!context) throw new Error('useNotifications must be used inside NotificationProvider')
  return context
}
