import { useEffect, useRef, useState } from 'react'
import { projectApi } from '../services/api'
import { Project, useProjectStore } from '../store/useProjectStore'

interface UseProjectPollingOptions {
  interval?: number // Polling interval, default10Seconds
  onProjectsUpdate?: (projects: Project[]) => void
  enabled?: boolean // Whether to enable polling
}

export const useProjectPolling = ({
  interval = 30000, // Default30seconds, reduce frequent requests
  onProjectsUpdate,
  enabled = true
}: UseProjectPollingOptions = {}) => {
  const [isPolling, setIsPolling] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [lastUpdateTime, setLastUpdateTime] = useState<number>(Date.now())

  const startPolling = (overrideInterval?: number) => {
    if (!enabled) return
    // Clear any existing timer before (re)starting
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }

    setIsPolling(true)

    const poll = async () => {
      try {
        // Skip poll while user is dragging
        const currentIsDragging = useProjectStore.getState().isDragging
        if (currentIsDragging) {
          console.log('Skipping poll: dragging in progress')
          return
        }

        console.log('Polling projects...')
        const projects = await projectApi.getProjects()

        const safeProjects = Array.isArray(projects) ? projects : []
        console.log(`Polled: ${safeProjects.length} projects`)

        // Consider a project "active" if it is processing OR pending (which
        // includes the downloading state before the video file lands on disk).
        const hasActiveProjects = safeProjects.some(p =>
          p.status === 'processing' ||
          p.status === 'pending'
        )

        if (onProjectsUpdate) {
          onProjectsUpdate(safeProjects)
        }

        setLastUpdateTime(Date.now())

        // Adaptive polling: fast while something is happening, stay stopped when idle.
        if (hasActiveProjects) {
          const targetInterval = 3000
          const currentInterval = overrideInterval ?? interval
          if (targetInterval !== currentInterval) {
            startPolling(targetInterval)
          } else if (!intervalRef.current) {
            intervalRef.current = setInterval(poll, targetInterval)
          }
        } else {
          stopPolling() // ensure it stays stopped, don't restart
          console.log('No active projects, stopped project polling')
        }
      } catch (error) {
        console.error('Polling error:', error)
      }
    }

    // Fire immediately. Interval is only scheduled if hasActiveProjects is true
    poll()
  }

  const stopPolling = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setIsPolling(false)
  }

  const refreshNow = async () => {
    try {
      const projects = await projectApi.getProjects()
      // EnsureprojectsIs array type
      const safeProjects = Array.isArray(projects) ? projects : []
      if (onProjectsUpdate) {
        onProjectsUpdate(safeProjects)
      }
      setLastUpdateTime(Date.now())
      return safeProjects
    } catch (error) {
      console.error('Manual refresh error:', error)
      throw error
    }
  }

  useEffect(() => {
    if (enabled) {
      startPolling()
    } else {
      stopPolling()
    }

    return () => {
      stopPolling()
    }
  }, [enabled, interval])

  return {
    isPolling,
    lastUpdateTime,
    startPolling,
    stopPolling,
    refreshNow
  }
}

export default useProjectPolling