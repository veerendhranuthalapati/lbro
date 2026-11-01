/**
 * Data Map — project asset inventory for compliance inference.
 */
import { useQuery } from '@tanstack/react-query'
import { Database } from 'lucide-react'
import { assetsApi } from '@/api/client'
import { useProjectStore } from '@/store/projectStore'
import { useCan } from '@/hooks/usePermissions'
import { Permission } from '@/types/rbac'

export default function DataMapPage() {
  const projectId = useProjectStore((s) => s.currentProject?.id)
  const canManage = useCan(Permission.MANAGE_ASSETS)

  const { data, isLoading } = useQuery({
    queryKey: ['assets', projectId],
    queryFn: () => assetsApi.list(projectId!, { page: 1, page_size: 100 }),
    enabled: !!projectId,
  })

  if (!projectId) {
    return (
      <div style={{ padding: 24 }}>
        <p>Select a project to view the data map.</p>
      </div>
    )
  }

  return (
    <div style={{ padding: 24, maxWidth: 1100 }}>
      <h1 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Database aria-hidden /> Data Map
      </h1>
      <p style={{ color: '#6b6560', maxWidth: 720 }}>
        Fictional asset metadata and record counts only — used to infer affected jurisdictions and
        obligations. Not legal advice.
      </p>
      {isLoading && <p role="status">Loading assets…</p>}
      {!isLoading && data && data.items.length === 0 && (
        <p>No assets yet. {canManage ? 'Create assets via the API or import CSV.' : 'Ask an analyst to populate the map.'}</p>
      )}
      <table style={{ width: '100%', marginTop: 16, borderCollapse: 'collapse' }} aria-label="Asset inventory">
        <thead>
          <tr>
            <th align="left">Name</th>
            <th align="left">Type</th>
            <th align="left">Categories</th>
            <th align="left">Residency</th>
          </tr>
        </thead>
        <tbody>
          {data?.items.map((a) => (
            <tr key={a.id} style={{ borderTop: '1px solid #c8c2b8' }}>
              <td>{a.name}</td>
              <td>{a.asset_type}</td>
              <td>{a.data_categories.join(', ')}</td>
              <td>
                {a.residency.map((r) => `${r.jurisdiction_code}:${r.record_count ?? '?'}`).join(' · ')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ marginTop: 24, fontSize: 12, color: '#6b6560' }}>
        MITRE ATT&CK technique display on incidents includes required attribution (see Exposure tab).
      </p>
    </div>
  )
}
