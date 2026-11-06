import type { DrawerMode } from './types'

interface LeftFloatingDockProps {
  onOpenDrawer: (mode: DrawerMode) => void
}

export default function LeftFloatingDock({ onOpenDrawer }: LeftFloatingDockProps) {
  return (
    <aside className="left-floating-dock" aria-label="Cụm phím tác vụ nhanh">
      {/* 1. Liked Videos */}
      <button
        type="button"
        className="glass-circle-btn liquid-glass"
        onClick={() => onOpenDrawer('liked-videos')}
        title="Các video đã thích"
        aria-label="Video yêu thích"
      >
        <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
          <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
        </svg>
        <span className="dock-tooltip">Video đã thích</span>
      </button>

      {/* 2. Liked Places */}
      <button
        type="button"
        className="glass-circle-btn liquid-glass"
        onClick={() => onOpenDrawer('liked-places')}
        title="Các địa điểm đã thích"
        aria-label="Địa điểm yêu thích"
      >
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
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
          <circle cx="12" cy="10" r="3" />
        </svg>
        <span className="dock-tooltip">Địa điểm đã lưu</span>
      </button>

      {/* 3. Analysis History */}
      <button
        type="button"
        className="glass-circle-btn liquid-glass"
        onClick={() => onOpenDrawer('history')}
        title="Lịch sử phân tích"
        aria-label="Lịch sử phân tích"
      >
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
          <polyline points="1 4 1 10 7 10" />
          <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        <span className="dock-tooltip">Lịch sử phân tích</span>
      </button>
    </aside>
  )
}

