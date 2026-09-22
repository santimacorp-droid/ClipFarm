import api from '../services/api'
import { apiConfigManager } from '../utils/apiConfig'

const API = '/campaigns'

const unwrap = (r: any) => (r && r.data !== undefined ? r.data : r)

export interface PriorityMoment {
  name: string
  description?: string
  start_line?: string
}

export interface CampaignSchema {
  brand_name: string
  campaign_name: string
  source_video_url?: string
  source_filename?: string
  source_duration?: number
  logo_url?: string
  clip_duration: { min_seconds: number; max_seconds: number; is_moment_based?: boolean }
  priority_moments: PriorityMoment[]
  caption_options: string[]
  platform_tags: { tiktok: string[]; instagram: string[]; youtube_shorts: string[]; facebook?: string[] }
  restrictions: {
    subtitles: 'native_preferred' | 'styled_burned' | 'clean_srt_only' | 'none' | 'optional' | 'required' | string
    caption_style?: 'hormozi_yellow' | 'neon_green' | 'neon_cyan' | 'minimal_box' | 'none' | string
    styled_captions: boolean
    show_hook_banner?: boolean
    background_music: string
    logo_required: boolean
    logo_position: string
    logo_scale_percent: number
    output_format?: 'blur_pad' | 'crop_center' | 'original'
    other_people_allowed: boolean
    external_footage_allowed: boolean
    filters_allowed: boolean
    edit_mode?: 'moment_extraction' | 'full_video_edit'
    outro_style?: 'none' | 'follow_handle' | 'check_bio' | 'custom_text'
    outro_text?: string
    outro_handle?: string
    remove_dead_air?: boolean
    silence_threshold_db?: number
    silence_gap_min_sec?: number
    cta_style?:         'none' | 'follow_tap' | 'subscribe_click' | 'follow_pulse' | 'bell_shake' | 'slide_up'
    cta_platform?:      'auto' | 'tiktok' | 'instagram' | 'youtube' | 'youtube_shorts' | 'facebook'
    cta_position?:      'bottom_right' | 'bottom_left' | 'bottom_center'
    cta_handle?:        string
    cta_start_offset?:  number | null
  }
  compliance: {
    min_days_live: number
    min_engagement_rate: number
    likes_must_be_visible: boolean
    tier1_2_audience_required: boolean
    ftc_compliant: boolean
  }
  raw_brief?: string
  status_message?: string
  max_clips?: number
}

export interface ComplianceItem {
  item: string
  status: 'pass' | 'fail' | 'manual' | 'pending'
  value?: string
}

export interface CampaignClip {
  id: string
  campaign_id: string
  moment_name: string
  video_file?: string
  logo_video_file?: string
  captioned_video_file?: string
  cta_video_file?: string
  cta_platforms?:  Record<string, string>
  platform_videos?: Record<string, string>
  cta_style?:      string
  cta_platform?:   string
  vertical_video_file?: string
  srt_file?: string
  subtitle_mode?: string
  output_format?: string
  duration_seconds?: number
  start_sec?: number
  end_sec?: number
  confidence: 'high' | 'low'
  matched_text?: string
  hook_text?: string
  caption_suggestions: Array<{ rank: number; text: string }>
  platform_post_guide: Record<string, { caption: string; tags?: string; title?: string }>
  compliance_checklist: ComplianceItem[]
  publish_log?: Array<{
    platform: string
    post_url: string
    published_at: string
    expires_at: string
  }>
  status: string
  full_edit?: boolean
  edit_mode?: string
  original_duration?: number
  edited_duration?: number
  outro_style?: string
}

export interface SourceVideoInfo {
  exists: boolean
  duration?: number
  width?: number
  height?: number
  size_mb?: number
  filename?: string
}

export interface Campaign {
  id: string
  name: string
  brand_name?: string
  status: string
  status_message?: string
  schema?: CampaignSchema
  clips?: CampaignClip[]
  clips_count?: number
  created_at?: string
}

export const campaignApi = {
  parseBrief: (raw_brief: string, use_llm: boolean = true): Promise<CampaignSchema> =>
    api.post(`${API}/parse-brief`, { raw_brief, use_llm }).then(unwrap),

  create: (payload: { raw_brief?: string; schema_json?: CampaignSchema; name?: string; brand_name?: string } | string): Promise<Campaign> => {
    const body = typeof payload === 'string' ? { raw_brief: payload } : payload
    return api.post(API, body).then(unwrap)
  },

  list: (): Promise<Campaign[]> =>
    api.get(API).then(unwrap),

  get: (id: string): Promise<Campaign> =>
    api.get(`${API}/${id}`).then(unwrap),

  update: (id: string, schema: CampaignSchema): Promise<{ status: string }> =>
    api.put(`${API}/${id}`, { schema_json: schema }).then(unwrap),

  run: (id: string, force: boolean = false): Promise<{ status: string; campaign_id: string }> =>
    api.post(`${API}/${id}/run${force ? '?force=true' : ''}`).then(unwrap),

  reset: (id: string): Promise<{ status: string; campaign_id: string }> =>
    api.post(`${API}/${id}/reset`).then(unwrap),

  delete: (id: string): Promise<{ status: string }> =>
    api.delete(`${API}/${id}`).then(unwrap),

  uploadVideo: (campaignId: string, file: File): Promise<SourceVideoInfo & { status: string; filename: string }> => {
    const formData = new FormData()
    formData.append('video_file', file)
    return api.post(`${API}/${campaignId}/upload-video`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }).then(unwrap)
  },

  importUrl: (campaignId: string, url: string): Promise<SourceVideoInfo & { status: string; url: string }> =>
    api.post(`${API}/${campaignId}/import-url`, { url }).then(unwrap),

  uploadLogo: (campaignId: string, file: File): Promise<{ status: string; logo_url: string }> => {
    const formData = new FormData()
    formData.append('logo_file', file)
    return api.post(`${API}/${campaignId}/upload-logo`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }).then(unwrap)
  },

  deleteLogo: (campaignId: string): Promise<{ status: string }> =>
    api.delete(`${API}/${campaignId}/logo`).then(unwrap),

  getLogoUrl: (campaignId: string): string => {
    const base = apiConfigManager.getBaseUrl()
    return `${base}${API}/${campaignId}/logo`
  },

  listSources: (campaignId: string): Promise<Array<SourceVideoInfo & { filename: string; is_active: boolean }>> =>
    api.get(`${API}/${campaignId}/sources`).then(unwrap),

  selectSource: (campaignId: string, filename: string): Promise<{ status: string }> =>
    api.post(`${API}/${campaignId}/select-source`, { filename }).then(unwrap),

  getSourceInfo: (campaignId: string): Promise<SourceVideoInfo> =>
    api.get(`${API}/${campaignId}/source-info`).then(unwrap),

  getSourceVideoUrl: (campaignId: string): string => {
    const base = apiConfigManager.getBaseUrl()
    return `${base}${API}/${campaignId}/source-video`
  },

  videoUrl: (campaign_id: string, clip_id: string, platform?: string): string => {
    const base = apiConfigManager.getBaseUrl()
    const query = platform ? `?platform=${encodeURIComponent(platform)}` : ''
    return `${base}${API}/${campaign_id}/clips/${clip_id}/video${query}`
  },

  getClipSrtUrl: (campaign_id: string, clip_id: string): string => {
    const base = apiConfigManager.getBaseUrl()
    return `${base}${API}/${campaign_id}/clips/${clip_id}/srt`
  },

  getExportUrl: (campaignId: string): string => {
    const base = apiConfigManager.getBaseUrl()
    return `${base}${API}/${campaignId}/export`
  },

  logPublish: (campaignId: string, clipId: string, data: {
    platform: string; post_url: string; published_at?: string
  }): Promise<{ status: string; entry: { platform: string; post_url: string; published_at: string; expires_at: string } }> =>
    api.post(`${API}/${campaignId}/clips/${clipId}/publish-log`, data).then(unwrap),

  removePublishLog: (campaignId: string, clipId: string, platform: string): Promise<{ status: string }> =>
    api.delete(`${API}/${campaignId}/clips/${clipId}/publish-log/${platform}`).then(unwrap),

  listTemplates: (): Promise<Array<{ id: string; name: string; brand_name?: string }>> =>
    api.get(`${API}/templates`).then(unwrap),

  saveAsTemplate: (campaignId: string, template_name: string): Promise<{ id: string; name: string; status: string }> =>
    api.post(`${API}/${campaignId}/save-template`, { template_name }).then(unwrap),

  createFromTemplate: (templateId: string): Promise<Campaign> =>
    api.post(`${API}/from-template/${templateId}`).then(unwrap),

  regenerateClipCopy: (campaignId: string, clipId: string): Promise<{ status: string; hook_text: string; platform_post_guide: any }> =>
    api.post(`${API}/${campaignId}/clips/${clipId}/regenerate-copy`).then(unwrap),

  updateClipCopy: (campaignId: string, clipId: string, data: { hook_text?: string; platform_post_guide?: any }): Promise<{ status: string; hook_text: string; platform_post_guide: any }> =>
    api.put(`${API}/${campaignId}/clips/${clipId}/copy`, data).then(unwrap)
}

