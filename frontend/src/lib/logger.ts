/**
 * LBRO Observability Utilities -- Phase 7
 *
 * Structured logging with context, Sentry integration hooks,
 * and frontend performance tracing.
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error'

interface LogContext {
  component?: string
  action?: string
  incident_id?: string
  user_id?: string
  request_id?: string
  [key: string]: unknown
}

interface LogEntry {
  level: LogLevel
  message: string
  timestamp: string
  context: LogContext
  error?: {
    message: string
    stack?: string
    name: string
  }
}

const IS_DEV = import.meta.env.DEV

function createEntry(level: LogLevel, message: string, context: LogContext = {}, error?: Error): LogEntry {
  return {
    level,
    message,
    timestamp: new Date().toISOString(),
    context,
    error: error ? { message: error.message, stack: error.stack, name: error.name } : undefined,
  }
}

function emit(entry: LogEntry): void {
  if (IS_DEV) {
    const style = {
      debug: 'color: #64748b',
      info: 'color: #00d4ff',
      warn: 'color: #eab308',
      error: 'color: #ef4444; font-weight: bold',
    }[entry.level]

    console.groupCollapsed(`%c[LBRO ${entry.level.toUpperCase()}] ${entry.message}`, style)
    console.log('Context:', entry.context)
    if (entry.error) console.error('Error:', entry.error)
    console.groupEnd()
  } else {
    // In production: send to log aggregator (e.g. Datadog RUM, CloudWatch Logs)
    // Replace with real transport
    try {
      const logLine = JSON.stringify(entry)
      // Example: navigator.sendBeacon('/api/v1/frontend-logs', logLine)
      // For now we suppress in production to avoid console exposure
      void logLine
    } catch {
      // Swallow serialization errors
    }
  }

  // Sentry integration stub
  if (entry.level === 'error' && entry.error) {
    sendToSentry(entry)
  }
}

function sendToSentry(entry: LogEntry): void {
  // When Sentry is configured:
  // import * as Sentry from '@sentry/react'
  // Sentry.captureException(new Error(entry.message), { extra: entry.context })
  // For now: no-op
  void entry
}

export const logger = {
  debug: (message: string, context?: LogContext) =>
    emit(createEntry('debug', message, context)),

  info: (message: string, context?: LogContext) =>
    emit(createEntry('info', message, context)),

  warn: (message: string, context?: LogContext) =>
    emit(createEntry('warn', message, context)),

  error: (message: string, error?: Error | unknown, context?: LogContext) => {
    const err = error instanceof Error ? error : new Error(String(error))
    emit(createEntry('error', message, context, err))
  },
}

// ---- User action audit trail ------------------------------------------------------------------------------------------------------

export function auditAction(action: string, resource_type: string, resource_id: string, metadata?: Record<string, unknown>): void {
  logger.info(`AUDIT: ${action}`, {
    action,
    resource_type,
    resource_id,
    ...metadata,
  })
  // In production: POST to /api/v1/audit-logs
}

// ---- Performance marks ----------------------------------------------------------------------------------------------------------------

export function markStart(name: string): void {
  if (typeof performance !== 'undefined') {
    performance.mark(`lbro-${name}-start`)
  }
}

export function markEnd(name: string): void {
  if (typeof performance !== 'undefined') {
    performance.mark(`lbro-${name}-end`)
    try {
      const measure = performance.measure(
        `lbro-${name}`,
        `lbro-${name}-start`,
        `lbro-${name}-end`
      )
      if (measure.duration > 1000) {
        logger.warn(`Slow operation: ${name} took ${measure.duration.toFixed(0)}ms`)
      }
    } catch {
      // Marks may not exist if start was not called
    }
  }
}

// ---- Request ID tracking --------------------------------------------------------------------------------------------------------------

export function generateRequestId(): string {
  return `lbro-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}
