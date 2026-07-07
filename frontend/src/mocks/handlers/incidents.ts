import { http, HttpResponse, delay } from 'msw'
import { MOCK_INCIDENTS } from '../data'

// mutable clone so mutations persist during the session
const incidents = MOCK_INCIDENTS.map(i => ({ ...i }))

export const incidentHandlers = [
  // List (paginated + filtered)
  http.get('/api/v1/incidents', async ({ request }) => {
    await delay(300)
    const url = new URL(request.url)
    const page      = Number(url.searchParams.get('page')      ?? 1)
    const page_size = Number(url.searchParams.get('page_size') ?? 20)
    const status    = url.searchParams.get('status')
    const severity  = url.searchParams.get('severity')
    const search    = url.searchParams.get('search')?.toLowerCase()

    let filtered = incidents
    if (status)   filtered = filtered.filter(i => i.status   === status)
    if (severity) filtered = filtered.filter(i => i.severity === severity)
    if (search)   filtered = filtered.filter(i =>
      i.title.toLowerCase().includes(search) ||
      (i.description ?? '').toLowerCase().includes(search) ||
      (i.source_ip ?? '').toLowerCase().includes(search),
    )
    const total = filtered.length
    const items = filtered.slice((page - 1) * page_size, page * page_size)
    return HttpResponse.json({ items, total, page, page_size })
  }),

  // Stats
  http.get('/api/v1/incidents/stats', async () => {
    await delay(200)
    const bySeverity = { critical: 0, high: 0, medium: 0, low: 0 } as Record<string, number>
    const byStatus   = { open: 0, investigating: 0, resolved: 0, closed: 0 } as Record<string, number>
    incidents.forEach(i => { bySeverity[i.severity]++; byStatus[i.status]++ })
    return HttpResponse.json({ total: incidents.length, by_severity: bySeverity, by_status: byStatus })
  }),

  // Create
  http.post('/api/v1/incidents', async ({ request }) => {
    await delay(400)
    const body = await request.json() as Record<string, unknown>
    const newInc = {
      id: crypto.randomUUID(),
      title: body.title as string,
      description: (body.description as string) ?? '',
      severity: (body.severity as string) ?? 'medium',
      status: 'open',
      attack_category: (body.attack_category as string) ?? null,
      source_ip: (body.source_ip as string) ?? null,
      destination_port: (body.destination_port as number) ?? null,
      protocol: (body.protocol as string) ?? null,
      assigned_to: null,
      detected_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    incidents.unshift(newInc)
    return HttpResponse.json(newInc, { status: 201 })
  }),

  // Detail
  http.get('/api/v1/incidents/:id', async ({ params }) => {
    await delay(200)
    const inc = incidents.find(i => i.id === params.id)
    if (!inc) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    return HttpResponse.json(inc)
  }),

  // Update
  http.patch('/api/v1/incidents/:id', async ({ params, request }) => {
    await delay(300)
    const idx = incidents.findIndex(i => i.id === params.id)
    if (idx === -1) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    const body = await request.json() as Record<string, unknown>
    incidents[idx] = { ...incidents[idx], ...body, updated_at: new Date().toISOString() }
    return HttpResponse.json(incidents[idx])
  }),

  // Delete
  http.delete('/api/v1/incidents/:id', async ({ params }) => {
    await delay(300)
    const idx = incidents.findIndex(i => i.id === params.id)
    if (idx === -1) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    incidents.splice(idx, 1)
    return new HttpResponse(null, { status: 204 })
  }),

  // Explain incident — GET /api/v1/incidents/:id/explain
  // (backend + client both use /explain, not /explanation)
  http.get('/api/v1/incidents/:id/explain', async ({ params }) => {
    await delay(500)
    const inc = incidents.find(i => i.id === params.id)
    if (!inc) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    return HttpResponse.json({
      incident_id: inc.id,
      incident_title: inc.title,
      incident_severity: inc.severity,
      attack_category: inc.attack_category,
      category: inc.attack_category ?? 'Unknown',
      plain_english: `This incident involves a ${inc.attack_category ?? 'security'} event originating from ${inc.source_ip}. The attack targeted port ${inc.destination_port} using ${inc.protocol} protocol.`,
      context: 'Detected by ML classifier and WAF correlation rules.',
      business_impact: 'Potential data exposure and service disruption if left unaddressed.',
      technical_impact: 'May allow attacker to escalate privileges or exfiltrate sensitive data.',
      likelihood: inc.severity === 'critical' ? 'Critical' : inc.severity === 'high' ? 'High' : 'Medium',
      owasp: 'A03:2021 - Injection',
      mitre_attack: ['T1190', 'T1071'],
      recommended_fixes: ['Block source IP at WAF level', 'Review and harden input validation', 'Enable MFA for all accounts'],
      severity_hint: `Classified as ${inc.severity.toUpperCase()} by ML model with 94.2% confidence.`,
      learn_more_url: null,
    })
  }),
]
