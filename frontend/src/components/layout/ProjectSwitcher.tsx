import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, Plus, Settings, Layers } from 'lucide-react'
import { cn } from '@/utils'
import { useProjectStore } from '@/store/projectStore'
import { useSwitchProject } from '@/hooks/useSwitchProject'

export function ProjectSwitcher() {
  const navigate = useNavigate()
  const switchProject = useSwitchProject()
  const currentProject = useProjectStore(s => s.currentProject)
  const projects = useProjectStore(s => s.projects)
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const label = currentProject?.name ?? 'Select project'

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className={cn(
          'flex items-center gap-2 px-3 py-1.5 text-xs font-medium border rounded transition-colors',
          currentProject
            ? 'border-lbro-border bg-white text-lbro-text'
            : 'border-orange-300 bg-orange-50 text-orange-700',
        )}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Current project: ${label}. Click to switch.`}
      >
        <Layers className="w-3.5 h-3.5 shrink-0 text-lbro-accent" aria-hidden />
        <span className="max-w-[140px] truncate">{label}</span>
        <ChevronDown className={cn('w-3.5 h-3.5 shrink-0 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div
          className="absolute left-0 top-full mt-1 z-50 min-w-[220px] py-1 bg-white border border-lbro-border rounded shadow-lg"
          role="listbox"
        >
          {projects.length === 0 ? (
            <p className="px-3 py-2 text-xs text-lbro-muted">No projects yet</p>
          ) : (
            projects.map(p => (
              <button
                key={p.id}
                type="button"
                role="option"
                aria-selected={currentProject?.id === p.id}
                className={cn(
                  'w-full text-left px-3 py-2 text-sm hover:bg-lbro-surface transition-colors',
                  currentProject?.id === p.id && 'bg-orange-50 font-medium',
                )}
                onClick={() => {
                  switchProject(p)
                  setOpen(false)
                }}
              >
                <span className="block truncate">{p.name}</span>
                {p.my_role && (
                  <span className="text-[10px] text-lbro-muted uppercase tracking-wide">{p.my_role}</span>
                )}
              </button>
            ))
          )}

          <div className="border-t border-lbro-border my-1" />

          <button
            type="button"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-lbro-surface text-left"
            onClick={() => { setOpen(false); navigate('/projects') }}
          >
            <Plus className="w-3.5 h-3.5" /> Create project
          </button>

          {currentProject && (
            <button
              type="button"
              className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-lbro-surface text-left"
              onClick={() => {
                setOpen(false)
                navigate(`/projects/${currentProject.id}/settings`)
              }}
            >
              <Settings className="w-3.5 h-3.5" /> Project settings
            </button>
          )}
        </div>
      )}
    </div>
  )
}
