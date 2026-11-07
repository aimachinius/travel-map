import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../services/useAuth'
import './UnifiedHeader.css'

export default function UnifiedHeader() {
  const [mobileMenu, setMobileMenu] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  // Đóng mobile menu khi chuyển trang
  useEffect(() => {
    setMobileMenu(false)
  }, [location.pathname])

  const isExplore = location.pathname === '/explore'
  const isHome = location.pathname === '/'

  const handleGoHome = (e: React.MouseEvent) => {
    e.preventDefault()
    setMobileMenu(false)
    if (isHome) {
      const pane = document.querySelector('.pane-home')
      if (pane) pane.scrollTo({ top: 0, behavior: 'smooth' })
    } else {
      navigate('/')
    }
  }

  const handleGoExplore = (e: React.MouseEvent) => {
    e.preventDefault()
    setMobileMenu(false)
    if (!isExplore) {
      navigate('/explore')
    }
  }

  const handleSectionScroll = (e: React.MouseEvent, targetId: string) => {
    e.preventDefault()
    setMobileMenu(false)
    if (isHome) {
      const el = document.getElementById(targetId)
      if (el) el.scrollIntoView({ behavior: 'smooth' })
    } else {
      navigate('/')
      setTimeout(() => {
        const el = document.getElementById(targetId)
        if (el) el.scrollIntoView({ behavior: 'smooth' })
      }, 450)
    }
  }

  const handleLogout = () => {
    logout()
  }

  return (
    <header className="unified-header">
      <div className="unified-header-inner">
        {/* Logo Food Spot dùng chung */}
        <a
          href="/"
          onClick={handleGoHome}
          className="unified-brand-link"
          aria-label="Food Spot — Về Trang chủ"
        >
          <img className="unified-logo-img" src="/food-spot.svg" alt="Food Spot" />
        </a>

        {/* Mobile menu toggle */}
        <button
          type="button"
          className="unified-mobile-btn"
          onClick={() => setMobileMenu(!mobileMenu)}
          aria-label={mobileMenu ? 'Đóng menu' : 'Mở menu'}
        >
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2">
            {mobileMenu ? (
              <>
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </>
            ) : (
              <>
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </>
            )}
          </svg>
        </button>

        {/* Điều hướng chung */}
        <nav className={`unified-nav-links ${mobileMenu ? 'open' : ''}`}>
          <a
            href="/"
            onClick={handleGoHome}
            className={`unified-nav-item ${isHome ? 'is-active' : ''}`}
          >
            Trang chủ
          </a>
          <a
            href="/explore"
            onClick={handleGoExplore}
            className={`unified-nav-item ${isExplore ? 'is-active' : ''}`}
          >
            Bản đồ Review ⌖
          </a>
          <a
            href="#discover"
            onClick={(e) => handleSectionScroll(e, 'discover')}
            className="unified-nav-item"
          >
            Danh sách quán
          </a>
          <a
            href="#features"
            onClick={(e) => handleSectionScroll(e, 'features')}
            className="unified-nav-item"
          >
            Tính năng
          </a>
          <a
            href="#contact"
            onClick={(e) => handleSectionScroll(e, 'contact')}
            className="unified-nav-item"
          >
            Liên hệ
          </a>

          {/* Tài khoản người dùng */}
          {user ? (
            <div className="unified-auth-slot">
              <div className="unified-user-badge">
                <span className="unified-user-avatar">
                  {(user.full_name || user.username || 'U').charAt(0).toUpperCase()}
                </span>
                <span className="unified-user-name">{user.full_name || user.username}</span>
                <button
                  type="button"
                  className="unified-logout-btn"
                  onClick={handleLogout}
                  title="Đăng xuất tài khoản"
                >
                  Đăng xuất
                </button>
              </div>
            </div>
          ) : (
            <div className="unified-auth-slot">
              <a
                href="/login"
                onClick={(e) => {
                  e.preventDefault()
                  setMobileMenu(false)
                  navigate('/login')
                }}
                className="unified-nav-item unified-login-link"
              >
                Đăng nhập
              </a>
            </div>
          )}
        </nav>
      </div>
    </header>
  )
}
