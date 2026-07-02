import { create } from 'zustand'
import { X, CheckCircle, AlertTriangle, Info, XCircle } from 'lucide-react'

type ToastType = 'success' | 'error' | 'warning' | 'info'

interface Toast {
  id: string
  type: ToastType
  title: string
  message?: string
}

interface ToastStore {
  toasts: Toast[]
  add: (t: Omit<Toast, 'id'>) => void
  remove: (id: string) => void
}

export const useToast = create<ToastStore>((set) => ({
  toasts: [],
  add: (t) => {
    const id = Math.random().toString(36).slice(2)
    set((s) => ({ toasts: [...s.toasts, { ...t, id }] }))
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter(x => x.id !== id) })), 5000)
  },
  remove: (id) => set((s) => ({ toasts: s.toasts.filter(x => x.id !== id) })),
}))

const ICON: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle style={{ width: 14, height: 14, color: '#3a7a50', flexShrink: 0 }} />,
  error:   <XCircle     style={{ width: 14, height: 14, color: '#e54e1b', flexShrink: 0 }} />,
  warning: <AlertTriangle style={{ width: 14, height: 14, color: '#d97706', flexShrink: 0 }} />,
  info:    <Info        style={{ width: 14, height: 14, color: '#3b82f6', flexShrink: 0 }} />,
}

const LEFT_BORDER: Record<ToastType, string> = {
  success: '#3a7a50',
  error:   '#e54e1b',
  warning: '#d97706',
  info:    '#3b82f6',
}

export function ToastContainer() {
  const { toasts, remove } = useToast()
  return (
    <div style={{ position: 'fixed', bottom: 16, right: 16, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 8, width: 300 }}>
      {toasts.map(t => (
        <div
          key={t.id}
          style={{
            background: '#f9f5ef',
            border: '1px solid #c8c2b8',
            borderLeft: `3px solid ${LEFT_BORDER[t.type]}`,
            borderRadius: 4,
            padding: '10px 12px',
            display: 'flex',
            gap: 10,
            alignItems: 'flex-start',
            boxShadow: '0 4px 16px rgba(0,0,0,0.08)',
            animation: 'toast-in 0.18s ease',
          }}
        >
          <div style={{ marginTop: 1 }}>{ICON[t.type]}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: '#111111' }}>{t.title}</div>
            {t.message && <div style={{ fontSize: 11, color: '#6b6560', marginTop: 2 }}>{t.message}</div>}
          </div>
          <button
            onClick={() => remove(t.id)}
            style={{ color: '#c8c2b8', background: 'none', border: 'none', cursor: 'pointer', padding: 0, flexShrink: 0, lineHeight: 1 }}
            aria-label="Dismiss"
          >
            <X style={{ width: 13, height: 13 }} />
          </button>
        </div>
      ))}
      <style>{`@keyframes toast-in { from { opacity: 0; transform: translateX(16px); } to { opacity: 1; transform: translateX(0); } }`}</style>
    </div>
  )
}

// Convenience helpers
export const toast = {
  success: (title: string, message?: string) => useToast.getState().add({ type: 'success', title, message }),
  error:   (title: string, message?: string) => useToast.getState().add({ type: 'error',   title, message }),
  warning: (title: string, message?: string) => useToast.getState().add({ type: 'warning', title, message }),
  info:    (title: string, message?: string) => useToast.getState().add({ type: 'info',    title, message }),
}
