import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import type { VideoPlaylistItem } from './types'
import type { RoutePoint, RouteResult } from './routingService'

interface LiquidMapProps {
  center?: [number, number]
  zoom?: number
  tileStyle: 'dark' | 'standard'
  targetLocation?: { lat: number; lng: number } | null
  locationName?: string
  playlist?: VideoPlaylistItem[]
  onSelectPlaylistItem?: (index: number) => void
  radiusCircle?: {
    lat: number
    lng: number
    radiusKm: number
  } | null
  fromCloudTransition?: boolean
  transitionTimestamp?: number
  routeData?: RouteResult | null
  routeOrigin?: RoutePoint | null
  onStartRouting?: (item: VideoPlaylistItem) => void
  onSelectOrigin?: (point: RoutePoint) => void
}

export default function LiquidMap({
  center = [16.0678, 108.2208], // Default Đà Nẵng / Việt Nam
  zoom = 14.5,
  tileStyle,
  targetLocation,
  locationName,
  playlist = [],
  onSelectPlaylistItem,
  radiusCircle = null,
  fromCloudTransition = false,
  transitionTimestamp,
  routeData = null,
  routeOrigin = null,
  onStartRouting: _onStartRouting,
  onSelectOrigin,
}: LiquidMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<L.Map | null>(null)
  const tileLayerRef = useRef<L.TileLayer | null>(null)
  const markersLayerRef = useRef<L.LayerGroup | null>(null)
  const radiusLayerRef = useRef<L.LayerGroup | null>(null)
  const routeLayerRef = useRef<L.LayerGroup | null>(null)
  const initialCenterRef = useRef<[number, number]>(
    targetLocation ? [targetLocation.lat, targetLocation.lng] : center,
  )
  const initialZoomRef = useRef(zoom)

  // Quản lý hiển thị các nút địa điểm:
  // Nếu đến từ chuyển cảnh mây thì ban đầu không hiện sẵn,
  // chỉ khi mây tan ra tầm 50% màn hình thì mới bắt đầu bật hiển thị và nhảy lên
  const [prevTimestamp, setPrevTimestamp] = useState<number | undefined>(transitionTimestamp)
  const [markersVisible, setMarkersVisible] = useState<boolean>(() => !fromCloudTransition)
  const hasEntranceAnimationPlayedRef = useRef(false)
  const lastHandledTransitionRef = useRef<number | undefined>(undefined)

  if (transitionTimestamp !== prevTimestamp) {
    setPrevTimestamp(transitionTimestamp)
    if (fromCloudTransition) {
      setMarkersVisible(false)
    }
  }

  useEffect(() => {
    if (!fromCloudTransition) return
    hasEntranceAnimationPlayedRef.current = false

    // Lắng nghe sự kiện mây tan ra tầm 50% từ CloudTransitionOverlay
    const handleHalfway = () => {
      setMarkersVisible(true)
    }

    window.addEventListener('cloud-uncover-halfway', handleHalfway)

    // Fallback an toàn phòng khi event bị trễ hoặc lỡ: ~1100ms sau khi chuyển trang
    const fallbackTimer = setTimeout(() => {
      setMarkersVisible(true)
    }, 1100)

    return () => {
      window.removeEventListener('cloud-uncover-halfway', handleHalfway)
      clearTimeout(fallbackTimer)
    }
  }, [fromCloudTransition, transitionTimestamp])

  // Điều hướng bản đồ:
  // - Khi chuyển từ trang Danh sách quán sang (transitionTimestamp mới): setView tọa độ mục tiêu dưới tầng mây
  // - Khi đã ở trong map và nhấn đổi điểm: chỉ lướt nhẹ panTo, tuyệt đối không nhảy zoom lại
  // - Nếu đang bật vẽ lộ trình OSRM thì nhường việc căn góc nhìn cho route fitBounds
  useEffect(() => {
    const map = mapInstanceRef.current
    if (!map || !targetLocation) return

    if (routeData) return

    if (transitionTimestamp && transitionTimestamp !== lastHandledTransitionRef.current) {
      lastHandledTransitionRef.current = transitionTimestamp
      map.setView([targetLocation.lat, targetLocation.lng], 14.5)
    } else {
      map.panTo([targetLocation.lat, targetLocation.lng], { animate: true, duration: 0.5 })
    }
  }, [transitionTimestamp, targetLocation, routeData])

  const cartoApiKey = import.meta.env.VITE_CARTO_API_KEY

  // Khởi tạo Leaflet Map
  useEffect(() => {
    if (!containerRef.current || mapInstanceRef.current) return

    const map = L.map(containerRef.current, {
      center: initialCenterRef.current,
      zoom: initialZoomRef.current,
      zoomControl: false,
      attributionControl: false,
      zoomSnap: 0.5,
      zoomDelta: 0.5,
      maxZoom: 20,
    })

    L.control
      .zoom({
        position: 'bottomright',
      })
      .addTo(map)

    const markersGroup = L.layerGroup().addTo(map)
    markersLayerRef.current = markersGroup
    const radiusGroup = L.layerGroup().addTo(map)
    radiusLayerRef.current = radiusGroup
    const routeGroup = L.layerGroup().addTo(map)
    routeLayerRef.current = routeGroup
    mapInstanceRef.current = map

    const handleResize = () => {
      map.invalidateSize()
    }
    const onLocationChange = () => {
      setTimeout(() => map.invalidateSize(), 450)
    }
    window.addEventListener('resize', handleResize)
    window.addEventListener('popstate', onLocationChange)
    const timer = setTimeout(() => {
      map.invalidateSize()
    }, 450)

    return () => {
      window.removeEventListener('resize', handleResize)
      window.removeEventListener('popstate', onLocationChange)
      clearTimeout(timer)
      map.remove()
      mapInstanceRef.current = null
      markersLayerRef.current = null
      radiusLayerRef.current = null
      routeLayerRef.current = null
    }
  }, [])

  // Cập nhật tile layer (Dark / Standard)
  // ĐẶC BIỆT: Khắc phục lỗi màn hình trắng khi zoom gần:
  // Carto tiles chỉ hỗ trợ native zoom đến 18 (zoom 19+ trả về 403 Forbidden).
  // Đặt maxNativeZoom: 18 và maxZoom: 20 để Leaflet tự động phóng to mượt mà không bị trắng màn hình.
  useEffect(() => {
    const map = mapInstanceRef.current
    if (!map) return

    if (tileLayerRef.current) {
      map.removeLayer(tileLayerRef.current)
    }

    if (tileStyle === 'standard') {
      // Bản đồ màu sáng tiêu chuẩn giống trang chủ (Carto Voyager)
      if (cartoApiKey) {
        tileLayerRef.current = L.tileLayer(
          `https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=${cartoApiKey}`,
          {
            subdomains: 'abcd',
            maxNativeZoom: 18,
            maxZoom: 20,
          },
        ).addTo(map)
      } else {
        tileLayerRef.current = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxNativeZoom: 19,
          maxZoom: 20,
        }).addTo(map)
      }
    } else {
      // Bản đồ Dark Mode đồng bộ tone Forest Night
      if (cartoApiKey) {
        tileLayerRef.current = L.tileLayer(
          `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png?key=${cartoApiKey}`,
          {
            subdomains: 'abcd',
            maxNativeZoom: 18,
            maxZoom: 20,
          },
        ).addTo(map)
      } else {
        // Fallback OpenStreetMap với CSS Dark Filter
        tileLayerRef.current = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxNativeZoom: 19,
          maxZoom: 20,
        }).addTo(map)
      }
    }
  }, [tileStyle, cartoApiKey])

  // Cập nhật Markers trên bản đồ đồng bộ phong cách Food Spot
  useEffect(() => {
    const map = mapInstanceRef.current
    const markersGroup = markersLayerRef.current
    if (!map || !markersGroup) return

    markersGroup.clearLayers()

    // Nếu đang trong quá trình chuyển mây, các nút địa điểm ban đầu chưa hiện
    // Chỉ khi mây tan tầm 50% thì markersVisible bật true và các địa điểm nhảy lên
    if (!markersVisible) {
      return
    }

    // 1. Thêm các markers từ playlist (màu xanh lá/matcha)
    // Chỉ nhảy lên (bounce) ở lần đầu tiên vào map từ mây; khi đang ở trong map thì giữ tĩnh (static)
    const isInitialEntrance = !hasEntranceAnimationPlayedRef.current
    if (markersVisible && !hasEntranceAnimationPlayedRef.current) {
      hasEntranceAnimationPlayedRef.current = true
    }

    playlist.forEach((item, index) => {
      const isActive =
        targetLocation &&
        Math.abs(item.lat - targetLocation.lat) < 0.0001 &&
        Math.abs(item.lng - targetLocation.lng) < 0.0001

      if (!isActive) {
        const wrapperClass = isInitialEntrance ? 'foodspot-marker-bounce' : 'foodspot-marker-static'
        const delayStyle = isInitialEntrance
          ? `style="animation-delay: ${(0.04 + index * 0.04).toFixed(2)}s;"`
          : ''

        const spotIcon = L.divIcon({
          className: 'foodspot-marker-container',
          html: `
            <div class="${wrapperClass}" ${delayStyle}>
              <div class="foodspot-marker-pin" style="background: #2f4b36;">
                <span style="position: absolute; font-size: 11px; transform: rotate(45deg);">${item.icon || '📍'}</span>
              </div>
            </div>
          `,
          iconSize: [30, 30],
          iconAnchor: [15, 30],
          popupAnchor: [0, -30],
        })

        const marker = L.marker([item.lat, item.lng], { icon: spotIcon })
        marker.bindPopup(`
          <div style="font-family: system-ui; padding: 4px;">
            <strong style="color: #235c42; font-size: 13px;">${item.locationName}</strong>
            <p style="margin: 4px 0 0; font-size: 12px; color: #555;">${item.desc || item.title}</p>
          </div>
        `)
        if (onSelectPlaylistItem) {
          marker.on('click', () => onSelectPlaylistItem(index))
        }
        markersGroup.addLayer(marker)
      }
    })

    // 2. Thêm Active Target Marker (Ánh xanh cyan rực rỡ đặc trưng theo yêu cầu)
    if (targetLocation) {
      const activeWrapperClass = isInitialEntrance ? 'foodspot-marker-bounce' : 'foodspot-marker-active-pulse'
      const activeDelayStyle = isInitialEntrance ? 'style="animation-delay: 0.16s;"' : ''

      const activeIcon = L.divIcon({
        className: 'foodspot-marker-container is-active-container',
        html: `
          <div class="${activeWrapperClass}" ${activeDelayStyle}>
            <div class="foodspot-marker-cyan-glow"></div>
            <div class="foodspot-marker-pulse is-cyan"></div>
            <div class="foodspot-marker-pin is-active is-cyan">
              <span style="position: absolute; font-size: 12px; transform: rotate(45deg);">🍜</span>
            </div>
          </div>
        `,
        iconSize: [36, 36],
        iconAnchor: [18, 36],
        popupAnchor: [0, -36],
      })

      const targetMarker = L.marker([targetLocation.lat, targetLocation.lng], {
        icon: activeIcon,
        zIndexOffset: 1000,
      })

      if (locationName) {
        targetMarker.bindPopup(`
          <div style="font-family: system-ui; padding: 6px;">
            <span style="display:inline-block; font-size: 10px; font-weight:700; color:#0891b2; text-transform:uppercase; letter-spacing:1px;">ĐIỂM ĐANG CHỌN</span>
            <h4 style="margin: 2px 0 4px; color: #0e7490; font-size: 14px;">${locationName}</h4>
            <span style="font-size: 11px; color: #666;">Bấm video bên phải để xem review</span>
          </div>
        `)
      }

      markersGroup.addLayer(targetMarker)
    }
  }, [playlist, targetLocation, locationName, onSelectPlaylistItem, markersVisible])

  // Vẽ vòng tròn bán kính quét radar khi ở chế độ khám phá quanh vị trí
  useEffect(() => {
    const map = mapInstanceRef.current
    const radiusGroup = radiusLayerRef.current
    if (!map || !radiusGroup) return

    radiusGroup.clearLayers()

    if (radiusCircle) {
      // Vòng tròn bán kính Leaflet (đơn vị meters = radiusKm * 1000)
      const circle = L.circle([radiusCircle.lat, radiusCircle.lng], {
        radius: radiusCircle.radiusKm * 1000,
        color: '#2e7d32',
        weight: 1.5,
        fillColor: '#4ade80',
        fillOpacity: 0.08,
        dashArray: '6, 6',
      })
      radiusGroup.addLayer(circle)

      // Marker tâm bán kính (Vị trí đang đứng)
      const centerPin = L.divIcon({
        className: 'center-hub-pin-container',
        html: `
          <div class="center-hub-beacon"></div>
          <div class="center-hub-pin">📍</div>
        `,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      })
      const centerMarker = L.marker([radiusCircle.lat, radiusCircle.lng], {
        icon: centerPin,
        zIndexOffset: 500,
      }).bindPopup(`
        <div style="font-family: system-ui; padding: 4px;">
          <strong style="color: #1b4332;">📍 Vị trí tâm bán kính</strong>
          <p style="margin: 2px 0 0; font-size: 11px; color: #555;">Bán kính quét: ${radiusCircle.radiusKm} km</p>
        </div>
      `)
      radiusGroup.addLayer(centerMarker)
    }
  }, [radiusCircle])

  // Fly to targetLocation với tốc độ nhanh chóng, dứt khoát khi lướt video (chỉ khi không bật chỉ đường)
  const isFirstRenderRef = useRef(true)
  useEffect(() => {
    const map = mapInstanceRef.current
    if (!map || !targetLocation || routeData) return

    if (isFirstRenderRef.current) {
      isFirstRenderRef.current = false
      return
    }

    try {
      map.flyTo([targetLocation.lat, targetLocation.lng], 14.5, {
        duration: 0.75, // Lướt nhanh dứt khoát trong 750ms
        easeLinearity: 0.3,
      })
    } catch (e) {
      console.warn('Map fly error:', e)
    }
  }, [targetLocation, routeData])

  // Lắng nghe sự kiện click trên bản đồ khi đang bật chỉ đường để cho phép người dùng chấm điểm xuất phát tùy thích
  useEffect(() => {
    const map = mapInstanceRef.current
    if (!map || !routeOrigin || !onSelectOrigin) return

    const handleMapClick = (e: L.LeafletMouseEvent) => {
      onSelectOrigin({
        lat: e.latlng.lat,
        lng: e.latlng.lng,
        name: 'Vị trí bạn đã chấm trên bản đồ',
      })
    }

    map.on('click', handleMapClick)
    return () => {
      map.off('click', handleMapClick)
    }
  }, [routeOrigin, onSelectOrigin])

  // Vẽ lộ trình đường đi OSRM và điểm xuất phát
  useEffect(() => {
    const map = mapInstanceRef.current
    const routeGroup = routeLayerRef.current
    if (!map || !routeGroup) return

    routeGroup.clearLayers()

    if (!routeData || !routeOrigin) return

    // 1. Thêm Chấm định vị Vị trí xuất phát (glowing pulse beacon kèm label rõ ràng & kéo thả được)
    const originPin = L.divIcon({
      className: 'route-origin-marker-container',
      html: `
        <div class="route-origin-badge">🚩 Vị trí của bạn (Kéo hoặc click map để đổi)</div>
        <div class="route-origin-beacon"></div>
        <div class="route-origin-pin">🧭</div>
      `,
      iconSize: [36, 36],
      iconAnchor: [18, 18],
      popupAnchor: [0, -18],
    })

    const originMarker = L.marker([routeOrigin.lat, routeOrigin.lng], {
      icon: originPin,
      draggable: true,
      zIndexOffset: 950,
    }).bindPopup(`
      <div style="font-family: system-ui; padding: 6px;">
        <span style="font-size: 10px; font-weight:700; color:#0891b2; text-transform:uppercase;">ĐIỂM XUẤT PHÁT</span>
        <strong style="display:block; color: #155e75; font-size: 13px; margin: 2px 0;">${routeOrigin.name || 'Vị trí của bạn'}</strong>
        <p style="margin: 4px 0 0; font-size: 11px; color: #666;">💡 Bạn có thể kéo icon la bàn này hoặc click bất kỳ đâu trên bản đồ để dời điểm đi.</p>
      </div>
    `)

    originMarker.on('dragend', (e) => {
      const newLatLng = (e.target as L.Marker).getLatLng()
      onSelectOrigin?.({
        lat: newLatLng.lat,
        lng: newLatLng.lng,
        name: 'Vị trí bạn đã kéo thả trên bản đồ',
      })
    })

    routeGroup.addLayer(originMarker)

    // 2. Thêm đường vẽ lộ trình: Outer Casing (ánh sáng mờ trắng/cyan) + Core Line (cyan rực rỡ)
    if (routeData.coordinates && routeData.coordinates.length > 1) {
      const casing = L.polyline(routeData.coordinates, {
        color: '#ffffff',
        weight: 8,
        opacity: 0.65,
        lineCap: 'round',
        lineJoin: 'round',
      })
      routeGroup.addLayer(casing)

      const core = L.polyline(routeData.coordinates, {
        color: '#0891b2',
        weight: 4.5,
        opacity: 0.95,
        dashArray: routeData.vehicle === 'foot' ? '6, 8' : undefined,
        lineCap: 'round',
        lineJoin: 'round',
        className: 'foodspot-route-core-line',
      })
      routeGroup.addLayer(core)

      // Căn chỉnh khung nhìn thông minh: Chừa khoảng trống bên phải cho khung điện thoại TikTok
      const bounds = L.latLngBounds(routeData.coordinates)
      map.fitBounds(bounds, {
        paddingTopLeft: [75, 75],
        paddingBottomRight: [window.innerWidth > 900 ? 400 : 40, 75],
        maxZoom: 16,
        animate: true,
        duration: 0.8,
      })
    }
  }, [routeData, routeOrigin, onSelectOrigin])

  const isUsingCssDarkFilter = tileStyle === 'dark' && !cartoApiKey

  return (
    <>
      <div
        ref={containerRef}
        className={`map-background-container ${isUsingCssDarkFilter ? 'map-dark-tiles' : ''}`}
      />
      <div className={`map-dark-overlay ${tileStyle === 'dark' ? 'subtle' : ''}`} />
    </>
  )
}
