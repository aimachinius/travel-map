export interface Video {
  id: string
  platform: 'tiktok' | 'youtube' | string
  platform_video_id: string
  video_url: string
  title: string | null
  caption: string | null
  duration_seconds: number | null
  file_size_mb: number | null
  transcript?: string | null
  transcript_text?: string | null
  thumbnail_url: string | null
  author_name: string | null
  view_count: number | null
  like_count: number | null
  comment_count: number | null
  published_at: string | null
  created_at: string
  is_saved?: boolean
}

export interface VideoSubmitRequest {
  video_url: string
  force_reanalyze?: boolean
}

export interface VideoSubmitResponse {
  analysis_run_id: string
  video_id: string
  submitted_url: string
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
  cached: boolean
  created_at: string
}

export interface AnalysisRun {
  id: string
  video_id: string | null
  submitted_url: string
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
  trigger_source: 'USER_SUBMIT' | 'SYSTEM_DISCOVERY'
  priority: number
  result_place_id: string | null
  keyframes_data?: any
  ocr_data?: any
  execution_metrics?: any
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}
