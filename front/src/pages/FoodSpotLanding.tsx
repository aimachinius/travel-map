
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Icon from '../components/Icon'
import 'leaflet/dist/leaflet.css'
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet'
import './FoodSpotLanding.css'




const spots = [
  {
    name: 'Một tô mì, trọn vị miền Trung',
    type: 'Món Việt',
    description: 'Mì Quảng · Bữa trưa đậm đà',
    image: 'photo-1569718212165-3a8278d5f624',
    lat: 16.0678,
    lng: 108.2208,
  },
  {
    name: 'Góc cà phê cho ngày thong thả',
    type: 'Cà phê',
    description: 'Cà phê · Một chút bình yên',
    image: 'photo-1445116572660-236099ec97a0',
    lat: 16.0614,
    lng: 108.2232,
  },
  {
    name: 'Hẹn nhau một bữa thật ngon',
    type: 'Món Việt',
    description: 'Món Việt · Đi cùng bạn bè',
    image: 'photo-1504674900247-0877df9cc836',
    lat: 16.0544,
    lng: 108.2022,
  },
]

const categories = ['Tất cả', 'Món Việt', 'Cà phê']

function MapFocus({ lat, lng }: { lat: number; lng: number }) {
  const map = useMap()

  useEffect(() => {
    map.flyTo([lat, lng], 15, { duration: 0.7 })
  }, [map, lat, lng])

  return null
}


export default function FoodSpotLanding() {
  const [menu, setMenu] = useState(false)
  const [category, setCategory] = useState('Tất cả')
  const [selected, setSelected] = useState(0)

  useEffect(() => { 
    document.title = 'Food Spot — Xem review, tìm quán ngon' 
  }, [])

  const visible = spots.map((spot, index) => ({ ...spot, index })).filter(spot => category === 'Tất cả' || spot.type === category)
  
  function chooseCategory(value: string) {
    setCategory(value)
    setSelected(Math.max(0, spots.findIndex(spot => value === 'Tất cả' || spot.type === value)))
  }

  return (
    <div className="fs-page">
      <a className="fs-skip" href="#fs-main">Đến nội dung chính</a>
      
      <header className="fs-header">
        <div className="fs-container fs-nav">
          <Link to="/" aria-label="Food Spot — Trang chủ">
            <img className="fs-logo" src="/food-spot.svg" alt="Food Spot" />
          </Link>
          <button 
            className="fs-menu" 
            aria-expanded={menu} 
            aria-controls="fs-navigation" 
            aria-label={menu ? 'Đóng menu' : 'Mở menu'} 
            onClick={() => setMenu(!menu)}
          >
            <Icon name={menu ? 'close' : 'menu'} />
          </button>
          <nav 
            id="fs-navigation" 
            className={menu ? 'fs-links open' : 'fs-links'} 
            aria-label="Điều hướng chính" 
            onKeyDown={event => { if (event.key === 'Escape') setMenu(false) }}
          >
            <a className="fs-current" href="#fs-main" onClick={() => setMenu(false)}>Trang chủ</a>
            <a href="#discover" onClick={() => { chooseCategory('Tất cả'); setMenu(false); }}>Khám phá</a>
            <a href="#features" onClick={() => setMenu(false)}>Tính năng</a>
            <a href="#contact" onClick={() => setMenu(false)}>Liên hệ</a>
            <div className="fs-auth">
              <Link to="/login">Đăng nhập</Link>
              <Link className="fs-button" to="/register">Đăng ký <span>↗</span></Link>
            </div>
          </nav>
        </div>
      </header>

      <main id="fs-main">
        {/* Phần Hero */}
        <section className="fs-hero fs-container">
          <div className="fs-hero-copy">
            <span className="fs-eyebrow"><span /> TỪ MÀN HÌNH ĐẾN ĐIỂM HẸN</span>
            <h1>Xem review.<br />Tìm quán ngon.<br /><em>Đi thôi!</em></h1>
            <p>Đừng để quán ngon chỉ nằm trong video đã lưu. Cùng Food Spot khám phá địa điểm ăn uống từ những review bạn yêu thích.</p>
            <div className="fs-hero-actions">
              <a className="fs-button" href="#discover">Khám phá ngay <Icon name="arrow" /></a>
              <a className="fs-text-link" href="#features">Tìm hiểu tính năng ↗</a>
            </div>
            <div className="fs-hero-note"><span>⌖</span> Một bản đồ, thêm nhiều trải nghiệm ngon.</div>
          </div>
          <div className="fs-hero-visual">
            <div className="fs-photo">
              <img src="https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1000&q=85" alt="Bàn ăn với nhiều món ăn đầy màu sắc" />
              <span className="fs-photo-tag">Ăn ngon, đi cùng nhau.</span>
            </div>
            <div className="fs-orbit">ĂN GÌ<br /><b>HÔM NAY?</b><span>↙</span></div>
            <div className="fs-floating">
              <span className="fs-floating-icon"><Icon name="pin" /></span>
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

        {/* Phần Bản đồ và danh sách quán */}
        <section id="discover" className="fs-discover">
          <div className="fs-container">
            <div className="fs-section-head">
              <div>
                
                <h2>Hôm nay, mình ăn ở đâu?</h2>
              </div>
              
            </div>
            <div className="fs-demo">
              <div className="fs-results">
                <div className="fs-demo-title">
                  <h3>Khám phá theo khẩu vị</h3>
                  <Icon name="compass" />
                </div>
                <div className="fs-filters" aria-label="Loại địa điểm">
                  {categories.map(value => (
                    <button key={value} aria-pressed={category === value} onClick={() => chooseCategory(value)}>{value}</button>
                  ))}
                </div>
                <div className="fs-spot-list">
                  {visible.map(spot => (
                    <button 
                      className={`fs-spot ${selected === spot.index ? 'selected' : ''}`} 
                      key={spot.name} 
                      onClick={() => setSelected(spot.index)} 
                      aria-pressed={selected === spot.index}
                    >
                      <img src={`https://images.unsplash.com/${spot.image}?auto=format&fit=crop&w=280&q=80`} alt="" />
                      <div className="fs-spot-info">
                        <small>{spot.type}</small>
                        <strong>{spot.name}</strong>
                        <span>{spot.description}</span>
                      </div>
                      <span className="fs-spot-arrow">↗</span>
                    </button>
                  ))}
                </div>
                <p className="fs-demo-note">Rê chuột hoặc chọn quán để xem vị trí trên bản đồ.</p>
              </div>

              {/* KHUNG BẢN ĐỒ KHU VỰC ĐƯỜNG PHỐ THỰC TẾ */}
              
<div className="fs-map" aria-label="Bản đồ địa điểm ăn uống">
  <MapContainer
    center={[16.0678, 108.2208]}
    zoom={13}
    scrollWheelZoom={true}
    className="fs-leaflet-map"
  >
    <TileLayer
      attribution={
        import.meta.env.VITE_CARTO_API_KEY
          ? '&copy; OpenStreetMap contributors &copy; CARTO'
          : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      }
      url={
        import.meta.env.VITE_CARTO_API_KEY
          ? `https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=${import.meta.env.VITE_CARTO_API_KEY}`
          : 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
      }
    />

    <MapFocus
      lat={spots[selected].lat}
      lng={spots[selected].lng}
    />

    {visible.map(spot => (
      <CircleMarker
        key={spot.name}
        center={[spot.lat, spot.lng]}
        radius={selected === spot.index ? 11 : 8}
        pathOptions={{
          color: '#ffffff',
          weight: 3,
          fillColor: selected === spot.index ? '#315d43' : '#d9825b',
          fillOpacity: 1,
        }}
        eventHandlers={{
          click: () => setSelected(spot.index),
        }}
      >
        <Popup>
          <strong>{spot.name}</strong>
          <br />
          {spot.description}
        </Popup>
      </CircleMarker>
    ))}
  
  </MapContainer>
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
                <p>Xác định chính xác vị trí quán ăn ngay từ video review yêu thích mà không phải tìm kiếm thủ công.</p>
              </div>
              <div className="fs-feature-card">
                <div className="fs-feature-icon">⚡</div>
                <h3>Lọc nhanh khẩu vị</h3>
                <p>Dễ dàng phân loại theo món Việt, quán cà phê hay các điểm ăn uống phù hợp với nhu cầu trong ngày.</p>
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
              <a className="fs-button" href="mailto:contact@foodspot.vn">Gửi đóng góp ngay <span>↗</span></a>
            </div>
          </div>
        </section>
      </main>

      <footer className="fs-footer">
        <div className="fs-container fs-footer-content">
          <Link to="/" aria-label="Food Spot trang chủ"><img src="/food-spot.svg" alt="Food Spot" /></Link>
          <p>Xem review. Tìm quán ngon. Tạo thêm những cuộc hẹn.</p>
          <a href="#fs-main">Về đầu trang ↑</a>
        </div>
      </footer>
    </div>
  )
}