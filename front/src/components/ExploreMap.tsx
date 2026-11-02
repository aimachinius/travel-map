import { useEffect, useState, type FormEvent } from 'react'
import L from 'leaflet'
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Circle,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './ExploreMap.css'

export type SearchCenter = {
  position: [number, number]
  label: string
}

export interface MapPlaceMarker {
  id: string
  name: string
  address: string | null
  latitude: number
  longitude: number
  category?: string | null
  is_saved?: boolean
}

interface ExploreMapProps {
  searchCenter: SearchCenter | null
  onSelectCenter: (position: [number, number], label: string) => void
  radius: number
  onRadiusChange: (radius: number) => void
  places?: MapPlaceMarker[]
  onSelectPlace?: (place: MapPlaceMarker) => void
}

const INITIAL_CENTER: [number, number] = [15.8801, 108.3380]

// Icon ghim quán ăn
const createPlaceIcon = (name: string) => {
  return L.divIcon({
    className: 'fs-custom-marker',
    html: `<div class="fs-marker-pin" title="${name}"><span>🍽️</span></div>`,
    iconSize: [34, 34],
    iconAnchor: [17, 34],
    popupAnchor: [0, -32],
  })
}

function MapClickHandler({
  onSelect,
}: {
  onSelect: (position: [number, number]) => void
}) {
  useMapEvents({
    click(event) {
      onSelect([event.latlng.lat, event.latlng.lng])
    },
  })

  return null
}

function MapController({
  center,
}: {
  center: [number, number] | null
}) {
  const map = useMap()

  useEffect(() => {
    if (center) {
      map.flyTo(center, Math.max(map.getZoom(), 13), {
        duration: 0.8,
      })
    }
  }, [center, map])

  return null
}

export default function ExploreMap({
  searchCenter,
  onSelectCenter,
  radius,
  onRadiusChange,
  places = [],
  onSelectPlace,
}: ExploreMapProps) {
  const [address, setAddress] = useState('')
  const [error, setError] = useState('')
  const [searching, setSearching] = useState(false)

  const handleCurrentLocation = () => {
    setError('')

    if (!navigator.geolocation) {
      setError('Trình duyệt của bạn không hỗ trợ định vị.')
      return
    }

    navigator.geolocation.getCurrentPosition(
      (result) => {
        onSelectCenter(
          [result.coords.latitude, result.coords.longitude],
          'Vị trí hiện tại của bạn',
        )
      },
      () => {
        setError(
          'Không lấy được vị trí. Hãy cấp quyền định vị hoặc chọn trực tiếp trên bản đồ.',
        )
      },
      {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 60000,
      },
    )
  }

  const handleAddressSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const keyword = address.trim()

    if (!keyword) {
      setError('Vui lòng nhập địa chỉ cần tìm.')
      return
    }

    setSearching(true)
    setError('')

    const withoutDiacritics = keyword
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/đ/g, 'd')
      .replace(/Đ/g, 'D')

    const queries = [
      keyword,
      `${keyword}, Việt Nam`,
      withoutDiacritics,
      `${withoutDiacritics}, Vietnam`,
    ].filter((query, index, all) => all.indexOf(query) === index)

    try {
      let foundResult: {
        lat: string
        lon: string
        display_name: string
      } | null = null

      for (const query of queries) {
        const params = new URLSearchParams({
          q: query,
          format: 'jsonv2',
          limit: '5',
          countrycodes: 'vn',
        })

        const response = await fetch(
          `https://nominatim.openstreetmap.org/search?${params.toString()}`,
        )

        if (!response.ok) {
          throw new Error('Address search failed')
        }

        const results: {
          lat: string
          lon: string
          display_name: string
        }[] = await response.json()

        if (results.length > 0) {
          foundResult = results[0]
          break
        }
      }

      if (!foundResult) {
        setError(
          'Không tìm thấy địa điểm. Thử nhập tên đầy đủ hoặc thêm tỉnh/thành phố nhé.',
        )
        return
      }

      onSelectCenter(
        [Number(foundResult.lat), Number(foundResult.lon)],
        foundResult.display_name,
      )
    } catch {
      setError(
        'Không kết nối được dịch vụ tìm kiếm địa điểm. Vui lòng thử lại.',
      )
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="real-map">
      <div className="map-toolbar">
        <form className="map-address-search" onSubmit={handleAddressSearch}>
          <input
            type="text"
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            placeholder="Tìm địa chỉ hoặc địa điểm..."
            aria-label="Địa chỉ cần tìm"
          />

          <button type="submit" disabled={searching}>
            {searching ? 'Đang tìm...' : 'Tìm'}
          </button>
        </form>

        <button
          type="button"
          className="current-location-button"
          onClick={handleCurrentLocation}
        >
          📍 Vị trí của tôi
        </button>
      </div>

      <div className="map-radius-control">
        <div className="map-radius-heading">
          <label htmlFor="search-radius">Bán kính quét ẩm thực</label>
          <strong>{radius} km</strong>
        </div>

        <input
          id="search-radius"
          className="map-radius-slider"
          type="range"
          min={1}
          max={10}
          step={1}
          value={radius}
          onChange={(event) => onRadiusChange(Number(event.target.value))}
        />

        <div className="map-radius-labels">
          <span>1 km</span>
          <span>5 km</span>
          <span>10 km</span>
        </div>
      </div>

      {error && (
        <div className="map-error" role="alert">
          {error}
        </div>
      )}

      <div className="real-map-canvas">
        <MapContainer
          center={INITIAL_CENTER}
          zoom={14}
          scrollWheelZoom
          className="real-map-container"
        >
          <TileLayer
            attribution={
              import.meta.env.VITE_CARTO_API_KEY
                ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }
            url={
              import.meta.env.VITE_CARTO_API_KEY
                ? `https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?key=${import.meta.env.VITE_CARTO_API_KEY}`
                : 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
            }
          />

          <MapClickHandler
            onSelect={(position) =>
              onSelectCenter(position, 'Vị trí đã chọn trên bản đồ')
            }
          />

          <MapController center={searchCenter?.position ?? null} />

          {searchCenter && (
            <>
              <Circle
                center={searchCenter.position}
                radius={radius * 1000}
                pathOptions={{
                  color: '#10b981',
                  fillColor: '#10b981',
                  fillOpacity: 0.12,
                  weight: 2,
                }}
              />

              <Marker position={searchCenter.position}>
                <Popup>
                  <strong>{searchCenter.label}</strong>
                  <br />
                  Bán kính quét: {radius} km
                  <br />
                  Tọa độ: {searchCenter.position[0].toFixed(5)},{' '}
                  {searchCenter.position[1].toFixed(5)}
                </Popup>
              </Marker>
            </>
          )}

          {/* Hiển thị các Marker quán ăn được tìm thấy */}
          {places.map((place) => (
            <Marker
              key={place.id}
              position={[place.latitude, place.longitude]}
              icon={createPlaceIcon(place.name)}
              eventHandlers={{
                click: () => {
                  if (onSelectPlace) onSelectPlace(place)
                },
              }}
            >
              <Popup>
                <div className="fs-map-popup">
                  <strong>{place.name}</strong>
                  <p>{place.address || 'Chưa có địa chỉ'}</p>
                  <button
                    type="button"
                    className="fs-popup-view-btn"
                    onClick={() => {
                      if (onSelectPlace) onSelectPlace(place)
                    }}
                  >
                    Xem video reviews →
                  </button>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  )
}
