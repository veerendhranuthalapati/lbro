import { Bell, Search, RefreshCw } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { cn } from '@/utils'
import { useAuthStore } from '@/store/authStore'
import { ProjectSwitcher } from '@/components/layout/ProjectSwitcher'
import { ProjectContextBar } from '@/components/layout/ProjectContextBar'
import { PROJECT_SCOPED_QUERY_PREFIXES } from '@/store/projectStore'
import { getPageTitle } from '@/lib/navigation'
import { LBRO } from '@/lib/tokens'

function getUserInitials(name: string | undefined, email: string | undefined): string {
  if (name?.trim()) {
    const parts = name.trim().split(' ')
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    return parts[0].slice(0, 2).toUpperCase()
  }
  if (email) return email.slice(0, 2).toUpperCase()
  return 'U'
}

interface Props { alertCount?: number }

export function Navbar({ alertCount = 0 }: Props) {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const user = useAuthStore(s => s.user)
  const title = getPageTitle(pathname)
  const [refreshing, setRefreshing] = useState(false)
  const initials = getUserInitials(user?.name, user?.email)
  const isPlatformView = pathname.startsWith('/users')
    || pathname.startsWith('/audit-logs')
    || (pathname.startsWith('/security-overview') && (user?.role === 'admin' || (user?.role as string) === 'super_admin'))

  const handleRefresh = () => {
    setRefreshing(true)
    for (const prefix of PROJECT_SCOPED_QUERY_PREFIXES) {
      queryClient.invalidateQueries({ queryKey: [prefix] })
    }
    queryClient.invalidateQueries({ queryKey: ['projects'] })
    setTimeout(() => setRefreshing(false), 1000)
  }

  const openSearch = () =>
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }))

  return (
    <header
      className="sticky top-0 z-20 flex items-center gap-4 px-6 min-h-14 py-2 border-b"
      style={{ background: LBRO.cream, borderColor: LBRO.border }}
    >
      <div className="flex-1 flex flex-col gap-0.5 min-w-0">
        <div className="flex items-center gap-3 flex-wrap">
          <h1
            className="font-display text-xl leading-none shrink-0"
            style={{ color: LBRO.black, letterSpacing: '0.04em' }}
          >
            {title}
          </h1>
          <ProjectSwitcher />
          {isPlatformView && (
            <span
              className="text-[10px] uppercase tracking-wide font-semibold px-2 py-0.5 rounded"
              style={{ background: LBRO.parchment, color: LBRO.orange }}
            >
              Platform view
            </span>
          )}
          <div
            className="text-[10px] font-mono flex items-center gap-1.5 shrink-0 ml-auto md:ml-0"
            style={{ color: LBRO.gray }}
          >
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: LBRO.success }} aria-hidden />
            Live
          </div>
        </div>
        <ProjectContextBar />
      </div>

      <button
        type="button"
        className="hidden md:flex items-center gap-2 px-3 py-1.5 text-xs border"
        style={{
          background: LBRO.offwhite,
          borderColor: LBRO.border,
          borderRadius: 4,
          color: LBRO.gray,
          width: 176,
        }}
        onClick={openSearch}
        aria-label="Open global search (Cmd+K)"
      >
        <Search className="w-3.5 h-3.5 shrink-0" aria-hidden />
        <span className="flex-1 text-left">Search incidents</span>
        <kbd className="text-[9px] px-1 rounded" style={{ background: LBRO.parchment, border: `1px solid ${LBRO.border}` }}>
          ⌘K
        </kbd>
      </button>

      <button
        type="button"
        onClick={handleRefresh}
        className="p-1.5 rounded transition-colors"
        style={{ color: LBRO.gray }}
        aria-label="Refresh page data"
      >
        <RefreshCw className={cn('w-4 h-4', refreshing && 'animate-spin')} />
      </button>

      <button
        type="button"
        onClick={() => navigate('/notifications')}
        className="relative p-1.5 rounded transition-colors"
        style={{ color: LBRO.gray }}
        aria-label={`${alertCount} active alert${alertCount !== 1 ? 's' : ''}`}
      >
        <Bell className="w-4 h-4" aria-hidden />
        {alertCount > 0 && (
          <span
            className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full text-[9px] font-bold text-white flex items-center justify-center"
            style={{ background: LBRO.orange }}
          >
            {alertCount > 9 ? '9+' : alertCount}
          </span>
        )}
      </button>

      <button
        type="button"
        onClick={() => navigate('/settings')}
        className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
        style={{ background: LBRO.orange }}
        title={user?.name ?? user?.email ?? 'Profile settings'}
        aria-label="Open profile settings"
      >
        {initials}
      </button>
    </header>
  )
}
