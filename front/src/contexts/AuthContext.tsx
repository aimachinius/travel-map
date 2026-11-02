import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { getMe, login as apiLogin, register as apiRegister } from '../api/auth'
import { wsManager } from '../api/ws'
import type { LoginRequest, RegisterRequest, User } from '../types/auth'

interface AuthContextType {
  user: User | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (data: LoginRequest) => Promise<void>
  register: (data: RegisterRequest) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(
    localStorage.getItem('foodspot_access_token'),
  )
  const [isLoading, setIsLoading] = useState(true)

  const initAuth = async () => {
    const savedToken = localStorage.getItem('foodspot_access_token')
    if (!savedToken) {
      setUser(null)
      setIsLoading(false)
      return
    }

    try {
      const currentUser = await getMe()
      setUser(currentUser)
      setToken(savedToken)
      wsManager.connect(savedToken)
    } catch {
      localStorage.removeItem('foodspot_access_token')
      setUser(null)
      setToken(null)
      wsManager.disconnect()
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    initAuth()

    const handleAuthExpired = () => {
      setUser(null)
      setToken(null)
      wsManager.disconnect()
    }

    window.addEventListener('foodspot_auth_expired', handleAuthExpired)
    return () => {
      window.removeEventListener('foodspot_auth_expired', handleAuthExpired)
    }
  }, [])

  const login = async (data: LoginRequest) => {
    const response = await apiLogin(data)
    localStorage.setItem('foodspot_access_token', response.access_token)
    setToken(response.access_token)

    const currentUser = await getMe()
    setUser(currentUser)
    wsManager.connect(response.access_token)
  }

  const register = async (data: RegisterRequest) => {
    await apiRegister(data)
    // Sau khi đăng ký thành công, tự động đăng nhập
    await login({
      username_or_email: data.username,
      password: data.password,
    })
  }

  const logout = () => {
    localStorage.removeItem('foodspot_access_token')
    setUser(null)
    setToken(null)
    wsManager.disconnect()
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
