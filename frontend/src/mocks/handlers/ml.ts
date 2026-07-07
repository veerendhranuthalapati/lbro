import { http, HttpResponse, delay } from 'msw'
import { MOCK_ML_STATS, MOCK_ML_MODEL_INFO, MOCK_ML_FLOWS } from '../data'

const CATEGORIES = ['BENIGN', 'BRUTE_FORCE', 'PORT_SCAN', 'SQL_INJECTION', 'XSS', 'DoS', 'RCE', 'SSRF', 'IDOR', 'DATA_EXFILTRATION']

export const mlHandlers = [
  http.get('/api/v1/ml/stats', async () => {
    await delay(200)
    return HttpResponse.json(MOCK_ML_STATS)
  }),

  http.get('/api/v1/ml/model-info', async () => {
    await delay(150)
    return HttpResponse.json(MOCK_ML_MODEL_INFO)
  }),

  http.get('/api/v1/ml/models', async () => {
    await delay(150)
    return HttpResponse.json([MOCK_ML_MODEL_INFO])
  }),

  http.get('/api/v1/ml/flows', async ({ request }) => {
    await delay(250)
    const url = new URL(request.url)
    const page      = Number(url.searchParams.get('page')      ?? 1)
    const page_size = Number(url.searchParams.get('page_size') ?? 20)
    const items = MOCK_ML_FLOWS.slice((page - 1) * page_size, page * page_size)
    return HttpResponse.json({ items, total: MOCK_ML_FLOWS.length, page, page_size })
  }),

  http.get('/api/v1/ml/metrics', async () => {
    await delay(200)
    return HttpResponse.json({
      accuracy_over_time: Array.from({ length: 30 }, (_, i) => ({
        date: new Date(Date.now() - (29 - i) * 86_400_000).toISOString().slice(0, 10),
        accuracy: Number((0.945 + Math.random() * 0.025).toFixed(4)),
      })),
      confusion_matrix: {
        labels: CATEGORIES,
        matrix: CATEGORIES.map((_, ri) => CATEGORIES.map((_, ci) => ri === ci ? Math.floor(Math.random() * 400 + 100) : Math.floor(Math.random() * 8))),
      },
    })
  }),

  http.post('/api/v1/ml/classify', async ({ request }) => {
    await delay(350)
    const body = await request.json() as Record<string, unknown>
    const category = body.destination_port === 22 ? 'BRUTE_FORCE'
                   : body.destination_port === 3306 ? 'SQL_INJECTION'
                   : Math.random() > 0.7 ? CATEGORIES[Math.floor(Math.random() * CATEGORIES.length)]
                   : 'BENIGN'
    return HttpResponse.json({
      category,
      confidence: Number((0.82 + Math.random() * 0.17).toFixed(3)),
      ml_score: Number((Math.random()).toFixed(3)),
      is_anomaly: category !== 'BENIGN',
      model_version: MOCK_ML_MODEL_INFO.version,
    })
  }),
]
