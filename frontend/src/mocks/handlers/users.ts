import { http, HttpResponse, delay } from 'msw'
import { MOCK_USERS } from '../data'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const users: any[] = MOCK_USERS.map(u => ({ ...u }))

export const userHandlers = [
  http.get('/api/v1/users', async ({ request }) => {
    await delay(200)
    const url       = new URL(request.url)
    const page      = Number(url.searchParams.get('page')      ?? 1)
    const page_size = Number(url.searchParams.get('page_size') ?? 20)
    const role      = url.searchParams.get('role')
    const search    = url.searchParams.get('search')?.toLowerCase()

    let filtered = users
    if (role)   filtered = filtered.filter(u => u.role === role)
    if (search) filtered = filtered.filter(u =>
      u.email.toLowerCase().includes(search) ||
      (u.full_name ?? '').toLowerCase().includes(search),
    )
    const total = filtered.length
    const items = filtered.slice((page - 1) * page_size, page * page_size)
    return HttpResponse.json({ items, total, page, page_size })
  }),

  http.post('/api/v1/users', async ({ request }) => {
    await delay(350)
    const body = await request.json() as Record<string, unknown>
    const newUser = {
      id:          crypto.randomUUID(),
      email:       body.email     as string,
      username:    body.username  as string,
      full_name:   body.full_name as string,
      role:        (body.role as string) ?? 'analyst',
      is_active:   true,
      is_verified: false,
      mfa_enabled: false,
      last_login:  null,
      created_at:  new Date().toISOString(),
      updated_at:  new Date().toISOString(),
    }
    users.push(newUser)
    return HttpResponse.json(newUser, { status: 201 })
  }),

  http.get('/api/v1/users/:id', async ({ params }) => {
    await delay(150)
    const u = users.find(u => u.id === params.id)
    if (!u) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    return HttpResponse.json(u)
  }),

  http.patch('/api/v1/users/:id', async ({ params, request }) => {
    await delay(250)
    const idx = users.findIndex(u => u.id === params.id)
    if (idx === -1) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    const body = await request.json() as Record<string, unknown>
    users[idx] = { ...users[idx], ...body, updated_at: new Date().toISOString() }
    return HttpResponse.json(users[idx])
  }),

  http.delete('/api/v1/users/:id', async ({ params }) => {
    await delay(300)
    const idx = users.findIndex(u => u.id === params.id)
    if (idx === -1) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    users.splice(idx, 1)
    return new HttpResponse(null, { status: 204 })
  }),
]
