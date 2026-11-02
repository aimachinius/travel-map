export interface AnalysisUpdateRestaurant {
  id: string
  name: string
  address: string
  latitude: number | null
  longitude: number | null
}

export interface AnalysisUpdateData {
  analysis_run_id: string
  video_id: string | null
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
  restaurant: AnalysisUpdateRestaurant | null
  error_message: string | null
}

export interface AnalysisUpdatedEvent {
  event: 'ANALYSIS_UPDATED'
  data: AnalysisUpdateData
}
