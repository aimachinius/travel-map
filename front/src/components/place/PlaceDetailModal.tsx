import { useEffect, useState } from 'react'
import { getPlaceVideos } from '../../api/places'
import { savePlace, unsavePlace } from '../../api/saved'
import { useAuth } from '../../contexts/AuthContext'
import type { Place, PlaceVideoMatchItem } from '../../types/place'
import VideoCard from '../video/VideoCard'
import './PlaceDetailModal.css'

interface PlaceDetailModalProps {
  place: Place | null
  onClose: () => void
  onPlayVideo: (video: any) => void
}

export default function PlaceDetailModal({
  place,
  onClose,
  onPlayVideo,
}: PlaceDetailModalProps) {
  const { isAuthenticated } = useAuth()
  const [videos, setVideos] = useState<PlaceVideoMatchItem[]>([])
  const [loading, setLoading] = useState(false)
  const [isSaved, setIsSaved] = useState(!!place?.is_saved)
  const [savingPlace, setSavingPlace] = useState(false)

  useEffect(() => {
    if (!place) return

    setIsSaved(!!place.is_saved)
    setLoading(true)

    getPlaceVideos(place.id)
      .then((data) => setVideos(data))
      .catch((err) => console.error('Error fetching place videos:', err))
      .finally(() => setLoading(false))
  }, [place])

  if (!place) return null

  const handleToggleSavePlace = async () => {
    if (!isAuthenticated) {
      alert('Vui lòng đăng nhập để lưu địa điểm vào bộ sưu tập.')
      return
    }

    setSavingPlace(true)
    try {
      if (isSaved) {
        await unsavePlace(place.id)
        setIsSaved(false)
      } else {
        await savePlace(place.id)
        setIsSaved(true)
      }
    } catch (err: any) {
      alert(err.message || 'Không thể cập nhật trạng thái lưu quán.')
    } finally {
      setSavingPlace(false)
    }
  }

  return (
    <div className="place-modal-backdrop" onClick={onClose}>
      <div
        className="place-modal-content"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="place-modal-header">
          <div>
            <div className="place-modal-eyebrow">
              <span className="place-category-badge">
                {place.category || 'Ẩm thực'}
              </span>
              {place.latitude && place.longitude && (
                <span className="place-coords">
                  {place.latitude.toFixed(4)}, {place.longitude.toFixed(4)}
                </span>
              )}
            </div>
            <h2>{place.name}</h2>
            <p className="place-modal-address">
              📍 {place.normalized_address || place.address || 'Chưa có địa chỉ chi tiết'}
            </p>
          </div>

          <div className="place-modal-actions">
            <button
              type="button"
              className={`place-save-btn ${isSaved ? 'saved' : ''}`}
              onClick={handleToggleSavePlace}
              disabled={savingPlace}
            >
              {isSaved ? '♥ Đã lưu quán' : '♡ Lưu quán này'}
            </button>

            <button
              type="button"
              className="place-modal-close"
              onClick={onClose}
              aria-label="Đóng"
            >
              ✕
            </button>
          </div>
        </div>

        <div className="place-modal-body">
          <div className="place-videos-heading">
            <h3>Video reviews ({videos.length})</h3>
            <span className="place-videos-sub">
              Sắp xếp theo độ tin cậy từ cao xuống thấp
            </span>
          </div>

          {loading ? (
            <div className="place-loading-state">
              <span className="place-spinner" />
              <p>Đang tải danh sách video review...</p>
            </div>
          ) : videos.length === 0 ? (
            <div className="place-empty-videos">
              <p>Chưa có video review nào khớp với địa điểm này.</p>
            </div>
          ) : (
            <div className="place-videos-grid">
              {videos.map((item) => (
                <VideoCard
                  key={item.video.id}
                  video={item.video}
                  confidenceStatus={item.confidence_status}
                  onPlay={() => onPlayVideo(item.video)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
