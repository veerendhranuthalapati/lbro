import { http, HttpResponse, delay } from 'msw'
import { MOCK_ME, MOCK_USERS } from '../data'

const FAKE_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwMDAwMDAwMC0wMDAwLTQwMDAtYTAwMC0wMDAwMDAwMDAwMDEiLCJlbWFpbCI6ImFkbWluQGxicm8uZGV2Iiwicm9sZSI6ImFkbWluIiwicGVybWlzc2lvbnMiOlsiVklFV19EQVNIQ0JPQVJEX1NVTU1BUlkiLCJWSUVXX0NPTVBMSUFOQ0UiLCJWSUVXX0lORlJBU1RSVUNUVVJFIiwiVklFV19NTCIsIlJFQURfSU5DSURFTlQiLCJDUkVBVEVfSU5DSURFTlQiLCJVUERBVEVfSU5DSURFTlQiLCJERUxFVEVfSU5DSURFTlQiLCJNQU5BR0VfVVNFUlMiLCJWSUVXX0FVRElUIiwiTUFOQUdFX0NPTVBMSUFOQ0UiXSwiZXhwIjo5OTk5OTk5OTk5fQ.mock-signature'

export const authHandlers = [
  http.post('/api/v1/auth/login', async ({ request }) => {
    await delay(400)
    const body = await request.json() as { email?: string; password?: string }
    const user = MOCK_USERS.find(u => u.email === body?.email)
    if (!user || body?.password !== 'password123') {
      return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 })
    }
    return HttpResponse.json({
      access_token: FAKE_TOKEN,
      token_type: 'bearer',
      user: { id: user.id, email: user.email, full_name: user.full_name, role: user.role },
    })
  }),

  http.post('/api/v1/auth/register', async ({ request }) => {
    await delay(400)
    const body = await request.json() as { email?: string; full_name?: string; role?: string }
    return HttpResponse.json({
      id: crypto.randomUUID(),
      email: body?.email ?? 'new@lbro.dev',
      full_name: body?.full_name ?? 'New User',
      role: body?.role ?? 'viewer',
      is_active: true,
      created_at: new Date().toISOString(),
    }, { status: 201 })
  }),

  http.post('/api/v1/auth/logout', async () => {
    await delay(200)
    return new HttpResponse(null, { status: 204 })
  }),

  http.get('/api/v1/auth/me', async () => {
    await delay(150)
    return HttpResponse.json(MOCK_ME)
  }),

  http.post('/api/v1/auth/refresh', async () => {
    await delay(200)
    return HttpResponse.json({ access_token: FAKE_TOKEN, token_type: 'bearer' })
  }),

  http.post('/api/v1/auth/api-key/rotate', async () => {
    await delay(300)
    return HttpResponse.json({ api_key: 'lbro_' + Math.random().toString(36).slice(2) })
  }),
]
