import { useEffect } from 'react'
import { AtSign, Bell, CheckCheck, Heart, Mail, MessageCircle, Phone, PhoneMissed, Sparkles, UserPlus } from 'lucide-react'
import { Notification as Notice } from '../types'
import Avatar from '../components/Avatar'
import { useNotifications, notificationLabel } from '../context/NotificationContext'
import { timeAgo } from '../utils'

const icons: Record<Notice['kind'], typeof Heart> = {
  like: Heart, comment: MessageCircle, follow: UserPlus, message: Mail, call: Phone,
  missed_call: PhoneMissed, declined_call: PhoneMissed, mention: AtSign,
  story_reply: MessageCircle, story_reaction: Heart,
}

export default function Notifications() {
  const { notifications, unread, loading, error, refresh, openNotification, markAllRead } = useNotifications()
  useEffect(() => { void refresh() }, [refresh])

  return <div className="page-column">
    <div className="page-heading"><div><p className="eyebrow">STAY IN THE LOOP</p><h1>Your notifications</h1><p className="muted">The little moments when someone thinks of you.</p></div><span className="heading-spark"><Bell size={19}/></span></div>
    <div className="notifications-card card">
      <div className="notifications-toolbar"><div><strong>Recent activity</strong><span>{unread ? `${unread} unread` : 'You’re all caught up'}</span></div>{unread > 0 && <button className="text-link" onClick={() => void markAllRead()}><CheckCheck size={15}/> Mark all read</button>}</div>
      {error && <p className="form-error">{error}</p>}
      {loading ? <div className="skeleton-stack"><div className="skeleton-card"><div className="skeleton-line"/><div className="skeleton-line short"/></div></div>
        : notifications.length === 0 ? <div className="empty-state compact"><span className="empty-icon"><Sparkles/></span><h3>A quiet moment</h3><p>Likes, comments, and new followers will show up here.</p></div>
          : <div className="notification-list">{notifications.map(item => {
            const Icon = icons[item.kind]
            return <button className={`notification-item ${item.is_read ? 'read' : 'unread'}`} key={item.id} onClick={() => void openNotification(item)}>
              <span className="notification-avatar"><Avatar user={item.actor}/><i className={`activity-icon activity-${item.kind}`}><Icon size={12} fill={item.kind === 'like' || item.kind === 'story_reaction' ? 'currentColor' : 'none'}/></i></span>
              <span className="notification-copy"><span><strong>{item.actor.full_name || item.actor.username}</strong> {notificationLabel(item.kind)}{item.post_preview && item.post && <em> “{item.post_preview.slice(0, 90)}”</em>}</span><time>{timeAgo(item.created_at)}</time></span>
              {!item.is_read && <i className="unread-dot"/>}
            </button>
          })}</div>}
    </div>
  </div>
}
