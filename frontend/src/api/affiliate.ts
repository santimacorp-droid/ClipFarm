import api from '../services/api'

const unwrap = (r: any) => (r && r.data !== undefined ? r.data : r)

export interface CaptionStyleItem {
  key: string
  name: string
  font_size: number
  uppercase: boolean
}

export interface AffiliateStylesResponse {
  styles: CaptionStyleItem[]
  default_style: string
  default_language: string
  supported_languages: { code: string; name: string }[]
  cta: {
    platform: string
    action: string
    supported_styles: string[]
    supported_positions: string[]
  }
}

export interface RecentAffiliateVideo {
  filename: string
  path: string
  size_mb: number
  modified: number
  has_srt: boolean
  video_url: string
}

export interface CandidateVideo {
  filename: string
  path: string
  size_mb: number
  mtime: number
}

export interface ProcessAffiliateResult {
  success: boolean
  input_video: string
  output_video: string
  video_url: string
  srt_path: string
  ass_path: string
  language: string
  model_used?: string
  caption_style: string
  cta_platform: string
  cta_handle: string
  cta_style: string
  video_width: number
  video_height: number
  video_duration: number
  segment_count: number
  word_count: number
  processing_time_sec: number
}

export const affiliateApi = {
  getStyles: async (): Promise<AffiliateStylesResponse> => {
    return unwrap(await api.get('/affiliate/styles'))
  },
  getRecentVideos: async (): Promise<RecentAffiliateVideo[]> => {
    return unwrap(await api.get('/affiliate/recent'))
  },
  getCandidateVideos: async (): Promise<CandidateVideo[]> => {
    return unwrap(await api.get('/affiliate/candidates'))
  },
  processByPath: async (payload: {
    video_path: string
    output_dir?: string
    fb_handle?: string
    caption_style?: string
    cta_style?: string
    cta_position?: string
    language?: string
    engine?: string
  }): Promise<ProcessAffiliateResult> => {
    return unwrap(await api.post('/affiliate/process-path', payload))
  },
  processByUpload: async (formData: FormData): Promise<ProcessAffiliateResult> => {
    return unwrap(
      await api.post('/affiliate/process-upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    )
  }
}
