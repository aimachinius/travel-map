import { useMemo, useState } from 'react'
import type { DrawerMode, SavedFoodSpotItem, VideoPlaylistItem } from './types'

export interface SavedPlaceItem {
  id: string
  placeId?: string
  name: string
  address: string
  lat: number
  lng: number
  category: string
  icon: string
  videos: SavedFoodSpotItem[]
}

interface LiquidDrawerProps {
  mode: DrawerMode | null
  playlist: VideoPlaylistItem[]
  savedSpots?: SavedFoodSpotItem[]
  onClose: () => void
  onSelectPlaylistItem: (index: number) => void
  onSelectSavedSpot?: (spot: SavedFoodSpotItem) => void
  onSelectSavedPlace?: (place: SavedPlaceItem) => void
  onUnsaveSpot?: (spotId: string) => void
}

export default function LiquidDrawer({
  mode,
  playlist,
  savedSpots = [],
  onClose,
  onSelectPlaylistItem,
  onSelectSavedSpot,
  onSelectSavedPlace,
  onUnsaveSpot,
}: LiquidDrawerProps) {
  // 2 Option lựa chọn xem trong Bảng lưu: Video đã lưu HOẶC Địa điểm đã lưu (lọc ngược từ video)
  const [viewOption, setViewOption] = useState<'videos' | 'places'>('videos')
  const isOpen = mode !== null

  // Lọc ngược lại từ danh sách video đã lưu ra danh sách các Địa điểm quán ăn duy nhất
  const savedPlacesList = useMemo<SavedPlaceItem[]>(() => {
    const map = new Map<string, SavedPlaceItem>()

    for (const spot of savedSpots) {
      const key =
        spot.placeId ||
        `${spot.lat.toFixed(4)},${spot.lng.toFixed(4)}` ||
        spot.locationName

      const existing = map.get(key)
      if (existing) {
        existing.videos.push(spot)
      } else {
        map.set(key, {
          id: key,
          placeId: spot.placeId,
          name: spot.locationName,
          address: spot.desc || 'Địa điểm ẩm thực',
          lat: spot.lat,
          lng: spot.lng,
          category: spot.category,
          icon: spot.icon || '📍',
          videos: [spot],
        })
      }
    }

    return Array.from(map.values())
  }, [savedSpots])

  const getHeaderInfo = () => {
    switch (mode) {
      case 'saved-spots':
        return {
          title: 'Bộ Sưu Tập Món & Quán',
          subtitle: `${savedSpots.length} video review & ${savedPlacesList.length} địa điểm đã lưu`,
          icon: (
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
          ),
        }
      case 'liked-videos':
        return {
          title: 'Các Video Đã Thích',
          subtitle: `${playlist.length} video thịnh hành đã lưu trong bộ sưu tập`,
          icon: (
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
              <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
            </svg>
          ),
        }
      case 'liked-places':
        return {
          title: 'Các Địa Điểm Đã Thích',
          subtitle: 'Quán ăn & địa danh đã lưu trên bản đồ',
          icon: (
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
          ),
        }
      case 'history':
        return {
          title: 'Lịch Sử Phân Tích',
          subtitle: 'Nhật ký các video TikTok và vị trí đã trích xuất',
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

        {/* 2 Option Lựa Chọn Cho Bảng Lưu: Video Đã Lưu vs Địa Điểm Đã Lưu */}
        {mode === 'saved-spots' && (
          <div className="drawer-filter-pills" role="tablist" aria-label="Chế độ xem bộ sưu tập">
            <button
              type="button"
              role="tab"
              aria-selected={viewOption === 'videos'}
              className={`drawer-pill ${viewOption === 'videos' ? 'active' : ''}`}
              onClick={() => setViewOption('videos')}
            >
              📹 Video đã lưu ({savedSpots.length})
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={viewOption === 'places'}
              className={`drawer-pill ${viewOption === 'places' ? 'active' : ''}`}
              onClick={() => setViewOption('places')}
            >
              📍 Địa điểm đã lưu ({savedPlacesList.length})
            </button>
          </div>
        )}

        <div className="drawer-body">
          {/* ============================================================== */}
          {/* 1. BẢNG LƯU: OPTION 1 - VIDEO ĐÃ LƯU                           */}
          {/* ============================================================== */}
          {mode === 'saved-spots' && viewOption === 'videos' && (
            <>
              {savedSpots.length === 0 ? (
                <div className="drawer-empty-state">
                  <div className="empty-icon">📹</div>
                  <h4 className="empty-title">Chưa có video nào được lưu</h4>
                  <p className="empty-desc">
                    Khi đang xem video review trên bản đồ, bấm biểu tượng <strong>🔖 Lưu video</strong> để gom vào bộ sưu tập này nhé!
                  </p>
                </div>
              ) : (
                savedSpots.map((spot) => (
                  <div
                    key={spot.id}
                    className="drawer-card liquid-glass saved-spot-card"
                    onClick={() => {
                      if (onSelectSavedSpot) {
                        onSelectSavedSpot(spot)
                      }
                      onClose()
                    }}
                  >
                    <div className="drawer-card-icon">{spot.icon || '🍜'}</div>
                    <div className="drawer-card-info">
                      <div className="drawer-card-title">{spot.title}</div>
                      <div className="drawer-card-desc">📍 {spot.locationName}</div>
                      <div className="drawer-card-meta">
                        <span className="drawer-card-badge">{spot.category}</span>
                        {spot.author && (
                          <span className="drawer-author-tag">@{spot.author}</span>
                        )}
                      </div>
                    </div>
                    <div
                      className="drawer-card-actions"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        type="button"
                        className="drawer-action-btn map-btn"
                        title="Xem video và định vị quán trên bản đồ"
                        onClick={() => {
                          if (onSelectSavedSpot) {
                            onSelectSavedSpot(spot)
                          }
                          onClose()
                        }}
                      >
                        ▶️ Xem ngay
                      </button>
                      {onUnsaveSpot && (
                        <button
                          type="button"
                          className="drawer-action-btn unsave-btn"
                          title="Bỏ lưu video"
                          aria-label="Bỏ lưu video"
                          onClick={() => onUnsaveSpot(spot.id)}
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </>
          )}

          {/* ============================================================== */}
          {/* 2. BẢNG LƯU: OPTION 2 - ĐỊA ĐIỂM ĐÃ LƯU (LỌC NGƯỢC TỪ VIDEO)   */}
          {/* ============================================================== */}
          {mode === 'saved-spots' && viewOption === 'places' && (
            <>
              {savedPlacesList.length === 0 ? (
                <div className="drawer-empty-state">
                  <div className="empty-icon">📍</div>
                  <h4 className="empty-title">Chưa có địa điểm nào trong danh sách</h4>
                  <p className="empty-desc">
                    Lưu các video review TikTok thì địa điểm tương ứng sẽ tự động xuất hiện tại đây!
                  </p>
                </div>
              ) : (
                savedPlacesList.map((place) => (
                  <div
                    key={place.id}
                    className="drawer-card liquid-glass saved-spot-card saved-place-grouped-card"
                    onClick={() => {
                      if (onSelectSavedPlace) {
                        onSelectSavedPlace(place)
                      }
                      onClose()
                    }}
                  >
                    <div className="drawer-card-icon">{place.icon}</div>
                    <div className="drawer-card-info">
                      <div className="drawer-card-title">{place.name}</div>
                      <div className="drawer-card-desc">{place.address}</div>
                      <div className="drawer-card-meta">
                        <span className="drawer-card-badge">{place.category}</span>
                        <span className="drawer-video-count-badge">
                          🎬 {place.videos.length} video review
                        </span>
                      </div>
                    </div>
                    <div
                      className="drawer-card-actions"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        type="button"
                        className="drawer-action-btn map-btn"
                        title="Bay tới quán trên bản đồ"
                        onClick={() => {
                          if (onSelectSavedPlace) {
                            onSelectSavedPlace(place)
                          }
                          onClose()
                        }}
                      >
                        🗺️ Bay tới quán
                      </button>
                    </div>
                  </div>
                ))
              )}
            </>
          )}

          {/* ============================================================== */}
          {/* 3. CÁC VIEW KHÁC (BẢO TOÀN LỊCH SỬ PHÂN TÍCH & VIEW PHỤ)       */}
          {/* ============================================================== */}
          {mode === 'liked-places' &&
            playlist.map((item, idx) => (
              <div
                key={item.id}
                className="drawer-card liquid-glass"
                onClick={() => {
                  onSelectPlaylistItem(idx)
                  onClose()
                }}
              >
                <div className="drawer-card-icon">📍</div>
                <div className="drawer-card-info">
                  <div className="drawer-card-title">{item.locationName}</div>
                  <div className="drawer-card-desc">{item.desc}</div>
                </div>
                <span
                  className="drawer-card-badge"
                  style={{ background: 'rgba(0, 223, 162, 0.15)', color: '#00dfa2' }}
                >
                  Bay tới Map
                </span>
              </div>
            ))}

          {mode === 'history' &&
            playlist.map((item, idx) => (
              <div
                key={item.id}
                className="drawer-card liquid-glass"
                onClick={() => {
                  onSelectPlaylistItem(idx)
                  onClose()
                }}
              >
                <div className="drawer-card-icon">⚡</div>
                <div className="drawer-card-info">
                  <div className="drawer-card-title">
                    ID: {item.id} ({item.title})
                  </div>
                  <div className="drawer-card-desc">
                    Tọa độ: [{item.lat.toFixed(4)}, {item.lng.toFixed(4)}] • Trạng thái: 200 OK
                  </div>
                </div>
                <span
                  className="drawer-card-badge"
                  style={{ background: 'rgba(255, 0, 127, 0.15)', color: '#ff007f' }}
                >
                  Đã quét
                </span>
              </div>
            ))}

          {mode === 'liked-videos' &&
            playlist.map((item, idx) => (
              <div
                key={item.id}
                className="drawer-card liquid-glass"
                onClick={() => {
                  onSelectPlaylistItem(idx)
                  onClose()
                }}
              >
                <div className="drawer-card-icon">{item.icon}</div>
                <div className="drawer-card-info">
                  <div className="drawer-card-title">{item.title}</div>
                  <div className="drawer-card-desc">
                    {item.author} • {item.locationName}
                  </div>
                </div>
                <span className="drawer-card-badge">{item.category}</span>
              </div>
            ))}
        </div>
      </aside>
    </>
  )
}

