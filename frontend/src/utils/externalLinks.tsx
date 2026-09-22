import React from 'react'

/**
 * External link handler
 * UnderneathTauriSafely open external link in environment
 */

// Detect if inTauriIn environment
const isTauri = () => {
  return typeof window !== 'undefined' && Boolean((window as any).__TAURI__ || (window as any).__TAURI_INTERNALS__)
}

/**
 * Open external link
 * @param url Link to openURL
 */
export const openExternalLink = async (url: string) => {
  try {
    if (isTauri()) {
      // UnderneathTauriEnvironment usingshell API
      const { open } = await import('@tauri-apps/plugin-shell')
      await open(url)
    } else {
      // UnderneathWebOpen normally in environment
      window.open(url, '_blank', 'noopener,noreferrer')
    }
  } catch (error) {
    console.error('Failed to open external link:', error)
    // Fallback to trywindow.open
    try {
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch (fallbackError) {
      console.error('Opening link fallback also failed:', fallbackError)
      // Last fallback: Copy link to clipboard
      try {
        await navigator.clipboard.writeText(url)
        alert(`Link copied to clipboard: ${url}`)
      } catch (clipboardError) {
        console.error('Failed to copy to clipboard:', clipboardError)
        alert(`Please open manually: ${url}`)
      }
    }
  }
}

/**
 * Create a clickable external link component
 * @param url Link address
 * @param text Display text
 * @param className CSSClass name
 */
export const ExternalLink: React.FC<{
  url: string
  text: string
  className?: string
}> = ({ url, text, className }) => {
  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    openExternalLink(url)
  }

  return (
    <a
      href={url}
      onClick={handleClick}
      className={className}
      style={{ 
        color: '#1890ff',
        cursor: 'pointer',
        textDecoration: 'underline'
      }}
    >
      {text}
    </a>
  )
}
