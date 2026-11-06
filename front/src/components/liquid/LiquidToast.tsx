import type { ToastState } from './types'

interface LiquidToastProps {
  toast: ToastState | null
}

export default function LiquidToast({ toast }: LiquidToastProps) {
  if (!toast) return null

  const getIcon = () => {
    if (toast.type === 'success') {
      return (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      )
    }
    if (toast.type === 'error') {
      return (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      )
    }
    return (
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="16" x2="12" y2="12" />
        <line x1="12" y1="8" x2="12.01" y2="8" />
      </svg>
    )
  }

  return (
    <div className={`toast-notification liquid-glass ${toast.type} show`} role="alert">
      <div className="toast-icon">{getIcon()}</div>
      <div className="toast-body">
        <div className="toast-title">{toast.title}</div>
        <div className="toast-msg">{toast.message}</div>
      </div>
    </div>
  )
}

