import type { DrawerMode, VideoPlaylistItem } from './types'

interface LiquidDrawerProps {
  mode: DrawerMode | null
  playlist: VideoPlaylistItem[]
  onClose: () => void
  onSelectPlaylistItem: (index: number) => void
}

export default function LiquidDrawer({
  mode,
  playlist,
  onClose,
  onSelectPlaylistItem,
}: LiquidDrawerProps) {
  const isOpen = mode !== null

  const getHeaderInfo = () => {
    switch (mode) {
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

        <div className="drawer-body">
          {playlist.map((item, idx) => {
            if (mode === 'liked-places') {
              return (
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
              )
            }

            if (mode === 'history') {
              return (
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
              )
            }

            // Liked Videos
            return (
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
            )
          })}
        </div>
      </aside>
    </>
  )
}

