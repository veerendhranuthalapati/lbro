import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, ShieldAlert, FileText, Lock,
  Cloud, Settings, LogOut, Brain, Bell, Users,
  Target, ClipboardList,
} from 'lucide-react'
import type { LucideProps } from 'lucide-react'
import { cn } from '@/utils'
import { useAuthStore } from '@/store/authStore'
import { logger, auditAction } from '@/lib/logger'

interface NavItem {
  to: string
  icon: React.FC<LucideProps>
  label: string
}

// All authenticated users see all nav items.
// Backend enforces access; sidebar never hides pages based on JWT permissions
// because missing/empty permissions would cause the entire sidebar to collapse.
const NAV: NavItem[] = [
  { to: '/dashboard',      icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/incidents',      icon: ShieldAlert,     label: 'Incidents' },
  { to: '/notifications',  icon: Bell,            label: 'Notifications' },
  { to: '/compliance',     icon: FileText,        label: 'Compliance' },
  { to: '/ml-insights',    icon: Brain,           label: 'ML Insights' },
  { to: '/threat-intel',   icon: Target,          label: 'Threat Intel' },
  { to: '/evidence',       icon: Lock,            label: 'Evidence' },
  { to: '/infrastructure', icon: Cloud,           label: 'Infrastructure' },
  { to: '/audit-logs',     icon: ClipboardList,   label: 'Audit Logs' },
  { to: '/users',          icon: Users,           label: 'Users' },
  { to: '/settings',       icon: Settings,        label: 'Settings' },
]

export function Sidebar() {
  const logout = useAuthStore(s => s.logout)
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    auditAction('auth:logout', 'session', 'current')
    logger.info('User logged out')
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <aside
      className="flex flex-col w-14 shrink-0 h-screen sticky top-0 z-30 border-r border-lbro-border"
      style={{ background: '#111111' }}
      role="navigation"
      aria-label="Main navigation"
    >
      <div
        className="flex items-center justify-center h-14 border-b shrink-0"
        style={{ borderColor: '#1e1e1e' }}
      >
        <span
          className="font-display text-xl"
          style={{ color: '#e54e1b', letterSpacing: '0.05em' }}
          aria-label="LBRO"
        >
          LB
        </span>
      </div>

      <nav
        className="flex-1 flex flex-col items-center py-3 gap-1 overflow-y-auto"
        aria-label="Application pages"
      >
        {NAV.map(({ to, icon: Icon, label }) => {
          const isActive =
            location.pathname === to ||
            (to !== '/dashboard' && location.pathname.startsWith(to))
          return (
            <NavLink
              key={to}
              to={to}
              title={label}
              aria-label={label}
              aria-current={isActive ? 'page' : undefined}
              className={cn(
                'flex items-center justify-center w-9 h-9 rounded transition-all focus:outline-none focus:ring-2',
                isActive ? 'text-white' : 'text-zinc-500 hover:text-zinc-300',
              )}
              style={isActive ? { background: '#e54e1b', color: '#fff' } : {}}
            >
              <Icon className="w-4 h-4" aria-hidden="true" />
            </NavLink>
          )
        })}
      </nav>

      <div
        className="flex items-center justify-center py-2 border-t"
        style={{ borderColor: '#1e1e1e' }}
        aria-live="polite"
        aria-label="System live"
      >
        <span
          className="w-1.5 h-1.5 rounded-full animate-pulse"
          style={{ background: '#4ade80' }}
          aria-hidden="true"
        />
      </div>

      <div className="flex items-center justify-center pb-4 pt-1">
        <button
          onClick={handleLogout}
          title="Sign out"
          aria-label="Sign out of LBRO"
          className="flex items-center justify-center w-9 h-9 rounded text-zinc-500 hover:text-red-400 transition-all focus:outline-none focus:ring-2 focus:ring-red-500/50"
        >
          <LogOut className="w-4 h-4" aria-hidden="true" />
        </button>
      </div>
    </aside>
  )
}
