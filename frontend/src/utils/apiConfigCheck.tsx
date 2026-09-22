/**
 * APIConfiguration checker
 * Used to check before project creationAPIIs configuration complete?
 */

import { settingsApi } from '../services/api'
import { isDesktopMode } from './desktopMode'
import { message, Modal } from 'antd'
import { useNavigate } from 'react-router-dom'

export interface ApiConfigStatus {
  hasValidConfig: boolean
  missingProviders: string[]
  currentProvider?: string
  currentApiKey?: string
}

/**
 * CheckAPIIs configuration complete?
 */
export const checkApiConfig = async (): Promise<ApiConfigStatus> => {
  try {
    console.log('=== StartAPIConfiguration check ===')
    
    // Check whether inDesktopRunning in mode
    const isDesktop = await isDesktopMode()
    console.log('DesktopMode check result:', isDesktop)
    
    // Whether or not inDesktopIn all patterns, attempt to get settings
    let settings
    try {
      settings = await settingsApi.getSettings()
      console.log('Setting saved successfully:', settings)
    } catch (error) {
      console.warn('Failed to get settings, may not be inDesktopMode:', error)
      // If getting settings fails, check whether it's inDesktopMode
      if (!isDesktop) {
        console.log('NotDesktopPattern, returning no configuration state')
        return {
          hasValidConfig: false,
          missingProviders: ['LLM API'],
          currentProvider: undefined,
          currentApiKey: undefined
        }
      }
      // DesktopIn pattern, failed to get settings, also return no configuration
      console.log('DesktopIn pattern, failed to get settings, returning no configuration state')
      return {
        hasValidConfig: false,
        missingProviders: ['LLM API'],
        currentProvider: undefined,
        currentApiKey: undefined
      }
    }
    
    if (!settings || !settings.api || !settings.api.api_keys) {
      console.log('Setting data is incomplete:', { settings, hasApi: !!settings?.api, hasApiKeys: !!settings?.api?.api_keys })
      return {
        hasValidConfig: false,
        missingProviders: ['LLM API'],
        currentProvider: undefined,
        currentApiKey: undefined
      }
    }

    const apiKeys = settings.api.api_keys
    // Fix: api_model A model name, not a provider name
    // Need to get from api_provider Or llm_provider Get provider name
    const currentProvider = settings.api.api_provider || settings.api.llm_provider || 'dashscope'
    
    console.log('API config details:', {
      currentProvider,
      apiKeys: {
        dashscope: apiKeys.dashscope ? '***' + apiKeys.dashscope.slice(-4) : 'Not configured',
        openai: apiKeys.openai ? '***' + apiKeys.openai.slice(-4) : 'Not configured',
        gemini: apiKeys.gemini ? '***' + apiKeys.gemini.slice(-4) : 'Not configured',
        siliconflow: apiKeys.siliconflow ? '***' + apiKeys.siliconflow.slice(-4) : 'Not configured',
        jimeng_access: apiKeys.jimeng_access ? '***' + apiKeys.jimeng_access.slice(-4) : 'Not configured',
        jimeng_secret: apiKeys.jimeng_secret ? '***' + apiKeys.jimeng_secret.slice(-4) : 'Not configured'
      }
    })
    
    // Check for current provider'sAPI Key
    let currentApiKey = ''
    let hasValidKey = false
    
    switch (currentProvider) {
      case 'dashscope':
        currentApiKey = apiKeys.dashscope || ''
        hasValidKey = !!currentApiKey.trim()
        console.log('DashScope API KeyCheck:', { hasKey: !!currentApiKey, keyLength: currentApiKey.length, isValid: hasValidKey })
        break
      case 'openai':
        currentApiKey = apiKeys.openai || ''
        hasValidKey = !!currentApiKey.trim()
        console.log('OpenAI API KeyCheck:', { hasKey: !!currentApiKey, keyLength: currentApiKey.length, isValid: hasValidKey })
        break
      case 'gemini':
        currentApiKey = apiKeys.gemini || ''
        hasValidKey = !!currentApiKey.trim()
        console.log('Gemini API KeyCheck:', { hasKey: !!currentApiKey, keyLength: currentApiKey.length, isValid: hasValidKey })
        break
      case 'siliconflow':
        currentApiKey = apiKeys.siliconflow || ''
        hasValidKey = !!currentApiKey.trim()
        console.log('SiliconFlow API KeyCheck:', { hasKey: !!currentApiKey, keyLength: currentApiKey.length, isValid: hasValidKey })
        break
      case 'jimeng':
        currentApiKey = apiKeys.jimeng_access || ''
        hasValidKey = !!(apiKeys.jimeng_access?.trim() && apiKeys.jimeng_secret?.trim())
        console.log('Jimeng API KeyCheck:', { 
          hasAccess: !!apiKeys.jimeng_access, 
          hasSecret: !!apiKeys.jimeng_secret, 
          isValid: hasValidKey 
        })
        break
      default:
        hasValidKey = false
        console.log('Unknown provider:', currentProvider)
    }

    console.log('=== APIFinal result of configuration check ===', {
      hasValidConfig: hasValidKey,
      currentProvider,
      currentApiKey: currentApiKey ? '***' + currentApiKey.slice(-4) : undefined,
      isDesktop
    })

    return {
      hasValidConfig: hasValidKey,
      missingProviders: hasValidKey ? [] : ['LLM API'],
      currentProvider,
      currentApiKey: currentApiKey ? '***' + currentApiKey.slice(-4) : undefined
    }
  } catch (error) {
    console.error('CheckAPIConfiguration failed:', error)
    return {
      hasValidConfig: false,
      missingProviders: ['LLM API'],
      currentProvider: undefined,
      currentApiKey: undefined
    }
  }
}

/**
 * ShowAPIConfiguration missing dialog box
 */
export const showApiConfigModal = (missingProviders: string[], onNavigateToSettings?: () => void) => {
  const providerNames = {
    'LLM API': 'AI Model API (e.g. Qwen / OpenAI)',
    'Speech API': 'Speech Recognition API'
  }

  const missingNames = missingProviders.map(p => providerNames[p as keyof typeof providerNames] || p).join(', ')

  Modal.confirm({
    title: <span style={{ color: '#fff' }}>API Configuration Required</span>,
    content: (
      <div style={{ color: '#fff' }}>
        <p style={{ color: '#fff', marginBottom: '12px', fontSize: '14px' }}>Project processing requires configuring the following:</p>
        <p style={{ fontWeight: 'bold', color: '#40a9ff', marginBottom: '12px', fontSize: '16px' }}>{missingNames}</p>
        <p style={{ color: '#f0f0f0', fontSize: '14px' }}>Please go to Settings to configure your API key.</p>
      </div>
    ),
    okText: 'Go to Settings',
    cancelText: 'Cancel',
    onOk: () => {
      if (onNavigateToSettings) {
        onNavigateToSettings()
      } else {
        // Redirect directly to settings page
        window.location.href = '#/settings'
        // Force refresh page to ensure redirect takes effect
        window.location.reload()
      }
    },
    icon: null,
    centered: true,
    style: { backgroundColor: '#1f1f1f' }
  })
}

/**
 * Before project creation, checkAPIConfiguration
 * If configuration is incomplete, show prompt and block creation
 */
export const validateApiConfigBeforeProjectCreation = async (): Promise<boolean> => {
  console.log('Validating API config...')
  const configStatus = await checkApiConfig()
  
  console.log('API config validation status:', configStatus)
  
  if (!configStatus.hasValidConfig) {
    console.log('API config invalid, showing modal')
    showApiConfigModal(configStatus.missingProviders)
    return false
  }
  
  console.log('API config valid, allowing project creation')
  return true
}

/**
 * GetAPIFriendly description of configuration status
 */
export const getApiConfigDescription = (status: ApiConfigStatus): string => {
  if (status.hasValidConfig) {
    return `${status.currentProvider} API configured`
  } else {
    return 'API not configured, cannot process projects'
  }
}
