import { useState, type MouseEvent } from 'react'
import { saveVideo, unsaveVideo } from '../../api/saved'
import { useAuth } from '../../contexts/AuthContext'
import './VideoCard.css'

export interface VideoCardProps {
  video: {
    id: string
    platform: string
    platform_video_id: string
    video_url: string
    title: string | null
    caption: string | null
    thumbnail_url: string | null
    author_name: string | null
    duration_seconds?: number | null
    is_saved?: boolean
  }
  place?: {
    id: string
    name: string
    address: string | null
  } | null
  confidenceStatus?: 'HIGH' | 'MEDIUM' | 'LOW'
  distanceM?: number | null
  onPlay: () => void
  onSelectPlace?: (placeId: string) => void
}

export default function VideoCard({
  video,
  place,
  confidenceStatus,
  distanceM,
  onPlay,
  onSelectPlace,
}: VideoCardProps) {
  const { isAuthenticated } = useAuth()
  const [isSaved, setIsSaved] = useState(!!video.is_saved)
  const [saving, setSaving] = useState(false)

  const handleToggleSave = async (e: MouseEvent) => {
    e.stopPropagation()
    if (!isAuthenticated) {
      alert('Vui lòng đăng nhập để lưu video vào bộ sưu tập.')
      return
    }

    setSaving(true)
    try {
      if (isSaved) {
        await unsaveVideo(video.id)
        setIsSaved(false)
      } else {
        await saveVideo(video.id)
        setIsSaved(true)
      }
    } catch (err: any) {
      alert(err.message || 'Không thể cập nhật trạng thái lưu video.')
    } finally {
      setSaving(false)
    }
  }

  const formatDistance = (m?: number | null) => {
    if (m === undefined || m === null) return null
    if (m < 1000) return `${Math.round(m)}m`
    return `${(m / 1000).toFixed(1)}km`
  }

  return (
    <div className="fs-video-card" onClick={onPlay}>
      <div className="fs-video-thumb-container">
        {video.thumbnail_url ? (
          <img
            src={video.thumbnail_url}
            alt={video.title || 'Video thumbnail'}
            className="fs-video-thumb"
          />
        ) : (
          <div className={`fs-video-thumb-placeholder fs-thumb-${video.platform}`}>
            <span className="fs-play-icon">▶</span>
          </div>
        )}

        <span className={`fs-platform-tag fs-tag-${video.platform}`}>
          {video.platform === 'tiktok' ? 'TikTok' : 'Shorts'}
        </span>

        {distanceM !== undefined && distanceM !== null && (
          <span className="fs-distance-tag">
            {formatDistance(distanceM)}
          </span>
        )}

        <button
          type="button"
          className={`fs-save-video-btn ${isSaved ? 'saved' : ''}`}
          onClick={handleToggleSave}
          disabled={saving}
          aria-label={isSaved ? 'Bỏ lưu video' : 'Lưu video'}
          title={isSaved ? 'Đã lưu (Nhấn để bỏ lưu)' : 'Lưu vào danh sách yêu thích'}
        >
          {isSaved ? '♥' : '♡'}
        </button>
      </div>

      <div className="fs-video-info">
        <h4 className="fs-video-title">
          {video.title || video.caption || 'Video review ẩm thực'}
        </h4>

        {video.author_name && (
          <span className="fs-video-author">@{video.author_name}</span>
        )}

        {place && (
          <div
            className="fs-video-place-link"
            onClick={(e) => {
              e.stopPropagation()
              if (onSelectPlace) onSelectPlace(place.id)
            }}
          >
            <span className="fs-place-icon">📍</span>
            <span className="fs-place-name">{place.name}</span>
            {confidenceStatus && (
              <span className={`fs-confidence-badge fs-conf-${confidenceStatus.toLowerCase()}`}>
                {confidenceStatus}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
