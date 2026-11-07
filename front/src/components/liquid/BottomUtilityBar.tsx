import { useFpsMonitor } from './hooks/useFpsMonitor'

interface BottomUtilityBarProps {
  tileStyle: 'dark' | 'standard'
  onToggleTileStyle: () => void
}

export default function BottomUtilityBar({
  tileStyle,
  onToggleTileStyle,
}: BottomUtilityBarProps) {
  const { fps, status } = useFpsMonitor()

  const getFpsColor = () => {
    if (status === 'smooth') return '#3b5335'
    if (status === 'medium') return '#d97706'
    return '#dc2626'
  }

  return (
    <div className="bottom-utility-dock" aria-label="Công cụ bản đồ phía dưới">
      {/* Nút chuyển Bản đồ Sáng / Tối */}
      <button
        type="button"
        className="bottom-util-btn liquid-glass"
        onClick={onToggleTileStyle}
        title="Bấm để đổi chế độ Bản đồ Sáng (Voyager) / Tối (Dark Matter)"
      >
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
          {tileStyle === 'dark' ? (
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
          ) : (
            <>
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </>
          )}
        </svg>
        <span>{tileStyle === 'dark' ? 'Bản đồ Tối' : 'Bản đồ Sáng'}</span>
      </button>

      {/* Bộ đo FPS thời gian thực */}
      <div className="bottom-util-fps liquid-glass" title="Tốc độ khung hình mượt mà thực tế">
        <span className="fps-dot" style={{ backgroundColor: getFpsColor() }} />
        <span style={{ fontWeight: 600 }}>{fps} FPS</span>
      </div>
    </div>
  )
}

