import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, ShieldAlert, FileText, Lock,
  Cloud, Settings, LogOut, Brain, Bell, Users,
  Target, ClipboardList, ShieldCheck, BarChart2, Map, ClipboardCheck,
  Layers, BookOpen,
} from 'lucide-react'
import type { LucideProps } from 'lucide-react'
import { cn } from '@/utils'
import { useAuthStore } from '@/store/authStore'
import { useProjectStore } from '@/store/projectStore'
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
  { to: '/dashboard',      icon: LayoutDashboard, label: 'Application Security' },
  { to: '/security-score', icon: ShieldCheck,     label: 'Security Score' },
  { to: '/weekly-report',  icon: BarChart2,       label: 'Weekly Report' },
  { to: '/incidents',      icon: ShieldAlert,     label: 'Security Events' },
  { to: '/notifications',  icon: Bell,            label: 'Notifications' },
  { to: '/compliance',       icon: FileText,        label: 'Compliance' },
  { to: '/compliance/audit', icon: ClipboardCheck,  label: 'Audit Report' },
  { to: '/ml-insights',    icon: Brain,           label: 'Threat Detection' },
  { to: '/threat-intel',   icon: Target,          label: 'Security Activity' },
  { to: '/evidence',       icon: Lock,            label: 'Evidence Vault' },
  { to: '/infrastructure', icon: Cloud,           label: 'Infrastructure' },
  { to: '/audit-logs',     icon: ClipboardList,   label: 'Security History' },
  { to: '/users',          icon: Users,           label: 'Users' },
  { to: '/roadmap',        icon: Map,             label: 'Roadmap' },
  { to: '/docs',           icon: BookOpen,        label: 'API Docs' },
  { to: '/settings',       icon: Settings,        label: 'Settings' },
]

export function Sidebar() {
  const logout = useAuthStore(s => s.logout)
  const navigate = useNavigate()
  const location = useLocation()
  const currentProject = useProjectStore(s => s.currentProject)

  const handleLogout = () => {
    auditAction('auth:logout', 'session', 'current')
    logger.info('User logged out')
    logout()
    navigate('/login', { replace: true })
  }

  // First two letters of project name for the badge, or generic icon
  const projectInitials = currentProject
    ? currentProject.name.slice(0, 2).toUpperCase()
    : null

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

      {/* Project switcher */}
      <div
        className="flex items-center justify-center py-2 border-b"
        style={{ borderColor: '#1e1e1e' }}
      >
        <button
          onClick={() => navigate('/projects')}
          title={currentProject ? `Project: ${currentProject.name}` : 'Select project'}
          aria-label={currentProject ? `Switch project (current: ${currentProject.name})` : 'Select a project'}
          className={cn(
            'flex items-center justify-center w-9 h-9 rounded text-xs font-bold transition-all focus:outline-none focus:ring-2',
            currentProject
              ? 'text-white'
              : 'text-zinc-600 hover:text-zinc-400 border border-dashed border-zinc-700 hover:border-zinc-500',
          )}
          style={currentProject ? { background: '#2a2a2a', color: '#e54e1b', border: '1px solid #3a3a3a' } : {}}
        >
          {projectInitials ?? <Layers className="w-3.5 h-3.5" aria-hidden="true" />}
        </button>
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
