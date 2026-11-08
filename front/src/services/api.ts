/**
 * Food Spot Frontend API Client
 *
 * Kết nối trực tiếp tới FastAPI Backend (Base URL: VITE_API_BASE_URL || 'http://localhost:8000')
 * Hỗ trợ tự động đính kèm JWT Bearer Token, chuẩn hóa tham số URL và xử lý lỗi đồng nhất.
 */

import type {
  AnalysisStatusResponse,
  CurrentUserResponse,
  GetPlacesParams,
  HealthResponse,
  LoginRequest,
  LoginResponse,
  PlaceResponse,
  RegisterRequest,
  RegisterResponse,
  SavedPlaceResponse,
  SavedVideoResponse,
  VideoResponse,
  VideoSubmitRequest,
  VideoSubmitResponse,
} from '../types/api'

// Re-export toàn bộ kiểu dữ liệu để dễ dàng import từ '@services/api'
export type * from '../types/api'

export const TOKEN_STORAGE_KEY = 'foodspot_token'
export const USER_STORAGE_KEY = 'foodspot_user'
export const AUTH_CHANGE_EVENT = 'foodspot_auth_changed'

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

/** Lấy Thông tin Người dùng đã lưu từ LocalStorage */
export function getStoredUser(): CurrentUserResponse | null {
  try {
    const raw = localStorage.getItem(USER_STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/** Cập nhật hoặc xóa Thông tin Người dùng trong LocalStorage */
export function setStoredUser(user: CurrentUserResponse | null): void {
  try {
    if (user) {
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user))
    } else {
      localStorage.removeItem(USER_STORAGE_KEY)
    }
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent(AUTH_CHANGE_EVENT, { detail: user }))
    }
  } catch {
    // ignore
  }
}

/** Cập nhật hoặc xóa Auth Token trong LocalStorage */
export function setAuthToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token)
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY)
      localStorage.removeItem(USER_STORAGE_KEY)
    }
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent(AUTH_CHANGE_EVENT, { detail: null }))
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
      errorMessage = typeof detail === 'string' ? detail : JSON.stringify(detail)
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

  /** Đăng nhập lấy Bearer Access Token, tự lưu vào LocalStorage và nạp User Profile thật */
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
      try {
        const user = await this.getMe()
        setStoredUser(user)
      } catch {
        // Nếu getMe tạm thời lỗi, vẫn giữ token để người dùng tiếp tục thao tác
      }
    }

    return res
  },

  /** Lấy thông tin tài khoản hiện tại thông qua Access Token */
  async getMe(): Promise<CurrentUserResponse> {
    const user = await request<CurrentUserResponse>('/api/v1/auth/me', {
      method: 'GET',
    })
    setStoredUser(user)
    return user
  },

  /** Đăng xuất: xóa token và phiên đăng nhập khỏi LocalStorage */
  logout(): void {
    setAuthToken(null)
    setStoredUser(null)
  },

  /** Kiểm tra trạng thái đã đăng nhập hay chưa */
  isAuthenticated(): boolean {
    return Boolean(getAuthToken())
  },

  /** Lấy profile người dùng hiện tại từ bộ nhớ local */
  getCurrentUser(): CurrentUserResponse | null {
    return getStoredUser()
  },
}

// ============================================================================
// 2. PLACES API (/api/v1/places)
// ============================================================================
export const placesApi = {
  /** Lấy danh sách địa điểm theo từ khóa tìm kiếm hoặc thể loại */
  async getPlaces(params?: GetPlacesParams): Promise<PlaceResponse[]> {
    return request<PlaceResponse[]>(
      '/api/v1/places',
      { method: 'GET' },
      params as Record<string, string | number | boolean | null | undefined>,
    )
  },

  /** Lấy danh sách địa điểm người dùng đã lưu */
  async getSavedPlaces(): Promise<SavedPlaceResponse[]> {
    return request<SavedPlaceResponse[]>('/api/v1/saved/places', {
      method: 'GET',
    })
  },

  /** Xem chi tiết một địa điểm theo ID */
  async getPlaceDetail(placeId: string): Promise<PlaceResponse> {
    return request<PlaceResponse>(`/api/v1/places/${placeId}`, {
      method: 'GET',
    })
  },

  /** Lưu một địa điểm vào danh sách yêu thích */
  async savePlace(placeId: string): Promise<{ status: string; saved_id: string }> {
    return request<{ status: string; saved_id: string }>(`/api/v1/saved/places/${placeId}`, {
      method: 'POST',
    })
  },

  /** Bỏ lưu địa điểm khỏi danh sách yêu thích */
  async unsavePlace(placeId: string): Promise<void> {
    return request<void>(`/api/v1/saved/places/${placeId}`, {
      method: 'DELETE',
    })
  },
}

// ============================================================================
// 3. VIDEOS & ANALYSIS API (/api/v1/videos)
// ============================================================================
export const videosApi = {
  /** Gửi URL video TikTok/Facebook/YouTube để phân tích và trích xuất địa điểm */
  async submitVideo(data: VideoSubmitRequest): Promise<VideoSubmitResponse> {
    return request<VideoSubmitResponse>('/api/v1/videos/submit', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  /** Lấy danh sách video mà tài khoản hiện tại đã gửi */
  async getMyVideos(): Promise<VideoResponse[]> {
    return request<VideoResponse[]>('/api/v1/videos', {
      method: 'GET',
    })
  },

  /** Lấy danh sách video mà tài khoản hiện tại đã lưu */
  async getSavedVideos(): Promise<SavedVideoResponse[]> {
    return request<SavedVideoResponse[]>('/api/v1/saved/videos', {
      method: 'GET',
    })
  },

  /** Xem chi tiết một video theo ID */
  async getVideoDetail(videoId: string): Promise<VideoResponse> {
    return request<VideoResponse>(`/api/v1/videos/${videoId}`, {
      method: 'GET',
    })
  },

  /** Lưu một video */
  async saveVideo(videoId: string): Promise<{ status: string; saved_id: string }> {
    return request<{ status: string; saved_id: string }>(`/api/v1/saved/videos/${videoId}`, {
      method: 'POST',
    })
  },

  /** Bỏ lưu một video */
  async unsaveVideo(videoId: string): Promise<void> {
    return request<void>(`/api/v1/saved/videos/${videoId}`, {
      method: 'DELETE',
    })
  },

  /** Lịch sử các lần submit phân tích video */
  async getAnalysisHistory(): Promise<AnalysisStatusResponse[]> {
    return request<AnalysisStatusResponse[]>('/api/v1/videos/analysis', {
      method: 'GET',
    })
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
}

// ============================================================================
// 4. SAVED ITEMS API (/api/v1/saved) - BỘ SƯU TẬP QUÁN & VIDEO HỢP NHẤT
// ============================================================================
export const savedApi = {
  /** Lấy danh sách video đã lưu (Backend tự động JOIN kèm thông tin quán ăn nếu có) */
  async getSavedVideos(limit = 50, offset = 0): Promise<SavedVideoResponse[]> {
    return request<SavedVideoResponse[]>(
      '/api/v1/saved/videos',
      { method: 'GET' },
      { limit, offset },
    )
  },

  /** Lấy danh sách địa điểm đã lưu */
  async getSavedPlaces(limit = 50, offset = 0): Promise<SavedPlaceResponse[]> {
    return request<SavedPlaceResponse[]>(
      '/api/v1/saved/places',
      { method: 'GET' },
      { limit, offset },
    )
  },

  /** Lưu video vào bộ sưu tập */
  async saveVideo(videoId: string): Promise<{ status: string; saved_id: string }> {
    return request<{ status: string; saved_id: string }>(
      `/api/v1/saved/videos/${videoId}`,
      { method: 'POST' },
    )
  },

  /** Bỏ lưu video */
  async unsaveVideo(videoId: string): Promise<void> {
    return request<void>(
      `/api/v1/saved/videos/${videoId}`,
      { method: 'DELETE' },
    )
  },

  /** Lưu địa điểm quán ăn vào bộ sưu tập */
  async savePlace(placeId: string): Promise<{ status: string; saved_id: string }> {
    return request<{ status: string; saved_id: string }>(
      `/api/v1/saved/places/${placeId}`,
      { method: 'POST' },
    )
  },

  /** Bỏ lưu địa điểm quán ăn */
  async unsavePlace(placeId: string): Promise<void> {
    return request<void>(
      `/api/v1/saved/places/${placeId}`,
      { method: 'DELETE' },
    )
  },

  /**
   * Lưu / Bỏ lưu Video (Video vốn dĩ luôn đi kèm Địa điểm quán ăn từ kết quả phân tích)
   */
  async toggleSaveVideo(videoId: string, isSaved: boolean): Promise<boolean> {
    if (isSaved) {
      await this.unsaveVideo(videoId)
      return false
    } else {
      await this.saveVideo(videoId)
      return true
    }
  },

  /**
   * Hợp nhất 1 chạm: Lưu / Bỏ lưu Video (kèm địa điểm)
   */
  async toggleSaveSpot(params: {
    videoId?: string
    isSaved: boolean
  }): Promise<boolean> {
    const { videoId, isSaved } = params
    if (!videoId) return isSaved
    return this.toggleSaveVideo(videoId, isSaved)
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

// Default export tập hợp toàn bộ API client
export const api = {
  auth: authApi,
  places: placesApi,
  videos: videosApi,
  saved: savedApi,
  health: healthApi,
  getAuthToken,
  setAuthToken,
  getStoredUser,
  setStoredUser,
  getApiBaseUrl,
  AUTH_CHANGE_EVENT,
}

export default api

