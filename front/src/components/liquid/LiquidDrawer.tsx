import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { DrawerMode, VideoPlaylistItem } from './types'
import { savedApi, videosApi } from '../../services/api'
import { useAuth } from '../../services/useAuth'
import type {
  AnalysisStatusResponse,
  SavedPlaceResponse,
  SavedVideoResponse,
} from '../../types/api'

interface LiquidDrawerProps {
  mode: DrawerMode | null
  playlist: VideoPlaylistItem[]
  onClose: () => void
  onSelectPlaylistItem: (index: number) => void
  onSelectLocation?: (lat: number, lng: number, name?: string) => void
}

export default function LiquidDrawer({
  mode,
  playlist,
  onClose,
  onSelectPlaylistItem,
  onSelectLocation,
}: LiquidDrawerProps) {
  const isOpen = mode !== null
  const { user, token } = useAuth()
  const navigate = useNavigate()

  const [savedVideos, setSavedVideos] = useState<SavedVideoResponse[]>([])
  const [savedPlaces, setSavedPlaces] = useState<SavedPlaceResponse[]>([])
  const [history, setHistory] = useState<AnalysisStatusResponse[]>([])
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen || !token) {
      setSavedVideos([])
      setSavedPlaces([])
      setHistory([])
      return
    }

    let isSubscribed = true
    setLoading(true)
    setError(null)

    const fetchData = async () => {
      try {
        if (mode === 'liked-videos') {
          const data = await savedApi.getSavedVideos()
          if (isSubscribed) setSavedVideos(data)
        } else if (mode === 'liked-places') {
          const data = await savedApi.getSavedPlaces()
          if (isSubscribed) setSavedPlaces(data)
        } else if (mode === 'history') {
          const data = await videosApi.getAnalysisHistory()
          if (isSubscribed) setHistory(data)
        }
      } catch (err: unknown) {
        if (isSubscribed) {
          setError((err as Error)?.message || 'Không thể tải dữ liệu.')
        }
      } finally {
        if (isSubscribed) setLoading(false)
      }
    }

    fetchData()

    return () => {
      isSubscribed = false
    }
  }, [isOpen, mode, token])

  const getHeaderInfo = () => {
    switch (mode) {
      case 'liked-videos':
        return {
          title: 'Các Video Đã Lưu',
          subtitle: `${savedVideos.length} video review yêu thích trong bộ sưu tập`,
          icon: (
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
              <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
            </svg>
          ),
        }
      case 'liked-places':
        return {
          title: 'Các Quán Ăn Đã Lưu',
          subtitle: `${savedPlaces.length} địa điểm ẩm thực đã lưu trên bản đồ`,
          icon: (
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
          ),
        }
      case 'history':
        return {
          title: 'Lịch Sử Phân Tích AI',
          subtitle: `${history.length} video đã gửi máy chủ AI trích xuất`,
          icon: (
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="1 4 1 10 7 10" />
              <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          ),
        }
      default:
        return { title: '', subtitle: '', icon: null }
    }
  }

  const { title, subtitle, icon } = getHeaderInfo()

  return (
    <>
      <div
        className={`drawer-backdrop ${isOpen ? 'active' : ''}`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside className={`liquid-glass-drawer ${isOpen ? 'active' : ''}`} aria-hidden={!isOpen}>
        <div className="drawer-header">
          <div className="drawer-title-group">
            <div className="drawer-icon-badge">{icon}</div>
            <div>
              <h3 className="drawer-title">{title}</h3>
              <p className="drawer-subtitle">{subtitle}</p>
            </div>
          </div>
          <button
            type="button"
            className="drawer-close-btn liquid-glass"
            onClick={onClose}
            aria-label="Đóng"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="drawer-body">
          {/* Chưa đăng nhập */}
          {!user && (
            <div className="drawer-empty-state" style={{ padding: '32px 16px', textAlign: 'center' }}>
              <div style={{ fontSize: '36px', marginBottom: '12px' }}>🔒</div>
              <h4 style={{ color: '#fff', marginBottom: '8px' }}>Chưa đăng nhập</h4>
              <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '13px', marginBottom: '16px' }}>
                Vui lòng đăng nhập tài khoản để đồng bộ các video, quán ăn yêu thích và xem lịch sử phân tích.
              </p>
              <button
                type="button"
                className="liquid-btn primary"
                onClick={() => {
                  onClose()
                  navigate('/login')
                }}
                style={{
                  padding: '8px 20px',
                  borderRadius: '20px',
                  background: '#00dfa2',
                  color: '#001a14',
                  fontWeight: 600,
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                Đăng nhập ngay
              </button>
            </div>
          )}

          {/* Đang tải */}
          {user && loading && (
            <div style={{ padding: '32px 16px', textAlign: 'center', color: 'rgba(255,255,255,0.7)' }}>
              <div className="spinner" style={{ marginBottom: '8px' }}>⏳ Đang tải dữ liệu từ máy chủ...</div>
            </div>
          )}

          {/* Lỗi */}
          {user && !loading && error && (
            <div style={{ padding: '16px', color: '#ff4d6d', textAlign: 'center' }}>
              {error}
            </div>
          )}

          {/* 1. Danh sách Quán Ăn đã lưu */}
          {user && !loading && mode === 'liked-places' && (
            <>
              {savedPlaces.length === 0 ? (
                <div style={{ padding: '32px 16px', textAlign: 'center', color: 'rgba(255,255,255,0.6)' }}>
                  <div style={{ fontSize: '32px', marginBottom: '8px' }}>📍</div>
                  Chưa có quán ăn nào được lưu. Bấm biểu tượng trái tim trên quán ăn để lưu lại.
                </div>
              ) : (
                savedPlaces.map((sp) => {
                  const place = sp.place
                  return (
                    <div
                      key={sp.saved_id}
                      className="drawer-card liquid-glass"
                      onClick={() => {
                        if (place.latitude && place.longitude && onSelectLocation) {
                          onSelectLocation(place.latitude, place.longitude, place.name)
                        }
                        onClose()
                      }}
                    >
                      <div className="drawer-card-icon">📍</div>
                      <div className="drawer-card-info">
                        <div className="drawer-card-title">{place.name}</div>
                        <div className="drawer-card-desc">{place.address || 'Đà Nẵng'}</div>
                      </div>
                      <span
                        className="drawer-card-badge"
                        style={{ background: 'rgba(0, 223, 162, 0.15)', color: '#00dfa2' }}
                      >
                        {place.category || 'Quán ăn'}
                      </span>
                    </div>
                  )
                })
              )}
            </>
          )}

          {/* 2. Danh sách Video đã lưu */}
          {user && !loading && mode === 'liked-videos' && (
            <>
              {savedVideos.length === 0 ? (
                <div style={{ padding: '32px 16px', textAlign: 'center', color: 'rgba(255,255,255,0.6)' }}>
                  <div style={{ fontSize: '32px', marginBottom: '8px' }}>❤️</div>
                  Chưa có video review nào được lưu vào danh sách yêu thích.
                </div>
              ) : (
                savedVideos.map((sv) => {
                  const v = sv.video
                  const p = sv.place
                  // Tìm index nếu video đang có trong active playlist
                  const existingIdx = playlist.findIndex((item) => item.id === v.platform_video_id || item.id === v.id)
                  return (
                    <div
                      key={sv.saved_id}
                      className="drawer-card liquid-glass"
                      onClick={() => {
                        if (existingIdx !== -1) {
                          onSelectPlaylistItem(existingIdx)
                        } else if (p?.latitude && p?.longitude && onSelectLocation) {
                          onSelectLocation(p.latitude, p.longitude, p.name)
                        }
                        onClose()
                      }}
                    >
                      <div className="drawer-card-icon">🎬</div>
                      <div className="drawer-card-info">
                        <div className="drawer-card-title">{v.title || p?.name || 'Video review ẩm thực'}</div>
                        <div className="drawer-card-desc">
                          {v.author_name ? `@${v.author_name}` : ''} {p?.name ? `• ${p.name}` : ''}
                        </div>
                      </div>
                      <span className="drawer-card-badge">{p?.category || 'Quán ăn'}</span>
                    </div>
                  )
                })
              )}
            </>
          )}

          {/* 3. Lịch sử phân tích AI */}
          {user && !loading && mode === 'history' && (
            <>
              {history.length === 0 ? (
                <div style={{ padding: '32px 16px', textAlign: 'center', color: 'rgba(255,255,255,0.6)' }}>
                  <div style={{ fontSize: '32px', marginBottom: '8px' }}>⚡</div>
                  Chưa có yêu cầu phân tích video nào. Dán liên kết TikTok để bắt đầu trích xuất!
                </div>
              ) : (
                history.map((run) => {
                  const statusColors: Record<string, { bg: string; color: string; label: string }> = {
                    COMPLETED: { bg: 'rgba(0, 223, 162, 0.15)', color: '#00dfa2', label: 'Hoàn tất' },
                    PROCESSING: { bg: 'rgba(255, 193, 7, 0.15)', color: '#ffc107', label: 'Đang xử lý' },
                    PENDING: { bg: 'rgba(13, 202, 240, 0.15)', color: '#0dcaf0', label: 'Hàng đợi' },
                    FAILED: { bg: 'rgba(255, 77, 109, 0.15)', color: '#ff4d6d', label: 'Thất bại' },
                  }
                  const badge = statusColors[run.status] || {
                    bg: 'rgba(255,255,255,0.1)',
                    color: '#fff',
                    label: run.status,
                  }

                  return (
                    <div
                      key={run.id}
                      className="drawer-card liquid-glass"
                      onClick={() => {
                        onClose()
                      }}
                    >
                      <div className="drawer-card-icon">⚡</div>
                      <div className="drawer-card-info">
                        <div className="drawer-card-title" title={run.submitted_url}>
                          {run.submitted_url.slice(0, 40)}...
                        </div>
                        <div className="drawer-card-desc">
                          {new Date(run.created_at).toLocaleString('vi-VN')}
                          {run.error_message && ` • Lỗi: ${run.error_message}`}
                        </div>
                      </div>
                      <span
                        className="drawer-card-badge"
                        style={{ background: badge.bg, color: badge.color }}
                      >
                        {badge.label}
                      </span>
                    </div>
                  )
                })
              )}
            </>
          )}
        </div>
      </aside>
    </>
  )
}
