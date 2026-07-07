import { http, HttpResponse, delay } from 'msw'
import { MOCK_AUDIT_LOGS } from '../data'

export const auditHandlers = [
  http.get('/api/v1/audit/logs', async ({ request }) => {
    await delay(250)
    const url = new URL(request.url)
    const page      = Number(url.searchParams.get('page')      ?? 1)
    const page_size = Number(url.searchParams.get('page_size') ?? 25)
    const action    = url.searchParams.get('action')

    let filtered = MOCK_AUDIT_LOGS
    if (action) filtered = filtered.filter(l => l.action === action)

    const total = filtered.length
    const items = filtered.slice((page - 1) * page_size, page * page_size)
    return HttpResponse.json({ items, total, page, page_size })
  }),
]
