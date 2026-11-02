import { apiClient } from './client'
import type { SavedPlaceItem, SavedVideoItem } from '../types/saved'

// Saved Videos
export async function saveVideo(videoId: string): Promise<any> {
  return apiClient(`/api/v1/saved/videos/${videoId}`, {
    method: 'POST',
  })
}

export async function unsaveVideo(videoId: string): Promise<void> {
  return apiClient(`/api/v1/saved/videos/${videoId}`, {
    method: 'DELETE',
  })
}

export async function getSavedVideos(
  limit = 20,
  offset = 0,
): Promise<SavedVideoItem[]> {
  return apiClient<SavedVideoItem[]>(
    `/api/v1/saved/videos?limit=${limit}&offset=${offset}`,
    {
      method: 'GET',
    },
  )
}

// Saved Places
export async function savePlace(placeId: string): Promise<any> {
  return apiClient(`/api/v1/saved/places/${placeId}`, {
    method: 'POST',
  })
}

export async function unsavePlace(placeId: string): Promise<void> {
  return apiClient(`/api/v1/saved/places/${placeId}`, {
    method: 'DELETE',
  })
}

export async function getSavedPlaces(
  limit = 20,
  offset = 0,
): Promise<SavedPlaceItem[]> {
  return apiClient<SavedPlaceItem[]>(
    `/api/v1/saved/places?limit=${limit}&offset=${offset}`,
    {
      method: 'GET',
    },
  )
}
