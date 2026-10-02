/**
 * Local Credentials Storage Utility
 * Manages persisting AI Provider API keys and model configurations locally in the browser's localStorage.
 * Ensures credentials survive page reloads, work offline, and sync with backend settings.
 */

export interface LocalAiCredentials {
  provider: string
  model: string
  apiKey: string
  baseUrl?: string
  apiKeys: Record<string, string>
}

const STORAGE_KEYS = {
  PROVIDER: 'clipfarm_llm_provider',
  MODEL: 'clipfarm_api_model',
  BASE_URL: 'clipfarm_custom_base_url',
  API_KEYS: 'clipfarm_api_keys',
  CONFIGURED: 'clipfarm_api_configured',
  AI_MODE: 'clipfarm_ai_mode'
}

/**
 * Retrieves all locally saved AI credentials from localStorage
 */
export function getLocalCredentials(): LocalAiCredentials {
  const provider = localStorage.getItem(STORAGE_KEYS.PROVIDER) || 'gemini'
  const model = localStorage.getItem(STORAGE_KEYS.MODEL) || ''
  const baseUrl = localStorage.getItem(STORAGE_KEYS.BASE_URL) || ''
  
  let apiKeys: Record<string, string> = {}
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.API_KEYS)
    if (raw) {
      apiKeys = JSON.parse(raw)
    }
  } catch (err) {
    console.warn('Failed to parse clipfarm_api_keys from localStorage:', err)
  }

  // Also check individual keys like clipfarm_api_key_<provider> for backwards compatibility
  for (const prov of ['gemini', 'openai', 'anthropic', 'deepseek', 'dashscope', 'groq', 'openrouter', 'siliconflow', 'custom', 'ollama', 'lmstudio']) {
    if (!apiKeys[prov]) {
      const legacyKey = localStorage.getItem(`clipfarm_api_key_${prov}`)
      if (legacyKey) {
        apiKeys[prov] = legacyKey
      }
    }
  }

  const apiKey = apiKeys[provider] || ''

  return {
    provider,
    model,
    apiKey,
    baseUrl,
    apiKeys
  }
}

/**
 * Saves AI provider credentials locally into localStorage
 */
export function saveLocalCredentials(options: {
  provider: string
  model?: string
  apiKey?: string
  baseUrl?: string
  allKeys?: Record<string, string>
}): void {
  const { provider, model, apiKey, baseUrl, allKeys } = options

  if (provider) {
    localStorage.setItem(STORAGE_KEYS.PROVIDER, provider)
  }

  if (model) {
    localStorage.setItem(STORAGE_KEYS.MODEL, model)
  }

  if (baseUrl !== undefined) {
    localStorage.setItem(STORAGE_KEYS.BASE_URL, baseUrl)
  }

  // Update apiKeys map
  const current = getLocalCredentials().apiKeys
  const updatedKeys = {
    ...current,
    ...(allKeys || {})
  }

  if (apiKey !== undefined && provider) {
    updatedKeys[provider] = apiKey
    // Also save individual key for backward compatibility
    localStorage.setItem(`clipfarm_api_key_${provider}`, apiKey)
  }

  localStorage.setItem(STORAGE_KEYS.API_KEYS, JSON.stringify(updatedKeys))
  localStorage.setItem(STORAGE_KEYS.CONFIGURED, 'true')
  localStorage.removeItem(STORAGE_KEYS.AI_MODE) // Clear heuristic mode when real config is saved

  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('clipfarm_credentials_updated', {
      detail: { provider, model, apiKey, baseUrl }
    }))
  }
}

/**
 * Sets the AI mode to offline heuristic
 */
export function setHeuristicMode(): void {
  localStorage.setItem(STORAGE_KEYS.AI_MODE, 'offline_heuristic')
  localStorage.setItem(STORAGE_KEYS.CONFIGURED, 'true')
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('clipfarm_credentials_updated', {
      detail: { provider: 'offline_heuristic' }
    }))
  }
}

/**
 * Checks if local credentials are valid for a given or currently active provider
 */
export function hasValidLocalCredentials(targetProvider?: string): boolean {
  if (localStorage.getItem(STORAGE_KEYS.AI_MODE) === 'offline_heuristic') {
    return true
  }

  const creds = getLocalCredentials()
  const prov = targetProvider || creds.provider

  if (!prov) return false

  // Local engines don't strictly require an API key
  if (prov === 'ollama' || prov === 'lmstudio') {
    return true
  }

  if (prov === 'custom') {
    return Boolean(creds.baseUrl && creds.baseUrl.trim())
  }

  const key = creds.apiKeys[prov] || ''
  if (!key || key.trim() === '') return false

  // Check dummy or invalid placeholders
  if (key.startsWith('sk-ws-H.DDHHMIL') || key.startsWith('AQ.Ab8RN6') || key === 'sk-test' || key.length < 6) {
    return false
  }

  return true
}

/**
 * Clear all locally stored AI credentials
 */
export function clearLocalCredentials(): void {
  localStorage.removeItem(STORAGE_KEYS.PROVIDER)
  localStorage.removeItem(STORAGE_KEYS.MODEL)
  localStorage.removeItem(STORAGE_KEYS.BASE_URL)
  localStorage.removeItem(STORAGE_KEYS.API_KEYS)
  localStorage.removeItem(STORAGE_KEYS.CONFIGURED)
  localStorage.removeItem(STORAGE_KEYS.AI_MODE)
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('clipfarm_credentials_updated'))
  }
}

export interface LocalPlatformHandles {
  tiktok?: string
  youtube_shorts?: string
  instagram?: string
  facebook?: string
}

/**
 * Retrieves saved social handles per platform
 */
export function getLocalPlatformHandles(): LocalPlatformHandles {
  try {
    const raw = localStorage.getItem('clipfarm_platform_handles')
    if (raw) {
      return JSON.parse(raw)
    }
  } catch (err) {
    console.warn('Failed to parse clipfarm_platform_handles from localStorage:', err)
  }
  return {
    tiktok: '',
    youtube_shorts: '',
    instagram: '',
    facebook: ''
  }
}

/**
 * Saves social handles per platform locally into localStorage
 */
export function saveLocalPlatformHandles(handles: LocalPlatformHandles): void {
  localStorage.setItem('clipfarm_platform_handles', JSON.stringify(handles))
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('clipfarm_platform_handles_updated', { detail: handles }))
  }
}

