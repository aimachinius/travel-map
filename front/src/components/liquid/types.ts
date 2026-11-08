export interface VideoPlaylistItem {
  id: string
  url: string
  title: string
  author: string
  locationName: string
  address?: string
  lat: number
  lng: number
  gmapQuery?: string
  category: string
  icon: string
  desc: string
  mp4Url?: string
  distanceKm?: number
  placeId?: string
}

export interface MapCity {
  name: string
  flag: string
  center: [number, number]
  zoom: number
}

export type EngineType = 'mp4' | 'v1' | 'v2'

export type DrawerMode = 'saved-spots' | 'liked-videos' | 'liked-places' | 'history'

export interface SavedFoodSpotItem {
  id: string
  savedAt: string
  title: string
  locationName: string
  lat: number
  lng: number
  category: string
  icon: string
  desc: string
  url?: string
  mp4Url?: string
  videoId?: string
  placeId?: string
  author?: string
}

export interface ToastState {
  type: 'success' | 'error' | 'info'
  title: string
  message: string
}

export interface ChromaticPalette {
  c1: string
  c2: string
  c3: string
  c4: string
  c5: string
  c6: string
  c7: string
  tl?: string
  tr?: string
  bl?: string
  br?: string
  mid?: string
}

