/**
 * @deprecated LEGACY COMPONENT - ĐÃ NGƯNG SỬ DỤNG TRONG ROUTING CHÍNH
 * Chức năng "Địa điểm yêu thích" đã được thay thế bằng ngăn kéo kính thể lỏng (Liquid Drawer: Liked Places)
 * trực tiếp trên trang /explore.
 * File này được giữ lại nhằm mục đích tham khảo mã nguồn cũ, không xóa.
 */

import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import MainLayout from './MainLayout'
import './SavedPlaces.css'

type Place = {
  id: number
  name: string
  address: string
  category: 'Quán ăn' | 'Cà phê'
  image: string
}

const initialPlaces: Place[] = [
  {
    id: 1,
    name: 'Bún chả cá Đà Nẵng',
    address: 'Đà Nẵng, Việt Nam',
    category: 'Quán ăn',
    image:
      'https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=800&q=80',
  },
  {
    id: 2,
    name: 'Góc cà phê xanh',
    address: 'Đà Nẵng, Việt Nam',
    category: 'Cà phê',
    image:
      'https://images.unsplash.com/photo-1445116572660-236099ec97a0?auto=format&fit=crop&w=800&q=80',
  },
  {
    id: 3,
    name: 'Món ngon địa phương',
    address: 'Đà Nẵng, Việt Nam',
    category: 'Quán ăn',
    image:
      'https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=800&q=80',
  },
]

export default function SavedPlaces() {
  const navigate = useNavigate()
  const [places, setPlaces] = useState(initialPlaces)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('Tất cả')

  const filteredPlaces = useMemo(() => {
    return places.filter((place) => {
      const matchesSearch =
        place.name.toLowerCase().includes(search.toLowerCase()) ||
        place.address.toLowerCase().includes(search.toLowerCase())

      const matchesCategory =
        category === 'Tất cả' || place.category === category

      return matchesSearch && matchesCategory
    })
  }, [places, search, category])

  const removePlace = (id: number) => {
    setPlaces((current) => current.filter((place) => place.id !== id))
  }

  return (
    <MainLayout pageTitle="Saved Places">
      <section className="saved-places-page">
        <div className="saved-places-heading">
          <div>
            <span className="saved-places-eyebrow">YOUR COLLECTION</span>
            <h2>Địa điểm yêu thích</h2>
            <p>Lưu lại những nơi bạn muốn ghé thăm tiếp theo.</p>
          </div>

          <div className="saved-places-count">
            <span>{places.length}</span>
            <span>địa điểm</span>
          </div>
        </div>

        <div className="saved-places-toolbar">
          <label className="saved-places-search">
            <span aria-hidden="true">⌕</span>
            <input
              type="search"
              placeholder="Tìm tên quán hoặc địa chỉ..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label="Tìm địa điểm đã lưu"
            />
            {search && (
              <button
                type="button"
                className="saved-places-clear"
                onClick={() => setSearch('')}
                aria-label="Xóa nội dung tìm kiếm"
              >
                ×
              </button>
            )}
          </label>

          <div className="saved-places-filters">
            {['Tất cả', 'Quán ăn', 'Cà phê'].map((item) => (
              <button
                type="button"
                key={item}
                className={category === item ? 'active' : ''}
                onClick={() => setCategory(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        {filteredPlaces.length > 0 ? (
          <div className="saved-places-grid">
            {filteredPlaces.map((place) => (
              <article className="saved-place-card" key={place.id}>
                <div className="saved-place-image">
                  <img src={place.image} alt={place.name} loading="lazy" />
                  <span className="saved-place-category">
                    {place.category}
                  </span>

                  <button
                    type="button"
                    className="saved-place-heart"
                    onClick={() => removePlace(place.id)}
                    aria-label={`Bỏ lưu ${place.name}`}
                    title="Bỏ khỏi địa điểm yêu thích"
                  >
                    ♥
                  </button>
                </div>

                <div className="saved-place-content">
                  <h3>{place.name}</h3>

                  <p className="saved-place-address">
                    <span aria-hidden="true">⌖</span>
                    {place.address}
                  </p>

                  <div className="saved-place-actions">
                    <button
                      type="button"
                      className="saved-place-map-button"
                      onClick={() => navigate('/explore')}
                    >
                      <span aria-hidden="true">⌖</span>
                      Xem bản đồ
                    </button>
                    <button
                      type="button"
                      className="saved-place-remove"
                      onClick={() => removePlace(place.id)}
                    >
                      Bỏ lưu
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="saved-places-empty">
            <div className="saved-places-empty-icon">⌖</div>
            <h3>
              {search || category !== 'Tất cả'
                ? 'Không tìm thấy địa điểm'
                : 'Chưa có địa điểm yêu thích'}
            </h3>
            <p>
              {search || category !== 'Tất cả'
                ? 'Thử thay đổi từ khóa hoặc bộ lọc để tìm địa điểm.'
                : 'Khi tìm được một quán ăn thú vị, hãy lưu lại để dễ dàng tìm thấy sau này.'}
            </p>
            <button
              type="button"
              className="saved-place-map-button"
              onClick={() => navigate('/explore')}
            >
              Khám phá địa điểm
            </button>
          </div>
        )}
      </section>
    </MainLayout>
  )
}
