import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { authApi, getAuthToken } from './api'
import type {
  CurrentUserResponse,
  LoginRequest,
  RegisterRequest,
} from '../types/api'

interface AuthContextType {
  user: CurrentUserResponse | null
  token: string | null
  loading: boolean
  login: (credentials: LoginRequest) => Promise<void>
  register: (data: RegisterRequest) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

// Key lưu trữ thông tin cache user để hiển thị tức thì khi tải lại trang
const USER_CACHE_KEY = 'foodspot_user_cache'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => getAuthToken())
  const [user, setUser] = useState<CurrentUserResponse | null>(() => {
    try {
      const cached = localStorage.getItem(USER_CACHE_KEY)
      return cached ? JSON.parse(cached) : null
    } catch {
      return null
    }
  })
  const [loading, setLoading] = useState<boolean>(true)

  const refreshUser = useCallback(async () => {
    const currentToken = getAuthToken()
    if (!currentToken) {
      setUser(null)
      localStorage.removeItem(USER_CACHE_KEY)
      setLoading(false)
      return
    }

    try {
      const me = await authApi.getMe()
      setUser(me)
      localStorage.setItem(USER_CACHE_KEY, JSON.stringify(me))
    } catch {
      // Token hết hạn hoặc không hợp lệ -> xóa token
      authApi.logout()
      setUser(null)
      localStorage.removeItem(USER_CACHE_KEY)
      setTokenState(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshUser()
  }, [refreshUser])

  const login = useCallback(
    async (credentials: LoginRequest) => {
      const res = await authApi.login(credentials, true)
      setTokenState(res.access_token)
      const me = await authApi.getMe()
      setUser(me)
      localStorage.setItem(USER_CACHE_KEY, JSON.stringify(me))
    },
    [],
  )

  const register = useCallback(
    async (data: RegisterRequest) => {
      await authApi.register(data)
    },
    [],
  )

  const logout = useCallback(() => {
    authApi.logout()
    setTokenState(null)
    setUser(null)
    localStorage.removeItem(USER_CACHE_KEY)
  }, [])

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth phải được sử dụng bên trong AuthProvider')
  }
  return context
}
