import { settingsApi } from '../services/api'
import { useApiModalStore } from '../store/useApiModalStore'
import { getLocalCredentials, saveLocalCredentials, hasValidLocalCredentials } from './localCredentials'

export interface ApiConfigStatus {
  hasValidConfig: boolean
  isOfflineMode: boolean
  provider: string
  model: string
  keyPresent: boolean
  displayLabel: string
  statusColor: 'green' | 'blue' | 'orange' | 'red'
}

export const PROVIDER_NAMES: Record<string, string> = {
  gemini: 'Google Gemini',
  openai: 'OpenAI',
  anthropic: 'Anthropic Claude',
  deepseek: 'DeepSeek',
  ollama: 'Ollama (Local)',
  lmstudio: 'LM Studio (Local)',
  dashscope: 'Alibaba Qwen',
  siliconflow: 'SiliconFlow',
  groq: 'Groq',
  openrouter: 'OpenRouter',
  custom: 'Custom LLM',
  offline_heuristic: 'Offline Heuristics'
}

/**
 * Checks whether an AI provider is configured and has an active API key,
 * checking BOTH local browser storage and backend settings.
 */
export async function checkApiConfig(): Promise<ApiConfigStatus> {
  // 1. Check if user explicitly selected offline heuristic fallback
  const offlineMode = localStorage.getItem('clipfarm_ai_mode') === 'offline_heuristic'
  if (offlineMode) {
    return {
      hasValidConfig: true,
      isOfflineMode: true,
      provider: 'offline_heuristic',
      model: 'Built-in Heuristic Engine',
      keyPresent: true,
      displayLabel: 'Offline Heuristics (No Key Required)',
      statusColor: 'blue'
    }
  }

  // 2. Read local credentials
  const localCreds = getLocalCredentials()
  const localValid = hasValidLocalCredentials()

  // 3. Try to query backend settings to reconcile
  let backendSettings: any = null
  try {
    backendSettings = await settingsApi.getSettings()
  } catch (err) {
    // Backend may be starting or offline
  }

  const backendProvider = (backendSettings?.api?.llm_provider || '').trim()
  const backendKeys = backendSettings?.api?.api_keys || {}
  const backendKey = (backendKeys[backendProvider] || '').trim()
  const backendModel = backendSettings?.api?.api_model || ''
  const backendBaseUrl = backendSettings?.api?.custom_base_url || ''

  // Determine active provider
  const provider = localCreds.provider || backendProvider || ''
  const model = localCreds.model || backendModel || ''
  const baseUrl = localCreds.baseUrl || backendBaseUrl || ''
  const rawKey = localCreds.apiKeys[provider] || backendKeys[provider] || backendKey || ''

  // If local credentials exist but backend doesn't have them yet, sync to backend in background
  if (localValid && backendSettings && (!backendKeys[provider] || backendKeys[provider] !== localCreds.apiKeys[provider])) {
    try {
      const mergedKeys = {
        ...backendKeys,
        ...localCreds.apiKeys
      }
      settingsApi.updateSettings({
        ...backendSettings,
        api: {
          ...backendSettings.api,
          api_keys: mergedKeys,
          llm_provider: provider,
          api_model: model || backendModel,
          custom_base_url: baseUrl
        }
      }).catch(() => {})
    } catch {
      // ignore background sync errors
    }
  }

  // If backend has keys but localStorage was empty, populate localStorage
  if (backendKey && !localCreds.apiKeys[provider]) {
    saveLocalCredentials({
      provider: backendProvider || provider,
      model: backendModel,
      apiKey: backendKey,
      baseUrl: backendBaseUrl,
      allKeys: backendKeys
    })
  }

  // Check validity
  if (!provider) {
    return {
      hasValidConfig: false,
      isOfflineMode: false,
      provider: '',
      model: '',
      keyPresent: false,
      displayLabel: 'AI Engine: Not Configured',
      statusColor: 'orange'
    }
  }

  // Local offline providers do not strictly require an API key
  if (provider === 'ollama' || provider === 'lmstudio') {
    const name = PROVIDER_NAMES[provider] || provider
    return {
      hasValidConfig: true,
      isOfflineMode: false,
      provider,
      model: model || 'local',
      keyPresent: true,
      displayLabel: `${name} (${model || 'default'})`,
      statusColor: 'green'
    }
  }

  // Custom OpenAI compatible endpoint requires base_url
  if (provider === 'custom') {
    const hasBaseUrl = Boolean(baseUrl.trim())
    return {
      hasValidConfig: hasBaseUrl,
      isOfflineMode: false,
      provider,
      model: model || 'custom',
      keyPresent: hasBaseUrl,
      displayLabel: hasBaseUrl ? `Custom API (${baseUrl})` : 'Custom API (Missing Base URL)',
      statusColor: hasBaseUrl ? 'green' : 'orange'
    }
  }

  // Check for dummy or placeholder keys
  const isDummyKey = 
    rawKey.startsWith('sk-ws-H.DDHHMIL') || 
    rawKey.startsWith('AQ.Ab8RN6') || 
    rawKey === 'sk-test' ||
    rawKey.length < 6

  const keyPresent = Boolean(rawKey) && !isDummyKey
  const name = PROVIDER_NAMES[provider] || provider

  if (keyPresent || localValid) {
    return {
      hasValidConfig: true,
      isOfflineMode: false,
      provider,
      model,
      keyPresent: true,
      displayLabel: `${name} (${model || 'Active'})`,
      statusColor: 'green'
    }
  } else {
    return {
      hasValidConfig: false,
      isOfflineMode: false,
      provider,
      model,
      keyPresent: false,
      displayLabel: `${name} (Key Missing or Invalid)`,
      statusColor: 'orange'
    }
  }
}

/**
 * Validates API configuration before performing an action (e.g. adding or editing video).
 * If valid, invokes `onProceed` (if provided) and returns true.
 * If not configured, prompts the user with the ApiConfigModal and queues `onProceed` to run after setup.
 */
export async function validateApiConfig(options?: {
  actionName?: string
  onProceed?: () => void
}): Promise<boolean> {
  const status = await checkApiConfig()

  if (status.hasValidConfig) {
    if (options?.onProceed) {
      options.onProceed()
    }
    return true
  }

  // Not configured: trigger prompt modal
  const actionText = options?.actionName ? ` Before ${options.actionName}` : ''
  useApiModalStore.getState().openModal({
    title: `AI Engine Setup Required${actionText}`,
    description: `ClipFarm requires an AI model to detect viral hooks, score climax moments, and format subtitles. Please select an AI provider and enter your API key, or choose the built-in offline engine to continue.`,
    onSuccess: options?.onProceed
  })

  return false
}

// Backward-compatible alias
export const validateApiConfigBeforeProjectCreation = validateApiConfig
