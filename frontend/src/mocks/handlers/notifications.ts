import { http, HttpResponse, delay } from 'msw'
import { MOCK_NOTIFICATIONS } from '../data'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const notifications: any[] = MOCK_NOTIFICATIONS.map(n => ({ ...n }))

export const notificationHandlers = [
  http.get('/api/v1/notifications', async ({ request }) => {
    await delay(200)
    const url       = new URL(request.url)
    const page      = Number(url.searchParams.get('page')      ?? 1)
    const page_size = Number(url.searchParams.get('page_size') ?? 20)
    const status     = url.searchParams.get('status')
    const regulation = url.searchParams.get('regulation')
    const incident_id = url.searchParams.get('incident_id')

    let filtered = notifications
    if (status)       filtered = filtered.filter(n => n.status      === status)
    if (regulation)   filtered = filtered.filter(n => n.regulation  === regulation)
    if (incident_id)  filtered = filtered.filter(n => n.incident_id === incident_id)

    const total = filtered.length
    const items = filtered.slice((page - 1) * page_size, page * page_size)
    return HttpResponse.json({ items, total, page, page_size })
  }),

  http.get('/api/v1/notifications/:id', async ({ params }) => {
    await delay(150)
    const n = notifications.find(n => n.id === params.id)
    if (!n) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    return HttpResponse.json(n)
  }),

  http.post('/api/v1/notifications/:id/approve', async ({ params }) => {
    await delay(200)
    const idx = notifications.findIndex(n => n.id === params.id)
    if (idx === -1) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    notifications[idx] = {
      ...notifications[idx],
      status: 'approved',
      approved_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    return HttpResponse.json(notifications[idx])
  }),

  http.post('/api/v1/notifications/:id/dispatch', async ({ params }) => {
    await delay(300)
    const idx = notifications.findIndex(n => n.id === params.id)
    if (idx === -1) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    notifications[idx] = {
      ...notifications[idx],
      status: 'sent',
      approved_at: notifications[idx].approved_at ?? new Date().toISOString(),
      sent_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    return HttpResponse.json(notifications[idx])
  }),

  http.post('/api/v1/notifications/:id/send', async ({ params }) => {
    await delay(300)
    const idx = notifications.findIndex(n => n.id === params.id)
    if (idx === -1) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    notifications[idx] = {
      ...notifications[idx],
      status: 'sent',
      sent_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    return HttpResponse.json(notifications[idx])
  }),
]
