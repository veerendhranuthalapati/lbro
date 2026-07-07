import { http, HttpResponse, delay } from 'msw'
import { MOCK_DASHBOARD, MOCK_SECURITY_SCORE } from '../data'

// Note: /api/v1/reports/weekly and /api/v1/reports/weekly/pdf are handled
// by reportHandlers in handlers/reports.ts (real reportlab PDF, correct headers).
// Removed here to avoid MSW handler conflicts (first-registered wins).

export const dashboardHandlers = [
  http.get('/api/v1/dashboard/summary', async () => {
    await delay(200)
    return HttpResponse.json(MOCK_DASHBOARD)
  }),

  http.get('/api/v1/security-score', async () => {
    await delay(250)
    return HttpResponse.json(MOCK_SECURITY_SCORE)
  }),
]
