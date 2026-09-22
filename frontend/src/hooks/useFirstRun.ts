import { useState, useEffect } from 'react'

interface FirstRunState {
  isFirstRun: boolean
  isLoading: boolean
  hasCompleted: boolean
}

export const useFirstRun = () => {
  const [state, setState] = useState<FirstRunState>({
    isFirstRun: false,
    isLoading: true,
    hasCompleted: false
  })

  useEffect(() => {
    checkFirstRun()
  }, [])

  const checkFirstRun = async () => {
    try {
      console.log('Checking first-run state...')
      
      // Request with timeout
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 5000)
      
      try {
        const response = await fetch('/api/v1/settings/', {
          signal: controller.signal
        })
        clearTimeout(timeoutId)
        
        if (response.ok) {
          const settings = await response.json()
          console.log('Loaded settings:', settings)
          
          const hasApiKey = settings.api?.api_keys?.dashscope || 
                           settings.api?.api_keys?.openai ||
                           settings.api?.api_keys?.gemini ||
                           settings.api?.api_keys?.siliconflow
          
          console.log('API Key status:', hasApiKey)
          
          setState({
            isFirstRun: !hasApiKey,
            isLoading: false,
            hasCompleted: hasApiKey
          })
        } else {
          console.log('Settings API response failed:', response.status)
          setState({
            isFirstRun: true,
            isLoading: false,
            hasCompleted: false
          })
        }
      } catch (fetchError) {
        clearTimeout(timeoutId)
        if (fetchError instanceof Error && fetchError.name === 'AbortError') {
          console.log('API request timeout, assuming first run')
        } else {
          console.log('API request failed:', fetchError)
        }
        setState({
          isFirstRun: true,
          isLoading: false,
          hasCompleted: false
        })
      }
    } catch (error) {
      console.error('Failed to check first-run state:', error)
      setState({
        isFirstRun: true,
        isLoading: false,
        hasCompleted: false
      })
    }
  }

  const markCompleted = () => {
    setState(prev => ({
      ...prev,
      isFirstRun: false,
      hasCompleted: true
    }))
  }

  return {
    ...state,
    markCompleted,
    refresh: checkFirstRun
  }
}
