import { User } from '../types'
import { initials } from '../utils'

export default function Avatar({ user, size = 'md', className = '' }: { user?: Partial<User> | null; size?: 'sm'|'md'|'lg'|'xl'; className?: string }) {
  const label = user?.full_name || user?.username || 'Member'
  return user?.avatar_url
    ? <img className={`avatar avatar-${size} ${className}`} src={user.avatar_url} alt={`${label}'s profile`} />
    : <span className={`avatar avatar-${size} avatar-fallback ${className}`} aria-label={`${label}'s profile`}>{initials(user?.full_name, user?.username)}</span>
}
