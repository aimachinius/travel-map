
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import './Login.css'
import './Register.css'
import { authApi, ApiError } from '../services/api'

export default function Register() {
  const navigate = useNavigate()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [agreed, setAgreed] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setError('')

    if (!fullName.trim() || !email.trim() || !password || !confirmPassword) {
      setError('Vui lòng điền đầy đủ thông tin.')
      return
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError('Email không hợp lệ.')
      return
    }

    if (password.length < 8) {
      setError('Mật khẩu phải có ít nhất 8 ký tự.')
      return
    }

    if (password !== confirmPassword) {
      setError('Mật khẩu xác nhận không khớp.')
      return
    }

    if (!agreed) {
      setError('Vui lòng đồng ý với điều khoản sử dụng.')
      return
    }

    setLoading(true)

    try {
      const username =
        email.trim().split('@')[0].replace(/[^a-zA-Z0-9_]/g, '') ||
        `user_${Date.now().toString().slice(-6)}`

      await authApi.register({
        username,
        email: email.trim(),
        password,
        full_name: fullName.trim(),
      })

      // Tự động đăng nhập luôn sau khi đăng ký thành công
      try {
        await authApi.login({
          username_or_email: email.trim(),
          password,
        })
        navigate('/explore')
      } catch {
        navigate('/login')
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        const errorDetail = err.detail
        let msg = err.message
        if (typeof errorDetail === 'string') {
          msg = errorDetail
        } else if (errorDetail && typeof errorDetail === 'object' && 'detail' in errorDetail) {
          msg = String((errorDetail as { detail: unknown }).detail)
        }
        setError(msg || 'Đăng ký không thành công. Email hoặc username có thể đã tồn tại.')
      } else {
        setError('Không thể kết nối đến máy chủ Backend. Vui lòng thử lại.')
      }
    } finally {
      setLoading(false)
    }
  }


  return (
    <main className="login-page register-page">
      {/* Frame bên trái: giữ nguyên thiết kế Food Spot */}
      <section
        className="login-visual"
        aria-label="Khám phá địa điểm ăn uống"
      >
        <Link
          to="/"
          className="login-brand"
          aria-label="Quay về trang chủ Food Spot"
        >
          <img
            className="fs-logo"
            src="/food-spot.svg"
            alt="Food Spot"
          />
        </Link>

        <div className="login-collage">
          <div className="login-photo login-photo-food">
            <img
              src="https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=700&q=85"
              alt="Món ăn hấp dẫn"
            />
            <span className="login-photo-label">
              <span className="login-label-dot" />
              Food review
            </span>
          </div>

          <div className="login-photo login-photo-cafe">
            <img
              src="https://images.unsplash.com/photo-1445116572660-236099ec97a0?auto=format&fit=crop&w=600&q=85"
              alt="Không gian quán cà phê"
            />
          </div>

          <div className="login-phone">
            <div className="login-phone-camera" />

            <div className="login-phone-search">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="10.8" cy="10.8" r="6.8" />
                <path d="m16 16 4.5 4.5" />
              </svg>
              <span>Tìm quán ăn, cà phê...</span>
            </div>

            <div className="login-mini-map">
              <div className="login-map-road login-road-one" />
              <div className="login-map-road login-road-two" />
              <div className="login-map-road login-road-three" />
              <div className="login-map-road login-road-four" />

              <span className="login-map-pin pin-one">
                <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M12 22s8-7.3 8-13A8 8 0 1 0 4 9c0 5.7 8 13 8 13Zm0-10a3 3 0 1 1 0-6 3 3 0 0 1 0 6Z" />
                </svg>
              </span>

              <span className="login-map-pin pin-two">
                <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M12 22s8-7.3 8-13A8 8 0 1 0 4 9c0 5.7 8 13 8 13Zm0-10a3 3 0 1 1 0-6 3 3 0 0 1 0 6Z" />
                </svg>
              </span>

              <span className="login-map-pin pin-three">
                <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M12 22s8-7.3 8-13A8 8 0 1 0 4 9c0 5.7 8 13 8 13Zm0-10a3 3 0 1 1 0-6 3 3 0 0 1 0 6Z" />
                </svg>
              </span>
            </div>

            <div className="login-phone-card">
              <img
                src="https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=500&q=80"
                alt="Món ăn được gợi ý"
              />
              <div className="login-phone-card-info">
                <strong>Quán ngon gần bạn</strong>
                <span>
                  <span className="login-star">★</span> 4.8
                  <span className="login-card-distance">
                    {' '}· Gợi ý địa điểm
                  </span>
                </span>
              </div>
            </div>

            <div className="login-phone-nav">
              <span className="active">⌂</span>
              <span>⌕</span>
              <span>♡</span>
              <span>♙</span>
            </div>
          </div>

          <div className="login-floating-review">
            <span className="login-review-play">▶</span>
            <div>
              <strong>Video review</strong>
              <span>Khám phá món ngon</span>
            </div>
          </div>

          <div className="login-floating-pin" aria-hidden="true">
            <svg viewBox="0 0 40 40" fill="none">
              <path
                d="M20 36S5.5 23.4 5.5 15.8a14.5 14.5 0 1 1 29 0C34.5 23.4 20 36 20 36Z"
                fill="#D9825B"
              />
              <circle cx="20" cy="15.5" r="5" fill="#FFFDF8" />
            </svg>
          </div>
        </div>
      </section>

      {/* Frame bên phải: form đăng ký */}
      <section className="login-form-panel register-form-panel">
        <div className="login-form-wrap register-form-wrap">
          <h1 className="login-title register-title">
            <img
              className="fs-logo login-title-logo"
              src="/food-spot.svg"
              alt=""
            />
            <span>Đăng ký</span>
          </h1>

          <p className="register-description">
            Tham gia Food Spot và khám phá những địa điểm ăn uống thú vị.
          </p>

          <form
            className="login-form register-form"
            onSubmit={handleSubmit}
            noValidate
          >
            <div className="login-field">
              <label htmlFor="register-name">Họ và tên</label>
              <div className="login-input-wrap">
                <svg
                  className="login-input-icon"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
                  <circle cx="12" cy="8" r="4" />
                  <path d="M4 21v-2a8 8 0 0 1 16 0v2Z" />
                </svg>

                <input
                  id="register-name"
                  type="text"
                  placeholder="Nhập họ và tên của bạn"
                  autoComplete="name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </div>
            </div>

            <div className="login-field">
              <label htmlFor="register-email">Email</label>
              <div className="login-input-wrap">
                <svg
                  className="login-input-icon"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
                  <rect x="3" y="5" width="18" height="14" rx="2" />
                  <path d="m4 7 8 6 8-6" />
                </svg>

                <input
                  id="register-email"
                  type="email"
                  placeholder="Nhập email của bạn"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </div>

            <div className="login-field">
              <label htmlFor="register-password">Mật khẩu</label>
              <div className="login-input-wrap">
                <svg
                  className="login-input-icon"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
                  <rect x="4" y="10" width="16" height="11" rx="2" />
                  <path d="M8 10V7a4 4 0 0 1 8 0v3" />
                  <path d="M12 14v3" />
                </svg>

                <input
                  id="register-password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Tạo mật khẩu (ít nhất 8 ký tự)"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />

                <button
                  type="button"
                  className="login-password-toggle"
                  onClick={() => setShowPassword((current) => !current)}
                  aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                >
                  {showPassword ? (
                    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path d="M3 3 21 21" />
                      <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                      <path d="M9.9 5.2A10.8 10.8 0 0 1 12 5c5.5 0 9 7 9 7a16 16 0 0 1-3.2 4.1" />
                      <path d="M6.2 6.2C4.1 7.6 3 12 3 12s3.5 7 9 7a10 10 0 0 0 3-.5" />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path d="M2.5 12s3.5-7 9.5-7 9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7Z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <div className="login-field">
              <label htmlFor="register-confirm-password">
                Xác nhận mật khẩu
              </label>
              <div className="login-input-wrap">
                <svg
                  className="login-input-icon"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
                  <rect x="4" y="10" width="16" height="11" rx="2" />
                  <path d="M8 10V7a4 4 0 0 1 8 0v3" />
                  <path d="m9 15 2 2 4-4" />
                </svg>

                <input
                  id="register-confirm-password"
                  type={showConfirmPassword ? 'text' : 'password'}
                  placeholder="Nhập lại mật khẩu"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />

                <button
                  type="button"
                  className="login-password-toggle"
                  onClick={() =>
                    setShowConfirmPassword((current) => !current)
                  }
                  aria-label={
                    showConfirmPassword
                      ? 'Ẩn mật khẩu xác nhận'
                      : 'Hiện mật khẩu xác nhận'
                  }
                >
                  {showConfirmPassword ? (
                    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path d="M3 3 21 21" />
                      <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                      <path d="M9.9 5.2A10.8 10.8 0 0 1 12 5c5.5 0 9 7 9 7a16 16 0 0 1-3.2 4.1" />
                      <path d="M6.2 6.2C4.1 7.6 3 12 3 12s3.5 7 9 7a10 10 0 0 0 3-.5" />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path d="M2.5 12s3.5-7 9.5-7 9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7Z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <label className="register-terms">
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
              />
              <span>
                Tôi đồng ý với{' '}
                <Link to="/terms">Điều khoản sử dụng</Link>
                {' '}và{' '}
                <Link to="/privacy">Chính sách bảo mật</Link>.
              </span>
            </label>

            {error && (
              <p className="login-error" role="alert">
                {error}
              </p>
            )}

            <button
              type="submit"
              className="login-submit"
              disabled={loading}
            >
              {loading ? 'Đang xử lý...' : 'Tạo tài khoản'}
              {!loading && (
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M5 12h14" />
                  <path d="m13 5 7 7-7 7" />
                </svg>
              )}
            </button>
          </form>

          <div className="login-register">
            <span>Đã có tài khoản?</span>
            <Link to="/login">Đăng nhập ngay</Link>
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M5 12h14" />
              <path d="m13 5 7 7-7 7" />
            </svg>
          </div>
        </div>

        <div className="login-bottom-decoration" aria-hidden="true">
          <span />
          <svg viewBox="0 0 40 40" fill="none">
            <path
              d="M20 36S5.5 23.4 5.5 15.8a14.5 14.5 0 1 1 29 0C34.5 23.4 20 36 20 36Z"
              fill="#829873"
            />
            <circle cx="20" cy="15.5" r="5" fill="#FFFDF8" />
          </svg>
          <span />
        </div>
      </section>
    </main>
  )
}
