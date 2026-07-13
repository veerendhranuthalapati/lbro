/**
 * LBRO Project Store
 *
 * Holds the currently selected project and the full project list.
 * Persisted to sessionStorage so the selection survives page refreshes
 * but is cleared when the tab closes (matches authStore behaviour).
 *
 * Usage:
 *   const { currentProject, setCurrentProject } = useProjectStore()
 *   const projectId = currentProject?.id  // inject into every API call
 */
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { Project } from '@/types'

interface ProjectStoreState {
  /** The project the user is currently working in. null = no project selected yet. */
  currentProject: Project | null
  /** Full list fetched from GET /projects — used to populate the switcher. */
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
      // Only persist the selection and list — everything else is derived from the API
      partialize: (state) => ({
        currentProject: state.currentProject,
        projects: state.projects,
      }),
    }
  )
)
