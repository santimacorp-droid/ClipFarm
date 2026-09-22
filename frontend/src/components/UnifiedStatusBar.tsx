/**
 * Unified status bar component - replace old complex progress system
 * Support unified display of download in progress, processing in progress, completed states
 */

import React, { useEffect, useState } from 'react'
import { Progress, Typography } from 'antd'
import { useSimpleProgressStore, getStageDisplayName, getStageColor, isCompleted, isFailed } from '../stores/useSimpleProgressStore'

const { Text } = Typography

interface UnifiedStatusBarProps {
  projectId: string
  status: string
  downloadProgress?: number
  onStatusChange?: (status: string) => void
  onDownloadProgressUpdate?: (progress: number) => void
}

export const UnifiedStatusBar: React.FC<UnifiedStatusBarProps> = ({
  projectId,
  status,
  downloadProgress = 0,
  onStatusChange,
  onDownloadProgressUpdate
}) => {
  const { getProgress, startPolling, stopPolling } = useSimpleProgressStore()
  const [isPolling, setIsPolling] = useState(false)
  const [currentDownloadProgress, setCurrentDownloadProgress] = useState(downloadProgress)
  
  const progress = getProgress(projectId)

  // Poll based on state
  useEffect(() => {
    // Stop polling if already terminal
    if (progress && (isCompleted(progress.stage) || isFailed(progress.message))) {
      if (isPolling) {
        console.log(`Progress terminal, stopping polling: ${projectId}`)
        stopPolling()
        setIsPolling(false)
      }
      return
    }

    if ((status === 'processing' || status === 'pending') && !isPolling) {
      console.log(`Starting processing polling: ${projectId}`)
      startPolling([projectId], 5000)
      setIsPolling(true)
    } else if (status !== 'processing' && status !== 'pending' && isPolling) {
      console.log(`Stopping processing polling: ${projectId}`)
      stopPolling()
      setIsPolling(false)
    }

    return () => {
      if (isPolling) {
        console.log(`Cleaning up polling: ${projectId}`)
        stopPolling()
        setIsPolling(false)
      }
    }
  }, [status, projectId, isPolling, startPolling, stopPolling, progress])

  // Download progress polling
  useEffect(() => {
    if (status === 'downloading') {
      const pollDownloadProgress = async () => {
        try {
          const response = await fetch(`/api/v1/projects/${projectId}`)
          if (response.ok) {
            const projectData = await response.json()
            const cfg = projectData.processing_config || projectData.settings || {}
            const newProgress = cfg.download_progress ?? 0
            setCurrentDownloadProgress(newProgress)
            onDownloadProgressUpdate?.(newProgress)
            
            // If download complete, transition to processing
            if (newProgress >= 100) {
              setTimeout(() => {
                onStatusChange?.('processing')
              }, 1000)
            }
          } else {
            console.error('Failed to get project data:', response.status, response.statusText)
          }
        } catch (error) {
          console.error('Failed to get download progress:', error)
        }
      }

      // Fetch once immediately
      pollDownloadProgress()
      
      // Per5Poll once per second, reduce frequent requests
      const interval = setInterval(pollDownloadProgress, 5000)
      
      return () => clearInterval(interval)
    }
  }, [status, projectId, onDownloadProgressUpdate, onStatusChange])

  // Handle status change
  useEffect(() => {
    if (progress) {
      // On reaching terminal state, immediately stop polling and sync status
      if (isCompleted(progress.stage) || isFailed(progress.message)) {
        if (isPolling) {
          console.log(`Progress reached terminal state, stopping polling: ${projectId}`)
          stopPolling()
          setIsPolling(false)
        }
        if (onStatusChange) {
          onStatusChange(isCompleted(progress.stage) ? 'completed' : 'failed')
        }
      }
    }
  }, [progress, onStatusChange])

  // ===== Calm Premium Status display (see DESIGN.md)=====
  // In progress: fine progress line + Label + Right side mono Percentage
  const ProgressRow = ({ label, percent }: { label: string; percent: number }) => (
    <div style={{ width: '100%' }}>
      <div style={{ height: 4, background: 'var(--ac-line)', borderRadius: 999, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${Math.max(0, Math.min(100, percent))}%`, background: 'var(--ac-accent)', borderRadius: 999, transition: 'width .4s ease' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 9 }}>
        <span style={{ color: 'var(--ac-sub)', fontSize: 12.5 }}>{label}</span>
        <span className="ac-mono" style={{ color: 'var(--ac-accent)', fontSize: 12.5 }}>{Math.round(percent)}%</span>
      </div>
    </div>
  )
  // Terminal state: small dot + Label
  const StatusRow = ({ label, dot, color }: { label: string; dot: string; color: string }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, height: 4 + 9 + 12.5 + 2, minHeight: 26 }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: dot, flex: '0 0 auto' }} />
      <span style={{ color, fontSize: 12.5 }}>{label}</span>
    </div>
  )

  if (status === 'importing') return <ProgressRow label="Importing" percent={downloadProgress} />
  if (status === 'downloading') return <ProgressRow label="Downloading" percent={currentDownloadProgress} />

  if (status === 'processing') {
    if (!progress) return <ProgressRow label="Initializing" percent={0} />
    const { stage, percent, message } = progress
    if (isFailed(message)) return <StatusRow label="Failed" dot="var(--ac-error)" color="var(--ac-error)" />
    return <ProgressRow label={getStageDisplayName(stage)} percent={percent} />
  }

  if (status === 'completed') return <StatusRow label="Completed" dot="var(--ac-ok)" color="var(--ac-sub)" />
  if (status === 'failed') return <StatusRow label="Failed" dot="var(--ac-error)" color="var(--ac-error)" />

  // Pending
  return <StatusRow label="Pending" dot="var(--ac-muted)" color="var(--ac-muted)" />
}

// Simplified progress bar component - for detailed progress display
interface SimpleProgressDisplayProps {
  projectId: string
  status: string
  showDetails?: boolean
}

export const SimpleProgressDisplay: React.FC<SimpleProgressDisplayProps> = ({
  projectId,
  status,
  showDetails = false
}) => {
  const { getProgress } = useSimpleProgressStore()
  const progress = getProgress(projectId)

  if (status !== 'processing' || !progress || !showDetails) {
    return null
  }

  const { stage, percent, message } = progress
  const stageColor = getStageColor(stage)

  return (
    <div style={{ marginTop: '8px' }}>
      <Progress
        percent={percent}
        strokeColor={stageColor}
        showInfo={true}
        size="small"
        format={(percent) => `${percent}%`}
      />
      {message && (
        <Text type="secondary" style={{ fontSize: '11px', display: 'block', marginTop: '4px' }}>
          {message}
        </Text>
      )}
    </div>
  )
}
