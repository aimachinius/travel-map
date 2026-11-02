import type { Video } from './video'

export interface Place {
  id: string
  name: string
  address: string | null
  normalized_address?: string | null
  latitude: number | null
  longitude: number | null
  description?: string | null
  category: string | null
  source?: string | null
  phone_number?: string | null
  website_url?: string | null
  created_at?: string
  updated_at?: string
  is_saved?: boolean
}

export interface MatchInfo {
  confidence_status: 'HIGH' | 'MEDIUM' | 'LOW'
  evidence_sources?: string[] | any
}

export interface NearbyVideoItem {
  video: {
    id: string
    platform: string
    platform_video_id: string
    video_url: string
    title: string | null
    caption: string | null
    duration_seconds: number | null
    thumbnail_url: string | null
    author_name: string | null
    created_at: string
    is_saved?: boolean
  }
  place: {
    id: string
    name: string
    address: string | null
    latitude: number | null
    longitude: number | null
    category: string | null
    is_saved?: boolean
  }
  match: MatchInfo
  distance_m: number | null
}

export interface PlaceVideoMatchItem {
  video: Video
  confidence_status: 'HIGH' | 'MEDIUM' | 'LOW'
  evidence_sources?: string[] | any
  matched_at: string
}
