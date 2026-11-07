/**
 * Food Spot Frontend API Client
 *
 * Kết nối trực tiếp tới FastAPI Backend (Base URL: VITE_API_BASE_URL || 'http://localhost:8000')
 * Hỗ trợ tự động đính kèm JWT Bearer Token, chuẩn hóa tham số URL và xử lý lỗi đồng nhất.
 */

import type {
  AnalysisStatusResponse,
  CurrentUserResponse,
  GetNearbyVideosParams,
  GetPlacesParams,
  HealthResponse,
  LoginRequest,
  LoginResponse,
  NearbyVideoItem,
  PlaceResponse,
  PlaceVideoMatchItem,
  RegisterRequest,
  RegisterResponse,
  SavedPlaceResponse,
  SavedVideoResponse,
  VideoResponse,
  VideoSubmitRequest,
  VideoSubmitResponse,
} from '../types/api'

// Re-export toàn bộ kiểu dữ liệu để dễ dàng import từ 'services/api'
export type * from '../types/api'

export const TOKEN_STORAGE_KEY = 'foodspot_token'

export class ApiError extends Error {
  status: number
  detail: string | unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

/** Lấy Base URL từ biến môi trường hoặc fallback về localhost:8000 */
export function getApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL
  if (typeof envUrl === 'string' && envUrl.trim().length > 0) {
    return envUrl.replace(/\/+$/, '')
  }
  return 'http://localhost:8000'
}

/** Lấy Auth Token từ LocalStorage */
export function getAuthToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

/** Cập nhật hoặc xóa Auth Token trong LocalStorage */
export function setAuthToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token)
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY)
    }
  } catch {
    // Không chặn luồng nếu môi trường không cho phép truy cập LocalStorage
  }
}

/** Request helper xử lý Header, Token, Body JSON và Parse lỗi trả về */
async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  queryParams?: Record<string, string | number | boolean | null | undefined>,
): Promise<T> {
  const baseUrl = getApiBaseUrl()
  let url = `${baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`

  if (queryParams) {
    const searchParams = new URLSearchParams()
    for (const [key, val] of Object.entries(queryParams)) {
      if (val !== undefined && val !== null && val !== '') {
        searchParams.append(key, String(val))
      }
    }
    const queryString = searchParams.toString()
    if (queryString) {
      url += (url.includes('?') ? '&' : '?') + queryString
    }
  }

  const token = getAuthToken()
  const headers = new Headers(options.headers || {})

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(url, {
    ...options,
    headers,
  })

  // Nếu trả về 204 No Content (ví dụ các hàm DELETE/Unsave)
  if (response.status === 204) {
    return undefined as unknown as T
  }

  let responseData: unknown
  const contentType = response.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    try {
      responseData = await response.json()
    } catch {
      responseData = null
    }
  } else {
    responseData = await response.text()
  }

  if (!response.ok) {
    let errorMessage = `Yêu cầu thất bại (${response.status})`
    if (
      responseData &&
      typeof responseData === 'object' &&
      'detail' in responseData
    ) {
      const detail = (responseData as { detail: unknown }).detail
      if (typeof detail === 'string') {
        errorMessage = detail
      } else if (Array.isArray(detail)) {
        errorMessage = detail
          .map((item: unknown) =>
            item && typeof item === 'object' && 'msg' in item
              ? String((item as { msg: unknown }).msg)
              : JSON.stringify(item),
          )
          .join(', ')
      } else if (detail) {
        errorMessage = JSON.stringify(detail)
      }
    } else if (typeof responseData === 'string' && responseData.length > 0) {
      errorMessage = responseData
    }

    throw new ApiError(response.status, errorMessage, responseData)
  }

  return responseData as T
}

// ============================================================================
// 1. AUTH API (/api/v1/auth)
// ============================================================================
export const authApi = {
  /** Đăng ký tài khoản người dùng mới */
  async register(data: RegisterRequest): Promise<RegisterResponse> {
    return request<RegisterResponse>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  /** Đăng nhập lấy Bearer Access Token và tự lưu vào LocalStorage */
  async login(
    data: LoginRequest,
    autoStoreToken = true,
  ): Promise<LoginResponse> {
    const res = await request<LoginResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    })

    if (autoStoreToken && res.access_token) {
      setAuthToken(res.access_token)
    }

    return res
  },

  /** Lấy thông tin tài khoản hiện tại thông qua Access Token */
  async getMe(): Promise<CurrentUserResponse> {
    return request<CurrentUserResponse>('/api/v1/auth/me', {
      method: 'GET',
    })
  },

  /** Đăng xuất: xóa token khỏi LocalStorage */
  logout(): void {
    setAuthToken(null)
  },
}

// ============================================================================
// 2. PLACES API (/api/v1/places)
// ============================================================================
export const placesApi = {
  /** Lấy danh sách video và quán ăn theo bán kính tọa độ (Core Map Discovery) */
  async getNearbyVideos(params: GetNearbyVideosParams): Promise<NearbyVideoItem[]> {
    return request<NearbyVideoItem[]>(
      '/api/v1/places/nearby-videos',
      { method: 'GET' },
      params as unknown as Record<string, string | number | boolean | null | undefined>,
    )
  },

  /** Tìm kiếm địa điểm theo từ khóa hoặc thể loại */
  async searchPlaces(params?: GetPlacesParams): Promise<PlaceResponse[]> {
    return request<PlaceResponse[]>(
      '/api/v1/places/search',
      { method: 'GET' },
      params as unknown as Record<string, string | number | boolean | null | undefined>,
    )
  },

  /** Alias lấy danh sách địa điểm */
  async getPlaces(params?: GetPlacesParams): Promise<PlaceResponse[]> {
    return this.searchPlaces(params)
  },

  /** Xem chi tiết một địa điểm theo ID */
  async getPlaceDetail(placeId: string): Promise<PlaceResponse> {
    return request<PlaceResponse>(`/api/v1/places/${placeId}`, {
      method: 'GET',
    })
  },

  /** Lấy toàn bộ video review của một quán ăn */
  async getPlaceVideos(placeId: string, limit = 50, offset = 0): Promise<PlaceVideoMatchItem[]> {
    return request<PlaceVideoMatchItem[]>(
      `/api/v1/places/${placeId}/videos`,
      { method: 'GET' },
      { limit, offset },
    )
  },

  /** Forward to Saved Items */
  async getSavedPlaces(): Promise<SavedPlaceResponse[]> {
    return savedApi.getSavedPlaces()
  },
  async savePlace(placeId: string): Promise<{ status: string; message: string; saved_id: string }> {
    return savedApi.savePlace(placeId)
  },
  async unsavePlace(placeId: string): Promise<void> {
    return savedApi.unsavePlace(placeId)
  },
}

// ============================================================================
// 3. VIDEOS & ANALYSIS API (/api/v1/videos)
// ============================================================================
export const videosApi = {
  /** Gửi URL video TikTok/YouTube để phân tích và trích xuất địa điểm */
  async submitVideo(data: VideoSubmitRequest): Promise<VideoSubmitResponse> {
    return request<VideoSubmitResponse>('/api/v1/videos/submit', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  /** Lấy danh sách video mà tài khoản hiện tại đã gửi */
  async getMyVideos(limit = 20, offset = 0): Promise<VideoResponse[]> {
    return request<VideoResponse[]>(
      '/api/v1/videos',
      { method: 'GET' },
      { limit, offset },
    )
  },

  /** Xem chi tiết một video theo ID */
  async getVideoDetail(videoId: string): Promise<VideoResponse> {
    return request<VideoResponse>(`/api/v1/videos/${videoId}`, {
      method: 'GET',
    })
  },

  /** Lịch sử các lần submit phân tích video của tài khoản */
  async getAnalysisHistory(limit = 20, offset = 0): Promise<AnalysisStatusResponse[]> {
    return request<AnalysisStatusResponse[]>(
      '/api/v1/videos/analysis',
      { method: 'GET' },
      { limit, offset },
    )
  },

  /** Kiểm tra trạng thái phân tích của một tác vụ cụ thể */
  async getAnalysisStatus(
    analysisRunId: string,
  ): Promise<AnalysisStatusResponse> {
    return request<AnalysisStatusResponse>(
      `/api/v1/videos/analysis/${analysisRunId}`,
      { method: 'GET' },
    )
  },

  /** Forward to Saved Items */
  async getSavedVideos(): Promise<SavedVideoResponse[]> {
    return savedApi.getSavedVideos()
  },
  async saveVideo(videoId: string): Promise<{ status: string; message: string; saved_id: string }> {
    return savedApi.saveVideo(videoId)
  },
  async unsaveVideo(videoId: string): Promise<void> {
    return savedApi.unsaveVideo(videoId)
  },
}

// ============================================================================
// 4. SAVED API (/api/v1/saved)
// ============================================================================
export const savedApi = {
  /** Lấy danh sách video đã lưu */
  async getSavedVideos(limit = 50, offset = 0): Promise<SavedVideoResponse[]> {
    return request<SavedVideoResponse[]>(
      '/api/v1/saved/videos',
      { method: 'GET' },
      { limit, offset },
    )
  },

  /** Lưu video vào danh sách yêu thích */
  async saveVideo(videoId: string): Promise<{ status: string; message: string; saved_id: string }> {
    return request<{ status: string; message: string; saved_id: string }>(
      `/api/v1/saved/videos/${videoId}`,
      { method: 'POST' },
    )
  },

  /** Bỏ lưu video khỏi danh sách yêu thích */
  async unsaveVideo(videoId: string): Promise<void> {
    return request<void>(`/api/v1/saved/videos/${videoId}`, {
      method: 'DELETE',
    })
  },

  /** Lấy danh sách địa điểm đã lưu */
  async getSavedPlaces(limit = 50, offset = 0): Promise<SavedPlaceResponse[]> {
    return request<SavedPlaceResponse[]>(
      '/api/v1/saved/places',
      { method: 'GET' },
      { limit, offset },
    )
  },

  /** Lưu địa điểm vào danh sách yêu thích */
  async savePlace(placeId: string): Promise<{ status: string; message: string; saved_id: string }> {
    return request<{ status: string; message: string; saved_id: string }>(
      `/api/v1/saved/places/${placeId}`,
      { method: 'POST' },
    )
  },

  /** Bỏ lưu địa điểm khỏi danh sách yêu thích */
  async unsavePlace(placeId: string): Promise<void> {
    return request<void>(`/api/v1/saved/places/${placeId}`, {
      method: 'DELETE',
    })
  },
}

// ============================================================================
// 5. HEALTH API (/api/v1/health & /health)
// ============================================================================
export const healthApi = {
  /** Kiểm tra trạng thái hoạt động của Backend */
  async check(): Promise<HealthResponse> {
    return request<HealthResponse>('/api/v1/health', {
      method: 'GET',
    })
  },
}

// ============================================================================
// 6. WEBSOCKET HELPER
// ============================================================================
export function createAnalysisWebSocket(
  token: string,
  onMessage: (data: unknown) => void,
  onError?: (err: Event) => void,
  onClose?: () => void,
): WebSocket {
  const baseUrl = getApiBaseUrl()
  const wsProto = baseUrl.startsWith('https') ? 'wss:' : 'ws:'
  const wsHost = baseUrl.replace(/^https?:\/\//, '')
  const wsUrl = `${wsProto}//${wsHost}/api/v1/ws?token=${encodeURIComponent(token)}`

  const ws = new WebSocket(wsUrl)
  let pingTimer: ReturnType<typeof setInterval> | null = null

  ws.onopen = () => {
    // Gửi ping heartbeat mỗi 25 giây để tránh timeout
    pingTimer = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 25000)
  }

  ws.onmessage = (event) => {
    if (event.data === 'pong') return
    try {
      const parsed = JSON.parse(event.data)
      onMessage(parsed)
    } catch {
      onMessage(event.data)
    }
  }

  const handleClose = () => {
    if (pingTimer) {
      clearInterval(pingTimer)
      pingTimer = null
    }
    if (onClose) onClose()
  }

  ws.onclose = handleClose
  if (onError) ws.onerror = onError
  return ws
}

// Default export tập hợp toàn bộ API client
export const api = {
  auth: authApi,
  places: placesApi,
  videos: videosApi,
  saved: savedApi,
  health: healthApi,
  createAnalysisWebSocket,
  getAuthToken,
  setAuthToken,
  getApiBaseUrl,
}

export default api
