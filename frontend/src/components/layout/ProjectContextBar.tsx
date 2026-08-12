import { Link } from 'react-router-dom'
import { useProjectStore } from '@/store/projectStore'
import { RoleBadge } from '@/components/ui/RoleBadge'
import { LBRO } from '@/lib/tokens'

/** Subtle project context under the navbar title. */
export function ProjectContextBar() {
  const currentProject = useProjectStore(s => s.currentProject)
  if (!currentProject) return null

  const role = currentProject.my_role === 'admin' && currentProject.owner_id
    ? 'owner'
    : (currentProject.my_role ?? undefined)

  return (
    <p className="text-xs flex items-center gap-2 min-w-0" style={{ color: LBRO.gray }}>
      <span className="truncate">
        Project:{' '}
        <Link
          to={`/projects/${currentProject.id}`}
          className="font-medium hover:underline"
          style={{ color: LBRO.black }}
        >
          {currentProject.name}
        </Link>
      </span>
      {role && <RoleBadge role={role} />}
    </p>
  )
}
