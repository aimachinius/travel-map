
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import MainLayout from './MainLayout'
import VideoCard from '../components/video/VideoCard'
import VideoEmbedModal from '../components/video/VideoEmbedModal'
import PlaceDetailModal from '../components/place/PlaceDetailModal'
import { getSavedVideos } from '../api/saved'
import { getPlaceDetail } from '../api/places'
import { useAuth } from '../contexts/AuthContext'
import type { SavedVideoItem } from '../types/saved'
import type { Place } from '../types/place'
import type { Video } from '../types/video'
import './SavedVideos.css'

export default function SavedVideos() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()

  const [savedItems, setSavedItems] = useState<SavedVideoItem[]>([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [platform, setPlatform] = useState<'ALL' | 'tiktok' | 'youtube'>('ALL')

  const [playingVideo, setPlayingVideo] = useState<Video | any | null>(null)
  const [detailPlace, setDetailPlace] = useState<Place | null>(null)

  useEffect(() => {
    if (!isAuthenticated) return

    let cancelled = false
    setLoading(true)

    getSavedVideos(50, 0)
      .then((items) => {
        if (!cancelled) {
          setSavedItems(items)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error('Lỗi lấy video đã lưu:', err)
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

  const filteredVideos = useMemo(() => {
    return savedItems.filter((item) => {
      const titleMatch = (item.video.title || '').toLowerCase().includes(search.toLowerCase())
      const captionMatch = (item.video.caption || '').toLowerCase().includes(search.toLowerCase())
      const authorMatch = (item.video.author_name || '').toLowerCase().includes(search.toLowerCase())
      const placeMatch = (item.place?.name || '').toLowerCase().includes(search.toLowerCase())

      const matchesSearch = !search || titleMatch || captionMatch || authorMatch || placeMatch
      const matchesPlatform = platform === 'ALL' || item.video.platform === platform

      return matchesSearch && matchesPlatform
    })
  }, [savedItems, search, platform])

  const handleOpenPlaceDetail = async (placeId: string) => {
    try {
      const place = await getPlaceDetail(placeId)
      setDetailPlace(place)
    } catch (err) {
      console.error('Lỗi lấy thông tin quán:', err)
    }
  }

  return (
    <MainLayout pageTitle="Saved Videos">
      <section className="saved-videos-page">
        <div className="saved-videos-heading">
          <div>
            <span className="section-eyebrow">YOUR COLLECTION</span>
            <h2>Saved Videos</h2>
            <p>Những video review ẩm thực bạn đã lưu để ghé thăm và thưởng thức.</p>
          </div>

          <span className="saved-videos-count">{savedItems.length} videos</span>
        </div>

        <div className="saved-videos-toolbar">
          <label className="saved-videos-search">
            <span aria-hidden="true">⌕</span>
            <input
              type="search"
              placeholder="Tìm theo tiêu đề, món ăn, kênh review hoặc tên quán..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Tìm kiếm video đã lưu"
            />
            {search && (
              <button
                type="button"
                className="saved-videos-clear"
                onClick={() => setSearch('')}
                aria-label="Xóa tìm kiếm"
              >
                ×
              </button>
            )}
          </label>

          <div className="saved-videos-filters">
            {(['ALL', 'tiktok', 'youtube'] as const).map((p) => (
              <button
                type="button"
                key={p}
                className={platform === p ? 'active' : ''}
                onClick={() => setPlatform(p)}
              >
                {p === 'ALL' ? 'Tất cả' : p === 'tiktok' ? 'TikTok' : 'YouTube Shorts'}
              </button>
            ))}
          </div>
        </div>

        {!isAuthenticated ? (
          <div className="saved-videos-empty">
            <div className="saved-videos-icon">🔒</div>
            <h3>Yêu cầu đăng nhập</h3>
            <p>Vui lòng đăng nhập để lưu trữ và quản lý bộ sưu tập video ẩm thực của bạn.</p>
            <button
              type="button"
              className="saved-videos-explore-btn"
              onClick={() => navigate('/login')}
            >
              Đăng nhập ngay
            </button>
          </div>
        ) : loading ? (
          <div className="saved-videos-loading">
            <div className="saved-videos-spinner" />
            <p>Đang tải danh sách video đã lưu...</p>
          </div>
        ) : filteredVideos.length === 0 ? (
          <div className="saved-videos-empty">
            <div className="saved-videos-icon">♡</div>
            <h3>
              {search || platform !== 'ALL'
                ? 'Không tìm thấy video phù hợp'
                : 'Chưa có video nào trong bộ sưu tập'}
            </h3>
            <p>
              {search || platform !== 'ALL'
                ? 'Thử thay đổi từ khóa hoặc bộ lọc nền tảng để tìm kiếm.'
                : 'Khi khám phá trên bản đồ hoặc phân tích video ẩm thực, hãy bấm biểu tượng trái tim để lưu lại.'}
            </p>
            <button
              type="button"
              className="saved-videos-explore-btn"
              onClick={() => navigate('/explore')}
            >
              Khám phá bản đồ ẩm thực
            </button>
          </div>
        ) : (
          <div className="saved-videos-grid">
            {filteredVideos.map((item) => (
              <VideoCard
                key={item.saved_id}
                video={{
                  ...item.video,
                  is_saved: true,
                }}
                place={item.place}
                onPlay={() => setPlayingVideo(item.video)}
                onSelectPlace={(placeId) => handleOpenPlaceDetail(placeId)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Video Player Modal */}
      <VideoEmbedModal
        video={playingVideo}
        onClose={() => setPlayingVideo(null)}
      />

      {/* Place Detail Modal */}
      <PlaceDetailModal
        place={detailPlace}
        onClose={() => setDetailPlace(null)}
        onPlayVideo={(v) => {
          setDetailPlace(null)
          setPlayingVideo(v)
        }}
      />
    </MainLayout>
  )
}

