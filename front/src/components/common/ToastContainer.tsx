import { useAnalysis } from '../../contexts/AnalysisContext'
import './ToastContainer.css'

export default function ToastContainer() {
  const { toasts, dismissToast, setLatestTargetLocation } = useAnalysis()

  if (toasts.length === 0) return null

  return (
    <div className="toast-container" aria-live="polite">
      {toasts.map((toast) => {
        const isCompleted = toast.status === 'COMPLETED'
        const isFailed = toast.status === 'FAILED'
        const isProcessing = toast.status === 'PROCESSING'
        const isPending = toast.status === 'PENDING'

        return (
          <div
            key={toast.id}
            className={`toast-item toast-${toast.status.toLowerCase()}`}
          >
            <div className="toast-icon-area">
              {isProcessing && <span className="toast-spinner" />}
              {isPending && <span className="toast-badge">⏳</span>}
              {isCompleted && <span className="toast-badge">✓</span>}
              {isFailed && <span className="toast-badge">✕</span>}
            </div>

            <div className="toast-content">
              <h4>{toast.title}</h4>
              <p>{toast.message}</p>
              {toast.restaurant && (
                <button
                  type="button"
                  className="toast-action-btn"
                  onClick={() => {
                    const r = toast.restaurant
                    if (
                      r &&
                      r.latitude !== null &&
                      r.latitude !== undefined &&
                      r.longitude !== null &&
                      r.longitude !== undefined
                    ) {
                      setLatestTargetLocation([r.latitude, r.longitude])
                    }
                  }}
                >
                  Xem trên bản đồ →
                </button>
              )}
            </div>

            <button
              type="button"
              className="toast-close"
              onClick={() => dismissToast(toast.id)}
              aria-label="Đóng thông báo"
            >
              ×
            </button>
          </div>
        )
      })}
    </div>
  )
}

