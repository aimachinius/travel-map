import { useState } from 'react'
import { Link } from 'react-router-dom'
import { getSessionUser, logoutUser, type MockUser } from '../../mocks/mockAuth'

interface LiquidHeaderProps {
  onNavigateHome?: () => void
}

export default function LiquidHeader({ onNavigateHome }: LiquidHeaderProps) {
  const [user, setUser] = useState<Omit<MockUser, 'password'> | null>(() => getSessionUser())
  const [mobileMenu, setMobileMenu] = useState(false)

  const handleHomeClick = (e: React.MouseEvent) => {
    if (onNavigateHome) {
      e.preventDefault()
      onNavigateHome()
    }
  }

  const handleLogout = () => {
    logoutUser()
    setUser(null)
  }

  return (
    <header className="explore-unified-header">
      <div className="explore-nav-container">
        {/* 1. Logo Food Spot đồng bộ với Trang chủ */}
        <Link
          to="/"
          className="explore-logo-link"
          onClick={handleHomeClick}
          aria-label="Food Spot — Về Trang chủ"
        >
          <img className="explore-logo-img" src="/food-spot.svg" alt="Food Spot" />
        </Link>

        {/* Mobile menu toggle */}
        <button
          type="button"
          className="explore-mobile-menu-btn"
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

        {/* 2. Menu Điều hướng đồng bộ 100% với Trang chủ */}
        <nav className={`explore-nav-links ${mobileMenu ? 'open' : ''}`}>
          <Link to="/" onClick={handleHomeClick} className="explore-nav-item">
            Trang chủ
          </Link>
          <Link to="/explore" className="explore-nav-item is-active">
            Bản đồ Review ⌖
          </Link>
          <Link to="/" onClick={handleHomeClick} className="explore-nav-item">
            Danh sách quán
          </Link>
          <Link to="/" onClick={handleHomeClick} className="explore-nav-item">
            Tính năng
          </Link>
          <Link to="/" onClick={handleHomeClick} className="explore-nav-item">
            Liên hệ
          </Link>

          {/* 3. Tài khoản người dùng: Nếu đã đăng nhập thì hiện, nếu chưa thì KHÔNG HIỆN */}
          {user && (
            <div className="explore-auth-slot">
              <div className="explore-user-badge">
                <span className="explore-user-avatar">
                  {user.fullName ? user.fullName.charAt(0).toUpperCase() : 'U'}
                </span>
                <span className="explore-user-name">{user.fullName}</span>
                <button
                  type="button"
                  className="explore-logout-link"
                  onClick={handleLogout}
                  title="Đăng xuất tài khoản"
                >
                  Đăng xuất
                </button>
              </div>
            </div>
          )}
        </nav>
      </div>
    </header>
  )
}
