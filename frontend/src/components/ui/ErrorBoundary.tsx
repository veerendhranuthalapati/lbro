import { Component, type ErrorInfo, type ReactNode } from 'react'
import { logger } from '@/lib/logger'
import { ShieldOff, RefreshCw } from 'lucide-react'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, info: ErrorInfo) => void
}

interface State {
  hasError: boolean
  error: Error | null
  errorId: string | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null, errorId: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
      errorId: `err-${Date.now().toString(36)}`,
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    logger.error('React ErrorBoundary caught error', error, {
      component: 'ErrorBoundary',
      componentStack: info.componentStack ?? undefined,
    })
    this.props.onError?.(error, info)
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null, errorId: null })
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <div
          role="alert"
          aria-live="assertive"
          style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            minHeight: 256, gap: 16, padding: 32,
            background: CREAM, border: `1px solid ${BORDER}`, borderLeft: `3px solid ${ORANGE}`, borderRadius: 4,
          }}
        >
          <ShieldOff style={{ width: 32, height: 32, color: ORANGE, opacity: 0.5 }} aria-hidden="true" />
          <div style={{ textAlign: 'center' }}>
            <h2 style={{ fontSize: 14, fontWeight: 500, color: BLACK, marginBottom: 4 }}>Something went wrong</h2>
            <p style={{ fontSize: 12, color: GRAY }}>
              {this.state.error?.message ?? 'An unexpected error occurred'}
            </p>
            {this.state.errorId && (
              <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: BORDER, marginTop: 4 }}>
                Error ID: {this.state.errorId}
              </p>
            )}
          </div>
          <button
            onClick={this.handleReset}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 16px', border: `1px solid ${BORDER}`, borderRadius: 2, background: 'transparent',
              fontSize: 11, color: GRAY, cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.08em',
              transition: 'border-color 0.15s, color 0.15s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = ORANGE; (e.currentTarget as HTMLElement).style.color = ORANGE }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = BORDER; (e.currentTarget as HTMLElement).style.color = GRAY }}
          >
            <RefreshCw style={{ width: 12, height: 12 }} aria-hidden="true" />
            Try again
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
