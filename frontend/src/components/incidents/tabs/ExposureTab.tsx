import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { exposureApi } from '@/api/client'
import { useCan } from '@/hooks/usePermissions'
import { Permission } from '@/types/rbac'

interface Props {
  incidentId: string
}

export function ExposureTab({ incidentId }: Props) {
  const qc = useQueryClient()
  const canConfirm = useCan(Permission.CONFIRM_EXPOSURE)
  const { data, isLoading, isError } = useQuery({
    queryKey: ['exposure', incidentId],
    queryFn: () => exposureApi.get(incidentId),
    retry: false,
  })
  const recompute = useMutation({
    mutationFn: () => exposureApi.recompute(incidentId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['exposure', incidentId] }),
  })

  if (isLoading) return <p role="status">Loading exposure assessment…</p>
  if (isError || !data) {
    return (
      <div>
        <p>No exposure assessment yet.</p>
        {canConfirm && (
          <button type="button" onClick={() => recompute.mutate()} aria-label="Recompute exposure">
            Recompute
          </button>
        )}
      </div>
    )
  }

  const results = data.results as Record<string, unknown>
  const provisional = data.status === 'provisional'

  return (
    <div aria-label="Exposure and obligations">
      {provisional && (
        <div role="alert" style={{ background: '#fef3c7', padding: 12, marginBottom: 12 }}>
          Provisional — analyst confirmation required.
        </div>
      )}
      <p style={{ fontSize: 12, color: '#6b6560' }}>
        {String(results.disclaimer ?? 'Decision support only; not legal advice.')}
      </p>
      {canConfirm && (
        <button type="button" onClick={() => recompute.mutate()} style={{ marginBottom: 12 }}>
          Recompute assessment
        </button>
      )}
      <h3>Techniques</h3>
      <ul>
        {((results.techniques as Record<string, string>[]) || []).map((t, i) => (
          <li key={i}>
            {t.technique_id}: {t.name} ({t.likelihood}) — {t.rationale}
          </li>
        ))}
      </ul>
      <h3>Jurisdictions</h3>
      <ul>
        {((results.jurisdiction_exposure as Record<string, unknown>[]) || []).map((j, i) => (
          <li key={i}>
            {String(j.jurisdiction_code)}: lower {String(j.lower_bound)} / upper {String(j.upper_bound)}
          </li>
        ))}
      </ul>
      <h3>Trace</h3>
      <ol>
        {data.trace.map((step, i) => (
          <li key={i}>
            <strong>{step.step}</strong>: {JSON.stringify(step.detail)}
          </li>
        ))}
      </ol>
      <p style={{ fontSize: 11, marginTop: 16 }}>
        MITRE ATT&CK is a registered trademark of The MITRE Corporation.
      </p>
    </div>
  )
}
