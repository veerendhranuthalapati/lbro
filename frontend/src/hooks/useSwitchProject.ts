import { useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useProjectStore, PROJECT_SCOPED_QUERY_PREFIXES } from '@/store/projectStore'
import type { Project } from '@/types'

/** Switch active project and invalidate all project-scoped cached data. */
export function useSwitchProject() {
  const queryClient = useQueryClient()
  const setCurrentProject = useProjectStore(s => s.setCurrentProject)
  const setProjects = useProjectStore(s => s.setProjects)
  const projects = useProjectStore(s => s.projects)
  const navigate = useNavigate()

  return useCallback(
    (project: Project, options?: { navigateToDashboard?: boolean }) => {
      setCurrentProject(project)
      const updated = projects.some(p => p.id === project.id)
        ? projects.map(p => (p.id === project.id ? project : p))
        : [...projects, project]
      setProjects(updated)

      for (const prefix of PROJECT_SCOPED_QUERY_PREFIXES) {
        queryClient.removeQueries({ queryKey: [prefix] })
      }

      if (options?.navigateToDashboard !== false) {
        navigate('/dashboard')
      }
    },
    [queryClient, setCurrentProject, setProjects, projects, navigate],
  )
}
