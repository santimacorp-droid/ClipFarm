/**
 * Submission-relatedAPIService
 */

import api from './api'

// Type definition
export interface BilibiliAccount {
  id: string
  username: string
  nickname?: string
  status: string
  is_default: boolean
  created_at: string
}

export interface UploadRequest {
  clip_ids: string[]
  account_id: string
  title: string
  description: string
  tags: string[]
  partition_id: number
}

export interface UploadRecord {
  id: string | number
  task_id?: string
  project_id?: string
  account_id: string | number
  clip_id: string
  title: string
  description?: string
  tags?: string
  partition_id: number
  video_path?: string
  bv_id?: string
  av_id?: string
  status: string
  error_message?: string
  progress: number
  file_size?: number
  upload_duration?: number
  created_at: string
  updated_at: string
  account_username?: string
  account_nickname?: string
  project_name?: string
}

export interface UploadStatus {
  id: string
  status: string
  bvid?: string
  error_message?: string
  created_at: string
}

// BSite partition information - official versionAPIDocument update, primary main partition
export const BILIBILI_PARTITIONS = [
  { id: 1, name: "Animation/Cartoons" },
  { id: 4, name: "Games" },
  { id: 8, name: "Grue (Meme/Video Editing)" },
  { id: 3, name: "Music" },
  { id: 129, name: "Dance" },
  { id: 181, name: "Film & TV" },
  { id: 5, name: "Entertainment" },
  { id: 36, name: "knowledge" },
  { id: 188, name: "Science and technology, digital products" },
  { id: 202, name: "News/Information" },
  { id: 76, name: "Food" },
  { id: 138, name: "Mini Theater" },
  { id: 176, name: "Automobile" },
  { id: 155, name: "Fashion and cosmetics" },
  { id: 235, name: "Sports" },
  { id: 75, name: "Animals" },
  { id: 21, name: "vlog" },
  { id: 162, name: "Painting/Art" },
  { id: 207, name: "Artificial intelligence" },
  { id: 208, name: "Home decoration and real estate" },
  { id: 209, name: "Outdoor fashion and trend" },
  { id: 164, name: "Fitness" },
  { id: 161, name: "Manual" },
  { id: 165, name: "Travel & Outdoors" },
  { id: 158, name: "Rural Areas (Agriculture, Countryside, Farmers)" },
  { id: 159, name: "Parenting" },
  { id: 160, name: "Health" },
  { id: 163, name: "emotion" },
  { id: 22, name: "Daily life interests" },
  { id: 23, name: "Daily life experience" }
]

// SubmissionsAPI
export const uploadApi = {
  // Account management
  createAccount: async (username: string, password: string, nickname?: string, cookieContent?: string): Promise<BilibiliAccount> => {
    return api.post('/upload/accounts', { username, password, nickname, cookie_content: cookieContent })
  },

  // Get supported login methods
  getLoginMethods: async (): Promise<{methods: Array<{
    id: string,
    name: string,
    description: string,
    icon: string,
    recommended: boolean,
    risk_level: string
  }>}> => {
    return api.get('/upload/login-methods')
  },

  // Account password login
  passwordLogin: async (username: string, password: string, nickname?: string): Promise<BilibiliAccount> => {
    return api.post('/upload/password-login', { username, password, nickname })
  },

  // CookieImport login
  cookieLogin: async (cookies: Record<string, string>, nickname?: string): Promise<BilibiliAccount> => {
    return api.post('/upload/cookie-login', { cookies, nickname })
  },

  // Third-party login
  thirdPartyLogin: async (type: 'wechat' | 'qq', nickname?: string): Promise<{login_url: string, message: string}> => {
    return api.post('/upload/third-party-login', { type, nickname })
  },

  startQRLogin: async (nickname?: string): Promise<{session_id: string, status: string, message: string}> => {
    return api.post('/upload/qr-login', { nickname })
  },

  checkQRLoginStatus: async (sessionId: string): Promise<{session_id: string, status: string, message: string, qr_code?: string}> => {
    return api.get(`/upload/qr-login/${sessionId}`)
  },

  completeQRLogin: async (sessionId: string, nickname?: string): Promise<BilibiliAccount> => {
    return api.post(`/upload/qr-login/${sessionId}/complete`, { nickname })
  },

  getAccounts: async (): Promise<BilibiliAccount[]> => {
    return api.get('/upload/accounts')
  },

  deleteAccount: async (accountId: string): Promise<void> => {
    return api.delete(`/upload/accounts/${accountId}`)
  },

  checkAccountStatus: async (accountId: string): Promise<{is_valid: boolean, message: string}> => {
    return api.post(`/upload/accounts/${accountId}/check`)
  },

  // Submission management
  createUploadTask: async (projectId: string, uploadData: UploadRequest): Promise<{message: string, record_id: string, clip_count: number}> => {
    return api.post(`/upload/projects/${projectId}/upload`, uploadData)
  },

  retryUploadTask: async (recordId: string): Promise<{message: string}> => {
    return api.post(`/upload/records/${recordId}/retry`)
  },

  cancelUploadTask: async (recordId: string): Promise<{message: string}> => {
    return api.post(`/upload/records/${recordId}/cancel`)
  },

  getUploadRecords: async (projectId?: string): Promise<UploadRecord[]> => {
    const params = projectId ? { project_id: projectId } : {}
    return api.get('/upload/records', { params })
  },

  getUploadRecord: async (recordId: string): Promise<UploadStatus> => {
    return api.get(`/upload/records/${recordId}`)
  },

  getBilibiliAccounts: async (): Promise<BilibiliAccount[]> => {
    return api.get('/upload/accounts')
  },

  // Submission task management
  retryUpload: async (recordId: string | number): Promise<{message: string}> => {
    return api.post(`/upload/records/${recordId}/retry`)
  },

  cancelUpload: async (recordId: string | number): Promise<{message: string}> => {
    return api.post(`/upload/records/${recordId}/cancel`)
  },

  deleteUpload: async (recordId: string | number): Promise<{message: string}> => {
    return api.delete(`/upload/records/${recordId}`)
  }
}
