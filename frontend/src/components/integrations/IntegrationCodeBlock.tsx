/**
 * Accessible copy control for integration code blocks.
 * Uses Clipboard API with execCommand fallback for non-secure contexts.
 */
import { useState, useCallback } from 'react'
import { Check, Copy } from 'lucide-react'

async function copyText(text: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      /* fall through */
    }
  }
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.setAttribute('readonly', 'true')
    ta.style.position = 'fixed'
    ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch {
    return false
  }
}

export function CopyCodeButton({
  text,
  label = 'Copy code',
}: {
  text: string
  label?: string
}) {
  const [state, setState] = useState<'idle' | 'ok' | 'fail'>('idle')

  const onCopy = useCallback(async () => {
    const ok = await copyText(text)
    setState(ok ? 'ok' : 'fail')
    window.setTimeout(() => setState('idle'), 2000)
  }, [text])

  const labelText =
    state === 'ok' ? 'Copied' : state === 'fail' ? 'Copy failed' : label

  return (
    <button
      type="button"
      onClick={() => void onCopy()}
      aria-label={labelText}
      className="flex items-center gap-1 transition-colors text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 rounded px-1"
      style={{
        color: state === 'ok' ? '#22c55e' : state === 'fail' ? ORANGE : '#555',
        ['--tw-ring-color' as string]: ORANGE,
      }}
    >
      {state === 'ok' ? <Check className="w-3 h-3" aria-hidden /> : <Copy className="w-3 h-3" aria-hidden />}
      <span aria-hidden>{state === 'ok' ? 'Copied' : state === 'fail' ? 'Failed' : 'Copy'}</span>
    </button>
  )
}

const ORANGE = '#e54e1b'

export function IntegrationCodeBlock({
  code,
  lang,
  wrap,
  onToggleWrap,
}: {
  code: string
  lang?: string
  wrap?: boolean
  onToggleWrap?: () => void
}) {
  return (
    <div className="rounded-lg overflow-hidden" style={{ border: '1px solid #1e1e1e' }}>
      <div
        className="flex items-center justify-between px-3 py-1.5 gap-2"
        style={{ background: '#0f0f0f', borderBottom: '1px solid #1e1e1e' }}
      >
        <span className="text-xs text-zinc-500 truncate">{lang ?? 'bash'}</span>
        <div className="flex items-center gap-2 shrink-0">
          {onToggleWrap && (
            <button
              type="button"
              onClick={onToggleWrap}
              className="text-xs text-zinc-500 hover:text-zinc-300 focus-visible:outline focus-visible:outline-2 rounded px-1"
              aria-pressed={wrap}
            >
              {wrap ? 'No wrap' : 'Wrap'}
            </button>
          )}
          <CopyCodeButton text={code} />
        </div>
      </div>
      <pre
        tabIndex={0}
        className="p-4 text-xs leading-relaxed overflow-x-auto max-h-[28rem] overflow-y-auto"
        style={{
          background: '#0a0a0a',
          color: '#d4d4d4',
          fontFamily: 'monospace',
          margin: 0,
          whiteSpace: wrap ? 'pre-wrap' : 'pre',
          wordBreak: wrap ? 'break-word' : 'normal',
        }}
      >
        {code}
      </pre>
    </div>
  )
}
