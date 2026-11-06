import { useState, type FormEvent } from 'react'
import type { LocationHub } from './geoUtils'
import { POPULAR_HUBS, RADIUS_OPTIONS } from './geoUtils'

interface ControlsAreaProps {
  inputValue: string
  onInputChange: (val: string) => void
  onSubmit: (url: string) => void
  hasError: boolean
  filterMode: 'trending' | 'nearby'
  onFilterModeChange: (mode: 'trending' | 'nearby') => void
  selectedRadius: number
  onRadiusChange: (radiusKm: number) => void
  currentHub: LocationHub
  onSelectHub: (hub: LocationHub) => void
  onUseCurrentLocation: () => void
  isLocating: boolean
  matchedCount: number
}

export default function ControlsArea({
  inputValue,
  onInputChange,
  onSubmit,
  hasError,
  filterMode,
  onFilterModeChange,
  selectedRadius,
  onRadiusChange,
  currentHub,
  onSelectHub,
  onUseCurrentLocation,
  isLocating,
  matchedCount,
}: ControlsAreaProps) {
  const [pasteNotice, setPasteNotice] = useState(false)
  const [isCollapsed, setIsCollapsed] = useState(false)

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    onSubmit(inputValue)
  }

  const handleClear = () => {
    onInputChange('')
  }

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText()
      if (text) {
        onInputChange(text.trim())
        setPasteNotice(true)
        setTimeout(() => setPasteNotice(false), 2000)
      }
    } catch (err) {
      console.warn('Clipboard read error:', err)
    }
  }

  // Nếu người dùng chọn thu gọn để ngắm trọn bản đồ rộng rãi
  if (isCollapsed) {
    return (
      <section className="controls-area is-collapsed" aria-label="Bảng điều khiển thu gọn">
        <button
          type="button"
          className="controls-collapsed-pill liquid-glass"
          onClick={() => setIsCollapsed(false)}
          title="Mở rộng tìm kiếm & bộ lọc"
          aria-label="Mở rộng bảng điều khiển"
        >
          <span className="collapsed-pill-icon">🔍</span>
          <span className="collapsed-pill-text">Tìm kiếm & Lọc quán</span>
          <span className="collapsed-pill-badge">{matchedCount} quán</span>
          <span className="collapsed-pill-chevron" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="18 15 12 9 6 15" />
            </svg>
          </span>
        </button>
      </section>
    )
  }

  return (
    <section className="controls-area" aria-label="Khu vực điều khiển và khám phá">
      {/* Thanh công cụ Khám phá Thông minh & Bộ lọc Bán kính */}
      <div className="discovery-filter-toolbar liquid-glass">
        {/* Hàng 1: Chuyển đổi chế độ (🔥 Nổi tiếng vs 📍 Quanh vị trí) + Nút Thu gọn */}
        <div className="filter-header-row">
          <div className="filter-mode-pills">
            <button
              type="button"
              className={`mode-pill-btn ${filterMode === 'trending' ? 'active' : ''}`}
              onClick={() => onFilterModeChange('trending')}
              title="Khám phá các video review ẩm thực nổi tiếng"
            >
              <span className="mode-pill-icon">🔥</span>
              <span className="mode-pill-label">Nổi tiếng</span>
            </button>
            <button
              type="button"
              className={`mode-pill-btn ${filterMode === 'nearby' ? 'active' : ''}`}
              onClick={() => onFilterModeChange('nearby')}
              title="Lọc các quán ăn theo bán kính quanh vị trí đang đứng"
            >
              <span className="mode-pill-icon">📍</span>
              <span className="mode-pill-label">Quanh đây</span>
            </button>
          </div>

          <div className="filter-right-tools">
            {/* Badge hiển thị số lượng quán tìm thấy */}
            <div className="matched-spots-badge">
              <span className="spots-pulse" />
              <span className="spots-count">
                {matchedCount} video {filterMode === 'nearby' ? `${selectedRadius}km` : ''}
              </span>
            </div>

            {/* Nút Thu gọn bản điều khiển theo yêu cầu để xem map rộng hơn */}
            <button
              type="button"
              className="controls-collapse-toggle-btn"
              onClick={() => setIsCollapsed(true)}
              title="Thu gọn để xem bản đồ rộng hơn"
              aria-label="Thu gọn"
            >
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="6 9 12 15 18 9" />
              </svg>
              <span>Thu gọn</span>
            </button>
          </div>
        </div>

        {/* Hàng 2: Khi ở chế độ 'Quanh đây' -> Hiện bán kính km & Chọn khu vực mốc / GPS */}
        {filterMode === 'nearby' && (
          <div className="radius-control-panel">
            {/* Lựa chọn tâm vị trí */}
            <div className="hub-selector-strip">
              <span className="strip-label">Vị trí:</span>
              <div className="hub-chips">
                <button
                  type="button"
                  className={`hub-chip ${currentHub.id === 'user-gps' ? 'active' : ''}`}
                  onClick={onUseCurrentLocation}
                  disabled={isLocating}
                  title="Lấy vị trí GPS hiện tại của bạn"
                >
                  <span className="chip-ico">{isLocating ? '⏳' : '📍'}</span>
                  <span>{isLocating ? 'Định vị...' : 'GPS tôi'}</span>
                </button>
                {POPULAR_HUBS.map((hub) => (
                  <button
                    key={hub.id}
                    type="button"
                    className={`hub-chip ${currentHub.id === hub.id ? 'active' : ''}`}
                    onClick={() => onSelectHub(hub)}
                  >
                    <span className="chip-ico">{hub.icon}</span>
                    <span>{hub.name}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Lựa chọn bán kính km */}
            <div className="radius-selector-strip">
              <span className="strip-label">Bán kính:</span>
              <div className="radius-pills">
                {RADIUS_OPTIONS.map((km) => (
                  <button
                    key={km}
                    type="button"
                    className={`radius-pill ${selectedRadius === km ? 'active' : ''}`}
                    onClick={() => onRadiusChange(km)}
                  >
                    {km} km
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Pill Input & Circular Search Button Row */}
      <form className="input-action-group" onSubmit={handleSubmit}>
        <div className={`input-pill-wrapper liquid-glass ${hasError ? 'shake-error' : ''}`}>
          <div className="input-icon-slot">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="link-svg"
              width="18"
              height="18"
            >
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
            </svg>
          </div>

          <input
            type="text"
            className="video-input"
            value={inputValue}
            onChange={(e) => onInputChange(e.target.value)}
            placeholder="Dán đường dẫn video TikTok..."
            autoComplete="off"
            spellCheck="false"
            aria-label="Đường dẫn video TikTok"
          />

          {inputValue.length > 0 && (
            <button
              type="button"
              className="clear-btn"
              onClick={handleClear}
              title="Xóa nội dung"
              aria-label="Xóa nội dung"
            >
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          )}

          <button
            type="button"
            className="paste-btn"
            onClick={handlePaste}
            title={pasteNotice ? 'Đã dán!' : 'Dán từ bộ nhớ tạm'}
            aria-label="Dán liên kết"
          >
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
              <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
            </svg>
          </button>
        </div>

        {/* Circular search button */}
        <button
          type="submit"
          className="search-btn-circle liquid-glass"
          title="Tìm kiếm & Tải Video"
          aria-label="Tìm kiếm"
        >
          <div className="search-icon-wrapper">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              width="18"
              height="18"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </div>
        </button>
      </form>
    </section>
  )
}
