/**
 * LBRO Project Store
 *
 * Holds the currently selected project and the full project list.
 * Persisted to sessionStorage so the selection survives page refreshes.
 */
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { Project } from '@/types'

interface ProjectStoreState {
  currentProject: Project | null
  projects: Project[]

  setCurrentProject: (project: Project) => void
  setProjects: (projects: Project[]) => void
  clearProject: () => void
}

export const useProjectStore = create<ProjectStoreState>()(
  persist(
    (set) => ({
      currentProject: null,
      projects: [],

      setCurrentProject: (project) => set({ currentProject: project }),
      setProjects: (projects) => set({ projects }),
      clearProject: () => set({ currentProject: null, projects: [] }),
    }),
    {
      name: 'lbro-project',
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        currentProject: state.currentProject,
        projects: state.projects,
      }),
    }
  )
)

/** Query keys cleared when switching projects to prevent stale cross-project data. */
export const PROJECT_SCOPED_QUERY_PREFIXES = [
  'incidents',
  'dashboard',
  'compliance',
  'notifications',
  'security-score',
  'reports',
  'ml',
  'evidence',
  'project',
  'invitations',
] as const
