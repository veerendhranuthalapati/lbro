import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { LogOut } from 'lucide-react'
import { cn } from '@/utils'
import { useAuthStore } from '@/store/authStore'
import { useProjectStore } from '@/store/projectStore'
import { usePermissions } from '@/hooks/usePermissions'
import { logger, auditAction } from '@/lib/logger'
import {
  NAV_SECTIONS,
  resolveNavHref,
  isNavActive,
  type NavItemDef,
} from '@/lib/navigation'
import { LBRO } from '@/lib/tokens'

function NavItem({
  item,
  href,
  active,
  disabled,
}: {
  item: NavItemDef
  href: string
  active: boolean
  disabled?: boolean
}) {
  const Icon = item.icon
  const className = cn(
    'flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-all focus:outline-none focus:ring-2 focus:ring-offset-1',
    active ? 'font-medium' : 'font-normal',
    disabled && 'opacity-40 pointer-events-none',
  )
  const style = active
    ? { background: LBRO.orange, color: '#fff' }
    : { color: '#a1a1aa' }

  if (disabled) {
    return (
      <span className={className} style={style} title={`Select a project to open ${item.label}`}>
        <Icon className="w-4 h-4 shrink-0" aria-hidden />
        <span className="truncate">{item.label}</span>
      </span>
    )
  }

  return (
    <NavLink
      to={href}
      className={className}
      style={style}
      aria-current={active ? 'page' : undefined}
    >
      <Icon className="w-4 h-4 shrink-0" aria-hidden />
      <span className="truncate">{item.label}</span>
    </NavLink>
  )
}

export function Sidebar() {
  const logout = useAuthStore(s => s.logout)
  const navigate = useNavigate()
  const location = useLocation()
  const currentProject = useProjectStore(s => s.currentProject)
  const queryClient = useQueryClient()
  const { can } = usePermissions()
  const user = useAuthStore(s => s.user)

  const isPlatformUser = user?.role === 'admin' || String(user?.role) === 'super_admin'

  const handleLogout = () => {
    auditAction('auth:logout', 'session', 'current')
    logger.info('User logged out')
    logout()
    queryClient.clear()
    navigate('/login', { replace: true })
  }

  const visibleSections = NAV_SECTIONS.filter(section => {
    if (section.id === 'platform') return isPlatformUser
    return true
  })

  return (
    <aside
      className="flex flex-col w-56 shrink-0 h-screen sticky top-0 z-30 border-r"
      style={{ background: LBRO.black, borderColor: '#1e1e1e' }}
      role="navigation"
      aria-label="Main navigation"
    >
      <button
        type="button"
        onClick={() => navigate('/dashboard')}
        className="flex items-center h-14 px-4 border-b shrink-0 focus:outline-none focus:ring-2"
        style={{ borderColor: '#1e1e1e' }}
        aria-label="LBRO home"
      >
        <span className="font-display text-2xl" style={{ color: LBRO.orange, letterSpacing: '0.06em' }}>
          LB<span style={{ color: '#fff' }}>RO</span>
        </span>
      </button>

      <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-5" aria-label="Application pages">
        {visibleSections.map(section => (
          <div key={section.id}>
            <p
              className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest"
              style={{ color: '#52525b' }}
            >
              {section.label}
              {section.id === 'platform' && (
                <span className="ml-1 normal-case font-normal" style={{ color: LBRO.orange }}>
                  (global)
                </span>
              )}
            </p>
            <div className="space-y-0.5">
              {section.items.map(item => {
                if (item.permission && !can(item.permission) && !isPlatformUser) return null
                if (item.platformOnly && !isPlatformUser) return null

                const href = resolveNavHref(item, currentProject?.id)
                if (item.projectScoped && !href) {
                  return (
                    <NavItem
                      key={item.label}
                      item={item}
                      href="#"
                      active={false}
                      disabled
                    />
                  )
                }
                if (!href) return null

                const active = isNavActive(location.pathname, item, href)
                return (
                  <NavItem
                    key={item.label + href}
                    item={item}
                    href={href}
                    active={active}
                  />
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t px-2 py-3" style={{ borderColor: '#1e1e1e' }}>
        <button
          type="button"
          onClick={handleLogout}
          className="flex items-center gap-2.5 w-full px-3 py-2 rounded-md text-sm text-zinc-500 hover:text-red-400 transition-colors focus:outline-none focus:ring-2"
        >
          <LogOut className="w-4 h-4" aria-hidden />
          Sign out
        </button>
      </div>
    </aside>
  )
}
