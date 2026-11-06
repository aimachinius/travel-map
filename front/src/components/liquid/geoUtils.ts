import type { VideoPlaylistItem } from './types'

export interface LocationHub {
  id: string
  name: string
  lat: number
  lng: number
  city: string
  icon: string
}

export const POPULAR_HUBS: LocationHub[] = [
  { id: 'hanoi', name: 'Hà Nội', lat: 21.0285, lng: 105.8542, city: 'Hà Nội', icon: '🏛️' },
  { id: 'hcm', name: 'TP. Hồ Chí Minh', lat: 10.7769, lng: 106.7009, city: 'TP. HCM', icon: '🏙️' },
  { id: 'tokyo', name: 'Tokyo', lat: 35.6762, lng: 139.6503, city: 'Tokyo', icon: '🗼' },
  { id: 'dubai', name: 'Dubai', lat: 25.2048, lng: 55.2708, city: 'Dubai', icon: '✈️' },
]

export const RADIUS_OPTIONS = [1, 3, 5, 10, 25] as const

export interface LandmarkPreset {
  id: string
  name: string
  lat: number
  lng: number
  icon: string
  hubId: string
}

export const QUICK_LANDMARKS: LandmarkPreset[] = [
  // TP.HCM
  { id: 'ben-thanh', name: 'Chợ Bến Thành', lat: 10.7725, lng: 106.6980, icon: '🏪', hubId: 'hcm' },
  { id: 'nguyen-hue', name: 'Phố Nguyễn Huệ', lat: 10.7743, lng: 106.7032, icon: '🚶‍♂️', hubId: 'hcm' },
  { id: 'duc-ba', name: 'Nhà thờ Đức Bà', lat: 10.7798, lng: 106.6990, icon: '⛪', hubId: 'hcm' },
  { id: 'turtle-lake', name: 'Hồ Con Rùa', lat: 10.7828, lng: 106.6961, icon: '☕', hubId: 'hcm' },
  // Hà Nội
  { id: 'ho-guom', name: 'Hồ Hoàn Kiếm', lat: 21.0285, lng: 105.8542, icon: '🐢', hubId: 'hanoi' },
  { id: 'dong-xuan', name: 'Chợ Đồng Xuân', lat: 21.0378, lng: 105.8497, icon: '🏪', hubId: 'hanoi' },
  { id: 'nha-tho-lon', name: 'Nhà Thờ Lớn', lat: 21.0288, lng: 105.8490, icon: '⛪', hubId: 'hanoi' },
  { id: 'van-mieu', name: 'Văn Miếu', lat: 21.0293, lng: 105.8360, icon: '⛩️', hubId: 'hanoi' },
]

/**
 * Tính khoảng cách trắc địa đường chim bay theo công thức Haversine (tính bằng km)
 */
export function calculateDistanceKm(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const R = 6371 // Bán kính Trái Đất (km)
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLon = ((lon2 - lon1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return Math.round(R * c * 10) / 10 // Làm tròn 1 số thập phân
}

/**
 * Lọc và sắp xếp các video theo khoảng cách so với tâm bán kính
 */
export function filterVideosByRadius(
  videos: VideoPlaylistItem[],
  centerLat: number,
  centerLng: number,
  radiusKm: number,
): VideoPlaylistItem[] {
  const withDistance = videos.map((v) => ({
    ...v,
    distanceKm: calculateDistanceKm(centerLat, centerLng, v.lat, v.lng),
  }))

  const insideRadius = withDistance.filter((v) => (v.distanceKm ?? 9999) <= radiusKm)

  // Nếu không có video nào nằm trong bán kính quá hẹp, trả về ít nhất 1 video gần nhất
  if (insideRadius.length === 0 && withDistance.length > 0) {
    withDistance.sort((a, b) => (a.distanceKm ?? 9999) - (b.distanceKm ?? 9999))
    return withDistance.slice(0, 1)
  }

  insideRadius.sort((a, b) => (a.distanceKm ?? 0) - (b.distanceKm ?? 0))
  return insideRadius
}

