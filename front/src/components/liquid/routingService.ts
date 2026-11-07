/**
 * Dịch vụ chỉ đường và tính toán lộ trình OSRM (Open Source Routing Machine)
 * Tích hợp đa server dự phòng (FOSSGIS OSM DE + OSRM Public API)
 * Hoàn toàn miễn phí, không yêu cầu API Key.
 */

export type RouteVehicle = 'motorcycle' | 'car' | 'foot'

export interface RouteStep {
  instruction: string
  streetName: string
  distanceMeters: number
  durationSeconds: number
  icon: string
}

export interface RouteEstimates {
  motorcycleMinutes: number
  carMinutes: number
  footMinutes: number
}

export interface RouteResult {
  coordinates: [number, number][] // [lat, lng] chuẩn của Leaflet
  distanceMeters: number
  distanceKm: number
  durationSeconds: number
  estimates: RouteEstimates
  summaryStreet: string
  steps: RouteStep[]
  vehicle: RouteVehicle
}

export interface RoutePoint {
  lat: number
  lng: number
  name?: string
}

// Bộ nhớ đệm Route Cache để tránh gọi lặp lại khi người dùng bấm qua lại giữa các quán
const routeCache = new Map<string, RouteResult>()

/**
 * Dịch các bước chỉ dẫn ngã rẽ của OSRM sang Tiếng Việt tự nhiên, thân thiện
 */
function formatStepInstruction(
  type: string,
  modifier: string | undefined,
  name: string,
  destName?: string,
): { text: string; icon: string } {
  const street = name && name.trim() ? name.trim() : 'đoạn đường'

  if (type === 'depart') {
    return { text: `Bắt đầu xuất phát trên ${street}`, icon: '🟢' }
  }
  if (type === 'arrive') {
    return { text: `Đã đến đích: ${destName || street}`, icon: '🏁' }
  }
  if (type === 'roundabout' || type === 'rotary') {
    return { text: `Đi vào vòng xuyến, rẽ vào ${street}`, icon: '🔄' }
  }
  if (type === 'fork') {
    if (modifier?.includes('left')) return { text: `Rẽ theo nhánh bên trái vào ${street}`, icon: '↖️' }
    if (modifier?.includes('right')) return { text: `Rẽ theo nhánh bên phải vào ${street}`, icon: '↗️' }
    return { text: `Đi theo nhánh rẽ vào ${street}`, icon: '🔀' }
  }
  if (type === 'turn' || type === 'new name' || type === 'end of road') {
    if (modifier === 'sharp left') return { text: `Rẽ ngoặt sang trái vào ${street}`, icon: '⬅️' }
    if (modifier === 'left') return { text: `Rẽ trái vào ${street}`, icon: '↩️' }
    if (modifier === 'slight left') return { text: `Chếch sang trái vào ${street}`, icon: '↖️' }
    if (modifier === 'sharp right') return { text: `Rẽ ngoặt sang phải vào ${street}`, icon: '➡️' }
    if (modifier === 'right') return { text: `Rẽ phải vào ${street}`, icon: '↪️' }
    if (modifier === 'slight right') return { text: `Chếch sang phải vào ${street}`, icon: '↗️' }
    if (modifier === 'uturn') return { text: `Quay đầu xe trên ${street}`, icon: '🔄' }
    if (modifier === 'straight') return { text: `Tiếp tục đi thẳng trên ${street}`, icon: '⬆️' }
  }
  if (type === 'continue') {
    return { text: `Tiếp tục đi trên ${street}`, icon: '⬆️' }
  }
  return { text: `Đi tiếp theo ${street}`, icon: '➡️' }
}

/**
 * Tính toán thời gian di chuyển thực tế tại đô thị Việt Nam cho 3 loại phương tiện:
 * - 🛵 Xe máy: Tốc độ trung bình ~26 km/h + độ trễ dừng đèn đỏ
 * - 🚕 Taxi / Ô tô: Tốc độ trung bình ~20 km/h + độ trễ ùn ứ
 * - 🚶‍♀️ Đi bộ: Tốc độ dạo phố thư thái ~4.8 km/h
 */
function calculateVietnamEstimates(distanceMeters: number, stepsCount: number): RouteEstimates {
  const km = distanceMeters / 1000

  // Xe máy: ~26 km/h + 15 giây/ngã rẽ (chờ đèn đỏ)
  const motorcycleRaw = (km / 26) * 60 + (stepsCount * 0.25)
  const motorcycleMinutes = Math.max(1, Math.round(motorcycleRaw))

  // Ô tô / Taxi: ~20 km/h + 25 giây/ngã rẽ
  const carRaw = (km / 20) * 60 + (stepsCount * 0.4)
  const carMinutes = Math.max(2, Math.round(carRaw))

  // Đi bộ: ~4.8 km/h
  const footRaw = (km / 4.8) * 60
  const footMinutes = Math.max(1, Math.round(footRaw))

  return {
    motorcycleMinutes,
    carMinutes,
    footMinutes,
  }
}

/**
 * Gọi OSRM API với cơ chế dự phòng đa server (Fallback Server)
 */
async function fetchOsrmRaw(
  origin: RoutePoint,
  dest: RoutePoint,
  vehicle: RouteVehicle,
): Promise<any> {
  // LƯU Ý OSRM: Kinh độ (lng) trước, Vĩ độ (lat) sau
  const coordParam = `${origin.lng.toFixed(6)},${origin.lat.toFixed(6)};${dest.lng.toFixed(6)},${dest.lat.toFixed(6)}`

  // Danh sách URL ưu tiên và fallback
  const endpoints: string[] = []
  if (vehicle === 'foot') {
    endpoints.push(
      `https://routing.openstreetmap.de/routed-foot/route/v1/walking/${coordParam}?overview=full&geometries=geojson&steps=true`,
      `https://router.project-osrm.org/route/v1/driving/${coordParam}?overview=full&geometries=geojson&steps=true`,
    )
  } else if (vehicle === 'motorcycle') {
    endpoints.push(
      `https://routing.openstreetmap.de/routed-car/route/v1/driving/${coordParam}?overview=full&geometries=geojson&steps=true`,
      `https://router.project-osrm.org/route/v1/driving/${coordParam}?overview=full&geometries=geojson&steps=true`,
    )
  } else {
    endpoints.push(
      `https://routing.openstreetmap.de/routed-car/route/v1/driving/${coordParam}?overview=full&geometries=geojson&steps=true`,
      `https://router.project-osrm.org/route/v1/driving/${coordParam}?overview=full&geometries=geojson&steps=true`,
    )
  }

  let lastError: Error | null = null

  for (const url of endpoints) {
    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 4500) // Timeout 4.5s

      const res = await fetch(url, {
        signal: controller.signal,
        headers: {
          Accept: 'application/json',
        },
      })
      clearTimeout(timeoutId)

      if (!res.ok) {
        throw new Error(`HTTP Error ${res.status}`)
      }

      const json = await res.json()
      if (json.code === 'Ok' && json.routes && json.routes.length > 0) {
        return json
      }
    } catch (err: any) {
      lastError = err
      // Thử endpoint tiếp theo
    }
  }

  throw lastError || new Error('Không thể kết nối máy chủ chỉ đường OSRM')
}

/**
 * Lấy lộ trình hoàn chỉnh giữa 2 điểm
 */
export async function getRouteDirections(
  origin: RoutePoint,
  dest: RoutePoint,
  vehicle: RouteVehicle = 'motorcycle',
): Promise<RouteResult> {
  const cacheKey = `${origin.lat.toFixed(4)},${origin.lng.toFixed(4)}_${dest.lat.toFixed(4)},${dest.lng.toFixed(4)}_${vehicle}`
  if (routeCache.has(cacheKey)) {
    return routeCache.get(cacheKey)!
  }

  const raw = await fetchOsrmRaw(origin, dest, vehicle)
  const route = raw.routes[0]
  const leg = route.legs?.[0]

  // Đảo ngược [lng, lat] thành [lat, lng] cho Leaflet
  const coordinates: [number, number][] = route.geometry.coordinates.map(
    (c: [number, number]) => [c[1], c[0]],
  )

  const distanceMeters = Math.round(route.distance || 0)
  const distanceKm = Math.round((distanceMeters / 1000) * 10) / 10
  const durationSeconds = Math.round(route.duration || 0)

  // Danh sách các ngã rẽ
  const rawSteps = leg?.steps || []
  const steps: RouteStep[] = rawSteps.map((s: any) => {
    const formatted = formatStepInstruction(
      s.maneuver?.type || '',
      s.maneuver?.modifier,
      s.name,
      dest.name,
    )
    return {
      instruction: formatted.text,
      streetName: s.name || '',
      distanceMeters: Math.round(s.distance || 0),
      durationSeconds: Math.round(s.duration || 0),
      icon: formatted.icon,
    }
  })

  // Đoạn đường tiêu biểu (ví dụ: "Qua Lê Thánh Tôn, Nguyễn Huệ")
  const mainStreets = steps
    .map((s) => s.streetName.trim())
    .filter((name, idx, arr) => name && arr.indexOf(name) === idx)
    .slice(0, 2)
  const summaryStreet = mainStreets.length > 0 ? `Qua ${mainStreets.join(' • ')}` : 'Đường phố nội đô'

  const estimates = calculateVietnamEstimates(distanceMeters, steps.length)

  const result: RouteResult = {
    coordinates,
    distanceMeters,
    distanceKm,
    durationSeconds,
    estimates,
    summaryStreet,
    steps,
    vehicle,
  }

  // Lưu vào cache
  routeCache.set(cacheKey, result)
  return result
}

