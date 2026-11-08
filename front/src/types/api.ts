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
  platform_video_id?: string | null
  video_url?: string | null
  created_at: string
  updated_at: string
}

export interface GetPlacesParams {
  q?: string
  category?: string
  limit?: number
  offset?: number
}

// ==========================================
// 3. VIDEO & ANALYSIS SCHEMAS (backend/app/schemas/video.py)
// ==========================================

export interface VideoSubmitRequest {
  video_url: string
}

export interface VideoResponse {
  id: string
  platform: string
  platform_video_id: string
  video_url: string
  title: string | null
  caption: string | null
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
  submitted_url: string
  status: string
  video: VideoResponse
  created_at: string
}

export interface AnalysisStatusResponse {
  id: string
  video_id: string | null
  submitted_url: string
  status: string
  result_place_id: string | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

// ==========================================
// 4. SAVED SCHEMAS (backend/app/api/v1/endpoints/saved.py)
// ==========================================

export interface SavedVideoResponse {
  saved_id: string
  saved_at: string
  video: VideoResponse
  place?: PlaceResponse | null
}

export interface SavedPlaceResponse {
  saved_id: string
  saved_at: string
  place: PlaceResponse
  video_count: number
}

// ==========================================
// 5. HEALTH SCHEMAS (backend/app/api/v1/endpoints/health.py)
// ==========================================

export interface HealthResponse {
  status: string
  service: string
  version: string
}

