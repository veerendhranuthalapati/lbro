import { http, HttpResponse, delay } from 'msw'
import { MOCK_INFRASTRUCTURE, MOCK_SQS_HISTORY } from '../data'

export const infrastructureHandlers = [
  http.get('/api/v1/infrastructure', async () => {
    await delay(300)
    return HttpResponse.json(MOCK_INFRASTRUCTURE)
  }),

  http.get('/api/v1/infrastructure/sqs-history', async () => {
    await delay(200)
    return HttpResponse.json(MOCK_SQS_HISTORY)
  }),

  http.get('/api/v1/health', async () => {
    await delay(100)
    return HttpResponse.json({ status: 'healthy', timestamp: new Date().toISOString(), version: '2.4.1' })
  }),
]
