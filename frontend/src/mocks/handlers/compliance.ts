import { http, HttpResponse, delay } from 'msw'
import { MOCK_COMPLIANCE } from '../data'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const records: any[] = MOCK_COMPLIANCE.records.map(r => ({ ...r }))

export const complianceHandlers = [
  // GET /api/v1/compliance/dashboard
  // Returns { summaries, overdue_records, upcoming_deadlines } — matches backend ComplianceDashboard schema
  http.get('/api/v1/compliance/dashboard', async () => {
    await delay(250)
    const now = Date.now()

    // Per-regulation summaries matching ComplianceSummary: { regulation, total, met, overdue, pending }
    const regs = ['GDPR', 'HIPAA', 'DPDPA']
    const summaries = regs.map(reg => {
      const subset  = records.filter(r => r.regulation === reg)
      const met     = subset.filter(r =>  r.is_met).length
      const overdue = subset.filter(r => !r.is_met && new Date(r.deadline).getTime() < now).length
      const pending = subset.filter(r => !r.is_met && new Date(r.deadline).getTime() >= now).length
      return { regulation: reg, total: subset.length, met, overdue, pending }
    })

    const overdue_records    = records.filter(r => !r.is_met && new Date(r.deadline).getTime() < now)
    const upcoming_deadlines = records
      .filter(r => !r.is_met && new Date(r.deadline).getTime() >= now)
      .sort((a, b) => new Date(a.deadline).getTime() - new Date(b.deadline).getTime())

    const grandTotal = summaries.reduce((n, s) => n + s.total, 0)
    const grandMet = summaries.reduce((n, s) => n + s.met, 0)
    const overallPct = grandTotal > 0 ? Math.round(grandMet / grandTotal * 100) : null

    return HttpResponse.json({
      summaries: summaries.map(s => ({
        ...s,
        compliance_pct: s.total > 0 ? Math.round(s.met / s.total * 100) : null,
        has_data: s.total > 0,
      })),
      overdue_records,
      upcoming_deadlines,
      total_records: grandTotal,
      met_records: grandMet,
      overall_compliance_pct: overallPct,
      has_data: grandTotal > 0,
    })
  }),

  // POST /api/v1/compliance/records/:id/mark-met
  http.post('/api/v1/compliance/records/:id/mark-met', async ({ params, request }) => {
    await delay(300)
    const body = await request.json() as { notes?: string }
    const idx  = records.findIndex(r => r.id === params.id)
    if (idx === -1) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    records[idx] = {
      ...records[idx],
      is_met: true,
      met_at: new Date().toISOString(),
      notes: body.notes ?? null,
      updated_at: new Date().toISOString(),
    }
    return HttpResponse.json(records[idx])
  }),
]
