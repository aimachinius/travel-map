import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { DrawerMode } from './types'
import {
  authApi,
  getStoredUser,
  AUTH_CHANGE_EVENT,
  type CurrentUserResponse,
} from '../../services/api'

interface LeftFloatingDockProps {
  onOpenDrawer: (mode: DrawerMode) => void
  savedCount?: number
}

export default function LeftFloatingDock({
  onOpenDrawer,
  savedCount = 0,
}: LeftFloatingDockProps) {
  const [user, setUser] = useState<CurrentUserResponse | null>(() => getStoredUser())
  const navigate = useNavigate()

  useEffect(() => {
    const handleAuthChange = () => {
      setUser(getStoredUser())
    }
    window.addEventListener(AUTH_CHANGE_EVENT, handleAuthChange)
    window.addEventListener('storage', handleAuthChange)
    return () => {
      window.removeEventListener(AUTH_CHANGE_EVENT, handleAuthChange)
      window.removeEventListener('storage', handleAuthChange)
    }
  }, [])

  const handleAccountClick = () => {
    if (user) {
      if (window.confirm(`Bạn có muốn đăng xuất khỏi tài khoản "${user.full_name || user.username}"?`)) {
        authApi.logout()
        setUser(null)
      }
    } else {
      navigate('/login')
    }
  }

  return (
    <aside className="left-floating-dock" aria-label="Cụm phím tác vụ nhanh">
      {/* 1. Bộ Sưu Tập Món & Quán Đã Lưu (Gộp Video Review + Quán Ăn) */}
      <button
        type="button"
        className="glass-circle-btn liquid-glass"
        onClick={() => onOpenDrawer('saved-spots')}
        title="Bộ sưu tập Quán & Video đã lưu"
        aria-label="Bộ sưu tập đã lưu"
      >
        <svg
          viewBox="0 0 24 24"
          width="20"
          height="20"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
        </svg>
        {savedCount > 0 && (
          <span className="dock-badge-count">{savedCount}</span>
        )}
        <span className="dock-tooltip">Bộ sưu tập đã lưu</span>
      </button>

      {/* 2. Lịch sử phân tích TikTok */}
      <button
        type="button"
        className="glass-circle-btn liquid-glass"
        onClick={() => onOpenDrawer('history')}
        title="Lịch sử phân tích"
        aria-label="Lịch sử phân tích"
      >
        <svg
          viewBox="0 0 24 24"
          width="20"
          height="20"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="1 4 1 10 7 10" />
          <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        <span className="dock-tooltip">Lịch sử phân tích</span>
      </button>

      {/* 3. Nút Đăng nhập / Tài khoản trực tiếp trên Dock */}
      <button
        type="button"
        className={`glass-circle-btn liquid-glass ${user ? 'is-user-badge' : ''}`}
        onClick={handleAccountClick}
        title={user ? `Tài khoản: ${user.full_name || user.username}` : 'Đăng nhập / Đăng ký'}
        aria-label="Tài khoản người dùng"
      >
        {user ? (
          <span
            style={{
              fontWeight: 700,
              fontSize: '13px',
              color: '#166534',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
              height: '100%',
              borderRadius: '50%',
              background: 'rgba(34, 197, 94, 0.15)',
            }}
          >
            {(user.full_name || user.username || 'U')[0].toUpperCase()}
          </span>
        ) : (
          <svg
            viewBox="0 0 24 24"
            width="20"
            height="20"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        )}
        <span className="dock-tooltip">
          {user ? `👤 ${user.full_name || user.username} (Bấm để đăng xuất)` : '🔑 Đăng nhập / Đăng ký'}
        </span>
      </button>
    </aside>
  )
}

