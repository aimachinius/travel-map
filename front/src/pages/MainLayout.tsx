
import { useState, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import './MainLayout.css'

const menuItems = [
  { label: 'Explore Map', icon: '⌖', path: '/explore' },
  { label: 'Saved Videos', icon: '♡', path: '/saved-videos' },
  { label: 'Saved Places', icon: '⌑', path: '/saved-places' },
  { label: 'Analysis History', icon: '◷', path: '/history' },
]

type MainLayoutProps = {
  children: ReactNode
  pageTitle: string
}

export default function MainLayout({
  children,
  pageTitle,
}: MainLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  return (
    <div className="explore-page">
      <aside
        className={`explore-sidebar ${sidebarOpen ? 'expanded' : 'collapsed'}`}
        onMouseEnter={() => setSidebarOpen(true)}
        onMouseLeave={() => setSidebarOpen(false)}
      >
        <div className="sidebar-brand">
          <div className="brand-mark">F</div>
          {sidebarOpen && <span className="brand-name">Food Spot</span>}
        </div>

        <button
          type="button"
          className="sidebar-toggle"
          onClick={() => setSidebarOpen((open) => !open)}
          aria-label="Mở hoặc thu gọn menu"
        >
          {sidebarOpen ? '‹' : '☰'}
        </button>

        <nav className="sidebar-nav">
          {menuItems.map((item) => (
            <button
              type="button"
              key={item.path}
              className={`sidebar-item ${
                location.pathname === item.path ? 'active' : ''
              }`}
              onClick={() => navigate(item.path)}
              title={item.label}
            >
              <span className="sidebar-icon">{item.icon}</span>
              {sidebarOpen && <span>{item.label}</span>}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <button
            type="button"
            className={`sidebar-item ${
              location.pathname === '/settings' ? 'active' : ''
            }`}
            onClick={() => navigate('/settings')}
            title="Settings"
          >
            <span className="sidebar-icon">⚙</span>
            {sidebarOpen && <span>Settings</span>}
          </button>

          {user ? (
            <div
              className="sidebar-profile"
              onClick={() => {
                if (window.confirm('Bạn có muốn đăng xuất không?')) {
                  logout()
                  navigate('/login')
                }
              }}
              style={{ cursor: 'pointer' }}
              title="Nhấn để đăng xuất"
            >
              <div className="profile-avatar">
                {user.full_name ? user.full_name.charAt(0).toUpperCase() : user.username.charAt(0).toUpperCase()}
              </div>
              {sidebarOpen && (
                <div className="profile-info">
                  <strong>{user.full_name || user.username}</strong>
                  <span>Đăng xuất</span>
                </div>
              )}
            </div>
          ) : (
            <div
              className="sidebar-profile"
              onClick={() => navigate('/login')}
              style={{ cursor: 'pointer' }}
              title="Đăng nhập"
            >
              <div className="profile-avatar">?</div>
              {sidebarOpen && (
                <div className="profile-info">
                  <strong>Khách</strong>
                  <span style={{ color: '#10b981' }}>Đăng nhập</span>
                </div>
              )}
            </div>
          )}
        </div>
      </aside>

      <main className="explore-main">
        <header className="explore-header">
          <div className="header-brand">
            <img
              src="/food-spot.svg"
              alt="Food Spot logo"
              className="header-logo"
            />
            <div className="header-brand-info">
              <span className="header-brand-name">Food Spot</span>
              <span className="header-slogan">
                Discover places, taste stories.
              </span>
            </div>
          </div>

          <div className="header-page">
            <span className="header-page-icon">⌖</span>
            <h1>{pageTitle}</h1>
          </div>
        </header>

        {children}
      </main>
    </div>
  )
}
