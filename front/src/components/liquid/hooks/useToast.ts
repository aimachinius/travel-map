import { useCallback, useRef, useState } from 'react'
import type { ToastState } from '../types'

export function useToast() {
  const [toast, setToast] = useState<ToastState | null>(null)
  const timerRef = useRef<number | null>(null)

  const showToast = useCallback(
    (type: 'success' | 'error' | 'info', title: string, message: string) => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
      }
      setToast({ type, title, message })
      timerRef.current = window.setTimeout(() => {
        setToast(null)
      }, 3500)
    },
    [],
  )

  const hideToast = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
    }
    setToast(null)
  }, [])

  return { toast, showToast, hideToast }
}

