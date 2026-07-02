/**
 * Frontend rate limiting utilities -- Phase 4
 *
 * Implements:
 * - Token bucket for per-endpoint throttling
 * - Exponential backoff with jitter
 * - Request deduplication via in-flight map
 * - Login attempt tracking
 */
import { REQUEST_THROTTLE_MS, RETRY_BASE_DELAY_MS, RETRY_MAX_DELAY_MS } from '@/constants'

// ---- Exponential backoff --------------------------------------------------------------------------------------------------------------

export function exponentialBackoff(attempt: number, baseMs = RETRY_BASE_DELAY_MS, maxMs = RETRY_MAX_DELAY_MS): number {
  const jitter = Math.random() * 200
  return Math.min(baseMs * Math.pow(2, attempt) + jitter, maxMs)
}

export function shouldRetry(status: number, attempt: number, maxRetries: number): boolean {
  if (attempt >= maxRetries) return false
  // Retry on network errors and 5xx, never on 4xx (client errors)
  return status === 0 || status === 429 || status >= 500
}

// ---- Token bucket throttle --------------------------------------------------------------------------------------------------------

class TokenBucket {
  private tokens: number
  private lastRefill: number

  constructor(
    private readonly capacity: number,
    private readonly refillRatePerMs: number
  ) {
    this.tokens = capacity
    this.lastRefill = Date.now()
  }

  consume(count = 1): boolean {
    this.refill()
    if (this.tokens >= count) {
      this.tokens -= count
      return true
    }
    return false
  }

  private refill(): void {
    const now = Date.now()
    const elapsed = now - this.lastRefill
    const refilled = elapsed * this.refillRatePerMs
    this.tokens = Math.min(this.capacity, this.tokens + refilled)
    this.lastRefill = now
  }

  get remaining(): number {
    this.refill()
    return Math.floor(this.tokens)
  }
}

// 60 requests per minute burst, refill 1 per second
export const globalApiThrottle = new TokenBucket(60, 1 / 1000)

// ---- Request deduplication --------------------------------------------------------------------------------------------------------

const inflight = new Map<string, Promise<unknown>>()

export function deduplicate<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const existing = inflight.get(key)
  if (existing) return existing as Promise<T>

  const promise = fn().finally(() => inflight.delete(key))
  inflight.set(key, promise)
  return promise
}

// ---- Debounce ----------------------------------------------------------------------------------------------------------------------------------

export function debounce<T extends (...args: unknown[]) => unknown>(
  fn: T,
  delayMs = REQUEST_THROTTLE_MS
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout> | null = null
  return (...args: Parameters<T>) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delayMs)
  }
}

// ---- Upload rate limiter --------------------------------------------------------------------------------------------------------------

class UploadRateLimiter {
  private bytesThisMinute = 0
  private windowStart = Date.now()

  canUpload(bytes: number, limitBytesPerMin: number): boolean {
    const now = Date.now()
    if (now - this.windowStart > 60_000) {
      this.bytesThisMinute = 0
      this.windowStart = now
    }
    if (this.bytesThisMinute + bytes > limitBytesPerMin) return false
    this.bytesThisMinute += bytes
    return true
  }
}

export const uploadLimiter = new UploadRateLimiter()
