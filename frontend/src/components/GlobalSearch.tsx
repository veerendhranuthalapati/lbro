import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useIncidents } from '@/hooks/useApi'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'

const SEV_DOT: Record<string, string> = {
  critical: '#e54e1b',
  high:     '#d97706',
  medium:   '#6b6560',
  low:      '#4ade80',
  info:     '#3b82f6',
}

export function GlobalSearch() {
  const [open, setOpen]     = useState(false)
  const [query, setQuery]   = useState('')
  const [active, setActive] = useState(0)
  const navigate            = useNavigate()
  const inputRef            = useRef<HTMLInputElement>(null)

  // Search fires when query is non-empty; backend supports ?search= on incidents list
  const { data, isFetching } = useIncidents(
    query.trim().length >= 2
      ? { search: query.trim(), page_size: 8 }
      : { page_size: 0 }   // no results when query is too short
  )
  const results = query.trim().length >= 2 ? (data?.items ?? []) : []

  // Cmd+K / Ctrl+K — open
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(prev => !prev)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  // Focus input when modal opens
  useEffect(() => {
    if (open) {
      setQuery('')
      setActive(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  // Arrow-key + Enter navigation within results
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive(a => Math.min(a + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive(a => Math.max(a - 1, 0))
    } else if (e.key === 'Enter' && results[active]) {
      navigate(`/incidents/${results[active].id}`)
      setOpen(false)
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }, [results, active, navigate])

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={() => setOpen(false)}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(17,17,17,0.55)',
          backdropFilter: 'blur(2px)',
          zIndex: 9998,
        }}
      />

      {/* Modal */}
      <div
        style={{
          position: 'fixed',
          top: '15%',
          left: '50%',
          transform: 'translateX(-50%)',
          width: '100%',
          maxWidth: 560,
          background: CREAM,
          border: `1px solid ${BORDER}`,
          borderRadius: 6,
          boxShadow: '0 24px 48px rgba(17,17,17,0.18)',
          zIndex: 9999,
          overflow: 'hidden',
        }}
      >
        {/* Search input row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', borderBottom: `1px solid ${BORDER}` }}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0, color: GRAY }}>
            <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M11 11l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <input
            ref={inputRef}
            value={query}
            onChange={e => { setQuery(e.target.value); setActive(0) }}
            onKeyDown={handleKeyDown}
            placeholder="Search incidents — title, source IP, attack type…"
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              background: 'transparent',
              fontSize: 14,
              color: BLACK,
              fontFamily: 'inherit',
            }}
          />
          {isFetching && (
            <span style={{ fontSize: 10, color: GRAY, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              searching…
            </span>
          )}
          <kbd style={{
            fontSize: 10, color: GRAY, background: PARCH,
            border: `1px solid ${BORDER}`, borderRadius: 3,
            padding: '2px 6px', fontFamily: 'JetBrains Mono, monospace',
          }}>
            ESC
          </kbd>
        </div>

        {/* Results */}
        {results.length > 0 && (
          <ul style={{ margin: 0, padding: '6px 0', listStyle: 'none', maxHeight: 360, overflowY: 'auto' }}>
            {results.map((inc, i) => (
              <li
                key={inc.id}
                onClick={() => { navigate(`/incidents/${inc.id}`); setOpen(false) }}
                onMouseEnter={() => setActive(i)}
                style={{
                  padding: '10px 16px',
                  cursor: 'pointer',
                  background: i === active ? PARCH : 'transparent',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  transition: 'background 0.08s',
                }}
              >
                {/* Severity dot */}
                <span style={{
                  width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                  background: SEV_DOT[inc.severity] ?? GRAY,
                }} />

                {/* Title + meta */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, color: BLACK, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {inc.title}
                  </div>
                  <div style={{ fontSize: 10, color: GRAY, marginTop: 2, display: 'flex', gap: 8 }}>
                    {inc.attack_category && <span>{inc.attack_category}</span>}
                    {inc.source_ip && (
                      <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>{inc.source_ip}</span>
                    )}
                    <span style={{
                      padding: '0 5px',
                      border: `1px solid ${BORDER}`,
                      borderRadius: 2,
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                    }}>
                      {inc.status}
                    </span>
                  </div>
                </div>

                {/* Severity label */}
                <span style={{
                  fontSize: 9,
                  padding: '2px 7px',
                  borderRadius: 2,
                  textTransform: 'uppercase',
                  letterSpacing: '0.07em',
                  fontWeight: 600,
                  color: SEV_DOT[inc.severity] ?? GRAY,
                  border: `1px solid ${SEV_DOT[inc.severity] ?? BORDER}`,
                  background: `${SEV_DOT[inc.severity] ?? GRAY}11`,
                  flexShrink: 0,
                }}>
                  {inc.severity}
                </span>
              </li>
            ))}
          </ul>
        )}

        {/* Empty state — only shown when query is long enough but no results */}
        {query.trim().length >= 2 && !isFetching && results.length === 0 && (
          <div style={{ padding: '28px 16px', textAlign: 'center', color: GRAY, fontSize: 12 }}>
            No incidents found for <strong style={{ color: BLACK }}>"{query}"</strong>
          </div>
        )}

        {/* Hint row */}
        <div style={{
          borderTop: `1px solid ${BORDER}`,
          padding: '8px 16px',
          display: 'flex',
          gap: 16,
          alignItems: 'center',
        }}>
          {[
            ['↑↓', 'navigate'],
            ['↵', 'open'],
            ['esc', 'close'],
          ].map(([key, label]) => (
            <span key={key} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <kbd style={{
                fontSize: 10, color: GRAY, background: PARCH,
                border: `1px solid ${BORDER}`, borderRadius: 3,
                padding: '1px 5px', fontFamily: 'JetBrains Mono, monospace',
              }}>
                {key}
              </kbd>
              <span style={{ fontSize: 10, color: GRAY }}>{label}</span>
            </span>
          ))}
          <span style={{ marginLeft: 'auto', fontSize: 10, color: BORDER }}>
            type 2+ chars to search
          </span>
        </div>
      </div>
    </>
  )
}
