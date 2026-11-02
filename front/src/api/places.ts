import { apiClient } from './client'
import type { NearbyVideoItem, Place, PlaceVideoMatchItem } from '../types/place'

export async function getNearbyVideos(
  lat: number,
  lon: number,
  radiusM = 2000,
  limit = 20,
  offset = 0,
): Promise<NearbyVideoItem[]> {
  const params = new URLSearchParams({
    lat: lat.toString(),
    lon: lon.toString(),
    radius_m: radiusM.toString(),
    limit: limit.toString(),
    offset: offset.toString(),
  })

  return apiClient<NearbyVideoItem[]>(`/api/v1/places/nearby-videos?${params.toString()}`, {
    method: 'GET',
  })
}

export async function searchPlaces(
  q?: string,
  category?: string,
  limit = 20,
  offset = 0,
): Promise<Place[]> {
  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString(),
  })
  if (q) params.set('q', q)
  if (category) params.set('category', category)

  return apiClient<Place[]>(`/api/v1/places/search?${params.toString()}`, {
    method: 'GET',
  })
}

export async function getPlaceDetail(placeId: string): Promise<Place> {
  return apiClient<Place>(`/api/v1/places/${placeId}`, {
    method: 'GET',
  })
}

export async function getPlaceVideos(
  placeId: string,
  limit = 50,
  offset = 0,
): Promise<PlaceVideoMatchItem[]> {
  return apiClient<PlaceVideoMatchItem[]>(
    `/api/v1/places/${placeId}/videos?limit=${limit}&offset=${offset}`,
    {
      method: 'GET',
    },
  )
}
