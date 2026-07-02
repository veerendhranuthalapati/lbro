import { Bell, Search, RefreshCw } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { useState } from 'react'
import { cn } from '@/utils'

const PAGE_TITLES: Record<string, string> = {
  '/dashboard':      'Dashboard',
  '/incidents':      'Incidents',
  '/notifications':  'Notifications',
  '/compliance':     'Compliance',
  '/ml-insights':    'ML Insights',
  '/evidence':       'Evidence',
  '/infrastructure': 'Infrastructure',
  '/users':          'Users',
  '/settings':       'Settings',
}

interface Props { alertCount?: number }

export function Navbar({ alertCount = 0 }: Props) {
  const { pathname } = useLocation()
  const title = PAGE_TITLES[pathname] ?? 'LBRO'
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = () => {
    setRefreshing(true)
    setTimeout(() => setRefreshing(false), 1000)
    window.location.reload()
  }

  return (
    <header
      className="sticky top-0 z-20 flex items-center gap-4 px-6 h-14 border-b"
      style={{ background: '#f9f5ef', borderColor: '#c8c2b8' }}
    >
      {/* Page title */}
      <div className="flex-1 flex items-baseline gap-3">
        <h1
          className="font-display text-2xl leading-none"
          style={{ color: '#111111', letterSpacing: '0.04em' }}
        >
          {title.toUpperCase()}
        </h1>
        <div
          className="text-[10px] font-mono flex items-center gap-1.5"
          style={{ color: '#6b6560' }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full animate-pulse"
            style={{ background: '#4ade80' }}
            aria-hidden="true"
          />
          Live
        </div>
      </div>

      {/* Search */}
      <div className="relative hidden md:block">
        <Search
          className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5"
          style={{ color: '#6b6560' }}
          aria-hidden="true"
        />
        <input
          placeholder="Search incidents..."
          className="w-44 pl-8 pr-3 py-1.5 text-xs border"
          style={{
            background: '#f0ebe2',
            borderColor: '#c8c2b8',
            borderRadius: 4,
            color: '#111111',
            outline: 'none',
          }}
          onFocus={e => (e.target.style.borderColor = '#e54e1b')}
          onBlur={e => (e.target.style.borderColor = '#c8c2b8')}
        />
      </div>

      {/* Refresh */}
      <button
        onClick={handleRefresh}
        className="p-1.5 rounded transition-colors"
        style={{ color: '#6b6560' }}
        aria-label="Refresh"
      >
        <RefreshCw className={cn('w-4 h-4', refreshing && 'animate-spin')} />
      </button>

      {/* Alerts bell */}
      <button
        className="relative p-1.5 rounded transition-colors"
        style={{ color: '#6b6560' }}
        aria-label={`${alertCount} alert${alertCount !== 1 ? 's' : ''}`}
      >
        <Bell className="w-4 h-4" aria-hidden="true" />
        {alertCount > 0 && (
          <span
            className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full text-[9px] font-bold text-white flex items-center justify-center"
            style={{ background: '#e54e1b' }}
          >
            {alertCount > 9 ? '9+' : alertCount}
          </span>
        )}
      </button>

      {/* Avatar */}
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white"
        style={{ background: '#e54e1b' }}
        aria-label="Admin user"
      >
        A
      </div>
    </header>
  )
}
