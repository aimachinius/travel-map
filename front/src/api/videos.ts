import { apiClient } from './client'
import type {
  AnalysisRun,
  Video,
  VideoSubmitRequest,
  VideoSubmitResponse,
} from '../types/video'

export async function submitVideo(
  data: string | VideoSubmitRequest,
): Promise<VideoSubmitResponse> {
  const payload = typeof data === 'string' ? { video_url: data } : data
  return apiClient<VideoSubmitResponse>('/api/v1/videos/submit', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getMyVideos(
  limit = 20,
  offset = 0,
): Promise<Video[]> {
  return apiClient<Video[]>(`/api/v1/videos?limit=${limit}&offset=${offset}`, {
    method: 'GET',
  })
}

export async function getVideoDetail(videoId: string): Promise<Video> {
  return apiClient<Video>(`/api/v1/videos/${videoId}`, {
    method: 'GET',
  })
}

export async function getAnalysisHistory(
  limit = 20,
  offset = 0,
): Promise<AnalysisRun[]> {
  return apiClient<AnalysisRun[]>(
    `/api/v1/videos/analysis?limit=${limit}&offset=${offset}`,
    {
      method: 'GET',
    },
  )
}

export async function getAnalysisStatus(
  analysisRunId: string,
): Promise<AnalysisRun> {
  return apiClient<AnalysisRun>(`/api/v1/videos/analysis/${analysisRunId}`, {
    method: 'GET',
  })
}
