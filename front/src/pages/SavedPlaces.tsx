import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import MainLayout from './MainLayout'
import PlaceDetailModal from '../components/place/PlaceDetailModal'
import VideoEmbedModal from '../components/video/VideoEmbedModal'
import { getSavedPlaces, unsavePlace } from '../api/saved'
import { useAuth } from '../contexts/AuthContext'
import type { SavedPlaceItem } from '../types/saved'
import type { Place } from '../types/place'
import type { Video } from '../types/video'
import './SavedPlaces.css'

const DEFAULT_FOOD_IMAGE =
  'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=800&q=80'

export default function SavedPlaces() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()

  const [savedPlaces, setSavedPlaces] = useState<SavedPlaceItem[]>([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('Tất cả')

  const [detailPlace, setDetailPlace] = useState<Place | null>(null)
  const [playingVideo, setPlayingVideo] = useState<Video | any | null>(null)

  useEffect(() => {
    if (!isAuthenticated) return

    let cancelled = false
    setLoading(true)

    getSavedPlaces(50, 0)
      .then((items) => {
        if (!cancelled) {
          setSavedPlaces(items)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error('Lỗi lấy danh sách quán đã lưu:', err)
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [isAuthenticated])

  const categories = useMemo(() => {
    const set = new Set<string>()
    set.add('Tất cả')
    for (const item of savedPlaces) {
      if (item.place.category) {
        set.add(item.place.category)
      }
    }
    return Array.from(set)
  }, [savedPlaces])

  const filteredPlaces = useMemo(() => {
    return savedPlaces.filter((item) => {
      const p = item.place
      const matchesSearch =
        p.name.toLowerCase().includes(search.toLowerCase()) ||
        (p.address && p.address.toLowerCase().includes(search.toLowerCase())) ||
        (p.normalized_address &&
          p.normalized_address.toLowerCase().includes(search.toLowerCase()))

      const matchesCategory =
        category === 'Tất cả' || p.category === category

      return matchesSearch && matchesCategory
    })
  }, [savedPlaces, search, category])

  const handleRemovePlace = async (placeId: string) => {
    try {
      await unsavePlace(placeId)
      setSavedPlaces((current) =>
        current.filter((item) => item.place.id !== placeId),
      )
    } catch (err: any) {
      alert(err.message || 'Không thể bỏ lưu địa điểm.')
    }
  }

  return (
    <MainLayout pageTitle="Saved Places">
      <section className="saved-places-page">
        <div className="saved-places-heading">
          <div>
            <span className="saved-places-eyebrow">YOUR COLLECTION</span>
            <h2>Địa điểm yêu thích</h2>
            <p>Những quán ăn và quán cà phê bạn đã lưu để ghé thăm.</p>
          </div>

          <div className="saved-places-count">
            <span>{savedPlaces.length}</span>
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
            {categories.map((item) => (
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

        {!isAuthenticated ? (
          <div className="saved-places-empty">
            <div className="saved-places-empty-icon">🔒</div>
            <h3>Yêu cầu đăng nhập</h3>
            <p>Vui lòng đăng nhập để xem danh sách quán ăn yêu thích của bạn.</p>
            <button
              type="button"
              className="saved-place-map-button"
              onClick={() => navigate('/login')}
            >
              Đăng nhập ngay
            </button>
          </div>
        ) : loading ? (
          <div className="saved-places-empty">
            <div className="saved-places-empty-icon">⌖</div>
            <h3>Đang tải dữ liệu...</h3>
            <p>Đang đồng bộ danh sách địa điểm ẩm thực đã lưu.</p>
          </div>
        ) : filteredPlaces.length > 0 ? (
          <div className="saved-places-grid">
            {filteredPlaces.map(({ place, video_count }) => (
              <article className="saved-place-card" key={place.id}>
                <div
                  className="saved-place-image"
                  onClick={() => setDetailPlace(place)}
                  style={{ cursor: 'pointer' }}
                >
                  <img
                    src={DEFAULT_FOOD_IMAGE}
                    alt={place.name}
                    loading="lazy"
                  />
                  <span className="saved-place-category">
                    {place.category || 'Ẩm thực'}
                  </span>

                  <button
                    type="button"
                    className="saved-place-heart"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleRemovePlace(place.id)
                    }}
                    aria-label={`Bỏ lưu ${place.name}`}
                    title="Bỏ khỏi địa điểm yêu thích"
                  >
                    ♥
                  </button>
                </div>

                <div className="saved-place-content">
                  <h3
                    onClick={() => setDetailPlace(place)}
                    style={{ cursor: 'pointer' }}
                  >
                    {place.name}
                  </h3>

                  <p className="saved-place-address">
                    <span aria-hidden="true">⌖</span>
                    {place.normalized_address ||
                      place.address ||
                      'Chưa có địa chỉ chi tiết'}
                  </p>

                  <div className="saved-place-actions">
                    <button
                      type="button"
                      className="saved-place-map-button"
                      onClick={() => setDetailPlace(place)}
                    >
                      <span>▷</span> {video_count} video review
                    </button>
                    <button
                      type="button"
                      className="saved-place-remove"
                      onClick={() => handleRemovePlace(place.id)}
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
                : 'Khi tìm được một quán ăn thú vị trên bản đồ, hãy lưu lại để dễ dàng tìm thấy sau này.'}
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

      {/* Place Detail Modal */}
      <PlaceDetailModal
        place={detailPlace}
        onClose={() => setDetailPlace(null)}
        onPlayVideo={(v) => {
          setDetailPlace(null)
          setPlayingVideo(v)
        }}
      />

      {/* Video Player Modal */}
      <VideoEmbedModal
        video={playingVideo}
        onClose={() => setPlayingVideo(null)}
      />
    </MainLayout>
  )
}