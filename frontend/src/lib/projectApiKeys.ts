/** Session-only storage for project API keys (shown once at create/regenerate). */

const STORAGE_KEY = 'lbro-project-api-keys'

function readMap(): Record<string, string> {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? '{}') as Record<string, string>
  } catch {
    return {}
  }
}

export function storeProjectApiKey(projectId: string, apiKey: string): void {
  const map = readMap()
  map[projectId] = apiKey
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(map))
}

export function getProjectApiKey(projectId: string): string | null {
  return readMap()[projectId] ?? null
}

export function clearProjectApiKey(projectId: string): void {
  const map = readMap()
  delete map[projectId]
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(map))
}
