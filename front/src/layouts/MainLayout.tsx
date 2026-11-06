/**
 * @deprecated LEGACY LAYOUT - ĐÃ NGƯNG SỬ DỤNG
 * Bố cục vỏ app-shell cũ. Đã được thay thế bởi Liquid Glass layout.
 * File này được giữ lại để tham khảo, không xóa.
 */

import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import Icon from '../components/Icon'
import '../styles/shell.css'

export default function MainLayout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  const menuButton = useRef<HTMLButtonElement>(null)
  const main = useRef<HTMLElement>(null)
  const previousPath = useRef(location.pathname)
  useEffect(() => {
    if (previousPath.current !== location.pathname) {
      previousPath.current = location.pathname
      main.current?.focus()
      window.scrollTo(0, 0)
    }
  }, [location.pathname])
  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && menuOpen) {
        setMenuOpen(false)
        menuButton.current?.focus()
      }
    }
    const media = window.matchMedia('(min-width: 761px)')
    const onDesktop = () => { if (media.matches) setMenuOpen(false) }
    window.addEventListener('keydown', escape)
    media.addEventListener('change', onDesktop)
    return () => {
      window.removeEventListener('keydown', escape)
      media.removeEventListener('change', onDesktop)
    }
  }, [menuOpen])
  const close = () => setMenuOpen(false)
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Đến nội dung chính</a>
      <header className="site-header">
        <div className="header-inner">
          <Link className="brand" to="/explore" onClick={close} aria-label="FoodMap — Trang khám phá">
            <span className="brand-mark"><Icon name="pin" /></span>
            <span>FoodMap<span className="brand-dot">.</span></span>
          </Link>
          <button ref={menuButton} className="menu-toggle" type="button" aria-controls="site-navigation" aria-expanded={menuOpen} aria-label={menuOpen ? 'Đóng menu' : 'Mở menu'} onClick={() => setMenuOpen(!menuOpen)}>
            <Icon name={menuOpen ? 'close' : 'menu'} />
          </button>
          <nav id="site-navigation" className={`site-navigation ${menuOpen ? 'is-open' : ''}`} aria-label="Điều hướng chính">
            <div className="nav-pages">
              <NavLink to="/explore" onClick={close}><Icon name="compass" />Khám phá</NavLink>
              <NavLink to="/history" onClick={close}><Icon name="clock" />Lịch sử</NavLink>
            </div>
            <div className="nav-account">
              <NavLink to="/login" onClick={close}>Đăng nhập</NavLink>
              <NavLink className="register-link" to="/register" onClick={close}>Đăng ký<Icon name="arrow" /></NavLink>
            </div>
          </nav>
        </div>
      </header>
      <main id="main-content" ref={main} tabIndex={-1} className="main-content"><Outlet /></main>
      <footer className="site-footer"><div className="footer-inner"><span><strong>FoodMap.</strong> Một chiếc video, một điểm đến.</span><span>Food review & bản đồ ↗</span></div></footer>
    </div>
  )
}
