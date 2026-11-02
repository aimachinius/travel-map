export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  data: any

  constructor(status: number, message: string, data?: any) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const token = localStorage.getItem('foodspot_access_token')

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const url = endpoint.startsWith('http')
    ? endpoint
    : `${API_BASE_URL}${endpoint}`

  const response = await fetch(url, {
    ...options,
    headers,
  })

  if (response.status === 204) {
    return null as T
  }

  let responseData: any = null
  const contentType = response.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    try {
      responseData = await response.json()
    } catch {
      responseData = null
    }
  } else {
    try {
      responseData = await response.text()
    } catch {
      responseData = null
    }
  }

  if (!response.ok) {
    if (response.status === 401) {
      // Token hết hạn hoặc không hợp lệ
      localStorage.removeItem('foodspot_access_token')
      window.dispatchEvent(new Event('foodspot_auth_expired'))
    }

    const message =
      (responseData && (responseData.detail || responseData.message)) ||
      `Yêu cầu thất bại với mã lỗi ${response.status}`
    throw new ApiError(response.status, message, responseData)
  }

  return responseData as T
}
