import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import './liquid-glass.css'
import type { DrawerMode, EngineType, SavedFoodSpotItem, VideoPlaylistItem } from './types'
import {
  PRESET_PLAYLIST,
  extractTikTokVideoId,
} from './mockData'
import { useToast } from './hooks/useToast'
import LiquidMap from './LiquidMap'
import LeftFloatingDock from './LeftFloatingDock'
import LiquidDrawer, { type SavedPlaceItem } from './LiquidDrawer'
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
import { authApi, placesApi, savedApi, videosApi } from '../../services/api'
import type { PlaceResponse } from '../../types/api'

const SAVED_SPOTS_STORAGE_KEY = 'foodspot_saved_spots_v1'

const INITIAL_SAVED_SPOTS: SavedFoodSpotItem[] = [
  {
    id: PRESET_PLAYLIST[0].id,
    savedAt: new Date().toISOString(),
    title: PRESET_PLAYLIST[0].title,
    locationName: PRESET_PLAYLIST[0].locationName,
    lat: PRESET_PLAYLIST[0].lat,
    lng: PRESET_PLAYLIST[0].lng,
    category: PRESET_PLAYLIST[0].category,
    icon: PRESET_PLAYLIST[0].icon,
    desc: PRESET_PLAYLIST[0].desc,
    url: PRESET_PLAYLIST[0].url,
    mp4Url: PRESET_PLAYLIST[0].mp4Url,
    author: PRESET_PLAYLIST[0].author,
  },
  {
    id: PRESET_PLAYLIST[1].id,
    savedAt: new Date().toISOString(),
    title: PRESET_PLAYLIST[1].title,
    locationName: PRESET_PLAYLIST[1].locationName,
    lat: PRESET_PLAYLIST[1].lat,
    lng: PRESET_PLAYLIST[1].lng,
    category: PRESET_PLAYLIST[1].category,
    icon: PRESET_PLAYLIST[1].icon,
    desc: PRESET_PLAYLIST[1].desc,
    url: PRESET_PLAYLIST[1].url,
    mp4Url: PRESET_PLAYLIST[1].mp4Url,
    author: PRESET_PLAYLIST[1].author,
  },
]

interface LiquidGlassExperienceProps {
  isActive?: boolean
}

export default function LiquidGlassExperience({ isActive = true }: LiquidGlassExperienceProps) {
  const navigate = useNavigate()
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

  // Lọc playlist theo chế độ: Toàn cầu thịnh hành HOẶC Quanh vị trí bán kính R km
  const activePlaylist = useMemo(() => {
    if (filterMode === 'trending') {
      return playlist
    }
    return filterVideosByRadius(playlist, currentHub.lat, currentHub.lng, selectedRadius)
  }, [playlist, filterMode, currentHub, selectedRadius])

  // Đồng bộ video đang phát khi activePlaylist thay đổi mà không gây cascading render
  if (activePlaylist.length > 0 && !activePlaylist.some((p) => p.id === currentVideo?.id)) {
    const first = activePlaylist[0]
    setCurrentIndex(0)
    setCurrentVideo(first)
    setInputValue(first.url)
    setTargetLocation({ lat: first.lat, lng: first.lng })
  }

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

  // ============================================================================
  // Bộ Sưu Tập Món & Quán Đã Lưu (Hợp nhất Video + Địa điểm)
  // ============================================================================
  const [savedSpots, setSavedSpots] = useState<SavedFoodSpotItem[]>(() => {
    try {
      const stored = localStorage.getItem(SAVED_SPOTS_STORAGE_KEY)
      if (stored) {
        return JSON.parse(stored)
      }
    } catch {
      // ignore
    }
    return INITIAL_SAVED_SPOTS
  })

  // Lưu danh sách vào localStorage để duy trì trạng thái mượt mà
  useEffect(() => {
    try {
      localStorage.setItem(SAVED_SPOTS_STORAGE_KEY, JSON.stringify(savedSpots))
    } catch {
      // ignore
    }
  }, [savedSpots])

  // Video hiện tại đã được lưu trong bộ sưu tập hay chưa
  const isCurrentVideoSaved = useMemo(() => {
    if (!currentVideo) return false
    return savedSpots.some(
      (s) => s.id === currentVideo.id || (s.url && s.url === currentVideo.url),
    )
  }, [currentVideo, savedSpots])

  // Thao tác Lưu / Bỏ lưu Video (Video vốn luôn liên kết với Địa điểm quán ăn)
  const handleToggleSaveCurrent = useCallback(() => {
    if (!currentVideo) return

    const existingIndex = savedSpots.findIndex(
      (s) => s.id === currentVideo.id || (s.url && s.url === currentVideo.url),
    )

    if (existingIndex >= 0) {
      const updated = savedSpots.filter((_, idx) => idx !== existingIndex)
      setSavedSpots(updated)
      showToast(
        'info',
        'Đã bỏ lưu',
        `Đã gỡ video "${currentVideo.locationName || currentVideo.title}" khỏi Bộ sưu tập`,
      )
      // Chỉ lưu video, không cần lưu quán riêng
      savedApi.toggleSaveVideo(currentVideo.id, true).catch(() => {})
    } else {
      const newSpot: SavedFoodSpotItem = {
        id: currentVideo.id,
        savedAt: new Date().toISOString(),
        title: currentVideo.title,
        locationName: currentVideo.locationName || currentVideo.title,
        lat: currentVideo.lat,
        lng: currentVideo.lng,
        category: currentVideo.category,
        icon: currentVideo.icon,
        desc: currentVideo.desc,
        url: currentVideo.url,
        mp4Url: currentVideo.mp4Url,
        author: currentVideo.author,
      }
      setSavedSpots([newSpot, ...savedSpots])
      showToast(
        'success',
        'Đã lưu video',
        `Đã lưu video review kèm địa điểm "${currentVideo.locationName}"!`,
      )
      // Chỉ lưu video, không cần lưu quán riêng
      savedApi.toggleSaveVideo(currentVideo.id, false).catch(() => {})
    }
  }, [currentVideo, savedSpots, showToast])

  // Bỏ lưu trực tiếp video từ trong Drawer
  const handleUnsaveSpot = useCallback(
    (spotId: string) => {
      setSavedSpots((prev) => {
        const target = prev.find((s) => s.id === spotId)
        const filtered = prev.filter((s) => s.id !== spotId)
        if (target) {
          showToast('info', 'Đã bỏ lưu', `Đã gỡ "${target.title}" khỏi danh sách`)
          savedApi.toggleSaveVideo(spotId, true).catch(() => {})
        }
        return filtered
      })
    },
    [showToast],
  )

  // Chọn video từ Drawer: Bay tới tọa độ và phát video
  const handleSelectSavedSpot = useCallback(
    (spot: SavedFoodSpotItem) => {
      const foundIdx = activePlaylist.findIndex(
        (item) => item.id === spot.id || (spot.url && item.url === spot.url),
      )
      if (foundIdx >= 0) {
        playVideoByIndex(foundIdx)
      } else {
        setTargetLocation({ lat: spot.lat, lng: spot.lng })
      }
    },
    [activePlaylist, playVideoByIndex],
  )

  // Chọn địa điểm quán ăn từ Drawer (Option 2): Bay camera tới quán và phát video review tương ứng
  const handleSelectSavedPlace = useCallback(
    (place: SavedPlaceItem) => {
      setTargetLocation({ lat: place.lat, lng: place.lng })
      if (place.videos && place.videos.length > 0) {
        const firstVid = place.videos[0]
        const foundIdx = activePlaylist.findIndex(
          (item) => item.id === firstVid.id || (firstVid.url && item.url === firstVid.url),
        )
        if (foundIdx >= 0) {
          playVideoByIndex(foundIdx)
        }
      }
    },
    [activePlaylist, playVideoByIndex],
  )

  // ============================================================================
  // TẢI DỮ LIỆU THẬT TỪ BACKEND (/places và /saved/videos)
  // ============================================================================
  // 1. Tải danh sách địa điểm thật từ Backend
  useEffect(() => {
    let isCancelled = false
    async function loadPlacesFromBackend() {
      try {
        const places = await placesApi.getPlaces({ limit: 50 })
        if (!isCancelled && places && places.length > 0) {
          const validPlaces = places.filter(
            (p): p is typeof p & { latitude: number; longitude: number } =>
              typeof p.latitude === 'number' && typeof p.longitude === 'number',
          )
          if (validPlaces.length > 0) {
            const dynamicList: VideoPlaylistItem[] = validPlaces.map((p) => {
              const effectiveVideoId =
                p.platform_video_id || extractTikTokVideoId(p.video_url || '') || p.id
              const effectiveUrl =
                p.video_url || `https://www.tiktok.com/@foodspot/video/${effectiveVideoId}`
              return {
                id: effectiveVideoId,
                placeId: p.id,
                url: effectiveUrl,
                title: p.name,
                author: p.category || 'Food Spot Review',
                locationName: p.name,
                address: p.normalized_address || p.address || undefined,
                lat: p.latitude,
                lng: p.longitude,
                category: p.category || 'Món ngon',
                icon: '🍽️',
                desc: p.normalized_address || p.address || p.description || 'Địa điểm ẩm thực tuyển chọn',
                gmapQuery: `${p.name}, ${p.normalized_address || p.address || ''}`,
              }
            })
            setPlaylist(dynamicList)
            if (dynamicList.length > 0) {
              setCurrentVideo(dynamicList[0])
              setInputValue(dynamicList[0].url)
              setTargetLocation({ lat: dynamicList[0].lat, lng: dynamicList[0].lng })
            }
          }
        }
      } catch (err) {
        console.warn('Backend chưa có dữ liệu hoặc offline, sử dụng danh sách khởi tạo:', err)
      }
    }
    loadPlacesFromBackend()
    return () => {
      isCancelled = true
    }
  }, [])

  // 2. Tải danh sách video đã lưu từ Backend nếu đã đăng nhập
  useEffect(() => {
    let isCancelled = false
    async function loadSavedFromBackend() {
      if (!authApi.isAuthenticated()) return
      try {
        const res = await savedApi.getSavedVideos(50, 0)
        if (!isCancelled && Array.isArray(res) && res.length > 0) {
          const loaded: SavedFoodSpotItem[] = res.map((item) => ({
            id: item.video.id,
            savedAt: item.saved_at,
            title: item.video.title || item.video.caption || 'Video review',
            locationName: item.place?.name || 'Quán ăn',
            lat:
              typeof item.place?.latitude === 'number'
                ? item.place.latitude
                : currentHub.lat,
            lng:
              typeof item.place?.longitude === 'number'
                ? item.place.longitude
                : currentHub.lng,
            category: item.place?.category || 'Ẩm thực',
            icon: '🍜',
            desc: item.place?.address || item.video.caption || '',
            url: item.video.video_url,
            author: item.video.author_name || undefined,
            videoId: item.video.id,
            placeId: item.place?.id,
          }))
          setSavedSpots(loaded)
        }
      } catch (err) {
        console.warn('Chưa thể lấy saved videos từ backend:', err)
      }
    }
    loadSavedFromBackend()
    return () => {
      isCancelled = true
    }
  }, [currentHub.lat, currentHub.lng])

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

  // Xử lý gửi link tìm kiếm & trích xuất qua AI Server trên Colab
  const handleSearchSubmit = async (url: string) => {
    const trimmed = url.trim()
    if (!trimmed) {
      setHasError(true)
      showToast('error', 'Chưa nhập liên kết', 'Vui lòng dán link video TikTok hoặc YouTube Shorts.')
      return
    }

    // Chặn người dùng vãng lai - Bắt buộc đăng nhập để sử dụng tài nguyên AI
    if (!authApi.isAuthenticated()) {
      showToast(
        'error',
        'Yêu cầu đăng nhập 🔒',
        'Vui lòng đăng nhập tài khoản để gửi video phân tích AI và ghim quán ăn!',
      )
      setTimeout(() => {
        navigate('/login')
      }, 1200)
      return
    }

    const videoId = extractTikTokVideoId(trimmed) || `vid_${Date.now()}`

    // Kiểm tra xem đã có trong playlist chưa
    const existingIndex = playlist.findIndex((item) => item.id === videoId || item.url === trimmed)
    if (existingIndex !== -1) {
      playVideoByIndex(existingIndex)
      showToast('info', 'Địa điểm đã có trên bản đồ', `Đang xem: ${playlist[existingIndex].locationName}`)
      return
    }

    showToast(
      'info',
      'Đang gửi tới AI Server...',
      'Đang gửi video đến GPU AI Server để trích xuất OCR bảng hiệu và địa chỉ quán...',
    )

    try {
      // 1. Gửi video tới Backend API
      const submitRes = await videosApi.submitVideo({ video_url: trimmed })
      const runId = submitRes.analysis_run_id

      // 2. Polling kết quả phân tích từ Background Queue Worker
      let finalPlace: PlaceResponse | null = null
      let attempts = 0
      const maxAttempts = 20 // Tối đa ~40s cho GPU Colab

      while (attempts < maxAttempts) {
        await new Promise((r) => setTimeout(r, 2000))
        attempts++

        try {
          const statusRes = await videosApi.getAnalysisStatus(runId)
          if (statusRes.status === 'COMPLETED') {
            if (statusRes.result_place_id) {
              finalPlace = await placesApi.getPlaceDetail(statusRes.result_place_id)
            }
            break
          } else if (statusRes.status === 'FAILED') {
            throw new Error(statusRes.error_message || 'AI Server không trích xuất được địa chỉ từ video.')
          }
        } catch (pollErr: any) {
          if (pollErr?.message && pollErr.message.includes('AI Server không')) {
            throw pollErr
          }
        }
      }

      if (finalPlace && finalPlace.name) {
        const placeName = finalPlace.name
        const placeAddr = finalPlace.normalized_address || finalPlace.address || 'Chưa có địa chỉ chi tiết'
        const placeLat =
          typeof finalPlace.latitude === 'number'
            ? finalPlace.latitude
            : currentHub.lat + (Math.random() - 0.5) * 0.01
        const placeLng =
          typeof finalPlace.longitude === 'number'
            ? finalPlace.longitude
            : currentHub.lng + (Math.random() - 0.5) * 0.01

        const effectiveVideoId = finalPlace.platform_video_id || videoId

        const newItem: VideoPlaylistItem = {
          id: effectiveVideoId,
          placeId: finalPlace.id,
          url: trimmed,
          title: `Review ${placeName}`,
          author: finalPlace.category || '@foodspot',
          locationName: placeName,
          address: placeAddr,
          lat: placeLat,
          lng: placeLng,
          gmapQuery: `${placeName}, ${placeAddr}`,
          category: finalPlace.category || 'Món ngon',
          icon: '🍜',
          desc: placeAddr,
        }

        setPlaylist((prev) => [newItem, ...prev])
        setCurrentIndex(0)
        setCurrentVideo(newItem)
        setTargetLocation({ lat: newItem.lat, lng: newItem.lng })
        setHasError(false)
        showToast('success', 'Trích xuất thành công! 🎉', `Đã tìm thấy quán: ${placeName} (${placeAddr})`)
        return
      }

      // Fallback nếu AI chưa xác định được địa chỉ cụ thể
      throw new Error('AI Server chưa tìm thấy địa chỉ quán ăn rõ ràng trong video.')
    } catch (err: any) {
      console.warn('Lỗi phân tích video thật, dùng fallback tạm thời:', err)

      // Fallback vị trí gần tâm khu vực hiện tại nếu chưa chạy được AI
      const fallbackItem: VideoPlaylistItem = {
        id: videoId,
        url: trimmed,
        title: `TikTok Video #${videoId.slice(-4)}`,
        author: '@tiktok_creator',
        locationName: 'Địa điểm ẩm thực review',
        address: `${currentHub.name}, Việt Nam (Chờ AI cập nhật)`,
        lat: currentHub.lat + (Math.random() - 0.5) * 0.015,
        lng: currentHub.lng + (Math.random() - 0.5) * 0.015,
        gmapQuery: `${currentHub.name}, Vietnam`,
        category: 'Khám phá ẩm thực',
        icon: '🍜',
        desc: `${currentHub.name}, Việt Nam`,
      }

      setPlaylist((prev) => [fallbackItem, ...prev])
      setCurrentIndex(0)
      setCurrentVideo(fallbackItem)
      setTargetLocation({ lat: fallbackItem.lat, lng: fallbackItem.lng })
      setHasError(false)
      showToast(
        'info',
        'Đã thêm video vào bản đồ',
        err?.message || 'Video đã được đưa lên bản đồ để bạn trải nghiệm.',
      )
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
        selectedItem={currentVideo}
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
      <LeftFloatingDock
        onOpenDrawer={(mode) => setDrawerMode(mode)}
        savedCount={savedSpots.length}
      />

      {/* Slide-in Drawer */}
      <LiquidDrawer
        mode={drawerMode}
        playlist={activePlaylist}
        savedSpots={savedSpots}
        onClose={() => setDrawerMode(null)}
        onSelectPlaylistItem={(idx) => playVideoByIndex(idx)}
        onSelectSavedSpot={handleSelectSavedSpot}
        onSelectSavedPlace={handleSelectSavedPlace}
        onUnsaveSpot={handleUnsaveSpot}
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
        isSaved={isCurrentVideoSaved}
        onToggleSave={handleToggleSaveCurrent}
      />

      {/* Toast Notification */}
      <LiquidToast toast={toast} />
    </div>
  )
}


