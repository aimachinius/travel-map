import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import './liquid-glass.css'
import type { DrawerMode, EngineType, VideoPlaylistItem } from './types'
import {
  PRESET_PLAYLIST,
  extractTikTokVideoId,
} from './mockData'
import { useToast } from './hooks/useToast'
import LiquidMap from './LiquidMap'
import LeftFloatingDock from './LeftFloatingDock'
import LiquidDrawer from './LiquidDrawer'
import ControlsArea from './ControlsArea'
import LiquidVideoPlayer from './LiquidVideoPlayer'
import LiquidToast from './LiquidToast'
import BottomUtilityBar from './BottomUtilityBar'
import {
  POPULAR_HUBS,
  QUICK_LANDMARKS,
  filterVideosByRadius,
  type LandmarkPreset,
  type LocationHub,
} from './geoUtils'
import LiquidRouteCard from './LiquidRouteCard'
import {
  getRouteDirections,
  type RoutePoint,
  type RouteResult,
  type RouteVehicle,
} from './routingService'
import { createAnalysisWebSocket, placesApi, videosApi } from '../../services/api'
import { useAuth } from '../../services/useAuth'
import type { AnalysisWebSocketMessage, NearbyVideoItem } from '../../types/api'

function mapNearbyItemToPlaylist(item: NearbyVideoItem): VideoPlaylistItem {
  const v = item.video
  const p = item.place
  const isCafe =
    p.category?.toLowerCase().includes('cà phê') ||
    p.category?.toLowerCase().includes('cafe')
  return {
    id: v.platform_video_id || v.id,
    url: v.video_url,
    title: v.title || `${p.name} - Review`,
    author: v.author_name ? `@${v.author_name}` : '@foodspot_review',
    locationName: p.name,
    lat: p.latitude || 16.0544,
    lng: p.longitude || 108.2022,
    gmapQuery: `${p.name}, ${p.address || ''}`,
    category: p.category || 'Quán ăn',
    icon: isCafe ? '☕' : '🍜',
    desc: p.address || 'Địa chỉ được nhận diện từ video review ẩm thực.',
    distanceKm:
      item.distance_m !== undefined && item.distance_m !== null
        ? Number((item.distance_m / 1000).toFixed(2))
        : item.distance_meters !== undefined && item.distance_meters !== null
          ? Number((item.distance_meters / 1000).toFixed(2))
          : undefined,
    placeId: p.id,
    videoId: v.id,
    isSaved: v.is_saved || p.is_saved,
  }
}

interface LiquidGlassExperienceProps {
  isActive?: boolean
}

export default function LiquidGlassExperience({ isActive = true }: LiquidGlassExperienceProps) {
  const { token } = useAuth()
  const [playlist, setPlaylist] = useState<VideoPlaylistItem[]>(PRESET_PLAYLIST)
  const [currentIndex, setCurrentIndex] = useState<number>(0)
  const [currentVideo, setCurrentVideo] = useState<VideoPlaylistItem | null>(PRESET_PLAYLIST[0])
  const [inputValue, setInputValue] = useState<string>(PRESET_PLAYLIST[0].url)
  const [engine, setEngine] = useState<EngineType>('mp4')
  const [drawerMode, setDrawerMode] = useState<DrawerMode | null>(null)
  const [tileStyle, setTileStyle] = useState<'dark' | 'standard'>('standard')
  const [targetLocation, setTargetLocation] = useState<{ lat: number; lng: number } | null>({
    lat: PRESET_PLAYLIST[0].lat,
    lng: PRESET_PLAYLIST[0].lng,
  })
  const [hasError, setHasError] = useState<boolean>(false)

  // Bộ lọc Khám phá Thông minh: Nổi tiếng (trending) vs Quanh vị trí (nearby)
  const [filterMode, setFilterMode] = useState<'trending' | 'nearby'>('trending')
  const [selectedRadius, setSelectedRadius] = useState<number>(5)
  const [currentHub, setCurrentHub] = useState<LocationHub>(POPULAR_HUBS[0])
  const [isLocating, setIsLocating] = useState<boolean>(false)

  // Chế độ Chỉ đường OSRM (Miễn phí 100%)
  const [isRoutingActive, setIsRoutingActive] = useState<boolean>(false)
  const [routeVehicle, setRouteVehicle] = useState<RouteVehicle>('motorcycle')
  const [customOrigin, setCustomOrigin] = useState<RoutePoint | null>(null)
  const [routeData, setRouteData] = useState<RouteResult | null>(null)
  const [isRouteLoading, setIsRouteLoading] = useState<boolean>(false)
  const [routeError, setRouteError] = useState<string | null>(null)

  // Điểm xuất phát: Ưu tiên điểm người dùng tự chọn/kéo thả, mặc định lấy tâm khu vực
  const routeOrigin = useMemo<RoutePoint>(() => {
    if (customOrigin) {
      return customOrigin
    }
    return {
      lat: currentHub.lat,
      lng: currentHub.lng,
      name: `Tâm ${currentHub.name}`,
    }
  }, [customOrigin, currentHub])

  // Danh sách các địa điểm xuất phát nhanh quen thuộc cho khu vực hiện tại
  const currentLandmarks = useMemo(() => {
    return QUICK_LANDMARKS.filter((lm) => lm.hubId === currentHub.id)
  }, [currentHub.id])

  // Người dùng chọn điểm trên bản đồ hoặc kéo thả marker
  const handleSelectOrigin = useCallback((point: RoutePoint) => {
    setCustomOrigin(point)
  }, [])

  // Người dùng bấm vào gợi ý điểm xuất phát nhanh
  const handleSelectLandmark = useCallback((lm: LandmarkPreset) => {
    setCustomOrigin({
      lat: lm.lat,
      lng: lm.lng,
      name: lm.name,
    })
  }, [])

  // Đặt lại điểm xuất phát về tâm khu vực đang chọn
  const handleResetHubOrigin = useCallback(() => {
    setCustomOrigin(null)
  }, [])

  // Bật/tắt chế độ chỉ đường
  const handleToggleRouting = () => {
    setIsRoutingActive((prev) => {
      if (prev) {
        setRouteData(null)
        setRouteError(null)
      }
      return !prev
    })
  }

  const handleCloseRouting = () => {
    setIsRoutingActive(false)
    setRouteData(null)
    setRouteError(null)
  }

  // Tự động tính toán lộ trình OSRM khi chế độ chỉ đường bật hoặc đổi quán/phương tiện
  useEffect(() => {
    if (!isRoutingActive || !currentVideo) return

    let isCancelled = false
    queueMicrotask(() => {
      if (!isCancelled) {
        setIsRouteLoading(true)
        setRouteError(null)
      }
    })

    const destPoint: RoutePoint = {
      lat: currentVideo.lat,
      lng: currentVideo.lng,
      name: currentVideo.locationName || currentVideo.title,
    }

    getRouteDirections(routeOrigin, destPoint, routeVehicle)
      .then((res) => {
        if (!isCancelled) {
          setRouteData(res)
          setIsRouteLoading(false)
        }
      })
      .catch((err: any) => {
        if (!isCancelled) {
          setRouteError(err?.message || 'Không thể kết nối máy chủ chỉ đường OSRM.')
          setIsRouteLoading(false)
        }
      })

    return () => {
      isCancelled = true
    }
  }, [isRoutingActive, currentVideo, routeOrigin, routeVehicle])

  const { toast, showToast } = useToast()

  // Tải danh sách video và quán ăn thật từ PostGIS qua API /places/nearby-videos
  const loadNearbyVideos = useCallback(
    async (lat: number, lon: number, radiusKm: number) => {
      try {
        const items = await placesApi.getNearbyVideos({
          lat,
          lon,
          radius_m: radiusKm * 1000,
          limit: 50,
        })

        if (items && items.length > 0) {
          const mapped = items.map(mapNearbyItemToPlaylist)
          setPlaylist(mapped)
          setCurrentIndex(0)
          setCurrentVideo(mapped[0])
          setInputValue(mapped[0].url)
          setTargetLocation({ lat: mapped[0].lat, lng: mapped[0].lng })
          showToast(
            'success',
            'Đã tải dữ liệu PostGIS',
            `Tìm thấy ${mapped.length} quán ăn và video review thật quanh đây.`,
          )
        }
      } catch (err: unknown) {
        console.warn('Lỗi khi tải nearby-videos từ backend:', err)
      }
    },
    [showToast],
  )

  useEffect(() => {
    loadNearbyVideos(currentHub.lat, currentHub.lng, selectedRadius)
  }, [currentHub.lat, currentHub.lng, selectedRadius, loadNearbyVideos])

  // Lọc playlist theo chế độ: Toàn cầu thịnh hành HOẶC Quanh vị trí bán kính R km
  const activePlaylist = useMemo(() => {
    if (filterMode === 'trending') {
      return playlist
    }
    return filterVideosByRadius(playlist, currentHub.lat, currentHub.lng, selectedRadius)
  }, [playlist, filterMode, currentHub, selectedRadius])

  // Đồng bộ video đang phát khi activePlaylist thay đổi
  useEffect(() => {
    if (activePlaylist.length > 0 && !activePlaylist.some((p) => p.id === currentVideo?.id)) {
      const first = activePlaylist[0]
      setCurrentIndex(0)
      setCurrentVideo(first)
      setInputValue(first.url)
      setTargetLocation({ lat: first.lat, lng: first.lng })
    }
  }, [activePlaylist, currentVideo?.id])

  // Chuyển video theo vị trí trong playlist đang lọc
  const playVideoByIndex = useCallback(
    (index: number) => {
      if (activePlaylist.length === 0) return
      const nextIndex = (index + activePlaylist.length) % activePlaylist.length
      const item = activePlaylist[nextIndex]
      setCurrentIndex(nextIndex)
      setCurrentVideo(item)
      setInputValue(item.url)
      setTargetLocation({ lat: item.lat, lng: item.lng })
      setHasError(false)
    },
    [activePlaylist],
  )

  // Đồng bộ và nhảy đến video/tọa độ tương ứng khi điều hướng từ Trang chủ
  const location = useLocation()
  const handledKeyRef = useRef<string | number | null>(null)

  useEffect(() => {
    const searchParams = new URLSearchParams(location.search)
    const stateObj = location.state as {
      targetVideoId?: string
      lat?: number
      lng?: number
      fromCloudTransition?: boolean
      transitionTimestamp?: number
    } | null

    const targetVid = searchParams.get('vid') || stateObj?.targetVideoId
    const incomingKey = stateObj?.transitionTimestamp || targetVid || null

    if (targetVid && incomingKey !== handledKeyRef.current) {
      handledKeyRef.current = incomingKey

      const timer = setTimeout(() => {
        const foundIdx = activePlaylist.findIndex((item) => item.id === targetVid)
        if (foundIdx !== -1) {
          playVideoByIndex(foundIdx)
          if (stateObj?.lat && stateObj?.lng) {
            setTargetLocation({ lat: stateObj.lat, lng: stateObj.lng })
          }
        } else {
          const foundGlobalIdx = playlist.findIndex((item) => item.id === targetVid)
          if (foundGlobalIdx !== -1) {
            setFilterMode('trending')
            const item = playlist[foundGlobalIdx]
            setCurrentIndex(foundGlobalIdx)
            setCurrentVideo(item)
            setInputValue(item.url)
            setTargetLocation({
              lat: stateObj?.lat ?? item.lat,
              lng: stateObj?.lng ?? item.lng,
            })
          }
        }
      }, 0)
      return () => clearTimeout(timer)
    }
  }, [location.search, location.state, activePlaylist, playlist, playVideoByIndex])

  // Vòng bán kính vẽ trên Leaflet map (chỉ hiện khi ở chế độ 'nearby')
  const radiusCircle = useMemo(() => {
    if (filterMode !== 'nearby') return null
    return {
      lat: currentHub.lat,
      lng: currentHub.lng,
      radiusKm: selectedRadius,
    }
  }, [filterMode, currentHub, selectedRadius])

  // Chuyển đổi giữa chế độ Nổi tiếng và Quanh đây
  const handleFilterModeChange = (mode: 'trending' | 'nearby') => {
    setFilterMode(mode)
    if (mode === 'trending') {
      showToast('info', 'Video Thịnh Hành', 'Đang hiển thị các video nổi tiếng đặc sắc nhất')
    } else {
      showToast(
        'info',
        'Quanh vị trí',
        `Đang quét trong bán kính ${selectedRadius} km quanh ${currentHub.name}`,
      )
    }
  }

  // Đổi bán kính km
  const handleRadiusChange = (km: number) => {
    setSelectedRadius(km)
    showToast('info', 'Thay đổi bán kính', `Bán kính quét: ${km} km quanh ${currentHub.name}`)
  }

  // Đổi thành phố / tâm vị trí
  const handleSelectHub = (hub: LocationHub) => {
    setCurrentHub(hub)
    showToast('info', 'Đổi khu vực', `Đã chuyển tâm điểm tới ${hub.name}`)
  }

  // Lấy vị trí GPS hiện tại của thiết bị
  const handleUseCurrentLocation = () => {
    if (!navigator.geolocation) {
      showToast('error', 'Không hỗ trợ GPS', 'Trình duyệt không hỗ trợ Geolocation.')
      return
    }
    setIsLocating(true)
    showToast('info', 'Đang định vị...', 'Đang lấy tọa độ GPS từ thiết bị của bạn')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setIsLocating(false)
        const userHub: LocationHub = {
          id: 'user-gps',
          name: 'Vị trí của bạn',
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          city: 'Vị trí hiện tại',
          icon: '📍',
        }
        setCurrentHub(userHub)
        setFilterMode('nearby')
        showToast(
          'success',
          'Định vị thành công',
          `Tọa độ: ${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`,
        )
      },
      () => {
        setIsLocating(false)
        showToast('info', 'Vị trí mặc định', 'Không thể lấy GPS, dùng mốc trung tâm Hà Nội.')
        setCurrentHub(POPULAR_HUBS[0])
        setFilterMode('nearby')
      },
      { timeout: 8000 },
    )
  }

  const activeWsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    return () => {
      if (activeWsRef.current) {
        activeWsRef.current.close()
        activeWsRef.current = null
      }
    }
  }, [])

  // Xử lý gửi link tìm kiếm / phân tích AI
  const handleSearchSubmit = async (url: string) => {
    const trimmed = url.trim()
    if (!trimmed) {
      setHasError(true)
      showToast('error', 'Chưa nhập liên kết', 'Vui lòng dán link video TikTok hoặc nhập Video ID.')
      return
    }

    const videoId = extractTikTokVideoId(trimmed)
    if (!videoId) {
      setHasError(true)
      showToast('error', 'Link không hợp lệ', 'Không nhận dạng được định dạng video TikTok hợp lệ.')
      return
    }

    // Kiểm tra xem đã có trong playlist chưa
    const existingIndex = playlist.findIndex((item) => item.id === videoId)
    if (existingIndex !== -1) {
      playVideoByIndex(existingIndex)
      showToast('info', 'Video đã có trên bản đồ', playlist[existingIndex].title)
      return
    }

    if (!token) {
      showToast(
        'info',
        'Yêu cầu đăng nhập',
        'Vui lòng đăng nhập tài khoản để gửi link video cho máy chủ AI phân tích!',
      )
      return
    }

    // Gửi yêu cầu phân tích video tới Backend FastAPI
    try {
      showToast('info', 'Đang gửi phân tích', 'Gửi link tới hàng đợi phân tích AI...')
      const submitRes = await videosApi.submitVideo({ video_url: trimmed })

      if (submitRes.cached) {
        showToast('success', 'Đã phân tích trước đó', 'Dữ liệu quán đã sẵn sàng trên hệ thống!')
        await loadNearbyVideos(currentHub.lat, currentHub.lng, selectedRadius)
        return
      }

      showToast(
        'info',
        'Đã vào hàng đợi AI',
        `Mã tiến trình: ${submitRes.analysis_run_id.slice(0, 8)}... (Đang chờ xử lý)`,
      )

      if (activeWsRef.current) {
        activeWsRef.current.close()
        activeWsRef.current = null
      }

      const ws = createAnalysisWebSocket(
        token,
        (msg: unknown) => {
          const wsMsg = msg as AnalysisWebSocketMessage
          if (wsMsg?.event === 'ANALYSIS_UPDATED' && wsMsg?.data) {
            const data = wsMsg.data
            if (data.analysis_run_id === submitRes.analysis_run_id) {
              if (data.status === 'PROCESSING') {
                showToast('info', 'AI đang xử lý', 'Máy chủ AI đang phân tích khung hình & OCR biển hiệu...')
              } else if (data.status === 'COMPLETED') {
                const rest = data.restaurant
                if (rest) {
                  const newItem: VideoPlaylistItem = {
                    id: videoId,
                    url: trimmed,
                    title: rest.name,
                    author: '@tiktok_creator',
                    locationName: rest.name,
                    lat: rest.latitude,
                    lng: rest.longitude,
                    gmapQuery: `${rest.name}, ${rest.address || ''}`,
                    category: 'Quán ăn',
                    icon: '🍜',
                    desc: rest.address || 'Địa chỉ được nhận diện từ video review ẩm thực.',
                    placeId: rest.id,
                  }
                  setPlaylist((prev) => [newItem, ...prev.filter((p) => p.id !== newItem.id)])
                  setCurrentIndex(0)
                  setCurrentVideo(newItem)
                  setTargetLocation({ lat: rest.latitude, lng: rest.longitude })
                  showToast('success', 'Nhận diện thành công!', `Đã ghim "${rest.name}" lên bản đồ.`)
                }
                ws.close()
                activeWsRef.current = null
              } else if (data.status === 'FAILED') {
                showToast('error', 'Phân tích thất bại', data.error_message || 'AI không nhận diện được quán.')
                ws.close()
                activeWsRef.current = null
              }
            }
          }
        },
        (err) => {
          console.warn('WS error:', err)
        },
        () => {
          activeWsRef.current = null
        },
      )
      activeWsRef.current = ws
    } catch (err: unknown) {
      showToast('error', 'Lỗi gửi phân tích', (err as Error)?.message || 'Không thể kết nối máy chủ.')
    }
  }

  // Đổi style bản đồ (Sáng / Tối) - Chuyển đổi trực tiếp, không hiện toast thừa
  const handleToggleTileStyle = () => {
    const nextStyle = tileStyle === 'dark' ? 'standard' : 'dark'
    setTileStyle(nextStyle)
  }

  // Chuyển Engine phát video
  const handleToggleEngine = () => {
    if (engine === 'mp4') {
      setEngine('v1')
      showToast('info', 'Trình phát TikTok', 'Chế độ Player v1 (Iframe chính thức)')
    } else if (engine === 'v1') {
      setEngine('v2')
      showToast('info', 'Trình phát TikTok', 'Chế độ Embed v2 (Iframe nhúng)')
    } else {
      setEngine('mp4')
      showToast('success', 'Trình phát TikTok', 'Chế độ .MP4 phần cứng 60 FPS (Đồng bộ màu trực tiếp)')
    }
  }

  // Bắt phím tắt toàn cục: ArrowUp, ArrowDown, Escape
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (document.activeElement?.tagName === 'INPUT') {
        if (e.key === 'Escape') {
          ;(document.activeElement as HTMLElement).blur()
        }
        return
      }

      if (e.key === 'ArrowUp') {
        e.preventDefault()
        playVideoByIndex(currentIndex - 1)
      } else if (e.key === 'ArrowDown') {
        e.preventDefault()
        playVideoByIndex(currentIndex + 1)
      } else if (e.key === 'Escape') {
        setDrawerMode(null)
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [currentIndex, playVideoByIndex])

  return (
    <div className="liquid-experience-root">
      {/* Background Interactive Map */}
      <LiquidMap
        center={[currentHub.lat, currentHub.lng]}
        tileStyle={tileStyle}
        targetLocation={targetLocation}
        locationName={currentVideo?.locationName}
        playlist={activePlaylist}
        onSelectPlaylistItem={(idx) => playVideoByIndex(idx)}
        radiusCircle={radiusCircle}
        fromCloudTransition={Boolean(
          (location.state as { fromCloudTransition?: boolean } | null)?.fromCloudTransition,
        )}
        transitionTimestamp={
          (location.state as { transitionTimestamp?: number } | null)?.transitionTimestamp
        }
        routeData={isRoutingActive ? routeData : null}
        routeOrigin={isRoutingActive ? routeOrigin : null}
        onSelectOrigin={handleSelectOrigin}
      />

      {/* Thẻ Lộ trình & Đo thời gian OSRM (Hiển thị khi bật chỉ đường) */}
      {isRoutingActive && currentVideo && (
        <LiquidRouteCard
          routeData={routeData}
          isLoading={isRouteLoading}
          error={routeError}
          origin={routeOrigin}
          destination={{
            lat: currentVideo.lat,
            lng: currentVideo.lng,
            name: currentVideo.locationName || currentVideo.title,
          }}
          vehicle={routeVehicle}
          onChangeVehicle={(v) => setRouteVehicle(v)}
          landmarks={currentLandmarks}
          onSelectLandmark={handleSelectLandmark}
          onResetHubOrigin={handleResetHubOrigin}
          onClose={handleCloseRouting}
        />
      )}

      {/* Cụm công cụ Sáng/Tối & Đo FPS đưa xuống dưới (dịch sang trái không bị điện thoại che) */}
      <BottomUtilityBar
        tileStyle={tileStyle}
        onToggleTileStyle={handleToggleTileStyle}
      />

      {/* Left Dock */}
      <LeftFloatingDock onOpenDrawer={(mode) => setDrawerMode(mode)} />

      {/* Slide-in Drawer */}
      <LiquidDrawer
        mode={drawerMode}
        playlist={activePlaylist}
        onClose={() => setDrawerMode(null)}
        onSelectPlaylistItem={(idx) => playVideoByIndex(idx)}
        onSelectLocation={(lat, lng, name) => {
          setTargetLocation({ lat, lng })
          if (name) showToast('info', 'Bay tới quán', name)
        }}
      />

      {/* Controls Area (Bottom-Left) */}
      <ControlsArea
        inputValue={inputValue}
        onInputChange={(val) => {
          setInputValue(val)
          if (hasError) setHasError(false)
        }}
        onSubmit={handleSearchSubmit}
        hasError={hasError}
        filterMode={filterMode}
        onFilterModeChange={handleFilterModeChange}
        selectedRadius={selectedRadius}
        onRadiusChange={handleRadiusChange}
        currentHub={currentHub}
        onSelectHub={handleSelectHub}
        onUseCurrentLocation={handleUseCurrentLocation}
        isLocating={isLocating}
        matchedCount={activePlaylist.length}
      />

      {/* Video Display Area (Right Side 9:16 Frame) */}
      <LiquidVideoPlayer
        currentVideo={currentVideo}
        isActive={isActive}
        engine={engine}
        onToggleEngine={handleToggleEngine}
        onRefresh={() => {
          if (currentVideo) {
            showToast('info', 'Tải lại', `Đang tải lại video: ${currentVideo.title}`)
          }
        }}
        onPrevVideo={() => playVideoByIndex(currentIndex - 1)}
        onNextVideo={() => playVideoByIndex(currentIndex + 1)}
        playlist={activePlaylist}
        currentIndex={currentIndex}
        isRoutingActive={isRoutingActive}
        onToggleRouting={handleToggleRouting}
      />

      {/* Toast Notification */}
      <LiquidToast toast={toast} />
    </div>
  )
}


