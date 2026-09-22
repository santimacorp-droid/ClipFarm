import axios from 'axios'
import { Project, Clip, Collection } from '../store/useProjectStore'
import { errorHandler } from '../utils/errorHandler'
import { apiConfigManager } from '../utils/apiConfig'
import {
  trackVideoImported,
  trackClipsExported,
  trackProcessingFailed,
} from '../appEvents/events'

// ExtensionAxiosConfiguration type
declare module 'axios' {
  interface InternalAxiosRequestConfig {
    metadata?: {
      startTime: number
      retryCount?: number
    }
  }
}

// Formatting time function (not currently used; retain as standby))

const api = axios.create({
  baseURL: apiConfigManager.getBaseUrl(),
  timeout: 300000, // Add to5Minute timeout
  headers: {
    'Content-Type': 'application/json',
  },
})

const RETRYABLE_METHODS = new Set(['get', 'head', 'options'])
const RETRYABLE_STATUS_CODES = new Set([408, 429, 500, 502, 503, 504])
const MAX_RETRIES = 2

const shouldRetry = (error: any): boolean => {
  const method = error?.config?.method?.toLowerCase()
  if (!method || !RETRYABLE_METHODS.has(method)) return false

  const status = error?.response?.status
  if (status && RETRYABLE_STATUS_CODES.has(status)) return true

  const code = error?.code
  return code === 'ECONNABORTED' || !error?.response
}

const getRetryDelay = (retryCount: number): number => 300 * Math.pow(2, retryCount)

apiConfigManager.addListener((config) => {
  api.defaults.baseURL = config.baseUrl
})

const isTauriRuntime = () => (
  typeof window !== 'undefined' &&
  ((window as any).__TAURI__ || (window as any).__TAURI_INTERNALS__)
)

// Request interceptor
api.interceptors.request.use(
  async (config) => {
    if (isTauriRuntime() && !apiConfigManager.isReady()) {
      await apiConfigManager.waitForReady()
    }

    config.baseURL = apiConfigManager.getBaseUrl()
    // Add requestIDFor tracking
    config.metadata = { startTime: Date.now() }
    return config
  },
  (error) => {
    errorHandler.handleError(error, 'RequestInterceptor')
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => {
    // Record request duration
    if (response.config.metadata?.startTime) {
      const duration = Date.now() - response.config.metadata.startTime
      if (duration > 5000) { // Over5Second request
        console.warn(`Slow API request: ${response.config.url} took ${duration}ms`)
      }
    }
    
    return response.data
  },
  async (error) => {
    if (shouldRetry(error)) {
      const currentRetryCount = error.config?.metadata?.retryCount || 0
      if (currentRetryCount < MAX_RETRIES) {
        error.config.metadata = {
          ...(error.config.metadata || { startTime: Date.now() }),
          retryCount: currentRetryCount + 1,
        }
        await new Promise((resolve) => setTimeout(resolve, getRetryDelay(currentRetryCount)))
        return api.request(error.config)
      }
    }

    // Use unified error handler
    errorHandler.handleError(error, 'API')
    
    // Keep original error object structure, ensure backward compatibility and convert non-string errors to clear text
    let userMsg = 'An unexpected error occurred'
    if (error.response?.data?.detail) {
      if (typeof error.response.data.detail === 'string') {
        userMsg = error.response.data.detail
      } else if (Array.isArray(error.response.data.detail)) {
        // FastAPI / Pydantic validation errors (array of {loc, msg, type})
        userMsg = error.response.data.detail
          .map((d: any) => d.msg || d.message || (typeof d === 'string' ? d : JSON.stringify(d)))
          .join('; ')
      } else if (typeof error.response.data.detail === 'object') {
        userMsg = error.response.data.detail.msg || error.response.data.detail.message || JSON.stringify(error.response.data.detail)
      }
      // Ensure response.data.detail Always be a string to prevent direct injection React DOM Crash caused by rendering object during server-side rendering
      error.response.data.detail = userMsg
    } else if (error.response?.status === 429) {
      userMsg = 'System is currently busy processing other requests. Please try again later.'
    } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      userMsg = 'Request timed out. The project may still be processing in the background.'
    } else if (error.code === 'NETWORK_ERROR' || !error.response) {
      userMsg = 'Network connection failed. Please check your connection.'
    } else if (error.response?.status >= 500) {
      userMsg = 'Internal server error. Please try again later.'
    } else if (typeof error.message === 'string') {
      userMsg = error.message
    }
    
    error.userMessage = userMsg
    
    return Promise.reject(error)
  }
)

export interface UploadFilesRequest {
  video_file: File
  srt_file?: File
  project_name: string
  video_category?: string
  caption_style?: string
  duration_mode?: string
  aspect_ratio?: string
  show_hook_banner?: boolean
  watermark_preset_id?: string
  watermark_text?: string
  watermark_text_opacity?: number
  watermark_text_position?: string
}

export interface WatermarkPreset {
  id: string
  name: string
  logo_filename: string
  logo_url?: string
  logo_exists?: boolean
  position: 'bottom_right' | 'bottom_left' | 'top_right' | 'top_left'
  scale_percent: number
  opacity: number
  margin: number
  is_default: boolean
  created_at?: string
}

export interface VideoCategory {
  value: string
  name: string
  description: string
  icon: string
  color: string
}

export interface VideoCategoriesResponse {
  categories: VideoCategory[]
  default_category: string
}

export interface ProcessingStatus {
  status: 'processing' | 'completed' | 'error'
  current_step: number
  total_steps: number
  step_name: string
  progress: number
  error_message?: string
}

// BSite-related interface types
export interface BilibiliVideoInfo {
  title: string
  description: string
  duration: number
  uploader: string
  upload_date: string
  view_count: number
  like_count: number
  thumbnail: string
  url: string
}

export interface BilibiliDownloadRequest {
  url: string
  project_name: string
  video_category?: string
  browser?: string
  caption_style?: string
  duration_mode?: string
  show_hook_banner?: boolean
  watermark_preset_id?: string
}

export interface BilibiliDownloadTask {
  id: string
  url: string
  project_name: string
  video_category?: string
  browser?: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  error_message?: string
  video_info?: BilibiliVideoInfo
  project_id?: string
  created_at: string
  updated_at: string
}

// Settings relatedAPI
export const settingsApi = {
  // Get system configuration
  getSettings: (): Promise<any> => {
    return api.get('/settings')
  },

  // Update system configuration
  updateSettings: (settings: any): Promise<any> => {
    return api.put('/settings/', settings)
  },

  // Testing API Key and connectivity
  testApiKey: (provider: string, apiKey?: string, modelName?: string, baseUrl?: string): Promise<{ success: boolean; message?: string; error?: string }> => {
    return api.post('/settings/test-api', { 
      provider, 
      api_key: apiKey,
      model_name: modelName,
      base_url: baseUrl
    })
  },

  // Dynamically fetch models from local or custom OpenAI-compatible endpoint
  fetchRemoteModels: (provider: string, apiKey?: string, baseUrl?: string): Promise<{ success: boolean; models?: string[]; count?: number; error?: string }> => {
    return api.post('/settings/fetch-models', {
      provider,
      api_key: apiKey,
      base_url: baseUrl
    })
  },

  // Get all available models
  getAvailableModels: (): Promise<any> => {
    return api.get('/settings/available-models')
  },

  // Get current provider information
  getCurrentProvider: (): Promise<any> => {
    return api.get('/settings/current-provider')
  },

  // Check desktop mode
  checkDesktopMode: (): Promise<{ is_desktop_mode: boolean; environment: any }> => {
    return api.get('/settings/desktop-mode')
  },

  // RetrievingTokenUsage statistics and rates
  getTokenStats: (): Promise<{
    total_tokens: number
    total_prompt_tokens: number
    total_completion_tokens: number
    total_cost_usd: number
    total_requests: number
    by_model: Record<string, any>
    by_provider: Record<string, any>
    recent_history: any[]
    model_rates: Record<string, any>
  }> => {
    return api.get('/settings/token-stats')
  },

  // ResetTokenConsumption statistics
  resetTokenStats: (): Promise<{ message: string }> => {
    return api.post('/settings/token-stats/reset')
  }
}

// Project-relatedAPI
export const projectApi = {
  // Get video category configuration
  getVideoCategories: async (): Promise<VideoCategoriesResponse> => {
    return api.get('/video-categories')
  },

  // Get all projects
  getProjects: async (): Promise<Project[]> => {
    const response = await api.get('/projects/')
    // Process pagination response structure and returnitemsArray
    return (response as any).items || response || []
  },

  // Get single project
  getProject: async (id: string): Promise<Project> => {
    return api.get(`/projects/${id}`)
  },

  // Upload file and create project
  uploadFiles: async (data: UploadFilesRequest): Promise<Project> => {
    const formData = new FormData()
    formData.append('video_file', data.video_file)
    if (data.srt_file) {
      formData.append('srt_file', data.srt_file)
    }
    formData.append('project_name', data.project_name)
    if (data.video_category) {
      formData.append('video_category', data.video_category)
    }
    if (data.caption_style) {
      formData.append('caption_style', data.caption_style)
    }
    if (data.duration_mode) {
      formData.append('duration_mode', data.duration_mode)
    }
    if (data.aspect_ratio) {
      formData.append('aspect_ratio', data.aspect_ratio)
    }
    if (data.show_hook_banner !== undefined) {
      formData.append('show_hook_banner', String(data.show_hook_banner))
    }
    if (data.watermark_preset_id) {
      formData.append('watermark_preset_id', data.watermark_preset_id)
    }
    if (data.watermark_text) {
      formData.append('watermark_text', data.watermark_text)
    }
    if (data.watermark_text_opacity !== undefined) {
      formData.append('watermark_text_opacity', String(data.watermark_text_opacity))
    }
    if (data.watermark_text_position) {
      formData.append('watermark_text_position', data.watermark_text_position)
    }
    
    try {
      const project = await api.post<unknown, Project>('/projects/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })
      trackVideoImported({
        source: 'upload',
        fileType: data.video_file?.type || undefined,
        sizeBytes: data.video_file?.size,
      })
      return project
    } catch (error: any) {
      trackProcessingFailed({
        stage: 'import',
        message: error?.message,
        code: error?.response?.status,
      })
      throw error
    }
  },

  // Delete project
  deleteProject: async (id: string): Promise<void> => {
    await api.delete(`/projects/${id}`)
  },

  // Start processing project
  startProcessing: async (id: string): Promise<void> => {
    await api.post(`/projects/${id}/process`)
  },

  // Retry processing project
  retryProcessing: async (id: string): Promise<void> => {
    await api.post(`/projects/${id}/retry`)
  },

  // Get processing status
  getProcessingStatus: async (id: string): Promise<ProcessingStatus> => {
    return api.get(`/projects/${id}/status`)
  },

  // Get project logs
  getProjectLogs: async (id: string, lines: number = 50): Promise<{logs: Array<{timestamp: string, module: string, level: string, message: string}>}> => {
    return api.get(`/projects/${id}/logs?lines=${lines}`)
  },

  // Get project slice
  getClips: async (projectId: string): Promise<any[]> => {
    try {
      // Retrieve data only from database; no longer fall back to file system
      console.log('🔍 Calling clips API for project:', projectId)
      const response = await api.get(`/clips/?project_id=${projectId}`)
      console.log('📦 Raw API response:', response)
      const clips = (response as any).items || response || []
      console.log('📋 Extracted clips:', clips.length, 'clips found')
      
      // Convert backend data format to frontend expected format
      const convertedClips = clips.map((clip: any) => {
        // Convert seconds to time string format
        const formatSecondsToTime = (seconds: number) => {
          const hours = Math.floor(seconds / 3600)
          const minutes = Math.floor((seconds % 3600) / 60)
          const secs = Math.floor(seconds % 60)
          return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
        }
        
        // RetrievingmetadataContents of
        const metadata = clip.clip_metadata || {}
        
        return {
          id: clip.id,
          title: clip.title,
          generated_title: clip.title,
          start_time: formatSecondsToTime(clip.start_time),
          end_time: formatSecondsToTime(clip.end_time),
          duration: clip.duration || 0,
          final_score: clip.score || 0,
          recommend_reason: metadata.recommend_reason || '',
          outline: metadata.outline || '',
          // Only usemetadataIncontent, Avoid usingdescription(May be transcription text)
          content: metadata.content || [],
          chunk_index: metadata.chunk_index || 0,
          video_url: `/api/v1/clips/${clip.id}/video`,
          video_path: clip.video_path,
          clip_metadata: metadata,
          cta_platforms: metadata.cta_platforms || metadata.platform_videos || {},
          cta_style: metadata.cta_style,
          cta_position: metadata.cta_position,
          platform_advisory: clip.platform_advisory || metadata.platform_advisory,
          social_copy: clip.social_copy || metadata.social_copy,
          post_caption: clip.social_copy?.post_caption || metadata.post_caption || metadata.social_copy?.post_caption,
          hashtags: clip.social_copy?.hashtags || metadata.hashtags || metadata.social_copy?.hashtags || []
        }
      })
      
      console.log('✅ Converted clips:', convertedClips.length, 'clips')
      console.log('📄 First clip sample:', convertedClips[0])
      return convertedClips
    } catch (error) {
      console.error('❌ Failed to get clips:', error)
      return []
    }
  },

  // Get project collection
  getCollections: async (projectId: string): Promise<any[]> => {
    try {
      // Retrieve data only from database; no longer fall back to file system
      const response = await api.get(`/collections/?project_id=${projectId}`)
      const collections = (response as any).items || response || []
      
      // Convert backend data format to frontend expected format
      return collections.map((collection: any) => ({
        id: collection.id,
        collection_title: collection.name || collection.collection_title || '',
        collection_summary: collection.description || collection.collection_summary || '',
        clip_ids: collection.clip_ids || collection.metadata?.clip_ids || [],
        collection_type: collection.collection_type || 'ai_recommended',
        created_at: collection.created_at,
        project_id: collection.project_id,
        thumbnail_path: collection.thumbnail_path
      }))
    } catch (error) {
      console.error('Failed to get collections:', error)
      return []
    }
  },

  // Restart specified step
  restartStep: async (id: string, step: number): Promise<void> => {
    await api.post(`/projects/${id}/restart-step`, { step })
  },

  // Update slice information
  updateClip: (projectId: string, clipId: string, updates: Partial<Clip>): Promise<Clip> => {
    return api.patch(`/projects/${projectId}/clips/${clipId}`, updates)
  },

  // Update slice title
  updateClipTitle: async (clipId: string, title: string): Promise<any> => {
    return api.patch(`/clips/${clipId}/title`, { title })
  },

  // Generate slice title
  generateClipTitle: async (clipId: string): Promise<{clip_id: string, generated_title: string, success: boolean}> => {
    return api.post(`/clips/${clipId}/generate-title`)
  },

  // Generate / regenerate social posting caption and hashtags
  generateSocialCaption: async (clipId: string, payload?: { category?: string, model?: string }): Promise<{ clip_id: string, social_copy: any, success: boolean }> => {
    return api.post(`/clips/${clipId}/social-caption`, payload || {})
  },

  // Save custom edited social caption
  updateSocialCaption: async (clipId: string, socialCopy: any): Promise<{ clip_id: string, social_copy: any, success: boolean }> => {
    return api.patch(`/clips/${clipId}/social-caption`, { social_copy: socialCopy })
  },

  // Create collection
  createCollection: (projectId: string, collectionData: { collection_title: string, collection_summary: string, clip_ids: string[] }): Promise<Collection> => {
    return api.post(`/collections/`, {
      project_id: projectId,
      name: collectionData.collection_title,
      description: collectionData.collection_summary,
      clip_ids: collectionData.clip_ids,
      collection_type: 'manual'
    })
  },

  // Update collection information
  updateCollection: (_projectId: string, collectionId: string, updates: Partial<Collection>): Promise<Collection> => {
    return api.put(`/collections/${collectionId}`, updates)
  },

  // Reorder collection slices
  reorderCollectionClips: (projectId: string, collectionId: string, clipIds: string[]): Promise<Collection> => {
    return api.patch(`/projects/${projectId}/collections/${collectionId}/reorder`, clipIds)
  },

  // Delete collection
  deleteCollection: (_projectId: string, collectionId: string): Promise<{message: string, deleted_collection: string}> => {
    return api.delete(`/collections/${collectionId}`)
  },

  // Generate collection title
  generateCollectionTitle: (collectionId: string): Promise<{collection_id: string, generated_title: string, success: boolean}> => {
    return api.post(`/collections/${collectionId}/generate-title`)
  },

  // Update collection title
  updateCollectionTitle: (collectionId: string, title: string): Promise<{collection_id: string, title: string, success: boolean}> => {
    return api.put(`/collections/${collectionId}/title`, { title })
  },

  // Download slice video
  downloadClip: (_projectId: string, clipId: string): Promise<Blob> => {
    return api.get(`/files/projects/${_projectId}/clips/${clipId}`, {
      responseType: 'blob'
    })
  },

  // Download collection video
  downloadCollection: (projectId: string, collectionId: string): Promise<Blob> => {
    return api.get(`/files/projects/${projectId}/collections/${collectionId}`, {
      responseType: 'blob'
    })
  },

  // Export metadata
  exportMetadata: (projectId: string): Promise<Blob> => {
    return api.get(`/projects/${projectId}/export`, {
      responseType: 'blob'
    })
  },

  // Generate collection video
  generateCollectionVideo: (projectId: string, collectionId: string) => {
    return api.post(`/projects/${projectId}/collections/${collectionId}/generate`)
  },

  downloadVideo: async (projectId: string, clipId?: string, collectionId?: string) => {
    let url = `/projects/${projectId}/download`
    if (clipId) {
      url += `?clip_id=${clipId}`
    } else if (collectionId) {
      url += `?collection_id=${collectionId}`
    }
    
    try {
      const baseUrl = apiConfigManager.getBaseUrl().replace(/\/+$/, '')
      const fullUrl = `${baseUrl}${url.startsWith('/') ? url : `/${url}`}`

      const response = await axios.get(fullUrl, { 
        responseType: 'blob',
        headers: {
          'Accept': 'application/octet-stream'
        }
      })
      
      // Get filename from response headers; use default name if not present
      const contentDisposition = response.headers['content-disposition'] || response.headers['Content-Disposition']
      let filename = clipId ? `clip_${clipId}.mp4` : 
                     collectionId ? `collection_${collectionId}.mp4` : 
                     `project_${projectId}.mp4`
      
      if (contentDisposition) {
        // Prioritize attempting parsing RFC 6266 In format filename* Parameters
        const filenameStarMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
        if (filenameStarMatch) {
          filename = decodeURIComponent(filenameStarMatch[1])
        } else {
          // Roll back to traditional filename Parameters
          const filenameMatch = contentDisposition.match(/filename="?([^";]+)"?/i)
          if (filenameMatch) {
            filename = filenameMatch[1]
          }
        }
      }
      
      // Create download link
      const blob = new Blob([response.data], { type: 'video/mp4' })
      const downloadUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = filename
      
      // Trigger download
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(downloadUrl)

      trackClipsExported({
        clipCount: 1,
        // Export granularity differentiation: single slice / Collection / Whole film
        exportType: clipId ? 'clip' : collectionId ? 'collection' : 'project',
      })
      return response.data
    } catch (error: any) {
      let errorMessage = error?.message || 'Download failed'
      if (error?.response?.data instanceof Blob) {
        try {
          const errorText = await error.response.data.text()
          const parsed = JSON.parse(errorText)
          if (parsed?.detail) {
            errorMessage = parsed.detail
          }
        } catch {
          // Keep default message
        }
      }
      console.error('Download video failed:', errorMessage, error)
      trackProcessingFailed({
        stage: 'export',
        message: errorMessage,
        code: error?.response?.status,
      })
      const customError = new Error(errorMessage)
      ;(customError as any).response = error?.response
      throw customError
    }
  },

  // Export all slices as ZIP Compressed file
  exportAllClipsZip: async (projectId: string, platform?: string): Promise<Blob> => {
    try {
      const baseUrl = apiConfigManager.getBaseUrl().replace(/\/+$/, '')
      const query = platform ? `?platform=${encodeURIComponent(platform)}` : ''
      const fullUrl = `${baseUrl}/projects/${projectId}/export-zip${query}`

      const response = await axios.get(fullUrl, {
        responseType: 'blob',
        timeout: 120000 // 2 minutes timeout for zipping
      })

      // Parse file name
      const contentDisposition = response.headers['content-disposition'] || response.headers['Content-Disposition']
      let filename = `project_${projectId}_clips.zip`

      if (contentDisposition) {
        const filenameStarMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
        if (filenameStarMatch) {
          filename = decodeURIComponent(filenameStarMatch[1])
        } else {
          const filenameMatch = contentDisposition.match(/filename="?([^";]+)"?/i)
          if (filenameMatch) {
            filename = filenameMatch[1]
          }
        }
      }

      const blob = new Blob([response.data], { type: 'application/zip' })
      const downloadUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(downloadUrl)

      trackClipsExported({
        clipCount: 1,
        exportType: 'zip_bundle'
      })

      return response.data
    } catch (error: any) {
      let errorMessage = error?.message || 'ZIP Export failed'
      if (error?.response?.data instanceof Blob) {
        try {
          const errorText = await error.response.data.text()
          const parsed = JSON.parse(errorText)
          if (parsed?.detail) {
            errorMessage = parsed.detail
          }
        } catch {
          // Keep default message
        }
      }
      console.error('ZIP Export failed:', errorMessage, error)
      const customError = new Error(errorMessage)
      ;(customError as any).response = error?.response
      throw customError
    }
  },

  // Get project filesURL
  getProjectFileUrl: (projectId: string, filename: string): string => {
    return `${api.defaults.baseURL}/projects/${projectId}/files/${filename}`
  },

  // Get project videoURL
  getProjectVideoUrl: (projectId: string): string => {
    return `${api.defaults.baseURL}/projects/${projectId}/video`
  },

  // Get slice videoURL
  getClipVideoUrl: (_projectId: string, clipId: string, _clipTitle?: string, platform?: string): string => {
    const query = platform ? `?platform=${encodeURIComponent(platform)}` : ''
    return `/api/v1/clips/${clipId}/video${query}`
  },

  // Get collection videoURL
  getCollectionVideoUrl: (projectId: string, collectionId: string): string => {
    // UsagefilesRoute to get collection videos
    return `/api/v1/files/projects/${projectId}/collections/${collectionId}`
  },

  // Generate project thumbnail
  generateThumbnail: async (projectId: string): Promise<{success: boolean, thumbnail: string, message: string}> => {
    return api.post(`/projects/${projectId}/generate-thumbnail`)
  }
}

// Video download relatedAPI
export const bilibiliApi = {
  // ParsingBSite video information
  parseVideoInfo: async (url: string, browser?: string): Promise<{success: boolean, video_info: BilibiliVideoInfo}> => {
    const formData = new FormData()
    formData.append('url', url)
    if (browser) {
      formData.append('browser', browser)
    }
    return api.post('/bilibili/parse', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  // ParsingYouTubeVideo information
  parseYouTubeVideoInfo: async (url: string, browser?: string): Promise<{success: boolean, video_info: BilibiliVideoInfo}> => {
    const formData = new FormData()
    formData.append('url', url)
    if (browser) {
      formData.append('browser', browser)
    }
    return api.post('/youtube/parse', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  // CreationBSite download task
  createDownloadTask: async (data: BilibiliDownloadRequest): Promise<BilibiliDownloadTask> => {
    const task = await api.post<unknown, BilibiliDownloadTask>('/bilibili/download', data)
    trackVideoImported({ source: 'url', fileType: 'bilibili' })
    return task
  },

  // CreationYouTubeDownload task
  createYouTubeDownloadTask: async (data: BilibiliDownloadRequest): Promise<BilibiliDownloadTask> => {
    const task = await api.post<unknown, BilibiliDownloadTask>('/youtube/download', data)
    trackVideoImported({ source: 'url', fileType: 'youtube' })
    return task
  },

  // Get download task status
  getTaskStatus: async (taskId: string): Promise<BilibiliDownloadTask> => {
    return api.get(`/bilibili/tasks/${taskId}`)
  },

  // RetrievingYouTubeDownload task status
  getYouTubeTaskStatus: async (taskId: string): Promise<BilibiliDownloadTask> => {
    return api.get(`/youtube/tasks/${taskId}`)
  },

  // Get all download tasks
  getAllTasks: async (): Promise<BilibiliDownloadTask[]> => {
    return api.get('/bilibili/tasks')
  },

  // Get allYouTubeDownload task
  getAllYouTubeTasks: async (): Promise<BilibiliDownloadTask[]> => {
    return api.get('/youtube/tasks')
  }
}

export const youtubeApi = {
  parseVideoInfo: bilibiliApi.parseYouTubeVideoInfo,
  createDownloadTask: bilibiliApi.createYouTubeDownloadTask,
  getTaskStatus: bilibiliApi.getYouTubeTaskStatus,
  getAllTasks: bilibiliApi.getAllYouTubeTasks
}

// System status relatedAPI
export const systemApi = {
  // Get system status
  getSystemStatus: (): Promise<{
    current_processing_count: number
    max_concurrent_processing: number
    total_projects: number
    processing_projects: string[]
  }> => {
    return api.get('/system/status')
  }
}

export interface WhisperRuntimeStatus {
  status: 'unknown' | 'not_installed' | 'installing' | 'installed' | 'error'
  progress: number
  message: string
  log_tail?: string
  platform_supported: boolean
  packages: string[]
}

export interface WhisperModel {
  name: string
  size: string
  sizeBytes: number
  description: string
  accuracy: string
  speed: string
  status: 'available' | 'downloading' | 'downloaded' | 'error' | 'not_found'
  downloadProgress?: number | null
  localPath?: string | null
  errorMessage?: string | null
}

// Watermark preset managementAPI
export const watermarkApi = {
  getPresets: (): Promise<WatermarkPreset[]> => api.get('/watermarks/presets'),
  createPreset: (formData: FormData): Promise<WatermarkPreset> => {
    return api.post('/watermarks/presets', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  updatePreset: (id: string, updates: Partial<WatermarkPreset>): Promise<WatermarkPreset> => {
    return api.put(`/watermarks/presets/${id}`, updates)
  },
  deletePreset: (id: string): Promise<{ success: boolean; message: string }> => {
    return api.delete(`/watermarks/presets/${id}`)
  }
}

// Speech recognition / Whisper Runtime and model management
export const speechApi = {
  getRuntimeStatus: (): Promise<WhisperRuntimeStatus> => api.get('/whisper/runtime-status'),
  installRuntime: (): Promise<{ started: boolean; message: string }> => api.post('/whisper/install'),
  uninstallRuntime: (): Promise<{ success: boolean; message: string }> => api.post('/whisper/uninstall'),
  getModels: (): Promise<WhisperModel[]> => api.get('/whisper-models'),
  downloadModel: (model: string): Promise<unknown> => api.post('/whisper-models/download', { model }),
  deleteModel: (model: string): Promise<unknown> => api.delete(`/whisper-models/${model}`),
}

export interface SubtitleWord {
  word: string
  startTime: number
  endTime: number
}

export interface SubtitleSegment {
  id?: string
  startTime: number
  endTime: number
  text: string
  words?: SubtitleWord[]
  index?: number
}

export interface SubtitleDataResponse {
  segments: SubtitleSegment[]
  total_duration: number
  word_count: number
  segment_count: number
}

export interface UpdateClipSubtitlesRequest {
  segments: SubtitleSegment[]
  caption_style?: string
  reburn_video?: boolean
  hook_title?: string
  show_hook_banner?: boolean
  aspect_ratio?: string
  dynamic_zoom?: boolean
  bgm_track?: string
  bgm_volume?: number
  sfx_enabled?: boolean
  custom_bgm_path?: string
}

// Subtitle editingAPI
export const subtitleApi = {
  getClipSubtitles: (projectId: string, clipId: string): Promise<SubtitleDataResponse> => {
    return api.get(`/subtitle-editor/${projectId}/clips/${clipId}/subtitles`)
  },
  updateClipSubtitles: (
    projectId: string,
    clipId: string,
    data: UpdateClipSubtitlesRequest
  ): Promise<{ success: boolean; message: string; reburned: boolean; srt_path?: string; ass_path?: string }> => {
    return api.put(`/subtitle-editor/${projectId}/clips/${clipId}/subtitles`, data)
  },
  getProjectSubtitles: (projectId: string): Promise<SubtitleDataResponse> => {
    return api.get(`/subtitle-editor/${projectId}/subtitles`)
  },
  updateProjectSubtitles: (
    projectId: string,
    segments: SubtitleSegment[]
  ): Promise<{ success: boolean; message: string; count: number }> => {
    return api.put(`/subtitle-editor/${projectId}/subtitles`, { segments })
  },
  getBgmTracks: (): Promise<{ success: boolean; tracks: Array<{ id: string; name: string; description: string; default_volume: number; is_custom?: boolean; path?: string }> }> => {
    return api.get(`/subtitle-editor/bgm-tracks`)
  },
  uploadCustomBgm: (file: File): Promise<{ success: boolean; message: string; track: { id: string; name: string; filename: string; path: string; default_volume: number } }> => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/subtitle-editor/upload-bgm`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },
  getExportSrtUrl: (projectId: string, clipId: string): string => {
    return `/api/v1/subtitle-editor/${projectId}/clips/${clipId}/export-srt`
  }
}

// Creator Bounty & Brand Campaigns API (Kettle & Fire Fasting Campaign)
export interface ApprovedSourceItem {
  id: string
  category: string
  title: string
  speaker: string
  url: string
  platform: string
  type: 'celebrity' | 'sponsor'
  recommended_use: string
}

export interface CampaignDetailsResponse {
  id: string
  name: string
  brand_name: string
  brand_tag: string
  min_duration_sec: number
  description: string
  preferred_structure: string
  tagging_requirements: {
    tiktok: string
    instagram: string
    youtube_shorts: string
  }
  hook_suggestions: string[]
  social_captions: string[]
  approved_sources: ApprovedSourceItem[]
}

export interface CampaignStitchPayload {
  campaign_id?: string
  title?: string
  hook_title: string
  caption_style?: string
  part_a_video_path: string
  part_a_srt_path?: string
  part_b_video_path: string
  part_b_srt_path?: string
}

export interface CampaignStitchResult {
  success: boolean
  clip_id: string
  title: string
  video_path: string
  duration: number
  aspect_ratio: string
  social_metadata: {
    tiktok: string
    instagram: string
    youtube_shorts: string
    required_tag: string
  }
  message: string
}

export const campaignApi = {
  getKettleFireCampaign: (): Promise<CampaignDetailsResponse> => {
    return api.get('/campaigns/kettle-fire')
  },
  stitchCampaignClip: (data: CampaignStitchPayload): Promise<CampaignStitchResult> => {
    return api.post('/campaigns/stitch', data)
  }
}

export default api
