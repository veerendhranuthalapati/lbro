import { Bell, Search, RefreshCw } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { cn } from '@/utils'
import { useAuthStore } from '@/store/authStore'

const PAGE_TITLES: Record<string, string> = {
  '/dashboard':      'Dashboard',
  '/incidents':      'Incidents',
  '/notifications':  'Notifications',
  '/compliance':     'Compliance',
  '/ml-insights':    'ML Insights',
  '/threat-intel':   'Threat Intel',
  '/evidence':       'Evidence',
  '/infrastructure': 'Infrastructure',
  '/audit-logs':     'Audit Logs',
  '/users':          'Users',
  '/settings':       'Settings',
  '/incidents/new':  'New Incident',
}

function getPageTitle(pathname: string): string {
  if (PAGE_TITLES[pathname]) return PAGE_TITLES[pathname]
  if (pathname.startsWith("/incidents/")) return "Incident Detail"
  return "LBRO"
}

function getUserInitials(name: string | undefined, email: string | undefined): string {
  if (name && name.trim()) {
    const parts = name.trim().split(" ")
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    return parts[0].slice(0, 2).toUpperCase()
  }
  if (email) return email.slice(0, 2).toUpperCase()
  return "U"
}

interface Props { alertCount?: number }

export function Navbar({ alertCount = 0 }: Props) {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const user = useAuthStore(s => s.user)
  const title = getPageTitle(pathname)
  const [refreshing, setRefreshing] = useState(false)

  const initials = getUserInitials(user?.name, user?.email)

  const handleRefresh = () => {
    setRefreshing(true)
    setTimeout(() => setRefreshing(false), 1000)
    window.location.reload()
  }

  const openSearch = () =>
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }))

  return (
    <header
      className="sticky top-0 z-20 flex items-center gap-4 px-6 h-14 border-b"
      style={{ background: "#f9f5ef", borderColor: "#c8c2b8" }}
    >
      {/* Page title */}
      <div className="flex-1 flex items-baseline gap-3">
        <h1
          className="font-display text-2xl leading-none"
          style={{ color: "#111111", letterSpacing: "0.04em" }}
        >
          {title.toUpperCase()}
        </h1>
        <div
          className="text-[10px] font-mono flex items-center gap-1.5"
          style={{ color: "#6b6560" }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full animate-pulse"
            style={{ background: "#4ade80" }}
            aria-hidden="true"
          />
          Live
        </div>
      </div>

      {/* Global Search trigger */}
      <button
        className="hidden md:flex items-center gap-2 px-3 py-1.5 text-xs border"
        style={{
          background: "#f0ebe2",
          borderColor: "#c8c2b8",
          borderRadius: 4,
          color: "#6b6560",
          cursor: "pointer",
          width: 176,
        }}
        onClick={openSearch}
        aria-label="Open global search (Cmd+K)"
      >
        <Search className="w-3.5 h-3.5 flex-shrink-0" aria-hidden="true" />
        <span style={{ flex: 1, textAlign: "left" }}>Search incidents</span>
        <kbd style={{
          fontSize: 9, background: "#e8e2d9", border: "1px solid #c8c2b8",
          borderRadius: 3, padding: "1px 5px", fontFamily: "JetBrains Mono, monospace",
          lineHeight: 1.6, letterSpacing: "0.04em",
        }}>
          ⌘K
        </kbd>
      </button>

      {/* Refresh */}
      <button
        onClick={handleRefresh}
        className="p-1.5 rounded transition-colors"
        style={{ color: "#6b6560" }}
        aria-label="Refresh page"
      >
        <RefreshCw className={cn("w-4 h-4", refreshing && "animate-spin")} />
      </button>

      {/* Alerts bell */}
      <button
        onClick={() => navigate("/notifications")}
        className="relative p-1.5 rounded transition-colors"
        style={{ color: "#6b6560" }}
        aria-label={alertCount + " active alert" + (alertCount !== 1 ? "s" : "")}
      >
        <Bell className="w-4 h-4" aria-hidden="true" />
        {alertCount > 0 && (
          <span
            className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full text-[9px] font-bold text-white flex items-center justify-center"
            style={{ background: "#e54e1b" }}
          >
            {alertCount > 9 ? "9+" : alertCount}
          </span>
        )}
      </button>

      {/* Avatar */}
      <button
        onClick={() => navigate("/settings")}
        className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white"
        style={{ background: "#e54e1b" }}
        title={user?.name ?? user?.email ?? "Settings"}
        aria-label="Go to settings"
      >
        {initials}
      </button>
    </header>
  )
}
