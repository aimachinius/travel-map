import { useState } from 'react'
import type { RoutePoint, RouteResult, RouteVehicle } from './routingService'
import type { LandmarkPreset } from './geoUtils'

interface LiquidRouteCardProps {
  routeData: RouteResult | null
  isLoading: boolean
  error: string | null
  origin: RoutePoint
  destination: RoutePoint
  vehicle: RouteVehicle
  onChangeVehicle: (v: RouteVehicle) => void
  landmarks: LandmarkPreset[]
  onSelectLandmark: (lm: LandmarkPreset) => void
  onResetHubOrigin: () => void
  onClose: () => void
}

export default function LiquidRouteCard({
  routeData,
  isLoading,
  error,
  origin,
  destination,
  vehicle,
  onChangeVehicle,
  landmarks = [],
  onSelectLandmark,
  onResetHubOrigin,
  onClose,
}: LiquidRouteCardProps) {
  const [showSteps, setShowSteps] = useState<boolean>(false)

  // Link điều hướng trực tiếp bằng Google Maps
  const travelMode =
    vehicle === 'foot' ? 'walking' : vehicle === 'motorcycle' ? 'two-wheeler' : 'driving'
  const gmapsNavUrl = `https://www.google.com/maps/dir/?api=1&origin=${origin.lat},${origin.lng}&destination=${destination.lat},${destination.lng}&travelmode=${travelMode}`

  const currentEtaMinutes =
    vehicle === 'motorcycle'
      ? routeData?.estimates.motorcycleMinutes
      : vehicle === 'car'
        ? routeData?.estimates.carMinutes
        : routeData?.estimates.footMinutes

  return (
    <div className="liquid-route-card-container liquid-glass">
      {/* Header card */}
      <div className="route-card-header">
        <div className="route-card-title-group">
          <span className="route-card-icon">🧭</span>
          <div>
            <span className="route-card-label">CHỈ ĐƯỜNG ĐẾN QUÁN</span>
            <h4 className="route-card-dest-name">{destination.name || 'Quán ăn'}</h4>
          </div>
        </div>
        <button
          type="button"
          className="route-card-close-btn"
          onClick={onClose}
          aria-label="Đóng chỉ đường"
        >
          ✕
        </button>
      </div>

      {/* Khối Điểm xuất phát rõ ràng, cho phép chọn tùy thích */}
      <div className="route-origin-card-box">
        <div className="route-origin-row-main">
          <span className="route-origin-pin-icon">🚩</span>
          <div className="route-origin-info">
            <span className="route-origin-sublabel">ĐIỂM XUẤT PHÁT:</span>
            <strong className="route-origin-name">{origin.name || 'Vị trí của bạn'}</strong>
          </div>
          <button
            type="button"
            className="route-origin-reset-btn"
            onClick={onResetHubOrigin}
            title="Đưa về tâm trung tâm thành phố"
          >
            🏛️ Về trung tâm
          </button>
        </div>

        {/* Hướng dẫn thao tác trực tiếp trên bản đồ */}
        <div className="route-origin-hint-note">
          <span>💡 <strong>Tự chọn điểm:</strong> Bấm vào bất kỳ đâu trên bản đồ hoặc kéo icon 🧭 để đặt điểm đi tùy thích.</span>
        </div>

        {/* Các gợi ý điểm xuất phát nhanh quen thuộc */}
        {landmarks.length > 0 && (
          <div className="route-landmarks-pills">
            <span className="landmarks-pills-label">Điểm đi nhanh:</span>
            <div className="landmarks-pills-list">
              {landmarks.map((lm) => {
                const isSelected = origin.name === lm.name
                return (
                  <button
                    key={lm.id}
                    type="button"
                    className={`landmark-pill-btn ${isSelected ? 'is-selected' : ''}`}
                    onClick={() => onSelectLandmark(lm)}
                  >
                    <span>{lm.icon} {lm.name}</span>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* 3 Tabs Phương tiện du lịch */}
      <div className="route-vehicle-tabs">
        <button
          type="button"
          className={`vehicle-tab-btn ${vehicle === 'motorcycle' ? 'is-active' : ''}`}
          onClick={() => onChangeVehicle('motorcycle')}
        >
          <span className="v-icon">🛵</span>
          <div className="v-info">
            <span className="v-name">Xe máy</span>
            <span className="v-eta">
              {routeData ? `${routeData.estimates.motorcycleMinutes}p` : '...'}
            </span>
          </div>
        </button>

        <button
          type="button"
          className={`vehicle-tab-btn ${vehicle === 'car' ? 'is-active' : ''}`}
          onClick={() => onChangeVehicle('car')}
        >
          <span className="v-icon">🚕</span>
          <div className="v-info">
            <span className="v-name">Taxi / Ô tô</span>
            <span className="v-eta">
              {routeData ? `${routeData.estimates.carMinutes}p` : '...'}
            </span>
          </div>
        </button>

        <button
          type="button"
          className={`vehicle-tab-btn ${vehicle === 'foot' ? 'is-active' : ''}`}
          onClick={() => onChangeVehicle('foot')}
        >
          <span className="v-icon">🚶‍♀️</span>
          <div className="v-info">
            <span className="v-name">Đi bộ</span>
            <span className="v-eta">
              {routeData ? `${routeData.estimates.footMinutes}p` : '...'}
            </span>
          </div>
        </button>
      </div>

      {/* Trạng thái Loading hoặc Lỗi */}
      {isLoading && (
        <div className="route-status-box is-loading">
          <span className="route-spinner">🌀</span>
          <span>Đang tính lộ trình OSRM nhanh nhất...</span>
        </div>
      )}

      {error && !isLoading && (
        <div className="route-status-box is-error">
          <span>⚠️ {error}</span>
        </div>
      )}

      {/* Tóm tắt lộ trình */}
      {routeData && !isLoading && (
        <div className="route-summary-section">
          <div className="route-metrics-row">
            <div className="metric-pill is-distance">
              <span className="m-val">{routeData.distanceKm} km</span>
              <span className="m-sub">Mặt đường thực tế</span>
            </div>
            <div className="metric-pill is-time">
              <span className="m-val">~{currentEtaMinutes} phút</span>
              <span className="m-sub">Thời gian dự kiến</span>
            </div>
          </div>

          <div className="route-via-text">
            <span>🛣️ {routeData.summaryStreet}</span>
          </div>

          {/* Nút xem chi tiết từng ngã rẽ */}
          {routeData.steps.length > 0 && (
            <button
              type="button"
              className="route-toggle-steps-btn"
              onClick={() => setShowSteps(!showSteps)}
            >
              <span>{showSteps ? '▲ Thu gọn hướng dẫn' : `📋 Xem ${routeData.steps.length} ngã rẽ chi tiết ▼`}</span>
            </button>
          )}

          {/* Danh sách ngã rẽ cuộn mượt */}
          {showSteps && (
            <div className="route-steps-scrollable">
              {routeData.steps.map((step, idx) => (
                <div key={idx} className="route-step-item">
                  <span className="step-icon">{step.icon}</span>
                  <div className="step-body">
                    <p className="step-instruction">{step.instruction}</p>
                    {step.distanceMeters > 0 && (
                      <span className="step-distance">({step.distanceMeters} m)</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Nút mở Google Maps điều hướng */}
          <a
            href={gmapsNavUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="route-gmaps-nav-btn"
          >
            <span>🚀 Mở Google Maps để nổ máy đi</span>
          </a>
        </div>
      )}
    </div>
  )
}
