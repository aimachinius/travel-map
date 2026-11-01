
import { useEffect, useState, type FormEvent } from 'react'
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

type SearchCenter = {
  position: [number, number]
  label: string
}

const INITIAL_CENTER: [number, number] = [15.8801, 108.3380]

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

export default function ExploreMap() {
  const [searchCenter, setSearchCenter] = useState<SearchCenter | null>(null)
  const [address, setAddress] = useState('')
  const [radius, setRadius] = useState(5)
  const [error, setError] = useState('')
  const [searching, setSearching] = useState(false)

  const selectCenter = (
    position: [number, number],
    label: string,
  ) => {
    setSearchCenter({ position, label })
    setError('')
  }

  const handleCurrentLocation = () => {
    setError('')

    if (!navigator.geolocation) {
      setError('Trình duyệt của bạn không hỗ trợ định vị.')
      return
    }

    navigator.geolocation.getCurrentPosition(
      (result) => {
        selectCenter(
          [result.coords.latitude, result.coords.longitude],
          'Vị trí hiện tại',
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

  
const handleAddressSearch = async (
  event: FormEvent<HTMLFormElement>,
) => {
  event.preventDefault()

  const keyword = address.trim()

  if (!keyword) {
    setError('Vui lòng nhập địa chỉ cần tìm.')
    return
  }

  setSearching(true)
  setError('')

  // Thử nhiều cách tìm nếu từ khóa ban đầu không có kết quả.
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

    selectCenter(
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
          Vị trí của tôi
        </button>
      </div>

      <div className="map-radius-control">
        <div className="map-radius-heading">
          <label htmlFor="search-radius">Bán kính</label>
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
          onChange={(event) => setRadius(Number(event.target.value))}
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
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
            url={`https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=${import.meta.env.VITE_CARTO_API_KEY}`}
          />

          <MapClickHandler
            onSelect={(position) =>
              selectCenter(position, 'Vị trí đã chọn trên bản đồ')
            }
          />

          <MapController center={searchCenter?.position ?? null} />

          {searchCenter && (
            <>
              <Circle
                center={searchCenter.position}
                radius={radius * 1000}
                pathOptions={{
                  color: '#2563eb',
                  fillColor: '#3b82f6',
                  fillOpacity: 0.12,
                  weight: 2,
                }}
              />

              <Marker position={searchCenter.position}>
                <Popup>
                  <strong>{searchCenter.label}</strong>
                  <br />
                  Bán kính tìm kiếm: {radius} km
                  <br />
                  Tọa độ: {searchCenter.position[0].toFixed(5)},{' '}
                  {searchCenter.position[1].toFixed(5)}
                </Popup>
              </Marker>
            </>
          )}
        </MapContainer>
      </div>
    </div>
  )
}
