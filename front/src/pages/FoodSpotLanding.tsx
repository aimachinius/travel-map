import { useEffect, useState, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Icon from '../components/Icon'
import 'leaflet/dist/leaflet.css'
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet'
import { HOT_WEEKLY_SPOTS, type HotFoodSpot } from '../components/liquid/mockData'
import CloudTransitionOverlay from '../components/transition/CloudTransitionOverlay'
import './FoodSpotLanding.css'
import '../styles/swoosh-transition.css'

const CATEGORY_ITEMS = [
  { value: 'Tất cả', label: 'Tất cả món ngon', icon: '🍽️' },
  { value: 'Ăn Vặt & Đường Phố', label: 'Ăn Vặt & Đường Phố', icon: '🍢' },
  { value: 'Món Việt & Phở', label: 'Món Việt & Phở', icon: '🍜' },
  { value: 'Hải Sản Tươi Sống', label: 'Hải Sản Tươi Sống', icon: '🦀' },
  { value: 'Món Nhật Bản', label: 'Món Nhật Bản', icon: '🍣' },
  { value: 'Healthy & Eatclean', label: 'Healthy & Eatclean', icon: '🥗' },
]

function MapFocus({ lat, lng }: { lat: number; lng: number }) {
  const map = useMap()

  useEffect(() => {
    map.flyTo([lat, lng], 14, { duration: 0.75 })
  }, [map, lat, lng])

  return null
}

export default function FoodSpotLanding() {
  const [category, setCategory] = useState<string>('Tất cả')
  const [isCatDropdownOpen, setIsCatDropdownOpen] = useState<boolean>(false)
  const catDropdownRef = useRef<HTMLDivElement>(null)
  const [selectedId, setSelectedId] = useState<string>(HOT_WEEKLY_SPOTS[0].id)
  const [isCloudActive, setIsCloudActive] = useState<boolean>(false)
  const [targetDestination, setTargetDestination] = useState<string>('')
  const [showMapHint, setShowMapHint] = useState<boolean>(true)

  const navigate = useNavigate()

  useEffect(() => {
    document.title = 'Food Spot — Món Hot Trong Tuần & Bản Đồ Review'
  }, [])

  // Dòng nhắc nhở trên minimap chỉ hiện nhẹ vài giây (3.5s) rồi tự động tắt, không hiện vĩnh viễn
  useEffect(() => {
    const hintTimer = setTimeout(() => {
      setShowMapHint(false)
    }, 3500)
    return () => clearTimeout(hintTimer)
  }, [])

  // Đóng dropdown thể loại khi click ra ngoài
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (catDropdownRef.current && !catDropdownRef.current.contains(e.target as Node)) {
        setIsCatDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const visible = HOT_WEEKLY_SPOTS.filter(
    (spot) => category === 'Tất cả' || spot.type === category,
  )

  const selectedSpot =
    visible.find((s) => s.id === selectedId) || visible[0] || HOT_WEEKLY_SPOTS[0]

  const chooseCategory = (value: string) => {
    setCategory(value)
    const firstMatch = HOT_WEEKLY_SPOTS.find(
      (spot) => value === 'Tất cả' || spot.type === value,
    )
    if (firstMatch) {
      setSelectedId(firstMatch.id)
    }
  }

  const pendingSpotRef = useRef<HotFoodSpot | null>(null)
  const transitionSeqRef = useRef<number>(1)

  // Chuyển sang Bản đồ Review kèm hiệu ứng mây bay xuyên màn hình
  const handlePlayReview = (spot: HotFoodSpot) => {
    pendingSpotRef.current = spot
    transitionSeqRef.current += 1
    setTargetDestination(`${spot.dishName} (${spot.name})`)
    setIsCloudActive(true)
  }

  // Khi mây đã phủ kín hoàn toàn màn hình: chuyển trang sang Bản đồ Review
  const handleCloudCovered = () => {
    const spot = pendingSpotRef.current
    if (spot) {
      navigate(`/explore?vid=${spot.videoId}`, {
        state: {
          targetVideoId: spot.videoId,
          lat: spot.lat,
          lng: spot.lng,
          fromCloudTransition: true,
          transitionTimestamp: transitionSeqRef.current,
        },
      })
    }
  }

  // Khi mây đã dạt ra 2 bên hoàn tất: đóng lớp overlay mây
  const handleCloudRevealed = () => {
    setIsCloudActive(false)
    pendingSpotRef.current = null
  }

  const handleGoToExplore = (e: React.MouseEvent) => {
    e.preventDefault()
    handlePlayReview(selectedSpot)
  }

  return (
    <div className="fs-page">
      {/* Hiệu ứng chuyển cảnh Mây phủ kín màn hình kéo vào từ 2 bên */}
      <CloudTransitionOverlay
        isActive={isCloudActive}
        destinationName={targetDestination}
        onCovered={handleCloudCovered}
        onRevealed={handleCloudRevealed}
      />

      <main id="fs-main">
          {/* Phần Hero */}
          <section className="fs-hero fs-container">
            <div className="fs-hero-copy">
              <span className="fs-eyebrow">
                <span /> TỪ MÀN HÌNH ĐẾN ĐIỂM HẸN
              </span>
              <h1>
                Xem review.
                <br />
                Tìm quán ngon.
                <br />
                <em>Đi thôi!</em>
              </h1>
              <p>
                Đừng để quán ngon chỉ nằm trong video đã lưu. Cùng Food Spot khám phá địa điểm ăn uống
                từ những review bạn yêu thích.
              </p>
              <div className="fs-hero-actions">
                <Link className="fs-button" to="/explore" onClick={handleGoToExplore}>
                  Khám phá ngay <Icon name="arrow" />
                </Link>
                <a className="fs-text-link" href="#features">
                  Tìm hiểu tính năng ↗
                </a>
              </div>
              <div className="fs-hero-note">
                <span>⌖</span> Một bản đồ, thêm nhiều trải nghiệm ngon.
              </div>
            </div>
            <div className="fs-hero-visual">
              <div className="fs-photo">
                <img
                  src="https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1000&q=85"
                  alt="Bàn ăn với nhiều món ăn đầy màu sắc"
                />
                <span className="fs-photo-tag">Ăn ngon, đi cùng nhau.</span>
              </div>
              <div className="fs-orbit">
                ĂN GÌ
                <br />
                <b>HÔM NAY?</b>
                <span>↙</span>
              </div>
              <div
                className="fs-floating"
                onClick={handleGoToExplore}
                style={{ cursor: 'pointer' }}
                title="Bấm để bay vào Bản đồ Review ngay"
              >
                <span className="fs-floating-icon">
                  <Icon name="pin" />
                </span>
                <div>
                  <small>ĐIỂM HẸN TIẾP THEO</small>
                  <strong>Quán ngon trong chiếc review ấy</strong>
                  <span>Từ cảm hứng đến một nơi để ghé.</span>
                </div>
                <span>↗</span>
              </div>
              <span className="fs-spark">✳</span>
            </div>
          </section>

        {/* Phần Bản đồ và danh sách Món Hot Trong Tuần */}
        <section id="discover" className="fs-discover">
          <div className="fs-container">
            <div className="fs-section-head">
              <div>
                <span className="fs-eyebrow">🔥 XU HƯỚNG ẨM THỰC TUẦN NÀY</span>
                <h2>Món Hot Trong Tuần — Ăn là dính!</h2>
                <p>
                  Khám phá các tọa độ quán ăn & món ngon đang viral trên TikTok.
                  Chọn món để xem vị trí, nhấn xem review để bay xuyên mây đến video review chi tiết!
                </p>
              </div>
            </div>

            <div className="fs-demo">
              {/* CỘT 1: Danh sách món hot trong tuần (thu gọn) */}
              <div className="fs-results">
                <div className="fs-demo-title">
                  <div className="fs-title-group">
                    <span className="fs-title-badge">HOT TUẦN NÀY</span>
                    <h3>Món hot đang viral</h3>
                  </div>
                  <Icon name="compass" />
                </div>

                <div className="fs-category-dropdown-container" ref={catDropdownRef}>
                  <button
                    type="button"
                    className={`fs-cat-dropdown-trigger ${isCatDropdownOpen ? 'is-active' : ''}`}
                    onClick={() => setIsCatDropdownOpen(!isCatDropdownOpen)}
                    aria-expanded={isCatDropdownOpen}
                    aria-label="Chọn thể loại món ăn"
                  >
                    <span className="fs-cat-active-icon">
                      {CATEGORY_ITEMS.find((c) => c.value === category)?.icon || '🍽️'}
                    </span>
                    <span className="fs-cat-active-label">
                      {CATEGORY_ITEMS.find((c) => c.value === category)?.label || category}
                    </span>
                    <span className={`fs-cat-arrow-icon ${isCatDropdownOpen ? 'is-flipped' : ''}`}>
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <polyline points="6 9 12 15 18 9" />
                      </svg>
                    </span>
                  </button>

                  {isCatDropdownOpen && (
                    <div className="fs-cat-dropdown-menu">
                      {CATEGORY_ITEMS.map((item) => {
                        const isSelected = category === item.value
                        return (
                          <button
                            key={item.value}
                            type="button"
                            className={`fs-cat-menu-item ${isSelected ? 'is-selected' : ''}`}
                            onClick={() => {
                              chooseCategory(item.value)
                              setIsCatDropdownOpen(false)
                            }}
                          >
                            <span className="fs-menu-item-emoji">{item.icon}</span>
                            <span className="fs-menu-item-text">{item.label}</span>
                            {isSelected && <span className="fs-menu-item-checkmark">✓</span>}
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>

                <div className="fs-spot-list">
                  {visible.map((spot) => {
                    const isSelected = selectedSpot.id === spot.id
                    return (
                      <button
                        className={`fs-spot ${isSelected ? 'selected' : ''}`}
                        key={spot.id}
                        type="button"
                        onClick={() => setSelectedId(spot.id)}
                        aria-pressed={isSelected}
                      >
                        <div className="fs-spot-thumb-wrap">
                          <img
                            src={`https://images.unsplash.com/${spot.image}?auto=format&fit=crop&w=160&q=80`}
                            alt={spot.dishName}
                          />
                          <span className="fs-spot-icon-overlay">{spot.icon}</span>
                        </div>
                        <div className="fs-spot-info">
                          <div className="fs-spot-top-line">
                            <small>{spot.type}</small>
                            {spot.badge && (
                              <span className="fs-spot-mini-badge">{spot.badge}</span>
                            )}
                          </div>
                          <strong>{spot.dishName}</strong>
                          <span className="fs-spot-place-name">📍 {spot.name}</span>
                          <span className="fs-spot-price-tag">{spot.price}</span>
                        </div>
                        <span className="fs-spot-arrow">↗</span>
                      </button>
                    )
                  })}
                </div>

                <p className="fs-demo-note">Chọn hoặc rê chuột vào món để xem vị trí & mô tả chi tiết.</p>
              </div>

              {/* CỘT 2: KHUNG BẢN ĐỒ MINIMAP KÉO QUA GIỮA */}
              <div className="fs-map" aria-label="Bản đồ tọa độ quán hot">
                <MapContainer
                  center={[selectedSpot.lat, selectedSpot.lng]}
                  zoom={13}
                  maxZoom={20}
                  scrollWheelZoom={true}
                  className="fs-leaflet-map"
                >
                  <TileLayer
                    attribution="&copy; OpenStreetMap contributors &copy; CARTO"
                    url={`https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=${import.meta.env.VITE_CARTO_API_KEY}`}
                    maxNativeZoom={18}
                    maxZoom={20}
                  />

                  <MapFocus lat={selectedSpot.lat} lng={selectedSpot.lng} />

                  {visible.map((spot) => {
                    const isSelected = selectedSpot.id === spot.id
                    return (
                      <CircleMarker
                        key={spot.id}
                        center={[spot.lat, spot.lng]}
                        radius={isSelected ? 13 : 9}
                        pathOptions={{
                          color: '#ffffff',
                          weight: isSelected ? 3.5 : 2,
                          fillColor: isSelected ? '#1b4332' : '#e65100',
                          fillOpacity: 1,
                        }}
                        eventHandlers={{
                          click: () => {
                            setSelectedId(spot.id)
                            setShowMapHint(false)
                          },
                        }}
                      >
                        <Popup>
                          <div className="fs-map-popup-card">
                            <span className="fs-popup-badge">{spot.badge || spot.type}</span>
                            <strong>{spot.dishName}</strong>
                            <p className="fs-popup-place">📍 {spot.name}</p>
                            <span className="fs-popup-price">{spot.price}</span>
                            <button
                              type="button"
                              className="fs-popup-play-btn"
                              onClick={() => handlePlayReview(spot)}
                            >
                              ▶ Xem review ngay
                            </button>
                          </div>
                        </Popup>
                      </CircleMarker>
                    )
                  })}
                </MapContainer>

                <div className={`fs-map-floating-hint ${!showMapHint ? 'fade-out' : ''}`}>
                  <span>🗺️ Lướt bản đồ hoặc bấm marker để chọn quán</span>
                </div>
              </div>

              {/* CỘT 3: KHỐI CHI TIẾT QUÁN & MÓN ĂN TRƯỢT TỪ PHẢI SANG TRÁI */}
              <div className="fs-spot-detail-panel" key={selectedSpot.id}>
                <div className="fs-detail-card">
                  <div className="fs-detail-image-wrap">
                    <img
                      src={`https://images.unsplash.com/${selectedSpot.image}?auto=format&fit=crop&w=700&q=85`}
                      alt={selectedSpot.dishName}
                      className="fs-detail-cover"
                    />
                    <div className="fs-detail-image-overlay" />
                    {selectedSpot.badge && (
                      <span className="fs-detail-hot-badge">{selectedSpot.badge}</span>
                    )}
                    <span className="fs-detail-emoji-tag">{selectedSpot.icon}</span>
                  </div>

                  <div className="fs-detail-body">
                    <div className="fs-detail-meta-row">
                      <span className="fs-detail-cat-pill">{selectedSpot.type}</span>
                      <span className="fs-detail-price-pill">{selectedSpot.price}</span>
                    </div>

                    <h4 className="fs-detail-dish-title">{selectedSpot.dishName}</h4>

                    <div className="fs-detail-location-box">
                      <span className="fs-loc-pin">📍</span>
                      <div>
                        <strong>{selectedSpot.name}</strong>
                        <p>{selectedSpot.address}</p>
                      </div>
                    </div>

                    <div className="fs-detail-quote-box">
                      <span className="quote-mark">“</span>
                      <p>{selectedSpot.description}</p>
                    </div>

                    <div className="fs-detail-author-row">
                      <span className="fs-author-label">Reviewer TikTok:</span>
                      <span className="fs-author-handle">{selectedSpot.author}</span>
                    </div>

                    {/* Nút hành động chính: Nhấn và phát review ngay lập tức */}
                    <button
                      type="button"
                      className="fs-play-review-btn"
                      onClick={() => handlePlayReview(selectedSpot)}
                      title="Nhảy đến bản đồ review và phát video TikTok tương ứng"
                    >
                      <span className="btn-play-icon">▶</span>
                      <div className="btn-play-text">
                        <strong>Xem video review quán</strong>
                        <small>Bay xuyên mây đến bản đồ review ↗</small>
                      </div>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Phần Tính năng */}
        <section id="features" className="fs-features">
          <div className="fs-container">
            <div className="fs-section-head">
              <div>
                <span className="fs-eyebrow">TẠI SAO CHỌN CHÚNG MÌNH ?</span>
                <h2>Tính năng nổi bật của Food Spot</h2>
              </div>
              <p>Trải nghiệm mượt mà giúp bạn không bỏ lỡ bất kỳ quán ngon nào.</p>
            </div>
            <div className="fs-features-grid">
              <div className="fs-feature-card">
                <div className="fs-feature-icon">📍</div>
                <h3>Bản đồ trực quan</h3>
                <p>
                  Xác định chính xác vị trí quán ăn ngay từ video review yêu thích mà không phải tìm
                  kiếm thủ công.
                </p>
              </div>
              <div className="fs-feature-card">
                <div className="fs-feature-icon">⚡</div>
                <h3>Lọc nhanh khẩu vị</h3>
                <p>
                  Dễ dàng phân loại theo món Việt, quán cà phê hay các điểm ăn uống phù hợp với nhu
                  cầu trong ngày.
                </p>
              </div>
              <div className="fs-feature-card">
                <div className="fs-feature-icon">🤝</div>
                <h3>Kết nối điểm hẹn</h3>
                <p>Lên kế hoạch đi chơi, tụ tập bạn bè nhanh chóng chỉ với vài cú nhấp chuột.</p>
              </div>
            </div>
          </div>
        </section>

        {/* Phần Liên hệ */}
        <section id="contact" className="fs-contact">
          <div className="fs-container">
            <div className="fs-contact-box">
              <div>
                <span className="fs-eyebrow">KẾT NỐI VỚI CHÚNG MÌNH</span>
                <h2>Bạn muốn đóng góp hoặc chia sẻ quán ngon?</h2>
                <p>Hãy gửi ngay gợi ý để Food Spot ngày càng hoàn thiện hơn cho cộng đồng yêu ẩm thực.</p>
              </div>
              <a className="fs-button" href="mailto:contact@foodspot.vn">
                Gửi đóng góp ngay <span>↗</span>
              </a>
            </div>
          </div>
        </section>
      </main>

      <footer className="fs-footer">
        <div className="fs-container fs-footer-content">
          <Link to="/" aria-label="Food Spot trang chủ">
            <img src="/food-spot.svg" alt="Food Spot" />
          </Link>
          <p>Xem review. Tìm quán ngon. Tạo thêm những cuộc hẹn.</p>
          <a href="#fs-main">Về đầu trang ↑</a>
        </div>
      </footer>
    </div>
  )
}
