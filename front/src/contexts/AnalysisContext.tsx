import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { wsManager } from '../api/ws'
import type {
  AnalysisUpdateRestaurant,
  AnalysisUpdatedEvent,
} from '../types/ws'

export interface AnalysisToast {
  id: string
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
  title: string
  message: string
  restaurant?: AnalysisUpdateRestaurant | null
}

interface AnalysisContextType {
  toasts: AnalysisToast[]
  dismissToast: (id: string) => void
  addCustomToast: (toast: Omit<AnalysisToast, 'id'>) => string
  latestTargetLocation: [number, number] | null
  setLatestTargetLocation: (loc: [number, number] | null) => void
}

const AnalysisContext = createContext<AnalysisContextType | undefined>(undefined)

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<AnalysisToast[]>([])
  const [latestTargetLocation, setLatestTargetLocation] = useState<
    [number, number] | null
  >(null)

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  const addCustomToast = (toast: Omit<AnalysisToast, 'id'>): string => {
    const id = Date.now().toString() + Math.random().toString(36).substring(2, 6)
    const newToast: AnalysisToast = { ...toast, id }
    setToasts((prev) => [newToast, ...prev.slice(0, 4)])
    return id
  }

  useEffect(() => {
    const unsubscribe = wsManager.subscribe((event: AnalysisUpdatedEvent) => {
      const { data } = event
      const runId = data.analysis_run_id

      let title = 'Tiến trình phân tích video'
      let message = ''

      if (data.status === 'PROCESSING') {
        title = 'AI đang trích xuất dữ liệu...'
        message = 'Đang nhận diện âm thanh, hình ảnh và biển hiệu quán ăn.'
      } else if (data.status === 'COMPLETED') {
        if (data.restaurant && data.restaurant.name) {
          title = 'Phân tích hoàn tất!'
          message = `Đã tìm thấy: ${data.restaurant.name} (${data.restaurant.address || 'Đã định vị trên bản đồ'})`
          if (
            data.restaurant.latitude !== null &&
            data.restaurant.longitude !== null
          ) {
            setLatestTargetLocation([
              data.restaurant.latitude,
              data.restaurant.longitude,
            ])
          }
        } else {
          title = 'Phân tích hoàn tất'
          message = 'Video không chứa thông tin địa điểm ẩm thực cụ thể.'
        }
      } else if (data.status === 'FAILED') {
        title = 'Phân tích thất bại'
        message = data.error_message || 'Có lỗi xảy ra trong quá trình xử lý.'
      }

      setToasts((prev) => {
        // Cập nhật toast cũ nếu cùng runId hoặc thêm mới
        const filtered = prev.filter((t) => t.id !== runId)
        const updated: AnalysisToast = {
          id: runId,
          status: data.status,
          title,
          message,
          restaurant: data.restaurant,
        }
        return [updated, ...filtered.slice(0, 4)]
      })

      // Tự động tắt toast sau 8s nếu COMPLETED hoặc FAILED
      if (data.status === 'COMPLETED' || data.status === 'FAILED') {
        setTimeout(() => {
          dismissToast(runId)
        }, 8000)
      }
    })

    return () => {
      unsubscribe()
    }
  }, [])

  return (
    <AnalysisContext.Provider
      value={{
        toasts,
        dismissToast,
        addCustomToast,
        latestTargetLocation,
        setLatestTargetLocation,
      }}
    >
      {children}
    </AnalysisContext.Provider>
  )
}

export function useAnalysis() {
  const context = useContext(AnalysisContext)
  if (!context) {
    throw new Error('useAnalysis must be used within an AnalysisProvider')
  }
  return context
}
