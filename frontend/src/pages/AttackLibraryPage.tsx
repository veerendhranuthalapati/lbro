/**
 * Attack library — searchable list of defensive attack guides (GET /api/v1/knowledge/attacks).
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Search, Shield } from 'lucide-react'
import { apiClient } from '@/api/client'
import { PageHeader } from '@/components/ui/PageHeader'
import { LoadingState } from '@/components/ui/LoadingState'
import { EmptyState } from '@/components/ui/EmptyState'

const ORANGE = '#e54e1b'
const BORDER = '#c8c2b8'

type AttackListItem = {
  class_id: string
  title: string
  summary_plain: string
}

export default function AttackLibraryPage() {
  const [q, setQ] = useState('')
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['knowledge', 'attacks', q],
    queryFn: async () => {
      const r = await apiClient.get<{ items: AttackListItem[]; disclaimer: string }>(
        '/api/v1/knowledge/attacks',
        { params: q ? { q } : {} },
      )
      return r.data
    },
  })

  if (isLoading) return <LoadingState label="Loading attack library…" />
  if (isError) {
    return (
      <EmptyState
        title="Could not load attack library"
        description="Check your connection and try again."
        action={
          <button type="button" onClick={() => void refetch()} className="px-4 py-2 rounded text-sm text-white" style={{ background: ORANGE }}>
            Retry
          </button>
        }
      />
    )
  }

  const items = data?.items ?? []

  return (
    <div className="max-w-4xl mx-auto">
      <PageHeader
        compact
        description="Defensive guides for each attack class LBRO can flag. Detections are leads — verify before acting."
      />
      <p className="text-xs text-zinc-600 mb-4" role="note">{data?.disclaimer}</p>
      <label className="flex items-center gap-2 mb-6 border rounded px-3 py-2" style={{ borderColor: BORDER }}>
        <Search className="w-4 h-4 text-zinc-500" aria-hidden />
        <input
          type="search"
          value={q}
          onChange={e => setQ(e.target.value)}
          placeholder="Search attack class or summary"
          className="flex-1 text-sm bg-transparent outline-none"
          aria-label="Search attack library"
        />
      </label>
      {items.length === 0 ? (
        <EmptyState title="No matches" description="Try a different search term." />
      ) : (
        <ul className="space-y-3">
          {items.map(item => (
            <li key={item.class_id} className="rounded-lg border p-4" style={{ borderColor: BORDER }}>
              <div className="flex items-start gap-2">
                <Shield className="w-4 h-4 mt-0.5 shrink-0" style={{ color: ORANGE }} aria-hidden />
                <div>
                  <h2 className="text-sm font-medium">{item.title}</h2>
                  <p className="text-xs text-zinc-600 mt-1 font-mono">{item.class_id}</p>
                  <p className="text-sm mt-2 leading-relaxed">{item.summary_plain}</p>
                  <Link to="/incidents" className="text-xs mt-2 inline-block" style={{ color: ORANGE }}>
                    View incidents →
                  </Link>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
