import type { Place } from './place'
import type { Video } from './video'

export interface SavedVideoItem {
  saved_id: string
  saved_at: string
  video: Video
  place: Place | null
}

export interface SavedPlaceItem {
  saved_id: string
  saved_at: string
  place: Place
  video_count: number
}
