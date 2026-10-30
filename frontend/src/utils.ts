export function timeAgo(value: string) {
  const seconds = Math.max(1, Math.floor((Date.now() - new Date(value).getTime()) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: new Date(value).getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined })
}
export function initials(name?: string, username?: string) { return (name || username || '?').trim().split(/[\s._-]+/).slice(0,2).map(part => part[0]).join('').toUpperCase() }
export function formatCount(value = 0) { return Intl.NumberFormat(undefined, { notation: value > 9999 ? 'compact' : 'standard', maximumFractionDigits: 1 }).format(value) }
