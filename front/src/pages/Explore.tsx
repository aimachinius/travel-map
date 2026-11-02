
import { useState, useEffect, useMemo, type FormEvent } from 'react'
import ExploreMap, { type SearchCenter, type MapPlaceMarker } from '../components/ExploreMap'
import VideoCard from '../components/video/VideoCard'
import VideoEmbedModal from '../components/video/VideoEmbedModal'
import PlaceDetailModal from '../components/place/PlaceDetailModal'
import MainLayout from './MainLayout'
import { getNearbyVideos, getPlaceDetail } from '../api/places'
import { submitVideo } from '../api/videos'
import { useAuth } from '../contexts/AuthContext'
import { useAnalysis } from '../contexts/AnalysisContext'
import type { NearbyVideoItem, Place } from '../types/place'
import type { Video } from '../types/video'
import './Explore.css'

const DEFAULT_CENTER: SearchCenter = {
  position: [16.0544, 108.2022], // Đà Nẵng
  label: 'Khu vực trung tâm Đà Nẵng',
}

export default function Explore() {
  const { isAuthenticated } = useAuth()
  const { addCustomToast, latestTargetLocation } = useAnalysis()

  const [videoUrl, setVideoUrl] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const [searchCenter, setSearchCenter] = useState<SearchCenter | null>(DEFAULT_CENTER)
  const [radius, setRadius] = useState<number>(5)

  const [nearbyVideos, setNearbyVideos] = useState<NearbyVideoItem[]>([])
  const [loadingVideos, setLoadingVideos] = useState<boolean>(false)

  const [selectedPlaceId, setSelectedPlaceId] = useState<string | null>(null)
  const [playingVideo, setPlayingVideo] = useState<Video | any | null>(null)
  const [detailPlace, setDetailPlace] = useState<Place | null>(null)

  // Tự động di chuyển tâm bản đồ khi nhận thông báo AI hoàn tất
  useEffect(() => {
    if (latestTargetLocation) {
      setSearchCenter({
        position: latestTargetLocation,
        label: 'Địa điểm AI vừa phát hiện',
      })
    }
  }, [latestTargetLocation])

  // Lấy danh sách video xung quanh bán kính khi tâm bản đồ hoặc bán kính thay đổi
  useEffect(() => {
    if (!searchCenter) return

    let cancelled = false
    setLoadingVideos(true)

    getNearbyVideos(
      searchCenter.position[0],
      searchCenter.position[1],
      radius * 1000,
      50,
      0,
    )
      .then((items) => {
        if (!cancelled) {
          setNearbyVideos(items)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error('Lỗi tải video lân cận:', err)
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingVideos(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [searchCenter, radius])

  // Trích xuất các marker địa điểm duy nhất cho bản đồ
  const mapPlaces: MapPlaceMarker[] = useMemo(() => {
    const placeMap = new Map<string, MapPlaceMarker>()
    for (const item of nearbyVideos) {
      if (item.place && item.place.latitude !== null && item.place.longitude !== null) {
        if (!placeMap.has(item.place.id)) {
          placeMap.set(item.place.id, {
            id: item.place.id,
            name: item.place.name,
            address: item.place.address,
            latitude: item.place.latitude,
            longitude: item.place.longitude,
            category: item.place.category,
            is_saved: item.place.is_saved,
          })
        }
      }
    }
    return Array.from(placeMap.values())
  }, [nearbyVideos])

  // Lọc video theo địa điểm đang chọn nếu có
  const displayedVideos = useMemo(() => {
    if (!selectedPlaceId) return nearbyVideos
    return nearbyVideos.filter((item) => item.place?.id === selectedPlaceId)
  }, [nearbyVideos, selectedPlaceId])

  const selectedPlaceInfo = useMemo(() => {
    if (!selectedPlaceId) return null
    const found = nearbyVideos.find((item) => item.place?.id === selectedPlaceId)
    return found ? found.place : null
  }, [nearbyVideos, selectedPlaceId])

  // Xử lý gửi video phân tích
  const handleSubmitVideo = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const trimmed = videoUrl.trim()
    if (!trimmed) return

    if (!isAuthenticated) {
      alert('Vui lòng đăng nhập để gửi video phân tích tự động.')
      return
    }

    setSubmitting(true)
    try {
      await submitVideo(trimmed)
      addCustomToast({
        status: 'PENDING',
        title: 'Video đã được gửi!',
        message: 'AI đang tiến hành phân tích và trích xuất địa điểm quán ăn.',
      })
      setVideoUrl('')
    } catch (err: any) {
      alert(err.message || 'Không thể gửi video phân tích. Vui lòng thử lại.')
    } finally {
      setSubmitting(false)
    }
  }

  // Mở modal chi tiết quán ăn
  const handleOpenPlaceDetail = async (placeId: string) => {
    try {
      const place = await getPlaceDetail(placeId)
      setDetailPlace(place)
    } catch (err) {
      console.error('Lỗi lấy thông tin quán:', err)
    }
  }

  return (
    <MainLayout pageTitle="Explore Map">
      <form className="video-search" onSubmit={handleSubmitVideo}>
        <span className="search-link-icon">↗</span>

        <input
          type="url"
          value={videoUrl}
          onChange={(e) => setVideoUrl(e.target.value)}
          placeholder="Dán link video review TikTok hoặc YouTube Shorts..."
          aria-label="Link video review"
          disabled={submitting}
        />

        <button type="submit" disabled={submitting}>
          {submitting ? 'Đang gửi...' : 'Phân tích video'} <span>→</span>
        </button>
      </form>

      <section className="explore-workspace">
        <section className="map-panel">
          <ExploreMap
            searchCenter={searchCenter}
            onSelectCenter={(pos, label) => setSearchCenter({ position: pos, label })}
            radius={radius}
            onRadiusChange={(r) => setRadius(r)}
            places={mapPlaces}
            onSelectPlace={(place) => setSelectedPlaceId(place.id)}
          />
        </section>

        <aside className="reviews-panel">
          <div className="reviews-heading">
            <div>
              <span className="section-eyebrow">
                {selectedPlaceInfo ? 'SELECTED PLACE' : 'NEARBY REVIEWS'}
              </span>
              <h2>{selectedPlaceInfo ? selectedPlaceInfo.name : 'Video reviews'}</h2>
            </div>

            <span className="video-count">{displayedVideos.length} videos</span>
          </div>

          {selectedPlaceInfo && (
            <div className="reviews-selected-bar">
              <div className="selected-bar-info">
                <span className="selected-address">
                  📍 {selectedPlaceInfo.address || 'Chưa có địa chỉ chi tiết'}
                </span>
              </div>
              <div className="selected-bar-actions">
                <button
                  type="button"
                  className="selected-detail-btn"
                  onClick={() => handleOpenPlaceDetail(selectedPlaceInfo.id)}
                >
                  Chi tiết quán ↗
                </button>
                <button
                  type="button"
                  className="selected-clear-btn"
                  onClick={() => setSelectedPlaceId(null)}
                >
                  ✕ Xem tất cả
                </button>
              </div>
            </div>
          )}

          <div className="reviews-body">
            {loadingVideos ? (
              <div className="reviews-loading">
                <div className="reviews-spinner" />
                <p>Đang tìm kiếm video review trong bán kính {radius} km...</p>
              </div>
            ) : displayedVideos.length === 0 ? (
              <div className="reviews-empty">
                <div className="empty-video-icon">▷</div>
                <h3>Không có video nào</h3>
                <p>
                  {selectedPlaceId
                    ? 'Chưa có video review nào khớp với địa điểm đã chọn.'
                    : `Chưa tìm thấy video review nào trong bán kính ${radius} km quanh vị trí này. Thử kéo thả tâm bản đồ hoặc tăng bán kính.`}
                </p>
                {selectedPlaceId && (
                  <button
                    type="button"
                    className="reviews-reset-btn"
                    onClick={() => setSelectedPlaceId(null)}
                  >
                    Xem tất cả video khu vực
                  </button>
                )}
              </div>
            ) : (
              <div className="reviews-list">
                {displayedVideos.map((item) => (
                  <VideoCard
                    key={`${item.video.id}-${item.place?.id || 'none'}`}
                    video={item.video}
                    place={item.place}
                    confidenceStatus={item.match?.confidence_status}
                    distanceM={item.distance_m}
                    onPlay={() => setPlayingVideo(item.video)}
                    onSelectPlace={(placeId) => {
                      setSelectedPlaceId(placeId)
                      handleOpenPlaceDetail(placeId)
                    }}
                  />
                ))}
              </div>
            )}
          </div>

          <div className="reviews-footer">
            <span className="source-dot" />
            <span>
              Phát hiện vị trí tự động qua AI và chuẩn hóa địa lý PostGIS.
            </span>
          </div>
        </aside>
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

