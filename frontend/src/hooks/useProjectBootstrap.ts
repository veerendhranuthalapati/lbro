import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { projectsApi } from '@/api/client'
import { useAuthStore } from '@/store/authStore'
import { useProjectStore } from '@/store/projectStore'

const SKIP_BOOTSTRAP = ['/welcome', '/login', '/register', '/projects']

/** Load authorized projects after login; redirect new users to onboarding. */
export function useProjectBootstrap() {
  const isAuthenticated = useAuthStore(s => s.isAuthenticated)
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { currentProject, setProjects, setCurrentProject } = useProjectStore()

  const { data } = useQuery({
    queryKey: ['projects', 'list'],
    queryFn: () => projectsApi.list(),
    enabled: isAuthenticated,
    staleTime: 30_000,
  })

  useEffect(() => {
    if (!data) return
    setProjects(data.items)

    const skip = SKIP_BOOTSTRAP.some(p => pathname === p || pathname.startsWith(p + '/'))
    if (skip) return

    if (data.total === 0 && pathname !== '/welcome') {
      navigate('/welcome', { replace: true })
      return
    }

    if (data.total > 0 && !currentProject) {
      setCurrentProject(data.items[0])
    } else if (currentProject && !data.items.some(p => p.id === currentProject.id)) {
      setCurrentProject(data.items[0] ?? null)
    }
  }, [data, pathname, currentProject, setProjects, setCurrentProject, navigate])
}
