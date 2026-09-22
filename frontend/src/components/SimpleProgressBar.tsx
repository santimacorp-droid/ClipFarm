/**
 * Simplified progress bar component - based on fixed stages
 */

import React, { useEffect, useState } from 'react'
import { Progress, Card, Typography, Space, Tag, Tooltip } from 'antd'
import { 
  useSimpleProgressStore, 
  getStageDisplayName, 
  getStageColor, 
  isCompleted, 
  isFailed,
  SimpleProgress 
} from '../stores/useSimpleProgressStore'

const { Text } = Typography

interface SimpleProgressBarProps {
  projectId: string
  autoStart?: boolean
  pollingInterval?: number
  showDetails?: boolean
  onProgressUpdate?: (progress: SimpleProgress) => void
}

export const SimpleProgressBar: React.FC<SimpleProgressBarProps> = ({
  projectId,
  autoStart = true,
  pollingInterval = 2000,
  showDetails = true,
  onProgressUpdate
}) => {
  const { 
    getProgress, 
    startPolling, 
    stopPolling
  } = useSimpleProgressStore()

  const progress = getProgress(projectId)

  // 1-second elapsed timer (always counting during active runs)
  const [elapsed, setElapsed] = useState<number>(0)

  useEffect(() => {
    if (progress?.elapsed_seconds !== undefined && progress.elapsed_seconds > 0) {
      setElapsed(Math.round(progress.elapsed_seconds))
    }
  }, [progress?.elapsed_seconds])

  useEffect(() => {
    const isFinished = isCompleted(progress?.stage || '', progress?.status) || isFailed(progress?.message || '', progress?.status)
    if (isFinished) return

    const interval = setInterval(() => setElapsed(e => e + 1), 1000)
    return () => clearInterval(interval)
  }, [progress?.stage, progress?.status, progress?.message])

  const formatTime = (s: number) =>
    `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`

  // Start polling automatically
  useEffect(() => {
    if (autoStart && projectId) {
      startPolling([projectId], pollingInterval)
      
      return () => {
        stopPolling()
      }
    }
  }, [projectId, autoStart, pollingInterval, startPolling, stopPolling])

  // Notify parent component of progress update
  useEffect(() => {
    if (progress && onProgressUpdate) {
      onProgressUpdate(progress)
    }
  }, [progress, onProgressUpdate])

  // Display waiting status if no progress data is available
  if (!progress) {
    return (
      <Card size="small" style={{ margin: '8px 0' }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text type="secondary">Waiting to begin processing...</Text>
          <Progress 
            percent={0} 
            status="active" 
            strokeColor="#1890ff"
            showInfo={false}
          />
        </Space>
      </Card>
    )
  }

  const { stage, percent, message, ts } = progress
  const stageDisplayName = getStageDisplayName(stage)
  const stageColor = getStageColor(stage)
  const completed = isCompleted(stage, progress.status)
  const failed = isFailed(message, progress.status)

  // Overall percentage
  const effectiveOverallPercent = progress.overall_percent !== undefined 
    ? Math.round(progress.overall_percent) 
    : percent

  // Alive evaluation (heartbeat within 15 seconds)
  const lastHeartbeatSec = progress.last_heartbeat || ts || 0
  const heartbeatFresh = lastHeartbeatSec > 0 && ((Date.now() / 1000 - lastHeartbeatSec) < 15)
  const isAlive = (progress.is_alive !== false) && heartbeatFresh && !completed && !failed

  // Determine progress bar status
  let progressStatus: 'normal' | 'active' | 'success' | 'exception' = 'normal'
  if (failed) {
    progressStatus = 'exception'
  } else if (completed) {
    progressStatus = 'success'
  } else if (effectiveOverallPercent > 0) {
    progressStatus = 'active'
  }

  const hasGranular = progress.current_step !== undefined || Boolean(progress.step_name)

  return (
    <Card size="small" style={{ margin: '8px 0' }}>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.3; transform: scale(0.9); }
        }
        .dot-alive {
          color: #22c55e;
          display: inline-block;
          animation: pulse 1.5s infinite ease-in-out;
        }
        .dot-stuck {
          color: #ef4444;
          display: inline-block;
        }
        .progress-logs {
          font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
          font-size: 0.72rem;
          color: #94a3b8;
          background: rgba(15, 23, 42, 0.75);
          border: 1px solid rgba(51, 65, 85, 0.4);
          border-radius: 4px;
          padding: 6px 8px;
          max-height: 96px;
          overflow-y: auto;
          margin-top: 6px;
          line-height: 1.45;
        }
        .progress-logs .log-line {
          white-space: pre-wrap;
          word-break: break-word;
        }
        .substep-bar-container {
          width: 100%;
          height: 4px;
          background: rgba(148, 163, 184, 0.2);
          border-radius: 2px;
          overflow: hidden;
          margin-top: 4px;
        }
        .substep-bar {
          height: 100%;
          background: #1890ff;
          transition: width 0.3s ease;
        }
      `}</style>
      
      <Space direction="vertical" style={{ width: '100%' }}>
        {/* Header: Step / Stage & Elapsed Time */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space align="center" size={8}>
            {hasGranular ? (
              <Text strong style={{ fontSize: '13px' }}>
                Step {progress.current_step ?? 1} of {progress.total_steps ?? 6} — {progress.step_name || stageDisplayName}
              </Text>
            ) : (
              <Tag color={stageColor} style={{ margin: 0 }}>
                {stageDisplayName}
              </Tag>
            )}

            {/* Alive pulse indicator */}
            <Tooltip title={isAlive ? "Active & processing" : completed ? "Completed" : failed ? "Failed" : "Heartbeat timeout"}>
              {isAlive ? (
                <span className="dot-alive">●</span>
              ) : completed ? (
                <span style={{ color: '#52c41a' }}>✓</span>
              ) : (
                <span className="dot-stuck">●</span>
              )}
            </Tooltip>
          </Space>

          <Space align="center" size={8}>
            <Text type="secondary" style={{ fontFamily: 'monospace', fontSize: '12px' }}>
              {formatTime(elapsed)}
            </Text>
            <Text strong style={{ color: stageColor }}>
              {effectiveOverallPercent}%
            </Text>
          </Space>
        </div>

        {/* Primary Overall Progress bar */}
        <Progress
          percent={effectiveOverallPercent}
          status={progressStatus}
          strokeColor={stageColor}
          showInfo={false}
          size="small"
        />

        {/* Substep detail & Mini Progress Bar */}
        {progress.substep && (
          <div style={{ margin: '2px 0' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
              <Text type="secondary" style={{ fontSize: '12px' }}>
                {progress.substep}
              </Text>
              {progress.step_percent !== undefined && progress.step_percent > 0 && (
                <Text type="secondary" style={{ fontSize: '11px' }}>
                  Within step: {progress.step_percent}%
                </Text>
              )}
            </div>
            {progress.substep_total !== undefined && progress.substep_total > 0 && (
              <div className="substep-bar-container">
                <div 
                  className="substep-bar" 
                  style={{ 
                    width: `${Math.min(100, Math.max(0, ((progress.substep_current || 0) / progress.substep_total) * 100))}%` 
                  }} 
                />
              </div>
            )}
          </div>
        )}

        {/* Standard details if no substep */}
        {showDetails && !progress.substep && message && (
          <Text type="secondary" style={{ fontSize: '12px' }}>
            {message}
          </Text>
        )}

        {/* Recent logs console box */}
        {showDetails && progress.recent_logs && progress.recent_logs.length > 0 && (
          <div className="progress-logs">
            {progress.recent_logs.map((line, i) => (
              <div key={i} className="log-line">{line}</div>
            ))}
          </div>
        )}

        {/* Timestamp */}
        {showDetails && ts > 0 && !progress.recent_logs?.length && (
          <Text type="secondary" style={{ fontSize: '11px' }}>
            Update time: {new Date(ts * 1000).toLocaleTimeString()}
          </Text>
        )}
      </Space>
    </Card>
  )
}

// Batch progress display component
interface BatchProgressBarProps {
  projectIds: string[]
  autoStart?: boolean
  pollingInterval?: number
  showDetails?: boolean
  onProgressUpdate?: (projectId: string, progress: SimpleProgress) => void
}

export const BatchProgressBar: React.FC<BatchProgressBarProps> = ({
  projectIds,
  autoStart = true,
  pollingInterval = 2000,
  showDetails = true,
  onProgressUpdate
}) => {
  const { 
    getAllProgress, 
    startPolling, 
    stopPolling
  } = useSimpleProgressStore()

  const allProgress = getAllProgress()

  // Start polling automatically
  useEffect(() => {
    if (autoStart && projectIds.length > 0) {
      startPolling(projectIds, pollingInterval)
      
      return () => {
        stopPolling()
      }
    }
  }, [projectIds, autoStart, pollingInterval, startPolling, stopPolling])

  // Notify parent component of progress update
  useEffect(() => {
    if (onProgressUpdate) {
      projectIds.forEach(projectId => {
        const progress = allProgress[projectId]
        if (progress) {
          onProgressUpdate(projectId, progress)
        }
      })
    }
  }, [allProgress, projectIds, onProgressUpdate])

  return (
    <div>
      {projectIds.map(projectId => (
        <SimpleProgressBar
          key={projectId}
          projectId={projectId}
          autoStart={false} // Do not automatically start in batch mode
          showDetails={showDetails}
          onProgressUpdate={(progress) => onProgressUpdate?.(projectId, progress)}
        />
      ))}
    </div>
  )
}
