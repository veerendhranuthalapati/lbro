/**
 * Security Overview — consolidated Security Score + Weekly Report.
 */
import { useSearchParams } from 'react-router-dom'
import { ShieldCheck, BarChart2 } from 'lucide-react'
import SecurityScorePage from '@/pages/SecurityScorePage'
import WeeklyReportPage from '@/pages/WeeklyReportPage'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'

type Tab = 'score' | 'report'

export default function SecurityOverviewPage() {
  const [params, setParams] = useSearchParams()
  const tab: Tab = params.get('tab') === 'report' ? 'report' : 'score'

  const setTab = (next: Tab) => {
    setParams(next === 'score' ? {} : { tab: next }, { replace: true })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>
          Security Overview
        </h1>
        <p style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>
          Live security score and weekly report — sourced from backend APIs
        </p>
      </div>

      <div
        role="tablist"
        aria-label="Security overview sections"
        style={{ display: 'flex', gap: 8, borderBottom: `1px solid ${BORDER}`, paddingBottom: 0 }}
      >
        {([
          { id: 'score' as Tab, label: 'Security Score', icon: ShieldCheck },
          { id: 'report' as Tab, label: 'Weekly Report', icon: BarChart2 },
        ]).map(({ id, label, icon: Icon }) => {
          const active = tab === id
          return (
            <button
              key={id}
              role="tab"
              aria-selected={active}
              aria-controls={`panel-${id}`}
              id={`tab-${id}`}
              onClick={() => setTab(id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '10px 16px', marginBottom: -1,
                fontSize: 11, fontWeight: 500, letterSpacing: '0.06em', textTransform: 'uppercase',
                background: active ? CREAM : 'transparent',
                border: `1px solid ${active ? BORDER : 'transparent'}`,
                borderBottom: active ? `1px solid ${CREAM}` : `1px solid transparent`,
                borderRadius: '4px 4px 0 0',
                color: active ? ORANGE : GRAY,
                cursor: 'pointer',
              }}
            >
              <Icon style={{ width: 13, height: 13 }} aria-hidden="true" />
              {label}
            </button>
          )
        })}
      </div>

      <div
        role="tabpanel"
        id={`panel-${tab}`}
        aria-labelledby={`tab-${tab}`}
      >
        {tab === 'score' ? <SecurityScorePage embedded /> : <WeeklyReportPage embedded />}
      </div>
    </div>
  )
}
