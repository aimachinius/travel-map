import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import UnifiedHeader from '../components/layout/UnifiedHeader'
import FoodSpotLanding from '../pages/FoodSpotLanding'
import Explore from '../pages/Explore'
import './RootLayout.css'

export default function RootLayout() {
  const location = useLocation()
  const isExplore = location.pathname === '/explore' || location.pathname === '/liquid'
  const isFirstMount = useRef(true)
  const [enableTransition, setEnableTransition] = useState(false)

  useEffect(() => {
    // Bật hiệu ứng lướt mượt sau khi render xong lần đầu tiên
    const timer = setTimeout(() => {
      setEnableTransition(true)
      isFirstMount.current = false
    }, 60)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="unified-app-shell">
      {/* 1. Thanh Header dùng chung cố định 100% không chuyển động */}
      <UnifiedHeader />

      {/* 2. Khung Viewport bên dưới Header */}
      <div className="dual-track-viewport" id="unified-main-content">
        <div
          className={`dual-track-slider ${isExplore ? 'at-explore' : 'at-home'} ${
            enableTransition ? 'has-transition' : ''
          }`}
        >
          {/* Surface 1: Trang chủ */}
          <div
            className={`dual-track-pane pane-home ${!isExplore ? 'is-active' : ''}`}
            aria-hidden={isExplore}
          >
            <FoodSpotLanding />
          </div>

          {/* Surface 2: Khám phá */}
          <div
            className={`dual-track-pane pane-explore ${isExplore ? 'is-active' : ''}`}
            aria-hidden={!isExplore}
          >
            <Explore isActive={isExplore} />
          </div>
        </div>
      </div>
    </div>
  )
}
