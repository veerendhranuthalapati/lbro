import type { FC } from 'react'
import type { LucideProps } from 'lucide-react'
import {
  LayoutDashboard, FolderKanban, ShieldAlert, Activity, Lock,
  Brain, FileText, BarChart3, Plug2, Settings, Bell, User,
  Users, ClipboardList, ShieldCheck, BookOpen, Cloud,
} from 'lucide-react'
import { Permission, type PermissionValue } from '@/types/rbac'

export interface NavItemDef {
  to: string
  label: string
  icon: FC<LucideProps>
  /** Match nested routes (default true except dashboard) */
  matchPrefix?: boolean
  permission?: PermissionValue
  /** super_admin / admin platform section */
  platformOnly?: boolean
  /** Requires currentProject — path uses :projectId placeholder */
  projectScoped?: boolean
  projectPath?: (projectId: string) => string
}

export interface NavSection {
  id: string
  label: string
  items: NavItemDef[]
}

export const NAV_SECTIONS: NavSection[] = [
  {
    id: 'main',
    label: 'Main',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, matchPrefix: false },
      { to: '/projects', label: 'Projects', icon: FolderKanban },
      { to: '/incidents', label: 'Incidents', icon: ShieldAlert },
      {
        to: '/events',
        label: 'Live Events',
        icon: Activity,
        projectScoped: true,
        projectPath: (id) => `/projects/${id}/events`,
      },
      { to: '/evidence', label: 'Evidence', icon: Lock },
    ],
  },
  {
    id: 'analysis',
    label: 'Analysis',
    items: [
      { to: '/ml-insights', label: 'ML Analysis', icon: Brain, permission: Permission.VIEW_ML },
      { to: '/compliance', label: 'Compliance', icon: FileText, permission: Permission.VIEW_COMPLIANCE },
      { to: '/security-overview', label: 'Reports', icon: BarChart3 },
    ],
  },
  {
    id: 'project',
    label: 'Project',
    items: [
      {
        to: '/integrations',
        label: 'Integrations',
        icon: Plug2,
        projectScoped: true,
        projectPath: (id) => `/projects/${id}/integrations`,
      },
      {
        to: '/project-settings',
        label: 'Settings',
        icon: Settings,
        projectScoped: true,
        projectPath: (id) => `/projects/${id}/settings`,
      },
    ],
  },
  {
    id: 'account',
    label: 'Account',
    items: [
      { to: '/notifications', label: 'Notifications', icon: Bell },
      { to: '/settings', label: 'Profile', icon: User },
    ],
  },
  {
    id: 'platform',
    label: 'Platform',
    items: [
      { to: '/security-overview', label: 'Monitoring', icon: ShieldCheck, platformOnly: true },
      { to: '/users', label: 'Users', icon: Users, permission: Permission.MANAGE_USERS, platformOnly: true },
      { to: '/audit-logs', label: 'Audit Logs', icon: ClipboardList, permission: Permission.VIEW_AUDIT, platformOnly: true },
      { to: '/infrastructure', label: 'Infrastructure', icon: Cloud, permission: Permission.VIEW_INFRASTRUCTURE, platformOnly: true },
      { to: '/docs', label: 'API Docs', icon: BookOpen, platformOnly: true },
    ],
  },
]

/** Page titles for navbar (canonical labels). */
export const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/projects': 'Projects',
  '/incidents': 'Incidents',
  '/evidence': 'Evidence',
  '/notifications': 'Notifications',
  '/settings': 'Profile',
  '/compliance': 'Compliance',
  '/compliance/audit': 'Compliance Audit',
  '/ml-insights': 'ML Analysis',
  '/security-overview': 'Reports',
  '/threat-intel': 'Threat Intel',
  '/infrastructure': 'Infrastructure',
  '/audit-logs': 'Audit Logs',
  '/users': 'Users',
  '/docs': 'API Docs',
  '/privacy': 'Privacy',
  '/incidents/new': 'New Incident',
}

export function resolveNavHref(item: NavItemDef, projectId: string | undefined): string | null {
  if (item.projectScoped) {
    if (!projectId) return null
    return item.projectPath?.(projectId) ?? null
  }
  return item.to
}

export function isNavActive(pathname: string, item: NavItemDef, resolvedHref: string): boolean {
  if (pathname === resolvedHref) return true
  if (item.matchPrefix === false) return false
  if (resolvedHref !== '/dashboard' && pathname.startsWith(resolvedHref)) return true
  if (item.to === '/incidents' && pathname.startsWith('/incidents')) return true
  if (item.to === '/projects' && pathname.startsWith('/projects')) return true
  if (item.to === '/security-overview' && (pathname.startsWith('/security-overview') || pathname.startsWith('/weekly-report'))) return true
  return false
}

export function getPageTitle(pathname: string): string {
  if (PAGE_TITLES[pathname]) return PAGE_TITLES[pathname]
  if (pathname.startsWith('/incidents/')) return 'Incident Detail'
  if (pathname.includes('/integrations')) return 'Integrations'
  if (pathname.includes('/events')) return 'Live Events'
  if (pathname.includes('/settings') && pathname.includes('/projects/')) return 'Project Settings'
  if (pathname.startsWith('/projects/') && !pathname.includes('/setup')) return 'Project'
  return 'LBRO'
}
