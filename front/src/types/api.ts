/**
 * Food Spot API - Type Definitions
 * Matched 1:1 with Backend FastAPI Pydantic Schemas (backend/app/schemas/*)
 */

// ==========================================
// 1. AUTH SCHEMAS (backend/app/schemas/auth.py)
// ==========================================

export interface RegisterRequest {
  username: string
  email: string
  password: string
  full_name?: string | null
}

export interface RegisterResponse {
  id: string
  username: string
  email: string
  full_name: string | null
  created_at: string
}

export interface LoginRequest {
  username_or_email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface CurrentUserResponse {
  id: string
  username: string
  email: string
  full_name: string | null
  avatar_url: string | null
  is_active: boolean
  created_at: string
}

// ==========================================
// 2. PLACE SCHEMAS (backend/app/schemas/place.py)
// ==========================================

export interface PlaceResponse {
  id: string
  name: string
  address: string | null
  normalized_address?: string | null
  latitude: number | null
  longitude: number | null
  description: string | null
  category: string | null
  source: string | null
  phone_number: string | null
  website_url: string | null
  created_at: string
  updated_at: string
}

export interface PlaceMini {
  id: string
  name: string
  address: string | null
  latitude: number | null
  longitude: number | null
  category: string | null
  is_saved?: boolean
}

export interface VideoMini {
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

export interface MatchInfo {
  confidence_status: string
  evidence_sources?: string[] | Record<string, unknown> | null
}

export interface NearbyVideoItem {
  video: VideoMini
  place: PlaceMini
  match?: MatchInfo
  distance_m?: number
  distance_meters?: number
}

export interface PlaceVideoMatchItem {
  video: VideoResponse
  confidence_status: string
  evidence_sources?: string[] | Record<string, unknown> | null
  evidence?: unknown
}

export interface GetPlacesParams {
  q?: string
  category?: string
  limit?: number
  offset?: number
}

export interface GetNearbyVideosParams {
  lat: number
  lon: number
  radius_m?: number
  limit?: number
  offset?: number
}

// ==========================================
// 3. VIDEO & ANALYSIS SCHEMAS (backend/app/schemas/video.py)
// ==========================================

export interface VideoSubmitRequest {
  video_url: string
  force_reanalyze?: boolean
}

export interface VideoResponse {
  id: string
  platform: string
  platform_video_id: string
  video_url: string
  title: string | null
  caption: string | null
  duration_seconds?: number | null
  file_size_mb?: number | null
  transcript?: string | null
  transcript_text?: string | null
  thumbnail_url: string | null
  author_name: string | null
  view_count: number | null
  like_count: number | null
  comment_count: number | null
  published_at: string | null
  created_at: string
}

export interface VideoSubmitResponse {
  analysis_run_id: string
  video_id: string
  submitted_url: string
  status: string
  cached?: boolean
  created_at: string
}

export interface AnalysisStatusResponse {
  id: string
  video_id: string | null
  submitted_url: string
  status: string
  trigger_source?: string
  priority?: number
  result_place_id: string | null
  keyframes_data?: unknown
  ocr_data?: unknown
  execution_metrics?: unknown
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

// ==========================================
// 4. SAVED SCHEMAS (backend/app/schemas/saved.py)
// ==========================================

export interface SavedVideoResponse {
  saved_id: string
  saved_at: string
  video: VideoResponse
  place: PlaceResponse | null
}

export interface SavedPlaceResponse {
  saved_id: string
  saved_at: string
  place: PlaceResponse
  video_count: number
}

// ==========================================
// 5. WEBSOCKET NOTIFICATION SCHEMAS
// ==========================================

export interface AnalysisUpdatedData {
  analysis_run_id: string
  video_id: string | null
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
  restaurant?: {
    id: string
    name: string
    address: string
    latitude: number
    longitude: number
  } | null
  error_message?: string | null
}

export interface AnalysisWebSocketMessage {
  event: 'ANALYSIS_UPDATED'
  data: AnalysisUpdatedData
}

// ==========================================
// 6. HEALTH SCHEMAS (backend/app/api/v1/endpoints/health.py)
// ==========================================

export interface HealthResponse {
  status: string
  service: string
  version: string
}
